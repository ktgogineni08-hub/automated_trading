#!/usr/bin/env python3
"""
Dashboard Launcher
Launches the enhanced trading dashboard from the correct directory
"""

import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path
from trading_config import TradingConfig

def main():
    print("📊 Enhanced Trading Dashboard Launcher")
    print("="*50)
    trading_cfg = TradingConfig.from_env()
    dashboard_url = getattr(trading_cfg, "dashboard_url", "https://localhost:8080")
    
    # Define the correct path
    trading_system_dir = Path(__file__).parent
    dashboard_server_file = trading_system_dir / "enhanced_dashboard_server.py"
    
    # Check if directory exists
    if not trading_system_dir.exists():
        print(f"❌ Trading system directory not found: {trading_system_dir}")
        return 1
    
    # Check if dashboard server file exists
    if not dashboard_server_file.exists():
        print(f"❌ Dashboard server file not found: {dashboard_server_file}")
        return 1
    
    print(f"✅ Found dashboard server at: {dashboard_server_file}")
    print(f"📁 Working directory: {trading_system_dir}")
    
    # Change to the correct directory and run the dashboard
    try:
        print("\n🌐 Starting Enhanced Trading Dashboard...")
        print(f"   URL: {dashboard_url}")
        print("   Press Ctrl+C to stop\n")
        
        # Change directory and run the dashboard server
        os.chdir(trading_system_dir)
        
        # Start the server in a subprocess so we can open browser
        process = subprocess.Popen([sys.executable, "enhanced_dashboard_server.py"])
        
        # Wait a moment for server to start, then open browser
        print("⏳ Waiting for server to start...")
        time.sleep(3)
        
        try:
            print("🌐 Opening dashboard in browser...")
            webbrowser.open(dashboard_url)
        except Exception:
            print(f"   (Could not auto-open browser - please go to {dashboard_url})")
        
        # Wait for the process to complete
        process.wait()
        
    except KeyboardInterrupt:
        print("\n\n🛑 Dashboard stopped by user")
        if 'process' in locals():
            process.terminate()
        return 0
    except Exception as e:
        print(f"\n❌ Error running dashboard: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
