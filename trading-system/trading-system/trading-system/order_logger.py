#!/usr/bin/env python3
"""
Comprehensive Order Logging System
Provides complete audit trail for all trading operations
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict

from trading_utils import get_ist_now, sanitize_for_logging
from safe_file_ops import atomic_write_json, ensure_directory

logger = logging.getLogger('trading_system.order_logger')


@dataclass
class OrderRequest:
    """Order request details"""
    order_id: str
    symbol: str
    transaction_type: str  # 'BUY' or 'SELL'
    quantity: int
    price: float
    order_type: str  # 'LIMIT', 'MARKET', etc.
    product: str  # 'MIS', 'CNC', etc.
    exchange: str
    mode: str  # 'paper' or 'live'
    timestamp_request: str
    metadata: Dict[str, Any] = None


@dataclass
class OrderResponse:
    """Order response details"""
    order_id: str
    status: str  # 'COMPLETE', 'REJECTED', 'PENDING', etc.
    filled_quantity: int
    average_price: float
    exchange_order_id: Optional[str]
    timestamp_response: str
    message: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class OrderAudit:
    """Complete order audit entry"""
    request: OrderRequest
    response: Optional[OrderResponse]
    error: Optional[Dict[str, Any]]
    duration_ms: float
    status: str  # 'SUCCESS', 'FAILED', 'PENDING'


class OrderLogger:
    """
    Comprehensive order logging with audit trail

    Features:
    - Logs every order request and response
    - Separate files per day
    - JSONL format for easy parsing
    - Thread-safe operations
    - Automatic directory creation
    """

    def __init__(self, log_dir: str = "logs/orders"):
        """
        Initialize order logger

        Args:
            log_dir: Directory for order logs
        """
        self.log_dir = Path(log_dir)
        ensure_directory(self.log_dir)

        # Summary log file
        self.summary_log = self.log_dir / "order_summary.log"

        logger.info(f"✅ Order logger initialized: {self.log_dir}")

    def _get_daily_log_file(self) -> Path:
        """Get log file for today"""
        today = get_ist_now().strftime('%Y%m%d')
        return self.log_dir / f"orders_{today}.jsonl"

    def log_order_request(
        self,
        order_id: str,
        symbol: str,
        transaction_type: str,
        quantity: int,
        price: float,
        order_type: str = "LIMIT",
        product: str = "MIS",
        exchange: str = "NSE",
        mode: str = "paper",
        metadata: Optional[Dict] = None
    ) -> OrderRequest:
        """
        Log order request

        Args:
            order_id: Unique order ID
            symbol: Stock symbol
            transaction_type: 'BUY' or 'SELL'
            quantity: Number of shares
            price: Price per share
            order_type: Order type
            product: Product type
            exchange: Exchange
            mode: Trading mode
            metadata: Additional metadata

        Returns:
            OrderRequest object
        """
        request = OrderRequest(
            order_id=order_id,
            symbol=symbol,
            transaction_type=transaction_type,
            quantity=quantity,
            price=price,
            order_type=order_type,
            product=product,
            exchange=exchange,
            mode=mode,
            timestamp_request=get_ist_now().isoformat(),
            metadata=metadata or {}
        )

        # Log to file
        logger.info(
            f"📤 ORDER REQUEST: {order_id} | {transaction_type} {quantity} {symbol} "
            f"@ ₹{price:.2f} | Mode: {mode}"
        )

        return request

    def log_order_response(
        self,
        request: OrderRequest,
        response: Optional[Dict],
        error: Optional[Exception],
        duration_ms: float
    ) -> OrderAudit:
        """
        Log order response and create audit entry

        Args:
            request: Original order request
            response: API response (if successful)
            error: Exception (if failed)
            duration_ms: Time taken in milliseconds

        Returns:
            OrderAudit entry
        """
        timestamp = get_ist_now().isoformat()

        # Parse response
        order_response = None
        error_dict = None
        status = 'FAILED'

        if response:
            order_response = OrderResponse(
                order_id=response.get('order_id', request.order_id),
                status=response.get('status', 'UNKNOWN'),
                filled_quantity=response.get('filled_quantity', request.quantity),
                average_price=response.get('average_price', request.price),
                exchange_order_id=response.get('exchange_order_id'),
                timestamp_response=timestamp,
                message=response.get('message')
            )
            status = 'SUCCESS'

            logger.info(
                f"✅ ORDER SUCCESS: {request.order_id} | {request.symbol} | "
                f"Status: {order_response.status} | Duration: {duration_ms:.0f}ms"
            )

        elif error:
            error_dict = {
                'error_type': type(error).__name__,
                'error_message': str(error),
                'timestamp_error': timestamp
            }
            status = 'FAILED'

            logger.error(
                f"❌ ORDER FAILED: {request.order_id} | {request.symbol} | "
                f"Error: {error} | Duration: {duration_ms:.0f}ms"
            )

        # Create audit entry
        audit = OrderAudit(
            request=request,
            response=order_response,
            error=error_dict,
            duration_ms=duration_ms,
            status=status
        )

        # Write to JSONL file
        self._write_audit_entry(audit)

        # Update summary
        self._update_summary(audit)

        return audit

    def _write_audit_entry(self, audit: OrderAudit) -> None:
        """Write audit entry to JSONL file"""
        log_file = self._get_daily_log_file()

        try:
            # Convert to dict (handle dataclasses)
            audit_dict = {
                'request': asdict(audit.request),
                'response': asdict(audit.response) if audit.response else None,
                'error': audit.error,
                'duration_ms': audit.duration_ms,
                'status': audit.status
            }

            # Sanitize sensitive data
            audit_dict_sanitized = sanitize_for_logging(audit_dict)

            # Append to JSONL
            with open(log_file, 'a') as f:
                f.write(json.dumps(audit_dict_sanitized) + '\n')

        except Exception as e:
            logger.error(f"Failed to write audit entry: {e}", exc_info=True)

    def _update_summary(self, audit: OrderAudit) -> None:
        """Update daily summary statistics"""
        try:
            summary_file = self.log_dir / f"summary_{get_ist_now().strftime('%Y%m%d')}.json"

            # Load existing summary
            if summary_file.exists():
                with open(summary_file, 'r') as f:
                    summary = json.load(f)
            else:
                summary = {
                    'date': get_ist_now().strftime('%Y-%m-%d'),
                    'total_orders': 0,
                    'successful_orders': 0,
                    'failed_orders': 0,
                    'total_quantity_bought': 0,
                    'total_quantity_sold': 0,
                    'avg_duration_ms': 0,
                    'symbols_traded': set()
                }
                # Convert set to list for JSON
                summary['symbols_traded'] = []

            # Update summary
            summary['total_orders'] += 1

            if audit.status == 'SUCCESS':
                summary['successful_orders'] += 1

                if audit.request.transaction_type == 'BUY':
                    summary['total_quantity_bought'] += audit.request.quantity
                elif audit.request.transaction_type == 'SELL':
                    summary['total_quantity_sold'] += audit.request.quantity

                if audit.request.symbol not in summary['symbols_traded']:
                    summary['symbols_traded'].append(audit.request.symbol)

            elif audit.status == 'FAILED':
                summary['failed_orders'] += 1

            # Update average duration
            prev_avg = summary['avg_duration_ms']
            n = summary['total_orders']
            summary['avg_duration_ms'] = ((prev_avg * (n - 1)) + audit.duration_ms) / n

            # Write summary
            atomic_write_json(summary_file, summary, create_backup=False)

        except Exception as e:
            logger.error(f"Failed to update summary: {e}", exc_info=True)

    def get_daily_summary(self, date: Optional[str] = None) -> Dict:
        """
        Get summary for a specific date

        Args:
            date: Date in YYYYMMDD format (default: today)

        Returns:
            Summary dict
        """
        if not date:
            date = get_ist_now().strftime('%Y%m%d')

        summary_file = self.log_dir / f"summary_{date}.json"

        if summary_file.exists():
            with open(summary_file, 'r') as f:
                return json.load(f)

        return {}

    def get_order_history(
        self,
        date: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[str] = None
    ) -> list:
        """
        Get order history with filters

        Args:
            date: Date in YYYYMMDD format (default: today)
            symbol: Filter by symbol
            status: Filter by status ('SUCCESS' or 'FAILED')

        Returns:
            List of order audit entries
        """
        if not date:
            date = get_ist_now().strftime('%Y%m%d')

        log_file = self.log_dir / f"orders_{date}.jsonl"

        if not log_file.exists():
            return []

        orders = []
        with open(log_file, 'r') as f:
            for line in f:
                try:
                    order = json.loads(line)

                    # Apply filters
                    if symbol and order['request']['symbol'] != symbol.upper():
                        continue
                    if status and order['status'] != status:
                        continue

                    orders.append(order)
                except json.JSONDecodeError:
                    continue

        return orders


# Singleton instance
_order_logger_instance = None


def get_order_logger(log_dir: str = "logs/orders") -> OrderLogger:
    """Get singleton order logger instance"""
    global _order_logger_instance
    if _order_logger_instance is None:
        _order_logger_instance = OrderLogger(log_dir)
    return _order_logger_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("🧪 Testing Order Logger")
    print("=" * 60)

    order_logger = OrderLogger("test_logs/orders")

    # Simulate order
    import time

    request = order_logger.log_order_request(
        order_id="TEST001",
        symbol="SBIN",
        transaction_type="BUY",
        quantity=100,
        price=550.50,
        mode="paper"
    )

    time.sleep(0.1)

    # Simulate success
    response = {
        'order_id': 'TEST001',
        'status': 'COMPLETE',
        'filled_quantity': 100,
        'average_price': 550.50
    }

    order_logger.log_order_response(request, response, None, 100.0)

    # Get summary
    summary = order_logger.get_daily_summary()
    print(f"\n📊 Daily Summary:")
    print(json.dumps(summary, indent=2))

    print("\n✅ Order logger working correctly!")
