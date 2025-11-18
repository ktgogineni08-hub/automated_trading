#!/usr/bin/env python3
"""
Realistic Paper Trading Pricing Module
Adds bid-ask spreads, slippage, and market impact to paper trading
"""

import logging
from typing import Dict, Optional
from datetime import datetime, time

logger = logging.getLogger('trading_system')


class RealisticPricingEngine:
    """
    Provides realistic pricing for paper trading by adding:
    - Bid-ask spreads based on liquidity
    - Slippage based on order size
    - Market impact for large orders
    - Time-of-day adjustments
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        # Base spread percentages (can be tuned)
        self.spread_config = {
            'nifty_atm': 0.005,      # 0.5% for ATM NIFTY options
            'nifty_otm': 0.01,       # 1.0% for OTM NIFTY options
            'nifty_deep_otm': 0.02,  # 2.0% for deep OTM
            'illiquid': 0.05,        # 5.0% for very illiquid options
            'stock': 0.001,          # 0.1% for liquid stocks
        }

        # Slippage (execution worse than expected)
        self.slippage_config = {
            'small_order': 0.0005,   # 0.05% for small orders
            'medium_order': 0.001,   # 0.1% for medium orders
            'large_order': 0.002,    # 0.2% for large orders
        }

        # Market hours impact (spreads widen at open/close)
        self.time_multipliers = {
            'market_open': 1.5,      # 9:15-10:00 AM
            'mid_day': 1.0,          # 10:00-14:30
            'market_close': 1.3,     # 14:30-15:30
        }

    def get_realistic_execution_price(
        self,
        symbol: str,
        side: str,
        base_price: float,
        quantity: int,
        timestamp: Optional[datetime] = None
    ) -> Dict:
        """
        Calculate realistic execution price with spreads and slippage

        Args:
            symbol: Trading symbol (e.g., 'NIFTY25OCT25000CE')
            side: 'buy' or 'sell'
            base_price: Mid price or LTP
            quantity: Order quantity
            timestamp: Time of trade (for time-of-day adjustments)

        Returns:
            Dict with execution_price, spread_cost, slippage_cost, total_impact
        """

        if base_price <= 0:
            logger.warning(f"Invalid base price {base_price} for {symbol}")
            return {
                'execution_price': base_price,
                'spread_cost': 0,
                'slippage_cost': 0,
                'total_impact': 0,
                'impact_pct': 0
            }

        # 1. Calculate bid-ask spread
        spread_pct = self._calculate_spread_percentage(symbol, base_price)

        # 2. Calculate slippage
        slippage_pct = self._calculate_slippage(symbol, quantity, base_price)

        # 3. Apply time-of-day multiplier
        if timestamp:
            time_multiplier = self._get_time_multiplier(timestamp)
            spread_pct *= time_multiplier

        # 4. Calculate costs
        spread_cost = base_price * (spread_pct / 2)  # Half-spread
        slippage_cost = base_price * slippage_pct

        # 5. Apply to buy/sell
        if side.lower() == 'buy':
            # Buy at ASK (higher) + slippage
            execution_price = base_price + spread_cost + slippage_cost
        else:  # sell
            # Sell at BID (lower) - slippage
            execution_price = base_price - spread_cost - slippage_cost

        # 6. Apply price floor to prevent negative prices (critical for deep OTM options)
        MIN_PRICE = 0.05  # Minimum ₹0.05 (NSE tick size for options)
        original_execution_price = execution_price

        if execution_price < MIN_PRICE:
            execution_price = MIN_PRICE
            logger.warning(
                f"⚠️ Price floor applied for {symbol}: "
                f"calculated ₹{original_execution_price:.2f} → clamped to ₹{MIN_PRICE:.2f} "
                f"(base: ₹{base_price:.2f}, spread: ₹{spread_cost:.2f}, slippage: ₹{slippage_cost:.2f})"
            )

        # Recalculate total impact after any adjustments (positive = worse fill for buys)
        total_impact = execution_price - base_price
        impact_pct = (total_impact / base_price) if base_price > 0 else 0

        logger.debug(
            f"Realistic pricing: {symbol} {side} @ ₹{base_price:.2f} → "
            f"₹{execution_price:.2f} (spread: ₹{spread_cost:.2f}, "
            f"slippage: ₹{slippage_cost:.2f}, total: {impact_pct*100:.2f}%)"
        )

        return {
            'execution_price': round(execution_price, 2),
            'spread_cost': round(spread_cost, 2),
            'slippage_cost': round(slippage_cost, 2),
            'total_impact': round(total_impact, 2),
            'impact_pct': round(impact_pct * 100, 3)
        }

    def _calculate_spread_percentage(self, symbol: str, price: float) -> float:
        """
        Calculate bid-ask spread based on symbol and price

        Rules:
        - ATM options (high price): Narrow spread
        - OTM options (medium price): Medium spread
        - Deep OTM (low price): Wide spread
        - Very illiquid (very low price): Very wide spread
        """

        # Check if it's an option
        is_option = any(x in symbol for x in ['CE', 'PE', 'NIFTY', 'BANK', 'SENSEX', 'MIDCP'])

        if not is_option:
            # Stock
            return self.spread_config['stock']

        # Option spread based on price (proxy for moneyness)
        if price > 150:
            # Deep ITM or high-priced ATM
            return self.spread_config['nifty_atm']
        elif price > 50:
            # ATM to slightly OTM
            return self.spread_config['nifty_atm']
        elif price > 20:
            # OTM
            return self.spread_config['nifty_otm']
        elif price > 5:
            # Deep OTM
            return self.spread_config['nifty_deep_otm']
        else:
            # Very deep OTM or illiquid
            return self.spread_config['illiquid']

    def _calculate_slippage(self, symbol: str, quantity: int, price: float) -> float:
        """
        Calculate slippage based on order size

        Larger orders = more slippage (market impact)
        """

        order_value = quantity * price

        # Categorize order size
        if order_value < 50000:  # < ₹50k
            return self.slippage_config['small_order']
        elif order_value < 200000:  # < ₹2L
            return self.slippage_config['medium_order']
        else:  # > ₹2L
            return self.slippage_config['large_order']

    def _get_time_multiplier(self, timestamp: datetime) -> float:
        """
        Get spread multiplier based on time of day

        Spreads are wider at market open/close due to volatility
        """

        current_time = timestamp.time()

        # Market open (9:15 - 10:00)
        if time(9, 15) <= current_time < time(10, 0):
            return self.time_multipliers['market_open']

        # Market close (14:30 - 15:30)
        elif time(14, 30) <= current_time <= time(15, 30):
            return self.time_multipliers['market_close']

        # Mid-day (normal)
        else:
            return self.time_multipliers['mid_day']

    def estimate_round_trip_cost(
        self,
        symbol: str,
        price: float,
        quantity: int
    ) -> Dict:
        """
        Estimate total cost of entry + exit (round trip)

        Useful for pre-trade analysis
        """

        # Entry cost
        entry = self.get_realistic_execution_price(symbol, 'buy', price, quantity)

        # Exit cost (assume same price for estimation)
        exit_result = self.get_realistic_execution_price(symbol, 'sell', price, quantity)

        # Total impact
        entry_cost = entry['total_impact']
        exit_cost = abs(exit_result['total_impact'])
        total_cost = entry_cost + exit_cost

        position_value = price * quantity
        cost_pct = (total_cost / position_value * 100) if position_value > 0 else 0

        return {
            'entry_cost': entry_cost,
            'exit_cost': exit_cost,
            'total_round_trip_cost': total_cost,
            'cost_pct': cost_pct,
            'position_value': position_value,
            'break_even_move_pct': cost_pct  # Need to move this much to break even
        }


class PricingAdjuster:
    """
    Helper class to adjust existing paper trading prices
    Can be integrated into existing trading system
    """

    def __init__(self):
        self.pricing_engine = RealisticPricingEngine()

    def adjust_paper_trade_price(
        self,
        original_price: float,
        symbol: str,
        side: str,
        quantity: int,
        timestamp: Optional[datetime] = None
    ) -> float:
        """
        Simple wrapper to get adjusted price

        Use this to replace paper trading prices in your existing code
        """

        result = self.pricing_engine.get_realistic_execution_price(
            symbol=symbol,
            side=side,
            base_price=original_price,
            quantity=quantity,
            timestamp=timestamp or datetime.now()
        )

        return result['execution_price']


# Convenience function for easy integration
def get_realistic_price(
    symbol: str,
    side: str,
    base_price: float,
    quantity: int = 1
) -> float:
    """
    Quick function to get realistic price

    Usage:
        real_price = get_realistic_price('NIFTY25OCT25000CE', 'buy', 150.0, 50)
    """
    adjuster = PricingAdjuster()
    return adjuster.adjust_paper_trade_price(base_price, symbol, side, quantity)


# Testing
if __name__ == "__main__":
    print("="*80)
    print("REALISTIC PRICING ENGINE - TEST")
    print("="*80)

    engine = RealisticPricingEngine()

    # Test cases
    test_cases = [
        {'symbol': 'NIFTY25OCT25000CE', 'side': 'buy', 'price': 150.0, 'qty': 50, 'desc': 'ATM Call'},
        {'symbol': 'NIFTY25OCT25500CE', 'side': 'buy', 'price': 50.0, 'qty': 50, 'desc': 'OTM Call'},
        {'symbol': 'NIFTY25OCT26000CE', 'side': 'buy', 'price': 10.0, 'qty': 50, 'desc': 'Deep OTM Call'},
        {'symbol': 'NIFTY25OCT25000CE', 'side': 'sell', 'price': 150.0, 'qty': 50, 'desc': 'ATM Call (Sell)'},
        {'symbol': 'RELIANCE', 'side': 'buy', 'price': 2800.0, 'qty': 10, 'desc': 'Stock'},
    ]

    for test in test_cases:
        result = engine.get_realistic_execution_price(
            test['symbol'], test['side'], test['price'], test['qty']
        )

        print(f"\n{test['desc']}:")
        print(f"  Base Price:       ₹{test['price']:.2f}")
        print(f"  Execution Price:  ₹{result['execution_price']:.2f}")
        print(f"  Spread Cost:      ₹{result['spread_cost']:.2f}")
        print(f"  Slippage Cost:    ₹{result['slippage_cost']:.2f}")
        print(f"  Total Impact:     ₹{result['total_impact']:.2f} ({result['impact_pct']:.2f}%)")

        # Round trip cost
        rt = engine.estimate_round_trip_cost(test['symbol'], test['price'], test['qty'])
        print(f"  Round-trip Cost:  ₹{rt['total_round_trip_cost']:.2f} ({rt['cost_pct']:.2f}%)")
        print(f"  Break-even Move:  {rt['break_even_move_pct']:.2f}%")

    print("\n" + "="*80)
    print("✅ Realistic pricing will reduce paper trading profits by 1-3%")
    print("✅ This makes results closer to live trading")
    print("="*80)
