#!/usr/bin/env python3
"""
Comprehensive test to verify all F&O system fixes
"""

import sys
sys.path.append('.')

def test_all_fno_fixes():
    """Test all F&O system fixes comprehensively"""
    print("🧪 Comprehensive F&O System Fixes Test")
    print("=" * 60)

    tests_passed = 0
    total_tests = 0

    try:
        from enhanced_trading_system_complete import (
            FNOTerminal,
            UnifiedPortfolio,
            FNODataProvider,
            MarketHoursManager
        )

        # Test 1: FNOTerminal has market_hours attribute
        total_tests += 1
        print(f"\n🔧 Test {total_tests}: FNOTerminal market_hours attribute")
        try:
            terminal = FNOTerminal()
            assert hasattr(terminal, 'market_hours'), "FNOTerminal missing market_hours attribute"
            assert isinstance(terminal.market_hours, MarketHoursManager), "market_hours is not MarketHoursManager"
            print("  ✅ PASS - FNOTerminal has market_hours attribute")
            tests_passed += 1
        except Exception as e:
            print(f"  ❌ FAIL - {e}")

        # Test 2: UnifiedPortfolio has market_hours_manager attribute
        total_tests += 1
        print(f"\n🔧 Test {total_tests}: UnifiedPortfolio market_hours_manager attribute")
        try:
            portfolio = UnifiedPortfolio(initial_cash=1000000)
            assert hasattr(portfolio, 'market_hours_manager'), "UnifiedPortfolio missing market_hours_manager attribute"
            assert isinstance(portfolio.market_hours_manager, MarketHoursManager), "market_hours_manager is not MarketHoursManager"
            print("  ✅ PASS - UnifiedPortfolio has market_hours_manager attribute")
            tests_passed += 1
        except Exception as e:
            print(f"  ❌ FAIL - {e}")

        # Test 3: FNODataProvider has _calculate_profit_confidence method
        total_tests += 1
        print(f"\n🔧 Test {total_tests}: FNODataProvider _calculate_profit_confidence method")
        try:
            provider = FNODataProvider()
            assert hasattr(provider, '_calculate_profit_confidence'), "FNODataProvider missing _calculate_profit_confidence method"

            # Test the method with sample data
            class MockIndex:
                def __init__(self, lot_size):
                    self.lot_size = lot_size

            # Test major indices
            nifty_confidence = provider._calculate_profit_confidence('NIFTY', MockIndex(75))
            banknifty_confidence = provider._calculate_profit_confidence('BANKNIFTY', MockIndex(35))

            assert 0.8 <= nifty_confidence <= 1.0, f"NIFTY confidence {nifty_confidence} not in expected range"
            assert 0.8 <= banknifty_confidence <= 1.0, f"BANKNIFTY confidence {banknifty_confidence} not in expected range"

            print(f"  ✅ PASS - Method works correctly (NIFTY: {nifty_confidence:.1%}, BANKNIFTY: {banknifty_confidence:.1%})")
            tests_passed += 1
        except Exception as e:
            print(f"  ❌ FAIL - {e}")

        # Test 4: Market hours functionality
        total_tests += 1
        print(f"\n🔧 Test {total_tests}: Market hours functionality")
        try:
            market_hours = MarketHoursManager()
            can_trade, reason = market_hours.can_trade()
            is_open = market_hours.is_market_open()

            assert isinstance(can_trade, bool), "can_trade should return boolean"
            assert isinstance(reason, str), "reason should return string"
            assert isinstance(is_open, bool), "is_market_open should return boolean"

            print(f"  ✅ PASS - Market hours working (Status: {reason})")
            tests_passed += 1
        except Exception as e:
            print(f"  ❌ FAIL - {e}")

        # Test 5: Strategy execution protection (simulate division by zero prevention)
        total_tests += 1
        print(f"\n🔧 Test {total_tests}: Strategy execution error protection")
        try:
            from enhanced_trading_system_complete import IntelligentFNOStrategySelector

            # Create a mock strategy selector
            selector = IntelligentFNOStrategySelector()

            # Test that the methods exist and handle edge cases
            assert hasattr(selector, '_execute_straddle'), "Missing _execute_straddle method"
            assert hasattr(selector, '_execute_strangle'), "Missing _execute_strangle method"

            # Test with invalid/zero premium data
            invalid_details = {
                'total_premium': 0.0,
                'call_option': type('MockOption', (), {'lot_size': 75, 'symbol': 'TEST', 'last_price': 0.0})(),
                'put_option': type('MockOption', (), {'lot_size': 75, 'symbol': 'TEST', 'last_price': 0.0})()
            }

            portfolio = UnifiedPortfolio(initial_cash=1000000)
            result = selector._execute_straddle(invalid_details, 200000, portfolio)

            assert result['success'] == False, "Should fail with zero premium"
            assert 'Invalid premium calculation' in result['error'], "Should have proper error message"

            print("  ✅ PASS - Division by zero protection working")
            tests_passed += 1
        except Exception as e:
            print(f"  ❌ FAIL - {e}")

        # Test 6: Complete system integration
        total_tests += 1
        print(f"\n🔧 Test {total_tests}: Complete system integration")
        try:
            # Test that we can create all components without errors
            terminal = FNOTerminal()
            portfolio = UnifiedPortfolio(initial_cash=1000000)
            provider = FNODataProvider()

            # Test market hours integration
            can_trade, reason = terminal.market_hours.can_trade()
            portfolio_can_trade, portfolio_reason = portfolio.market_hours_manager.can_trade()

            assert can_trade == portfolio_can_trade, "Market hours should be consistent across components"

            print("  ✅ PASS - Complete system integration working")
            tests_passed += 1
        except Exception as e:
            print(f"  ❌ FAIL - {e}")

    except ImportError as e:
        print(f"❌ CRITICAL ERROR - Cannot import required classes: {e}")
        return False

    # Summary
    print(f"\n📊 TEST RESULTS SUMMARY")
    print("=" * 40)
    print(f"Tests Passed: {tests_passed}/{total_tests}")
    print(f"Success Rate: {(tests_passed/total_tests)*100:.1f}%")

    if tests_passed == total_tests:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ F&O system is fully functional")
        print("✅ All critical errors have been fixed")
        print("\n🎯 System Status:")
        print("  • Market hours restrictions: Working")
        print("  • Profit confidence calculation: Working")
        print("  • Strategy execution protection: Working")
        print("  • Component integration: Working")
        return True
    else:
        print(f"\n⚠️  {total_tests - tests_passed} tests failed")
        print("❌ Some issues remain in the F&O system")
        return False

def main():
    """Run the comprehensive test"""
    print("🔬 Starting comprehensive F&O system test...")
    success = test_all_fno_fixes()

    if success:
        print("\n✅ F&O system is ready for use!")
        print("💡 You should now be able to:")
        print("   • Use option 2 (Continuous F&O Monitoring) without errors")
        print("   • Execute strategies without division by zero errors")
        print("   • See proper market hours restrictions")
        print("   • Get profit confidence calculations")
    else:
        print("\n❌ F&O system still has issues that need attention")

    return success

if __name__ == "__main__":
    main()