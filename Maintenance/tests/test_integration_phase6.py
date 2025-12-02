#!/usr/bin/env python3
"""
Phase 6 Integration Tests
Tests the complete modular trading system
"""

import sys
import os
from typing import Dict, List

def test_all_module_imports():
    """Test that all modules import without errors"""
    print("=" * 70)
    print("TEST 1: Module Import Validation")
    print("=" * 70)

    modules_to_test = [
        # Strategies
        ('strategies.base', 'BaseStrategy'),
        ('strategies.moving_average', 'ImprovedMovingAverageCrossover'),
        ('strategies.rsi', 'EnhancedRSIStrategy'),
        ('strategies.bollinger', 'BollingerBandsStrategy'),
        ('strategies.volume_breakout', 'ImprovedVolumeBreakoutStrategy'),
        ('strategies.momentum', 'EnhancedMomentumStrategy'),

        # Infrastructure
        ('infrastructure.caching', 'LRUCacheWithTTL'),
        ('infrastructure.rate_limiting', 'EnhancedRateLimiter'),

        # Data
        ('data.provider', 'DataProvider'),

        # Core
        ('core.signal_aggregator', 'EnhancedSignalAggregator'),
        ('core.regime_detector', 'MarketRegimeDetector'),
        ('core.transaction', 'TradingTransaction'),
        ('core.portfolio', 'UnifiedPortfolio'),
        ('core.trading_system', 'UnifiedTradingSystem'),

        # FNO
        ('fno.indices', 'IndexConfig'),
        ('fno.options', 'OptionContract'),
        ('fno.options', 'OptionChain'),
        ('fno.data_provider', 'FNODataProvider'),
        ('fno.strategies', 'FNOStrategy'),
        ('fno.broker', 'FNOBroker'),
        ('fno.analytics', 'FNOAnalytics'),
        ('fno.analytics', 'FNOBacktester'),
        ('fno.strategy_selector', 'IntelligentFNOStrategySelector'),
        ('fno.terminal', 'FNOTerminal'),

        # Utilities
        ('utilities.logger', 'TradingLogger'),
        ('utilities.dashboard', 'DashboardConnector'),
        ('utilities.market_hours', 'MarketHoursManager'),
        ('utilities.state_managers', 'TradingStateManager'),
        ('utilities.state_managers', 'EnhancedStateManager'),
    ]

    passed = 0
    failed = 0

    for module_name, class_name in modules_to_test:
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            print(f"  ✅ {module_name}.{class_name}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {module_name}.{class_name} - {e}")
            failed += 1

    print()
    print(f"Results: {passed} passed, {failed} failed out of {len(modules_to_test)} tests")
    print()
    return failed == 0


def test_main_entry_point():
    """Test main.py entry point"""
    print("=" * 70)
    print("TEST 2: Main Entry Point Validation")
    print("=" * 70)

    try:
        import main

        required_functions = [
            'ensure_correct_directory',
            'setup_zerodha_authentication',
            'display_main_menu',
            'display_nifty_menu',
            'display_fno_menu',
            'run_paper_trading',
            'run_backtesting',
            'run_live_trading',
            'run_fno_trading',
            'start_dashboard',
            'main'
        ]

        passed = 0
        failed = 0

        for func_name in required_functions:
            if hasattr(main, func_name) and callable(getattr(main, func_name)):
                print(f"  ✅ {func_name}()")
                passed += 1
            else:
                print(f"  ❌ {func_name}() - NOT FOUND")
                failed += 1

        print()
        print(f"Results: {passed} passed, {failed} failed out of {len(required_functions)} functions")
        print()
        return failed == 0

    except Exception as e:
        print(f"  ❌ Failed to import main.py: {e}")
        print()
        return False


def test_circular_imports():
    """Test for circular import issues"""
    print("=" * 70)
    print("TEST 3: Circular Import Detection")
    print("=" * 70)

    # Clear all imports
    import_modules = [
        'strategies', 'infrastructure', 'data', 'core', 'fno', 'utilities', 'main'
    ]

    for mod_name in list(sys.modules.keys()):
        for check_mod in import_modules:
            if mod_name.startswith(check_mod):
                del sys.modules[mod_name]

    try:
        # Import in dependency order
        import infrastructure.caching
        import infrastructure.rate_limiting
        print("  ✅ Infrastructure imports clean")

        import strategies.base
        import strategies.moving_average
        import strategies.rsi
        import strategies.bollinger
        import strategies.volume_breakout
        import strategies.momentum
        print("  ✅ Strategies imports clean")

        import data.provider
        print("  ✅ Data provider imports clean")

        import core.signal_aggregator
        import core.regime_detector
        import core.transaction
        import core.portfolio
        import core.trading_system
        print("  ✅ Core system imports clean")

        import fno.indices
        import fno.options
        import fno.data_provider
        import fno.strategies
        import fno.broker
        import fno.analytics
        import fno.strategy_selector
        import fno.terminal
        print("  ✅ FNO system imports clean")

        import utilities.logger
        import utilities.dashboard
        import utilities.market_hours
        import utilities.state_managers
        print("  ✅ Utilities imports clean")

        import main
        print("  ✅ Main entry point imports clean")

        print()
        print("Results: No circular import issues detected")
        print()
        return True

    except ImportError as e:
        print(f"  ❌ Circular import detected: {e}")
        print()
        return False


def test_class_instantiation():
    """Test basic class instantiation"""
    print("=" * 70)
    print("TEST 4: Class Instantiation")
    print("=" * 70)

    tests = []

    # Test strategy instantiation
    try:
        from strategies.base import BaseStrategy
        strategy = BaseStrategy("test")
        print("  ✅ BaseStrategy instantiation")
        tests.append(True)
    except Exception as e:
        print(f"  ❌ BaseStrategy instantiation: {e}")
        tests.append(False)

    # Test cache instantiation
    try:
        from infrastructure.caching import LRUCacheWithTTL
        cache = LRUCacheWithTTL(max_size=100, ttl_seconds=60)
        print("  ✅ LRUCacheWithTTL instantiation")
        tests.append(True)
    except Exception as e:
        print(f"  ❌ LRUCacheWithTTL instantiation: {e}")
        tests.append(False)

    # Test rate limiter instantiation
    try:
        from infrastructure.rate_limiting import EnhancedRateLimiter
        limiter = EnhancedRateLimiter()
        print("  ✅ EnhancedRateLimiter instantiation")
        tests.append(True)
    except Exception as e:
        print(f"  ❌ EnhancedRateLimiter instantiation: {e}")
        tests.append(False)

    # Test signal aggregator instantiation
    try:
        from core.signal_aggregator import EnhancedSignalAggregator
        aggregator = EnhancedSignalAggregator()
        print("  ✅ EnhancedSignalAggregator instantiation")
        tests.append(True)
    except Exception as e:
        print(f"  ❌ EnhancedSignalAggregator instantiation: {e}")
        tests.append(False)

    # Test logger instantiation
    try:
        from utilities.logger import TradingLogger
        logger = TradingLogger()
        print("  ✅ TradingLogger instantiation")
        tests.append(True)
    except Exception as e:
        print(f"  ❌ TradingLogger instantiation: {e}")
        tests.append(False)

    print()
    passed = sum(tests)
    total = len(tests)
    print(f"Results: {passed} passed, {total - passed} failed out of {total} instantiation tests")
    print()
    return all(tests)


def test_module_structure():
    """Test module structure and file organization"""
    print("=" * 70)
    print("TEST 5: Module Structure Validation")
    print("=" * 70)

    expected_structure = {
        'strategies': ['__init__.py', 'base.py', 'moving_average.py', 'rsi.py',
                      'bollinger.py', 'volume_breakout.py', 'momentum.py'],
        'infrastructure': ['__init__.py', 'caching.py', 'rate_limiting.py'],
        'data': ['__init__.py', 'provider.py'],
        'core': ['__init__.py', 'signal_aggregator.py', 'regime_detector.py',
                'transaction.py', 'portfolio.py', 'trading_system.py'],
        'fno': ['__init__.py', 'indices.py', 'options.py', 'data_provider.py',
               'strategies.py', 'broker.py', 'analytics.py', 'strategy_selector.py', 'terminal.py'],
        'utilities': ['__init__.py', 'logger.py', 'dashboard.py', 'market_hours.py', 'state_managers.py']
    }

    all_found = True

    for module_dir, files in expected_structure.items():
        if os.path.isdir(module_dir):
            print(f"  ✅ {module_dir}/ directory exists")
            for file in files:
                file_path = os.path.join(module_dir, file)
                if os.path.exists(file_path):
                    print(f"     ✅ {file}")
                else:
                    print(f"     ❌ {file} - MISSING")
                    all_found = False
        else:
            print(f"  ❌ {module_dir}/ directory - MISSING")
            all_found = False

    # Check main.py
    if os.path.exists('main.py'):
        print(f"  ✅ main.py exists")
    else:
        print(f"  ❌ main.py - MISSING")
        all_found = False

    print()
    if all_found:
        print("Results: All expected files and directories found")
    else:
        print("Results: Some files or directories are missing")
    print()
    return all_found


def main():
    """Run all integration tests"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "PHASE 6 INTEGRATION TESTS" + " " * 28 + "║")
    print("║" + " " * 15 + "Trading System Validation" + " " * 28 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    results = []

    # Run all tests
    results.append(("Module Imports", test_all_module_imports()))
    results.append(("Main Entry Point", test_main_entry_point()))
    results.append(("Circular Imports", test_circular_imports()))
    results.append(("Class Instantiation", test_class_instantiation()))
    results.append(("Module Structure", test_module_structure()))

    # Print summary
    print("=" * 70)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {test_name}")

    print()

    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)

    print(f"Overall: {passed_tests}/{total_tests} test suites passed")
    print()

    if passed_tests == total_tests:
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        print("✅ The modular trading system is ready for deployment")
        return 0
    else:
        print("⚠️  SOME TESTS FAILED")
        print("❌ Please review the failures above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
