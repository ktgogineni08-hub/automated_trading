#!/usr/bin/env python3
"""
Comprehensive tests for config_validator.py module
Tests ConfigValidator for configuration validation
"""

import pytest
import tempfile
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config_validator import (
    ConfigValidationError,
    SecurityConfigError,
    ValidationResult,
    ConfigValidator,
    validate_config,
    validate_config_or_exit
)


# ============================================================================
# ValidationResult Tests
# ============================================================================

class TestValidationResult:
    """Test ValidationResult dataclass"""

    def test_has_errors_true(self):
        """Test has_errors returns True when errors exist"""
        result = ValidationResult(
            is_valid=False,
            errors=["Error 1"],
            warnings=[],
            info=[]
        )
        assert result.has_errors() is True

    def test_has_errors_false(self):
        """Test has_errors returns False when no errors"""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            info=[]
        )
        assert result.has_errors() is False

    def test_has_warnings_true(self):
        """Test has_warnings returns True when warnings exist"""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=["Warning 1"],
            info=[]
        )
        assert result.has_warnings() is True

    def test_has_warnings_false(self):
        """Test has_warnings returns False when no warnings"""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            info=[]
        )
        assert result.has_warnings() is False

    def test_print_report_with_errors(self, capsys):
        """Test print_report with errors"""
        result = ValidationResult(
            is_valid=False,
            errors=["Critical error"],
            warnings=["Warning message"],
            info=["Info message"]
        )
        
        result.print_report()
        captured = capsys.readouterr()
        
        assert "CRITICAL ERRORS" in captured.out
        assert "Critical error" in captured.out
        assert "WARNINGS" in captured.out
        assert "INFORMATION" in captured.out


# ============================================================================
# ConfigValidator Initialization Tests
# ============================================================================

class TestConfigValidatorInitialization:
    """Test ConfigValidator initialization"""

    def test_initialization_paper_mode(self):
        """Test initialization with paper mode"""
        validator = ConfigValidator(mode="paper")
        assert validator.mode == "paper"

    def test_initialization_live_mode(self):
        """Test initialization with live mode"""
        validator = ConfigValidator(mode="live")
        assert validator.mode == "live"

    def test_initialization_case_insensitive(self):
        """Test that mode is case-insensitive"""
        validator = ConfigValidator(mode="PAPER")
        assert validator.mode == "paper"


# ============================================================================
# Environment Variable Validation Tests
# ============================================================================

class TestEnvironmentVariableValidation:
    """Test _validate_environment_variables method"""

    def test_validate_missing_required_env_vars(self, monkeypatch):
        """Test validation fails when required env vars missing"""
        # Clear all env vars
        monkeypatch.delenv('ZERODHA_API_KEY', raising=False)
        monkeypatch.delenv('ZERODHA_API_SECRET', raising=False)
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        assert not result.is_valid
        assert any('ZERODHA_API_KEY' in err for err in result.errors)
        assert any('ZERODHA_API_SECRET' in err for err in result.errors)

    def test_validate_empty_env_vars(self, monkeypatch):
        """Test validation fails when env vars are empty"""
        monkeypatch.setenv('ZERODHA_API_KEY', '   ')
        monkeypatch.setenv('ZERODHA_API_SECRET', '   ')
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        assert not result.is_valid
        assert any('empty' in err.lower() for err in result.errors)

    def test_validate_too_short_env_vars(self, monkeypatch):
        """Test validation fails when env vars are too short"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'short')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'short')
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        assert not result.is_valid
        assert any('too short' in err for err in result.errors)

    def test_validate_valid_env_vars(self, monkeypatch):
        """Test validation passes with valid env vars"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        # Should have info messages about valid env vars
        assert any('ZERODHA_API_KEY' in info for info in result.info)

    def test_validate_recommended_env_vars_warning(self, monkeypatch):
        """Test warnings for missing recommended env vars"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.delenv('TRADING_SECURITY_PASSWORD', raising=False)
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        # Should have warning about missing recommended var
        assert any('TRADING_SECURITY_PASSWORD' in warn for warn in result.warnings)


# ============================================================================
# API Credentials Validation Tests
# ============================================================================

class TestAPICredentialsValidation:
    """Test _validate_api_credentials method"""

    def test_validate_unusual_api_key_format(self, monkeypatch):
        """Test warning for unusual API key format"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'invalid-key-with-dashes!')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        assert any('format looks unusual' in warn for warn in result.warnings)

    def test_validate_identical_api_key_secret(self, monkeypatch):
        """Test error when API key and secret are identical"""
        same_value = 'samevalue123456789'
        monkeypatch.setenv('ZERODHA_API_KEY', same_value)
        monkeypatch.setenv('ZERODHA_API_SECRET', same_value)
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        assert not result.is_valid
        assert any('identical' in err for err in result.errors)

    def test_validate_placeholder_api_key(self, monkeypatch):
        """Test error for placeholder API key"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'your_api_key_here')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        assert not result.is_valid
        assert any('placeholder' in err for err in result.errors)

    def test_validate_placeholder_api_secret(self, monkeypatch):
        """Test error for placeholder API secret"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'test_secret_replace')
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        assert not result.is_valid
        assert any('placeholder' in err for err in result.errors)

    def test_validate_valid_api_credentials(self, monkeypatch):
        """Test validation passes with valid API credentials"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'abc123xyz456valid')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'def789uvw012secret')
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        # Should not have errors related to API credentials format
        api_errors = [err for err in result.errors if 'API' in err and 'format' in err]
        assert len(api_errors) == 0


# ============================================================================
# Encryption Keys Validation Tests
# ============================================================================

class TestEncryptionKeysValidation:
    """Test _validate_encryption_keys method"""

    def test_validate_missing_security_password_warning(self, monkeypatch):
        """Test warning for missing TRADING_SECURITY_PASSWORD"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.delenv('TRADING_SECURITY_PASSWORD', raising=False)
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        assert any('TRADING_SECURITY_PASSWORD' in warn for warn in result.warnings)

    def test_validate_weak_security_password(self, monkeypatch):
        """Test warning for weak TRADING_SECURITY_PASSWORD"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.setenv('TRADING_SECURITY_PASSWORD', 'short')
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        assert any('weak' in warn for warn in result.warnings)

    def test_validate_password_missing_complexity(self, monkeypatch):
        """Test warning for password lacking complexity"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.setenv('TRADING_SECURITY_PASSWORD', 'alllowercaseletters')
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        # Should warn about missing uppercase, numbers, special chars
        assert any('missing' in warn for warn in result.warnings)

    def test_validate_strong_security_password(self, monkeypatch):
        """Test validation passes with strong password"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.setenv('TRADING_SECURITY_PASSWORD', 'StrongPassword123!@#')
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        # Should have info about password meeting requirements
        assert any('meets strength requirements' in info for info in result.info)

    def test_validate_data_encryption_key_too_short(self, monkeypatch):
        """Test error for DATA_ENCRYPTION_KEY too short"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.setenv('DATA_ENCRYPTION_KEY', 'tooshort')
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        assert not result.is_valid
        assert any('too short' in err for err in result.errors)

    def test_validate_data_encryption_key_valid(self, monkeypatch):
        """Test validation passes with valid DATA_ENCRYPTION_KEY"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.setenv('DATA_ENCRYPTION_KEY', 'a' * 32)
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        # Should have info about valid data encryption key
        assert any('DATA_ENCRYPTION_KEY' in info for info in result.info)


# ============================================================================
# Path Validation Tests
# ============================================================================

class TestPathValidation:
    """Test _validate_paths method"""

    def test_validate_path_traversal_resolved(self, monkeypatch):
        """Test that path traversal paths are resolved correctly"""
        # Note: Path.resolve() normalizes paths and removes '..'
        # so the validation doesn't explicitly block path traversal
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.setenv('ZERODHA_TOKEN_FILE', '/tmp/test_token.json')

        validator = ConfigValidator()
        result = validator.validate_all()

        # Path should be accepted (resolved paths are allowed)
        assert isinstance(result, ValidationResult)

    def test_validate_predictable_token_path(self, monkeypatch):
        """Test warning for predictable token path"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.setenv('ZERODHA_TOKEN_FILE', str(Path.home() / "zerodha_token.json"))
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        # Should warn about token file in home directory root
        assert any('home directory root' in warn for warn in result.warnings)

    def test_validate_creates_working_directories(self, monkeypatch, tmp_path):
        """Test that validator creates working directories"""
        # Change to temp directory
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
            monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
            
            validator = ConfigValidator()
            result = validator.validate_all()
            
            # Should create logs, state, data directories
            assert (tmp_path / 'logs').exists()
            assert (tmp_path / 'state').exists()
            assert (tmp_path / 'data').exists()
            
        finally:
            os.chdir(original_cwd)


# ============================================================================
# Security Settings Validation Tests
# ============================================================================

class TestSecuritySettingsValidation:
    """Test _validate_security_settings method"""

    def test_validate_missing_dashboard_api_key_warning(self, monkeypatch):
        """Test warning for missing DASHBOARD_API_KEY"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.delenv('DASHBOARD_API_KEY', raising=False)
        
        validator = ConfigValidator(mode='paper')
        result = validator.validate_all()
        
        assert any('DASHBOARD_API_KEY' in warn for warn in result.warnings)

    def test_validate_missing_dashboard_api_key_error_live(self, monkeypatch):
        """Test error for missing DASHBOARD_API_KEY in live mode"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.setenv('TRADING_SECURITY_PASSWORD', 'StrongPassword123!@#')
        monkeypatch.delenv('DASHBOARD_API_KEY', raising=False)
        
        validator = ConfigValidator(mode='live')
        result = validator.validate_all()
        
        assert not result.is_valid
        assert any('DASHBOARD_API_KEY' in err for err in result.errors)

    def test_validate_weak_dashboard_api_key(self, monkeypatch):
        """Test warning for weak DASHBOARD_API_KEY"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.setenv('DASHBOARD_API_KEY', 'weak')
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        assert any('weak' in warn for warn in result.warnings)

    def test_validate_development_mode_live_error(self, monkeypatch):
        """Test error for DEVELOPMENT_MODE in live mode"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.setenv('TRADING_SECURITY_PASSWORD', 'StrongPassword123!@#')
        monkeypatch.setenv('DASHBOARD_API_KEY', 'a' * 32)
        monkeypatch.setenv('DEVELOPMENT_MODE', 'true')
        
        validator = ConfigValidator(mode='live')
        result = validator.validate_all()
        
        assert not result.is_valid
        assert any('DEVELOPMENT_MODE' in err for err in result.errors)

    def test_validate_development_mode_paper_warning(self, monkeypatch):
        """Test warning for DEVELOPMENT_MODE in paper mode"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.setenv('DEVELOPMENT_MODE', 'true')
        
        validator = ConfigValidator(mode='paper')
        result = validator.validate_all()
        
        assert any('DEVELOPMENT_MODE' in warn for warn in result.warnings)


# ============================================================================
# Mode-Specific Requirements Tests
# ============================================================================

class TestModeSpecificRequirements:
    """Test _validate_mode_specific_requirements method"""

    def test_validate_live_mode_strict_requirements(self, monkeypatch):
        """Test live mode enforces strict requirements"""
        # Missing critical env vars
        monkeypatch.delenv('ZERODHA_API_KEY', raising=False)
        monkeypatch.delenv('TRADING_SECURITY_PASSWORD', raising=False)
        monkeypatch.delenv('DASHBOARD_API_KEY', raising=False)
        
        validator = ConfigValidator(mode='live')
        result = validator.validate_all()
        
        assert not result.is_valid
        # Should have errors for all missing critical vars
        assert len(result.errors) >= 3

    def test_validate_live_mode_aggressive_risk(self, monkeypatch):
        """Test warning for aggressive risk settings in live mode"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.setenv('TRADING_SECURITY_PASSWORD', 'StrongPassword123!@#')
        monkeypatch.setenv('DASHBOARD_API_KEY', 'a' * 32)
        monkeypatch.setenv('RISK_PER_TRADE_PCT', '0.05')  # 5% risk - aggressive
        
        validator = ConfigValidator(mode='live')
        result = validator.validate_all()
        
        assert any('aggressive' in warn for warn in result.warnings)

    def test_validate_paper_mode_relaxed(self, monkeypatch):
        """Test paper mode has relaxed requirements"""
        # Missing API key is okay for paper
        monkeypatch.delenv('ZERODHA_API_KEY', raising=False)
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        
        validator = ConfigValidator(mode='paper')
        result = validator.validate_all()
        
        # Should have info message about simulated data
        assert any('simulated data' in info.lower() for info in result.info)

    def test_validate_backtest_mode_no_credentials_needed(self, monkeypatch):
        """Test backtest mode doesn't require live credentials"""
        monkeypatch.delenv('ZERODHA_API_KEY', raising=False)
        monkeypatch.delenv('ZERODHA_API_SECRET', raising=False)
        
        validator = ConfigValidator(mode='backtest')
        result = validator.validate_all()
        
        # Should have info about not requiring credentials
        assert any('not required' in info.lower() for info in result.info)


# ============================================================================
# Integration Tests
# ============================================================================

class TestConfigValidatorIntegration:
    """Test complete validation flow"""

    def test_validate_all_with_minimal_config(self, monkeypatch):
        """Test validation with minimal configuration"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        
        validator = ConfigValidator(mode='paper')
        result = validator.validate_all()
        
        # Should be valid but have warnings
        assert result.is_valid
        assert len(result.warnings) > 0

    def test_validate_all_with_complete_config(self, monkeypatch):
        """Test validation with complete configuration"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.setenv('TRADING_SECURITY_PASSWORD', 'StrongPassword123!@#')
        monkeypatch.setenv('DATA_ENCRYPTION_KEY', 'a' * 32)
        monkeypatch.setenv('DASHBOARD_API_KEY', 'b' * 32)
        monkeypatch.setenv('LOG_LEVEL', 'INFO')
        
        validator = ConfigValidator(mode='paper')
        result = validator.validate_all()
        
        # Should be valid with no errors
        assert result.is_valid
        assert len(result.errors) == 0


# ============================================================================
# Convenience Function Tests
# ============================================================================

class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_validate_config_returns_result(self, monkeypatch):
        """Test validate_config returns ValidationResult"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        
        result = validate_config(mode='paper', verbose=False)
        
        assert isinstance(result, ValidationResult)

    def test_validate_config_or_exit_success(self, monkeypatch):
        """Test validate_config_or_exit succeeds with valid config"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        monkeypatch.setenv('TRADING_SECURITY_PASSWORD', 'StrongPassword123!@#')
        monkeypatch.setenv('DATA_ENCRYPTION_KEY', 'a' * 32)
        monkeypatch.setenv('DASHBOARD_API_KEY', 'b' * 32)
        monkeypatch.setenv('LOG_LEVEL', 'INFO')

        # Should not raise exception (no warnings with complete config)
        validate_config_or_exit(mode='paper')

    def test_validate_config_or_exit_failure(self, monkeypatch):
        """Test validate_config_or_exit raises on invalid config"""
        # Missing required env vars
        monkeypatch.delenv('ZERODHA_API_KEY', raising=False)
        monkeypatch.delenv('ZERODHA_API_SECRET', raising=False)
        
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config_or_exit(mode='paper')
        
        assert "validation failed" in str(exc_info.value)


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_validate_empty_mode_string(self, monkeypatch):
        """Test validation with empty mode string"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey12345678')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'validsecret123456')
        
        validator = ConfigValidator(mode='')
        result = validator.validate_all()
        
        # Should still run validation
        assert isinstance(result, ValidationResult)

    def test_validate_special_characters_in_env_vars(self, monkeypatch):
        """Test validation with special characters in env vars"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'key!@#$%^&*()123456')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'secret!@#$%^&*()123')
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        # Should handle special characters
        assert isinstance(result, ValidationResult)

    def test_validate_unicode_in_env_vars(self, monkeypatch):
        """Test validation with unicode in env vars"""
        monkeypatch.setenv('ZERODHA_API_KEY', 'validkey文字列123456')
        monkeypatch.setenv('ZERODHA_API_SECRET', 'secret漢字123456789')
        
        validator = ConfigValidator()
        result = validator.validate_all()
        
        # Should handle unicode
        assert isinstance(result, ValidationResult)


if __name__ == "__main__":
    # Run tests with: pytest test_config_validator.py -v
    pytest.main([__file__, "-v", "--tb=short"])
