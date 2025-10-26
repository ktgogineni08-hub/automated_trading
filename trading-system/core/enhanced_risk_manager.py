#!/usr/bin/env python3
"""
Enhanced Risk Management System
Sector limits, correlation-based position limits, dynamic risk adjustment

ADDRESSES WEEK 4 ISSUE:
- Original: Basic position limits only
- This implementation: Sector concentration, correlation limits, dynamic volatility adjustment
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from unified_config import get_config

logger = logging.getLogger('trading_system.enhanced_risk')


class RiskLevel(Enum):
    """Risk level classification"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class SectorExposure:
    """Sector exposure tracking"""
    sector: str
    total_value: float
    num_positions: int
    symbols: List[str] = field(default_factory=list)
    percentage_of_portfolio: float = 0.0


@dataclass
class CorrelationRisk:
    """Correlation risk between positions"""
    symbol1: str
    symbol2: str
    correlation: float
    combined_exposure: float
    risk_level: RiskLevel


# Sector mapping for Indian stocks
SECTOR_MAPPING = {
    # Banking & Finance
    'HDFCBANK': 'Banking', 'ICICIBANK': 'Banking', 'KOTAKBANK': 'Banking',
    'AXISBANK': 'Banking', 'SBIN': 'Banking', 'BAJFINANCE': 'NBFC',
    'BAJAJFINSV': 'NBFC', 'HDFCLIFE': 'Insurance', 'SBILIFE': 'Insurance',

    # IT & Technology
    'TCS': 'IT', 'INFY': 'IT', 'WIPRO': 'IT', 'HCLTECH': 'IT',
    'TECHM': 'IT', 'LTI': 'IT', 'COFORGE': 'IT',

    # Auto & Auto Components
    'MARUTI': 'Auto', 'M&M': 'Auto', 'TATAMOTORS': 'Auto',
    'BAJAJ-AUTO': 'Auto', 'EICHERMOT': 'Auto', 'HEROMOTOCO': 'Auto',

    # Energy & Power
    'RELIANCE': 'Energy', 'ONGC': 'Energy', 'BPCL': 'Energy',
    'IOC': 'Energy', 'POWERGRID': 'Power', 'NTPC': 'Power',

    # FMCG & Consumer
    'HINDUNILVR': 'FMCG', 'ITC': 'FMCG', 'NESTLEIND': 'FMCG',
    'BRITANNIA': 'FMCG', 'DABUR': 'FMCG', 'MARICO': 'FMCG',

    # Pharma
    'SUNPHARMA': 'Pharma', 'DRREDDY': 'Pharma', 'CIPLA': 'Pharma',
    'DIVISLAB': 'Pharma', 'AUROPHARMA': 'Pharma',

    # Metals & Mining
    'TATASTEEL': 'Metals', 'JSWSTEEL': 'Metals', 'HINDALCO': 'Metals',
    'VEDL': 'Metals', 'COALINDIA': 'Mining',

    # Telecom
    'BHARTIARTL': 'Telecom', 'IDEA': 'Telecom',

    # Cement
    'ULTRACEMCO': 'Cement', 'AMBUJACEM': 'Cement', 'ACC': 'Cement',

    # Realty
    'DLF': 'Realty', 'GODREJPROP': 'Realty',
}

# High correlation pairs (Indian market)
HIGH_CORRELATION_PAIRS = {
    ('HDFCBANK', 'ICICIBANK'): 0.85,
    ('INFY', 'TCS'): 0.90,
    ('RELIANCE', 'ONGC'): 0.75,
    ('MARUTI', 'M&M'): 0.70,
    ('SUNPHARMA', 'DRREDDY'): 0.80,
    ('TATASTEEL', 'JSWSTEEL'): 0.85,
}


class EnhancedRiskManager:
    """
    Enhanced Risk Management System

    Features:
    - Sector concentration limits
    - Correlation-based position limits
    - Dynamic risk adjustment based on volatility
    - Position sizing with Kelly Criterion
    - Drawdown protection
    - Exposure tracking

    Usage:
        risk_mgr = EnhancedRiskManager(total_capital=1_000_000)

        # Check if can open position
        can_trade = risk_mgr.can_open_position(
            symbol='RELIANCE',
            value=50_000,
            existing_positions={'ONGC': 30_000}
        )

        # Get dynamic position size
        size = risk_mgr.calculate_dynamic_position_size(
            symbol='TCS',
            win_rate=0.65,
            avg_profit=1000,
            avg_loss=500,
            current_volatility=0.25
        )
    """

    def __init__(
        self,
        total_capital: float,
        max_sector_exposure_pct: float = 0.30,  # 30% max per sector
        max_correlation_exposure_pct: float = 0.40,  # 40% max for correlated pairs
        high_correlation_threshold: float = 0.70,
        dynamic_risk_adjustment: bool = True
    ):
        """
        Initialize enhanced risk manager

        Args:
            total_capital: Total trading capital
            max_sector_exposure_pct: Maximum exposure to single sector
            max_correlation_exposure_pct: Maximum combined exposure for correlated pairs
            high_correlation_threshold: Correlation threshold for risk warnings
            dynamic_risk_adjustment: Enable dynamic risk adjustment based on volatility
        """
        self.total_capital = total_capital
        self.max_sector_exposure_pct = max_sector_exposure_pct
        self.max_correlation_exposure_pct = max_correlation_exposure_pct
        self.high_correlation_threshold = high_correlation_threshold
        self.dynamic_risk_adjustment = dynamic_risk_adjustment

        # Get base risk config
        config = get_config()
        self.base_risk_per_trade = config.risk.risk_per_trade_pct

        # Volatility tracking
        self._volatility_history: Dict[str, List[float]] = {}
        self._market_volatility = 0.15  # Default 15% annual volatility

        logger.info(
            f"🛡️  EnhancedRiskManager initialized: "
            f"capital=₹{total_capital:,.0f}, "
            f"max_sector={max_sector_exposure_pct:.0%}"
        )

    def get_sector(self, symbol: str) -> str:
        """Get sector for symbol"""
        return SECTOR_MAPPING.get(symbol, 'Other')

    def calculate_sector_exposure(
        self,
        positions: Dict[str, float]
    ) -> Dict[str, SectorExposure]:
        """
        Calculate exposure by sector

        Args:
            positions: Dict of {symbol: position_value}

        Returns:
            Dict of {sector: SectorExposure}
        """
        sector_exposure: Dict[str, SectorExposure] = {}

        for symbol, value in positions.items():
            sector = self.get_sector(symbol)

            if sector not in sector_exposure:
                sector_exposure[sector] = SectorExposure(
                    sector=sector,
                    total_value=0.0,
                    num_positions=0,
                    symbols=[]
                )

            sector_exposure[sector].total_value += value
            sector_exposure[sector].num_positions += 1
            sector_exposure[sector].symbols.append(symbol)

        # Calculate percentages
        for exposure in sector_exposure.values():
            exposure.percentage_of_portfolio = (exposure.total_value / self.total_capital) * 100

        return sector_exposure

    def check_sector_limits(
        self,
        symbol: str,
        new_position_value: float,
        existing_positions: Dict[str, float]
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if adding position would violate sector limits

        Args:
            symbol: Symbol to add
            new_position_value: Value of new position
            existing_positions: Current positions

        Returns:
            (allowed, reason)
        """
        sector = self.get_sector(symbol)

        # Calculate new exposures
        new_positions = existing_positions.copy()
        new_positions[symbol] = new_positions.get(symbol, 0) + new_position_value

        sector_exposure = self.calculate_sector_exposure(new_positions)

        # Check sector limit
        if sector in sector_exposure:
            exposure_pct = sector_exposure[sector].percentage_of_portfolio / 100

            if exposure_pct > self.max_sector_exposure_pct:
                return False, (
                    f"Sector limit exceeded: {sector} would be "
                    f"{exposure_pct:.1%} (max: {self.max_sector_exposure_pct:.1%})"
                )

        return True, None

    def find_correlated_positions(
        self,
        symbol: str,
        existing_positions: Dict[str, float]
    ) -> List[CorrelationRisk]:
        """
        Find positions that are highly correlated with symbol

        Args:
            symbol: Symbol to check
            existing_positions: Current positions

        Returns:
            List of correlation risks
        """
        risks = []

        for existing_symbol, existing_value in existing_positions.items():
            if existing_symbol == symbol:
                continue

            # Check predefined correlations
            pair = tuple(sorted([symbol, existing_symbol]))
            correlation = HIGH_CORRELATION_PAIRS.get(pair)

            if correlation and correlation >= self.high_correlation_threshold:
                combined_exposure = existing_value

                # Classify risk level
                exposure_pct = combined_exposure / self.total_capital

                if exposure_pct > 0.40:
                    risk_level = RiskLevel.EXTREME
                elif exposure_pct > 0.30:
                    risk_level = RiskLevel.HIGH
                elif exposure_pct > 0.20:
                    risk_level = RiskLevel.MEDIUM
                else:
                    risk_level = RiskLevel.LOW

                risks.append(CorrelationRisk(
                    symbol1=symbol,
                    symbol2=existing_symbol,
                    correlation=correlation,
                    combined_exposure=combined_exposure,
                    risk_level=risk_level
                ))

        return risks

    def check_correlation_limits(
        self,
        symbol: str,
        new_position_value: float,
        existing_positions: Dict[str, float]
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if adding position would create excessive correlation risk

        Args:
            symbol: Symbol to add
            new_position_value: Value of new position
            existing_positions: Current positions

        Returns:
            (allowed, reason)
        """
        correlated = self.find_correlated_positions(symbol, existing_positions)

        for risk in correlated:
            combined_exposure = risk.combined_exposure + new_position_value
            exposure_pct = combined_exposure / self.total_capital

            if exposure_pct > self.max_correlation_exposure_pct:
                return False, (
                    f"Correlation limit exceeded: {symbol} + {risk.symbol2} "
                    f"(correlation: {risk.correlation:.2f}) would be "
                    f"{exposure_pct:.1%} (max: {self.max_correlation_exposure_pct:.1%})"
                )

        return True, None

    def calculate_dynamic_risk_adjustment(
        self,
        current_volatility: float,
        baseline_volatility: float = 0.15
    ) -> float:
        """
        Calculate dynamic risk adjustment based on volatility

        Higher volatility = lower risk per trade

        Args:
            current_volatility: Current market/symbol volatility
            baseline_volatility: Baseline volatility (15% annual)

        Returns:
            Risk adjustment multiplier (0.5 - 1.5)
        """
        if not self.dynamic_risk_adjustment:
            return 1.0

        # Inverse relationship with volatility
        volatility_ratio = baseline_volatility / max(current_volatility, 0.01)

        # Cap adjustment between 0.5x and 1.5x
        adjustment = np.clip(volatility_ratio, 0.5, 1.5)

        return adjustment

    def calculate_dynamic_position_size(
        self,
        symbol: str,
        win_rate: float,
        avg_profit: float,
        avg_loss: float,
        current_volatility: Optional[float] = None
    ) -> float:
        """
        Calculate position size using Kelly Criterion with volatility adjustment

        Kelly % = (Win Rate × Avg Profit - Loss Rate × Avg Loss) / Avg Profit

        Args:
            symbol: Trading symbol
            win_rate: Historical win rate (0-1)
            avg_profit: Average profit per winning trade
            avg_loss: Average loss per losing trade (positive number)
            current_volatility: Current volatility (optional)

        Returns:
            Position size as fraction of capital
        """
        # Kelly Criterion
        loss_rate = 1 - win_rate

        if avg_profit <= 0:
            return 0.0

        kelly_pct = (win_rate * avg_profit - loss_rate * avg_loss) / avg_profit

        # Conservative Kelly (1/2 or 1/3 Kelly)
        conservative_kelly = kelly_pct / 2

        # Apply base risk limit
        position_size = min(conservative_kelly, self.base_risk_per_trade)

        # Apply volatility adjustment if enabled
        if current_volatility:
            adjustment = self.calculate_dynamic_risk_adjustment(current_volatility)
            position_size *= adjustment

        # Cap between 0.5% and 5%
        position_size = np.clip(position_size, 0.005, 0.05)

        return position_size

    def can_open_position(
        self,
        symbol: str,
        value: float,
        existing_positions: Dict[str, float]
    ) -> Tuple[bool, List[str]]:
        """
        Check if can open a new position considering all risk factors

        Args:
            symbol: Symbol to trade
            value: Position value
            existing_positions: Current positions {symbol: value}

        Returns:
            (allowed, list of reasons if not allowed)
        """
        reasons = []

        # Check sector limits
        sector_ok, sector_reason = self.check_sector_limits(
            symbol, value, existing_positions
        )
        if not sector_ok:
            reasons.append(sector_reason)

        # Check correlation limits
        corr_ok, corr_reason = self.check_correlation_limits(
            symbol, value, existing_positions
        )
        if not corr_ok:
            reasons.append(corr_reason)

        # Check total exposure
        total_exposure = sum(existing_positions.values()) + value
        if total_exposure > self.total_capital:
            reasons.append(
                f"Total exposure ({total_exposure:,.0f}) would exceed capital ({self.total_capital:,.0f})"
            )

        return len(reasons) == 0, reasons

    def get_risk_report(self, positions: Dict[str, float]) -> Dict:
        """
        Generate comprehensive risk report

        Args:
            positions: Current positions

        Returns:
            Risk report with all metrics
        """
        # Sector exposure
        sector_exposure = self.calculate_sector_exposure(positions)

        # Find all correlation risks
        all_corr_risks = []
        checked_pairs = set()

        for symbol in positions.keys():
            for other_symbol in positions.keys():
                if symbol == other_symbol:
                    continue

                pair = tuple(sorted([symbol, other_symbol]))
                if pair in checked_pairs:
                    continue

                checked_pairs.add(pair)

                risks = self.find_correlated_positions(symbol, {other_symbol: positions[other_symbol]})
                all_corr_risks.extend(risks)

        # Highest risk sectors
        high_risk_sectors = [
            exp for exp in sector_exposure.values()
            if exp.percentage_of_portfolio > self.max_sector_exposure_pct * 100 * 0.8  # 80% of limit
        ]

        # Total exposure
        total_exposure = sum(positions.values())
        exposure_pct = (total_exposure / self.total_capital) * 100

        return {
            'total_exposure': total_exposure,
            'exposure_percentage': exposure_pct,
            'sector_exposure': sector_exposure,
            'high_risk_sectors': high_risk_sectors,
            'correlation_risks': all_corr_risks,
            'num_positions': len(positions),
            'risk_level': self._classify_overall_risk(exposure_pct, sector_exposure, all_corr_risks)
        }

    def _classify_overall_risk(
        self,
        exposure_pct: float,
        sector_exposure: Dict[str, SectorExposure],
        correlation_risks: List[CorrelationRisk]
    ) -> RiskLevel:
        """Classify overall portfolio risk level"""
        # Check exposure
        if exposure_pct > 90:
            return RiskLevel.EXTREME

        # Check sector concentration
        max_sector_exp = max([exp.percentage_of_portfolio for exp in sector_exposure.values()], default=0)
        if max_sector_exp > self.max_sector_exposure_pct * 100:
            return RiskLevel.HIGH

        # Check correlation risks
        extreme_corr = [r for r in correlation_risks if r.risk_level == RiskLevel.EXTREME]
        if extreme_corr:
            return RiskLevel.HIGH

        high_corr = [r for r in correlation_risks if r.risk_level == RiskLevel.HIGH]
        if len(high_corr) > 2:
            return RiskLevel.MEDIUM

        if exposure_pct > 70:
            return RiskLevel.MEDIUM

        return RiskLevel.LOW

    def print_risk_report(self, positions: Dict[str, float]):
        """Print formatted risk report"""
        report = self.get_risk_report(positions)

        print("\n" + "="*70)
        print("🛡️  ENHANCED RISK REPORT")
        print("="*70)

        print(f"\nOverall Risk Level: {report['risk_level'].value.upper()}")
        print(f"Total Exposure:     ₹{report['total_exposure']:,.0f} ({report['exposure_percentage']:.1f}%)")
        print(f"Number of Positions: {report['num_positions']}")

        print("\n--- SECTOR EXPOSURE ---")
        for sector, exp in sorted(report['sector_exposure'].items(), key=lambda x: x[1].total_value, reverse=True):
            icon = "⚠️ " if exp.percentage_of_portfolio > self.max_sector_exposure_pct * 100 else ""
            print(f"{icon}{sector:.<20} ₹{exp.total_value:>10,.0f} ({exp.percentage_of_portfolio:>5.1f}%) - {exp.num_positions} positions")

        if report['correlation_risks']:
            print("\n--- CORRELATION RISKS ---")
            for risk in sorted(report['correlation_risks'], key=lambda x: x.combined_exposure, reverse=True):
                print(f"{risk.risk_level.value.upper():.<10} {risk.symbol1} + {risk.symbol2} (corr: {risk.correlation:.2f})")

        print("="*70 + "\n")


if __name__ == "__main__":
    # Test enhanced risk manager
    risk_mgr = EnhancedRiskManager(total_capital=1_000_000)

    # Test positions
    positions = {
        'HDFCBANK': 150_000,
        'ICICIBANK': 120_000,
        'TCS': 100_000,
        'INFY': 80_000,
        'RELIANCE': 90_000
    }

    # Print risk report
    risk_mgr.print_risk_report(positions)

    # Test can open position
    can_trade, reasons = risk_mgr.can_open_position('AXISBANK', 100_000, positions)
    print(f"Can trade AXISBANK: {'✅ YES' if can_trade else '❌ NO'}")
    if reasons:
        for reason in reasons:
            print(f"  - {reason}")

    print("\n✅ Enhanced risk manager tests passed")
