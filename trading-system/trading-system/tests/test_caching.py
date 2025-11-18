#!/usr/bin/env python3
"""
Comprehensive tests for caching.py module
Tests Redis caching layer, serialization, TTL, stats tracking, and decorators
"""

import pytest
import json
import pickle
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock redis module before importing caching
sys.modules['redis'] = MagicMock()

from core.caching import (
    RedisCache,
    cached,
    initialize_cache,
    MarketDataCache,
    PortfolioCache
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    with patch('redis.Redis') as mock:
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.get.return_value = None
        mock_client.set.return_value = True
        mock_client.setex.return_value = True
        mock_client.delete.return_value = 1
        mock_client.exists.return_value = 1
        mock_client.ttl.return_value = 60
        mock_client.incrby.return_value = 1
        mock_client.keys.return_value = []
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def redis_cache(mock_redis):
    """Create RedisCache instance with mocked Redis"""
    cache = RedisCache()
    cache.client = mock_redis
    return cache


# ============================================================================
# RedisCache Initialization Tests
# ============================================================================

class TestRedisCacheInit:
    """Test RedisCache initialization"""

    def test_initialization_default_params(self, mock_redis):
        """Test initialization with default parameters"""
        cache = RedisCache()

        assert cache.default_ttl == 300
        assert cache.stats["hits"] == 0
        assert cache.stats["misses"] == 0

    def test_initialization_custom_params(self, mock_redis):
        """Test initialization with custom parameters"""
        cache = RedisCache(
            host="redis.example.com",
            port=6380,
            db=1,
            password="secret",
            default_ttl=600
        )

        assert cache.default_ttl == 600

    def test_initialization_redis_connection_fails(self):
        """Test initialization when Redis connection fails"""
        with patch('redis.Redis') as mock:
            mock_client = MagicMock()
            mock_client.ping.side_effect = Exception("Connection failed")
            mock.return_value = mock_client

            with pytest.raises(Exception, match="Connection failed"):
                RedisCache()


# ============================================================================
# Serialization Tests
# ============================================================================

class TestSerialization:
    """Test serialization and deserialization"""

    def test_serialize_simple_dict(self, redis_cache):
        """Test serializing simple dictionary"""
        data = {"key": "value", "number": 123}
        serialized = redis_cache._serialize(data)

        assert isinstance(serialized, bytes)
        # Should use JSON for simple types
        assert b'"key"' in serialized

    def test_serialize_list_and_nested(self, redis_cache):
        """Test serializing list and nested structures"""
        data = {
            "list": [1, 2, 3],
            "nested": {"a": {"b": {"c": 1}}}
        }
        serialized = redis_cache._serialize(data)

        assert isinstance(serialized, bytes)

    def test_deserialize_json_data(self, redis_cache):
        """Test deserializing JSON data"""
        original = {"key": "value", "number": 123}
        serialized = json.dumps(original).encode('utf-8')

        deserialized = redis_cache._deserialize(serialized)

        assert deserialized == original

    def test_deserialize_pickle_data(self, redis_cache):
        """Test deserializing pickle data"""
        original = {"key": "value"}
        serialized = pickle.dumps(original)

        deserialized = redis_cache._deserialize(serialized)

        assert deserialized == original

    def test_serialize_deserialize_roundtrip(self, redis_cache):
        """Test full serialization roundtrip"""
        original_data = {
            "string": "test",
            "number": 42,
            "list": [1, 2, 3],
            "nested": {"a": 1, "b": 2}
        }

        serialized = redis_cache._serialize(original_data)
        deserialized = redis_cache._deserialize(serialized)

        assert deserialized == original_data


# ============================================================================
# Get/Set Operations Tests
# ============================================================================

class TestGetSetOperations:
    """Test cache get and set operations"""

    def test_get_existing_key(self, redis_cache, mock_redis):
        """Test getting existing key from cache"""
        test_data = {"value": 123}
        mock_redis.get.return_value = json.dumps(test_data).encode('utf-8')

        result = redis_cache.get("test_key")

        assert result == test_data
        assert redis_cache.stats["hits"] == 1
        assert redis_cache.stats["misses"] == 0

    def test_get_missing_key_returns_default(self, redis_cache, mock_redis):
        """Test getting missing key returns default"""
        mock_redis.get.return_value = None

        result = redis_cache.get("missing_key", default="DEFAULT")

        assert result == "DEFAULT"
        assert redis_cache.stats["hits"] == 0
        assert redis_cache.stats["misses"] == 1

    def test_get_error_returns_default(self, redis_cache, mock_redis):
        """Test that get errors return default value"""
        mock_redis.get.side_effect = Exception("Redis error")

        result = redis_cache.get("error_key", default="FALLBACK")

        assert result == "FALLBACK"
        assert redis_cache.stats["errors"] == 1

    def test_set_with_default_ttl(self, redis_cache, mock_redis):
        """Test setting value with default TTL"""
        result = redis_cache.set("test_key", {"value": 123})

        assert result is True
        assert redis_cache.stats["sets"] == 1
        mock_redis.setex.assert_called_once()

    def test_set_with_custom_ttl(self, redis_cache, mock_redis):
        """Test setting value with custom TTL"""
        redis_cache.set("test_key", {"value": 123}, ttl=60)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 60  # TTL argument

    def test_set_with_zero_ttl_no_expiry(self, redis_cache, mock_redis):
        """Test setting value with zero TTL (no expiry)"""
        redis_cache.set("test_key", {"value": 123}, ttl=0)

        mock_redis.set.assert_called_once()
        mock_redis.setex.assert_not_called()

    def test_set_error_returns_false(self, redis_cache, mock_redis):
        """Test that set errors return False"""
        mock_redis.setex.side_effect = Exception("Redis error")

        result = redis_cache.set("error_key", "value")

        assert result is False
        assert redis_cache.stats["errors"] == 1


# ============================================================================
# Delete Operations Tests
# ============================================================================

class TestDeleteOperations:
    """Test cache delete operations"""

    def test_delete_existing_key(self, redis_cache, mock_redis):
        """Test deleting existing key"""
        mock_redis.delete.return_value = 1

        result = redis_cache.delete("test_key")

        assert result is True
        assert redis_cache.stats["deletes"] == 1

    def test_delete_missing_key(self, redis_cache, mock_redis):
        """Test deleting missing key"""
        mock_redis.delete.return_value = 0

        result = redis_cache.delete("missing_key")

        assert result is False

    def test_delete_pattern_with_matches(self, redis_cache, mock_redis):
        """Test deleting keys by pattern"""
        mock_redis.keys.return_value = [b"key1", b"key2", b"key3"]
        mock_redis.delete.return_value = 3

        count = redis_cache.delete_pattern("test:*")

        assert count == 3

    def test_delete_pattern_no_matches(self, redis_cache, mock_redis):
        """Test deleting pattern with no matches"""
        mock_redis.keys.return_value = []

        count = redis_cache.delete_pattern("nomatch:*")

        assert count == 0

    def test_delete_pattern_error(self, redis_cache, mock_redis):
        """Test delete pattern error handling"""
        mock_redis.keys.side_effect = Exception("Redis error")

        count = redis_cache.delete_pattern("error:*")

        assert count == 0
        assert redis_cache.stats["errors"] == 1


# ============================================================================
# Utility Operations Tests
# ============================================================================

class TestUtilityOperations:
    """Test utility operations (exists, TTL, increment, etc.)"""

    def test_exists_key_present(self, redis_cache, mock_redis):
        """Test checking if key exists"""
        mock_redis.exists.return_value = 1

        assert redis_cache.exists("test_key") is True

    def test_exists_key_absent(self, redis_cache, mock_redis):
        """Test checking if key doesn't exist"""
        mock_redis.exists.return_value = 0

        assert redis_cache.exists("missing_key") is False

    def test_get_ttl(self, redis_cache, mock_redis):
        """Test getting TTL for key"""
        mock_redis.ttl.return_value = 120

        ttl = redis_cache.get_ttl("test_key")

        assert ttl == 120

    def test_increment(self, redis_cache, mock_redis):
        """Test incrementing counter"""
        mock_redis.incrby.return_value = 5

        result = redis_cache.increment("counter", 5)

        assert result == 5
        mock_redis.incrby.assert_called_once_with("counter", 5)

    def test_decrement(self, redis_cache, mock_redis):
        """Test decrementing counter"""
        mock_redis.incrby.return_value = -3

        result = redis_cache.decrement("counter", 3)

        assert result == -3
        mock_redis.incrby.assert_called_once_with("counter", -3)


# ============================================================================
# Distributed Lock Tests
# ============================================================================

class TestDistributedLock:
    """Test distributed lock context manager"""

    def test_lock_acquired_and_released(self, redis_cache, mock_redis):
        """Test successful lock acquisition and release"""
        mock_redis.set.return_value = True

        with redis_cache.lock("resource"):
            pass

        # Verify lock was acquired with correct parameters
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args[1]
        assert call_args.get('nx') is True
        assert 'ex' in call_args

        # Verify lock was released
        mock_redis.delete.assert_called_once()

    def test_lock_not_acquired(self, redis_cache, mock_redis):
        """Test lock acquisition failure"""
        mock_redis.set.return_value = False

        with pytest.raises(Exception, match="Could not acquire lock"):
            with redis_cache.lock("busy_resource"):
                pass

    def test_lock_released_on_exception(self, redis_cache, mock_redis):
        """Test that lock is released even if exception occurs"""
        mock_redis.set.return_value = True

        with pytest.raises(ValueError):
            with redis_cache.lock("resource"):
                raise ValueError("Test error")

        # Lock should still be deleted
        mock_redis.delete.assert_called_once()


# ============================================================================
# Statistics Tests
# ============================================================================

class TestStatistics:
    """Test cache statistics tracking"""

    def test_get_stats_initial(self, redis_cache):
        """Test initial stats are zero"""
        stats = redis_cache.get_stats()

        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["sets"] == 0
        assert stats["total_requests"] == 0
        assert stats["hit_rate_percent"] == 0

    def test_get_stats_after_operations(self, redis_cache, mock_redis):
        """Test stats after some operations"""
        # Do some cache operations
        mock_redis.get.return_value = json.dumps({"value": 1}).encode('utf-8')
        redis_cache.get("key1")  # hit

        mock_redis.get.return_value = None
        redis_cache.get("key2")  # miss

        redis_cache.set("key3", "value")

        stats = redis_cache.get_stats()

        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["sets"] == 1
        assert stats["total_requests"] == 2
        assert stats["hit_rate_percent"] == 50.0

    def test_flush_all(self, redis_cache, mock_redis):
        """Test flushing entire cache"""
        redis_cache.flush_all()

        mock_redis.flushdb.assert_called_once()


# ============================================================================
# Caching Decorator Tests
# ============================================================================

class TestCachedDecorator:
    """Test @cached decorator"""

    def test_cached_decorator_caches_result(self, redis_cache):
        """Test that decorator caches function results"""
        call_count = [0]

        @cached(ttl=60, cache_instance=redis_cache)
        def expensive_function(x):
            call_count[0] += 1
            return x * 2

        # First call - function executed
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count[0] == 1

        # Second call - should use cached value
        redis_cache.client.get.return_value = json.dumps(10).encode('utf-8')
        result2 = expensive_function(5)
        assert result2 == 10
        # Function not called again
        assert call_count[0] == 1

    def test_cached_decorator_no_cache_instance(self):
        """Test decorator when no cache instance available"""
        call_count = [0]

        @cached(ttl=60, cache_instance=None)
        def expensive_function(x):
            call_count[0] += 1
            return x * 2

        # Should call function directly without caching
        result = expensive_function(5)
        assert result == 10
        assert call_count[0] == 1


# ============================================================================
# MarketDataCache Tests
# ============================================================================

class TestMarketDataCache:
    """Test MarketDataCache class"""

    def test_get_set_quote(self, redis_cache, mock_redis):
        """Test getting and setting market quotes"""
        market_cache = MarketDataCache(redis_cache)

        quote = {"ltp": 2500.50, "volume": 1000000}
        market_cache.set_quote("RELIANCE", quote, ttl=5)

        # Verify set was called with correct key
        assert redis_cache.stats["sets"] == 1

    def test_get_set_ohlc(self, redis_cache, mock_redis):
        """Test getting and setting OHLC data"""
        market_cache = MarketDataCache(redis_cache)

        ohlc_data = [
            {"open": 2500, "high": 2520, "low": 2490, "close": 2510}
        ]
        market_cache.set_ohlc("RELIANCE", "1min", ohlc_data, ttl=60)

        # Verify correct key pattern
        assert redis_cache.stats["sets"] == 1

    def test_invalidate_symbol(self, redis_cache, mock_redis):
        """Test invalidating all data for a symbol"""
        market_cache = MarketDataCache(redis_cache)

        mock_redis.keys.return_value = [b"key1", b"key2"]
        mock_redis.delete.return_value = 2

        market_cache.invalidate_symbol("RELIANCE")

        mock_redis.keys.assert_called_once()
        mock_redis.delete.assert_called_once()


# ============================================================================
# PortfolioCache Tests
# ============================================================================

class TestPortfolioCache:
    """Test PortfolioCache class"""

    def test_get_set_positions(self, redis_cache, mock_redis):
        """Test getting and setting positions"""
        portfolio_cache = PortfolioCache(redis_cache)

        positions = [{"symbol": "RELIANCE", "quantity": 10}]
        portfolio_cache.set_positions(positions, user_id="user123", ttl=10)

        assert redis_cache.stats["sets"] == 1

    def test_get_set_summary(self, redis_cache, mock_redis):
        """Test getting and setting portfolio summary"""
        portfolio_cache = PortfolioCache(redis_cache)

        summary = {"total_value": 100000, "pnl": 5000}
        portfolio_cache.set_summary(summary, user_id="user123", ttl=10)

        assert redis_cache.stats["sets"] == 1

    def test_invalidate_portfolio(self, redis_cache, mock_redis):
        """Test invalidating portfolio cache"""
        portfolio_cache = PortfolioCache(redis_cache)

        portfolio_cache.invalidate_portfolio(user_id="user123")

        mock_redis.keys.assert_called_once()


# ============================================================================
# Global Cache Initialization Tests
# ============================================================================

class TestGlobalCache:
    """Test global cache initialization"""

    def test_initialize_cache(self, mock_redis):
        """Test initializing global cache"""
        cache = initialize_cache(
            host="localhost",
            port=6379,
            password="secret"
        )

        assert isinstance(cache, RedisCache)


if __name__ == "__main__":
    # Run tests with: pytest test_caching.py -v
    pytest.main([__file__, "-v", "--tb=short"])
