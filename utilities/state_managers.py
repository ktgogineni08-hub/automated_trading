#!/usr/bin/env python3
"""
State Management
Trading state persistence and recovery
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime, time as datetime_time
from typing import Any, Dict, Optional
import logging

import pytz

from safe_file_ops import atomic_write_json
from infrastructure.security import SecureStateManager

logger = logging.getLogger('trading_system.state_managers')

class TradingStateManager:
    """Handles persistence of trading state and trade history across sessions."""

    def __init__(self, base_dir: str = None, security_context: Any = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent / "state"
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.archive_dir = self.base_dir / "archive"
        self.archive_dir.mkdir(exist_ok=True)

        self.trades_dir = self.base_dir / "trades"
        self.trades_dir.mkdir(exist_ok=True)

        self.state_path = self.base_dir / "current_state.json"
        self.ist = pytz.timezone('Asia/Kolkata')
        self.security_context = security_context
        self.data_protection = getattr(security_context, "data_protection", None) if security_context else None
        self.secure_manager: Optional[SecureStateManager] = None
        self.encryption_enabled = False
        self.encrypted_filename = "current_state.enc"

        security_config = None
        if security_context:
            try:
                security_config = security_context.get_state_encryption_settings()
            except AttributeError:
                security_config = None

        if security_config:
            self._configure_security(security_config)

    def _configure_security(self, security_config: Dict[str, Any]) -> None:
        """Configure encrypted state persistence when enabled."""
        state_enc = security_config or {}
        if not state_enc.get("enabled"):
            return

        password = state_enc.get("password")
        if not password:
            env_var = state_enc.get("password_env", "TRADING_SECURITY_PASSWORD")
            if env_var:
                password = os.getenv(env_var)
        if not password:
            raise RuntimeError(
                "State encryption enabled but TRADING_SECURITY_PASSWORD (or configured password) is missing."
            )

        try:
            self.secure_manager = SecureStateManager(master_password=password)
            filename = state_enc.get("filename", "current_state.enc")
            self.encrypted_filename = Path(filename).name if isinstance(filename, str) else "current_state.enc"
            self.encryption_enabled = True
            logger.info("🔐 State encryption enabled (target file: %s)", self.encrypted_filename)
        except Exception as exc:
            raise RuntimeError(f"Failed to initialize SecureStateManager: {exc}") from exc

    def current_trading_day(self) -> str:
        return datetime.now(self.ist).strftime('%Y-%m-%d')

    def load_state(self) -> Dict:
        if self.encryption_enabled and self.secure_manager:
            try:
                if self.security_context:
                    self.security_context.log_state_access("read")
                encrypted_state = self.secure_manager.load_encrypted_state(self.encrypted_filename)
                if encrypted_state:
                    return encrypted_state
                logger.warning("Encrypted state not found; falling back to sanitized state file.")
            except Exception as exc:
                logger.error(f"Failed to load encrypted state: {exc}")

        if not self.state_path.exists():
            return {}
        try:
            with self.state_path.open('r', encoding='utf-8') as handle:
                return json.load(handle)
        except Exception as exc:
            logger.error(f"Failed to load saved trading state: {exc}")
            return {}

    def save_state(self, state: Dict) -> None:
        try:
            # Convert datetime objects to ISO format strings for JSON serialization
            serializable_state = self._make_json_serializable(state)
            if self.encryption_enabled and self.secure_manager:
                if self.security_context:
                    self.security_context.log_state_access("write")
                success = self.secure_manager.save_encrypted_state(serializable_state, self.encrypted_filename)
                if success:
                    self._write_sanitized_state(serializable_state)
                    return
                logger.error("Failed to persist encrypted state; falling back to plaintext storage.")

            if self.security_context:
                self.security_context.log_state_access("write")
            # Use atomic write from safe_file_ops
            atomic_write_json(self.state_path, serializable_state, create_backup=True)
        except Exception as exc:
            logger.error(f"Failed to persist trading state: {exc}")

    def _make_json_serializable(self, obj):
        """Convert datetime objects and other non-serializable objects to JSON-compatible format"""
        if isinstance(obj, dict):
            return {key: self._make_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            # Handle custom objects by converting to dict
            return self._make_json_serializable(obj.__dict__)
        else:
            return obj

    def archive_state(self, state: Dict) -> None:
        trading_day = state.get('trading_day') or self.current_trading_day()
        archive_path = self.archive_dir / f"state_{trading_day}.json"
        try:
            # Convert datetime objects to ISO format strings for JSON serialization
            serializable_state = self._make_json_serializable(state)
            with archive_path.open('w', encoding='utf-8') as handle:
                json.dump(serializable_state, handle, indent=2, default=str)
        except Exception as exc:
            logger.error(f"Failed to archive trading state: {exc}")

    def _write_sanitized_state(self, state: Dict[str, Any]) -> None:
        """Persist a sanitized snapshot for dashboard bootstrapping."""
        try:
            sanitized = self._build_sanitized_state(state)
            atomic_write_json(self.state_path, sanitized, create_backup=True)
        except Exception as exc:
            logger.error(f"Failed to write sanitized state file: {exc}")

    def _build_sanitized_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Return non-sensitive subset of state for plaintext storage."""
        portfolio = state.get('portfolio', {}) or {}
        sanitized_portfolio = {
            'cash': portfolio.get('cash'),
            'total_pnl': portfolio.get('total_pnl'),
            'positions_count': len(portfolio.get('positions', {}) or {}),
            'trades_count': portfolio.get('trades_count'),
            'winning_trades': portfolio.get('winning_trades'),
            'losing_trades': portfolio.get('losing_trades')
        }
        sanitized = {
            'mode': state.get('mode'),
            'iteration': state.get('iteration'),
            'trading_day': state.get('trading_day'),
            'last_update': state.get('last_update'),
            'total_value': state.get('total_value'),
            'portfolio': sanitized_portfolio,
            'day_close_executed': state.get('day_close_executed'),
        }
        return sanitized

    def log_trade(self, trade: Dict, trading_day: str = None) -> None:
        day = trading_day or self.current_trading_day()
        trades_path = self.trades_dir / f"trades_{day}.jsonl"
        try:
            # Convert datetime objects to ISO format strings for JSON serialization
            serializable_trade = self._make_json_serializable(trade)
            with trades_path.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(serializable_trade, default=str) + "\n")
        except Exception as exc:
            logger.error(f"Failed to log trade: {exc}")

    def write_daily_summary(self, trading_day: str, summary: Dict) -> None:
        summary_path = self.archive_dir / f"summary_{trading_day}.json"
        try:
            # Convert datetime objects to ISO format strings for JSON serialization
            serializable_summary = self._make_json_serializable(summary)
            with summary_path.open('w', encoding='utf-8') as handle:
                json.dump(serializable_summary, handle, indent=2, default=str)
        except Exception as exc:
            logger.error(f"Failed to write daily summary: {exc}")

# ============================================================================
# MARKET COMPONENTS
# ============================================================================
class MarketHours:
    def __init__(self):
        self.ist = pytz.timezone('Asia/Kolkata')
        self.market_open = datetime.strptime("09:15", "%H:%M").time()
        self.market_close = datetime.strptime("15:30", "%H:%M").time()

    def is_market_open(self) -> bool:
        now = datetime.now(self.ist).replace(tzinfo=None)
        if now.weekday() >= 5:
            return False
        current_time = now.time()
        # FIXED: Stop trading AT 3:30 PM, not after
        return self.market_open <= current_time < self.market_close

class MarketHoursManager:
    """Enhanced market hours management with trading restrictions"""

    def __init__(self):
        # LOW PRIORITY FIX: Removed redundant import - using datetime_time from top
        self.ist = pytz.timezone('Asia/Kolkata')
        self.market_open = datetime_time(9, 15)  # 9:15 AM
        self.market_close = datetime_time(15, 30)  # 3:30 PM

    def is_market_open(self) -> bool:
        """Check if Indian stock market is currently open"""
        now = datetime.now(self.ist).replace(tzinfo=None)
        current_time = now.time()
        current_weekday = now.weekday()  # 0=Monday, 6=Sunday

        # Market hours: 9:15 AM to 3:30 PM IST, Monday to Friday
        # FIXED: Stop trading AT 3:30 PM, not after
        is_weekday = current_weekday < 5  # Monday to Friday
        is_trading_hours = self.market_open <= current_time < self.market_close

        return is_weekday and is_trading_hours

    def can_trade(self) -> tuple[bool, str]:
        """Check if trading is allowed and return reason"""
        if not self.is_market_open():
            now = datetime.now(self.ist).replace(tzinfo=None)
            current_time = now.time()
            current_weekday = now.weekday()

            if current_weekday >= 5:  # Weekend
                return False, "❌ WEEKEND - Market closed"
            elif current_time < self.market_open:
                return False, "❌ PRE-MARKET - Trading starts at 9:15 AM"
            elif current_time > self.market_close:
                return False, "❌ POST-MARKET - Trading ended at 3:30 PM"
            else:
                return False, "❌ MARKET CLOSED"

        return True, "✅ TRADING ALLOWED - Market is open"

    def time_until_market_open(self) -> str:
        """Get time until market opens"""
        now = datetime.now(self.ist).replace(tzinfo=None)

        if now.weekday() >= 5:  # Weekend
            days_until_monday = 7 - now.weekday()
            return f"{days_until_monday} days until Monday"

        if now.time() < self.market_open:
            # Market opens today
            market_open_today = datetime.combine(now.date(), self.market_open)
            time_diff = market_open_today - now
            hours, remainder = divmod(int(time_diff.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            return f"{hours}h {minutes}m until market open"

        return "Market is open or closed for the day"

    def should_save_data(self) -> bool:
        """Check if data should be saved (after market hours)"""
        return not self.is_market_open()

class EnhancedStateManager:
    """Enhanced state management with market hours and proper data saving"""

    def __init__(self, base_dir: str = None):
        # LOW PRIORITY FIX: Removed redundant Path import - already imported at top
        if base_dir is None:
            base_dir = Path(__file__).parent
        self.base_dir = Path(base_dir)
        self.state_dir = self.base_dir / 'state'
        self.state_file = self.state_dir / 'current_state.json'
        self.archive_dir = self.state_dir / 'archive'
        self.market_hours = MarketHoursManager()

        # Ensure directories exist
        self.state_dir.mkdir(exist_ok=True)
        self.archive_dir.mkdir(exist_ok=True)

    def can_trade(self) -> tuple[bool, str]:
        """Check if trading is allowed and return reason"""
        return self.market_hours.can_trade()

    def save_state_if_needed(self, state_data: dict, force: bool = False):
        """Save state data only after trading hours or if forced"""
        can_trade_now, reason = self.can_trade()

        if not can_trade_now or force:
            self.save_state(state_data)
            logger.info(f"💾 State saved: {reason}")
        else:
            logger.info("⏳ State save deferred: Market is open")

    def save_state(self, state_data: dict):
        """Save current state to file"""
        try:
            # LOW PRIORITY FIX: Removed redundant json import - already imported at top
            # Add timestamp
            state_data['last_update'] = datetime.now().isoformat()
            state_data['saved_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Save current state
            # MEDIUM PRIORITY FIX: Add UTF-8 encoding for cross-platform compatibility
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2)

            # Archive daily state if it's end of trading day
            now = datetime.now()
            if now.time() > self.market_hours.market_close:  # After market close
                archive_file = self.archive_dir / f"state_{now.strftime('%Y-%m-%d')}.json"
                with open(archive_file, 'w', encoding='utf-8') as f:
                    json.dump(state_data, f, indent=2)
                logger.info(f"📁 Daily state archived: {archive_file.name}")

            logger.info("✅ State saved successfully")

        except Exception as e:
            logger.error(f"❌ Error saving state: {e}")

    def load_state(self) -> dict:
        """Load current state from file"""
        try:
            # LOW PRIORITY FIX: Removed redundant json import - already imported at top
            if self.state_file.exists():
                # MEDIUM PRIORITY FIX: Added UTF-8 encoding for cross-platform compatibility
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                logger.info(f"✅ State loaded from {self.state_file.name}")
                return state
            else:
                logger.info("ℹ️ No existing state file, creating new state")
                return self.create_default_state()

        except Exception as e:
            logger.error(f"❌ Error loading state: {e}")
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
