#!/usr/bin/env python3
"""
Comprehensive Test Suite for Trading System Core Modules
Phase 3 Tier 3: DevOps & Cloud Infrastructure

Tests all core modules with pytest:
- Advanced Risk Manager
- Real-time Data Pipeline
- Vectorized Backtester
- ML Integration
- Advanced Analytics
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

# Import core modules
from core.advanced_risk_manager import AdvancedRiskManager
from core.vectorized_backtester import (
    VectorizedBacktester,
    BacktestConfig,
    Strategy
)
from core.ml_integration import (
    FeatureEngineering,
    MLSignalScorer,
    AnomalyDetector,
    ModelType
)
from core.advanced_analytics import AdvancedAnalytics


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_returns():
    """Generate sample return series"""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
    returns = pd.Series(np.random.normal(0.001, 0.02, len(dates)), index=dates)
    return returns


@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV data"""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
    close_prices = 100 + np.random.randn(len(dates)).cumsum()

    data = pd.DataFrame({
        'open': close_prices * 0.99,
        'high': close_prices * 1.01,
        'low': close_prices * 0.98,
        'close': close_prices,
        'volume': np.random.randint(100000, 1000000, len(dates))
    }, index=dates)

    return data


@pytest.fixture
def temp_model_dir():
    """Create temporary directory for models"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


# ============================================================================
# Advanced Risk Manager Tests
# ============================================================================

class TestAdvancedRiskManager:
    """Test suite for Advanced Risk Manager"""

    def test_initialization(self):
        """Test risk manager initialization"""
        risk_mgr = AdvancedRiskManager(
            max_position_size_pct=0.20,
            max_drawdown_pct=0.10
        )

        assert risk_mgr.max_position_size_pct == 0.20
        assert risk_mgr.max_drawdown_pct == 0.10

    def test_var_calculation_historical(self, sample_returns):
        """Test historical VaR calculation"""
        risk_mgr = AdvancedRiskManager()

        var, cvar = risk_mgr.calculate_var(
            sample_returns.values,
            method='historical',
            confidence=0.95
        )

        assert var >= 0
        assert cvar >= var  # CVaR should be >= VaR
        assert var < 1.0  # Reasonable value

    def test_var_calculation_parametric(self, sample_returns):
        """Test parametric VaR calculation"""
        risk_mgr = AdvancedRiskManager()

        var, cvar = risk_mgr.calculate_var(
            sample_returns.values,
            method='parametric',
            confidence=0.95
        )

        assert var >= 0
        assert cvar >= var

    def test_var_calculation_monte_carlo(self, sample_returns):
        """Test Monte Carlo VaR calculation"""
        risk_mgr = AdvancedRiskManager()

        var, cvar = risk_mgr.calculate_var(
            sample_returns.values,
            method='monte_carlo',
            confidence=0.95
        )

        assert var >= 0
        assert cvar >= var

    def test_kelly_criterion(self):
        """Test Kelly Criterion calculation"""
        risk_mgr = AdvancedRiskManager()

        position_size = risk_mgr.optimize_kelly_criterion(
            win_rate=0.60,
            avg_win=0.05,
            avg_loss=0.03
        )

        assert 0 < position_size <= risk_mgr.max_position_size_pct
        assert isinstance(position_size, float)

    def test_risk_parity_optimization(self):
        """Test risk parity optimization"""
        risk_mgr = AdvancedRiskManager()

        # Generate sample returns for 3 assets as DataFrame
        np.random.seed(42)
        returns_df = pd.DataFrame(
            np.random.normal(0.001, 0.02, (100, 3)),
            columns=['Asset_A', 'Asset_B', 'Asset_C']
        )

        weights = risk_mgr.optimize_risk_parity(returns_df)

        assert len(weights) == 3
        # weights is a dict, so sum the values
        assert np.isclose(sum(weights.values()), 1.0)
        assert all(w >= 0 for w in weights.values())

    def test_sharpe_ratio(self, sample_returns):
        """Test Sharpe ratio calculation"""
        risk_mgr = AdvancedRiskManager()

        sharpe = risk_mgr.calculate_sharpe_ratio(sample_returns.values)

        assert isinstance(sharpe, float)
        assert -5 < sharpe < 5  # Reasonable range


# ============================================================================
# Vectorized Backtester Tests
# ============================================================================

class SimpleTestStrategy(Strategy):
    """Simple strategy for testing"""
    def __init__(self, fast=10, slow=20):
        self.fast = fast
        self.slow = slow

    def generate_signals(self, data):
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0

        fast_ma = data['close'].rolling(self.fast).mean()
        slow_ma = data['close'].rolling(self.slow).mean()

        signals['signal'] = np.where(fast_ma > slow_ma, 1, 0)
        signals['position_change'] = signals['signal'].diff()
        signals.loc[signals['position_change'] == 1, 'signal'] = 1
        signals.loc[signals['position_change'] == -1, 'signal'] = -1

        return signals


class TestVectorizedBacktester:
    """Test suite for Vectorized Backtester"""

    def test_initialization(self):
        """Test backtester initialization"""
        config = BacktestConfig(
            initial_capital=1000000,
            transaction_cost_pct=0.001
        )
        backtester = VectorizedBacktester(config)

        assert backtester.config.initial_capital == 1000000
        assert backtester.config.transaction_cost_pct == 0.001

    def test_backtest_run(self, sample_ohlcv_data):
        """Test running a backtest"""
        strategy = SimpleTestStrategy(fast=10, slow=20)
        backtester = VectorizedBacktester()

        results = backtester.run(strategy, sample_ohlcv_data)

        assert hasattr(results, 'total_return_pct')
        assert hasattr(results, 'sharpe_ratio')
        assert hasattr(results, 'max_drawdown_pct')
        assert results.total_trades >= 0

    def test_parameter_optimization(self, sample_ohlcv_data):
        """Test parameter optimization"""
        backtester = VectorizedBacktester()

        param_grid = {
            'fast': [5, 10],
            'slow': [20, 30]
        }

        best_params, best_results = backtester.optimize_parameters(
            SimpleTestStrategy,
            sample_ohlcv_data,
            param_grid,
            metric='sharpe_ratio'
        )

        assert 'fast' in best_params
        assert 'slow' in best_params
        assert hasattr(best_results, 'sharpe_ratio')

    def test_transaction_costs(self, sample_ohlcv_data):
        """Test that transaction costs reduce returns"""
        strategy = SimpleTestStrategy()

        # Backtest without costs
        config_no_cost = BacktestConfig(transaction_cost_pct=0, slippage_pct=0)
        backtester_no_cost = VectorizedBacktester(config_no_cost)
        results_no_cost = backtester_no_cost.run(strategy, sample_ohlcv_data)

        # Backtest with costs
        config_with_cost = BacktestConfig(transaction_cost_pct=0.01, slippage_pct=0.005)
        backtester_with_cost = VectorizedBacktester(config_with_cost)
        results_with_cost = backtester_with_cost.run(strategy, sample_ohlcv_data)

        # Returns with costs should be lower (or equal if no trades)
        assert results_with_cost.total_return_pct <= results_no_cost.total_return_pct


# ============================================================================
# ML Integration Tests
# ============================================================================

class TestFeatureEngineering:
    """Test suite for Feature Engineering"""

    def test_feature_generation(self, sample_ohlcv_data):
        """Test feature generation"""
        features = FeatureEngineering.generate_all_features(sample_ohlcv_data)

        # Should generate many features
        assert len(features.columns) > 50

        # Should have some common features
        assert 'sma_20' in features.columns
        assert 'rsi_14' in features.columns
        assert 'macd' in features.columns

    def test_trend_features(self, sample_ohlcv_data):
        """Test trend feature generation"""
        df = FeatureEngineering.add_trend_features(sample_ohlcv_data.copy())

        assert 'sma_20' in df.columns
        assert 'ema_20' in df.columns
        assert 'macd' in df.columns

    def test_momentum_features(self, sample_ohlcv_data):
        """Test momentum feature generation"""
        df = FeatureEngineering.add_momentum_features(sample_ohlcv_data.copy())

        assert 'rsi_14' in df.columns
        assert 'roc_10' in df.columns
        assert 'momentum_10' in df.columns

    def test_volatility_features(self, sample_ohlcv_data):
        """Test volatility feature generation"""
        df = FeatureEngineering.add_volatility_features(sample_ohlcv_data.copy())

        assert 'atr_14' in df.columns
        assert 'bb_upper_20' in df.columns
        assert 'volatility_20' in df.columns


class TestMLSignalScorer:
    """Test suite for ML Signal Scorer"""

    def test_initialization(self, temp_model_dir):
        """Test ML scorer initialization"""
        scorer = MLSignalScorer(model_dir=temp_model_dir)

        assert scorer.model_dir == Path(temp_model_dir)
        assert len(scorer.models) == 0

    def test_model_training(self, sample_ohlcv_data, temp_model_dir):
        """Test model training"""
        # Generate features
        features = FeatureEngineering.generate_all_features(sample_ohlcv_data)

        # Create synthetic labels
        y = pd.Series(np.random.choice([0, 1, 2], size=len(features)))

        # Train model
        scorer = MLSignalScorer(model_dir=temp_model_dir)
        model_id = scorer.train_model(features, y, ModelType.RANDOM_FOREST)

        assert model_id in scorer.models
        assert model_id in scorer.metadata
        assert scorer.metadata[model_id].trained_on_samples == len(features)

    def test_signal_prediction(self, sample_ohlcv_data, temp_model_dir):
        """Test signal prediction"""
        features = FeatureEngineering.generate_all_features(sample_ohlcv_data)

        # Split data
        train_size = int(len(features) * 0.7)
        X_train = features.iloc[:train_size]
        X_test = features.iloc[train_size:]

        # Create labels
        y_train = pd.Series(np.random.choice([0, 1, 2], size=len(X_train)))

        # Train and predict
        scorer = MLSignalScorer(model_dir=temp_model_dir)
        model_id = scorer.train_model(X_train, y_train, ModelType.RANDOM_FOREST)

        scores = scorer.predict_signal(X_test, model_id)

        assert len(scores) == len(X_test)
        assert all(-5 <= s <= 145 for s in scores)  # Scores roughly 0-100 (with tolerance)

    def test_model_persistence(self, sample_ohlcv_data, temp_model_dir):
        """Test model save/load"""
        features = FeatureEngineering.generate_all_features(sample_ohlcv_data)
        y = pd.Series(np.random.choice([0, 1, 2], size=len(features)))

        # Train and save
        scorer = MLSignalScorer(model_dir=temp_model_dir)
        model_id = scorer.train_model(features, y, ModelType.RANDOM_FOREST)
        scorer.save_model(model_id)

        # Create new scorer and load
        scorer2 = MLSignalScorer(model_dir=temp_model_dir)
        scorer2.load_model(model_id)

        assert model_id in scorer2.models
        assert model_id in scorer2.metadata


class TestAnomalyDetector:
    """Test suite for Anomaly Detector"""

    def test_initialization(self):
        """Test anomaly detector initialization"""
        detector = AnomalyDetector(window_size=50, n_std=3.0)

        assert detector.window_size == 50
        assert detector.n_std == 3.0

    def test_price_anomaly_detection(self, sample_ohlcv_data):
        """Test price anomaly detection"""
        # Inject anomaly
        data = sample_ohlcv_data.copy()
        data.iloc[100, data.columns.get_loc('close')] *= 1.5  # 50% spike

        detector = AnomalyDetector(window_size=50, n_std=2.0)
        anomalies = detector.detect_price_anomalies(data)

        assert isinstance(anomalies, pd.Series)
        assert anomalies.dtype == bool
        # Should detect the injected anomaly
        assert anomalies.iloc[100:110].any()  # Around the anomaly

    def test_volume_anomaly_detection(self, sample_ohlcv_data):
        """Test volume anomaly detection"""
        data = sample_ohlcv_data.copy()
        data.iloc[100, data.columns.get_loc('volume')] *= 10  # 10x volume spike

        detector = AnomalyDetector(window_size=50, n_std=2.0)
        anomalies = detector.detect_volume_anomalies(data)

        assert isinstance(anomalies, pd.Series)
        # Should detect the volume spike
        assert anomalies.iloc[100:110].any()

    def test_all_anomalies(self, sample_ohlcv_data):
        """Test detecting all anomaly types"""
        detector = AnomalyDetector()
        anomalies = detector.detect_all_anomalies(sample_ohlcv_data)

        assert 'price' in anomalies
        assert 'volume' in anomalies
        assert 'volatility' in anomalies
        assert all(isinstance(a, pd.Series) for a in anomalies.values())


# ============================================================================
# Advanced Analytics Tests
# ============================================================================

class TestAdvancedAnalytics:
    """Test suite for Advanced Analytics"""

    def test_initialization(self):
        """Test analytics initialization"""
        analytics = AdvancedAnalytics()
        assert analytics is not None

    def test_performance_attribution(self, sample_returns):
        """Test performance attribution"""
        analytics = AdvancedAnalytics()

        # Create position data
        dates = sample_returns.index
        position_data = pd.DataFrame({
            'date': np.repeat(dates, 2),
            'symbol': ['STOCK_A', 'STOCK_B'] * len(dates),
            'return': np.tile(sample_returns.values / 2, 2),
            'weight': [0.5, 0.5] * len(dates),
            'strategy': ['momentum', 'value'] * len(dates),
            'sector': ['tech', 'finance'] * len(dates)
        })

        attribution = analytics.calculate_performance_attribution(
            sample_returns, position_data
        )

        assert hasattr(attribution, 'total_return')
        assert hasattr(attribution, 'strategy_attribution')
        assert hasattr(attribution, 'sector_attribution')

    def test_factor_exposure(self, sample_returns):
        """Test factor exposure analysis"""
        analytics = AdvancedAnalytics()

        # Create market returns
        market_returns = sample_returns * 1.2 + np.random.normal(0, 0.01, len(sample_returns))

        exposure = analytics.calculate_factor_exposure(
            sample_returns, market_returns
        )

        assert hasattr(exposure, 'market_beta')
        assert hasattr(exposure, 'r_squared')
        assert isinstance(exposure.market_beta, float)

    def test_drawdown_analysis(self, sample_returns):
        """Test drawdown analysis"""
        analytics = AdvancedAnalytics()

        # Create equity curve
        equity_curve = (1 + sample_returns).cumprod() * 1000000

        dd_analysis = analytics.analyze_drawdowns(equity_curve, min_duration_days=5)

        assert hasattr(dd_analysis, 'max_drawdown_pct')
        assert hasattr(dd_analysis, 'max_drawdown_duration_days')
        assert dd_analysis.max_drawdown_pct >= 0

    def test_monte_carlo_simulation(self, sample_returns):
        """Test Monte Carlo simulation"""
        analytics = AdvancedAnalytics()

        mc_results = analytics.monte_carlo_simulation(
            sample_returns,
            initial_capital=1000000,
            n_simulations=100,  # Reduced for speed
            n_periods=100
        )

        assert 'n_simulations' in mc_results
        assert 'median_final_value' in mc_results
        assert 'probability_of_profit' in mc_results
        assert mc_results['n_simulations'] == 100

    def test_trade_quality_metrics(self):
        """Test trade quality metrics"""
        analytics = AdvancedAnalytics()

        # Create sample trades
        trades = pd.DataFrame({
            'entry_date': pd.date_range('2024-01-01', periods=20, freq='W'),
            'exit_date': pd.date_range('2024-01-08', periods=20, freq='W'),
            'symbol': ['STOCK_A'] * 20,
            'pnl': np.random.normal(100, 500, 20)
        })

        metrics = analytics.calculate_trade_quality_metrics(trades)

        assert 'total_trades' in metrics
        assert 'win_rate' in metrics
        assert 'profit_factor' in metrics
        assert metrics['total_trades'] == 20


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows"""

    def test_ml_backtesting_workflow(self, sample_ohlcv_data, temp_model_dir):
        """Test complete ML + backtesting workflow"""
        # Generate features
        features = FeatureEngineering.generate_all_features(sample_ohlcv_data)

        # Train model
        train_size = int(len(features) * 0.7)
        X_train = features.iloc[:train_size]
        y_train = pd.Series(np.random.choice([0, 1, 2], size=len(X_train)))

        scorer = MLSignalScorer(model_dir=temp_model_dir)
        model_id = scorer.train_model(X_train, y_train, ModelType.RANDOM_FOREST)

        # Create ML strategy
        class MLStrategy(Strategy):
            def __init__(self, scorer, model_id):
                self.scorer = scorer
                self.model_id = model_id

            def generate_signals(self, data):
                features = FeatureEngineering.generate_all_features(data)
                scores = self.scorer.predict_signal(features, self.model_id)

                signals = pd.DataFrame(index=data.index)
                signals['signal'] = 0

                aligned_scores = pd.Series(0.0, index=data.index, dtype=float)
                aligned_scores.loc[features.index] = scores.astype(float)

                signals.loc[aligned_scores >= 70, 'signal'] = 1
                signals.loc[aligned_scores <= 30, 'signal'] = -1

                return signals

        # Backtest
        strategy = MLStrategy(scorer, model_id)
        backtester = VectorizedBacktester()
        results = backtester.run(strategy, sample_ohlcv_data)

        assert hasattr(results, 'total_return_pct')
        assert hasattr(results, 'sharpe_ratio')

    def test_analytics_workflow(self, sample_returns):
        """Test complete analytics workflow"""
        analytics = AdvancedAnalytics()

        # Performance attribution
        dates = sample_returns.index
        position_data = pd.DataFrame({
            'date': dates,
            'symbol': ['STOCK_A'] * len(dates),
            'return': sample_returns.values,
            'weight': [1.0] * len(dates),
            'strategy': ['test'] * len(dates),
            'sector': ['tech'] * len(dates)
        })

        attribution = analytics.calculate_performance_attribution(
            sample_returns, position_data
        )

        # Drawdown analysis
        equity_curve = (1 + sample_returns).cumprod() * 1000000
        dd_analysis = analytics.analyze_drawdowns(equity_curve)

        # Monte Carlo
        mc_results = analytics.monte_carlo_simulation(
            sample_returns, n_simulations=50, n_periods=50
        )

        assert attribution.total_return != 0
        assert dd_analysis.max_drawdown_pct >= 0
        assert mc_results['n_simulations'] == 50


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, '-v', '--tb=short'])
