#!/usr/bin/env python3
"""
Simplified Integration Tests for Week 5-8 Medium-Priority Enhancements

Tests verify that the components can be imported and instantiated correctly.
More detailed functional testing can be done manually or with component-specific tests.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch


def test_performance_monitor_import():
    """Test that PerformanceMonitor can be imported and instantiated"""
    from infrastructure.performance_monitor import PerformanceMonitor

    monitor = PerformanceMonitor()
    assert monitor is not None


def test_performance_monitor_singleton():
    """Test that get_performance_monitor returns singleton"""
    from infrastructure.performance_monitor import get_performance_monitor

    monitor1 = get_performance_monitor()
    monitor2 = get_performance_monitor()

    assert monitor1 is monitor2  # Same instance


def test_log_correlator_import():
    """Test that LogCorrelator can be imported and instantiated"""
    from infrastructure.log_correlator import LogCorrelator, LogEntry, LogLevel

    correlator = LogCorrelator()
    assert correlator is not None

    # Test LogEntry creation
    entry = LogEntry(
        timestamp=datetime.now(),
        level=LogLevel.INFO,
        component='test',
        message='test message'
    )
    assert entry is not None


def test_log_correlator_parse():
    """Test log parsing functionality"""
    from infrastructure.log_correlator import LogCorrelator

    correlator = LogCorrelator()

    log_line = "2025-01-15 10:30:45,123 - INFO - trading_system - trade_id: TRADE_001 - Order placed"
    entry = correlator.parse_log_line(log_line)

    assert entry is not None
    assert entry.correlation_id == 'TRADE_001'


def test_advanced_analytics_import():
    """Test that AdvancedAnalytics can be imported and instantiated"""
    with patch('analytics.advanced_analytics.get_database'), \
         patch('analytics.advanced_analytics.get_strategy_registry'):
        from analytics.advanced_analytics import AdvancedAnalytics

        analytics = AdvancedAnalytics()
        assert analytics is not None


def test_advanced_analytics_sharpe_ratio():
    """Test Sharpe ratio calculation"""
    with patch('analytics.advanced_analytics.get_database'), \
         patch('analytics.advanced_analytics.get_strategy_registry'):
        from analytics.advanced_analytics import AdvancedAnalytics

        analytics = AdvancedAnalytics()

        # Positive returns
        returns = [0.01, 0.02, -0.01, 0.015, -0.005, 0.02, 0.01, -0.002]
        sharpe = analytics.calculate_sharpe_ratio(returns)

        assert sharpe is not None
        assert isinstance(sharpe, (float, np.floating))
        assert -20 < sharpe < 20  # Reasonable range for Sharpe ratio


def test_advanced_analytics_sortino_ratio():
    """Test Sortino ratio calculation"""
    with patch('analytics.advanced_analytics.get_database'), \
         patch('analytics.advanced_analytics.get_strategy_registry'):
        from analytics.advanced_analytics import AdvancedAnalytics

        analytics = AdvancedAnalytics()

        returns = [0.02, 0.01, -0.01, 0.015, -0.02, 0.01, -0.005, 0.02]
        sortino = analytics.calculate_sortino_ratio(returns)

        assert sortino is not None
        assert isinstance(sortino, float)


def test_advanced_analytics_max_drawdown():
    """Test maximum drawdown calculation"""
    with patch('analytics.advanced_analytics.get_database'), \
         patch('analytics.advanced_analytics.get_strategy_registry'):
        from analytics.advanced_analytics import AdvancedAnalytics

        analytics = AdvancedAnalytics()

        # Equity curve with clear drawdown
        equity_curve = [1000, 1050, 1100, 1150, 1200, 1100, 1000, 900, 950, 1000, 1100]

        max_dd, start_idx, end_idx = analytics.calculate_max_drawdown(equity_curve)

        assert max_dd >= 0  # Non-negative
        assert max_dd <= 1  # Less than 100%
        assert start_idx <= end_idx


def test_advanced_analytics_market_regime():
    """Test market regime detection"""
    with patch('analytics.advanced_analytics.get_database'), \
         patch('analytics.advanced_analytics.get_strategy_registry'):
        from analytics.advanced_analytics import AdvancedAnalytics

        analytics = AdvancedAnalytics()

        # Generate uptrending price data
        dates = pd.date_range(start='2024-01-01', periods=50, freq='D')
        prices = 1000 + np.arange(50) * 5 + np.random.randn(50) * 2
        price_data = pd.DataFrame({'close': prices}, index=dates)

        regime = analytics.detect_market_regime(price_data)

        assert regime is not None
        assert regime.regime in ['trending_up', 'trending_down', 'ranging', 'volatile']
        assert 0 <= regime.confidence <= 1
        assert isinstance(regime.recommended_strategies, list)


def test_advanced_analytics_predict_strategy():
    """Test strategy performance prediction"""
    with patch('analytics.advanced_analytics.get_database') as mock_db, \
         patch('analytics.advanced_analytics.get_strategy_registry'):
        from analytics.advanced_analytics import AdvancedAnalytics

        analytics = AdvancedAnalytics()

        # Mock database to return sample trades
        mock_trades = []
        base_date = datetime.now() - timedelta(days=30)

        for i in range(20):
            mock_trades.append({
                'timestamp': (base_date + timedelta(days=i)).isoformat(),
                'pnl': 100 + i * 10
            })

        analytics.db.get_trades = Mock(return_value=mock_trades)

        prediction = analytics.predict_strategy_performance('TestStrategy')

        assert prediction is not None
        assert prediction.strategy_name == 'TestStrategy'
        assert prediction.recommendation in ['strong_buy', 'buy', 'hold', 'avoid']


def test_integration_all_components():
    """Test that all three components can work together"""
    from infrastructure.performance_monitor import get_performance_monitor
    from infrastructure.log_correlator import LogCorrelator

    with patch('analytics.advanced_analytics.get_database'), \
         patch('analytics.advanced_analytics.get_strategy_registry'):
        from analytics.advanced_analytics import get_analytics

        # Initialize all components
        monitor = get_performance_monitor()
        correlator = LogCorrelator()
        analytics = get_analytics()

        # All should be instantiated
        assert monitor is not None
        assert correlator is not None
        assert analytics is not None


def test_components_are_production_ready():
    """Verify all components can be imported in production"""
    # This test verifies the imports work without errors
    from infrastructure.performance_monitor import (
        PerformanceMonitor, MetricType, get_performance_monitor
    )
    from infrastructure.log_correlator import (
        LogCorrelator, LogEntry, LogLevel, CorrelatedLogs
    )

    with patch('analytics.advanced_analytics.get_database'), \
         patch('analytics.advanced_analytics.get_strategy_registry'):
        from analytics.advanced_analytics import (
            AdvancedAnalytics, StrategyPrediction, MarketRegimePrediction,
            PredictionConfidence, get_analytics
        )

    # If we get here, all imports succeeded
    assert True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
