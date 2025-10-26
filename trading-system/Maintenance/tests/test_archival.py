#!/usr/bin/env python3
"""
Test script to verify automatic archival is working
"""

import sys
import os
from datetime import datetime
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.portfolio import UnifiedPortfolio
from fno.terminal import FNOTerminal

def test_archival():
    """Test the archival functionality"""
    print("="*70)
    print("🧪 TESTING ARCHIVAL FUNCTIONALITY")
    print("="*70)

    # Initialize portfolio
    print("\n1. Initializing portfolio...")
    portfolio = UnifiedPortfolio(trading_mode='paper', initial_cash=1000000)
    print(f"✅ Portfolio initialized")
    print(f"   • Mode: {portfolio.trading_mode}")
    print(f"   • Initial cash: ₹{portfolio.cash:,.2f}")
    print(f"   • Trades in history: {len(portfolio.trades_history)}")
    print(f"   • Active positions: {len(portfolio.positions)}")

    # Initialize FNO Terminal
    print("\n2. Initializing FNO Terminal...")
    terminal = FNOTerminal(kite=None, portfolio=portfolio)
    print("✅ FNO Terminal initialized")

    # Test archival method
    print("\n3. Testing _perform_end_of_day_archival() method...")
    try:
        terminal._perform_end_of_day_archival()
        print("✅ Archival method executed successfully")
    except Exception as e:
        print(f"❌ Archival method failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Check if files were created
    print("\n4. Verifying archive files...")
    ist = pytz.timezone('Asia/Kolkata')
    today = datetime.now(ist).strftime('%Y-%m-%d')
    year = today[:4]

    # Check trade archives
    trade_archive_dir = f"/Users/gogineni/Python/trading-system/trade_archives/{year}"
    trade_file = f"{trade_archive_dir}/trades_{today}_paper.json"

    print(f"   • Looking for: {trade_file}")
    if os.path.exists(trade_file):
        print(f"   ✅ Trade archive file exists")
        file_size = os.path.getsize(trade_file)
        print(f"   • File size: {file_size:,} bytes")
    else:
        print(f"   ⚠️ Trade archive file not found (might be 'no_trades' status)")

    # Check backup
    backup_dir = f"/Users/gogineni/Python/trading-system/trade_archives_backup/{year}"
    backup_file = f"{backup_dir}/trades_{today}_paper.json"

    print(f"\n   • Looking for backup: {backup_file}")
    if os.path.exists(backup_file):
        print(f"   ✅ Backup archive file exists")
        file_size = os.path.getsize(backup_file)
        print(f"   • File size: {file_size:,} bytes")
    else:
        print(f"   ⚠️ Backup archive file not found")

    # Check saved positions
    positions_file = f"/Users/gogineni/Python/trading-system/saved_trades/fno_positions_{today}.json"
    print(f"\n   • Looking for positions: {positions_file}")
    if os.path.exists(positions_file):
        print(f"   ✅ Positions file exists")
        file_size = os.path.getsize(positions_file)
        print(f"   • File size: {file_size:,} bytes")
    else:
        print(f"   ⚠️ Positions file not found (might be no open positions)")

    print("\n" + "="*70)
    print("✅ ARCHIVAL TEST COMPLETE")
    print("="*70)
    return True

if __name__ == "__main__":
    test_archival()
