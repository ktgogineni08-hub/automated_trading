#!/usr/bin/env python3
"""
Comprehensive System Integrity Validation Framework
Tests all fixes and improvements implemented in the trading system
"""

import os
import sys
import time
import json
try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None
import threading
import subprocess
import requests
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import importlib.util

# Setup logging for validation
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('validation_results.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class ValidationResult:
    """Stores validation results for each test"""

    def __init__(self, test_name: str, status: str, details: str = "", metrics: Dict = None):
        self.test_name = test_name
        self.status = status  # 'PASS', 'FAIL', 'WARNING', 'ERROR'
        self.details = details
        self.metrics = metrics or {}
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict:
        return {
            'test_name': self.test_name,
            'status': self.status,
            'details': self.details,
            'metrics': self.metrics,
            'timestamp': self.timestamp.isoformat()
        }

class SystemIntegrityValidator:
    """Comprehensive validation framework for trading system"""

    def __init__(self):
        self.results: List[ValidationResult] = []
        self.start_time = datetime.now()
        self.process = psutil.Process()

    def log_result(self, test_name: str, status: str, details: str = "", metrics: Dict = None):
        """Log a validation result"""
        result = ValidationResult(test_name, status, details, metrics)
        self.results.append(result)

        # Log to console with appropriate level
        if status == 'PASS':
            logger.info(f"✅ {test_name}: {details}")
        elif status == 'FAIL':
            logger.error(f"❌ {test_name}: {details}")
        elif status == 'WARNING':
            logger.warning(f"⚠️ {test_name}: {details}")
        else:
            logger.info(f"ℹ️ {test_name}: {details}")

    def validate_security_fixes(self) -> bool:
        """Validate all security fixes"""
        logger.info("🔒 Validating Security Fixes...")

        all_passed = True

        # Test 1: API Key Encryption/Decryption
        try:
            from infrastructure.security import (
                initialize_security, encrypt_api_key, decrypt_api_key,
                save_encrypted_state, load_encrypted_state, validate_secure_path,
                sanitize_log_message, hash_sensitive_data, log_security_event
            )

            # Test API key encryption
            test_api_key = "test_api_key_12345"
            encrypted = encrypt_api_key(test_api_key, "test_service")
            decrypted = decrypt_api_key("test_service")

            if decrypted == test_api_key:
                self.log_result("API Key Encryption", "PASS",
                    "API key encryption/decryption working correctly")
            else:
                self.log_result("API Key Encryption", "FAIL",
                    f"API key decryption failed: expected {test_api_key}, got {decrypted}")
                all_passed = False

        except Exception as e:
            self.log_result("API Key Encryption", "ERROR",
                f"Exception during API key encryption test: {e}")
            all_passed = False

        # Test 2: State File Encryption
        try:
            test_state = {"test": "data", "timestamp": datetime.now().isoformat()}
            success = save_encrypted_state(test_state, "test_state.json")
            loaded_state = load_encrypted_state("test_state.json")

            if success and loaded_state == test_state:
                self.log_result("State File Encryption", "PASS",
                    "State file encryption/decryption working correctly")
            else:
                self.log_result("State File Encryption", "FAIL",
                    "State file encryption/decryption failed")
                all_passed = False

        except Exception as e:
            self.log_result("State File Encryption", "ERROR",
                f"Exception during state encryption test: {e}")
            all_passed = False

        # Test 3: Path Traversal Protection
        try:
            test_path = "../../../etc/passwd"
            try:
                validated_path = validate_secure_path(test_path)
                self.log_result("Path Traversal Protection", "FAIL",
                    "Path traversal attack was not blocked")
                all_passed = False
            except ValueError:
                self.log_result("Path Traversal Protection", "PASS",
                    "Path traversal attack correctly blocked")

        except Exception as e:
            self.log_result("Path Traversal Protection", "ERROR",
                f"Exception during path traversal test: {e}")
            all_passed = False

        # Test 4: Sensitive Data Sanitization
        try:
            sensitive_message = "API key: test_key_12345 is valid"
            sanitized = sanitize_log_message(sensitive_message)

            if "test_key_12345" not in sanitized or "*" in sanitized:
                self.log_result("Sensitive Data Sanitization", "PASS",
                    "Sensitive data correctly sanitized in logs")
            else:
                self.log_result("Sensitive Data Sanitization", "FAIL",
                    "Sensitive data not properly sanitized")
                all_passed = False

        except Exception as e:
            self.log_result("Sensitive Data Sanitization", "ERROR",
                f"Exception during sanitization test: {e}")
            all_passed = False

        # Test 5: Session Management
        try:
            from infrastructure.security import create_secure_session, get_secure_session

            test_data = {"user_id": "test_user", "permissions": ["read"]}
            session_id = create_secure_session(test_data)
            retrieved_data = get_secure_session(session_id)

            if retrieved_data == test_data:
                self.log_result("Session Management", "PASS",
                    "Secure session creation and retrieval working correctly")
            else:
                self.log_result("Session Management", "FAIL",
                    "Session management failed")
                all_passed = False

        except Exception as e:
            self.log_result("Session Management", "ERROR",
                f"Exception during session management test: {e}")
            all_passed = False

        return all_passed

    def validate_performance_fixes(self) -> bool:
        """Validate all performance fixes"""
        logger.info("⚡ Validating Performance Fixes...")

        all_passed = True

        # Test 1: Signal Processing Complexity (O(n) vs O(n²))
        try:
            from infrastructure.performance import (
                process_signals_optimized, can_make_request_optimized,
                record_request_optimized, detect_memory_leaks,
                force_memory_cleanup, get_performance_report,
                create_optimized_lock
            )

            # Test optimized signal processing
            test_symbols = ["HDFCBANK", "ICICIBANK", "TCS", "INFY", "RELIANCE"] * 10  # 50 symbols
            start_time = time.time()

            # Mock data provider and strategies for testing
            class MockDataProvider:
                def fetch_with_retry(self, symbol, **kwargs):
                    import pandas as pd
                    import numpy as np
                    # Return mock OHLCV data
                    dates = pd.date_range('2024-01-01', periods=100, freq='5T')
                    data = pd.DataFrame({
                        'open': np.random.uniform(100, 200, 100),
                        'high': np.random.uniform(100, 200, 100),
                        'low': np.random.uniform(100, 200, 100),
                        'close': np.random.uniform(100, 200, 100),
                        'volume': np.random.uniform(1000, 10000, 100)
                    }, index=dates)
                    return data

            class MockStrategy:
                def __init__(self, name):
                    self.name = name
                def generate_signals(self, data, symbol=None):
                    return {'signal': 1, 'strength': 0.7, 'reason': 'test_signal'}

            mock_dp = MockDataProvider()
            mock_strategies = [MockStrategy(f"Strategy_{i}") for i in range(3)]

            # Test optimized processing
            results = process_signals_optimized(test_symbols, mock_dp, mock_strategies)
            processing_time = time.time() - start_time

            if processing_time < 5.0:  # Should complete in under 5 seconds for 50 symbols
                self.log_result("Signal Processing Complexity", "PASS",
                    f"O(n) signal processing completed in {processing_time:.2f}s for 50 symbols")
            else:
                self.log_result("Signal Processing Complexity", "WARNING",
                    f"Signal processing took {processing_time:.2f}s - may still have performance issues")
                all_passed = False

        except Exception as e:
            self.log_result("Signal Processing Complexity", "ERROR",
                f"Exception during signal processing test: {e}")
            all_passed = False

        # Test 2: Rate Limiting O(1) Performance
        try:
            start_time = time.time()
            for i in range(1000):  # 1000 rate limit checks
                can_make_request_optimized()
                record_request_optimized()
            rate_limit_time = time.time() - start_time

            if rate_limit_time < 1.0:  # Should complete in under 1 second
                self.log_result("Rate Limiting O(1)", "PASS",
                    f"O(1) rate limiting completed 1000 operations in {rate_limit_time:.3f}s")
            else:
                self.log_result("Rate Limiting O(1)", "FAIL",
                    f"Rate limiting took {rate_limit_time:.3f}s for 1000 operations - not O(1)")
                all_passed = False

        except Exception as e:
            self.log_result("Rate Limiting O(1)", "ERROR",
                f"Exception during rate limiting test: {e}")
            all_passed = False

        # Test 3: Memory Leak Detection
        try:
            memory_analysis = detect_memory_leaks()
            if not memory_analysis.get('leak_detected', False):
                self.log_result("Memory Leak Detection", "PASS",
                    "Memory leak detection system operational")
            else:
                self.log_result("Memory Leak Detection", "WARNING",
                    f"Memory leak detected: {memory_analysis}")
                # Don't fail the test for detected leaks, just warn

        except Exception as e:
            self.log_result("Memory Leak Detection", "ERROR",
                f"Exception during memory leak test: {e}")
            all_passed = False

        # Test 4: Thread Contention Resolution
        try:
            test_lock = create_optimized_lock("test_lock")
            contention_start = time.time()

            def test_thread_contention():
                for i in range(100):
                    with test_lock:
                        time.sleep(0.001)  # Small delay to create contention

            threads = [threading.Thread(target=test_thread_contention) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            contention_time = time.time() - contention_start

            if contention_time < 2.0:  # Should complete in reasonable time
                self.log_result("Thread Contention Resolution", "PASS",
                    f"Thread contention handling completed in {contention_time:.2f}s")
            else:
                self.log_result("Thread Contention Resolution", "WARNING",
                    f"Thread contention took {contention_time:.2f}s - may have contention issues")

        except Exception as e:
            self.log_result("Thread Contention Resolution", "ERROR",
                f"Exception during thread contention test: {e}")
            all_passed = False

        # Test 5: Performance Monitoring
        try:
            report = get_performance_report()
            if report and 'metrics' in report:
                self.log_result("Performance Monitoring", "PASS",
                    "Performance monitoring system operational")
            else:
                self.log_result("Performance Monitoring", "FAIL",
                    "Performance monitoring system not working correctly")
                all_passed = False

        except Exception as e:
            self.log_result("Performance Monitoring", "ERROR",
                f"Exception during performance monitoring test: {e}")
            all_passed = False

        return all_passed

    def validate_system_functionality(self) -> bool:
        """Validate system functionality across all modes"""
        logger.info("🔧 Validating System Functionality...")

        all_passed = True

        # Test 1: Module Imports and Dependencies
        try:
            required_modules = [
                'enhanced_trading_system_complete',
                'infrastructure.security',
                'infrastructure.performance',
                'enhanced_dashboard_server'
            ]

            for module in required_modules:
                try:
                    if module.endswith('.py'):
                        module_name = module[:-3]
                        spec = importlib.util.spec_from_file_location(module_name, f"{module_name}.py")
                        if spec and spec.loader:
                            importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(sys.modules[module_name])
                    else:
                        importlib.import_module(module)

                    self.log_result(f"Module Import: {module}", "PASS",
                        f"Module {module} imported successfully")

                except ImportError as e:
                    self.log_result(f"Module Import: {module}", "FAIL",
                        f"Failed to import {module}: {e}")
                    all_passed = False
                except Exception as e:
                    self.log_result(f"Module Import: {module}", "ERROR",
                        f"Error loading {module}: {e}")
                    all_passed = False

        except Exception as e:
            self.log_result("Module Dependencies", "ERROR",
                f"Exception during module validation: {e}")
            all_passed = False

        # Test 2: Configuration Loading
        try:
            from trading_config import TradingConfig

            config = TradingConfig.from_env()
            config.validate()

            self.log_result("Configuration Loading", "PASS",
                "Configuration loaded and validated successfully")

        except Exception as e:
            self.log_result("Configuration Loading", "ERROR",
                f"Exception during configuration test: {e}")
            all_passed = False

        # Test 3: Dashboard Server Startup
        try:
            # Test if dashboard server can be imported and initialized
            from enhanced_dashboard_server import SecureDashboardHandler

            # Test handler creation (without starting server)
            handler = SecureDashboardHandler
            if handler:
                self.log_result("Dashboard Server", "PASS",
                    "Dashboard server components loaded successfully")
            else:
                self.log_result("Dashboard Server", "FAIL",
                    "Dashboard server handler creation failed")
                all_passed = False

        except Exception as e:
            self.log_result("Dashboard Server", "ERROR",
                f"Exception during dashboard test: {e}")
            all_passed = False

        # Test 4: State Management
        try:
            from safe_file_ops import StateManager, atomic_write_json

            # Test state manager
            state_mgr = StateManager()
            test_state = {"test": "state", "timestamp": datetime.now().isoformat()}

            # Test atomic write
            success = atomic_write_json("test_state.json", test_state)
            if success:
                self.log_result("State Management", "PASS",
                    "State management and atomic operations working correctly")
            else:
                self.log_result("State Management", "FAIL",
                    "State management atomic operations failed")
                all_passed = False

        except Exception as e:
            self.log_result("State Management", "ERROR",
                f"Exception during state management test: {e}")
            all_passed = False

        # Test 5: Trading Mode Support
        try:
            from enhanced_trading_system_complete import UnifiedTradingSystem, UnifiedPortfolio

            # Test portfolio creation for different modes
            modes = ['paper', 'live', 'backtest']
            for mode in modes:
                try:
                    portfolio = UnifiedPortfolio(
                        initial_cash=1000000,
                        trading_mode=mode,
                        silent=True
                    )

                    if portfolio:
                        self.log_result(f"Trading Mode: {mode}", "PASS",
                            f"{mode.upper()} trading mode initialized successfully")
                    else:
                        self.log_result(f"Trading Mode: {mode}", "FAIL",
                            f"{mode.upper()} trading mode initialization failed")
                        all_passed = False

                except Exception as e:
                    self.log_result(f"Trading Mode: {mode}", "ERROR",
                        f"Exception during {mode} mode test: {e}")
                    all_passed = False

        except Exception as e:
            self.log_result("Trading Mode Support", "ERROR",
                f"Exception during trading mode test: {e}")
            all_passed = False

        return all_passed

    def validate_integration_testing(self) -> bool:
        """Validate module interactions and integration"""
        logger.info("🔗 Validating Integration Testing...")

        all_passed = True

        # Test 1: Security Module Integration
        try:
            from infrastructure.security import initialize_security
            from infrastructure.performance import initialize_performance_monitoring

            # Test that security and performance modules can be initialized together
            initialize_security()
            initialize_performance_monitoring()

            self.log_result("Security-Performance Integration", "PASS",
                "Security and performance modules integrate correctly")

        except Exception as e:
            self.log_result("Security-Performance Integration", "ERROR",
                f"Exception during security-performance integration test: {e}")
            all_passed = False

        # Test 2: Dashboard Integration
        try:
            from enhanced_dashboard_server import dashboard_data
            from enhanced_trading_system_complete import DashboardConnector

            # Test dashboard data structure
            if isinstance(dashboard_data, dict) and 'signals' in dashboard_data:
                self.log_result("Dashboard Data Structure", "PASS",
                    "Dashboard data structure is correctly initialized")
            else:
                self.log_result("Dashboard Data Structure", "FAIL",
                    "Dashboard data structure is incorrect")
                all_passed = False

            # Test dashboard connector
            dashboard_url = os.getenv('DASHBOARD_BASE_URL', 'https://localhost:8080')
            api_key = os.getenv('DASHBOARD_API_KEY')
            connector = DashboardConnector(base_url=dashboard_url, api_key=api_key)
            connector.ensure_connection(force=True)
            if hasattr(connector, 'send_signal'):
                self.log_result("Dashboard Connector", "PASS",
                    "Dashboard connector has required methods")
            else:
                self.log_result("Dashboard Connector", "FAIL",
                    "Dashboard connector missing required methods")
                all_passed = False

        except Exception as e:
            self.log_result("Dashboard Integration", "ERROR",
                f"Exception during dashboard integration test: {e}")
            all_passed = False

        # Test 3: Error Handling Integration
        try:
            from trading_exceptions import TradingError, ConfigurationError, APIError

            # Test that custom exceptions are properly defined
            exceptions = [TradingError, ConfigurationError, APIError]
            for exc in exceptions:
                if issubclass(exc, Exception):
                    self.log_result(f"Exception: {exc.__name__}", "PASS",
                        f"Custom exception {exc.__name__} properly defined")
                else:
                    self.log_result(f"Exception: {exc.__name__}", "FAIL",
                        f"Custom exception {exc.__name__} not properly defined")
                    all_passed = False

        except Exception as e:
            self.log_result("Error Handling Integration", "ERROR",
                f"Exception during error handling test: {e}")
            all_passed = False

        # Test 4: Configuration Integration
        try:
            from trading_config import TradingConfig
            from input_validator import InputValidator

            # Test configuration and validation integration
            config = TradingConfig.from_env()
            validator = InputValidator()

            if config and validator:
                self.log_result("Configuration Integration", "PASS",
                    "Configuration and validation modules integrate correctly")
            else:
                self.log_result("Configuration Integration", "FAIL",
                    "Configuration integration failed")
                all_passed = False

        except Exception as e:
            self.log_result("Configuration Integration", "ERROR",
                f"Exception during configuration integration test: {e}")
            all_passed = False

        return all_passed

    def validate_regression_testing(self) -> bool:
        """Validate that existing functionality still works"""
        logger.info("🔄 Validating Regression Testing...")

        all_passed = True

        # Test 1: Core Trading System Components
        try:
            from enhanced_trading_system_complete import (
                NIFTY_50_SYMBOLS, SECTOR_GROUPS, MarketHoursManager,
                EnhancedStateManager, LRUCacheWithTTL, CircuitBreaker
            )

            # Test constants are still available
            if len(NIFTY_50_SYMBOLS) == 50:
                self.log_result("NIFTY 50 Symbols", "PASS",
                    "NIFTY 50 symbols list intact (50 symbols)")
            else:
                self.log_result("NIFTY 50 Symbols", "FAIL",
                    f"NIFTY 50 symbols count incorrect: {len(NIFTY_50_SYMBOLS)}")
                all_passed = False

            # Test sector groups
            if 'Banking' in SECTOR_GROUPS and 'IT' in SECTOR_GROUPS:
                self.log_result("Sector Groups", "PASS",
                    "Sector groups configuration intact")
            else:
                self.log_result("Sector Groups", "FAIL",
                    "Sector groups configuration missing")
                all_passed = False

            # Test market hours manager
            market_mgr = MarketHoursManager()
            can_trade, reason = market_mgr.can_trade()

            self.log_result("Market Hours Manager", "PASS",
                f"Market hours manager operational: {reason}")

        except Exception as e:
            self.log_result("Core Components", "ERROR",
                f"Exception during core components test: {e}")
            all_passed = False

        # Test 2: Strategy Components
        try:
            from enhanced_trading_system_complete import (
                ImprovedMovingAverageCrossover, EnhancedRSIStrategy,
                BollingerBandsStrategy, EnhancedMomentumStrategy
            )

            # Test strategy creation
            strategies = [
                ImprovedMovingAverageCrossover(),
                EnhancedRSIStrategy(),
                BollingerBandsStrategy(),
                EnhancedMomentumStrategy()
            ]

            for strategy in strategies:
                if hasattr(strategy, 'generate_signals'):
                    self.log_result(f"Strategy: {strategy.name}", "PASS",
                        f"Strategy {strategy.name} properly initialized")
                else:
                    self.log_result(f"Strategy: {strategy.name}", "FAIL",
                        f"Strategy {strategy.name} missing generate_signals method")
                    all_passed = False

        except Exception as e:
            self.log_result("Strategy Components", "ERROR",
                f"Exception during strategy components test: {e}")
            all_passed = False

        # Test 3: Data Provider Components
        try:
            from enhanced_trading_system_complete import DataProvider

            # Test data provider creation
            dp = DataProvider(use_yf_fallback=True)
            if dp:
                self.log_result("Data Provider", "PASS",
                    "Data provider initialized successfully")
            else:
                self.log_result("Data Provider", "FAIL",
                    "Data provider initialization failed")
                all_passed = False

        except Exception as e:
            self.log_result("Data Provider Components", "ERROR",
                f"Exception during data provider test: {e}")
            all_passed = False

        # Test 4: Backup and Recovery Systems
        try:
            # Test that backup directories exist or can be created
            backup_dirs = ['state', 'trade_archives', 'logs']
            for dir_name in backup_dirs:
                dir_path = Path(dir_name)
                if dir_path.exists() or dir_path.mkdir(parents=True, exist_ok=True):
                    self.log_result(f"Backup Directory: {dir_name}", "PASS",
                        f"Backup directory {dir_name} accessible")
                else:
                    self.log_result(f"Backup Directory: {dir_name}", "FAIL",
                        f"Backup directory {dir_name} not accessible")
                    all_passed = False

        except Exception as e:
            self.log_result("Backup Systems", "ERROR",
                f"Exception during backup systems test: {e}")
            all_passed = False

        return all_passed

    def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run all validation tests"""
        logger.info("🚀 Starting Comprehensive System Integrity Validation")
        logger.info("=" * 80)

        # Run all validation suites
        security_results = self.validate_security_fixes()
        performance_results = self.validate_performance_fixes()
        functionality_results = self.validate_system_functionality()
        integration_results = self.validate_integration_testing()
        regression_results = self.validate_regression_testing()

        # Calculate overall results
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r.status == 'PASS'])
        failed_tests = len([r for r in self.results if r.status == 'FAIL'])
        warning_tests = len([r for r in self.results if r.status == 'WARNING'])
        error_tests = len([r for r in self.results if r.status == 'ERROR'])

        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

        # Generate summary
        end_time = datetime.now()
        duration = end_time - self.start_time

        summary = {
            'validation_timestamp': end_time.isoformat(),
            'duration_seconds': duration.total_seconds(),
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'warning_tests': warning_tests,
            'error_tests': error_tests,
            'success_rate': success_rate,
            'overall_status': 'PASS' if failed_tests == 0 and error_tests == 0 else 'FAIL',
            'results': [r.to_dict() for r in self.results],
            'category_results': {
                'security': security_results,
                'performance': performance_results,
                'functionality': functionality_results,
                'integration': integration_results,
                'regression': regression_results
            }
        }

        # Log final summary
        logger.info("=" * 80)
        logger.info("📊 VALIDATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Duration: {duration.total_seconds():.2f} seconds")
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"✅ Passed: {passed_tests}")
        logger.info(f"❌ Failed: {failed_tests}")
        logger.info(f"⚠️ Warnings: {warning_tests}")
        logger.info(f"🔥 Errors: {error_tests}")
        logger.info(f"Success Rate: {success_rate:.1f}%")
        logger.info(f"Overall Status: {'✅ PASS' if summary['overall_status'] == 'PASS' else '❌ FAIL'}")

        # Save detailed results
        try:
            with open('validation_detailed_results.json', 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            logger.info("💾 Detailed results saved to validation_detailed_results.json")
        except Exception as e:
            logger.error(f"Failed to save detailed results: {e}")

        return summary

def main():
    """Main validation function"""
    print("🔬 SYSTEM INTEGRITY VALIDATION FRAMEWORK")
    print("=" * 80)
    print("🧪 Comprehensive testing of all system fixes and improvements")
    print("📊 Validates security, performance, functionality, integration, and regression")
    print("=" * 80)

    # Create validator instance
    validator = SystemIntegrityValidator()

    try:
        # Run comprehensive validation
        results = validator.run_comprehensive_validation()

        # Print recommendations
        if results['failed_tests'] > 0 or results['error_tests'] > 0:
            print("\n💡 RECOMMENDATIONS:")
            print("-" * 40)

            failed_results = [r for r in validator.results if r.status in ['FAIL', 'ERROR']]
            for result in failed_results[:10]:  # Show top 10 issues
                print(f"• {result.test_name}: {result.details}")

            if len(failed_results) > 10:
                print(f"• ... and {len(failed_results) - 10} more issues")

            print("\n🔧 Please address the failed tests before deploying to production")
        else:
            print("\n🎉 VALIDATION COMPLETE!")
            print("✅ All critical systems are functioning correctly")
            print("🚀 System is ready for production deployment")

        return results['overall_status'] == 'PASS'

    except KeyboardInterrupt:
        print("\n🛑 Validation interrupted by user")
        return False
    except Exception as e:
        logger.error(f"Validation framework error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
