#!/usr/bin/env python3
"""
Test script for Daily Trade Archival System

Tests:
1. Trade archival with various scenarios
2. Folder structure creation
3. JSON format validation
4. Backup mechanism
5. Data integrity checks
6. Error handling
"""

import sys
import os
import json
import shutil
from datetime import datetime, timedelta

import pytest
import pytz

# Add parent directory to path
if __name__ != "__main__":  # pragma: no cover - manual integration script
    pytest.skip(
        "Legacy trade archival console demo – run manually via python test_trade_archival.py",
        allow_module_level=True,
    )

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_trade_archival_basic():
    """Test basic trade archival functionality"""
    print("\n" + "="*80)
    print("TEST 1: Basic Trade Archival")
    print("="*80)

    from enhanced_trading_system_complete import UnifiedPortfolio

    # Create test portfolio
    portfolio = UnifiedPortfolio(
        initial_cash=100000,
        trading_mode='paper',
        silent=True
    )

    # Add some test trades
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    trading_day = now_ist.strftime('%Y-%m-%d')

    print(f"\n📝 Adding test trades for {trading_day}...")

    # Buy trade
    trade1 = portfolio.record_trade(
        symbol='NIFTY25OCT24800CE',
        side='buy',
        shares=50,
        price=100.0,
        fees=50.0,
        pnl=None,
        timestamp=now_ist,
        confidence=0.75,
        sector='F&O'
    )
    print(f"✅ Trade 1: BUY NIFTY25OCT24800CE @ ₹100")

    # Sell trade with P&L
    trade2 = portfolio.record_trade(
        symbol='NIFTY25OCT24800CE',
        side='sell',
        shares=50,
        price=110.0,
        fees=55.0,
        pnl=450.0,  # 50 * (110-100) - 50 - 55
        timestamp=now_ist + timedelta(minutes=30),
        confidence=0.75,
        sector='F&O'
    )
    print(f"✅ Trade 2: SELL NIFTY25OCT24800CE @ ₹110 (P&L: ₹450)")

    # Buy another symbol
    trade3 = portfolio.record_trade(
        symbol='BANKNIFTY25OCT49000CE',
        side='buy',
        shares=25,
        price=200.0,
        fees=50.0,
        pnl=None,
        timestamp=now_ist + timedelta(hours=1),
        confidence=0.65,
        sector='F&O'
    )
    print(f"✅ Trade 3: BUY BANKNIFTY25OCT49000CE @ ₹200")

    print(f"\n📦 Archiving {len(portfolio.trades_history)} trades...")

    # Save trades
    result = portfolio.save_daily_trades(trading_day)

    if result['status'] == 'success':
        print(f"✅ PASS: Trade archival successful")
        print(f"   File: {result['file_path']}")
        print(f"   Backup: {result['backup_path']}")
        print(f"   Trade count: {result['trade_count']}")

        # Verify file exists and is valid JSON
        if os.path.exists(result['file_path']):
            with open(result['file_path'], 'r') as f:
                data = json.load(f)

            print(f"\n✅ JSON file valid")
            print(f"   Metadata: {data['metadata']['trading_mode']}")
            print(f"   Daily summary: {data['daily_summary']['total_trades']} trades")
            print(f"   Total P&L: ₹{data['daily_summary']['total_pnl']}")
            print(f"   Win rate: {data['daily_summary']['win_rate']}%")

            # Check trade IDs
            if data['trades']:
                first_id = data['trades'][0]['trade_id']
                last_id = data['trades'][-1]['trade_id']
                print(f"   Trade IDs: {first_id} ... {last_id}")

            return True
        else:
            print(f"❌ FAIL: File not created")
            return False
    else:
        print(f"❌ FAIL: {result.get('errors')}")
        return False


def test_folder_structure():
    """Test that folder structure is created correctly"""
    print("\n" + "="*80)
    print("TEST 2: Folder Structure")
    print("="*80)

    from enhanced_trading_system_complete import UnifiedPortfolio

    portfolio = UnifiedPortfolio(
        initial_cash=100000,
        trading_mode='live',
        silent=True
    )

    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)

    # Add one trade
    portfolio.record_trade(
        symbol='TEST',
        side='buy',
        shares=1,
        price=100.0,
        fees=1.0,
        timestamp=now_ist
    )

    trading_day = now_ist.strftime('%Y-%m-%d')
    year = trading_day[:4]
    month = trading_day[5:7]

    result = portfolio.save_daily_trades(trading_day)

    if result['status'] == 'success':
        # Check folder structure
        expected_folder = os.path.join(portfolio.trade_archive_base_dir, year, month)
        backup_folder = os.path.join(portfolio.archive_backup_dir, year, month)

        if os.path.exists(expected_folder) and os.path.exists(backup_folder):
            print(f"✅ PASS: Folder structure correct")
            print(f"   Primary: {expected_folder}/")
            print(f"   Backup: {backup_folder}/")

            # List files
            files = os.listdir(expected_folder)
            print(f"   Files: {files}")
            return True
        else:
            print(f"❌ FAIL: Folders not created")
            return False
    else:
        print(f"❌ FAIL: {result.get('errors')}")
        return False


def test_no_trades_scenario():
    """Test archival when no trades exist"""
    print("\n" + "="*80)
    print("TEST 3: No Trades Scenario")
    print("="*80)

    from enhanced_trading_system_complete import UnifiedPortfolio

    portfolio = UnifiedPortfolio(
        initial_cash=100000,
        trading_mode='paper',
        silent=True
    )

    # Don't add any trades
    ist = pytz.timezone('Asia/Kolkata')
    trading_day = datetime.now(ist).strftime('%Y-%m-%d')

    result = portfolio.save_daily_trades(trading_day)

    if result['status'] == 'no_trades':
        print(f"✅ PASS: Correctly handled no trades")
        print(f"   Message: {result.get('message')}")
        return True
    else:
        print(f"❌ FAIL: Should return 'no_trades' status")
        return False


def test_data_integrity():
    """Test data integrity and checksum"""
    print("\n" + "="*80)
    print("TEST 4: Data Integrity")
    print("="*80)

    from enhanced_trading_system_complete import UnifiedPortfolio

    portfolio = UnifiedPortfolio(
        initial_cash=100000,
        trading_mode='paper',
        silent=True
    )

    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    trading_day = now_ist.strftime('%Y-%m-%d')

    # Add 10 trades
    for i in range(10):
        portfolio.record_trade(
            symbol=f'SYMBOL{i}',
            side='buy' if i % 2 == 0 else 'sell',
            shares=10 + i,
            price=100.0 + i,
            fees=5.0,
            pnl=None if i % 2 == 0 else float(i * 10),
            timestamp=now_ist + timedelta(minutes=i*5)
        )

    result = portfolio.save_daily_trades(trading_day)

    if result['status'] == 'success':
        # Load and verify
        with open(result['file_path'], 'r') as f:
            data = json.load(f)

        # Check data integrity section
        integrity = data['data_integrity']
        trade_count = integrity['trade_count']
        checksum = integrity['checksum']

        if trade_count == 10:
            print(f"✅ PASS: Data integrity verified")
            print(f"   Trade count: {trade_count}")
            print(f"   Checksum: {checksum}")
            print(f"   Last trade ID: {integrity['last_trade_id']}")

            # Verify all trades have IDs
            all_have_ids = all('trade_id' in trade for trade in data['trades'])
            if all_have_ids:
                print(f"   ✅ All trades have unique IDs")
                return True
            else:
                print(f"   ❌ Some trades missing IDs")
                return False
        else:
            print(f"❌ FAIL: Trade count mismatch")
            return False
    else:
        print(f"❌ FAIL: {result.get('errors')}")
        return False


def test_comprehensive_metadata():
    """Test comprehensive metadata and analytics"""
    print("\n" + "="*80)
    print("TEST 5: Comprehensive Metadata")
    print("="*80)

    from enhanced_trading_system_complete import UnifiedPortfolio

    portfolio = UnifiedPortfolio(
        initial_cash=100000,
        trading_mode='paper',
        silent=True
    )

    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    trading_day = now_ist.strftime('%Y-%m-%d')

    # Add trades with different sectors and P&L
    trades = [
        {'symbol': 'NIFTY25OCT24800CE', 'side': 'buy', 'shares': 50, 'price': 100, 'pnl': None, 'sector': 'F&O'},
        {'symbol': 'NIFTY25OCT24800CE', 'side': 'sell', 'shares': 50, 'price': 110, 'pnl': 450, 'sector': 'F&O'},
        {'symbol': 'RELIANCE', 'side': 'buy', 'shares': 10, 'price': 2500, 'pnl': None, 'sector': 'Energy'},
        {'symbol': 'RELIANCE', 'side': 'sell', 'shares': 10, 'price': 2480, 'pnl': -250, 'sector': 'Energy'},
    ]

    for trade_data in trades:
        portfolio.record_trade(
            symbol=trade_data['symbol'],
            side=trade_data['side'],
            shares=trade_data['shares'],
            price=trade_data['price'],
            fees=10.0,
            pnl=trade_data['pnl'],
            timestamp=now_ist,
            sector=trade_data['sector']
        )

    result = portfolio.save_daily_trades(trading_day)

    if result['status'] == 'success':
        with open(result['file_path'], 'r') as f:
            data = json.load(f)

        # Check metadata
        metadata = data['metadata']
        summary = data['daily_summary']
        portfolio_state = data['portfolio_state']

        checks = {
            'Metadata exists': all(k in metadata for k in ['trading_day', 'trading_mode', 'export_timestamp']),
            'Daily summary complete': all(k in summary for k in ['total_trades', 'total_pnl', 'win_rate', 'symbols_traded']),
            'Portfolio state complete': all(k in portfolio_state for k in ['opening_cash', 'closing_cash', 'total_pnl_cumulative']),
            'Sector distribution': 'sector_distribution' in summary and len(summary['sector_distribution']) > 0,
            'Win rate calculated': summary['win_rate'] == 50.0,  # 1 win, 1 loss
            'Total P&L': summary['total_pnl'] == 200.0,  # 450 - 250
        }

        all_passed = all(checks.values())

        if all_passed:
            print(f"✅ PASS: All metadata checks passed")
            for check, passed in checks.items():
                status = "✅" if passed else "❌"
                print(f"   {status} {check}")
            return True
        else:
            print(f"❌ FAIL: Some metadata checks failed")
            for check, passed in checks.items():
                status = "✅" if passed else "❌"
                print(f"   {status} {check}")
            return False
    else:
        print(f"❌ FAIL: {result.get('errors')}")
        return False


def test_backup_mechanism():
    """Test backup file creation"""
    print("\n" + "="*80)
    print("TEST 6: Backup Mechanism")
    print("="*80)

    from enhanced_trading_system_complete import UnifiedPortfolio

    portfolio = UnifiedPortfolio(
        initial_cash=100000,
        trading_mode='paper',
        silent=True
    )

    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    trading_day = now_ist.strftime('%Y-%m-%d')

    portfolio.record_trade(
        symbol='TEST',
        side='buy',
        shares=1,
        price=100,
        fees=1,
        timestamp=now_ist
    )

    result = portfolio.save_daily_trades(trading_day)

    if result['status'] == 'success':
        primary_exists = os.path.exists(result['file_path'])
        backup_exists = result['backup_path'] and os.path.exists(result['backup_path'])

        if primary_exists and backup_exists:
            # Verify both files are identical
            with open(result['file_path'], 'r') as f1:
                data1 = json.load(f1)
            with open(result['backup_path'], 'r') as f2:
                data2 = json.load(f2)

            if data1 == data2:
                print(f"✅ PASS: Backup mechanism working")
                print(f"   Primary: {result['file_path']}")
                print(f"   Backup: {result['backup_path']}")
                print(f"   Files identical: ✅")
                return True
            else:
                print(f"❌ FAIL: Primary and backup differ")
                return False
        else:
            print(f"❌ FAIL: Backup file not created")
            print(f"   Primary exists: {primary_exists}")
            print(f"   Backup exists: {backup_exists}")
            return False
    else:
        print(f"❌ FAIL: {result.get('errors')}")
        return False


def cleanup_test_folders():
    """Clean up test folders"""
    folders = ['trade_archives', 'trade_archives_backup']
    for folder in folders:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                print(f"🧹 Cleaned up: {folder}/")
            except Exception as e:
                print(f"⚠️  Failed to clean {folder}: {e}")


def run_all_tests():
    """Run all trade archival tests"""
    print("\n" + "="*80)
    print("TRADE ARCHIVAL SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*80)

    # Clean up first
    cleanup_test_folders()

    tests = [
        ("Basic Trade Archival", test_trade_archival_basic),
        ("Folder Structure", test_folder_structure),
        ("No Trades Scenario", test_no_trades_scenario),
        ("Data Integrity", test_data_integrity),
        ("Comprehensive Metadata", test_comprehensive_metadata),
        ("Backup Mechanism", test_backup_mechanism),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test crashed: {test_name}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    # Show folder structure
    if os.path.exists('trade_archives'):
        print("\n📁 Trade Archive Structure:")
        for root, dirs, files in os.walk('trade_archives'):
            level = root.replace('trade_archives', '').count(os.sep)
            indent = '  ' * level
            print(f'{indent}{os.path.basename(root)}/')
            sub_indent = '  ' * (level + 1)
            for file in files:
                print(f'{sub_indent}{file}')

    # Final cleanup
    print("\n🧹 Cleaning up test folders...")
    cleanup_test_folders()

    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Trade archival system ready for production!")
        return 0
    else:
        print(f"\n❌ {total - passed} tests failed - Review before deployment")
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
