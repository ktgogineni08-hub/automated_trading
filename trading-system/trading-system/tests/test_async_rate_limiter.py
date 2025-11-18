#!/usr/bin/env python3
"""
Comprehensive tests for async_rate_limiter.py module
Tests async rate limiting, token buckets, burst handling, and decorators
"""

import pytest
import asyncio
import time
from typing import List
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.async_rate_limiter import (
    RateLimitConfig,
    TokenBucket,
    AsyncRateLimiter,
    AsyncRateLimitContext,
    ZerodhaRateLimiter,
    rate_limit,
    get_global_rate_limiter,
    set_global_rate_limiter,
    benchmark_rate_limiter
)


# ============================================================================
# RateLimitConfig Tests
# ============================================================================

class TestRateLimitConfig:
    """Test RateLimitConfig dataclass"""

    def test_basic_config(self):
        """Test basic rate limit configuration"""
        config = RateLimitConfig(max_requests=10, window_seconds=1.0)

        assert config.max_requests == 10
        assert config.window_seconds == 1.0
        assert config.burst_size == 10  # Default burst = max_requests

    def test_custom_burst_size(self):
        """Test custom burst size"""
        config = RateLimitConfig(max_requests=5, window_seconds=1.0, burst_size=10)

        assert config.max_requests == 5
        assert config.burst_size == 10

    def test_zero_burst_defaults_to_max_requests(self):
        """Test that burst_size=0 defaults to max_requests"""
        config = RateLimitConfig(max_requests=3, window_seconds=1.0, burst_size=0)

        assert config.burst_size == 3


# ============================================================================
# TokenBucket Tests
# ============================================================================

class TestTokenBucket:
    """Test TokenBucket class"""

    def test_initialization(self):
        """Test token bucket initialization"""
        bucket = TokenBucket(capacity=10.0, tokens=10.0, fill_rate=5.0)

        assert bucket.capacity == 10.0
        assert bucket.tokens == 10.0
        assert bucket.fill_rate == 5.0
        assert bucket.last_update > 0

    def test_consume_success(self):
        """Test successful token consumption"""
        bucket = TokenBucket(capacity=10.0, tokens=10.0, fill_rate=5.0)

        success = bucket.consume(5.0)

        assert success is True
        assert bucket.tokens == 5.0

    def test_consume_failure(self):
        """Test failed token consumption (insufficient tokens)"""
        bucket = TokenBucket(capacity=10.0, tokens=3.0, fill_rate=5.0)

        success = bucket.consume(5.0)

        assert success is False
        assert bucket.tokens == pytest.approx(3.0, abs=0.001)  # Tokens unchanged

    def test_consume_exact_amount(self):
        """Test consuming exact token amount"""
        bucket = TokenBucket(capacity=10.0, tokens=5.0, fill_rate=5.0)

        success = bucket.consume(5.0)

        assert success is True
        assert bucket.tokens == pytest.approx(0.0, abs=0.001)

    def test_refill_over_time(self):
        """Test token refill over time"""
        bucket = TokenBucket(capacity=10.0, tokens=0.0, fill_rate=10.0)

        time.sleep(0.5)  # Wait 0.5 seconds
        bucket._refill()

        # Should have ~5 tokens (10 per second × 0.5 seconds)
        assert bucket.tokens >= 4.0  # Allow some margin
        assert bucket.tokens <= 6.0

    def test_refill_respects_capacity(self):
        """Test that refill doesn't exceed capacity"""
        bucket = TokenBucket(capacity=10.0, tokens=8.0, fill_rate=100.0)

        time.sleep(0.5)  # Would add 50 tokens if uncapped
        bucket._refill()

        assert bucket.tokens == 10.0  # Capped at capacity

    def test_wait_time_with_available_tokens(self):
        """Test wait time when tokens are available"""
        bucket = TokenBucket(capacity=10.0, tokens=10.0, fill_rate=5.0)

        wait = bucket.wait_time(5.0)

        assert wait == 0.0

    def test_wait_time_with_insufficient_tokens(self):
        """Test wait time calculation when tokens insufficient"""
        bucket = TokenBucket(capacity=10.0, tokens=2.0, fill_rate=10.0)

        wait = bucket.wait_time(5.0)

        # Need 3 more tokens at 10/second = 0.3 seconds
        assert abs(wait - 0.3) < 0.01

    def test_multiple_consumes(self):
        """Test multiple token consumptions"""
        bucket = TokenBucket(capacity=10.0, tokens=10.0, fill_rate=5.0)

        assert bucket.consume(3.0) is True
        assert bucket.consume(3.0) is True
        assert bucket.consume(3.0) is True
        assert bucket.consume(2.0) is False  # Only 1 token left


# ============================================================================
# AsyncRateLimiter Tests
# ============================================================================

class TestAsyncRateLimiter:
    """Test AsyncRateLimiter class"""

    def test_initialization(self):
        """Test AsyncRateLimiter initialization"""
        limiter = AsyncRateLimiter()

        assert limiter._buckets == {}
        assert limiter._configs == {}

    def test_add_limit(self):
        """Test adding rate limit"""
        limiter = AsyncRateLimiter()
        config = RateLimitConfig(max_requests=10, window_seconds=1.0)

        limiter.add_limit("test_endpoint", config)

        assert "test_endpoint" in limiter._buckets
        assert "test_endpoint" in limiter._configs
        assert limiter._configs["test_endpoint"] == config

    def test_add_multiple_limits(self):
        """Test adding multiple rate limits"""
        limiter = AsyncRateLimiter()

        limiter.add_limit("api1", RateLimitConfig(max_requests=10, window_seconds=1.0))
        limiter.add_limit("api2", RateLimitConfig(max_requests=20, window_seconds=2.0))
        limiter.add_limit("api3", RateLimitConfig(max_requests=5, window_seconds=0.5))

        assert len(limiter._buckets) == 3
        assert len(limiter._configs) == 3

    @pytest.mark.asyncio
    async def test_acquire_returns_context(self):
        """Test that acquire returns context manager"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("test", RateLimitConfig(max_requests=10, window_seconds=1.0))

        context = await limiter.acquire("test")

        assert isinstance(context, AsyncRateLimitContext)

    @pytest.mark.asyncio
    async def test_basic_rate_limiting(self):
        """Test basic rate limiting"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("test", RateLimitConfig(max_requests=5, window_seconds=1.0))

        # Should allow 5 requests immediately
        for i in range(5):
            async with await limiter.acquire("test"):
                pass

        stats = limiter.get_stats("test")
        assert stats['requests'] == 5

    @pytest.mark.asyncio
    async def test_throttling_when_limit_exceeded(self):
        """Test that requests are throttled when limit exceeded"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("test", RateLimitConfig(max_requests=2, window_seconds=1.0))

        start = time.time()

        # First 2 should be immediate, 3rd should wait
        for i in range(3):
            async with await limiter.acquire("test"):
                pass

        elapsed = time.time() - start

        # Should take at least 0.5 seconds (need to wait for tokens to refill)
        assert elapsed >= 0.4

        stats = limiter.get_stats("test")
        assert stats['throttled'] >= 1

    @pytest.mark.asyncio
    async def test_burst_handling(self):
        """Test burst handling with larger burst size"""
        limiter = AsyncRateLimiter()
        limiter.add_limit(
            "burst_test",
            RateLimitConfig(max_requests=2, window_seconds=1.0, burst_size=5)
        )

        start = time.time()

        # First 5 should go through immediately (burst)
        for i in range(5):
            async with await limiter.acquire("burst_test"):
                pass

        burst_time = time.time() - start

        # Burst should be nearly immediate
        assert burst_time < 0.2

    @pytest.mark.asyncio
    async def test_acquire_without_configured_limit(self):
        """Test acquiring tokens for unconfigured endpoint"""
        limiter = AsyncRateLimiter()

        # Should allow request (with warning logged)
        async with await limiter.acquire("unconfigured"):
            pass

        # Should not raise error

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test concurrent requests with rate limiting"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("concurrent", RateLimitConfig(max_requests=5, window_seconds=1.0))

        async def make_request(i):
            async with await limiter.acquire("concurrent"):
                await asyncio.sleep(0.01)
                return i

        # Make 10 concurrent requests
        results = await asyncio.gather(*[make_request(i) for i in range(10)])

        assert len(results) == 10
        stats = limiter.get_stats("concurrent")
        assert stats['requests'] == 10
        assert stats['throttled'] > 0  # Some should be throttled

    @pytest.mark.asyncio
    async def test_multiple_endpoints(self):
        """Test rate limiting for multiple endpoints independently"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("api1", RateLimitConfig(max_requests=3, window_seconds=1.0))
        limiter.add_limit("api2", RateLimitConfig(max_requests=5, window_seconds=1.0))

        # Use both endpoints
        for i in range(3):
            async with await limiter.acquire("api1"):
                pass

        for i in range(5):
            async with await limiter.acquire("api2"):
                pass

        stats1 = limiter.get_stats("api1")
        stats2 = limiter.get_stats("api2")

        assert stats1['requests'] == 3
        assert stats2['requests'] == 5

    def test_get_stats_single_endpoint(self):
        """Test getting statistics for single endpoint"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("test", RateLimitConfig(max_requests=10, window_seconds=1.0))

        stats = limiter.get_stats("test")

        assert 'requests' in stats
        assert 'throttled' in stats
        assert 'total_wait_time' in stats
        assert 'current_rate' in stats
        assert 'available_tokens' in stats
        assert 'capacity' in stats

    def test_get_stats_all_endpoints(self):
        """Test getting statistics for all endpoints"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("api1", RateLimitConfig(max_requests=10, window_seconds=1.0))
        limiter.add_limit("api2", RateLimitConfig(max_requests=20, window_seconds=2.0))

        all_stats = limiter.get_stats()

        assert isinstance(all_stats, dict)
        # Stats might be empty if no requests made yet

    def test_reset_stats_single_endpoint(self):
        """Test resetting statistics for single endpoint"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("test", RateLimitConfig(max_requests=10, window_seconds=1.0))

        # Manually set some stats
        limiter._stats["test"]["requests"] = 100
        limiter._stats["test"]["throttled"] = 10

        limiter.reset_stats("test")

        stats = limiter.get_stats("test")
        assert stats['requests'] == 0
        assert stats['throttled'] == 0

    def test_reset_stats_all_endpoints(self):
        """Test resetting all statistics"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("api1", RateLimitConfig(max_requests=10, window_seconds=1.0))
        limiter.add_limit("api2", RateLimitConfig(max_requests=20, window_seconds=2.0))

        limiter._stats["api1"]["requests"] = 50
        limiter._stats["api2"]["requests"] = 75

        limiter.reset_stats()

        assert len(limiter._stats) == 0


# ============================================================================
# AsyncRateLimitContext Tests
# ============================================================================

class TestAsyncRateLimitContext:
    """Test AsyncRateLimitContext class"""

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self):
        """Test context manager enter and exit"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("test", RateLimitConfig(max_requests=10, window_seconds=1.0))

        context = AsyncRateLimitContext(limiter, "test", 1.0)

        async with context as ctx:
            assert ctx.start_time > 0

        # Context should exit successfully

    @pytest.mark.asyncio
    async def test_context_tracks_tokens(self):
        """Test that context uses specified token amount"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("test", RateLimitConfig(max_requests=10, window_seconds=1.0, burst_size=10))

        # Consume 5 tokens
        async with await limiter.acquire("test", tokens=5.0):
            pass

        # Should have 5 tokens left in bucket
        bucket = limiter._buckets["test"]
        bucket._refill()
        assert bucket.tokens == pytest.approx(5.0, abs=0.1)


# ============================================================================
# Rate Limit Decorator Tests
# ============================================================================

class TestRateLimitDecorator:
    """Test rate_limit decorator"""

    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """Test basic decorator usage"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("decorated", RateLimitConfig(max_requests=5, window_seconds=1.0))
        set_global_rate_limiter(limiter)

        @rate_limit("decorated")
        async def api_call(value):
            return value * 2

        result = await api_call(21)

        assert result == 42
        stats = limiter.get_stats("decorated")
        assert stats['requests'] == 1

    @pytest.mark.asyncio
    async def test_decorator_with_multiple_calls(self):
        """Test decorator with multiple calls"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("multi", RateLimitConfig(max_requests=10, window_seconds=1.0))
        set_global_rate_limiter(limiter)

        @rate_limit("multi")
        async def fetch_data(n):
            await asyncio.sleep(0.01)
            return f"data_{n}"

        results = await asyncio.gather(*[fetch_data(i) for i in range(5)])

        assert len(results) == 5
        stats = limiter.get_stats("multi")
        assert stats['requests'] == 5

    @pytest.mark.asyncio
    async def test_decorator_with_custom_tokens(self):
        """Test decorator with custom token amount"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("custom_tokens", RateLimitConfig(max_requests=10, window_seconds=1.0))
        set_global_rate_limiter(limiter)

        @rate_limit("custom_tokens", tokens=3.0)
        async def expensive_call():
            return "expensive"

        result = await expensive_call()

        assert result == "expensive"


# ============================================================================
# ZerodhaRateLimiter Tests
# ============================================================================

class TestZerodhaRateLimiter:
    """Test ZerodhaRateLimiter class"""

    def test_initialization(self):
        """Test ZerodhaRateLimiter initialization"""
        limiter = ZerodhaRateLimiter()

        # Should have pre-configured limits
        assert "zerodha_api" in limiter._configs
        assert "zerodha_quote" in limiter._configs
        assert "zerodha_order" in limiter._configs
        assert "zerodha_positions" in limiter._configs

    def test_zerodha_api_limit(self):
        """Test Zerodha API limit configuration"""
        limiter = ZerodhaRateLimiter()

        config = limiter._configs["zerodha_api"]
        assert config.max_requests == 3
        assert config.window_seconds == 1.0
        assert config.burst_size == 10

    def test_zerodha_quote_limit(self):
        """Test Zerodha quote limit configuration"""
        limiter = ZerodhaRateLimiter()

        config = limiter._configs["zerodha_quote"]
        assert config.max_requests == 3
        assert config.window_seconds == 1.0
        assert config.burst_size == 5

    def test_zerodha_order_limit(self):
        """Test Zerodha order limit configuration"""
        limiter = ZerodhaRateLimiter()

        config = limiter._configs["zerodha_order"]
        assert config.max_requests == 2
        assert config.window_seconds == 1.0
        assert config.burst_size == 3

    def test_zerodha_positions_limit(self):
        """Test Zerodha positions limit configuration"""
        limiter = ZerodhaRateLimiter()

        config = limiter._configs["zerodha_positions"]
        assert config.max_requests == 1
        assert config.window_seconds == 1.0
        assert config.burst_size == 2

    @pytest.mark.asyncio
    async def test_zerodha_api_usage(self):
        """Test using Zerodha rate limiter for API calls"""
        limiter = ZerodhaRateLimiter()

        # Make 3 API calls (should be immediate)
        start = time.time()
        for i in range(3):
            async with await limiter.acquire("zerodha_api"):
                await asyncio.sleep(0.01)

        immediate_time = time.time() - start

        assert immediate_time < 0.5  # Should be fast


# ============================================================================
# Global Rate Limiter Tests
# ============================================================================

class TestGlobalRateLimiter:
    """Test global rate limiter functions"""

    def test_get_global_rate_limiter(self):
        """Test getting global rate limiter"""
        # Reset global
        import core.async_rate_limiter
        core.async_rate_limiter._global_rate_limiter = None

        limiter = get_global_rate_limiter()

        assert isinstance(limiter, ZerodhaRateLimiter)

    def test_get_global_returns_same_instance(self):
        """Test that get_global returns same instance"""
        # Reset global
        import core.async_rate_limiter
        core.async_rate_limiter._global_rate_limiter = None

        limiter1 = get_global_rate_limiter()
        limiter2 = get_global_rate_limiter()

        assert limiter1 is limiter2

    def test_set_global_rate_limiter(self):
        """Test setting global rate limiter"""
        custom_limiter = AsyncRateLimiter()
        custom_limiter.add_limit("custom", RateLimitConfig(max_requests=100, window_seconds=1.0))

        set_global_rate_limiter(custom_limiter)

        limiter = get_global_rate_limiter()

        assert limiter is custom_limiter
        assert "custom" in limiter._configs


# ============================================================================
# Benchmark Tests
# ============================================================================

class TestBenchmark:
    """Test benchmark utilities"""

    @pytest.mark.asyncio
    async def test_benchmark_async_mode(self):
        """Test benchmark in async mode"""
        results = await benchmark_rate_limiter(
            requests=20,
            rate_limit=10,
            use_async=True
        )

        assert results['requests'] == 20
        assert results['mode'] == 'async'
        assert results['elapsed_seconds'] > 0
        assert results['requests_per_second'] > 0
        assert 'throttled' in results

    @pytest.mark.asyncio
    async def test_benchmark_sync_mode(self):
        """Test benchmark in sync mode"""
        results = await benchmark_rate_limiter(
            requests=20,
            rate_limit=10,
            use_async=False
        )

        assert results['requests'] == 20
        assert results['mode'] == 'sync'
        assert results['elapsed_seconds'] > 0
        assert results['requests_per_second'] > 0

    @pytest.mark.asyncio
    async def test_benchmark_async_faster_than_sync(self):
        """Test that async mode is faster than sync"""
        async_results = await benchmark_rate_limiter(
            requests=30,
            rate_limit=15,
            use_async=True
        )

        sync_results = await benchmark_rate_limiter(
            requests=30,
            rate_limit=15,
            use_async=False
        )

        # Async should be significantly faster
        assert async_results['requests_per_second'] > sync_results['requests_per_second']


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for rate limiting"""

    @pytest.mark.asyncio
    async def test_realistic_api_usage(self):
        """Test realistic API usage pattern"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("api", RateLimitConfig(max_requests=10, window_seconds=1.0, burst_size=15))

        async def simulate_api_call(i):
            async with await limiter.acquire("api"):
                await asyncio.sleep(0.01)  # Simulate API latency
                return f"response_{i}"

        # Simulate burst of 15 requests, then steady stream
        start = time.time()
        results = await asyncio.gather(*[simulate_api_call(i) for i in range(25)])
        elapsed = time.time() - start

        assert len(results) == 25
        stats = limiter.get_stats("api")
        assert stats['requests'] == 25

        # Should take at least 1 second due to rate limiting
        assert elapsed >= 1.0

    @pytest.mark.asyncio
    async def test_multiple_concurrent_endpoints(self):
        """Test multiple endpoints being used concurrently"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("fast_api", RateLimitConfig(max_requests=20, window_seconds=1.0))
        limiter.add_limit("slow_api", RateLimitConfig(max_requests=5, window_seconds=1.0))

        async def use_fast_api(i):
            async with await limiter.acquire("fast_api"):
                await asyncio.sleep(0.01)
                return f"fast_{i}"

        async def use_slow_api(i):
            async with await limiter.acquire("slow_api"):
                await asyncio.sleep(0.01)
                return f"slow_{i}"

        # Use both APIs concurrently
        fast_tasks = [use_fast_api(i) for i in range(10)]
        slow_tasks = [use_slow_api(i) for i in range(10)]

        fast_results, slow_results = await asyncio.gather(
            asyncio.gather(*fast_tasks),
            asyncio.gather(*slow_tasks)
        )

        assert len(fast_results) == 10
        assert len(slow_results) == 10

        fast_stats = limiter.get_stats("fast_api")
        slow_stats = limiter.get_stats("slow_api")

        assert fast_stats['requests'] == 10
        assert slow_stats['requests'] == 10
        assert slow_stats['throttled'] > fast_stats['throttled']  # Slow API more throttled

    @pytest.mark.asyncio
    async def test_error_handling_in_rate_limited_code(self):
        """Test that errors in rate-limited code don't break limiter"""
        limiter = AsyncRateLimiter()
        limiter.add_limit("error_test", RateLimitConfig(max_requests=10, window_seconds=1.0))

        async def failing_call():
            async with await limiter.acquire("error_test"):
                raise ValueError("Simulated error")

        # Should still track the request even if it fails
        with pytest.raises(ValueError):
            await failing_call()

        stats = limiter.get_stats("error_test")
        assert stats['requests'] == 1


if __name__ == "__main__":
    # Run tests with: pytest test_async_rate_limiter.py -v
    # Run with coverage: pytest test_async_rate_limiter.py -v --cov=core.async_rate_limiter --cov-report=term-missing
    pytest.main([__file__, "-v", "--tb=short"])
