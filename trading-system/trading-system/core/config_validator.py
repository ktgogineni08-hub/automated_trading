#!/usr/bin/env python3
"""
Configuration Validation Framework
Addresses Critical Issue #4: Environment Variable Validation

CRITICAL FIXES:
- Validates all required environment variables are set and non-empty
- Prevents system from running with missing/empty credentials
- Validates encryption keys before use
- Provides detailed error messages for missing configuration
"""

import os
import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger('trading_system.config_validator')


class ConfigValidationError(Exception):
    """Raised when critical configuration validation fails"""
    pass


class SecurityConfigError(Exception):
    """Raised when security-related configuration is invalid"""
    pass


@dataclass
class ValidationResult:
    """Result of configuration validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    info: List[str]

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def print_report(self):
        """Print formatted validation report"""
        print("\n" + "="*70)
        print("🔍 CONFIGURATION VALIDATION REPORT")
        print("="*70)

        if self.errors:
            print("\n❌ CRITICAL ERRORS (Must fix before running):")
            for i, error in enumerate(self.errors, 1):
                print(f"   {i}. {error}")

        if self.warnings:
            print("\n⚠️  WARNINGS (Recommended to fix):")
            for i, warning in enumerate(self.warnings, 1):
                print(f"   {i}. {warning}")

        if self.info:
            print("\n💡 INFORMATION:")
            for i, info in enumerate(self.info, 1):
                print(f"   {i}. {info}")

        if self.is_valid and not self.warnings:
            print("\n✅ Configuration validation passed with no issues!")
        elif self.is_valid:
            print("\n✅ Configuration validation passed (with warnings)")
        else:
            print("\n❌ Configuration validation FAILED - fix errors above")

        print("="*70 + "\n")


class ConfigValidator:
    """
    Comprehensive configuration validator

    Validates:
    - Environment variables
    - API credentials
    - Encryption keys
    - File paths
    - Security settings
    """

    def __init__(self, mode: str = "paper"):
        """
        Initialize validator

        Args:
            mode: Trading mode (paper/live/backtest)
        """
        self.mode = mode.lower()
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def validate_all(self) -> ValidationResult:
        """
        Validate all configuration aspects

        Returns:
            ValidationResult with all findings
        """
        # Reset state
        self.errors = []
        self.warnings = []
        self.info = []

        # Run all validations
        self._validate_environment_variables()
        self._validate_api_credentials()
        self._validate_encryption_keys()
        self._validate_paths()
        self._validate_security_settings()
        self._validate_mode_specific_requirements()

        is_valid = len(self.errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=self.errors,
            warnings=self.warnings,
            info=self.info
        )

    def _validate_environment_variables(self):
        """Validate required environment variables"""
        logger.debug("Validating environment variables...")

        # Critical environment variables
        required_vars = {
            'ZERODHA_API_KEY': 'Zerodha API key for market data access',
            'ZERODHA_API_SECRET': 'Zerodha API secret for authentication',
        }

        # Optional but recommended
        recommended_vars = {
            'TRADING_SECURITY_PASSWORD': 'Master password for encrypting sensitive data',
            'DATA_ENCRYPTION_KEY': 'Key for encrypting trading state data',
            'LOG_LEVEL': 'Logging verbosity level',
        }

        # Check required variables
        for var_name, description in required_vars.items():
            value = os.getenv(var_name)

            if not value:
                self.errors.append(
                    f"Environment variable '{var_name}' is not set. "
                    f"Required for: {description}"
                )
            elif not value.strip():
                self.errors.append(
                    f"Environment variable '{var_name}' is empty. "
                    f"Required for: {description}"
                )
            elif len(value.strip()) < 8:
                self.errors.append(
                    f"Environment variable '{var_name}' is too short ({len(value)} chars). "
                    f"Expected at least 8 characters for security."
                )
            else:
                self.info.append(f"✓ {var_name} is set and valid")

        # Check recommended variables
        for var_name, description in recommended_vars.items():
            value = os.getenv(var_name)

            if not value or not value.strip():
                self.warnings.append(
                    f"Environment variable '{var_name}' is not set. "
                    f"Recommended for: {description}"
                )
            else:
                self.info.append(f"✓ {var_name} is set")

    def _validate_api_credentials(self):
        """Validate API credentials format and strength"""
        logger.debug("Validating API credentials...")

        api_key = os.getenv('ZERODHA_API_KEY', '').strip()
        api_secret = os.getenv('ZERODHA_API_SECRET', '').strip()

        # Validate API key format (Zerodha keys are alphanumeric, typically 32 chars)
        if api_key:
            if not re.match(r'^[a-zA-Z0-9]{15,}$', api_key):
                self.warnings.append(
                    "ZERODHA_API_KEY format looks unusual. "
                    "Expected: alphanumeric string, 15+ characters"
                )

        # Validate API secret format
        if api_secret:
            if not re.match(r'^[a-zA-Z0-9]{10,}$', api_secret):
                self.warnings.append(
                    "ZERODHA_API_SECRET format looks unusual. "
                    "Expected: alphanumeric string, 10+ characters"
                )

        # Check if credentials are suspiciously similar (potential copy-paste error)
        if api_key and api_secret and api_key == api_secret:
            self.errors.append(
                "ZERODHA_API_KEY and ZERODHA_API_SECRET are identical. "
                "This is likely a configuration error."
            )

        # Check for placeholder values
        placeholder_patterns = [
            'your_api_key', 'your_secret', 'replace_me',
            'xxx', 'test', 'example', 'placeholder'
        ]

        for pattern in placeholder_patterns:
            if pattern in api_key.lower():
                self.errors.append(
                    f"ZERODHA_API_KEY contains placeholder text '{pattern}'. "
                    "Replace with actual API key from Zerodha."
                )
            if pattern in api_secret.lower():
                self.errors.append(
                    f"ZERODHA_API_SECRET contains placeholder text '{pattern}'. "
                    "Replace with actual API secret from Zerodha."
                )

    def _validate_encryption_keys(self):
        """Validate encryption keys are set and secure"""
        logger.debug("Validating encryption keys...")

        # Check master password for state encryption
        master_password = os.getenv('TRADING_SECURITY_PASSWORD', '').strip()

        if not master_password:
            self.warnings.append(
                "TRADING_SECURITY_PASSWORD not set. "
                "Trading state will not be encrypted at rest."
            )
        elif len(master_password) < 16:
            self.warnings.append(
                f"TRADING_SECURITY_PASSWORD is weak ({len(master_password)} chars). "
                "Recommended: 16+ characters with mixed case, numbers, symbols."
            )
        else:
            # Check password strength
            has_upper = any(c.isupper() for c in master_password)
            has_lower = any(c.islower() for c in master_password)
            has_digit = any(c.isdigit() for c in master_password)
            has_special = any(not c.isalnum() for c in master_password)

            strength_issues = []
            if not has_upper:
                strength_issues.append("uppercase letters")
            if not has_lower:
                strength_issues.append("lowercase letters")
            if not has_digit:
                strength_issues.append("numbers")
            if not has_special:
                strength_issues.append("special characters")

            if strength_issues:
                self.warnings.append(
                    f"TRADING_SECURITY_PASSWORD is missing: {', '.join(strength_issues)}. "
                    "Use a stronger password for better security."
                )
            else:
                self.info.append("✓ TRADING_SECURITY_PASSWORD meets strength requirements")

        # Check data encryption key
        data_key = os.getenv('DATA_ENCRYPTION_KEY', '').strip()

        if not data_key:
            self.warnings.append(
                "DATA_ENCRYPTION_KEY not set. "
                "Sensitive data in logs/archives will not be encrypted."
            )
        elif len(data_key) < 32:
            self.errors.append(
                f"DATA_ENCRYPTION_KEY is too short ({len(data_key)} chars). "
                "Required: 32+ characters (256-bit key)"
            )
        else:
            self.info.append("✓ DATA_ENCRYPTION_KEY is set and sufficient length")

    def _validate_paths(self):
        """Validate file paths are secure and accessible"""
        logger.debug("Validating file paths...")

        # Token file path validation
        token_path_str = os.getenv(
            'ZERODHA_TOKEN_FILE',
            str(Path.home() / ".config" / "trading-system" / "zerodha_token.json")
        )

        try:
            token_path = Path(token_path_str).resolve()

            # Check for path traversal attempts
            if '..' in str(token_path):
                self.errors.append(
                    f"Token path contains '..' (path traversal): {token_path_str}"
                )

            # Ensure parent directory exists or can be created
            token_dir = token_path.parent
            if not token_dir.exists():
                try:
                    token_dir.mkdir(parents=True, exist_ok=True)
                    self.info.append(f"✓ Created token directory: {token_dir}")
                except PermissionError:
                    self.errors.append(
                        f"Cannot create token directory: {token_dir}. "
                        "Permission denied."
                    )

            # Check if path is predictable (security concern)
            if token_path == Path.home() / "zerodha_token.json":
                self.warnings.append(
                    "Token file is in home directory root. "
                    "Consider moving to ~/.config/trading-system/ for better security."
                )

            self.info.append(f"✓ Token path: {token_path}")

        except Exception as e:
            self.errors.append(f"Invalid token path '{token_path_str}': {e}")

        # Validate working directories
        critical_dirs = ['logs', 'state', 'data']

        for dir_name in critical_dirs:
            dir_path = Path(dir_name)

            if not dir_path.exists():
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    self.info.append(f"✓ Created directory: {dir_name}/")
                except PermissionError:
                    self.errors.append(
                        f"Cannot create directory '{dir_name}/'. "
                        "Check permissions."
                    )

    def _validate_security_settings(self):
        """Validate security-related settings"""
        logger.debug("Validating security settings...")

        # Dashboard API key validation
        dashboard_api_key = os.getenv('DASHBOARD_API_KEY', '').strip()

        if not dashboard_api_key:
            if self.mode == 'live':
                self.errors.append(
                    "DASHBOARD_API_KEY not set in LIVE mode. "
                    "Dashboard will accept unauthenticated requests - SECURITY RISK!"
                )
            else:
                self.warnings.append(
                    "DASHBOARD_API_KEY not set. "
                    "Dashboard will accept unauthenticated requests."
                )
        elif len(dashboard_api_key) < 32:
            self.warnings.append(
                f"DASHBOARD_API_KEY is weak ({len(dashboard_api_key)} chars). "
                "Recommended: 32+ character random string."
            )
        else:
            self.info.append("✓ DASHBOARD_API_KEY is set and strong")

        # Check if running in development mode
        dev_mode = os.getenv('DEVELOPMENT_MODE', 'false').lower()

        if dev_mode == 'true':
            if self.mode == 'live':
                self.errors.append(
                    "DEVELOPMENT_MODE=true in LIVE trading mode. "
                    "This disables critical security checks - NEVER use in production!"
                )
            else:
                self.warnings.append(
                    "DEVELOPMENT_MODE=true enables relaxed security. "
                    "Only use for local development/testing."
                )

    def _validate_mode_specific_requirements(self):
        """Validate requirements specific to trading mode"""
        logger.debug(f"Validating mode-specific requirements for: {self.mode}")

        if self.mode == 'live':
            # LIVE mode has stricter requirements
            self.info.append("⚠️  LIVE TRADING MODE - Enforcing strict validation")

            # Must have all credentials
            if not os.getenv('ZERODHA_API_KEY') or not os.getenv('ZERODHA_API_SECRET'):
                self.errors.append(
                    "LIVE mode requires valid ZERODHA_API_KEY and ZERODHA_API_SECRET"
                )

            # Must have security password
            if not os.getenv('TRADING_SECURITY_PASSWORD'):
                self.errors.append(
                    "LIVE mode requires TRADING_SECURITY_PASSWORD for state encryption"
                )

            # Must have dashboard authentication
            if not os.getenv('DASHBOARD_API_KEY'):
                self.errors.append(
                    "LIVE mode requires DASHBOARD_API_KEY for secure dashboard access"
                )

            # Warn about risk settings
            risk_per_trade = float(os.getenv('RISK_PER_TRADE_PCT', '0.015'))
            if risk_per_trade > 0.02:
                self.warnings.append(
                    f"RISK_PER_TRADE_PCT={risk_per_trade:.1%} is aggressive for LIVE trading. "
                    "Recommended: ≤2% (0.02)"
                )

        elif self.mode == 'paper':
            self.info.append("📄 PAPER TRADING MODE - Relaxed validation")

            # Paper trading can work with minimal config
            if not os.getenv('ZERODHA_API_KEY'):
                self.info.append(
                    "Paper trading without API key - will use simulated data"
                )

        elif self.mode == 'backtest':
            self.info.append("📊 BACKTEST MODE - Historical data only")

            # Backtest doesn't need live credentials
            self.info.append("API credentials not required for backtesting")


def validate_config(mode: str = "paper", verbose: bool = True) -> ValidationResult:
    """
    Validate configuration and return results

    Args:
        mode: Trading mode (paper/live/backtest)
        verbose: Print detailed report

    Returns:
        ValidationResult

    Raises:
        ConfigValidationError: If critical validation fails
    """
    validator = ConfigValidator(mode=mode)
    result = validator.validate_all()

    if verbose:
        result.print_report()

    return result


def validate_config_or_exit(mode: str = "paper"):
    """
    Validate configuration and exit if invalid

    Use this at application startup to ensure valid config

    Args:
        mode: Trading mode
    """
    result = validate_config(mode=mode, verbose=True)

    if not result.is_valid:
        print("\n❌ Configuration validation failed. Fix the errors above and try again.\n")
        raise ConfigValidationError(
            f"Configuration validation failed with {len(result.errors)} error(s)"
        )

    if result.has_warnings():
        print("\n⚠️  Configuration has warnings. Review them before proceeding.\n")
        response = input("Continue anyway? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Exiting...")
            raise ConfigValidationError("User chose not to continue with warnings")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Validate trading system configuration')
    parser.add_argument(
        '--mode',
        choices=['paper', 'live', 'backtest'],
        default='paper',
        help='Trading mode to validate for'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Exit with error if any warnings are found'
    )

    args = parser.parse_args()

    result = validate_config(mode=args.mode, verbose=True)

    if args.strict and result.has_warnings():
        print("\n❌ Strict mode: Exiting due to warnings")
        exit(1)

    if not result.is_valid:
        print("\n❌ Validation failed")
        exit(1)

    print("\n✅ Configuration validation successful")
    exit(0)
