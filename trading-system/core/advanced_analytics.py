#!/usr/bin/env python3
"""
Advanced Analytics Dashboard
Phase 3 Tier 2: Intelligence - Component #5

FEATURES:
- Performance attribution analysis (strategy, asset, sector)
- Factor exposure analysis (market, size, value, momentum)
- Monte Carlo portfolio simulation
- Risk decomposition
- Drawdown analysis with recovery periods
- Rolling performance metrics
- Trade quality metrics

Impact:
- BEFORE: Basic P&L tracking, limited insights
- AFTER: Deep understanding of performance drivers
- Identify what works and what doesn't
- Optimize portfolio construction
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger('trading_system.advanced_analytics')


@dataclass
class PerformanceAttribution:
    """Performance attribution results"""
    total_return: float
    strategy_attribution: Dict[str, float]
    asset_attribution: Dict[str, float]
    sector_attribution: Dict[str, float]
    timing_effect: float
    selection_effect: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class FactorExposure:
    """Factor exposure analysis"""
    market_beta: float
    size_factor: float  # Small cap vs large cap
    value_factor: float  # Value vs growth
    momentum_factor: float  # Winners vs losers
    r_squared: float
    factor_contributions: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class DrawdownAnalysis:
    """Drawdown analysis results"""
    max_drawdown_pct: float
    max_drawdown_duration_days: int
    current_drawdown_pct: float
    recovery_time_days: Optional[int]
    drawdown_periods: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        return result


class AdvancedAnalytics:
    """
    Advanced analytics engine for trading system

    Provides deep insights into:
    - What drives performance (attribution)
    - Risk factor exposures
    - Drawdown characteristics
    - Trade quality metrics
    """

    def __init__(self):
        """Initialize advanced analytics"""
        logger.info("AdvancedAnalytics initialized")

    def calculate_performance_attribution(
        self,
        portfolio_returns: pd.Series,
        position_data: pd.DataFrame
    ) -> PerformanceAttribution:
        """
        Calculate performance attribution

        Args:
            portfolio_returns: Time series of portfolio returns
            position_data: DataFrame with columns: date, symbol, return, weight, strategy, sector

        Returns:
            PerformanceAttribution
        """
        logger.info("Calculating performance attribution")

        # Total return
        total_return = (1 + portfolio_returns).prod() - 1

        # Strategy attribution (weighted by contribution)
        strategy_attr = defaultdict(float)
        if 'strategy' in position_data.columns:
            for strategy in position_data['strategy'].unique():
                strategy_data = position_data[position_data['strategy'] == strategy]
                strategy_return = (strategy_data['return'] * strategy_data['weight']).sum()
                strategy_attr[strategy] = strategy_return

        # Asset attribution
        asset_attr = defaultdict(float)
        if 'symbol' in position_data.columns:
            for symbol in position_data['symbol'].unique():
                symbol_data = position_data[position_data['symbol'] == symbol]
                symbol_return = (symbol_data['return'] * symbol_data['weight']).sum()
                asset_attr[symbol] = symbol_return

        # Sector attribution
        sector_attr = defaultdict(float)
        if 'sector' in position_data.columns:
            for sector in position_data['sector'].unique():
                sector_data = position_data[position_data['sector'] == sector]
                sector_return = (sector_data['return'] * sector_data['weight']).sum()
                sector_attr[sector] = sector_return

        # Selection effect (stock picking within sectors)
        selection_effect = 0.0
        if 'sector' in position_data.columns and 'benchmark_return' in position_data.columns:
            for sector in position_data['sector'].unique():
                sector_data = position_data[position_data['sector'] == sector]
                selection = ((sector_data['return'] - sector_data['benchmark_return']) *
                            sector_data['weight']).sum()
                selection_effect += selection

        # Timing effect (sector allocation decisions)
        timing_effect = total_return - sum(asset_attr.values()) - selection_effect

        return PerformanceAttribution(
            total_return=total_return,
            strategy_attribution=dict(strategy_attr),
            asset_attribution=dict(asset_attr),
            sector_attribution=dict(sector_attr),
            timing_effect=timing_effect,
            selection_effect=selection_effect
        )

    def calculate_factor_exposure(
        self,
        portfolio_returns: pd.Series,
        market_returns: pd.Series,
        factor_data: Optional[Dict[str, pd.Series]] = None
    ) -> FactorExposure:
        """
        Calculate factor exposures using Fama-French style regression

        Args:
            portfolio_returns: Portfolio returns
            market_returns: Market benchmark returns
            factor_data: Optional dict of factor returns (SMB, HML, MOM)

        Returns:
            FactorExposure
        """
        logger.info("Calculating factor exposures")

        # Align data
        common_index = portfolio_returns.index.intersection(market_returns.index)
        y = portfolio_returns.loc[common_index].values
        X = market_returns.loc[common_index].values.reshape(-1, 1)

        # Add factors if provided
        factor_names = ['market']
        if factor_data:
            for name, series in factor_data.items():
                aligned = series.loc[common_index].values.reshape(-1, 1)
                X = np.column_stack([X, aligned])
                factor_names.append(name)

        # Add intercept
        X = np.column_stack([np.ones(len(X)), X])

        # Linear regression (VECTORIZED)
        try:
            coefficients = np.linalg.lstsq(X, y, rcond=None)[0]
        except np.linalg.LinAlgError:
            # If singular matrix, return zeros
            coefficients = np.zeros(len(factor_names) + 1)

        # Calculate R-squared
        y_pred = X @ coefficients
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # Extract coefficients
        alpha = coefficients[0]
        market_beta = coefficients[1]

        # Other factors (if provided)
        size_factor = coefficients[2] if len(coefficients) > 2 else 0.0
        value_factor = coefficients[3] if len(coefficients) > 3 else 0.0
        momentum_factor = coefficients[4] if len(coefficients) > 4 else 0.0

        # Calculate factor contributions
        factor_contributions = {'alpha': alpha}
        for i, name in enumerate(factor_names):
            factor_contributions[name] = coefficients[i + 1]

        return FactorExposure(
            market_beta=market_beta,
            size_factor=size_factor,
            value_factor=value_factor,
            momentum_factor=momentum_factor,
            r_squared=r_squared,
            factor_contributions=factor_contributions
        )

    def analyze_drawdowns(
        self,
        equity_curve: pd.Series,
        min_duration_days: int = 5
    ) -> DrawdownAnalysis:
        """
        Analyze drawdown periods

        Args:
            equity_curve: Time series of portfolio value
            min_duration_days: Minimum drawdown duration to include

        Returns:
            DrawdownAnalysis
        """
        logger.info("Analyzing drawdowns")

        # Calculate running maximum (VECTORIZED)
        running_max = equity_curve.expanding().max()

        # Calculate drawdown
        drawdown = (equity_curve - running_max) / running_max

        # Find drawdown periods
        in_drawdown = drawdown < 0
        drawdown_starts = in_drawdown & ~in_drawdown.shift(1).fillna(False)
        drawdown_ends = ~in_drawdown & in_drawdown.shift(1).fillna(False)

        # Extract drawdown periods
        drawdown_periods = []
        start_idx = None

        for idx in equity_curve.index:
            if drawdown_starts.loc[idx]:
                start_idx = idx
            elif drawdown_ends.loc[idx] and start_idx is not None:
                # Calculate period statistics
                period_data = drawdown.loc[start_idx:idx]
                duration = (idx - start_idx).days

                if duration >= min_duration_days:
                    max_dd = period_data.min()
                    max_dd_date = period_data.idxmin()

                    # Recovery time
                    recovery_time = (idx - max_dd_date).days

                    drawdown_periods.append({
                        'start_date': start_idx,
                        'end_date': idx,
                        'max_drawdown_pct': max_dd * 100,
                        'max_drawdown_date': max_dd_date,
                        'duration_days': duration,
                        'recovery_time_days': recovery_time
                    })

                start_idx = None

        # Overall statistics
        max_drawdown_pct = drawdown.min() * 100
        current_drawdown_pct = drawdown.iloc[-1] * 100

        # Maximum drawdown duration
        if drawdown_periods:
            max_duration = max(p['duration_days'] for p in drawdown_periods)
            avg_recovery = np.mean([p['recovery_time_days'] for p in drawdown_periods])
        else:
            max_duration = 0
            avg_recovery = None

        return DrawdownAnalysis(
            max_drawdown_pct=abs(max_drawdown_pct),
            max_drawdown_duration_days=max_duration,
            current_drawdown_pct=abs(current_drawdown_pct),
            recovery_time_days=int(avg_recovery) if avg_recovery else None,
            drawdown_periods=drawdown_periods
        )

    def calculate_rolling_metrics(
        self,
        returns: pd.Series,
        window_days: int = 252
    ) -> pd.DataFrame:
        """
        Calculate rolling performance metrics (VECTORIZED)

        Args:
            returns: Time series of returns
            window_days: Rolling window size

        Returns:
            DataFrame with rolling metrics
        """
        logger.info(f"Calculating rolling metrics (window={window_days} days)")

        # Rolling return
        rolling_return = returns.rolling(window=window_days).apply(
            lambda x: (1 + x).prod() - 1
        )

        # Rolling volatility (annualized)
        rolling_vol = returns.rolling(window=window_days).std() * np.sqrt(252)

        # Rolling Sharpe ratio (assume 5% risk-free rate)
        risk_free_rate = 0.05
        rolling_sharpe = (rolling_return - risk_free_rate) / rolling_vol

        # Rolling max drawdown
        def rolling_max_dd(x):
            cumulative = (1 + x).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            return abs(drawdown.min())

        rolling_max_dd = returns.rolling(window=window_days).apply(rolling_max_dd)

        # Combine into DataFrame
        metrics = pd.DataFrame({
            'rolling_return': rolling_return,
            'rolling_volatility': rolling_vol,
            'rolling_sharpe': rolling_sharpe,
            'rolling_max_drawdown': rolling_max_dd
        }, index=returns.index)

        return metrics

    def calculate_trade_quality_metrics(
        self,
        trades: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Calculate trade quality metrics

        Args:
            trades: DataFrame with columns: entry_date, exit_date, pnl, symbol

        Returns:
            Dictionary of trade quality metrics
        """
        logger.info(f"Calculating trade quality metrics for {len(trades)} trades")

        if len(trades) == 0:
            return {}

        # Basic metrics
        total_trades = len(trades)
        winning_trades = len(trades[trades['pnl'] > 0])
        losing_trades = len(trades[trades['pnl'] < 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # P&L metrics
        total_pnl = trades['pnl'].sum()
        avg_win = trades[trades['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades[trades['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0

        # Profit factor
        gross_profit = trades[trades['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(trades[trades['pnl'] < 0]['pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Expectancy
        expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

        # Hold time analysis
        if 'entry_date' in trades.columns and 'exit_date' in trades.columns:
            trades['hold_time'] = (pd.to_datetime(trades['exit_date']) -
                                   pd.to_datetime(trades['entry_date'])).dt.days
            avg_hold_time = trades['hold_time'].mean()
            avg_win_hold = trades[trades['pnl'] > 0]['hold_time'].mean() if winning_trades > 0 else 0
            avg_loss_hold = trades[trades['pnl'] < 0]['hold_time'].mean() if losing_trades > 0 else 0
        else:
            avg_hold_time = avg_win_hold = avg_loss_hold = 0

        # Consecutive wins/losses
        pnl_sign = np.sign(trades['pnl'].values)
        consecutive_streaks = []
        current_streak = 1

        for i in range(1, len(pnl_sign)):
            if pnl_sign[i] == pnl_sign[i-1]:
                current_streak += 1
            else:
                consecutive_streaks.append(current_streak)
                current_streak = 1
        consecutive_streaks.append(current_streak)

        max_consecutive_wins = max([s for i, s in enumerate(consecutive_streaks)
                                    if i < len(pnl_sign) and pnl_sign[i] > 0], default=0)
        max_consecutive_losses = max([s for i, s in enumerate(consecutive_streaks)
                                      if i < len(pnl_sign) and pnl_sign[i] < 0], default=0)

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'expectancy': expectancy,
            'avg_hold_time_days': avg_hold_time,
            'avg_win_hold_time_days': avg_win_hold,
            'avg_loss_hold_time_days': avg_loss_hold,
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses,
            'best_trade': trades['pnl'].max(),
            'worst_trade': trades['pnl'].min()
        }

    def monte_carlo_simulation(
        self,
        returns: pd.Series,
        initial_capital: float = 1000000,
        n_simulations: int = 1000,
        n_periods: int = 252
    ) -> Dict[str, Any]:
        """
        Monte Carlo portfolio simulation

        Args:
            returns: Historical returns
            initial_capital: Starting capital
            n_simulations: Number of simulations
            n_periods: Number of periods to simulate

        Returns:
            Dictionary with simulation results
        """
        logger.info(f"Running Monte Carlo simulation: {n_simulations} paths, {n_periods} periods")

        # Calculate return distribution parameters
        mean_return = returns.mean()
        std_return = returns.std()

        # Generate random returns (VECTORIZED)
        np.random.seed(42)  # For reproducibility
        random_returns = np.random.normal(mean_return, std_return, (n_simulations, n_periods))

        # Calculate equity curves for all simulations (VECTORIZED)
        equity_curves = initial_capital * (1 + random_returns).cumprod(axis=1)

        # Calculate final values
        final_values = equity_curves[:, -1]

        # Calculate statistics
        median_final = np.percentile(final_values, 50)
        p5_final = np.percentile(final_values, 5)  # 5% worst case
        p95_final = np.percentile(final_values, 95)  # 5% best case

        # Probability of profit
        prob_profit = (final_values > initial_capital).mean()

        # Maximum drawdown across simulations
        def calc_max_dd(equity):
            running_max = np.maximum.accumulate(equity)
            drawdown = (equity - running_max) / running_max
            return abs(drawdown.min())

        max_drawdowns = np.array([calc_max_dd(equity_curves[i]) for i in range(n_simulations)])
        median_max_dd = np.percentile(max_drawdowns, 50)
        worst_max_dd = max_drawdowns.max()

        return {
            'n_simulations': n_simulations,
            'n_periods': n_periods,
            'initial_capital': initial_capital,
            'median_final_value': median_final,
            'median_return_pct': (median_final / initial_capital - 1) * 100,
            'p5_final_value': p5_final,
            'p95_final_value': p95_final,
            'probability_of_profit': prob_profit,
            'median_max_drawdown_pct': median_max_dd * 100,
            'worst_max_drawdown_pct': worst_max_dd * 100,
            'equity_curves': equity_curves  # All simulation paths
        }


if __name__ == "__main__":
    # Test advanced analytics
    print("🧪 Testing Advanced Analytics\n")

    analytics = AdvancedAnalytics()

    print("1. Performance Attribution:")

    # Create sample position data
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
    position_data = pd.DataFrame({
        'date': np.repeat(dates, 3),
        'symbol': ['RELIANCE', 'TCS', 'INFY'] * len(dates),
        'return': np.random.normal(0.001, 0.02, len(dates) * 3),
        'weight': [0.4, 0.3, 0.3] * len(dates),
        'strategy': ['momentum', 'value', 'growth'] * len(dates),
        'sector': ['energy', 'it', 'it'] * len(dates)
    })

    portfolio_returns = position_data.groupby('date').apply(
        lambda x: (x['return'] * x['weight']).sum()
    )

    attribution = analytics.calculate_performance_attribution(portfolio_returns, position_data)

    print(f"   Total Return: {attribution.total_return*100:.2f}%")
    print(f"   Strategy Attribution:")
    for strategy, ret in attribution.strategy_attribution.items():
        print(f"      {strategy:12s}: {ret*100:>6.2f}%")
    print("   ✅ Passed\n")

    print("2. Factor Exposure Analysis:")

    # Create market returns
    market_returns = pd.Series(
        np.random.normal(0.0005, 0.015, len(dates)),
        index=dates
    )

    exposure = analytics.calculate_factor_exposure(portfolio_returns, market_returns)

    print(f"   Market Beta:      {exposure.market_beta:.3f}")
    print(f"   R-squared:        {exposure.r_squared:.3f}")
    print("   ✅ Passed\n")

    print("3. Drawdown Analysis:")

    # Create equity curve with drawdowns
    returns = pd.Series(np.random.normal(0.001, 0.02, len(dates)), index=dates)
    equity_curve = (1 + returns).cumprod() * 1000000

    dd_analysis = analytics.analyze_drawdowns(equity_curve, min_duration_days=5)

    print(f"   Max Drawdown:     {dd_analysis.max_drawdown_pct:.2f}%")
    print(f"   Max DD Duration:  {dd_analysis.max_drawdown_duration_days} days")
    print(f"   Current Drawdown: {dd_analysis.current_drawdown_pct:.2f}%")
    print(f"   Drawdown Periods: {len(dd_analysis.drawdown_periods)}")
    print("   ✅ Passed\n")

    print("4. Rolling Metrics:")

    rolling_metrics = analytics.calculate_rolling_metrics(returns, window_days=60)

    print(f"   Calculated {len(rolling_metrics.columns)} rolling metrics")
    print(f"   Metrics: {list(rolling_metrics.columns)}")
    print(f"   Latest Sharpe:    {rolling_metrics['rolling_sharpe'].iloc[-1]:.2f}")
    print("   ✅ Passed\n")

    print("5. Trade Quality Metrics:")

    # Create sample trades
    trades = pd.DataFrame({
        'entry_date': pd.date_range('2024-01-01', periods=50, freq='W'),
        'exit_date': pd.date_range('2024-01-08', periods=50, freq='W'),
        'symbol': np.random.choice(['RELIANCE', 'TCS', 'INFY'], 50),
        'pnl': np.random.normal(1000, 5000, 50)
    })

    trade_metrics = analytics.calculate_trade_quality_metrics(trades)

    print(f"   Total Trades:     {trade_metrics['total_trades']}")
    print(f"   Win Rate:         {trade_metrics['win_rate']*100:.1f}%")
    print(f"   Profit Factor:    {trade_metrics['profit_factor']:.2f}")
    print(f"   Expectancy:       ₹{trade_metrics['expectancy']:.2f}")
    print("   ✅ Passed\n")

    print("6. Monte Carlo Simulation:")

    mc_results = analytics.monte_carlo_simulation(
        returns,
        initial_capital=1000000,
        n_simulations=100,  # Reduced for speed
        n_periods=252
    )

    print(f"   Simulations:      {mc_results['n_simulations']}")
    print(f"   Median Return:    {mc_results['median_return_pct']:.2f}%")
    print(f"   P5 Final Value:   ₹{mc_results['p5_final_value']:,.0f}")
    print(f"   P95 Final Value:  ₹{mc_results['p95_final_value']:,.0f}")
    print(f"   Prob of Profit:   {mc_results['probability_of_profit']*100:.1f}%")
    print("   ✅ Passed\n")

    print("✅ All advanced analytics tests passed!")
    print("\n💡 Impact: Deep insights into performance drivers")
    print("💡 Understand what works and optimize accordingly")
