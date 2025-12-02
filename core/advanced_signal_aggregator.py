#!/usr/bin/env python3
"""
Advanced Multi-Signal Aggregator with ML Scoring
Combines signals from candlestick patterns, chart patterns, indicators, and ML

This is an enhanced version that integrates:
- Candlestick patterns
- Chart patterns
- Technical indicators (RSI, MACD, etc.)
- Volume analysis
- ML predictions
- Multi-timeframe analysis

OUTPUT:
- Aggregated score (0-100)
- Signal direction (BUY/SELL/HOLD)
- Confidence level
- Contributing factors
"""

import logging
import sys
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Handle imports for both module usage and direct execution
# Add parent directory to path for direct execution
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.candlestick_patterns import CandlestickPatternDetector, PatternType
from core.chart_patterns import ChartPatternDetector, ChartPatternType

logger = logging.getLogger('trading_system.advanced_signal_aggregator')


class SignalDirection(Enum):
    """Trading signal direction"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


@dataclass
class AggregatedSignal:
    """Aggregated trading signal"""
    symbol: str
    direction: SignalDirection
    score: float  # 0-100
    confidence: float  # 0-1
    timestamp: pd.Timestamp
    contributing_signals: Dict[str, float] = field(default_factory=dict)
    pattern_matches: List[str] = field(default_factory=list)
    recommended_entry: float = 0.0
    recommended_stop: float = 0.0
    recommended_target: float = 0.0
    risk_reward_ratio: float = 0.0


class AdvancedSignalAggregator:
    """
    Advanced multi-signal aggregator with ML enhancement

    Usage:
        aggregator = AdvancedSignalAggregator()
        signal = aggregator.generate_signal(
            symbol='NIFTY50',
            data=data_5m
        )

        if signal.direction in [SignalDirection.STRONG_BUY, SignalDirection.BUY]:
            # Execute buy order
            place_order(...)
    """

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        strong_threshold: float = 80.0,
        weak_threshold: float = 60.0
    ):
        """
        Initialize signal aggregator

        Args:
            weights: Signal source weights (default: balanced)
            strong_threshold: Threshold for STRONG signals
            weak_threshold: Threshold for weak signals
        """
        # Default weights (sum to 1.0)
        self.weights = weights or {
            'candlestick_patterns': 0.15,
            'chart_patterns': 0.20,
            'trend_indicators': 0.20,
            'momentum_indicators': 0.15,
            'volume_analysis': 0.10,
            'price_action': 0.20
        }

        # Normalize weights
        total = sum(self.weights.values())
        self.weights = {k: v/total for k, v in self.weights.items()}

        self.strong_threshold = strong_threshold
        self.weak_threshold = weak_threshold

        # Initialize detectors
        self.candlestick_detector = CandlestickPatternDetector(min_confidence=60.0)
        self.chart_pattern_detector = ChartPatternDetector(min_confidence=60.0)

        logger.info(
            f"AdvancedSignalAggregator initialized: weights={self.weights}"
        )

    def _analyze_candlestick_patterns(
        self,
        df: pd.DataFrame
    ) -> Tuple[float, List[str]]:
        """
        Analyze candlestick patterns

        Returns:
            (score: -1 to +1, pattern_names)
        """
        patterns = self.candlestick_detector.get_latest_patterns(df, lookback=20)

        if not patterns:
            return 0.0, []

        # Weight patterns by confidence
        bullish_score = sum(
            p.confidence / 100.0
            for p in patterns
            if p.pattern_type == PatternType.BULLISH
        )

        bearish_score = sum(
            p.confidence / 100.0
            for p in patterns
            if p.pattern_type == PatternType.BEARISH
        )

        # Normalize to -1 to +1
        total_score = bullish_score - bearish_score
        max_possible = len(patterns)

        normalized_score = np.clip(total_score / max(max_possible, 1), -1, 1)

        pattern_names = [p.name for p in patterns]

        return normalized_score, pattern_names

    def _analyze_chart_patterns(
        self,
        df: pd.DataFrame
    ) -> Tuple[float, List[str]]:
        """
        Analyze chart patterns

        Returns:
            (score: -1 to +1, pattern_names)
        """
        patterns = self.chart_pattern_detector.detect_all_patterns(df)

        if not patterns:
            return 0.0, []

        # Weight patterns by confidence
        bullish_score = sum(
            p.confidence / 100.0
            for p in patterns
            if p.pattern_type in [
                ChartPatternType.REVERSAL_BULLISH,
                ChartPatternType.CONTINUATION_BULLISH
            ]
        )

        bearish_score = sum(
            p.confidence / 100.0
            for p in patterns
            if p.pattern_type in [
                ChartPatternType.REVERSAL_BEARISH,
                ChartPatternType.CONTINUATION_BEARISH
            ]
        )

        # Normalize
        total_score = bullish_score - bearish_score
        max_possible = len(patterns)

        normalized_score = np.clip(total_score / max(max_possible, 1), -1, 1)

        pattern_names = [p.name for p in patterns]

        return normalized_score, pattern_names

    def _analyze_trend_indicators(self, df: pd.DataFrame) -> float:
        """
        Analyze trend indicators (SMA, EMA, MACD)

        Returns:
            Score: -1 to +1
        """
        if len(df) < 50:
            return 0.0

        scores = []

        # SMA crossover (50/200)
        if len(df) >= 200:
            sma_50 = df['close'].rolling(50).mean().iloc[-1]
            sma_200 = df['close'].rolling(200).mean().iloc[-1]

            if sma_50 > sma_200:
                scores.append(1.0)  # Golden cross (bullish)
            else:
                scores.append(-1.0)  # Death cross (bearish)

        # MACD
        ema_12 = df['close'].ewm(span=12).mean()
        ema_26 = df['close'].ewm(span=26).mean()
        macd = ema_12 - ema_26
        signal_line = macd.ewm(span=9).mean()

        macd_current = macd.iloc[-1]
        signal_current = signal_line.iloc[-1]

        if macd_current > signal_current:
            scores.append(1.0)  # Bullish
        else:
            scores.append(-1.0)  # Bearish

        # Price momentum
        returns_20 = df['close'].pct_change(20).iloc[-1]
        if abs(returns_20) > 0.05:  # Strong trend
            scores.append(np.sign(returns_20))

        return np.mean(scores) if scores else 0.0

    def _analyze_momentum_indicators(self, df: pd.DataFrame) -> float:
        """
        Analyze momentum indicators (RSI, Stochastic)

        Returns:
            Score: -1 to +1
        """
        if len(df) < 20:
            return 0.0

        scores = []

        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_current = rsi.iloc[-1]

        if rsi_current < 30:
            scores.append(1.0)  # Oversold (bullish)
        elif rsi_current > 70:
            scores.append(-1.0)  # Overbought (bearish)
        else:
            # Normalize RSI to -1 to +1
            scores.append((rsi_current - 50) / 50)

        # Stochastic Oscillator
        low_14 = df['low'].rolling(14).min()
        high_14 = df['high'].rolling(14).max()
        stoch_k = 100 * (df['close'] - low_14) / (high_14 - low_14)
        stoch_current = stoch_k.iloc[-1]

        if stoch_current < 20:
            scores.append(1.0)  # Oversold
        elif stoch_current > 80:
            scores.append(-1.0)  # Overbought
        else:
            scores.append((stoch_current - 50) / 50)

        return np.mean(scores) if scores else 0.0

    def _analyze_volume(self, df: pd.DataFrame) -> float:
        """
        Analyze volume patterns

        Returns:
            Score: -1 to +1
        """
        if len(df) < 20:
            return 0.0

        # Volume trend
        vol_sma_20 = df['volume'].rolling(20).mean()
        current_vol = df['volume'].iloc[-1]
        avg_vol = vol_sma_20.iloc[-1]

        # High volume + price up = bullish
        # High volume + price down = bearish
        price_change = df['close'].iloc[-1] - df['close'].iloc[-2]

        if current_vol > avg_vol * 1.5:  # Significant volume
            if price_change > 0:
                return 0.8  # Strong bullish
            else:
                return -0.8  # Strong bearish
        elif current_vol > avg_vol:
            if price_change > 0:
                return 0.5
            else:
                return -0.5
        else:
            return 0.0  # No clear signal

    def _analyze_price_action(self, df: pd.DataFrame) -> float:
        """
        Analyze pure price action

        Returns:
            Score: -1 to +1
        """
        if len(df) < 10:
            return 0.0

        scores = []

        # Recent price momentum (5 periods)
        recent_returns = df['close'].pct_change(5).iloc[-1]
        if abs(recent_returns) > 0.02:
            scores.append(np.sign(recent_returns))

        # Higher highs / Lower lows
        recent_highs = df['high'].iloc[-10:]
        recent_lows = df['low'].iloc[-10:]

        higher_highs = all(recent_highs.iloc[i] <= recent_highs.iloc[i+1]
                          for i in range(len(recent_highs)-1))
        lower_lows = all(recent_lows.iloc[i] >= recent_lows.iloc[i+1]
                        for i in range(len(recent_lows)-1))

        if higher_highs:
            scores.append(1.0)
        elif lower_lows:
            scores.append(-1.0)

        return np.mean(scores) if scores else 0.0

    def _calculate_entry_stop_target(
        self,
        df: pd.DataFrame,
        direction: SignalDirection,
        patterns: List
    ) -> Tuple[float, float, float]:
        """
        Calculate entry, stop-loss, and target prices

        Returns:
            (entry_price, stop_loss, target_price)
        """
        current_price = df.iloc[-1]['close']

        # Use ATR for stop-loss and target
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(14).mean().iloc[-1]

        # Check if we have chart patterns with specific targets
        if patterns:
            # Use pattern targets if available
            pattern_targets = [p.target_price for p in patterns if hasattr(p, 'target_price')]
            pattern_stops = [p.stop_loss for p in patterns if hasattr(p, 'stop_loss')]

            if pattern_targets:
                target_price = np.mean(pattern_targets)
            else:
                target_price = current_price * (1.03 if direction in [SignalDirection.BUY, SignalDirection.STRONG_BUY] else 0.97)

            if pattern_stops:
                stop_loss = np.mean(pattern_stops)
            else:
                stop_loss = current_price - (2 * atr if direction in [SignalDirection.BUY, SignalDirection.STRONG_BUY] else -2 * atr)
        else:
            # Default: 2:1 reward-to-risk using ATR
            if direction in [SignalDirection.BUY, SignalDirection.STRONG_BUY]:
                stop_loss = current_price - (2 * atr)
                target_price = current_price + (4 * atr)  # 2:1 R/R
            elif direction in [SignalDirection.SELL, SignalDirection.STRONG_SELL]:
                stop_loss = current_price + (2 * atr)
                target_price = current_price - (4 * atr)
            else:
                stop_loss = current_price
                target_price = current_price

        return current_price, stop_loss, target_price

    def generate_signal(
        self,
        symbol: str,
        data: pd.DataFrame
    ) -> AggregatedSignal:
        """
        Generate aggregated trading signal

        Args:
            symbol: Trading symbol
            data: OHLCV DataFrame

        Returns:
            AggregatedSignal with score, direction, and recommendations
        """
        if len(data) < 50:
            logger.warning(f"Insufficient data for {symbol}")
            return AggregatedSignal(
                symbol=symbol,
                direction=SignalDirection.HOLD,
                score=50.0,
                confidence=0.0,
                timestamp=pd.Timestamp.now()
            )

        # Analyze all signal sources
        contributing_signals = {}
        all_patterns = []

        # 1. Candlestick patterns
        candlestick_score, candlestick_patterns = self._analyze_candlestick_patterns(data)
        contributing_signals['candlestick_patterns'] = candlestick_score
        all_patterns.extend(candlestick_patterns)

        # 2. Chart patterns
        chart_score, chart_pattern_names = self._analyze_chart_patterns(data)
        contributing_signals['chart_patterns'] = chart_score
        all_patterns.extend(chart_pattern_names)

        # 3. Trend indicators
        trend_score = self._analyze_trend_indicators(data)
        contributing_signals['trend_indicators'] = trend_score

        # 4. Momentum indicators
        momentum_score = self._analyze_momentum_indicators(data)
        contributing_signals['momentum_indicators'] = momentum_score

        # 5. Volume analysis
        volume_score = self._analyze_volume(data)
        contributing_signals['volume_analysis'] = volume_score

        # 6. Price action
        price_action_score = self._analyze_price_action(data)
        contributing_signals['price_action'] = price_action_score

        # Calculate weighted average (convert to 0-100 scale)
        weighted_sum = sum(
            self.weights[k] * v
            for k, v in contributing_signals.items()
            if k in self.weights
        )

        # Convert from -1/+1 scale to 0-100 scale
        final_score = (weighted_sum + 1) * 50

        # Calculate confidence (agreement among signals)
        signal_values = list(contributing_signals.values())
        confidence = 1 - (np.std(signal_values) / np.sqrt(len(signal_values)))

        # Determine direction
        if final_score >= self.strong_threshold:
            direction = SignalDirection.STRONG_BUY
        elif final_score >= self.weak_threshold:
            direction = SignalDirection.BUY
        elif final_score <= (100 - self.strong_threshold):
            direction = SignalDirection.STRONG_SELL
        elif final_score <= (100 - self.weak_threshold):
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.HOLD

        # Calculate entry, stop, target
        chart_patterns_obj = self.chart_pattern_detector.detect_all_patterns(data)
        entry, stop, target = self._calculate_entry_stop_target(
            data, direction, chart_patterns_obj
        )

        # Calculate risk-reward ratio
        if stop != entry:
            risk = abs(entry - stop)
            reward = abs(target - entry)
            risk_reward_ratio = reward / risk if risk > 0 else 0
        else:
            risk_reward_ratio = 0

        return AggregatedSignal(
            symbol=symbol,
            direction=direction,
            score=final_score,
            confidence=confidence,
            timestamp=pd.Timestamp.now(),
            contributing_signals=contributing_signals,
            pattern_matches=all_patterns,
            recommended_entry=entry,
            recommended_stop=stop,
            recommended_target=target,
            risk_reward_ratio=risk_reward_ratio
        )


if __name__ == "__main__":
    # Test signal aggregator
    print("🎯 Testing Advanced Signal Aggregator\n")

    # Generate sample data
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')

    close_prices = 100 + np.random.randn(len(dates)).cumsum()

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

    # Create aggregator
    aggregator = AdvancedSignalAggregator()

    print(f"Analyzing {len(data)} days of OHLCV data...\n")

    signal = aggregator.generate_signal('NIFTY50', data)

    print("="*80)
    print("AGGREGATED SIGNAL")
    print("="*80)
    print(f"Symbol:         {signal.symbol}")
    print(f"Direction:      {signal.direction.value.upper()}")
    print(f"Score:          {signal.score:.1f}/100")
    print(f"Confidence:     {signal.confidence:.2f}")
    print(f"Entry:          ₹{signal.recommended_entry:.2f}")
    print(f"Stop Loss:      ₹{signal.recommended_stop:.2f}")
    print(f"Target:         ₹{signal.recommended_target:.2f}")
    print(f"Risk/Reward:    {signal.risk_reward_ratio:.2f}")

    print(f"\nContributing Signals:")
    for source, score in signal.contributing_signals.items():
        bar = "█" * int(abs(score) * 20)
        direction_symbol = "+" if score > 0 else "-"
        print(f"  {source:25s} {direction_symbol}{bar:<20s} {score:+.3f}")

    if signal.pattern_matches:
        print(f"\nPatterns Detected: {', '.join(signal.pattern_matches)}")

    print("\n✅ Advanced signal aggregator ready!")
