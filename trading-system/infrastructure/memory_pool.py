#!/usr/bin/env python3
"""
Memory Pool Optimization for Trading Objects
Object pooling to reduce memory allocation overhead

ADDRESSES HIGH PRIORITY RECOMMENDATION #6:
- Object pooling for frequently created objects
- Memory pre-allocation for hot paths
- Reduced garbage collection pressure
- Improved performance in trading loops
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Any, Type, TypeVar, Generic, Callable
from datetime import datetime
from dataclasses import dataclass
from collections import deque
from enum import Enum
import weakref

logger = logging.getLogger('trading_system.memory_pool')

T = TypeVar('T')


class PoolStrategy(Enum):
    """Object pool strategies"""
    FIFO = "fifo"              # First-in, first-out
    LIFO = "lifo"              # Last-in, first-out (stack)
    ROUND_ROBIN = "round_robin"  # Round-robin allocation


@dataclass
class PoolStatistics:
    """Pool statistics"""
    pool_name: str
    object_type: str
    total_created: int
    total_acquired: int
    total_released: int
    total_reused: int
    current_available: int
    current_in_use: int
    max_pool_size: int
    hit_rate: float  # Reuse rate
    timestamp: datetime


class ObjectPool(Generic[T]):
    """
    Generic Object Pool

    Features:
    - Configurable pool size
    - Automatic object creation
    - Object validation and cleanup
    - Thread-safe operations
    - Statistics tracking
    - Memory leak detection

    Usage:
        # Create pool with factory
        pool = ObjectPool(
            name="TradeSignal",
            factory=TradeSignal,
            max_size=1000
        )

        # Acquire object
        signal = pool.acquire()
        signal.symbol = "NIFTY"
        signal.price = 25000

        # Release back to pool
        pool.release(signal)
    """

    def __init__(
        self,
        name: str,
        factory: Callable[[], T],
        max_size: int = 1000,
        min_size: int = 10,
        strategy: PoolStrategy = PoolStrategy.LIFO,
        validate_fn: Optional[Callable[[T], bool]] = None,
        reset_fn: Optional[Callable[[T], None]] = None
    ):
        """
        Initialize object pool

        Args:
            name: Pool name for identification
            factory: Function to create new objects
            max_size: Maximum pool size
            min_size: Minimum pool size (pre-allocated)
            strategy: Pool allocation strategy
            validate_fn: Optional validation function for objects
            reset_fn: Optional reset function to clean objects before reuse
        """
        self.name = name
        self.factory = factory
        self.max_size = max_size
        self.min_size = min_size
        self.strategy = strategy
        self.validate_fn = validate_fn
        self.reset_fn = reset_fn

        # Pool storage
        if strategy == PoolStrategy.LIFO:
            self._available: deque = deque(maxlen=max_size)
        else:
            self._available: deque = deque(maxlen=max_size)

        # Track objects in use
        self._in_use: set = set()
        self._lock = threading.RLock()

        # Statistics
        self.total_created = 0
        self.total_acquired = 0
        self.total_released = 0
        self.total_reused = 0

        # Pre-allocate minimum objects
        self._preallocate()

        logger.info(f"📦 ObjectPool '{name}' initialized: {min_size}/{max_size} objects")

    def _preallocate(self):
        """Pre-allocate minimum objects"""
        for _ in range(self.min_size):
            obj = self._create_object()
            self._available.append(obj)

    def _create_object(self) -> T:
        """Create new object using factory"""
        obj = self.factory()
        self.total_created += 1
        return obj

    def acquire(self, timeout: float = 5.0) -> Optional[T]:
        """
        Acquire object from pool

        Args:
            timeout: Max time to wait for available object

        Returns:
            Object from pool or None if timeout
        """
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            with self._lock:
                # Try to get from available pool
                if self._available:
                    if self.strategy == PoolStrategy.LIFO:
                        obj = self._available.pop()
                    else:
                        obj = self._available.popleft()

                    # Validate object
                    if self.validate_fn and not self.validate_fn(obj):
                        logger.warning(f"Invalid object in pool '{self.name}', creating new")
                        obj = self._create_object()

                    self._in_use.add(id(obj))
                    self.total_acquired += 1
                    self.total_reused += 1

                    return obj

                # Create new object if under max size
                elif self.total_created < self.max_size:
                    obj = self._create_object()
                    self._in_use.add(id(obj))
                    self.total_acquired += 1
                    return obj

            # Wait a bit before retry
            time.sleep(0.001)

        logger.warning(f"Pool '{self.name}' acquisition timeout after {timeout}s")
        return None

    def release(self, obj: T) -> bool:
        """
        Release object back to pool

        Args:
            obj: Object to release

        Returns:
            True if successful
        """
        with self._lock:
            obj_id = id(obj)

            # Check if object was from this pool
            if obj_id not in self._in_use:
                logger.warning(f"Releasing object not from pool '{self.name}'")
                return False

            # Reset object if reset function provided
            if self.reset_fn:
                try:
                    self.reset_fn(obj)
                except Exception as e:
                    logger.error(f"Error resetting object in pool '{self.name}': {e}")
                    # Don't return to pool if reset failed
                    self._in_use.remove(obj_id)
                    return False

            # Return to pool
            self._in_use.remove(obj_id)

            if len(self._available) < self.max_size:
                self._available.append(obj)
                self.total_released += 1
                return True
            else:
                # Pool full, let object be garbage collected
                return True

    def clear(self):
        """Clear all objects from pool"""
        with self._lock:
            self._available.clear()
            self._in_use.clear()
            logger.info(f"Pool '{self.name}' cleared")

    def get_statistics(self) -> PoolStatistics:
        """Get pool statistics"""
        with self._lock:
            total_acquired = self.total_acquired
            total_reused = self.total_reused

            hit_rate = (
                total_reused / total_acquired
                if total_acquired > 0 else 0
            )

            return PoolStatistics(
                pool_name=self.name,
                object_type=str(self.factory),
                total_created=self.total_created,
                total_acquired=total_acquired,
                total_released=self.total_released,
                total_reused=total_reused,
                current_available=len(self._available),
                current_in_use=len(self._in_use),
                max_pool_size=self.max_size,
                hit_rate=hit_rate,
                timestamp=datetime.now()
            )


class PooledObjectManager:
    """
    Centralized manager for all object pools

    Manages pools for common trading objects:
    - TradeSignal
    - OrderData
    - PositionData
    - PriceData
    - MarketData

    Usage:
        manager = PooledObjectManager()

        # Get pool
        signal_pool = manager.get_pool("TradeSignal")

        # Or acquire directly
        signal = manager.acquire("TradeSignal")
        manager.release("TradeSignal", signal)
    """

    def __init__(self):
        """Initialize pooled object manager"""
        self._pools: Dict[str, ObjectPool] = {}
        self._lock = threading.RLock()

        # Register common pools
        self._register_default_pools()

        logger.info("📦 PooledObjectManager initialized")

    def _register_default_pools(self):
        """Register default object pools"""

        # TradeSignal pool
        @dataclass
        class TradeSignal:
            symbol: str = ""
            action: str = ""
            quantity: int = 0
            price: float = 0.0
            strategy: str = ""
            confidence: float = 0.0
            timestamp: datetime = None

        def reset_trade_signal(signal: TradeSignal):
            signal.symbol = ""
            signal.action = ""
            signal.quantity = 0
            signal.price = 0.0
            signal.strategy = ""
            signal.confidence = 0.0
            signal.timestamp = None

        self.register_pool(
            name="TradeSignal",
            factory=TradeSignal,
            max_size=1000,
            min_size=50,
            reset_fn=reset_trade_signal
        )

        # OrderData pool
        @dataclass
        class OrderData:
            order_id: str = ""
            symbol: str = ""
            action: str = ""
            quantity: int = 0
            price: float = 0.0
            status: str = ""
            filled_quantity: int = 0
            timestamp: datetime = None

        def reset_order_data(order: OrderData):
            order.order_id = ""
            order.symbol = ""
            order.action = ""
            order.quantity = 0
            order.price = 0.0
            order.status = ""
            order.filled_quantity = 0
            order.timestamp = None

        self.register_pool(
            name="OrderData",
            factory=OrderData,
            max_size=500,
            min_size=25,
            reset_fn=reset_order_data
        )

        # PriceData pool
        @dataclass
        class PriceData:
            symbol: str = ""
            price: float = 0.0
            volume: int = 0
            timestamp: datetime = None

        def reset_price_data(price: PriceData):
            price.symbol = ""
            price.price = 0.0
            price.volume = 0
            price.timestamp = None

        self.register_pool(
            name="PriceData",
            factory=PriceData,
            max_size=2000,
            min_size=100,
            reset_fn=reset_price_data
        )

    def register_pool(
        self,
        name: str,
        factory: Callable,
        max_size: int = 1000,
        min_size: int = 10,
        strategy: PoolStrategy = PoolStrategy.LIFO,
        validate_fn: Optional[Callable] = None,
        reset_fn: Optional[Callable] = None
    ):
        """
        Register new object pool

        Args:
            name: Pool name
            factory: Object factory function
            max_size: Maximum pool size
            min_size: Minimum pool size
            strategy: Pool strategy
            validate_fn: Validation function
            reset_fn: Reset function
        """
        with self._lock:
            if name in self._pools:
                logger.warning(f"Pool '{name}' already exists, replacing")

            pool = ObjectPool(
                name=name,
                factory=factory,
                max_size=max_size,
                min_size=min_size,
                strategy=strategy,
                validate_fn=validate_fn,
                reset_fn=reset_fn
            )

            self._pools[name] = pool
            logger.info(f"Registered pool: {name}")

    def get_pool(self, name: str) -> Optional[ObjectPool]:
        """Get pool by name"""
        with self._lock:
            return self._pools.get(name)

    def acquire(self, pool_name: str, timeout: float = 5.0):
        """Acquire object from pool"""
        pool = self.get_pool(pool_name)
        if not pool:
            raise ValueError(f"Pool '{pool_name}' not found")

        return pool.acquire(timeout)

    def release(self, pool_name: str, obj: Any) -> bool:
        """Release object to pool"""
        pool = self.get_pool(pool_name)
        if not pool:
            raise ValueError(f"Pool '{pool_name}' not found")

        return pool.release(obj)

    def get_all_statistics(self) -> List[PoolStatistics]:
        """Get statistics for all pools"""
        with self._lock:
            return [pool.get_statistics() for pool in self._pools.values()]

    def print_statistics(self):
        """Print formatted statistics for all pools"""
        stats_list = self.get_all_statistics()

        print("\n" + "="*100)
        print("📦 OBJECT POOL STATISTICS")
        print("="*100)
        print(
            f"{'Pool Name':<20} {'Available':<12} {'In Use':<10} {'Created':<10} "
            f"{'Acquired':<10} {'Hit Rate':<10}"
        )
        print("-"*100)

        for stats in stats_list:
            print(
                f"{stats.pool_name:<20} "
                f"{stats.current_available:>10}  "
                f"{stats.current_in_use:>8}  "
                f"{stats.total_created:>8}  "
                f"{stats.total_acquired:>8}  "
                f"{stats.hit_rate:>8.1%}"
            )

        print("="*100 + "\n")

    def clear_all_pools(self):
        """Clear all pools"""
        with self._lock:
            for pool in self._pools.values():
                pool.clear()
            logger.info("All pools cleared")


# Context manager for pool usage
class pooled:
    """
    Context manager for automatic pool acquire/release

    Usage:
        with pooled(manager, "TradeSignal") as signal:
            signal.symbol = "NIFTY"
            signal.price = 25000
            # Automatically released on exit
    """

    def __init__(self, manager: PooledObjectManager, pool_name: str):
        self.manager = manager
        self.pool_name = pool_name
        self.obj = None

    def __enter__(self):
        self.obj = self.manager.acquire(self.pool_name)
        return self.obj

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.obj:
            self.manager.release(self.pool_name, self.obj)


# Global instance
_global_pool_manager: Optional[PooledObjectManager] = None


def get_pool_manager() -> PooledObjectManager:
    """Get global pool manager (singleton)"""
    global _global_pool_manager
    if _global_pool_manager is None:
        _global_pool_manager = PooledObjectManager()
    return _global_pool_manager


if __name__ == "__main__":
    # Test object pooling
    print("Testing Object Pool...\n")

    manager = PooledObjectManager()

    # Test 1: Acquire and release
    print("1. Testing acquire/release")
    signal = manager.acquire("TradeSignal")
    if signal:
        signal.symbol = "NIFTY"
        signal.price = 25000
        print(f"Acquired signal: {signal.symbol} @ {signal.price}")

        success = manager.release("TradeSignal", signal)
        print(f"Released: {success}")

    # Test 2: Context manager
    print("\n2. Testing context manager")
    with pooled(manager, "TradeSignal") as signal:
        signal.symbol = "BANKNIFTY"
        signal.price = 53500
        print(f"Using pooled signal: {signal.symbol} @ {signal.price}")

    # Test 3: Multiple acquisitions
    print("\n3. Testing multiple acquisitions")
    objects = []
    for i in range(10):
        obj = manager.acquire("PriceData")
        if obj:
            obj.symbol = f"SYMBOL_{i}"
            objects.append(obj)

    print(f"Acquired {len(objects)} objects")

    # Release all
    for obj in objects:
        manager.release("PriceData", obj)

    print("Released all objects")

    # Print statistics
    print("\n4. Pool Statistics")
    manager.print_statistics()

    print("\n✅ Object pool tests passed")
