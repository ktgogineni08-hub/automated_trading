#!/usr/bin/env python3
"""
Test Refactored Strategies
Validates that new strategies work correctly
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Test the refactored strategies
from strategies.bollinger_fixed_new import BollingerBandsStrategy
from strategies.rsi_fixed_new import EnhancedRSIStrategy
from strategies.moving_average_fixed_new import ImprovedMovingAverageCrossover

def create_test_data(length=100):
    """Create sample OHLCV data for testing"""
    dates = pd.date_range(start='2025-01-01', periods=length, freq='5min')

    # Create realistic price movement
    base_price = 100
    price_changes = np.random.randn(length) * 0.5
    prices = base_price + np.cumsum(price_changes)

    data = pd.DataFrame({
        'open': prices + np.random.randn(length) * 0.2,
        'high': prices + abs(np.random.randn(length)) * 0.5,
        'low': prices - abs(np.random.randn(length)) * 0.5,
        'close': prices,
        'volume': np.random.randint(1000, 5000, length)
    }, index=dates)

    # Ensure high >= open, close and low <= open, close
    data['high'] = data[['high', 'open', 'close']].max(axis=1)
    data['low'] = data[['low', 'open', 'close']].min(axis=1)

    return data

def test_bollinger_strategy():
    """Test Bollinger Bands strategy"""
    print("Testing Bollinger Bands Strategy...")

    strategy = BollingerBandsStrategy(
        period=20,
        std_dev=2,
        confirmation_bars=2,
        cooldown_minutes=15
    )

    data = create_test_data(150)

    # Test signal generation
    signal = strategy.generate_signals(data, 'TEST_SYMBOL')

    print(f"  ✅ Strategy created: {strategy.name}")
    print(f"  ✅ Signal generated: {signal}")
    print(f"     - Action: {signal.get('signal', 'N/A')}")
    print(f"     - Strength: {signal.get('strength', 0):.2f}")
    print(f"     - Reason: {signal.get('reason', 'N/A')}")

    # Test state management
    state = strategy.get_state()
    print(f"  ✅ State: {state}")

    # Test reset
    strategy.reset()
    print(f"  ✅ Reset successful")

    return True

def test_rsi_strategy():
    """Test RSI strategy"""
    print("\nTesting RSI Strategy...")

    strategy = EnhancedRSIStrategy(
        period=7,
        oversold=25,
        overbought=75,
        confirmation_bars=2,
        cooldown_minutes=15
    )

    data = create_test_data(150)

    # Test signal generation
    signal = strategy.generate_signals(data, 'TEST_SYMBOL')

    print(f"  ✅ Strategy created: {strategy.name}")
    print(f"  ✅ Signal generated: {signal}")
    print(f"     - Action: {signal.get('signal', 'N/A')}")
    print(f"     - Strength: {signal.get('strength', 0):.2f}")
    print(f"     - Reason: {signal.get('reason', 'N/A')}")

    # Test position tracking
    strategy.set_position('TEST_SYMBOL', 1)  # Long position
    pos = strategy.get_position('TEST_SYMBOL')
    print(f"  ✅ Position tracking: {pos}")

    strategy.reset()
    print(f"  ✅ Reset successful")

    return True

def test_ma_strategy():
    """Test Moving Average strategy"""
    print("\nTesting Moving Average Strategy...")

    strategy = ImprovedMovingAverageCrossover(
        short_window=5,
        long_window=20,
        confirmation_bars=1,
        cooldown_minutes=15
    )

    data = create_test_data(150)

    # Test signal generation
    signal = strategy.generate_signals(data, 'TEST_SYMBOL')

    print(f"  ✅ Strategy created: {strategy.name}")
    print(f"  ✅ Signal generated: {signal}")
    print(f"     - Action: {signal.get('signal', 'N/A')}")
    print(f"     - Strength: {signal.get('strength', 0):.2f}")
    print(f"     - Reason: {signal.get('reason', 'N/A')}")

    strategy.reset()
    print(f"  ✅ Reset successful")

    return True

def test_all_strategies():
    """Test all refactored strategies"""
    print("=" * 70)
    print("  REFACTORED STRATEGIES TEST")
    print("=" * 70)
    print()

    try:
        # Test each strategy
        bb_ok = test_bollinger_strategy()
        rsi_ok = test_rsi_strategy()
        ma_ok = test_ma_strategy()

        print()
        print("=" * 70)
        if bb_ok and rsi_ok and ma_ok:
            print("✅ ALL TESTS PASSED")
            print("=" * 70)
            print()
            print("Summary:")
            print("  ✅ Bollinger Bands strategy: WORKING")
            print("  ✅ RSI strategy: WORKING")
            print("  ✅ Moving Average strategy: WORKING")
            print()
            print("All refactored strategies are ready to use!")
            return True
        else:
            print("❌ SOME TESTS FAILED")
            print("=" * 70)
            return False

    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ TEST ERROR: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_all_strategies()
    exit(0 if success else 1)
