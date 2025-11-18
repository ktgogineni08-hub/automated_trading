#!/usr/bin/env python3
"""
Moving Average Crossover Strategy
Implements fast EMA crossover for trend detection
"""

import pandas as pd
from typing import Dict
from strategies.base import BaseStrategy
from trading_utils import safe_float_conversion, safe_divide
import logging

logger = logging.getLogger('trading_system.strategies.ma')


class ImprovedMovingAverageCrossover(BaseStrategy):
    """
    Fast Moving Average Crossover Strategy

    Uses exponential moving averages (EMA) for quicker response to price changes.
    Short window default: 3 periods
    Long window default: 10 periods

    Signals:
    - Bullish crossover: Short EMA crosses above long EMA
    - Bearish crossover: Short EMA crosses below long EMA
    - Trend continuation: Separation maintained above threshold
    """

    def __init__(self, short_window: int = 3, long_window: int = 10):
        super().__init__("Fast_MA_Crossover")
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> Dict:
        """
        Generate signals based on EMA crossover

        Args:
            data: OHLCV DataFrame
            symbol: Trading symbol (for logging)

        Returns:
            Dict with signal (1=buy, -1=sell, 0=hold), strength (0-1), reason
        """
        if not self.validate_data(data) or len(data) < self.long_window + 5:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}

        try:
            # Calculate EMAs
            ema_short = data["close"].ewm(span=self.short_window, adjust=False).mean()
            ema_long = data["close"].ewm(span=self.long_window, adjust=False).mean()

            # Get current and previous values
            current_short = safe_float_conversion(ema_short.iloc[-1])
            current_long = safe_float_conversion(ema_long.iloc[-1])
            prev_short = safe_float_conversion(ema_short.iloc[-2])
            prev_long = safe_float_conversion(ema_long.iloc[-2])

            # Check crossover conditions
            currently_above = current_short > current_long
            previously_above = prev_short > prev_long

            bullish_cross = not previously_above and currently_above
            bearish_cross = previously_above and not currently_above

            # Calculate separation strength
            separation = safe_divide(abs(current_short - current_long), current_long, 0.0)
            strength = min(separation * 100, 1.0)

            # Generate signals
            if bullish_cross and strength > 0.1:
                return {'signal': 1, 'strength': strength, 'reason': 'bullish_crossover'}
            elif bearish_cross and strength > 0.1:
                return {'signal': -1, 'strength': strength, 'reason': 'bearish_crossover'}
            elif currently_above and separation > 0.003:
                return {'signal': 1, 'strength': strength * 0.8, 'reason': 'bullish_trend'}
            elif not currently_above and separation > 0.003:
                return {'signal': -1, 'strength': strength * 0.8, 'reason': 'bearish_trend'}

            return {'signal': 0, 'strength': 0.0, 'reason': 'no_signal'}
        except Exception as e:
            logger.error(f"Error in MA Crossover strategy for {symbol}: {e}")
            return {'signal': 0, 'strength': 0.0, 'reason': 'error'}
