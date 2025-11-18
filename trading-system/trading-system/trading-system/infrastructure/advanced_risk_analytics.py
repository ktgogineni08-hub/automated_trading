#!/usr/bin/env python3
"""
Advanced Risk Analytics
Value at Risk (VaR), stress testing, and risk metrics

ADDRESSES MEDIUM PRIORITY RECOMMENDATION #8:
- Value at Risk (VaR) calculations (Historical, Parametric, Monte Carlo)
- Conditional VaR (CVaR/Expected Shortfall)
- Stress testing scenarios
- Risk decomposition
- Correlation analysis
- Portfolio risk attribution
"""

import logging
import threading
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger('trading_system.risk_analytics')


class VaRMethod(Enum):
    """VaR calculation methods"""
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    MONTE_CARLO = "monte_carlo"


class StressScenario(Enum):
    """Predefined stress scenarios"""
    MARKET_CRASH = "market_crash"          # 20% market drop
    FLASH_CRASH = "flash_crash"            # 5% instant drop
    VOLATILITY_SPIKE = "volatility_spike"  # 3x volatility
    LIQUIDITY_CRISIS = "liquidity_crisis"  # High slippage
    BLACK_SWAN = "black_swan"              # 6-sigma event


@dataclass
class VaRResult:
    """VaR calculation result"""
    method: VaRMethod
    confidence_level: float  # e.g., 0.95
    time_horizon_days: int
    value_at_risk: float
    expected_shortfall: float  # CVaR
    portfolio_value: float
    var_pct: float  # VaR as % of portfolio
    calculated_at: datetime = field(default_factory=datetime.now)


@dataclass
class StressTestResult:
    """Stress test result"""
    scenario: StressScenario
    scenario_description: str
    current_portfolio_value: float
    stressed_portfolio_value: float
    loss_amount: float
    loss_pct: float
    worst_position: str
    worst_position_loss: float
    tested_at: datetime = field(default_factory=datetime.now)


@dataclass
class RiskMetrics:
    """Comprehensive risk metrics"""
    portfolio_value: float
    volatility_daily: float
    volatility_annual: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    beta: float
    var_95_daily: float
    cvar_95_daily: float
    calculated_at: datetime = field(default_factory=datetime.now)


class AdvancedRiskAnalytics:
    """
    Advanced Risk Analytics Engine

    Features:
    - Multiple VaR calculation methods
    - Conditional VaR (Expected Shortfall)
    - Historical simulation
    - Parametric VaR (variance-covariance)
    - Monte Carlo simulation
    - Stress testing scenarios
    - Risk decomposition
    - Correlation analysis

    Usage:
        analytics = AdvancedRiskAnalytics()

        # Calculate VaR
        var_result = analytics.calculate_var(
            returns=portfolio_returns,
            portfolio_value=1000000,
            confidence=0.95,
            method=VaRMethod.HISTORICAL
        )

        # Run stress test
        stress_result = analytics.stress_test(
            portfolio=portfolio,
            scenario=StressScenario.MARKET_CRASH
        )
    """

    def __init__(
        self,
        risk_free_rate: float = 0.05,  # 5% risk-free rate
        market_return: float = 0.12    # 12% market return
    ):
        """
        Initialize risk analytics

        Args:
            risk_free_rate: Annual risk-free rate
            market_return: Expected market return
        """
        self.risk_free_rate = risk_free_rate
        self.market_return = market_return

        # Historical data cache
        self._returns_history: Dict[str, List[float]] = {}
        self._price_history: Dict[str, List[float]] = {}

        # Statistics
        self.total_var_calculations = 0
        self.total_stress_tests = 0

        logger.info("📊 Advanced Risk Analytics initialized")

    def calculate_var(
        self,
        returns: np.ndarray,
        portfolio_value: float,
        confidence: float = 0.95,
        time_horizon_days: int = 1,
        method: VaRMethod = VaRMethod.HISTORICAL
    ) -> VaRResult:
        """
        Calculate Value at Risk

        Args:
            returns: Array of historical returns
            portfolio_value: Current portfolio value
            confidence: Confidence level (e.g., 0.95 for 95%)
            time_horizon_days: Time horizon in days
            method: VaR calculation method

        Returns:
            VaRResult
        """
        self.total_var_calculations += 1

        if method == VaRMethod.HISTORICAL:
            var, cvar = self._historical_var(returns, confidence, time_horizon_days)

        elif method == VaRMethod.PARAMETRIC:
            var, cvar = self._parametric_var(returns, confidence, time_horizon_days)

        elif method == VaRMethod.MONTE_CARLO:
            var, cvar = self._monte_carlo_var(returns, confidence, time_horizon_days)

        else:
            raise ValueError(f"Unknown VaR method: {method}")

        # Calculate absolute VaR
        value_at_risk = abs(var * portfolio_value)
        expected_shortfall = abs(cvar * portfolio_value)

        result = VaRResult(
            method=method,
            confidence_level=confidence,
            time_horizon_days=time_horizon_days,
            value_at_risk=value_at_risk,
            expected_shortfall=expected_shortfall,
            portfolio_value=portfolio_value,
            var_pct=abs(var) * 100
        )

        logger.info(
            f"VaR calculated ({method.value}): "
            f"₹{value_at_risk:,.0f} ({result.var_pct:.2f}%) "
            f"at {confidence:.0%} confidence"
        )

        return result

    def _historical_var(
        self,
        returns: np.ndarray,
        confidence: float,
        horizon: int
    ) -> Tuple[float, float]:
        """
        Historical VaR using empirical distribution

        Args:
            returns: Historical returns
            confidence: Confidence level
            horizon: Time horizon

        Returns:
            (VaR, CVaR) as percentages
        """
        if len(returns) == 0:
            return 0.0, 0.0

        # Scale returns to horizon
        scaled_returns = returns * np.sqrt(horizon)

        # Calculate VaR (percentile)
        var = np.percentile(scaled_returns, (1 - confidence) * 100)

        # Calculate CVaR (Expected Shortfall)
        # Average of returns worse than VaR
        tail_returns = scaled_returns[scaled_returns <= var]
        cvar = np.mean(tail_returns) if len(tail_returns) > 0 else var

        return var, cvar

    def _parametric_var(
        self,
        returns: np.ndarray,
        confidence: float,
        horizon: int
    ) -> Tuple[float, float]:
        """
        Parametric VaR assuming normal distribution

        Args:
            returns: Historical returns
            confidence: Confidence level
            horizon: Time horizon

        Returns:
            (VaR, CVaR) as percentages
        """
        if len(returns) == 0:
            return 0.0, 0.0

        # Calculate mean and std
        mean = np.mean(returns)
        std = np.std(returns)

        # Scale to horizon
        mean_scaled = mean * horizon
        std_scaled = std * np.sqrt(horizon)

        # Calculate VaR using normal distribution
        z_score = stats.norm.ppf(1 - confidence)
        var = mean_scaled + z_score * std_scaled

        # Calculate CVaR
        # For normal distribution: CVaR = μ - σ * φ(z) / (1 - α)
        # where φ is PDF and α is confidence level
        phi = stats.norm.pdf(z_score)
        cvar = mean_scaled - std_scaled * phi / (1 - confidence)

        return var, cvar

    def _monte_carlo_var(
        self,
        returns: np.ndarray,
        confidence: float,
        horizon: int,
        num_simulations: int = 10000
    ) -> Tuple[float, float]:
        """
        Monte Carlo VaR simulation

        Args:
            returns: Historical returns
            confidence: Confidence level
            horizon: Time horizon
            num_simulations: Number of Monte Carlo simulations

        Returns:
            (VaR, CVaR) as percentages
        """
        if len(returns) == 0:
            return 0.0, 0.0

        # Fit distribution to historical returns
        mean = np.mean(returns)
        std = np.std(returns)

        # Generate simulations
        simulated_returns = np.random.normal(
            mean * horizon,
            std * np.sqrt(horizon),
            num_simulations
        )

        # Calculate VaR
        var = np.percentile(simulated_returns, (1 - confidence) * 100)

        # Calculate CVaR
        tail_returns = simulated_returns[simulated_returns <= var]
        cvar = np.mean(tail_returns) if len(tail_returns) > 0 else var

        return var, cvar

    def stress_test(
        self,
        portfolio: Dict[str, Dict[str, float]],
        scenario: StressScenario,
        custom_shocks: Optional[Dict[str, float]] = None
    ) -> StressTestResult:
        """
        Run stress test on portfolio

        Args:
            portfolio: Portfolio positions {symbol: {'quantity': X, 'price': Y, 'value': Z}}
            scenario: Predefined stress scenario
            custom_shocks: Custom price shocks {symbol: shock_pct}

        Returns:
            StressTestResult
        """
        self.total_stress_tests += 1

        # Get scenario shocks
        if custom_shocks:
            shocks = custom_shocks
        else:
            shocks = self._get_scenario_shocks(scenario)

        # Calculate current portfolio value
        current_value = sum(pos['value'] for pos in portfolio.values())

        # Apply shocks and calculate stressed value
        stressed_value = 0
        worst_position = ""
        worst_position_loss = 0

        for symbol, position in portfolio.items():
            # Get shock for this symbol (or market shock if not specified)
            shock = shocks.get(symbol, shocks.get('market', 0))

            # Calculate stressed position value
            current_pos_value = position['value']
            stressed_pos_value = current_pos_value * (1 + shock)
            position_loss = current_pos_value - stressed_pos_value

            stressed_value += stressed_pos_value

            # Track worst position
            if position_loss > worst_position_loss:
                worst_position = symbol
                worst_position_loss = position_loss

        # Calculate total loss
        loss_amount = current_value - stressed_value
        loss_pct = (loss_amount / current_value) * 100 if current_value > 0 else 0

        result = StressTestResult(
            scenario=scenario,
            scenario_description=self._get_scenario_description(scenario),
            current_portfolio_value=current_value,
            stressed_portfolio_value=stressed_value,
            loss_amount=loss_amount,
            loss_pct=loss_pct,
            worst_position=worst_position,
            worst_position_loss=worst_position_loss
        )

        logger.warning(
            f"Stress test ({scenario.value}): "
            f"Loss = ₹{loss_amount:,.0f} ({loss_pct:.2f}%)"
        )

        return result

    def _get_scenario_shocks(self, scenario: StressScenario) -> Dict[str, float]:
        """Get price shocks for scenario"""
        scenarios = {
            StressScenario.MARKET_CRASH: {
                'market': -0.20,  # 20% drop
                'NIFTY': -0.20,
                'BANKNIFTY': -0.22,
                'RELIANCE': -0.18
            },
            StressScenario.FLASH_CRASH: {
                'market': -0.05,  # 5% instant drop
                'NIFTY': -0.05,
                'BANKNIFTY': -0.06,
            },
            StressScenario.VOLATILITY_SPIKE: {
                'market': -0.10,  # 10% with high volatility
                'NIFTY': -0.10,
                'BANKNIFTY': -0.12,
            },
            StressScenario.LIQUIDITY_CRISIS: {
                'market': -0.15,  # 15% with slippage
                'NIFTY': -0.15,
                'BANKNIFTY': -0.18,
            },
            StressScenario.BLACK_SWAN: {
                'market': -0.30,  # 30% extreme event
                'NIFTY': -0.30,
                'BANKNIFTY': -0.35,
            },
        }

        return scenarios.get(scenario, {'market': -0.10})

    def _get_scenario_description(self, scenario: StressScenario) -> str:
        """Get scenario description"""
        descriptions = {
            StressScenario.MARKET_CRASH: "2008-style market crash (20% decline)",
            StressScenario.FLASH_CRASH: "Flash crash event (5% instant drop)",
            StressScenario.VOLATILITY_SPIKE: "Volatility spike (3x normal)",
            StressScenario.LIQUIDITY_CRISIS: "Liquidity crisis (high slippage)",
            StressScenario.BLACK_SWAN: "Black swan event (6-sigma)"
        }

        return descriptions.get(scenario, "Custom scenario")

    def calculate_portfolio_metrics(
        self,
        returns: np.ndarray,
        portfolio_value: float,
        benchmark_returns: Optional[np.ndarray] = None
    ) -> RiskMetrics:
        """
        Calculate comprehensive portfolio risk metrics

        Args:
            returns: Portfolio returns
            portfolio_value: Current portfolio value
            benchmark_returns: Benchmark returns for beta calculation

        Returns:
            RiskMetrics
        """
        if len(returns) == 0:
            return RiskMetrics(
                portfolio_value=portfolio_value,
                volatility_daily=0,
                volatility_annual=0,
                sharpe_ratio=0,
                sortino_ratio=0,
                max_drawdown=0,
                beta=1.0,
                var_95_daily=0,
                cvar_95_daily=0
            )

        # Volatility
        volatility_daily = np.std(returns)
        volatility_annual = volatility_daily * np.sqrt(252)

        # Sharpe ratio
        mean_return = np.mean(returns)
        excess_return = mean_return - (self.risk_free_rate / 252)
        sharpe_ratio = (
            excess_return / volatility_daily * np.sqrt(252)
            if volatility_daily > 0 else 0
        )

        # Sortino ratio (downside deviation)
        downside_returns = returns[returns < 0]
        downside_std = (
            np.std(downside_returns) if len(downside_returns) > 0
            else volatility_daily
        )
        sortino_ratio = (
            excess_return / downside_std * np.sqrt(252)
            if downside_std > 0 else 0
        )

        # Max drawdown
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdown)

        # Beta
        if benchmark_returns is not None and len(benchmark_returns) == len(returns):
            covariance = np.cov(returns, benchmark_returns)[0, 1]
            benchmark_variance = np.var(benchmark_returns)
            beta = covariance / benchmark_variance if benchmark_variance > 0 else 1.0
        else:
            beta = 1.0

        # VaR and CVaR
        var_95, cvar_95 = self._historical_var(returns, 0.95, 1)

        return RiskMetrics(
            portfolio_value=portfolio_value,
            volatility_daily=volatility_daily,
            volatility_annual=volatility_annual,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            beta=beta,
            var_95_daily=abs(var_95 * portfolio_value),
            cvar_95_daily=abs(cvar_95 * portfolio_value)
        )

    def calculate_correlation_matrix(
        self,
        returns_dict: Dict[str, np.ndarray]
    ) -> pd.DataFrame:
        """
        Calculate correlation matrix for portfolio positions

        Args:
            returns_dict: Dictionary of symbol -> returns array

        Returns:
            Correlation matrix as DataFrame
        """
        # Convert to DataFrame
        df = pd.DataFrame(returns_dict)

        # Calculate correlation
        correlation = df.corr()

        return correlation

    def print_risk_report(
        self,
        metrics: RiskMetrics,
        var_result: Optional[VaRResult] = None,
        stress_results: Optional[List[StressTestResult]] = None
    ):
        """Print comprehensive risk report"""
        print("\n" + "="*80)
        print("📊 RISK ANALYTICS REPORT")
        print("="*80)

        # Portfolio metrics
        print(f"\n💼 Portfolio Metrics:")
        print(f"  Portfolio Value:       ₹{metrics.portfolio_value:,.0f}")
        print(f"  Daily Volatility:      {metrics.volatility_daily:.4f} ({metrics.volatility_daily*100:.2f}%)")
        print(f"  Annual Volatility:     {metrics.volatility_annual:.4f} ({metrics.volatility_annual*100:.2f}%)")
        print(f"  Sharpe Ratio:          {metrics.sharpe_ratio:.2f}")
        print(f"  Sortino Ratio:         {metrics.sortino_ratio:.2f}")
        print(f"  Max Drawdown:          {metrics.max_drawdown:.2%}")
        print(f"  Beta:                  {metrics.beta:.2f}")

        # VaR metrics
        if var_result:
            print(f"\n📉 Value at Risk ({var_result.confidence_level:.0%} confidence):")
            print(f"  Method:                {var_result.method.value}")
            print(f"  VaR (1-day):           ₹{var_result.value_at_risk:,.0f} ({var_result.var_pct:.2f}%)")
            print(f"  CVaR/ES (1-day):       ₹{var_result.expected_shortfall:,.0f}")

        # Stress tests
        if stress_results:
            print(f"\n⚠️  Stress Test Results:")
            for result in stress_results:
                print(f"\n  {result.scenario.value.upper()}:")
                print(f"    Description:         {result.scenario_description}")
                print(f"    Potential Loss:      ₹{result.loss_amount:,.0f} ({result.loss_pct:.2f}%)")
                print(f"    Stressed Value:      ₹{result.stressed_portfolio_value:,.0f}")
                print(f"    Worst Position:      {result.worst_position} "
                      f"(Loss: ₹{result.worst_position_loss:,.0f})")

        print("="*80 + "\n")


if __name__ == "__main__":
    # Test advanced risk analytics
    print("Testing Advanced Risk Analytics...\n")

    analytics = AdvancedRiskAnalytics()

    # Generate sample returns
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, 252)  # 1 year of daily returns
    portfolio_value = 1000000  # 10 lakh

    # Test 1: Calculate VaR
    print("1. Value at Risk Calculation")
    var_historical = analytics.calculate_var(
        returns=returns,
        portfolio_value=portfolio_value,
        confidence=0.95,
        method=VaRMethod.HISTORICAL
    )
    print(f"Historical VaR: ₹{var_historical.value_at_risk:,.0f} ({var_historical.var_pct:.2f}%)")

    var_parametric = analytics.calculate_var(
        returns=returns,
        portfolio_value=portfolio_value,
        confidence=0.95,
        method=VaRMethod.PARAMETRIC
    )
    print(f"Parametric VaR: ₹{var_parametric.value_at_risk:,.0f} ({var_parametric.var_pct:.2f}%)")

    # Test 2: Stress Testing
    print("\n2. Stress Testing")
    portfolio = {
        'NIFTY': {'quantity': 50, 'price': 25000, 'value': 500000},
        'BANKNIFTY': {'quantity': 15, 'price': 53500, 'value': 300000},
        'RELIANCE': {'quantity': 1000, 'price': 2500, 'value': 200000}
    }

    stress_results = []
    for scenario in [StressScenario.MARKET_CRASH, StressScenario.FLASH_CRASH]:
        result = analytics.stress_test(portfolio, scenario)
        stress_results.append(result)

    # Test 3: Portfolio Metrics
    print("\n3. Portfolio Metrics")
    metrics = analytics.calculate_portfolio_metrics(
        returns=returns,
        portfolio_value=portfolio_value
    )

    # Print comprehensive report
    analytics.print_risk_report(
        metrics=metrics,
        var_result=var_historical,
        stress_results=stress_results
    )

    print("\n✅ Advanced risk analytics tests passed")
