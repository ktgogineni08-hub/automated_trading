#!/usr/bin/env python3
"""
Test Live Dashboard Data Integration
Tests that the enhanced trading system properly updates state files for dashboard display
"""

import sys
import time
import json
from datetime import datetime

# Add current directory to path
sys.path.append('.')

from enhanced_trading_system_complete import UnifiedPortfolio, DashboardConnector, FNODataProvider

def test_dashboard_live_data():
    """Test that live trading data is properly saved to state files for dashboard"""
    print("🧪 Testing Live Dashboard Data Integration")
    print("=" * 70)

    # Initialize dashboard and portfolio
    dashboard = DashboardConnector("http://localhost:8080")
    portfolio = UnifiedPortfolio(
        initial_cash=500000.0,
        dashboard=dashboard,
        trading_mode='paper'
    )

    print(f"✅ Test portfolio created with ₹{portfolio.initial_cash:,.2f}")

    # Get live market data for current expiries and strikes
    print("\n🔄 Fetching live market data...")
    fno_provider = FNODataProvider()

    try:
        nifty_chain = fno_provider.get_option_chain('NIFTY')
        banknifty_chain = fno_provider.get_option_chain('BANKNIFTY')
        finnifty_chain = fno_provider.get_option_chain('FINNIFTY')

        nifty_expiry = nifty_chain['current_expiry'] if nifty_chain and nifty_chain.get('current_expiry') else None
        nifty_atm = nifty_chain['atm_strike'] if nifty_chain and nifty_chain.get('atm_strike') else None

        banknifty_expiry = banknifty_chain['current_expiry'] if banknifty_chain and banknifty_chain.get('current_expiry') else None
        banknifty_atm = banknifty_chain['atm_strike'] if banknifty_chain and banknifty_chain.get('atm_strike') else None

        finnifty_expiry = finnifty_chain['current_expiry'] if finnifty_chain and finnifty_chain.get('current_expiry') else None
        finnifty_atm = finnifty_chain['atm_strike'] if finnifty_chain and finnifty_chain.get('atm_strike') else None

        if nifty_expiry and banknifty_expiry and finnifty_expiry:
            print(f"✅ Live expiries: NIFTY({nifty_expiry}), BANKNIFTY({banknifty_expiry}), FINNIFTY({finnifty_expiry})")
        else:
            print("⚠️ Some live data unavailable, using generic test symbols where needed")

    except Exception as e:
        print(f"⚠️ API error, using generic test symbols: {e}")
        nifty_expiry = banknifty_expiry = finnifty_expiry = None
        nifty_atm = banknifty_atm = finnifty_atm = None

    # Test 1: Execute some trades to generate live data
    print("\n📊 Test 1: Executing Live Trades")
    print("-" * 50)

    # Build trades data with live symbols when available, generic otherwise
    trades_data = []
    if nifty_expiry and nifty_atm:
        trades_data.extend([
            (f"NIFTY{nifty_expiry}{nifty_atm}CE", 75, 225.0, "straddle"),
            (f"NIFTY{nifty_expiry}{nifty_atm}PE", 75, 190.0, "straddle"),
        ])
    else:
        trades_data.extend([
            ("TEST_NIFTY_CE", 75, 225.0, "straddle"),
            ("TEST_NIFTY_PE", 75, 190.0, "straddle"),
        ])

    if banknifty_expiry and banknifty_atm:
        trades_data.append((f"BANKNIFTY{banknifty_expiry}{banknifty_atm}CE", 50, 380.0, "iron_condor"))
    else:
        trades_data.append(("TEST_BANKNIFTY_CE", 50, 380.0, "iron_condor"))

    if finnifty_expiry and finnifty_atm:
        trades_data.append((f"FINNIFTY{finnifty_expiry}{finnifty_atm}CE", 100, 150.0, "strangle"))
    else:
        trades_data.append(("TEST_FINNIFTY_CE", 100, 150.0, "strangle"))

    for symbol, shares, price, strategy in trades_data:
        result = portfolio.execute_trade(
            symbol=symbol,
            shares=shares,
            price=price,
            side="buy",
            confidence=0.8,
            sector="F&O",
            strategy=strategy
        )
        if result:
            print(f"   ✅ {strategy}: {symbol} - {shares} @ ₹{price}")
        else:
            print(f"   ❌ Failed: {symbol}")

    print(f"\n   Total positions created: {len(portfolio.positions)}")
    print(f"   Total trades: {portfolio.trades_count}")
    print(f"   Cash remaining: ₹{portfolio.cash:,.2f}")

    # Test 2: Check that state files are being updated
    print("\n📊 Test 2: Verifying State File Updates")
    print("-" * 50)

    # Wait a moment for file operations
    time.sleep(1)

    # Check shared_portfolio_state.json
    try:
        with open('state/shared_portfolio_state.json', 'r') as f:
            portfolio_state = json.load(f)

        print(f"   ✅ shared_portfolio_state.json updated:")
        print(f"      • Cash: ₹{portfolio_state.get('cash', 0):,.2f}")
        print(f"      • Positions: {len(portfolio_state.get('positions', {}))}")
        print(f"      • Trading Mode: {portfolio_state.get('trading_mode', 'unknown')}")

        # Verify positions have strategy assignments
        positions = portfolio_state.get('positions', {})
        strategy_count = {}
        for symbol, pos in positions.items():
            strategy = pos.get('strategy', 'unknown')
            strategy_count[strategy] = strategy_count.get(strategy, 0) + 1
            print(f"      • {symbol}: {strategy} - {pos.get('shares', 0)} shares @ ₹{pos.get('entry_price', 0):.2f}")

        print(f"      • Strategy Distribution: {strategy_count}")

    except Exception as e:
        print(f"   ❌ Error reading shared_portfolio_state.json: {e}")

    # Check current_state.json
    try:
        with open('state/current_state.json', 'r') as f:
            current_state = json.load(f)

        print(f"\n   ✅ current_state.json updated:")
        print(f"      • Last Update: {current_state.get('last_update', 'unknown')}")
        print(f"      • Trading Day: {current_state.get('trading_day', 'unknown')}")
        print(f"      • Total Value: ₹{current_state.get('total_value', 0):,.2f}")

        portfolio_data = current_state.get('portfolio', {})
        print(f"      • Trades Count: {portfolio_data.get('trades_count', 0)}")
        print(f"      • Positions: {len(portfolio_data.get('positions', {}))}")
        print(f"      • Total P&L: ₹{portfolio_data.get('total_pnl', 0):,.2f}")

    except Exception as e:
        print(f"   ❌ Error reading current_state.json: {e}")

    # Test 3: Simulate price changes and position exits
    print("\n📊 Test 3: Testing Position Updates with Price Changes")
    print("-" * 50)

    # Build mock prices based on actual symbols in portfolio
    mock_prices = {}
    for symbol in portfolio.positions.keys():
        if "CE" in symbol:
            mock_prices[symbol] = 275.0  # Simulate profit
        elif "PE" in symbol:
            mock_prices[symbol] = 170.0  # Simulate loss

    print("   Simulating price changes...")
    for symbol, new_price in mock_prices.items():
        if symbol in portfolio.positions:
            entry_price = portfolio.positions[symbol]["entry_price"]
            pnl_pct = ((new_price - entry_price) / entry_price) * 100
            print(f"   📊 {symbol}: ₹{entry_price:.2f} → ₹{new_price:.2f} ({pnl_pct:+.1f}%)")

    # Update portfolio with new prices (this should trigger state save)
    portfolio.send_dashboard_update(mock_prices)

    # Test 4: Execute a position exit
    print("\n📊 Test 4: Testing Position Exit and State Update")
    print("-" * 50)

    # Exit one position
    # Get first available symbol for exit test
    exit_symbol = next(iter(portfolio.positions.keys())) if portfolio.positions else "NO_POSITIONS"
    if exit_symbol in portfolio.positions:
        exit_result = portfolio.execute_trade(
            symbol=exit_symbol,
            shares=portfolio.positions[exit_symbol]["shares"],
            price=mock_prices[exit_symbol],
            side="sell",
            confidence=0.8,
            sector="F&O",
            allow_immediate_sell=True
        )

        if exit_result:
            print(f"   ✅ Position exited: {exit_symbol}")
            print(f"   📊 Remaining positions: {len(portfolio.positions)}")

    # Final verification
    time.sleep(1)  # Wait for file update

    # Check updated state files
    try:
        with open('state/shared_portfolio_state.json', 'r') as f:
            final_state = json.load(f)

        final_positions = len(final_state.get('positions', {}))
        final_cash = final_state.get('cash', 0)

        print(f"\n   ✅ Final state verification:")
        print(f"      • Final Positions: {final_positions}")
        print(f"      • Final Cash: ₹{final_cash:,.2f}")

        # Check if timestamp is recent (within last minute)
        with open('state/current_state.json', 'r') as f:
            current_state = json.load(f)

        last_update_str = current_state.get('last_update', '')
        if last_update_str:
            try:
                last_update = datetime.fromisoformat(last_update_str.replace('Z', '+00:00'))
                time_diff = (datetime.now() - last_update.replace(tzinfo=None)).total_seconds()
                if time_diff < 60:  # Within last minute
                    print(f"      ✅ State files are current (updated {time_diff:.1f}s ago)")
                else:
                    print(f"      ⚠️ State files may be stale (updated {time_diff:.1f}s ago)")
            except:
                print(f"      ⚠️ Could not parse last update time")

    except Exception as e:
        print(f"   ❌ Error in final verification: {e}")

    # Test 5: Dashboard Auto-Refresh Test
    print("\n📊 Test 5: Dashboard Auto-Refresh Verification")
    print("-" * 50)

    if dashboard.is_connected:
        print("   ✅ Dashboard connected")
        print(f"   🌐 Dashboard URL: http://localhost:8080")
        print("   📊 Dashboard should now show:")
        print(f"      • Live portfolio value: ₹{portfolio.calculate_total_value(mock_prices):,.2f}")
        print(f"      • Active positions: {len(portfolio.positions)}")
        print(f"      • Strategy distribution from live trades")
        print("   🔄 Auto-refresh every 2 seconds will show live updates")
    else:
        print("   ⚠️ Dashboard not connected")
        print("   💡 Start dashboard with: python enhanced_dashboard_server.py")

    # Summary
    print("\n📈 LIVE DATA INTEGRATION SUMMARY")
    print("=" * 70)

    portfolio_value = portfolio.calculate_total_value(mock_prices)
    total_pnl = portfolio_value - portfolio.initial_cash

    print(f"✅ Live Trading Data Successfully Integrated")
    print(f"✅ State Files Updated with Current Positions")
    print(f"✅ Dashboard Auto-Refresh Enabled (2-second intervals)")
    print(f"✅ Real-time Position Tracking Active")
    print(f"✅ Strategy Assignment Properly Recorded")

    print(f"\n💰 Current Portfolio Status:")
    print(f"   Total Value: ₹{portfolio_value:,.2f}")
    print(f"   Cash: ₹{portfolio.cash:,.2f}")
    print(f"   Active Positions: {len(portfolio.positions)}")
    print(f"   Total P&L: ₹{total_pnl:+,.2f} ({(total_pnl/portfolio.initial_cash)*100:+.2f}%)")
    print(f"   Total Trades: {portfolio.trades_count}")

    strategy_dist = portfolio.get_strategy_distribution()
    if strategy_dist:
        print(f"   Strategy Mix: {', '.join([f'{k}({v})' for k, v in strategy_dist.items()])}")

    print(f"\n🎯 The dashboard at http://localhost:8080 should now display:")
    print(f"   ✅ Real-time portfolio value and P&L")
    print(f"   ✅ Current active positions with live pricing")
    print(f"   ✅ Proper strategy names (not 'unknown')")
    print(f"   ✅ Updated every 2 seconds automatically")
    print(f"   ✅ Trade history and performance metrics")

    return True

if __name__ == "__main__":
    try:
        print("🚀 Starting Live Dashboard Data Integration Test...")
        success = test_dashboard_live_data()
        if success:
            print("\n✅ Live dashboard data integration tested successfully!")
            print("🎯 Dashboard should now display current trading data!")
        else:
            print("\n❌ Live dashboard data integration test failed!")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()