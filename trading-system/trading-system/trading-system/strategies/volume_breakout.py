#!/usr/bin/env python3
"""
Volume Breakout Strategy
Identifies significant price moves confirmed by volume spikes
"""

import pandas as pd
from typing import Dict
from strategies.base import BaseStrategy
from trading_utils import safe_float_conversion
import logging

logger = logging.getLogger('trading_system.strategies.volume_breakout')


class ImprovedVolumeBreakoutStrategy(BaseStrategy):
    """
    Volume-Confirmed Price Breakout Strategy

    Detects significant price movements that are confirmed by high volume,
    indicating strong market conviction behind the move.

    Default settings:
    - Volume multiplier: 1.3 (30% above 20-day average)
    - Price threshold: 0.001 (0.1% price change)

    Signals:
    - Buy: High volume + price increase > threshold
    - Sell: High volume + price decrease > threshold
    - Hold: Normal volume or small price changes

    Signal strength combines volume ratio and price change magnitude.
    """

    def __init__(self, volume_multiplier: float = 1.3, price_threshold: float = 0.001):
        super().__init__("Volume_Price_Breakout")
        self.volume_multiplier = volume_multiplier
        self.price_threshold = price_threshold

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> Dict:
        """
        Generate signals based on volume-confirmed price breakouts

        Args:
            data: OHLCV DataFrame
            symbol: Trading symbol (for logging)

        Returns:
            Dict with signal (1=buy, -1=sell, 0=hold), strength (0-1), reason
        """
        if not self.validate_data(data) or len(data) < 20:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}

        try:
            # Calculate volume metrics
            vol_avg = safe_float_conversion(data['volume'].rolling(20).mean().iloc[-1])
            current_vol = safe_float_conversion(data['volume'].iloc[-1])

            # Calculate price change
            prev_close = safe_float_conversion(data['close'].iloc[-2])
            current_close = safe_float_conversion(data['close'].iloc[-1])

            if prev_close > 0:
                price_change = (current_close - prev_close) / prev_close
            else:
                price_change = 0.0

            # Check for volume breakout
            if current_vol > 0 and vol_avg > 0 and current_vol > vol_avg * self.volume_multiplier:
                if price_change > self.price_threshold:
                    # Bullish breakout: high volume + price up
                    strength = min((current_vol / vol_avg - 1) * 0.3 + abs(price_change) * 50, 1.0)
                    return {
                        'signal': 1,
                        'strength': strength,
                        'reason': 'volume_breakout_up'
                    }
                elif price_change < -self.price_threshold:
                    # Bearish breakout: high volume + price down
                    strength = min((current_vol / vol_avg - 1) * 0.3 + abs(price_change) * 50, 1.0)
                    return {
                        'signal': -1,
                        'strength': strength,
                        'reason': 'volume_breakout_down'
                    }

            # No significant volume or price movement
            return {'signal': 0, 'strength': 0.0, 'reason': 'no_volume_signal'}
        except Exception as e:
            logger.error(f"Error in Volume Breakout strategy for {symbol}: {e}")
            return {'signal': 0, 'strength': 0.0, 'reason': 'error'}
