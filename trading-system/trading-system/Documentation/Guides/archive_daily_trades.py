#!/usr/bin/env python3
"""
Automatic Daily Trade Archival Script
Reads trades from dashboard state and saves them to archive
Run this at end of each trading day (3:30 PM IST) via cron or scheduler
"""

import json
import os
import sys
from datetime import datetime
import pytz
import hashlib
from pathlib import Path

def archive_trades_from_dashboard(trading_day: str = None, force: bool = False):
    """
    Archive all trades from dashboard state to JSON archive

    Args:
        trading_day: Date in YYYY-MM-DD format. Defaults to today.
        force: If True, overwrite existing archive

    Returns:
        Dict with status and details
    """

    # Get today's date in IST
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)

    if trading_day is None:
        trading_day = now.strftime('%Y-%m-%d')

    print("=" * 80)
    print("DAILY TRADE ARCHIVAL")
    print("=" * 80)
    print(f"\n📅 Trading Day: {trading_day}")
    print(f"⏰ Archive Time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Check if dashboard state exists
    state_file = Path('state/current_state.json')
    if not state_file.exists():
        print(f"\n❌ Error: Dashboard state file not found: {state_file}")
        return {'status': 'error', 'message': 'Dashboard state file not found'}

    # Read dashboard state
    print(f"\n📂 Reading dashboard state from: {state_file}")
    try:
        with open(state_file, 'r') as f:
            state = json.load(f)
    except Exception as e:
        print(f"❌ Error reading state file: {e}")
        return {'status': 'error', 'message': f'Failed to read state: {e}'}

    # Extract portfolio and trades
    portfolio = state.get('portfolio', {})
    all_trades = portfolio.get('trades_history', [])

    print(f"✅ Loaded {len(all_trades)} total trades from system")

    # Filter trades for today
    today_trades = [t for t in all_trades if t.get('timestamp', '').startswith(trading_day)]

    if len(today_trades) == 0:
        print(f"\n⚠️  No trades found for {trading_day}")
        print("   This may be normal if:")
        print("   1. No trades were executed today")
        print("   2. Market conditions didn't trigger any trades")
        print("   3. System was in standby mode")
        return {'status': 'no_trades', 'message': f'No trades for {trading_day}'}

    print(f"📊 Found {len(today_trades)} trades from {trading_day}")

    # Check if already archived (unless force=True)
    mode = state.get('mode', 'paper')
    year = trading_day[:4]
    month = trading_day[5:7]
    archive_dir = Path('trade_archives') / year / month
    archive_file = archive_dir / f"trades_{trading_day}_{mode}.json"

    if archive_file.exists() and not force:
        print(f"\n✅ Trades already archived: {archive_file}")
        print("   Use --force to overwrite existing archive")
        with open(archive_file, 'r') as f:
            existing = json.load(f)
        print(f"   Existing archive: {existing['data_integrity']['trade_count']} trades")
        print(f"   Total P&L: ₹{existing['daily_summary']['total_pnl']:,.2f}")
        return {'status': 'already_exists', 'file_path': str(archive_file)}

    # Calculate daily summary
    total_pnl = 0
    wins = 0
    losses = 0
    symbols_traded = set()
    sectors = {}

    for trade in today_trades:
        pnl = trade.get('pnl', 0)
        if pnl != 0:  # Only count closed trades
            total_pnl += pnl
            if pnl > 0:
                wins += 1
            else:
                losses += 1

        symbol = trade.get('symbol', '')
        if symbol:
            symbols_traded.add(symbol)

        sector = trade.get('sector', 'Unknown')
        sectors[sector] = sectors.get(sector, 0) + 1

    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

    # Prepare archive data structure
    archive_data = {
        'metadata': {
            'trading_day': trading_day,
            'trading_mode': mode,
            'export_timestamp': now.isoformat(),
            'system_version': '1.0',
            'data_source': 'dashboard_state',
            'archived_by': 'archive_daily_trades.py'
        },
        'daily_summary': {
            'total_trades': len(today_trades),
            'closed_trades': wins + losses,
            'open_trades': len(today_trades) - (wins + losses),
            'total_pnl': round(total_pnl, 2),
            'winning_trades': wins,
            'losing_trades': losses,
            'win_rate': round(win_rate, 2),
            'symbols_traded': sorted(list(symbols_traded)),
            'unique_symbols': len(symbols_traded),
            'sector_distribution': sectors
        },
        'portfolio_state': {
            'opening_cash': portfolio.get('initial_cash', 0),
            'closing_cash': portfolio.get('cash', 0),
            'total_pnl_cumulative': portfolio.get('total_pnl', 0),
            'best_trade': portfolio.get('best_trade', 0),
            'worst_trade': portfolio.get('worst_trade', 0),
            'total_trades_count': portfolio.get('trades_count', 0),
            'winning_trades_total': portfolio.get('winning_trades', 0),
            'losing_trades_total': portfolio.get('losing_trades', 0),
            'open_positions': len(portfolio.get('positions', {}))
        },
        'trades': today_trades,
        'data_integrity': {
            'trade_count': len(today_trades),
            'checksum': hashlib.sha256(
                json.dumps(today_trades, sort_keys=True).encode()
            ).hexdigest()[:16],
            'first_trade_timestamp': today_trades[0]['timestamp'] if today_trades else None,
            'last_trade_timestamp': today_trades[-1]['timestamp'] if today_trades else None
        }
    }

    # Create directory structure
    archive_dir.mkdir(parents=True, exist_ok=True)
    backup_dir = Path('trade_archives_backup') / year / month
    backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📦 Saving archive...")
    print(f"   Directory: {archive_dir}")
    print(f"   Filename: {archive_file.name}")

    # Save main archive (atomic write)
    try:
        temp_file = archive_file.with_suffix('.json.tmp')
        with open(temp_file, 'w') as f:
            json.dump(archive_data, f, indent=2, ensure_ascii=False)
        temp_file.replace(archive_file)
        print(f"✅ Main archive saved: {archive_file}")
    except Exception as e:
        print(f"❌ Failed to save main archive: {e}")
        return {'status': 'error', 'message': f'Save failed: {e}'}

    # Save backup copy
    backup_file = backup_dir / archive_file.name
    try:
        with open(backup_file, 'w') as f:
            json.dump(archive_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Backup created: {backup_file}")
    except Exception as e:
        print(f"⚠️  Backup failed (non-critical): {e}")

    # Verify integrity
    try:
        with open(archive_file, 'r') as f:
            verified = json.load(f)
        if verified['data_integrity']['trade_count'] != len(today_trades):
            raise ValueError("Trade count mismatch")
        print(f"✅ Integrity verified: {len(today_trades)} trades")
    except Exception as e:
        print(f"⚠️  Verification warning: {e}")

    # Print summary
    file_size_kb = archive_file.stat().st_size / 1024

    print(f"\n" + "=" * 80)
    print(f"✅ ARCHIVAL COMPLETE")
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"   Date: {trading_day}")
    print(f"   Mode: {mode}")
    print(f"   Total Trades: {len(today_trades)}")
    print(f"   Closed: {wins + losses} | Open: {len(today_trades) - (wins + losses)}")
    print(f"   Wins: {wins} | Losses: {losses} | Win Rate: {win_rate:.1f}%")
    print(f"   Day P&L: ₹{total_pnl:,.2f}")
    print(f"   Symbols: {len(symbols_traded)}")
    print(f"\n💾 Files:")
    print(f"   Main: {archive_file} ({file_size_kb:.1f} KB)")
    print(f"   Backup: {backup_file}")
    print(f"\n" + "=" * 80)

    return {
        'status': 'success',
        'file_path': str(archive_file),
        'backup_path': str(backup_file),
        'trade_count': len(today_trades),
        'total_pnl': total_pnl
    }


def main():
    """Main entry point for script"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Archive daily trades from trading system dashboard'
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Trading day to archive (YYYY-MM-DD). Defaults to today.'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force overwrite existing archive'
    )

    args = parser.parse_args()

    result = archive_trades_from_dashboard(
        trading_day=args.date,
        force=args.force
    )

    # Exit with appropriate code
    if result['status'] == 'success':
        sys.exit(0)
    elif result['status'] in ['no_trades', 'already_exists']:
        sys.exit(0)  # Not an error
    else:
        sys.exit(1)  # Error


if __name__ == '__main__':
    main()
