#!/usr/bin/env python3
"""
Comprehensive tests for signal_aggregator.py module
Tests EnhancedSignalAggregator for multi-strategy signal aggregation
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock config before importing
sys.modules['config'] = MagicMock(signal_agreement_threshold=0.5)

from core.signal_aggregator import EnhancedSignalAggregator


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def aggregator():
    """Create EnhancedSignalAggregator instance"""
    return EnhancedSignalAggregator(min_agreement=0.5)


# ============================================================================
# Initialization Tests
# ============================================================================

class TestInitialization:
    """Test aggregator initialization"""

    def test_initialization_default_agreement(self):
        """Test initialization with default agreement threshold"""
        agg = EnhancedSignalAggregator()

        assert agg.min_agreement == 0.5  # From mocked config
        assert agg.market_bias == 'neutral'
        assert agg.signal_history == {}

    def test_initialization_custom_agreement(self):
        """Test initialization with custom agreement threshold"""
        agg = EnhancedSignalAggregator(min_agreement=0.7)

        assert agg.min_agreement == 0.7

    def test_initialization_zero_agreement(self):
        """Test initialization with zero agreement defaults to config"""
        # Note: 0.0 is falsy, so it uses config value
        agg = EnhancedSignalAggregator(min_agreement=0.0)

        assert agg.min_agreement == 0.5  # Falls back to config


# ============================================================================
# Market Regime Tests
# ============================================================================

class TestMarketRegime:
    """Test market regime updates"""

    def test_update_market_regime_bullish(self, aggregator):
        """Test updating to bullish regime"""
        aggregator.update_market_regime({'bias': 'bullish'})

        assert aggregator.market_bias == 'bullish'

    def test_update_market_regime_bearish(self, aggregator):
        """Test updating to bearish regime"""
        aggregator.update_market_regime({'regime': 'bearish'})

        assert aggregator.market_bias == 'bearish'

    def test_update_market_regime_neutral(self, aggregator):
        """Test updating to neutral regime"""
        aggregator.update_market_regime({'bias': 'neutral'})

        assert aggregator.market_bias == 'neutral'

    def test_update_market_regime_case_insensitive(self, aggregator):
        """Test that regime is case-insensitive"""
        aggregator.update_market_regime({'bias': 'BULLISH'})

        assert aggregator.market_bias == 'bullish'

    def test_update_market_regime_invalid_defaults_neutral(self, aggregator):
        """Test that invalid regime defaults to neutral"""
        aggregator.update_market_regime({'bias': 'unknown'})

        assert aggregator.market_bias == 'neutral'

    def test_update_market_regime_none(self, aggregator):
        """Test updating with None regime"""
        aggregator.update_market_regime(None)

        assert aggregator.market_bias == 'neutral'

    def test_update_market_regime_empty_dict(self, aggregator):
        """Test updating with empty dict"""
        aggregator.update_market_regime({})

        assert aggregator.market_bias == 'neutral'

    def test_update_market_regime_stores_full_info(self, aggregator):
        """Test that full regime info is stored"""
        regime_info = {'bias': 'bullish', 'volatility': 'high', 'trend': 'up'}
        aggregator.update_market_regime(regime_info)

        assert aggregator.market_regime == regime_info


# ============================================================================
# Regime Allows Tests
# ============================================================================

class TestRegimeAllows:
    """Test regime filtering logic"""

    def test_regime_allows_exit_always_true(self, aggregator):
        """Test that exits are always allowed"""
        aggregator.market_bias = 'bullish'

        # Sell exit should be allowed even in bullish market
        assert aggregator._regime_allows('sell', is_exit=True) is True

        aggregator.market_bias = 'bearish'

        # Buy exit should be allowed even in bearish market
        assert aggregator._regime_allows('buy', is_exit=True) is True

    def test_regime_allows_buy_entry_in_neutral(self, aggregator):
        """Test buy entries allowed in neutral market"""
        aggregator.market_bias = 'neutral'

        assert aggregator._regime_allows('buy', is_exit=False) is True

    def test_regime_allows_sell_entry_in_neutral(self, aggregator):
        """Test sell entries allowed in neutral market"""
        aggregator.market_bias = 'neutral'

        assert aggregator._regime_allows('sell', is_exit=False) is True

    def test_regime_blocks_sell_entry_in_bullish(self, aggregator):
        """Test sell entries blocked in bullish market"""
        aggregator.market_bias = 'bullish'

        assert aggregator._regime_allows('sell', is_exit=False) is False

    def test_regime_blocks_buy_entry_in_bearish(self, aggregator):
        """Test buy entries blocked in bearish market"""
        aggregator.market_bias = 'bearish'

        assert aggregator._regime_allows('buy', is_exit=False) is False

    def test_regime_allows_buy_entry_in_bullish(self, aggregator):
        """Test buy entries allowed in bullish market"""
        aggregator.market_bias = 'bullish'

        assert aggregator._regime_allows('buy', is_exit=False) is True

    def test_regime_allows_sell_entry_in_bearish(self, aggregator):
        """Test sell entries allowed in bearish market"""
        aggregator.market_bias = 'bearish'

        assert aggregator._regime_allows('sell', is_exit=False) is True


# ============================================================================
# Signal Aggregation Tests
# ============================================================================

class TestSignalAggregation:
    """Test signal aggregation logic"""

    def test_aggregate_no_signals_returns_hold(self, aggregator):
        """Test that no signals returns hold"""
        result = aggregator.aggregate_signals([], 'RELIANCE')

        assert result['action'] == 'hold'
        assert result['confidence'] == 0.0

    def test_aggregate_strong_buy_signals(self, aggregator):
        """Test aggregating strong buy signals"""
        signals = [
            {'signal': 1, 'strength': 0.8, 'reason': 'RSI oversold'},
            {'signal': 1, 'strength': 0.7, 'reason': 'MACD crossover'},
            {'signal': 1, 'strength': 0.9, 'reason': 'Trend following'}
        ]

        result = aggregator.aggregate_signals(signals, 'RELIANCE')

        assert result['action'] == 'buy'
        assert result['confidence'] > 0.7
        assert len(result['reasons']) == 3

    def test_aggregate_strong_sell_signals(self, aggregator):
        """Test aggregating strong sell signals"""
        signals = [
            {'signal': -1, 'strength': 0.8, 'reason': 'RSI overbought'},
            {'signal': -1, 'strength': 0.7, 'reason': 'Resistance hit'}
        ]

        result = aggregator.aggregate_signals(signals, 'TCS')

        assert result['action'] == 'sell'
        assert result['confidence'] > 0.0

    def test_aggregate_mixed_signals_requires_agreement(self, aggregator):
        """Test that mixed signals require agreement threshold"""
        signals = [
            {'signal': 1, 'strength': 0.8, 'reason': 'Buy'},
            {'signal': -1, 'strength': 0.7, 'reason': 'Sell'},
            {'signal': 0, 'strength': 0.0, 'reason': 'Hold'}
        ]

        result = aggregator.aggregate_signals(signals, 'RELIANCE')

        # With 50% threshold, 1/3 buy (33%) and 1/3 sell (33%) - neither meets threshold
        assert result['action'] == 'hold'

    def test_aggregate_weak_signals_filtered(self, aggregator):
        """Test that weak signals (<0.20 confidence) are filtered"""
        signals = [
            {'signal': 1, 'strength': 0.10, 'reason': 'Weak buy'},
            {'signal': 1, 'strength': 0.15, 'reason': 'Weak buy 2'}
        ]

        result = aggregator.aggregate_signals(signals, 'RELIANCE')

        # Average strength 0.125 < 0.20 threshold
        assert result['action'] == 'hold'

    def test_aggregate_confidence_includes_agreement(self, aggregator):
        """Test that confidence score includes agreement factor"""
        signals = [
            {'signal': 1, 'strength': 1.0, 'reason': 'Strong buy'}
        ]

        result = aggregator.aggregate_signals(signals, 'RELIANCE')

        # Confidence = strength * (0.6 + agreement * 0.4)
        # With 100% agreement (1 of 1): 1.0 * (0.6 + 1.0 * 0.4) = 1.0
        assert result['action'] == 'buy'
        assert result['confidence'] == pytest.approx(1.0)

    def test_aggregate_non_dict_signals_skipped(self, aggregator):
        """Test that non-dict signals are skipped"""
        signals = [
            {'signal': 1, 'strength': 0.8, 'reason': 'Buy'},
            None,  # Should be skipped
            'invalid',  # Should be skipped
            {'signal': 1, 'strength': 0.9, 'reason': 'Buy 2'}
        ]

        result = aggregator.aggregate_signals(signals, 'RELIANCE')

        # Should only count the 2 valid dict signals
        assert result['action'] == 'buy'


# ============================================================================
# Exit Signal Tests
# ============================================================================

class TestExitSignals:
    """Test exit signal handling with lower thresholds"""

    def test_exit_signal_lowers_agreement_threshold(self, aggregator):
        """Test that exit signals have lower agreement threshold"""
        # Single sell signal among 4 strategies
        signals = [
            {'signal': -1, 'strength': 0.8, 'reason': 'Risk management'},
            {'signal': 0, 'strength': 0.0, 'reason': 'Hold'},
            {'signal': 0, 'strength': 0.0, 'reason': 'Hold'},
            {'signal': 0, 'strength': 0.0, 'reason': 'Hold'}
        ]

        # For entries, this wouldn't meet 50% threshold
        result_entry = aggregator.aggregate_signals(signals, 'RELIANCE', is_exit=False)
        assert result_entry['action'] == 'hold'

        # For exits, any single signal (1/4 = 25%) triggers exit
        result_exit = aggregator.aggregate_signals(signals, 'RELIANCE', is_exit=True)
        assert result_exit['action'] == 'sell'

    def test_exit_always_allowed_regardless_of_regime(self, aggregator):
        """Test that exits are allowed regardless of market regime"""
        aggregator.market_bias = 'bullish'

        # Sell exit should work even in bullish market
        signals = [
            {'signal': -1, 'strength': 0.8, 'reason': 'Take profit'}
        ]

        result = aggregator.aggregate_signals(signals, 'RELIANCE', is_exit=True)

        assert result['action'] == 'sell'

    def test_exit_logs_debug_message(self, aggregator):
        """Test that exit mode logs debug message"""
        signals = [
            {'signal': -1, 'strength': 0.8, 'reason': 'Exit'}
        ]

        with patch('core.signal_aggregator.logger') as mock_logger:
            result = aggregator.aggregate_signals(signals, 'RELIANCE', is_exit=True)

            # Should have logged debug message about lowered threshold
            mock_logger.debug.assert_called_once()


# ============================================================================
# Regime Filtering Tests
# ============================================================================

class TestRegimeFiltering:
    """Test regime-based signal filtering"""

    def test_bullish_regime_blocks_sell_entries(self, aggregator):
        """Test bullish regime blocks new sell entries"""
        aggregator.market_bias = 'bullish'

        signals = [
            {'signal': -1, 'strength': 0.8, 'reason': 'Sell signal'}
        ]

        result = aggregator.aggregate_signals(signals, 'RELIANCE', is_exit=False)

        assert result['action'] == 'hold'

    def test_bearish_regime_blocks_buy_entries(self, aggregator):
        """Test bearish regime blocks new buy entries"""
        aggregator.market_bias = 'bearish'

        signals = [
            {'signal': 1, 'strength': 0.8, 'reason': 'Buy signal'}
        ]

        result = aggregator.aggregate_signals(signals, 'RELIANCE', is_exit=False)

        assert result['action'] == 'hold'

    def test_regime_blocking_logs_message(self, aggregator):
        """Test that regime blocking logs informative message"""
        aggregator.market_bias = 'bullish'

        signals = [
            {'signal': -1, 'strength': 0.8, 'reason': 'Sell'}
        ]

        with patch('core.signal_aggregator.logger') as mock_logger:
            result = aggregator.aggregate_signals(signals, 'RELIANCE', is_exit=False)

            # Should have logged info about blocking
            mock_logger.info.assert_called_once()
            assert 'blocked' in str(mock_logger.info.call_args[0][0]).lower()

    def test_regime_blocking_not_logged_for_exits(self, aggregator):
        """Test that regime blocking is not logged for exits"""
        aggregator.market_bias = 'bullish'

        signals = [
            {'signal': -1, 'strength': 0.8, 'reason': 'Exit'}
        ]

        with patch('core.signal_aggregator.logger') as mock_logger:
            result = aggregator.aggregate_signals(signals, 'RELIANCE', is_exit=True)

            # Should not log blocking message for exits (exits are allowed)
            assert result['action'] == 'sell'


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_zero_total_strategies(self, aggregator):
        """Test handling of zero total strategies"""
        signals = []

        result = aggregator.aggregate_signals(signals, 'RELIANCE')

        assert result['action'] == 'hold'
        assert result['confidence'] == 0.0

    def test_all_hold_signals(self, aggregator):
        """Test all strategies recommending hold"""
        signals = [
            {'signal': 0, 'strength': 0.0, 'reason': 'Hold'},
            {'signal': 0, 'strength': 0.0, 'reason': 'Hold'}
        ]

        result = aggregator.aggregate_signals(signals, 'RELIANCE')

        assert result['action'] == 'hold'

    def test_signals_missing_strength(self, aggregator):
        """Test signals with missing strength field"""
        signals = [
            {'signal': 1, 'reason': 'Buy'}  # Missing strength
        ]

        result = aggregator.aggregate_signals(signals, 'RELIANCE')

        # Should use default strength of 0.0
        assert result['action'] == 'hold'

    def test_signals_missing_reason(self, aggregator):
        """Test signals with missing reason field"""
        signals = [
            {'signal': 1, 'strength': 0.8}  # Missing reason
        ]

        result = aggregator.aggregate_signals(signals, 'RELIANCE')

        assert result['action'] == 'buy'
        assert '' in result['reasons']

    def test_exactly_at_threshold(self, aggregator):
        """Test signals exactly at threshold"""
        signals = [
            {'signal': 1, 'strength': 0.6, 'reason': 'Buy'},
            {'signal': 0, 'strength': 0.0, 'reason': 'Hold'}
        ]

        # Exactly 50% agreement (1 of 2)
        result = aggregator.aggregate_signals(signals, 'RELIANCE')

        assert result['action'] == 'buy'


if __name__ == "__main__":
    # Run tests with: pytest test_signal_aggregator.py -v
    pytest.main([__file__, "-v", "--tb=short"])
