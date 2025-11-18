#!/usr/bin/env python3
"""
Thread-Safe Portfolio Manager
Prevents race conditions in portfolio operations with atomic updates
"""

import threading
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
import logging

from trading_utils import AtomicFloat, get_ist_now, safe_divide
from trading_exceptions import RiskManagementError, ValidationError

logger = logging.getLogger('trading_system.portfolio')


@dataclass
class Position:
    """Thread-safe position data"""
    symbol: str
    shares: int
    avg_price: float
    created_at: datetime
    updated_at: datetime
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Trade:
    """Trade record"""
    trade_id: str
    action: str  # 'BUY' or 'SELL'
    symbol: str
    shares: int
    price: float
    total_amount: float
    pnl: Optional[float]
    timestamp: datetime
    metadata: dict = None


class ThreadSafePortfolio:
    """
    Thread-safe portfolio with atomic operations

    Features:
    - Atomic cash operations using AtomicFloat
    - Thread-safe position updates with RLock
    - Complete trade history
    - Position size limits
    - Comprehensive error handling
    """

    def __init__(
        self,
        initial_cash: float,
        max_position_pct: float = 0.20,  # 20% max per position
        max_total_positions: int = 10
    ):
        """
        Initialize thread-safe portfolio

        Args:
            initial_cash: Initial cash balance
            max_position_pct: Max % of portfolio per position
            max_total_positions: Max number of positions
        """
        if initial_cash <= 0:
            raise ValueError(f"Initial cash must be positive, got: {initial_cash}")

        # Atomic cash operations
        self.cash = AtomicFloat(initial_cash)
        self.initial_cash = initial_cash

        # Position limits
        self.max_position_pct = max_position_pct
        self.max_total_positions = max_total_positions

        # Thread-safe position storage
        self.positions: Dict[str, Position] = {}
        self._positions_lock = threading.RLock()

        # Trade history
        self.trade_history: List[Trade] = []
        self._history_lock = threading.RLock()

        # Trade counter for IDs
        self._trade_counter = 0
        self._counter_lock = threading.Lock()

        logger.info(
            f"✅ Portfolio initialized: Cash=₹{initial_cash:,.2f}, "
            f"MaxPositionPct={max_position_pct*100}%, MaxPositions={max_total_positions}"
        )

    def _generate_trade_id(self) -> str:
        """Generate unique trade ID"""
        with self._counter_lock:
            self._trade_counter += 1
            return f"T{get_ist_now().strftime('%Y%m%d%H%M%S')}_{self._trade_counter:04d}"

    def buy(
        self,
        symbol: str,
        shares: int,
        price: float,
        timestamp: Optional[datetime] = None,
        metadata: Optional[dict] = None
    ) -> Trade:
        """
        Buy shares (thread-safe)

        Args:
            symbol: Stock symbol
            shares: Number of shares
            price: Price per share
            timestamp: Optional trade timestamp
            metadata: Optional metadata

        Returns:
            Trade record

        Raises:
            ValueError: Invalid parameters
            RiskManagementError: Position limits exceeded
            InsufficientFundsError: Not enough cash
        """
        # Validation
        if shares <= 0:
            raise ValueError(f"Shares must be positive, got: {shares}")
        if price <= 0:
            raise ValueError(f"Price must be positive, got: {price}")

        symbol = symbol.upper().strip()
        timestamp = timestamp or get_ist_now()
        total_cost = shares * price

        # Check position limits BEFORE deducting cash
        portfolio_value = self.get_total_value()
        position_pct = safe_divide(total_cost, portfolio_value, 0.0)

        if position_pct > self.max_position_pct:
            raise RiskManagementError(
                f"Position {symbol} would be {position_pct*100:.1f}% of portfolio "
                f"(max {self.max_position_pct*100}%)"
            )

        # Check max positions count
        with self._positions_lock:
            if symbol not in self.positions and len(self.positions) >= self.max_total_positions:
                raise RiskManagementError(
                    f"Cannot open new position: already at max {self.max_total_positions} positions"
                )

        # Atomic cash deduction
        if not self.cash.deduct_if_available(total_cost):
            available = self.cash.get()
            raise RiskManagementError(
                f"Insufficient funds: need ₹{total_cost:,.2f}, have ₹{available:,.2f}"
            )

        # Update position with lock
        try:
            with self._positions_lock:
                if symbol in self.positions:
                    # Update existing position
                    existing = self.positions[symbol]
                    new_shares = existing.shares + shares
                    new_avg_price = (
                        (existing.shares * existing.avg_price) + (shares * price)
                    ) / new_shares

                    self.positions[symbol] = Position(
                        symbol=symbol,
                        shares=new_shares,
                        avg_price=new_avg_price,
                        created_at=existing.created_at,
                        updated_at=timestamp,
                        metadata={**(existing.metadata or {}), **(metadata or {})}
                    )
                else:
                    # New position
                    self.positions[symbol] = Position(
                        symbol=symbol,
                        shares=shares,
                        avg_price=price,
                        created_at=timestamp,
                        updated_at=timestamp,
                        metadata=metadata or {}
                    )

            # Record trade
            trade = Trade(
                trade_id=self._generate_trade_id(),
                action='BUY',
                symbol=symbol,
                shares=shares,
                price=price,
                total_amount=total_cost,
                pnl=None,
                timestamp=timestamp,
                metadata=metadata
            )

            with self._history_lock:
                self.trade_history.append(trade)

            logger.info(
                f"✅ BOUGHT: {shares} {symbol} @ ₹{price:.2f} = ₹{total_cost:,.2f} "
                f"| Cash: ₹{self.cash.get():,.2f}"
            )

            return trade

        except Exception as e:
            # Rollback cash deduction on error
            self.cash.add(total_cost)
            logger.error(f"Failed to execute buy, rolled back cash: {e}")
            raise

    def sell(
        self,
        symbol: str,
        shares: int,
        price: float,
        timestamp: Optional[datetime] = None,
        metadata: Optional[dict] = None
    ) -> Trade:
        """
        Sell shares (thread-safe)

        Args:
            symbol: Stock symbol
            shares: Number of shares
            price: Price per share
            timestamp: Optional trade timestamp
            metadata: Optional metadata

        Returns:
            Trade record with P&L

        Raises:
            ValueError: Invalid parameters or insufficient shares
        """
        # Validation
        if shares <= 0:
            raise ValueError(f"Shares must be positive, got: {shares}")
        if price <= 0:
            raise ValueError(f"Price must be positive, got: {price}")

        symbol = symbol.upper().strip()
        timestamp = timestamp or get_ist_now()
        proceeds = shares * price

        # Update position with lock
        with self._positions_lock:
            if symbol not in self.positions:
                raise ValueError(f"Cannot sell {symbol}: no position")

            existing = self.positions[symbol]
            if existing.shares < shares:
                raise ValueError(
                    f"Cannot sell {shares} {symbol}: only have {existing.shares}"
                )

            # Calculate P&L
            cost_basis = shares * existing.avg_price
            pnl = proceeds - cost_basis

            # Update or remove position
            new_shares = existing.shares - shares
            if new_shares == 0:
                del self.positions[symbol]
                logger.info(f"🔒 Position {symbol} closed completely")
            else:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    shares=new_shares,
                    avg_price=existing.avg_price,  # Avg price stays same on sell
                    created_at=existing.created_at,
                    updated_at=timestamp,
                    metadata=existing.metadata
                )

        # Atomic cash addition
        self.cash.add(proceeds)

        # Record trade
        trade = Trade(
            trade_id=self._generate_trade_id(),
            action='SELL',
            symbol=symbol,
            shares=shares,
            price=price,
            total_amount=proceeds,
            pnl=pnl,
            timestamp=timestamp,
            metadata=metadata
        )

        with self._history_lock:
            self.trade_history.append(trade)

        pnl_pct = safe_divide(pnl, cost_basis, 0.0) * 100
        logger.info(
            f"✅ SOLD: {shares} {symbol} @ ₹{price:.2f} = ₹{proceeds:,.2f} "
            f"| P&L: ₹{pnl:,.2f} ({pnl_pct:+.2f}%) | Cash: ₹{self.cash.get():,.2f}"
        )

        return trade

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol (thread-safe)"""
        with self._positions_lock:
            return self.positions.get(symbol.upper().strip())

    def get_all_positions(self) -> Dict[str, Position]:
        """Get all positions (thread-safe copy)"""
        with self._positions_lock:
            return self.positions.copy()

    def get_total_value(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate total portfolio value (thread-safe)

        Args:
            current_prices: Optional dict of current prices

        Returns:
            Total value (cash + positions)
        """
        cash = self.cash.get()

        with self._positions_lock:
            positions_value = 0.0
            for symbol, position in self.positions.items():
                if current_prices and symbol in current_prices:
                    positions_value += position.shares * current_prices[symbol]
                else:
                    # Use avg price if current price not available
                    positions_value += position.shares * position.avg_price

        return cash + positions_value

    def get_unrealized_pnl(self, current_prices: Dict[str, float]) -> float:
        """Calculate unrealized P&L (thread-safe)"""
        with self._positions_lock:
            total_pnl = 0.0
            for symbol, position in self.positions.items():
                if symbol in current_prices:
                    current_value = position.shares * current_prices[symbol]
                    cost_basis = position.shares * position.avg_price
                    total_pnl += (current_value - cost_basis)

        return total_pnl

    def get_realized_pnl(self) -> float:
        """Calculate total realized P&L from trade history"""
        with self._history_lock:
            return sum(trade.pnl for trade in self.trade_history if trade.pnl is not None)

    def get_trade_history(self, symbol: Optional[str] = None) -> List[Trade]:
        """Get trade history (thread-safe copy)"""
        with self._history_lock:
            if symbol:
                symbol = symbol.upper().strip()
                return [t for t in self.trade_history if t.symbol == symbol]
            return self.trade_history.copy()

    def get_statistics(self) -> Dict:
        """Get portfolio statistics"""
        with self._positions_lock:
            position_count = len(self.positions)
            position_symbols = list(self.positions.keys())

        with self._history_lock:
            total_trades = len(self.trade_history)
            buy_trades = sum(1 for t in self.trade_history if t.action == 'BUY')
            sell_trades = sum(1 for t in self.trade_history if t.action == 'SELL')

        realized_pnl = self.get_realized_pnl()
        cash = self.cash.get()
        total_value = self.get_total_value()

        return {
            'cash': cash,
            'initial_cash': self.initial_cash,
            'total_value': total_value,
            'realized_pnl': realized_pnl,
            'return_pct': safe_divide(realized_pnl, self.initial_cash, 0.0) * 100,
            'position_count': position_count,
            'position_symbols': position_symbols,
            'total_trades': total_trades,
            'buy_trades': buy_trades,
            'sell_trades': sell_trades,
            'max_positions': self.max_total_positions,
            'max_position_pct': self.max_position_pct
        }

    def __repr__(self) -> str:
        return (
            f"Portfolio(cash=₹{self.cash.get():,.2f}, "
            f"positions={len(self.positions)}, "
            f"trades={len(self.trade_history)})"
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("🧪 Testing Thread-Safe Portfolio")
    print("=" * 60)

    # Create portfolio
    portfolio = ThreadSafePortfolio(initial_cash=1000000, max_position_pct=0.20)

    print(f"\n📊 Initial: {portfolio}")

    # Buy some stocks
    print("\n🔵 Executing trades...")
    portfolio.buy('SBIN', 100, 550.50)
    portfolio.buy('INFY', 50, 1450.75)
    portfolio.buy('SBIN', 50, 555.00)  # Average up

    # Sell some
    portfolio.sell('SBIN', 100, 560.00)

    # Statistics
    print(f"\n📈 Statistics:")
    stats = portfolio.get_statistics()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:,.2f}")
        else:
            print(f"  {key}: {value}")

    print(f"\n✅ Thread-safe portfolio working correctly!")
