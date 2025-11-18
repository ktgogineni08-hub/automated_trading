#!/usr/bin/env python3
"""
Professional Risk Management Module
Based on: "A Comprehensive Guide to Trading Indian Equity Futures" Section 7

Implements:
- 1% Risk Rule (Section 7.1)
- Risk-Reward Ratio Validation (Section 7.2)
- Volatility-Based Position Adjustments (Section 7.3)
- Position Sizing Based on Stop-Loss Distance
"""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from utilities.structured_logger import get_logger, log_function_call

logger = get_logger(__name__)


class VolatilityRegime(Enum):
    """Market volatility classification"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"


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


class RiskManager:
    """
    Professional Risk Management System

    Key Principles from Guide:
    1. Never risk more than 1% of capital per trade (Section 7.1)
    2. Minimum risk-reward ratio of 1:1.5 (Section 7.2)
    3. Adjust position size based on volatility (Section 7.3)
    4. Position size driven by stop-loss distance, not arbitrary percentages
    """

    def __init__(self, total_capital: float, risk_per_trade_pct: float = 0.01):
        """
        Initialize Risk Manager

        Args:
            total_capital: Total trading capital in account
            risk_per_trade_pct: Maximum risk per trade (default 1% = 0.01)
        """
        self.total_capital = total_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.min_rrr = 1.5  # Minimum risk-reward ratio

        # Volatility-based adjustments (Section 7.3)
        self.volatility_multipliers = {
            VolatilityRegime.LOW: 1.0,      # Normal position size
            VolatilityRegime.NORMAL: 1.0,   # Normal position size
            VolatilityRegime.HIGH: 0.6,     # Reduce to 60%
            VolatilityRegime.EXTREME: 0.4   # Reduce to 40%
        }

        logger.info(f"✅ RiskManager initialized: Capital=₹{total_capital:,.0f}, Risk={risk_per_trade_pct*100}%")

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        lot_size: int,
        volatility_regime: VolatilityRegime = VolatilityRegime.NORMAL
    ) -> int:
        """
        Calculate position size using 1% rule (Guide Section 7.1)

        Formula:
            max_loss = total_capital * risk_per_trade_pct
            risk_per_lot = abs(entry_price - stop_loss) * lot_size
            lots = max_loss / risk_per_lot

        Args:
            entry_price: Proposed entry price
            stop_loss: Stop-loss price
            lot_size: Contract lot size (e.g., 65 for NIFTY)
            volatility_regime: Current market volatility

        Returns:
            Number of lots to trade (0 if trade should be skipped)
        """
        # Calculate maximum acceptable loss
        max_loss = self.total_capital * self.risk_per_trade_pct

        # Calculate risk per lot
        risk_per_lot = abs(entry_price - stop_loss) * lot_size

        if risk_per_lot == 0:
            logger.warning("⚠️ Risk per lot is zero - invalid stop-loss")
            return 0

        # Calculate base lots
        base_lots = max_loss / risk_per_lot

        # Apply volatility adjustment (Section 7.3)
        volatility_multiplier = self.volatility_multipliers.get(volatility_regime, 1.0)
        adjusted_lots = base_lots * volatility_multiplier

        # Round down to integer lots
        lots = int(adjusted_lots)

        # Log calculation
        if lots > 0:
            logger.info(
                f"📊 Position Sizing: "
                f"Entry=₹{entry_price:.2f}, Stop=₹{stop_loss:.2f}, "
                f"LotSize={lot_size}, "
                f"Risk/Lot=₹{risk_per_lot:,.0f}, "
                f"MaxLoss=₹{max_loss:,.0f}, "
                f"BaseLots={base_lots:.2f}, "
                f"Volatility={volatility_regime.value}, "
                f"Multiplier={volatility_multiplier}, "
                f"FinalLots={lots}"
            )
        else:
            logger.warning(
                f"⚠️ Position size too small: "
                f"Risk/Lot=₹{risk_per_lot:,.0f} exceeds MaxLoss=₹{max_loss:,.0f}. "
                f"Calculated lots={adjusted_lots:.3f}. SKIP TRADE."
            )

        return max(0, lots)

    def validate_risk_reward_ratio(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        min_rrr: Optional[float] = None
    ) -> Tuple[bool, float, str]:
        """
        Validate risk-reward ratio meets minimum threshold (Guide Section 7.2)

        Professional traders refuse trades with RRR < 1:1.5 or 1:2
        Even with 40% win rate, 1:2 RRR yields profitability.

        Args:
            entry_price: Proposed entry price
            stop_loss: Stop-loss price
            take_profit: Take-profit target
            min_rrr: Minimum acceptable RRR (default 1.5)

        Returns:
            (is_valid, actual_rrr, message)
        """
        min_rrr = min_rrr or self.min_rrr

        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)

        if risk == 0:
            return False, 0.0, "Invalid: Risk is zero (entry = stop)"

        rrr = reward / risk

        is_valid = rrr >= min_rrr

        if is_valid:
            message = f"✅ RRR={rrr:.2f} (≥{min_rrr:.2f}) - ACCEPTABLE"
            logger.info(message)
        else:
            message = f"❌ RRR={rrr:.2f} (<{min_rrr:.2f}) - REJECT TRADE"
            logger.warning(message)

        return is_valid, rrr, message

    def assess_trade_viability(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        lot_size: int,
        current_atr: Optional[float] = None,
        volatility_regime: VolatilityRegime = VolatilityRegime.NORMAL
    ) -> TradeRiskProfile:
        """
        Comprehensive pre-trade risk assessment (Guide Section 6.2)

        Validates:
        1. Risk-reward ratio
        2. Position size calculation
        3. Stop-loss placement (should be outside 1.5x ATR)
        4. Overall trade viability

        Returns:
            TradeRiskProfile with complete risk analysis
        """
        profile = TradeRiskProfile(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            lot_size=lot_size
        )

        # 1. Validate risk-reward ratio
        is_rrr_valid, rrr, rrr_msg = self.validate_risk_reward_ratio(
            entry_price, stop_loss, take_profit
        )

        if not is_rrr_valid:
            profile.is_valid = False
            profile.rejection_reason = rrr_msg
            return profile

        profile.risk_reward_ratio = rrr

        # 2. Calculate risk and reward per lot
        profile.risk_per_lot = abs(entry_price - stop_loss) * lot_size
        profile.reward_per_lot = abs(take_profit - entry_price) * lot_size

        # 3. Calculate position size
        lots = self.calculate_position_size(
            entry_price, stop_loss, lot_size, volatility_regime
        )

        if lots == 0:
            profile.is_valid = False
            profile.rejection_reason = "Position size too small (risk/lot exceeds 1% limit)"
            return profile

        profile.max_lots_allowed = lots

        # 4. Validate stop-loss placement (if ATR provided)
        if current_atr:
            stop_distance = abs(entry_price - stop_loss)
            min_stop_distance = current_atr * 1.5  # Should be outside 1.5x ATR

            if stop_distance < min_stop_distance:
                logger.warning(
                    f"⚠️ Stop too tight: {stop_distance:.2f} < {min_stop_distance:.2f} (1.5x ATR). "
                    f"May get stopped out by noise."
                )
                # Not rejection, just warning

        # 5. Calculate required margin (approximate)
        contract_value = entry_price * lot_size * lots
        profile.required_margin = contract_value * 0.10  # ~10% for index futures

        # 6. Final validation
        profile.is_valid = True

        logger.info(
            f"✅ Trade Assessment PASSED: {symbol}\n"
            f"   Entry=₹{entry_price:.2f}, Stop=₹{stop_loss:.2f}, Target=₹{take_profit:.2f}\n"
            f"   RRR={rrr:.2f}, Lots={lots}, Risk/Lot=₹{profile.risk_per_lot:,.0f}, "
            f"Reward/Lot=₹{profile.reward_per_lot:,.0f}\n"
            f"   Total Risk=₹{profile.risk_per_lot * lots:,.0f}, "
            f"Total Reward=₹{profile.reward_per_lot * lots:,.0f}"
        )

        return profile

    def detect_volatility_regime(
        self,
        current_atr: float,
        historical_atr_mean: float,
        historical_atr_std: float
    ) -> VolatilityRegime:
        """
        Classify current volatility regime (Guide Section 7.3)

        Used to adjust position sizes:
        - High volatility → Reduce position size
        - Low volatility → Normal position size (tighter targets)

        Args:
            current_atr: Current ATR value
            historical_atr_mean: Mean ATR over lookback period
            historical_atr_std: Std deviation of ATR

        Returns:
            VolatilityRegime classification
        """
        z_score = (current_atr - historical_atr_mean) / historical_atr_std if historical_atr_std > 0 else 0

        if z_score > 2.0:
            regime = VolatilityRegime.EXTREME
        elif z_score > 1.0:
            regime = VolatilityRegime.HIGH
        elif z_score < -1.0:
            regime = VolatilityRegime.LOW
        else:
            regime = VolatilityRegime.NORMAL

        logger.debug(
            f"Volatility: ATR={current_atr:.2f}, "
            f"Mean={historical_atr_mean:.2f}, "
            f"Z-Score={z_score:.2f}, "
            f"Regime={regime.value}"
        )

        return regime

    def calculate_trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        initial_stop: float,
        target_price: float,
        is_long: bool = True
    ) -> float:
        """
        Calculate trailing stop-loss (Guide Section 6.3)

        Logic:
        - Initially: Use initial stop
        - At halfway to target: Move stop to entry (risk-free)
        - Beyond halfway: Trail stop to lock in profits

        Args:
            entry_price: Original entry price
            current_price: Current market price
            initial_stop: Initial stop-loss
            target_price: Take-profit target
            is_long: True for long position, False for short

        Returns:
            Updated stop-loss price
        """
        if is_long:
            # Long position
            profit_distance = target_price - entry_price
            halfway_price = entry_price + (profit_distance / 2)

            if current_price >= target_price:
                # Target reached or exceeded - very tight trail
                new_stop = current_price * 0.99  # Trail 1% below current
            elif current_price >= halfway_price:
                # Halfway to target - risk-free position
                new_stop = max(initial_stop, entry_price, current_price * 0.97)  # Trail 3% below
            else:
                # Not yet halfway - use initial stop
                new_stop = initial_stop

            # Never move stop down
            new_stop = max(new_stop, initial_stop)

        else:
            # Short position
            profit_distance = entry_price - target_price
            halfway_price = entry_price - (profit_distance / 2)

            if current_price <= target_price:
                # Target reached or exceeded - very tight trail
                new_stop = current_price * 1.01  # Trail 1% above current
            elif current_price <= halfway_price:
                # Halfway to target - risk-free position
                new_stop = min(initial_stop, entry_price, current_price * 1.03)  # Trail 3% above
            else:
                # Not yet halfway - use initial stop
                new_stop = initial_stop

            # Never move stop up
            new_stop = min(new_stop, initial_stop)

        if new_stop != initial_stop:
            logger.info(
                f"🎯 Trailing Stop: "
                f"Entry=₹{entry_price:.2f}, "
                f"Current=₹{current_price:.2f}, "
                f"Stop: ₹{initial_stop:.2f} → ₹{new_stop:.2f}"
            )

        return new_stop

    def get_position_size_recommendation(
        self,
        entry_price: float,
        stop_loss: float,
        lot_size: int,
        available_margin: float,
        volatility_regime: VolatilityRegime = VolatilityRegime.NORMAL
    ) -> Dict[str, any]:
        """
        Get comprehensive position sizing recommendation

        Returns:
            {
                'lots': int,
                'risk_amount': float,
                'required_margin': float,
                'is_feasible': bool,
                'warnings': list
            }
        """
        lots = self.calculate_position_size(entry_price, stop_loss, lot_size, volatility_regime)

        risk_amount = abs(entry_price - stop_loss) * lot_size * lots
        contract_value = entry_price * lot_size * lots
        required_margin = contract_value * 0.10  # Approximate

        warnings = []
        is_feasible = True

        if lots == 0:
            warnings.append("Position size too small - skip trade")
            is_feasible = False

        if required_margin > available_margin:
            warnings.append(f"Insufficient margin: Need ₹{required_margin:,.0f}, Have ₹{available_margin:,.0f}")
            is_feasible = False

        if risk_amount > self.total_capital * 0.02:
            warnings.append(f"Risk exceeds 2% of capital: ₹{risk_amount:,.0f}")

        return {
            'lots': lots,
            'risk_amount': risk_amount,
            'required_margin': required_margin,
            'is_feasible': is_feasible,
            'warnings': warnings,
            'volatility_regime': volatility_regime.value
        }


# Module-level convenience function
def create_risk_manager(total_capital: float, risk_pct: float = 0.01) -> RiskManager:
    """
    Convenience function to create a RiskManager instance

    Args:
        total_capital: Total trading capital
        risk_pct: Risk per trade (default 1%)

    Returns:
        Configured RiskManager instance
    """
    return RiskManager(total_capital, risk_pct)


if __name__ == "__main__":
    # Example usage matching Guide's NIFTY 50 case study (Section 6)
    logging.basicConfig(level=logging.INFO)

    # Create risk manager for ₹10 lakh capital
    rm = RiskManager(total_capital=1000000, risk_per_trade_pct=0.01)

    # NIFTY 50 trade from guide (Section 6.2)
    profile = rm.assess_trade_viability(
        symbol="NIFTY50FUT",
        entry_price=25160,
        stop_loss=24980,
        take_profit=25520,
        lot_size=65,
        current_atr=180,  # Approximate ATR
        volatility_regime=VolatilityRegime.NORMAL
    )

    print(f"\n{'='*80}")
    print(f"TRADE ASSESSMENT RESULT")
    print(f"{'='*80}")
    print(f"Valid: {profile.is_valid}")
    if profile.is_valid:
        print(f"Lots to Trade: {profile.max_lots_allowed}")
        print(f"Risk per Lot: ₹{profile.risk_per_lot:,.0f}")
        print(f"Reward per Lot: ₹{profile.reward_per_lot:,.0f}")
        print(f"Risk-Reward Ratio: {profile.risk_reward_ratio:.2f}:1")
        print(f"Total Risk: ₹{profile.risk_per_lot * profile.max_lots_allowed:,.0f}")
        print(f"Total Reward: ₹{profile.reward_per_lot * profile.max_lots_allowed:,.0f}")
    else:
        print(f"Rejection Reason: {profile.rejection_reason}")
    print(f"{'='*80}\n")
