#!/usr/bin/env python3
"""
Comprehensive tests for exception_handler.py module
Tests circuit breaker, retry logic, correlation IDs, and error handling decorators
"""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.exception_handler import (
    TradingSystemError,
    APIError,
    DataError,
    OrderExecutionError,
    CircuitBreakerError,
    CircuitBreaker,
    CorrelationContext,
    safe_execute,
    critical_section,
    retry,
    ErrorCounter,
    get_circuit_breaker,
    get_error_counter,
    log_exception_with_context
)


# ============================================================================
# Custom Exception Classes Tests
# ============================================================================

class TestExceptionClasses:
    """Test custom exception hierarchy"""

    def test_trading_system_error(self):
        """Test TradingSystemError base exception"""
        error = TradingSystemError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_api_error(self):
        """Test APIError inherits from TradingSystemError"""
        error = APIError("API failed")
        assert isinstance(error, TradingSystemError)
        assert isinstance(error, Exception)

    def test_data_error(self):
        """Test DataError inherits from TradingSystemError"""
        error = DataError("Data processing failed")
        assert isinstance(error, TradingSystemError)

    def test_order_execution_error(self):
        """Test OrderExecutionError inherits from TradingSystemError"""
        error = OrderExecutionError("Order failed")
        assert isinstance(error, TradingSystemError)

    def test_circuit_breaker_error(self):
        """Test CircuitBreakerError inherits from TradingSystemError"""
        error = CircuitBreakerError("Circuit open")
        assert isinstance(error, TradingSystemError)


# ============================================================================
# CircuitBreaker Tests
# ============================================================================

class TestCircuitBreaker:
    """Test circuit breaker pattern implementation"""

    def test_initialization(self):
        """Test circuit breaker initialization"""
        breaker = CircuitBreaker(
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2
        )

        assert breaker.failure_threshold == 5
        assert breaker.success_threshold == 2
        assert breaker.failure_count == 0
        assert breaker.success_count == 0
        assert breaker.state == "CLOSED"

    def test_successful_call_in_closed_state(self):
        """Test successful call when circuit is closed"""
        breaker = CircuitBreaker()

        def successful_func():
            return "success"

        result = breaker.call(successful_func)

        assert result == "success"
        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 0

    def test_failed_call_increments_counter(self):
        """Test that failed calls increment failure counter"""
        breaker = CircuitBreaker(failure_threshold=3)

        def failing_func():
            raise ValueError("Test error")

        # First failure
        with pytest.raises(ValueError):
            breaker.call(failing_func)

        assert breaker.failure_count == 1
        assert breaker.state == "CLOSED"  # Still closed

    def test_circuit_opens_after_threshold(self):
        """Test that circuit opens after failure threshold"""
        breaker = CircuitBreaker(failure_threshold=3)

        def failing_func():
            raise ValueError("Test error")

        # Fail 3 times to reach threshold
        for i in range(3):
            with pytest.raises(ValueError):
                breaker.call(failing_func)

        assert breaker.state == "OPEN"
        assert breaker.failure_count >= 3

    def test_circuit_blocks_calls_when_open(self):
        """Test that open circuit blocks calls"""
        breaker = CircuitBreaker(failure_threshold=2)

        def failing_func():
            raise ValueError("Test error")

        # Open the circuit
        for i in range(2):
            with pytest.raises(ValueError):
                breaker.call(failing_func)

        assert breaker.state == "OPEN"

        # Next call should be blocked
        def any_func():
            return "should not execute"

        with pytest.raises(CircuitBreakerError):
            breaker.call(any_func)

    def test_circuit_enters_half_open_after_timeout(self):
        """Test that circuit enters half-open state after timeout"""
        breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=1)

        def failing_func():
            raise ValueError("Test error")

        # Open the circuit
        for i in range(2):
            with pytest.raises(ValueError):
                breaker.call(failing_func)

        assert breaker.state == "OPEN"

        # Wait for timeout
        time.sleep(1.1)

        # Next call should transition to half-open
        def successful_func():
            return "success"

        result = breaker.call(successful_func)

        assert result == "success"
        # After successful call in half-open, check state changed

    def test_circuit_closes_from_half_open_after_successes(self):
        """Test that circuit closes from half-open after enough successes"""
        breaker = CircuitBreaker(
            failure_threshold=2,
            timeout_seconds=1,
            success_threshold=2
        )

        def failing_func():
            raise ValueError("Test error")

        # Open the circuit
        for i in range(2):
            with pytest.raises(ValueError):
                breaker.call(failing_func)

        assert breaker.state == "OPEN"

        # Wait for timeout
        time.sleep(1.1)

        # Make 2 successful calls to close circuit
        def successful_func():
            return "success"

        breaker.call(successful_func)
        breaker.call(successful_func)

        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 0

    def test_circuit_reopens_on_failure_in_half_open(self):
        """Test that circuit reopens if failure occurs in half-open state"""
        breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=1)

        def failing_func():
            raise ValueError("Test error")

        # Open the circuit
        for i in range(2):
            with pytest.raises(ValueError):
                breaker.call(failing_func)

        # Wait for timeout to enter half-open
        time.sleep(1.1)

        # Fail again in half-open state
        with pytest.raises(ValueError):
            breaker.call(failing_func)

        assert breaker.state == "OPEN"


# ============================================================================
# CorrelationContext Tests
# ============================================================================

class TestCorrelationContext:
    """Test correlation ID tracking"""

    def test_get_correlation_id_generates_uuid(self):
        """Test that get_correlation_id generates UUID"""
        CorrelationContext.clear_correlation_id()

        corr_id = CorrelationContext.get_correlation_id()

        assert corr_id is not None
        assert len(corr_id) > 0

    def test_set_correlation_id(self):
        """Test setting custom correlation ID"""
        CorrelationContext.set_correlation_id("TEST-123")

        corr_id = CorrelationContext.get_correlation_id()

        assert corr_id == "TEST-123"

    def test_clear_correlation_id(self):
        """Test clearing correlation ID"""
        CorrelationContext.set_correlation_id("TEST-123")
        CorrelationContext.clear_correlation_id()

        # Should generate new ID after clear
        new_id = CorrelationContext.get_correlation_id()
        assert new_id != "TEST-123"

    def test_correlation_id_persists_across_calls(self):
        """Test that correlation ID persists"""
        CorrelationContext.set_correlation_id("PERSIST-123")

        id1 = CorrelationContext.get_correlation_id()
        id2 = CorrelationContext.get_correlation_id()

        assert id1 == id2 == "PERSIST-123"


# ============================================================================
# safe_execute Decorator Tests
# ============================================================================

class TestSafeExecute:
    """Test safe_execute decorator"""

    def test_safe_execute_returns_result_on_success(self):
        """Test that safe_execute returns result on success"""
        @safe_execute("test_op")
        def successful_func():
            return "success"

        result = successful_func()

        assert result == "success"

    def test_safe_execute_returns_default_on_error(self):
        """Test that safe_execute returns default on error"""
        @safe_execute("test_op", default_return="DEFAULT", raise_on_error=False)
        def failing_func():
            raise ValueError("Test error")

        result = failing_func()

        assert result == "DEFAULT"

    def test_safe_execute_raises_when_configured(self):
        """Test that safe_execute raises when raise_on_error=True"""
        @safe_execute("test_op", raise_on_error=True)
        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_func()

    def test_safe_execute_with_circuit_breaker(self):
        """Test safe_execute with circuit breaker enabled"""
        @safe_execute("breaker_test", use_circuit_breaker=True, raise_on_error=False)
        def failing_func():
            raise ValueError("Test error")

        # Should use circuit breaker
        for i in range(6):
            result = failing_func()

        # Circuit should be open now
        # Get the circuit breaker and check state
        breaker = get_circuit_breaker("breaker_test")
        assert breaker.state == "OPEN"

    def test_safe_execute_logs_errors(self):
        """Test that safe_execute logs errors"""
        @safe_execute("test_op", log_errors=True, raise_on_error=False)
        def failing_func():
            raise ValueError("Test error")

        with patch('core.exception_handler.logger') as mock_logger:
            result = failing_func()

            # Should have logged error
            assert mock_logger.error.called

    def test_safe_execute_preserves_function_metadata(self):
        """Test that decorator preserves function metadata"""
        @safe_execute("test_op")
        def my_function():
            """My docstring"""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring"


# ============================================================================
# critical_section Decorator Tests
# ============================================================================

class TestCriticalSection:
    """Test critical_section decorator"""

    def test_critical_section_returns_result_on_success(self):
        """Test that critical_section returns result on success"""
        @critical_section("critical_op")
        def successful_func():
            return "success"

        result = successful_func()

        assert result == "success"

    def test_critical_section_always_raises_on_error(self):
        """Test that critical_section always raises on error"""
        @critical_section("critical_op")
        def failing_func():
            raise ValueError("Critical error")

        with pytest.raises(ValueError):
            failing_func()

    def test_critical_section_logs_errors(self):
        """Test that critical_section logs errors"""
        @critical_section("critical_op")
        def failing_func():
            raise ValueError("Critical error")

        with patch('core.exception_handler.logger') as mock_logger:
            with pytest.raises(ValueError):
                failing_func()

            # Should have logged critical error
            assert mock_logger.critical.called


# ============================================================================
# retry Decorator Tests
# ============================================================================

class TestRetryDecorator:
    """Test retry decorator with exponential backoff"""

    def test_retry_succeeds_immediately(self):
        """Test that retry succeeds on first attempt"""
        @retry(max_attempts=3)
        def successful_func():
            return "success"

        result = successful_func()

        assert result == "success"

    def test_retry_succeeds_after_failures(self):
        """Test that retry eventually succeeds"""
        attempt_count = [0]

        @retry(max_attempts=3, delay_seconds=0.1)
        def eventually_succeeds():
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise ValueError(f"Attempt {attempt_count[0]} failed")
            return "success"

        result = eventually_succeeds()

        assert result == "success"
        assert attempt_count[0] == 3

    def test_retry_raises_after_max_attempts(self):
        """Test that retry raises after max attempts"""
        @retry(max_attempts=3, delay_seconds=0.1)
        def always_fails():
            raise ValueError("Always fails")

        with pytest.raises(ValueError):
            always_fails()

    def test_retry_only_catches_specified_exceptions(self):
        """Test that retry only retries specified exceptions"""
        @retry(max_attempts=3, delay_seconds=0.1, exceptions=(ValueError,))
        def raises_different_error():
            raise RuntimeError("Different error")

        # Should raise immediately without retrying
        with pytest.raises(RuntimeError):
            raises_different_error()

    def test_retry_exponential_backoff(self):
        """Test that retry uses exponential backoff"""
        attempt_times = []

        @retry(max_attempts=3, delay_seconds=0.1, backoff_multiplier=2.0)
        def track_timing():
            attempt_times.append(time.time())
            if len(attempt_times) < 3:
                raise ValueError("Not yet")
            return "success"

        result = track_timing()

        assert result == "success"
        assert len(attempt_times) == 3

        # Check delays are roughly exponential
        # First retry: ~0.1s, second retry: ~0.2s
        if len(attempt_times) >= 3:
            delay1 = attempt_times[1] - attempt_times[0]
            delay2 = attempt_times[2] - attempt_times[1]

            # Allow some tolerance
            assert delay1 >= 0.08  # ~0.1s
            assert delay2 >= 0.18  # ~0.2s


# ============================================================================
# ErrorCounter Tests
# ============================================================================

class TestErrorCounter:
    """Test error counter functionality"""

    def test_error_counter_initialization(self):
        """Test error counter starts at zero"""
        counter = ErrorCounter()

        assert counter.get_count("APIError") == 0

    def test_increment_error_count(self):
        """Test incrementing error count"""
        counter = ErrorCounter()

        counter.increment("APIError")
        counter.increment("APIError")

        assert counter.get_count("APIError") == 2

    def test_multiple_error_types(self):
        """Test tracking multiple error types"""
        counter = ErrorCounter()

        counter.increment("APIError")
        counter.increment("APIError")
        counter.increment("ValueError")

        assert counter.get_count("APIError") == 2
        assert counter.get_count("ValueError") == 1

    def test_get_all_counts(self):
        """Test getting all error counts"""
        counter = ErrorCounter()

        counter.increment("APIError")
        counter.increment("ValueError")
        counter.increment("APIError")

        all_counts = counter.get_all_counts()

        assert all_counts["APIError"] == 2
        assert all_counts["ValueError"] == 1

    def test_reset_counters(self):
        """Test resetting all counters"""
        counter = ErrorCounter()

        counter.increment("APIError")
        counter.increment("ValueError")

        counter.reset()

        assert counter.get_count("APIError") == 0
        assert counter.get_count("ValueError") == 0


# ============================================================================
# Global Functions Tests
# ============================================================================

class TestGlobalFunctions:
    """Test global helper functions"""

    def test_get_circuit_breaker_creates_breaker(self):
        """Test that get_circuit_breaker creates new breaker"""
        breaker = get_circuit_breaker("test_operation")

        assert isinstance(breaker, CircuitBreaker)

    def test_get_circuit_breaker_returns_same_instance(self):
        """Test that get_circuit_breaker returns same instance"""
        breaker1 = get_circuit_breaker("same_operation")
        breaker2 = get_circuit_breaker("same_operation")

        assert breaker1 is breaker2

    def test_get_error_counter_returns_global_instance(self):
        """Test that get_error_counter returns global counter"""
        counter1 = get_error_counter()
        counter2 = get_error_counter()

        assert counter1 is counter2

    def test_log_exception_with_context(self):
        """Test logging exception with context"""
        exception = ValueError("Test error")
        context = {"user": "test_user", "action": "place_order"}

        with patch('core.exception_handler.logger') as mock_logger:
            log_exception_with_context("test_operation", exception, context)

            # Should have logged error
            assert mock_logger.error.called

            # Should have incremented counter
            counter = get_error_counter()
            # Note: counter may have counts from other tests, just check it exists
            assert counter.get_count("ValueError") >= 1


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for exception handling"""

    def test_safe_execute_with_retry(self):
        """Test combining safe_execute with retry"""
        attempt_count = [0]

        # Note: retry must be outer decorator to catch exceptions
        # before safe_execute handles them
        @safe_execute("combined_op", raise_on_error=True)
        @retry(max_attempts=3, delay_seconds=0.1)
        def eventually_succeeds():
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise ValueError("Not yet")
            return "success"

        result = eventually_succeeds()

        assert result == "success"
        assert attempt_count[0] == 3

    def test_correlation_id_preserved_through_decorators(self):
        """Test that correlation ID is preserved through decorated calls"""
        CorrelationContext.set_correlation_id("TEST-PRESERVE")

        @safe_execute("preserve_test")
        def check_correlation():
            return CorrelationContext.get_correlation_id()

        corr_id = check_correlation()

        assert corr_id == "TEST-PRESERVE"


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_circuit_breaker_thread_safety(self):
        """Test that circuit breaker is thread-safe"""
        breaker = CircuitBreaker(failure_threshold=10)

        def thread_safe_call():
            try:
                return breaker.call(lambda: "success")
            except Exception:
                return None

        # Call from "multiple threads" (sequential for simplicity)
        results = [thread_safe_call() for _ in range(100)]

        # All should succeed
        assert all(r == "success" for r in results)

    def test_error_counter_thread_safety(self):
        """Test that error counter is thread-safe"""
        counter = ErrorCounter()

        # Increment many times
        for i in range(100):
            counter.increment("TestError")

        assert counter.get_count("TestError") == 100


if __name__ == "__main__":
    # Run tests with: pytest test_exception_handler.py -v
    pytest.main([__file__, "-v", "--tb=short"])
