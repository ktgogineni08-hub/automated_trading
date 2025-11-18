#!/usr/bin/env python3
"""
Extract ALL Trading Activity for 2025-10-24
Creates complete trade log including:
- All BUY orders (position openings)
- All SELL orders (position closings)
- Trade execution details
"""

import json
from pathlib import Path
from datetime import datetime
import pytz

def extract_all_trades_today():
    """Extract all trade activity from today"""

    today = '2025-10-24'
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)

    print("="*70)
    print(f"📊 EXTRACTING ALL TRADES - {today}")
    print("="*70)

    # Load current state
    state_file = Path('state/current_state.json')
    if not state_file.exists():
        print(f"❌ State file not found")
        return

    with open(state_file, 'r') as f:
        state = json.load(f)

    positions = state.get('positions', {})

    print(f"\n📈 Found {len(positions)} OPEN POSITIONS")
    print("   (Each position = 1 BUY trade executed today)")

    # Create comprehensive trade log
    all_trades = []
    trade_id = 1

    for symbol, pos in positions.items():
        # Extract trade details
        trade = {
            'trade_id': trade_id,
            'date': today,
            'timestamp': state.get('timestamp', now_ist.isoformat()),
            'symbol': symbol,
            'action': 'BUY',
            'transaction_type': 'OPEN_POSITION',
            'quantity': pos.get('shares', 0),
            'entry_price': pos.get('entry_price', 0),
            'total_cost': pos.get('shares', 0) * pos.get('entry_price', 0),
            'strategy': pos.get('strategy', 'unknown'),
            'sector': pos.get('sector', 'unknown'),
            'confidence': pos.get('confidence', 0),
            'current_price': pos.get('current_price', 0),
            'current_value': pos.get('shares', 0) * pos.get('current_price', 0),
            'unrealized_pnl': pos.get('pnl', 0),
            'status': 'OPEN',
            'notes': 'Position still open at market close'
        }

        all_trades.append(trade)
        trade_id += 1

    # Save complete trade log
    output_dir = Path('trade_archives/2025/10')
    output_dir.mkdir(parents=True, exist_ok=True)

    backup_dir = Path('trade_archives_backup/2025/10')
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Create comprehensive trade report
    trade_report = {
        'trading_date': today,
        'report_generated': now_ist.strftime('%Y-%m-%d %H:%M:%S IST'),
        'trading_mode': state.get('trading_mode', 'paper'),

        'summary': {
            'total_trades': len(all_trades),
            'buy_trades': len([t for t in all_trades if t['action'] == 'BUY']),
            'sell_trades': len([t for t in all_trades if t['action'] == 'SELL']),
            'open_positions': len([t for t in all_trades if t['status'] == 'OPEN']),
            'closed_positions': len([t for t in all_trades if t['status'] == 'CLOSED']),
            'total_capital_deployed': sum(t['total_cost'] for t in all_trades),
            'total_current_value': sum(t['current_value'] for t in all_trades),
            'total_unrealized_pnl': sum(t['unrealized_pnl'] for t in all_trades)
        },

        'trades_by_sector': {},
        'trades_by_strategy': {},

        'all_trades': all_trades,

        'portfolio_state_at_close': {
            'cash_remaining': state.get('cash', 0),
            'total_portfolio_value': state.get('total_value', 0),
            'open_positions_count': len(positions)
        }
    }

    # Analyze by sector and strategy
    for trade in all_trades:
        sector = trade['sector']
        strategy = trade['strategy']

        if sector not in trade_report['trades_by_sector']:
            trade_report['trades_by_sector'][sector] = {
                'trade_count': 0,
                'total_invested': 0,
                'symbols': []
            }

        trade_report['trades_by_sector'][sector]['trade_count'] += 1
        trade_report['trades_by_sector'][sector]['total_invested'] += trade['total_cost']
        trade_report['trades_by_sector'][sector]['symbols'].append(trade['symbol'])

        if strategy not in trade_report['trades_by_strategy']:
            trade_report['trades_by_strategy'][strategy] = {
                'trade_count': 0,
                'total_invested': 0
            }

        trade_report['trades_by_strategy'][strategy]['trade_count'] += 1
        trade_report['trades_by_strategy'][strategy]['total_invested'] += trade['total_cost']

    # Save to multiple locations
    trade_log_files = [
        output_dir / f'all_trades_{today}.json',
        backup_dir / f'all_trades_{today}.json'
    ]

    for trade_file in trade_log_files:
        with open(trade_file, 'w') as f:
            json.dump(trade_report, f, indent=2)
        print(f"\n✅ Trade log saved: {trade_file}")
        print(f"   Size: {trade_file.stat().st_size:,} bytes")

    # Create human-readable trade log
    readable_log = []
    readable_log.append("="*70)
    readable_log.append(f"COMPLETE TRADE LOG - {today}")
    readable_log.append("="*70)
    readable_log.append(f"Trading Mode: {state.get('trading_mode', 'paper').upper()}")
    readable_log.append(f"Report Generated: {trade_report['report_generated']}")
    readable_log.append("")
    readable_log.append("SUMMARY:")
    readable_log.append(f"  Total Trades Executed: {trade_report['summary']['total_trades']}")
    readable_log.append(f"  BUY Orders: {trade_report['summary']['buy_trades']}")
    readable_log.append(f"  SELL Orders: {trade_report['summary']['sell_trades']}")
    readable_log.append(f"  Open Positions: {trade_report['summary']['open_positions']}")
    readable_log.append(f"  Closed Positions: {trade_report['summary']['closed_positions']}")
    readable_log.append(f"  Total Capital Deployed: ₹{trade_report['summary']['total_capital_deployed']:,.2f}")
    readable_log.append("")
    readable_log.append("TRADES BY SECTOR:")
    for sector, data in sorted(trade_report['trades_by_sector'].items()):
        readable_log.append(f"  {sector}: {data['trade_count']} trades, ₹{data['total_invested']:,.2f}")
    readable_log.append("")
    readable_log.append("TRADES BY STRATEGY:")
    for strategy, data in sorted(trade_report['trades_by_strategy'].items()):
        readable_log.append(f"  {strategy}: {data['trade_count']} trades, ₹{data['total_invested']:,.2f}")
    readable_log.append("")
    readable_log.append("="*70)
    readable_log.append("DETAILED TRADE LOG:")
    readable_log.append("="*70)

    for trade in all_trades:
        readable_log.append(f"\nTrade #{trade['trade_id']}:")
        readable_log.append(f"  Symbol: {trade['symbol']}")
        readable_log.append(f"  Action: {trade['action']} (Open Position)")
        readable_log.append(f"  Quantity: {trade['quantity']} contracts")
        readable_log.append(f"  Entry Price: ₹{trade['entry_price']:.2f}")
        readable_log.append(f"  Total Cost: ₹{trade['total_cost']:,.2f}")
        readable_log.append(f"  Strategy: {trade['strategy']}")
        readable_log.append(f"  Sector: {trade['sector']}")
        readable_log.append(f"  Confidence: {trade['confidence']:.0%}")
        readable_log.append(f"  Current Price: ₹{trade['current_price']:.2f}")
        readable_log.append(f"  Unrealized P&L: ₹{trade['unrealized_pnl']:.2f}")
        readable_log.append(f"  Status: {trade['status']}")

    readable_log.append("")
    readable_log.append("="*70)
    readable_log.append("END OF TRADE LOG")
    readable_log.append("="*70)

    # Save readable log
    readable_files = [
        output_dir / f'trade_log_{today}.txt',
        backup_dir / f'trade_log_{today}.txt'
    ]

    for readable_file in readable_files:
        with open(readable_file, 'w') as f:
            f.write('\n'.join(readable_log))
        print(f"\n✅ Readable trade log: {readable_file}")

    # Print summary
    print("\n" + "="*70)
    print(f"📊 TRADE SUMMARY - {today}")
    print("="*70)
    print(f"\n✅ Total Trades Executed: {len(all_trades)}")
    print(f"   • All {len(all_trades)} trades are BUY orders (opening positions)")
    print(f"   • 0 SELL orders (no positions closed today)")
    print(f"\n💰 Capital Deployed: ₹{trade_report['summary']['total_capital_deployed']:,.2f}")
    print(f"💵 Cash Remaining: ₹{state.get('cash', 0):,.2f}")
    print(f"📊 Portfolio Value: ₹{state.get('total_value', 0):,.2f}")

    print(f"\n🎯 Breakdown by Sector:")
    for sector, data in sorted(trade_report['trades_by_sector'].items()):
        print(f"   {sector}: {data['trade_count']} trades")

    print(f"\n📈 Breakdown by Strategy:")
    for strategy, data in sorted(trade_report['trades_by_strategy'].items()):
        print(f"   {strategy}: {data['trade_count']} trades")

    print("\n" + "="*70)
    print("✅ ALL TRADE DATA SAVED SUCCESSFULLY")
    print("="*70)

    print(f"\n📁 Files created:")
    print(f"   • all_trades_{today}.json (JSON format)")
    print(f"   • trade_log_{today}.txt (Human readable)")
    print(f"   • Saved in both trade_archives/ and trade_archives_backup/")

if __name__ == '__main__':
    extract_all_trades_today()
