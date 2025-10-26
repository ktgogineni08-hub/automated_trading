#!/usr/bin/env python3
"""
Structured Logging System with Correlation IDs
Month 2 Production Enhancement

Features:
- JSON structured logging
- Correlation ID tracking
- Request/response logging
- Performance metrics
- Error categorization
- Log levels per environment
"""

import logging
import json
import sys
import uuid
import time
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar
from functools import wraps
import traceback

# Context variable for correlation ID (thread-safe)
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add correlation ID if available
        correlation_id = correlation_id_var.get()
        if correlation_id:
            log_data['correlation_id'] = correlation_id

        # Add extra fields
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }

        # Add performance metrics if present
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms

        # Add context data
        if hasattr(record, 'context'):
            log_data['context'] = record.context

        return json.dumps(log_data)


class StructuredLogger:
    """
    Structured logger with correlation ID support

    Usage:
        logger = StructuredLogger(__name__)

        # Basic logging
        logger.info("Order executed", symbol="RELIANCE", quantity=100)

        # With correlation ID
        with logger.correlation_context():
            logger.info("Processing order")
            # All logs in this block will have same correlation_id

        # Performance logging
        with logger.performance_context("api_call"):
            api.fetch_data()  # Duration automatically logged
    """

    def __init__(self, name: str):
        """
        Initialize structured logger

        Args:
            name: Logger name (usually __name__)
        """
        self.logger = logging.getLogger(name)

        # Don't add handlers if already configured
        if not self.logger.handlers:
            self._configure_logger()

    def _configure_logger(self):
        """Configure logger with structured formatter"""
        # Console handler with JSON formatter
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(console_handler)

        # File handler with JSON formatter
        file_handler = logging.FileHandler('logs/trading_system_structured.log')
        file_handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(file_handler)

        # Default level
        self.logger.setLevel(logging.INFO)

    def _log(
        self,
        level: int,
        message: str,
        **kwargs
    ):
        """
        Internal logging method with extra data

        Args:
            level: Log level
            message: Log message
            **kwargs: Additional structured data
        """
        # Create log record with extra data
        extra = {'extra_data': kwargs} if kwargs else {}
        self.logger.log(level, message, extra=extra)

    def debug(self, message: str, **kwargs):
        """Log debug message with structured data"""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message with structured data"""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message with structured data"""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs):
        """Log error message with structured data"""
        extra = {'extra_data': kwargs} if kwargs else {}
        self.logger.error(message, exc_info=exc_info, extra=extra)

    def critical(self, message: str, exc_info: bool = False, **kwargs):
        """Log critical message with structured data"""
        extra = {'extra_data': kwargs} if kwargs else {}
        self.logger.critical(message, exc_info=exc_info, extra=extra)

    def log_trade(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        order_id: str,
        strategy: str,
        **kwargs
    ):
        """
        Log trade execution with standard fields

        Args:
            symbol: Trading symbol
            side: BUY or SELL
            quantity: Order quantity
            price: Execution price
            order_id: Order ID
            strategy: Strategy name
            **kwargs: Additional data
        """
        self.info(
            "trade_executed",
            event_type="trade",
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_id=order_id,
            strategy=strategy,
            **kwargs
        )

    def log_risk_event(
        self,
        risk_type: str,
        severity: str,
        message: str,
        **kwargs
    ):
        """
        Log risk management event

        Args:
            risk_type: Type of risk (position_limit, daily_loss, etc.)
            severity: Severity level (warning, critical)
            message: Risk message
            **kwargs: Additional data
        """
        level = logging.CRITICAL if severity == "critical" else logging.WARNING
        self._log(
            level,
            message,
            event_type="risk",
            risk_type=risk_type,
            severity=severity,
            **kwargs
        )

    def log_performance(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        **kwargs
    ):
        """
        Log performance metrics

        Args:
            operation: Operation name
            duration_ms: Duration in milliseconds
            success: Whether operation succeeded
            **kwargs: Additional data
        """
        self.info(
            f"{operation}_performance",
            event_type="performance",
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            **kwargs
        )

    def log_api_call(
        self,
        endpoint: str,
        method: str,
        duration_ms: float,
        status_code: Optional[int] = None,
        **kwargs
    ):
        """
        Log API call metrics

        Args:
            endpoint: API endpoint
            method: HTTP method
            duration_ms: Request duration
            status_code: HTTP status code
            **kwargs: Additional data
        """
        self.info(
            "api_call",
            event_type="api",
            endpoint=endpoint,
            method=method,
            duration_ms=duration_ms,
            status_code=status_code,
            **kwargs
        )

    class correlation_context:
        """Context manager for correlation ID"""

        def __init__(self, correlation_id: Optional[str] = None):
            """
            Initialize correlation context

            Args:
                correlation_id: Optional correlation ID (generated if not provided)
            """
            self.correlation_id = correlation_id or str(uuid.uuid4())
            self.token = None

        def __enter__(self):
            """Set correlation ID in context"""
            self.token = correlation_id_var.set(self.correlation_id)
            return self.correlation_id

        def __exit__(self, *args):
            """Reset correlation ID"""
            if self.token:
                correlation_id_var.reset(self.token)

    class performance_context:
        """Context manager for performance logging"""

        def __init__(
            self,
            logger: 'StructuredLogger',
            operation: str,
            **context_data
        ):
            """
            Initialize performance context

            Args:
                logger: StructuredLogger instance
                operation: Operation name
                **context_data: Additional context data
            """
            self.logger = logger
            self.operation = operation
            self.context_data = context_data
            self.start_time = None

        def __enter__(self):
            """Start timing"""
            self.start_time = time.time()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            """Log performance"""
            duration_ms = (time.time() - self.start_time) * 1000
            success = exc_type is None

            self.logger.log_performance(
                self.operation,
                duration_ms,
                success=success,
                **self.context_data
            )

            # Don't suppress exceptions
            return False


def get_logger(name: str) -> StructuredLogger:
    """
    Get or create a structured logger

    Args:
        name: Logger name (usually __name__)

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)


def log_function_call(
    logger: Optional[StructuredLogger] = None,
    log_args: bool = False,
    log_result: bool = False
):
    """
    Decorator to log function calls with performance metrics

    Args:
        logger: Optional logger (uses function's module logger if not provided)
        log_args: Whether to log function arguments
        log_result: Whether to log return value

    Usage:
        @log_function_call(log_args=True)
        def my_function(a, b):
            return a + b
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_logger = logger or get_logger(func.__module__)

            # Log function entry
            log_data = {
                'function': func.__name__,
                'module': func.__module__,
            }

            if log_args:
                log_data['args'] = str(args)
                log_data['kwargs'] = str(kwargs)

            func_logger.debug(f"Entering {func.__name__}", **log_data)

            # Execute with performance tracking
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                # Log success
                result_data = {
                    'function': func.__name__,
                    'duration_ms': duration_ms,
                    'success': True
                }

                if log_result:
                    result_data['result'] = str(result)

                func_logger.debug(
                    f"Completed {func.__name__}",
                    **result_data
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                # Log failure
                func_logger.error(
                    f"Failed {func.__name__}",
                    exc_info=True,
                    function=func.__name__,
                    duration_ms=duration_ms,
                    success=False,
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                raise

        return wrapper
    return decorator


# Example usage and testing
if __name__ == "__main__":
    # Create logger
    logger = get_logger(__name__)

    # Basic logging
    logger.info("System started", version="1.0.0", mode="production")

    # Logging with correlation ID
    with logger.correlation_context() as corr_id:
        logger.info("Processing order", order_id="12345")
        logger.info("Order validated", order_id="12345")
        logger.info("Order executed", order_id="12345")

    # Trade logging
    logger.log_trade(
        symbol="RELIANCE",
        side="BUY",
        quantity=100,
        price=2450.50,
        order_id="ORD-001",
        strategy="MovingAverage",
        signal_strength=0.85
    )

    # Performance logging
    with logger.performance_context("database_query", table="trades"):
        time.sleep(0.1)  # Simulate work

    # Risk event
    logger.log_risk_event(
        risk_type="position_limit",
        severity="warning",
        message="Approaching position limit",
        current_positions=18,
        limit=20
    )

    # Error logging
    try:
        raise ValueError("Test error")
    except Exception:
        logger.error("Operation failed", exc_info=True, operation="test")

    # Function decorator
    @log_function_call(log_args=True, log_result=True)
    def calculate_pnl(entry_price, exit_price, quantity):
        return (exit_price - entry_price) * quantity

    pnl = calculate_pnl(2400, 2450, 100)

    print("\n✅ Structured logging examples completed")
    print("📋 Check logs/trading_system_structured.log for JSON formatted logs")
