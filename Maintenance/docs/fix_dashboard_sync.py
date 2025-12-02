#!/usr/bin/env python3
"""
Quick fix to manually sync portfolio data to dashboard
Use this when dashboard shows stale data
"""

import json
import requests
from datetime import datetime

def read_current_state():
    """Read current state from state file"""
    try:
        with open('state/current_state.json', 'r') as f:
            state = json.load(f)
        return state
    except Exception as e:
        print(f"❌ Error reading state file: {e}")
        return None

def send_to_dashboard(state):
    """Send portfolio data to dashboard"""
    try:
        portfolio_data = state.get('portfolio', {})

        # Extract values
        total_value = portfolio_data.get('total_value', 0)
        cash = portfolio_data.get('cash', 0)
        positions = portfolio_data.get('positions', {})
        total_pnl = portfolio_data.get('total_pnl', 0)

        print(f"\n📊 Current State from File:")
        print(f"  Total Value: ₹{total_value:,.2f}")
        print(f"  Cash: ₹{cash:,.2f}")
        print(f"  Positions: {len(positions)}")
        print(f"  Total P&L: ₹{total_pnl:,.2f}")

        # Send to dashboard
        payload = {
            'total_value': total_value,
            'cash': cash,
            'positions_count': len(positions),
            'total_pnl': total_pnl
        }

        response = requests.post('http://localhost:8080/api/portfolio',
                               json=payload,
                               timeout=5)

        if response.status_code == 200:
            print(f"\n✅ Successfully sent to dashboard")
            return True
        else:
            print(f"\n❌ Dashboard returned status {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"\n❌ Cannot connect to dashboard at http://localhost:8080")
        print(f"   Make sure dashboard is running: python enhanced_dashboard_server.py")
        return False
    except Exception as e:
        print(f"\n❌ Error sending to dashboard: {e}")
        return False

def main():
    print("="*60)
    print("Dashboard Sync Fix Tool")
    print("="*60)

    # Read state
    state = read_current_state()
    if not state:
        return

    # Send to dashboard
    success = send_to_dashboard(state)

    if success:
        print(f"\n💡 Now refresh your browser (Ctrl+Shift+R or Cmd+Shift+R)")
        print(f"   Dashboard should show updated values")
    else:
        print(f"\n💡 Troubleshooting steps:")
        print(f"   1. Check if dashboard is running: ps aux | grep dashboard")
        print(f"   2. Restart dashboard: python enhanced_dashboard_server.py &")
        print(f"   3. Try this script again")

if __name__ == "__main__":
    main()
