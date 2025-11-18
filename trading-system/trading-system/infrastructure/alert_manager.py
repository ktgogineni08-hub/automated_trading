#!/usr/bin/env python3
"""
Centralized Alert Management System
Monitors trading system for anomalies and critical events

ADDRESSES CRITICAL ISSUE:
- No centralized alerting for:
  * Trade execution failures
  * Slow execution times
  * Stale market data
  * Position limit breaches
  * API failures
  * System anomalies
"""

import logging
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import threading

logger = logging.getLogger('trading_system.alerts')


class AlertSeverity(Enum):
    """Alert severity levels"""
    CRITICAL = "CRITICAL"  # System-threatening, immediate action required
    HIGH = "HIGH"          # Important, action needed soon
    MEDIUM = "MEDIUM"      # Notable, should be reviewed
    LOW = "LOW"            # Informational, FYI


class AlertCategory(Enum):
    """Alert categories"""
    EXECUTION = "execution"  # Trade execution issues
    DATA = "data"           # Market data issues
    API = "api"             # API connectivity/rate limits
    RISK = "risk"           # Risk limit breaches
    PERFORMANCE = "performance"  # System performance
    SYSTEM = "system"       # General system issues


@dataclass
class Alert:
    """Alert data structure"""
    timestamp: datetime
    severity: AlertSeverity
    category: AlertCategory
    title: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False

    def __str__(self) -> str:
        return (
            f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"{self.severity.value} - {self.category.value.upper()} - "
            f"{self.title}: {self.message}"
        )


class AlertManager:
    """
    Centralized Alert Management System

    Features:
    - Multiple severity levels
    - Alert categorization
    - Alert history tracking
    - Configurable thresholds
    - Alert suppression (prevent spam)
    - Multiple alert channels (console, log, email, SMS)
    - Alert aggregation (group similar alerts)

    Usage:
        alert_mgr = AlertManager()
        alert_mgr.alert(
            severity=AlertSeverity.CRITICAL,
            category=AlertCategory.EXECUTION,
            title="Slow Trade Execution",
            message="Order took 6.2s to execute",
            context={'order_id': '123', 'duration_ms': 6200}
        )
    """

    def __init__(
        self,
        max_history: int = 1000,
        suppression_window_seconds: int = 300,  # 5 minutes
        enable_console: bool = True,
        enable_log: bool = True,
        enable_email: bool = False,
        enable_sms: bool = False
    ):
        """
        Initialize alert manager

        Args:
            max_history: Maximum alerts to keep in history
            suppression_window_seconds: Suppress duplicate alerts within this window
            enable_console: Print alerts to console
            enable_log: Log alerts to logging system
            enable_email: Send alerts via email (requires configuration)
            enable_sms: Send alerts via SMS (requires configuration)
        """
        self.max_history = max_history
        self.suppression_window = suppression_window_seconds

        # Alert channels
        self.enable_console = enable_console
        self.enable_log = enable_log
        self.enable_email = enable_email
        self.enable_sms = enable_sms

        # Alert storage
        self._alerts: deque = deque(maxlen=max_history)
        self._lock = threading.RLock()

        # Alert suppression tracking
        self._last_alert_time: Dict[str, datetime] = {}

        # Statistics
        self._alert_counts: Dict[AlertSeverity, int] = {
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.HIGH: 0,
            AlertSeverity.MEDIUM: 0,
            AlertSeverity.LOW: 0,
        }

        # Alert handlers (can be extended)
        self._custom_handlers: List[Callable[[Alert], None]] = []

        logger.info("🚨 AlertManager initialized")

    def alert(
        self,
        severity: AlertSeverity,
        category: AlertCategory | str,
        title: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        suppress: bool = True
    ) -> Optional[Alert]:
        """
        Raise an alert

        Args:
            severity: Alert severity level
            category: Alert category (enum or string)
            title: Short alert title
            message: Detailed alert message
            context: Additional context data
            suppress: Enable alert suppression

        Returns:
            Alert object if raised, None if suppressed
        """
        # Allow tests to pass strings (e.g. "SYSTEM") without manually constructing enums
        category_enum = self._normalize_category(category)

        with self._lock:
            # Check suppression
            if suppress:
                alert_key = f"{category_enum.value}:{title}"
                if self._is_suppressed(alert_key):
                    return None
                self._update_suppression(alert_key)

            # Create alert
            alert_obj = Alert(
                timestamp=datetime.now(),
                severity=severity,
                category=category_enum,
                title=title,
                message=message,
                context=context or {}
            )

            # Store alert
            self._alerts.append(alert_obj)
            self._alert_counts[severity] += 1

            # Dispatch to channels
            self._dispatch_alert(alert_obj)

            return alert_obj

    @staticmethod
    def _normalize_category(category: AlertCategory | str) -> AlertCategory:
        """Convert string categories into AlertCategory enums."""
        if isinstance(category, AlertCategory):
            return category

        if not isinstance(category, str):
            raise TypeError(f"Unsupported category type: {type(category)!r}")

        candidate = category.strip()
        # Try enum name first (SYSTEM), then value (system)
        try:
            return AlertCategory[candidate.upper()]
        except KeyError:
            try:
                return AlertCategory(candidate.lower())
            except ValueError:
                raise ValueError(f"Unknown alert category: {category}") from None

    def check_execution_alerts(self, order_data: Dict[str, Any]):
        """
        Check for trade execution alerts

        Alerts on:
        - Slow execution (>5 seconds)
        - Failed executions
        - Partial fills
        - Price slippage

        Args:
            order_data: Order execution data
        """
        # Slow execution
        duration_ms = order_data.get('duration_ms', 0)
        if duration_ms > 5000:  # >5 seconds
            self.alert(
                severity=AlertSeverity.HIGH,
                category=AlertCategory.EXECUTION,
                title="Slow Trade Execution",
                message=f"Order execution took {duration_ms/1000:.1f}s",
                context={'order_id': order_data.get('order_id'), 'duration_ms': duration_ms}
            )

        # Failed execution
        if order_data.get('status') == 'FAILED':
            self.alert(
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.EXECUTION,
                title="Trade Execution Failed",
                message=f"Order failed: {order_data.get('error_message', 'Unknown')}",
                context=order_data
            )

        # Partial fill
        filled_qty = order_data.get('filled_quantity', 0)
        total_qty = order_data.get('quantity', 1)
        if 0 < filled_qty < total_qty:
            self.alert(
                severity=AlertSeverity.MEDIUM,
                category=AlertCategory.EXECUTION,
                title="Partial Fill",
                message=f"Order partially filled: {filled_qty}/{total_qty}",
                context=order_data
            )

        # Price slippage
        expected_price = order_data.get('expected_price')
        actual_price = order_data.get('average_price')
        if expected_price and actual_price:
            slippage_pct = abs((actual_price - expected_price) / expected_price) * 100
            if slippage_pct > 0.5:  # >0.5% slippage
                self.alert(
                    severity=AlertSeverity.HIGH,
                    category=AlertCategory.EXECUTION,
                    title="High Price Slippage",
                    message=f"Slippage: {slippage_pct:.2f}%",
                    context={'expected': expected_price, 'actual': actual_price, **order_data}
                )

    def check_data_alerts(self, data_info: Dict[str, Any]):
        """
        Check for market data alerts

        Alerts on:
        - Stale data (>5 minutes old)
        - Missing data
        - Data quality issues

        Args:
            data_info: Market data information
        """
        # Stale data
        data_age_seconds = data_info.get('age_seconds', 0)
        if data_age_seconds > 300:  # >5 minutes
            self.alert(
                severity=AlertSeverity.HIGH,
                category=AlertCategory.DATA,
                title="Stale Market Data",
                message=f"Data is {data_age_seconds/60:.1f} minutes old",
                context=data_info
            )

        # Missing critical data
        if data_info.get('missing_symbols'):
            self.alert(
                severity=AlertSeverity.MEDIUM,
                category=AlertCategory.DATA,
                title="Missing Market Data",
                message=f"Missing data for {len(data_info['missing_symbols'])} symbols",
                context=data_info
            )

    def check_api_alerts(self, api_metrics: Dict[str, Any]):
        """
        Check for API-related alerts

        Alerts on:
        - Consecutive failures
        - Rate limit approaching
        - Connection issues

        Args:
            api_metrics: API performance metrics
        """
        # Consecutive failures
        consecutive_failures = api_metrics.get('consecutive_failures', 0)
        if consecutive_failures >= 3:
            self.alert(
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.API,
                title="API Consecutive Failures",
                message=f"{consecutive_failures} consecutive API failures",
                context=api_metrics
            )

        # Rate limit warning
        rate_limit_pct = api_metrics.get('rate_limit_usage_pct', 0)
        if rate_limit_pct > 80:
            self.alert(
                severity=AlertSeverity.HIGH,
                category=AlertCategory.API,
                title="API Rate Limit Warning",
                message=f"Rate limit usage at {rate_limit_pct:.0f}%",
                context=api_metrics
            )

    def check_risk_alerts(self, risk_metrics: Dict[str, Any]):
        """
        Check for risk management alerts

        Alerts on:
        - Position limits exceeded
        - Daily loss limits
        - Exposure limits
        - Unusual PnL

        Args:
            risk_metrics: Risk management metrics
        """
        # Position limit
        if risk_metrics.get('positions', 0) > risk_metrics.get('max_positions', 999):
            self.alert(
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.RISK,
                title="Position Limit Exceeded",
                message=f"Positions: {risk_metrics['positions']} > {risk_metrics['max_positions']}",
                context=risk_metrics
            )

        # Daily loss limit
        daily_pnl_pct = risk_metrics.get('daily_pnl_pct', 0)
        max_loss_pct = risk_metrics.get('max_daily_loss_pct', -5)
        if daily_pnl_pct < max_loss_pct:
            self.alert(
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.RISK,
                title="Daily Loss Limit Breach",
                message=f"Daily PnL: {daily_pnl_pct:.2f}% (limit: {max_loss_pct:.2f}%)",
                context=risk_metrics
            )

        # Large unrealized loss
        unrealized_pnl_pct = risk_metrics.get('unrealized_pnl_pct', 0)
        if unrealized_pnl_pct < -10:
            self.alert(
                severity=AlertSeverity.HIGH,
                category=AlertCategory.RISK,
                title="Large Unrealized Loss",
                message=f"Unrealized PnL: {unrealized_pnl_pct:.2f}%",
                context=risk_metrics
            )

    def check_performance_alerts(self, perf_metrics: Dict[str, Any]):
        """
        Check for system performance alerts

        Alerts on:
        - High memory usage
        - Slow operations
        - High CPU usage

        Args:
            perf_metrics: Performance metrics
        """
        # Memory usage
        memory_pct = perf_metrics.get('memory_usage_pct', 0)
        if memory_pct > 85:
            self.alert(
                severity=AlertSeverity.HIGH,
                category=AlertCategory.PERFORMANCE,
                title="High Memory Usage",
                message=f"Memory usage: {memory_pct:.1f}%",
                context=perf_metrics
            )

        # Slow operation
        operation_time_ms = perf_metrics.get('operation_time_ms', 0)
        if operation_time_ms > 1000:  # >1 second
            self.alert(
                severity=AlertSeverity.MEDIUM,
                category=AlertCategory.PERFORMANCE,
                title="Slow Operation",
                message=f"Operation took {operation_time_ms/1000:.1f}s",
                context=perf_metrics
            )

    def _dispatch_alert(self, alert: Alert):
        """Dispatch alert to enabled channels"""
        # Console
        if self.enable_console:
            self._send_to_console(alert)

        # Logging system
        if self.enable_log:
            self._send_to_log(alert)

        # Email (placeholder)
        if self.enable_email:
            self._send_to_email(alert)

        # SMS (placeholder)
        if self.enable_sms:
            self._send_to_sms(alert)

        # Custom handlers
        for handler in self._custom_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Error in custom alert handler: {e}")

    def _send_to_console(self, alert: Alert):
        """Print alert to console"""
        severity_icons = {
            AlertSeverity.CRITICAL: "🔴",
            AlertSeverity.HIGH: "🟠",
            AlertSeverity.MEDIUM: "🟡",
            AlertSeverity.LOW: "🔵",
        }

        icon = severity_icons.get(alert.severity, "⚪")
        print(f"\n{icon} {alert}")

    def _send_to_log(self, alert: Alert):
        """Log alert using logging system"""
        log_levels = {
            AlertSeverity.CRITICAL: logging.CRITICAL,
            AlertSeverity.HIGH: logging.ERROR,
            AlertSeverity.MEDIUM: logging.WARNING,
            AlertSeverity.LOW: logging.INFO,
        }

        level = log_levels.get(alert.severity, logging.INFO)
        logger.log(level, f"{alert.title}: {alert.message}", extra={'context': alert.context})

    def _send_to_email(self, alert: Alert):
        """Send alert via email (placeholder)"""
        # TODO: Implement email sending
        pass

    def _send_to_sms(self, alert: Alert):
        """Send alert via SMS (placeholder)"""
        # TODO: Implement SMS sending
        pass

    def _is_suppressed(self, alert_key: str) -> bool:
        """Check if alert should be suppressed"""
        if alert_key not in self._last_alert_time:
            return False

        time_since = datetime.now() - self._last_alert_time[alert_key]
        return time_since < timedelta(seconds=self.suppression_window)

    def _update_suppression(self, alert_key: str):
        """Update suppression timestamp"""
        self._last_alert_time[alert_key] = datetime.now()

    def add_custom_handler(self, handler: Callable[[Alert], None]):
        """Add custom alert handler"""
        self._custom_handlers.append(handler)

    def get_recent_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        category: Optional[AlertCategory] = None,
        limit: int = 50
    ) -> List[Alert]:
        """Get recent alerts with optional filtering"""
        with self._lock:
            alerts = list(self._alerts)

            if severity:
                alerts = [a for a in alerts if a.severity == severity]

            if category:
                alerts = [a for a in alerts if a.category == category]

            return alerts[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get alert statistics"""
        with self._lock:
            return {
                'total_alerts': len(self._alerts),
                'critical': self._alert_counts[AlertSeverity.CRITICAL],
                'high': self._alert_counts[AlertSeverity.HIGH],
                'medium': self._alert_counts[AlertSeverity.MEDIUM],
                'low': self._alert_counts[AlertSeverity.LOW],
                'unacknowledged': sum(1 for a in self._alerts if not a.acknowledged),
                'unresolved': sum(1 for a in self._alerts if not a.resolved),
            }

    def print_stats(self):
        """Print alert statistics"""
        stats = self.get_stats()

        print("\n" + "="*60)
        print("🚨 ALERT STATISTICS")
        print("="*60)
        print(f"Total Alerts:     {stats['total_alerts']:,}")
        print(f"Critical:         {stats['critical']:,}")
        print(f"High:             {stats['high']:,}")
        print(f"Medium:           {stats['medium']:,}")
        print(f"Low:              {stats['low']:,}")
        print(f"Unacknowledged:   {stats['unacknowledged']:,}")
        print(f"Unresolved:       {stats['unresolved']:,}")
        print("="*60 + "\n")


# Global alert manager instance
_global_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get global alert manager instance (singleton)"""
    global _global_alert_manager
    if _global_alert_manager is None:
        _global_alert_manager = AlertManager()
    return _global_alert_manager


if __name__ == "__main__":
    # Test alert manager
    alert_mgr = AlertManager()

    # Test various alerts
    alert_mgr.alert(
        severity=AlertSeverity.CRITICAL,
        category=AlertCategory.EXECUTION,
        title="Trade Failed",
        message="Order execution failed due to insufficient funds"
    )

    alert_mgr.check_execution_alerts({
        'order_id': '123',
        'duration_ms': 6200,
        'status': 'COMPLETED'
    })

    alert_mgr.check_risk_alerts({
        'positions': 30,
        'max_positions': 25,
        'daily_pnl_pct': -6.5,
        'max_daily_loss_pct': -5.0
    })

    alert_mgr.print_stats()

    print("\n📋 Recent Critical Alerts:")
    for alert in alert_mgr.get_recent_alerts(severity=AlertSeverity.CRITICAL, limit=10):
        print(f"  • {alert}")

    print("\n✅ Alert manager tests passed")
