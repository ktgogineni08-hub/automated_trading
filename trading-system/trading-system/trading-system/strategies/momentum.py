#!/usr/bin/env python3
"""
Enhanced Momentum Strategy
Multi-indicator momentum strategy combining RSI, MACD, ROC, and trend analysis
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple
from strategies.base import BaseStrategy
from trading_utils import safe_float_conversion, is_zero
import logging

logger = logging.getLogger('trading_system.strategies.momentum')


class EnhancedMomentumStrategy(BaseStrategy):
    """
    Enhanced Multi-Indicator Momentum Strategy

    Combines multiple momentum indicators for high-quality signals:
    - Price momentum (rate of change over period)
    - RSI (relative strength index)
    - ROC (rate of change)
    - MACD (moving average convergence divergence)
    - Trend strength (linear regression slope)
    - Price acceleration (momentum of momentum)

    Default settings:
    - Momentum period: 10
    - RSI period: 7
    - Momentum threshold: 0.015 (1.5%)
    - Acceleration threshold: 0.003 (0.3%)
    - ROC period: 12
    - Trend strength period: 20

    Signal strength weighted combination:
    - Momentum: 25%
    - RSI: 20%
    - MACD: 20%
    - ROC: 15%
    - Trend strength: 12%
    - Acceleration: 8%

    Minimum signal strength: 0.35 (35%)
    """

    def __init__(self,
                 momentum_period: int = 10,
                 rsi_period: int = 7,
                 momentum_threshold: float = 0.015,
                 acceleration_threshold: float = 0.003,
                 rsi_oversold: int = 30,
                 rsi_overbought: int = 70,
                 roc_period: int = 12,
                 trend_strength_period: int = 20):
        super().__init__("Enhanced_Momentum")
        self.momentum_period = momentum_period
        self.rsi_period = rsi_period
        self.momentum_threshold = momentum_threshold
        self.acceleration_threshold = acceleration_threshold
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.roc_period = roc_period
        self.trend_strength_period = trend_strength_period

    def _calculate_rsi(self, data: pd.DataFrame, period: int) -> pd.Series:
        """Calculate RSI efficiently with proper NaN handling"""
        delta = data["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        # Use a small epsilon to avoid division by zero
        epsilon = 1e-10
        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, epsilon)
        rsi = 100 - (100 / (1 + rs))

        # Fill any remaining NaN values with neutral RSI (50)
        rsi = rsi.fillna(50.0)
        return rsi

    def _calculate_roc(self, data: pd.DataFrame, period: int) -> float:
        """Calculate Rate of Change"""
        if len(data) < period + 1:
            return 0.0
        current_price = safe_float_conversion(data['close'].iloc[-1])
        past_price = safe_float_conversion(data['close'].iloc[-(period + 1)])
        if is_zero(past_price):
            return 0.0
        return (current_price - past_price) / past_price

    def _calculate_macd(self, data: pd.DataFrame, fast_period: int = 12,
                       slow_period: int = 26, signal_period: int = 9) -> Tuple[float, float]:
        """Calculate MACD and signal line"""
        if len(data) < slow_period + signal_period:
            return 0.0, 0.0

        try:
            # Calculate EMAs
            ema_fast = data['close'].ewm(span=fast_period, adjust=False).mean()
            ema_slow = data['close'].ewm(span=slow_period, adjust=False).mean()

            # MACD line
            macd_line = ema_fast - ema_slow

            # Signal line
            signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()

            current_macd = safe_float_conversion(macd_line.iloc[-1])
            current_signal = safe_float_conversion(signal_line.iloc[-1])

            return current_macd, current_signal
        except Exception:
            return 0.0, 0.0

    def _calculate_trend_strength(self, data: pd.DataFrame, period: int) -> float:
        """Calculate trend strength using linear regression slope"""
        if len(data) < period:
            return 0.0

        try:
            recent_data = data['close'].tail(period)
            x = np.arange(len(recent_data))
            y = recent_data.values

            # Calculate linear regression slope
            slope = np.polyfit(x, y, 1)[0]

            # Normalize slope by price level
            avg_price = y.mean()
            if avg_price == 0:
                return 0.0

            normalized_slope = slope / avg_price
            return abs(normalized_slope)  # Return absolute value for trend strength
        except Exception:
            return 0.0

    def _calculate_acceleration(self, data: pd.DataFrame, period: int = 5) -> float:
        """Calculate price acceleration using exponential smoothing"""
        if len(data) < period * 2:
            return 0.0

        try:
            # Use exponential weighted moving average for smoother acceleration
            prices = data['close']
            momentum = prices.pct_change(period)
            acceleration = momentum.diff().ewm(span=3, adjust=False).mean()
            return safe_float_conversion(acceleration.iloc[-1])
        except Exception:
            return 0.0

    def _calculate_signal_strength(self, momentum: float, rsi: float, roc: float,
                                  trend_strength: float, acceleration: float, macd: float,
                                  signal_line: float, signal_type: str) -> float:
        """Calculate comprehensive signal strength with MACD"""
        strength = 0.0

        # Momentum component (25% weight) - direction-based scoring
        momentum_normalized = abs(momentum) / self.momentum_threshold
        momentum_score = min(momentum_normalized, 1.0)

        # Apply direction logic - only credit momentum in signal direction
        if signal_type == 'buy' and momentum > 0:
            strength += momentum_score * 0.25
        elif signal_type == 'sell' and momentum < 0:
            strength += momentum_score * 0.25

        # RSI component (20% weight)
        if signal_type == 'buy':
            rsi_score = max(0, (self.rsi_overbought - rsi) / (self.rsi_overbought - self.rsi_oversold)) if rsi < self.rsi_overbought else 0.0
        else:
            rsi_score = max(0, (rsi - self.rsi_oversold) / (self.rsi_overbought - self.rsi_oversold)) if rsi > self.rsi_oversold else 0.0
        strength += rsi_score * 0.20

        # MACD component (20% weight)
        macd_threshold = 0.001
        if signal_type == 'buy':
            macd_score = min(abs(macd - signal_line) / macd_threshold, 1.0) if macd > signal_line else 0.0
        else:
            macd_score = min(abs(macd - signal_line) / macd_threshold, 1.0) if macd < signal_line else 0.0
        strength += macd_score * 0.20

        # ROC component (15% weight)
        roc_threshold = 0.02  # 2% ROC threshold
        if signal_type == 'buy':
            roc_score = min(abs(roc) / roc_threshold, 1.0) if roc > 0 else 0.0
        else:
            roc_score = min(abs(roc) / roc_threshold, 1.0) if roc < 0 else 0.0
        strength += roc_score * 0.15

        # Trend strength component (12% weight)
        trend_threshold = 0.001  # 0.1% daily trend
        trend_score = min(trend_strength / trend_threshold, 1.0)
        strength += trend_score * 0.12

        # Acceleration component (8% weight)
        if signal_type == 'buy':
            accel_score = min(abs(acceleration) / self.acceleration_threshold, 1.0) if acceleration > 0 else 0.0
        else:
            accel_score = min(abs(acceleration) / self.acceleration_threshold, 1.0) if acceleration < 0 else 0.0
        strength += accel_score * 0.08

        return min(strength, 1.0)

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> Dict:
        """
        Generate signals based on multi-indicator momentum analysis

        Args:
            data: OHLCV DataFrame
            symbol: Trading symbol (for logging)

        Returns:
            Dict with signal (1=buy, -1=sell, 0=hold), strength (0-1), reason
        """
        if not self.validate_data(data) or len(data) < max(self.momentum_period, self.roc_period, self.trend_strength_period) + 10:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}

        try:
            # Calculate all indicators
            momentum = safe_float_conversion(data['close'].pct_change(self.momentum_period).iloc[-1])
            rsi = self._calculate_rsi(data, self.rsi_period)
            current_rsi = safe_float_conversion(rsi.iloc[-1], 50.0)
            roc = self._calculate_roc(data, self.roc_period)
            trend_strength = self._calculate_trend_strength(data, self.trend_strength_period)
            acceleration = self._calculate_acceleration(data)
            macd, signal_line = self._calculate_macd(data)

            # Enhanced bullish conditions with MACD confirmation
            bullish_conditions = (
                momentum > self.momentum_threshold and
                current_rsi < self.rsi_overbought and
                roc > 0.01 and  # 1% ROC minimum
                trend_strength > 0.0005 and  # Minimum trend strength
                acceleration > self.acceleration_threshold and
                macd > signal_line  # MACD bullish crossover
            )

            # Enhanced bearish conditions with MACD confirmation
            bearish_conditions = (
                momentum < -self.momentum_threshold and
                current_rsi > self.rsi_oversold and
                roc < -0.01 and  # -1% ROC minimum
                trend_strength > 0.0005 and  # Minimum trend strength
                acceleration < -self.acceleration_threshold and
                macd < signal_line  # MACD bearish crossover
            )

            if bullish_conditions:
                strength = self._calculate_signal_strength(
                    momentum, current_rsi, roc, trend_strength, acceleration,
                    macd, signal_line, 'buy'
                )
                if strength > 0.35:  # Minimum strength threshold
                    return {
                        'signal': 1,
                        'strength': strength,
                        'reason': f'enhanced_momentum_up_mom{momentum:.3f}_rsi{current_rsi:.0f}_roc{roc:.3f}_macd{macd:.4f}'
                    }

            elif bearish_conditions:
                strength = self._calculate_signal_strength(
                    momentum, current_rsi, roc, trend_strength, acceleration,
                    macd, signal_line, 'sell'
                )
                if strength > 0.35:  # Minimum strength threshold
                    return {
                        'signal': -1,
                        'strength': strength,
                        'reason': f'enhanced_momentum_down_mom{momentum:.3f}_rsi{current_rsi:.0f}_roc{roc:.3f}_macd{macd:.4f}'
                    }

            return {'signal': 0, 'strength': 0.0, 'reason': 'no_momentum_conditions'}

        except Exception as e:
            logger.error(f"Error in Enhanced Momentum strategy for {symbol}: {e}")
            return {'signal': 0, 'strength': 0.0, 'reason': 'error'}
