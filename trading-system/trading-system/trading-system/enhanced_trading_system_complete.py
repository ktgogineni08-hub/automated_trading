#!/usr/bin/env python3
"""
Legacy compatibility shim for the historic `enhanced_trading_system_complete` module.
Modern code is split across packages, but the long-tail maintenance tests still import
the monolithic entry point. This module re-exports the refactored components while
retaining backwards-compatible helpers.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import config
from data.provider import DataProvider
from fno.data_provider import FNODataProvider as _ModernFNODataProvider
from fno.options import OptionChain
from core.signal_aggregator import EnhancedSignalAggregator
from core.trading_system import UnifiedTradingSystem as _UnifiedTradingSystem
from core.portfolio import UnifiedPortfolio as _UnifiedPortfolio
from utilities.dashboard import DashboardConnector as _DashboardConnector
from utilities.logger import TradingLogger
from utilities.market_hours import MarketHoursManager
from enhanced_state_manager import EnhancedStateManager
from safe_file_ops import atomic_write_json
from trading_utils import safe_float_conversion, validate_symbol

logger = logging.getLogger("trading_system.compat")


def _option_chain_to_legacy_dict(chain: OptionChain) -> Dict[str, Any]:
    """Convert the modern OptionChain object into the dict-based format legacy code expects."""
    return {
        "underlying": chain.underlying,
        "current_expiry": chain.expiry_date,
        "expiry": chain.expiry_date,
        "atm_strike": chain.get_atm_strike(),
        "spot_price": chain.spot_price,
        "lot_size": getattr(chain, "lot_size", None),
        "timestamp": getattr(chain, "timestamp", None),
        "calls": chain.calls,
        "puts": chain.puts,
        "option_chain": chain,
    }


def _make_serializable(value: Any) -> Any:
    """Recursively convert unsupported JSON types (e.g. datetime) to serialisable values."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _make_serializable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_make_serializable(item) for item in value]
    return value


class DashboardConnector(_DashboardConnector):
    """Legacy wrapper that tolerates missing API keys in test environments."""

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        api_key = api_key or os.environ.get("DASHBOARD_API_KEY") or "test-dashboard-key"
        super().__init__(base_url=base_url, api_key=api_key)


class FNODataProvider(_ModernFNODataProvider):
    """Expose the modern provider under the legacy import path."""

    def get_option_chain_dict(self, symbol: str) -> Dict[str, Any]:
        chain = super().get_option_chain(symbol)
        return _option_chain_to_legacy_dict(chain)


class UnifiedPortfolio(_UnifiedPortfolio):
    """Backwards-compatible adapter exposing the legacy state export behaviour."""

    def _capture_portfolio_snapshot(self, price_map: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        snapshot = super()._capture_portfolio_snapshot(price_map)
        snapshot.setdefault("trading_day", datetime.now().strftime("%Y-%m-%d"))
        return snapshot

    def save_state_to_files(self, price_map: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        snapshot = self._capture_portfolio_snapshot(price_map)
        trading_day = snapshot["trading_day"]

        shared_state = {
            "trading_mode": snapshot["trading_mode"],
            "cash": snapshot["cash"],
            "positions": snapshot["positions"],
        }

        current_state = {
            "mode": snapshot["trading_mode"],
            "iteration": getattr(self, "iteration", 0),
            "trading_day": trading_day,
            "last_update": snapshot["timestamp"],
            "portfolio": {
                "initial_cash": self.initial_cash,
                "cash": snapshot["cash"],
                "positions": snapshot["positions"],
                "trades_count": getattr(self, "trades_count", 0),
                "winning_trades": getattr(self, "winning_trades", 0),
                "losing_trades": getattr(self, "losing_trades", 0),
                "total_pnl": getattr(self, "total_pnl", 0.0),
                "best_trade": getattr(self, "best_trade", 0.0),
                "worst_trade": getattr(self, "worst_trade", 0.0),
                "trades_history": getattr(self, "trades_history", []),
                "position_entry_times": getattr(self, "position_entry_times", {}),
            },
            "total_value": snapshot["total_value"],
        }

        shared_path = Path(self.shared_state_file_path)
        current_path = Path(self.current_state_file_path)
        shared_path.parent.mkdir(parents=True, exist_ok=True)
        current_path.parent.mkdir(parents=True, exist_ok=True)

        atomic_write_json(shared_path, _make_serializable(shared_state), create_backup=True)
        atomic_write_json(current_path, _make_serializable(current_state), create_backup=True)
        return snapshot

    def _save_state_impl(self):
        self.save_state_to_files()


class UnifiedTradingSystem(_UnifiedTradingSystem):
    """Extend the modern trading system with helpers old tooling still calls."""

    def export_state(self, file_path: str) -> None:
        state = self.state_manager.get_persisted_state()
        atomic_write_json(file_path, _make_serializable(state))


__all__ = [
    "config",
    "DataProvider",
    "FNODataProvider",
    "EnhancedSignalAggregator",
    "UnifiedTradingSystem",
    "UnifiedPortfolio",
    "DashboardConnector",
    "TradingLogger",
    "MarketHoursManager",
    "EnhancedStateManager",
    "safe_float_conversion",
    "validate_symbol",
]
