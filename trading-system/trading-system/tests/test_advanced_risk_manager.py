#!/usr/bin/env python3
"""
Comprehensive tests for advanced_risk_manager.py module
Tests AdvancedRiskManager for risk calculations and portfolio optimization
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.advanced_risk_manager import (
    RiskMetrics,
    AdvancedRiskManager
)


class TestRiskMetrics:
    """Test RiskMetrics dataclass"""

    def test_risk_metrics_initialization(self):
        metrics = RiskMetrics()
        assert metrics.var_95 == 0.0
        assert isinstance(metrics.timestamp, datetime)


class TestAdvancedRiskManagerInitialization:
    """Test AdvancedRiskManager initialization"""

    def test_initialization_defaults(self):
        manager = AdvancedRiskManager()
        assert manager.confidence_level == 0.95
        assert manager.var_window == 252


class TestVaRCalculation:
    """Test calculate_var method"""

    def test_var_empty_returns(self):
        manager = AdvancedRiskManager()
        returns = np.array([])
        var, cvar = manager.calculate_var(returns)
        assert var == 0.0
        assert cvar == 0.0

    def test_var_historical_method(self):
        manager = AdvancedRiskManager(confidence_level=0.95)
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 1000)
        var, cvar = manager.calculate_var(returns, method='historical')
        assert var >= 0
        assert cvar >= var


class TestSharpeRatio:
    """Test calculate_sharpe_ratio method"""

    def test_sharpe_ratio_calculation(self):
        manager = AdvancedRiskManager(risk_free_rate=0.05)
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.01, 252)
        sharpe = manager.calculate_sharpe_ratio(returns, periods_per_year=252)
        assert isinstance(sharpe, (int, float))


class TestSortinoRatio:
    """Test calculate_sortino_ratio method"""

    def test_sortino_ratio_calculation(self):
        manager = AdvancedRiskManager(risk_free_rate=0.05)
        returns = np.array([0.10, -0.02, 0.08, -0.01, 0.12, 0.05])
        sortino = manager.calculate_sortino_ratio(returns, periods_per_year=252)
        assert isinstance(sortino, (int, float))


class TestMaxDrawdown:
    """Test calculate_max_drawdown method"""

    def test_max_drawdown_increasing_values(self):
        manager = AdvancedRiskManager()
        values = np.array([100, 105, 110, 115, 120])
        max_dd, duration = manager.calculate_max_drawdown(values)
        assert max_dd == 0.0
        assert duration == 0

    def test_max_drawdown_with_decline(self):
        manager = AdvancedRiskManager()
        values = np.array([100, 110, 100, 90, 95, 100])
        max_dd, duration = manager.calculate_max_drawdown(values)
        assert 0.15 < max_dd < 0.20
        assert duration > 0


class TestKellyCriterion:
    """Test optimize_kelly_criterion method"""

    def test_kelly_criterion_calculation(self):
        manager = AdvancedRiskManager()
        # Kelly formula needs win_rate, avg_win, avg_loss
        kelly_fraction = manager.optimize_kelly_criterion(
            win_rate=0.6, avg_win=0.15, avg_loss=0.10
        )
        assert 0 <= kelly_fraction <= 1


class TestRiskParity:
    """Test optimize_risk_parity method"""

    def test_risk_parity_optimization(self):
        manager = AdvancedRiskManager()
        cov_matrix = np.array([
            [0.04, 0.01, 0.02],
            [0.01, 0.09, 0.03],
            [0.02, 0.03, 0.16]
        ])
        weights = manager.optimize_risk_parity(cov_matrix)
        assert np.isclose(weights.sum(), 1.0, atol=0.01)
        assert np.all(weights >= 0)


class TestPortfolioMetrics:
    """Test calculate_portfolio_metrics method"""

    def test_portfolio_metrics_calculation(self):
        manager = AdvancedRiskManager()
        positions = {
            'STOCK1': {
                'quantity': 100,
                'current_price': 500.0
            },
            'STOCK2': {
                'quantity': 200,
                'current_price': 150.0
            }
        }
        metrics = manager.calculate_portfolio_metrics(
            positions=positions,
            portfolio_value=100000.0,
            returns_df=None
        )
        assert isinstance(metrics, RiskMetrics)
        assert metrics.total_exposure >= 0


class TestRiskLimits:
    """Test check_risk_limits method"""

    def test_risk_limits_within_bounds(self):
        manager = AdvancedRiskManager(max_drawdown_pct=0.15, max_leverage=2.0)
        metrics = RiskMetrics(current_drawdown=-0.10, leverage=1.5)
        violations = manager.check_risk_limits(metrics)
        assert len(violations) == 0

    def test_risk_limits_drawdown_violation(self):
        manager = AdvancedRiskManager(max_drawdown_pct=0.10)
        metrics = RiskMetrics(current_drawdown=-0.15, leverage=0.5)
        violations = manager.check_risk_limits(metrics)
        assert len(violations) > 0


class TestHistoryUpdate:
    """Test update_history method"""

    def test_update_history_basic(self):
        manager = AdvancedRiskManager()
        manager.update_history(portfolio_value=100000.0)
        assert len(manager.portfolio_value_history) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
