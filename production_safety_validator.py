#!/usr/bin/env python3
"""
Production Safety Validator
Ensures system is safe for production trading
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger('trading_system.safety_validator')


@dataclass
class SafetyCheck:
    """Safety check result"""
    name: str
    passed: bool
    severity: str  # 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    message: str
    fix_suggestion: Optional[str] = None


class ProductionSafetyValidator:
    """
    Validates system is safe for production

    Checks:
    - No synthetic data mode in live trading
    - API credentials configured
    - Required environment variables
    - File permissions
    - Configuration sanity
    """

    def __init__(self, config):
        """
        Initialize validator

        Args:
            config: Trading configuration object
        """
        self.config = config
        self.checks: List[SafetyCheck] = []

    def run_all_checks(self) -> Tuple[bool, List[SafetyCheck]]:
        """
        Run all safety checks

        Returns:
            (all_passed, list_of_checks)
        """
        self.checks = []

        # Run checks
        self._check_trading_mode()
        self._check_synthetic_data_mode()
        self._check_api_credentials()
        self._check_environment_variables()
        self._check_sensitive_files()
        self._check_configuration_sanity()
        self._check_directory_structure()
        self._check_market_hours_config()

        # Determine if all critical/high checks passed
        critical_failed = [c for c in self.checks if c.severity == 'CRITICAL' and not c.passed]
        high_failed = [c for c in self.checks if c.severity == 'HIGH' and not c.passed]

        all_passed = len(critical_failed) == 0 and len(high_failed) == 0

        return all_passed, self.checks

    def _check_trading_mode(self):
        """Check trading mode is valid"""
        try:
            mode = getattr(self.config, 'mode', None) or self.config.get('mode', 'paper')

            if mode not in ['paper', 'live', 'backtest']:
                self.checks.append(SafetyCheck(
                    name="Trading Mode",
                    passed=False,
                    severity='CRITICAL',
                    message=f"Invalid trading mode: {mode}",
                    fix_suggestion="Set mode to 'paper', 'live', or 'backtest' in config"
                ))
            else:
                self.checks.append(SafetyCheck(
                    name="Trading Mode",
                    passed=True,
                    severity='CRITICAL',
                    message=f"Trading mode: {mode}"
                ))

        except Exception as e:
            self.checks.append(SafetyCheck(
                name="Trading Mode",
                passed=False,
                severity='CRITICAL',
                message=f"Cannot determine trading mode: {e}",
                fix_suggestion="Ensure 'mode' is set in configuration"
            ))

    def _check_synthetic_data_mode(self):
        """Check if synthetic data mode is disabled in live trading"""
        try:
            mode = getattr(self.config, 'mode', None) or self.config.get('mode', 'paper')
            use_kite_trends = getattr(self.config, 'use_kite_trends', None)

            if use_kite_trends is None:
                use_kite_trends = self.config.get('use_kite_trends', True)

            if mode == 'live' and use_kite_trends is False:
                self.checks.append(SafetyCheck(
                    name="Synthetic Data Mode",
                    passed=False,
                    severity='CRITICAL',
                    message="CRITICAL: Synthetic data mode enabled in LIVE trading!",
                    fix_suggestion="Set 'use_kite_trends': true in config for live trading"
                ))
            else:
                self.checks.append(SafetyCheck(
                    name="Synthetic Data Mode",
                    passed=True,
                    severity='CRITICAL',
                    message=f"Synthetic data: {'disabled' if use_kite_trends else 'enabled (safe for paper trading)'}"
                ))

        except Exception as e:
            self.checks.append(SafetyCheck(
                name="Synthetic Data Mode",
                passed=False,
                severity='HIGH',
                message=f"Cannot check synthetic data mode: {e}"
            ))

    def _check_api_credentials(self):
        """Check API credentials are configured"""
        try:
            api_key = os.getenv('ZERODHA_API_KEY')
            api_secret = os.getenv('ZERODHA_API_SECRET')

            # Also check config
            if hasattr(self.config, 'get_api_credentials'):
                config_key, config_secret = self.config.get_api_credentials()
            else:
                config_key = self.config.get('api.zerodha.api_key')
                config_secret = self.config.get('api.zerodha.api_secret')

            has_env_creds = bool(api_key and api_secret)
            has_config_creds = bool(config_key and config_secret)

            if not (has_env_creds or has_config_creds):
                self.checks.append(SafetyCheck(
                    name="API Credentials",
                    passed=False,
                    severity='CRITICAL',
                    message="API credentials not found",
                    fix_suggestion="Set ZERODHA_API_KEY and ZERODHA_API_SECRET environment variables"
                ))
            else:
                source = "environment variables" if has_env_creds else "config file"
                self.checks.append(SafetyCheck(
                    name="API Credentials",
                    passed=True,
                    severity='CRITICAL',
                    message=f"API credentials found in {source}"
                ))

        except Exception as e:
            self.checks.append(SafetyCheck(
                name="API Credentials",
                passed=False,
                severity='CRITICAL',
                message=f"Error checking credentials: {e}"
            ))

    def _check_environment_variables(self):
        """Check required environment variables"""
        required_vars = []
        optional_vars = ['ZERODHA_TOKEN_KEY']  # For encryption

        missing_optional = [var for var in optional_vars if not os.getenv(var)]

        if missing_optional:
            self.checks.append(SafetyCheck(
                name="Environment Variables",
                passed=True,
                severity='MEDIUM',
                message=f"Optional env vars not set: {', '.join(missing_optional)}",
                fix_suggestion="Set ZERODHA_TOKEN_KEY for encrypted token caching"
            ))
        else:
            self.checks.append(SafetyCheck(
                name="Environment Variables",
                passed=True,
                severity='MEDIUM',
                message="All environment variables configured"
            ))

    def _check_sensitive_files(self):
        """Check sensitive files have proper permissions"""
        sensitive_patterns = [
            'zerodha_token.json',
            '**/zerodha_token.json',
            '.env',
            'credentials.json'
        ]

        issues = []

        for pattern in sensitive_patterns:
            for file_path in Path('.').glob(pattern):
                if file_path.exists():
                    # Check if file is in .gitignore
                    gitignore_path = Path('.gitignore')
                    if gitignore_path.exists():
                        with open(gitignore_path, 'r') as f:
                            gitignore_content = f.read()
                            if file_path.name not in gitignore_content:
                                issues.append(f"{file_path} not in .gitignore")

                    # Check file permissions (Unix-like systems)
                    if hasattr(os, 'stat'):
                        import stat
                        file_stat = os.stat(file_path)
                        mode = stat.filemode(file_stat.st_mode)
                        # Check if file is readable by others
                        if file_stat.st_mode & (stat.S_IROTH | stat.S_IWOTH):
                            issues.append(f"{file_path} has unsafe permissions ({mode})")

        if issues:
            self.checks.append(SafetyCheck(
                name="Sensitive Files",
                passed=False,
                severity='HIGH',
                message=f"Sensitive file issues: {'; '.join(issues)}",
                fix_suggestion="Add files to .gitignore and set permissions to 0600"
            ))
        else:
            self.checks.append(SafetyCheck(
                name="Sensitive Files",
                passed=True,
                severity='HIGH',
                message="No sensitive file security issues found"
            ))

    def _check_configuration_sanity(self):
        """Check configuration values are sane"""
        issues = []

        try:
            # Check capital
            if hasattr(self.config, 'default_capital'):
                capital = self.config.default_capital
            else:
                capital = self.config.get('trading.default_capital', 0)

            if capital < 10000:
                issues.append(f"Capital too low: ₹{capital:,.0f} (min ₹10,000)")
            elif capital > 100000000:
                issues.append(f"Capital suspiciously high: ₹{capital:,.0f}")

            # Check risk per trade
            if hasattr(self.config, 'risk_per_trade'):
                risk_pct = self.config.risk_per_trade
            else:
                risk_pct = self.config.get('trading.risk_per_trade', 0.02)

            if risk_pct > 0.05:
                issues.append(f"Risk per trade too high: {risk_pct*100}% (recommend <5%)")

            # Check max positions
            if hasattr(self.config, 'max_positions'):
                max_pos = self.config.max_positions
            else:
                max_pos = self.config.get('trading.max_positions', 10)

            if max_pos > 50:
                issues.append(f"Max positions very high: {max_pos} (hard to manage)")

        except Exception as e:
            issues.append(f"Error reading config: {e}")

        if issues:
            self.checks.append(SafetyCheck(
                name="Configuration Sanity",
                passed=False,
                severity='MEDIUM',
                message=f"Config issues: {'; '.join(issues)}",
                fix_suggestion="Review and adjust configuration values"
            ))
        else:
            self.checks.append(SafetyCheck(
                name="Configuration Sanity",
                passed=True,
                severity='MEDIUM',
                message="Configuration values are reasonable"
            ))

    def _check_directory_structure(self):
        """Check required directories exist"""
        required_dirs = ['logs', 'state', 'logs/orders']
        missing = [d for d in required_dirs if not Path(d).exists()]

        if missing:
            self.checks.append(SafetyCheck(
                name="Directory Structure",
                passed=False,
                severity='MEDIUM',
                message=f"Missing directories: {', '.join(missing)}",
                fix_suggestion=f"Create directories: mkdir -p {' '.join(missing)}"
            ))
        else:
            self.checks.append(SafetyCheck(
                name="Directory Structure",
                passed=True,
                severity='MEDIUM',
                message="All required directories exist"
            ))

    def _check_market_hours_config(self):
        """Check market hours are configured"""
        try:
            if hasattr(self.config, 'is_trading_time'):
                # Try calling it
                self.config.is_trading_time()
                self.checks.append(SafetyCheck(
                    name="Market Hours",
                    passed=True,
                    severity='LOW',
                    message="Market hours check functional"
                ))
            else:
                self.checks.append(SafetyCheck(
                    name="Market Hours",
                    passed=False,
                    severity='LOW',
                    message="No market hours check found",
                    fix_suggestion="Ensure AdvancedMarketManager is initialized"
                ))

        except Exception as e:
            self.checks.append(SafetyCheck(
                name="Market Hours",
                passed=False,
                severity='LOW',
                message=f"Market hours check error: {e}"
            ))

    def print_report(self, checks: Optional[List[SafetyCheck]] = None):
        """Print safety check report"""
        if checks is None:
            checks = self.checks

        print("\n" + "=" * 80)
        print("🔒 PRODUCTION SAFETY VALIDATION REPORT")
        print("=" * 80)

        # Group by severity
        by_severity = {
            'CRITICAL': [],
            'HIGH': [],
            'MEDIUM': [],
            'LOW': []
        }

        for check in checks:
            by_severity[check.severity].append(check)

        # Print each severity level
        for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            if by_severity[severity]:
                print(f"\n{severity} CHECKS:")
                print("-" * 80)

                for check in by_severity[severity]:
                    status = "✅ PASS" if check.passed else "❌ FAIL"
                    print(f"{status} | {check.name}")
                    print(f"     {check.message}")

                    if not check.passed and check.fix_suggestion:
                        print(f"     💡 Fix: {check.fix_suggestion}")

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY:")
        total = len(checks)
        passed = sum(1 for c in checks if c.passed)
        failed = total - passed

        critical_failed = sum(1 for c in checks if c.severity == 'CRITICAL' and not c.passed)
        high_failed = sum(1 for c in checks if c.severity == 'HIGH' and not c.passed)

        print(f"  Total Checks: {total}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")

        if critical_failed > 0:
            print(f"  ⚠️  CRITICAL failures: {critical_failed}")
        if high_failed > 0:
            print(f"  ⚠️  HIGH priority failures: {high_failed}")

        print("=" * 80)

        if critical_failed > 0 or high_failed > 0:
            print("❌ SYSTEM NOT SAFE FOR PRODUCTION")
            print("   Fix all CRITICAL and HIGH priority issues before trading")
        else:
            print("✅ SYSTEM PASSED ALL CRITICAL AND HIGH PRIORITY CHECKS")
            if failed > 0:
                print(f"   ({failed} low/medium priority issues remain)")

        print("=" * 80 + "\n")

        return critical_failed == 0 and high_failed == 0


def validate_production_safety(config) -> bool:
    """
    Validate system is safe for production

    Args:
        config: Trading configuration

    Returns:
        True if safe, False otherwise
    """
    validator = ProductionSafetyValidator(config)
    passed, checks = validator.run_all_checks()
    safe = validator.print_report(checks)

    return safe


if __name__ == "__main__":
    print("🧪 Testing Production Safety Validator")

    # Mock config
    class MockConfig:
        mode = 'paper'
        use_kite_trends = True
        default_capital = 1000000
        risk_per_trade = 0.02
        max_positions = 10

        def get(self, key, default=None):
            parts = key.split('.')
            obj = self
            for part in parts:
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                else:
                    return default
            return obj

        def get_api_credentials(self):
            return (os.getenv('ZERODHA_API_KEY'), os.getenv('ZERODHA_API_SECRET'))

        def is_trading_time(self):
            return True

    config = MockConfig()
    validate_production_safety(config)
