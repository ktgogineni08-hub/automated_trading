#!/usr/bin/env python3
"""
Unified Risk Management System
Combines professional risk rules (1% rule, RRR) with enhanced features (sector limits, correlations).

Merges logic from:
- risk_manager.py (Guide-based rules)
- core/enhanced_risk_manager.py (Sector/Correlation limits)
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

from unified_config import get_config

logger = logging.getLogger('trading_system.risk')

class VolatilityRegime(Enum):
    """Market volatility classification"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"

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

@dataclass
class TradeRiskProfile:
    """Complete risk profile for a potential trade"""
    symbol: str
    entry_price: float
    stop_loss: float
    take_profit: float
    lot_size: int

    # Calculated fields
    risk_per_lot: float = 0.0
    reward_per_lot: float = 0.0
    risk_reward_ratio: float = 0.0
    max_lots_allowed: int = 0
    required_margin: float = 0.0

    # Validation results
    is_valid: bool = False
    rejection_reason: str = ""

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

class UnifiedRiskManager:
    """
    Unified Risk Management System
    
    Combines:
    1. Capital Preservation (1% Rule)
    2. Trade Quality (Risk-Reward Ratio)
    3. Portfolio Balance (Sector Limits)
    4. Systemic Risk Control (Correlation Limits)
    5. Dynamic Adjustment (Volatility-based Sizing)
    """

    def __init__(
        self,
        total_capital: float,
        risk_per_trade_pct: float = 0.01,
        max_sector_exposure_pct: float = 0.30,
        max_correlation_exposure_pct: float = 0.40,
        high_correlation_threshold: float = 0.70,
        dynamic_risk_adjustment: bool = True
    ):
        self.total_capital = total_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_sector_exposure_pct = max_sector_exposure_pct
        self.max_correlation_exposure_pct = max_correlation_exposure_pct
        self.high_correlation_threshold = high_correlation_threshold
        self.dynamic_risk_adjustment = dynamic_risk_adjustment
        self.min_rrr = 1.5

        # Volatility multipliers
        self.volatility_multipliers = {
            VolatilityRegime.LOW: 1.0,
            VolatilityRegime.NORMAL: 1.0,
            VolatilityRegime.HIGH: 0.6,
            VolatilityRegime.EXTREME: 0.4
        }

        logger.info(
            f"🛡️ UnifiedRiskManager initialized: "
            f"Capital=₹{total_capital:,.0f}, "
            f"Risk/Trade={risk_per_trade_pct:.1%}, "
            f"SectorLimit={max_sector_exposure_pct:.0%}"
        )

    # --- Helper Methods ---

    def get_sector(self, symbol: str) -> str:
        return SECTOR_MAPPING.get(symbol, 'Other')

    def detect_volatility_regime(
        self,
        current_atr: float,
        historical_atr_mean: float,
        historical_atr_std: float
    ) -> VolatilityRegime:
        """Classify current volatility regime"""
        if historical_atr_std <= 0:
            return VolatilityRegime.NORMAL
            
        z_score = (current_atr - historical_atr_mean) / historical_atr_std

        if z_score > 2.0:
            return VolatilityRegime.EXTREME
        elif z_score > 1.0:
            return VolatilityRegime.HIGH
        elif z_score < -1.0:
            return VolatilityRegime.LOW
        else:
            return VolatilityRegime.NORMAL

    # --- Core Risk Logic (1% Rule & RRR) ---

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        lot_size: int,
        volatility_regime: VolatilityRegime = VolatilityRegime.NORMAL
    ) -> int:
        """Calculate position size using 1% rule and volatility adjustment"""
        max_loss = self.total_capital * self.risk_per_trade_pct
        risk_per_lot = abs(entry_price - stop_loss) * lot_size

        if risk_per_lot == 0:
            logger.warning("⚠️ Risk per lot is zero - invalid stop-loss")
            return 0

        base_lots = max_loss / risk_per_lot
        
        # Apply volatility adjustment
        volatility_multiplier = self.volatility_multipliers.get(volatility_regime, 1.0) if self.dynamic_risk_adjustment else 1.0
        adjusted_lots = base_lots * volatility_multiplier
        
        lots = int(adjusted_lots)
        return max(0, lots)

    def validate_risk_reward_ratio(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        min_rrr: Optional[float] = None
    ) -> Tuple[bool, float, str]:
        """Validate risk-reward ratio"""
        min_rrr = min_rrr or self.min_rrr
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)

        if risk == 0:
            return False, 0.0, "Invalid: Risk is zero"

        rrr = reward / risk
        is_valid = rrr >= min_rrr
        
        msg = f"RRR={rrr:.2f} (≥{min_rrr:.2f})"
        return is_valid, rrr, msg

    # --- Portfolio Risk Logic (Sector & Correlation) ---

    def calculate_sector_exposure(self, positions: Dict[str, float]) -> Dict[str, SectorExposure]:
        """Calculate exposure by sector"""
        sector_exposure: Dict[str, SectorExposure] = {}

        for symbol, value in positions.items():
            sector = self.get_sector(symbol)
            if sector not in sector_exposure:
                sector_exposure[sector] = SectorExposure(
                    sector=sector, total_value=0.0, num_positions=0, symbols=[]
                )
            sector_exposure[sector].total_value += value
            sector_exposure[sector].num_positions += 1
            sector_exposure[sector].symbols.append(symbol)

        for exposure in sector_exposure.values():
            exposure.percentage_of_portfolio = (exposure.total_value / self.total_capital) * 100

        return sector_exposure

    def check_sector_limits(
        self,
        symbol: str,
        new_position_value: float,
        existing_positions: Dict[str, float]
    ) -> Tuple[bool, Optional[str]]:
        """Check if adding position would violate sector limits"""
        sector = self.get_sector(symbol)
        
        # Calculate projected exposure
        current_sector_value = sum(
            val for sym, val in existing_positions.items() 
            if self.get_sector(sym) == sector
        )
        projected_value = current_sector_value + new_position_value
        projected_pct = projected_value / self.total_capital

        if projected_pct > self.max_sector_exposure_pct:
            return False, (
                f"Sector limit exceeded: {sector} would be "
                f"{projected_pct:.1%} (max: {self.max_sector_exposure_pct:.1%})"
            )
        return True, None

    def find_correlated_positions(
        self,
        symbol: str,
        existing_positions: Dict[str, float]
    ) -> List[CorrelationRisk]:
        """Find positions correlated with the target symbol"""
        risks = []
        for existing_symbol, existing_value in existing_positions.items():
            if existing_symbol == symbol:
                continue

            pair = tuple(sorted([symbol, existing_symbol]))
            correlation = HIGH_CORRELATION_PAIRS.get(pair)

            if correlation and correlation >= self.high_correlation_threshold:
                combined_exposure = existing_value # Note: This is just existing, caller adds new
                
                exposure_pct = combined_exposure / self.total_capital
                
                if exposure_pct > 0.40: risk_level = RiskLevel.EXTREME
                elif exposure_pct > 0.30: risk_level = RiskLevel.HIGH
                elif exposure_pct > 0.20: risk_level = RiskLevel.MEDIUM
                else: risk_level = RiskLevel.LOW

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
        """Check if adding position would create excessive correlation risk"""
        correlated = self.find_correlated_positions(symbol, existing_positions)
        
        for risk in correlated:
            combined_exposure = risk.combined_exposure + new_position_value
            exposure_pct = combined_exposure / self.total_capital
            
            if exposure_pct > self.max_correlation_exposure_pct:
                return False, (
                    f"Correlation limit exceeded: {symbol} + {risk.symbol2} "
                    f"(corr: {risk.correlation:.2f}) would be "
                    f"{exposure_pct:.1%} (max: {self.max_correlation_exposure_pct:.1%})"
                )
        return True, None

    # --- Main Assessment Method ---

    def assess_trade_viability(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        lot_size: int,
        existing_positions: Dict[str, float],
        current_atr: Optional[float] = None,
        volatility_regime: VolatilityRegime = VolatilityRegime.NORMAL
    ) -> TradeRiskProfile:
        """
        Comprehensive pre-trade risk assessment
        """
        profile = TradeRiskProfile(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            lot_size=lot_size
        )

        # 1. Validate RRR
        is_rrr_valid, rrr, rrr_msg = self.validate_risk_reward_ratio(
            entry_price, stop_loss, take_profit
        )
        if not is_rrr_valid:
            profile.is_valid = False
            profile.rejection_reason = rrr_msg
            return profile
        profile.risk_reward_ratio = rrr

        # 2. Calculate Risk/Reward per lot
        profile.risk_per_lot = abs(entry_price - stop_loss) * lot_size
        profile.reward_per_lot = abs(take_profit - entry_price) * lot_size

        # 3. Calculate Position Size (1% Rule + Volatility)
        lots = self.calculate_position_size(
            entry_price, stop_loss, lot_size, volatility_regime
        )
        if lots == 0:
            profile.is_valid = False
            profile.rejection_reason = "Position size too small (risk/lot exceeds 1% limit)"
            return profile

        # 4. Check Portfolio Limits (Sector & Correlation)
        position_value = entry_price * lot_size * lots
        
        sector_ok, sector_msg = self.check_sector_limits(symbol, position_value, existing_positions)
        if not sector_ok:
            profile.is_valid = False
            profile.rejection_reason = sector_msg
            return profile

        corr_ok, corr_msg = self.check_correlation_limits(symbol, position_value, existing_positions)
        if not corr_ok:
            profile.is_valid = False
            profile.rejection_reason = corr_msg
            return profile

        # 5. Check Total Exposure
        total_exposure = sum(existing_positions.values()) + position_value
        if total_exposure > self.total_capital:
             profile.is_valid = False
             profile.rejection_reason = f"Total exposure ({total_exposure:,.0f}) exceeds capital"
             return profile

        # 6. Stop Loss Check
        if current_atr:
            stop_distance = abs(entry_price - stop_loss)
            if stop_distance < current_atr * 1.5:
                logger.warning(f"⚠️ Stop too tight: {stop_distance:.2f} < 1.5x ATR ({current_atr*1.5:.2f})")

        profile.max_lots_allowed = lots
        profile.required_margin = position_value * 0.10 # Approx margin
        profile.is_valid = True
        
        return profile

    def calculate_trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        initial_stop: float,
        target_price: float,
        is_long: bool = True
    ) -> float:
        """Calculate trailing stop-loss"""
        if is_long:
            profit_distance = target_price - entry_price
            halfway_price = entry_price + (profit_distance / 2)

            if current_price >= target_price:
                return current_price * 0.99
            elif current_price >= halfway_price:
                return max(initial_stop, entry_price, current_price * 0.97)
            else:
                return max(initial_stop, initial_stop) # No change
        else:
            profit_distance = entry_price - target_price
            halfway_price = entry_price - (profit_distance / 2)

            if current_price <= target_price:
                return current_price * 1.01
            elif current_price <= halfway_price:
                return min(initial_stop, entry_price, current_price * 1.03)
            else:
                return min(initial_stop, initial_stop)

if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    rm = UnifiedRiskManager(total_capital=1000000)
    
    # Test positions
    positions = {'HDFCBANK': 150000}
    
    profile = rm.assess_trade_viability(
        symbol="ICICIBANK", # Correlated with HDFCBANK
        entry_price=1000,
        stop_loss=980,
        take_profit=1040,
        lot_size=100,
        existing_positions=positions
    )
    
    print(f"Valid: {profile.is_valid}")
    if not profile.is_valid:
        print(f"Reason: {profile.rejection_reason}")
    else:
        print(f"Lots: {profile.max_lots_allowed}")
