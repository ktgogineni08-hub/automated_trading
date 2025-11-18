#!/usr/bin/env python3
"""
Comprehensive tests for metrics_exporter.py module
Tests Prometheus metrics, simple fallback metrics, and global metrics
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock prometheus_client before importing
mock_prometheus = MagicMock()
mock_prometheus.Counter = MagicMock
mock_prometheus.Gauge = MagicMock
mock_prometheus.Histogram = MagicMock
mock_prometheus.Summary = MagicMock
mock_prometheus.CollectorRegistry = MagicMock
mock_prometheus.generate_latest = MagicMock(return_value=b'# Prometheus metrics\ntest_metric 42\n')
mock_prometheus.CONTENT_TYPE_LATEST = 'text/plain; version=0.0.4; charset=utf-8'

sys.modules['prometheus_client'] = mock_prometheus

from core.metrics_exporter import (
    TradingMetrics,
    get_global_metrics,
    set_global_metrics,
    create_metrics_endpoint,
    PROMETHEUS_AVAILABLE
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def prometheus_metrics():
    """Create TradingMetrics with Prometheus enabled"""
    # Force PROMETHEUS_AVAILABLE to True
    with patch('core.metrics_exporter.PROMETHEUS_AVAILABLE', True):
        return TradingMetrics(enable_prometheus=True)


@pytest.fixture
def simple_metrics():
    """Create TradingMetrics with simple fallback mode"""
    return TradingMetrics(enable_prometheus=False)


# ============================================================================
# Initialization Tests
# ============================================================================

class TestInitialization:
    """Test TradingMetrics initialization"""

    def test_initialization_prometheus_disabled(self):
        """Test initialization with Prometheus disabled"""
        metrics = TradingMetrics(enable_prometheus=False)

        assert metrics.enable_prometheus is False
        assert hasattr(metrics, '_simple_metrics')
        assert hasattr(metrics, '_lock')

    def test_initialization_prometheus_enabled(self):
        """Test initialization with Prometheus enabled"""
        with patch('core.metrics_exporter.PROMETHEUS_AVAILABLE', True):
            metrics = TradingMetrics(enable_prometheus=True)

            assert metrics.enable_prometheus is True
            assert hasattr(metrics, 'registry')

    def test_initialization_with_custom_registry(self):
        """Test initialization with custom registry"""
        custom_registry = MagicMock()

        with patch('core.metrics_exporter.PROMETHEUS_AVAILABLE', True):
            metrics = TradingMetrics(registry=custom_registry, enable_prometheus=True)

            assert metrics.registry == custom_registry


# ============================================================================
# System Health Metrics Tests
# ============================================================================

class TestSystemHealthMetrics:
    """Test system health metric methods"""

    def test_set_uptime_simple_mode(self, simple_metrics):
        """Test setting uptime in simple mode"""
        simple_metrics.set_uptime(3600.0)

        simple = simple_metrics.get_simple_metrics()
        assert simple['uptime_seconds'] == 3600.0

    def test_set_active_positions_simple_mode(self, simple_metrics):
        """Test setting active positions in simple mode"""
        simple_metrics.set_active_positions(5)

        simple = simple_metrics.get_simple_metrics()
        assert simple['active_positions'] == 5

    def test_set_available_capital_simple_mode(self, simple_metrics):
        """Test setting available capital in simple mode"""
        simple_metrics.set_available_capital(100000.0)

        simple = simple_metrics.get_simple_metrics()
        assert simple['available_capital'] == 100000.0


# ============================================================================
# Trading Performance Metrics Tests
# ============================================================================

class TestTradingPerformanceMetrics:
    """Test trading performance metric methods"""

    def test_set_total_pnl_simple_mode(self, simple_metrics):
        """Test setting total PnL in simple mode"""
        simple_metrics.set_total_pnl(25000.50)

        simple = simple_metrics.get_simple_metrics()
        assert simple['total_pnl'] == 25000.50

    def test_set_daily_pnl_simple_mode(self, simple_metrics):
        """Test setting daily PnL in simple mode"""
        simple_metrics.set_daily_pnl(1500.75)

        simple = simple_metrics.get_simple_metrics()
        assert simple['daily_pnl'] == 1500.75

    def test_record_trade_buy_success_simple_mode(self, simple_metrics):
        """Test recording buy trade (success) in simple mode"""
        simple_metrics.record_trade('buy', 'success')
        simple_metrics.record_trade('buy', 'success')

        simple = simple_metrics.get_simple_metrics()
        assert simple['trades_buy_success'] == 2

    def test_record_trade_sell_failure_simple_mode(self, simple_metrics):
        """Test recording sell trade (failure) in simple mode"""
        simple_metrics.record_trade('sell', 'failure')

        simple = simple_metrics.get_simple_metrics()
        assert simple['trades_sell_failure'] == 1

    def test_set_win_rate_simple_mode(self, simple_metrics):
        """Test setting win rate in simple mode"""
        simple_metrics.set_win_rate(65.5)

        simple = simple_metrics.get_simple_metrics()
        assert simple['win_rate_percent'] == 65.5


# ============================================================================
# API Metrics Tests
# ============================================================================

class TestAPIMetrics:
    """Test API metric methods"""

    def test_record_api_request_success_simple_mode(self, simple_metrics):
        """Test recording successful API request in simple mode"""
        simple_metrics.record_api_request('zerodha_quote', 0.125, 'success')

        simple = simple_metrics.get_simple_metrics()
        assert simple['api_zerodha_quote_success'] == 1
        assert simple['api_zerodha_quote_duration_sum'] == 0.125

    def test_record_api_request_failure_simple_mode(self, simple_metrics):
        """Test recording failed API request in simple mode"""
        simple_metrics.record_api_request('zerodha_quote', 1.5, 'failure')

        simple = simple_metrics.get_simple_metrics()
        assert simple['api_zerodha_quote_failure'] == 1
        assert simple['api_zerodha_quote_duration_sum'] == 1.5

    def test_record_api_request_multiple_simple_mode(self, simple_metrics):
        """Test recording multiple API requests in simple mode"""
        simple_metrics.record_api_request('zerodha_quote', 0.1, 'success')
        simple_metrics.record_api_request('zerodha_quote', 0.2, 'success')
        simple_metrics.record_api_request('zerodha_quote', 0.3, 'success')

        simple = simple_metrics.get_simple_metrics()
        assert simple['api_zerodha_quote_success'] == 3
        assert simple['api_zerodha_quote_duration_sum'] == pytest.approx(0.6)

    def test_record_api_error_simple_mode(self, simple_metrics):
        """Test recording API error in simple mode"""
        simple_metrics.record_api_error('zerodha_quote', 'TimeoutError')

        simple = simple_metrics.get_simple_metrics()
        assert simple['api_errors_zerodha_quote_TimeoutError'] == 1

    def test_record_rate_limit_hit_simple_mode(self, simple_metrics):
        """Test recording rate limit hit in simple mode"""
        simple_metrics.record_rate_limit_hit('zerodha_orders')

        simple = simple_metrics.get_simple_metrics()
        assert simple['rate_limit_hits_zerodha_orders'] == 1

    def test_record_rate_limit_hit_multiple_simple_mode(self, simple_metrics):
        """Test recording multiple rate limit hits in simple mode"""
        for _ in range(5):
            simple_metrics.record_rate_limit_hit('zerodha_orders')

        simple = simple_metrics.get_simple_metrics()
        assert simple['rate_limit_hits_zerodha_orders'] == 5


# ============================================================================
# Business Metrics Tests
# ============================================================================

class TestBusinessMetrics:
    """Test business metric methods"""

    def test_record_signal_high_confidence_simple_mode(self, simple_metrics):
        """Test recording high-confidence signal in simple mode"""
        simple_metrics.record_signal('buy', 0.85)

        simple = simple_metrics.get_simple_metrics()
        assert simple['signals_buy_high'] == 1

    def test_record_signal_medium_confidence_simple_mode(self, simple_metrics):
        """Test recording medium-confidence signal in simple mode"""
        simple_metrics.record_signal('sell', 0.65)

        simple = simple_metrics.get_simple_metrics()
        assert simple['signals_sell_medium'] == 1

    def test_record_signal_low_confidence_simple_mode(self, simple_metrics):
        """Test recording low-confidence signal in simple mode"""
        simple_metrics.record_signal('buy', 0.35)

        simple = simple_metrics.get_simple_metrics()
        assert simple['signals_buy_low'] == 1

    def test_record_signal_confidence_boundary_80(self, simple_metrics):
        """Test signal at high/medium boundary (0.8)"""
        simple_metrics.record_signal('buy', 0.8)

        simple = simple_metrics.get_simple_metrics()
        assert simple['signals_buy_high'] == 1

    def test_record_signal_confidence_boundary_50(self, simple_metrics):
        """Test signal at medium/low boundary (0.5)"""
        simple_metrics.record_signal('sell', 0.5)

        simple = simple_metrics.get_simple_metrics()
        assert simple['signals_sell_medium'] == 1

    def test_record_order_market_filled_simple_mode(self, simple_metrics):
        """Test recording market order (filled) in simple mode"""
        simple_metrics.record_order('market', 'filled')

        simple = simple_metrics.get_simple_metrics()
        assert simple['orders_market_filled'] == 1

    def test_record_order_limit_rejected_simple_mode(self, simple_metrics):
        """Test recording limit order (rejected) in simple mode"""
        simple_metrics.record_order('limit', 'rejected')

        simple = simple_metrics.get_simple_metrics()
        assert simple['orders_limit_rejected'] == 1

    def test_record_order_pending_simple_mode(self, simple_metrics):
        """Test recording pending order in simple mode"""
        simple_metrics.record_order('limit', 'pending')

        simple = simple_metrics.get_simple_metrics()
        assert simple['orders_limit_pending'] == 1

    def test_set_portfolio_value_simple_mode(self, simple_metrics):
        """Test setting portfolio value in simple mode"""
        simple_metrics.set_portfolio_value(250000.0)

        simple = simple_metrics.get_simple_metrics()
        assert simple['portfolio_value'] == 250000.0


# ============================================================================
# Error Metrics Tests
# ============================================================================

class TestErrorMetrics:
    """Test error metric methods"""

    def test_record_exception_error_simple_mode(self, simple_metrics):
        """Test recording error-level exception in simple mode"""
        simple_metrics.record_exception('ValueError', 'error')

        simple = simple_metrics.get_simple_metrics()
        assert simple['exceptions_ValueError_error'] == 1

    def test_record_exception_critical_simple_mode(self, simple_metrics):
        """Test recording critical-level exception in simple mode"""
        simple_metrics.record_exception('SystemError', 'critical')

        simple = simple_metrics.get_simple_metrics()
        assert simple['exceptions_SystemError_critical'] == 1

    def test_record_exception_warning_simple_mode(self, simple_metrics):
        """Test recording warning-level exception in simple mode"""
        simple_metrics.record_exception('DeprecationWarning', 'warning')

        simple = simple_metrics.get_simple_metrics()
        assert simple['exceptions_DeprecationWarning_warning'] == 1

    def test_set_circuit_breaker_state_closed_simple_mode(self, simple_metrics):
        """Test setting circuit breaker to closed state in simple mode"""
        simple_metrics.set_circuit_breaker_state('database', 'closed')

        simple = simple_metrics.get_simple_metrics()
        assert simple['circuit_breaker_database'] == 0

    def test_set_circuit_breaker_state_open_simple_mode(self, simple_metrics):
        """Test setting circuit breaker to open state in simple mode"""
        simple_metrics.set_circuit_breaker_state('api', 'open')

        simple = simple_metrics.get_simple_metrics()
        assert simple['circuit_breaker_api'] == 1

    def test_set_circuit_breaker_state_half_open_simple_mode(self, simple_metrics):
        """Test setting circuit breaker to half-open state in simple mode"""
        simple_metrics.set_circuit_breaker_state('cache', 'half_open')

        simple = simple_metrics.get_simple_metrics()
        assert simple['circuit_breaker_cache'] == 2

    def test_set_circuit_breaker_state_invalid_defaults_to_closed(self, simple_metrics):
        """Test that invalid circuit breaker state defaults to closed"""
        simple_metrics.set_circuit_breaker_state('test', 'invalid')

        simple = simple_metrics.get_simple_metrics()
        assert simple['circuit_breaker_test'] == 0


# ============================================================================
# Export Metrics Tests
# ============================================================================

class TestExportMetrics:
    """Test metrics export methods"""

    def test_export_metrics_simple_mode(self, simple_metrics):
        """Test exporting metrics in simple mode"""
        simple_metrics.set_total_pnl(10000)
        simple_metrics.record_trade('buy', 'success')

        exported = simple_metrics.export_metrics()

        assert isinstance(exported, bytes)
        exported_text = exported.decode('utf-8')
        assert 'total_pnl 10000' in exported_text
        assert 'trades_buy_success 1' in exported_text

    def test_export_metrics_prometheus_mode(self):
        """Test exporting metrics in Prometheus mode"""
        with patch('core.metrics_exporter.PROMETHEUS_AVAILABLE', True):
            with patch('core.metrics_exporter.generate_latest', return_value=b'# HELP metric\nmetric 42\n'):
                metrics = TradingMetrics(enable_prometheus=True)

                exported = metrics.export_metrics()

                assert isinstance(exported, bytes)
                assert b'metric 42' in exported

    def test_get_content_type_simple_mode(self, simple_metrics):
        """Test getting content type in simple mode"""
        content_type = simple_metrics.get_content_type()

        assert content_type == 'text/plain; charset=utf-8'

    def test_get_content_type_prometheus_mode(self):
        """Test getting content type in Prometheus mode"""
        with patch('core.metrics_exporter.PROMETHEUS_AVAILABLE', True):
            with patch('core.metrics_exporter.CONTENT_TYPE_LATEST', 'text/plain; version=0.0.4'):
                metrics = TradingMetrics(enable_prometheus=True)

                content_type = metrics.get_content_type()

                assert 'text/plain' in content_type

    def test_get_simple_metrics_returns_copy(self, simple_metrics):
        """Test that get_simple_metrics returns a copy"""
        simple_metrics.set_total_pnl(5000)

        metrics1 = simple_metrics.get_simple_metrics()
        metrics2 = simple_metrics.get_simple_metrics()

        # Modify one copy
        metrics1['new_key'] = 999

        # Should not affect the other copy
        assert 'new_key' not in metrics2


# ============================================================================
# Global Metrics Tests
# ============================================================================

class TestGlobalMetrics:
    """Test global metrics singleton"""

    def test_get_global_metrics_creates_instance(self):
        """Test that get_global_metrics creates an instance"""
        # Reset global metrics
        import core.metrics_exporter
        core.metrics_exporter._global_metrics = None

        metrics = get_global_metrics()

        assert metrics is not None
        assert isinstance(metrics, TradingMetrics)

    def test_get_global_metrics_returns_same_instance(self):
        """Test that get_global_metrics returns same instance"""
        metrics1 = get_global_metrics()
        metrics2 = get_global_metrics()

        assert metrics1 is metrics2

    def test_set_global_metrics(self):
        """Test setting global metrics instance"""
        custom_metrics = TradingMetrics(enable_prometheus=False)

        set_global_metrics(custom_metrics)

        metrics = get_global_metrics()

        assert metrics is custom_metrics


# ============================================================================
# Metrics Endpoint Tests
# ============================================================================

class TestMetricsEndpoint:
    """Test metrics HTTP endpoint creation"""

    def test_create_metrics_endpoint_default(self):
        """Test creating metrics endpoint with default metrics"""
        content, content_type = create_metrics_endpoint()

        assert isinstance(content, bytes)
        assert isinstance(content_type, str)

    def test_create_metrics_endpoint_custom_metrics(self, simple_metrics):
        """Test creating metrics endpoint with custom metrics"""
        simple_metrics.set_total_pnl(12345)

        content, content_type = create_metrics_endpoint(simple_metrics)

        assert isinstance(content, bytes)
        assert b'total_pnl 12345' in content

    def test_create_metrics_endpoint_content_type(self, simple_metrics):
        """Test that endpoint returns correct content type"""
        content, content_type = create_metrics_endpoint(simple_metrics)

        assert content_type == 'text/plain; charset=utf-8'


# ============================================================================
# Thread Safety Tests
# ============================================================================

class TestThreadSafety:
    """Test thread safety of simple metrics"""

    def test_concurrent_metric_updates(self, simple_metrics):
        """Test that metrics can handle concurrent updates"""
        import threading

        def update_metrics():
            for _ in range(100):
                simple_metrics.record_trade('buy', 'success')

        threads = [threading.Thread(target=update_metrics) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        simple = simple_metrics.get_simple_metrics()
        # 10 threads * 100 updates each = 1000
        assert simple['trades_buy_success'] == 1000


# ============================================================================
# Comprehensive Workflow Tests
# ============================================================================

class TestComprehensiveWorkflow:
    """Test comprehensive metric workflows"""

    def test_full_trading_session_metrics(self, simple_metrics):
        """Test recording metrics for a full trading session"""
        # System startup
        simple_metrics.set_uptime(0)
        simple_metrics.set_available_capital(500000)
        simple_metrics.set_portfolio_value(500000)

        # Trading activity
        simple_metrics.record_signal('buy', 0.9)
        simple_metrics.record_order('market', 'filled')
        simple_metrics.record_trade('buy', 'success')
        simple_metrics.set_active_positions(1)

        simple_metrics.record_signal('sell', 0.85)
        simple_metrics.record_order('market', 'filled')
        simple_metrics.record_trade('sell', 'success')
        simple_metrics.set_active_positions(0)

        # PnL update
        simple_metrics.set_daily_pnl(5000)
        simple_metrics.set_total_pnl(25000)
        simple_metrics.set_win_rate(75.0)

        # API calls
        simple_metrics.record_api_request('zerodha_quote', 0.05, 'success')
        simple_metrics.record_api_request('zerodha_orders', 0.15, 'success')

        # Export metrics
        exported = simple_metrics.export_metrics()

        assert isinstance(exported, bytes)
        exported_text = exported.decode('utf-8')

        # Verify all metrics are present
        assert 'trades_buy_success 1' in exported_text
        assert 'trades_sell_success 1' in exported_text
        assert 'daily_pnl 5000' in exported_text
        assert 'win_rate_percent 75' in exported_text


if __name__ == "__main__":
    # Run tests with: pytest test_metrics_exporter.py -v
    pytest.main([__file__, "-v", "--tb=short"])
