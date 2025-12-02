#!/usr/bin/env python3
"""
F&O Paper Trading Simulation Script
Simulates F&O trading using FNOTerminal and mock data.
"""

import os
import sys
import time
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fno.terminal import FNOTerminal
from fno.data_provider import FNODataProvider
from fno.options import OptionChain, OptionContract
from core.portfolio import UnifiedPortfolio
from utilities.market_hours import MarketHoursManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fno_simulation.log', mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('fno_simulation')
with open('fno_simulation.log', 'a') as f:
    f.write("DEBUG: Script started\n")
print("DEBUG: Script started")

class MockKiteConnect:
    def __init__(self):
        self.orders = []
        self.positions = []
        self.margins = {'equity': {'available': {'live_balance': 1000000.0}}}

    def orders(self):
        return self.orders

    def positions(self):
        return {'net': self.positions, 'day': self.positions}
    
    def margins(self):
        return self.margins
        
    def place_order(self, variety, exchange, tradingsymbol, transaction_type, quantity, product, order_type, price=None, trigger_price=None, tag=None):
        order_id = f"order_{len(self.orders) + 1}"
        order = {
            'order_id': order_id,
            'variety': variety,
            'exchange': exchange,
            'tradingsymbol': tradingsymbol,
            'transaction_type': transaction_type,
            'quantity': quantity,
            'product': product,
            'order_type': order_type,
            'price': price,
            'status': 'COMPLETE',
            'order_timestamp': datetime.now(),
            'tag': tag
        }
        self.orders.append(order)
        logger.info(f"Mock Order Placed: {transaction_type} {quantity} {tradingsymbol} @ {price}")
        return order_id

    def ltp(self, instruments):
        return {inst: {'last_price': 100.0} for inst in instruments}

    def quote(self, instruments):
        return {inst: {'last_price': 100.0, 'ohlc': {'open': 100, 'high': 105, 'low': 95, 'close': 100}, 'depth': {'buy': [{'price': 99.5, 'quantity': 100}], 'sell': [{'price': 100.5, 'quantity': 100}]}} for inst in instruments}

def create_mock_option_chain(symbol, spot_price):
    expiry = datetime.now() + timedelta(days=7)
    strikes = []
    atm = round(spot_price / 50) * 50
    
    calls = []
    puts = []
    
    for i in range(-5, 6):
        strike = atm + (i * 50)
        strikes.append(strike)
        
        # Create mock call
        call = OptionContract(
            symbol=f"{symbol}24JAN{strike}CE",
            strike_price=strike,
            option_type='CE',
            expiry_date=expiry,
            underlying=symbol,
            lot_size=50 if symbol == 'NIFTY' else 15
        )
        call.last_price = max(0.05, spot_price - strike + 10) if strike < spot_price else max(0.05, 10 - (strike - spot_price)/10)
        call.volume = 10000
        call.oi = 50000
        call.change = 1.5
        calls.append(call)
        
        # Create mock put
        put = OptionContract(
            symbol=f"{symbol}24JAN{strike}PE",
            strike_price=strike,
            option_type='PE',
            expiry_date=expiry,
            underlying=symbol,
            lot_size=50 if symbol == 'NIFTY' else 15
        )
        put.last_price = max(0.05, strike - spot_price + 10) if strike > spot_price else max(0.05, 10 - (spot_price - strike)/10)
        put.volume = 10000
        put.oi = 50000
        put.change = -1.5
        puts.append(put)
        
    chain = OptionChain(
        underlying=symbol,
        expiry_date=expiry,
        lot_size=50 if symbol == 'NIFTY' else 15
    )
    chain.spot_price = spot_price
    chain.calls = calls
    chain.puts = puts
    chain.timestamp = datetime.now()
    return chain

def run_simulation():
    logger.info("Starting F&O Paper Trading Simulation...")
    
    # 1. Setup Mock Environment
    os.environ['DASHBOARD_API_KEY'] = 'mock-api-key'
    os.environ['TRADING_SECURITY_PASSWORD'] = 'mock-password-123'
    
    mock_kite = MockKiteConnect()
    
    # 2. Initialize Terminal with Mocks
    # Mock DataProvider to return synthetic option chains
    with patch('fno.data_provider.FNODataProvider') as MockDataProvider:
        mock_dp = MockDataProvider.return_value
        mock_dp.get_available_indices.return_value = {
            'NIFTY': MagicMock(name='NIFTY', lot_size=50),
            'BANKNIFTY': MagicMock(name='BANKNIFTY', lot_size=15)
        }
        
        # Mock fetch_option_chain to return dynamic data
        mock_dp.fetch_option_chain.side_effect = lambda symbol: create_mock_option_chain(symbol, 21500.0 if symbol == 'NIFTY' else 46000.0)
        
        # Initialize Portfolio
        portfolio = UnifiedPortfolio(
            initial_cash=1000000.0,
            kite=mock_kite,
            trading_mode='paper',
            dashboard=None
        )
        
        # Initialize Terminal
        terminal = FNOTerminal(kite=mock_kite, portfolio=portfolio)
        terminal.data_provider = mock_dp # Inject mock DP
        
        # Mock Market Hours
        terminal.market_hours.is_market_open = MagicMock(return_value=True)
        terminal.market_hours.can_trade = MagicMock(return_value=(True, "Simulation"))
        
        # 3. Run Simulation Loop
        logger.info("Running simulation loop...")
        
        # Simulate a few iterations of continuous monitoring
        # We'll mock the internal loop of run_continuous_monitoring to avoid infinite loop
        # Instead, we'll call the core logic methods directly
        
        # Iteration 1: Scan and find opportunity
        logger.info("--- Iteration 1: Scanning ---")
        terminal.run_single_scan()
        
        # Verify if any trade was placed (auto-execution might be triggered)
        if len(mock_kite.orders) > 0:
            logger.info(f"✅ Orders placed: {len(mock_kite.orders)}")
        else:
            logger.info("ℹ️ No orders placed yet (might need higher confidence)")
            
        # Force a trade execution to verify pipeline
        logger.info("--- Forcing Trade Execution ---")
        chain = create_mock_option_chain('NIFTY', 21500.0)
        analysis = {
            'confidence': 0.9,
            'max_profit': 5000,
            'max_loss': 2000,
            'strategy': 'straddle',
            'call_option': chain.calls[5], # ATM
            'put_option': chain.puts[5],   # ATM
            'strike': 21500,
            'total_premium': 200,
            'breakeven_lower': 21300,
            'breakeven_upper': 21700
        }
        
        terminal._execute_strategy(chain, 'straddle', analysis)
        
        # 4. Verify Results
        logger.info("Simulation complete. Verifying state...")
        logger.info(f"Total Orders: {len(mock_kite.orders)}")
        
        if len(mock_kite.orders) > 0:
            logger.info("✅ SUCCESS: F&O Orders were placed.")
        else:
            logger.warning("❌ FAILURE: No F&O orders were executed.")
            
        # Clean up
        terminal._reset_portfolio_state()

if __name__ == "__main__":
    run_simulation()
