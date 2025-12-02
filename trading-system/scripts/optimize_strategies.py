#!/usr/bin/env python3
"""
Strategy Parameter Optimization Script
Uses VectorizedBacktester to find optimal parameters for trading strategies.
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.vectorized_backtester import VectorizedBacktester, BacktestConfig
from strategies.vectorized_strategies import (
    VectorizedMACrossover,
    VectorizedRSI,
    VectorizedBollingerBands,
    VectorizedMomentum,
    VectorizedVolumeBreakout
)
from data.provider import DataProvider
from unified_config import get_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('optimization')

def run_optimization():
    """Run parameter optimization for all strategies"""
    
    # 1. Initialize components
    config = get_config()
    data_provider = DataProvider(config)
    
    backtest_config = BacktestConfig(
        initial_capital=100000.0,
        transaction_cost_pct=0.001,
        slippage_pct=0.0005
    )
    backtester = VectorizedBacktester(backtest_config)
    
    # 2. Fetch Data
    symbol = 'NIFTY 50' # optimize on index or a major stock
    logger.info(f"Fetching data for {symbol}...")
    
    # Try to fetch 1 year of data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    # Note: In a real scenario, we might iterate over multiple symbols
    # For now, we'll use a synthetic fallback if live data isn't available or just mock it for the script
    # But let's try to use the provider.
    
    try:
        # We need OHLCV data. 
        # If DataProvider fails (e.g. no API key), we'll generate synthetic data for testing
        data = data_provider.fetch_historical_data(symbol, "5minute", start_date, end_date)
        if data is None or len(data) < 100:
            raise ValueError("Insufficient data fetched")
            
    except Exception as e:
        logger.warning(f"Could not fetch live data: {e}. Using synthetic data.")
        dates = pd.date_range(start_date, end_date, freq='5min')
        np.random.seed(42)
        trend = np.linspace(10000, 12000, len(dates))
        noise = np.random.normal(0, 50, len(dates))
        close = trend + noise.cumsum()
        data = pd.DataFrame({
            'open': close * 0.999,
            'high': close * 1.001,
            'low': close * 0.998,
            'close': close,
            'volume': np.random.randint(1000, 10000, len(dates))
        }, index=dates)

    logger.info(f"Data loaded: {len(data)} bars")

    # 3. Define Optimization Tasks
    tasks = [
        {
            'name': 'MA Crossover',
            'strategy': VectorizedMACrossover,
            'params': {
                'fast_period': [5, 10, 20],
                'slow_period': [20, 50, 100]
            }
        },
        {
            'name': 'RSI',
            'strategy': VectorizedRSI,
            'params': {
                'period': [14, 21],
                'buy_threshold': [20, 30, 40],
                'sell_threshold': [60, 70, 80]
            }
        },
        {
            'name': 'Bollinger Bands',
            'strategy': VectorizedBollingerBands,
            'params': {
                'period': [20, 30],
                'std_dev': [2.0, 2.5, 3.0]
            }
        },
        {
            'name': 'Momentum',
            'strategy': VectorizedMomentum,
            'params': {
                'momentum_period': [10, 14, 20],
                'rsi_period': [14, 21]
            }
        },
        {
            'name': 'Volume Breakout',
            'strategy': VectorizedVolumeBreakout,
            'params': {
                'volume_multiplier': [1.5, 2.0, 3.0],
                'price_threshold': [0.001, 0.002, 0.005]
            }
        }
    ]

    # 4. Run Optimization
    print("\n" + "="*60)
    print("STRATEGY OPTIMIZATION RESULTS")
    print("="*60)

    for task in tasks:
        logger.info(f"Optimizing {task['name']}...")
        
        best_params, best_results = backtester.optimize_parameters(
            task['strategy'],
            data,
            task['params'],
            metric='sharpe_ratio'
        )
        
        print(f"\nStrategy: {task['name']}")
        print("-" * 30)
        print(f"Best Parameters: {best_params}")
        print(f"Sharpe Ratio:    {best_results.sharpe_ratio:.2f}")
        print(f"Total Return:    {best_results.total_return_pct:.2f}%")
        print(f"Win Rate:        {best_results.win_rate_pct:.2f}%")
        print(f"Max Drawdown:    {best_results.max_drawdown_pct:.2f}%")
        print(f"Trades:          {best_results.total_trades}")

    print("\n" + "="*60)

if __name__ == "__main__":
    run_optimization()
