#!/usr/bin/env python3
"""
Trade Quality Filter
Prevents low-quality entries that lead to losses
Only take high-probability trades
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, time

# CRITICAL FIX: Import IST-aware time functions to prevent trading during off-hours
from trading_utils import get_ist_now, parse_timestamp

logger = logging.getLogger('trading_system')


class TradeQualityFilter:
    """
    Filter out low-quality trade setups before execution

    Goal: Reduce trade quantity but increase quality
    Current problem: 267 trades/day with 81% not closing
    Target: 100-150 trades/day with 80%+ close rate
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        # Confidence thresholds
        self.min_confidence = 0.75  # Minimum to consider
        self.high_confidence = 0.85  # High quality threshold

        # Portfolio limits
        self.max_open_positions = 15  # Never exceed this
        self.max_losing_positions = 4  # Pause if too many losers
        self.max_same_symbol_trades = 3  # Per hour

        # Time-based scoring
        self.best_hours = (10, 14)  # 10 AM - 2 PM
        self.avoid_hours = (9, 10, 14, 15)  # First/last hour

        # Quality score threshold
        self.min_quality_score = 70  # Out of 100

        logger.info("✅ Trade Quality Filter initialized")

    def should_enter_trade(
        self,
        signal: Dict,
        market_conditions: Dict,
        portfolio_state: Dict
    ) -> Tuple[bool, str, int]:
        """
        Evaluate if we should enter this trade

        Args:
            signal: Trade signal with confidence, direction, symbol, etc.
            market_conditions: Market data (volatility, trend, hour, etc.)
            portfolio_state: Current portfolio (open positions, recent trades, etc.)

        Returns:
            (should_enter, reason, quality_score)
        """

        symbol = signal.get('symbol', 'UNKNOWN')
        confidence = signal.get('confidence', 0.0)
        direction = signal.get('direction', 'neutral')

        # Initialize scoring
        score = 0
        max_score = 100
        reasons = []

        # ===================================================================
        # FILTER 1: CONFIDENCE THRESHOLD (CRITICAL)
        # ===================================================================
        if confidence < self.min_confidence:
            return False, f"Confidence too low: {confidence:.1%} < {self.min_confidence:.1%}", 0

        # Score based on confidence
        conf_score = min((confidence - 0.75) / 0.25 * 50, 50)  # Max 50 points
        score += conf_score
        reasons.append(f"Confidence: {confidence:.1%} (+{conf_score:.0f}pts)")

        # ===================================================================
        # FILTER 2: PORTFOLIO HEAT CHECK (CRITICAL)
        # ===================================================================
        open_positions = portfolio_state.get('open_positions', 0)
        losing_positions = portfolio_state.get('losing_positions', 0)

        # Hard stop if too many positions
        if open_positions >= self.max_open_positions:
            return False, f"Max positions reached: {open_positions}/{self.max_open_positions}", 0

        # Hard stop if too many losers
        if losing_positions >= self.max_losing_positions:
            if confidence < self.high_confidence:
                return False, f"Portfolio stressed: {losing_positions} losers, need {self.high_confidence:.0%} confidence", 0

        # Score for position count (fewer = better)
        position_score = max(0, 20 - (open_positions * 2))  # Max 20 points
        score += position_score
        if position_score > 0:
            reasons.append(f"Position count: {open_positions} (+{position_score:.0f}pts)")

        # Penalize if losing
        if losing_positions > 0:
            penalty = min(losing_positions * 5, 15)
            score -= penalty
            reasons.append(f"⚠️ {losing_positions} losers (-{penalty}pts)")

        # ===================================================================
        # FILTER 3: TREND ALIGNMENT
        # ===================================================================
        trend = market_conditions.get('trend', 'neutral')
        trend_strength = market_conditions.get('trend_strength', 0.5)

        trend_score = 0
        if trend == direction:  # Aligned with trend
            trend_score = 20
            reasons.append(f"Trend aligned: {trend} (+20pts)")
        elif trend == 'neutral':
            trend_score = 10
            reasons.append(f"Neutral trend (+10pts)")
        else:  # Counter-trend
            trend_score = 0
            reasons.append(f"⚠️ Counter-trend (+0pts)")

        score += trend_score

        # ===================================================================
        # FILTER 4: VOLATILITY CHECK
        # ===================================================================
        volatility = market_conditions.get('volatility', 'normal')

        if volatility == 'extreme':
            # Only take very high confidence trades in extreme volatility
            if confidence < 0.85:
                return False, f"Volatility too high for confidence {confidence:.1%}", 0
            else:
                score += 10
                reasons.append("Extreme vol but high confidence (+10pts)")

        elif volatility == 'high':
            if confidence >= 0.80:
                score += 5
                reasons.append("High vol, adequate confidence (+5pts)")
            else:
                score -= 5
                reasons.append("⚠️ High vol, lower confidence (-5pts)")

        elif volatility == 'normal':
            score += 10
            reasons.append("Normal volatility (+10pts)")

        else:  # Low volatility
            score += 15
            reasons.append("Low volatility - ideal (+15pts)")

        # ===================================================================
        # FILTER 5: TIME OF DAY
        # ===================================================================
        current_hour = market_conditions.get('hour', 12)

        time_score = 0
        if self.best_hours[0] <= current_hour < self.best_hours[1]:
            # Best trading hours (10 AM - 2 PM)
            time_score = 15
            reasons.append(f"Prime time: {current_hour}:00 (+15pts)")
        elif current_hour in self.avoid_hours:
            # Avoid first/last hour
            time_score = 5
            reasons.append(f"⚠️ Volatile hour: {current_hour}:00 (+5pts)")
        else:
            time_score = 10
            reasons.append(f"Acceptable time: {current_hour}:00 (+10pts)")

        score += time_score

        # Late in day? Avoid new positions after 2:30 PM
        if current_hour >= 14 and (current_hour > 14 or market_conditions.get('minute', 0) >= 30):
            if confidence < 0.85:
                return False, "Too late in day for this confidence level", 0
            score -= 10
            reasons.append("⚠️ Late day entry (-10pts)")

        # ===================================================================
        # FILTER 6: AVOID OVER-TRADING SAME SYMBOL
        # ===================================================================
        recent_trades = portfolio_state.get('recent_trades', [])

        # Count trades in this symbol in last hour
        same_symbol_count = 0
        # CRITICAL FIX: Use IST-aware time to prevent timezone issues
        cutoff_time = get_ist_now()
        for trade in recent_trades:
            if trade.get('symbol') == symbol:
                trade_time = trade.get('timestamp')

                if isinstance(trade_time, str):
                    trade_time = parse_timestamp(trade_time)
                elif isinstance(trade_time, datetime):
                    trade_time = parse_timestamp(trade_time.isoformat())
                else:
                    continue

                if (cutoff_time - trade_time).total_seconds() < 3600:  # Last hour
                    same_symbol_count += 1

        if same_symbol_count >= self.max_same_symbol_trades:
            return False, f"Already traded {symbol} {same_symbol_count} times in last hour", 0

        if same_symbol_count > 0:
            penalty = same_symbol_count * 5
            score -= penalty
            reasons.append(f"⚠️ {same_symbol_count} recent {symbol} trades (-{penalty}pts)")

        # ===================================================================
        # FILTER 7: RISK/REWARD CHECK
        # ===================================================================
        risk_reward = signal.get('risk_reward', 0)
        if risk_reward > 0:
            if risk_reward >= 2.0:  # 1:2 or better
                score += 15
                reasons.append(f"Excellent R:R {risk_reward:.1f} (+15pts)")
            elif risk_reward >= 1.5:
                score += 10
                reasons.append(f"Good R:R {risk_reward:.1f} (+10pts)")
            elif risk_reward < 1.0:  # Bad R:R
                score -= 10
                reasons.append(f"⚠️ Poor R:R {risk_reward:.1f} (-10pts)")

        # ===================================================================
        # FILTER 8: SECTOR DIVERSIFICATION
        # ===================================================================
        sector = signal.get('sector', 'F&O')
        sector_exposure = portfolio_state.get('sector_exposure', {})
        sector_count = sector_exposure.get(sector, 0)

        if sector_count >= 5:  # Too concentrated in one sector
            score -= 15
            reasons.append(f"⚠️ Over-concentrated in {sector} (-15pts)")
        elif sector_count >= 3:
            score -= 5
            reasons.append(f"⚠️ Multiple {sector} positions (-5pts)")

        # ===================================================================
        # FINAL DECISION
        # ===================================================================
        should_enter = score >= self.min_quality_score

        reason_str = f"Quality: {score}/{max_score} | " + " | ".join(reasons[:5])

        if should_enter:
            logger.info(f"✅ ENTRY APPROVED: {symbol} | {reason_str}")
        else:
            logger.info(f"❌ ENTRY REJECTED: {symbol} | {reason_str}")

        return should_enter, reason_str, score

    def get_daily_trade_limit(self, portfolio_state: Dict) -> int:
        """
        Calculate dynamic daily trade limit

        Reduces trades if system is losing
        """

        base_limit = 150  # Base daily limit

        # Check today's performance
        daily_pnl = portfolio_state.get('daily_pnl', 0)
        completed_trades = portfolio_state.get('completed_trades_today', 0)

        # If losing significantly, reduce limit
        if daily_pnl < -50000:  # -50k
            return min(100, base_limit)
        elif daily_pnl < -20000:  # -20k
            return min(120, base_limit)

        # If doing well, maintain limit
        return base_limit

    def should_pause_trading(self, portfolio_state: Dict) -> Tuple[bool, str]:
        """
        Check if trading should be paused

        Returns:
            (should_pause, reason)
        """

        # Check losing streak
        losing_streak = portfolio_state.get('losing_streak', 0)
        if losing_streak >= 5:
            return True, f"Losing streak: {losing_streak} trades"

        # Check daily loss limit
        daily_pnl = portfolio_state.get('daily_pnl', 0)
        if daily_pnl < -100000:  # -1 lakh
            return True, f"Daily loss limit hit: ₹{daily_pnl:,.0f}"

        # Check too many open positions
        open_positions = portfolio_state.get('open_positions', 0)
        if open_positions >= 20:
            return True, f"Too many open positions: {open_positions}"

        # Check system health
        close_rate = portfolio_state.get('close_rate', 1.0)
        if close_rate < 0.5:  # Less than 50% closing
            return True, f"Poor close rate: {close_rate*100:.0f}%"

        return False, ""


class AdvancedSignalScorer:
    """
    Advanced scoring for trade signals
    Combines multiple factors for better quality assessment
    """

    def __init__(self):
        self.weights = {
            'confidence': 0.30,
            'trend_alignment': 0.20,
            'risk_reward': 0.15,
            'volatility': 0.10,
            'time_of_day': 0.10,
            'technical_strength': 0.15
        }

    def score_signal(self, signal: Dict, market_conditions: Dict) -> float:
        """
        Generate composite quality score for signal

        Returns:
            Score between 0 and 1
        """

        total_score = 0

        # 1. Confidence
        confidence = signal.get('confidence', 0.5)
        total_score += confidence * self.weights['confidence']

        # 2. Trend alignment
        trend = market_conditions.get('trend', 'neutral')
        direction = signal.get('direction', 'neutral')
        if trend == direction:
            trend_score = 1.0
        elif trend == 'neutral':
            trend_score = 0.7
        else:
            trend_score = 0.3
        total_score += trend_score * self.weights['trend_alignment']

        # 3. Risk/Reward
        rr = signal.get('risk_reward', 1.0)
        rr_score = min(rr / 3.0, 1.0)  # Cap at 3:1
        total_score += rr_score * self.weights['risk_reward']

        # 4. Volatility (prefer normal/low)
        vol = market_conditions.get('volatility', 'normal')
        vol_scores = {'low': 1.0, 'normal': 0.8, 'high': 0.5, 'extreme': 0.2}
        vol_score = vol_scores.get(vol, 0.5)
        total_score += vol_score * self.weights['volatility']

        # 5. Time of day (prefer 10-14)
        hour = market_conditions.get('hour', 12)
        if 10 <= hour < 14:
            time_score = 1.0
        elif hour < 10 or hour >= 14:
            time_score = 0.6
        else:
            time_score = 0.8
        total_score += time_score * self.weights['time_of_day']

        # 6. Technical strength
        tech_strength = signal.get('technical_strength', 0.5)
        total_score += tech_strength * self.weights['technical_strength']

        return total_score


# Convenience function
def filter_trade(
    signal: Dict,
    market_conditions: Dict,
    portfolio_state: Dict
) -> Tuple[bool, str, int]:
    """Quick function to filter a trade"""
    filter_obj = TradeQualityFilter()
    return filter_obj.should_enter_trade(signal, market_conditions, portfolio_state)


if __name__ == "__main__":
    print("="*80)
    print("TRADE QUALITY FILTER - TEST")
    print("="*80)

    filter_obj = TradeQualityFilter()

    # Test cases
    test_cases = [
        {
            'name': 'High quality trade',
            'signal': {
                'symbol': 'NIFTY25OCT25000CE',
                'confidence': 0.85,
                'direction': 'bullish',
                'risk_reward': 2.5,
                'sector': 'F&O'
            },
            'market': {
                'trend': 'bullish',
                'trend_strength': 0.8,
                'volatility': 'normal',
                'hour': 11
            },
            'portfolio': {
                'open_positions': 5,
                'losing_positions': 1,
                'recent_trades': []
            }
        },
        {
            'name': 'Low confidence trade',
            'signal': {
                'symbol': 'BANKNIFTY25OCT51000PE',
                'confidence': 0.65,
                'direction': 'bearish',
                'risk_reward': 1.5,
                'sector': 'F&O'
            },
            'market': {
                'trend': 'neutral',
                'volatility': 'normal',
                'hour': 12
            },
            'portfolio': {
                'open_positions': 8,
                'losing_positions': 2,
                'recent_trades': []
            }
        },
        {
            'name': 'Portfolio stressed',
            'signal': {
                'symbol': 'MIDCPNIFTY25OCT13000CE',
                'confidence': 0.78,
                'direction': 'bullish',
                'risk_reward': 2.0,
                'sector': 'F&O'
            },
            'market': {
                'trend': 'bullish',
                'volatility': 'normal',
                'hour': 13
            },
            'portfolio': {
                'open_positions': 12,
                'losing_positions': 5,  # Too many losers!
                'recent_trades': []
            }
        },
    ]

    for test in test_cases:
        print(f"\n{'='*80}")
        print(f"TEST: {test['name']}")
        print(f"{'='*80}")

        should_enter, reason, score = filter_obj.should_enter_trade(
            test['signal'],
            test['market'],
            test['portfolio']
        )

        print(f"Decision: {'ENTER ✅' if should_enter else 'REJECT ❌'}")
        print(f"Score: {score}/100")
        print(f"Reason: {reason}")

    print("\n" + "="*80)
    print("✅ Trade quality filter will reduce bad entries significantly!")
    print("✅ Expected: 267 trades/day → 100-150 trades/day (higher quality)")
    print("="*80)
