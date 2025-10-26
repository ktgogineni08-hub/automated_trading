#!/usr/bin/env python3
"""
Manual script to save today's trades and positions
Run this to immediately archive today's data
"""

import sys
import os
from datetime import datetime
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.portfolio import UnifiedPortfolio
from fno.terminal import FNOTerminal

def save_today_data():
    """Manually save today's trades and positions"""
    print("="*70)
    print("💾 MANUAL SAVE - Today's Trading Data")
    print("="*70)

    ist = pytz.timezone('Asia/Kolkata')
    today = datetime.now(ist).strftime('%Y-%m-%d')
    print(f"\n📅 Today's date: {today}")

    # Load existing portfolio state
    print("\n1. Loading portfolio state...")
    try:
        portfolio = UnifiedPortfolio(trading_mode='paper', initial_cash=1000000)

        # Try to load from state file
        state_file = "state/current_state.json"
        if os.path.exists(state_file):
            import json
            with open(state_file, 'r') as f:
                state = json.load(f)

            # Restore positions
            if 'positions' in state:
                portfolio.positions = state['positions']

            # Restore trades history
            if 'trades_history' in state:
                portfolio.trades_history = state['trades_history']

            # Restore cash
            if 'cash' in state:
                portfolio.cash = state['cash']

            print(f"✅ Portfolio state loaded")
            print(f"   • Cash: ₹{portfolio.cash:,.2f}")
            print(f"   • Trades in history: {len(portfolio.trades_history)}")
            print(f"   • Active positions: {len(portfolio.positions)}")
        else:
            print("⚠️  No state file found, using fresh portfolio")

    except Exception as e:
        print(f"❌ Error loading portfolio: {e}")
        return False

    # Initialize FNO Terminal
    print("\n2. Initializing FNO Terminal...")
    terminal = FNOTerminal(kite=None, portfolio=portfolio)
    print("✅ FNO Terminal initialized")

    # Perform archival
    print("\n3. Performing end-of-day archival...")
    try:
        terminal._perform_end_of_day_archival()
        print("\n✅ Manual save completed successfully!")
    except Exception as e:
        print(f"\n❌ Manual save failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Verify files were created
    print("\n4. Verifying saved files...")
    year = today[:4]

    # Check trade archive
    trade_file = f"/Users/gogineni/Python/trading-system/trade_archives/{year}/trades_{today}_paper.json"
    if os.path.exists(trade_file):
        size = os.path.getsize(trade_file)
        print(f"✅ Trade archive: {trade_file}")
        print(f"   Size: {size:,} bytes")
    else:
        print(f"ℹ️  Trade archive not created (no trades for {today})")

    # Check backup
    backup_file = f"/Users/gogineni/Python/trading-system/trade_archives_backup/{year}/trades_{today}_paper.json"
    if os.path.exists(backup_file):
        size = os.path.getsize(backup_file)
        print(f"✅ Backup archive: {backup_file}")
        print(f"   Size: {size:,} bytes")

    # Check positions
    positions_file = f"/Users/gogineni/Python/trading-system/saved_trades/fno_positions_{today}.json"
    if os.path.exists(positions_file):
        size = os.path.getsize(positions_file)
        print(f"✅ Positions file: {positions_file}")
        print(f"   Size: {size:,} bytes")
    else:
        print(f"ℹ️  Positions file not created (no open positions for {today})")

    print("\n" + "="*70)
    print("✅ SAVE COMPLETE")
    print("="*70)
    return True

if __name__ == "__main__":
    save_today_data()
