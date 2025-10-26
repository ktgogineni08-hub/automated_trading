
import json
from datetime import datetime, time
from pathlib import Path

# CRITICAL FIX: Import IST-aware time functions to prevent trading during off-hours
from trading_utils import get_ist_now

class EnhancedStateManager:
    """Enhanced state management with market hours and proper data saving"""

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = Path(__file__).parent
        self.base_dir = Path(base_dir)
        self.state_dir = self.base_dir / 'state'
        self.state_file = self.state_dir / 'current_state.json'
        self.archive_dir = self.state_dir / 'archive'

        # Ensure directories exist
        self.state_dir.mkdir(exist_ok=True)
        self.archive_dir.mkdir(exist_ok=True)

    def is_market_open(self) -> bool:
        """Check if Indian stock market is currently open"""
        # CRITICAL FIX: Use IST-aware time to prevent timezone issues
        now = get_ist_now()
        current_time = now.time()
        current_weekday = now.weekday()  # 0=Monday, 6=Sunday

        # Market hours: 9:15 AM to 3:30 PM IST, Monday to Friday
        market_open = time(9, 15)
        market_close = time(15, 30)

        is_weekday = current_weekday < 5  # Monday to Friday
        # FIXED: Stop trading AT 3:30 PM, not after
        is_trading_hours = market_open <= current_time < market_close

        return is_weekday and is_trading_hours

    def can_trade(self) -> tuple[bool, str]:
        """Check if trading is allowed and return reason"""
        if not self.is_market_open():
            # CRITICAL FIX: Use IST-aware time to prevent timezone issues
            now = get_ist_now()
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
            # Add timestamp - CRITICAL FIX: Use IST-aware time
            now = get_ist_now()
            state_data['last_update'] = now.isoformat()
            state_data['saved_at'] = now.strftime('%Y-%m-%d %H:%M:%S')

            # Save current state
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)

            # Archive daily state if it's end of trading day
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
        # CRITICAL FIX: Use IST-aware time
        now = get_ist_now()
        return {
            "mode": "paper",
            "iteration": 0,
            "trading_day": now.strftime('%Y-%m-%d'),
            "last_update": now.isoformat(),
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
