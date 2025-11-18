#!/usr/bin/env python3
"""
API Rate Limiter
Prevents API throttling by enforcing rate limits on all API calls
"""

import time
from functools import wraps
from typing import Callable, Any
import logging

from infrastructure.rate_limiting import EnhancedRateLimiter

logger = logging.getLogger('trading_system.rate_limiter')


class APIRateLimiter:
    """
    Thread-safe rate limiter for API calls

    Usage:
        limiter = APIRateLimiter(calls_per_second=3)

        @limiter.limit('quote')
        def get_quote(symbols):
            return kite.quote(symbols)
    """

    def __init__(self, calls_per_second: float = 3.0, burst_size: int = 5):
        self._limiter = EnhancedRateLimiter(
            max_requests_per_second=int(calls_per_second),
            burst_size=burst_size,
        )
        logger.info("✅ Rate limiter initialized: %.2f calls/sec, burst=%s", calls_per_second, burst_size)

    def limit(self, key: str = 'default'):
        """
        Decorator to rate limit function calls

        Args:
            key: Rate limit key (different keys have independent limits)
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                if not self._limiter.acquire(key):
                    raise TimeoutError(f"Rate limit exceeded for key '{key}'")
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def wait(self, key: str = 'default') -> bool:
        """
        Manually wait for rate limit (for non-decorated calls)

        Returns:
            bool: True if wait succeeded, False if timeout

        CRITICAL FIX v2: Must check return value from underlying limiter!
        EnhancedRateLimiter.wait() returns False on timeout, not an exception.
        """
        try:
            result = self._limiter.wait(key)
            # CRITICAL: Return the actual result from underlying limiter
            # If it times out, result will be False
            return result
        except Exception as e:
            logger.error(f"Rate limiter exception for key '{key}': {e}")
            return False

    def reset(self, key: str | None = None) -> None:
        """Reset rate limiter for a key or all keys"""
        self._limiter.reset(key)

    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        return self._limiter.get_stats()


class KiteAPIWrapper:
    """
    Wrapper for KiteConnect with automatic rate limiting

    Usage:
        kite = KiteConnect(api_key=...)
        kite_limited = KiteAPIWrapper(kite, calls_per_second=3)

        # All calls are now rate-limited
        quotes = kite_limited.quote(['SBIN', 'INFY'])
    """

    def __init__(self, kite_instance, calls_per_second: float = 3.0):
        """
        Wrap KiteConnect instance with rate limiting

        Args:
            kite_instance: KiteConnect instance
            calls_per_second: Rate limit
        """
        self._kite = kite_instance
        self._limiter = APIRateLimiter(calls_per_second=calls_per_second)

        # Methods that need rate limiting
        self._rate_limited_methods = [
            'quote', 'ltp', 'ohlc',
            'place_order', 'modify_order', 'cancel_order',
            'orders', 'positions', 'holdings',
            'margins', 'profile',
            'instruments', 'historical_data'
        ]

        logger.info(f"✅ KiteAPIWrapper initialized with {calls_per_second} calls/sec")

    def __getattr__(self, name: str):
        """Intercept method calls and add rate limiting"""
        attr = getattr(self._kite, name)

        # If it's a rate-limited method, wrap it
        if callable(attr) and name in self._rate_limited_methods:
            @wraps(attr)
            def rate_limited_method(*args, **kwargs):
                if not self._limiter.wait(name):
                    raise TimeoutError(f"Rate limit exceeded while calling {name}")
                return attr(*args, **kwargs)
            return rate_limited_method

        # Otherwise return as-is
        return attr

    def get_rate_limiter_stats(self) -> dict:
        """Get rate limiter statistics"""
        return self._limiter.get_stats()


# Convenience function
def wrap_kite_with_rate_limiter(kite_instance, calls_per_second: float = 3.0):
    """
    Wrap a KiteConnect instance with rate limiting

    Args:
        kite_instance: KiteConnect instance
        calls_per_second: Maximum calls per second

    Returns:
        Rate-limited wrapper
    """
    return KiteAPIWrapper(kite_instance, calls_per_second)


if __name__ == "__main__":
    # Test rate limiter
    logging.basicConfig(level=logging.DEBUG)

    print("🧪 Testing API Rate Limiter")
    print("=" * 60)

    limiter = APIRateLimiter(calls_per_second=2, burst_size=3)

    @limiter.limit('test')
    def mock_api_call(call_num):
        print(f"  ✓ API call {call_num} executed at {time.time():.3f}")
        return f"result_{call_num}"

    print("\n📊 Making 10 API calls (limit: 2/sec)...")
    start = time.time()

    for i in range(10):
        mock_api_call(i)

    elapsed = time.time() - start
    print(f"\n⏱️  Total time: {elapsed:.2f}s")
    print(f"📈 Stats: {limiter.get_stats()}")
    print(f"✅ Rate limiter working correctly!")
