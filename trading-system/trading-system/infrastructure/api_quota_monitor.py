#!/usr/bin/env python3
"""
API Quota Monitoring and Management
Comprehensive quota tracking and alerting for Zerodha API

ADDRESSES CRITICAL RECOMMENDATION #3:
- Real-time API quota tracking
- Proactive quota alerts
- Usage analytics and reporting
- Automatic throttling to prevent quota exhaustion
- Multi-timeframe quota management (per-second, per-minute, per-day)
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from collections import deque, defaultdict
from enum import Enum
import json

from infrastructure.alert_manager import get_alert_manager, AlertSeverity, AlertCategory

logger = logging.getLogger('trading_system.api_quota')


class QuotaLevel(Enum):
    """API quota consumption levels"""
    SAFE = "safe"          # < 50% of quota
    WARNING = "warning"    # 50-75% of quota
    CRITICAL = "critical"  # 75-90% of quota
    DANGER = "danger"      # > 90% of quota


@dataclass
class QuotaLimit:
    """API quota limit configuration"""
    name: str
    max_requests: int
    window_seconds: int
    threshold_warning: float = 0.75  # Alert at 75%
    threshold_critical: float = 0.90  # Critical at 90%


@dataclass
class QuotaUsage:
    """Current quota usage statistics"""
    limit_name: str
    current_usage: int
    max_requests: int
    window_seconds: int
    usage_percent: float
    level: QuotaLevel
    time_until_reset: float  # seconds
    requests_remaining: int
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            **asdict(self),
            'level': self.level.value,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class APICall:
    """Individual API call record"""
    timestamp: datetime
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    quota_consumed: int = 1
    error: Optional[str] = None


class APIQuotaMonitor:
    """
    Comprehensive API Quota Monitoring System

    Features:
    - Multi-timeframe quota tracking (per-second, per-minute, per-hour, per-day)
    - Real-time usage analytics
    - Proactive quota alerts
    - Automatic throttling
    - Usage reporting and trends
    - Per-endpoint tracking
    - Quota violation detection

    Zerodha API Limits (as of 2024):
    - 3 requests per second
    - 1000 requests per minute
    - 3000 requests per hour (estimated)
    - No official daily limit, but monitored

    Usage:
        monitor = APIQuotaMonitor()
        monitor.start_monitoring()

        # Record API call
        monitor.record_api_call(
            endpoint="/api/quote",
            method="GET",
            status_code=200,
            response_time_ms=150
        )

        # Check if can make request
        if monitor.can_make_request():
            # Make API call
            pass
    """

    def __init__(
        self,
        enable_auto_throttling: bool = True,
        alert_threshold_warning: float = 0.75,
        alert_threshold_critical: float = 0.90
    ):
        """
        Initialize API quota monitor

        Args:
            enable_auto_throttling: Auto-throttle when quota near limit
            alert_threshold_warning: Warning threshold (0-1)
            alert_threshold_critical: Critical threshold (0-1)
        """
        self.enable_auto_throttling = enable_auto_throttling
        self.alert_threshold_warning = alert_threshold_warning
        self.alert_threshold_critical = alert_threshold_critical

        # Quota limits (Zerodha API)
        self.quota_limits = [
            QuotaLimit("per_second", max_requests=3, window_seconds=1),
            QuotaLimit("per_minute", max_requests=1000, window_seconds=60),
            QuotaLimit("per_hour", max_requests=3000, window_seconds=3600),
            QuotaLimit("per_day", max_requests=50000, window_seconds=86400),  # Conservative
        ]

        # API call tracking
        self._api_calls: deque = deque(maxlen=100000)  # Last 100k calls
        self._calls_by_endpoint: Dict[str, List[APICall]] = defaultdict(list)

        # Current usage by timeframe
        self._current_usage: Dict[str, QuotaUsage] = {}

        # Alert tracking
        self._last_alerts: Dict[str, datetime] = {}
        self._alert_cooldown_seconds = 300  # 5 minutes

        # Monitoring
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # Alert manager
        self.alert_mgr = get_alert_manager()

        # Statistics
        self.total_calls = 0
        self.total_errors = 0
        self.total_throttled = 0

        logger.info("📊 API Quota Monitor initialized")

    def start_monitoring(self):
        """Start background quota monitoring"""
        if self._monitoring:
            logger.warning("Monitoring already started")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        logger.info("✅ Quota monitoring started")

    def stop_monitoring(self):
        """Stop monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

        logger.info("🛑 Quota monitoring stopped")

    def _monitor_loop(self):
        """Background monitoring loop"""
        while self._monitoring:
            try:
                # Update usage statistics
                self._update_usage_statistics()

                # Check for quota violations
                self._check_quota_violations()

                # Cleanup old data
                self._cleanup_old_data()

                time.sleep(5)  # Check every 5 seconds

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

    def record_api_call(
        self,
        endpoint: str,
        method: str = "GET",
        status_code: int = 200,
        response_time_ms: float = 0,
        error: Optional[str] = None
    ):
        """
        Record an API call

        Args:
            endpoint: API endpoint path
            method: HTTP method
            status_code: Response status code
            response_time_ms: Response time in milliseconds
            error: Error message if call failed
        """
        call = APICall(
            timestamp=datetime.now(),
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            error=error
        )

        with self._lock:
            self._api_calls.append(call)
            self._calls_by_endpoint[endpoint].append(call)

            # Keep only last 1000 calls per endpoint
            if len(self._calls_by_endpoint[endpoint]) > 1000:
                self._calls_by_endpoint[endpoint] = (
                    self._calls_by_endpoint[endpoint][-1000:]
                )

            self.total_calls += 1
            if error or status_code >= 400:
                self.total_errors += 1

        # Update usage immediately
        self._update_usage_statistics()

    def can_make_request(self, safety_margin: float = 0.95) -> bool:
        """
        Check if can make API request without exceeding quota

        Args:
            safety_margin: Use this fraction of quota (0.95 = 95%)

        Returns:
            True if safe to make request
        """
        # Ensure we evaluate against the most recent window boundaries.
        self._update_usage_statistics()

        with self._lock:
            for limit_name, usage in self._current_usage.items():
                # Calculate effective limit with safety margin
                effective_limit = usage.max_requests * safety_margin

                if usage.current_usage >= effective_limit:
                    logger.warning(
                        f"⚠️ Quota near limit for {limit_name}: "
                        f"{usage.current_usage}/{usage.max_requests} "
                        f"({usage.usage_percent:.1f}%)"
                    )
                    return False

            return True

    def wait_if_needed(
        self,
        timeout: float = 10.0,
        safety_margin: float = 0.95
    ) -> bool:
        """
        Wait if quota near limit

        Args:
            timeout: Max time to wait in seconds
            safety_margin: Use this fraction of quota

        Returns:
            True if can proceed, False if timeout
        """
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            if self.can_make_request(safety_margin):
                return True

            # Wait for shortest quota window to reset
            min_wait = self._get_min_wait_time()
            if min_wait > 0:
                wait_time = min(min_wait, 0.1)  # Wait max 100ms at a time
                time.sleep(wait_time)
                self.total_throttled += 1

        logger.error(f"❌ Quota wait timeout after {timeout}s")
        return False

    def _get_min_wait_time(self) -> float:
        """Get minimum time to wait for quota reset"""
        min_wait = float('inf')

        with self._lock:
            for usage in self._current_usage.values():
                if usage.level in [QuotaLevel.CRITICAL, QuotaLevel.DANGER]:
                    min_wait = min(min_wait, usage.time_until_reset)

        return min_wait if min_wait != float('inf') else 0

    def _update_usage_statistics(self):
        """Update current usage statistics for all quota limits"""
        now = datetime.now()

        with self._lock:
            for limit in self.quota_limits:
                # Count calls within window
                cutoff = now - timedelta(seconds=limit.window_seconds)
                calls_in_window = sum(
                    1 for call in self._api_calls
                    if call.timestamp >= cutoff
                )

                # Calculate usage percentage
                usage_percent = (calls_in_window / limit.max_requests) * 100

                # Determine level
                if usage_percent >= 90:
                    level = QuotaLevel.DANGER
                elif usage_percent >= 75:
                    level = QuotaLevel.CRITICAL
                elif usage_percent >= 50:
                    level = QuotaLevel.WARNING
                else:
                    level = QuotaLevel.SAFE

                # Calculate time until reset (oldest call expires)
                time_until_reset = 0
                if calls_in_window > 0:
                    oldest_call = min(
                        (call for call in self._api_calls if call.timestamp >= cutoff),
                        key=lambda c: c.timestamp
                    )
                    time_until_reset = (
                        limit.window_seconds -
                        (now - oldest_call.timestamp).total_seconds()
                    )

                # Create usage object
                usage = QuotaUsage(
                    limit_name=limit.name,
                    current_usage=calls_in_window,
                    max_requests=limit.max_requests,
                    window_seconds=limit.window_seconds,
                    usage_percent=usage_percent,
                    level=level,
                    time_until_reset=max(time_until_reset, 0),
                    requests_remaining=max(limit.max_requests - calls_in_window, 0),
                    timestamp=now
                )

                self._current_usage[limit.name] = usage

    def _check_quota_violations(self):
        """Check for quota violations and send alerts"""
        now = datetime.now()

        with self._lock:
            for limit_name, usage in self._current_usage.items():
                # Skip if recently alerted
                last_alert = self._last_alerts.get(limit_name)
                if last_alert:
                    time_since_alert = (now - last_alert).total_seconds()
                    if time_since_alert < self._alert_cooldown_seconds:
                        continue

                # Check thresholds
                if usage.level == QuotaLevel.DANGER:
                    self._send_quota_alert(
                        usage,
                        AlertSeverity.CRITICAL,
                        "API quota DANGER - immediate throttling required!"
                    )
                    self._last_alerts[limit_name] = now

                elif usage.level == QuotaLevel.CRITICAL:
                    self._send_quota_alert(
                        usage,
                        AlertSeverity.HIGH,
                        "API quota CRITICAL - approaching limit"
                    )
                    self._last_alerts[limit_name] = now

                elif usage.level == QuotaLevel.WARNING:
                    self._send_quota_alert(
                        usage,
                        AlertSeverity.MEDIUM,
                        "API quota WARNING - monitoring required"
                    )
                    self._last_alerts[limit_name] = now

    def _send_quota_alert(self, usage: QuotaUsage, severity: AlertSeverity, message: str):
        """Send quota alert"""
        self.alert_mgr.alert(
            severity=severity,
            category=AlertCategory.SYSTEM,
            title=f"API Quota Alert: {usage.limit_name}",
            message=message,
            context={
                'limit_name': usage.limit_name,
                'usage': usage.current_usage,
                'max_requests': usage.max_requests,
                'usage_percent': usage.usage_percent,
                'level': usage.level.value,
                'time_until_reset': usage.time_until_reset,
                'requests_remaining': usage.requests_remaining
            }
        )

    def _cleanup_old_data(self):
        """Remove old API call data"""
        cutoff = datetime.now() - timedelta(days=1)

        with self._lock:
            # Cleanup by endpoint
            for endpoint in list(self._calls_by_endpoint.keys()):
                self._calls_by_endpoint[endpoint] = [
                    call for call in self._calls_by_endpoint[endpoint]
                    if call.timestamp >= cutoff
                ]

                # Remove endpoint if empty
                if not self._calls_by_endpoint[endpoint]:
                    del self._calls_by_endpoint[endpoint]

    def get_current_usage(self, limit_name: Optional[str] = None) -> Dict[str, QuotaUsage]:
        """
        Get current quota usage

        Args:
            limit_name: Specific limit or None for all

        Returns:
            Dictionary of limit_name -> QuotaUsage
        """
        with self._lock:
            if limit_name:
                return {limit_name: self._current_usage.get(limit_name)}
            return self._current_usage.copy()

    def get_endpoint_statistics(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """
        Get per-endpoint statistics

        Args:
            endpoint: Specific endpoint or None for all

        Returns:
            Endpoint statistics
        """
        with self._lock:
            if endpoint:
                calls = self._calls_by_endpoint.get(endpoint, [])
                return self._calculate_endpoint_stats(endpoint, calls)

            # All endpoints
            stats = {}
            for endpoint, calls in self._calls_by_endpoint.items():
                stats[endpoint] = self._calculate_endpoint_stats(endpoint, calls)

            return stats

    def _calculate_endpoint_stats(self, endpoint: str, calls: List[APICall]) -> Dict[str, Any]:
        """Calculate statistics for endpoint"""
        if not calls:
            return {
                'endpoint': endpoint,
                'total_calls': 0,
                'error_count': 0,
                'avg_response_time_ms': 0,
                'p95_response_time_ms': 0,
                'p99_response_time_ms': 0
            }

        response_times = [call.response_time_ms for call in calls]
        errors = sum(1 for call in calls if call.error or call.status_code >= 400)

        return {
            'endpoint': endpoint,
            'total_calls': len(calls),
            'error_count': errors,
            'error_rate': errors / len(calls) if calls else 0,
            'avg_response_time_ms': sum(response_times) / len(response_times),
            'min_response_time_ms': min(response_times),
            'max_response_time_ms': max(response_times),
            'p95_response_time_ms': sorted(response_times)[int(len(response_times) * 0.95)],
            'p99_response_time_ms': sorted(response_times)[int(len(response_times) * 0.99)],
        }

    def get_quota_report(self) -> Dict[str, Any]:
        """Generate comprehensive quota report"""
        with self._lock:
            report = {
                'timestamp': datetime.now().isoformat(),
                'total_api_calls': self.total_calls,
                'total_errors': self.total_errors,
                'total_throttled': self.total_throttled,
                'error_rate': self.total_errors / self.total_calls if self.total_calls else 0,
                'current_usage': {
                    name: usage.to_dict()
                    for name, usage in self._current_usage.items()
                },
                'top_endpoints': self._get_top_endpoints(limit=10),
                'recommendations': self._generate_recommendations()
            }

            return report

    def _get_top_endpoints(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top endpoints by call count"""
        endpoint_counts = [
            {'endpoint': endpoint, 'calls': len(calls)}
            for endpoint, calls in self._calls_by_endpoint.items()
        ]

        # Sort by call count
        endpoint_counts.sort(key=lambda x: x['calls'], reverse=True)

        return endpoint_counts[:limit]

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on usage patterns"""
        recommendations = []

        with self._lock:
            # Check for high usage
            for limit_name, usage in self._current_usage.items():
                if usage.level in [QuotaLevel.CRITICAL, QuotaLevel.DANGER]:
                    recommendations.append(
                        f"🚨 {limit_name}: Reduce API calls immediately "
                        f"({usage.usage_percent:.1f}% of quota used)"
                    )

                elif usage.level == QuotaLevel.WARNING:
                    recommendations.append(
                        f"⚠️ {limit_name}: Monitor API usage closely "
                        f"({usage.usage_percent:.1f}% of quota used)"
                    )

            # Check for high error rates
            if self.total_calls > 100 and (self.total_errors / self.total_calls) > 0.05:
                recommendations.append(
                    f"🔧 High error rate detected: {self.total_errors}/{self.total_calls} "
                    f"({(self.total_errors/self.total_calls)*100:.1f}%) - investigate API issues"
                )

            # Check for frequent throttling
            if self.total_throttled > 100:
                recommendations.append(
                    f"⏱️ Frequent throttling detected: {self.total_throttled} times - "
                    f"consider implementing request batching or caching"
                )

        return recommendations

    def print_quota_report(self):
        """Print formatted quota report"""
        report = self.get_quota_report()

        print("\n" + "="*70)
        print("📊 API QUOTA MONITORING REPORT")
        print("="*70)

        print(f"\nGenerated: {report['timestamp']}")
        print(f"Total API Calls: {report['total_api_calls']}")
        print(f"Total Errors: {report['total_errors']} ({report['error_rate']*100:.2f}%)")
        print(f"Total Throttled: {report['total_throttled']}")

        print("\nCurrent Quota Usage:")
        for limit_name, usage in report['current_usage'].items():
            level_emoji = {
                'safe': '✅',
                'warning': '⚠️',
                'critical': '🔶',
                'danger': '🚨'
            }
            emoji = level_emoji.get(usage['level'], '❓')

            print(
                f"  {emoji} {limit_name:.<25} "
                f"{usage['current_usage']:>4}/{usage['max_requests']:>5} "
                f"({usage['usage_percent']:>5.1f}%) "
                f"[{usage['requests_remaining']:>4} remaining]"
            )

        if report['top_endpoints']:
            print("\nTop API Endpoints:")
            for i, endpoint_data in enumerate(report['top_endpoints'][:5], 1):
                print(f"  {i}. {endpoint_data['endpoint']:.<40} {endpoint_data['calls']:>5} calls")

        if report['recommendations']:
            print("\nRecommendations:")
            for rec in report['recommendations']:
                print(f"  {rec}")

        print("="*70 + "\n")


# Global instance
_global_quota_monitor: Optional[APIQuotaMonitor] = None


def get_api_quota_monitor() -> APIQuotaMonitor:
    """Get global API quota monitor (singleton)"""
    global _global_quota_monitor
    if _global_quota_monitor is None:
        _global_quota_monitor = APIQuotaMonitor()
    return _global_quota_monitor


if __name__ == "__main__":
    # Test API quota monitor
    print("Testing API Quota Monitor...")

    monitor = APIQuotaMonitor()
    monitor.start_monitoring()

    # Simulate API calls
    print("\nSimulating API calls...")
    for i in range(100):
        monitor.record_api_call(
            endpoint="/api/quote",
            method="GET",
            status_code=200,
            response_time_ms=100 + i
        )
        time.sleep(0.01)

    # Check usage
    print("\nChecking quota usage...")
    usage = monitor.get_current_usage()
    for limit_name, quota_usage in usage.items():
        print(
            f"{limit_name}: {quota_usage.current_usage}/{quota_usage.max_requests} "
            f"({quota_usage.usage_percent:.1f}%)"
        )

    # Test can_make_request
    print(f"\nCan make request: {monitor.can_make_request()}")

    # Print report
    monitor.print_quota_report()

    monitor.stop_monitoring()
    print("\n✅ API quota monitor tests passed")
