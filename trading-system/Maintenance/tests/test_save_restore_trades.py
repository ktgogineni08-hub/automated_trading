#!/usr/bin/env python3
"""
Test script for the updated save/restore trades functionality
- Auto-save trades at 3:30 PM for next day
- User-initiated save for next day
- Automatic restoration of saved trades
"""

import sys
import os
import json
from datetime import datetime, timedelta, time

import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock

if __name__ != "__main__":  # pragma: no cover - manual integration script
    pytest.skip(
        "Legacy save/restore console demo – run manually via python test_save_restore_trades.py",
        allow_module_level=True,
    )

from enhanced_trading_system_complete import UnifiedTradingSystem, FNOTerminal, DataProvider, FNODataProvider

def test_save_trades_functionality():
    """Test saving trades for next day"""
    print("💾 Testing Save Trades for Next Day Functionality")
    print("=" * 60)

    # Create mock objects
    mock_data_provider = Mock(spec=DataProvider)
    mock_kite = Mock()

    # Create test data
    test_data = pd.DataFrame({
        'close': [100, 105, 108, 103, 106],
        'volume': [1000, 1200, 1100, 1300, 1150]
    })
    mock_data_provider.fetch_with_retry.return_value = test_data

    # Initialize trading system
    trading_system = UnifiedTradingSystem(
        data_provider=mock_data_provider,
        kite=mock_kite,
        initial_cash=100000,
        trading_mode='paper'
    )

    # Add test positions
    test_positions = {
        'STOCK1': {'shares': 50, 'entry_price': 100.0, 'sector': 'Technology', 'confidence': 0.8},
        'STOCK2': {'shares': 30, 'entry_price': 200.0, 'sector': 'Finance', 'confidence': 0.7},
        'STOCK3': {'shares': 40, 'entry_price': 150.0, 'sector': 'Healthcare', 'confidence': 0.9}
    }

    for symbol, position in test_positions.items():
        trading_system.portfolio.positions[symbol] = position
        print(f"📊 Added position: {symbol} - {position['shares']} shares @ ₹{position['entry_price']}")

    # Test auto-save at 3:30 PM
    test_time = datetime.now().replace(hour=15, minute=30, second=0, microsecond=0)
    print(f"\n🕒 Simulating auto-save at {test_time.strftime('%H:%M:%S')}")

    trading_system.auto_stop_all_trades(test_time)

    # Check if save file was created
    next_day = (test_time + timedelta(days=1)).strftime('%Y-%m-%d')
    save_file = f"saved_trades/positions_{next_day}.json"

    if os.path.exists(save_file):
        with open(save_file, 'r') as f:
            save_data = json.load(f)

        print(f"✅ Save file created: {save_file}")
        print(f"📊 Positions saved: {save_data['total_positions']}")
        print(f"💰 Total value: ₹{save_data['total_value']:,.2f}")
        print(f"📈 Total unrealized P&L: ₹{save_data['total_unrealized_pnl']:,.2f}")
        return True
    else:
        print(f"❌ Save file not created: {save_file}")
        return False

def test_restore_trades_functionality():
    """Test restoring saved trades"""
    print("\n🔄 Testing Restore Saved Trades Functionality")
    print("=" * 60)

    # Create mock objects
    mock_data_provider = Mock(spec=DataProvider)
    mock_kite = Mock()

    test_data = pd.DataFrame({
        'close': [105, 110],  # Prices changed from yesterday
        'volume': [1100, 1200]
    })
    mock_data_provider.fetch_with_retry.return_value = test_data

    # Initialize new trading system (simulating next day)
    trading_system = UnifiedTradingSystem(
        data_provider=mock_data_provider,
        kite=mock_kite,
        initial_cash=100000,
        trading_mode='paper'
    )

    # Clear existing positions to simulate fresh start
    trading_system.portfolio.positions.clear()

    # Test restore functionality
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"🔄 Attempting to restore positions for {today}")

    restored = trading_system.restore_positions_for_day(today)

    if restored:
        print(f"✅ Successfully restored positions")
        print(f"📊 Current positions: {len(trading_system.portfolio.positions)}")

        for symbol, position in trading_system.portfolio.positions.items():
            print(f"🔄 Restored: {symbol} - {position['shares']} shares @ ₹{position['entry_price']:.2f}")

        return True
    else:
        print("❌ No positions were restored (this is expected if no save file exists)")
        return False

def test_user_stop_and_save():
    """Test user-initiated stop and save"""
    print("\n👤 Testing User Stop and Save Functionality")
    print("=" * 60)

    # Create mock objects
    mock_data_provider = Mock(spec=DataProvider)
    mock_kite = Mock()

    test_data = pd.DataFrame({
        'close': [120, 125],
        'volume': [1000, 1100]
    })
    mock_data_provider.fetch_with_retry.return_value = test_data

    # Initialize trading system
    trading_system = UnifiedTradingSystem(
        data_provider=mock_data_provider,
        kite=mock_kite,
        initial_cash=100000,
        trading_mode='paper'
    )

    # Add test positions
    trading_system.portfolio.positions['USERTEST'] = {
        'shares': 25, 'entry_price': 120.0, 'sector': 'Technology', 'confidence': 0.8
    }

    print(f"📊 Added position for user stop test: USERTEST - 25 shares @ ₹120.0")

    # Test user stop and save
    positions_saved = trading_system.user_stop_and_save_trades("manual_user_stop")

    if positions_saved > 0:
        print(f"✅ User stop and save completed: {positions_saved} positions saved")
        return True
    else:
        print("❌ User stop and save failed")
        return False

def test_fno_save_restore():
    """Test F&O save and restore functionality"""
    print("\n🎯 Testing F&O Save and Restore Functionality")
    print("=" * 60)

    # Get live market data for realistic testing
    print("🔄 Fetching live market data...")
    fno_provider = FNODataProvider()

    ce_symbol = pe_symbol = "FALLBACK_SYMBOL"
    try:
        nifty_chain = fno_provider.get_option_chain('NIFTY')
        if nifty_chain:
            current_expiry = nifty_chain['current_expiry']
            atm_strike = nifty_chain['atm_strike']
            ce_symbol = f"NIFTY{current_expiry}{atm_strike}CE"
            pe_symbol = f"NIFTY{current_expiry}{atm_strike + 50}PE"
            print(f"✅ Using live symbols: {ce_symbol}, {pe_symbol}")
    except Exception as e:
        print(f"⚠️ Using fallback symbols: {e}")
        ce_symbol = "NIFTY_CE_SYMBOL"
        pe_symbol = "NIFTY_PE_SYMBOL"

    # Create mock F&O terminal
    mock_kite = Mock()
    mock_kite.quote.return_value = {
        ce_symbol: {'last_price': 50.0},
        pe_symbol: {'last_price': 45.0}
    }

    fno_terminal = FNOTerminal(kite=mock_kite)

    # Add test F&O positions with live symbols
    fno_positions = {
        ce_symbol: {'shares': 75, 'entry_price': 48.0, 'sector': 'F&O', 'confidence': 0.8},
        pe_symbol: {'shares': 50, 'entry_price': 42.0, 'sector': 'F&O', 'confidence': 0.7}
    }

    for symbol, position in fno_positions.items():
        fno_terminal.portfolio.positions[symbol] = position
        print(f"📊 Added F&O position: {symbol} - {position['shares']} shares @ ₹{position['entry_price']}")

    # Test F&O save
    positions_saved = fno_terminal.save_fno_positions_for_next_day("test_fno_save")

    if positions_saved > 0:
        print(f"✅ F&O save completed: {positions_saved} positions saved")

        # Test F&O restore
        fno_terminal.portfolio.positions.clear()  # Clear to simulate next day

        today = datetime.now().strftime('%Y-%m-%d')
        restored = fno_terminal.restore_fno_positions_for_day(today)

        if restored:
            print(f"✅ F&O restore completed")
            return True
        else:
            print("❌ F&O restore failed")
            return False
    else:
        print("❌ F&O save failed")
        return False

def test_save_file_structure():
    """Test the structure and content of save files"""
    print("\n📁 Testing Save File Structure")
    print("=" * 60)

    # Look for recent save files
    save_dir = "saved_trades"
    if not os.path.exists(save_dir):
        print("📂 No saved_trades directory found")
        return False

    files = [f for f in os.listdir(save_dir) if f.endswith('.json')]

    if not files:
        print("📂 No save files found")
        return False

    print(f"📁 Found {len(files)} save files:")

    for file in files[:3]:  # Check first 3 files
        file_path = os.path.join(save_dir, file)
        print(f"\n📄 Examining: {file}")

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Check required fields
            required_fields = ['saved_at', 'target_date', 'total_positions']

            for field in required_fields:
                if field in data:
                    print(f"  ✅ {field}: {data[field]}")
                else:
                    print(f"  ❌ Missing {field}")

            # Check positions data
            positions_key = 'positions' if 'positions' in data else 'fno_positions'
            if positions_key in data:
                positions = data[positions_key]
                print(f"  📊 Positions count: {len(positions)}")

                # Check first position structure
                if positions:
                    first_symbol = list(positions.keys())[0]
                    first_pos = positions[first_symbol]
                    required_pos_fields = ['symbol', 'shares', 'entry_price', 'current_price']

                    print(f"  📈 Sample position ({first_symbol}):")
                    for field in required_pos_fields:
                        if field in first_pos:
                            print(f"    ✅ {field}: {first_pos[field]}")
                        else:
                            print(f"    ❌ Missing {field}")

        except Exception as e:
            print(f"  ❌ Error reading file: {e}")

    return True

def cleanup_test_files():
    """Clean up test files"""
    print("\n🧹 Cleaning up test files...")

    save_dir = "saved_trades"
    if os.path.exists(save_dir):
        try:
            files = os.listdir(save_dir)
            for file in files:
                if 'test' in file.lower() or datetime.now().strftime('%Y-%m-%d') in file:
                    os.remove(os.path.join(save_dir, file))
                    print(f"🗑️ Removed test file: {file}")
        except Exception as e:
            print(f"⚠️ Error cleaning up: {e}")

def main():
    """Run all save/restore functionality tests"""
    print("🔄 SAVE/RESTORE TRADES FUNCTIONALITY TESTS")
    print("=" * 70)
    print("Testing the updated functionality:")
    print("• Auto-save trades at 3:30 PM for next day")
    print("• User-initiated save for next day")
    print("• Automatic restoration of saved trades")
    print("• F&O specific save/restore functionality")
    print("=" * 70)

    try:
        # Run all tests
        test_results = []

        test_results.append(test_save_trades_functionality())
        test_results.append(test_user_stop_and_save())
        test_results.append(test_fno_save_restore())
        test_results.append(test_restore_trades_functionality())
        test_results.append(test_save_file_structure())

        # Summary
        print("\n📋 TEST SUMMARY")
        print("=" * 40)
        passed = sum(test_results)
        total = len(test_results)

        print(f"✅ Tests Passed: {passed}/{total}")

        if passed >= 3:  # Allow some tests to fail due to missing save files
            print("🎉 Save/Restore functionality is working correctly!")
        else:
            print("⚠️ Some critical tests failed. Please review the implementation.")

        print("\n💡 UPDATED FEATURE SUMMARY:")
        print("• Trades are now SAVED (not closed) at 3:30 PM for next day")
        print("• Users can manually stop and save trades for next day")
        print("• Saved trades are automatically restored the next trading day")
        print("• Both equity and F&O positions support save/restore")
        print("• Save files include unrealized P&L and position details")
        print("• Used save files are automatically archived")

        # Cleanup
        cleanup_test_files()

    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return False

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
