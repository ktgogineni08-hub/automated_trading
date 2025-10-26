#!/usr/bin/env python3
"""
Trading System Utilities
Common utilities for validation, comparisons, and safe operations
"""

import time
import math
from typing import Optional, Callable, Any
from functools import wraps
import logging

from trading_exceptions import ValidationError
from input_validator import InputValidator

# Backward compatibility: allow legacy code that uses logger.*
if not hasattr(logging.Logger, "logger"):  # pragma: no cover - compatibility shim
    logging.Logger.logger = property(lambda self: self)

logger = logging.getLogger('trading_system')

# ============================================================================
# FLOAT COMPARISON UTILITIES (FIX HIGH-4)
# ============================================================================

EPSILON = 1e-9  # Tolerance for float comparisons
PRICE_EPSILON = 0.01  # Tolerance for price comparisons (1 paisa)

def float_equals(a: float, b: float, epsilon: float = EPSILON) -> bool:
    """
    Safely compare two floats for equality

    Args:
        a: First float
        b: Second float
        epsilon: Tolerance for comparison

    Returns:
        True if floats are equal within epsilon
    """
    return abs(a - b) < epsilon

def is_zero(value: float, epsilon: float = EPSILON) -> bool:
    """Check if float is effectively zero"""
    return abs(value) < epsilon

def is_positive(value: float, epsilon: float = EPSILON) -> bool:
    """Check if float is positive (greater than epsilon)"""
    return value > epsilon

def is_negative(value: float, epsilon: float = EPSILON) -> bool:
    """Check if float is negative (less than -epsilon)"""
    return value < -epsilon

def price_equals(price1: float, price2: float) -> bool:
    """Compare prices with 1 paisa tolerance"""
    return float_equals(price1, price2, PRICE_EPSILON)

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default if denominator is zero

    Args:
        numerator: The numerator
        denominator: The denominator
        default: Value to return if denominator is zero

    Returns:
        Result of division or default value
    """
    if is_zero(denominator):
        return default
    return numerator / denominator


def validate_symbol(symbol: str) -> str:
    """
    Validate and normalize a trading symbol using the shared InputValidator.

    Args:
        symbol: Raw symbol string

    Returns:
        Sanitized/validated symbol string

    Raises:
        ValidationError: If the symbol fails validation rules
    """
    return InputValidator.validate_symbol(symbol)


# ============================================================================
# INPUT VALIDATION UTILITIES (FIX HIGH-3)
# ============================================================================

def get_validated_int(prompt: str, min_val: int, max_val: int, default: Optional[int] = None) -> int:
    """
    Get validated integer input from user

    Args:
        prompt: Prompt to display
        min_val: Minimum acceptable value
        max_val: Maximum acceptable value
        default: Default value if user presses Enter

    Returns:
        Validated integer
    """
    while True:
        try:
            user_input = input(prompt).strip()

            if not user_input and default is not None:
                return default

            value = int(user_input)

            if min_val <= value <= max_val:
                return value
            else:
                print(f"❌ Please enter a number between {min_val} and {max_val}")

        except ValueError:
            print("❌ Invalid input. Please enter a number.")
        except (KeyboardInterrupt, EOFError):
            print("\n⚠️  Input cancelled")
            raise


def get_validated_float(prompt: str, min_val: float, max_val: float, default: Optional[float] = None) -> float:
    """Get validated float input from user"""
    while True:
        try:
            user_input = input(prompt).strip()

            if not user_input and default is not None:
                return default

            value = float(user_input)

            if min_val <= value <= max_val:
                return value
            else:
                print(f"❌ Please enter a number between {min_val} and {max_val}")

        except ValueError:
            print("❌ Invalid input. Please enter a number.")
        except (KeyboardInterrupt, EOFError):
            print("\n⚠️  Input cancelled")
            raise


def validate_financial_amount(value: float, min_val: float = 0.0, max_val: float = 1e12) -> float:
    """
    Validate financial amount is within acceptable bounds

    Args:
        value: Amount to validate
        min_val: Minimum acceptable value
        max_val: Maximum acceptable value

    Returns:
        Validated amount

    Raises:
        ValidationError: If amount is invalid or outside acceptable range

    Example:
        cash = validate_financial_amount(1000000.0, min_val=1000.0, max_val=100000000.0)
    """
    if not isinstance(value, (int, float)):
        raise ValidationError(f"Financial amount must be numeric, got {type(value)}")

    if math.isnan(value) or math.isinf(value):
        raise ValidationError(f"Financial amount cannot be NaN or Inf: {value}")

    if value < min_val or value > max_val:
        raise ValidationError(f"Financial amount {value:,.2f} outside acceptable range [{min_val:,.2f}, {max_val:,.2f}]")

    return float(value)


def get_validated_choice(prompt: str, valid_choices: list, default: Optional[str] = None) -> str:
    """Get validated choice from list"""
    while True:
        try:
            user_input = input(prompt).strip().lower()

            if not user_input and default is not None:
                return default

            if user_input in [str(c).lower() for c in valid_choices]:
                return user_input
            else:
                print(f"❌ Please choose from: {', '.join(map(str, valid_choices))}")

        except (KeyboardInterrupt, EOFError):
            print("\n⚠️  Input cancelled")
            raise


def get_confirmed_input(prompt: str, confirmation_word: str = "CONFIRM") -> bool:
    """Get confirmation from user"""
    try:
        user_input = input(f"{prompt} (Type '{confirmation_word}' to proceed): ").strip().upper()
        return user_input == confirmation_word
    except (KeyboardInterrupt, EOFError):
        print("\n⚠️  Cancelled")
        return False


# ============================================================================
# EXPONENTIAL BACKOFF (FIX MEDIUM-2)
# ============================================================================

def exponential_backoff(
    func: Callable,
    max_attempts: int = 5,
    initial_delay: float = 0.5,
    max_delay: float = 30.0,
    exponential_base: float = 2.0
) -> Any:
    """
    Retry function with exponential backoff

    Args:
        func: Function to retry
        max_attempts: Maximum retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential growth

    Returns:
        Function result

    Raises:
        Last exception if all attempts fail
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            last_exception = e

            if attempt < max_attempts - 1:
                logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed: {e}. Retrying in {delay:.1f}s...")
                time.sleep(delay)
                delay = min(delay * exponential_base, max_delay)
            else:
                logger.error(f"All {max_attempts} attempts failed")

    raise last_exception


def poll_with_backoff(
    check_func: Callable[[], Optional[Any]],
    timeout: float = 30.0,
    initial_interval: float = 0.5,
    max_interval: float = 5.0
) -> Optional[Any]:
    """
    Poll a function with exponential backoff until it returns non-None or timeout

    Args:
        check_func: Function to poll (returns None if not ready, result if ready)
        timeout: Maximum time to wait
        initial_interval: Initial polling interval
        max_interval: Maximum polling interval

    Returns:
        Result from check_func or None if timeout
    """
    start_time = time.time()
    interval = initial_interval

    while time.time() - start_time < timeout:
        result = check_func()
        if result is not None:
            return result

        time.sleep(interval)
        interval = min(interval * 2, max_interval)

    return None


# ============================================================================
# CIRCUIT BREAKER (FIX MEDIUM-3)
# ============================================================================

class CircuitBreaker:
    """
    Circuit breaker pattern for API calls

    States:
    - CLOSED: Normal operation
    - OPEN: Too many failures, reject calls
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.name = name

        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker"""

        # Check if circuit should transition from OPEN to HALF_OPEN
        if self.state == 'OPEN':
            if self.last_failure_time and time.time() - self.last_failure_time > self.timeout:
                logger.info(f"Circuit breaker {self.name}: OPEN → HALF_OPEN (timeout expired)")
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker {self.name} is OPEN "
                    f"(failures: {self.failure_count}/{self.failure_threshold})"
                )

        # Try to execute
        try:
            result = func(*args, **kwargs)

            # Success - reset if we were in HALF_OPEN
            if self.state == 'HALF_OPEN':
                logger.info(f"Circuit breaker {self.name}: HALF_OPEN → CLOSED (recovery confirmed)")
                self.state = 'CLOSED'
                self.failure_count = 0

            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            # Open circuit if threshold exceeded
            if self.failure_count >= self.failure_threshold:
                if self.state != 'OPEN':
                    logger.error(
                        f"Circuit breaker {self.name}: {self.state} → OPEN "
                        f"(failures: {self.failure_count}/{self.failure_threshold})"
                    )
                self.state = 'OPEN'

            raise

    def reset(self):
        """Manually reset circuit breaker"""
        logger.info(f"Circuit breaker {self.name}: Manual reset")
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


# ============================================================================
# POSITION SIZE VALIDATION (FIX MEDIUM-5)
# ============================================================================

# Configuration
MAX_POSITION_SIZE_INR = 500_000  # 5 lakh max per position
MAX_TOTAL_EXPOSURE_INR = 5_000_000  # 50 lakh max total exposure
MAX_SHARES_PER_TRADE = 100_000

def validate_position_size(
    shares: int,
    price: float,
    max_position_value: float = MAX_POSITION_SIZE_INR,
    max_shares: int = MAX_SHARES_PER_TRADE
) -> None:
    """
    Validate position size against safety limits

    Args:
        shares: Number of shares
        price: Price per share
        max_position_value: Maximum position value in INR
        max_shares: Maximum number of shares

    Raises:
        ValueError: If position size exceeds limits
    """
    from trading_exceptions import RiskManagementError

    if shares <= 0:
        raise ValueError(f"Shares must be positive, got {shares}")

    if shares > max_shares:
        raise RiskManagementError(
            f"Share quantity {shares:,} exceeds maximum {max_shares:,}"
        )

    position_value = shares * price
    if position_value > max_position_value:
        raise RiskManagementError(
            f"Position value ₹{position_value:,.2f} exceeds maximum ₹{max_position_value:,.2f}"
        )


def validate_total_exposure(
    current_exposure: float,
    additional_exposure: float,
    max_total: float = MAX_TOTAL_EXPOSURE_INR
) -> None:
    """Validate total portfolio exposure"""
    from trading_exceptions import RiskManagementError

    total = current_exposure + additional_exposure
    if total > max_total:
        raise RiskManagementError(
            f"Total exposure ₹{total:,.2f} would exceed maximum ₹{max_total:,.2f}"
        )


# ============================================================================
# GRACEFUL SHUTDOWN (FIX MEDIUM-7)
# ============================================================================

import signal
import atexit

class GracefulShutdown:
    """Handle graceful shutdown on signals"""

    def __init__(self, cleanup_func: Callable):
        self.cleanup_func = cleanup_func
        self.shutdown_requested = False

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        atexit.register(self._cleanup)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        signal_name = 'SIGINT' if signum == signal.SIGINT else 'SIGTERM'
        logger.warning(f"Received {signal_name}, initiating graceful shutdown...")
        self.shutdown_requested = True

    def _cleanup(self):
        """Cleanup on exit"""
        if not self.shutdown_requested:
            logger.info("Normal exit, running cleanup...")
        self.cleanup_func()

    def should_stop(self) -> bool:
        """Check if shutdown was requested"""
        return self.shutdown_requested


def setup_graceful_shutdown(cleanup_func: Callable) -> GracefulShutdown:
    """
    Setup graceful shutdown handler with cleanup function

    Args:
        cleanup_func: Function to call on shutdown (should save state, close connections, etc.)

    Returns:
        GracefulShutdown instance that can be checked with should_stop()

    Example:
        def cleanup():
            portfolio.save_state()
            logger.info("State saved")

        shutdown_handler = setup_graceful_shutdown(cleanup)
        while not shutdown_handler.should_stop():
            # Main trading loop
            pass
    """
    return GracefulShutdown(cleanup_func)


# ============================================================================
# TIMEZONE UTILITIES (FIX MEDIUM-8)
# ============================================================================

import pytz
from datetime import datetime, timedelta

IST = pytz.timezone('Asia/Kolkata')

def get_current_time() -> datetime:
    """Get current time in IST (always timezone-aware)"""
    return datetime.now(IST)

def parse_timestamp(ts_string: str) -> datetime:
    """Parse timestamp and ensure it's IST timezone-aware"""
    dt = datetime.fromisoformat(ts_string.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = IST.localize(dt)
    else:
        dt = dt.astimezone(IST)
    return dt

def format_timestamp(dt: datetime) -> str:
    """Format datetime as IST timestamp"""
    if dt.tzinfo is None:
        dt = IST.localize(dt)
    return dt.astimezone(IST).isoformat()


# Aliases for consistency with main system imports
get_ist_now = get_current_time
format_ist_timestamp = format_timestamp


# ============================================================================
# LOGGING SANITIZATION (FIX MEDIUM-6)
# ============================================================================

SENSITIVE_KEYS = {
    'access_token', 'api_secret', 'api_key', 'password',
    'secret', 'token', 'authorization', 'auth',
    'account_number', 'pan', 'account_id'
}

def sanitize_for_logging(data: Any) -> Any:
    """Remove sensitive fields before logging"""
    if isinstance(data, dict):
        return {
            k: '***REDACTED***' if k.lower() in SENSITIVE_KEYS else sanitize_for_logging(v)
            for k, v in data.items()
        }
    elif isinstance(data, (list, tuple)):
        return type(data)(sanitize_for_logging(item) for item in data)
    else:
        return data


# ============================================================================
# ATOMIC OPERATIONS (FIX HIGH-5)
# ============================================================================

import threading

class AtomicFloat:
    """Thread-safe atomic float operations"""

    def __init__(self, initial_value: float = 0.0):
        self._value = initial_value
        self._lock = threading.RLock()

    def get(self) -> float:
        """Get current value"""
        with self._lock:
            return self._value

    def set(self, value: float) -> None:
        """Set value"""
        with self._lock:
            self._value = value

    def add(self, amount: float) -> float:
        """Add amount and return new value"""
        with self._lock:
            self._value += amount
            return self._value

    def subtract(self, amount: float) -> float:
        """Subtract amount and return new value"""
        with self._lock:
            self._value -= amount
            return self._value

    def compare_and_set(self, expected: float, new_value: float) -> bool:
        """Atomically set value if it equals expected"""
        with self._lock:
            if float_equals(self._value, expected):
                self._value = new_value
                return True
            return False

    def deduct_if_available(self, amount: float) -> bool:
        """Deduct amount if sufficient funds available"""
        with self._lock:
            if self._value >= amount:
                self._value -= amount
                return True
            return False

    def __float__(self) -> float:
        return self.get()

    def __repr__(self) -> str:
        return f"AtomicFloat({self.get()})"


# ============================================================================
# CONSTANTS (FIX LOW-1: Magic Numbers)
# ============================================================================

# API Configuration
API_RETRY_ATTEMPTS = 3
API_TIMEOUT_SECONDS = 30
ORDER_STATUS_POLL_INTERVAL = 2  # seconds
ORDER_CONFIRMATION_TIMEOUT = 60  # seconds

# Trading Limits
MIN_TRADE_AMOUNT_INR = 1000
MAX_TRADE_AMOUNT_INR = 1_000_000
MIN_SHARES = 1
MAX_SHARES = 1_000_000

# File Operations
STATE_SAVE_INTERVAL = 300  # seconds (5 minutes)
BACKUP_RETENTION_DAYS = 30

# Timing
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30

# Price Tolerances
MIN_PRICE = 0.01  # 1 paisa
MAX_PRICE = 1_000_000  # 10 lakh per unit


# ============================================================================
# SAFE TYPE CONVERSION
# ============================================================================

def safe_float_conversion(value: Any, default: float = 0.0) -> float:
    """
    Safely convert value to float with validation
    
    Handles pandas Series, DataFrames, numpy arrays, and scalar values.
    Returns default value if conversion fails.
    
    Args:
        value: Value to convert (can be Series, DataFrame, array, scalar)
        default: Default value to return on failure
        
    Returns:
        Float value or default
    """
    import pandas as pd
    import numpy as np
    
    try:
        # Handle None and NaN values
        if value is None or pd.isna(value):
            return default

        # Handle pandas Series by extracting scalar value
        if isinstance(value, pd.Series):
            if len(value) > 0:
                try:
                    # For Series with single element, use .item() directly
                    if len(value) == 1:
                        return float(value.item())
                    else:
                        # For Series with multiple elements, get the last value
                        last_value = value.iloc[-1]
                        if hasattr(last_value, 'item'):
                            return float(last_value.item())
                        else:
                            return float(last_value)
                except (ValueError, TypeError, IndexError, AttributeError):
                    # If .item() fails, try converting the Series to float directly
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return default
            else:
                return default

        # Handle pandas DataFrame by extracting scalar value
        if isinstance(value, pd.DataFrame):
            if not value.empty:
                try:
                    scalar_value = value.iloc[0, 0]
                    if hasattr(scalar_value, 'item'):
                        scalar_value = scalar_value.item()
                    return float(scalar_value)
                except (ValueError, TypeError, IndexError):
                    return default
            else:
                return default

        # Handle numpy/pandas scalar types
        if hasattr(value, 'item'):
            try:
                value = value.item()
            except (ValueError, TypeError):
                pass

        # Handle numpy arrays
        if isinstance(value, np.ndarray):
            if value.size > 0:
                try:
                    return float(value.item())
                except (ValueError, TypeError):
                    return default
            else:
                return default

        # Handle scalar values
        result = float(value)
        if not np.isfinite(result):
            logger.warning(f"Non-finite value encountered: {value}")
            return default
        return result
    except (ValueError, TypeError, IndexError) as e:
        logger.warning(f"Failed to convert {value} to float: {e}")
        return default
