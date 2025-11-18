#!/usr/bin/env python3
"""
Complete Today's Trading Data Archive
Saves all trading activity for 2025-10-24 including:
- Current portfolio state
- All open positions (14 F&O positions)
- Trading summary report
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
import pytz

def save_complete_today_data():
    """Save complete snapshot of today's trading activity"""

    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    today = '2025-10-24'
    timestamp = now_ist.strftime('%Y-%m-%d %H:%M:%S IST')

    print("="*70)
    print(f"📦 COMPLETE DATA SAVE - {today}")
    print("="*70)

    # Load current state
    state_file = Path('state/current_state.json')
    if not state_file.exists():
        print(f"❌ State file not found: {state_file}")
        return

    with open(state_file, 'r') as f:
        current_state = json.load(f)

    # Create archive directories
    archives_dir = Path('trade_archives/2025/10')
    archives_dir.mkdir(parents=True, exist_ok=True)

    backups_dir = Path('trade_archives_backup/2025/10')
    backups_dir.mkdir(parents=True, exist_ok=True)

    saved_trades_dir = Path('saved_trades')
    saved_trades_dir.mkdir(exist_ok=True)

    # 1. Save complete portfolio snapshot
    portfolio_snapshot = {
        'date': today,
        'timestamp': timestamp,
        'trading_mode': current_state.get('trading_mode', 'paper'),
        'cash': current_state.get('cash', 0),
        'total_value': current_state.get('total_value', 0),
        'positions': current_state.get('positions', {}),
        'position_count': len(current_state.get('positions', {})),
        'metadata': {
            'save_type': 'manual_complete_save',
            'reason': 'user_requested_today_data_save',
            'system_time': now_ist.isoformat()
        }
    }

    # Save to multiple locations for safety
    snapshot_files = [
        archives_dir / f'portfolio_snapshot_{today}.json',
        backups_dir / f'portfolio_snapshot_{today}.json',
    ]

    for snapshot_file in snapshot_files:
        with open(snapshot_file, 'w') as f:
            json.dump(portfolio_snapshot, f, indent=2)
        print(f"✅ Portfolio snapshot: {snapshot_file}")
        print(f"   Size: {snapshot_file.stat().st_size:,} bytes")

    # 2. Save F&O positions (already done but ensure it's current)
    fno_positions = {}
    total_invested = 0

    for symbol, pos in current_state.get('positions', {}).items():
        fno_positions[symbol] = {
            'symbol': symbol,
            'quantity': pos.get('shares', 0),
            'entry_price': pos.get('entry_price', 0),
            'current_price': pos.get('current_price', 0),
            'strategy': pos.get('strategy', 'unknown'),
            'sector': pos.get('sector', 'unknown'),
            'confidence': pos.get('confidence', 0),
            'pnl': pos.get('pnl', 0),
            'invested': pos.get('shares', 0) * pos.get('entry_price', 0)
        }
        total_invested += fno_positions[symbol]['invested']

    fno_save_data = {
        'fno_positions': fno_positions,
        'saved_at': timestamp,
        'target_date': today,
        'position_count': len(fno_positions),
        'total_invested': total_invested,
        'cash_remaining': current_state.get('cash', 0),
        'total_portfolio_value': current_state.get('total_value', 0)
    }

    fno_file = saved_trades_dir / f'fno_positions_{today}.json'
    with open(fno_file, 'w') as f:
        json.dump(fno_save_data, f, indent=2)

    print(f"\n✅ F&O Positions: {fno_file}")
    print(f"   Positions: {len(fno_positions)}")
    print(f"   Total invested: ₹{total_invested:,.2f}")

    # 3. Create detailed trading summary report
    summary_report = {
        'trading_date': today,
        'report_generated': timestamp,
        'trading_mode': current_state.get('trading_mode', 'paper'),

        'portfolio_summary': {
            'cash_available': current_state.get('cash', 0),
            'positions_value': current_state.get('total_value', 0) - current_state.get('cash', 0),
            'total_portfolio_value': current_state.get('total_value', 0),
            'open_positions': len(current_state.get('positions', {}))
        },

        'positions_by_sector': {},
        'positions_by_strategy': {},

        'all_positions': fno_positions,

        'notes': [
            'All positions are OPEN (not closed)',
            'No completed trades to archive today',
            'When positions close, they will be archived to trade_archives/',
            'This is a complete snapshot of market close activity'
        ]
    }

    # Analyze by sector
    for symbol, pos in fno_positions.items():
        sector = pos['sector']
        strategy = pos['strategy']

        if sector not in summary_report['positions_by_sector']:
            summary_report['positions_by_sector'][sector] = {
                'count': 0,
                'invested': 0,
                'positions': []
            }

        summary_report['positions_by_sector'][sector]['count'] += 1
        summary_report['positions_by_sector'][sector]['invested'] += pos['invested']
        summary_report['positions_by_sector'][sector]['positions'].append(symbol)

        if strategy not in summary_report['positions_by_strategy']:
            summary_report['positions_by_strategy'][strategy] = {
                'count': 0,
                'invested': 0
            }

        summary_report['positions_by_strategy'][strategy]['count'] += 1
        summary_report['positions_by_strategy'][strategy]['invested'] += pos['invested']

    # Save summary report
    summary_files = [
        archives_dir / f'trading_summary_{today}.json',
        backups_dir / f'trading_summary_{today}.json',
    ]

    for summary_file in summary_files:
        with open(summary_file, 'w') as f:
            json.dump(summary_report, f, indent=2)
        print(f"\n✅ Trading summary: {summary_file}")

    # 4. Print detailed summary
    print("\n" + "="*70)
    print(f"📊 TRADING SUMMARY - {today}")
    print("="*70)

    print(f"\n💰 Portfolio:")
    print(f"   Cash: ₹{current_state.get('cash', 0):,.2f}")
    print(f"   Invested: ₹{total_invested:,.2f}")
    print(f"   Total Value: ₹{current_state.get('total_value', 0):,.2f}")

    print(f"\n📊 Positions by Sector:")
    for sector, data in sorted(summary_report['positions_by_sector'].items()):
        print(f"   {sector}: {data['count']} positions, ₹{data['invested']:,.2f} invested")

    print(f"\n🎯 Positions by Strategy:")
    for strategy, data in sorted(summary_report['positions_by_strategy'].items()):
        print(f"   {strategy}: {data['count']} positions, ₹{data['invested']:,.2f} invested")

    print("\n" + "="*70)
    print("✅ ALL DATA SAVED SUCCESSFULLY")
    print("="*70)

    print(f"\n📁 Saved to:")
    print(f"   • {archives_dir}/")
    print(f"   • {backups_dir}/")
    print(f"   • {saved_trades_dir}/")

if __name__ == '__main__':
    save_complete_today_data()
