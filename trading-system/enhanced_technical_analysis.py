#!/usr/bin/env python3
"""
Enhanced Technical Analysis Module
Based on: "A Comprehensive Guide to Trading Indian Equity Futures" Section 5

Implements:
- RSI (Relative Strength Index) - Section 5.3
- MACD (Moving Average Convergence Divergence) - Section 5.3
- Volume Confirmation - Section 5.4
- Multiple Moving Averages - Section 5.3
- Candlestick Pattern Recognition - Section 5.1
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np

logger = logging.getLogger('trading_system.technical_analysis')


class TrendDirection(Enum):
    """Trend classification"""
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


class CandlestickPattern(Enum):
    """Key reversal patterns (Guide Section 5.1)"""
    BULLISH_ENGULFING = "bullish_engulfing"
    BEARISH_ENGULFING = "bearish_engulfing"
    HAMMER = "hammer"
    HANGING_MAN = "hanging_man"
    DOJI = "doji"
    MARUBOZU_BULLISH = "marubozu_bullish"
    MARUBOZU_BEARISH = "marubozu_bearish"
    NONE = "none"


@dataclass
class TechnicalSignals:
    """Aggregated technical analysis signals"""
    # Indicators
    rsi: float
    rsi_signal: str  # "overbought", "oversold", "neutral"

    macd_line: float
    macd_signal: float
    macd_histogram: float
    macd_crossover: str  # "bullish", "bearish", "none"

    # Moving averages
    sma_20: float
    sma_50: float
    sma_200: float
    price_vs_ma: str  # "above_all", "below_all", "mixed"

    # Volume
    current_volume: float
    avg_volume_20d: float
    volume_confirmation: bool

    # Patterns
    candlestick_pattern: CandlestickPattern

    # Overall assessment
    trend_direction: TrendDirection
    signal_strength: float  # 0.0 to 1.0


class EnhancedTechnicalAnalysis:
    """
    Professional Technical Analysis Suite

    Implements all indicators recommended in Guide Section 5
    """

    def __init__(self):
        self.rsi_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9

        logger.info("✅ EnhancedTechnicalAnalysis initialized")

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """
        Calculate RSI (Guide Section 5.3)

        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss

        Interpretation:
        - RSI > 70: Overbought (potential pullback)
        - RSI < 30: Oversold (potential bounce)
        - Divergence: Price makes new high/low but RSI doesn't → reversal signal

        Args:
            prices: Price series (typically close prices)
            period: RSI period (default 14)

        Returns:
            RSI value (0-100)
        """
        if len(prices) < period + 1:
            return 50.0  # Neutral if insufficient data

        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1]

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """
        Calculate ATR (Average True Range)
        
        Args:
            df: DataFrame with high, low, close columns
            period: ATR period (default 14)
            
        Returns:
            ATR value
        """
        if df is None or df.empty or len(df) < period + 2:
            return 0.0
            
        high = df['high']
        low = df['low']
        close = df['close']
        prev_close = close.shift(1)
        
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Use simple moving average of TR for ATR (standard)
        # or Wilder's smoothing if preferred, but here matching original logic
        atr = true_range.rolling(period).mean().iloc[-1]
        
        # Handle NaN
        if pd.isna(atr) or atr == 0:
             atr = true_range.tail(period).mean()
             
        return float(atr) if not pd.isna(atr) else 0.0

    def calculate_macd(self, prices: pd.Series) -> Dict[str, float]:
        """
        Calculate MACD (Guide Section 5.3)

        MACD Line = 12-period EMA - 26-period EMA
        Signal Line = 9-period EMA of MACD Line
        Histogram = MACD Line - Signal Line

        Signals:
        - MACD crosses above signal → Bullish
        - MACD crosses below signal → Bearish
        - Divergence → Reversal warning

        Args:
            prices: Price series

        Returns:
            {'macd': float, 'signal': float, 'histogram': float}
        """
        if len(prices) < 26:
            return {'macd': 0, 'signal': 0, 'histogram': 0}

        exp1 = prices.ewm(span=self.macd_fast, adjust=False).mean()
        exp2 = prices.ewm(span=self.macd_slow, adjust=False).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return {
            'macd': macd_line.iloc[-1],
            'signal': signal_line.iloc[-1],
            'histogram': histogram.iloc[-1]
        }

    def calculate_moving_averages(
        self,
        prices: pd.Series,
        periods: List[int] = [20, 50, 200]
    ) -> Dict[int, float]:
        """
        Calculate multiple moving averages (Guide Section 5.3)

        Key MAs:
        - 20-day: Short-term trend
        - 50-day: Medium-term trend
        - 200-day: Long-term trend

        Golden Cross: 50-day crosses above 200-day (bullish)
        Death Cross: 50-day crosses below 200-day (bearish)

        Args:
            prices: Price series
            periods: MA periods to calculate

        Returns:
            {period: ma_value}
        """
        mas = {}
        for period in periods:
            if len(prices) >= period:
                mas[period] = prices.rolling(window=period).mean().iloc[-1]
            else:
                mas[period] = prices.mean()  # Fallback

        return mas

    def validate_volume_breakout(
        self,
        current_volume: float,
        avg_volume_20d: float,
        threshold: float = 1.5
    ) -> Tuple[bool, str]:
        """
        Validate breakout with volume confirmation (Guide Section 5.4)

        Rule: Breakout is more reliable if volume is 50%+ above average
        High volume = Strong conviction behind move
        Low volume = Potentially false breakout

        Args:
            current_volume: Current period volume
            avg_volume_20d: 20-day average volume
            threshold: Volume multiplier (default 1.5 = 50% above avg)

        Returns:
            (is_confirmed, explanation)
        """
        if avg_volume_20d == 0:
            return False, "No historical volume data"

        volume_ratio = current_volume / avg_volume_20d

        if volume_ratio >= threshold:
            return True, f"✅ Volume confirmed ({volume_ratio:.1f}x average)"
        else:
            return False, f"⚠️ Weak volume ({volume_ratio:.1f}x average, need {threshold}x)"

    def detect_candlestick_pattern(
        self,
        open_price: float,
        high: float,
        low: float,
        close: float,
        prev_open: float,
        prev_close: float
    ) -> CandlestickPattern:
        """
        Detect key candlestick patterns (Guide Section 5.1)

        Patterns:
        - Hammer: Small body at top, long lower shadow (bullish reversal)
        - Hanging Man: Small body at top, long lower shadow (bearish reversal)
        - Doji: Very small body, indecision
        - Engulfing: Large candle engulfs previous (strong reversal)
        - Marubozu: No wicks, strong momentum

        Args:
            open_price, high, low, close: Current candle
            prev_open, prev_close: Previous candle

        Returns:
            Detected pattern
        """
        body = abs(close - open_price)
        total_range = high - low

        if total_range == 0:
            return CandlestickPattern.NONE

        body_ratio = body / total_range

        # Doji: Very small body
        if body_ratio < 0.1:
            return CandlestickPattern.DOJI

        # Marubozu: Large body, minimal wicks
        if body_ratio > 0.9:
            if close > open_price:
                return CandlestickPattern.MARUBOZU_BULLISH
            else:
                return CandlestickPattern.MARUBOZU_BEARISH

        # Hammer / Hanging Man
        lower_wick = min(open_price, close) - low
        upper_wick = high - max(open_price, close)

        if lower_wick > body * 2 and upper_wick < body * 0.3:
            # Long lower shadow, small body at top
            if close > open_price:
                return CandlestickPattern.HAMMER  # Bullish if after downtrend
            else:
                return CandlestickPattern.HANGING_MAN  # Bearish if after uptrend

        # Engulfing
        prev_body = abs(prev_close - prev_open)
        current_body_engulfs = (
            body > prev_body and
            close > max(prev_open, prev_close) and
            open_price < min(prev_open, prev_close)
        )

        if current_body_engulfs:
            if close > open_price:
                return CandlestickPattern.BULLISH_ENGULFING
            else:
                return CandlestickPattern.BEARISH_ENGULFING

        return CandlestickPattern.NONE

    def assess_trend_direction(
        self,
        current_price: float,
        sma_20: float,
        sma_50: float,
        sma_200: float,
        rsi: float,
        macd_histogram: float
    ) -> TrendDirection:
        """
        Determine overall trend direction

        Bullish if:
        - Price > MA20 > MA50 > MA200
        - RSI > 50
        - MACD histogram positive

        Args:
            current_price: Current price
            sma_20, sma_50, sma_200: Moving averages
            rsi: RSI value
            macd_histogram: MACD histogram

        Returns:
            TrendDirection classification
        """
        # Check MA alignment
        ma_bullish = (current_price > sma_20 > sma_50 > sma_200)
        ma_bearish = (current_price < sma_20 < sma_50 < sma_200)

        # Count bullish signals
        bullish_signals = 0
        if current_price > sma_50:
            bullish_signals += 1
        if rsi > 50:
            bullish_signals += 1
        if macd_histogram > 0:
            bullish_signals += 1

        # Classify
        if ma_bullish and bullish_signals >= 2:
            return TrendDirection.STRONG_BULLISH
        elif bullish_signals >= 2:
            return TrendDirection.BULLISH
        elif ma_bearish and bullish_signals == 0:
            return TrendDirection.STRONG_BEARISH
        elif bullish_signals == 0:
            return TrendDirection.BEARISH
        else:
            return TrendDirection.NEUTRAL

    def generate_comprehensive_signals(
        self,
        prices: pd.Series,
        volumes: pd.Series,
        ohlc: Optional[pd.DataFrame] = None
    ) -> TechnicalSignals:
        """
        Generate all technical signals in one call

        Args:
            prices: Close prices
            volumes: Volume data
            ohlc: DataFrame with ['open', 'high', 'low', 'close']

        Returns:
            TechnicalSignals with all indicators
        """
        # Calculate indicators
        rsi = self.calculate_rsi(prices)
        macd_data = self.calculate_macd(prices)
        mas = self.calculate_moving_averages(prices)

        # RSI signal
        if rsi > 70:
            rsi_signal = "overbought"
        elif rsi < 30:
            rsi_signal = "oversold"
        else:
            rsi_signal = "neutral"

        # MACD crossover
        if macd_data['histogram'] > 0 and len(prices) > 1:
            prev_macd = self.calculate_macd(prices[:-1])
            if prev_macd['histogram'] <= 0:
                macd_crossover = "bullish"
            else:
                macd_crossover = "none"
        elif macd_data['histogram'] < 0 and len(prices) > 1:
            prev_macd = self.calculate_macd(prices[:-1])
            if prev_macd['histogram'] >= 0:
                macd_crossover = "bearish"
            else:
                macd_crossover = "none"
        else:
            macd_crossover = "none"

        # MA position
        current_price = prices.iloc[-1]
        if current_price > mas.get(20, 0) and current_price > mas.get(50, 0):
            price_vs_ma = "above_all"
        elif current_price < mas.get(20, float('inf')) and current_price < mas.get(50, float('inf')):
            price_vs_ma = "below_all"
        else:
            price_vs_ma = "mixed"

        # Volume
        current_volume = volumes.iloc[-1]
        avg_volume = volumes.rolling(window=min(20, len(volumes))).mean().iloc[-1]
        volume_confirmed, _ = self.validate_volume_breakout(current_volume, avg_volume)

        # Candlestick pattern
        pattern = CandlestickPattern.NONE
        if ohlc is not None and len(ohlc) >= 2:
            last = ohlc.iloc[-1]
            prev = ohlc.iloc[-2]
            pattern = self.detect_candlestick_pattern(
                last['open'], last['high'], last['low'], last['close'],
                prev['open'], prev['close']
            )

        # Trend direction
        trend = self.assess_trend_direction(
            current_price,
            mas.get(20, current_price),
            mas.get(50, current_price),
            mas.get(200, current_price),
            rsi,
            macd_data['histogram']
        )

        # Signal strength (0.0 to 1.0)
        strength = 0.5  # Base neutral
        if trend in [TrendDirection.STRONG_BULLISH, TrendDirection.STRONG_BEARISH]:
            strength = 0.8
        elif trend in [TrendDirection.BULLISH, TrendDirection.BEARISH]:
            strength = 0.6

        if volume_confirmed:
            strength += 0.1
        if pattern in [CandlestickPattern.BULLISH_ENGULFING, CandlestickPattern.BEARISH_ENGULFING]:
            strength += 0.1

        strength = min(1.0, strength)

        return TechnicalSignals(
            rsi=rsi,
            rsi_signal=rsi_signal,
            macd_line=macd_data['macd'],
            macd_signal=macd_data['signal'],
            macd_histogram=macd_data['histogram'],
            macd_crossover=macd_crossover,
            sma_20=mas.get(20, 0),
            sma_50=mas.get(50, 0),
            sma_200=mas.get(200, 0),
            price_vs_ma=price_vs_ma,
            current_volume=current_volume,
            avg_volume_20d=avg_volume,
            volume_confirmation=volume_confirmed,
            candlestick_pattern=pattern,
            trend_direction=trend,
            signal_strength=strength
        )


# Module convenience function
def create_technical_analyzer() -> EnhancedTechnicalAnalysis:
    """Create technical analyzer instance"""
    return EnhancedTechnicalAnalysis()


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    analyzer = EnhancedTechnicalAnalysis()

    # Simulate price data
    prices = pd.Series([25000, 25050, 25100, 25080, 25120, 25160, 25200, 25180,
                       25220, 25250, 25280, 25300, 25350, 25400, 25420])
    volumes = pd.Series([1000, 1100, 1200, 900, 1400, 1500, 1600, 1100,
                         1300, 1400, 1500, 1600, 1800, 1900, 2000])

    signals = analyzer.generate_comprehensive_signals(prices, volumes)

    print(f"\n{'='*80}")
    print(f"TECHNICAL ANALYSIS SIGNALS")
    print(f"{'='*80}")
    print(f"RSI: {signals.rsi:.2f} ({signals.rsi_signal})")
    print(f"MACD: {signals.macd_line:.2f} / Signal: {signals.macd_signal:.2f} / Histogram: {signals.macd_histogram:.2f}")
    print(f"MACD Crossover: {signals.macd_crossover}")
    print(f"Price vs MAs: {signals.price_vs_ma}")
    print(f"Volume Confirmed: {signals.volume_confirmation}")
    print(f"Trend: {signals.trend_direction.value}")
    print(f"Signal Strength: {signals.signal_strength:.2f}")
    print(f"{'='*80}\n")
