import time

from api_rate_limiter import APIRateLimiter
from infrastructure.rate_limiting import EnhancedRateLimiter


def test_api_rate_limiter_enforces_min_interval():
    limiter = APIRateLimiter(calls_per_second=2, burst_size=1)
    start = time.perf_counter()
    limiter.wait('test')
    limiter.wait('test')
    duration = time.perf_counter() - start
    assert duration >= 0.45  # allow slight scheduling variance


def test_enhanced_rate_limiter_stats():
    limiter = EnhancedRateLimiter(max_requests_per_second=5)
    assert limiter.acquire('alpha')
    stats = limiter.get_stats()
    assert stats['total_calls'] == 1
    limiter.reset('alpha')
    assert limiter.get_stats()['active_keys'] == 0
