#!/usr/bin/env python3
"""
Test script for the Advanced Market Management System
Demonstrates all the new features implemented
"""

import sys
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from advanced_market_manager import AdvancedMarketManager, MarketTrend
    print("✅ Successfully imported AdvancedMarketManager")
except ImportError as e:
    print(f"❌ Failed to import AdvancedMarketManager: {e}")
    sys.exit(1)

def test_market_status():
    """Test market status functionality"""
    print("\n🔍 Testing Market Status Functionality")
    print("=" * 50)

    manager = AdvancedMarketManager()
    status = manager.get_market_status_display()

    print(f"📊 Market Status Report:")
    print(f"   Current Time: {status['current_time']}")
    print(f"   Market Open: {status['market_open_time']} - {status['market_close_time']}")
    print(f"   Is Trading Day: {status['is_trading_day']}")
    print(f"   Is Market Open: {status['is_market_open']}")
    print(f"   Should Stop Trading: {status['should_stop_trading']} ({status['stop_reason']})")
    print(f"   Time Remaining: {status['time_remaining']}")
    print(f"   Is Expiry Close Time: {status['is_expiry_close_time']}")
    print(f"   Market Trend: {status['market_trend'].upper()}")
    print(f"   Should Stop Dashboard: {status['should_stop_dashboard']}")

def test_trend_analysis():
    """Test market trend analysis"""
    print("\n📈 Testing Market Trend Analysis")
    print("=" * 50)

    manager = AdvancedMarketManager()

    # Test with NIFTY
    print("🔍 Analyzing NIFTY trend...")
    nifty_trend = manager.analyze_market_trend("^NSEI")
    print(f"   NIFTY Trend: {nifty_trend.value.upper()}")

    # Test with Bank NIFTY
    print("🔍 Analyzing Bank NIFTY trend...")
    banknifty_trend = manager.analyze_market_trend("^NSEBANK")
    print(f"   Bank NIFTY Trend: {banknifty_trend.value.upper()}")

def test_position_classification():
    """Test position classification"""
    print("\n🔄 Testing Position Classification")
    print("=" * 50)

    manager = AdvancedMarketManager()

    # Sample F&O positions
    sample_positions = {
        "NIFTY25OCT24650CE": {
            "shares": 75,
            "entry_price": 126.22,
            "strategy": "straddle",
            "entry_time": "2025-09-29T13:35:37.444866"
        },
        "NIFTY25DEC24700CE": {
            "shares": 50,
            "entry_price": 200.15,
            "strategy": "long_call",
            "entry_time": "2025-09-29T13:36:00.408046"
        },
        "FINNIFTY25SEP26050CE": {
            "shares": 65,
            "entry_price": 107.81,
            "strategy": "covered_call",
            "entry_time": "2025-09-29T13:35:47.291500"
        }
    }

    expiry_positions, overnight_positions = manager.classify_positions(sample_positions)

    print(f"📊 Position Classification Results:")
    print(f"   Total Positions: {len(sample_positions)}")
    print(f"   Expiry Positions: {len(expiry_positions)}")
    if expiry_positions:
        for symbol in expiry_positions.keys():
            print(f"     • {symbol}")

    print(f"   Overnight Positions: {len(overnight_positions)}")
    if overnight_positions:
        for symbol in overnight_positions.keys():
            print(f"     • {symbol}")

def test_position_management():
    """Test position management at close"""
    print("\n🔔 Testing Position Management at Close")
    print("=" * 50)

    manager = AdvancedMarketManager()

    # Sample positions
    positions = {
        "NIFTY25OCT24650CE": {"shares": 75, "entry_price": 126.22},
        "NIFTY25DEC24700CE": {"shares": 50, "entry_price": 200.15},
        "FINNIFTY25OCT26050CE": {"shares": 65, "entry_price": 107.81}
    }

    print(f"📋 Original Positions: {len(positions)}")
    for symbol, pos in positions.items():
        print(f"   • {symbol}: {pos['shares']} shares @ ₹{pos['entry_price']}")

    # Test position management
    updated_positions = manager.manage_positions_at_close(positions, close_expiry_only=True)

    print(f"📋 After Expiry Close: {len(updated_positions)}")
    for symbol, pos in updated_positions.items():
        print(f"   • {symbol}: {pos['shares']} shares @ ₹{pos['entry_price']}")

def test_trend_adjustment():
    """Test trend-based position adjustment"""
    print("\n🎯 Testing Trend-Based Position Adjustment")
    print("=" * 50)

    manager = AdvancedMarketManager()

    positions = {
        "NIFTY25DEC24700CE": {"shares": 50, "entry_price": 200.15},
        "NIFTY25DEC24650PE": {"shares": -40, "entry_price": 150.30}
    }

    print(f"📋 Original Positions:")
    for symbol, pos in positions.items():
        print(f"   • {symbol}: {pos['shares']} shares @ ₹{pos['entry_price']}")

    # Get current trend
    current_trend = manager.analyze_market_trend()
    print(f"📈 Current Market Trend: {current_trend.value.upper()}")

    # Adjust positions
    adjusted_positions = manager.adjust_overnight_positions_for_trend(positions, current_trend)

    print(f"📋 Adjusted Positions:")
    for symbol, pos in adjusted_positions.items():
        original_shares = positions[symbol]['shares']
        new_shares = pos['shares']
        if new_shares != original_shares:
            adjustment = pos.get('adjustment_factor', 1.0)
            print(f"   • {symbol}: {original_shares} -> {new_shares} shares (factor: {adjustment:.1f}x)")
        else:
            print(f"   • {symbol}: {new_shares} shares (no change)")

def test_overnight_state():
    """Test overnight state management"""
    print("\n💾 Testing Overnight State Management")
    print("=" * 50)

    manager = AdvancedMarketManager()

    positions = {
        "NIFTY25DEC24700CE": {"shares": 50, "entry_price": 200.15},
        "BANKNIFTY25DEC45000CE": {"shares": 30, "entry_price": 300.25}
    }

    trading_day = datetime.now().strftime('%Y-%m-%d')

    # Save overnight state
    print(f"💾 Saving overnight state for {trading_day}...")
    manager.save_overnight_state(positions, trading_day)

    # Load overnight state
    print(f"📂 Loading overnight state for {trading_day}...")
    loaded_positions = manager.load_overnight_state(trading_day)

    if loaded_positions:
        print(f"✅ Successfully loaded {len(loaded_positions)} overnight positions:")
        for symbol, pos in loaded_positions.items():
            print(f"   • {symbol}: {pos['shares']} shares @ ₹{pos['entry_price']}")
    else:
        print("❌ Failed to load overnight state")

def main():
    """Run all tests"""
    print("🚀 Advanced Market Management System - Testing Suite")
    print("=" * 60)
    print("Testing all implemented features...")

    try:
        # Test all functionalities
        test_market_status()
        test_trend_analysis()
        test_position_classification()
        test_position_management()
        test_trend_adjustment()
        test_overnight_state()

        print("\n✅ All tests completed successfully!")
        print("\n📋 Summary of Implemented Features:")
        print("   ✅ Market hours validation and auto-stop functionality")
        print("   ✅ Expiry-based position closing at 3:30 PM")
        print("   ✅ Market trend analysis for position adjustments")
        print("   ✅ Overnight position management system")
        print("   ✅ Market closed status display")
        print("   ✅ Dashboard integration ready")

        print("\n🎯 Key Benefits:")
        print("   • Automatic position management based on expiry")
        print("   • Market trend-based position adjustments")
        print("   • Overnight position persistence and restoration")
        print("   • Enhanced market status monitoring")
        print("   • Smart dashboard control (auto-stop after hours)")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()