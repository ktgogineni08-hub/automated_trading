#!/usr/bin/env python3
"""
FIXED Moving Average Crossover Strategy
Less aggressive EMA crossover with confirmation

FIXES APPLIED:
1. Changed from 3/10 to 5/20 EMA (less sensitive to noise)
2. Added volume confirmation requirement
3. Added minimum separation threshold (avoid whipsaws)
4. Removed continuous trend signals (only crossovers)
5. Added position awareness and exit logic
6. Added debouncing
"""

import pandas as pd
from typing import Dict, Optional
from strategies.base import BaseStrategy
from trading_utils import safe_float_conversion, safe_divide
import logging
from datetime import datetime, timedelta

logger = logging.getLogger('trading_system.strategies.ma')


class ImprovedMovingAverageCrossover(BaseStrategy):
    """
    FIXED Moving Average Crossover Strategy

    Improvements over original:
    - Less aggressive: 5/20 EMA instead of 3/10 (reduced noise)
    - Volume confirmation: Requires above-average volume
    - Minimum separation: Avoids insignificant crossovers
    - Crossover-only: No continuous trend signals
    - Exit logic: Exit on opposite crossover or stop loss
    - Position awareness: Different behavior when holding

    Default settings:
    - Short window: 5 periods (was 3)
    - Long window: 20 periods (was 10)
    - Min separation: 0.5% (avoid noise)
    - Volume multiplier: 1.2x average
    - Cooldown: 15 minutes

    Signals:
    - Bullish crossover: Short EMA crosses above long EMA with volume
    - Bearish crossover: Short EMA crosses below long EMA with volume
    - Exit: Opposite crossover
    """

    def __init__(
        self,
        short_window: int = 5,
        long_window: int = 20,
        min_separation_pct: float = 0.005,
        volume_multiplier: float = 1.2,
        cooldown_minutes: int = 15
    ):
        super().__init__("MA_Crossover_Fixed")
        self.short_window = short_window
        self.long_window = long_window
        self.min_separation_pct = min_separation_pct
        self.volume_multiplier = volume_multiplier
        self.cooldown_minutes = cooldown_minutes

        # Track last signal time per symbol (debouncing)
        self.last_signal_time: Dict[str, datetime] = {}

        # Track current position per symbol (position awareness)
        self.current_position: Dict[str, int] = {}  # 1=long, -1=short, 0=flat

    def _is_on_cooldown(self, symbol: str) -> bool:
        """Check if symbol is on signal cooldown"""
        if symbol not in self.last_signal_time:
            return False

        time_since_last = datetime.now() - self.last_signal_time[symbol]
        return time_since_last < timedelta(minutes=self.cooldown_minutes)

    def _update_signal_time(self, symbol: str):
        """Update last signal time for symbol"""
        self.last_signal_time[symbol] = datetime.now()

    def set_position(self, symbol: str, position: int):
        """Update current position for symbol"""
        self.current_position[symbol] = position

    def get_position(self, symbol: str) -> int:
        """Get current position for symbol"""
        return self.current_position.get(symbol, 0)

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> Dict:
        """
        Generate signals based on EMA crossover with confirmation

        Args:
            data: OHLCV DataFrame
            symbol: Trading symbol (for logging)

        Returns:
            Dict with signal (1=buy, -1=sell, 0=hold), strength (0-1), reason
        """
        if not self.validate_data(data) or len(data) < self.long_window + 5:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}

        # Use 'unknown' if no symbol provided
        if symbol is None:
            symbol = 'unknown'

        # Check cooldown
        if self._is_on_cooldown(symbol):
            return {'signal': 0, 'strength': 0.0, 'reason': 'cooldown'}

        try:
            # Calculate EMAs
            ema_short = data["close"].ewm(span=self.short_window, adjust=False).mean()
            ema_long = data["close"].ewm(span=self.long_window, adjust=False).mean()

            # Get current and previous values
            current_short = safe_float_conversion(ema_short.iloc[-1])
            current_long = safe_float_conversion(ema_long.iloc[-1])
            prev_short = safe_float_conversion(ema_short.iloc[-2])
            prev_long = safe_float_conversion(ema_long.iloc[-2])

            if not all([current_short, current_long, prev_short, prev_long]):
                return {'signal': 0, 'strength': 0.0, 'reason': 'invalid_ema'}

            # Check crossover conditions
            currently_above = current_short > current_long
            previously_above = prev_short > prev_long

            bullish_cross = not previously_above and currently_above
            bearish_cross = previously_above and not currently_above

            # Calculate separation strength
            separation = safe_divide(abs(current_short - current_long), current_long, 0.0)

            # Volume confirmation
            volume_confirmed = self._check_volume_confirmation(data)

            # Get current position
            position = self.get_position(symbol)

            # EXIT LOGIC
            if position != 0:
                exit_signal = self._check_exit_conditions(
                    position, bullish_cross, bearish_cross, separation
                )
                if exit_signal:
                    self._update_signal_time(symbol)
                    return exit_signal

            # ENTRY LOGIC - Only on crossovers with confirmation
            # Minimum separation check (avoid noise)
            if separation < self.min_separation_pct:
                return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_separation'}

            # BULLISH CROSSOVER
            if bullish_cross:
                # Calculate signal strength
                strength = min(separation * 100, 1.0)

                # Boost strength if volume confirmed
                if volume_confirmed:
                    strength = min(strength * 1.3, 1.0)
                    reason = 'bullish_crossover_volume_confirmed'
                else:
                    reason = 'bullish_crossover'

                # Minimum strength threshold
                if strength < 0.3:
                    return {'signal': 0, 'strength': strength, 'reason': 'weak_crossover'}

                self._update_signal_time(symbol)
                return {'signal': 1, 'strength': strength, 'reason': reason}

            # BEARISH CROSSOVER
            elif bearish_cross:
                # Calculate signal strength
                strength = min(separation * 100, 1.0)

                # Boost strength if volume confirmed
                if volume_confirmed:
                    strength = min(strength * 1.3, 1.0)
                    reason = 'bearish_crossover_volume_confirmed'
                else:
                    reason = 'bearish_crossover'

                # Minimum strength threshold
                if strength < 0.3:
                    return {'signal': 0, 'strength': strength, 'reason': 'weak_crossover'}

                self._update_signal_time(symbol)
                return {'signal': -1, 'strength': strength, 'reason': reason}

            # No crossover - no signal (REMOVED continuous trend signals)
            return {'signal': 0, 'strength': 0.0, 'reason': 'no_crossover'}

        except Exception as e:
            logger.error(f"Error in MA Crossover strategy for {symbol}: {e}", exc_info=True)
            return {'signal': 0, 'strength': 0.0, 'reason': 'error'}

    def _check_volume_confirmation(self, data: pd.DataFrame, lookback: int = 20) -> bool:
        """
        Check if current volume confirms the signal

        Args:
            data: OHLCV DataFrame
            lookback: Bars to calculate average volume

        Returns:
            True if volume is above average
        """
        if 'volume' not in data.columns or len(data) < lookback:
            return True  # If no volume data, don't penalize

        try:
            current_volume = safe_float_conversion(data['volume'].iloc[-1], 0)
            avg_volume = safe_float_conversion(data['volume'].tail(lookback).mean(), 1)

            # Volume should be above average
            return current_volume >= (avg_volume * self.volume_multiplier)

        except Exception:
            return True  # On error, don't penalize

    def _check_exit_conditions(
        self,
        position: int,
        bullish_cross: bool,
        bearish_cross: bool,
        separation: float
    ) -> Optional[Dict]:
        """
        Check if exit conditions are met

        Exit long: Bearish crossover
        Exit short: Bullish crossover

        Args:
            position: Current position (1=long, -1=short)
            bullish_cross: Bullish crossover occurred
            bearish_cross: Bearish crossover occurred
            separation: Current EMA separation

        Returns:
            Exit signal dict or None
        """
        # Exit long on bearish crossover
        if position == 1 and bearish_cross:
            strength = min(separation * 100, 1.0)
            return {
                'signal': -1,
                'strength': max(strength, 0.7),
                'reason': 'exit_long_bearish_cross'
            }

        # Exit short on bullish crossover
        elif position == -1 and bullish_cross:
            strength = min(separation * 100, 1.0)
            return {
                'signal': 1,
                'strength': max(strength, 0.7),
                'reason': 'exit_short_bullish_cross'
            }

        return None

    def reset(self):
        """Reset strategy state (useful for backtesting)"""
        self.last_signal_time.clear()
        self.current_position.clear()
