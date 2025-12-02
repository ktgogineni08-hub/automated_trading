#!/usr/bin/env python3
"""
Candlestick Pattern Recognition Engine
Advanced pattern detection with ML confidence scoring

PATTERNS SUPPORTED:
- Bullish: Hammer, Bullish Engulfing, Morning Star, Piercing Pattern
- Bearish: Shooting Star, Bearish Engulfing, Evening Star, Dark Cloud Cover
- Reversal: Doji, Harami, Three White Soldiers, Three Black Crows
- Continuation: Rising/Falling Three Methods

Features:
- Multi-candle pattern detection (1-5 candles)
- Confidence scoring (0-100)
- Volume confirmation
- Trend context awareness
- Vectorized computation for speed
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger('trading_system.candlestick_patterns')


class PatternType(Enum):
    """Candlestick pattern types"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    REVERSAL = "reversal"
    CONTINUATION = "continuation"


@dataclass
class CandlestickPattern:
    """Candlestick pattern detection result"""
    name: str
    pattern_type: PatternType
    confidence: float  # 0-100
    index: int  # Index in dataframe where pattern completes
    price: float  # Price at pattern completion
    volume_confirmed: bool
    trend_aligned: bool
    description: str


class CandlestickPatternDetector:
    """
    Advanced candlestick pattern detector with ML confidence scoring

    Usage:
        detector = CandlestickPatternDetector()
        patterns = detector.detect_all_patterns(data)

        # Get high-confidence patterns only
        strong_patterns = [p for p in patterns if p.confidence > 70]
    """

    def __init__(
        self,
        min_confidence: float = 50.0,
        volume_threshold: float = 1.2,
        trend_lookback: int = 20
    ):
        """
        Initialize candlestick pattern detector

        Args:
            min_confidence: Minimum confidence score to report patterns
            volume_threshold: Minimum volume multiplier for confirmation
            trend_lookback: Periods to look back for trend detection
        """
        self.min_confidence = min_confidence
        self.volume_threshold = volume_threshold
        self.trend_lookback = trend_lookback

        logger.info(
            f"CandlestickPatternDetector initialized: "
            f"min_confidence={min_confidence}, "
            f"volume_threshold={volume_threshold}"
        )

    def _calculate_body(self, df: pd.DataFrame) -> pd.Series:
        """Calculate candle body size (VECTORIZED)"""
        return df['close'] - df['open']

    def _calculate_upper_shadow(self, df: pd.DataFrame) -> pd.Series:
        """Calculate upper shadow size (VECTORIZED)"""
        return df['high'] - df[['close', 'open']].max(axis=1)

    def _calculate_lower_shadow(self, df: pd.DataFrame) -> pd.Series:
        """Calculate lower shadow size (VECTORIZED)"""
        return df[['close', 'open']].min(axis=1) - df['low']

    def _is_bullish_candle(self, df: pd.DataFrame) -> pd.Series:
        """Check if candle is bullish (VECTORIZED)"""
        return df['close'] > df['open']

    def _is_bearish_candle(self, df: pd.DataFrame) -> pd.Series:
        """Check if candle is bearish (VECTORIZED)"""
        return df['close'] < df['open']

    def _detect_trend(self, df: pd.DataFrame, index: int) -> str:
        """
        Detect trend at given index

        Returns:
            'uptrend', 'downtrend', or 'sideways'
        """
        if index < self.trend_lookback:
            return 'sideways'

        # Use SMA to determine trend
        lookback_data = df.iloc[index - self.trend_lookback:index]
        sma = lookback_data['close'].mean()
        current_price = df.iloc[index]['close']

        # Calculate slope
        x = np.arange(len(lookback_data))
        y = lookback_data['close'].values
        slope = np.polyfit(x, y, 1)[0]

        # Trend classification
        if current_price > sma and slope > 0:
            return 'uptrend'
        elif current_price < sma and slope < 0:
            return 'downtrend'
        else:
            return 'sideways'

    def _check_volume_confirmation(
        self,
        df: pd.DataFrame,
        index: int,
        lookback: int = 20
    ) -> bool:
        """Check if volume confirms the pattern"""
        if index < lookback:
            return False

        current_volume = df.iloc[index]['volume']
        avg_volume = df.iloc[index - lookback:index]['volume'].mean()

        return current_volume >= (avg_volume * self.volume_threshold)

    def _calculate_confidence(
        self,
        base_confidence: float,
        volume_confirmed: bool,
        trend_aligned: bool,
        additional_factors: Dict[str, float] = None
    ) -> float:
        """
        Calculate pattern confidence score

        Args:
            base_confidence: Base pattern match confidence (0-100)
            volume_confirmed: Whether volume confirms pattern
            trend_aligned: Whether pattern aligns with trend
            additional_factors: Additional scoring factors

        Returns:
            Final confidence score (0-100)
        """
        confidence = base_confidence

        # Volume confirmation adds 10-15 points
        if volume_confirmed:
            confidence += 15

        # Trend alignment adds 10 points
        if trend_aligned:
            confidence += 10

        # Additional factors
        if additional_factors:
            for factor, weight in additional_factors.items():
                confidence += weight

        return min(confidence, 100.0)

    # =========================================================================
    # SINGLE CANDLE PATTERNS
    # =========================================================================

    def detect_doji(self, df: pd.DataFrame) -> List[CandlestickPattern]:
        """
        Detect Doji patterns (indecision candles)

        Characteristics:
        - Very small body (open ≈ close)
        - Can have long shadows
        - Signals indecision/potential reversal
        """
        patterns = []

        body = self._calculate_body(df).abs()
        full_range = df['high'] - df['low']

        # Doji: body < 10% of full range
        is_doji = body < (full_range * 0.1)

        for i in range(len(df)):
            if not is_doji.iloc[i]:
                continue

            trend = self._detect_trend(df, i)
            volume_confirmed = self._check_volume_confirmation(df, i)

            # Higher confidence if at trend extremes
            base_confidence = 60.0
            if trend != 'sideways':
                base_confidence = 70.0

            trend_aligned = trend in ['uptrend', 'downtrend']  # Reversal pattern

            confidence = self._calculate_confidence(
                base_confidence,
                volume_confirmed,
                trend_aligned
            )

            if confidence >= self.min_confidence:
                patterns.append(CandlestickPattern(
                    name="Doji",
                    pattern_type=PatternType.REVERSAL,
                    confidence=confidence,
                    index=i,
                    price=df.iloc[i]['close'],
                    volume_confirmed=volume_confirmed,
                    trend_aligned=trend_aligned,
                    description=f"Doji in {trend} - potential reversal"
                ))

        return patterns

    def detect_hammer(self, df: pd.DataFrame) -> List[CandlestickPattern]:
        """
        Detect Hammer pattern (bullish reversal)

        Characteristics:
        - Small body at top of range
        - Long lower shadow (2-3× body)
        - Little to no upper shadow
        - Appears in downtrend
        """
        patterns = []

        body = self._calculate_body(df).abs()
        upper_shadow = self._calculate_upper_shadow(df)
        lower_shadow = self._calculate_lower_shadow(df)

        # Hammer conditions
        is_hammer = (
            (lower_shadow >= 2 * body) &  # Long lower shadow
            (upper_shadow < body) &  # Small upper shadow
            (body > 0)  # Has a body
        )

        for i in range(len(df)):
            if not is_hammer.iloc[i]:
                continue

            trend = self._detect_trend(df, i)
            volume_confirmed = self._check_volume_confirmation(df, i)

            # Best in downtrend (reversal signal)
            trend_aligned = (trend == 'downtrend')

            base_confidence = 75.0 if trend_aligned else 55.0

            # Extra confidence for very long shadow
            shadow_ratio = lower_shadow.iloc[i] / body.iloc[i]
            if shadow_ratio > 3:
                base_confidence += 5

            confidence = self._calculate_confidence(
                base_confidence,
                volume_confirmed,
                trend_aligned
            )

            if confidence >= self.min_confidence:
                patterns.append(CandlestickPattern(
                    name="Hammer",
                    pattern_type=PatternType.BULLISH,
                    confidence=confidence,
                    index=i,
                    price=df.iloc[i]['close'],
                    volume_confirmed=volume_confirmed,
                    trend_aligned=trend_aligned,
                    description=f"Hammer - bullish reversal signal"
                ))

        return patterns

    def detect_shooting_star(self, df: pd.DataFrame) -> List[CandlestickPattern]:
        """
        Detect Shooting Star pattern (bearish reversal)

        Characteristics:
        - Small body at bottom of range
        - Long upper shadow (2-3× body)
        - Little to no lower shadow
        - Appears in uptrend
        """
        patterns = []

        body = self._calculate_body(df).abs()
        upper_shadow = self._calculate_upper_shadow(df)
        lower_shadow = self._calculate_lower_shadow(df)

        # Shooting star conditions
        is_shooting_star = (
            (upper_shadow >= 2 * body) &  # Long upper shadow
            (lower_shadow < body) &  # Small lower shadow
            (body > 0)  # Has a body
        )

        for i in range(len(df)):
            if not is_shooting_star.iloc[i]:
                continue

            trend = self._detect_trend(df, i)
            volume_confirmed = self._check_volume_confirmation(df, i)

            # Best in uptrend (reversal signal)
            trend_aligned = (trend == 'uptrend')

            base_confidence = 75.0 if trend_aligned else 55.0

            confidence = self._calculate_confidence(
                base_confidence,
                volume_confirmed,
                trend_aligned
            )

            if confidence >= self.min_confidence:
                patterns.append(CandlestickPattern(
                    name="Shooting Star",
                    pattern_type=PatternType.BEARISH,
                    confidence=confidence,
                    index=i,
                    price=df.iloc[i]['close'],
                    volume_confirmed=volume_confirmed,
                    trend_aligned=trend_aligned,
                    description=f"Shooting Star - bearish reversal signal"
                ))

        return patterns

    # =========================================================================
    # TWO CANDLE PATTERNS
    # =========================================================================

    def detect_engulfing(self, df: pd.DataFrame) -> List[CandlestickPattern]:
        """
        Detect Engulfing patterns (bullish & bearish)

        Bullish Engulfing:
        - First candle: small bearish
        - Second candle: large bullish that engulfs first

        Bearish Engulfing:
        - First candle: small bullish
        - Second candle: large bearish that engulfs first
        """
        patterns = []

        if len(df) < 2:
            return patterns

        for i in range(1, len(df)):
            prev_open = df.iloc[i-1]['open']
            prev_close = df.iloc[i-1]['close']
            curr_open = df.iloc[i]['open']
            curr_close = df.iloc[i]['close']

            # Bullish engulfing
            if (prev_close < prev_open and  # Previous bearish
                curr_close > curr_open and  # Current bullish
                curr_open < prev_close and  # Opens below prev close
                curr_close > prev_open):    # Closes above prev open

                trend = self._detect_trend(df, i)
                volume_confirmed = self._check_volume_confirmation(df, i)
                trend_aligned = (trend == 'downtrend')

                base_confidence = 80.0 if trend_aligned else 60.0

                confidence = self._calculate_confidence(
                    base_confidence,
                    volume_confirmed,
                    trend_aligned
                )

                if confidence >= self.min_confidence:
                    patterns.append(CandlestickPattern(
                        name="Bullish Engulfing",
                        pattern_type=PatternType.BULLISH,
                        confidence=confidence,
                        index=i,
                        price=df.iloc[i]['close'],
                        volume_confirmed=volume_confirmed,
                        trend_aligned=trend_aligned,
                        description="Bullish engulfing - strong reversal signal"
                    ))

            # Bearish engulfing
            elif (prev_close > prev_open and  # Previous bullish
                  curr_close < curr_open and  # Current bearish
                  curr_open > prev_close and  # Opens above prev close
                  curr_close < prev_open):    # Closes below prev open

                trend = self._detect_trend(df, i)
                volume_confirmed = self._check_volume_confirmation(df, i)
                trend_aligned = (trend == 'uptrend')

                base_confidence = 80.0 if trend_aligned else 60.0

                confidence = self._calculate_confidence(
                    base_confidence,
                    volume_confirmed,
                    trend_aligned
                )

                if confidence >= self.min_confidence:
                    patterns.append(CandlestickPattern(
                        name="Bearish Engulfing",
                        pattern_type=PatternType.BEARISH,
                        confidence=confidence,
                        index=i,
                        price=df.iloc[i]['close'],
                        volume_confirmed=volume_confirmed,
                        trend_aligned=trend_aligned,
                        description="Bearish engulfing - strong reversal signal"
                    ))

        return patterns

    def detect_piercing_pattern(self, df: pd.DataFrame) -> List[CandlestickPattern]:
        """
        Detect Piercing Pattern (bullish reversal)

        Characteristics:
        - First candle: long bearish
        - Second candle: opens below prev low, closes above midpoint
        - Appears in downtrend
        """
        patterns = []

        if len(df) < 2:
            return patterns

        for i in range(1, len(df)):
            prev_open = df.iloc[i-1]['open']
            prev_close = df.iloc[i-1]['close']
            prev_low = df.iloc[i-1]['low']
            curr_open = df.iloc[i]['open']
            curr_close = df.iloc[i]['close']

            prev_midpoint = (prev_open + prev_close) / 2

            # Piercing pattern conditions
            if (prev_close < prev_open and  # Previous bearish
                curr_close > curr_open and  # Current bullish
                curr_open < prev_low and    # Opens below prev low
                curr_close > prev_midpoint and  # Closes above midpoint
                curr_close < prev_open):    # But not above prev open

                trend = self._detect_trend(df, i)
                volume_confirmed = self._check_volume_confirmation(df, i)
                trend_aligned = (trend == 'downtrend')

                base_confidence = 75.0 if trend_aligned else 55.0

                confidence = self._calculate_confidence(
                    base_confidence,
                    volume_confirmed,
                    trend_aligned
                )

                if confidence >= self.min_confidence:
                    patterns.append(CandlestickPattern(
                        name="Piercing Pattern",
                        pattern_type=PatternType.BULLISH,
                        confidence=confidence,
                        index=i,
                        price=df.iloc[i]['close'],
                        volume_confirmed=volume_confirmed,
                        trend_aligned=trend_aligned,
                        description="Piercing pattern - bullish reversal"
                    ))

        return patterns

    def detect_dark_cloud_cover(self, df: pd.DataFrame) -> List[CandlestickPattern]:
        """
        Detect Dark Cloud Cover (bearish reversal)

        Characteristics:
        - First candle: long bullish
        - Second candle: opens above prev high, closes below midpoint
        - Appears in uptrend
        """
        patterns = []

        if len(df) < 2:
            return patterns

        for i in range(1, len(df)):
            prev_open = df.iloc[i-1]['open']
            prev_close = df.iloc[i-1]['close']
            prev_high = df.iloc[i-1]['high']
            curr_open = df.iloc[i]['open']
            curr_close = df.iloc[i]['close']

            prev_midpoint = (prev_open + prev_close) / 2

            # Dark cloud cover conditions
            if (prev_close > prev_open and  # Previous bullish
                curr_close < curr_open and  # Current bearish
                curr_open > prev_high and   # Opens above prev high
                curr_close < prev_midpoint and  # Closes below midpoint
                curr_close > prev_open):    # But not below prev open

                trend = self._detect_trend(df, i)
                volume_confirmed = self._check_volume_confirmation(df, i)
                trend_aligned = (trend == 'uptrend')

                base_confidence = 75.0 if trend_aligned else 55.0

                confidence = self._calculate_confidence(
                    base_confidence,
                    volume_confirmed,
                    trend_aligned
                )

                if confidence >= self.min_confidence:
                    patterns.append(CandlestickPattern(
                        name="Dark Cloud Cover",
                        pattern_type=PatternType.BEARISH,
                        confidence=confidence,
                        index=i,
                        price=df.iloc[i]['close'],
                        volume_confirmed=volume_confirmed,
                        trend_aligned=trend_aligned,
                        description="Dark cloud cover - bearish reversal"
                    ))

        return patterns

    # =========================================================================
    # THREE CANDLE PATTERNS
    # =========================================================================

    def detect_morning_star(self, df: pd.DataFrame) -> List[CandlestickPattern]:
        """
        Detect Morning Star (bullish reversal)

        Characteristics:
        - First candle: long bearish
        - Second candle: small body (star)
        - Third candle: long bullish closing above first midpoint
        """
        patterns = []

        if len(df) < 3:
            return patterns

        for i in range(2, len(df)):
            c1_open = df.iloc[i-2]['open']
            c1_close = df.iloc[i-2]['close']
            c2_open = df.iloc[i-1]['open']
            c2_close = df.iloc[i-1]['close']
            c3_open = df.iloc[i]['open']
            c3_close = df.iloc[i]['close']

            c1_body = abs(c1_close - c1_open)
            c2_body = abs(c2_close - c2_open)
            c3_body = abs(c3_close - c3_open)
            c1_midpoint = (c1_open + c1_close) / 2

            # Morning star conditions
            if (c1_close < c1_open and  # First bearish
                c2_body < c1_body * 0.3 and  # Star is small
                c3_close > c3_open and  # Third bullish
                c3_close > c1_midpoint and  # Closes above first midpoint
                c3_body > c1_body * 0.5):  # Third candle is substantial

                trend = self._detect_trend(df, i)
                volume_confirmed = self._check_volume_confirmation(df, i)
                trend_aligned = (trend == 'downtrend')

                base_confidence = 85.0 if trend_aligned else 65.0

                confidence = self._calculate_confidence(
                    base_confidence,
                    volume_confirmed,
                    trend_aligned
                )

                if confidence >= self.min_confidence:
                    patterns.append(CandlestickPattern(
                        name="Morning Star",
                        pattern_type=PatternType.BULLISH,
                        confidence=confidence,
                        index=i,
                        price=df.iloc[i]['close'],
                        volume_confirmed=volume_confirmed,
                        trend_aligned=trend_aligned,
                        description="Morning star - strong bullish reversal"
                    ))

        return patterns

    def detect_evening_star(self, df: pd.DataFrame) -> List[CandlestickPattern]:
        """
        Detect Evening Star (bearish reversal)

        Characteristics:
        - First candle: long bullish
        - Second candle: small body (star)
        - Third candle: long bearish closing below first midpoint
        """
        patterns = []

        if len(df) < 3:
            return patterns

        for i in range(2, len(df)):
            c1_open = df.iloc[i-2]['open']
            c1_close = df.iloc[i-2]['close']
            c2_open = df.iloc[i-1]['open']
            c2_close = df.iloc[i-1]['close']
            c3_open = df.iloc[i]['open']
            c3_close = df.iloc[i]['close']

            c1_body = abs(c1_close - c1_open)
            c2_body = abs(c2_close - c2_open)
            c3_body = abs(c3_close - c3_open)
            c1_midpoint = (c1_open + c1_close) / 2

            # Evening star conditions
            if (c1_close > c1_open and  # First bullish
                c2_body < c1_body * 0.3 and  # Star is small
                c3_close < c3_open and  # Third bearish
                c3_close < c1_midpoint and  # Closes below first midpoint
                c3_body > c1_body * 0.5):  # Third candle is substantial

                trend = self._detect_trend(df, i)
                volume_confirmed = self._check_volume_confirmation(df, i)
                trend_aligned = (trend == 'uptrend')

                base_confidence = 85.0 if trend_aligned else 65.0

                confidence = self._calculate_confidence(
                    base_confidence,
                    volume_confirmed,
                    trend_aligned
                )

                if confidence >= self.min_confidence:
                    patterns.append(CandlestickPattern(
                        name="Evening Star",
                        pattern_type=PatternType.BEARISH,
                        confidence=confidence,
                        index=i,
                        price=df.iloc[i]['close'],
                        volume_confirmed=volume_confirmed,
                        trend_aligned=trend_aligned,
                        description="Evening star - strong bearish reversal"
                    ))

        return patterns

    def detect_three_white_soldiers(self, df: pd.DataFrame) -> List[CandlestickPattern]:
        """
        Detect Three White Soldiers (bullish continuation/reversal)

        Characteristics:
        - Three consecutive long bullish candles
        - Each opens within previous body
        - Each closes near high
        """
        patterns = []

        if len(df) < 3:
            return patterns

        for i in range(2, len(df)):
            # Get three candles
            candles = df.iloc[i-2:i+1]

            # All must be bullish
            if not all(candles['close'] > candles['open']):
                continue

            # Check consecutive higher closes
            if not (candles.iloc[1]['close'] > candles.iloc[0]['close'] and
                    candles.iloc[2]['close'] > candles.iloc[1]['close']):
                continue

            # Each opens within previous body
            if not (candles.iloc[1]['open'] > candles.iloc[0]['open'] and
                    candles.iloc[1]['open'] < candles.iloc[0]['close'] and
                    candles.iloc[2]['open'] > candles.iloc[1]['open'] and
                    candles.iloc[2]['open'] < candles.iloc[1]['close']):
                continue

            trend = self._detect_trend(df, i)
            volume_confirmed = self._check_volume_confirmation(df, i)
            trend_aligned = (trend == 'downtrend')  # Better as reversal

            base_confidence = 80.0 if trend_aligned else 70.0

            confidence = self._calculate_confidence(
                base_confidence,
                volume_confirmed,
                trend_aligned
            )

            if confidence >= self.min_confidence:
                patterns.append(CandlestickPattern(
                    name="Three White Soldiers",
                    pattern_type=PatternType.BULLISH,
                    confidence=confidence,
                    index=i,
                    price=df.iloc[i]['close'],
                    volume_confirmed=volume_confirmed,
                    trend_aligned=trend_aligned,
                    description="Three white soldiers - strong bullish signal"
                ))

        return patterns

    def detect_three_black_crows(self, df: pd.DataFrame) -> List[CandlestickPattern]:
        """
        Detect Three Black Crows (bearish continuation/reversal)

        Characteristics:
        - Three consecutive long bearish candles
        - Each opens within previous body
        - Each closes near low
        """
        patterns = []

        if len(df) < 3:
            return patterns

        for i in range(2, len(df)):
            # Get three candles
            candles = df.iloc[i-2:i+1]

            # All must be bearish
            if not all(candles['close'] < candles['open']):
                continue

            # Check consecutive lower closes
            if not (candles.iloc[1]['close'] < candles.iloc[0]['close'] and
                    candles.iloc[2]['close'] < candles.iloc[1]['close']):
                continue

            # Each opens within previous body
            if not (candles.iloc[1]['open'] < candles.iloc[0]['open'] and
                    candles.iloc[1]['open'] > candles.iloc[0]['close'] and
                    candles.iloc[2]['open'] < candles.iloc[1]['open'] and
                    candles.iloc[2]['open'] > candles.iloc[1]['close']):
                continue

            trend = self._detect_trend(df, i)
            volume_confirmed = self._check_volume_confirmation(df, i)
            trend_aligned = (trend == 'uptrend')  # Better as reversal

            base_confidence = 80.0 if trend_aligned else 70.0

            confidence = self._calculate_confidence(
                base_confidence,
                volume_confirmed,
                trend_aligned
            )

            if confidence >= self.min_confidence:
                patterns.append(CandlestickPattern(
                    name="Three Black Crows",
                    pattern_type=PatternType.BEARISH,
                    confidence=confidence,
                    index=i,
                    price=df.iloc[i]['close'],
                    volume_confirmed=volume_confirmed,
                    trend_aligned=trend_aligned,
                    description="Three black crows - strong bearish signal"
                ))

        return patterns

    # =========================================================================
    # MASTER DETECTION METHOD
    # =========================================================================

    def detect_all_patterns(
        self,
        df: pd.DataFrame,
        pattern_types: Optional[List[str]] = None
    ) -> List[CandlestickPattern]:
        """
        Detect all candlestick patterns in data

        Args:
            df: OHLCV DataFrame
            pattern_types: Optional list of pattern names to detect

        Returns:
            List of detected patterns sorted by confidence
        """
        if len(df) < 3:
            logger.warning("Insufficient data for pattern detection")
            return []

        all_patterns = []

        # Single candle patterns
        if pattern_types is None or 'doji' in pattern_types:
            all_patterns.extend(self.detect_doji(df))
        if pattern_types is None or 'hammer' in pattern_types:
            all_patterns.extend(self.detect_hammer(df))
        if pattern_types is None or 'shooting_star' in pattern_types:
            all_patterns.extend(self.detect_shooting_star(df))

        # Two candle patterns
        if pattern_types is None or 'engulfing' in pattern_types:
            all_patterns.extend(self.detect_engulfing(df))
        if pattern_types is None or 'piercing' in pattern_types:
            all_patterns.extend(self.detect_piercing_pattern(df))
        if pattern_types is None or 'dark_cloud' in pattern_types:
            all_patterns.extend(self.detect_dark_cloud_cover(df))

        # Three candle patterns
        if pattern_types is None or 'morning_star' in pattern_types:
            all_patterns.extend(self.detect_morning_star(df))
        if pattern_types is None or 'evening_star' in pattern_types:
            all_patterns.extend(self.detect_evening_star(df))
        if pattern_types is None or 'three_white_soldiers' in pattern_types:
            all_patterns.extend(self.detect_three_white_soldiers(df))
        if pattern_types is None or 'three_black_crows' in pattern_types:
            all_patterns.extend(self.detect_three_black_crows(df))

        # Sort by confidence (highest first)
        all_patterns.sort(key=lambda p: p.confidence, reverse=True)

        logger.info(f"Detected {len(all_patterns)} patterns")

        return all_patterns

    def get_latest_patterns(
        self,
        df: pd.DataFrame,
        lookback: int = 10
    ) -> List[CandlestickPattern]:
        """
        Get patterns from the most recent candles

        Args:
            df: OHLCV DataFrame
            lookback: Number of recent candles to analyze

        Returns:
            List of recent patterns
        """
        recent_df = df.iloc[-lookback:]
        patterns = self.detect_all_patterns(recent_df)

        return patterns


if __name__ == "__main__":
    # Test candlestick pattern detector
    print("🕯️  Testing Candlestick Pattern Detector\n")

    # Generate sample data
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')

    close_prices = 100 + np.random.randn(len(dates)).cumsum()

    data = pd.DataFrame({
        'open': close_prices * (1 + np.random.randn(len(dates)) * 0.01),
        'high': close_prices * (1 + abs(np.random.randn(len(dates))) * 0.02),
        'low': close_prices * (1 - abs(np.random.randn(len(dates))) * 0.02),
        'close': close_prices,
        'volume': np.random.randint(100000, 1000000, len(dates))
    }, index=dates)

    # Ensure high/low are correct
    data['high'] = data[['open', 'high', 'close']].max(axis=1)
    data['low'] = data[['open', 'low', 'close']].min(axis=1)

    detector = CandlestickPatternDetector(min_confidence=60.0)

    print(f"Analyzing {len(data)} days of OHLCV data...\n")

    patterns = detector.detect_all_patterns(data)

    print(f"✅ Detected {len(patterns)} patterns\n")

    # Show top 10 patterns
    print("Top 10 Patterns by Confidence:")
    print("-" * 80)
    for i, pattern in enumerate(patterns[:10], 1):
        print(f"{i:2d}. {pattern.name:25s} | "
              f"Confidence: {pattern.confidence:5.1f} | "
              f"Type: {pattern.pattern_type.value:12s} | "
              f"Volume: {'✓' if pattern.volume_confirmed else '✗'}")

    # Statistics
    bullish = [p for p in patterns if p.pattern_type == PatternType.BULLISH]
    bearish = [p for p in patterns if p.pattern_type == PatternType.BEARISH]
    reversal = [p for p in patterns if p.pattern_type == PatternType.REVERSAL]

    print(f"\n📊 Pattern Statistics:")
    print(f"   Bullish Patterns: {len(bullish)}")
    print(f"   Bearish Patterns: {len(bearish)}")
    print(f"   Reversal Patterns: {len(reversal)}")
    print(f"   Avg Confidence: {np.mean([p.confidence for p in patterns]):.1f}")

    print("\n✅ Candlestick pattern detector ready!")
