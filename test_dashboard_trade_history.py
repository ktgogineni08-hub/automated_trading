#!/usr/bin/env python3
"""
Test script to manually send trade history to dashboard
This helps verify the dashboard display is working
"""

import requests
import json
from datetime import datetime, timedelta

def test_send_trade_history():
    """Send test trade history to dashboard"""

    dashboard_url = "http://localhost:8080/api/trade_history"

    print("\n" + "="*60)
    print("Testing Trade History Dashboard Display")
    print("="*60)

    # Create some test trades
    test_trades = [
        {
            "symbol": "NIFTY25O0725350PE",
            "entry_time": (datetime.now() - timedelta(hours=3)).isoformat(),
            "entry_price": 523.54,
            "shares": 680,
            "exit_time": datetime.now().isoformat(),
            "exit_price": 545.72,
            "pnl": 15082.40,
            "pnl_percent": 4.24,
            "exit_reason": "Quick profit taking (Net: ₹14,673 > ₹10k after fees)"
        },
        {
            "symbol": "BANKEX25OCT62400CE",
            "entry_time": (datetime.now() - timedelta(hours=5)).isoformat(),
            "entry_price": 964.31,
            "shares": 373,
            "exit_time": (datetime.now() - timedelta(hours=1)).isoformat(),
            "exit_price": 1003.46,
            "pnl": 14602.03,
            "pnl_percent": 4.06,
            "exit_reason": "Quick profit taking (Net: ₹14,207 > ₹10k after fees)"
        },
        {
            "symbol": "SENSEX25OCT82000CE",
            "entry_time": (datetime.now() - timedelta(hours=2)).isoformat(),
            "entry_price": 450.25,
            "shares": 200,
            "exit_time": (datetime.now() - timedelta(minutes=30)).isoformat(),
            "exit_price": 478.50,
            "pnl": 5650.00,
            "pnl_percent": 6.27,
            "exit_reason": "Quick profit taking (Net: ₹5,580 > ₹5k after fees)"
        }
    ]

    print(f"\n📤 Sending {len(test_trades)} test trades to dashboard...\n")

    for i, trade in enumerate(test_trades, 1):
        try:
            response = requests.post(dashboard_url, json=trade, timeout=2)

            if response.status_code == 200:
                print(f"✅ Trade {i}: {trade['symbol']} - P&L: ₹{trade['pnl']:,.0f} - Sent successfully")
            else:
                print(f"❌ Trade {i}: Failed with status {response.status_code}")

        except requests.exceptions.ConnectionError:
            print(f"\n❌ ERROR: Could not connect to dashboard at {dashboard_url}")
            print("   Make sure the dashboard server is running!")
            print("   Run: python enhanced_dashboard_server.py")
            return False
        except Exception as e:
            print(f"❌ Trade {i}: Error - {e}")
            return False

    print("\n" + "="*60)
    print("✅ Test trades sent successfully!")
    print("="*60)

    print("\n📊 Next steps:")
    print("   1. Open dashboard: http://localhost:8080")
    print("   2. Click '📊 Trade History' tab")
    print("   3. You should see 3 test trades with full details")
    print("\n   If you see 'No completed trades yet', check:")
    print("   - Dashboard server logs for 'Received trade history' messages")
    print("   - Browser console for any JavaScript errors")
    print("   - Network tab to see if /api/data is returning trade_history")

    return True

if __name__ == "__main__":
    success = test_send_trade_history()
    exit(0 if success else 1)
