#!/usr/bin/env python3
"""
Quick test to verify F&O system fixes
"""

import sys
sys.path.append('.')

def test_fno_terminal_initialization():
    """Test that FNOTerminal can be initialized without errors"""
    try:
        from enhanced_trading_system_complete import FNOTerminal, MarketHoursManager

        print("🧪 Testing FNOTerminal initialization...")

        # Test FNOTerminal creation
        terminal = FNOTerminal()

        # Check that market_hours attribute exists
        assert hasattr(terminal, 'market_hours'), "FNOTerminal missing market_hours attribute"
        assert isinstance(terminal.market_hours, MarketHoursManager), "market_hours is not MarketHoursManager instance"

        # Test market hours functionality
        can_trade, reason = terminal.market_hours.can_trade()
        print(f"✅ FNOTerminal initialized successfully")
        print(f"   • Market hours manager: {type(terminal.market_hours).__name__}")
        print(f"   • Trading status: {reason}")

        return True

    except Exception as e:
        print(f"❌ FNOTerminal initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run tests"""
    print("🔧 Testing F&O System Fixes")
    print("=" * 40)

    success = test_fno_terminal_initialization()

    if success:
        print("\n✅ All fixes verified successfully!")
        print("🎯 The F&O system should now work without errors")
    else:
        print("\n❌ Some issues remain")

    return success

if __name__ == "__main__":
    main()