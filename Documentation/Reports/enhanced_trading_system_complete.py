#!/usr/bin/env python3
"""
Legacy compatibility shim for the historic `enhanced_trading_system_complete`
module.  Modern code lives in the refactored packages, but a number of long-tail
maintenance tests still import the monolith.  This module re-exports the current
implementations while smoothing over minor behavioural differences.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import logging
import os
from datetime import datetime

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
    """Convert modern OptionChain objects back to the dict format legacy tests expect."""
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
    """Recursively convert unsupported JSON types (e.g. datetime) to strings."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _make_serializable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_make_serializable(item) for item in value]
    return value


class DashboardConnector(_DashboardConnector):
    """
    Legacy wrapper that tolerates missing API keys. Production code insists on an
    explicit key, but the archival test-suite instantiates the connector without
    credentials.
    """

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        api_key = api_key or os.environ.get("DASHBOARD_API_KEY") or "test-dashboard-key"
        super().__init__(base_url=base_url, api_key=api_key)


class FNODataProvider(_ModernFNODataProvider):
    """Expose the modern provider under the legacy name."""

    def get_option_chain_dict(self, symbol: str) -> Dict[str, Any]:
        chain = super().get_option_chain(symbol)
        return _option_chain_to_legacy_dict(chain)


class UnifiedTradingSystem(_UnifiedTradingSystem):
    """Extend the modern system with helpers that legacy tests still call."""

    def export_state(self, file_path: str) -> None:
        state = self.state_manager.get_persisted_state()
        atomic_write_json(file_path, _make_serializable(state))


class UnifiedPortfolio(_UnifiedPortfolio):
    """Legacy alias for the refactored portfolio implementation."""

    def to_dict(self) -> Dict[str, Any]:
        portfolio = super().to_dict()
        portfolio["exported_at"] = datetime.now(timezone.utc).isoformat()
        return portfolio


# Backwards compatible exports -------------------------------------------------

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
