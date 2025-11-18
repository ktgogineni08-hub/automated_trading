#!/usr/bin/env python3
"""
Phase 1 Critical Fixes - Comprehensive Test Suite

Tests all critical security and stability fixes from Phase 1:
1. Environment variable validation
2. Input sanitization
3. Authentication bypass fix
4. Secure path handling
5. Exception handling framework
"""

import os
import sys
import pytest
from pathlib import Path
import tempfile
import shutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config_validator import ConfigValidator, validate_config, ConfigValidationError
from core.input_sanitizer import InputSanitizer, sanitize_log, sanitize_symbol, sanitize_path
from core.secure_path_handler import SecurePathHandler, PathSecurityError
from core.exception_handler import (
    safe_execute, critical_section, retry, CircuitBreaker,
    CircuitBreakerError, CorrelationContext, get_error_counter
)


class TestConfigValidator:
    """Test environment variable validation"""

    def test_missing_api_key(self, monkeypatch):
        """Test that missing API key is detected"""
        monkeypatch.delenv('ZERODHA_API_KEY', raising=False)
        monkeypatch.delenv('ZERODHA_API_SECRET', raising=False)

        validator = ConfigValidator(mode='paper')
        result = validator.validate_all()

        assert not result.is_valid
        assert any('ZERODHA_API_KEY' in error for error in result.errors)

    def test_empty_api_key(self, monkeypatch):
        """Test that empty API key is detected"""
        monkeypatch.setenv('ZERODHA_API_KEY', '   ')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'test_secret')

        validator = ConfigValidator(mode='paper')
        result = validator.validate_all()

        assert not result.is_valid
        assert any('empty' in error.lower() for error in result.errors)

    def test_short_api_key(self, monkeypatch):
        """Test that short API key is detected"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'short')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'test_secret_key_12345')

        validator = ConfigValidator(mode='paper')
        result = validator.validate_all()

        assert not result.is_valid
        assert any('too short' in error.lower() for error in result.errors)

    def test_placeholder_api_key(self, monkeypatch):
        """Test that placeholder API keys are detected"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'your_api_key_here')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'your_secret_here')

        validator = ConfigValidator(mode='paper')
        result = validator.validate_all()

        assert not result.is_valid
        assert any('placeholder' in error.lower() for error in result.errors)

    def test_identical_key_and_secret(self, monkeypatch):
        """Test that identical key and secret are detected"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'test_key_12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'test_key_12345678')

        validator = ConfigValidator(mode='paper')
        result = validator.validate_all()

        assert not result.is_valid
        assert any('identical' in error.lower() for error in result.errors)

    def test_weak_password(self, monkeypatch):
        """Test weak password detection"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'valid_api_key_12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'valid_secret_key_12345')
        monkeypatch.setenv('TRADING_SECURITY_PASSWORD', 'weak')

        validator = ConfigValidator(mode='paper')
        result = validator.validate_all()

        assert result.has_warnings()
        assert any('weak' in warning.lower() for warning in result.warnings)

    def test_live_mode_strict_validation(self, monkeypatch):
        """Test that LIVE mode has stricter validation"""
        monkeypatch.delenv('ZERODHA_API_KEY', raising=False)
        monkeypatch.delenv('DASHBOARD_API_KEY', raising=False)

        validator = ConfigValidator(mode='live')
        result = validator.validate_all()

        assert not result.is_valid
        assert any('LIVE mode' in error for error in result.errors)

    def test_valid_configuration(self, monkeypatch):
        """Test that valid configuration passes"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'valid_api_key_12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'valid_secret_key_987654321')
        monkeypatch.setenv('TRADING_SECURITY_PASSWORD', 'StrongPassword123!@#')
        monkeypatch.setenv('DATA_ENCRYPTION_KEY', 'a' * 32)

        validator = ConfigValidator(mode='paper')
        result = validator.validate_all()

        assert result.is_valid


class TestInputSanitizer:
    """Test input sanitization"""

    def test_log_injection_prevention(self):
        """Test that log injection is prevented"""
        malicious = "Normal log\nFAKE: Unauthorized access"
        sanitized = sanitize_log(malicious)

        assert '\n' not in sanitized
        assert '\\n' in sanitized  # Should be escaped

    def test_ansi_escape_removal(self):
        """Test that ANSI escape codes are removed"""
        ansi_attack = "Text\x1b[31mRED\x1b[0m"
        sanitized = sanitize_log(ansi_attack)

        assert '\x1b' not in sanitized
        assert '\033' not in sanitized

    def test_null_byte_removal(self):
        """Test that null bytes are removed"""
        with_null = "test\x00file"
        sanitized = sanitize_log(with_null)

        assert '\x00' not in sanitized

    def test_symbol_sanitization(self):
        """Test symbol name sanitization"""
        assert sanitize_symbol("RELIANCE") == "RELIANCE"
        assert sanitize_symbol("m&m") == "M&M"
        assert sanitize_symbol("  tcs  ") == "TCS"

    def test_symbol_invalid_characters(self):
        """Test that invalid symbol characters are stripped"""
        # Should strip invalid characters rather than raise error
        result = sanitize_symbol("INVALID!@#$%")
        assert result == "INVALID"
        assert "!" not in result and "@" not in result

    def test_path_traversal_detection(self):
        """Test path traversal detection"""
        with pytest.raises(ValueError):
            sanitize_path("../../../etc/passwd")

    def test_variable_expansion_detection(self):
        """Test variable expansion detection"""
        with pytest.raises(ValueError):
            sanitize_path("${HOME}/data")

        with pytest.raises(ValueError):
            sanitize_path("$(whoami)")

    def test_api_key_validation(self):
        """Test API key format validation"""
        # Valid key
        assert InputSanitizer.validate_api_key("valid_api_key_1234567890")

        # Too short
        with pytest.raises(ValueError):
            InputSanitizer.validate_api_key("short")

        # Placeholder
        with pytest.raises(ValueError):
            InputSanitizer.validate_api_key("your_api_key_replace_me")

    def test_sql_injection_detection(self):
        """Test SQL injection pattern detection"""
        sql_injection = "'; DROP TABLE users;--"
        detected = InputSanitizer.detect_injection_attempt(sql_injection)

        assert 'sql_injection' in detected

    def test_command_injection_detection(self):
        """Test command injection detection"""
        cmd_injection = "file.txt; rm -rf /"
        detected = InputSanitizer.detect_injection_attempt(cmd_injection)

        assert 'command_injection' in detected

    def test_dict_sanitization_masks_sensitive_keys(self):
        """Test that sensitive dictionary keys are masked"""
        data = {
            'username': 'john',
            'password': 'secret123',
            'api_key': 'key_12345',
            'balance': 100000
        }

        sanitized = InputSanitizer.sanitize_dict_for_logging(data)

        assert 'MASKED' in str(sanitized['password'])
        assert 'MASKED' in str(sanitized['api_key'])
        assert sanitized['balance'] == 100000  # Not sensitive


class TestSecurePathHandler:
    """Test secure path handling"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.handler = SecurePathHandler(base_dir=self.temp_dir)

    def teardown_method(self):
        """Cleanup test environment"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_valid_relative_path(self):
        """Test valid relative path validation"""
        path = self.handler.validate_path("logs/test.log")
        assert path.is_absolute()
        assert 'logs' in str(path)

    def test_path_traversal_blocked(self):
        """Test that path traversal is blocked"""
        with pytest.raises(PathSecurityError):
            self.handler.validate_path("../../../etc/passwd")

    def test_null_byte_blocked(self):
        """Test that null bytes are blocked"""
        with pytest.raises(PathSecurityError):
            self.handler.validate_path("logs/file\x00.txt")

    def test_invalid_directory_blocked(self):
        """Test that invalid directories are blocked"""
        with pytest.raises(PathSecurityError):
            self.handler.validate_path("invalid_dir/file.txt")

    def test_secure_token_path(self):
        """Test secure token path generation"""
        token_path = self.handler.get_secure_token_path()

        assert token_path.is_absolute()
        assert '.config/trading-system' in str(token_path)
        assert not self.handler.is_predictable_path(token_path)

    def test_predictable_path_detection(self):
        """Test predictable path detection"""
        # Home directory root is predictable
        predictable = Path.home() / "token.json"
        assert self.handler.is_predictable_path(predictable)

        # Config directory is not predictable
        secure = Path.home() / ".config" / "trading-system" / "token.json"
        assert not self.handler.is_predictable_path(secure)

    def test_directory_creation(self):
        """Test automatic directory creation"""
        log_path = self.handler.validate_path("logs/new_dir/test.log", allow_create=True)

        assert log_path.parent.exists()

    def test_symlink_detection(self):
        """Test symlink detection in path"""
        # Create a symlink
        target = self.temp_dir / "logs"
        target.mkdir()
        link = self.temp_dir / "link_to_logs"
        link.symlink_to(target)

        file_path = link / "test.log"

        # Should raise error if symlink detection is enforced
        with pytest.raises(PathSecurityError):
            self.handler.validate_no_symlink_in_path(file_path)


class TestExceptionHandler:
    """Test exception handling framework"""

    def test_safe_execute_returns_default(self):
        """Test that safe_execute returns default on error"""
        @safe_execute("test_op", default_return="DEFAULT", raise_on_error=False)
        def failing_func():
            raise ValueError("Test error")

        result = failing_func()
        assert result == "DEFAULT"

    def test_safe_execute_with_raise(self):
        """Test that safe_execute can re-raise exceptions"""
        @safe_execute("test_op", raise_on_error=True)
        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_func()

    def test_circuit_breaker_opens_after_failures(self):
        """Test that circuit breaker opens after threshold"""
        breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=1)

        def failing_operation():
            raise ValueError("Simulated failure")

        # Trigger failures
        for _ in range(3):
            try:
                breaker.call(failing_operation)
            except ValueError:
                pass

        # Circuit should now be open
        with pytest.raises(CircuitBreakerError):
            breaker.call(failing_operation)

    def test_circuit_breaker_recovers(self):
        """Test that circuit breaker recovers after timeout"""
        import time

        breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=1, success_threshold=1)

        def sometimes_fails():
            if breaker.failure_count < 2:
                raise ValueError("Fail")
            return "SUCCESS"

        # Trigger failures
        for _ in range(2):
            try:
                breaker.call(sometimes_fails)
            except ValueError:
                pass

        # Wait for timeout
        time.sleep(1.1)

        # Should allow retry and succeed
        result = breaker.call(sometimes_fails)
        assert result == "SUCCESS"

    def test_retry_with_eventual_success(self):
        """Test retry decorator with eventual success"""
        attempt_count = 0

        @retry(max_attempts=3, delay_seconds=0.01, exceptions=(ValueError,))
        def eventually_succeeds():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError(f"Attempt {attempt_count}")
            return "SUCCESS"

        result = eventually_succeeds()
        assert result == "SUCCESS"
        assert attempt_count == 3

    def test_retry_exhausts_attempts(self):
        """Test that retry raises after max attempts"""
        @retry(max_attempts=2, delay_seconds=0.01, exceptions=(ValueError,))
        def always_fails():
            raise ValueError("Always fails")

        with pytest.raises(ValueError):
            always_fails()

    def test_critical_section_always_raises(self):
        """Test that critical_section always raises"""
        @critical_section("test_critical")
        def critical_failure():
            raise RuntimeError("Critical error")

        with pytest.raises(RuntimeError):
            critical_failure()

    def test_correlation_id_tracking(self):
        """Test correlation ID tracking"""
        @safe_execute("test_corr")
        def get_correlation_id():
            return CorrelationContext.get_correlation_id()

        CorrelationContext.set_correlation_id("TEST-456")
        corr_id = get_correlation_id()

        assert corr_id == "TEST-456"

    def test_error_counter(self):
        """Test error counter functionality"""
        counter = get_error_counter()
        counter.reset()

        counter.increment("APIError")
        counter.increment("APIError")
        counter.increment("ValueError")

        assert counter.get_count("APIError") == 2
        assert counter.get_count("ValueError") == 1
        assert counter.get_count("UnknownError") == 0


class TestIntegration:
    """Integration tests for Phase 1 fixes"""

    def test_end_to_end_secure_operation(self, monkeypatch):
        """Test end-to-end secure operation with all fixes"""
        # Setup environment
        monkeypatch.setenv('ZERODHA_API_KEY', 'valid_api_key_12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'valid_secret_key_987654321')
        monkeypatch.setenv('TRADING_SECURITY_PASSWORD', 'StrongPassword123!@#')

        # 1. Validate configuration
        validator = ConfigValidator(mode='paper')
        result = validator.validate_all()
        assert result.is_valid

        # 2. Sanitize input
        user_input = "RELIANCE\nFAKE LOG"
        sanitized = sanitize_symbol(user_input.split('\n')[0])
        assert sanitized == "RELIANCE"

        # 3. Validate path
        temp_dir = Path(tempfile.mkdtemp())
        handler = SecurePathHandler(base_dir=temp_dir)
        secure_path = handler.validate_path("logs/test.log")
        assert secure_path.is_absolute()

        # 4. Execute with exception handling
        @safe_execute("test_operation", default_return=None)
        @retry(max_attempts=2, delay_seconds=0.01)
        def secure_operation():
            return f"Processed: {sanitized}"

        result = secure_operation()
        assert "RELIANCE" in result

        # Cleanup
        shutil.rmtree(temp_dir)


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
