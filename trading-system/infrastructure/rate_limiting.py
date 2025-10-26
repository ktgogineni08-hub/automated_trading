#!/usr/bin/env python3
"""
Rate Limiting and Circuit Breaker for API protection
Prevents API throttling and cascading failures
"""

import threading
import time
from collections import defaultdict, deque
from typing import Dict, Optional
import logging

logger = logging.getLogger('trading_system.rate_limiting')


class EnhancedRateLimiter:
    """
    Enhanced rate limiter with burst protection for Zerodha API

    Zerodha API limits:
    - 3 requests per second
    - 1000 requests per minute
    - Burst protection: Max 5 requests in 100ms window

    Thread-safe implementation for concurrent API calls.
    """

    def __init__(
        self,
        max_requests_per_second: Optional[int] = None,
        max_requests_per_minute: Optional[int] = None,
        burst_size: int = 5,
        burst_window: float = 0.1,
        min_interval: Optional[float] = None,
    ):
        self.max_per_second = max_requests_per_second or 3
        self.max_per_minute = max_requests_per_minute or 1000
        self.max_burst = burst_size
        self.burst_window = burst_window
        self.min_interval = min_interval if min_interval is not None else (1.0 / self.max_per_second)

        self._burst_buckets = defaultdict(deque)
        self._second_buckets = defaultdict(deque)
        self._minute_buckets = defaultdict(deque)
        self._last_call: Dict[str, float] = {}

        self.total_calls = 0
        self.total_waits = 0
        self._lock = threading.RLock()

    def _cleanup_bucket(self, bucket: deque, window: float, now: float) -> None:
        while bucket and (now - bucket[0]) > window:
            bucket.popleft()

    def _required_wait_time(self, key: str, now: float) -> float:
        wait_time = 0.0

        burst_bucket = self._burst_buckets[key]
        self._cleanup_bucket(burst_bucket, self.burst_window, now)
        if len(burst_bucket) >= self.max_burst:
            wait_time = max(wait_time, (burst_bucket[0] + self.burst_window) - now)

        second_bucket = self._second_buckets[key]
        self._cleanup_bucket(second_bucket, 1.0, now)
        if len(second_bucket) >= self.max_per_second:
            wait_time = max(wait_time, (second_bucket[0] + 1.0) - now)

        minute_bucket = self._minute_buckets[key]
        self._cleanup_bucket(minute_bucket, 60.0, now)
        if len(minute_bucket) >= self.max_per_minute:
            wait_time = max(wait_time, (minute_bucket[0] + 60.0) - now)

        if self.min_interval:
            last_call = self._last_call.get(key)
            if last_call is not None:
                wait_time = max(wait_time, (last_call + self.min_interval) - now)

        return max(wait_time, 0.0)

    def can_make_request(self, key: str = 'default') -> bool:
        with self._lock:
            now = time.time()
            return self._required_wait_time(key, now) <= 0.0

    def wait_if_needed(self, key: str = 'default', timeout: float = 10.0) -> bool:
        start_time = time.time()
        while True:
            with self._lock:
                now = time.time()
                wait_time = self._required_wait_time(key, now)
            if wait_time <= 0:
                return True
            if (time.time() - start_time) + wait_time > timeout:
                logger.error(
                    "❌ Rate limit timeout after %.2fs for key '%s' - API overloaded",
                    timeout,
                    key,
                )
                return False
            self.total_waits += 1
            time.sleep(min(wait_time, 0.1))

    def record_request(self, key: str = 'default') -> None:
        with self._lock:
            now = time.time()
            self._burst_buckets[key].append(now)
            self._second_buckets[key].append(now)
            self._minute_buckets[key].append(now)
            self._last_call[key] = now
            self.total_calls += 1

    def acquire(self, key: str = 'default', timeout: float = 10.0) -> bool:
        if not self.wait_if_needed(key, timeout):
            return False
        self.record_request(key)
        return True

    def wait(self, key: str = 'default', timeout: float = 10.0) -> bool:
        """Backward-compatible alias combining wait and record."""
        return self.acquire(key, timeout)

    def limit(self, key: str = 'default', timeout: float = 10.0):
        """Decorator to rate-limit a function call."""
        from functools import wraps

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.acquire(key, timeout):
                    raise TimeoutError(f"Rate limit exceeded for key '{key}'")
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def get_stats(self) -> Dict[str, float]:
        with self._lock:
            return {
                'total_calls': self.total_calls,
                'total_waits': self.total_waits,
                'active_keys': len(self._last_call),
            }

    def reset(self, key: Optional[str] = None) -> None:
        with self._lock:
            if key:
                self._burst_buckets.pop(key, None)
                self._second_buckets.pop(key, None)
                self._minute_buckets.pop(key, None)
                self._last_call.pop(key, None)
            else:
                self._burst_buckets.clear()
                self._second_buckets.clear()
                self._minute_buckets.clear()
                self._last_call.clear()
                self.total_calls = 0
                self.total_waits = 0


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures in trading loop

    Protects against rapid error loops that can exhaust system resources.
    States: CLOSED (normal) -> OPEN (failures) -> HALF_OPEN (testing)

    Usage:
    - Record failures with record_failure()
    - Record successes with record_success()
    - Check if operations allowed with can_proceed()
    """

    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0, reset_timeout: int = None):
        """
        Initialize circuit breaker

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before attempting reset (alias for reset_timeout)
            reset_timeout: Seconds to wait before attempting reset (deprecated, use timeout)
        """
        self.failure_threshold = failure_threshold
        # Accept either 'timeout' or 'reset_timeout' for compatibility
        self.reset_timeout = timeout if reset_timeout is None else reset_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

        self._lock = threading.Lock()

    def record_failure(self) -> None:
        """Record a failure and potentially open the circuit"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.critical(
                    f"🚨 Circuit breaker OPEN: {self.failure_count} consecutive failures. "
                    f"System paused for {self.reset_timeout}s"
                )

    def record_success(self) -> None:
        """Record a success and reset the circuit"""
        with self._lock:
            if self.state == "HALF_OPEN":
                logger.info("✅ Circuit breaker reset to CLOSED state")
            self.failure_count = 0
            self.state = "CLOSED"

    def can_proceed(self) -> bool:
        """Check if operations can proceed"""
        with self._lock:
            if self.state == "CLOSED":
                return True

            if self.state == "OPEN":
                # Check if reset timeout has elapsed
                if time.time() - self.last_failure_time > self.reset_timeout:
                    self.state = "HALF_OPEN"
                    self.failure_count = 0
                    logger.info("🔄 Circuit breaker entering HALF_OPEN state (testing)")
                    return True
                return False

            if self.state == "HALF_OPEN":
                return True  # Allow one attempt

            return False

    def get_state(self) -> Dict:
        """Get current circuit breaker state"""
        with self._lock:
            return {
                'state': self.state,
                'failure_count': self.failure_count,
                'threshold': self.failure_threshold,
                'last_failure': self.last_failure_time
            }
