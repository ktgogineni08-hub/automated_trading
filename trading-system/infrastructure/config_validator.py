#!/usr/bin/env python3
"""
Configuration Validator
Validates all configuration requirements at startup before trading begins
"""

import os
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger('trading_system.config_validator')


@dataclass
class ValidationResult:
    """Result of a configuration validation check"""
    is_valid: bool
    category: str
    name: str
    message: str
    severity: str  # 'error', 'warning', 'info'


class ConfigurationValidator:
    """
    Validates system configuration before trading starts

    Checks:
    - Required environment variables
    - File permissions
    - Directory structure
    - API credentials
    - Security settings
    - Database configuration
    """

    def __init__(self, trading_mode: str = 'paper'):
        """
        Initialize validator

        Args:
            trading_mode: Trading mode (paper, live, backtest)
        """
        self.trading_mode = trading_mode
        self.results: List[ValidationResult] = []

    def validate_all(self) -> Tuple[bool, List[ValidationResult]]:
        """
        Run all validation checks

        Returns:
            (is_valid, list of validation results)
        """
        self.results = []

        # Run all validation categories
        self._validate_environment_variables()
        self._validate_directories()
        self._validate_security_settings()
        self._validate_api_credentials()
        self._validate_database_config()
        self._validate_file_permissions()

        # Check if any errors exist
        has_errors = any(r.severity == 'error' for r in self.results)
        is_valid = not has_errors

        return is_valid, self.results

    def _validate_environment_variables(self):
        """Validate required environment variables"""
        # Required for all modes
        required_vars = {}

        # DASHBOARD_API_KEY is mandatory only for live trading to enforce authentication
        if self.trading_mode == 'live':
            required_vars['DASHBOARD_API_KEY'] = 'Dashboard authentication key'

        # Additional requirements for live trading
        # CRITICAL FIX: Use correct env var names (ZERODHA_*, not KITE_*)
        if self.trading_mode == 'live':
            required_vars.update({
                'ZERODHA_API_KEY': 'Zerodha API key',
                'ZERODHA_API_SECRET': 'Zerodha API secret'
            })

        for var, description in required_vars.items():
            value = os.environ.get(var)
            if not value:
                self.results.append(ValidationResult(
                    is_valid=False,
                    category='Environment',
                    name=var,
                    message=f'Missing required environment variable: {var} ({description})',
                    severity='error'
                ))
            else:
                # Validate value is not placeholder
                if value in ['your-key-here', 'placeholder', 'changeme', 'test']:
                    self.results.append(ValidationResult(
                        is_valid=False,
                        category='Environment',
                        name=var,
                        message=f'{var} appears to be a placeholder value: {value}',
                        severity='error'
                    ))
                else:
                    self.results.append(ValidationResult(
                        is_valid=True,
                        category='Environment',
                        name=var,
                        message=f'{var} is set',
                        severity='info'
                    ))

    def _validate_directories(self):
        """Validate required directories exist and are writable"""
        required_dirs = [
            'state',
            'logs',
            'data/cache',
            'trade_archives'
        ]

        for dir_path in required_dirs:
            path = Path(dir_path)

            # Check if directory exists
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    self.results.append(ValidationResult(
                        is_valid=True,
                        category='Directories',
                        name=str(path),
                        message=f'Created directory: {path}',
                        severity='info'
                    ))
                except Exception as e:
                    self.results.append(ValidationResult(
                        is_valid=False,
                        category='Directories',
                        name=str(path),
                        message=f'Cannot create directory {path}: {e}',
                        severity='error'
                    ))
            else:
                # Check if writable
                if not os.access(path, os.W_OK):
                    self.results.append(ValidationResult(
                        is_valid=False,
                        category='Directories',
                        name=str(path),
                        message=f'Directory not writable: {path}',
                        severity='error'
                    ))
                else:
                    self.results.append(ValidationResult(
                        is_valid=True,
                        category='Directories',
                        name=str(path),
                        message=f'Directory exists and writable: {path}',
                        severity='info'
                    ))

    def _validate_security_settings(self):
        """Validate security configuration"""
        # Check development mode
        dev_mode = os.getenv('FORCE_DEVELOPMENT_MODE', 'false').lower() == 'true'
        if dev_mode and self.trading_mode == 'live':
            self.results.append(ValidationResult(
                is_valid=False,
                category='Security',
                name='DEVELOPMENT_MODE',
                message='DEVELOPMENT_MODE enabled in LIVE trading - UNSAFE!',
                severity='error'
            ))
        elif dev_mode:
            self.results.append(ValidationResult(
                is_valid=True,
                category='Security',
                name='DEVELOPMENT_MODE',
                message='Development mode enabled (acceptable for paper/backtest)',
                severity='warning'
            ))

        # Check TLS verification
        tls_disabled = os.getenv('DASHBOARD_DISABLE_TLS_VERIFY', 'false').lower() == 'true'
        if tls_disabled and self.trading_mode == 'live':
            self.results.append(ValidationResult(
                is_valid=False,
                category='Security',
                name='TLS_VERIFICATION',
                message='TLS verification disabled in LIVE trading - UNSAFE!',
                severity='error'
            ))
        elif tls_disabled:
            self.results.append(ValidationResult(
                is_valid=True,
                category='Security',
                name='TLS_VERIFICATION',
                message='TLS verification disabled (only for local development)',
                severity='warning'
            ))

        # Check state encryption
        encryption_password = os.getenv('TRADING_SECURITY_PASSWORD')
        if not encryption_password:
            self.results.append(ValidationResult(
                is_valid=True,
                category='Security',
                name='STATE_ENCRYPTION',
                message='State encryption not configured (state will be plaintext)',
                severity='warning'
            ))
        else:
            if len(encryption_password) < 16:
                self.results.append(ValidationResult(
                    is_valid=False,
                    category='Security',
                    name='STATE_ENCRYPTION',
                    message='TRADING_SECURITY_PASSWORD is too short (min 16 characters)',
                    severity='error'
                ))

    def _validate_api_credentials(self):
        """Validate API credentials for live trading"""
        if self.trading_mode != 'live':
            self.results.append(ValidationResult(
                is_valid=True,
                category='API',
                name='Credentials',
                message=f'API credentials not required for {self.trading_mode} mode',
                severity='info'
            ))
            return

        # CRITICAL FIX: Check correct Zerodha credentials (not Kite)
        api_key = os.getenv('ZERODHA_API_KEY')
        api_secret = os.getenv('ZERODHA_API_SECRET')

        if api_key and len(api_key) < 10:
            self.results.append(ValidationResult(
                is_valid=False,
                category='API',
                name='ZERODHA_API_KEY',
                message='ZERODHA_API_KEY appears invalid (too short)',
                severity='error'
            ))

        if api_secret and len(api_secret) < 10:
            self.results.append(ValidationResult(
                is_valid=False,
                category='API',
                name='ZERODHA_API_SECRET',
                message='ZERODHA_API_SECRET appears invalid (too short)',
                severity='error'
            ))

    def _validate_database_config(self):
        """Validate database configuration"""
        # Check if database file location is writable
        db_path = Path('logs_database.db')
        db_dir = db_path.parent

        if not db_dir.exists():
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
                self.results.append(ValidationResult(
                    is_valid=True,
                    category='Database',
                    name='db_directory',
                    message=f'Created database directory: {db_dir}',
                    severity='info'
                ))
            except Exception as e:
                self.results.append(ValidationResult(
                    is_valid=False,
                    category='Database',
                    name='db_directory',
                    message=f'Cannot create database directory: {e}',
                    severity='error'
                ))
        elif not os.access(db_dir, os.W_OK):
            self.results.append(ValidationResult(
                is_valid=False,
                category='Database',
                name='db_directory',
                message=f'Database directory not writable: {db_dir}',
                severity='error'
            ))

    def _validate_file_permissions(self):
        """Validate file permissions for critical files"""
        critical_files = [
            'config.py',
            'enhanced_dashboard_server.py'
        ]

        for file_path in critical_files:
            path = Path(file_path)
            if path.exists():
                # Check if readable
                if not os.access(path, os.R_OK):
                    self.results.append(ValidationResult(
                        is_valid=False,
                        category='Permissions',
                        name=file_path,
                        message=f'Critical file not readable: {path}',
                        severity='error'
                    ))

    def print_report(self):
        """Print formatted validation report"""
        print("\n" + "=" * 80)
        print("CONFIGURATION VALIDATION REPORT")
        print("=" * 80)
        print(f"Trading Mode: {self.trading_mode.upper()}")
        print()

        # Group by category
        by_category: Dict[str, List[ValidationResult]] = {}
        for result in self.results:
            if result.category not in by_category:
                by_category[result.category] = []
            by_category[result.category].append(result)

        # Print each category
        for category, results in sorted(by_category.items()):
            print(f"\n{category}:")
            print("-" * 80)

            for result in results:
                if result.severity == 'error':
                    icon = "❌"
                elif result.severity == 'warning':
                    icon = "⚠️"
                else:
                    icon = "✅"

                print(f"  {icon} {result.name}: {result.message}")

        # Summary
        print("\n" + "=" * 80)
        errors = sum(1 for r in self.results if r.severity == 'error')
        warnings = sum(1 for r in self.results if r.severity == 'warning')
        info = sum(1 for r in self.results if r.severity == 'info')

        print(f"Summary: {errors} errors, {warnings} warnings, {info} passed")

        if errors > 0:
            print("❌ VALIDATION FAILED - Fix errors before proceeding")
        else:
            print("✅ VALIDATION PASSED - System ready to start")

        print("=" * 80 + "\n")

        return errors == 0


def validate_configuration(trading_mode: str = 'paper', print_report: bool = True) -> bool:
    """
    Convenience function to validate configuration

    Args:
        trading_mode: Trading mode (paper, live, backtest)
        print_report: Print validation report

    Returns:
        True if configuration is valid
    """
    validator = ConfigurationValidator(trading_mode=trading_mode)
    is_valid, results = validator.validate_all()

    if print_report:
        validator.print_report()

    return is_valid


if __name__ == "__main__":
    # Test validator
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else 'paper'

    print(f"Testing configuration validator for {mode} mode...\n")
    is_valid = validate_configuration(trading_mode=mode)

    sys.exit(0 if is_valid else 1)
