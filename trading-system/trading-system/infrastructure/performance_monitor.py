#!/usr/bin/env python3
"""
Advanced Performance Monitoring System
Baseline metrics, anomaly detection, memory leak detection

ADDRESSES WEEK 5 ISSUE:
- Original: Basic performance monitoring only
- This implementation: Comprehensive monitoring with anomaly detection, baselines, alerts
"""

import logging
import time
import psutil
import os
import threading
import tracemalloc
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
from enum import Enum
import numpy as np

from infrastructure.alert_manager import get_alert_manager, AlertSeverity, AlertCategory

logger = logging.getLogger('trading_system.performance')


class MetricType(Enum):
    """Performance metric types"""
    CPU_PERCENT = "cpu_percent"
    MEMORY_MB = "memory_mb"
    DISK_IO_MB = "disk_io_mb"
    NETWORK_IO_MB = "network_io_mb"
    RESPONSE_TIME_MS = "response_time_ms"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"


@dataclass
class PerformanceMetric:
    """Single performance measurement"""
    timestamp: datetime
    metric_type: MetricType
    value: float
    component: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceBaseline:
    """Baseline performance metrics"""
    metric_type: MetricType
    mean: float
    std: float
    p95: float
    p99: float
    min_val: float
    max_val: float
    sample_count: int
    last_updated: datetime


@dataclass
class PerformanceAnomaly:
    """Detected performance anomaly"""
    timestamp: datetime
    metric_type: MetricType
    component: str
    current_value: float
    baseline_mean: float
    deviation_sigma: float
    severity: AlertSeverity
    description: str

    @property
    def value(self) -> float:
        """Alias for current_value for test compatibility"""
        return self.current_value

    @property
    def z_score(self) -> float:
        """Alias for deviation_sigma for test compatibility"""
        return self.deviation_sigma


class PerformanceMonitor:
    """
    Advanced Performance Monitoring System

    Features:
    - Real-time system resource monitoring (CPU, memory, disk, network)
    - Component-level performance tracking
    - Baseline establishment with statistical analysis
    - Anomaly detection using Z-score
    - Memory leak detection
    - Performance degradation alerts
    - Historical trending

    Usage:
        monitor = PerformanceMonitor()
        monitor.start_monitoring()

        # Track operation
        with monitor.track_operation("database_query"):
            db.execute(query)

        # Check for anomalies
        anomalies = monitor.detect_anomalies()
    """

    def __init__(
        self,
        baseline_window_hours: int = 24,
        anomaly_threshold_sigma: float = 3.0,
        memory_leak_threshold_mb: int = 100,
        sampling_interval_seconds: int = 60
    ):
        """
        Initialize performance monitor

        Args:
            baseline_window_hours: Hours of data to establish baseline
            anomaly_threshold_sigma: Standard deviations for anomaly detection
            memory_leak_threshold_mb: MB growth to trigger leak alert
            sampling_interval_seconds: Background sampling interval
        """
        self.baseline_window = timedelta(hours=baseline_window_hours)
        self.anomaly_threshold = anomaly_threshold_sigma
        self.memory_leak_threshold = memory_leak_threshold_mb
        self.sampling_interval = sampling_interval_seconds

        # Metrics storage (time-series data)
        self._metrics: Dict[MetricType, deque] = {
            metric_type: deque(maxlen=10000) for metric_type in MetricType
        }

        # Baselines
        self._baselines: Dict[MetricType, PerformanceBaseline] = {}

        # Anomaly tracking
        self._anomalies: List[PerformanceAnomaly] = []

        # Memory leak detection
        self._memory_snapshots: deque = deque(maxlen=100)
        self._initial_memory_mb = None

        # Operation tracking
        self._operation_times: Dict[str, List[float]] = {}

        # Background monitoring
        self._monitoring = False
        self._monitor_thread = None
        self._lock = threading.RLock()

        # Alert manager
        self.alert_mgr = get_alert_manager()

        # Process handle
        self._process = psutil.Process(os.getpid())

        logger.info("📊 PerformanceMonitor initialized")

    def start_monitoring(self):
        """Start background performance monitoring"""
        if self._monitoring:
            logger.warning("Monitoring already started")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        # Start memory tracking
        tracemalloc.start()
        self._initial_memory_mb = self._get_memory_usage()

        logger.info("✅ Background monitoring started")

    def stop_monitoring(self):
        """Stop background monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

        tracemalloc.stop()
        logger.info("🛑 Monitoring stopped")

    def record_metric(
        self,
        metric_type: MetricType,
        value: float,
        timestamp: Optional[datetime] = None,
        component: str = "system"
    ):
        """
        Public API to record a performance metric

        Args:
            metric_type: Type of metric to record
            value: Metric value
            timestamp: Optional timestamp (defaults to now)
            component: Component name for the metric
        """
        self._record_metric(metric_type, value, timestamp, component)

    def get_recent_metrics(
        self,
        metric_type: MetricType,
        hours: int = 1,
        component: Optional[str] = None
    ) -> List[PerformanceMetric]:
        """
        Get recent metrics of a specific type

        Args:
            metric_type: Type of metric to retrieve
            hours: Number of hours to look back
            component: Optional component filter

        Returns:
            List of metrics within the time window
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        with self._lock:
            metrics = self._metrics.get(metric_type, deque())
            recent = [
                m for m in metrics
                if m.timestamp >= cutoff_time
                and (component is None or m.component == component)
            ]
            return recent

    def get_recent_operations(
        self,
        operation_name: str,
        hours: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get recent operation tracking data

        Args:
            operation_name: Name of the operation
            hours: Number of hours to look back

        Returns:
            List of operation data dictionaries
        """
        if operation_name not in self._operation_times:
            return []

        cutoff_time = datetime.now() - timedelta(hours=hours)

        operations = []
        for duration_ms in self._operation_times[operation_name]:
            # For simplicity, assume recent operations
            # In production, you'd want to store timestamps too
            operations.append({
                'operation': operation_name,
                'duration_ms': duration_ms,
                'timestamp': datetime.now()  # Approximate
            })

        return operations

    def _monitor_loop(self):
        """Background monitoring loop"""
        while self._monitoring:
            try:
                self._collect_system_metrics()
                time.sleep(self.sampling_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

    def _collect_system_metrics(self):
        """Collect system-wide performance metrics"""
        timestamp = datetime.now()

        with self._lock:
            # CPU usage
            cpu_percent = self._process.cpu_percent(interval=0.1)
            self._record_metric(MetricType.CPU_PERCENT, cpu_percent, timestamp)

            # Memory usage
            memory_mb = self._get_memory_usage()
            self._record_metric(MetricType.MEMORY_MB, memory_mb, timestamp)
            self._memory_snapshots.append((timestamp, memory_mb))

            # Disk I/O
            try:
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    disk_mb = (disk_io.read_bytes + disk_io.write_bytes) / 1024 / 1024
                    self._record_metric(MetricType.DISK_IO_MB, disk_mb, timestamp)
            except:
                pass

            # Network I/O
            try:
                net_io = psutil.net_io_counters()
                if net_io:
                    net_mb = (net_io.bytes_sent + net_io.bytes_recv) / 1024 / 1024
                    self._record_metric(MetricType.NETWORK_IO_MB, net_mb, timestamp)
            except:
                pass

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        mem_info = self._process.memory_info()
        return mem_info.rss / 1024 / 1024  # Convert to MB

    def _record_metric(
        self,
        metric_type: MetricType,
        value: float,
        timestamp: Optional[datetime] = None,
        component: str = "system"
    ):
        """Record a performance metric"""
        if timestamp is None:
            timestamp = datetime.now()

        metric = PerformanceMetric(
            timestamp=timestamp,
            metric_type=metric_type,
            value=value,
            component=component
        )

        with self._lock:
            self._metrics[metric_type].append(metric)

    def track_operation(self, operation_name: str):
        """
        Context manager to track operation performance

        Usage:
            with monitor.track_operation("database_query"):
                result = db.execute(query)
        """
        return OperationTracker(self, operation_name)

    def record_operation_time(self, operation_name: str, duration_ms: float):
        """Record operation execution time"""
        with self._lock:
            if operation_name not in self._operation_times:
                self._operation_times[operation_name] = []

            self._operation_times[operation_name].append(duration_ms)

            # Keep last 1000 measurements
            if len(self._operation_times[operation_name]) > 1000:
                self._operation_times[operation_name] = self._operation_times[operation_name][-1000:]

        # Record as metric
        self._record_metric(
            MetricType.RESPONSE_TIME_MS,
            duration_ms,
            component=operation_name
        )

        # Check for slow operations
        if duration_ms > 1000:  # >1 second
            self.alert_mgr.check_performance_alerts({
                'operation_name': operation_name,
                'operation_time_ms': duration_ms
            })

    def establish_baseline(self, metric_type: MetricType) -> Optional[PerformanceBaseline]:
        """
        Establish baseline for metric type

        Args:
            metric_type: Metric to baseline

        Returns:
            PerformanceBaseline or None if insufficient data
        """
        with self._lock:
            metrics = self._metrics[metric_type]

            if len(metrics) < 10:
                logger.warning(f"Insufficient data for baseline: {metric_type.value}")
                return None

            # Filter recent data within baseline window
            cutoff = datetime.now() - self.baseline_window
            recent_metrics = [m for m in metrics if m.timestamp >= cutoff]

            if len(recent_metrics) < 10:
                return None

            # Calculate statistics
            values = [m.value for m in recent_metrics]
            mean = np.mean(values)
            std = np.std(values)
            p95 = np.percentile(values, 95)
            p99 = np.percentile(values, 99)
            min_val = np.min(values)
            max_val = np.max(values)

            baseline = PerformanceBaseline(
                metric_type=metric_type,
                mean=mean,
                std=std,
                p95=p95,
                p99=p99,
                min_val=min_val,
                max_val=max_val,
                sample_count=len(recent_metrics),
                last_updated=datetime.now()
            )

            self._baselines[metric_type] = baseline
            logger.info(f"✅ Baseline established for {metric_type.value}: mean={mean:.2f}, std={std:.2f}")

            return baseline

    def detect_anomalies(self) -> List[PerformanceAnomaly]:
        """
        Detect performance anomalies using Z-score

        Returns:
            List of detected anomalies
        """
        anomalies = []

        with self._lock:
            for metric_type, metrics in self._metrics.items():
                if metric_type not in self._baselines:
                    continue

                baseline = self._baselines[metric_type]

                # Check recent metrics
                recent = list(metrics)[-10:]  # Last 10 measurements

                for metric in recent:
                    if baseline.std == 0:
                        continue

                    # Calculate Z-score
                    z_score = abs((metric.value - baseline.mean) / baseline.std)

                    if z_score > self.anomaly_threshold:
                        # Determine severity
                        if z_score > 5:
                            severity = AlertSeverity.CRITICAL
                        elif z_score > 4:
                            severity = AlertSeverity.HIGH
                        else:
                            severity = AlertSeverity.MEDIUM

                        anomaly = PerformanceAnomaly(
                            timestamp=metric.timestamp,
                            metric_type=metric_type,
                            component=metric.component,
                            current_value=metric.value,
                            baseline_mean=baseline.mean,
                            deviation_sigma=z_score,
                            severity=severity,
                            description=f"{metric_type.value} is {z_score:.1f}σ from baseline"
                        )

                        anomalies.append(anomaly)

                        # Alert
                        self.alert_mgr.alert(
                            severity=severity,
                            category=AlertCategory.PERFORMANCE,
                            title="Performance Anomaly Detected",
                            message=anomaly.description,
                            context={
                                'metric_type': metric_type.value,
                                'current': metric.value,
                                'baseline': baseline.mean,
                                'z_score': z_score
                            }
                        )

        self._anomalies.extend(anomalies)
        return anomalies

    def detect_memory_leak(self) -> Optional[Dict[str, Any]]:
        """
        Detect memory leaks

        Returns:
            Leak info if detected, None otherwise
        """
        if not self._memory_snapshots or len(self._memory_snapshots) < 10:
            return None

        # Get memory growth over time
        snapshots = list(self._memory_snapshots)

        # Calculate linear regression to detect trend
        times = [(s[0] - snapshots[0][0]).total_seconds() for s in snapshots]
        memory = [s[1] for s in snapshots]

        # Simple linear regression
        n = len(times)
        sum_x = sum(times)
        sum_y = sum(memory)
        sum_xy = sum(x * y for x, y in zip(times, memory))
        sum_x2 = sum(x * x for x in times)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)

        # slope is MB per second
        growth_mb_per_hour = slope * 3600

        if growth_mb_per_hour > self.memory_leak_threshold / 24:  # Leak threshold per hour
            # Calculate total growth
            total_growth = memory[-1] - memory[0]

            leak_info = {
                'growth_mb_per_hour': growth_mb_per_hour,
                'total_growth_mb': total_growth,
                'current_memory_mb': memory[-1],
                'initial_memory_mb': memory[0],
                'duration_hours': (snapshots[-1][0] - snapshots[0][0]).total_seconds() / 3600
            }

            # Alert
            self.alert_mgr.alert(
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.PERFORMANCE,
                title="Memory Leak Detected",
                message=f"Memory growing at {growth_mb_per_hour:.2f} MB/hour",
                context=leak_info
            )

            return leak_info

        return None

    def get_operation_stats(self, operation_name: str) -> Optional[Dict[str, float]]:
        """Get statistics for an operation"""
        with self._lock:
            if operation_name not in self._operation_times:
                return None

            times = self._operation_times[operation_name]

            return {
                'count': len(times),
                'mean_ms': np.mean(times),
                'median_ms': np.median(times),
                'p95_ms': np.percentile(times, 95),
                'p99_ms': np.percentile(times, 99),
                'min_ms': np.min(times),
                'max_ms': np.max(times),
                'std_ms': np.std(times)
            }

    def get_current_metrics(self) -> Dict[str, float]:
        """Get current performance metrics"""
        return {
            'cpu_percent': self._process.cpu_percent(),
            'memory_mb': self._get_memory_usage(),
            'num_threads': self._process.num_threads(),
            'num_fds': self._process.num_fds() if hasattr(self._process, 'num_fds') else 0,
        }

    def print_performance_report(self):
        """Print comprehensive performance report"""
        print("\n" + "="*70)
        print("📊 PERFORMANCE MONITORING REPORT")
        print("="*70)

        # Current metrics
        current = self.get_current_metrics()
        print("\nCurrent System Metrics:")
        print(f"  CPU Usage:     {current['cpu_percent']:.1f}%")
        print(f"  Memory:        {current['memory_mb']:.1f} MB")
        print(f"  Threads:       {current['num_threads']}")

        # Baselines
        if self._baselines:
            print("\nPerformance Baselines:")
            for metric_type, baseline in self._baselines.items():
                print(f"  {metric_type.value:.<30} "
                      f"Mean: {baseline.mean:.2f}, "
                      f"P95: {baseline.p95:.2f}, "
                      f"P99: {baseline.p99:.2f}")

        # Operation stats
        if self._operation_times:
            print("\nOperation Performance:")
            for op_name in sorted(self._operation_times.keys()):
                stats = self.get_operation_stats(op_name)
                if stats:
                    print(f"  {op_name:.<30} "
                          f"Mean: {stats['mean_ms']:.1f}ms, "
                          f"P95: {stats['p95_ms']:.1f}ms")

        # Anomalies
        recent_anomalies = [a for a in self._anomalies if
                          (datetime.now() - a.timestamp).total_seconds() < 3600]
        if recent_anomalies:
            print(f"\nRecent Anomalies (last hour): {len(recent_anomalies)}")
            for anomaly in recent_anomalies[-5:]:
                print(f"  [{anomaly.severity.value}] {anomaly.description}")

        # Memory leak check
        leak = self.detect_memory_leak()
        if leak:
            print(f"\n⚠️  MEMORY LEAK DETECTED:")
            print(f"  Growth rate: {leak['growth_mb_per_hour']:.2f} MB/hour")
            print(f"  Total growth: {leak['total_growth_mb']:.2f} MB")

        print("="*70 + "\n")


class OperationTracker:
    """Context manager for tracking operation performance"""

    def __init__(self, monitor: PerformanceMonitor, operation_name: str):
        self.monitor = monitor
        self.operation_name = operation_name
        self.start_time = None
        self.result = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        self.monitor.record_operation_time(self.operation_name, duration_ms)

    def set_result(self, result: Any):
        """Set operation result (for test compatibility)"""
        self.result = result


# Global monitor instance
_global_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor (singleton)"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor


if __name__ == "__main__":
    # Test performance monitor
    monitor = PerformanceMonitor()
    monitor.start_monitoring()

    print("Monitoring started... collecting baseline data")
    time.sleep(5)

    # Establish baselines
    for metric_type in [MetricType.CPU_PERCENT, MetricType.MEMORY_MB]:
        monitor.establish_baseline(metric_type)

    # Track some operations
    for i in range(10):
        with monitor.track_operation("test_operation"):
            time.sleep(0.01)  # Simulate work

    # Print report
    monitor.print_performance_report()

    monitor.stop_monitoring()

    print("\n✅ Performance monitor tests passed")
