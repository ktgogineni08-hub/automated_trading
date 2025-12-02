#!/usr/bin/env python3
"""
Backtest Engine
Encapsulates backtesting logic, separating it from the main trading system.
"""

import logging
import pandas as pd
from typing import List, Dict, Optional

from core.vectorized_backtester import VectorizedBacktester, BacktestConfig
from strategies.vectorized_strategies import (
    VectorizedMACrossover,
    VectorizedRSI,
    VectorizedBollingerBands,
    VectorizedMomentum,
    VectorizedVolumeBreakout,
    CombinedVectorizedStrategy
)
from data.provider import DataProvider
from utilities.structured_logger import get_logger

logger = get_logger(__name__)

class BacktestEngine:
    """
    Handles execution of backtests using the vectorized backtester.
    """

    def __init__(self, data_provider: DataProvider, initial_capital: float = 1000000.0):
        self.dp = data_provider
        self.initial_capital = initial_capital

    def run_fast_backtest(self, symbols: List[str], interval: str = "5minute", days: int = 30) -> None:
        """
        Run high-performance vectorized backtest
        """
        interval = self._normalize_fast_interval(interval)
        logger.info(f"⚡ Running VECTORIZED backtest (100x faster) for {days} days...")
        
        # 1. Fetch Data
        df_map = {}
        for sym in symbols:
            try:
                df = self.dp.fetch_with_retry(sym, interval=interval, days=days)
                if not df.empty:
                    # Ensure index is timezone-naive for backtester
                    if df.index.tz is not None:
                        df.index = df.index.tz_localize(None)
                    df_map[sym] = df
            except Exception as e:
                logger.error(f"Error fetching {sym}: {e}")
        
        if not df_map:
            logger.error("❌ No data for backtest")
            return

        # 2. Configure Backtester
        config = BacktestConfig(
            initial_capital=self.initial_capital,
            transaction_cost_pct=0.001, # 0.1%
            slippage_pct=0.0005 # 0.05%
        )
        backtester = VectorizedBacktester(config)

        # 3. Configure Strategy
        # Use a combination of all vectorized strategies
        strategy = CombinedVectorizedStrategy([
            VectorizedMACrossover(fast_period=5, slow_period=15),
            VectorizedRSI(period=14, buy_threshold=30, sell_threshold=70),
            VectorizedBollingerBands(period=20, std_dev=2),
            VectorizedMomentum(momentum_period=10),
            VectorizedVolumeBreakout(volume_multiplier=1.5)
        ])

        # 4. Run Backtest for each symbol and aggregate
        total_pnl = 0
        total_trades = 0
        winning_trades = 0
        
        print("\n" + "="*60)
        print(f"VECTORIZED BACKTEST RESULTS ({days} days, {interval})")
        print("="*60)
        print(f"{'SYMBOL':<15} {'RETURN':<10} {'TRADES':<8} {'WIN RATE':<10} {'SHARPE':<8}")
        print("-" * 60)

        for sym, df in df_map.items():
            try:
                results = backtester.run(strategy, df)
                
                initial_cap = self.initial_capital
                pnl = results.final_capital - initial_cap
                total_pnl += pnl
                total_trades += results.total_trades
                winning_trades += results.winning_trades
                
                print(f"{sym:<15} {results.total_return_pct:>9.2f}% {results.total_trades:>8} {results.win_rate_pct:>9.1f}% {results.sharpe_ratio:>8.2f}")
                
            except Exception as e:
                logger.error(f"Backtest failed for {sym}: {e}")

        print("-" * 60)
        print(f"TOTAL P&L:      ₹{total_pnl:,.2f}")
        print(f"TOTAL TRADES:   {total_trades}")
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        print(f"AVG WIN RATE:   {win_rate:.1f}%")
        print("=" * 60 + "\n")

    @staticmethod
    def _normalize_fast_interval(interval: str) -> str:
        if not interval:
            return '5minute'
        interval = interval.lower().strip()
        mapping = {
            '5': '5minute', '5m': '5minute', '5min': '5minute', '5minute': '5minute',
            '10': '10minute', '10m': '10minute', '10min': '10minute', '10minute': '10minute',
            '15': '15minute', '15m': '15minute', '15min': '15minute', '15minute': '15minute',
            '30': '30minute', '30m': '30minute', '30min': '30minute', '30minute': '30minute',
            '60': '60minute', '60m': '60minute', '60min': '60minute', '1h': '60minute', '1hour': '60minute', '60minute': '60minute'
        }
        return mapping.get(interval, '5minute')
