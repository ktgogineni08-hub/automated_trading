#!/usr/bin/env python3
"""
Enhanced RSI Strategy
Relative Strength Index momentum strategy with customizable thresholds
"""

import pandas as pd
import numpy as np
from typing import Dict
from strategies.base import BaseStrategy
from trading_utils import safe_float_conversion
import logging

logger = logging.getLogger('trading_system.strategies.rsi')


class EnhancedRSIStrategy(BaseStrategy):
    """
    Enhanced Relative Strength Index Strategy

    Uses RSI to identify overbought and oversold conditions.
    Default settings:
    - Period: 7 (faster response)
    - Oversold: 25 (buy signal)
    - Overbought: 75 (sell signal)

    Signals:
    - Buy: RSI <= oversold threshold
    - Sell: RSI >= overbought threshold
    - Hold: RSI in neutral zone

    Signal strength increases with distance from threshold.
    """

    def __init__(self, period: int = 7, oversold: int = 25, overbought: int = 75):
        super().__init__("Enhanced_RSI")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> Dict:
        """
        Generate signals based on RSI levels

        Args:
            data: OHLCV DataFrame
            symbol: Trading symbol (for logging)

        Returns:
            Dict with signal (1=buy, -1=sell, 0=hold), strength (0-1), reason
        """
        if not self.validate_data(data) or len(data) < self.period + 5:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}

        try:
            # Calculate RSI
            delta = data["close"].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)

            avg_gain = gain.ewm(span=self.period, adjust=False).mean()
            avg_loss = loss.ewm(span=self.period, adjust=False).mean()

            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))

            current_rsi = safe_float_conversion(rsi.iloc[-1], 50.0)

            # Generate signals based on RSI levels
            if current_rsi <= self.oversold:
                # Oversold - buy signal
                strength = max(0, (self.oversold - current_rsi) / self.oversold)
                return {
                    'signal': 1,
                    'strength': min(strength * 2, 1.0),
                    'reason': f'oversold_{current_rsi:.0f}'
                }
            elif current_rsi >= self.overbought:
                # Overbought - sell signal
                strength = max(0, (current_rsi - self.overbought) / (100 - self.overbought))
                return {
                    'signal': -1,
                    'strength': min(strength * 2, 1.0),
                    'reason': f'overbought_{current_rsi:.0f}'
                }

            # Neutral zone
            return {'signal': 0, 'strength': 0.0, 'reason': 'neutral'}
        except Exception as e:
            logger.error(f"Error in RSI strategy for {symbol}: {e}")
            return {'signal': 0, 'strength': 0.0, 'reason': 'error'}
