#!/usr/bin/env python3
"""
Market Regime Detector
Detects market regimes using moving-average slopes and ADX
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger('trading_system.regime_detector')


class MarketRegimeDetector:
    """
    Market Regime Detection using Technical Analysis

    Detects market regimes (bullish, bearish, sideways) using:
    - Moving average crossovers (20 and 50 period)
    - ADX (Average Directional Index) for trend strength
    - MA slope analysis for trend direction

    Regime Classification:
    - Bullish: ADX > 20, Short MA > Long MA, positive slope
    - Bearish: ADX > 20, Short MA < Long MA, negative slope
    - Sideways: ADX < 20 or minimal slope

    Default Parameters:
    - Short MA window: 20
    - Long MA window: 50
    - ADX window: 14
    - Trend slope lookback: 5
    """

    def __init__(
        self,
        data_provider=None,  # Type hint omitted to avoid circular import
        short_window: int = 20,
        long_window: int = 50,
        adx_window: int = 14,
        trend_slope_lookback: int = 5
    ):
        self.data_provider = data_provider
        self.short_window = short_window
        self.long_window = long_window
        self.adx_window = adx_window
        self.trend_slope_lookback = trend_slope_lookback

    def update_data_provider(self, data_provider) -> None:
        """Update data provider after initialization"""
        self.data_provider = data_provider

    def detect_regime(
        self,
        symbol: str,
        interval: str = "30minute",
        days: int = 30,
        price_data: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Detect current market regime for a symbol

        Args:
            symbol: Trading symbol
            interval: Candle interval for analysis
            days: Number of days of historical data
            price_data: Optional pre-fetched price data

        Returns:
            Dict with regime, bias, ADX, moving averages, slopes, confidence
        """
        try:
            df = self._load_price_data(symbol, interval, days, price_data)
            if df.empty or len(df) < max(self.long_window + self.adx_window, 30):
                return self._default_response(symbol, 'unknown')

            # Prepare data
            df = df.sort_index()
            df = df[['open', 'high', 'low', 'close']].dropna()

            # Calculate moving averages
            df['short_ma'] = df['close'].ewm(span=self.short_window, adjust=False).mean()
            df['long_ma'] = df['close'].ewm(span=self.long_window, adjust=False).mean()

            # Calculate slopes
            df['short_slope'] = df['short_ma'].diff(self.trend_slope_lookback)
            df['long_slope'] = df['long_ma'].diff(self.trend_slope_lookback)

            # Calculate ADX
            adx_series = self._calculate_adx(df)
            adx_value = float(adx_series.iloc[-1]) if not adx_series.empty else 0.0

            # Get latest values
            latest = df.iloc[-1]
            short_ma = float(latest['short_ma']) if not np.isnan(latest['short_ma']) else 0.0
            long_ma = float(latest['long_ma']) if not np.isnan(latest['long_ma']) else 0.0
            short_slope = float(latest['short_slope']) if not np.isnan(latest['short_slope']) else 0.0
            long_slope = float(latest['long_slope']) if not np.isnan(latest['long_slope']) else 0.0

            # Determine regime
            bias = 'neutral'
            regime = 'sideways'

            slope_strength = short_slope / max(1e-6, abs(latest['close']))
            trend_strength = abs(slope_strength) * 10000  # scale for readability

            trend_threshold = 20  # ADX threshold for trending markets
            slope_threshold = 0.0005

            if adx_value >= trend_threshold and short_ma > long_ma and short_slope > slope_threshold:
                bias = 'bullish'
                regime = 'bullish'
            elif adx_value >= trend_threshold and short_ma < long_ma and short_slope < -slope_threshold:
                bias = 'bearish'
                regime = 'bearish'
            elif adx_value < trend_threshold and abs(short_slope) <= slope_threshold:
                bias = 'neutral'
                regime = 'sideways'

            # Calculate confidence
            confidence = min(1.0, (adx_value / 50.0) + min(0.5, abs(short_slope) * 50))

            return {
                'symbol': symbol,
                'regime': regime,
                'bias': bias,
                'adx': round(adx_value, 2),
                'short_ma': round(short_ma, 2),
                'long_ma': round(long_ma, 2),
                'short_slope': round(short_slope, 6),
                'long_slope': round(long_slope, 6),
                'trend_strength': round(trend_strength, 2),
                'confidence': round(confidence, 2),
                'data_points': int(len(df)),
                'updated_at': datetime.now().isoformat()
            }

        except Exception as exc:
            logger.error(f"❌ Regime detection failed for {symbol}: {exc}")
            return self._default_response(symbol, 'unknown')

    def _load_price_data(
        self,
        symbol: str,
        interval: str,
        days: int,
        price_data: Optional[pd.DataFrame]
    ) -> pd.DataFrame:
        """Load price data from provider or use provided data"""
        if price_data is not None and not price_data.empty:
            return price_data.copy()
        if not self.data_provider:
            return pd.DataFrame()
        try:
            df = self.data_provider.fetch_with_retry(symbol, interval=interval, days=days)
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.debug(f"Regime detector could not load data for {symbol}: {exc}")
            return pd.DataFrame()

    def _calculate_adx(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate Average Directional Index (ADX)

        ADX measures trend strength regardless of direction.
        Values above 20 indicate a trending market.

        Args:
            df: DataFrame with 'open', 'high', 'low', 'close'

        Returns:
            Series of ADX values
        """
        high = df['high']
        low = df['low']
        close = df['close']

        # Calculate directional movements
        plus_dm = high.diff()
        minus_dm = low.shift(1) - low

        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        # Calculate True Range
        tr_components = pd.concat([
            (high - low).abs(),
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1)
        tr = tr_components.max(axis=1)

        # Average True Range
        atr = tr.ewm(alpha=1 / self.adx_window, adjust=False).mean()

        # Directional Indicators
        plus_di = 100 * (plus_dm.ewm(alpha=1 / self.adx_window, adjust=False).mean() / atr.replace(0, np.nan))
        minus_di = 100 * (minus_dm.ewm(alpha=1 / self.adx_window, adjust=False).mean() / atr.replace(0, np.nan))

        # Directional Index and ADX
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.ewm(alpha=1 / self.adx_window, adjust=False).mean().fillna(0.0)

        return adx

    def _default_response(self, symbol: str, regime: str) -> Dict[str, Any]:
        """Return default response when detection fails"""
        return {
            'symbol': symbol,
            'regime': regime,
            'bias': 'neutral' if regime == 'sideways' else regime,
            'adx': 0.0,
            'short_ma': 0.0,
            'long_ma': 0.0,
            'short_slope': 0.0,
            'long_slope': 0.0,
            'trend_strength': 0.0,
            'confidence': 0.0,
            'data_points': 0,
            'updated_at': datetime.now().isoformat()
        }
