#!/usr/bin/env python3
"""
Intelligent Exit Manager
Smart exit logic that minimizes losses and captures profits
NO FORCED EXITS - Only intelligent decisions
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import re
from trading_utils import safe_divide

logger = logging.getLogger('trading_system')


@dataclass
class ExitDecision:
    """Result of exit evaluation"""
    should_exit: bool
    score: int  # 0-100, higher = stronger exit signal
    reasons: List[str]
    exit_type: str  # 'PROFIT_TAKE', 'STOP_LOSS', 'RISK_MANAGEMENT'
    urgency: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    suggested_exit_pct: float = 1.0  # Can suggest partial exits


class IntelligentExitManager:
    """
    Smart exit management system

    Features:
    - Quick profit taking to lock gains
    - Trailing stops for runners
    - Theta decay protection for options
    - Smart stop-loss (not rigid)
    - Position health scoring
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        # Exit thresholds (tunable)
        self.quick_profit_threshold = 0.15  # 15% quick profit
        self.good_profit_threshold = 0.10   # 10% good profit
        self.small_profit_threshold = 0.05  # 5% profit

        self.trailing_stop_trigger = 0.20   # Start trailing at 20% profit
        self.trailing_stop_distance = 0.10  # Trail by 10%

        self.smart_stop_initial = -0.03     # -3% initial concern
        self.smart_stop_medium = -0.05      # -5% medium concern
        self.smart_stop_critical = -0.08    # -8% critical - must exit

        self.exit_score_threshold = 60      # Need 60+ points to exit

        # Time-based thresholds
        self.quick_trade_minutes = 30
        self.stale_position_minutes = 120
        self.theta_risk_hours = 2

        logger.info("✅ Intelligent Exit Manager initialized")

    def evaluate_position_exit(
        self,
        position: Dict,
        current_price: float,
        market_conditions: Optional[Dict] = None
    ) -> ExitDecision:
        """
        Evaluate if a position should be exited

        Args:
            position: Position dict with entry_price, shares, entry_time, etc.
            current_price: Current market price
            market_conditions: Optional market data (volatility, trend, etc.)

        Returns:
            ExitDecision with recommendation
        """

        market_conditions = market_conditions or {}

        # Calculate position metrics
        entry_price = position.get('entry_price', 0)
        if entry_price <= 0 or current_price <= 0:
            logger.warning(f"Invalid prices for {position.get('symbol')}: entry={entry_price}, current={current_price}")
            return ExitDecision(
                should_exit=False,
                score=0,
                reasons=["Invalid price data"],
                exit_type='NONE',
                urgency='LOW'
            )

        # CRITICAL FIX: Use safe_divide to prevent divide-by-zero
        pnl_pct = safe_divide(current_price - entry_price, entry_price, 0.0)
        pnl_amount = (current_price - entry_price) * position.get('shares', 0)

        # Time held
        entry_time = position.get('entry_time')
        if isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))

        if entry_time:
            time_held = datetime.now() - entry_time.replace(tzinfo=None)
            time_held_minutes = time_held.total_seconds() / 60
            time_held_hours = time_held_minutes / 60
        else:
            time_held_minutes = 0
            time_held_hours = 0

        # Initialize scoring
        score = 0
        reasons = []
        exit_type = 'NONE'
        urgency = 'LOW'

        # ===================================================================
        # RULE 1: QUICK PROFIT TAKING (Highest Priority)
        # ===================================================================
        profit_score, profit_reasons, profit_type = self._evaluate_profit_taking(
            pnl_pct, pnl_amount, time_held_minutes, position
        )
        score += profit_score
        reasons.extend(profit_reasons)
        if profit_type:
            exit_type = profit_type

        # ===================================================================
        # RULE 2: TRAILING STOP FOR BIG WINNERS
        # ===================================================================
        trailing_score, trailing_reasons = self._evaluate_trailing_stop(
            pnl_pct, position
        )
        score += trailing_score
        reasons.extend(trailing_reasons)
        if trailing_score > 70:
            exit_type = 'PROFIT_PROTECT'
            urgency = 'HIGH'

        # ===================================================================
        # RULE 3: THETA DECAY PROTECTION (Options)
        # ===================================================================
        theta_score, theta_reasons = self._evaluate_theta_risk(
            position, time_held_hours, pnl_pct
        )
        score += theta_score
        reasons.extend(theta_reasons)

        # ===================================================================
        # RULE 4: SMART STOP LOSS (Not Rigid)
        # ===================================================================
        stop_score, stop_reasons, stop_urgency = self._evaluate_smart_stop(
            pnl_pct, pnl_amount, time_held_minutes, market_conditions
        )
        score += stop_score
        reasons.extend(stop_reasons)
        if stop_score > 70:
            exit_type = 'STOP_LOSS'
            urgency = stop_urgency

        # ===================================================================
        # RULE 5: POSITION STAGNATION
        # ===================================================================
        stagnation_score, stagnation_reasons = self._evaluate_stagnation(
            pnl_pct, time_held_minutes
        )
        score += stagnation_score
        reasons.extend(stagnation_reasons)

        # ===================================================================
        # FINAL DECISION
        # ===================================================================
        should_exit = score >= self.exit_score_threshold

        # Determine urgency based on score
        if score >= 90:
            urgency = 'CRITICAL'
        elif score >= 75:
            urgency = 'HIGH'
        elif score >= 60:
            urgency = 'MEDIUM'
        else:
            urgency = 'LOW'

        # Log decision
        symbol = position.get('symbol', 'UNKNOWN')
        if should_exit:
            logger.info(
                f"🚨 EXIT SIGNAL: {symbol} | Score: {score}/100 | "
                f"P&L: {pnl_pct*100:.1f}% (₹{pnl_amount:,.0f}) | "
                f"Type: {exit_type} | Urgency: {urgency} | "
                f"Reasons: {', '.join(reasons[:3])}"
            )
        else:
            logger.debug(
                f"✋ HOLD: {symbol} | Score: {score}/100 | "
                f"P&L: {pnl_pct*100:.1f}% | Time: {time_held_minutes:.0f}min"
            )

        return ExitDecision(
            should_exit=should_exit,
            score=score,
            reasons=reasons,
            exit_type=exit_type,
            urgency=urgency
        )

    def _evaluate_profit_taking(
        self,
        pnl_pct: float,
        pnl_amount: float,
        time_held_minutes: float,
        position: Dict
    ) -> Tuple[int, List[str], str]:
        """Evaluate if we should take profit"""

        score = 0
        reasons = []
        exit_type = None

        # Quick scalp profits (high priority)
        if pnl_pct >= self.quick_profit_threshold:  # 15%+
            if time_held_minutes < self.quick_trade_minutes:
                score += 100
                reasons.append(f"🎯 Quick scalp: {pnl_pct*100:.1f}% in {time_held_minutes:.0f}min")
                exit_type = 'PROFIT_TAKE'
            else:
                score += 85
                reasons.append(f"💰 Strong profit: {pnl_pct*100:.1f}%")
                exit_type = 'PROFIT_TAKE'

        # Good profit (medium priority)
        elif pnl_pct >= self.good_profit_threshold:  # 10%+
            if time_held_minutes < 60:
                score += 80
                reasons.append(f"✅ Fast profit: {pnl_pct*100:.1f}% in {time_held_minutes:.0f}min")
                exit_type = 'PROFIT_TAKE'
            else:
                score += 60
                reasons.append(f"📈 Solid profit: {pnl_pct*100:.1f}%")
                exit_type = 'PROFIT_TAKE'

        # Small profit that's stagnating
        elif pnl_pct >= self.small_profit_threshold:  # 5%+
            if time_held_minutes > self.stale_position_minutes:
                score += 60
                reasons.append(f"⏱️ Stagnant profit: {pnl_pct*100:.1f}% for {time_held_minutes:.0f}min")
                exit_type = 'RISK_MANAGEMENT'

        # Absolute profit targets (regardless of percentage)
        if pnl_amount >= 10000:  # ₹10k profit
            score += 50
            reasons.append(f"💵 Absolute profit: ₹{pnl_amount:,.0f}")
            if not exit_type:
                exit_type = 'PROFIT_TAKE'
        elif pnl_amount >= 5000:  # ₹5k profit
            score += 30
            reasons.append(f"💵 Good profit: ₹{pnl_amount:,.0f}")

        return score, reasons, exit_type

    def _evaluate_trailing_stop(
        self,
        current_pnl_pct: float,
        position: Dict
    ) -> Tuple[int, List[str]]:
        """Evaluate trailing stop for winners"""

        score = 0
        reasons = []

        # Track max profit achieved
        max_profit_pct = position.get('max_profit_pct', current_pnl_pct)

        # Update max if current is higher
        if current_pnl_pct > max_profit_pct:
            max_profit_pct = current_pnl_pct
            position['max_profit_pct'] = max_profit_pct

        # Check if profit has given back significantly
        if max_profit_pct >= self.trailing_stop_trigger:  # Was 20%+
            giveback = max_profit_pct - current_pnl_pct

            if giveback >= self.trailing_stop_distance:  # Gave back 10%+
                score += 90
                reasons.append(
                    f"🔻 Trailing stop: Peak {max_profit_pct*100:.1f}%, "
                    f"now {current_pnl_pct*100:.1f}% (gave back {giveback*100:.1f}%)"
                )
            elif giveback >= 0.05:  # Gave back 5%+
                score += 70
                reasons.append(
                    f"⚠️ Profit giveback: Peak {max_profit_pct*100:.1f}%, "
                    f"now {current_pnl_pct*100:.1f}%"
                )

        elif max_profit_pct >= 0.15:  # Was 15%+
            giveback = max_profit_pct - current_pnl_pct
            if giveback >= 0.07:  # Gave back 7%+
                score += 80
                reasons.append(f"📉 Large giveback: {giveback*100:.1f}%")

        return score, reasons

    def _evaluate_theta_risk(
        self,
        position: Dict,
        time_held_hours: float,
        pnl_pct: float
    ) -> Tuple[int, List[str]]:
        """Evaluate theta decay risk for options"""

        score = 0
        reasons = []

        symbol = position.get('symbol', '')

        # Check if it's an option
        if not any(x in symbol for x in ['CE', 'PE']):
            return 0, []  # Not an option

        # Parse expiry from symbol
        days_to_expiry = self._parse_days_to_expiry(symbol)

        if days_to_expiry is None:
            return 0, []

        # High risk if expiring soon
        if days_to_expiry == 0:  # Expiring today!
            score += 60
            reasons.append("⏰ EXPIRING TODAY - High theta risk")

            if time_held_hours >= 2:
                score += 30
                reasons.append(f"⚠️ Held {time_held_hours:.1f}hrs on expiry day")

            # If losing on expiry day, urgent exit
            if pnl_pct < 0:
                score += 40
                reasons.append("💀 Losing on expiry day - cut loss")

        elif days_to_expiry <= 2:  # Expiring this week
            score += 30
            reasons.append(f"⏱️ Expires in {days_to_expiry} days")

            if time_held_hours >= 4 and pnl_pct < 0.05:
                score += 25
                reasons.append("Long hold near expiry with small profit")

        elif days_to_expiry <= 5:  # Weekly expiry approaching
            if time_held_hours >= 6:
                score += 15
                reasons.append("Multi-hour hold, expiry approaching")

        return score, reasons

    def _evaluate_smart_stop(
        self,
        pnl_pct: float,
        pnl_amount: float,
        time_held_minutes: float,
        market_conditions: Dict
    ) -> Tuple[int, List[str], str]:
        """Smart stop-loss (not rigid)"""

        score = 0
        reasons = []
        urgency = 'LOW'

        if pnl_pct >= 0:
            return 0, [], 'LOW'  # Not losing

        # Critical loss - must exit
        if pnl_pct <= self.smart_stop_critical:  # -8%
            score += 95
            reasons.append(f"🛑 CRITICAL LOSS: {pnl_pct*100:.1f}%")
            urgency = 'CRITICAL'
            return score, reasons, urgency

        # Medium loss - strong exit signal
        if pnl_pct <= self.smart_stop_medium:  # -5%
            # Check for reasons to hold
            hold_score = 0

            # Just entered? Give it time
            if time_held_minutes < 5:
                hold_score += 30
                reasons.append(f"ℹ️ Just entered ({time_held_minutes:.1f}min ago)")

            # High volatility? Normal fluctuation
            volatility = market_conditions.get('volatility', 'normal')
            if volatility == 'high':
                hold_score += 20
                reasons.append("📊 High volatility - normal swing")

            # Strong trend in our favor?
            trend_strength = market_conditions.get('trend_strength', 0)
            if trend_strength > 0.7:
                hold_score += 25
                reasons.append("📈 Strong trend - hold")

            # If no good reasons to hold
            if hold_score < 30:
                score += 75
                reasons.append(f"📉 Medium loss: {pnl_pct*100:.1f}% - no reason to hold")
                urgency = 'HIGH'
            else:
                score += 30
                reasons.append(f"⚠️ Loss {pnl_pct*100:.1f}% but reasons to hold")
                urgency = 'MEDIUM'

        # Small loss but stagnating
        elif pnl_pct <= self.smart_stop_initial:  # -3%
            if time_held_minutes > self.stale_position_minutes:  # 2+ hours
                score += 50
                reasons.append(f"⏳ Small loss {pnl_pct*100:.1f}% for {time_held_minutes:.0f}min")
                urgency = 'MEDIUM'

        # Absolute loss amounts
        if pnl_amount <= -5000:  # -₹5k
            score += 40
            reasons.append(f"💸 Absolute loss: ₹{abs(pnl_amount):,.0f}")

        return score, reasons, urgency

    def _evaluate_stagnation(
        self,
        pnl_pct: float,
        time_held_minutes: float
    ) -> Tuple[int, List[str]]:
        """Check if position is stagnating"""

        score = 0
        reasons = []

        # Breakeven trade held too long
        if -0.01 < pnl_pct < 0.01:  # Basically breakeven
            if time_held_minutes > 180:  # 3+ hours
                score += 40
                reasons.append(f"💤 Breakeven for {time_held_minutes:.0f}min - opportunity cost")

        # Small profit/loss, held very long
        if -0.02 < pnl_pct < 0.03:  # -2% to +3%
            if time_held_minutes > 240:  # 4+ hours
                score += 35
                reasons.append(f"⏰ Going nowhere: {pnl_pct*100:.1f}% for {time_held_minutes/60:.1f}hrs")

        return score, reasons

    def _parse_days_to_expiry(self, symbol: str) -> Optional[int]:
        """Parse days to expiry from symbol"""

        try:
            # Try to extract date from symbol like 'NIFTY25OCT25000CE'
            # Format: SYMBOL + YY + MMM + DATE + CE/PE

            # Extract month and date
            months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                     'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

            for i, month in enumerate(months, 1):
                if month in symbol:
                    # Found month, now extract year and day
                    pattern = r'(\d{2})' + month + r'(\d{1,2})'
                    match = re.search(pattern, symbol)

                    if match:
                        year = int('20' + match.group(1))
                        day = int(match.group(2))
                        month_num = i

                        expiry_date = datetime(year, month_num, day).date()
                        today = datetime.now().date()

                        days = (expiry_date - today).days
                        return max(0, days)

            return None
        except Exception as e:
            logger.debug(f"Could not parse expiry from {symbol}: {e}")
            return None

    def batch_evaluate_positions(
        self,
        positions: Dict[str, Dict],
        current_prices: Dict[str, float],
        market_conditions: Optional[Dict] = None
    ) -> List[Tuple[str, ExitDecision]]:
        """
        Evaluate all positions and return prioritized exit list

        Returns:
            List of (symbol, ExitDecision) tuples sorted by urgency/score
        """

        exit_decisions = []

        for symbol, position in positions.items():
            current_price = current_prices.get(symbol)

            if current_price is None or current_price <= 0:
                logger.warning(f"No valid price for {symbol}, skipping exit evaluation")
                continue

            decision = self.evaluate_position_exit(
                position, current_price, market_conditions
            )

            if decision.should_exit:
                exit_decisions.append((symbol, decision))

        # Sort by urgency and score
        urgency_priority = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
        exit_decisions.sort(
            key=lambda x: (urgency_priority.get(x[1].urgency, 0), x[1].score),
            reverse=True
        )

        return exit_decisions


# Convenience function
def should_exit_position(
    position: Dict,
    current_price: float,
    market_conditions: Optional[Dict] = None
) -> ExitDecision:
    """Quick function to check if position should exit"""
    manager = IntelligentExitManager()
    return manager.evaluate_position_exit(position, current_price, market_conditions)


if __name__ == "__main__":
    print("="*80)
    print("INTELLIGENT EXIT MANAGER - TEST")
    print("="*80)

    manager = IntelligentExitManager()

    # Test cases
    test_positions = [
        {
            'desc': 'Quick 15% profit in 20 min',
            'position': {
                'symbol': 'NIFTY25OCT25000CE',
                'entry_price': 150.0,
                'shares': 50,
                'entry_time': (datetime.now() - timedelta(minutes=20)).isoformat()
            },
            'current_price': 172.5
        },
        {
            'desc': 'Losing 6% after 1 hour',
            'position': {
                'symbol': 'BANKNIFTY25OCT51000PE',
                'entry_price': 200.0,
                'shares': 30,
                'entry_time': (datetime.now() - timedelta(hours=1)).isoformat()
            },
            'current_price': 188.0
        },
        {
            'desc': 'Stagnant breakeven for 3 hours',
            'position': {
                'symbol': 'MIDCPNIFTY25OCT13000CE',
                'entry_price': 100.0,
                'shares': 70,
                'entry_time': (datetime.now() - timedelta(hours=3)).isoformat()
            },
            'current_price': 100.5
        },
    ]

    for test in test_positions:
        print(f"\n{'='*80}")
        print(f"TEST: {test['desc']}")
        print(f"{'='*80}")

        decision = manager.evaluate_position_exit(
            test['position'],
            test['current_price']
        )

        print(f"Should Exit: {'YES ✅' if decision.should_exit else 'NO ❌'}")
        print(f"Score: {decision.score}/100")
        print(f"Type: {decision.exit_type}")
        print(f"Urgency: {decision.urgency}")
        print(f"Reasons:")
        for reason in decision.reasons:
            print(f"  - {reason}")

    print("\n" + "="*80)
    print("✅ Intelligent exit manager ready to reduce losses and capture profits!")
    print("="*80)
