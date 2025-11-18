#!/usr/bin/env python3
"""
Comprehensive tests for regime_detector.py module
Tests MarketRegimeDetector for market regime detection using technical analysis
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.regime_detector import MarketRegimeDetector


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_data_provider():
    """Mock data provider"""
    provider = Mock()
    provider.fetch_with_retry = Mock(return_value=pd.DataFrame())
    return provider


@pytest.fixture
def detector(mock_data_provider):
    """Create MarketRegimeDetector instance"""
    return MarketRegimeDetector(
        data_provider=mock_data_provider,
        short_window=20,
        long_window=50,
        adx_window=14,
        trend_slope_lookback=5
    )


@pytest.fixture
def sample_price_data():
    """Create sample price data for testing"""
    dates = pd.date_range(start='2025-01-01', periods=100, freq='30min')
    data = {
        'open': np.random.uniform(2400, 2500, 100),
        'high': np.random.uniform(2450, 2550, 100),
        'low': np.random.uniform(2350, 2450, 100),
        'close': np.random.uniform(2400, 2500, 100)
    }
    df = pd.DataFrame(data, index=dates)
    # Ensure high is actually high and low is actually low
    df['high'] = df[['open', 'high', 'close']].max(axis=1) + 10
    df['low'] = df[['open', 'low', 'close']].min(axis=1) - 10
    return df


@pytest.fixture
def bullish_price_data():
    """Create price data with bullish trend"""
    dates = pd.date_range(start='2025-01-01', periods=100, freq='30min')
    # Create upward trending data
    close = np.linspace(2400, 2600, 100) + np.random.normal(0, 5, 100)
    data = {
        'open': close - np.random.uniform(5, 15, 100),
        'high': close + np.random.uniform(10, 20, 100),
        'low': close - np.random.uniform(10, 20, 100),
        'close': close
    }
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def bearish_price_data():
    """Create price data with bearish trend"""
    dates = pd.date_range(start='2025-01-01', periods=100, freq='30min')
    # Create downward trending data
    close = np.linspace(2600, 2400, 100) + np.random.normal(0, 5, 100)
    data = {
        'open': close + np.random.uniform(5, 15, 100),
        'high': close + np.random.uniform(10, 20, 100),
        'low': close - np.random.uniform(10, 20, 100),
        'close': close
    }
    return pd.DataFrame(data, index=dates)


# ============================================================================
# Initialization Tests
# ============================================================================

class TestInitialization:
    """Test detector initialization"""

    def test_initialization_default_params(self):
        """Test initialization with default parameters"""
        detector = MarketRegimeDetector()

        assert detector.short_window == 20
        assert detector.long_window == 50
        assert detector.adx_window == 14
        assert detector.trend_slope_lookback == 5

    def test_initialization_custom_params(self):
        """Test initialization with custom parameters"""
        detector = MarketRegimeDetector(
            short_window=10,
            long_window=30,
            adx_window=10,
            trend_slope_lookback=3
        )

        assert detector.short_window == 10
        assert detector.long_window == 30
        assert detector.adx_window == 10
        assert detector.trend_slope_lookback == 3

    def test_update_data_provider(self, detector):
        """Test updating data provider after initialization"""
        new_provider = Mock()
        detector.update_data_provider(new_provider)

        assert detector.data_provider == new_provider


# ============================================================================
# Regime Detection Tests
# ============================================================================

class TestRegimeDetection:
    """Test regime detection logic"""

    def test_detect_regime_insufficient_data(self, detector):
        """Test detection with insufficient data returns unknown"""
        small_df = pd.DataFrame({
            'open': [100],
            'high': [105],
            'low': [95],
            'close': [102]
        })

        result = detector.detect_regime('TEST', price_data=small_df)

        assert result['regime'] == 'unknown'
        assert result['confidence'] == 0.0

    def test_detect_regime_empty_dataframe(self, detector):
        """Test detection with empty DataFrame"""
        empty_df = pd.DataFrame()

        result = detector.detect_regime('TEST', price_data=empty_df)

        assert result['regime'] == 'unknown'
        # For unknown regime, bias is also 'unknown' (not neutral)
        assert result['bias'] == 'unknown'

    def test_detect_regime_with_bullish_data(self, detector, bullish_price_data):
        """Test detection of bullish regime"""
        result = detector.detect_regime('TEST', price_data=bullish_price_data)

        assert result['symbol'] == 'TEST'
        assert 'regime' in result
        assert 'bias' in result
        assert result['adx'] >= 0
        assert result['short_ma'] > 0
        assert result['long_ma'] > 0

    def test_detect_regime_with_bearish_data(self, detector, bearish_price_data):
        """Test detection of bearish regime"""
        result = detector.detect_regime('TEST', price_data=bearish_price_data)

        assert result['symbol'] == 'TEST'
        assert 'regime' in result
        assert 'bias' in result
        assert result['adx'] >= 0

    def test_detect_regime_returns_all_fields(self, detector, sample_price_data):
        """Test that detect_regime returns all expected fields"""
        result = detector.detect_regime('TEST', price_data=sample_price_data)

        required_fields = [
            'symbol', 'regime', 'bias', 'adx',
            'short_ma', 'long_ma', 'short_slope', 'long_slope',
            'trend_strength', 'confidence', 'data_points', 'updated_at'
        ]

        for field in required_fields:
            assert field in result

    def test_detect_regime_confidence_bounded(self, detector, sample_price_data):
        """Test that confidence is bounded between 0 and 1"""
        result = detector.detect_regime('TEST', price_data=sample_price_data)

        assert 0.0 <= result['confidence'] <= 1.0

    def test_detect_regime_handles_exception(self, detector):
        """Test that detection handles exceptions gracefully"""
        # Create data that will cause an exception
        bad_data = pd.DataFrame({
            'close': ['invalid']  # Invalid data type
        })

        result = detector.detect_regime('TEST', price_data=bad_data)

        assert result['regime'] == 'unknown'


# ============================================================================
# Data Loading Tests
# ============================================================================

class TestDataLoading:
    """Test data loading functionality"""

    def test_load_price_data_uses_provided_data(self, detector, sample_price_data):
        """Test that provided price data is used when available"""
        result = detector._load_price_data('TEST', '30minute', 30, sample_price_data)

        assert not result.empty
        assert len(result) == len(sample_price_data)

    def test_load_price_data_fetches_from_provider(self, detector, sample_price_data):
        """Test that data is fetched from provider when not provided"""
        detector.data_provider.fetch_with_retry.return_value = sample_price_data

        result = detector._load_price_data('TEST', '30minute', 30, None)

        detector.data_provider.fetch_with_retry.assert_called_once_with(
            'TEST', interval='30minute', days=30
        )
        assert not result.empty

    def test_load_price_data_no_provider(self, detector):
        """Test data loading with no provider"""
        detector.data_provider = None

        result = detector._load_price_data('TEST', '30minute', 30, None)

        assert result.empty

    def test_load_price_data_provider_exception(self, detector):
        """Test that provider exceptions are handled"""
        detector.data_provider.fetch_with_retry.side_effect = Exception("API error")

        result = detector._load_price_data('TEST', '30minute', 30, None)

        assert result.empty

    def test_load_price_data_provider_returns_none(self, detector):
        """Test handling when provider returns None"""
        detector.data_provider.fetch_with_retry.return_value = None

        result = detector._load_price_data('TEST', '30minute', 30, None)

        assert result.empty


# ============================================================================
# ADX Calculation Tests
# ============================================================================

class TestADXCalculation:
    """Test ADX calculation"""

    def test_calculate_adx_basic(self, detector, sample_price_data):
        """Test basic ADX calculation"""
        adx = detector._calculate_adx(sample_price_data)

        assert isinstance(adx, pd.Series)
        assert len(adx) == len(sample_price_data)
        assert not adx.empty

    def test_calculate_adx_values_non_negative(self, detector, sample_price_data):
        """Test that ADX values are non-negative"""
        adx = detector._calculate_adx(sample_price_data)

        # ADX should be >= 0 (or NaN for first few values)
        assert all(adx.dropna() >= 0)

    def test_calculate_adx_trending_market(self, detector, bullish_price_data):
        """Test ADX in strongly trending market"""
        adx = detector._calculate_adx(bullish_price_data)

        # In trending market, ADX should generally be higher
        latest_adx = adx.iloc[-1]
        assert latest_adx >= 0  # At minimum, should be non-negative

    def test_calculate_adx_handles_nan(self, detector):
        """Test ADX calculation handles NaN values"""
        # Create data with some NaN values
        df = pd.DataFrame({
            'open': [100, 105, np.nan, 110],
            'high': [105, 110, np.nan, 115],
            'low': [95, 100, np.nan, 105],
            'close': [102, 108, np.nan, 112]
        })

        adx = detector._calculate_adx(df)

        # Should not raise exception, returns series
        assert isinstance(adx, pd.Series)


# ============================================================================
# Default Response Tests
# ============================================================================

class TestDefaultResponse:
    """Test default response generation"""

    def test_default_response_unknown(self, detector):
        """Test default response for unknown regime"""
        result = detector._default_response('TEST', 'unknown')

        assert result['symbol'] == 'TEST'
        assert result['regime'] == 'unknown'
        assert result['bias'] == 'unknown'
        assert result['confidence'] == 0.0

    def test_default_response_sideways(self, detector):
        """Test default response for sideways regime"""
        result = detector._default_response('TEST', 'sideways')

        assert result['regime'] == 'sideways'
        assert result['bias'] == 'neutral'

    def test_default_response_bullish(self, detector):
        """Test default response for bullish regime"""
        result = detector._default_response('TEST', 'bullish')

        assert result['regime'] == 'bullish'
        assert result['bias'] == 'bullish'

    def test_default_response_has_all_fields(self, detector):
        """Test that default response has all required fields"""
        result = detector._default_response('TEST', 'unknown')

        required_fields = [
            'symbol', 'regime', 'bias', 'adx',
            'short_ma', 'long_ma', 'short_slope', 'long_slope',
            'trend_strength', 'confidence', 'data_points', 'updated_at'
        ]

        for field in required_fields:
            assert field in result

    def test_default_response_zeroes_numeric_fields(self, detector):
        """Test that default response zeros out numeric fields"""
        result = detector._default_response('TEST', 'unknown')

        assert result['adx'] == 0.0
        assert result['short_ma'] == 0.0
        assert result['long_ma'] == 0.0
        assert result['short_slope'] == 0.0
        assert result['long_slope'] == 0.0
        assert result['trend_strength'] == 0.0
        assert result['data_points'] == 0


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Test integration scenarios"""

    def test_full_workflow_with_provider(self, mock_data_provider, sample_price_data):
        """Test full workflow with data provider"""
        mock_data_provider.fetch_with_retry.return_value = sample_price_data

        detector = MarketRegimeDetector(data_provider=mock_data_provider)
        result = detector.detect_regime('TEST', interval='30minute', days=30)

        assert result['symbol'] == 'TEST'
        assert result['data_points'] > 0
        assert 'updated_at' in result

    def test_regime_classification_thresholds(self, detector):
        """Test regime classification returns valid regime"""
        # Create price data
        dates = pd.date_range(start='2025-01-01', periods=100, freq='30min')
        data = pd.DataFrame({
            'open': np.full(100, 2500) + np.random.normal(0, 2, 100),
            'high': np.full(100, 2510) + np.random.normal(0, 2, 100),
            'low': np.full(100, 2490) + np.random.normal(0, 2, 100),
            'close': np.full(100, 2500) + np.random.normal(0, 2, 100)
        }, index=dates)

        result = detector.detect_regime('TEST', price_data=data)

        # Should return a valid regime (any regime is acceptable with random data)
        assert result['regime'] in ['sideways', 'neutral', 'unknown', 'bullish', 'bearish']

    def test_moving_averages_calculated(self, detector, sample_price_data):
        """Test that moving averages are properly calculated"""
        result = detector.detect_regime('TEST', price_data=sample_price_data)

        # MAs should be positive and reasonable
        assert result['short_ma'] > 0
        assert result['long_ma'] > 0
        # Short MA should be close to long MA (same order of magnitude)
        assert 0.5 < (result['short_ma'] / result['long_ma']) < 2.0

    def test_slopes_calculated(self, detector, sample_price_data):
        """Test that slopes are calculated"""
        result = detector.detect_regime('TEST', price_data=sample_price_data)

        # Slopes can be positive, negative, or zero
        assert isinstance(result['short_slope'], (int, float))
        assert isinstance(result['long_slope'], (int, float))


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_minimum_data_points(self, detector):
        """Test with minimum required data points"""
        # Create data with exactly minimum length
        min_length = max(detector.long_window + detector.adx_window, 30)
        dates = pd.date_range(start='2025-01-01', periods=min_length, freq='30min')
        df = pd.DataFrame({
            'open': np.full(min_length, 2500),
            'high': np.full(min_length, 2510),
            'low': np.full(min_length, 2490),
            'close': np.full(min_length, 2500)
        }, index=dates)

        result = detector.detect_regime('TEST', price_data=df)

        # Should process without error
        assert 'regime' in result

    def test_all_same_prices(self, detector):
        """Test with all identical prices (zero volatility)"""
        dates = pd.date_range(start='2025-01-01', periods=100, freq='30min')
        df = pd.DataFrame({
            'open': np.full(100, 2500),
            'high': np.full(100, 2500),
            'low': np.full(100, 2500),
            'close': np.full(100, 2500)
        }, index=dates)

        result = detector.detect_regime('TEST', price_data=df)

        # Should handle gracefully
        assert result['regime'] in ['sideways', 'neutral', 'unknown']

    def test_extreme_volatility(self, detector):
        """Test with extreme price volatility"""
        dates = pd.date_range(start='2025-01-01', periods=100, freq='30min')
        # Create highly volatile data
        close = 2500 + np.random.normal(0, 500, 100)
        df = pd.DataFrame({
            'open': close - 100,
            'high': close + 200,
            'low': close - 200,
            'close': close
        }, index=dates)

        result = detector.detect_regime('TEST', price_data=df)

        # Should handle without crashing
        assert 'regime' in result
        assert result['confidence'] >= 0

    def test_missing_ohlc_columns(self, detector):
        """Test with missing required columns"""
        df = pd.DataFrame({
            'close': [100, 105, 110]
        })

        result = detector.detect_regime('TEST', price_data=df)

        # Should return unknown regime
        assert result['regime'] == 'unknown'


if __name__ == "__main__":
    # Run tests with: pytest test_regime_detector.py -v
    pytest.main([__file__, "-v", "--tb=short"])
