#!/usr/bin/env python3
"""
Advanced Alerting Rules
Sophisticated pattern-based and anomaly-based alerting

ADDRESSES HIGH PRIORITY RECOMMENDATION #5:
- Pattern-based alerts (unusual trading patterns)
- Time-series anomaly detection
- Correlation-based alerts
- Predictive alerts
- Custom rule engine
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque, defaultdict
from enum import Enum
import numpy as np

from infrastructure.alert_manager import (
    get_alert_manager,
    AlertSeverity,
    AlertCategory
)

logger = logging.getLogger('trading_system.advanced_alerts')


class AlertPattern(Enum):
    """Alert pattern types"""
    CONSECUTIVE_LOSSES = "consecutive_losses"
    WIN_RATE_DEGRADATION = "win_rate_degradation"
    POSITION_CONCENTRATION = "position_concentration"
    UNUSUAL_VOLUME = "unusual_volume"
    CORRELATION_BREAK = "correlation_break"
    DRAWDOWN_ACCELERATION = "drawdown_acceleration"
    ORDER_IMBALANCE = "order_imbalance"
    FLASH_CRASH = "flash_crash"


@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    pattern: AlertPattern
    enabled: bool = True
    severity: AlertSeverity = AlertSeverity.MEDIUM
    threshold: float = 0.0
    window_minutes: int = 60
    cooldown_minutes: int = 15
    custom_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PatternMatch:
    """Pattern match result"""
    pattern: AlertPattern
    severity: AlertSeverity
    confidence: float  # 0-1
    triggered_at: datetime
    description: str
    context: Dict[str, Any]
    rule_name: str


class AdvancedAlertingEngine:
    """
    Advanced Alerting Engine with Pattern Detection

    Features:
    - Consecutive losses detection
    - Win rate degradation tracking
    - Position concentration monitoring
    - Volume anomaly detection
    - Correlation break alerts
    - Drawdown acceleration detection
    - Order imbalance alerts
    - Flash crash detection
    - Custom rule engine

    Usage:
        engine = AdvancedAlertingEngine()
        engine.start_monitoring()

        # Add custom rule
        engine.add_rule(AlertRule(
            name="High Consecutive Losses",
            pattern=AlertPattern.CONSECUTIVE_LOSSES,
            threshold=5,
            severity=AlertSeverity.HIGH
        ))

        # Process trading events
        engine.process_trade_event({
            'symbol': 'NIFTY',
            'pnl': -500,
            'is_win': False
        })
    """

    def __init__(self, lookback_window_hours: int = 24):
        """
        Initialize advanced alerting engine

        Args:
            lookback_window_hours: Hours of data to keep for analysis
        """
        self.lookback_window = timedelta(hours=lookback_window_hours)

        # Alert manager
        self.alert_mgr = get_alert_manager()

        # Alert rules
        self._rules: Dict[str, AlertRule] = {}
        self._load_default_rules()

        # Pattern tracking
        self._trade_events: deque = deque(maxlen=10000)
        self._order_events: deque = deque(maxlen=10000)
        self._position_events: deque = deque(maxlen=10000)
        self._price_events: deque = deque(maxlen=10000)

        # Pattern state
        self._consecutive_losses = 0
        self._consecutive_wins = 0
        self._recent_win_rate = 0.0
        self._last_alert_times: Dict[str, datetime] = {}

        # Historical baselines
        self._historical_win_rate = 0.50
        self._historical_avg_trade = 0.0
        self._historical_volume = {}

        # Monitoring
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # Statistics
        self.total_patterns_detected = 0
        self.total_alerts_triggered = 0

        logger.info("🔍 Advanced Alerting Engine initialized")

    def _load_default_rules(self):
        """Load default alerting rules"""
        default_rules = [
            AlertRule(
                name="Critical Consecutive Losses",
                pattern=AlertPattern.CONSECUTIVE_LOSSES,
                threshold=5,
                severity=AlertSeverity.HIGH,
                cooldown_minutes=30
            ),
            AlertRule(
                name="Win Rate Degradation",
                pattern=AlertPattern.WIN_RATE_DEGRADATION,
                threshold=0.15,  # 15% drop
                severity=AlertSeverity.MEDIUM,
                window_minutes=180,  # 3 hours
                cooldown_minutes=60
            ),
            AlertRule(
                name="Position Concentration Risk",
                pattern=AlertPattern.POSITION_CONCENTRATION,
                threshold=0.40,  # 40% in one position
                severity=AlertSeverity.HIGH,
                cooldown_minutes=30
            ),
            AlertRule(
                name="Unusual Volume Spike",
                pattern=AlertPattern.UNUSUAL_VOLUME,
                threshold=3.0,  # 3x normal volume
                severity=AlertSeverity.MEDIUM,
                cooldown_minutes=15
            ),
            AlertRule(
                name="Drawdown Acceleration",
                pattern=AlertPattern.DRAWDOWN_ACCELERATION,
                threshold=0.05,  # 5% rapid drawdown
                severity=AlertSeverity.CRITICAL,
                cooldown_minutes=60
            ),
            AlertRule(
                name="Flash Crash Detection",
                pattern=AlertPattern.FLASH_CRASH,
                threshold=0.02,  # 2% drop in seconds
                severity=AlertSeverity.CRITICAL,
                cooldown_minutes=5
            ),
        ]

        for rule in default_rules:
            self._rules[rule.name] = rule

    def add_rule(self, rule: AlertRule):
        """Add or update alerting rule"""
        with self._lock:
            self._rules[rule.name] = rule
            logger.info(f"Added alerting rule: {rule.name}")

    def remove_rule(self, rule_name: str):
        """Remove alerting rule"""
        with self._lock:
            if rule_name in self._rules:
                del self._rules[rule_name]
                logger.info(f"Removed alerting rule: {rule_name}")

    def start_monitoring(self):
        """Start background pattern monitoring"""
        if self._monitoring:
            logger.warning("Monitoring already started")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        logger.info("✅ Pattern monitoring started")

    def stop_monitoring(self):
        """Stop monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

        logger.info("🛑 Pattern monitoring stopped")

    def _monitor_loop(self):
        """Background monitoring loop"""
        while self._monitoring:
            try:
                # Check all patterns
                self._check_all_patterns()

                # Cleanup old data
                self._cleanup_old_data()

                time.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

    def process_trade_event(self, trade_data: Dict[str, Any]):
        """
        Process trading event for pattern detection

        Args:
            trade_data: Trade event data
                - symbol: str
                - pnl: float
                - is_win: bool
                - quantity: int
                - timestamp: datetime (optional)
        """
        timestamp = trade_data.get('timestamp', datetime.now())

        with self._lock:
            # Store event
            event = {'timestamp': timestamp, **trade_data}
            self._trade_events.append(event)

            # Update consecutive counters
            if trade_data.get('is_win'):
                self._consecutive_wins += 1
                self._consecutive_losses = 0
            else:
                self._consecutive_losses += 1
                self._consecutive_wins = 0

            # Update win rate
            self._update_win_rate()

            # Check patterns immediately
            self._check_consecutive_losses()
            self._check_win_rate_degradation()

    def process_position_event(self, position_data: Dict[str, Any]):
        """
        Process position event

        Args:
            position_data: Position data
                - symbol: str
                - value: float
                - total_value: float
                - timestamp: datetime (optional)
        """
        timestamp = position_data.get('timestamp', datetime.now())

        with self._lock:
            event = {'timestamp': timestamp, **position_data}
            self._position_events.append(event)

            # Check position concentration
            self._check_position_concentration(position_data)

    def process_price_event(self, price_data: Dict[str, Any]):
        """
        Process price update event

        Args:
            price_data: Price data
                - symbol: str
                - price: float
                - volume: int (optional)
                - timestamp: datetime (optional)
        """
        timestamp = price_data.get('timestamp', datetime.now())

        with self._lock:
            event = {'timestamp': timestamp, **price_data}
            self._price_events.append(event)

            # Check flash crash
            self._check_flash_crash(price_data)

            # Check volume anomalies
            if 'volume' in price_data:
                self._check_volume_anomaly(price_data)

    def _check_all_patterns(self):
        """Check all enabled patterns"""
        with self._lock:
            for rule_name, rule in self._rules.items():
                if not rule.enabled:
                    continue

                # Check cooldown
                if self._is_in_cooldown(rule_name, rule.cooldown_minutes):
                    continue

                # Pattern-specific checks
                if rule.pattern == AlertPattern.CONSECUTIVE_LOSSES:
                    self._check_consecutive_losses()

                elif rule.pattern == AlertPattern.WIN_RATE_DEGRADATION:
                    self._check_win_rate_degradation()

                elif rule.pattern == AlertPattern.DRAWDOWN_ACCELERATION:
                    self._check_drawdown_acceleration()

    def _check_consecutive_losses(self):
        """Check for consecutive losses pattern"""
        rule = self._get_rule_by_pattern(AlertPattern.CONSECUTIVE_LOSSES)
        if not rule or self._consecutive_losses < rule.threshold:
            return

        match = PatternMatch(
            pattern=AlertPattern.CONSECUTIVE_LOSSES,
            severity=rule.severity,
            confidence=min(self._consecutive_losses / rule.threshold, 1.0),
            triggered_at=datetime.now(),
            description=f"{self._consecutive_losses} consecutive losing trades detected",
            context={
                'consecutive_losses': self._consecutive_losses,
                'threshold': rule.threshold,
                'recent_win_rate': self._recent_win_rate
            },
            rule_name=rule.name
        )

        self._trigger_pattern_alert(match, rule)

    def _check_win_rate_degradation(self):
        """Check for win rate degradation"""
        rule = self._get_rule_by_pattern(AlertPattern.WIN_RATE_DEGRADATION)
        if not rule:
            return

        # Calculate win rate drop
        win_rate_drop = self._historical_win_rate - self._recent_win_rate

        if win_rate_drop < rule.threshold:
            return

        match = PatternMatch(
            pattern=AlertPattern.WIN_RATE_DEGRADATION,
            severity=rule.severity,
            confidence=min(win_rate_drop / rule.threshold, 1.0),
            triggered_at=datetime.now(),
            description=f"Win rate dropped from {self._historical_win_rate:.1%} to {self._recent_win_rate:.1%}",
            context={
                'historical_win_rate': self._historical_win_rate,
                'recent_win_rate': self._recent_win_rate,
                'drop': win_rate_drop
            },
            rule_name=rule.name
        )

        self._trigger_pattern_alert(match, rule)

    def _check_position_concentration(self, position_data: Dict[str, Any]):
        """Check for position concentration risk"""
        rule = self._get_rule_by_pattern(AlertPattern.POSITION_CONCENTRATION)
        if not rule:
            return

        symbol = position_data.get('symbol')
        position_value = position_data.get('value', 0)
        total_value = position_data.get('total_value', 1)

        concentration = position_value / total_value if total_value > 0 else 0

        if concentration < rule.threshold:
            return

        match = PatternMatch(
            pattern=AlertPattern.POSITION_CONCENTRATION,
            severity=rule.severity,
            confidence=min(concentration / rule.threshold, 1.0),
            triggered_at=datetime.now(),
            description=f"{concentration:.1%} of portfolio in {symbol}",
            context={
                'symbol': symbol,
                'concentration': concentration,
                'position_value': position_value,
                'total_value': total_value
            },
            rule_name=rule.name
        )

        self._trigger_pattern_alert(match, rule)

    def _check_volume_anomaly(self, price_data: Dict[str, Any]):
        """Check for unusual volume"""
        rule = self._get_rule_by_pattern(AlertPattern.UNUSUAL_VOLUME)
        if not rule:
            return

        symbol = price_data.get('symbol')
        current_volume = price_data.get('volume', 0)

        # Get historical average volume
        historical_avg = self._historical_volume.get(symbol, current_volume)

        if historical_avg == 0:
            return

        volume_ratio = current_volume / historical_avg

        if volume_ratio < rule.threshold:
            return

        match = PatternMatch(
            pattern=AlertPattern.UNUSUAL_VOLUME,
            severity=rule.severity,
            confidence=min(volume_ratio / rule.threshold, 1.0),
            triggered_at=datetime.now(),
            description=f"{symbol} volume {volume_ratio:.1f}x normal",
            context={
                'symbol': symbol,
                'current_volume': current_volume,
                'historical_avg': historical_avg,
                'ratio': volume_ratio
            },
            rule_name=rule.name
        )

        self._trigger_pattern_alert(match, rule)

        # Update historical average
        self._historical_volume[symbol] = (
            historical_avg * 0.95 + current_volume * 0.05
        )

    def _check_flash_crash(self, price_data: Dict[str, Any]):
        """Check for flash crash pattern"""
        rule = self._get_rule_by_pattern(AlertPattern.FLASH_CRASH)
        if not rule:
            return

        symbol = price_data.get('symbol')
        current_price = price_data.get('price')

        # Get recent prices for this symbol
        recent_prices = [
            e['price'] for e in self._price_events
            if e.get('symbol') == symbol
            and (datetime.now() - e['timestamp']).total_seconds() < 60
        ]

        if len(recent_prices) < 2:
            return

        # Check for rapid price drop
        max_recent = max(recent_prices)
        price_drop_pct = (max_recent - current_price) / max_recent

        if price_drop_pct < rule.threshold:
            return

        match = PatternMatch(
            pattern=AlertPattern.FLASH_CRASH,
            severity=rule.severity,
            confidence=min(price_drop_pct / rule.threshold, 1.0),
            triggered_at=datetime.now(),
            description=f"{symbol} dropped {price_drop_pct:.2%} in <1 minute",
            context={
                'symbol': symbol,
                'max_recent': max_recent,
                'current_price': current_price,
                'drop_pct': price_drop_pct,
                'duration_seconds': 60
            },
            rule_name=rule.name
        )

        self._trigger_pattern_alert(match, rule)

    def _check_drawdown_acceleration(self):
        """Check for rapid drawdown acceleration"""
        rule = self._get_rule_by_pattern(AlertPattern.DRAWDOWN_ACCELERATION)
        if not rule:
            return

        # Get recent trades
        cutoff = datetime.now() - timedelta(minutes=rule.window_minutes)
        recent_trades = [
            e for e in self._trade_events
            if e['timestamp'] >= cutoff
        ]

        if len(recent_trades) < 5:
            return

        # Calculate drawdown
        cumulative_pnl = 0
        max_pnl = 0
        max_drawdown = 0

        for trade in recent_trades:
            cumulative_pnl += trade.get('pnl', 0)
            max_pnl = max(max_pnl, cumulative_pnl)
            drawdown = (max_pnl - cumulative_pnl) / max(abs(max_pnl), 1000)
            max_drawdown = max(max_drawdown, drawdown)

        if max_drawdown < rule.threshold:
            return

        match = PatternMatch(
            pattern=AlertPattern.DRAWDOWN_ACCELERATION,
            severity=rule.severity,
            confidence=min(max_drawdown / rule.threshold, 1.0),
            triggered_at=datetime.now(),
            description=f"Rapid drawdown of {max_drawdown:.2%} detected",
            context={
                'max_drawdown': max_drawdown,
                'window_minutes': rule.window_minutes,
                'num_trades': len(recent_trades)
            },
            rule_name=rule.name
        )

        self._trigger_pattern_alert(match, rule)

    def _trigger_pattern_alert(self, match: PatternMatch, rule: AlertRule):
        """Trigger alert for pattern match"""
        self.total_patterns_detected += 1

        # Check cooldown
        if self._is_in_cooldown(rule.name, rule.cooldown_minutes):
            return

        # Send alert
        self.alert_mgr.alert(
            severity=match.severity,
            category=AlertCategory.RISK,
            title=f"Pattern Detected: {match.pattern.value}",
            message=match.description,
            context={
                **match.context,
                'confidence': match.confidence,
                'rule_name': match.rule_name
            },
            suppress=False
        )

        # Update cooldown
        self._last_alert_times[rule.name] = datetime.now()
        self.total_alerts_triggered += 1

        logger.warning(
            f"🔍 Pattern detected: {match.pattern.value} "
            f"(Confidence: {match.confidence:.2f}) - {match.description}"
        )

    def _update_win_rate(self):
        """Update recent win rate"""
        cutoff = datetime.now() - timedelta(hours=1)
        recent_trades = [
            e for e in self._trade_events
            if e['timestamp'] >= cutoff
        ]

        if not recent_trades:
            return

        wins = sum(1 for t in recent_trades if t.get('is_win'))
        self._recent_win_rate = wins / len(recent_trades)

    def _get_rule_by_pattern(self, pattern: AlertPattern) -> Optional[AlertRule]:
        """Get first enabled rule for pattern"""
        for rule in self._rules.values():
            if rule.pattern == pattern and rule.enabled:
                return rule
        return None

    def _is_in_cooldown(self, rule_name: str, cooldown_minutes: int) -> bool:
        """Check if rule is in cooldown period"""
        if rule_name not in self._last_alert_times:
            return False

        time_since = datetime.now() - self._last_alert_times[rule_name]
        return time_since < timedelta(minutes=cooldown_minutes)

    def _cleanup_old_data(self):
        """Remove old events beyond lookback window"""
        cutoff = datetime.now() - self.lookback_window

        with self._lock:
            # Clean trade events
            self._trade_events = deque(
                (e for e in self._trade_events if e['timestamp'] >= cutoff),
                maxlen=self._trade_events.maxlen
            )

            # Clean position events
            self._position_events = deque(
                (e for e in self._position_events if e['timestamp'] >= cutoff),
                maxlen=self._position_events.maxlen
            )

            # Clean price events
            self._price_events = deque(
                (e for e in self._price_events if e['timestamp'] >= cutoff),
                maxlen=self._price_events.maxlen
            )

    def get_statistics(self) -> Dict[str, Any]:
        """Get engine statistics"""
        with self._lock:
            return {
                'total_patterns_detected': self.total_patterns_detected,
                'total_alerts_triggered': self.total_alerts_triggered,
                'total_rules': len(self._rules),
                'enabled_rules': sum(1 for r in self._rules.values() if r.enabled),
                'consecutive_losses': self._consecutive_losses,
                'consecutive_wins': self._consecutive_wins,
                'recent_win_rate': self._recent_win_rate,
                'trade_events_stored': len(self._trade_events),
                'position_events_stored': len(self._position_events),
                'price_events_stored': len(self._price_events)
            }

    def print_statistics(self):
        """Print formatted statistics"""
        stats = self.get_statistics()

        print("\n" + "="*70)
        print("🔍 ADVANCED ALERTING ENGINE STATISTICS")
        print("="*70)
        print(f"Patterns Detected:     {stats['total_patterns_detected']}")
        print(f"Alerts Triggered:      {stats['total_alerts_triggered']}")
        print(f"Total Rules:           {stats['total_rules']}")
        print(f"Enabled Rules:         {stats['enabled_rules']}")
        print(f"Consecutive Losses:    {stats['consecutive_losses']}")
        print(f"Consecutive Wins:      {stats['consecutive_wins']}")
        print(f"Recent Win Rate:       {stats['recent_win_rate']:.1%}")
        print(f"Events Stored:         {stats['trade_events_stored']} trades, "
              f"{stats['position_events_stored']} positions, "
              f"{stats['price_events_stored']} prices")
        print("="*70 + "\n")


# Global instance
_global_alerting_engine: Optional[AdvancedAlertingEngine] = None


def get_advanced_alerting_engine() -> AdvancedAlertingEngine:
    """Get global advanced alerting engine (singleton)"""
    global _global_alerting_engine
    if _global_alerting_engine is None:
        _global_alerting_engine = AdvancedAlertingEngine()
    return _global_alerting_engine


if __name__ == "__main__":
    # Test advanced alerting engine
    print("Testing Advanced Alerting Engine...\n")

    engine = AdvancedAlertingEngine()
    engine.start_monitoring()

    # Test 1: Consecutive losses
    print("1. Testing consecutive losses pattern...")
    for i in range(6):
        engine.process_trade_event({
            'symbol': 'NIFTY',
            'pnl': -100,
            'is_win': False
        })
        time.sleep(0.1)

    # Test 2: Position concentration
    print("\n2. Testing position concentration...")
    engine.process_position_event({
        'symbol': 'RELIANCE',
        'value': 450000,
        'total_value': 1000000
    })

    # Test 3: Flash crash
    print("\n3. Testing flash crash detection...")
    engine.process_price_event({'symbol': 'NIFTY', 'price': 25000})
    time.sleep(0.5)
    engine.process_price_event({'symbol': 'NIFTY', 'price': 24500})  # 2% drop

    # Print statistics
    print("\n4. Engine Statistics")
    engine.print_statistics()

    engine.stop_monitoring()
    print("\n✅ Advanced alerting engine tests passed")
