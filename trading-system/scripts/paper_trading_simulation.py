#!/usr/bin/env python3
"""
Paper Trading Simulation Script
Simulates a live trading session with mocked broker and synthetic market data.
Verifies UnifiedTradingSystem, UnifiedRiskManager, and UnifiedPortfolio in a live-like loop.
"""

import logging
import time
import sys
import os
import threading
from datetime import datetime, timedelta
from unittest.mock import MagicMock
import pandas as pd
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trading_system import UnifiedTradingSystem
from unified_config import get_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('simulation')

class MockKiteConnect:
    """Mock KiteConnect for simulation"""
    def __init__(self):
        self.orders = []
        self.positions = []
        self.margins = {'equity': {'available': {'live_balance': 100000.0}}}
        logger.info("MockKiteConnect initialized")

    def orders(self):
        return self.orders

    def positions(self):
        return {'net': self.positions}

    def margins(self):
        return self.margins

    def place_order(self, variety, exchange, tradingsymbol, transaction_type, quantity, product, order_type, price=None, trigger_price=None, tag=None):
        order_id = f"ORD-{int(time.time()*1000)}"
        logger.info(f"🔒 BROKER: Received Order {order_id}: {transaction_type} {quantity} {tradingsymbol} @ {price}")
        
        # Simulate order fill
        self.orders.append({
            'order_id': order_id,
            'tradingsymbol': tradingsymbol,
            'transaction_type': transaction_type,
            'quantity': quantity,
            'price': price,
            'status': 'COMPLETE',
            'order_timestamp': datetime.now()
        })
        
        # Update positions (simplified)
        existing_pos = next((p for p in self.positions if p['tradingsymbol'] == tradingsymbol), None)
        qty_change = quantity if transaction_type == 'BUY' else -quantity
        
        if existing_pos:
            existing_pos['quantity'] += qty_change
            if existing_pos['quantity'] == 0:
                self.positions.remove(existing_pos)
        else:
            self.positions.append({
                'tradingsymbol': tradingsymbol,
                'quantity': qty_change,
                'average_price': price,
                'last_price': price,
                'pnl': 0.0,
                'product': product,
                'exchange': exchange
            })
            
        return order_id

    def ltp(self, instruments):
        # Return dummy LTPs
        return {inst: {'last_price': 1000.0} for inst in instruments}

def run_simulation():
    """Run the paper trading simulation"""
    logger.info("Starting Paper Trading Simulation...")

    # Set mock environment variables
    os.environ['DASHBOARD_API_KEY'] = 'mock-api-key'
    os.environ['TRADING_SECURITY_PASSWORD'] = 'mock-password-123'

    # 1. Setup Configuration
    config = get_config()
    # Force paper trading mode
    config.trading_mode = 'paper'
    
    # 2. Initialize System with Mock Broker
    # Initialize dependencies
    from data.provider import DataProvider
    from utilities.dashboard import DashboardConnector
    
    mock_kite = MockKiteConnect()
    data_provider = DataProvider(kite=mock_kite)
    dashboard = DashboardConnector({})
    
    system = UnifiedTradingSystem(
        data_provider=data_provider,
        kite=mock_kite,
        initial_cash=100000.0,
        trading_mode='paper',
        config_override={},
        dashboard=dashboard
    )
    
    # Inject Mock Kite
    mock_kite = MockKiteConnect()
    system.portfolio.kite = mock_kite
    system.dp.kite = mock_kite
    
    # Also inject into the strategy's portfolio reference if needed
    # (The system usually handles this linkage)

    # 3. Start System
    # We run the system in a separate thread because start() is blocking
    system_thread = threading.Thread(target=system.run_nifty50_trading, args=('5minute', 1), daemon=True)
    system_thread.start()
    
    logger.info("System started. Waiting for initialization...")
    time.sleep(5) # Wait for system to settle

    # Mock market hours to force system to run
    system.market_hours.is_market_open = MagicMock(return_value=True)
    system.portfolio.market_hours_manager.is_market_open = MagicMock(return_value=True)
    system.portfolio.market_hours_manager.can_trade = MagicMock(return_value=(True, "Simulation"))

    # 4. Simulate Market Data (Ticks)
    logger.info("Generating synthetic market data...")
    
    symbols = ['INFY', 'TCS', 'RELIANCE']
    base_prices = {'INFY': 1500.0, 'TCS': 3500.0, 'RELIANCE': 2400.0}
    
    # Simulate 10 minutes of trading
    for i in range(20): # 20 ticks
        ticks = []
        for symbol in symbols:
            # Random walk price
            change = np.random.normal(0, 2.0)
            base_prices[symbol] += change
            
            ticks.append({
                'instrument_token': hash(symbol) % 100000, # Dummy token
                'mode': 'full',
                'volume': 1000 + i*10,
                'last_price': base_prices[symbol],
                'average_price': base_prices[symbol],
                'oi': 0,
                'oi_day_high': 0,
                'oi_day_low': 0,
                'timestamp': datetime.now(),
                'change': 0.0,
                'tradingsymbol': symbol # Important: System often maps token to symbol
            })
            
        # Inject ticks into the system
        # Note: UnifiedTradingSystem usually receives ticks via kws.on_ticks
        # We need to manually trigger the callback or method that handles ticks
        
        # Access the market manager or strategy orchestrator directly
        if hasattr(system, 'market_manager'):
            system.market_manager.on_ticks(None, ticks)
        elif hasattr(system, 'on_ticks'):
            system.on_ticks(None, ticks)
        else:
            # Fallback: Manually update data provider and trigger strategies
            logger.info(f"Tick {i+1}: Updating prices...")
            for tick in ticks:
                symbol = tick['tradingsymbol']
                price = tick['last_price']
                # Manually update data provider cache
                # Create a dummy dataframe for the cache
                df = pd.DataFrame({
                    'open': [price], 'high': [price], 'low': [price], 'close': [price], 'volume': [tick['volume']]
                }, index=[pd.Timestamp.now()])
                system.dp.price_cache.set(f"{symbol}:5minute", df)
                
                # Trigger strategy evaluation for this symbol
                # This depends on how the system loop is structured. 
                # If it's event-driven by ticks, we need to find that entry point.
                # If it's a polling loop, updating the data provider might be enough.
                
        # 5. Simulate a Signal (Force a trade)
        if i == 5:
            logger.info("⚡ SIMULATION: Forcing BUY signal for INFY")
            # Manually trigger a trade execution to verify the pipeline
            # We can use the portfolio's execute_trade method directly to test that path
            # Or better, inject a signal into the strategy
            
            # Calculate shares based on risk (simplified for simulation)
            price = base_prices['INFY']
            shares = int(100000 * 0.02 / (price * 0.01)) # 2% risk, 1% stop loss
            
            result = system.portfolio.execute_trade(
                symbol='INFY',
                shares=shares,
                price=price,
                side='BUY',
                strategy='SimulationStrategy',
                confidence=0.9
            )
            logger.info(f"Trade Execution Result: {result}")
            
        if i == 10:
             logger.info("⚡ SIMULATION: Forcing SELL signal for INFY (Profit Booking)")
             # Close position
             result = system.portfolio.execute_trade(
                symbol='INFY',
                shares=shares, # Assuming same shares
                price=base_prices['INFY'],
                side='SELL',
                strategy='SimulationStrategy',
                confidence=0.9
            )
             logger.info(f"Trade Execution Result: {result}")

        time.sleep(1) # 1 second per tick batch

    # 6. Verify Results
    logger.info("Simulation complete. Verifying state...")
    
    orders = mock_kite.orders
    positions = mock_kite.positions
    
    logger.info(f"Total Orders: {len(orders)}")
    logger.info(f"Open Positions: {len(positions)}")
    
    for order in orders:
        logger.info(f"Order: {order['transaction_type']} {order['tradingsymbol']} @ {order['price']}")
        
    if len(orders) >= 2:
        logger.info("✅ SUCCESS: Orders were placed and executed.")
    else:
        logger.warning("❌ FAILURE: No orders were executed.")

    # Stop system
    system.user_stop_and_save_trades()
    logger.info("System stopped.")

if __name__ == "__main__":
    run_simulation()
