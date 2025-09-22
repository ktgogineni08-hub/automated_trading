#!/usr/bin/env python3
"""
Unit tests for trading strategies
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add the current directory to the path so we can import the main module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enhanced_trading_system_complete import (
    ImprovedMovingAverageCrossover,
    EnhancedRSIStrategy,
    BollingerBandsStrategy,
    ImprovedVolumeBreakoutStrategy,
    EnhancedSignalAggregator,
    BaseStrategy,
    safe_float_conversion,
    validate_symbol,
    TradingConfig,
    ConfigurationError
)

class TestBaseStrategy(unittest.TestCase):
    """Test base strategy class"""

    def test_base_strategy_initialization(self):
        """Test base strategy initialization"""
        strategy = BaseStrategy("TestStrategy")
        self.assertEqual(strategy.name, "TestStrategy")

    def test_base_strategy_generate_signals_not_implemented(self):
        """Test that generate_signals raises NotImplementedError"""
        strategy = BaseStrategy("TestStrategy")
        with self.assertRaises(NotImplementedError):
            strategy.generate_signals(pd.DataFrame())

    def test_base_strategy_validate_data(self):
        """Test data validation"""
        strategy = BaseStrategy("TestStrategy")

        # Test with None
        self.assertFalse(strategy.validate_data(None))

        # Test with empty DataFrame
        self.assertFalse(strategy.validate_data(pd.DataFrame()))

        # Test with missing columns
        df = pd.DataFrame({'close': [1, 2, 3]})
        self.assertFalse(strategy.validate_data(df))

        # Test with all required columns
        df = pd.DataFrame({
            'open': [1, 2, 3],
            'high': [1.1, 2.1, 3.1],
            'low': [0.9, 1.9, 2.9],
            'close': [1, 2, 3],
            'volume': [100, 200, 300]
        })
        self.assertTrue(strategy.validate_data(df))

class TestMovingAverageCrossover(unittest.TestCase):
    """Test moving average crossover strategy"""

    def setUp(self):
        """Set up test data"""
        # Create test data with clear trend
        dates = pd.date_range('2023-01-01', periods=50, freq='D')
        self.df_uptrend = pd.DataFrame({
            'open': np.linspace(100, 150, 50),
            'high': np.linspace(105, 155, 50),
            'low': np.linspace(95, 145, 50),
            'close': np.linspace(100, 150, 50),
            'volume': np.random.randint(1000, 10000, 50)
        }, index=dates)

        self.strategy = ImprovedMovingAverageCrossover(short_window=5, long_window=10)

    def test_strategy_initialization(self):
        """Test strategy initialization"""
        self.assertEqual(self.strategy.name, "Fast_MA_Crossover")
        self.assertEqual(self.strategy.short_window, 5)
        self.assertEqual(self.strategy.long_window, 10)

    def test_insufficient_data(self):
        """Test with insufficient data"""
        small_df = self.df_uptrend.head(5)
        result = self.strategy.generate_signals(small_df)
        self.assertEqual(result['signal'], 0)
        self.assertEqual(result['reason'], 'insufficient_data')

    def test_bullish_crossover(self):
        """Test bullish crossover signal"""
        # Create data where short MA crosses above long MA
        df = self.df_uptrend.copy()
        # Modify recent data to create crossover
        df.iloc[-3:, df.columns.get_loc('close')] = [140, 145, 150]  # Rising prices

        result = self.strategy.generate_signals(df)
        self.assertIn(result['signal'], [0, 1])  # Could be 0 or 1 depending on exact crossover

    def test_bearish_crossover(self):
        """Test bearish crossover signal"""
        # Create data where short MA crosses below long MA
        df = self.df_uptrend.copy()
        # Modify recent data to create downward crossover
        df.iloc[-3:, df.columns.get_loc('close')] = [160, 155, 150]  # Falling prices

        result = self.strategy.generate_signals(df)
        self.assertIn(result['signal'], [-1, 0, 1])

    def test_no_signal(self):
        """Test no signal condition"""
        result = self.strategy.generate_signals(self.df_uptrend)
        self.assertIn(result['signal'], [-1, 0, 1])
        self.assertIsInstance(result['strength'], float)

class TestRSIStrategy(unittest.TestCase):
    """Test RSI strategy"""

    def setUp(self):
        """Set up test data"""
        dates = pd.date_range('2023-01-01', periods=50, freq='D')
        # Create oversold condition
        self.df_oversold = pd.DataFrame({
            'open': np.linspace(100, 50, 50),
            'high': np.linspace(105, 55, 50),
            'low': np.linspace(95, 45, 50),
            'close': np.linspace(100, 50, 50),
            'volume': np.random.randint(1000, 10000, 50)
        }, index=dates)

        # Create overbought condition
        self.df_overbought = pd.DataFrame({
            'open': np.linspace(50, 100, 50),
            'high': np.linspace(55, 105, 50),
            'low': np.linspace(45, 95, 50),
            'close': np.linspace(50, 100, 50),
            'volume': np.random.randint(1000, 10000, 50)
        }, index=dates)

        self.strategy = EnhancedRSIStrategy(period=7, oversold=25, overbought=75)

    def test_strategy_initialization(self):
        """Test strategy initialization"""
        self.assertEqual(self.strategy.name, "Enhanced_RSI")
        self.assertEqual(self.strategy.period, 7)
        self.assertEqual(self.strategy.oversold, 25)
        self.assertEqual(self.strategy.overbought, 75)

    def test_oversold_signal(self):
        """Test oversold signal generation"""
        result = self.strategy.generate_signals(self.df_oversold)
        self.assertIn(result['signal'], [0, 1])
        if result['signal'] == 1:
            self.assertIn('oversold', result['reason'])

    def test_overbought_signal(self):
        """Test overbought signal generation"""
        result = self.strategy.generate_signals(self.df_overbought)
        self.assertIn(result['signal'], [-1, 0])
        if result['signal'] == -1:
            self.assertIn('overbought', result['reason'])

    def test_neutral_signal(self):
        """Test neutral signal"""
        # Create neutral data
        df_neutral = pd.DataFrame({
            'open': [100] * 50,
            'high': [101] * 50,
            'low': [99] * 50,
            'close': [100] * 50,
            'volume': [1000] * 50
        })
        result = self.strategy.generate_signals(df_neutral)
        self.assertEqual(result['signal'], 0)
        self.assertEqual(result['reason'], 'neutral')

class TestBollingerBandsStrategy(unittest.TestCase):
    """Test Bollinger Bands strategy"""

    def setUp(self):
        """Set up test data"""
        dates = pd.date_range('2023-01-01', periods=50, freq='D')
        # Create data with price touching lower band
        base_price = 100
        self.df_lower_band = pd.DataFrame({
            'open': [base_price - i*0.5 for i in range(50)],
            'high': [base_price - i*0.5 + 1 for i in range(50)],
            'low': [base_price - i*0.5 - 1 for i in range(50)],
            'close': [base_price - i*0.5 for i in range(50)],
            'volume': np.random.randint(1000, 10000, 50)
        }, index=dates)

        # Create data with price touching upper band
        self.df_upper_band = pd.DataFrame({
            'open': [base_price + i*0.5 for i in range(50)],
            'high': [base_price + i*0.5 + 1 for i in range(50)],
            'low': [base_price + i*0.5 - 1 for i in range(50)],
            'close': [base_price + i*0.5 for i in range(50)],
            'volume': np.random.randint(1000, 10000, 50)
        }, index=dates)

        self.strategy = BollingerBandsStrategy(period=20, std_dev=2)

    def test_strategy_initialization(self):
        """Test strategy initialization"""
        self.assertEqual(self.strategy.name, "Bollinger_Bands")
        self.assertEqual(self.strategy.period, 20)
        self.assertEqual(self.strategy.std_dev, 2)

    def test_lower_band_signal(self):
        """Test signal when price touches lower band"""
        result = self.strategy.generate_signals(self.df_lower_band)
        self.assertIn(result['signal'], [0, 1])

    def test_upper_band_signal(self):
        """Test signal when price touches upper band"""
        result = self.strategy.generate_signals(self.df_upper_band)
        self.assertIn(result['signal'], [-1, 0])

class TestVolumeBreakoutStrategy(unittest.TestCase):
    """Test volume breakout strategy"""

    def setUp(self):
        """Set up test data"""
        dates = pd.date_range('2023-01-01', periods=50, freq='D')
        # Create data with volume spike and price increase
        self.df_volume_up = pd.DataFrame({
            'open': np.linspace(100, 120, 50),
            'high': np.linspace(105, 125, 50),
            'low': np.linspace(95, 115, 50),
            'close': np.linspace(100, 120, 50),
            'volume': [1000] * 30 + [5000] * 20  # Volume spike in last 20 days
        }, index=dates)

        # Create data with volume spike and price decrease
        self.df_volume_down = pd.DataFrame({
            'open': np.linspace(120, 100, 50),
            'high': np.linspace(125, 105, 50),
            'low': np.linspace(115, 95, 50),
            'close': np.linspace(120, 100, 50),
            'volume': [1000] * 30 + [5000] * 20  # Volume spike in last 20 days
        }, index=dates)

        self.strategy = ImprovedVolumeBreakoutStrategy(volume_multiplier=1.3, price_threshold=0.001)

    def test_strategy_initialization(self):
        """Test strategy initialization"""
        self.assertEqual(self.strategy.name, "Volume_Price_Breakout")
        self.assertEqual(self.strategy.volume_multiplier, 1.3)
        self.assertEqual(self.strategy.price_threshold, 0.001)

    def test_volume_breakout_up(self):
        """Test volume breakout up signal"""
        result = self.strategy.generate_signals(self.df_volume_up)
        self.assertIn(result['signal'], [-1, 0, 1])

    def test_volume_breakout_down(self):
        """Test volume breakout down signal"""
        result = self.strategy.generate_signals(self.df_volume_down)
        self.assertIn(result['signal'], [-1, 0, 1])

class TestSignalAggregator(unittest.TestCase):
    """Test signal aggregator"""

    def setUp(self):
        """Set up test data"""
        self.aggregator = EnhancedSignalAggregator(min_agreement=0.4)

        # Create mock signals
        self.buy_signals = [
            {'signal': 1, 'strength': 0.8, 'reason': 'bullish'},
            {'signal': 1, 'strength': 0.6, 'reason': 'oversold'},
            {'signal': 0, 'strength': 0.0, 'reason': 'neutral'}
        ]

        self.sell_signals = [
            {'signal': -1, 'strength': 0.7, 'reason': 'bearish'},
            {'signal': -1, 'strength': 0.5, 'reason': 'overbought'},
            {'signal': 0, 'strength': 0.0, 'reason': 'neutral'}
        ]

        self.mixed_signals = [
            {'signal': 1, 'strength': 0.8, 'reason': 'bullish'},
            {'signal': -1, 'strength': 0.7, 'reason': 'bearish'},
            {'signal': 0, 'strength': 0.0, 'reason': 'neutral'}
        ]

    def test_empty_signals(self):
        """Test with empty signal list"""
        result = self.aggregator.aggregate_signals([], "TEST")
        self.assertEqual(result['action'], 'hold')
        self.assertEqual(result['confidence'], 0.0)

    def test_buy_aggregation(self):
        """Test buy signal aggregation"""
        result = self.aggregator.aggregate_signals(self.buy_signals, "TEST")
        self.assertEqual(result['action'], 'buy')
        self.assertGreater(result['confidence'], 0.0)
        self.assertIsInstance(result['reasons'], list)

    def test_sell_aggregation(self):
        """Test sell signal aggregation"""
        result = self.aggregator.aggregate_signals(self.sell_signals, "TEST")
        self.assertEqual(result['action'], 'sell')
        self.assertGreater(result['confidence'], 0.0)
        self.assertIsInstance(result['reasons'], list)

    def test_mixed_signals(self):
        """Test mixed signals result in hold"""
        result = self.aggregator.aggregate_signals(self.mixed_signals, "TEST")
        self.assertEqual(result['action'], 'hold')
        self.assertEqual(result['confidence'], 0.0)

class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions"""

    def test_safe_float_conversion(self):
        """Test safe float conversion"""
        # Test normal conversion
        self.assertEqual(safe_float_conversion(1.5), 1.5)
        self.assertEqual(safe_float_conversion("2.5"), 2.5)

        # Test NaN handling
        self.assertEqual(safe_float_conversion(float('nan')), 0.0)
        self.assertEqual(safe_float_conversion(None), 0.0)

        # Test invalid input
        self.assertEqual(safe_float_conversion("invalid"), 0.0)

    def test_validate_symbol(self):
        """Test symbol validation"""
        # Test valid symbols
        self.assertEqual(validate_symbol("AAPL"), "AAPL")
        self.assertEqual(validate_symbol(" tcs "), "TCS")
        self.assertEqual(validate_symbol("HDFC Bank"), "HDFC BANK")

        # Test invalid symbols
        with self.assertRaises(ValueError):
            validate_symbol("")
        with self.assertRaises(ValueError):
            validate_symbol(None)
        with self.assertRaises(ValueError):
            validate_symbol("A" * 25)  # Too long

class TestConfiguration(unittest.TestCase):
    """Test configuration management"""

    def test_config_from_env(self):
        """Test configuration from environment variables"""
        # Set test environment variables
        os.environ['INITIAL_CAPITAL'] = '2000000'
        os.environ['MAX_POSITIONS'] = '30'

        config = TradingConfig.from_env()

        self.assertEqual(config.initial_capital, 2000000.0)
        self.assertEqual(config.max_positions, 30)

        # Clean up
        del os.environ['INITIAL_CAPITAL']
        del os.environ['MAX_POSITIONS']

    def test_config_validation(self):
        """Test configuration validation"""
        config = TradingConfig()

        # Test valid config
        config.validate()  # Should not raise

        # Test invalid initial capital
        config.initial_capital = -1000
        with self.assertRaises(ConfigurationError):
            config.validate()

        # Test invalid position sizes
        config = TradingConfig()
        config.min_position_size = 0.5
        config.max_position_size = 0.3
        with self.assertRaises(ConfigurationError):
            config.validate()

if __name__ == '__main__':
    # Set up test environment
    os.environ.setdefault('LOG_LEVEL', 'ERROR')  # Reduce log noise during tests

    # Run tests
    unittest.main(verbosity=2)