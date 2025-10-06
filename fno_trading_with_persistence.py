#!/usr/bin/env python3
"""
F&O Trading System with State Persistence
Launch F&O trading with automatic state saving and resumption capability
"""

import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.append('.')

def main():
    """Main F&O trading launcher with state persistence"""
    print("🚀 F&O TRADING SYSTEM WITH STATE PERSISTENCE")
    print("=" * 70)
    print("🎯 Automated F&O trading with session save/restore capability")
    print("💾 Automatically saves state when stopped (Ctrl+C)")
    print("🔄 Resumes from previous session when restarted")
    print("=" * 70)

    try:
        from enhanced_trading_system_complete import (
            create_fno_trading_system,
            DashboardConnector,
            UnifiedPortfolio
        )

        # Check for existing state
        state_file = 'state/fno_system_state.json'
        has_saved_state = os.path.exists(state_file)

        if has_saved_state:
            print(f"\n📂 Found previous trading session: {state_file}")
            print(f"   Last modified: {datetime.fromtimestamp(os.path.getmtime(state_file))}")

            resume = input("\n🔄 Resume from previous session? (y/n) [y]: ").strip().lower()
            if resume in ['', 'y', 'yes']:
                print("✅ Will resume from previous session")
                use_saved_state = True
            else:
                print("🆕 Starting fresh session")
                use_saved_state = False
        else:
            print("\n🆕 No previous session found, starting fresh")
            use_saved_state = False

        # Initialize trading system
        print("\n⚙️ Initializing F&O Trading System...")

        # Create dashboard connection
        dashboard = DashboardConnector("http://localhost:8888")

        # Create portfolio
        portfolio = UnifiedPortfolio(
            initial_cash=1000000.0,
            dashboard=dashboard,
            trading_mode='paper'  # Change to 'live' for real trading
        )

        # Create F&O trading system
        system = create_fno_trading_system(
            trading_mode='paper',  # Change to 'live' for real trading
            dashboard=dashboard
        )

        # Assign portfolio to system for state persistence
        system.portfolio = portfolio

        print("✅ Trading system initialized")

        # Load saved state if requested
        if use_saved_state:
            print("\n📥 Loading previous trading session...")
            loaded = system.load_system_state()
            if loaded:
                print("✅ Previous session loaded successfully!")
                print(f"   📊 Positions: {len(system.portfolio.positions)}")
                print(f"   💰 Cash: ₹{system.portfolio.cash:,.2f}")
                print(f"   🔢 Iteration: {getattr(system, 'iteration', 0)}")
            else:
                print("⚠️ Failed to load previous session, starting fresh")

        print(f"\n🌐 Dashboard available at: http://localhost:8888")
        print("📊 Monitor your portfolio in real-time through the web dashboard")

        # Start continuous F&O monitoring
        print("\n🚀 Starting F&O continuous monitoring...")
        print("💡 The system will automatically save state every 10 iterations")
        print("🛑 Press Ctrl+C to stop and save current session")
        print("-" * 70)

        # Run the F&O continuous monitoring system
        system.run_continuous_fno_monitoring()

    except KeyboardInterrupt:
        print("\n🛑 F&O Trading stopped by user")

        # Save trades before exit
        try:
            if hasattr(system, 'portfolio') and system.portfolio:
                print("💾 Saving current F&O portfolio state...")
                system.portfolio.save_state_to_files()
                print("✅ F&O portfolio state saved successfully")
        except Exception as e:
            print(f"❌ Error saving F&O portfolio state: {e}")

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure all required modules are available")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\n👋 F&O Trading session ended")
        print("📁 Session state has been saved for future resumption")

def show_saved_sessions():
    """Show information about saved trading sessions"""
    print("📂 SAVED TRADING SESSIONS")
    print("=" * 50)

    state_dir = 'state'
    if not os.path.exists(state_dir):
        print("No saved sessions found")
        return

    import json

    # Check main state file
    main_state = os.path.join(state_dir, 'fno_system_state.json')
    if os.path.exists(main_state):
        try:
            with open(main_state, 'r') as f:
                data = json.load(f)

            timestamp = data.get('timestamp', 'Unknown')
            iteration = data.get('iteration', 0)
            positions = len(data.get('portfolio', {}).get('positions', {}))
            cash = data.get('portfolio', {}).get('cash', 0)

            print(f"📊 Main Session:")
            print(f"   • Saved: {timestamp}")
            print(f"   • Iteration: {iteration}")
            print(f"   • Positions: {positions}")
            print(f"   • Cash: ₹{cash:,.2f}")

        except Exception as e:
            print(f"❌ Error reading main session: {e}")

    # Check other state files
    portfolio_state = os.path.join(state_dir, 'shared_portfolio_state.json')
    current_state = os.path.join(state_dir, 'current_state.json')

    if os.path.exists(portfolio_state):
        mod_time = datetime.fromtimestamp(os.path.getmtime(portfolio_state))
        print(f"📋 Portfolio State: Last updated {mod_time}")

    if os.path.exists(current_state):
        mod_time = datetime.fromtimestamp(os.path.getmtime(current_state))
        print(f"📈 Current State: Last updated {mod_time}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--show-sessions":
        show_saved_sessions()
    else:
        main()