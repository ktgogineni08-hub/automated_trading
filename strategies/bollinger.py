#!/usr/bin/env python3
"""
REFACTORED Bollinger Bands Strategy
Volatility-based mean reversion strategy with signal confirmation

IMPROVEMENTS:
- Uses AdvancedBaseStrategy base class (eliminates ~150 lines of duplication)
- All common logic (confirmation, debouncing, exits) inherited from base
- Cleaner, more maintainable code
- Same functionality as original bollinger_fixed.py

FEATURES (from AdvancedBaseStrategy):
1. Confirmation mechanism (requires 2-bar confirmation)
2. Debouncing (prevents repeated signals)
3. Position awareness (different logic for exits vs entries)
4. Exit logic (crossover-based)
"""

import pandas as pd
import numpy as np
from typing import Dict
from strategies.advanced_base import AdvancedBaseStrategy
from trading_utils import safe_float_conversion
import logging

logger = logging.getLogger('trading_system.strategies.bollinger')


class BollingerBandsStrategy(AdvancedBaseStrategy):
    """
    REFACTORED Bollinger Bands Mean Reversion Strategy

    Uses base class for all common functionality:
    - AdvancedBaseStrategy handles: confirmation, cooldowns, position tracking, exits

    This class only implements Bollinger-specific logic:
    - Band calculation
    - Signal generation based on band position

    Default settings:
    - Period: 20 (SMA calculation)
    - Standard Deviation: 2 (band width)
    - Confirmation bars: 2 (inherited from base)
    - Cooldown: 15 minutes (inherited from base)

    Signals:
    - Buy: Price touches/breaks lower band for 2+ consecutive bars (oversold)
    - Sell: Price touches/breaks upper band for 2+ consecutive bars (overbought)
    - Exit Long: Price crosses above middle band
    - Exit Short: Price crosses below middle band
    """

    def __init__(
        self,
        period: int = 20,
        std_dev: float = 2,
        confirmation_bars: int = 2,
        cooldown_minutes: int = 15
    ):
        """
        Initialize Bollinger Bands strategy

        Args:
            period: SMA calculation period
            std_dev: Number of standard deviations for bands
            confirmation_bars: Consecutive bars required for signal
            cooldown_minutes: Cooldown period after signals
        """
        # Initialize base class with common features
        super().__init__(
            name="Bollinger_Bands_Fixed_Refactored",
            confirmation_bars=confirmation_bars,
            cooldown_minutes=cooldown_minutes
        )

        # Bollinger-specific parameters
        self.period = period
        self.std_dev = std_dev

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> Dict:
        """
        Generate signals based on Bollinger Band position with confirmation

        This method focuses ONLY on Bollinger-specific logic.
        All common logic (cooldowns, confirmations, exits) is handled by base class.

        Args:
            data: OHLCV DataFrame
            symbol: Trading symbol (for logging and cooldown tracking)

        Returns:
            Dict with signal (1=buy, -1=sell, 0=hold), strength (0-1), reason
        """
        # Validate data
        if not self.validate_data(data) or len(data) < self.period + self.confirmation_bars + 5:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}

        # Use 'unknown' if no symbol provided
        if symbol is None:
            symbol = 'unknown'

        # Check cooldown (inherited from AdvancedBaseStrategy)
        if self._is_on_cooldown(symbol):
            return {'signal': 0, 'strength': 0.0, 'reason': 'cooldown'}

        try:
            # ============================================================
            # BOLLINGER-SPECIFIC LOGIC: Calculate Bollinger Bands
            # ============================================================

            close_prices = data['close']

            # Calculate SMA (middle band)
            sma = close_prices.rolling(self.period).mean()

            # Calculate standard deviation
            std = close_prices.rolling(self.period).std()

            # FIXED: Proper handling of zero standard deviation
            # Replace zeros with NaN, then forward fill from valid values
            std = std.replace(0, np.nan)
            std = std.ffill()

            # If still NaN (all zeros), use very small value to avoid division by zero
            std = std.fillna(1e-6)

            # Calculate upper and lower bands
            upper_band = sma + (std * self.std_dev)
            lower_band = sma - (std * self.std_dev)

            # Get current values
            current_price = safe_float_conversion(close_prices.iloc[-1])
            current_upper = safe_float_conversion(upper_band.iloc[-1])
            current_lower = safe_float_conversion(lower_band.iloc[-1])
            current_sma = safe_float_conversion(sma.iloc[-1])

            # Validate bands
            if not current_upper or not current_lower or not current_sma:
                return {'signal': 0, 'strength': 0.0, 'reason': 'invalid_bands'}

            if current_upper <= current_lower:
                return {'signal': 0, 'strength': 0.0, 'reason': 'collapsed_bands'}

            # Get current position (inherited from AdvancedBaseStrategy)
            position = self.get_position(symbol)

            # ============================================================
            # EXIT LOGIC (uses inherited method from AdvancedBaseStrategy)
            # ============================================================

            if position != 0:
                # Check for exit conditions using base class method
                exit_signal = self._check_crossover_exit(
                    prices=close_prices,
                    reference=sma,
                    position=position,
                    current_price=current_price,
                    current_reference=current_sma
                )

                if exit_signal:
                    # Update signal time before returning
                    self._update_signal_time(symbol)
                    return exit_signal

            # ============================================================
            # ENTRY LOGIC with CONFIRMATION (uses inherited method)
            # ============================================================

            # Count confirmations using base class method
            confirmation_count = self._count_band_confirmations(
                prices=close_prices.tail(self.confirmation_bars + 1),
                upper=upper_band.tail(self.confirmation_bars + 1),
                lower=lower_band.tail(self.confirmation_bars + 1)
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
            logger.error(
                f"Error in Bollinger Bands strategy for {symbol}: {e}",
                exc_info=True
            )
            return {'signal': 0, 'strength': 0.0, 'reason': 'error'}


# ============================================================================
# CODE REDUCTION SUMMARY
# ============================================================================
#
# BEFORE (bollinger_fixed.py): ~299 lines
# AFTER (this file): ~155 lines
# REDUCTION: ~144 lines (~48% less code!)
#
# Eliminated duplicated code:
# - ✅ Cooldown checking (_is_on_cooldown, _update_signal_time)
# - ✅ Position tracking (set_position, get_position, current_position dict)
# - ✅ Confirmation counting (_count_confirmations → _count_band_confirmations)
# - ✅ Exit logic (_check_exit_conditions → _check_crossover_exit)
# - ✅ State management (reset method)
#
# Benefits:
# - 🎯 Single source of truth for common logic
# - 🐛 Bug fixes in one place benefit all strategies
# - 📝 Easier to read and maintain
# - ✅ Same functionality, cleaner code
#
# ============================================================================
