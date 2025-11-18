#!/usr/bin/env python3
"""
Cross Trade Prevention Module
SEBI Compliance: Cross-trade prevention mechanisms
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger('trading_system.cross_trade_prevention')


class CrossTradeType(Enum):
    """Types of cross trades"""
    SELF_CROSS = "self_cross"  # Same client buying and selling same instrument
    WASH_TRADE = "wash_trade"  # Artificial volume creation
    FRONT_RUNNING = "front_running"  # Trading ahead of client orders
    LAYERING = "layering"  # Creating false market depth


@dataclass
class OrderFingerprint:
    """Order fingerprint for cross trade detection"""
    client_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    price: float
    quantity: int
    timestamp: str
    order_type: str = "limit"


class CrossTradePrevention:
    """
    Cross trade prevention system per SEBI regulations

    SEBI Requirements:
    - Prevent self-crossing trades
    - Detect wash trading
    - Monitor front-running
    - Prevent market manipulation
    """

    def __init__(self, data_dir: str = "cross_trade_data"):
        self.data_dir = data_dir
        self.order_book: Dict[str, List[OrderFingerprint]] = {}  # symbol -> orders
        self.client_orders: Dict[str, List[OrderFingerprint]] = {}  # client_id -> orders
        self.suspicious_activities: List[Dict] = []

        # Detection thresholds
        self.max_price_deviation = 0.05  # 5% price tolerance for matching
        self.max_time_window = 300  # 5 minutes for order matching
        self.min_volume_threshold = 1000  # Minimum volume for wash trade detection

        self._load_data()

    def check_cross_trade_risk(self, order: OrderFingerprint) -> Tuple[bool, str]:
        """
        Check if order poses cross trade risk

        Args:
            order: Order to check

        Returns:
            (is_safe: bool, reason: str)
        """
        # Check for self-cross (same client)
        if self._check_self_cross(order):
            return False, "Self-cross detected"

        # Check for wash trade patterns
        if self._check_wash_trade(order):
            return False, "Wash trade pattern detected"

        # Check for front-running
        if self._check_front_running(order):
            return False, "Front-running pattern detected"

        return True, "Order is safe"

    def _check_self_cross(self, order: OrderFingerprint) -> bool:
        """Check for self-crossing trades"""
        # Look for opposite orders from same client
        client_orders = self.client_orders.get(order.client_id, [])

        for existing_order in client_orders:
            # Skip if same order
            if (existing_order.symbol == order.symbol and
                existing_order.side != order.side and
                abs(existing_order.price - order.price) / order.price <= self.max_price_deviation):

                # Check time window
                try:
                    existing_time = datetime.fromisoformat(existing_order.timestamp)
                    order_time = datetime.fromisoformat(order.timestamp)
                    time_diff = abs((order_time - existing_time).total_seconds())

                    if time_diff <= self.max_time_window:
                        logger.warning(
                            f"🚨 SELF-CROSS DETECTED: Client {order.client_id} "
                            f"has opposite {order.symbol} orders within {time_diff:.0f}s"
                        )
                        return True
                except:
                    continue

        return False

    def _check_wash_trade(self, order: OrderFingerprint) -> bool:
        """Check for wash trading patterns"""
        # Look for rapid buy-sell patterns from same client
        client_orders = self.client_orders.get(order.client_id, [])

        # Count recent orders for same symbol
        recent_orders = []
        try:
            order_time = datetime.fromisoformat(order.timestamp)
            cutoff_time = order_time - timedelta(seconds=self.max_time_window)

            for existing_order in client_orders:
                if existing_order.symbol == order.symbol:
                    existing_time = datetime.fromisoformat(existing_order.timestamp)
                    if existing_time > cutoff_time:
                        recent_orders.append(existing_order)
        except:
            return False

        if len(recent_orders) >= 5:  # 5+ orders in time window
            # Check for alternating buy-sell pattern
            if self._detect_alternating_pattern(recent_orders + [order]):
                logger.warning(
                    f"🚨 WASH TRADE DETECTED: Client {order.client_id} "
                    f"has {len(recent_orders) + 1} alternating {order.symbol} orders"
                )
                return True

        return False

    def _detect_alternating_pattern(self, orders: List[OrderFingerprint]) -> bool:
        """Detect alternating buy-sell pattern"""
        if len(orders) < 3:
            return False

        # Sort by timestamp
        orders.sort(key=lambda x: x.timestamp)

        # Check for alternating pattern
        for i in range(len(orders) - 1):
            if orders[i].side == orders[i + 1].side:
                return False  # Same side consecutive orders

        return True

    def _check_front_running(self, order: OrderFingerprint) -> bool:
        """Check for front-running patterns"""
        # Look for orders that might be front-running client orders
        symbol_orders = self.order_book.get(order.symbol, [])

        # Check for large orders that might be front-running
        large_orders = [
            o for o in symbol_orders
            if o.quantity >= self.min_volume_threshold and
            abs(o.price - order.price) / order.price <= self.max_price_deviation
        ]

        if large_orders:
            # Check timing - if large order came right before client order
            try:
                order_time = datetime.fromisoformat(order.timestamp)

                for large_order in large_orders:
                    large_time = datetime.fromisoformat(large_order.timestamp)
                    time_diff = (order_time - large_time).total_seconds()

                    if 0 < time_diff <= 60:  # Within 1 minute
                        logger.warning(
                            f"🚨 FRONT-RUNNING SUSPICION: Large {large_order.quantity} "
                            f"{order.symbol} order {time_diff:.0f}s before client order"
                        )
                        return True
            except:
                pass

        return False

    def record_order(self, order: OrderFingerprint) -> None:
        """
        Record order for cross trade monitoring

        Args:
            order: Order to record
        """
        # Add to symbol order book
        if order.symbol not in self.order_book:
            self.order_book[order.symbol] = []
        self.order_book[order.symbol].append(order)

        # Add to client orders
        if order.client_id not in self.client_orders:
            self.client_orders[order.client_id] = []
        self.client_orders[order.client_id].append(order)

        # Clean old orders (keep last 1 hour)
        cutoff_time = datetime.now() - timedelta(hours=1)
        self._cleanup_old_orders(cutoff_time)

        self._save_data()

    def _cleanup_old_orders(self, cutoff_time: datetime) -> None:
        """Remove old orders to prevent memory buildup"""
        for symbol in self.order_book:
            self.order_book[symbol] = [
                order for order in self.order_book[symbol]
                if datetime.fromisoformat(order.timestamp) > cutoff_time
            ]

        for client_id in self.client_orders:
            self.client_orders[client_id] = [
                order for order in self.client_orders[client_id]
                if datetime.fromisoformat(order.timestamp) > cutoff_time
            ]

    def generate_cross_trade_report(self) -> Dict:
        """
        Generate cross trade monitoring report

        Returns:
            Report on cross trade prevention activities
        """
        total_orders = sum(len(orders) for orders in self.order_book.values())
        total_clients = len(self.client_orders)

        # Analyze suspicious activities
        suspicious_by_type = {}
        for activity in self.suspicious_activities:
            activity_type = activity.get('type', 'unknown')
            if activity_type not in suspicious_by_type:
                suspicious_by_type[activity_type] = 0
            suspicious_by_type[activity_type] += 1

        return {
            'report_date': datetime.now().isoformat(),
            'monitoring_period': '1_hour',
            'total_orders_monitored': total_orders,
            'unique_clients': total_clients,
            'suspicious_activities': len(self.suspicious_activities),
            'suspicious_by_type': suspicious_by_type,
            'blocked_orders': len([a for a in self.suspicious_activities if a.get('action') == 'blocked']),
            'alerts_generated': len([a for a in self.suspicious_activities if a.get('severity') == 'high']),
            'compliance_status': 'active'
        }

    def _load_data(self):
        """Load cross trade data from files"""
        try:
            import os
            os.makedirs(self.data_dir, exist_ok=True)

            # Load suspicious activities
            suspicious_file = f"{self.data_dir}/suspicious_activities.json"
            if os.path.exists(suspicious_file):
                with open(suspicious_file, 'r') as f:
                    self.suspicious_activities = json.load(f)

            logger.info(f"✅ Loaded cross trade data: {len(self.suspicious_activities)} suspicious activities")

        except Exception as e:
            logger.error(f"Error loading cross trade data: {e}")

    def _save_data(self):
        """Save cross trade data to files"""
        try:
            import os
            os.makedirs(self.data_dir, exist_ok=True)

            # Save suspicious activities
            suspicious_file = f"{self.data_dir}/suspicious_activities.json"
            with open(suspicious_file, 'w') as f:
                json.dump(self.suspicious_activities, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving cross trade data: {e}")