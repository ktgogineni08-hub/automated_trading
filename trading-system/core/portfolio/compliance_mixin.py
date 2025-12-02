#!/usr/bin/env python3
"""Compliancemixin for UnifiedPortfolio."""

import logging
from typing import Dict, Optional, Tuple

from core.unified_risk_manager import VolatilityRegime

logger = logging.getLogger('trading_system.portfolio')


class ComplianceMixin:
    def validate_trade_pre_execution(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        lot_size: int,
        side: str,
        current_atr: Optional[float] = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Comprehensive pre-trade validation using professional modules

        Validates:
        1. Risk-Reward Ratio (Guide Section 7.2)
        2. Position size using 1% rule (Guide Section 7.1)
        3. SEBI position limits (Guide Section 9.2)
        4. F&O ban period check (Guide Section 9.2)
        5. Margin requirements (Guide Section 3.4)
        6. Sector & Correlation limits (Unified Risk Manager)

        Returns:
            (is_valid, rejection_reason, trade_profile)
        """
        # Skip validation for exit trades
        if side == "sell" and symbol in self.positions:
            return True, "", None

        # 1. SEBI Compliance Check
        compliance_result = self.sebi_compliance.comprehensive_pre_trade_check(
            symbol=symbol,
            qty=lot_size,
            price=entry_price,
            transaction_type="BUY" if side == "buy" else "SELL"
        )

        if not compliance_result.is_compliant:
            reason = f"SEBI Compliance Failed: {', '.join(compliance_result.errors)}"
            logger.warning(f"❌ {reason}")
            return False, reason, None

        # 2. Detect volatility regime for position adjustment
        volatility_regime = VolatilityRegime.NORMAL
        if current_atr:
            # Simple volatility detection (can be enhanced with historical ATR data)
            # For now, classify based on ATR relative to price
            atr_pct = (current_atr / entry_price) * 100

            # CRITICAL FIX: Check thresholds in descending order
            # The previous code checked > 3.0 before > 4.5, making EXTREME unreachable
            if atr_pct > 4.5:
                volatility_regime = VolatilityRegime.EXTREME
            elif atr_pct > 3.0:
                volatility_regime = VolatilityRegime.HIGH
            elif atr_pct < 1.0:
                volatility_regime = VolatilityRegime.LOW

        # 3. Risk Management Assessment
        # Prepare existing positions for risk manager (Symbol -> Invested Value)
        existing_positions_value = {}
        for pos_sym, pos_data in self.positions.items():
            # Use invested_amount if available, else calculate
            val = pos_data.get('invested_amount', 0.0)
            if val == 0:
                shares = pos_data.get('shares', 0)
                price = pos_data.get('entry_price', 0)
                val = abs(shares * price)
            existing_positions_value[pos_sym] = val

        trade_profile = self.risk_manager.assess_trade_viability(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            lot_size=lot_size,
            existing_positions=existing_positions_value,
            current_atr=current_atr,
            volatility_regime=volatility_regime
        )

        if not trade_profile.is_valid:
            logger.warning(f"❌ Risk Assessment Failed: {trade_profile.rejection_reason}")
            return False, trade_profile.rejection_reason, None

        # 4. Log validation success
        logger.info(
            f"✅ Trade validation passed: {symbol}\n"
            f"   Lots: {trade_profile.max_lots_allowed}, RRR: {trade_profile.risk_reward_ratio:.2f}, "
            f"Risk: ₹{trade_profile.risk_per_lot * trade_profile.max_lots_allowed:,.0f}, "
            f"Volatility: {volatility_regime.value}"
        )

        return True, "", trade_profile

    def get_strategy_distribution(self) -> Dict[str, int]:
        """Get current strategy distribution across positions"""
        strategy_count = {}
        for symbol, pos in self.positions.items():
            strategy = pos.get('strategy', 'unknown')
            strategy_count[strategy] = strategy_count.get(strategy, 0) + 1
        return strategy_count

    def should_diversify_strategy(self, proposed_strategy: str, max_concentration: float = 0.6) -> bool:
        """Check if adding this strategy would create over-concentration"""
        if len(self.positions) == 0:
            return True  # First position, no diversification needed

        strategy_dist = self.get_strategy_distribution()
        current_count = strategy_dist.get(proposed_strategy, 0)
        total_positions = len(self.positions)

        # Check if adding one more would exceed concentration limit
        new_concentration = (current_count + 1) / (total_positions + 1)
        return new_concentration <= max_concentration
