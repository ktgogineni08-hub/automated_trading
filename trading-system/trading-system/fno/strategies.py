#!/usr/bin/env python3
"""
FNO Trading Strategies
Option strategies: Straddle, Iron Condor, Strangle, Butterfly
"""

from typing import Dict, Optional
import logging

from fno.options import OptionChain

logger = logging.getLogger('trading_system.fno.strategies')


class FNOStrategy:
    """Base class for F&O strategies"""

    def __init__(self, name: str):
        self.name = name

    def analyze_option_chain(self, chain: OptionChain) -> Dict:
        """Analyze option chain and return trading signals"""
        raise NotImplementedError("Subclasses must implement analyze_option_chain")

    def calculate_position_size(self, capital: float, risk_per_trade: float) -> int:
        """Calculate position size based on risk management"""
        return int(capital * risk_per_trade / 100)

class StraddleStrategy(FNOStrategy):
    """Straddle strategy - buy ATM call and put"""

    def __init__(self):
        super().__init__("Straddle")

    def analyze_option_chain(self, chain: OptionChain) -> Dict:
        """Find optimal straddle setup"""
        if not chain.calls or not chain.puts:
            logger.warning("No options available in chain")
            return {'action': 'hold', 'confidence': 0.0}

        atm_strike = chain.get_atm_strike()
        logger.info(f"ATM strike for {chain.underlying}: {atm_strike}")

        call_option = chain.calls.get(atm_strike)
        put_option = chain.puts.get(atm_strike)

        if not call_option or not put_option:
            logger.warning(f"Missing ATM options at strike {atm_strike}")
            # Try to find nearest strikes
            all_strikes = sorted(list(chain.calls.keys()) + list(chain.puts.keys()))
            nearest_strike = min(all_strikes, key=lambda x: abs(x - chain.spot_price))
            call_option = chain.calls.get(nearest_strike)
            put_option = chain.puts.get(nearest_strike)
            atm_strike = nearest_strike

        if not call_option or not put_option:
            logger.warning("No suitable options found for straddle")
            return {'action': 'hold', 'confidence': 0.0}

        # Calculate total premium
        total_premium = call_option.last_price + put_option.last_price
        breakeven_upper = atm_strike + total_premium
        breakeven_lower = atm_strike - total_premium

        # Calculate expected move (based on implied volatility)
        days_to_expiry = 7  # Assume weekly expiry
        avg_iv = (call_option.implied_volatility + put_option.implied_volatility) / 2
        expected_move = chain.spot_price * (avg_iv / 100) * (days_to_expiry / 365) ** 0.5

        # Strategy is favorable if expected move > total premium
        confidence = min(expected_move / total_premium, 1.0) if total_premium > 0 else 0.0

        logger.info(f"Straddle analysis: Premium={total_premium:.2f}, Expected Move={expected_move:.2f}, Confidence={confidence:.2%}")

        if confidence > 0.6:
            return {
                'action': 'buy_straddle',
                'confidence': confidence,
                'strike': atm_strike,
                'call_option': call_option,
                'put_option': put_option,
                'total_premium': total_premium,
                'breakeven_upper': breakeven_upper,
                'breakeven_lower': breakeven_lower,
                'expected_move': expected_move
            }

        return {'action': 'hold', 'confidence': 0.0}

class IronCondorStrategy(FNOStrategy):
    """Iron Condor strategy - sell OTM call/put spreads"""

    def __init__(self, width: int = 100):
        super().__init__("Iron Condor")
        self.width = width

    def analyze_option_chain(self, chain: OptionChain) -> Dict:
        """Find optimal iron condor setup with improved confidence calculation"""
        if not chain.calls or not chain.puts:
            logger.warning("No options available in chain")
            return {'action': 'hold', 'confidence': 0.0}

        spot = chain.spot_price
        all_strikes = sorted(list(chain.calls.keys()) + list(chain.puts.keys()))
        logger.info(f"Available strikes for {chain.underlying}: {len(all_strikes)} strikes")

        # Find strikes for the condor
        # Sell call spread: sell higher strike call, buy even higher strike call
        # Sell put spread: sell lower strike put, buy even lower strike put

        # Find call strikes (OTM)
        call_strikes = [s for s in all_strikes if s > spot]
        if len(call_strikes) < 2:
            logger.warning(f"Insufficient call strikes above spot {spot}")
            return {'action': 'hold', 'confidence': 0.0}

        # Use width parameter to determine spread
        width_pct = self.width / spot  # Convert absolute width to percentage
        sell_call_strike = call_strikes[0]  # First OTM call
        buy_call_strike = min(call_strikes[-1], sell_call_strike + int(spot * width_pct))

        # Find put strikes (OTM)
        put_strikes = [s for s in all_strikes if s < spot]
        if len(put_strikes) < 2:
            logger.warning(f"Insufficient put strikes below spot {spot}")
            return {'action': 'hold', 'confidence': 0.0}

        sell_put_strike = put_strikes[-1]  # First OTM put (highest strike below spot)
        buy_put_strike = max(put_strikes[0], sell_put_strike - int(spot * width_pct))

        logger.info(f"Iron Condor strikes: Sell Call {sell_call_strike}, Buy Call {buy_call_strike}, Sell Put {sell_put_strike}, Buy Put {buy_put_strike}")

        # Get options
        sell_call = chain.calls.get(sell_call_strike)
        buy_call = chain.calls.get(buy_call_strike)
        sell_put = chain.puts.get(sell_put_strike)
        buy_put = chain.puts.get(buy_put_strike)

        if not all([sell_call, buy_call, sell_put, buy_put]):
            logger.warning("Missing required options for iron condor")
            return {'action': 'hold', 'confidence': 0.0}

        # Calculate net credit
        net_credit = (sell_call.last_price + sell_put.last_price) - (buy_call.last_price + buy_put.last_price)

        if net_credit <= 0:
            logger.warning(f"Negative net credit: {net_credit}")
            return {'action': 'hold', 'confidence': 0.0}

        # Calculate max profit and loss
        call_spread_width = buy_call_strike - sell_call_strike
        put_spread_width = sell_put_strike - buy_put_strike
        max_profit = net_credit
        max_loss = (call_spread_width + put_spread_width) - net_credit

        # Risk-reward ratio
        risk_reward = max_profit / max_loss if max_loss > 0 else 0

        # Calculate expected move (based on implied volatility)
        days_to_expiry = 7  # Assume weekly expiry
        avg_iv = (sell_call.implied_volatility + buy_call.implied_volatility +
                 sell_put.implied_volatility + buy_put.implied_volatility) / 4
        expected_move = chain.spot_price * (avg_iv / 100) * (days_to_expiry / 365) ** 0.5

        # Calculate spread width as percentage of spot
        total_spread_width = call_spread_width + put_spread_width
        spread_width_pct = total_spread_width / spot

        # Improved confidence calculation considering multiple factors
        base_confidence = min(risk_reward * 0.8, 1.0) if risk_reward > 0 else 0.0

        # Liquidity factor (higher OI = higher confidence)
        avg_oi = (sell_call.open_interest + buy_call.open_interest +
                 sell_put.open_interest + buy_put.open_interest) / 4
        liquidity_factor = min(avg_oi / 50000, 1.0)  # Normalize to 0-1

        # Volatility factor (moderate IV is good for iron condor)
        volatility_factor = 1.0 if 20 <= avg_iv <= 35 else max(0, 1 - abs(avg_iv - 25) / 25)

        # Spread efficiency factor (wider spread = more room for error)
        spread_factor = min(spread_width_pct * 10, 1.0)  # Normalize spread width

        # Combined confidence with multiple factors
        confidence = (base_confidence * 0.4 + liquidity_factor * 0.3 +
                     volatility_factor * 0.2 + spread_factor * 0.1)

        logger.info(f"Iron Condor analysis: Credit={net_credit:.2f}, Max Profit={max_profit:.2f}, Max Loss={max_loss:.2f}, RR={risk_reward:.2f}")
        logger.info(f"  • Expected Move: {expected_move:.2f}")
        logger.info(f"  • Spread Width: {total_spread_width} ({spread_width_pct:.1%})")
        logger.info(f"  • Average IV: {avg_iv:.1f}%")
        logger.info(f"  • Average OI: {avg_oi:.0f}")
        logger.info(f"  • Base confidence: {base_confidence:.2%}")
        logger.info(f"  • Liquidity factor: {liquidity_factor:.2%}")
        logger.info(f"  • Volatility factor: {volatility_factor:.2%}")
        logger.info(f"  • Spread factor: {spread_factor:.2%}")
        logger.info(f"  • Combined confidence: {confidence:.2%}")

        if confidence > 0.4:  # Lower threshold for more opportunities
            return {
                'action': 'iron_condor',
                'confidence': confidence,
                'sell_call_strike': sell_call_strike,
                'buy_call_strike': buy_call_strike,
                'sell_put_strike': sell_put_strike,
                'buy_put_strike': buy_put_strike,
                'sell_call': sell_call,
                'buy_call': buy_call,
                'sell_put': sell_put,
                'buy_put': buy_put,
                'net_credit': net_credit,
                'max_profit': max_profit,
                'max_loss': max_loss,
                'risk_reward': risk_reward,
                'expected_move': expected_move,
                'avg_iv': avg_iv,
                'avg_oi': avg_oi,
                'spread_width_pct': spread_width_pct
            }

        return {'action': 'hold', 'confidence': 0.0}


class StrangleStrategy(FNOStrategy):
    """Strangle strategy - buy OTM call and put"""

    def __init__(self, otm_percent: float = 0.03):
        super().__init__("Strangle")
        self.otm_percent = otm_percent

    def analyze_option_chain(self, chain: OptionChain) -> Dict:
        """Identify a balanced long strangle opportunity."""
        if not chain.calls or not chain.puts or not chain.spot_price:
            logger.warning("Option chain missing data for strangle analysis")
            return {'action': 'hold', 'confidence': 0.0}

        spot = chain.spot_price
        all_strikes = sorted(set(list(chain.calls.keys()) + list(chain.puts.keys())))

        if not all_strikes:
            logger.warning("No strikes available for strangle selection")
            return {'action': 'hold', 'confidence': 0.0}

        call_candidates = [strike for strike in all_strikes if strike >= spot * (1 + self.otm_percent)]
        put_candidates = [strike for strike in all_strikes if strike <= spot * (1 - self.otm_percent)]

        if not call_candidates or not put_candidates:
            logger.info("Insufficient OTM strikes for strangle construction")
            return {'action': 'hold', 'confidence': 0.0}

        call_strike = min(call_candidates, key=lambda s: abs(s - spot * (1 + self.otm_percent)))
        put_strike = max(put_candidates, key=lambda s: abs(s - spot * (1 - self.otm_percent)))

        call_option = chain.calls.get(call_strike)
        put_option = chain.puts.get(put_strike)

        if not call_option or not put_option or call_option.last_price <= 0 or put_option.last_price <= 0:
            logger.warning("Missing or invalid option pricing for strangle")
            return {'action': 'hold', 'confidence': 0.0}

        total_premium = call_option.last_price + put_option.last_price
        breakeven_upper = call_strike + total_premium
        breakeven_lower = put_strike - total_premium

        days_to_expiry = 7  # default weekly cycle assumption
        avg_iv = max((call_option.implied_volatility + put_option.implied_volatility) / 2, 1.0)
        expected_move = spot * (avg_iv / 100) * (days_to_expiry / 365) ** 0.5

        premium_ratio = total_premium / max(spot, 1)
        otm_width = (call_strike - put_strike) / max(spot, 1)

        score = 0.0
        if expected_move > 0:
            score += min(expected_move / total_premium, 1.0) * 0.6
        score += max(0, 0.2 - premium_ratio) * 2.0  # tighter premium improves score
        score += min(otm_width, 0.15) * (1 / 0.15) * 0.2  # reward balanced wings up to 15%
        confidence = min(score, 0.95)

        logger.info(
            "Strangle analysis: call=%s put=%s premium=%.2f expected_move=%.2f confidence=%.2f",
            call_option.symbol, put_option.symbol, total_premium, expected_move, confidence
        )

        if confidence < 0.55:
            return {'action': 'hold', 'confidence': confidence}

        return {
            'action': 'buy_strangle',
            'confidence': confidence,
            'call_strike': call_strike,
            'put_strike': put_strike,
            'call_option': call_option,
            'put_option': put_option,
            'total_premium': total_premium,
            'expected_move': expected_move,
            'breakeven_upper': breakeven_upper,
            'breakeven_lower': breakeven_lower
        }


class ButterflyStrategy(FNOStrategy):
    """Long butterfly strategy using calls or puts."""

    def __init__(self, option_type: str = 'call'):
        if option_type not in ('call', 'put'):
            raise ValueError("option_type must be 'call' or 'put'")
        super().__init__(f"{option_type.capitalize()} Butterfly")
        self.option_type = option_type

    def analyze_option_chain(self, chain: OptionChain) -> Dict:
        if not chain.calls or not chain.puts:
            logger.warning("Option chain incomplete for butterfly analysis")
            return {'action': 'hold', 'confidence': 0.0}

        spot = chain.spot_price
        strikes = sorted(chain.calls.keys() if self.option_type == 'call' else chain.puts.keys())
        if not strikes:
            return {'action': 'hold', 'confidence': 0.0}

        # Identify middle strike close to spot
        middle = min(strikes, key=lambda s: abs(s - spot))
        middle_idx = strikes.index(middle)
        if middle_idx == 0 or middle_idx >= len(strikes) - 1:
            logger.info("Insufficient strikes around middle for butterfly construction")
            return {'action': 'hold', 'confidence': 0.0}

        lower = strikes[middle_idx - 1]
        upper = strikes[middle_idx + 1]

        if self.option_type == 'call':
            lower_opt = chain.calls.get(lower)
            middle_opt = chain.calls.get(middle)
            upper_opt = chain.calls.get(upper)
        else:
            lower_opt = chain.puts.get(lower)
            middle_opt = chain.puts.get(middle)
            upper_opt = chain.puts.get(upper)

        if not all([lower_opt, middle_opt, upper_opt]):
            logger.info("Butterfly options missing for strikes %s/%s/%s", lower, middle, upper)
            return {'action': 'hold', 'confidence': 0.0}

        net_cost = lower_opt.last_price + upper_opt.last_price - 2 * middle_opt.last_price
        wing_width = abs(middle - lower)
        max_profit = max(0.0, wing_width - max(net_cost, 0.0))

        if net_cost <= 0 or wing_width <= 0:
            logger.info("Butterfly rejected due to non-positive net cost or wing width")
            return {'action': 'hold', 'confidence': 0.0}

        reward_ratio = max_profit / net_cost if net_cost > 0 else 0.0
        iv_avg = max((lower_opt.implied_volatility + middle_opt.implied_volatility + upper_opt.implied_volatility) / 3, 1.0)
        iv_factor = 1.0 if 15 <= iv_avg <= 30 else max(0, 1 - abs(iv_avg - 22.5) / 30)

        confidence = min((reward_ratio * 0.5) + (iv_factor * 0.3) + (min(wing_width / max(spot, 1), 0.02) * 25 * 0.2), 0.9)

        action_name = f"buy_{self.option_type}_butterfly"
        logger.info(
            "%s butterfly analysis: strikes %s/%s/%s cost=%.2f profit=%.2f RR=%.2f confidence=%.2f",
            self.option_type.upper(), lower, middle, upper, net_cost, max_profit, reward_ratio, confidence
        )

        if confidence < 0.5:
            return {'action': 'hold', 'confidence': confidence}

        return {
            'action': action_name,
            'confidence': confidence,
            'lower_strike': lower,
            'middle_strike': middle,
            'upper_strike': upper,
            'lower_option': lower_opt,
            'middle_option': middle_opt,
            'upper_option': upper_opt,
            'net_cost': net_cost,
            'max_profit': max_profit,
            'reward_ratio': reward_ratio
        }
