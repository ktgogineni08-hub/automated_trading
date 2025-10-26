#!/usr/bin/env python3
"""
Instruments Bootstrap Service
Loads and caches instrument tokens from Zerodha Kite API
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta
from kiteconnect import KiteConnect

logger = logging.getLogger('trading_system.instruments')


class InstrumentsService:
    """
    Service to bootstrap and cache instrument tokens from Zerodha

    Features:
    - Fetches instruments from Kite API
    - Caches to local JSON file
    - Auto-refresh if cache is stale (daily)
    - Builds fast lookup map: symbol -> instrument_token
    """

    def __init__(self, kite: Optional[KiteConnect] = None, cache_dir: str = 'data/cache'):
        """
        Initialize instruments service

        Args:
            kite: KiteConnect instance (required for fetching)
            cache_dir: Directory to cache instruments
        """
        self.kite = kite
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / 'instruments_cache.json'
        self.cache_ttl = timedelta(days=1)  # Refresh daily

        self._instruments_map: Dict[str, int] = {}
        self._last_refresh: Optional[datetime] = None

    def get_instruments_map(self, exchange: str = 'NSE', force_refresh: bool = False) -> Dict[str, int]:
        """
        Get instruments map for specified exchange

        Args:
            exchange: Exchange to fetch (NSE, NFO, BFO, etc.)
            force_refresh: Force refresh even if cache is fresh

        Returns:
            Dict mapping trading_symbol -> instrument_token
        """
        # Check if we need to refresh
        needs_refresh = (
            force_refresh or
            not self._instruments_map or
            not self._is_cache_fresh()
        )

        if needs_refresh:
            logger.info(f"🔄 Refreshing instruments for {exchange}...")
            self._refresh_instruments(exchange)

        return self._instruments_map.copy()

    def _is_cache_fresh(self) -> bool:
        """Check if cached instruments are still fresh"""
        if not self.cache_file.exists():
            return False

        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)

            cached_time = datetime.fromisoformat(cache_data.get('timestamp', '2000-01-01'))
            age = datetime.now() - cached_time

            return age < self.cache_ttl
        except Exception:
            return False

    def _refresh_instruments(self, exchange: str):
        """
        Refresh instruments from Kite API or cache

        Args:
            exchange: Exchange to fetch
        """
        # Try to load from cache first
        if self._load_from_cache(exchange):
            logger.info(f"✅ Loaded {len(self._instruments_map)} instruments from cache")
            return

        # Fetch from API if cache miss and kite available
        if not self.kite:
            logger.warning("⚠️ No Kite instance - using empty instruments map")
            self._instruments_map = {}
            return

        try:
            logger.info(f"📡 Fetching instruments from Kite API for {exchange}...")
            instruments = self.kite.instruments(exchange)

            # Build symbol -> token map
            self._instruments_map = {}
            for inst in instruments:
                trading_symbol = inst.get('tradingsymbol')
                instrument_token = inst.get('instrument_token')

                if trading_symbol and instrument_token:
                    self._instruments_map[trading_symbol] = instrument_token

            # Save to cache
            self._save_to_cache(exchange)

            logger.info(f"✅ Loaded {len(self._instruments_map)} instruments from Kite API")
            self._last_refresh = datetime.now()

        except Exception as e:
            logger.error(f"❌ Failed to fetch instruments from Kite: {e}")
            self._instruments_map = {}

    def _load_from_cache(self, exchange: str) -> bool:
        """
        Load instruments from cache file

        Args:
            exchange: Exchange name

        Returns:
            bool: True if successfully loaded from cache
        """
        if not self.cache_file.exists():
            return False

        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)

            # Check if exchange matches
            if cache_data.get('exchange') != exchange:
                return False

            # Check if cache is fresh
            if not self._is_cache_fresh():
                return False

            self._instruments_map = cache_data.get('instruments', {})
            # Convert string keys to string, values to int
            self._instruments_map = {k: int(v) for k, v in self._instruments_map.items()}

            self._last_refresh = datetime.fromisoformat(cache_data.get('timestamp'))
            return True

        except Exception as e:
            logger.warning(f"⚠️ Failed to load instruments from cache: {e}")
            return False

    def _save_to_cache(self, exchange: str):
        """
        Save instruments to cache file

        Args:
            exchange: Exchange name
        """
        try:
            cache_data = {
                'exchange': exchange,
                'timestamp': datetime.now().isoformat(),
                'count': len(self._instruments_map),
                'instruments': self._instruments_map
            }

            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)

            logger.info(f"💾 Cached {len(self._instruments_map)} instruments to {self.cache_file}")

        except Exception as e:
            logger.warning(f"⚠️ Failed to cache instruments: {e}")

    def get_token(self, symbol: str) -> Optional[int]:
        """
        Get instrument token for a symbol

        Args:
            symbol: Trading symbol

        Returns:
            Instrument token or None if not found
        """
        return self._instruments_map.get(symbol.upper())

    def get_stats(self) -> Dict:
        """Get statistics about loaded instruments"""
        return {
            'total_instruments': len(self._instruments_map),
            'last_refresh': self._last_refresh.isoformat() if self._last_refresh else None,
            'cache_file': str(self.cache_file),
            'cache_exists': self.cache_file.exists(),
            'cache_fresh': self._is_cache_fresh()
        }


# Global singleton instance
_instruments_service: Optional[InstrumentsService] = None


def get_instruments_service(kite: Optional[KiteConnect] = None) -> InstrumentsService:
    """
    Get global instruments service instance (singleton)

    Args:
        kite: KiteConnect instance (only needed on first call)

    Returns:
        InstrumentsService instance
    """
    global _instruments_service

    if _instruments_service is None:
        _instruments_service = InstrumentsService(kite=kite)
        logger.info("✅ Initialized global instruments service")

    return _instruments_service


if __name__ == "__main__":
    # Test the service
    import logging
    logging.basicConfig(level=logging.INFO)

    service = InstrumentsService()

    # Test cache loading
    instruments = service.get_instruments_map('NSE')
    print(f"\n📊 Loaded {len(instruments)} instruments")

    # Test token lookup
    if instruments:
        sample_symbols = list(instruments.keys())[:5]
        for symbol in sample_symbols:
            token = service.get_token(symbol)
            print(f"  {symbol}: {token}")

    # Print stats
    print(f"\n📈 Stats:")
    for key, value in service.get_stats().items():
        print(f"  {key}: {value}")
