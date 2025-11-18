#!/usr/bin/env python3
"""
Comprehensive tests for transaction.py module
Tests TradingTransaction context manager with rollback functionality
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import sys
from threading import Lock

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.transaction import TradingTransaction


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_portfolio():
    """Create mock portfolio with all required attributes"""
    portfolio = Mock()
    portfolio._position_lock = Lock()
    portfolio.cash = 100000.0
    portfolio.positions = {
        'RELIANCE': {'shares': 10, 'avg_price': 2450.0},
        'TCS': {'shares': 5, 'avg_price': 3250.0}
    }
    portfolio.position_entry_times = {
        'RELIANCE': '2025-01-01T10:00:00',
        'TCS': '2025-01-01T11:00:00'
    }
    portfolio.trades_count = 15
    portfolio.winning_trades = 10
    portfolio.losing_trades = 5
    portfolio.total_pnl = 25000.0
    portfolio.best_trade = 5000.0
    portfolio.worst_trade = -1500.0
    portfolio.daily_profit = 1200.0
    return portfolio


# ============================================================================
# Basic Context Manager Tests
# ============================================================================

class TestBasicContextManager:
    """Test basic context manager functionality"""

    def test_enter_creates_snapshot(self, mock_portfolio):
        """Test that __enter__ creates a snapshot of portfolio state"""
        txn = TradingTransaction(mock_portfolio)

        with txn:
            # Snapshot should be created
            assert txn.snapshot is not None
            assert txn.snapshot['cash'] == 100000.0
            assert txn.snapshot['trades_count'] == 15

    def test_enter_returns_self(self, mock_portfolio):
        """Test that __enter__ returns self"""
        txn = TradingTransaction(mock_portfolio)

        with txn as result:
            assert result is txn

    def test_exit_without_exception_succeeds(self, mock_portfolio):
        """Test that __exit__ without exception allows changes to persist"""
        original_cash = mock_portfolio.cash

        with TradingTransaction(mock_portfolio):
            mock_portfolio.cash -= 1000

        # Changes should persist
        assert mock_portfolio.cash == original_cash - 1000

    def test_transaction_used_as_context_manager(self, mock_portfolio):
        """Test transaction can be used as context manager"""
        with TradingTransaction(mock_portfolio):
            # Make some changes
            mock_portfolio.cash = 50000.0
            mock_portfolio.trades_count += 1

        # Changes should be kept (no exception)
        assert mock_portfolio.cash == 50000.0
        assert mock_portfolio.trades_count == 16


# ============================================================================
# Rollback Tests
# ============================================================================

class TestRollback:
    """Test rollback functionality on exceptions"""

    def test_rollback_on_exception(self, mock_portfolio):
        """Test that portfolio state is rolled back on exception"""
        original_cash = mock_portfolio.cash
        original_trades = mock_portfolio.trades_count

        with pytest.raises(ValueError):
            with TradingTransaction(mock_portfolio):
                # Make changes
                mock_portfolio.cash = 50000.0
                mock_portfolio.trades_count += 5

                # Raise exception to trigger rollback
                raise ValueError("Transaction failed")

        # State should be rolled back
        assert mock_portfolio.cash == original_cash
        assert mock_portfolio.trades_count == original_trades

    def test_rollback_restores_positions(self, mock_portfolio):
        """Test that positions are restored on rollback"""
        # Store original values
        original_reliance_shares = mock_portfolio.positions['RELIANCE']['shares']
        original_tcs_shares = mock_portfolio.positions['TCS']['shares']

        with pytest.raises(RuntimeError):
            with TradingTransaction(mock_portfolio):
                # Add new position
                mock_portfolio.positions['NEW_STOCK'] = {'shares': 50, 'avg_price': 1000.0}

                # Replace entire position dict (not modify nested)
                mock_portfolio.positions['RELIANCE'] = {'shares': 100, 'avg_price': 2500.0}

                raise RuntimeError("Test error")

        # Positions should be restored
        assert mock_portfolio.positions['RELIANCE']['shares'] == original_reliance_shares
        assert mock_portfolio.positions['TCS']['shares'] == original_tcs_shares
        assert 'NEW_STOCK' not in mock_portfolio.positions

    def test_rollback_restores_all_tracked_fields(self, mock_portfolio):
        """Test that all tracked fields are restored on rollback"""
        original_state = {
            'cash': mock_portfolio.cash,
            'trades_count': mock_portfolio.trades_count,
            'winning_trades': mock_portfolio.winning_trades,
            'losing_trades': mock_portfolio.losing_trades,
            'total_pnl': mock_portfolio.total_pnl,
            'best_trade': mock_portfolio.best_trade,
            'worst_trade': mock_portfolio.worst_trade,
            'daily_profit': mock_portfolio.daily_profit
        }

        with pytest.raises(Exception):
            with TradingTransaction(mock_portfolio):
                # Modify all fields
                mock_portfolio.cash = 0
                mock_portfolio.trades_count = 999
                mock_portfolio.winning_trades = 500
                mock_portfolio.losing_trades = 499
                mock_portfolio.total_pnl = 1000000
                mock_portfolio.best_trade = 50000
                mock_portfolio.worst_trade = -20000
                mock_portfolio.daily_profit = 5000

                raise Exception("Rollback test")

        # All fields should be restored
        assert mock_portfolio.cash == original_state['cash']
        assert mock_portfolio.trades_count == original_state['trades_count']
        assert mock_portfolio.winning_trades == original_state['winning_trades']
        assert mock_portfolio.losing_trades == original_state['losing_trades']
        assert mock_portfolio.total_pnl == original_state['total_pnl']
        assert mock_portfolio.best_trade == original_state['best_trade']
        assert mock_portfolio.worst_trade == original_state['worst_trade']
        assert mock_portfolio.daily_profit == original_state['daily_profit']

    def test_rollback_logs_warning(self, mock_portfolio):
        """Test that rollback logs warning message"""
        with patch('core.transaction.logger') as mock_logger:
            with pytest.raises(ValueError):
                with TradingTransaction(mock_portfolio):
                    raise ValueError("Test error")

            # Should have logged warning
            mock_logger.warning.assert_called_once()
            assert 'Rolling back' in str(mock_logger.warning.call_args[0][0])

    def test_rollback_logs_success(self, mock_portfolio):
        """Test that successful rollback logs info message"""
        with patch('core.transaction.logger') as mock_logger:
            with pytest.raises(ValueError):
                with TradingTransaction(mock_portfolio):
                    raise ValueError("Test error")

            # Should have logged rollback success
            mock_logger.info.assert_called_once()
            assert 'rolled back successfully' in str(mock_logger.info.call_args[0][0])


# ============================================================================
# Exception Propagation Tests
# ============================================================================

class TestExceptionPropagation:
    """Test that exceptions are properly propagated"""

    def test_exception_is_reraised(self, mock_portfolio):
        """Test that exceptions are re-raised after rollback"""
        with pytest.raises(ValueError) as exc_info:
            with TradingTransaction(mock_portfolio):
                raise ValueError("Original error")

        assert str(exc_info.value) == "Original error"

    def test_different_exception_types(self, mock_portfolio):
        """Test rollback works with different exception types"""
        # RuntimeError
        with pytest.raises(RuntimeError):
            with TradingTransaction(mock_portfolio):
                raise RuntimeError("Runtime error")

        # KeyError
        with pytest.raises(KeyError):
            with TradingTransaction(mock_portfolio):
                raise KeyError("key_error")

        # Custom exception
        class CustomError(Exception):
            pass

        with pytest.raises(CustomError):
            with TradingTransaction(mock_portfolio):
                raise CustomError("Custom error")


# ============================================================================
# Snapshot Isolation Tests
# ============================================================================

class TestSnapshotIsolation:
    """Test snapshot isolation and deep copying"""

    def test_positions_snapshot_is_deep_copy(self, mock_portfolio):
        """Test that positions snapshot is deep copied"""
        with pytest.raises(ValueError):
            with TradingTransaction(mock_portfolio) as txn:
                # Modify nested dictionary
                mock_portfolio.positions['RELIANCE']['shares'] = 999

                # Snapshot should not be affected
                assert txn.snapshot['positions']['RELIANCE']['shares'] == 10

                raise ValueError("Test rollback")

        # Original should be restored
        assert mock_portfolio.positions['RELIANCE']['shares'] == 10

    def test_position_entry_times_snapshot_is_copy(self, mock_portfolio):
        """Test that position_entry_times is properly copied"""
        original_times = mock_portfolio.position_entry_times.copy()

        with pytest.raises(ValueError):
            with TradingTransaction(mock_portfolio):
                mock_portfolio.position_entry_times['NEW_SYMBOL'] = '2025-01-02T10:00:00'
                raise ValueError("Test")

        # Should be restored
        assert mock_portfolio.position_entry_times == original_times
        assert 'NEW_SYMBOL' not in mock_portfolio.position_entry_times


# ============================================================================
# Concurrent Access Tests
# ============================================================================

class TestConcurrentAccess:
    """Test thread-safe operations"""

    def test_uses_portfolio_lock_on_enter(self, mock_portfolio):
        """Test that transaction uses portfolio lock on enter"""
        mock_lock = MagicMock()
        mock_portfolio._position_lock = mock_lock

        with TradingTransaction(mock_portfolio):
            pass

        # Lock should have been acquired
        assert mock_lock.__enter__.called

    def test_uses_portfolio_lock_on_rollback(self, mock_portfolio):
        """Test that transaction uses portfolio lock on rollback"""
        mock_lock = MagicMock()
        mock_portfolio._position_lock = mock_lock

        with pytest.raises(ValueError):
            with TradingTransaction(mock_portfolio):
                raise ValueError("Test")

        # Lock should have been acquired twice (enter + rollback)
        assert mock_lock.__enter__.call_count == 2


# ============================================================================
# Complex Scenario Tests
# ============================================================================

class TestComplexScenarios:
    """Test complex real-world scenarios"""

    def test_multiple_position_modifications(self, mock_portfolio):
        """Test multiple position modifications in one transaction"""
        original_cash = mock_portfolio.cash
        original_positions = mock_portfolio.positions.copy()

        with pytest.raises(ValueError):
            with TradingTransaction(mock_portfolio):
                # Buy new stock
                mock_portfolio.cash -= 50000
                mock_portfolio.positions['INFY'] = {'shares': 20, 'avg_price': 2500.0}

                # Sell existing stock
                del mock_portfolio.positions['TCS']
                mock_portfolio.cash += 16250  # 5 shares * 3250

                # Update trades
                mock_portfolio.trades_count += 2

                raise ValueError("Transaction aborted")

        # Everything should be rolled back
        assert mock_portfolio.cash == original_cash
        assert mock_portfolio.positions == original_positions
        assert 'INFY' not in mock_portfolio.positions
        assert 'TCS' in mock_portfolio.positions
        assert mock_portfolio.trades_count == 15

    def test_nested_transactions_not_supported(self, mock_portfolio):
        """Test that nested transactions work independently"""
        # Note: This implementation doesn't support nested transactions
        # Each transaction creates its own snapshot
        original_cash = mock_portfolio.cash

        with TradingTransaction(mock_portfolio):
            mock_portfolio.cash = 90000

            # Inner transaction (separate snapshot)
            with pytest.raises(ValueError):
                with TradingTransaction(mock_portfolio):
                    mock_portfolio.cash = 80000
                    raise ValueError("Inner fails")

            # Outer transaction continues with current state
            # (inner changes were rolled back)
            assert mock_portfolio.cash == 90000

        # Outer transaction succeeded
        assert mock_portfolio.cash == 90000

    def test_partial_updates_prevented(self, mock_portfolio):
        """Test that partial updates are prevented on failure"""
        with pytest.raises(ZeroDivisionError):
            with TradingTransaction(mock_portfolio):
                # Step 1: Update cash
                mock_portfolio.cash -= 10000

                # Step 2: Update positions
                mock_portfolio.positions['NEW'] = {'shares': 10, 'avg_price': 1000}

                # Step 3: Update stats
                mock_portfolio.trades_count += 1
                mock_portfolio.winning_trades += 1

                # Step 4: Fail midway
                result = 1 / 0  # ZeroDivisionError

        # None of the changes should persist
        assert mock_portfolio.cash == 100000.0
        assert 'NEW' not in mock_portfolio.positions
        assert mock_portfolio.trades_count == 15
        assert mock_portfolio.winning_trades == 10


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_positions(self, mock_portfolio):
        """Test transaction with empty positions"""
        mock_portfolio.positions = {}
        mock_portfolio.position_entry_times = {}

        with pytest.raises(ValueError):
            with TradingTransaction(mock_portfolio):
                mock_portfolio.positions['NEW'] = {'shares': 10, 'avg_price': 1000}
                raise ValueError("Test")

        assert mock_portfolio.positions == {}

    def test_zero_cash(self, mock_portfolio):
        """Test transaction with zero cash"""
        mock_portfolio.cash = 0

        with pytest.raises(ValueError):
            with TradingTransaction(mock_portfolio):
                mock_portfolio.cash = 1000
                raise ValueError("Test")

        assert mock_portfolio.cash == 0

    def test_negative_pnl(self, mock_portfolio):
        """Test transaction with negative PnL values"""
        mock_portfolio.total_pnl = -5000.0
        mock_portfolio.daily_profit = -1000.0

        with pytest.raises(ValueError):
            with TradingTransaction(mock_portfolio):
                mock_portfolio.total_pnl = -10000
                raise ValueError("Test")

        assert mock_portfolio.total_pnl == -5000.0


if __name__ == "__main__":
    # Run tests with: pytest test_transaction.py -v
    pytest.main([__file__, "-v", "--tb=short"])
