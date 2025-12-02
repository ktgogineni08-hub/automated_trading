#!/usr/bin/env python3
"""
Data Provider
Fetches and caches market data from Kite API with rate limiting
"""

import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
from kiteconnect import KiteConnect
import logging

from unified_config import get_config
from infrastructure.rate_limiting import EnhancedRateLimiter
from infrastructure.caching import LRUCacheWithTTL
from enhanced_technical_analysis import EnhancedTechnicalAnalysis

logger = logging.getLogger('trading_system.data_provider')


class DataProvider:
    """
    Market Data Provider with caching and rate limiting

    Features:
    - Fetches historical OHLCV data from Kite API
    - LRU cache with 60-second TTL for price data
    - Rate limiting protection
    - Comprehensive technical analysis signals
    - Automatic retry on failures

    Cache Strategy:
    - Main cache: 60-second TTL for raw OHLCV data
    - Missing token cache: Avoid repeated lookups for invalid symbols
    """

    def __init__(self, kite: KiteConnect = None, instruments_map: Dict = None, use_yf_fallback: bool = True):
        self.kite = kite
        self.instruments = instruments_map or {}
        self.use_yf = use_yf_fallback
        self.rate_limiter = EnhancedRateLimiter()
        self.cache: Dict[str, Tuple[float, pd.DataFrame]] = {}
        self.system_config = get_config()
        self.cache_ttl = 60 # Default TTL

        # LRU cache for price data (60-second TTL)
        self.price_cache = LRUCacheWithTTL(max_size=1000, ttl_seconds=60)

        # Cache for symbols without tokens (to avoid repeated lookups)
        self._missing_token_cache: set = set()
        self._missing_token_logged: set = set()  # Track which symbols we've already logged

        # Cache for instruments list to reduce API calls
        self._instruments_cache = None
        self._instruments_cache_time = 0
        self._instruments_cache_ttl = 300  # Cache for 5 minutes

    def fetch_with_retry(self, symbol: str, interval: str = "5minute",
                        days: int = 5, max_retries: int = 3) -> pd.DataFrame:
        """
        Fetch historical data with retry logic and caching

        Args:
            symbol: Trading symbol
            interval: Candle interval ('5minute', '15minute', 'day')
            days: Number of days of historical data
            max_retries: Maximum retry attempts

        Returns:
            DataFrame with OHLCV data or empty DataFrame on failure
        """
        cache_key = f"{symbol}_{interval}_{days}"

        # Check cache first
        cached_data = self.price_cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        if not self.kite:
            return pd.DataFrame()

        # Check missing token cache
        if symbol in self._missing_token_cache:
            return pd.DataFrame()

        token = self.instruments.get(symbol)
        if not token:
            self._missing_token_cache.add(symbol)
            if symbol not in self._missing_token_logged:
                self._missing_token_logged.add(symbol)
                if symbol not in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']:
                    logger.warning(f"No instrument token found for {symbol}")
            return pd.DataFrame()

        for attempt in range(max_retries):
            try:
                end = datetime.now()
                start = end - timedelta(days=days)
                
                if not self.rate_limiter.acquire('historical_data'):
                    logger.warning(f"Rate limit hit for {symbol}, retrying...")
                    time.sleep(0.5) # Short sleep to allow token refill
                    continue

                candles = self.kite.historical_data(token, start, end, interval)

                if candles:
                    df = pd.DataFrame(candles)
                    if "date" in df.columns:
                        df["date"] = pd.to_datetime(df["date"])
                        df.set_index("date", inplace=True)

                    # Ensure standard column names
                    df = df.rename(columns={
                        "open": "open",
                        "high": "high",
                        "low": "low",
                        "close": "close",
                        "volume": "volume"
                    })

                    # Ensure all expected columns exist
                    expected_cols = ["open", "high", "low", "close", "volume"]
                    for c in expected_cols:
                        if c not in df.columns:
                            df[c] = np.nan

                    df = df[expected_cols]
                    self.price_cache.set(cache_key, df)
                    return df

            except Exception as e:
                logger.error(f"Data fetch attempt {attempt + 1} failed for {symbol}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue

        logger.error(f"Failed to fetch data for {symbol} after {max_retries} attempts")
        return pd.DataFrame()

    def get_enhanced_technical_signals(
        self,
        symbol: str,
        interval: str = "5minute",
        days: int = 5
    ) -> Optional[Dict]:
        """
        Get comprehensive technical analysis signals using professional indicators

        Args:
            symbol: Trading symbol
            interval: Candle interval
            days: Number of days of historical data

        Returns:
            Dict with RSI, MACD, Moving Averages, Volume confirmation, etc.
            None if data unavailable
        """
        try:
            # Fetch historical data
            df = self.fetch_with_retry(symbol, interval, days)
            if df.empty or len(df) < 50:
                return None

            analyzer = EnhancedTechnicalAnalysis()

            # Prepare OHLC dataframe for candlestick pattern detection
            ohlc_df = None
            if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
                ohlc_df = df[['open', 'high', 'low', 'close']].copy()

            # Generate comprehensive signals
            signals = analyzer.generate_comprehensive_signals(
                prices=df['close'],
                volumes=df['volume'],
                ohlc=ohlc_df
            )

            return {
                'rsi': signals.rsi,
                'rsi_signal': signals.rsi_signal,
                'macd_line': signals.macd_line,
                'macd_signal': signals.macd_signal,
                'macd_histogram': signals.macd_histogram,
                'macd_crossover': signals.macd_crossover,
                'sma_20': signals.sma_20,
                'sma_50': signals.sma_50,
                'sma_200': signals.sma_200,
                'price_vs_ma': signals.price_vs_ma,
                'current_volume': signals.current_volume,
                'avg_volume_20d': signals.avg_volume_20d,
                'volume_confirmation': signals.volume_confirmation,
                'candlestick_pattern': signals.candlestick_pattern.value,
                'trend_direction': signals.trend_direction.value,
                'signal_strength': signals.signal_strength
            }

        except Exception as e:
            logger.error(f"❌ Error calculating technical signals for {symbol}: {e}")
            return None
