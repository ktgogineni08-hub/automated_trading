#!/usr/bin/env python3
"""
AI-Enhanced Trading Strategy
Combines pattern recognition with ML-based signal aggregation

Integrates:
- Candlestick pattern recognition
- Chart pattern detection
- Multi-indicator analysis
- Volume confirmation
- ML-based confidence scoring
"""

import sys
from pathlib import Path
import pandas as pd
from typing import Dict
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategies.advanced_base import AdvancedBaseStrategy
from core.advanced_signal_aggregator import AdvancedSignalAggregator, SignalDirection

logger = logging.getLogger('trading_system.strategies.ai_enhanced')


class AIEnhancedStrategy(AdvancedBaseStrategy):
    """
    AI-Enhanced strategy using pattern recognition and multi-signal aggregation

    Features:
    - 11 candlestick patterns (Doji, Hammer, Engulfing, etc.)
    - 6 chart patterns (H&S, Double Top/Bottom, Triangles)
    - Trend indicators (MACD, SMA crossover)
    - Momentum indicators (RSI, Stochastic)
    - Volume analysis
    - Price action signals
    - ML-based confidence scoring

    Entry Criteria:
    - Aggregated score > 60 (BUY) or > 80 (STRONG_BUY)
    - Minimum confidence: 65%
    - Multiple pattern confirmation
    - Volume confirmation

    Exit Criteria:
    - Opposite signal with confidence > 50%
    - Stop-loss hit (ATR-based)
    - Target reached
    """

    def __init__(
        self,
        min_confidence: float = 0.65,
        strong_threshold: float = 80.0,
        weak_threshold: float = 60.0,
        confirmation_bars: int = 1,
        cooldown_minutes: int = 15
    ):
        """
        Initialize AI-Enhanced strategy

        Args:
            min_confidence: Minimum confidence for trade entry (0-1)
            strong_threshold: Score threshold for STRONG signals (0-100)
            weak_threshold: Score threshold for weak signals (0-100)
            confirmation_bars: Bars to wait for confirmation
            cooldown_minutes: Minutes to wait between signals
        """
        super().__init__(
            name="AI_Enhanced_Strategy",
            confirmation_bars=confirmation_bars,
            cooldown_minutes=cooldown_minutes
        )

        self.min_confidence = min_confidence
        self.strong_threshold = strong_threshold
        self.weak_threshold = weak_threshold

        # Initialize signal aggregator
        self.aggregator = AdvancedSignalAggregator(
            strong_threshold=strong_threshold,
            weak_threshold=weak_threshold
        )

        logger.info(
            f"AI Enhanced Strategy initialized: "
            f"min_confidence={min_confidence:.0%}, "
            f"thresholds={weak_threshold}/{strong_threshold}"
        )

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> Dict:
        """
        Generate trading signals using AI-enhanced analysis

        This is the main strategy logic that:
        1. Detects candlestick patterns
        2. Identifies chart patterns
        3. Analyzes technical indicators
        4. Aggregates all signals with ML scoring
        5. Returns high-confidence trade recommendations

        Args:
            data: OHLCV DataFrame with columns: open, high, low, close, volume
            symbol: Trading symbol (e.g., 'NIFTY50', 'BANKNIFTY', 'RELIANCE')

        Returns:
            Dict with:
                - signal: 1 (buy), -1 (sell), 0 (hold)
                - strength: confidence 0.0-1.0
                - reason: explanation string
        """
        # Validate data
        if not self.validate_data(data) or len(data) < 50:
            return {
                'signal': 0,
                'strength': 0.0,
                'reason': 'insufficient_data'
            }

        # Use 'unknown' if no symbol provided
        if symbol is None:
            symbol = 'unknown'

        # Check cooldown (inherited from AdvancedBaseStrategy)
        if self._is_on_cooldown(symbol):
            return {
                'signal': 0,
                'strength': 0.0,
                'reason': 'cooldown'
            }

        try:
            # Generate aggregated signal using all pattern recognition & indicators
            agg_signal = self.aggregator.generate_signal(symbol, data)

            # Log signal details
            logger.debug(
                f"{symbol} Signal: {agg_signal.direction.value} "
                f"(score={agg_signal.score:.1f}, conf={agg_signal.confidence:.2f})"
            )

            # Check confidence threshold
            if agg_signal.confidence < self.min_confidence:
                return {
                    'signal': 0,
                    'strength': agg_signal.confidence,
                    'reason': f'low_confidence_{agg_signal.confidence:.2f}'
                }

            # Get current position (inherited from AdvancedBaseStrategy)
            position = self.get_position(symbol)

            # ================================================================
            # EXIT LOGIC (if in position)
            # ================================================================

            # Exit long position on sell signal
            if position == 1 and agg_signal.direction in [
                SignalDirection.SELL,
                SignalDirection.STRONG_SELL
            ]:
                self._update_signal_time(symbol)
                logger.info(
                    f"🔴 EXIT LONG {symbol}: {agg_signal.direction.value} "
                    f"(score={agg_signal.score:.0f}, patterns={len(agg_signal.pattern_matches)})"
                )
                return {
                    'signal': -1,
                    'strength': agg_signal.confidence,
                    'reason': f'exit_long_{agg_signal.direction.value}_score_{agg_signal.score:.0f}'
                }

            # Exit short position on buy signal
            elif position == -1 and agg_signal.direction in [
                SignalDirection.BUY,
                SignalDirection.STRONG_BUY
            ]:
                self._update_signal_time(symbol)
                logger.info(
                    f"🟢 EXIT SHORT {symbol}: {agg_signal.direction.value} "
                    f"(score={agg_signal.score:.0f}, patterns={len(agg_signal.pattern_matches)})"
                )
                return {
                    'signal': 1,
                    'strength': agg_signal.confidence,
                    'reason': f'exit_short_{agg_signal.direction.value}_score_{agg_signal.score:.0f}'
                }

            # ================================================================
            # ENTRY LOGIC (if flat / no position)
            # ================================================================

            if position == 0:
                # BUY signal
                if agg_signal.direction in [SignalDirection.BUY, SignalDirection.STRONG_BUY]:
                    self._update_signal_time(symbol)

                    # Calculate strength multiplier for STRONG signals
                    strength_multiplier = 1.2 if agg_signal.direction == SignalDirection.STRONG_BUY else 1.0
                    final_strength = min(agg_signal.confidence * strength_multiplier, 1.0)

                    # Log entry with pattern details
                    pattern_str = ', '.join(agg_signal.pattern_matches[:3])  # Show first 3
                    logger.info(
                        f"🟢 BUY {symbol}: score={agg_signal.score:.0f}, "
                        f"conf={agg_signal.confidence:.2f}, "
                        f"patterns=[{pattern_str}], "
                        f"R/R={agg_signal.risk_reward_ratio:.2f}"
                    )

                    return {
                        'signal': 1,
                        'strength': final_strength,
                        'reason': (
                            f'buy_score_{agg_signal.score:.0f}_'
                            f'patterns_{len(agg_signal.pattern_matches)}_'
                            f'rr_{agg_signal.risk_reward_ratio:.1f}'
                        )
                    }

                # SELL signal
                elif agg_signal.direction in [SignalDirection.SELL, SignalDirection.STRONG_SELL]:
                    self._update_signal_time(symbol)

                    # Calculate strength multiplier for STRONG signals
                    strength_multiplier = 1.2 if agg_signal.direction == SignalDirection.STRONG_SELL else 1.0
                    final_strength = min(agg_signal.confidence * strength_multiplier, 1.0)

                    # Log entry with pattern details
                    pattern_str = ', '.join(agg_signal.pattern_matches[:3])
                    logger.info(
                        f"🔴 SELL {symbol}: score={agg_signal.score:.0f}, "
                        f"conf={agg_signal.confidence:.2f}, "
                        f"patterns=[{pattern_str}], "
                        f"R/R={agg_signal.risk_reward_ratio:.2f}"
                    )

                    return {
                        'signal': -1,
                        'strength': final_strength,
                        'reason': (
                            f'sell_score_{agg_signal.score:.0f}_'
                            f'patterns_{len(agg_signal.pattern_matches)}_'
                            f'rr_{agg_signal.risk_reward_ratio:.1f}'
                        )
                    }

            # No signal (HOLD)
            return {
                'signal': 0,
                'strength': 0.0,
                'reason': f'hold_score_{agg_signal.score:.0f}'
            }

        except Exception as e:
            logger.error(
                f"Error in AI Enhanced strategy for {symbol}: {e}",
                exc_info=True
            )
            return {
                'signal': 0,
                'strength': 0.0,
                'reason': 'error'
            }

    def get_stop_loss_target(
        self,
        data: pd.DataFrame,
        symbol: str,
        entry_price: float,
        position: int
    ) -> Dict[str, float]:
        """
        Get recommended stop-loss and target prices

        This uses the signal aggregator's recommendations which are based on:
        - ATR (Average True Range) for volatility
        - Chart pattern targets
        - Support/resistance levels

        Args:
            data: OHLCV DataFrame
            symbol: Trading symbol
            entry_price: Entry price
            position: 1 (long), -1 (short)

        Returns:
            Dict with 'stop_loss' and 'target'
        """
        try:
            agg_signal = self.aggregator.generate_signal(symbol, data)

            return {
                'stop_loss': agg_signal.recommended_stop,
                'target': agg_signal.recommended_target,
                'risk_reward': agg_signal.risk_reward_ratio
            }

        except Exception as e:
            logger.error(f"Error calculating stop/target for {symbol}: {e}")

            # Fallback: 2% stop, 4% target (2:1 R/R)
            if position == 1:  # Long
                return {
                    'stop_loss': entry_price * 0.98,
                    'target': entry_price * 1.04,
                    'risk_reward': 2.0
                }
            else:  # Short
                return {
                    'stop_loss': entry_price * 1.02,
                    'target': entry_price * 0.96,
                    'risk_reward': 2.0
                }


if __name__ == "__main__":
    # Test the strategy
    import numpy as np

    print("🧪 Testing AI-Enhanced Strategy\n")

    # Generate sample data
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
    close_prices = 100 + np.random.randn(len(dates)).cumsum() * 0.5

    data = pd.DataFrame({
        'open': close_prices * (1 + np.random.randn(len(dates)) * 0.005),
        'high': close_prices * (1 + abs(np.random.randn(len(dates))) * 0.015),
        'low': close_prices * (1 - abs(np.random.randn(len(dates))) * 0.015),
        'close': close_prices,
        'volume': np.random.randint(100000, 1000000, len(dates))
    }, index=dates)

    data['high'] = data[['open', 'high', 'close']].max(axis=1)
    data['low'] = data[['open', 'low', 'close']].min(axis=1)

    # Initialize strategy
    strategy = AIEnhancedStrategy(
        min_confidence=0.65,
        strong_threshold=80.0,
        weak_threshold=60.0
    )

    print(f"Analyzing {len(data)} days of data...\n")

    # Generate signal
    signal = strategy.generate_signals(data, 'TEST_SYMBOL')

    print("="*80)
    print("STRATEGY SIGNAL")
    print("="*80)
    print(f"Signal:         {signal['signal']} ({'BUY' if signal['signal'] == 1 else 'SELL' if signal['signal'] == -1 else 'HOLD'})")
    print(f"Strength:       {signal['strength']:.2f}")
    print(f"Reason:         {signal['reason']}")

    if signal['signal'] != 0:
        # Get stop/target
        entry_price = data.iloc[-1]['close']
        stops = strategy.get_stop_loss_target(data, 'TEST_SYMBOL', entry_price, signal['signal'])

        print(f"\nEntry:          ₹{entry_price:.2f}")
        print(f"Stop Loss:      ₹{stops['stop_loss']:.2f}")
        print(f"Target:         ₹{stops['target']:.2f}")
        print(f"Risk/Reward:    {stops['risk_reward']:.2f}")

    print("\n✅ AI-Enhanced Strategy ready for integration!")
