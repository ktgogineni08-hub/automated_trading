#!/usr/bin/env python3
"""
Legacy Compatibility Layer
===========================

This module provides a backwards-compatible surface for code that still
imports symbols from the former monolithic
``enhanced_trading_system_complete`` module.  The refactored codebase
now exposes functionality via dedicated packages (``core.``, ``fno.``,
``utilities.``, etc.), so this shim simply re-exports the modern
implementations while smoothing over historical API differences that
the maintenance test-suite still exercises.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import logging
import os
from datetime import datetime
from pathlib import Path

import config
from data.provider import DataProvider
from fno.data_provider import FNODataProvider as _ModernFNODataProvider
from fno.indices import IndexConfig
from fno.options import OptionChain
from fno.strategy_selector import IntelligentFNOStrategySelector
from fno.terminal import FNOTerminal
from core.signal_aggregator import EnhancedSignalAggregator
from core.trading_system import UnifiedTradingSystem as _UnifiedTradingSystem
from core.portfolio import UnifiedPortfolio as _UnifiedPortfolio
from utilities.dashboard import DashboardConnector as _DashboardConnector
from utilities.logger import TradingLogger
from utilities.market_hours import MarketHoursManager
from enhanced_state_manager import EnhancedStateManager
from trading_utils import safe_float_conversion, validate_symbol
from safe_file_ops import atomic_write_json

logger = logging.getLogger("trading_system.compat")


def _option_chain_to_legacy_dict(chain: OptionChain) -> Dict[str, Any]:
    """Convert the modern OptionChain object into the legacy dict format."""
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
        "option_chain": chain,  # expose raw object for advanced consumers
    }


def _make_serializable(value: Any) -> Any:
    """Recursively convert unsupported JSON types (e.g., datetime) to strings."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _make_serializable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_make_serializable(item) for item in value]
    return value


class DashboardConnector(_DashboardConnector):
    """
    Legacy wrapper that tolerates missing API keys by generating a temporary
    token.  The production connector enforces explicit secrets, but historical
    tests instantiate the DashboardConnector without providing one.
    """

    def __init__(self, base_url: str = None, api_key: Optional[str] = None):
        api_key = api_key or os.environ.get("DASHBOARD_API_KEY") or "test-dashboard-key"
        super().__init__(base_url=base_url, api_key=api_key)


class UnifiedPortfolio(_UnifiedPortfolio):
    """Backward-compatible alias for the modern UnifiedPortfolio."""

    def _capture_portfolio_snapshot(self, price_map: Optional[Dict[str, float]] = None) -> Dict:
        snapshot = super()._capture_portfolio_snapshot(price_map)
        snapshot.setdefault("trading_day", datetime.now().strftime("%Y-%m-%d"))
        return snapshot

    def save_state_to_files(self, price_map: Optional[Dict[str, float]] = None) -> Dict:
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
    """
    Compatibility wrapper that recreates the zero-argument constructor
    used by legacy scripts.  When explicit dependencies are omitted we
    lazily instantiate sensible defaults.
    """

    def __init__(
        self,
        data_provider: Optional[DataProvider] = None,
        kite: Any = None,
        initial_cash: Optional[float] = None,
        max_positions: Optional[int] = None,
        dashboard: Optional[DashboardConnector] = None,
        trading_mode: str = "paper",
        config_override: Optional[Dict[str, Any]] = None,
    ):
        data_provider = data_provider or DataProvider(kite=kite)
        if initial_cash is None:
            initial_cash = getattr(config, "initial_capital", 1_000_000)
        super().__init__(
            data_provider=data_provider,
            kite=kite,
            initial_cash=initial_cash,
            max_positions=max_positions,
            dashboard=dashboard,
            trading_mode=trading_mode,
            config_override=config_override or {},
        )


class FNODataProvider(_ModernFNODataProvider):
    """
    Compatibility wrapper that exposes the old dict-based ``get_option_chain``
    helper while keeping the improved ``fetch_option_chain`` implementation.
    """

    def get_option_chain(
        self,
        index_symbol: str,
        expiry_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        chain = super().fetch_option_chain(index_symbol, expiry_date)
        if not chain:
            return None
        return _option_chain_to_legacy_dict(chain)


def create_fno_trading_system(
    trading_mode: str = "paper",
    dashboard: Optional[DashboardConnector] = None,
    kite: Any = None,
    portfolio: Optional[UnifiedPortfolio] = None,
    **_: Any,
) -> FNOTerminal:
    """
    Legacy factory that returns an ``FNOTerminal`` instance configured for
    the requested trading mode.
    """
    portfolio = portfolio or UnifiedPortfolio(
        initial_cash=getattr(config, "initial_capital", 1_000_000),
        dashboard=dashboard,
        trading_mode=trading_mode,
    )
    terminal = FNOTerminal(kite=kite, portfolio=portfolio)
    if dashboard and hasattr(terminal.portfolio, "dashboard"):
        terminal.portfolio.dashboard = dashboard
    return terminal


def run_trading_system_directly(
    trading_mode: str = "paper",
    config_override: Optional[Dict[str, Any]] = None,
) -> UnifiedTradingSystem:
    """
    Lightweight replacement for the previous helper.  It simply builds
    a ``UnifiedTradingSystem`` instance with default dependencies and
    returns it to the caller.
    """
    return UnifiedTradingSystem(
        trading_mode=trading_mode,
        config_override=config_override or {},
    )


__all__ = [
    "UnifiedPortfolio",
    "DashboardConnector",
    "FNODataProvider",
    "UnifiedTradingSystem",
    "FNOTerminal",
    "IntelligentFNOStrategySelector",
    "IndexConfig",
    "EnhancedSignalAggregator",
    "MarketHoursManager",
    "EnhancedStateManager",
    "TradingLogger",
    "DataProvider",
    "safe_float_conversion",
    "validate_symbol",
    "create_fno_trading_system",
    "run_trading_system_directly",
]
