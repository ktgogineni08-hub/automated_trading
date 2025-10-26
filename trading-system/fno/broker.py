#!/usr/bin/env python3
"""
FNO Broker Integration
Margin management and order execution for F&O trades
"""

from typing import Dict, Optional
import logging

from fno.options import OptionContract

logger = logging.getLogger('trading_system.fno.broker')


class FNOBroker:
    """Handles F&O trading operations and risk management"""

    def __init__(self, initial_margin: float = 100000):
        self.initial_margin = initial_margin
        self.available_margin = initial_margin
        self.positions: Dict[str, Dict] = {}
        self.total_margin_used = 0.0

    def calculate_margin_requirement(self, strategy: str, premium: float, quantity: int) -> float:
        """Calculate margin requirement for different strategies"""
        if strategy == 'straddle':
            # For straddle, margin is higher of the two legs
            return premium * quantity * 0.3  # 30% of premium
        elif strategy == 'iron_condor':
            # For iron condor, margin is the max loss
            return premium * quantity * 0.2  # 20% of premium
        else:
            return premium * quantity * 0.25  # Default 25%

    def can_place_order(self, margin_required: float) -> bool:
        """Check if sufficient margin is available"""
        return self.available_margin >= margin_required

    def place_option_order(self, option: OptionContract, quantity: int, side: str) -> bool:
        """Place option order"""
        try:
            # Mock order placement
            order_value = option.last_price * quantity * option.lot_size

            if side == 'buy':
                margin_required = self.calculate_margin_requirement('option_buy', option.last_price, quantity)
                if not self.can_place_order(margin_required):
                    return False

                self.available_margin -= margin_required
                self.total_margin_used += margin_required

                self.positions[option.symbol] = {
                    'option': option,
                    'quantity': quantity,
                    'side': side,
                    'entry_price': option.last_price,
                    'margin_used': margin_required
                }

                logger.info(f"📈 BOUGHT {quantity} lots of {option.symbol} @ {option.last_price}")
                return True

            elif side == 'sell':
                # For selling, need to check if we have the position
                if option.symbol not in self.positions:
                    return False

                position = self.positions[option.symbol]
                if position['side'] == 'buy' and position['quantity'] >= quantity:
                    # Close the position
                    pnl = (option.last_price - position['entry_price']) * quantity * option.lot_size
                    self.available_margin += position['margin_used']
                    self.total_margin_used -= position['margin_used']

                    del self.positions[option.symbol]

                    logger.info(f"📉 SOLD {quantity} lots of {option.symbol} @ {option.last_price} | P&L: {pnl:.2f}")
                    return True

                return False

        except Exception as e:
            logger.error(f"Error placing option order: {e}")
            return False

class ImpliedVolatilityAnalyzer:
    """Analyzes implied volatility for trading decisions"""

