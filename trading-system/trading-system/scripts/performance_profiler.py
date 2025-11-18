#!/usr/bin/env python3
"""
Performance Profiling Script
Month 2 - Week 2 Task

Profiles key operations and generates performance baseline report
"""

import cProfile
import pstats
import io
import time
import psutil
import os
import sys
from pathlib import Path
from typing import Dict, List, Any
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class PerformanceProfiler:
    """Profile trading system performance"""

    def __init__(self):
        self.results = {}
        self.process = psutil.Process(os.getpid())

    def profile_function(self, func, *args, **kwargs) -> Dict[str, Any]:
        """Profile a single function"""
        # CPU profiling
        profiler = cProfile.Profile()

        # Memory before
        mem_before = self.process.memory_info().rss / 1024 / 1024  # MB

        # Time execution
        start_time = time.time()
        profiler.enable()

        try:
            result = func(*args, **kwargs)
            success = True
            error = None
        except Exception as e:
            result = None
            success = False
            error = str(e)

        profiler.disable()
        duration = time.time() - start_time

        # Memory after
        mem_after = self.process.memory_info().rss / 1024 / 1024  # MB
        mem_delta = mem_after - mem_before

        # Get stats
        s = io.StringIO()
        stats = pstats.Stats(profiler, stream=s)
        stats.sort_stats('cumulative')
        stats.print_stats(10)  # Top 10 functions

        return {
            'function': func.__name__,
            'duration_ms': duration * 1000,
            'memory_before_mb': mem_before,
            'memory_after_mb': mem_after,
            'memory_delta_mb': mem_delta,
            'success': success,
            'error': error,
            'profile_output': s.getvalue()
        }

    def profile_import_times(self) -> Dict[str, float]:
        """Profile module import times"""
        import_times = {}

        modules_to_test = [
            'config',
            'core.trading_system',
            'core.portfolio',
            'strategies.moving_average',
            'fno.terminal',
            'utilities.structured_logger',
            'infrastructure.performance_monitor'
        ]

        for module in modules_to_test:
            start = time.time()
            try:
                __import__(module)
                duration = (time.time() - start) * 1000
                import_times[module] = duration
            except Exception as e:
                import_times[module] = f"Error: {e}"

        return import_times

    def profile_system_resources(self) -> Dict[str, Any]:
        """Profile system resource usage"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            'cpu_percent': cpu_percent,
            'cpu_count': psutil.cpu_count(),
            'memory_total_gb': memory.total / 1024 / 1024 / 1024,
            'memory_available_gb': memory.available / 1024 / 1024 / 1024,
            'memory_percent': memory.percent,
            'disk_total_gb': disk.total / 1024 / 1024 / 1024,
            'disk_used_gb': disk.used / 1024 / 1024 / 1024,
            'disk_percent': disk.percent
        }

    def generate_report(self, output_file: str = 'performance_baseline_report.json'):
        """Generate performance report"""
        print("="*70)
        print("PERFORMANCE PROFILING REPORT")
        print("="*70)
        print()

        # System resources
        print("1. System Resources")
        print("-" * 70)
        resources = self.profile_system_resources()
        for key, value in resources.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")

        # Import times
        print("\n2. Module Import Times")
        print("-" * 70)
        import_times = self.profile_import_times()
        for module, duration in sorted(import_times.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0, reverse=True):
            if isinstance(duration, (int, float)):
                print(f"  {module}: {duration:.2f}ms")
            else:
                print(f"  {module}: {duration}")

        # Test function profiling
        print("\n3. Function Performance Tests")
        print("-" * 70)

        # Test config loading
        print("\n  Testing: Config Loading")
        try:
            from config import get_config

            def test_config():
                cfg = get_config()
                return cfg.get("trading.default_capital")

            result = self.profile_function(test_config)
            print(f"    Duration: {result['duration_ms']:.2f}ms")
            print(f"    Memory Delta: {result['memory_delta_mb']:.2f}MB")
        except Exception as e:
            print(f"    Error: {e}")

        # Test strategy import
        print("\n  Testing: Strategy Import")
        try:
            def test_strategy_import():
                from strategies.moving_average import MovingAverageCrossover
                return MovingAverageCrossover

            result = self.profile_function(test_strategy_import)
            print(f"    Duration: {result['duration_ms']:.2f}ms")
            print(f"    Memory Delta: {result['memory_delta_mb']:.2f}MB")
        except Exception as e:
            print(f"    Error: {e}")

        # Compile results
        full_report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'system_resources': resources,
            'import_times': import_times,
            'baseline_established': True
        }

        # Save report
        with open(output_file, 'w') as f:
            json.dump(full_report, f, indent=2)

        print(f"\n📊 Full report saved to: {output_file}")

        # Recommendations
        print("\n4. Optimization Recommendations")
        print("-" * 70)

        recommendations = []

        # Check import times
        slow_imports = [m for m, t in import_times.items() if isinstance(t, (int, float)) and t > 100]
        if slow_imports:
            recommendations.append(f"⚠️  Slow imports detected: {', '.join(slow_imports)}")
            recommendations.append("   Consider lazy imports or optimization")

        # Check memory
        if resources['memory_percent'] > 80:
            recommendations.append(f"⚠️  High memory usage: {resources['memory_percent']:.1f}%")
            recommendations.append("   Consider memory optimization")

        # Check CPU
        if resources['cpu_percent'] > 70:
            recommendations.append(f"⚠️  High CPU usage: {resources['cpu_percent']:.1f}%")
            recommendations.append("   Consider CPU optimization")

        # Check disk
        if resources['disk_percent'] > 80:
            recommendations.append(f"⚠️  Low disk space: {100-resources['disk_percent']:.1f}% free")
            recommendations.append("   Consider cleanup or expansion")

        if recommendations:
            for rec in recommendations:
                print(f"  {rec}")
        else:
            print("  ✅ No immediate optimization concerns detected")

        print("\n" + "="*70)
        print("PERFORMANCE BASELINE ESTABLISHED")
        print("="*70)


def main():
    """Run performance profiling"""
    profiler = PerformanceProfiler()
    profiler.generate_report()

    print("\n📋 Next Steps:")
    print("1. Review performance_baseline_report.json")
    print("2. Address any recommendations above")
    print("3. Profile specific bottlenecks with cProfile")
    print("4. Run load tests to find scalability limits")
    print("5. Implement optimizations and re-baseline")


if __name__ == "__main__":
    main()
