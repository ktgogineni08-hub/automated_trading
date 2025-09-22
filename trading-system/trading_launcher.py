#!/usr/bin/env python3
"""
Complete Trading System Launcher
Provides options to launch dashboard, trading system, or both
"""

import os
import sys
import subprocess
import webbrowser
import time
import threading
from pathlib import Path

class TradingLauncher:
    def __init__(self):
        self.trading_system_dir = Path("/Users/gogineni/Python/myenv/trading-system")
        self.dashboard_process = None
        self.trading_process = None
    
    def check_files(self):
        """Check if all required files exist"""
        required_files = [
            "enhanced_trading_system_complete.py",
            "enhanced_dashboard_server.py", 
            "enhanced_dashboard.html"
        ]
        
        missing_files = []
        for file in required_files:
            if not (self.trading_system_dir / file).exists():
                missing_files.append(file)
        
        if missing_files:
            print("❌ Missing required files:")
            for file in missing_files:
                print(f"   - {file}")
            return False
        
        return True
    
    def launch_dashboard(self):
        """Launch the dashboard server"""
        print("📊 Starting Enhanced Trading Dashboard...")
        
        try:
            os.chdir(self.trading_system_dir)
            self.dashboard_process = subprocess.Popen(
                [sys.executable, "enhanced_dashboard_server.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for server to start
            time.sleep(3)
            
            # Open browser
            try:
                webbrowser.open("http://localhost:5173")
                print("✅ Dashboard started and opened in browser")
                print("   URL: http://localhost:5173")
            except Exception:
                print("✅ Dashboard started at: http://localhost:5173")
                print("   (Please open this URL in your browser)")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to start dashboard: {e}")
            return False
    
    def launch_trading_system(self):
        """Launch the trading system"""
        print("🚀 Starting Enhanced NIFTY 50 Trading System...")
        
        try:
            os.chdir(self.trading_system_dir)
            self.trading_process = subprocess.Popen([sys.executable, "enhanced_trading_system_complete.py"])
            print("✅ Trading system started")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start trading system: {e}")
            return False
    
    def test_dashboard(self):
        """Test dashboard integration"""
        print("🧪 Testing Dashboard Integration...")
        
        try:
            os.chdir(self.trading_system_dir)
            result = subprocess.run([sys.executable, "test_dashboard_integration.py"], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("✅ Dashboard integration test passed")
                print(result.stdout)
            else:
                print("❌ Dashboard integration test failed")
                print(result.stderr)
            
        except subprocess.TimeoutExpired:
            print("⏰ Test timed out - dashboard may not be running")
        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    def stop_processes(self):
        """Stop all running processes"""
        if self.dashboard_process:
            self.dashboard_process.terminate()
            print("🛑 Dashboard stopped")
        
        if self.trading_process:
            self.trading_process.terminate()
            print("🛑 Trading system stopped")

def main():
    print("🎯 Enhanced NIFTY 50 Trading System Launcher")
    print("="*60)
    
    launcher = TradingLauncher()
    
    # Check if files exist
    if not launcher.check_files():
        print("\n❌ Cannot proceed - missing required files")
        return 1
    
    print("✅ All required files found")
    print(f"📁 Working directory: {launcher.trading_system_dir}")
    
    while True:
        print("\n" + "="*60)
        print("🎛️  MAIN MENU")
        print("="*60)
        print("1. 📊 Start Dashboard Only")
        print("2. 🚀 Start Trading System Only") 
        print("3. 🎯 Start Both (Recommended)")
        print("4. 🧪 Test Dashboard Integration")
        print("5. ⚡ Quick Token Test (Fix Auth Issues)")
        print("6. 🔧 Use Improved Trading System")
        print("7. 🎯 Select Trading Mode (Live/Paper/Backtest)")
        print("8. 🔧 Fix Dashboard Connection (Stop Demo Mode)")
        print("9. 🧪 Test Live Data Connection")
        print("10. 📖 View Quick Start Guide")
        print("11. 🛑 Exit")
        print("="*60)
        
        try:
            choice = input("Enter your choice (1-11): ").strip()
            
            if choice == "1":
                print("\n" + "="*40)
                if launcher.launch_dashboard():
                    print("\n✅ Dashboard is running!")
                    print("📊 Open http://localhost:5173 in your browser")
                    print("🔄 Dashboard will show demo data until trading system connects")
                    input("\nPress Enter to return to menu...")
                
            elif choice == "2":
                print("\n" + "="*40)
                print("⚠️  Note: Start dashboard first for best experience")
                confirm = input("Continue without dashboard? (y/n): ").strip().lower()
                if confirm == 'y':
                    if launcher.launch_trading_system():
                        print("\n✅ Trading system is running!")
                        print("💡 Tip: Start dashboard in another terminal to monitor trades")
                        try:
                            launcher.trading_process.wait()
                        except KeyboardInterrupt:
                            print("\n🛑 Trading system stopped by user")
                
            elif choice == "3":
                print("\n" + "="*40)
                print("🎯 Starting Complete Trading System...")
                
                # Start dashboard first
                if launcher.launch_dashboard():
                    print("✅ Dashboard started")
                    
                    # Wait a moment
                    time.sleep(2)
                    
                    # Start trading system
                    if launcher.launch_trading_system():
                        print("✅ Trading system started")
                        print("\n🎉 Complete system is running!")
                        print("📊 Dashboard: http://localhost:5173")
                        print("🚀 Trading system: Running with dashboard integration")
                        print("\n💡 Tips:")
                        print("   - Keep dashboard open in browser")
                        print("   - Monitor real-time signals and trades")
                        print("   - Press Ctrl+C to stop")
                        
                        try:
                            # Wait for trading system to complete
                            launcher.trading_process.wait()
                        except KeyboardInterrupt:
                            print("\n🛑 Stopping all processes...")
                            launcher.stop_processes()
                    else:
                        launcher.stop_processes()
                
            elif choice == "4":
                print("\n" + "="*40)
                launcher.test_dashboard()
                input("\nPress Enter to return to menu...")
                
            elif choice == "5":
                print("\n" + "="*40)
                print("⚡ Quick Token Test - Fix Authentication Issues")
                try:
                    subprocess.run([sys.executable, "quick_token_test.py"])
                except Exception as e:
                    print(f"❌ Error running token test: {e}")
                input("\nPress Enter to return to menu...")
                
            elif choice == "6":
                print("\n" + "="*40)
                print("🔧 Starting Improved Trading System (Better Token Management)")
                try:
                    subprocess.run([sys.executable, "improved_trading_system.py"])
                except Exception as e:
                    print(f"❌ Error running improved system: {e}")
                input("\nPress Enter to return to menu...")
                
            elif choice == "7":
                print("\n" + "="*40)
                print("🎯 Select Trading Mode (Live/Paper/Backtest)")
                try:
                    subprocess.run([sys.executable, "trading_mode_selector.py"])
                except Exception as e:
                    print(f"❌ Error running mode selector: {e}")
                input("\nPress Enter to return to menu...")
                
            elif choice == "8":
                print("\n" + "="*40)
                print("🔧 Fix Dashboard Connection - Stop Demo Mode")
                try:
                    subprocess.run([sys.executable, "fix_dashboard_connection.py"])
                except Exception as e:
                    print(f"❌ Error fixing dashboard: {e}")
                input("\nPress Enter to return to menu...")
                
            elif choice == "9":
                print("\n" + "="*40)
                print("🧪 Test Live Data Connection")
                try:
                    subprocess.run([sys.executable, "test_live_connection.py"])
                except Exception as e:
                    print(f"❌ Error testing live connection: {e}")
                input("\nPress Enter to return to menu...")
                
            elif choice == "10":
                print("\n" + "="*40)
                print("📖 QUICK START GUIDE")
                print("="*40)
                print("1. Choose option 7 to select trading mode (Live/Paper/Backtest)")
                print("2. Choose option 3 to start both dashboard and trading system")
                print("3. Open http://localhost:5173 in your browser")
                print("4. Watch real-time trading signals and performance")
                print("\n🎯 Trading Modes:")
                print("   🔴 Live Trading: Real money, actual orders")
                print("   📝 Paper Trading: Safe simulation with real data")
                print("   📊 Backtesting: Historical data analysis")
                print("\n⚡ If you have issues:")
                print("   - Token problems: Use option 5")
                print("   - Demo mode stuck: Use option 8")
                print("   - No live data: Use option 9")
                input("\nPress Enter to return to menu...")
                
            elif choice == "11":
                print("\n🛑 Stopping all processes and exiting...")
                launcher.stop_processes()
                print("👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid choice. Please enter 1-11.")
                
        except KeyboardInterrupt:
            print("\n\n🛑 Interrupted by user")
            launcher.stop_processes()
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())