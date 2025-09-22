#!/usr/bin/env python3
"""
Performance monitoring system for trading application
"""

import time
import psutil
import threading
from datetime import datetime
from typing import Dict, List, Optional, Callable
from collections import defaultdict, deque
import logging
from pathlib import Path
import json

class PerformanceMetrics:
    """Performance metrics collector"""

    def __init__(self, max_metrics: int = 1000):
        self.metrics = defaultdict(lambda: deque(maxlen=max_metrics))
        self.counters = defaultdict(int)
        self.gauges = {}
        self.histograms = defaultdict(lambda: {'sum': 0, 'count': 0, 'min': float('inf'), 'max': 0})

    def record_metric(self, name: str, value: float, timestamp: Optional[float] = None):
        """Record a metric value"""
        if timestamp is None:
            timestamp = time.time()
        self.metrics[name].append((timestamp, value))

    def increment_counter(self, name: str, value: int = 1):
        """Increment a counter"""
        self.counters[name] += value

    def set_gauge(self, name: str, value: float):
        """Set a gauge value"""
        self.gauges[name] = value

    def record_histogram(self, name: str, value: float):
        """Record histogram data"""
        hist = self.histograms[name]
        hist['sum'] += value
        hist['count'] += 1
        hist['min'] = min(hist['min'], value)
        hist['max'] = max(hist['max'], value)

    def get_metrics_summary(self, name: str, window_seconds: int = 60) -> Dict:
        """Get summary of metrics for a given name"""
        if name not in self.metrics:
            return {}

        now = time.time()
        recent_metrics = [v for t, v in self.metrics[name] if now - t <= window_seconds]

        if not recent_metrics:
            return {}

        return {
            'count': len(recent_metrics),
            'avg': sum(recent_metrics) / len(recent_metrics),
            'min': min(recent_metrics),
            'max': max(recent_metrics),
            'latest': recent_metrics[-1] if recent_metrics else 0
        }

    def get_all_summaries(self, window_seconds: int = 60) -> Dict:
        """Get summaries for all metrics"""
        return {name: self.get_metrics_summary(name, window_seconds) for name in self.metrics.keys()}

class SystemMonitor:
    """System resource monitor"""

    def __init__(self):
        self.process = psutil.Process()
        self.last_cpu_time = None
        self.last_check_time = time.time()

    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage"""
        try:
            cpu_percent = self.process.cpu_percent(interval=1.0)
            return cpu_percent
        except Exception:
            return 0.0

    def get_memory_usage(self) -> Dict:
        """Get memory usage information"""
        try:
            memory_info = self.process.memory_info()
            return {
                'rss': memory_info.rss,  # Resident Set Size
                'vms': memory_info.vms,  # Virtual Memory Size
                'percent': self.process.memory_percent()
            }
        except Exception:
            return {'rss': 0, 'vms': 0, 'percent': 0.0}

    def get_thread_count(self) -> int:
        """Get number of threads"""
        try:
            return self.process.num_threads()
        except Exception:
            return 0

    def get_file_handles(self) -> int:
        """Get number of open file handles"""
        try:
            return len(self.process.open_files())
        except Exception:
            return 0

class PerformanceMonitor:
    """Main performance monitoring class"""

    def __init__(self, log_dir: str = "logs"):
        self.metrics = PerformanceMetrics()
        self.system_monitor = SystemMonitor()
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Monitoring state
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitoring_interval = 5.0  # seconds

        # Setup logging
        self.logger = logging.getLogger('performance_monitor')
        self.logger.setLevel(logging.INFO)

        # File handler for performance logs
        log_file = self.log_dir / f'performance_{datetime.now().strftime("%Y-%m-%d")}.log'
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def start_monitoring(self):
        """Start performance monitoring"""
        if self.is_monitoring:
            return

        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("Performance monitoring started")

    def stop_monitoring(self):
        """Stop performance monitoring"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        self.logger.info("Performance monitoring stopped")

    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                self._collect_system_metrics()
                self._collect_application_metrics()
                time.sleep(self.monitoring_interval)
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(1.0)

    def _collect_system_metrics(self):
        """Collect system-level metrics"""
        try:
            # CPU usage
            cpu_usage = self.system_monitor.get_cpu_usage()
            self.metrics.record_metric('cpu_usage', cpu_usage)

            # Memory usage
            memory_info = self.system_monitor.get_memory_usage()
            self.metrics.record_metric('memory_rss', memory_info['rss'])
            self.metrics.record_metric('memory_percent', memory_info['percent'])

            # Thread count
            thread_count = self.system_monitor.get_thread_count()
            self.metrics.set_gauge('thread_count', thread_count)

            # File handles
            file_handles = self.system_monitor.get_file_handles()
            self.metrics.set_gauge('file_handles', file_handles)

        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")

    def _collect_application_metrics(self):
        """Collect application-level metrics"""
        try:
            # Get all metrics summaries
            summaries = self.metrics.get_all_summaries()

            # Log periodic summary
            if time.time() - self.last_check_time > 60:  # Log every minute
                self._log_performance_summary(summaries)
                self.last_check_time = time.time()

        except Exception as e:
            self.logger.error(f"Error collecting application metrics: {e}")

    def _log_performance_summary(self, summaries: Dict):
        """Log performance summary"""
        try:
            summary = {
                'timestamp': datetime.now().isoformat(),
                'system': {
                    'cpu_usage': summaries.get('cpu_usage', {}).get('avg', 0),
                    'memory_percent': summaries.get('memory_percent', {}).get('latest', 0),
                    'thread_count': self.metrics.gauges.get('thread_count', 0),
                    'file_handles': self.metrics.gauges.get('file_handles', 0)
                },
                'application': {
                    name: data for name, data in summaries.items()
                    if name not in ['cpu_usage', 'memory_rss', 'memory_percent']
                }
            }

            # Log to file
            log_file = self.log_dir / f'performance_summary_{datetime.now().strftime("%Y-%m-%d")}.json'
            with open(log_file, 'a') as f:
                f.write(json.dumps(summary) + '\n')

            # Log key metrics
            self.logger.info(
                f"Performance: CPU={summary['system']['cpu_usage']:.1f}%, "
                f"Memory={summary['system']['memory_percent']:.1f}%, "
                f"Threads={summary['system']['thread_count']}"
            )

        except Exception as e:
            self.logger.error(f"Error logging performance summary: {e}")

    def record_api_call(self, endpoint: str, method: str, duration: float, status_code: Optional[int] = None):
        """Record API call metrics"""
        metric_name = f'api_{method.lower()}_{endpoint.replace("/", "_")}'
        self.metrics.record_histogram(metric_name, duration)

        if status_code:
            status_metric = f'api_status_{status_code}'
            self.metrics.increment_counter(status_metric)

    def record_trade_execution(self, symbol: str, duration: float, success: bool = True):
        """Record trade execution metrics"""
        metric_name = f'trade_execution_{symbol}'
        self.metrics.record_histogram(metric_name, duration)

        if success:
            self.metrics.increment_counter('trades_successful')
        else:
            self.metrics.increment_counter('trades_failed')

    def record_strategy_signal(self, strategy_name: str, symbol: str, signal_type: str, confidence: float):
        """Record strategy signal metrics"""
        metric_name = f'strategy_{strategy_name.lower()}_{signal_type}'
        self.metrics.record_metric(metric_name, confidence)

        # Track signal counts
        self.metrics.increment_counter(f'signals_{signal_type}')

    def record_data_fetch(self, symbol: str, source: str, duration: float, success: bool = True):
        """Record data fetch metrics"""
        metric_name = f'data_fetch_{source}_{symbol}'
        self.metrics.record_histogram(metric_name, duration)

        if success:
            self.metrics.increment_counter('data_fetches_successful')
        else:
            self.metrics.increment_counter('data_fetches_failed')

    def get_performance_report(self, hours: int = 1) -> Dict:
        """Generate performance report"""
        window_seconds = hours * 3600
        summaries = self.metrics.get_all_summaries(window_seconds)

        report = {
            'period_hours': hours,
            'generated_at': datetime.now().isoformat(),
            'system_metrics': {
                'cpu_usage': summaries.get('cpu_usage', {}),
                'memory_usage': summaries.get('memory_percent', {}),
                'thread_count': self.metrics.gauges.get('thread_count', 0),
                'file_handles': self.metrics.gauges.get('file_handles', 0)
            },
            'api_metrics': {
                name: data for name, data in summaries.items()
                if name.startswith('api_')
            },
            'trade_metrics': {
                name: data for name, data in summaries.items()
                if name.startswith('trade_')
            },
            'strategy_metrics': {
                name: data for name, data in summaries.items()
                if name.startswith('strategy_')
            },
            'data_metrics': {
                name: data for name, data in summaries.items()
                if name.startswith('data_')
            },
            'counters': dict(self.metrics.counters),
            'histograms': dict(self.metrics.histograms)
        }

        return report

    def save_performance_report(self, hours: int = 1, filename: str = None):
        """Save performance report to file"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'performance_report_{timestamp}.json'

        report = self.get_performance_report(hours)
        report_path = self.log_dir / filename

        try:
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            self.logger.info(f"Performance report saved to {report_path}")
            return str(report_path)
        except Exception as e:
            self.logger.error(f"Error saving performance report: {e}")
            return None

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

def timing_decorator(metric_name: str):
    """Decorator to time function execution"""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                performance_monitor.metrics.record_histogram(metric_name, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                performance_monitor.metrics.record_histogram(metric_name, duration)
                raise
        return wrapper
    return decorator

def monitor_api_call(endpoint: str, method: str):
    """Decorator to monitor API calls"""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                performance_monitor.record_api_call(endpoint, method, duration, 200)
                return result
            except Exception as e:
                duration = time.time() - start_time
                performance_monitor.record_api_call(endpoint, method, duration, None)
                raise
        return wrapper
    return decorator

# Context managers for performance monitoring
class Timer:
    """Context manager for timing operations"""

    def __init__(self, metric_name: str):
        self.metric_name = metric_name
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            performance_monitor.metrics.record_histogram(self.metric_name, duration)

class APITimer:
    """Context manager for timing API calls"""

    def __init__(self, endpoint: str, method: str):
        self.endpoint = endpoint
        self.method = method
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            status_code = 200 if exc_type is None else None
            performance_monitor.record_api_call(self.endpoint, self.method, duration, status_code)

if __name__ == "__main__":
    # Example usage
    monitor = PerformanceMonitor()

    # Start monitoring
    monitor.start_monitoring()

    # Simulate some activity
    import time
    for i in range(10):
        with Timer('test_operation'):
            time.sleep(0.1)

        with APITimer('test/endpoint', 'GET'):
            time.sleep(0.05)

        monitor.record_trade_execution('AAPL', 0.1, True)
        monitor.record_strategy_signal('RSI', 'AAPL', 'buy', 0.8)

        time.sleep(1)

    # Generate report
    report = monitor.get_performance_report()
    print("Performance Report Generated:")
    print(f"System CPU: {report['system_metrics']['cpu_usage']}")
    print(f"Total Trades: {report['counters'].get('trades_successful', 0)}")

    # Save report
    monitor.save_performance_report()

    # Stop monitoring
    monitor.stop_monitoring()