#!/usr/bin/env python3
"""
Test script to verify portfolio data is being sent to dashboard correctly
"""

import sys
import time
import json
from datetime import datetime

# Add current directory to path
sys.path.append('.')

from enhanced_trading_system_complete import DashboardConnector, UnifiedPortfolio

def test_dashboard_portfolio():
    """Test portfolio data integration with dashboard"""
    print("🧪 Testing Dashboard Portfolio Integration")
    print("="*50)

    # Test dashboard connection
    dashboard = DashboardConnector("http://localhost:8080")
    if not dashboard.is_connected:
        print("❌ Dashboard not connected. Please start dashboard first:")
        print("   python enhanced_dashboard_server.py")
        return False

    print("✅ Dashboard connection established")

    # Create test portfolio
    portfolio = UnifiedPortfolio(
        initial_cash=100000.0,
        dashboard=dashboard,
        trading_mode='paper'
    )

    print(f"✅ Test portfolio created with ₹{portfolio.cash:,.2f}")

    # Send initial portfolio update
    print("\n📊 Sending initial portfolio status...")
    portfolio.send_dashboard_update()

    # Simulate some trades
    print("\n📈 Simulating trades...")

    # Buy trade
    portfolio.execute_trade(
        symbol="RELIANCE",
        shares=10,
        price=2800.0,
        side="buy",
        confidence=0.8,
        sector="Energy"
    )
    print("✅ Buy trade executed: RELIANCE 10 @ ₹2800")

    # Another buy trade
    portfolio.execute_trade(
        symbol="TCS",
        shares=5,
        price=3500.0,
        side="buy",
        confidence=0.9,
        sector="IT"
    )
    print("✅ Buy trade executed: TCS 5 @ ₹3500")

    # Wait a moment
    time.sleep(2)

    # Sell trade with profit
    portfolio.execute_trade(
        symbol="RELIANCE",
        shares=5,
        price=2850.0,
        side="sell",
        confidence=0.7,
        sector="Energy",
        allow_immediate_sell=True
    )
    print("✅ Sell trade executed: RELIANCE 5 @ ₹2850 (profit)")

    # Send final status
    print("\n📊 Sending final portfolio status...")
    total_value = portfolio.calculate_total_value({
        'RELIANCE': 2850.0,
        'TCS': 3600.0
    })

    portfolio.send_dashboard_update({
        'RELIANCE': 2850.0,
        'TCS': 3600.0
    })

    print(f"\n✅ Portfolio Status Sent to Dashboard:")
    print(f"   💰 Total Value: ₹{total_value:,.2f}")
    print(f"   💵 Cash: ₹{portfolio.cash:,.2f}")
    print(f"   📈 Positions: {len(portfolio.positions)}")
    print(f"   📊 Total P&L: ₹{portfolio.total_pnl:,.2f}")
    print(f"   🎯 Trades: {portfolio.trades_count}")

    # Send system status
    dashboard.send_system_status(True, 1, "testing")

    print(f"\n🌐 Check dashboard at: http://localhost:8080")
    print("   Portfolio data should now be visible!")

    return True

if __name__ == "__main__":
    try:
        success = test_dashboard_portfolio()
        if success:
            print("\n✅ Dashboard portfolio test completed successfully!")
        else:
            print("\n❌ Dashboard portfolio test failed!")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()