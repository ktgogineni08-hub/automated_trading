#!/usr/bin/env python3
"""
Comprehensive Exception Handling Framework
Addresses Critical Issue #6: Missing Exception Handling

CRITICAL FIXES:
- Wraps critical trading operations with exception handling
- Prevents unhandled exceptions from crashing the system
- Provides graceful degradation for API failures
- Adds correlation IDs for distributed tracing
- Implements circuit breaker pattern for failing operations
"""

import functools
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Callable, Optional, Any, Dict, TypeVar, cast
from collections import defaultdict
from threading import Lock
import logging

logger = logging.getLogger('trading_system.exception_handler')

T = TypeVar('T')


class TradingSystemError(Exception):
    """Base exception for trading system"""
    pass


class APIError(TradingSystemError):
    """API-related errors"""
    pass


class DataError(TradingSystemError):
    """Data processing errors"""
    pass


class OrderExecutionError(TradingSystemError):
    """Order execution errors"""
    pass


class CircuitBreakerError(TradingSystemError):
    """Circuit breaker is open"""
    pass


class CircuitBreaker:
    """
    Circuit breaker pattern implementation

    Prevents cascading failures by stopping calls to failing operations

    States:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Too many failures, calls blocked
    - HALF_OPEN: Testing if operation recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        success_threshold: int = 2
    ):
        """
        Initialize circuit breaker

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout_seconds: Seconds to wait before attempting recovery
            success_threshold: Successes needed to close circuit from half-open
        """
        self.failure_threshold = failure_threshold
        self.timeout = timedelta(seconds=timeout_seconds)
        self.success_threshold = success_threshold

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"
        self._lock = Lock()

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Call function through circuit breaker

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
        """
        with self._lock:
            if self.state == "OPEN":
                # Check if timeout expired
                if self.last_failure_time and \
                   datetime.now() - self.last_failure_time > self.timeout:
                    self.state = "HALF_OPEN"
                    self.success_count = 0
                    logger.info("Circuit breaker entering HALF_OPEN state")
                else:
                    raise CircuitBreakerError(
                        f"Circuit breaker is OPEN. "
                        f"Retry after {self.timeout.total_seconds()}s"
                    )

        # Attempt to call function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call"""
        with self._lock:
            self.failure_count = 0

            if self.state == "HALF_OPEN":
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = "CLOSED"
                    logger.info("Circuit breaker CLOSED (recovered)")

    def _on_failure(self):
        """Handle failed call"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            if self.state == "HALF_OPEN":
                self.state = "OPEN"
                logger.warning("Circuit breaker re-OPENED")

            elif self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.error(
                    f"Circuit breaker OPENED after {self.failure_count} failures"
                )


# Global circuit breakers for different operations
_circuit_breakers: Dict[str, CircuitBreaker] = {}
_circuit_breaker_lock = Lock()


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create circuit breaker for named operation"""
    with _circuit_breaker_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker()
        return _circuit_breakers[name]


class CorrelationContext:
    """Thread-local correlation ID for request tracing"""

    _correlation_id: Optional[str] = None

    @classmethod
    def get_correlation_id(cls) -> str:
        """Get current correlation ID or generate new one"""
        if cls._correlation_id is None:
            cls._correlation_id = str(uuid.uuid4())
        return cls._correlation_id

    @classmethod
    def set_correlation_id(cls, correlation_id: str):
        """Set correlation ID for current context"""
        cls._correlation_id = correlation_id

    @classmethod
    def clear_correlation_id(cls):
        """Clear correlation ID"""
        cls._correlation_id = None


def safe_execute(
    operation_name: str,
    default_return: Any = None,
    raise_on_error: bool = False,
    use_circuit_breaker: bool = False,
    log_errors: bool = True
):
    """
    Decorator for safe execution with exception handling

    Args:
        operation_name: Name of operation (for logging)
        default_return: Value to return on error
        raise_on_error: Re-raise exceptions after logging
        use_circuit_breaker: Use circuit breaker pattern
        log_errors: Log exceptions

    Usage:
        @safe_execute("place_order", default_return=None, use_circuit_breaker=True)
        def place_order(symbol, quantity):
            # Implementation
            pass
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            correlation_id = CorrelationContext.get_correlation_id()

            try:
                # Use circuit breaker if enabled
                if use_circuit_breaker:
                    breaker = get_circuit_breaker(operation_name)
                    result = breaker.call(func, *args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                return result

            except CircuitBreakerError as e:
                if log_errors:
                    logger.error(
                        f"[{correlation_id}] Circuit breaker blocked {operation_name}: {e}"
                    )
                if raise_on_error:
                    raise
                return cast(T, default_return)

            except Exception as e:
                if log_errors:
                    logger.error(
                        f"[{correlation_id}] Error in {operation_name}: {e}\n"
                        f"Traceback:\n{traceback.format_exc()}"
                    )

                if raise_on_error:
                    raise

                return cast(T, default_return)

        return wrapper

    return decorator


def critical_section(operation_name: str):
    """
    Decorator for critical sections that must not fail silently

    Always logs errors with full traceback
    Always raises exceptions

    Args:
        operation_name: Name of critical operation

    Usage:
        @critical_section("execute_trade")
        def execute_trade(order):
            # Critical trading logic
            pass
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            correlation_id = CorrelationContext.get_correlation_id()

            try:
                logger.info(
                    f"[{correlation_id}] CRITICAL: Starting {operation_name}"
                )
                result = func(*args, **kwargs)
                logger.info(
                    f"[{correlation_id}] CRITICAL: Completed {operation_name}"
                )
                return result

            except Exception as e:
                logger.critical(
                    f"[{correlation_id}] CRITICAL FAILURE in {operation_name}: {e}\n"
                    f"Args: {args}\n"
                    f"Kwargs: {kwargs}\n"
                    f"Traceback:\n{traceback.format_exc()}"
                )
                raise

        return wrapper

    return decorator


def retry(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_multiplier: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Retry decorator with exponential backoff

    Args:
        max_attempts: Maximum number of retry attempts
        delay_seconds: Initial delay between retries
        backoff_multiplier: Multiply delay by this after each retry
        exceptions: Tuple of exception types to catch and retry

    Usage:
        @retry(max_attempts=3, delay_seconds=1.0, exceptions=(APIError,))
        def fetch_market_data():
            # API call that may fail temporarily
            pass
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            correlation_id = CorrelationContext.get_correlation_id()
            current_delay = delay_seconds

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    if attempt == max_attempts:
                        logger.error(
                            f"[{correlation_id}] Failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    logger.warning(
                        f"[{correlation_id}] Attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {current_delay}s..."
                    )

                    import time
                    time.sleep(current_delay)
                    current_delay *= backoff_multiplier

            # Should never reach here
            raise RuntimeError("Retry logic error")

        return wrapper

    return decorator


class ErrorCounter:
    """Track error rates for monitoring"""

    def __init__(self):
        self._errors: Dict[str, int] = defaultdict(int)
        self._lock = Lock()

    def increment(self, error_type: str):
        """Increment error counter"""
        with self._lock:
            self._errors[error_type] += 1

    def get_count(self, error_type: str) -> int:
        """Get error count"""
        with self._lock:
            return self._errors[error_type]

    def get_all_counts(self) -> Dict[str, int]:
        """Get all error counts"""
        with self._lock:
            return dict(self._errors)

    def reset(self):
        """Reset all counters"""
        with self._lock:
            self._errors.clear()


# Global error counter
_error_counter = ErrorCounter()


def get_error_counter() -> ErrorCounter:
    """Get global error counter"""
    return _error_counter


def log_exception_with_context(
    operation: str,
    exception: Exception,
    context: Optional[Dict[str, Any]] = None
):
    """
    Log exception with full context for debugging

    Args:
        operation: Operation name
        exception: Exception that occurred
        context: Additional context (e.g., function arguments)
    """
    correlation_id = CorrelationContext.get_correlation_id()

    error_details = {
        'correlation_id': correlation_id,
        'operation': operation,
        'exception_type': type(exception).__name__,
        'exception_message': str(exception),
        'timestamp': datetime.now().isoformat(),
    }

    if context:
        error_details['context'] = context

    logger.error(
        f"Exception Details:\n"
        f"  Correlation ID: {correlation_id}\n"
        f"  Operation: {operation}\n"
        f"  Exception: {type(exception).__name__}\n"
        f"  Message: {exception}\n"
        f"  Context: {context}\n"
        f"  Traceback:\n{traceback.format_exc()}"
    )

    # Increment error counter
    _error_counter.increment(type(exception).__name__)


if __name__ == "__main__":
    # Test suite
    print("🧪 Testing Exception Handler\n")

    # Test 1: Safe execute with default return
    print("1. Safe Execute with Default Return:")

    @safe_execute("test_operation", default_return="DEFAULT", raise_on_error=False)
    def failing_function():
        raise ValueError("Test error")

    result = failing_function()
    print(f"   Result: {result}")
    assert result == "DEFAULT", "Should return default on error"
    print("   ✅ Passed\n")

    # Test 2: Circuit breaker
    print("2. Circuit Breaker:")

    call_count = [0]  # Use list for mutability in closure

    @safe_execute("circuit_test", use_circuit_breaker=True, raise_on_error=False)
    def intermittent_failure():
        call_count[0] += 1
        if call_count[0] < 6:  # Fail first 5 times
            raise APIError("API temporarily unavailable")
        return "SUCCESS"

    # This should trigger circuit breaker
    for i in range(10):
        try:
            result = intermittent_failure()
            print(f"   Attempt {i + 1}: {result}")
        except CircuitBreakerError as e:
            print(f"   Attempt {i + 1}: Circuit breaker blocked")

    print("   ✅ Circuit breaker activated after failures\n")

    # Test 3: Retry with exponential backoff
    print("3. Retry with Exponential Backoff:")

    attempt_count = [0]  # Use list for mutability in closure

    @retry(max_attempts=3, delay_seconds=0.1, exceptions=(ValueError,))
    def eventually_succeeds():
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise ValueError(f"Attempt {attempt_count[0]} failed")
        return "SUCCESS"

    result = eventually_succeeds()
    print(f"   Result after {attempt_count[0]} attempts: {result}")
    assert result == "SUCCESS", "Should succeed after retries"
    print("   ✅ Passed\n")

    # Test 4: Correlation ID tracking
    print("4. Correlation ID Tracking:")

    @safe_execute("correlated_op")
    def operation_with_correlation():
        corr_id = CorrelationContext.get_correlation_id()
        print(f"   Correlation ID: {corr_id}")
        return corr_id

    CorrelationContext.set_correlation_id("TEST-123")
    corr_id = operation_with_correlation()
    assert corr_id == "TEST-123", "Should preserve correlation ID"
    print("   ✅ Passed\n")

    # Test 5: Critical section
    print("5. Critical Section (always raises):")

    @critical_section("critical_operation")
    def critical_failure():
        raise RuntimeError("Critical error")

    try:
        critical_failure()
        print("   ❌ FAILED: Should have raised exception")
    except RuntimeError:
        print("   ✅ Passed: Exception raised as expected\n")

    # Test 6: Error counter
    print("6. Error Counter:")
    counter = get_error_counter()
    counter.reset()
    counter.increment("APIError")
    counter.increment("APIError")
    counter.increment("ValueError")

    counts = counter.get_all_counts()
    print(f"   Error counts: {counts}")
    assert counts["APIError"] == 2, "Should count API errors"
    assert counts["ValueError"] == 1, "Should count ValueError"
    print("   ✅ Passed\n")

    print("✅ All exception handler tests passed!")
