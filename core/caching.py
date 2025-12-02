#!/usr/bin/env python3
"""
Redis Caching Layer for Trading System
Provides high-performance caching for frequently accessed data
"""

import base64
import dataclasses
import io
import pickle
import hashlib
import json
import logging
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import wraps
from typing import Any, Dict, List, Optional, Union

import redis

logger = logging.getLogger(__name__)

try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - numpy optional
    np = None


_TYPE_KEY = "__type__"


def _default_serializer(value: Any) -> Dict[str, Any]:
    """JSON serializer that avoids unsafe pickle usage."""
    if isinstance(value, (datetime, date)):
        return {_TYPE_KEY: "datetime", "value": value.isoformat()}
    if isinstance(value, Decimal):
        return {_TYPE_KEY: "decimal", "value": str(value)}
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, set):
        return {_TYPE_KEY: "set", "value": list(value)}
    if isinstance(value, tuple):
        return {_TYPE_KEY: "tuple", "value": list(value)}
    if isinstance(value, bytes):
        return {_TYPE_KEY: "bytes", "value": base64.b64encode(value).decode("ascii")}
    if np is not None and isinstance(value, np.ndarray):
        return {
            _TYPE_KEY: "ndarray",
            "value": base64.b64encode(value.tobytes()).decode("ascii"),
            "dtype": str(value.dtype),
            "shape": value.shape,
        }
    if hasattr(value, "to_dict"):
        return value.to_dict()
    raise TypeError(f"Unsupported cache value type: {type(value)!r}")


def _object_hook(obj: Dict[str, Any]) -> Any:
    """Rehydrate values encoded by _default_serializer."""
    type_tag = obj.get(_TYPE_KEY)
    if type_tag is None:
        return obj

    if type_tag == "datetime":
        return datetime.fromisoformat(obj["value"])
    if type_tag == "decimal":
        return Decimal(obj["value"])
    if type_tag == "set":
        return set(obj["value"])
    if type_tag == "tuple":
        return tuple(obj["value"])
    if type_tag == "bytes":
        return base64.b64decode(obj["value"])
    if type_tag == "ndarray" and np is not None:
        raw = base64.b64decode(obj["value"])
        array = np.frombuffer(raw, dtype=np.dtype(obj["dtype"]))  # type: ignore[attr-defined]
        return array.reshape(obj["shape"])
    return obj

def _safe_pickle_loads(data: bytes) -> Any:
    """Safely deserialize limited pickle payloads for backward compatibility."""
    allowed_builtins = {
        'dict', 'list', 'set', 'tuple', 'str', 'int', 'float', 'bool', 'NoneType'
    }

    class SafeUnpickler(pickle.Unpickler):
        def find_class(self, module, name):
            if module == 'builtins' and name in allowed_builtins:
                return super().find_class(module, name)
            raise pickle.UnpicklingError("Disallowed pickle type: {}.{}".format(module, name))

    try:
        return SafeUnpickler(io.BytesIO(data)).load()
    except Exception as exc:  # pragma: no cover - defensive
        raise pickle.UnpicklingError(str(exc)) from exc

class RedisCache:
    """
    Redis-based caching system for the trading platform
    
    Features:
    - Automatic serialization/deserialization
    - TTL support
    - Cache hit/miss tracking
    - Atomic operations
    - Pattern-based deletion
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        default_ttl: int = 300  # 5 minutes default
    ):
        """
        Initialize Redis connection
        
        Args:
            host: Redis server host
            port: Redis server port
            db: Redis database number
            password: Redis password (if authentication enabled)
            default_ttl: Default time-to-live in seconds
        """
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=False  # We'll handle encoding ourselves
        )
        
        self.default_ttl = default_ttl
        
        # Performance tracking
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
        
        # Test connection
        try:
            self.client.ping()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.error("Redis connection failed: %s", e)
            raise
    


    def _serialize(self, value: Any) -> bytes:
        """Serialize value for Redis storage using JSON metadata."""
        try:
            return json.dumps(value, default=_default_serializer, ensure_ascii=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise TypeError(f"Cache value is not serializable: {exc}") from exc

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from Redis."""
        try:
            return json.loads(data.decode("utf-8"), object_hook=_object_hook)
        except (json.JSONDecodeError, UnicodeDecodeError):
            try:
                return _safe_pickle_loads(data)
            except pickle.UnpicklingError as exc:
                raise ValueError("Cached data corrupted or in an unexpected format") from exc

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache
        
        Args:
            key: Cache key
            default: Default value if key not found
            
        Returns:
            Cached value or default
        """
        try:
            data = self.client.get(key)
            
            if data is None:
                self.stats["misses"] += 1
                return default
            
            self.stats["hits"] += 1
            return self._deserialize(data)
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error("Cache get error for key '%s': %s", key, e)
            return default
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (None = use default)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            data = self._serialize(value)
            ttl = ttl if ttl is not None else self.default_ttl
            
            if ttl > 0:
                self.client.setex(key, ttl, data)
            else:
                self.client.set(key, data)
            
            self.stats["sets"] += 1
            return True
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error("Cache set error for key '%s': %s", key, e)
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete key from cache
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            result = self.client.delete(key)
            self.stats["deletes"] += 1
            return result > 0
        except Exception as e:
            self.stats["errors"] += 1
            logger.error("Cache delete error for key '%s': %s", key, e)
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern
        
        Args:
            pattern: Pattern to match (e.g., "market:*")
            
        Returns:
            Number of keys deleted
        """
        try:
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception as e:
            self.stats["errors"] += 1
            logger.error("Cache delete pattern error for '%s': %s", pattern, e)
            return 0
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            return self.client.exists(key) > 0
        except Exception as e:
            self.stats["errors"] += 1
            return False
    
    def get_ttl(self, key: str) -> int:
        """Get time-to-live for key in seconds"""
        try:
            return self.client.ttl(key)
        except Exception as e:
            self.stats["errors"] += 1
            return -1
    
    def increment(self, key: str, amount: int = 1) -> int:
        """
        Increment numeric value atomically
        
        Args:
            key: Cache key
            amount: Amount to increment by
            
        Returns:
            New value after increment
        """
        try:
            return self.client.incrby(key, amount)
        except Exception as e:
            self.stats["errors"] += 1
            return 0
    
    def decrement(self, key: str, amount: int = 1) -> int:
        """Decrement numeric value atomically"""
        return self.increment(key, -amount)
    
    @contextmanager
    def lock(self, key: str, timeout: int = 10):
        """
        Distributed lock context manager
        
        Usage:
            with cache.lock("my_resource"):
                # Critical section
                pass
        """
        lock_key = f"lock:{key}"
        lock_acquired = False
        
        try:
            # Try to acquire lock
            lock_acquired = self.client.set(
                lock_key,
                "locked",
                nx=True,  # Only set if not exists
                ex=timeout  # Expire after timeout
            )
            
            if not lock_acquired:
                raise Exception(f"Could not acquire lock for {key}")
            
            yield
            
        finally:
            if lock_acquired:
                self.client.delete(lock_key)
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache performance statistics"""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.stats,
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2)
        }
    
    def flush_all(self):
        """Clear entire cache - USE WITH CAUTION!"""
        try:
            self.client.flushdb()
            logger.warning("Cache flushed - all data cleared")
        except Exception as e:
            logger.error("Cache flush error: %s", e)


# Decorator for caching function results
def cached(
    ttl: int = 300,
    key_prefix: str = "",
    cache_instance: Optional[RedisCache] = None
):
    """
    Decorator to cache function results
    
    Args:
        ttl: Time-to-live in seconds
        key_prefix: Prefix for cache key
        cache_instance: RedisCache instance (or use global)
        
    Usage:
        @cached(ttl=60, key_prefix="market")
        def get_quote(symbol):
            return expensive_api_call(symbol)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Use provided cache or global instance
            cache = cache_instance or global_cache
            
            if not cache:
                # No cache available, call function directly
                return func(*args, **kwargs)
            
            # Generate cache key from function name and arguments
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            
            cache_key = ":".join(filter(None, key_parts))
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Call function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator


# Global cache instance (initialized when needed)
global_cache: Optional[RedisCache] = None

def initialize_cache(
    host: str = "localhost",
    port: int = 6379,
    password: Optional[str] = None
) -> RedisCache:
    """Initialize global cache instance"""
    global global_cache
    global_cache = RedisCache(host=host, port=port, password=password)
    return global_cache


# Example usage classes
class MarketDataCache:
    """Cache for market data"""
    
    def __init__(self, cache: RedisCache):
        self.cache = cache
        self.prefix = "market"
    
    def get_quote(self, symbol: str) -> Optional[Dict]:
        """Get cached market quote"""
        key = f"{self.prefix}:quote:{symbol}"
        return self.cache.get(key)
    
    def set_quote(self, symbol: str, quote: Dict, ttl: int = 5):
        """Cache market quote (5 second TTL by default)"""
        key = f"{self.prefix}:quote:{symbol}"
        self.cache.set(key, quote, ttl=ttl)
    
    def get_ohlc(self, symbol: str, timeframe: str) -> Optional[List]:
        """Get cached OHLC data"""
        key = f"{self.prefix}:ohlc:{symbol}:{timeframe}"
        return self.cache.get(key)
    
    def set_ohlc(self, symbol: str, timeframe: str, data: List, ttl: int = 60):
        """Cache OHLC data (1 minute TTL by default)"""
        key = f"{self.prefix}:ohlc:{symbol}:{timeframe}"
        self.cache.set(key, data, ttl=ttl)
    
    def invalidate_symbol(self, symbol: str):
        """Invalidate all cached data for symbol"""
        pattern = f"{self.prefix}:*:{symbol}*"
        deleted = self.cache.delete_pattern(pattern)
        logger.info("Invalidated %d cache entries for %s", deleted, symbol)


class PortfolioCache:
    """Cache for portfolio and position data"""
    
    def __init__(self, cache: RedisCache):
        self.cache = cache
        self.prefix = "portfolio"
    
    def get_positions(self, user_id: str = "default") -> Optional[List]:
        """Get cached positions"""
        key = f"{self.prefix}:positions:{user_id}"
        return self.cache.get(key)
    
    def set_positions(self, positions: List, user_id: str = "default", ttl: int = 10):
        """Cache positions"""
        key = f"{self.prefix}:positions:{user_id}"
        self.cache.set(key, positions, ttl=ttl)
    
    def get_summary(self, user_id: str = "default") -> Optional[Dict]:
        """Get cached portfolio summary"""
        key = f"{self.prefix}:summary:{user_id}"
        return self.cache.get(key)
    
    def set_summary(self, summary: Dict, user_id: str = "default", ttl: int = 10):
        """Cache portfolio summary"""
        key = f"{self.prefix}:summary:{user_id}"
        self.cache.set(key, summary, ttl=ttl)
    
    def invalidate_portfolio(self, user_id: str = "default"):
        """Invalidate all portfolio cache for user"""
        pattern = f"{self.prefix}:*:{user_id}"
        self.cache.delete_pattern(pattern)


if __name__ == "__main__":
    # Example usage
    print("Testing Redis Cache System\n")
    
    # Initialize cache
    cache = RedisCache()
    
    # Test basic operations
    print("1. Basic Operations:")
    cache.set("test_key", {"value": 123}, ttl=60)
    print(f"  Set test_key: {cache.get('test_key')}")
    
    # Test market data caching
    print("\n2. Market Data Caching:")
    market_cache = MarketDataCache(cache)
    market_cache.set_quote("RELIANCE", {"ltp": 2500.50, "volume": 1000000})
    print(f"  Cached quote: {market_cache.get_quote('RELIANCE')}")
    
    # Test performance
    print("\n3. Cache Performance:")
    print(f"  Stats: {cache.get_stats()}")
    
    print("\n✅ Cache system ready!")
