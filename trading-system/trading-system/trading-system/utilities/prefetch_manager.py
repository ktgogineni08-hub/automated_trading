"""
Predictive Prefetch Manager - Intelligently prefetch market data

This module implements predictive prefetching to reduce latency by
anticipating data requests before they happen.

Features:
- Pattern-based prefetching
- Time-series prediction
- User behavior learning
- Smart scheduling
- Resource-aware prefetching

Author: Trading System Team
Date: November 2025
"""

import logging
import asyncio
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
import time
from dataclasses import dataclass
import threading

logger = logging.getLogger(__name__)


@dataclass
class PrefetchRequest:
    """Prefetch request with priority"""
    symbol: str
    data_type: str  # 'quote', 'historical', 'depth'
    priority: int  # 1-10, higher is more important
    requested_at: datetime
    completed: bool = False


class PredictivePrefetcher:
    """
    Intelligent prefetching system that learns and predicts data access patterns
    """

    def __init__(
        self,
        data_provider,
        redis_client,
        max_prefetch_per_minute: int = 100,
        learning_window_hours: int = 24
    ):
        """
        Initialize predictive prefetcher

        Args:
            data_provider: Market data provider
            redis_client: Redis cache client
            max_prefetch_per_minute: Rate limit for prefetch requests
            learning_window_hours: Hours of historical data to learn from
        """
        self.data_provider = data_provider
        self.redis = redis_client
        self.max_prefetch_per_minute = max_prefetch_per_minute
        self.learning_window_hours = learning_window_hours

        # Access pattern tracking
        self.access_patterns = defaultdict(deque)  # symbol -> times
        self.symbol_sequences = deque(maxlen=1000)  # Recently accessed sequences
        self.time_based_patterns = defaultdict(set)  # hour -> symbols

        # Prefetch queue
        self.prefetch_queue = asyncio.PriorityQueue()
        self.active_prefetches = set()

        # Statistics
        self.stats = {
            'total_prefetches': 0,
            'successful_prefetches': 0,
            'cache_hits_from_prefetch': 0,
            'wasted_prefetches': 0,  # Prefetched but never accessed
            'prefetch_accuracy': 0.0
        }

        # Control
        self._running = False
        self._prefetch_thread = None

    def start(self):
        """Start the prefetch manager"""
        if self._running:
            logger.warning("Prefetch manager already running")
            return

        self._running = True
        self._prefetch_thread = threading.Thread(
            target=self._prefetch_worker,
            daemon=True
        )
        self._prefetch_thread.start()
        logger.info("Prefetch manager started")

    def stop(self):
        """Stop the prefetch manager"""
        self._running = False
        if self._prefetch_thread:
            self._prefetch_thread.join(timeout=5)
        logger.info("Prefetch manager stopped")

    def record_access(self, symbol: str, data_type: str = 'quote'):
        """
        Record data access to learn patterns

        Args:
            symbol: Symbol accessed
            data_type: Type of data accessed
        """
        now = datetime.now()

        # Record timestamp for this symbol
        self.access_patterns[symbol].append(now)

        # Keep only recent accesses (last 24 hours)
        cutoff = now - timedelta(hours=self.learning_window_hours)
        while (self.access_patterns[symbol] and
               self.access_patterns[symbol][0] < cutoff):
            self.access_patterns[symbol].popleft()

        # Record sequence
        self.symbol_sequences.append((symbol, now))

        # Record time-based pattern
        hour = now.hour
        self.time_based_patterns[hour].add(symbol)

        # Trigger predictive prefetching
        self._predict_and_prefetch(symbol)

    def _predict_and_prefetch(self, current_symbol: str):
        """
        Predict what data will be needed next and prefetch it

        Args:
            current_symbol: Currently accessed symbol
        """
        predictions = self._generate_predictions(current_symbol)

        for symbol, priority in predictions:
            self._schedule_prefetch(symbol, 'quote', priority)

    def _generate_predictions(self, current_symbol: str) -> List[Tuple[str, int]]:
        """
        Generate predictions for next symbols to access

        Args:
            current_symbol: Currently accessed symbol

        Returns:
            List of (symbol, priority) tuples
        """
        predictions = {}  # symbol -> priority

        # Strategy 1: Sequence-based prediction
        sequence_predictions = self._predict_from_sequence(current_symbol)
        for symbol, score in sequence_predictions.items():
            predictions[symbol] = predictions.get(symbol, 0) + score * 5

        # Strategy 2: Time-based prediction
        time_predictions = self._predict_from_time_patterns()
        for symbol, score in time_predictions.items():
            predictions[symbol] = predictions.get(symbol, 0) + score * 3

        # Strategy 3: Correlation-based (symbols often accessed together)
        correlation_predictions = self._predict_from_correlations(current_symbol)
        for symbol, score in correlation_predictions.items():
            predictions[symbol] = predictions.get(symbol, 0) + score * 4

        # Strategy 4: Sector-based (if viewing bank stock, prefetch other banks)
        sector_predictions = self._predict_from_sector(current_symbol)
        for symbol, score in sector_predictions.items():
            predictions[symbol] = predictions.get(symbol, 0) + score * 2

        # Convert to priority scores (1-10)
        result = []
        max_score = max(predictions.values()) if predictions else 1
        for symbol, score in predictions.items():
            priority = min(10, max(1, int((score / max_score) * 10)))
            result.append((symbol, priority))

        # Sort by priority and return top 10
        result.sort(key=lambda x: x[1], reverse=True)
        return result[:10]

    def _predict_from_sequence(self, current_symbol: str) -> Dict[str, float]:
        """
        Predict based on access sequences

        Args:
            current_symbol: Current symbol

        Returns:
            Dict of symbol -> score
        """
        predictions = defaultdict(float)

        # Look at sequences where current_symbol appeared
        sequence_list = list(self.symbol_sequences)
        for i, (symbol, timestamp) in enumerate(sequence_list):
            if symbol == current_symbol and i < len(sequence_list) - 1:
                next_symbol, _ = sequence_list[i + 1]
                # More recent sequences have higher weight
                recency_weight = 1.0 / (len(sequence_list) - i)
                predictions[next_symbol] += recency_weight

        return dict(predictions)

    def _predict_from_time_patterns(self) -> Dict[str, float]:
        """
        Predict based on time-of-day patterns

        Returns:
            Dict of symbol -> score
        """
        current_hour = datetime.now().hour
        predictions = {}

        # Symbols typically accessed at this hour
        symbols_this_hour = self.time_based_patterns.get(current_hour, set())
        for symbol in symbols_this_hour:
            # Check if already in cache
            if not self._is_in_cache(symbol, 'quote'):
                predictions[symbol] = 1.0

        return predictions

    def _predict_from_correlations(self, current_symbol: str) -> Dict[str, float]:
        """
        Predict based on symbol correlations

        Args:
            current_symbol: Current symbol

        Returns:
            Dict of symbol -> score
        """
        # Find symbols frequently accessed together with current_symbol
        predictions = defaultdict(float)

        # Look at co-occurrences within 5-minute windows
        sequence_list = list(self.symbol_sequences)
        for i, (symbol, timestamp) in enumerate(sequence_list):
            if symbol == current_symbol:
                # Look at symbols accessed within 5 minutes
                window_start = timestamp - timedelta(minutes=5)
                window_end = timestamp + timedelta(minutes=5)

                for j, (other_symbol, other_time) in enumerate(sequence_list):
                    if (other_symbol != current_symbol and
                        window_start <= other_time <= window_end):
                        predictions[other_symbol] += 1.0

        # Normalize
        if predictions:
            max_count = max(predictions.values())
            predictions = {k: v / max_count for k, v in predictions.items()}

        return dict(predictions)

    def _predict_from_sector(self, current_symbol: str) -> Dict[str, float]:
        """
        Predict based on sector membership

        Args:
            current_symbol: Current symbol

        Returns:
            Dict of symbol -> score
        """
        # Sector mappings (simplified)
        sectors = {
            'BANKING': ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'AXISBANK', 'SBIN', 'INDUSINDBK'],
            'IT': ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM'],
            'AUTO': ['MARUTI', 'TATAMOTORS', 'M&M', 'BAJAJ-AUTO', 'HEROMOTOCO'],
            'PHARMA': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB'],
            'FMCG': ['HINDUNILVR', 'ITC', 'NESTLEIND', 'BRITANNIA']
        }

        predictions = {}

        # Find sector of current symbol
        for sector, symbols in sectors.items():
            if current_symbol in symbols:
                # Prefetch other symbols in same sector
                for symbol in symbols:
                    if symbol != current_symbol:
                        predictions[symbol] = 0.8

                break

        return predictions

    def _schedule_prefetch(self, symbol: str, data_type: str, priority: int):
        """
        Schedule a prefetch request

        Args:
            symbol: Symbol to prefetch
            data_type: Type of data to prefetch
            priority: Priority (1-10)
        """
        # Skip if already in cache
        if self._is_in_cache(symbol, data_type):
            return

        # Skip if already being prefetched
        prefetch_key = f"{symbol}:{data_type}"
        if prefetch_key in self.active_prefetches:
            return

        request = PrefetchRequest(
            symbol=symbol,
            data_type=data_type,
            priority=priority,
            requested_at=datetime.now()
        )

        # Add to queue (using negative priority for max-heap behavior)
        asyncio.run_coroutine_threadsafe(
            self.prefetch_queue.put((-priority, request)),
            asyncio.get_event_loop()
        )

        logger.debug(f"Scheduled prefetch: {symbol} ({data_type}), priority={priority}")

    def _prefetch_worker(self):
        """Background worker that processes prefetch requests"""
        logger.info("Prefetch worker started")

        while self._running:
            try:
                # Rate limiting: max N requests per minute
                requests_this_minute = 0
                minute_start = time.time()

                while (self._running and
                       requests_this_minute < self.max_prefetch_per_minute):

                    try:
                        # Get highest priority request (timeout 1 second)
                        priority, request = asyncio.run_coroutine_threadsafe(
                            asyncio.wait_for(
                                self.prefetch_queue.get(),
                                timeout=1.0
                            ),
                            asyncio.get_event_loop()
                        ).result()

                        self._execute_prefetch(request)
                        requests_this_minute += 1

                    except asyncio.TimeoutError:
                        # No requests in queue
                        break
                    except Exception as e:
                        logger.error(f"Prefetch error: {e}")

                # Sleep until next minute
                elapsed = time.time() - minute_start
                if elapsed < 60:
                    time.sleep(60 - elapsed)

            except Exception as e:
                logger.error(f"Prefetch worker error: {e}")
                time.sleep(5)

        logger.info("Prefetch worker stopped")

    def _execute_prefetch(self, request: PrefetchRequest):
        """
        Execute a prefetch request

        Args:
            request: Prefetch request to execute
        """
        prefetch_key = f"{request.symbol}:{request.data_type}"

        try:
            self.active_prefetches.add(prefetch_key)

            # Fetch data
            if request.data_type == 'quote':
                data = self.data_provider.get_quote(request.symbol)
            elif request.data_type == 'historical':
                data = self.data_provider.get_historical_data(
                    request.symbol,
                    interval='minute',
                    from_date=datetime.now() - timedelta(days=1),
                    to_date=datetime.now()
                )
            else:
                logger.warning(f"Unknown data type: {request.data_type}")
                return

            # Cache the data
            cache_key = f"prefetch:{request.data_type}:{request.symbol}"
            self.redis.setex(
                cache_key,
                60,  # 60 second TTL
                str(data)  # In production, use proper serialization
            )

            self.stats['total_prefetches'] += 1
            self.stats['successful_prefetches'] += 1

            logger.debug(
                f"Prefetched {request.symbol} ({request.data_type}), "
                f"priority={request.priority}"
            )

        except Exception as e:
            logger.error(f"Failed to prefetch {request.symbol}: {e}")

        finally:
            self.active_prefetches.discard(prefetch_key)
            request.completed = True

    def _is_in_cache(self, symbol: str, data_type: str) -> bool:
        """
        Check if data is already in cache

        Args:
            symbol: Symbol to check
            data_type: Data type to check

        Returns:
            True if in cache
        """
        cache_key = f"{data_type}:{symbol}"
        return self.redis.exists(cache_key) or self.redis.exists(f"prefetch:{cache_key}")

    def get_statistics(self) -> Dict:
        """
        Get prefetch statistics

        Returns:
            Statistics dictionary
        """
        if self.stats['total_prefetches'] > 0:
            self.stats['prefetch_accuracy'] = (
                self.stats['cache_hits_from_prefetch'] /
                self.stats['total_prefetches']
            )

        return self.stats


class SmartPrefetchScheduler:
    """
    Schedule prefetching based on market conditions and system load
    """

    def __init__(self, prefetcher: PredictivePrefetcher):
        """
        Initialize scheduler

        Args:
            prefetcher: Predictive prefetcher instance
        """
        self.prefetcher = prefetcher

    def should_prefetch_now(self) -> bool:
        """
        Determine if prefetching should run now based on market conditions

        Returns:
            True if should prefetch
        """
        now = datetime.now()
        hour = now.hour
        minute = now.minute

        # Don't prefetch during market open (high load)
        if hour == 9 and 15 <= minute <= 30:
            return False

        # Don't prefetch during market close (high load)
        if hour == 15 and 25 <= minute <= 35:
            return False

        # Prefetch aggressively before market open
        if hour == 9 and minute < 15:
            return True

        # Normal prefetching during trading hours
        if 9 <= hour < 16:
            return True

        # Minimal prefetching after hours
        return False


# Integration example
def integrate_prefetch_with_data_provider(data_provider, redis_client):
    """
    Integrate prefetching with data provider

    Args:
        data_provider: Data provider instance
        redis_client: Redis client

    Returns:
        Prefetcher instance
    """
    # Initialize prefetcher
    prefetcher = PredictivePrefetcher(
        data_provider=data_provider,
        redis_client=redis_client,
        max_prefetch_per_minute=100
    )

    # Start prefetch manager
    prefetcher.start()

    # Wrap data provider methods to record access
    original_get_quote = data_provider.get_quote

    def wrapped_get_quote(symbol):
        # Record access for learning
        prefetcher.record_access(symbol, 'quote')
        # Call original method
        return original_get_quote(symbol)

    data_provider.get_quote = wrapped_get_quote

    logger.info("Prefetching integrated with data provider")
    return prefetcher


if __name__ == "__main__":
    # Example usage
    import redis

    # Initialize Redis
    redis_client = redis.Redis(host='localhost', port=6379, db=0)

    # Initialize prefetcher
    prefetcher = PredictivePrefetcher(
        data_provider=None,  # Inject your data provider
        redis_client=redis_client,
        max_prefetch_per_minute=100
    )

    # Start prefetching
    prefetcher.start()

    # Simulate access patterns
    symbols = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK']
    for symbol in symbols:
        prefetcher.record_access(symbol)
        time.sleep(1)

    # Get statistics
    time.sleep(5)
    stats = prefetcher.get_statistics()
    print(f"Prefetch statistics: {stats}")

    # Stop
    prefetcher.stop()
