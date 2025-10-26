#!/usr/bin/env python3
"""
FIXED Bollinger Bands Strategy
Volatility-based mean reversion strategy with signal confirmation

FIXES APPLIED:
1. Added confirmation mechanism (requires 2-bar confirmation)
2. Added debouncing (prevents repeated signals)
3. Fixed division by zero handling
4. Added exit logic
5. Added position awareness
6. Improved signal strength calculation
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from strategies.base import BaseStrategy
from trading_utils import safe_float_conversion
import logging
from datetime import datetime, timedelta

logger = logging.getLogger('trading_system.strategies.bollinger')


class BollingerBandsStrategy(BaseStrategy):
    """
    FIXED Bollinger Bands Mean Reversion Strategy

    Improvements over original:
    - Requires confirmation: 2 bars touching/breaking bands
    - Debouncing: Minimum 15-minute cooldown between signals
    - Exit logic: Exit when price crosses middle band
    - Position aware: Different signals when holding vs not holding
    - Better error handling: Properly handles invalid bands

    Default settings:
    - Period: 20 (SMA calculation)
    - Standard Deviation: 2 (band width)
    - Confirmation bars: 2 (require 2-bar confirmation)
    - Cooldown: 15 minutes (prevent overtrading)

    Signals:
    - Buy: Price touches/breaks lower band for 2+ bars
    - Sell: Price touches/breaks upper band for 2+ bars
    - Exit Long: Price crosses above middle band
    - Exit Short: Price crosses below middle band
    """

    def __init__(self, period: int = 20, std_dev: float = 2, confirmation_bars: int = 2, cooldown_minutes: int = 15):
        super().__init__("Bollinger_Bands_Fixed")
        self.period = period
        self.std_dev = std_dev
        self.confirmation_bars = confirmation_bars
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
        Generate signals based on Bollinger Band position with confirmation

        Args:
            data: OHLCV DataFrame
            symbol: Trading symbol (for logging and cooldown tracking)

        Returns:
            Dict with signal (1=buy, -1=sell, 0=hold), strength (0-1), reason
        """
        if not self.validate_data(data) or len(data) < self.period + self.confirmation_bars + 5:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}

        # Use 'unknown' if no symbol provided
        if symbol is None:
            symbol = 'unknown'

        # Check cooldown (debouncing)
        if self._is_on_cooldown(symbol):
            return {'signal': 0, 'strength': 0.0, 'reason': 'cooldown'}

        try:
            # Calculate Bollinger Bands
            close_prices = data['close']
            sma = close_prices.rolling(self.period).mean()
            std = close_prices.rolling(self.period).std()

            # FIXED: Proper handling of zero standard deviation
            # Replace zeros with NaN, then forward fill from valid values
            std = std.replace(0, np.nan)
            std = std.fillna(method='ffill')

            # If still NaN (all zeros), use very small value to avoid division by zero
            std = std.fillna(1e-6)

            upper_band = sma + (std * self.std_dev)
            lower_band = sma - (std * self.std_dev)

            # Get current and historical values for confirmation
            current_price = safe_float_conversion(close_prices.iloc[-1])
            current_upper = safe_float_conversion(upper_band.iloc[-1])
            current_lower = safe_float_conversion(lower_band.iloc[-1])
            current_sma = safe_float_conversion(sma.iloc[-1])

            # Validate bands
            if not current_upper or not current_lower or not current_sma:
                return {'signal': 0, 'strength': 0.0, 'reason': 'invalid_bands'}

            if current_upper <= current_lower:
                return {'signal': 0, 'strength': 0.0, 'reason': 'collapsed_bands'}

            # Get current position
            position = self.get_position(symbol)

            # EXIT LOGIC (New feature)
            if position != 0:
                # Check for exit conditions
                exit_signal = self._check_exit_conditions(
                    close_prices, sma, position, current_price, current_sma
                )
                if exit_signal:
                    self._update_signal_time(symbol)
                    return exit_signal

            # ENTRY LOGIC with CONFIRMATION
            # Check for confirmed signals at bands
            confirmation_count = self._count_confirmations(
                close_prices.tail(self.confirmation_bars + 1),
                upper_band.tail(self.confirmation_bars + 1),
                lower_band.tail(self.confirmation_bars + 1)
            )

            # OVERSOLD signal (buy)
            if confirmation_count['lower'] >= self.confirmation_bars:
                # Confirmed oversold - generate buy signal
                strength = min((current_lower - current_price) / current_lower * 100, 1.0)
                strength = max(strength, 0.5)  # Minimum 0.5 strength for confirmed signals

                self._update_signal_time(symbol)
                return {
                    'signal': 1,
                    'strength': strength,
                    'reason': f'oversold_confirmed_{confirmation_count["lower"]}_bars'
                }

            # OVERBOUGHT signal (sell)
            elif confirmation_count['upper'] >= self.confirmation_bars:
                # Confirmed overbought - generate sell signal
                strength = min((current_price - current_upper) / current_upper * 100, 1.0)
                strength = max(strength, 0.5)  # Minimum 0.5 strength for confirmed signals

                self._update_signal_time(symbol)
                return {
                    'signal': -1,
                    'strength': strength,
                    'reason': f'overbought_confirmed_{confirmation_count["upper"]}_bars'
                }

            # No confirmed signal
            return {'signal': 0, 'strength': 0.0, 'reason': 'no_confirmation'}

        except Exception as e:
            logger.error(f"Error in Bollinger Bands strategy for {symbol}: {e}", exc_info=True)
            return {'signal': 0, 'strength': 0.0, 'reason': 'error'}

    def _count_confirmations(self, prices: pd.Series, upper: pd.Series, lower: pd.Series) -> Dict[str, int]:
        """
        Count how many consecutive bars touch/break bands

        Args:
            prices: Recent close prices
            upper: Upper band values
            lower: Lower band values

        Returns:
            Dict with 'upper' and 'lower' confirmation counts
        """
        confirmations = {'upper': 0, 'lower': 0}

        # Count consecutive bars touching/breaking each band
        for i in range(len(prices)):
            price = safe_float_conversion(prices.iloc[i])
            upper_val = safe_float_conversion(upper.iloc[i])
            lower_val = safe_float_conversion(lower.iloc[i])

            if not price or not upper_val or not lower_val:
                continue

            # Check lower band (oversold)
            if price <= lower_val:
                confirmations['lower'] += 1
            else:
                break  # Must be consecutive

        for i in range(len(prices)):
            price = safe_float_conversion(prices.iloc[i])
            upper_val = safe_float_conversion(upper.iloc[i])

            if not price or not upper_val:
                continue

            # Check upper band (overbought)
            if price >= upper_val:
                confirmations['upper'] += 1
            else:
                break  # Must be consecutive

        return confirmations

    def _check_exit_conditions(
        self,
        prices: pd.Series,
        sma: pd.Series,
        position: int,
        current_price: float,
        current_sma: float
    ) -> Optional[Dict]:
        """
        Check if exit conditions are met

        Exit long: Price crosses above SMA (middle band)
        Exit short: Price crosses below SMA (middle band)

        Args:
            prices: Close prices
            sma: SMA values (middle band)
            position: Current position (1=long, -1=short)
            current_price: Current price
            current_sma: Current SMA value

        Returns:
            Exit signal dict or None
        """
        # Need at least 2 bars to check crossover
        if len(prices) < 2:
            return None

        prev_price = safe_float_conversion(prices.iloc[-2])
        prev_sma = safe_float_conversion(sma.iloc[-2])

        if not prev_price or not prev_sma:
            return None

        # Exit long position (bought at oversold, exit when back to middle)
        if position == 1:
            # Check if price crossed above SMA
            if prev_price <= prev_sma and current_price > current_sma:
                return {
                    'signal': -1,  # Sell to exit
                    'strength': 0.8,
                    'reason': 'exit_long_at_middle'
                }

        # Exit short position (sold at overbought, exit when back to middle)
        elif position == -1:
            # Check if price crossed below SMA
            if prev_price >= prev_sma and current_price < current_sma:
                return {
                    'signal': 1,  # Buy to cover
                    'strength': 0.8,
                    'reason': 'exit_short_at_middle'
                }

        return None

    def reset(self):
        """Reset strategy state (useful for backtesting)"""
        self.last_signal_time.clear()
        self.current_position.clear()
