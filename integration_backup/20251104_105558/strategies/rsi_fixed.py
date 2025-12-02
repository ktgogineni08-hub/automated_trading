#!/usr/bin/env python3
"""
FIXED Enhanced RSI Strategy
Relative Strength Index momentum strategy with exit logic

FIXES APPLIED:
1. Added exit logic (exit when RSI returns to neutral zone)
2. Added position awareness (different signals when holding)
3. Added debouncing (prevents repeated signals at same level)
4. Added RSI divergence detection
5. Improved signal strength calculation
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from strategies.base import BaseStrategy
from trading_utils import safe_float_conversion
import logging
from datetime import datetime, timedelta

logger = logging.getLogger('trading_system.strategies.rsi')


class EnhancedRSIStrategy(BaseStrategy):
    """
    FIXED Enhanced Relative Strength Index Strategy

    Improvements over original:
    - Exit logic: Exit when RSI crosses back to neutral zone (30-70)
    - Position awareness: Different behavior when holding position
    - Debouncing: Prevents repeated signals at same RSI level
    - Divergence detection: Identifies price/RSI divergences
    - Better signal strength: Based on RSI distance from extreme

    Default settings:
    - Period: 7 (faster response)
    - Oversold: 25 (buy signal threshold)
    - Overbought: 75 (sell signal threshold)
    - Neutral exit: 50 (exit threshold)
    - Cooldown: 15 minutes

    Signals:
    - Buy: RSI <= 25 (oversold)
    - Sell: RSI >= 75 (overbought)
    - Exit Long: RSI crosses above 50 (neutral)
    - Exit Short: RSI crosses below 50 (neutral)
    """

    def __init__(
        self,
        period: int = 7,
        oversold: int = 25,
        overbought: int = 75,
        neutral: int = 50,
        cooldown_minutes: int = 15
    ):
        super().__init__("Enhanced_RSI_Fixed")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.neutral = neutral
        self.cooldown_minutes = cooldown_minutes

        # Track last signal time and RSI level per symbol (debouncing)
        self.last_signal_time: Dict[str, datetime] = {}
        self.last_signal_rsi: Dict[str, float] = {}

        # Track current position per symbol (position awareness)
        self.current_position: Dict[str, int] = {}  # 1=long, -1=short, 0=flat

    def _is_on_cooldown(self, symbol: str, current_rsi: float) -> bool:
        """
        Check if symbol is on signal cooldown

        Cooldown applies if:
        - Less than cooldown_minutes since last signal
        - RSI hasn't moved significantly from last signal level
        """
        if symbol not in self.last_signal_time:
            return False

        time_since_last = datetime.now() - self.last_signal_time[symbol]
        time_cooldown = time_since_last < timedelta(minutes=self.cooldown_minutes)

        # Also check if RSI has moved significantly
        if symbol in self.last_signal_rsi:
            rsi_diff = abs(current_rsi - self.last_signal_rsi[symbol])
            rsi_stuck = rsi_diff < 5  # RSI hasn't moved >5 points
        else:
            rsi_stuck = False

        return time_cooldown and rsi_stuck

    def _update_signal_state(self, symbol: str, rsi: float):
        """Update last signal time and RSI level"""
        self.last_signal_time[symbol] = datetime.now()
        self.last_signal_rsi[symbol] = rsi

    def set_position(self, symbol: str, position: int):
        """
        Update current position for symbol

        Args:
            symbol: Trading symbol
            position: 1=long, -1=short, 0=flat
        """
        self.current_position[symbol] = position

    def get_position(self, symbol: str) -> int:
        """Get current position for symbol"""
        return self.current_position.get(symbol, 0)

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> Dict:
        """
        Generate signals based on RSI levels with exit logic

        Args:
            data: OHLCV DataFrame
            symbol: Trading symbol (for logging)

        Returns:
            Dict with signal (1=buy, -1=sell, 0=hold), strength (0-1), reason
        """
        if not self.validate_data(data) or len(data) < self.period + 10:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}

        # Use 'unknown' if no symbol provided
        if symbol is None:
            symbol = 'unknown'

        try:
            # Calculate RSI
            delta = data["close"].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)

            avg_gain = gain.ewm(span=self.period, adjust=False).mean()
            avg_loss = loss.ewm(span=self.period, adjust=False).mean()

            # Avoid division by zero
            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))

            current_rsi = safe_float_conversion(rsi.iloc[-1], 50.0)
            prev_rsi = safe_float_conversion(rsi.iloc[-2], 50.0) if len(rsi) >= 2 else current_rsi

            # Check cooldown
            if self._is_on_cooldown(symbol, current_rsi):
                return {'signal': 0, 'strength': 0.0, 'reason': 'cooldown'}

            # Get current position
            position = self.get_position(symbol)

            # EXIT LOGIC (New feature)
            if position != 0:
                exit_signal = self._check_exit_conditions(
                    position, current_rsi, prev_rsi
                )
                if exit_signal:
                    self._update_signal_state(symbol, current_rsi)
                    return exit_signal

            # ENTRY LOGIC
            # Oversold - buy signal
            if current_rsi <= self.oversold:
                # Calculate strength based on how oversold
                strength = max(0, (self.oversold - current_rsi) / self.oversold)
                strength = min(strength * 2, 1.0)  # Amplify but cap at 1.0

                # Check for bullish divergence (price makes new low, RSI doesn't)
                divergence = self._check_bullish_divergence(data, rsi)

                reason = f'oversold_{current_rsi:.0f}'
                if divergence:
                    reason += '_bullish_divergence'
                    strength = min(strength * 1.2, 1.0)  # Boost signal

                self._update_signal_state(symbol, current_rsi)
                return {
                    'signal': 1,
                    'strength': strength,
                    'reason': reason
                }

            # Overbought - sell signal
            elif current_rsi >= self.overbought:
                # Calculate strength based on how overbought
                strength = max(0, (current_rsi - self.overbought) / (100 - self.overbought))
                strength = min(strength * 2, 1.0)  # Amplify but cap at 1.0

                # Check for bearish divergence (price makes new high, RSI doesn't)
                divergence = self._check_bearish_divergence(data, rsi)

                reason = f'overbought_{current_rsi:.0f}'
                if divergence:
                    reason += '_bearish_divergence'
                    strength = min(strength * 1.2, 1.0)  # Boost signal

                self._update_signal_state(symbol, current_rsi)
                return {
                    'signal': -1,
                    'strength': strength,
                    'reason': reason
                }

            # Neutral zone
            return {'signal': 0, 'strength': 0.0, 'reason': 'neutral'}

        except Exception as e:
            logger.error(f"Error in RSI strategy for {symbol}: {e}", exc_info=True)
            return {'signal': 0, 'strength': 0.0, 'reason': 'error'}

    def _check_exit_conditions(
        self,
        position: int,
        current_rsi: float,
        prev_rsi: float
    ) -> Optional[Dict]:
        """
        Check if exit conditions are met

        Exit long: RSI crosses above neutral (50)
        Exit short: RSI crosses below neutral (50)

        Args:
            position: Current position (1=long, -1=short)
            current_rsi: Current RSI value
            prev_rsi: Previous RSI value

        Returns:
            Exit signal dict or None
        """
        # Exit long position (bought at oversold, exit at neutral)
        if position == 1:
            # RSI crossed above neutral from below
            if prev_rsi <= self.neutral and current_rsi > self.neutral:
                return {
                    'signal': -1,  # Sell to exit
                    'strength': 0.7,
                    'reason': f'exit_long_rsi_{current_rsi:.0f}'
                }
            # Also exit if RSI reaches overbought (strong profit)
            elif current_rsi >= self.overbought:
                return {
                    'signal': -1,
                    'strength': 0.9,
                    'reason': f'exit_long_overbought_{current_rsi:.0f}'
                }

        # Exit short position (sold at overbought, exit at neutral)
        elif position == -1:
            # RSI crossed below neutral from above
            if prev_rsi >= self.neutral and current_rsi < self.neutral:
                return {
                    'signal': 1,  # Buy to cover
                    'strength': 0.7,
                    'reason': f'exit_short_rsi_{current_rsi:.0f}'
                }
            # Also exit if RSI reaches oversold (strong profit)
            elif current_rsi <= self.oversold:
                return {
                    'signal': 1,
                    'strength': 0.9,
                    'reason': f'exit_short_oversold_{current_rsi:.0f}'
                }

        return None

    def _check_bullish_divergence(self, data: pd.DataFrame, rsi: pd.Series, lookback: int = 5) -> bool:
        """
        Check for bullish divergence (price makes lower low, RSI doesn't)

        Args:
            data: OHLCV DataFrame
            rsi: RSI series
            lookback: Bars to look back

        Returns:
            True if bullish divergence detected
        """
        if len(data) < lookback + 1 or len(rsi) < lookback + 1:
            return False

        try:
            recent_prices = data['close'].tail(lookback + 1)
            recent_rsi = rsi.tail(lookback + 1)

            # Check if price made lower low
            current_price = recent_prices.iloc[-1]
            min_price_idx = recent_prices.iloc[:-1].idxmin()
            min_price = recent_prices.loc[min_price_idx]

            if current_price < min_price:
                # Price made lower low - check if RSI made higher low
                current_rsi = recent_rsi.iloc[-1]
                min_rsi = recent_rsi.loc[min_price_idx]

                return current_rsi > min_rsi  # Bullish divergence

        except Exception:
            pass

        return False

    def _check_bearish_divergence(self, data: pd.DataFrame, rsi: pd.Series, lookback: int = 5) -> bool:
        """
        Check for bearish divergence (price makes higher high, RSI doesn't)

        Args:
            data: OHLCV DataFrame
            rsi: RSI series
            lookback: Bars to look back

        Returns:
            True if bearish divergence detected
        """
        if len(data) < lookback + 1 or len(rsi) < lookback + 1:
            return False

        try:
            recent_prices = data['close'].tail(lookback + 1)
            recent_rsi = rsi.tail(lookback + 1)

            # Check if price made higher high
            current_price = recent_prices.iloc[-1]
            max_price_idx = recent_prices.iloc[:-1].idxmax()
            max_price = recent_prices.loc[max_price_idx]

            if current_price > max_price:
                # Price made higher high - check if RSI made lower high
                current_rsi = recent_rsi.iloc[-1]
                max_rsi = recent_rsi.loc[max_price_idx]

                return current_rsi < max_rsi  # Bearish divergence

        except Exception:
            pass

        return False

    def reset(self):
        """Reset strategy state (useful for backtesting)"""
        self.last_signal_time.clear()
        self.last_signal_rsi.clear()
        self.current_position.clear()
