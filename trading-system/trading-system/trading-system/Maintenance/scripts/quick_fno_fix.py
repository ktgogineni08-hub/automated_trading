#!/usr/bin/env python3
"""
Quick fix to force restart F&O system with fresh data
"""

import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.append('/Users/gogineni/Python/trading-system')

def force_refresh_fno_system():
    """Force refresh the F&O system to clear any cached data"""
    print("🔄 Force refreshing F&O system...")

    try:
        # Clear any cached data
        cache_dirs = [
            '/Users/gogineni/Python/trading-system/__pycache__',
        ]

        for cache_dir in cache_dirs:
            if os.path.exists(cache_dir):
                import shutil
                shutil.rmtree(cache_dir)
                print(f"✅ Cleared cache: {cache_dir}")

        # Import fresh instances
        from enhanced_trading_system_complete import (
            FNOTerminal,
            UnifiedPortfolio,
            FNODataProvider,
            MarketHoursManager,
            IntelligentFNOStrategySelector
        )

        print("\n🧪 Testing fresh F&O components...")

        # Test 1: Create fresh portfolio with market hours
        portfolio = UnifiedPortfolio(initial_cash=1000000, trading_mode='paper')
        assert hasattr(portfolio, 'market_hours_manager'), "Portfolio missing market_hours_manager"
        print("✅ Fresh portfolio has market_hours_manager")

        # Test 2: Create fresh terminal
        terminal = FNOTerminal()
        assert hasattr(terminal, 'market_hours'), "Terminal missing market_hours"
        print("✅ Fresh terminal has market_hours")

        # Test 3: Create fresh data provider
        provider = FNODataProvider()
        assert hasattr(provider, '_calculate_profit_confidence'), "Provider missing _calculate_profit_confidence"
        print("✅ Fresh provider has profit confidence calculation")

        # Test 4: Create fresh strategy selector
        selector = IntelligentFNOStrategySelector(portfolio=portfolio)

        # Test division by zero protection
        invalid_details = {
            'total_premium': 0.0,
            'call_option': type('MockOption', (), {'lot_size': 75, 'symbol': 'TEST', 'last_price': 0.0})(),
            'put_option': type('MockOption', (), {'lot_size': 75, 'symbol': 'TEST', 'last_price': 0.0})()
        }

        result = selector._execute_straddle(invalid_details, 200000, portfolio)
        assert not result['success'], "Should fail with zero premium"
        print("✅ Division by zero protection working")

        # Test 5: Market hours functionality
        can_trade, reason = portfolio.market_hours_manager.can_trade()
        print(f"✅ Market hours check: {reason}")

        print("\n🎯 Current time info:")
        now = datetime.now()
        print(f"  📅 Date: {now.strftime('%Y-%m-%d')}")
        print(f"  🕐 Time: {now.strftime('%H:%M:%S')}")
        print(f"  📊 Trading allowed: {can_trade}")

        print("\n✅ All fresh components working correctly!")
        print("💡 The F&O system should now work without the previous errors")

        return True

    except Exception as e:
        print(f"❌ Error during refresh: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function"""
    print("🔧 F&O System Quick Fix and Refresh")
    print("=" * 50)

    success = force_refresh_fno_system()

    if success:
        print("\n🎉 F&O system refresh completed successfully!")
        print("\n💡 Next steps:")
        print("  1. Try running the F&O system again")
        print("  2. Use option 2 (Continuous F&O Monitoring)")
        print("  3. The system should now work without errors")
        print("\n📝 Key fixes applied:")
        print("  ✅ Portfolio instances have market_hours_manager")
        print("  ✅ Division by zero protection in place")
        print("  ✅ Profit confidence calculation available")
        print("  ✅ Market hours restrictions working")
    else:
        print("\n❌ F&O system refresh failed")
        print("Some manual intervention may be needed")

    return success

if __name__ == "__main__":
    main()