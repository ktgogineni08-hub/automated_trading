#!/usr/bin/env python3
"""
Trading System Launcher
Launches the enhanced NIFTY 50 trading system from the correct directory
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    print("🚀 NIFTY 50 Trading System Launcher")
    print("="*50)
    
    # Define the correct path
    trading_system_dir = Path(__file__).parent
    trading_system_file = trading_system_dir / "enhanced_trading_system_complete.py"

    print(f"📁 Current working directory: {os.getcwd()}")
    print(f"🎯 Target directory: {trading_system_dir}")
    
    # Check if directory exists
    if not trading_system_dir.exists():
        print(f"❌ Trading system directory not found: {trading_system_dir}")
        return 1
    
    # Check if trading system file exists
    if not trading_system_file.exists():
        print(f"❌ Trading system file not found: {trading_system_file}")
        return 1
    
    print(f"✅ Found trading system at: {trading_system_file}")
    print(f"📁 Working directory: {trading_system_dir}")
    
    # Change to the correct directory and run the trading system
    try:
        print("\n🎯 Starting Enhanced NIFTY 50 Trading System...")
        print("   (This will start the trading system with dashboard integration)")
        print("   Press Ctrl+C to stop\n")
        
        # Change directory and run the script
        os.chdir(trading_system_dir)
        subprocess.run([sys.executable, "enhanced_trading_system_complete.py"])
        
    except KeyboardInterrupt:
        print("\n\n🛑 Trading system stopped by user")
        return 0
    except Exception as e:
        print(f"\n❌ Error running trading system: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())