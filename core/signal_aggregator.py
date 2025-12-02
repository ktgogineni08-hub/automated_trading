#!/usr/bin/env python3
"""
Enhanced Signal Aggregator
Combines signals from multiple strategies with market regime awareness
"""

import numpy as np
from typing import Dict, List, Any, Optional
import logging
import config

logger = logging.getLogger('trading_system.signal_aggregator')


class EnhancedSignalAggregator:
    """
    Aggregates signals from multiple trading strategies

    Features:
    - Weighted confidence scoring
    - Strategy agreement threshold
    - Market regime awareness (bullish/bearish/neutral)
    - Lower thresholds for exits vs entries (risk management)

    Configuration:
    - min_agreement: Minimum fraction of strategies that must agree
    - market_bias: Current market regime ('bullish', 'bearish', 'neutral')

    Risk Management Principles:
    - Exits easier than entries (lower agreement threshold)
    - Always allow exits regardless of regime
    - Only filter NEW entries based on regime
    """

    def __init__(self, min_agreement: float = None):
        self.min_agreement = min_agreement or config.signal_agreement_threshold
        self.signal_history: Dict[str, List] = {}
        self.market_bias: str = 'neutral'
        self.market_regime: Dict[str, Any] = {}

    def update_market_regime(self, regime_info: Optional[Dict[str, Any]]) -> None:
        """
        Update market regime information

        Args:
            regime_info: Dict with 'bias' or 'regime' key ('bullish', 'bearish', 'neutral')
        """
        regime_info = regime_info or {}
        self.market_regime = regime_info
        bias = regime_info.get('bias') or regime_info.get('regime') or 'neutral'
        bias = bias.lower() if isinstance(bias, str) else 'neutral'
        if bias not in ('bullish', 'bearish'):
            bias = 'neutral'
        self.market_bias = bias

    def _regime_allows(self, action: str, is_exit: bool = False) -> bool:
        """
        Check if market regime allows an action

        Args:
            action: 'buy' or 'sell'
            is_exit: True if this is closing an existing position (always allow exits)

        Returns:
            True if action is allowed

        CRITICAL: Always allow exits regardless of regime.
        Only filter NEW entry signals, not position liquidations.
        """
        # Always allow exits regardless of regime
        if is_exit:
            return True

        # Filter entries based on market regime
        if self.market_bias == 'bullish' and action == 'sell':
            return False
        if self.market_bias == 'bearish' and action == 'buy':
            return False
        return True

    def aggregate_signals(self, strategy_signals: List[Dict], symbol: str,
                         is_exit: bool = False) -> Dict:
        """
        Aggregate signals from multiple strategies

        Args:
            strategy_signals: List of strategy signal dicts with keys:
                - signal: 1 (buy), -1 (sell), 0 (hold)
                - strength: 0.0-1.0 confidence
                - reason: explanation string
            symbol: Trading symbol
            is_exit: True if evaluating exit signal for existing position

        Returns:
            Dict with:
                - action: 'buy', 'sell', or 'hold'
                - confidence: 0.0-1.0 weighted confidence
                - reasons: list of reason strings

        Risk Management:
        - For exits: require only 1/N strategies to agree (any exit signal triggers)
        - For entries: require normal agreement threshold
        - Exits always allowed regardless of regime
        """
        if not strategy_signals:
            return {'action': 'hold', 'confidence': 0.0, 'reasons': []}

        buy_signals = []
        sell_signals = []
        reasons = []

        # Collect signals
        for sig in strategy_signals:
            if not isinstance(sig, dict):
                continue
            if sig.get('signal') == 1:
                buy_signals.append(sig.get('strength', 0.0))
                reasons.append(sig.get('reason', ''))
            elif sig.get('signal') == -1:
                sell_signals.append(sig.get('strength', 0.0))
                reasons.append(sig.get('reason', ''))

        # Calculate confidence and agreement
        buy_confidence = float(np.mean(buy_signals)) if buy_signals else 0.0
        sell_confidence = float(np.mean(sell_signals)) if sell_signals else 0.0

        total_strategies = len([s for s in strategy_signals if isinstance(s, dict)])
        buy_agreement = len(buy_signals) / total_strategies if total_strategies > 0 else 0
        sell_agreement = len(sell_signals) / total_strategies if total_strategies > 0 else 0

        # CRITICAL: Lower agreement threshold for exits
        # Risk management principle: exits should be easier than entries
        # Any single strategy detecting danger should be able to trigger exit
        min_agreement_threshold = self.min_agreement
        if is_exit and total_strategies > 0:
            # For exits, require only 1 strategy to agree (1/N = any exit signal)
            min_agreement_threshold = 1.0 / total_strategies
            logger.debug(f"Exit mode for {symbol}: lowered agreement threshold to {min_agreement_threshold:.1%}")

        # Evaluate buy signals
        if buy_agreement >= min_agreement_threshold and buy_confidence > 0.20:
            confidence = buy_confidence * (0.6 + buy_agreement * 0.4)
            if self._regime_allows('buy', is_exit=is_exit):
                return {'action': 'buy', 'confidence': confidence, 'reasons': reasons}
            # Only log if this was a new entry being blocked (not an exit)
            if not is_exit:
                logger.info(f"🚫 Regime bias ({self.market_bias}) blocked BUY entry on {symbol}")

        # Evaluate sell signals
        elif sell_agreement >= min_agreement_threshold and sell_confidence > 0.20:
            confidence = sell_confidence * (0.6 + sell_agreement * 0.4)
            if self._regime_allows('sell', is_exit=is_exit):
                return {'action': 'sell', 'confidence': confidence, 'reasons': reasons}
            # Only log if this was a new entry being blocked (not an exit)
            if not is_exit:
                logger.info(f"🚫 Regime bias ({self.market_bias}) blocked SELL entry on {symbol}")

        return {'action': 'hold', 'confidence': 0.0, 'reasons': []}
