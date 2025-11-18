#!/usr/bin/env python3
"""
Trading Transaction Context Manager
Provides atomic operations with automatic rollback on failure
"""

import logging

logger = logging.getLogger('trading_system.transaction')


class TradingTransaction:
    """
    Context manager for atomic trading operations with automatic rollback on failure

    Provides transactional semantics for portfolio modifications:
    - Takes snapshot before operation
    - Automatically rolls back on exception
    - Thread-safe using portfolio's position lock

    Usage:
        with TradingTransaction(portfolio) as txn:
            # Make changes to portfolio
            portfolio.cash -= 1000
            portfolio.positions[symbol] = {...}
            # If exception occurs, changes are rolled back automatically

    Benefits:
    - Prevents partial updates on errors
    - Maintains portfolio consistency
    - Simplifies error handling in trading operations
    """

    def __init__(self, portfolio):
        """
        Initialize transaction

        Args:
            portfolio: Portfolio instance to protect
        """
        self.portfolio = portfolio
        self.snapshot = None

    def __enter__(self):
        """
        Create snapshot of current state

        Returns:
            Self for context manager protocol
        """
        with self.portfolio._position_lock:
            self.snapshot = {
                'cash': self.portfolio.cash,
                'positions': {k: v.copy() for k, v in self.portfolio.positions.items()},
                'position_entry_times': self.portfolio.position_entry_times.copy(),
                'trades_count': self.portfolio.trades_count,
                'winning_trades': self.portfolio.winning_trades,
                'losing_trades': self.portfolio.losing_trades,
                'total_pnl': self.portfolio.total_pnl,
                'best_trade': self.portfolio.best_trade,
                'worst_trade': self.portfolio.worst_trade,
                'daily_profit': self.portfolio.daily_profit
            }
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Rollback on exception

        Args:
            exc_type: Exception type (None if no exception)
            exc_val: Exception value
            exc_tb: Exception traceback

        Returns:
            False to re-raise exception, True to suppress
        """
        if exc_type is not None:
            # Exception occurred - rollback to snapshot
            logger.warning(f"⚠️ Transaction failed: {exc_val} - Rolling back...")
            with self.portfolio._position_lock:
                self.portfolio.cash = self.snapshot['cash']
                self.portfolio.positions = self.snapshot['positions']
                self.portfolio.position_entry_times = self.snapshot['position_entry_times']
                self.portfolio.trades_count = self.snapshot['trades_count']
                self.portfolio.winning_trades = self.snapshot['winning_trades']
                self.portfolio.losing_trades = self.snapshot['losing_trades']
                self.portfolio.total_pnl = self.snapshot['total_pnl']
                self.portfolio.best_trade = self.snapshot['best_trade']
                self.portfolio.worst_trade = self.snapshot['worst_trade']
                self.portfolio.daily_profit = self.snapshot['daily_profit']
            logger.info("✅ Portfolio state rolled back successfully")
            return False  # Re-raise exception
        return True
