#!/usr/bin/env python3
"""
Cleanup old portfolio data and implement proper data saving with market hours restrictions
"""

import os
import sys
import json
import shutil
from datetime import datetime, time
from pathlib import Path

# Add the current directory to Python path
sys.path.append('/Users/gogineni/Python/trading-system')

def cleanup_old_data():
    """Clean up old portfolio data files"""
    print("🧹 Cleaning up old portfolio data...")

    base_dir = Path('/Users/gogineni/Python/trading-system')

    # Files and directories to clean up
    cleanup_targets = [
        'state/current_state.json',
        'state/fno_system_state.json',
        'state/shared_portfolio_state.json',
        'state/overnight_positions_2025-09-29.json',
        'saved_trades/positions_2025-09-30.json',
        'saved_trades/fno_positions_2025-09-30_used.json'
    ]

    cleaned_count = 0
    for target in cleanup_targets:
        file_path = base_dir / target
        if file_path.exists():
            try:
                if file_path.is_file():
                    file_path.unlink()
                    print(f"✅ Deleted: {target}")
                    cleaned_count += 1
                elif file_path.is_dir():
                    shutil.rmtree(file_path)
                    print(f"✅ Deleted directory: {target}")
                    cleaned_count += 1
            except Exception as e:
                print(f"❌ Error deleting {target}: {e}")

    print(f"🧹 Cleaned up {cleaned_count} old data files")
    return cleaned_count

def create_clean_state_structure():
    """Create a clean state directory structure"""
    print("📁 Creating clean state structure...")

    base_dir = Path('/Users/gogineni/Python/trading-system')

    # Create required directories
    directories = [
        'state',
        'state/archive',
        'state/trades',
        'state/daily',
        'saved_trades'
    ]

    for dir_path in directories:
        full_path = base_dir / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created/ensured: {dir_path}")

    # Create initial clean state file
    clean_state = {
        "mode": "paper",
        "iteration": 0,
        "trading_day": datetime.now().strftime('%Y-%m-%d'),
        "last_update": datetime.now().isoformat(),
        "portfolio": {
            "initial_cash": 1000000.0,
            "cash": 1000000.0,
            "positions": {},
            "total_value": 1000000.0,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0
        },
        "trading_session": {
            "session_start": None,
            "session_end": None,
            "market_hours_active": False,
            "trades_executed": 0,
            "last_trade_time": None
        },
        "performance": {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0
        }
    }

    state_file = base_dir / 'state/current_state.json'
    with open(state_file, 'w') as f:
        json.dump(clean_state, f, indent=2)

    print(f"✅ Created clean state file: {state_file}")

def test_market_hours_logic():
    """Test market hours detection logic"""
    print("🕒 Testing market hours logic...")

    # Indian market hours: 9:15 AM to 3:30 PM IST
    market_open = time(9, 15)
    market_close = time(15, 30)

    current_time = datetime.now().time()
    current_weekday = datetime.now().weekday()  # 0=Monday, 6=Sunday

    # Check if it's a weekday (Monday=0 to Friday=4)
    is_weekday = current_weekday < 5

    # Check if current time is within market hours
    is_market_hours = market_open <= current_time <= market_close

    # Overall market status
    market_open_now = is_weekday and is_market_hours

    print(f"📅 Current Day: {datetime.now().strftime('%A, %Y-%m-%d')}")
    print(f"🕐 Current Time: {current_time.strftime('%H:%M:%S')}")
    print(f"📊 Is Weekday: {is_weekday}")
    print(f"🕘 Market Hours (9:15-15:30): {is_market_hours}")
    print(f"🏛️ Market Open Now: {market_open_now}")

    if market_open_now:
        print("✅ TRADING ALLOWED - Market is open")
    else:
        if not is_weekday:
            print("❌ TRADING BLOCKED - Weekend")
        elif current_time < market_open:
            print("❌ TRADING BLOCKED - Before market open")
        elif current_time > market_close:
            print("❌ TRADING BLOCKED - After market close")

    return market_open_now

def create_enhanced_state_manager():
    """Create enhanced state management code"""
    print("💾 Creating enhanced state management...")

    code = '''
class EnhancedStateManager:
    """Enhanced state management with market hours and proper data saving"""

    def __init__(self, base_dir: str = '/Users/gogineni/Python/trading-system'):
        self.base_dir = Path(base_dir)
        self.state_dir = self.base_dir / 'state'
        self.state_file = self.state_dir / 'current_state.json'
        self.archive_dir = self.state_dir / 'archive'

        # Ensure directories exist
        self.state_dir.mkdir(exist_ok=True)
        self.archive_dir.mkdir(exist_ok=True)

    def is_market_open(self) -> bool:
        """Check if Indian stock market is currently open"""
        from datetime import datetime, time

        now = datetime.now()
        current_time = now.time()
        current_weekday = now.weekday()  # 0=Monday, 6=Sunday

        # Market hours: 9:15 AM to 3:30 PM IST, Monday to Friday
        market_open = time(9, 15)
        market_close = time(15, 30)

        is_weekday = current_weekday < 5  # Monday to Friday
        is_trading_hours = market_open <= current_time <= market_close

        return is_weekday and is_trading_hours

    def can_trade(self) -> tuple[bool, str]:
        """Check if trading is allowed and return reason"""
        if not self.is_market_open():
            now = datetime.now()
            current_time = now.time()
            current_weekday = now.weekday()

            if current_weekday >= 5:  # Weekend
                return False, "❌ WEEKEND - Market closed"
            elif current_time < time(9, 15):
                return False, "❌ PRE-MARKET - Trading starts at 9:15 AM"
            elif current_time > time(15, 30):
                return False, "❌ POST-MARKET - Trading ended at 3:30 PM"
            else:
                return False, "❌ MARKET CLOSED"

        return True, "✅ TRADING ALLOWED - Market is open"

    def save_state_if_needed(self, state_data: dict, force: bool = False):
        """Save state data only after trading hours or if forced"""
        can_trade_now, reason = self.can_trade()

        if not can_trade_now or force:
            self.save_state(state_data)
            print(f"💾 State saved: {reason}")
        else:
            print(f"⏳ State save deferred: Market is open")

    def save_state(self, state_data: dict):
        """Save current state to file"""
        try:
            # Add timestamp
            state_data['last_update'] = datetime.now().isoformat()
            state_data['saved_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Save current state
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)

            # Archive daily state if it's end of trading day
            now = datetime.now()
            if now.time() > time(15, 30):  # After market close
                archive_file = self.archive_dir / f"state_{now.strftime('%Y-%m-%d')}.json"
                with open(archive_file, 'w') as f:
                    json.dump(state_data, f, indent=2)
                print(f"📁 Daily state archived: {archive_file.name}")

            print(f"✅ State saved successfully")

        except Exception as e:
            print(f"❌ Error saving state: {e}")

    def load_state(self) -> dict:
        """Load current state from file"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                print(f"✅ State loaded from {self.state_file.name}")
                return state
            else:
                print(f"ℹ️ No existing state file, creating new state")
                return self.create_default_state()

        except Exception as e:
            print(f"❌ Error loading state: {e}")
            return self.create_default_state()

    def create_default_state(self) -> dict:
        """Create default state structure"""
        return {
            "mode": "paper",
            "iteration": 0,
            "trading_day": datetime.now().strftime('%Y-%m-%d'),
            "last_update": datetime.now().isoformat(),
            "portfolio": {
                "initial_cash": 1000000.0,
                "cash": 1000000.0,
                "positions": {},
                "total_value": 1000000.0,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0
            },
            "trading_session": {
                "session_start": None,
                "session_end": None,
                "market_hours_active": False,
                "trades_executed": 0,
                "last_trade_time": None
            },
            "performance": {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "total_pnl": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0
            }
        }
'''

    # Write to a separate file for reference
    code_file = Path('/Users/gogineni/Python/trading-system/enhanced_state_manager.py')
    with open(code_file, 'w') as f:
        f.write(code)

    print(f"✅ Enhanced state manager code saved to: {code_file}")

def main():
    """Main cleanup and setup function"""
    print("🔧 Portfolio Data Cleanup and Enhancement")
    print("=" * 60)

    # Step 1: Clean up old data
    cleanup_old_data()
    print()

    # Step 2: Create clean structure
    create_clean_state_structure()
    print()

    # Step 3: Test market hours logic
    market_open = test_market_hours_logic()
    print()

    # Step 4: Create enhanced state manager
    create_enhanced_state_manager()
    print()

    print("✅ CLEANUP AND ENHANCEMENT COMPLETE!")
    print("=" * 60)
    print("📊 Summary:")
    print("  ✅ Old portfolio data cleaned up")
    print("  ✅ Clean state structure created")
    print("  ✅ Market hours logic implemented")
    print("  ✅ Enhanced state manager created")
    print()

    if market_open:
        print("🏛️ Market is currently OPEN - Trading allowed")
    else:
        print("🔒 Market is currently CLOSED - No trading allowed")

    print("\n💡 Next steps:")
    print("  1. System will only trade during market hours (9:15-15:30)")
    print("  2. Data will be saved after trading hours or when stopped")
    print("  3. Daily states will be automatically archived")
    print("  4. Clean portfolio tracking with proper persistence")

if __name__ == "__main__":
    main()