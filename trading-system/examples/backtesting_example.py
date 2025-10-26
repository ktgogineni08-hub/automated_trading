#!/usr/bin/env python3
"""
Comprehensive Backtesting Example
Phase 3: Advanced Features

This example demonstrates:
1. Multiple trading strategies (SMA, RSI, Bollinger Bands)
2. Parameter optimization
3. Walk-forward optimization to prevent overfitting
4. Performance comparison
5. Equity curve visualization (conceptual)
"""

import numpy as np
import pandas as pd
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('backtesting_example')

from core.vectorized_backtester import (
    VectorizedBacktester,
    BacktestConfig,
    Strategy
)


# Strategy 1: Simple Moving Average Crossover
class SMAStrategy(Strategy):
    """Simple Moving Average Crossover Strategy"""

    def __init__(self, fast_period: int = 20, slow_period: int = 50):
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0

        # Calculate moving averages (VECTORIZED)
        signals['fast_ma'] = data['close'].rolling(window=self.fast_period).mean()
        signals['slow_ma'] = data['close'].rolling(window=self.slow_period).mean()

        # Generate signals (VECTORIZED)
        signals['signal'] = np.where(signals['fast_ma'] > signals['slow_ma'], 1, 0)

        # Detect crossovers
        signals['position_change'] = signals['signal'].diff()
        signals.loc[signals['position_change'] == 1, 'signal'] = 1
        signals.loc[signals['position_change'] == -1, 'signal'] = -1

        return signals


# Strategy 2: RSI Mean Reversion
class RSIStrategy(Strategy):
    """RSI Mean Reversion Strategy"""

    def __init__(self, rsi_period: int = 14, oversold: int = 30, overbought: int = 70):
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0

        # Calculate RSI (VECTORIZED)
        delta = data['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        signals['rsi'] = rsi

        # Buy when RSI < oversold, sell when RSI > overbought (VECTORIZED)
        signals.loc[rsi < self.oversold, 'signal'] = 1
        signals.loc[rsi > self.overbought, 'signal'] = -1

        return signals


# Strategy 3: Bollinger Bands
class BollingerBandsStrategy(Strategy):
    """Bollinger Bands Mean Reversion Strategy"""

    def __init__(self, period: int = 20, num_std: float = 2.0):
        self.period = period
        self.num_std = num_std

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0

        # Calculate Bollinger Bands (VECTORIZED)
        signals['middle_band'] = data['close'].rolling(window=self.period).mean()
        signals['std'] = data['close'].rolling(window=self.period).std()

        signals['upper_band'] = signals['middle_band'] + (signals['std'] * self.num_std)
        signals['lower_band'] = signals['middle_band'] - (signals['std'] * self.num_std)

        # Buy when price touches lower band, sell when price touches upper band (VECTORIZED)
        signals.loc[data['close'] <= signals['lower_band'], 'signal'] = 1
        signals.loc[data['close'] >= signals['upper_band'], 'signal'] = -1

        return signals


def generate_realistic_data(days: int = 730, initial_price: float = 100.0) -> pd.DataFrame:
    """
    Generate realistic synthetic market data with:
    - Trend
    - Volatility
    - Mean reversion
    - Random noise
    """
    np.random.seed(42)

    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')

    # Generate price series with multiple components
    trend = np.linspace(0, 50, days)  # Upward trend

    # Cyclical component (mean reversion)
    cyclical = 10 * np.sin(np.linspace(0, 8 * np.pi, days))

    # Random walk
    random_walk = np.random.normal(0, 1, days).cumsum()

    # Combine components
    close_prices = initial_price + trend + cyclical + random_walk

    # Generate OHLCV
    data = pd.DataFrame({
        'open': close_prices * (1 + np.random.uniform(-0.01, 0.01, days)),
        'high': close_prices * (1 + np.random.uniform(0, 0.02, days)),
        'low': close_prices * (1 + np.random.uniform(-0.02, 0, days)),
        'close': close_prices,
        'volume': np.random.randint(100000, 5000000, days)
    }, index=dates)

    return data


def example_basic_backtest():
    """Example 1: Basic backtest with single strategy"""
    print("=" * 70)
    print("📊 Example 1: Basic Backtest")
    print("=" * 70)
    print()

    # Generate data
    print("Generating 2 years of synthetic market data...")
    data = generate_realistic_data(days=730)
    print(f"   Date range: {data.index[0].date()} to {data.index[-1].date()}")
    print(f"   Initial price: ₹{data['close'].iloc[0]:.2f}")
    print(f"   Final price: ₹{data['close'].iloc[-1]:.2f}")
    print()

    # Create strategy
    print("Creating SMA Crossover Strategy (20/50)...")
    strategy = SMAStrategy(fast_period=20, slow_period=50)
    print()

    # Run backtest
    print("Running backtest...")
    config = BacktestConfig(
        initial_capital=1000000,
        transaction_cost_pct=0.001,  # 0.1%
        slippage_pct=0.0005  # 0.05%
    )

    backtester = VectorizedBacktester(config)
    results = backtester.run(strategy, data)

    print(results)
    print()


def example_strategy_comparison():
    """Example 2: Compare multiple strategies"""
    print("=" * 70)
    print("📊 Example 2: Strategy Comparison")
    print("=" * 70)
    print()

    # Generate data
    data = generate_realistic_data(days=730)

    # Create strategies
    strategies = {
        'SMA(20/50)': SMAStrategy(fast_period=20, slow_period=50),
        'RSI(14)': RSIStrategy(rsi_period=14, oversold=30, overbought=70),
        'BB(20,2)': BollingerBandsStrategy(period=20, num_std=2.0)
    }

    # Backtest all strategies
    backtester = VectorizedBacktester()
    results_dict = {}

    print(f"Testing {len(strategies)} strategies on same data...\n")

    for name, strategy in strategies.items():
        print(f"Testing {name}...")
        results = backtester.run(strategy, data)
        results_dict[name] = results

    print()

    # Compare results
    print("=" * 70)
    print("Strategy Performance Comparison")
    print("=" * 70)
    print()

    comparison_df = pd.DataFrame({
        'Total Return %': [r.total_return_pct for r in results_dict.values()],
        'Sharpe Ratio': [r.sharpe_ratio for r in results_dict.values()],
        'Max Drawdown %': [r.max_drawdown_pct for r in results_dict.values()],
        'Win Rate %': [r.win_rate_pct for r in results_dict.values()],
        'Profit Factor': [r.profit_factor for r in results_dict.values()],
        'Total Trades': [r.total_trades for r in results_dict.values()]
    }, index=results_dict.keys())

    print(comparison_df.to_string())
    print()

    # Find best strategy
    best_strategy = comparison_df['Sharpe Ratio'].idxmax()
    print(f"🏆 Best Strategy (by Sharpe Ratio): {best_strategy}")
    print()


def example_parameter_optimization():
    """Example 3: Parameter optimization"""
    print("=" * 70)
    print("📊 Example 3: Parameter Optimization")
    print("=" * 70)
    print()

    # Generate data
    data = generate_realistic_data(days=730)

    # Define parameter grid
    param_grid = {
        'fast_period': [10, 15, 20, 25, 30],
        'slow_period': [40, 50, 60, 70, 80]
    }

    total_combinations = len(param_grid['fast_period']) * len(param_grid['slow_period'])
    print(f"Optimizing SMA Strategy with {total_combinations} parameter combinations...")
    print()

    # Run optimization
    backtester = VectorizedBacktester()

    import time
    start_time = time.time()

    best_params, best_results = backtester.optimize_parameters(
        SMAStrategy,
        data,
        param_grid,
        metric='sharpe_ratio'
    )

    elapsed_time = time.time() - start_time

    print()
    print(f"⚡ Optimization completed in {elapsed_time:.2f}s")
    print(f"   ({total_combinations / elapsed_time:.0f} backtests per second!)")
    print()

    print("=" * 70)
    print("Optimization Results")
    print("=" * 70)
    print()
    print(f"Best Parameters: {best_params}")
    print()
    print(f"Performance:")
    print(f"  Total Return:     {best_results.total_return_pct:>10.2f}%")
    print(f"  Sharpe Ratio:     {best_results.sharpe_ratio:>10.2f}")
    print(f"  Max Drawdown:     {best_results.max_drawdown_pct:>10.2f}%")
    print(f"  Win Rate:         {best_results.win_rate_pct:>10.2f}%")
    print()


def example_walk_forward():
    """Example 4: Walk-forward optimization"""
    print("=" * 70)
    print("📊 Example 4: Walk-Forward Optimization")
    print("=" * 70)
    print()

    print("Walk-forward optimization prevents overfitting by:")
    print("1. Splitting data into multiple time windows")
    print("2. Optimizing parameters on in-sample data (60%)")
    print("3. Testing on out-of-sample data (40%)")
    print("4. Repeating for all windows")
    print()

    # Generate data
    data = generate_realistic_data(days=1095)  # 3 years

    # Define parameter grid (smaller for speed)
    param_grid = {
        'fast_period': [15, 20, 25],
        'slow_period': [40, 50, 60]
    }

    print(f"Running walk-forward optimization with 3 splits...")
    print()

    # Run walk-forward optimization
    backtester = VectorizedBacktester()

    import time
    start_time = time.time()

    wf_results = backtester.walk_forward_optimization(
        SMAStrategy,
        data,
        param_grid,
        in_sample_pct=0.6,
        n_splits=3
    )

    elapsed_time = time.time() - start_time

    print()
    print(f"⚡ Walk-forward optimization completed in {elapsed_time:.2f}s")
    print()

    # Aggregate results
    print("=" * 70)
    print("Walk-Forward Results (Out-of-Sample)")
    print("=" * 70)
    print()

    for i, results in enumerate(wf_results):
        print(f"Split {i+1}:")
        print(f"  Return:        {results.total_return_pct:>8.2f}%")
        print(f"  Sharpe Ratio:  {results.sharpe_ratio:>8.2f}")
        print(f"  Max Drawdown:  {results.max_drawdown_pct:>8.2f}%")
        print()

    # Average metrics
    avg_return = np.mean([r.total_return_pct for r in wf_results])
    avg_sharpe = np.mean([r.sharpe_ratio for r in wf_results])

    print(f"Average Out-of-Sample Performance:")
    print(f"  Return:        {avg_return:>8.2f}%")
    print(f"  Sharpe Ratio:  {avg_sharpe:>8.2f}")
    print()


def main():
    """Run all examples"""
    print("\n" + "=" * 70)
    print("🚀 Comprehensive Backtesting Examples")
    print("=" * 70)
    print()

    # Example 1: Basic backtest
    example_basic_backtest()

    input("Press Enter to continue to Example 2...")
    print("\n")

    # Example 2: Strategy comparison
    example_strategy_comparison()

    input("Press Enter to continue to Example 3...")
    print("\n")

    # Example 3: Parameter optimization
    example_parameter_optimization()

    input("Press Enter to continue to Example 4...")
    print("\n")

    # Example 4: Walk-forward optimization
    example_walk_forward()

    print("=" * 70)
    print("✅ All Examples Completed!")
    print("=" * 70)
    print()
    print("💡 Key Takeaways:")
    print("   - Vectorized backtesting is 100-1000x faster than event-driven")
    print("   - Parameter optimization helps find optimal strategy settings")
    print("   - Walk-forward optimization prevents overfitting")
    print("   - Always test on out-of-sample data before live trading")
    print()


if __name__ == "__main__":
    # Run specific example or all
    import sys

    if len(sys.argv) > 1:
        example_num = int(sys.argv[1])

        examples = [
            example_basic_backtest,
            example_strategy_comparison,
            example_parameter_optimization,
            example_walk_forward
        ]

        if 1 <= example_num <= len(examples):
            print(f"\nRunning Example {example_num}...\n")
            examples[example_num - 1]()
        else:
            print(f"Invalid example number. Choose 1-{len(examples)}")
    else:
        # Run all examples
        main()
