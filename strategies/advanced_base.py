#!/usr/bin/env python3
"""
Advanced Base Strategy
Provides enhanced features for strategy implementations:
- Confirmation mechanism (requires N-bar confirmation)
- Debouncing (prevents repeated signals via cooldowns)
- Position awareness (different logic for entry vs exit)
- Exit logic (smart position closing)
"""

import pandas as pd
from typing import Dict, Optional
from datetime import datetime, timedelta
from strategies.base import BaseStrategy
import logging

logger = logging.getLogger(__name__)


class AdvancedBaseStrategy(BaseStrategy):
    """
    Advanced base class with confirmation, debouncing, and position tracking

    This class extracts common functionality from all _fixed strategies,
    eliminating code duplication and making maintenance easier.

    Features:
    - 2-bar confirmation before generating signals
    - Cooldown period after signals to prevent overtrading
    - Position tracking (knows if we're long/short/flat)
    - Exit logic for closing positions
    """

    def __init__(
        self,
        name: str,
        confirmation_bars: int = 2,
        cooldown_minutes: int = 15
    ):
        """
        Initialize advanced strategy

        Args:
            name: Strategy name
            confirmation_bars: Number of consecutive bars required for confirmation
            cooldown_minutes: Minutes to wait after a signal before generating another
        """
        super().__init__(name)
        self.confirmation_bars = confirmation_bars
        self.cooldown_minutes = cooldown_minutes

        # Track last signal time per symbol (debouncing)
        self.last_signal_time: Dict[str, datetime] = {}

        # Track current position per symbol (position awareness)
        self.current_position: Dict[str, int] = {}  # 1=long, -1=short, 0=flat

    def _is_on_cooldown(self, symbol: str) -> bool:
        """
        Check if symbol is on signal cooldown

        Args:
            symbol: Trading symbol

        Returns:
            True if symbol is on cooldown, False otherwise
        """
        if symbol not in self.last_signal_time:
            return False

        time_since_last = datetime.now() - self.last_signal_time[symbol]
        return time_since_last < timedelta(minutes=self.cooldown_minutes)

    def _update_signal_time(self, symbol: str):
        """
        Update last signal time for symbol

        Args:
            symbol: Trading symbol
        """
        self.last_signal_time[symbol] = datetime.now()

    def set_position(self, symbol: str, position: int):
        """
        Update current position for symbol

        This should be called by the trading system when positions change

        Args:
            symbol: Trading symbol
            position: 1=long, -1=short, 0=flat
        """
        self.current_position[symbol] = position

    def get_position(self, symbol: str) -> int:
        """
        Get current position for symbol

        Args:
            symbol: Trading symbol

        Returns:
            Position: 1=long, -1=short, 0=flat
        """
        return self.current_position.get(symbol, 0)

    def _count_band_confirmations(
        self,
        prices: pd.Series,
        upper: pd.Series,
        lower: pd.Series
    ) -> Dict[str, int]:
        """
        Count how many consecutive bars touch/break bands

        Used for Bollinger Bands and similar strategies

        Args:
            prices: Recent close prices
            upper: Upper band values
            lower: Lower band values

        Returns:
            Dict with 'upper' and 'lower' confirmation counts
        """
        from trading_utils import safe_float_conversion

        confirmations = {'upper': 0, 'lower': 0}

        # Count consecutive bars touching/breaking lower band (oversold)
        for i in range(len(prices)):
            price = safe_float_conversion(prices.iloc[i])
            lower_val = safe_float_conversion(lower.iloc[i])

            if not price or not lower_val:
                continue

            if price <= lower_val:
                confirmations['lower'] += 1
            else:
                break  # Must be consecutive

        # Count consecutive bars touching/breaking upper band (overbought)
        for i in range(len(prices)):
            price = safe_float_conversion(prices.iloc[i])
            upper_val = safe_float_conversion(upper.iloc[i])

            if not price or not upper_val:
                continue

            if price >= upper_val:
                confirmations['upper'] += 1
            else:
                break  # Must be consecutive

        return confirmations

    def _count_threshold_confirmations(
        self,
        indicator: pd.Series,
        lower_threshold: float,
        upper_threshold: float
    ) -> Dict[str, int]:
        """
        Count how many consecutive bars indicator crosses thresholds

        Used for RSI and similar oscillator strategies

        Args:
            indicator: Indicator values (e.g., RSI)
            lower_threshold: Oversold threshold
            upper_threshold: Overbought threshold

        Returns:
            Dict with 'oversold' and 'overbought' confirmation counts
        """
        from trading_utils import safe_float_conversion

        confirmations = {'oversold': 0, 'overbought': 0}

        # Count consecutive bars below lower threshold (oversold)
        for i in range(len(indicator)):
            value = safe_float_conversion(indicator.iloc[i])

            if value is None:
                continue

            if value <= lower_threshold:
                confirmations['oversold'] += 1
            else:
                break  # Must be consecutive

        # Count consecutive bars above upper threshold (overbought)
        for i in range(len(indicator)):
            value = safe_float_conversion(indicator.iloc[i])

            if value is None:
                continue

            if value >= upper_threshold:
                confirmations['overbought'] += 1
            else:
                break  # Must be consecutive

        return confirmations

    def _check_crossover_exit(
        self,
        prices: pd.Series,
        reference: pd.Series,
        position: int,
        current_price: float,
        current_reference: float
    ) -> Optional[Dict]:
        """
        Check if exit conditions are met based on crossover

        Common exit logic:
        - Exit long: Price crosses above reference (e.g., middle band, SMA)
        - Exit short: Price crosses below reference

        Args:
            prices: Close prices
            reference: Reference line (e.g., SMA, middle band)
            position: Current position (1=long, -1=short)
            current_price: Current price
            current_reference: Current reference value

        Returns:
            Exit signal dict or None
        """
        from trading_utils import safe_float_conversion

        # Need at least 2 bars to check crossover
        if len(prices) < 2:
            return None

        prev_price = safe_float_conversion(prices.iloc[-2])
        prev_reference = safe_float_conversion(reference.iloc[-2])

        if not prev_price or not prev_reference:
            return None

        # Exit long position (bought at oversold, exit when back to middle)
        if position == 1:
            # Check if price crossed above reference
            if prev_price <= prev_reference and current_price > current_reference:
                return {
                    'signal': -1,  # Sell to exit
                    'strength': 0.8,
                    'reason': 'exit_long_crossover'
                }

        # Exit short position (sold at overbought, exit when back to middle)
        elif position == -1:
            # Check if price crossed below reference
            if prev_price >= prev_reference and current_price < current_reference:
                return {
                    'signal': 1,  # Buy to cover
                    'strength': 0.8,
                    'reason': 'exit_short_crossover'
                }

        return None

    def _check_threshold_exit(
        self,
        indicator: pd.Series,
        middle_value: float,
        position: int
    ) -> Optional[Dict]:
        """
        Check if exit conditions are met based on threshold crossing

        Common for oscillator-based strategies (RSI, Stochastic, etc.)

        Args:
            indicator: Indicator values
            middle_value: Neutral threshold (e.g., 50 for RSI)
            position: Current position (1=long, -1=short)

        Returns:
            Exit signal dict or None
        """
        from trading_utils import safe_float_conversion

        if len(indicator) < 2:
            return None

        current_value = safe_float_conversion(indicator.iloc[-1])
        prev_value = safe_float_conversion(indicator.iloc[-2])

        if not current_value or not prev_value:
            return None

        # Exit long position when indicator crosses back above middle
        if position == 1:
            if prev_value <= middle_value and current_value > middle_value:
                return {
                    'signal': -1,
                    'strength': 0.7,
                    'reason': 'exit_long_threshold'
                }

        # Exit short position when indicator crosses back below middle
        elif position == -1:
            if prev_value >= middle_value and current_value < middle_value:
                return {
                    'signal': 1,
                    'strength': 0.7,
                    'reason': 'exit_short_threshold'
                }

        return None

    def reset(self):
        """
        Reset strategy state

        Useful for backtesting to ensure clean state between runs
        """
        self.last_signal_time.clear()
        self.current_position.clear()
        logger.debug(f"{self.name}: State reset")

    def get_state(self) -> Dict:
        """
        Get current strategy state

        Useful for debugging and monitoring

        Returns:
            Dict with strategy state
        """
        return {
            'name': self.name,
            'cooldown_minutes': self.cooldown_minutes,
            'confirmation_bars': self.confirmation_bars,
            'tracked_symbols': len(self.last_signal_time),
            'active_positions': len([p for p in self.current_position.values() if p != 0])
        }

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"{self.__class__.__name__}("
            f"name='{self.name}', "
            f"confirmation={self.confirmation_bars}, "
            f"cooldown={self.cooldown_minutes}min)"
        )
