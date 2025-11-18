"""
Core Trading System Modules

Core components for the trading system including portfolio management,
trading execution, signal aggregation, and market regime detection.
"""

from core.signal_aggregator import EnhancedSignalAggregator
from core.regime_detector import MarketRegimeDetector
from core.transaction import TradingTransaction
from core.portfolio import UnifiedPortfolio
from core.trading_system import UnifiedTradingSystem

__all__ = [
    'EnhancedSignalAggregator',
    'MarketRegimeDetector',
    'TradingTransaction',
    'UnifiedPortfolio',
    'UnifiedTradingSystem',
]
