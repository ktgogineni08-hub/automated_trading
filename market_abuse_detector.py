#!/usr/bin/env python3
"""
Market Abuse Detection Module
SEBI Compliance: Market abuse prevention mechanisms
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger('trading_system.market_abuse_detector')


class AbuseType(Enum):
    """Types of market abuse"""
    INSIDER_TRADING = "insider_trading"
    MARKET_MANIPULATION = "market_manipulation"
    FRONT_RUNNING = "front_running"
    WASH_TRADE = "wash_trade"
    PUMP_AND_DUMP = "pump_and_dump"
    SPOOFING = "spoofing"


@dataclass
class AbuseAlert:
    """Market abuse alert"""
    alert_id: str
    client_id: str
    abuse_type: AbuseType
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    timestamp: str
    evidence: Dict
    status: str = "active"


class MarketAbuseDetector:
    """
    Market abuse detection system per SEBI regulations

    SEBI Requirements:
    - Insider trading prevention
    - Market manipulation detection
    - Front-running controls
    - Wash trade prevention
    """

    def __init__(self, data_dir: str = "abuse_detection_data"):
        self.data_dir = data_dir
        self.trade_history: List[Dict] = []
        self.client_patterns: Dict[str, Dict] = {}
        self.abuse_alerts: List[AbuseAlert] = []

        # Detection thresholds
        self.unusual_volume_threshold = 10  # 10x normal volume
        self.price_spike_threshold = 0.05  # 5% price movement
        self.rapid_trade_threshold = 20  # 20 trades in 5 minutes

        self._load_data()

    def analyze_trade_for_abuse(self, trade: Dict) -> List[AbuseAlert]:
        """
        Analyze trade for potential market abuse

        Args:
            trade: Trade data dictionary

        Returns:
            List of abuse alerts (if any)
        """
        alerts = []

        # Check for insider trading patterns
        insider_alert = self._check_insider_trading(trade)
        if insider_alert:
            alerts.append(insider_alert)

        # Check for market manipulation
        manipulation_alert = self._check_market_manipulation(trade)
        if manipulation_alert:
            alerts.append(manipulation_alert)

        # Check for front-running
        front_running_alert = self._check_front_running(trade)
        if front_running_alert:
            alerts.append(front_running_alert)

        # Check for wash trades
        wash_trade_alert = self._check_wash_trade(trade)
        if wash_trade_alert:
            alerts.append(wash_trade_alert)

        return alerts

    def _check_insider_trading(self, trade: Dict) -> Optional[AbuseAlert]:
        """Check for insider trading patterns"""
        client_id = trade.get('client_id', '')
        symbol = trade.get('symbol', '')
        price = trade.get('price', 0)
        quantity = trade.get('quantity', 0)
        timestamp = trade.get('timestamp', '')

        # Look for unusual trading patterns before major announcements
        # This is a simplified check - real implementation would need:
        # 1. Access to corporate action calendars
        # 2. News sentiment analysis
        # 3. Unusual volume/price patterns

        # Check for large trades in illiquid stocks
        if self._is_illiquid_symbol(symbol) and quantity > 10000:
            return AbuseAlert(
                alert_id=f"INSIDER_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{client_id}",
                client_id=client_id,
                abuse_type=AbuseType.INSIDER_TRADING,
                severity="medium",
                description=f"Large trade in illiquid stock {symbol}: {quantity} shares",
                timestamp=datetime.now().isoformat(),
                evidence={
                    'symbol': symbol,
                    'quantity': quantity,
                    'price': price,
                    'timestamp': timestamp,
                    'pattern': 'large_illiquid_trade'
                }
            )

        return None

    def _check_market_manipulation(self, trade: Dict) -> Optional[AbuseAlert]:
        """Check for market manipulation patterns"""
        client_id = trade.get('client_id', '')
        symbol = trade.get('symbol', '')
        price = trade.get('price', 0)
        quantity = trade.get('quantity', 0)

        # Check for pump and dump patterns
        if self._check_pump_and_dump_pattern(trade):
            return AbuseAlert(
                alert_id=f"MANIP_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{client_id}",
                client_id=client_id,
                abuse_type=AbuseType.MARKET_MANIPULATION,
                severity="high",
                description=f"Pump and dump pattern detected for {symbol}",
                timestamp=datetime.now().isoformat(),
                evidence={
                    'symbol': symbol,
                    'pattern': 'pump_and_dump',
                    'price': price,
                    'quantity': quantity
                }
            )

        # Check for spoofing (fake orders)
        if self._check_spoofing_pattern(trade):
            return AbuseAlert(
                alert_id=f"SPOOF_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{client_id}",
                client_id=client_id,
                abuse_type=AbuseType.SPOOFING,
                severity="medium",
                description=f"Spoofing pattern detected for {symbol}",
                timestamp=datetime.now().isoformat(),
                evidence={
                    'symbol': symbol,
                    'pattern': 'spoofing',
                    'price': price
                }
            )

        return None

    def _check_pump_and_dump_pattern(self, trade: Dict) -> bool:
        """Check for pump and dump pattern"""
        # Simplified check: look for rapid price increase followed by large sell
        # Real implementation would need price/volume analysis

        symbol = trade.get('symbol', '')
        client_id = trade.get('client_id', '')

        # Get recent trades for this symbol
        recent_trades = [
            t for t in self.trade_history
            if t.get('symbol') == symbol and
            datetime.fromisoformat(t.get('timestamp', '')) > datetime.now() - timedelta(hours=1)
        ]

        if len(recent_trades) < 5:
            return False

        # Check for rapid price increase
        prices = [t.get('price', 0) for t in recent_trades[-5:]]
        if len(prices) >= 2:
            price_change = (prices[-1] - prices[0]) / prices[0]
            if price_change > 0.10:  # 10% increase
                return True

        return False

    def _check_spoofing_pattern(self, trade: Dict) -> bool:
        """Check for spoofing pattern"""
        # Look for orders that are cancelled quickly without execution
        # This is a simplified check

        symbol = trade.get('symbol', '')
        client_id = trade.get('client_id', '')

        # Get recent orders for this client and symbol
        recent_orders = [
            t for t in self.trade_history
            if (t.get('client_id') == client_id and
                t.get('symbol') == symbol and
                datetime.fromisoformat(t.get('timestamp', '')) > datetime.now() - timedelta(minutes=5))
        ]

        # If many small orders followed by one large order, might be layering
        if len(recent_orders) >= 5:
            quantities = [t.get('quantity', 0) for t in recent_orders]
            if max(quantities) > sum(quantities[:-1]) * 2:
                return True

        return False

    def _check_front_running(self, trade: Dict) -> Optional[AbuseAlert]:
        """Check for front-running"""
        client_id = trade.get('client_id', '')
        symbol = trade.get('symbol', '')

        # Look for trades that occur right before large client orders
        # This would need integration with order management system

        # Simplified check: look for rapid trading in same symbol
        recent_trades = [
            t for t in self.trade_history
            if (t.get('symbol') == symbol and
                t.get('client_id') != client_id and
                datetime.fromisoformat(t.get('timestamp', '')) > datetime.now() - timedelta(minutes=1))
        ]

        if len(recent_trades) > 5:
            return AbuseAlert(
                alert_id=f"FRONT_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{client_id}",
                client_id=client_id,
                abuse_type=AbuseType.FRONT_RUNNING,
                severity="high",
                description=f"Front-running suspicion for {symbol}",
                timestamp=datetime.now().isoformat(),
                evidence={
                    'symbol': symbol,
                    'recent_trades': len(recent_trades),
                    'pattern': 'rapid_trading_before_client_order'
                }
            )

        return None

    def _check_wash_trade(self, trade: Dict) -> Optional[AbuseAlert]:
        """Check for wash trading"""
        client_id = trade.get('client_id', '')
        symbol = trade.get('symbol', '')

        # Look for same client trading with themselves
        # This would need order matching analysis

        # Simplified check: same client with many round trips
        client_symbol_trades = [
            t for t in self.trade_history
            if t.get('client_id') == client_id and t.get('symbol') == symbol
        ]

        if len(client_symbol_trades) >= 10:
            # Check for alternating buy/sell pattern
            sides = [t.get('side', '') for t in client_symbol_trades[-10:]]
            alternating = all(sides[i] != sides[i+1] for i in range(len(sides)-1))

            if alternating:
                return AbuseAlert(
                    alert_id=f"WASH_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{client_id}",
                    client_id=client_id,
                    abuse_type=AbuseType.WASH_TRADE,
                    severity="medium",
                    description=f"Wash trading pattern detected for {symbol}",
                    timestamp=datetime.now().isoformat(),
                    evidence={
                        'symbol': symbol,
                        'trade_count': len(client_symbol_trades),
                        'pattern': 'alternating_buy_sell'
                    }
                )

        return None

    def _is_illiquid_symbol(self, symbol: str) -> bool:
        """Check if symbol is illiquid (simplified)"""
        # In real implementation, this would check:
        # 1. Average daily volume
        # 2. Market capitalization
        # 3. Bid-ask spread
        # 4. Number of market makers

        # Simplified check based on symbol patterns
        illiquid_indicators = ['SME', 'SMALL', 'MICRO']
        return any(indicator in symbol.upper() for indicator in illiquid_indicators)

    def record_trade(self, trade: Dict) -> None:
        """
        Record trade for abuse monitoring

        Args:
            trade: Trade data dictionary
        """
        self.trade_history.append(trade)

        # Keep only last 24 hours of trades
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.trade_history = [
            t for t in self.trade_history
            if datetime.fromisoformat(t.get('timestamp', '')) > cutoff_time
        ]

        # Analyze for abuse
        alerts = self.analyze_trade_for_abuse(trade)
        for alert in alerts:
            self.abuse_alerts.append(alert)

        self._save_data()

    def generate_abuse_report(self) -> Dict:
        """
        Generate market abuse monitoring report

        Returns:
            Report on market abuse detection activities
        """
        # Analyze alerts by type and severity
        alerts_by_type = {}
        alerts_by_severity = {}

        for alert in self.abuse_alerts:
            # By type
            alert_type = alert.abuse_type.value
            if alert_type not in alerts_by_type:
                alerts_by_type[alert_type] = 0
            alerts_by_type[alert_type] += 1

            # By severity
            severity = alert.severity
            if severity not in alerts_by_severity:
                alerts_by_severity[severity] = 0
            alerts_by_severity[severity] += 1

        return {
            'report_date': datetime.now().isoformat(),
            'monitoring_period': '24_hours',
            'total_trades_monitored': len(self.trade_history),
            'total_alerts': len(self.abuse_alerts),
            'alerts_by_type': alerts_by_type,
            'alerts_by_severity': alerts_by_severity,
            'active_alerts': len([a for a in self.abuse_alerts if a.status == 'active']),
            'compliance_status': 'active'
        }

    def _load_data(self):
        """Load abuse detection data from files"""
        try:
            import os
            os.makedirs(self.data_dir, exist_ok=True)

            # Load abuse alerts
            alerts_file = f"{self.data_dir}/abuse_alerts.json"
            if os.path.exists(alerts_file):
                with open(alerts_file, 'r') as f:
                    alert_data = json.load(f)
                self.abuse_alerts = [AbuseAlert(**alert) for alert in alert_data]

            logger.info(f"✅ Loaded abuse detection data: {len(self.abuse_alerts)} alerts")

        except Exception as e:
            logger.error(f"Error loading abuse detection data: {e}")

    def _save_data(self):
        """Save abuse detection data to files"""
        try:
            import os
            os.makedirs(self.data_dir, exist_ok=True)

            # Save abuse alerts
            alerts_file = f"{self.data_dir}/abuse_alerts.json"
            with open(alerts_file, 'w') as f:
                json.dump([alert.__dict__ for alert in self.abuse_alerts], f, indent=2)

        except Exception as e:
            logger.error(f"Error saving abuse detection data: {e}")