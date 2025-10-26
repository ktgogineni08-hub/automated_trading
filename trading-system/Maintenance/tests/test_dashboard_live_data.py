#!/usr/bin/env python3
"""
Pytest for Live Dashboard Data Integration
Tests that the enhanced trading system properly updates state files for dashboard display.
"""

import sys
import time
import json
from datetime import datetime
from pathlib import Path
import pytest

# Add current directory to path
sys.path.append('.')

from enhanced_trading_system_complete import UnifiedPortfolio, DashboardConnector, FNODataProvider

@pytest.fixture(scope="module")
def live_fno_data():
    """Fixture to fetch live F&O data once for all tests in this module."""
    # The FNODataProvider expects a KiteConnect instance, even if it's None
    # when running without a live connection for testing.
    fno_provider = FNODataProvider(kite=None)
    data = {}
    for index in ['NIFTY', 'BANKNIFTY', 'FINNIFTY']:
        # FIX: Method was renamed from get_option_chain to fetch_option_chain
        chain = fno_provider.fetch_option_chain(index)
        # FIX: The returned 'chain' is an object, not a dict. Access attributes directly.
        if chain and hasattr(chain, 'expiry_date') and hasattr(chain, 'get_atm_strike'):
            atm_strike = chain.get_atm_strike()
            if atm_strike > 0:
                data[index] = {'expiry': chain.expiry_date, 'atm': atm_strike}
    return data

@pytest.fixture
def portfolio_with_dashboard(tmp_path):
    """Fixture to create a portfolio with a dashboard connector and temporary state files."""
    dashboard = DashboardConnector("http://localhost:8080")
    portfolio = UnifiedPortfolio(
        initial_cash=500000.0,
        dashboard=dashboard,
        trading_mode='paper'
    )

    # Override instance-level state file paths to use temporary directory
    portfolio.shared_state_file_path = tmp_path / "shared_portfolio_state.json"
    portfolio.current_state_file_path = tmp_path / "current_state.json"

    # Ensure the temp directory exists
    tmp_path.mkdir(parents=True, exist_ok=True)

    return portfolio, tmp_path

def test_dashboard_trade_execution_and_state_update(portfolio_with_dashboard, live_fno_data):
    """Test that live trading data is properly saved to state files for dashboard"""
    print("🧪 Testing Live Dashboard Data Integration")
    print("=" * 70)

    portfolio, tmp_path = portfolio_with_dashboard
    shared_state_file = tmp_path / "shared_portfolio_state.json"
    current_state_file = tmp_path / "current_state.json"

    assert portfolio.initial_cash == 500000.0
    print(f"✅ Test portfolio created with ₹{portfolio.initial_cash:,.2f}")

    # Get live market data for current expiries and strikes
    print("\n🔄 Fetching live market data...")

    # Test 1: Execute some trades to generate live data
    print("\n📊 Test 1: Executing Live Trades")
    print("-" * 50)

    # Build trades data with live symbols when available, generic otherwise
    trades_data = []
    if 'NIFTY' in live_fno_data:
        trades_data.extend([
            (f"NIFTY{live_fno_data['NIFTY']['expiry']}{live_fno_data['NIFTY']['atm']}CE", 75, 225.0, "straddle"),
            (f"NIFTY{live_fno_data['NIFTY']['expiry']}{live_fno_data['NIFTY']['atm']}PE", 75, 190.0, "straddle"),
        ])
    else:
        trades_data.extend([
            ("TEST_NIFTY_CE", 75, 225.0, "straddle"),
            ("TEST_NIFTY_PE", 75, 190.0, "straddle"),
        ])

    if 'BANKNIFTY' in live_fno_data:
        trades_data.append((f"BANKNIFTY{live_fno_data['BANKNIFTY']['expiry']}{live_fno_data['BANKNIFTY']['atm']}CE", 50, 380.0, "iron_condor"))
    else:
        trades_data.append(("TEST_BANKNIFTY_CE", 50, 380.0, "iron_condor"))

    if 'FINNIFTY' in live_fno_data:
        trades_data.append((f"FINNIFTY{live_fno_data['FINNIFTY']['expiry']}{live_fno_data['FINNIFTY']['atm']}CE", 100, 150.0, "strangle"))
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

    assert len(portfolio.positions) == len(trades_data)
    assert portfolio.trades_count == len(trades_data)

    # Test 2: Check that state files are being updated
    print("\n📊 Test 2: Verifying State File Updates")
    print("-" * 50)

    # Wait a moment for file operations
    time.sleep(0.5)

    # Check shared_portfolio_state.json
    assert shared_state_file.exists()
    portfolio_state = json.loads(shared_state_file.read_text())

    assert portfolio_state.get('trading_mode') == 'paper'
    assert len(portfolio_state.get('positions', {})) == len(trades_data)
    assert 'straddle' in [p.get('strategy') for p in portfolio_state['positions'].values()]
    print("   ✅ shared_portfolio_state.json updated correctly.")

    # Check current_state.json
    assert current_state_file.exists()
    current_state = json.loads(current_state_file.read_text())
    assert current_state.get('trading_day') == datetime.now().strftime('%Y-%m-%d')
    assert current_state.get('portfolio', {}).get('trades_count') == len(trades_data)
    print("   ✅ current_state.json updated correctly.")

def test_position_exit_and_state_update(portfolio_with_dashboard):
    """Test that exiting a position correctly updates the state files."""
    portfolio, tmp_path = portfolio_with_dashboard
    shared_state_file = tmp_path / "shared_portfolio_state.json"
    
    # Add a trade to exit
    # FIX: The arguments for execute_trade were in the wrong order.
    # The signature is: execute_trade(symbol, shares, price, side, timestamp, confidence, sector, atr, allow_immediate_sell, strategy)
    # 'timestamp' was being passed as a float (0.8), and 'confidence' as a string ("F&O").
    portfolio.execute_trade(
        symbol="TEST_EXIT_CE",
        shares=50,
        price=100.0,
        side="buy",
        confidence=0.8,
        sector="F&O",
        strategy="test_exit"
    )
    assert "TEST_EXIT_CE" in portfolio.positions
    
    print("\n📊 Test 3: Testing Position Updates with Price Changes")
    print("-" * 50)

    # Exit the position
    exit_result = portfolio.execute_trade(
        symbol="TEST_EXIT_CE",
        shares=50,
        price=110.0,
        side="sell",
        confidence=0.8,
        sector="F&O",
        allow_immediate_sell=True
    )
    assert exit_result is not None
    assert "TEST_EXIT_CE" not in portfolio.positions
    print("   ✅ Position exited successfully.")

    # Final verification
    time.sleep(0.5)  # Wait for file update

    final_state = json.loads(shared_state_file.read_text())
    assert "TEST_EXIT_CE" not in final_state.get('positions', {})
    assert len(final_state.get('positions', {})) == 0
    print("   ✅ Final state verification successful.")