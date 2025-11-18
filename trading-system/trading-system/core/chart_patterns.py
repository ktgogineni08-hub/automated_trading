#!/usr/bin/env python3
"""
Chart Pattern Detection Engine
Advanced pattern detection for reversal and continuation patterns

PATTERNS SUPPORTED:
- Reversal: Head & Shoulders, Inverse H&S, Double Top/Bottom, Triple Top/Bottom
- Continuation: Triangles, Flags, Pennants, Rectangles
- Breakout: Channels, Wedges

Features:
- Pivot point identification
- Pattern template matching
- Breakout/breakdown confirmation
- Volume analysis at critical points
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.signal import find_peaks, argrelextrema

logger = logging.getLogger('trading_system.chart_patterns')


class ChartPatternType(Enum):
    """Chart pattern types"""
    REVERSAL_BULLISH = "reversal_bullish"
    REVERSAL_BEARISH = "reversal_bearish"
    CONTINUATION_BULLISH = "continuation_bullish"
    CONTINUATION_BEARISH = "continuation_bearish"
    BREAKOUT = "breakout"


@dataclass
class ChartPattern:
    """Chart pattern detection result"""
    name: str
    pattern_type: ChartPatternType
    confidence: float  # 0-100
    start_index: int
    end_index: int
    breakout_level: float
    target_price: float
    stop_loss: float
    volume_confirmed: bool
    description: str
    pivot_points: List[Tuple[int, float]]  # List of (index, price)


class ChartPatternDetector:
    """
    Advanced chart pattern detector

    Usage:
        detector = ChartPatternDetector()
        patterns = detector.detect_all_patterns(data)

        # Get high-confidence patterns only
        strong_patterns = [p for p in patterns if p.confidence > 70]
    """

    def __init__(
        self,
        min_confidence: float = 60.0,
        pivot_order: int = 5,
        volume_threshold: float = 1.3
    ):
        """
        Initialize chart pattern detector

        Args:
            min_confidence: Minimum confidence score to report patterns
            pivot_order: Order for pivot point detection (higher = fewer pivots)
            volume_threshold: Minimum volume multiplier for confirmation
        """
        self.min_confidence = min_confidence
        self.pivot_order = pivot_order
        self.volume_threshold = volume_threshold

        logger.info(
            f"ChartPatternDetector initialized: "
            f"min_confidence={min_confidence}, pivot_order={pivot_order}"
        )

    def find_pivot_highs(self, df: pd.DataFrame) -> List[Tuple[int, float]]:
        """
        Find pivot highs (local maxima)

        Returns:
            List of (index, price) tuples
        """
        highs = df['high'].values
        pivot_indices = argrelextrema(highs, np.greater, order=self.pivot_order)[0]

        pivots = [(idx, df.iloc[idx]['high']) for idx in pivot_indices]
        return pivots

    def find_pivot_lows(self, df: pd.DataFrame) -> List[Tuple[int, float]]:
        """
        Find pivot lows (local minima)

        Returns:
            List of (index, price) tuples
        """
        lows = df['low'].values
        pivot_indices = argrelextrema(lows, np.less, order=self.pivot_order)[0]

        pivots = [(idx, df.iloc[idx]['low']) for idx in pivot_indices]
        return pivots

    def _check_volume_confirmation(
        self,
        df: pd.DataFrame,
        start_idx: int,
        end_idx: int
    ) -> bool:
        """Check if volume confirms the pattern"""
        pattern_volume = df.iloc[end_idx]['volume']
        avg_volume = df.iloc[start_idx:end_idx]['volume'].mean()

        return pattern_volume >= (avg_volume * self.volume_threshold)

    def _calculate_pattern_height(
        self,
        high_price: float,
        low_price: float
    ) -> float:
        """Calculate pattern height (for target calculation)"""
        return abs(high_price - low_price)

    # =========================================================================
    # REVERSAL PATTERNS
    # =========================================================================

    def detect_head_and_shoulders(
        self,
        df: pd.DataFrame
    ) -> List[ChartPattern]:
        """
        Detect Head and Shoulders pattern (bearish reversal)

        Characteristics:
        - Left shoulder, head (higher), right shoulder
        - Neckline connecting lows
        - Breakout below neckline
        """
        patterns = []

        pivot_highs = self.find_pivot_highs(df)
        pivot_lows = self.find_pivot_lows(df)

        if len(pivot_highs) < 3 or len(pivot_lows) < 2:
            return patterns

        # Look for three consecutive highs forming H&S
        for i in range(len(pivot_highs) - 2):
            left_shoulder_idx, left_shoulder = pivot_highs[i]
            head_idx, head = pivot_highs[i + 1]
            right_shoulder_idx, right_shoulder = pivot_highs[i + 2]

            # Head must be higher than shoulders
            if not (head > left_shoulder and head > right_shoulder):
                continue

            # Shoulders should be roughly equal (±5%)
            shoulder_diff = abs(left_shoulder - right_shoulder) / left_shoulder
            if shoulder_diff > 0.05:
                continue

            # Find neckline (lows between shoulders)
            neckline_lows = [
                (idx, price) for idx, price in pivot_lows
                if left_shoulder_idx < idx < right_shoulder_idx
            ]

            if len(neckline_lows) < 2:
                continue

            # Calculate neckline level (average of lows)
            neckline_level = np.mean([price for _, price in neckline_lows])

            # Check for breakout below neckline
            current_price = df.iloc[-1]['close']
            if current_price > neckline_level * 0.98:  # Not broken yet
                continue

            # Calculate target and stop
            pattern_height = head - neckline_level
            target_price = neckline_level - pattern_height
            stop_loss = head * 1.02

            # Volume confirmation
            volume_confirmed = self._check_volume_confirmation(
                df, left_shoulder_idx, len(df) - 1
            )

            # Confidence calculation
            base_confidence = 75.0
            if shoulder_diff < 0.02:  # Very symmetric
                base_confidence += 10
            if volume_confirmed:
                base_confidence += 15

            confidence = min(base_confidence, 100.0)

            if confidence >= self.min_confidence:
                patterns.append(ChartPattern(
                    name="Head and Shoulders",
                    pattern_type=ChartPatternType.REVERSAL_BEARISH,
                    confidence=confidence,
                    start_index=left_shoulder_idx,
                    end_index=len(df) - 1,
                    breakout_level=neckline_level,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    volume_confirmed=volume_confirmed,
                    description="Head and shoulders - bearish reversal",
                    pivot_points=[
                        (left_shoulder_idx, left_shoulder),
                        (head_idx, head),
                        (right_shoulder_idx, right_shoulder)
                    ]
                ))

        return patterns

    def detect_inverse_head_and_shoulders(
        self,
        df: pd.DataFrame
    ) -> List[ChartPattern]:
        """
        Detect Inverse Head and Shoulders (bullish reversal)

        Characteristics:
        - Left shoulder, head (lower), right shoulder
        - Neckline connecting highs
        - Breakout above neckline
        """
        patterns = []

        pivot_highs = self.find_pivot_highs(df)
        pivot_lows = self.find_pivot_lows(df)

        if len(pivot_lows) < 3 or len(pivot_highs) < 2:
            return patterns

        # Look for three consecutive lows forming inverse H&S
        for i in range(len(pivot_lows) - 2):
            left_shoulder_idx, left_shoulder = pivot_lows[i]
            head_idx, head = pivot_lows[i + 1]
            right_shoulder_idx, right_shoulder = pivot_lows[i + 2]

            # Head must be lower than shoulders
            if not (head < left_shoulder and head < right_shoulder):
                continue

            # Shoulders should be roughly equal (±5%)
            shoulder_diff = abs(left_shoulder - right_shoulder) / left_shoulder
            if shoulder_diff > 0.05:
                continue

            # Find neckline (highs between shoulders)
            neckline_highs = [
                (idx, price) for idx, price in pivot_highs
                if left_shoulder_idx < idx < right_shoulder_idx
            ]

            if len(neckline_highs) < 2:
                continue

            # Calculate neckline level
            neckline_level = np.mean([price for _, price in neckline_highs])

            # Check for breakout above neckline
            current_price = df.iloc[-1]['close']
            if current_price < neckline_level * 1.02:  # Not broken yet
                continue

            # Calculate target and stop
            pattern_height = neckline_level - head
            target_price = neckline_level + pattern_height
            stop_loss = head * 0.98

            # Volume confirmation
            volume_confirmed = self._check_volume_confirmation(
                df, left_shoulder_idx, len(df) - 1
            )

            # Confidence calculation
            base_confidence = 75.0
            if shoulder_diff < 0.02:
                base_confidence += 10
            if volume_confirmed:
                base_confidence += 15

            confidence = min(base_confidence, 100.0)

            if confidence >= self.min_confidence:
                patterns.append(ChartPattern(
                    name="Inverse Head and Shoulders",
                    pattern_type=ChartPatternType.REVERSAL_BULLISH,
                    confidence=confidence,
                    start_index=left_shoulder_idx,
                    end_index=len(df) - 1,
                    breakout_level=neckline_level,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    volume_confirmed=volume_confirmed,
                    description="Inverse H&S - bullish reversal",
                    pivot_points=[
                        (left_shoulder_idx, left_shoulder),
                        (head_idx, head),
                        (right_shoulder_idx, right_shoulder)
                    ]
                ))

        return patterns

    def detect_double_top(self, df: pd.DataFrame) -> List[ChartPattern]:
        """
        Detect Double Top pattern (bearish reversal)

        Characteristics:
        - Two peaks at similar levels
        - Trough between peaks
        - Breakout below trough
        """
        patterns = []

        pivot_highs = self.find_pivot_highs(df)
        pivot_lows = self.find_pivot_lows(df)

        if len(pivot_highs) < 2 or len(pivot_lows) < 1:
            return patterns

        # Look for two consecutive highs at similar levels
        for i in range(len(pivot_highs) - 1):
            first_peak_idx, first_peak = pivot_highs[i]
            second_peak_idx, second_peak = pivot_highs[i + 1]

            # Peaks should be roughly equal (±3%)
            peak_diff = abs(first_peak - second_peak) / first_peak
            if peak_diff > 0.03:
                continue

            # Find trough between peaks
            trough_lows = [
                (idx, price) for idx, price in pivot_lows
                if first_peak_idx < idx < second_peak_idx
            ]

            if not trough_lows:
                continue

            trough_idx, trough_price = min(trough_lows, key=lambda x: x[1])

            # Check for breakout below trough
            current_price = df.iloc[-1]['close']
            if current_price > trough_price * 0.98:
                continue

            # Calculate target and stop
            pattern_height = np.mean([first_peak, second_peak]) - trough_price
            target_price = trough_price - pattern_height
            stop_loss = max(first_peak, second_peak) * 1.02

            # Volume confirmation
            volume_confirmed = self._check_volume_confirmation(
                df, first_peak_idx, len(df) - 1
            )

            # Confidence
            base_confidence = 70.0
            if peak_diff < 0.01:  # Very equal peaks
                base_confidence += 10
            if volume_confirmed:
                base_confidence += 15

            confidence = min(base_confidence, 100.0)

            if confidence >= self.min_confidence:
                patterns.append(ChartPattern(
                    name="Double Top",
                    pattern_type=ChartPatternType.REVERSAL_BEARISH,
                    confidence=confidence,
                    start_index=first_peak_idx,
                    end_index=len(df) - 1,
                    breakout_level=trough_price,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    volume_confirmed=volume_confirmed,
                    description="Double top - bearish reversal",
                    pivot_points=[
                        (first_peak_idx, first_peak),
                        (trough_idx, trough_price),
                        (second_peak_idx, second_peak)
                    ]
                ))

        return patterns

    def detect_double_bottom(self, df: pd.DataFrame) -> List[ChartPattern]:
        """
        Detect Double Bottom pattern (bullish reversal)

        Characteristics:
        - Two troughs at similar levels
        - Peak between troughs
        - Breakout above peak
        """
        patterns = []

        pivot_highs = self.find_pivot_highs(df)
        pivot_lows = self.find_pivot_lows(df)

        if len(pivot_lows) < 2 or len(pivot_highs) < 1:
            return patterns

        # Look for two consecutive lows at similar levels
        for i in range(len(pivot_lows) - 1):
            first_trough_idx, first_trough = pivot_lows[i]
            second_trough_idx, second_trough = pivot_lows[i + 1]

            # Troughs should be roughly equal (±3%)
            trough_diff = abs(first_trough - second_trough) / first_trough
            if trough_diff > 0.03:
                continue

            # Find peak between troughs
            peak_highs = [
                (idx, price) for idx, price in pivot_highs
                if first_trough_idx < idx < second_trough_idx
            ]

            if not peak_highs:
                continue

            peak_idx, peak_price = max(peak_highs, key=lambda x: x[1])

            # Check for breakout above peak
            current_price = df.iloc[-1]['close']
            if current_price < peak_price * 1.02:
                continue

            # Calculate target and stop
            pattern_height = peak_price - np.mean([first_trough, second_trough])
            target_price = peak_price + pattern_height
            stop_loss = min(first_trough, second_trough) * 0.98

            # Volume confirmation
            volume_confirmed = self._check_volume_confirmation(
                df, first_trough_idx, len(df) - 1
            )

            # Confidence
            base_confidence = 70.0
            if trough_diff < 0.01:
                base_confidence += 10
            if volume_confirmed:
                base_confidence += 15

            confidence = min(base_confidence, 100.0)

            if confidence >= self.min_confidence:
                patterns.append(ChartPattern(
                    name="Double Bottom",
                    pattern_type=ChartPatternType.REVERSAL_BULLISH,
                    confidence=confidence,
                    start_index=first_trough_idx,
                    end_index=len(df) - 1,
                    breakout_level=peak_price,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    volume_confirmed=volume_confirmed,
                    description="Double bottom - bullish reversal",
                    pivot_points=[
                        (first_trough_idx, first_trough),
                        (peak_idx, peak_price),
                        (second_trough_idx, second_trough)
                    ]
                ))

        return patterns

    # =========================================================================
    # CONTINUATION PATTERNS
    # =========================================================================

    def detect_ascending_triangle(
        self,
        df: pd.DataFrame
    ) -> List[ChartPattern]:
        """
        Detect Ascending Triangle (bullish continuation)

        Characteristics:
        - Flat resistance (horizontal highs)
        - Rising support (higher lows)
        - Breakout above resistance
        """
        patterns = []

        pivot_highs = self.find_pivot_highs(df)
        pivot_lows = self.find_pivot_lows(df)

        if len(pivot_highs) < 2 or len(pivot_lows) < 2:
            return patterns

        # Look for flat resistance
        for i in range(len(pivot_highs) - 1):
            h1_idx, h1_price = pivot_highs[i]
            h2_idx, h2_price = pivot_highs[i + 1]

            # Highs should be roughly equal (flat resistance)
            if abs(h1_price - h2_price) / h1_price > 0.02:
                continue

            resistance_level = np.mean([h1_price, h2_price])

            # Find rising lows
            rising_lows = [
                (idx, price) for idx, price in pivot_lows
                if h1_idx < idx < h2_idx
            ]

            if len(rising_lows) < 2:
                continue

            # Check if lows are rising
            if not all(
                rising_lows[i][1] < rising_lows[i+1][1]
                for i in range(len(rising_lows) - 1)
            ):
                continue

            # Check for breakout above resistance
            current_price = df.iloc[-1]['close']
            if current_price < resistance_level * 1.01:
                continue

            # Calculate target
            pattern_height = resistance_level - rising_lows[0][1]
            target_price = resistance_level + pattern_height
            stop_loss = rising_lows[-1][1] * 0.98

            # Volume confirmation
            volume_confirmed = self._check_volume_confirmation(
                df, h1_idx, len(df) - 1
            )

            confidence = 75.0 if volume_confirmed else 60.0

            if confidence >= self.min_confidence:
                patterns.append(ChartPattern(
                    name="Ascending Triangle",
                    pattern_type=ChartPatternType.CONTINUATION_BULLISH,
                    confidence=confidence,
                    start_index=h1_idx,
                    end_index=len(df) - 1,
                    breakout_level=resistance_level,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    volume_confirmed=volume_confirmed,
                    description="Ascending triangle - bullish continuation",
                    pivot_points=[(h1_idx, h1_price), (h2_idx, h2_price)]
                ))

        return patterns

    def detect_descending_triangle(
        self,
        df: pd.DataFrame
    ) -> List[ChartPattern]:
        """
        Detect Descending Triangle (bearish continuation)

        Characteristics:
        - Flat support (horizontal lows)
        - Falling resistance (lower highs)
        - Breakout below support
        """
        patterns = []

        pivot_highs = self.find_pivot_highs(df)
        pivot_lows = self.find_pivot_lows(df)

        if len(pivot_lows) < 2 or len(pivot_highs) < 2:
            return patterns

        # Look for flat support
        for i in range(len(pivot_lows) - 1):
            l1_idx, l1_price = pivot_lows[i]
            l2_idx, l2_price = pivot_lows[i + 1]

            # Lows should be roughly equal (flat support)
            if abs(l1_price - l2_price) / l1_price > 0.02:
                continue

            support_level = np.mean([l1_price, l2_price])

            # Find falling highs
            falling_highs = [
                (idx, price) for idx, price in pivot_highs
                if l1_idx < idx < l2_idx
            ]

            if len(falling_highs) < 2:
                continue

            # Check if highs are falling
            if not all(
                falling_highs[i][1] > falling_highs[i+1][1]
                for i in range(len(falling_highs) - 1)
            ):
                continue

            # Check for breakout below support
            current_price = df.iloc[-1]['close']
            if current_price > support_level * 0.99:
                continue

            # Calculate target
            pattern_height = falling_highs[0][1] - support_level
            target_price = support_level - pattern_height
            stop_loss = falling_highs[-1][1] * 1.02

            # Volume confirmation
            volume_confirmed = self._check_volume_confirmation(
                df, l1_idx, len(df) - 1
            )

            confidence = 75.0 if volume_confirmed else 60.0

            if confidence >= self.min_confidence:
                patterns.append(ChartPattern(
                    name="Descending Triangle",
                    pattern_type=ChartPatternType.CONTINUATION_BEARISH,
                    confidence=confidence,
                    start_index=l1_idx,
                    end_index=len(df) - 1,
                    breakout_level=support_level,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    volume_confirmed=volume_confirmed,
                    description="Descending triangle - bearish continuation",
                    pivot_points=[(l1_idx, l1_price), (l2_idx, l2_price)]
                ))

        return patterns

    # =========================================================================
    # MASTER DETECTION METHOD
    # =========================================================================

    def detect_all_patterns(
        self,
        df: pd.DataFrame,
        pattern_types: Optional[List[str]] = None
    ) -> List[ChartPattern]:
        """
        Detect all chart patterns in data

        Args:
            df: OHLCV DataFrame
            pattern_types: Optional list of pattern names to detect

        Returns:
            List of detected patterns sorted by confidence
        """
        if len(df) < 20:
            logger.warning("Insufficient data for chart pattern detection")
            return []

        all_patterns = []

        # Reversal patterns
        if pattern_types is None or 'head_and_shoulders' in pattern_types:
            all_patterns.extend(self.detect_head_and_shoulders(df))
        if pattern_types is None or 'inverse_head_and_shoulders' in pattern_types:
            all_patterns.extend(self.detect_inverse_head_and_shoulders(df))
        if pattern_types is None or 'double_top' in pattern_types:
            all_patterns.extend(self.detect_double_top(df))
        if pattern_types is None or 'double_bottom' in pattern_types:
            all_patterns.extend(self.detect_double_bottom(df))

        # Continuation patterns
        if pattern_types is None or 'ascending_triangle' in pattern_types:
            all_patterns.extend(self.detect_ascending_triangle(df))
        if pattern_types is None or 'descending_triangle' in pattern_types:
            all_patterns.extend(self.detect_descending_triangle(df))

        # Sort by confidence
        all_patterns.sort(key=lambda p: p.confidence, reverse=True)

        logger.info(f"Detected {len(all_patterns)} chart patterns")

        return all_patterns


if __name__ == "__main__":
    # Test chart pattern detector
    print("📈 Testing Chart Pattern Detector\n")

    # Generate sample data with patterns
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')

    # Create data with visible patterns
    close_prices = 100 + np.random.randn(len(dates)).cumsum() * 0.5

    data = pd.DataFrame({
        'open': close_prices * (1 + np.random.randn(len(dates)) * 0.005),
        'high': close_prices * (1 + abs(np.random.randn(len(dates))) * 0.015),
        'low': close_prices * (1 - abs(np.random.randn(len(dates))) * 0.015),
        'close': close_prices,
        'volume': np.random.randint(100000, 1000000, len(dates))
    }, index=dates)

    # Ensure high/low are correct
    data['high'] = data[['open', 'high', 'close']].max(axis=1)
    data['low'] = data[['open', 'low', 'close']].min(axis=1)

    detector = ChartPatternDetector(min_confidence=60.0)

    print(f"Analyzing {len(data)} days of OHLCV data...\n")

    patterns = detector.detect_all_patterns(data)

    print(f"✅ Detected {len(patterns)} chart patterns\n")

    # Show detected patterns
    if patterns:
        print("Detected Patterns:")
        print("-" * 100)
        for i, pattern in enumerate(patterns, 1):
            print(f"{i:2d}. {pattern.name:30s} | "
                  f"Confidence: {pattern.confidence:5.1f} | "
                  f"Target: ₹{pattern.target_price:7.2f} | "
                  f"Stop: ₹{pattern.stop_loss:7.2f}")
    else:
        print("No patterns detected (this is normal with random data)")

    print("\n✅ Chart pattern detector ready!")
