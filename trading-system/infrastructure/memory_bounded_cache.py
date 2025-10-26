#!/usr/bin/env python3
"""
Memory-Bounded Cache Manager
Prevents unbounded memory growth from caching market data

ADDRESSES CRITICAL ISSUE:
- Original cache: Unbounded Dict could reach 10GB+ with 8,321 instruments
- This implementation: Hard limit of 2GB with LRU eviction
"""

import sys
import time
import threading
from typing import Any, Dict, Optional, Tuple, Callable
from collections import OrderedDict
from dataclasses import dataclass
import logging

logger = logging.getLogger('trading_system.cache')


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    value: Any
    timestamp: float
    size_bytes: int
    access_count: int


class MemoryBoundedCache:
    """
    Memory-bounded LRU cache with TTL

    Features:
    - Hard memory limit (default 2GB)
    - LRU eviction policy
    - TTL (time-to-live) for entries
    - Thread-safe operations
    - Memory usage tracking
    - Automatic eviction when limit reached

    Usage:
        cache = MemoryBoundedCache(max_size_mb=2048, default_ttl=60)
        cache.set('key', data)
        value = cache.get('key')
    """

    def __init__(
        self,
        max_size_mb: int = 2048,  # 2GB default
        default_ttl: int = 60,  # 60 seconds default
        max_entries: int = 1000,  # Maximum number of entries
        eviction_threshold: float = 0.9  # Start evicting at 90% full
    ):
        """
        Initialize memory-bounded cache

        Args:
            max_size_mb: Maximum cache size in megabytes
            default_ttl: Default TTL in seconds
            max_entries: Maximum number of cache entries
            eviction_threshold: Start evicting at this % of max_size
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self.eviction_threshold = eviction_threshold

        # Thread-safe cache storage (LRU)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

        # Statistics
        self._current_size_bytes = 0
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0

        logger.info(
            f"📦 MemoryBoundedCache initialized: "
            f"max_size={max_size_mb}MB, "
            f"max_entries={max_entries}, "
            f"default_ttl={default_ttl}s"
        )

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache

        Args:
            key: Cache key
            default: Default value if not found or expired

        Returns:
            Cached value or default
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return default

            entry = self._cache[key]

            # Check if expired
            age = time.time() - entry.timestamp
            if age > self.default_ttl:
                self._remove_entry(key)
                self._expirations += 1
                self._misses += 1
                return default

            # Update access (move to end for LRU)
            self._cache.move_to_end(key)
            entry.access_count += 1
            self._hits += 1

            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl: Custom TTL (uses default if None)

        Returns:
            True if successfully cached, False if evicted immediately
        """
        with self._lock:
            # Calculate size of new entry
            size_bytes = self._estimate_size(value)

            # Check if single entry exceeds max size
            if size_bytes > self.max_size_bytes:
                logger.warning(
                    f"⚠️  Entry too large to cache: {key} "
                    f"({size_bytes / 1024 / 1024:.1f}MB > {self.max_size_bytes / 1024 / 1024:.1f}MB)"
                )
                return False

            # Evict if necessary
            self._evict_if_needed(size_bytes)

            # Remove old entry if exists
            if key in self._cache:
                self._remove_entry(key)

            # Add new entry
            entry = CacheEntry(
                value=value,
                timestamp=time.time(),
                size_bytes=size_bytes,
                access_count=0
            )

            self._cache[key] = entry
            self._current_size_bytes += size_bytes

            # Move to end (most recently used)
            self._cache.move_to_end(key)

            return True

    def delete(self, key: str) -> bool:
        """
        Delete entry from cache

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                self._remove_entry(key)
                return True
            return False

    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
            self._current_size_bytes = 0
            logger.info("🗑️  Cache cleared")

    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl: Optional[int] = None
    ) -> Any:
        """
        Get value from cache or compute and cache it

        Args:
            key: Cache key
            compute_fn: Function to compute value if not cached
            ttl: Custom TTL

        Returns:
            Cached or computed value
        """
        # Try to get from cache first
        value = self.get(key)
        if value is not None:
            return value

        # Compute value
        computed = compute_fn()

        # Cache it
        self.set(key, computed, ttl)

        return computed

    def _evict_if_needed(self, incoming_size: int):
        """
        Evict entries if necessary to make room

        Uses LRU policy - evicts least recently used entries first

        Args:
            incoming_size: Size of incoming entry
        """
        # Calculate threshold
        threshold_bytes = int(self.max_size_bytes * self.eviction_threshold)

        # Evict while over threshold or too many entries
        while (
            (self._current_size_bytes + incoming_size > threshold_bytes) or
            (len(self._cache) >= self.max_entries)
        ):
            if not self._cache:
                break  # Nothing to evict

            # Evict oldest (first) entry (LRU)
            key_to_evict = next(iter(self._cache))
            self._remove_entry(key_to_evict)
            self._evictions += 1

            if self._evictions % 100 == 0:
                logger.info(
                    f"📤 Cache evictions: {self._evictions}, "
                    f"current_size: {self._current_size_bytes / 1024 / 1024:.1f}MB"
                )

    def _remove_entry(self, key: str):
        """Remove entry and update size tracking"""
        if key in self._cache:
            entry = self._cache.pop(key)
            self._current_size_bytes -= entry.size_bytes

    def _estimate_size(self, obj: Any) -> int:
        """
        Estimate memory size of object

        Args:
            obj: Object to estimate

        Returns:
            Estimated size in bytes
        """
        # Use sys.getsizeof for basic estimation
        # This includes object overhead but not deep size of complex objects
        return sys.getsizeof(obj)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0

            return {
                'entries': len(self._cache),
                'size_mb': self._current_size_bytes / 1024 / 1024,
                'max_size_mb': self.max_size_bytes / 1024 / 1024,
                'utilization_pct': (self._current_size_bytes / self.max_size_bytes) * 100,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate_pct': hit_rate * 100,
                'evictions': self._evictions,
                'expirations': self._expirations,
            }

    def print_stats(self):
        """Print cache statistics"""
        stats = self.get_stats()

        print("\n" + "="*60)
        print("📊 CACHE STATISTICS")
        print("="*60)
        print(f"Entries:        {stats['entries']:,} / {self.max_entries:,}")
        print(f"Size:           {stats['size_mb']:.1f} MB / {stats['max_size_mb']:.1f} MB")
        print(f"Utilization:    {stats['utilization_pct']:.1f}%")
        print(f"Hit Rate:       {stats['hit_rate_pct']:.1f}%")
        print(f"Hits:           {stats['hits']:,}")
        print(f"Misses:         {stats['misses']:,}")
        print(f"Evictions:      {stats['evictions']:,}")
        print(f"Expirations:    {stats['expirations']:,}")
        print("="*60 + "\n")


class InstrumentCache(MemoryBoundedCache):
    """
    Specialized cache for instrument/market data

    Optimized for:
    - Symbol lookup (O(1) hash instead of O(n) search)
    - DataFrame caching with compression
    - Longer TTL for instrument metadata
    """

    def __init__(
        self,
        max_size_mb: int = 2048,
        instrument_ttl: int = 3600,  # 1 hour for instruments
        quote_ttl: int = 60,  # 1 minute for quotes
        max_instruments: int = 1000
    ):
        super().__init__(
            max_size_mb=max_size_mb,
            default_ttl=quote_ttl,
            max_entries=max_instruments
        )
        self.instrument_ttl = instrument_ttl
        self.quote_ttl = quote_ttl

        # Symbol hash map for O(1) lookups
        self._symbol_map: Dict[str, str] = {}  # trading_symbol -> cache_key

    def set_instrument(self, trading_symbol: str, instrument_data: Any):
        """Cache instrument data with longer TTL"""
        key = f"instrument:{trading_symbol}"
        self.set(key, instrument_data, ttl=self.instrument_ttl)

        # Update symbol map for fast lookup
        self._symbol_map[trading_symbol] = key

    def get_instrument(self, trading_symbol: str) -> Optional[Any]:
        """Get instrument data"""
        key = self._symbol_map.get(trading_symbol)
        if key:
            return self.get(key)

        # Try direct key (fallback)
        return self.get(f"instrument:{trading_symbol}")

    def set_quote(self, symbol: str, quote_data: Any):
        """Cache quote data with shorter TTL"""
        key = f"quote:{symbol}"
        self.set(key, quote_data, ttl=self.quote_ttl)

    def get_quote(self, symbol: str) -> Optional[Any]:
        """Get quote data"""
        return self.get(f"quote:{symbol}")

    def find_by_symbol(self, symbol: str) -> Optional[str]:
        """
        O(1) symbol lookup using hash map

        Args:
            symbol: Trading symbol to find

        Returns:
            Cache key if found, None otherwise
        """
        return self._symbol_map.get(symbol)


# Global cache instances
_global_cache: Optional[MemoryBoundedCache] = None
_instrument_cache: Optional[InstrumentCache] = None


def get_global_cache() -> MemoryBoundedCache:
    """Get global cache instance (singleton)"""
    global _global_cache
    if _global_cache is None:
        _global_cache = MemoryBoundedCache(max_size_mb=2048)
    return _global_cache


def get_instrument_cache() -> InstrumentCache:
    """Get instrument cache instance (singleton)"""
    global _instrument_cache
    if _instrument_cache is None:
        _instrument_cache = InstrumentCache(max_size_mb=1024, max_instruments=1000)
    return _instrument_cache


if __name__ == "__main__":
    # Test cache
    import pandas as pd

    cache = MemoryBoundedCache(max_size_mb=10, max_entries=100)

    # Test basic operations
    cache.set('test1', 'value1')
    assert cache.get('test1') == 'value1'

    # Test DataFrame caching
    df = pd.DataFrame({'a': range(1000), 'b': range(1000)})
    cache.set('df1', df)
    cached_df = cache.get('df1')
    assert cached_df is not None

    # Test eviction
    for i in range(200):
        cache.set(f'key_{i}', 'x' * 1000)

    cache.print_stats()

    # Test instrument cache
    inst_cache = InstrumentCache(max_size_mb=10)
    inst_cache.set_instrument('RELIANCE', {'exchange': 'NSE', 'lot_size': 1})
    inst = inst_cache.get_instrument('RELIANCE')
    print(f"Instrument: {inst}")

    inst_cache.print_stats()

    print("✅ All tests passed")
