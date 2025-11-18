#!/usr/bin/env python3
"""
Test suite for all code review fixes
"""

import pytest
import tempfile
import os
from pathlib import Path

# Import utilities
from trading_utils import (
    float_equals, is_zero, is_positive, price_equals,
    get_validated_int, exponential_backoff, poll_with_backoff,
    CircuitBreaker, CircuitBreakerOpenError,
    validate_position_size, AtomicFloat,
    get_current_time, parse_timestamp,
    sanitize_for_logging
)
from safe_file_ops import (
    atomic_write_json, atomic_write_pickle,
    safe_read_json, safe_read_pickle,
    StateManager
)
from trading_exceptions import ValidationError


# ============================================================================
# TEST FLOAT COMPARISONS (FIX HIGH-4)
# ============================================================================

def test_float_equals():
    """Test safe float comparison"""
    assert float_equals(0.1 + 0.2, 0.3)
    assert float_equals(1.0, 1.0000000001)
    assert not float_equals(1.0, 1.1)

def test_is_zero():
    """Test zero detection"""
    assert is_zero(0.0)
    assert is_zero(0.0000000001)
    assert not is_zero(0.1)

def test_price_equals():
    """Test price comparison with paisa tolerance"""
    assert price_equals(100.00, 100.009)  # Within 1 paisa
    assert not price_equals(100.00, 100.02)  # More than 1 paisa


# ============================================================================
# TEST EXPONENTIAL BACKOFF (FIX MEDIUM-2)
# ============================================================================

def test_exponential_backoff_success():
    """Test successful retry"""
    attempt_count = [0]

    def flaky_function():
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise ValueError("Not yet!")
        return "success"

    result = exponential_backoff(flaky_function, max_attempts=5, initial_delay=0.01)
    assert result == "success"
    assert attempt_count[0] == 3


def test_exponential_backoff_failure():
    """Test all attempts fail"""
    def always_fails():
        raise ValueError("Always fails")

    with pytest.raises(ValueError):
        exponential_backoff(always_fails, max_attempts=3, initial_delay=0.01)


def test_poll_with_backoff():
    """Test polling with backoff"""
    check_count = [0]

    def check_ready():
        check_count[0] += 1
        if check_count[0] >= 3:
            return "ready"
        return None

    result = poll_with_backoff(check_ready, timeout=10, initial_interval=0.01)
    assert result == "ready"
    assert check_count[0] == 3


# ============================================================================
# TEST CIRCUIT BREAKER (FIX MEDIUM-3)
# ============================================================================

def test_circuit_breaker_opens():
    """Test circuit breaker opens after threshold"""
    breaker = CircuitBreaker(failure_threshold=3, timeout=1.0)

    def failing_func():
        raise ValueError("Fail")

    # First 3 failures should pass through
    for i in range(3):
        with pytest.raises(ValueError):
            breaker.call(failing_func)

    # 4th call should raise CircuitBreakerOpenError
    with pytest.raises(CircuitBreakerOpenError):
        breaker.call(failing_func)


def test_circuit_breaker_recovers():
    """Test circuit breaker transitions to HALF_OPEN and recovers"""
    breaker = CircuitBreaker(failure_threshold=2, timeout=0.1)

    def failing_func():
        raise ValueError("Fail")

    # Open the circuit
    for i in range(2):
        with pytest.raises(ValueError):
            breaker.call(failing_func)

    # Should be OPEN
    with pytest.raises(CircuitBreakerOpenError):
        breaker.call(failing_func)

    # Wait for timeout
    import time
    time.sleep(0.2)

    # Now should try again and succeed
    def success_func():
        return "success"

    result = breaker.call(success_func)
    assert result == "success"
    assert breaker.state == 'CLOSED'


# ============================================================================
# TEST POSITION VALIDATION (FIX MEDIUM-5)
# ============================================================================

def test_validate_position_size_normal():
    """Test position size validation passes for normal trade"""
    validate_position_size(shares=100, price=100)  # 10k - OK


def test_validate_position_size_too_large():
    """Test position size validation fails for oversized trade"""
    from trading_exceptions import RiskManagementError

    with pytest.raises(RiskManagementError):
        validate_position_size(shares=10000, price=1000)  # 10M - too large


def test_validate_position_negative_shares():
    """Test validation rejects negative shares"""
    with pytest.raises(ValueError):
        validate_position_size(shares=-100, price=100)


# ============================================================================
# TEST ATOMIC CASH OPERATIONS (FIX HIGH-5)
# ============================================================================

def test_atomic_float_basic():
    """Test basic atomic float operations"""
    cash = AtomicFloat(10000.0)

    assert cash.get() == 10000.0
    cash.add(500.0)
    assert cash.get() == 10500.0
    cash.subtract(200.0)
    assert cash.get() == 10300.0


def test_atomic_float_deduct_if_available():
    """Test conditional deduction"""
    cash = AtomicFloat(1000.0)

    # Sufficient funds
    assert cash.deduct_if_available(500.0) == True
    assert cash.get() == 500.0

    # Insufficient funds
    assert cash.deduct_if_available(1000.0) == False
    assert cash.get() == 500.0  # Unchanged


def test_atomic_float_compare_and_set():
    """Test compare-and-set operation"""
    cash = AtomicFloat(1000.0)

    # Correct expected value
    assert cash.compare_and_set(1000.0, 2000.0) == True
    assert cash.get() == 2000.0

    # Wrong expected value
    assert cash.compare_and_set(1000.0, 3000.0) == False
    assert cash.get() == 2000.0  # Unchanged


# ============================================================================
# TEST FILE OPERATIONS (FIX HIGH-2, MEDIUM-4)
# ============================================================================

def test_atomic_write_json():
    """Test atomic JSON write"""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "test.json")
        data = {"key": "value", "number": 42}

        atomic_write_json(filepath, data)

        # Verify file exists and content is correct
        assert os.path.exists(filepath)
        with open(filepath, 'r') as f:
            import json
            loaded = json.load(f)
        assert loaded == data


def test_atomic_write_creates_backup():
    """Test that atomic write creates backup"""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "test.json")

        # Write initial data
        atomic_write_json(filepath, {"version": 1})

        # Write new data with backup
        atomic_write_json(filepath, {"version": 2}, create_backup=True)

        # Backup should exist
        backup_path = filepath + '.backup'
        assert os.path.exists(backup_path)

        # Backup should have old data
        with open(backup_path, 'r') as f:
            import json
            backup_data = json.load(f)
        assert backup_data["version"] == 1


def test_safe_read_recovers_from_backup():
    """Test recovery from backup on corrupt file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "test.json")
        backup_path = filepath + '.backup'

        # Create backup with valid data
        import json
        with open(backup_path, 'w') as f:
            json.dump({"recovered": True}, f)

        # Create corrupt main file
        with open(filepath, 'w') as f:
            f.write("{invalid json")

        # Should recover from backup
        data = safe_read_json(filepath)
        assert data == {"recovered": True}


def test_state_manager():
    """Test StateManager for safe state persistence"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = StateManager(tmpdir)

        # Save state
        state_data = {"cash": 10000, "positions": ["NIFTY"]}
        manager.save_state("portfolio", state_data, format='json')

        # Load state
        loaded = manager.load_state("portfolio", format='json')
        assert loaded == state_data

        # Check existence
        assert manager.state_exists("portfolio", format='json')
        assert not manager.state_exists("nonexistent", format='json')


# ============================================================================
# TEST TIMEZONE HANDLING (FIX MEDIUM-8)
# ============================================================================

def test_get_current_time_is_aware():
    """Test current time is timezone-aware"""
    now = get_current_time()
    assert now.tzinfo is not None
    assert now.tzinfo.zone == 'Asia/Kolkata'


def test_parse_timestamp_makes_aware():
    """Test timestamp parsing creates timezone-aware datetime"""
    # Naive timestamp
    ts = "2025-10-08T15:30:00"
    dt = parse_timestamp(ts)
    assert dt.tzinfo is not None

    # Already aware timestamp
    ts_aware = "2025-10-08T15:30:00+05:30"
    dt_aware = parse_timestamp(ts_aware)
    assert dt_aware.tzinfo is not None


# ============================================================================
# TEST LOGGING SANITIZATION (FIX MEDIUM-6)
# ============================================================================

def test_sanitize_for_logging():
    """Test sensitive data is redacted"""
    sensitive_data = {
        "api_key": "secret123",
        "user_name": "john",
        "access_token": "token456",
        "balance": 10000
    }

    sanitized = sanitize_for_logging(sensitive_data)

    assert sanitized["api_key"] == "***REDACTED***"
    assert sanitized["access_token"] == "***REDACTED***"
    assert sanitized["user_name"] == "john"  # Not sensitive
    assert sanitized["balance"] == 10000  # Not sensitive


def test_sanitize_nested_dict():
    """Test sanitization works on nested structures"""
    data = {
        "user": {
            "name": "john",
            "password": "secret"
        },
        "tokens": ["token1", "token2"]
    }

    sanitized = sanitize_for_logging(data)

    assert sanitized["user"]["password"] == "***REDACTED***"
    assert sanitized["user"]["name"] == "john"


# ============================================================================
# TEST NEWLY ADDED FUNCTIONS
# ============================================================================

def test_safe_divide():
    """Test safe_divide function"""
    from trading_utils import safe_divide

    # Normal division
    assert safe_divide(10.0, 2.0) == 5.0

    # Division by zero returns default
    assert safe_divide(10.0, 0.0, default=0.0) == 0.0
    assert safe_divide(10.0, 0.0, default=-1.0) == -1.0

    # Division by very small number (effectively zero)
    assert safe_divide(10.0, 1e-10, default=999.0) == 999.0


def test_validate_financial_amount():
    """Test validate_financial_amount function"""
    from trading_utils import validate_financial_amount

    # Valid amounts
    assert validate_financial_amount(1000.0) == 1000.0
    assert validate_financial_amount(50000.0, min_val=1000.0, max_val=100000.0) == 50000.0

    # Out of range
    with pytest.raises(ValidationError, match="outside acceptable range"):
        validate_financial_amount(500.0, min_val=1000.0, max_val=100000.0)

    with pytest.raises(ValidationError, match="outside acceptable range"):
        validate_financial_amount(200000.0, min_val=1000.0, max_val=100000.0)

    # Invalid types
    with pytest.raises(ValidationError, match="must be numeric"):
        validate_financial_amount("1000")

    # NaN and Inf
    import math
    with pytest.raises(ValidationError, match="cannot be NaN or Inf"):
        validate_financial_amount(math.nan)

    with pytest.raises(ValidationError, match="cannot be NaN or Inf"):
        validate_financial_amount(math.inf)


def test_setup_graceful_shutdown():
    """Test setup_graceful_shutdown function"""
    from trading_utils import setup_graceful_shutdown

    cleanup_called = []

    def cleanup():
        cleanup_called.append(True)

    handler = setup_graceful_shutdown(cleanup)

    # Should not have stopped yet
    assert handler.should_stop() == False

    # Simulate signal
    handler._signal_handler(2, None)  # SIGINT

    # Should now be stopped
    assert handler.should_stop() == True


def test_ist_timezone_functions():
    """Test IST timezone helper functions"""
    from trading_utils import get_ist_now, format_ist_timestamp
    import pytz

    # get_ist_now should return timezone-aware datetime
    now = get_ist_now()
    assert now.tzinfo is not None
    # Check timezone name instead of object equality
    assert str(now.tzinfo) == 'Asia/Kolkata' or 'IST' in str(now.tzinfo)

    # format_ist_timestamp should format correctly
    formatted = format_ist_timestamp(now)
    assert isinstance(formatted, str)
    assert '+05:30' in formatted or '+0530' in formatted  # IST offset


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
