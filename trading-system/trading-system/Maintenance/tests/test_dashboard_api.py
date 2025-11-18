#!/usr/bin/env python3
"""
Test Dashboard API to verify live data display
"""

import requests
import json
import sys

def test_dashboard_api():
    """Test dashboard API endpoints"""
    print("🧪 Testing Dashboard API")
    print("=" * 50)

    # Test different ports
    ports = [8080, 5175, 8888]
    working_port = None

    for port in ports:
        try:
            response = requests.get(f"http://localhost:{port}/health", timeout=2)
            if response.status_code == 200:
                working_port = port
                print(f"✅ Dashboard found on port {port}")
                break
        except:
            continue

    if not working_port:
        print("❌ Dashboard not accessible on any port")
        return

    base_url = f"http://localhost:{working_port}"

    # Test API data endpoint
    try:
        response = requests.get(f"{base_url}/api/data", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API data endpoint working")

            print(f"\n📊 Dashboard Data:")
            print(f"   Portfolio Value: ₹{data.get('portfolio', {}).get('total_value', 0):,.2f}")
            print(f"   Cash: ₹{data.get('portfolio', {}).get('cash', 0):,.2f}")
            print(f"   Positions Count: {data.get('portfolio', {}).get('positions_count', 0)}")
            print(f"   Total P&L: ₹{data.get('portfolio', {}).get('total_pnl', 0):,.2f}")

            positions = data.get('positions', [])
            print(f"\n📈 Active Positions ({len(positions)}):")
            for pos in positions:
                symbol = pos.get('symbol', 'Unknown')
                quantity = pos.get('quantity', 0)
                current_price = pos.get('current_price', 0)
                unrealized_pnl = pos.get('unrealized_pnl', 0)
                print(f"   • {symbol}: {quantity} @ ₹{current_price:.2f} | P&L: ₹{unrealized_pnl:+.2f}")

            performance = data.get('performance', {})
            print(f"\n🎯 Performance:")
            print(f"   Trades: {performance.get('trades_count', 0)}")
            print(f"   Win Rate: {performance.get('win_rate', 0):.1f}%")

            system_status = data.get('system_status', {})
            print(f"\n⚙️ System Status:")
            print(f"   Running: {system_status.get('is_running', False)}")
            print(f"   Iteration: {system_status.get('iteration', 0)}")

        else:
            print(f"❌ API data endpoint error: {response.status_code}")

    except Exception as e:
        print(f"❌ API test error: {e}")

    print(f"\n🌐 Dashboard URL: {base_url}")
    print("   Open this URL in your browser to see the live dashboard")

if __name__ == "__main__":
    test_dashboard_api()