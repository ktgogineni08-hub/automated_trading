#!/usr/bin/env python3
"""
Script to start paper trading mode directly with default settings
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the main function and run it with default settings
from enhanced_trading_system_complete import run_trading_system_directly

if __name__ == "__main__":
    # Configuration for paper trading with default settings
    config = {
        'virtual_capital': 1000000,
        'use_real_data': True,
        'simulate_trades': True,
        'live_trading': False,
        'paper_trading': True,
        'trading_profile': 'Balanced',  # Default profile
        'min_confidence': 0.6,
        'top_n': 2,
        'max_positions': 15,
        'stop_loss_pct': 0.05,
        'take_profit_pct': 0.12,
        'bypass_market_hours': True,  # Allow testing outside market hours
        'trend_filter_enabled': False  # Disable trend filter to allow more trades
    }

    print("🚀 Starting Paper Trading with default settings...")
    print(f"💰 Virtual Capital: ₹{config['virtual_capital']:,}")
    print(f"📊 Trading Profile: {config['trading_profile']}")
    print(f"🎯 Min Confidence: {config['min_confidence']:.0%}")
    print(f"📈 Max Positions: {config['max_positions']}")

    try:
        # Run the trading system directly in paper mode
        run_trading_system_directly('paper', config)
    except KeyboardInterrupt:
        print("\n🛑 Paper trading stopped by user")
    except Exception as e:
        print(f"\n❌ Error in paper trading: {e}")
        import traceback
        traceback.print_exc()