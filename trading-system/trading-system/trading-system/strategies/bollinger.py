#!/usr/bin/env python3
"""
Bollinger Bands Strategy
Volatility-based mean reversion strategy
"""

import pandas as pd
import numpy as np
from typing import Dict
from strategies.base import BaseStrategy
from trading_utils import safe_float_conversion
import logging

logger = logging.getLogger('trading_system.strategies.bollinger')


class BollingerBandsStrategy(BaseStrategy):
    """
    Bollinger Bands Mean Reversion Strategy

    Uses standard deviation bands around a moving average to identify
    overbought and oversold conditions.

    Default settings:
    - Period: 20 (SMA calculation)
    - Standard Deviation: 2 (band width)

    Signals:
    - Buy: Price touches or breaks below lower band (oversold)
    - Sell: Price touches or breaks above upper band (overbought)
    - Hold: Price within bands

    Signal strength increases with distance from bands.
    """

    def __init__(self, period: int = 20, std_dev: float = 2):
        super().__init__("Bollinger_Bands")
        self.period = period
        self.std_dev = std_dev

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> Dict:
        """
        Generate signals based on Bollinger Band position

        Args:
            data: OHLCV DataFrame
            symbol: Trading symbol (for logging)

        Returns:
            Dict with signal (1=buy, -1=sell, 0=hold), strength (0-1), reason
        """
        if not self.validate_data(data) or len(data) < self.period + 5:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}

        try:
            # Calculate Bollinger Bands
            close_prices = data['close']
            sma = close_prices.rolling(self.period).mean()
            std = close_prices.rolling(self.period).std()

            # Handle zero standard deviation (replace with NaN to avoid invalid bands)
            std = std.replace(0, np.nan)

            upper_band = sma + (std * self.std_dev)
            lower_band = sma - (std * self.std_dev)

            # Get current values
            current_price = safe_float_conversion(close_prices.iloc[-1])
            current_upper = safe_float_conversion(upper_band.iloc[-1])
            current_lower = safe_float_conversion(lower_band.iloc[-1])

            # Validate bands
            if not current_upper or not current_lower or current_upper <= current_lower:
                return {'signal': 0, 'strength': 0.0, 'reason': 'invalid_bands'}

            # Generate signals based on band position
            if current_price <= current_lower:
                # Price at or below lower band - oversold
                strength = min((current_lower - current_price) / current_lower * 100, 1.0)
                return {
                    'signal': 1,
                    'strength': strength,
                    'reason': 'oversold_at_lower_band'
                }
            elif current_price >= current_upper:
                # Price at or above upper band - overbought
                strength = min((current_price - current_upper) / current_upper * 100, 1.0)
                return {
                    'signal': -1,
                    'strength': strength,
                    'reason': 'overbought_at_upper_band'
                }

            # Price within bands - no signal
            return {'signal': 0, 'strength': 0.0, 'reason': 'no_signal'}
        except Exception as e:
            logger.error(f"Error in Bollinger Bands strategy for {symbol}: {e}")
            return {'signal': 0, 'strength': 0.0, 'reason': 'error'}
