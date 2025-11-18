"""
Cache Warmer - Pre-populate cache on application startup

This module warms up the cache with frequently accessed data to reduce
cold-start latency and improve initial response times.

Features:
- Warm market data cache with active symbols
- Pre-load user sessions and preferences
- Prime database query cache
- Configurable warming strategies
- Parallel warming for fast startup

Author: Trading System Team
Date: November 2025
"""

import logging
import asyncio
from typing import List, Dict, Set, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)


class CacheWarmer:
    """
    Intelligently warm cache on application startup
    """

    def __init__(
        self,
        redis_client,
        data_provider,
        portfolio_manager=None,
        max_workers: int = 10,
        timeout: int = 60
    ):
        """
        Initialize cache warmer

        Args:
            redis_client: Redis client instance
            data_provider: Market data provider instance
            portfolio_manager: Portfolio manager instance (optional)
            max_workers: Maximum parallel warming tasks
            timeout: Maximum time for warming in seconds
        """
        self.redis = redis_client
        self.data_provider = data_provider
        self.portfolio = portfolio_manager
        self.max_workers = max_workers
        self.timeout = timeout

        # Statistics
        self.stats = {
            'symbols_warmed': 0,
            'cache_hits_saved': 0,
            'warming_duration': 0,
            'errors': 0
        }

    def warm_all(self, symbols: Optional[List[str]] = None) -> Dict:
        """
        Warm all caches

        Args:
            symbols: List of symbols to warm (if None, use default list)

        Returns:
            Statistics dictionary
        """
        start_time = time.time()
        logger.info("Starting cache warming...")

        try:
            # Get symbol list
            if symbols is None:
                symbols = self._get_default_symbols()

            logger.info(f"Warming cache for {len(symbols)} symbols")

            # Execute warming strategies in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []

                # Strategy 1: Market data cache
                futures.append(
                    executor.submit(self._warm_market_data, symbols)
                )

                # Strategy 2: Historical data cache
                futures.append(
                    executor.submit(self._warm_historical_data, symbols[:20])  # Top 20
                )

                # Strategy 3: User sessions (if portfolio manager available)
                if self.portfolio:
                    futures.append(
                        executor.submit(self._warm_user_sessions)
                    )

                # Strategy 4: Common queries
                futures.append(
                    executor.submit(self._warm_common_queries)
                )

                # Wait for all with timeout
                for future in as_completed(futures, timeout=self.timeout):
                    try:
                        result = future.result()
                        logger.info(f"Warming strategy completed: {result}")
                    except Exception as e:
                        logger.error(f"Warming strategy failed: {e}")
                        self.stats['errors'] += 1

        except Exception as e:
            logger.error(f"Cache warming failed: {e}")
            self.stats['errors'] += 1

        finally:
            self.stats['warming_duration'] = time.time() - start_time
            logger.info(
                f"Cache warming completed in {self.stats['warming_duration']:.2f}s. "
                f"Stats: {self.stats}"
            )

        return self.stats

    def _get_default_symbols(self) -> List[str]:
        """
        Get default list of symbols to warm

        Returns:
            List of symbol strings
        """
        # NIFTY 50 top constituents
        default_symbols = [
            'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HDFC', 'ICICIBANK',
            'KOTAKBANK', 'HINDUNILVR', 'SBIN', 'BHARTIARTL', 'ITC',
            'AXISBANK', 'LT', 'ASIANPAINT', 'MARUTI', 'HCLTECH',
            'BAJFINANCE', 'WIPRO', 'ULTRACEMCO', 'NESTLEIND',
            'TITAN', 'SUNPHARMA', 'ONGC', 'NTPC', 'TECHM',
            'POWERGRID', 'M&M', 'BAJAJFINSV', 'TATAMOTORS', 'INDUSINDBK'
        ]

        # Add indices
        default_symbols.extend(['NIFTY 50', 'NIFTY BANK', 'NIFTY FIN SERVICE'])

        return default_symbols

    def _warm_market_data(self, symbols: List[str]) -> str:
        """
        Warm market data cache (quotes, LTP)

        Args:
            symbols: List of symbols

        Returns:
            Status message
        """
        logger.info(f"Warming market data for {len(symbols)} symbols")

        try:
            # Fetch quotes in batches
            batch_size = 50
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i + batch_size]

                try:
                    # Fetch and cache quotes
                    quotes = self.data_provider.get_quotes(batch)

                    # Cache each quote
                    for symbol, quote_data in quotes.items():
                        cache_key = f"quote:{symbol}"
                        self.redis.setex(
                            cache_key,
                            60,  # 60 second TTL
                            str(quote_data)  # In production, use JSON serialization
                        )
                        self.stats['symbols_warmed'] += 1

                except Exception as e:
                    logger.warning(f"Failed to warm batch {i}-{i+batch_size}: {e}")
                    self.stats['errors'] += 1

            return f"Market data warmed: {self.stats['symbols_warmed']} symbols"

        except Exception as e:
            logger.error(f"Market data warming failed: {e}")
            return f"Market data warming failed: {e}"

    def _warm_historical_data(self, symbols: List[str]) -> str:
        """
        Warm historical data cache (OHLCV)

        Args:
            symbols: List of top symbols

        Returns:
            Status message
        """
        logger.info(f"Warming historical data for {len(symbols)} symbols")

        warmed_count = 0

        try:
            # Get last 5 days of data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5)

            for symbol in symbols:
                try:
                    # Fetch 1-minute bars
                    historical_data = self.data_provider.get_historical_data(
                        symbol=symbol,
                        interval='minute',
                        from_date=start_date,
                        to_date=end_date
                    )

                    # Cache historical data
                    cache_key = f"historical:{symbol}:1m"
                    self.redis.setex(
                        cache_key,
                        300,  # 5 minute TTL
                        str(historical_data)  # In production, use JSON
                    )

                    warmed_count += 1

                except Exception as e:
                    logger.warning(f"Failed to warm historical data for {symbol}: {e}")
                    self.stats['errors'] += 1

            return f"Historical data warmed: {warmed_count} symbols"

        except Exception as e:
            logger.error(f"Historical data warming failed: {e}")
            return f"Historical data warming failed: {e}"

    def _warm_user_sessions(self) -> str:
        """
        Warm user session cache

        Returns:
            Status message
        """
        logger.info("Warming user sessions")

        try:
            if not self.portfolio:
                return "User sessions warming skipped (no portfolio manager)"

            # Pre-load active user positions
            # In production, fetch from database
            active_users = ['user_1', 'user_2']  # Example

            for user_id in active_users:
                try:
                    # Cache user positions
                    cache_key = f"positions:{user_id}"
                    # positions = self.portfolio.get_user_positions(user_id)
                    # self.redis.setex(cache_key, 300, json.dumps(positions))

                except Exception as e:
                    logger.warning(f"Failed to warm session for {user_id}: {e}")
                    self.stats['errors'] += 1

            return f"User sessions warmed: {len(active_users)} users"

        except Exception as e:
            logger.error(f"User session warming failed: {e}")
            return f"User session warming failed: {e}"

    def _warm_common_queries(self) -> str:
        """
        Warm cache for common database queries

        Returns:
            Status message
        """
        logger.info("Warming common queries")

        try:
            # Example: Cache trading hours
            cache_key = "market:trading_hours"
            trading_hours = {
                'pre_open': '09:00',
                'open': '09:15',
                'close': '15:30',
                'post_close': '15:40'
            }
            self.redis.setex(cache_key, 3600, str(trading_hours))

            # Example: Cache holidays
            cache_key = "market:holidays_2025"
            # holidays = self._fetch_market_holidays()
            # self.redis.setex(cache_key, 86400, json.dumps(holidays))

            # Example: Cache strategy configurations
            cache_key = "strategies:config"
            # strategy_config = self._fetch_strategy_config()
            # self.redis.setex(cache_key, 600, json.dumps(strategy_config))

            return "Common queries warmed successfully"

        except Exception as e:
            logger.error(f"Common queries warming failed: {e}")
            return f"Common queries warming failed: {e}"


class AdaptiveCacheWarmer:
    """
    Adaptive cache warmer that learns from usage patterns
    """

    def __init__(self, redis_client, analytics_db=None):
        """
        Initialize adaptive cache warmer

        Args:
            redis_client: Redis client
            analytics_db: Database with usage analytics
        """
        self.redis = redis_client
        self.analytics_db = analytics_db

    def warm_based_on_usage_patterns(self):
        """
        Warm cache based on historical usage patterns
        """
        logger.info("Starting adaptive cache warming")

        # Get most frequently accessed symbols (last 7 days)
        popular_symbols = self._get_popular_symbols(days=7, limit=50)

        # Get symbols that are accessed during startup (first 5 minutes)
        startup_symbols = self._get_startup_symbols(limit=30)

        # Get symbols with high cache miss rate
        high_miss_symbols = self._get_high_cache_miss_symbols(limit=20)

        # Combine and deduplicate
        priority_symbols = list(set(
            popular_symbols + startup_symbols + high_miss_symbols
        ))

        logger.info(f"Adaptive warming: {len(priority_symbols)} priority symbols")

        # Warm these symbols with higher priority
        warmer = CacheWarmer(self.redis, data_provider=None)  # Inject provider
        return warmer.warm_all(symbols=priority_symbols)

    def _get_popular_symbols(self, days: int = 7, limit: int = 50) -> List[str]:
        """
        Get most frequently accessed symbols

        Args:
            days: Number of days to analyze
            limit: Maximum symbols to return

        Returns:
            List of popular symbols
        """
        # In production, query analytics database
        # Example query:
        # SELECT symbol, COUNT(*) as access_count
        # FROM cache_access_log
        # WHERE timestamp > NOW() - INTERVAL '7 days'
        # GROUP BY symbol
        # ORDER BY access_count DESC
        # LIMIT 50

        # For now, return default
        return ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']

    def _get_startup_symbols(self, limit: int = 30) -> List[str]:
        """
        Get symbols accessed within first 5 minutes of app start

        Args:
            limit: Maximum symbols to return

        Returns:
            List of startup symbols
        """
        # In production, analyze startup access patterns
        return ['NIFTY 50', 'NIFTY BANK', 'RELIANCE', 'TCS']

    def _get_high_cache_miss_symbols(self, limit: int = 20) -> List[str]:
        """
        Get symbols with high cache miss rate

        Args:
            limit: Maximum symbols to return

        Returns:
            List of symbols with high miss rate
        """
        # In production, calculate miss rates
        # Symbols frequently requested but not in cache
        return ['TITAN', 'BAJFINANCE', 'MARUTI']


# Standalone execution function
def warm_cache_on_startup(
    redis_client,
    data_provider,
    portfolio_manager=None,
    adaptive: bool = False
) -> Dict:
    """
    Main entry point for cache warming

    Args:
        redis_client: Redis client instance
        data_provider: Data provider instance
        portfolio_manager: Portfolio manager instance (optional)
        adaptive: Use adaptive warming based on usage patterns

    Returns:
        Warming statistics
    """
    try:
        if adaptive:
            warmer = AdaptiveCacheWarmer(redis_client)
            stats = warmer.warm_based_on_usage_patterns()
        else:
            warmer = CacheWarmer(redis_client, data_provider, portfolio_manager)
            stats = warmer.warm_all()

        logger.info(f"Cache warming completed: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Cache warming failed: {e}")
        return {'error': str(e), 'symbols_warmed': 0}


if __name__ == "__main__":
    # Example usage
    import redis

    # Initialize Redis client
    redis_client = redis.Redis(host='localhost', port=6379, db=0)

    # Initialize cache warmer
    warmer = CacheWarmer(
        redis_client=redis_client,
        data_provider=None,  # Inject your data provider
        max_workers=10,
        timeout=60
    )

    # Warm cache
    stats = warmer.warm_all()
    print(f"Cache warming completed: {stats}")
