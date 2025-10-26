#!/usr/bin/env python3
"""
FNO Data Provider
Fetches option chains, greeks, and market data for F&O trading
"""

import time
import random
from datetime import datetime
from typing import Dict, List, Optional, Any
from kiteconnect import KiteConnect
import logging

from fno.options import OptionContract, OptionChain
from fno.indices import FNOIndex, DynamicFNOIndices
from utilities.market_hours import MarketHoursManager
from infrastructure.rate_limiting import EnhancedRateLimiter

logger = logging.getLogger('trading_system.fno.data_provider')


DYNAMIC_FNO_INDICES = None


class FNODataProvider:
    """Provides F&O data including option chains"""

    def __init__(self, kite: KiteConnect = None):
        self.kite = kite
        self.option_chains: Dict[str, Dict[str, OptionChain]] = {}
        self.rate_limiter = EnhancedRateLimiter()

        # Instrument token cache for improved performance
        self.instrument_cache = {}
        self.cache_timestamp = None
        self.cache_expiry = 1800  # 30 minutes cache (instruments rarely change intraday)

        # O(1) lookup map: tradingsymbol -> {exchange, instrument_token, ...}
        # CRITICAL FIX: Prevents O(N×M) scan over ~200k instruments per price refresh
        self.instrument_lookup = {}
        self.lookup_cache_timestamp = None

        # Additional cache variables for fetch_option_chain method
        self._instruments_cache = None
        self._instruments_cache_time = 0
        self._instruments_cache_ttl = 3600  # 1 hour TTL

        # Initialize dynamic index discovery
        global DYNAMIC_FNO_INDICES
        if DYNAMIC_FNO_INDICES is None:
            DYNAMIC_FNO_INDICES = DynamicFNOIndices(kite)
        self.indices_provider = DYNAMIC_FNO_INDICES

    def _fetch_quote_with_retry(
        self,
        symbols: List[str],
        rate_key: str,
        max_attempts: int = 3,
        base_delay: float = 0.5
    ) -> Optional[Dict[str, Dict]]:
        """Fetch Kite quotes with retry/backoff to handle rate limits gracefully."""
        if not self.kite:
            logger.warning("⚠️ Kite client unavailable for quote fetch")
            return None

        last_error: Optional[Exception] = None
        delay = max(base_delay, 0.1)

        for attempt in range(1, max_attempts + 1):
            if not self.rate_limiter.acquire(rate_key):
                logger.debug(
                    "⏳ Rate limiter delaying quote fetch for %s (attempt %d/%d)",
                    symbols,
                    attempt,
                    max_attempts
                )
                time.sleep(delay)
                delay = min(delay * 2, 5.0)
                continue

            try:
                return self.kite.quote(symbols)
            except Exception as err:
                last_error = err
                message = str(err).lower()
                if 'too many requests' in message or getattr(err, 'code', None) == 429:
                    logger.warning(
                        "⚠️ Kite rate limit hit for %s (attempt %d/%d). Retrying in %.1fs",
                        symbols,
                        attempt,
                        max_attempts,
                        delay
                    )
                    time.sleep(delay)
                    delay = min(delay * 2, 5.0)
                    continue

                logger.error(f"❌ Quote request failed for {symbols}: {err}")
                return None

        logger.error(
            "❌ Exhausted %d attempts fetching quote for %s: %s",
            max_attempts,
            symbols,
            last_error
        )
        return None

    def get_available_indices(self) -> Dict[str, FNOIndex]:
        """Get all available F&O indices"""
        return self.indices_provider.get_available_indices()

    def _build_instrument_lookup(self) -> None:
        """Build O(1) lookup map from tradingsymbol to instrument details.

        CRITICAL FIX: This prevents O(N×M) scan over ~200k instruments for every price refresh.
        Called lazily on first use and cached for 30 minutes.
        """
        current_time = time.time()

        # Check if lookup is already built and still valid
        if (self.lookup_cache_timestamp and
            current_time - self.lookup_cache_timestamp < self.cache_expiry and
            self.instrument_lookup):
            return

        logger.info("Building instrument lookup map for O(1) access...")

        # Fetch instruments from both NFO and BFO
        nfo_instruments = self._get_instruments_cached("NFO")
        bfo_instruments = self._get_instruments_cached("BFO")
        all_instruments = nfo_instruments + bfo_instruments

        # Build the lookup dictionary
        self.instrument_lookup.clear()
        for inst in all_instruments:
            tradingsymbol = inst.get('tradingsymbol')
            if tradingsymbol:
                self.instrument_lookup[tradingsymbol] = {
                    'exchange': inst.get('exchange'),
                    'instrument_token': inst.get('instrument_token'),
                    'tradingsymbol': tradingsymbol
                }

        self.lookup_cache_timestamp = current_time
        logger.info(f"Built lookup map for {len(self.instrument_lookup)} instruments (NFO+BFO)")

    def _get_instruments_cached(self, exchange: str = "NFO") -> List[Dict]:
        """Get instruments with caching for improved performance"""
        cache_key = f"instruments_{exchange}"
        current_time = time.time()

        # Check if cache is valid
        if (self.cache_timestamp and
            current_time - self.cache_timestamp < self.cache_expiry and
            cache_key in self.instrument_cache):
            return self.instrument_cache[cache_key]

        # Fetch fresh instruments from Kite API
        try:
            instruments = self.kite.instruments(exchange)
            self.instrument_cache[cache_key] = instruments
            self.cache_timestamp = current_time
            logger.info(f"✅ Cached {len(instruments)} instruments for {exchange}")
            return instruments
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch instruments for {exchange}: {e}")
            # Return cached data if available, even if expired
            return self.instrument_cache.get(cache_key, [])

    def get_current_option_prices(self, option_symbols: List[str]) -> Dict[str, float]:
        """Fetch current market prices for option symbols with improved validation and retry logic"""
        if not self.kite or not option_symbols:
            return {}

        prices = {}
        retry_count = 3

        for attempt in range(retry_count):
            try:
                # CRITICAL FIX #8: Get instruments from BOTH NFO and BFO exchanges
                # CRITICAL FIX #9: Optimized caching to reduce API calls
                # CRITICAL FIX #10: O(1) lookup instead of O(N×M) scan over ~200k instruments
                # Some options (NIFTY, BANKNIFTY) are on NFO, others (SENSEX, BANKEX) are on BFO

                # Build the instrument lookup map (cached, only happens once per 30 min)
                self._build_instrument_lookup()

                symbol_to_quote_symbol = {}
                symbols_not_found = []

                # O(1) lookup per symbol instead of O(N) scan
                for symbol in option_symbols:
                    inst = self.instrument_lookup.get(symbol)
                    if inst:
                        # Use exchange:tradingsymbol format
                        quote_symbol = f"{inst['exchange']}:{inst['tradingsymbol']}"
                        symbol_to_quote_symbol[symbol] = quote_symbol
                    else:
                        symbols_not_found.append(symbol)

                # Log symbols that couldn't be found for debugging
                if symbols_not_found:
                    logger.debug(f"⚠️ Could not find instruments for: {', '.join(symbols_not_found[:3])}{'...' if len(symbols_not_found) > 3 else ''}")

                # Fetch quotes for all symbols with rate limiting
                if symbol_to_quote_symbol:
                    if not self.rate_limiter.acquire('option_quotes'):
                        continue
                    quote_symbols = list(symbol_to_quote_symbol.values())
                    quotes = self.kite.quote(quote_symbols)

                    # Map back to symbols with validation
                    for symbol, quote_symbol in symbol_to_quote_symbol.items():
                        if quote_symbol in quotes:
                            quote_data = quotes[quote_symbol]
                            last_price = quote_data.get('last_price', 0)

                            # Enhanced price validation - relaxed bounds for options
                            if last_price > 0 and last_price < 100000:  # Increased upper bound for options
                                # CRITICAL FIX: Always use last_price (LTP) for F&O
                                # Bid-ask midpoint is unreliable for options with wide spreads
                                # LTP is the actual last traded price and most accurate for current value
                                prices[symbol] = last_price
                                logger.debug(f"✅ Valid price for {symbol}: ₹{last_price:.2f}")
                            else:
                                logger.warning(f"⚠️ Skipping {symbol}: price {last_price} outside valid range (0 < price < 100000)")

                    logger.info(f"✅ Fetched valid prices for {len(prices)}/{len(option_symbols)} options")
                    break  # Success, exit retry loop

            except Exception as e:
                logger.warning(f"⚠️ Attempt {attempt + 1}/{retry_count} failed for option prices: {e}")
                if attempt < retry_count - 1:
                    time.sleep(1)  # Wait before retry
                else:
                    logger.error(f"❌ All {retry_count} attempts failed to fetch option prices")

        return prices

    def debug_specific_option(self, symbol: str):
        """Debug method to check specific option price and data"""
        try:
            logger.info(f"🔍 DEBUG: Checking specific option {symbol}")

            # Try to fetch the option price specifically
            prices = self.get_current_option_prices([symbol])

            if symbol in prices:
                price = prices[symbol]
                logger.info(f"✅ DEBUG: {symbol} price = ₹{price:.2f}")
                return price
            else:
                logger.warning(f"⚠️ DEBUG: {symbol} not found in price data")
                logger.info(f"🔍 DEBUG: Available symbols in response: {list(prices.keys())}")
                return None

        except Exception as e:
            logger.error(f"❌ DEBUG: Error checking {symbol}: {e}")
            return None

    def test_fno_connection(self) -> Dict:
        """Test F&O connection and permissions"""
        logger.info("🔍 Testing F&O connection and permissions...")

        if not self.kite:
            return {
                'success': False,
                'error': 'Kite connection not available',
                'can_access_fno': False,
                'available_indices': [],
                'total_instruments': 0
            }

        try:
            # Test basic connection
            profile = self.kite.profile()
            logger.info(f"✅ Kite profile: {profile.get('user_name')}")

            # Check margins to see if F&O is enabled
            margins = self.kite.margins()
            logger.info(f"✅ Margins available: {margins}")

            # Get all instruments
            logger.info("📋 Fetching NFO instruments...")
            instruments = self.kite.instruments("NFO")
            total_instruments = len(instruments)
            logger.info(f"✅ Total NFO instruments: {total_instruments}")

            # Check for F&O indices
            available_indices = []
            index_instruments = []

            for inst in instruments:
                if inst['instrument_type'] == 'FUT':
                    index_instruments.append(inst)
                    available_indices.append(inst['tradingsymbol'])

            logger.info(f"✅ Found {len(index_instruments)} index instruments:")
            for inst in index_instruments[:10]:  # Show first 10
                logger.info(f"   • {inst['tradingsymbol']} ({inst['instrument_type']})")

            # Check for option instruments
            option_instruments = [inst for inst in instruments
                                if inst['instrument_type'] in ['CE', 'PE']]
            logger.info(f"✅ Found {len(option_instruments)} option instruments")

            # Test quote fetch for a known instrument
            can_fetch_quotes = False
            if index_instruments:
                test_instrument = index_instruments[0]
                try:
                    quote = self.kite.quote(test_instrument['instrument_token'])
                    if quote:
                        can_fetch_quotes = True
                        logger.info(f"✅ Quote fetch successful: {quote}")
                except Exception as e:
                    logger.warning(f"⚠️ Quote fetch failed: {e}")

            return {
                'success': True,
                'error': None,
                'can_access_fno': True,
                'available_indices': list(set(available_indices)),
                'total_instruments': total_instruments,
                'index_instruments_count': len(index_instruments),
                'option_instruments_count': len(option_instruments),
                'can_fetch_quotes': can_fetch_quotes,
                'user_profile': profile,
                'margins': margins
            }

        except Exception as e:
            logger.error(f"❌ F&O connection test failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'can_access_fno': False,
                'available_indices': [],
                'total_instruments': 0
            }

    def fetch_option_chain(self, index_symbol: str, expiry_date: str = None) -> Optional[OptionChain]:
        """Fetch option chain for a specific index and expiry - ONLY live Kite data"""
        try:
            if not self.kite:
                logger.error("❌ Kite connection not available - cannot fetch real option chain")
                return None

            # Get LIVE instruments from Kite API - use cache to reduce API calls
            current_time = time.time()
            if self._instruments_cache is None or (current_time - self._instruments_cache_time) > self._instruments_cache_ttl:
                logger.info("🔄 Fetching live instruments from all exchanges (cache expired)...")
                nfo_instruments = self.kite.instruments("NFO")  # NSE F&O
                bfo_instruments = []

                # Try to get BSE F&O instruments if available
                try:
                    bfo_instruments = self.kite.instruments("BFO")  # BSE F&O
                    logger.info(f"✅ Retrieved {len(bfo_instruments)} BSE F&O instruments")
                except Exception as e:
                    logger.debug(f"BSE F&O not available: {e}")

                # Combine and cache instruments
                self._instruments_cache = nfo_instruments + bfo_instruments
                self._instruments_cache_time = current_time
                logger.info(f"✅ Cached {len(self._instruments_cache)} instruments (NSE: {len(nfo_instruments)}, BSE: {len(bfo_instruments)})")
            else:
                logger.info(f"✅ Using cached instruments ({len(self._instruments_cache)} total, age: {int(current_time - self._instruments_cache_time)}s)")

            instruments = self._instruments_cache

            # Enhanced index instrument search with better matching
            index_instrument = None

            # First, try to find the exact index instrument
            logger.info(f"🔍 Searching for {index_symbol} in NFO instruments...")

            # Look for futures instruments (FUT)
            for inst in instruments:
                if inst['instrument_type'] == 'FUT':
                    if index_symbol == inst['tradingsymbol']:
                        index_instrument = inst
                        logger.info(f"✅ Found exact match: {inst['tradingsymbol']} ({inst['instrument_type']})")
                        break

            # If not found, try partial matching and collect all candidates
            if not index_instrument:
                logger.info(f"🔄 Exact match not found, trying partial matching for {index_symbol}...")
                candidates = []
                prefix = index_symbol.upper()
                for inst in instruments:
                    tradingsymbol = str(inst.get('tradingsymbol', '')).upper()
                    if (inst['instrument_type'] == 'FUT' and
                        (tradingsymbol.startswith(prefix) or
                         tradingsymbol == prefix)):
                        candidates.append(inst)

                # If we have candidates, pick the best available expiry
                if candidates:
                    from datetime import datetime, date
                    current_date = datetime.now()
                    current_date_str = current_date.strftime('%Y-%m-%d')
                    current_date_obj = current_date.date()

                    # Helper function to get date object from expiry field
                    def get_expiry_date(instrument):
                        expiry = instrument['expiry']
                        if isinstance(expiry, str):
                            return datetime.strptime(expiry, '%Y-%m-%d').date()
                        elif isinstance(expiry, date) and not isinstance(expiry, datetime):
                            return expiry
                        elif isinstance(expiry, datetime):
                            return expiry.date()
                        elif hasattr(expiry, 'date'):
                            return expiry.date()
                        else:
                            # Fallback - try to parse as string
                            return datetime.strptime(str(expiry), '%Y-%m-%d').date()

                    # Log all available expiries for transparency
                    logger.info(f"📅 Found {len(candidates)} expiry candidates:")
                    for i, c in enumerate(sorted(candidates, key=lambda x: x['expiry'])[:5]):  # Show first 5
                        logger.info(f"   {i+1}. {c['tradingsymbol']} - {c['expiry']}")

                    # Strategy 1: Prefer nearest future expiry (avoid same-day expiry)
                    future_candidates = [c for c in candidates if get_expiry_date(c) > current_date_obj]

                    if future_candidates:
                        # Sort by expiry date and pick the nearest
                        future_candidates.sort(key=lambda x: get_expiry_date(x))
                        index_instrument = future_candidates[0]
                        logger.info(f"✅ Found nearest future expiry: {index_instrument['tradingsymbol']} (expiry: {index_instrument['expiry']})")
                    else:
                        # Strategy 2: Only use current expiry (same day) if no future expiry available
                        current_expiry_candidates = [c for c in candidates if get_expiry_date(c) == current_date_obj]
                        if current_expiry_candidates:
                            index_instrument = current_expiry_candidates[0]
                            logger.info(f"⚠️ Using current expiry (same day): {index_instrument['tradingsymbol']} (expiry: {index_instrument['expiry']})")
                        else:
                            # Strategy 3: Use most recent past expiry (for after-hours or holidays)
                            past_candidates = [c for c in candidates if get_expiry_date(c) < current_date_obj]
                            if past_candidates:
                                # Sort by expiry date descending and pick the most recent
                                past_candidates.sort(key=lambda x: get_expiry_date(x), reverse=True)
                                index_instrument = past_candidates[0]
                                logger.info(f"✅ Found most recent past expiry: {index_instrument['tradingsymbol']} (expiry: {index_instrument['expiry']})")
                            else:
                                # Strategy 4: Fallback to any available candidate
                                index_instrument = candidates[0]
                                logger.info(f"✅ Found fallback match: {index_instrument['tradingsymbol']} ({index_instrument['instrument_type']})")

            # Try alternative names for common indices
            if not index_instrument:
                logger.info(f"🔄 Trying alternative names for {index_symbol}...")
                alternative_names = {
                    'BANKNIFTY': ['NIFTY BANK', 'BANK NIFTY', 'NIFTYBANK', 'NIFTY BANK', 'BANK-NIFTY'],
                    'FINNIFTY': ['FIN NIFTY', 'NIFTY FIN', 'FINANCIAL NIFTY', 'NIFTY FIN SERVICE', 'FIN-NIFTY'],
                    'MIDCPNIFTY': ['MIDCAP NIFTY', 'NIFTY MIDCAP', 'MID CAP NIFTY', 'NIFTY MIDCAP 100', 'MIDCP-NIFTY']
                }

                if index_symbol in alternative_names:
                    alt_candidates = []
                    for alt_name in alternative_names[index_symbol]:
                        for inst in instruments:
                            if (alt_name.lower() in inst['tradingsymbol'].lower() and
                                inst['instrument_type'] == 'FUT'):
                                alt_candidates.append(inst)

                    # If we have alternative candidates, use enhanced expiry selection
                    if alt_candidates:
                        # Log alternative candidates
                        logger.info(f"📅 Found {len(alt_candidates)} alternative name candidates:")
                        for i, c in enumerate(sorted(alt_candidates, key=lambda x: get_expiry_date(c))[:3]):
                            logger.info(f"   {i+1}. {c['tradingsymbol']} - {c['expiry']}")

                        # Apply same intelligent expiry selection strategy (prefer future expiry)
                        future_alt_candidates = [c for c in alt_candidates if get_expiry_date(c) > current_date_obj]
                        if future_alt_candidates:
                            future_alt_candidates.sort(key=lambda x: get_expiry_date(x))
                            index_instrument = future_alt_candidates[0]
                            logger.info(f"✅ Found nearest future expiry with alternative name: {index_instrument['tradingsymbol']} (expiry: {index_instrument['expiry']})")
                        else:
                            current_alt_candidates = [c for c in alt_candidates if get_expiry_date(c) == current_date_obj]
                            if current_alt_candidates:
                                index_instrument = current_alt_candidates[0]
                                logger.info(f"⚠️ Using current expiry with alternative name: {index_instrument['tradingsymbol']} (expiry: {index_instrument['expiry']})")
                            else:
                                past_alt_candidates = [c for c in alt_candidates if get_expiry_date(c) < current_date_obj]
                                if past_alt_candidates:
                                    past_alt_candidates.sort(key=lambda x: get_expiry_date(x), reverse=True)
                                    index_instrument = past_alt_candidates[0]
                                    logger.info(f"✅ Found recent past expiry with alternative name: {index_instrument['tradingsymbol']} (expiry: {index_instrument['expiry']})")
                                else:
                                    index_instrument = alt_candidates[0]
                                    logger.info(f"✅ Found with alternative name: {index_instrument['tradingsymbol']} ({index_instrument['instrument_type']})")

            # If still not found, try to find futures contracts with nearest expiry
            if not index_instrument:
                logger.info(f"🔄 Looking for futures contracts for {index_symbol}...")
                final_candidates = []
                for inst in instruments:
                    if (index_symbol in inst['tradingsymbol'] and
                        inst['instrument_type'] == 'FUT'):
                        final_candidates.append(inst)

                # If we have final candidates, use enhanced expiry selection
                if final_candidates:
                    current_date_str = datetime.now().strftime('%Y-%m-%d')

                    # Log final candidates
                    logger.info(f"📅 Found {len(final_candidates)} final candidates:")
                    for i, c in enumerate(sorted(final_candidates, key=lambda x: x['expiry'])[:3]):
                        logger.info(f"   {i+1}. {c['tradingsymbol']} - {c['expiry']}")

                    # Apply comprehensive expiry selection strategy (prefer future expiry)
                    current_date_obj = datetime.strptime(current_date_str, '%Y-%m-%d').date()
                    future_final_candidates = [c for c in final_candidates if get_expiry_date(c) > current_date_obj]
                    if future_final_candidates:
                        future_final_candidates.sort(key=lambda x: get_expiry_date(x))
                        index_instrument = future_final_candidates[0]
                        logger.info(f"✅ Found nearest future expiry futures: {index_instrument['tradingsymbol']} (expiry: {index_instrument['expiry']})")
                    else:
                        current_final_candidates = [c for c in final_candidates if get_expiry_date(c) == current_date_obj]
                        if current_final_candidates:
                            index_instrument = current_final_candidates[0]
                            logger.info(f"⚠️ Using current expiry futures: {index_instrument['tradingsymbol']} (expiry: {index_instrument['expiry']})")
                        else:
                            past_final_candidates = [c for c in final_candidates if get_expiry_date(c) < current_date_obj]
                            if past_final_candidates:
                                past_final_candidates.sort(key=lambda x: get_expiry_date(x), reverse=True)
                                index_instrument = past_final_candidates[0]
                                logger.info(f"✅ Found recent past expiry futures: {index_instrument['tradingsymbol']} (expiry: {index_instrument['expiry']})")
                            else:
                                index_instrument = final_candidates[0]
                                logger.info(f"✅ Found futures contract: {index_instrument['tradingsymbol']} ({index_instrument['instrument_type']})")

            # Debug: Show available instruments if not found
            if not index_instrument:
                logger.warning(f"❌ Index {index_symbol} not found in NFO instruments")
                logger.info("Available index instruments in NFO:")
                index_instruments = []
                for inst in instruments:
                    if inst['instrument_type'] == 'FUT':
                        logger.info(f"  - {inst['tradingsymbol']} ({inst['instrument_type']})")
                        index_instruments.append(inst['tradingsymbol'])

                # Try to find similar instruments
                logger.info(f"🔍 Searching for similar instruments to {index_symbol}...")
                for inst in instruments:
                    if (index_symbol.lower() in inst['tradingsymbol'].lower() and
                        inst['instrument_type'] == 'FUT'):
                        logger.info(f"  - Found similar: {inst['tradingsymbol']} ({inst['instrument_type']})")
                        index_instrument = inst
                        break

                if not index_instrument:
                    logger.error(f"❌ Index {index_symbol} not found in NFO instruments")
                    available_indices = list(self.get_available_indices().keys())
                    logger.error(f"❌ Only available NFO indices are supported: {available_indices}")
                    return None

            # Get current market data for the index
            spot_price = self._get_index_spot_price(index_instrument)
            if spot_price is None:
                logger.error(f"❌ Unable to determine spot price for {index_symbol}. Skipping option chain build to avoid stale data.")
                return None

            # Create option chain with real spot price
            available_indices = self.get_available_indices()
            index_info = available_indices.get(index_symbol)
            if not index_info:
                logger.error(f"Index {index_symbol} not found in available indices: {list(available_indices.keys())}")
                return None

            # First check what option instruments we have for this index
            all_index_options = [inst for inst in instruments
                               if inst['name'] == index_symbol and
                               inst['instrument_type'] in ['CE', 'PE']]

            logger.info(f"📊 Total {index_symbol} options available in NFO: {len(all_index_options)}")

            if not all_index_options:
                logger.error(f"❌ No option instruments found for {index_symbol}")
                return None

            # Get available expiries and use the nearest one if not specified
            available_expiries = sorted(list(set(inst['expiry'] for inst in all_index_options)))
            logger.info(f"📅 Available expiry dates: {[exp.strftime('%Y-%m-%d') for exp in available_expiries[:5]]}...")

            # Select expiry date
            if expiry_date:
                target_expiry = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                if target_expiry not in [exp.date() if hasattr(exp, 'date') else exp for exp in available_expiries]:
                    logger.warning(f"⚠️ Requested expiry {expiry_date} not available, using next future expiry")
                    # Filter out same-day expiries and select next future expiry
                    current_date = datetime.now().date()
                    future_expiries = [exp for exp in available_expiries
                                     if (exp.date() if hasattr(exp, 'date') else exp) > current_date]
                    if future_expiries:
                        selected_expiry = min(future_expiries)
                        logger.info(f"✅ Selected next future expiry: {selected_expiry}")
                    else:
                        logger.warning("⚠️ No future expiries available, using nearest expiry")
                        selected_expiry = min(available_expiries)
                else:
                    selected_expiry = target_expiry
            else:
                # Avoid same-day expiry, use next future expiry
                current_date = datetime.now().date()
                future_expiries = [exp for exp in available_expiries
                                 if (exp.date() if hasattr(exp, 'date') else exp) > current_date]

                if future_expiries:
                    selected_expiry = min(future_expiries)
                    logger.info(f"✅ Avoiding same-day expiry, selected: {selected_expiry}")
                else:
                    # If no future expiries (unlikely), use the nearest available
                    selected_expiry = min(available_expiries)
                    logger.warning(f"⚠️ No future expiries available, using: {selected_expiry}")

            selected_expiry_str = selected_expiry.strftime('%Y-%m-%d') if hasattr(selected_expiry, 'strftime') else str(selected_expiry)
            logger.info(f"🎯 Selected expiry: {selected_expiry_str}")

            # Create option chain with selected expiry
            chain = OptionChain(index_symbol, selected_expiry_str, index_info.lot_size)
            chain.spot_price = spot_price

            # Filter options by selected expiry (ensure consistent date comparison)
            selected_expiry_date = selected_expiry.date() if hasattr(selected_expiry, 'date') else selected_expiry
            option_instruments = [inst for inst in all_index_options
                                if get_expiry_date(inst) == selected_expiry_date]
            logger.info(f"🔍 Found {len(option_instruments)} options for expiry {selected_expiry_str}")

            if not option_instruments:
                logger.warning(
                    f"⚠️ No options matched selected expiry {selected_expiry_str}; "
                    "falling back to all available contracts"
                )
                option_instruments = all_index_options

            # Create option contracts from real instruments (limit to prevent timeout)
            max_options = 150  # Reasonable limit for performance
            limited_instruments = option_instruments[:max_options]
            logger.info(f"📈 Creating option chain for {index_symbol}: {len(limited_instruments)}/{len(option_instruments)} options (performance limited)")

            parsed_count = 0
            live_data_count = 0
            start_time = time.time()
            timeout_seconds = 30  # 30 second timeout
            quote_batch: List[tuple[OptionContract, Dict]] = []
            batch_size = 40

            for inst in limited_instruments:
                # Check timeout
                if time.time() - start_time > timeout_seconds:
                    logger.warning(f"⏰ Option processing timeout after {timeout_seconds}s, stopping at {parsed_count} options")
                    break
                try:
                    option = self._parse_option_instrument(inst, index_symbol, selected_expiry_str, index_info.lot_size)
                    if option:
                        parsed_count += 1
                        quote_batch.append((option, inst))
                        if len(quote_batch) >= batch_size:
                            live_data_count += self._process_option_quote_batch(quote_batch)
                            quote_batch.clear()
                        chain.add_option(option)

                        # Progress update every 50 options
                        if parsed_count % 50 == 0:
                            logger.info(f"📊 Progress: {parsed_count} options processed...")

                except Exception as e:
                    logger.debug(f"Error processing option {inst['tradingsymbol']}: {e}")
                    continue

            if quote_batch:
                live_data_count += self._process_option_quote_batch(quote_batch)
                quote_batch.clear()

            logger.info(f"📊 Final results: {parsed_count} parsed, {live_data_count} with live data")

            if not chain.calls and not chain.puts:
                logger.error(f"❌ No valid options found for {index_symbol}")
                return None

            # If we have some options but not many, supplement with mock data
            total_options = len(chain.calls) + len(chain.puts)
            if total_options < 20:
                logger.warning(f"⚠️ Only {total_options} live options found - this may limit strategy options")
                logger.info("💡 Consider using a more active index or different expiry date")

            logger.info(f"✅ Created option chain: {len(chain.calls)} calls, {len(chain.puts)} puts")
            return chain

        except Exception as e:
            # Check if it's a market hours issue
            market_hours = MarketHoursManager()
            is_open, market_status = market_hours.can_trade()

            if not is_open:
                logger.info(f"ℹ️  Cannot fetch option chain for {index_symbol}: {market_status}")
                logger.info("💡 Market hours: Monday-Friday, 9:15 AM - 3:30 PM IST")
                logger.info(f"⏰ Current time: {datetime.now().strftime('%I:%M %p IST')}")
            else:
                logger.error(f"❌ Error fetching option chain for {index_symbol}: {e}")
                logger.error("❌ Cannot proceed without real market data - check API permissions")
            return None

    def _get_kite_spot_price(self, index_symbol: str) -> float:
        """Get spot price from Kite API only, no external fallbacks"""
        try:
            # Symbol mapping for correct index names (NSE and BSE)
            symbol_mapping = {
                # NSE Indices
                'NIFTY': 'NIFTY 50',
                'BANKNIFTY': 'NIFTY BANK',
                'FINNIFTY': 'NIFTY FIN SERVICE',
                'MIDCPNIFTY': 'NIFTY MIDCAP 100',
                # BSE Indices
                'SENSEX': 'BSE SENSEX',
                'BANKEX': 'BSE BANKEX'
            }

            # Determine exchange based on index
            bse_indices = ['SENSEX', 'BANKEX']
            exchange = 'BSE' if index_symbol in bse_indices else 'NSE'

            # Get the correct symbol
            mapped_symbol = symbol_mapping.get(index_symbol, index_symbol)

            # Find spot index instrument in Kite instruments
            instruments = self._get_instruments_cached(exchange)

            for inst in instruments:
                if (inst['name'] == mapped_symbol or
                    inst['tradingsymbol'] == mapped_symbol):

                    quote_symbol = f"{inst['exchange']}:{inst['tradingsymbol']}"
                    logger.debug(f"🔍 Fetching quote for {quote_symbol}")

                    quote = self._fetch_quote_with_retry([quote_symbol], 'spot_quote')
                    if quote and quote_symbol in quote:
                        spot_price = quote[quote_symbol]['last_price']
                        logger.info(f"✅ Got live spot price from Kite: {spot_price} for {index_symbol} -> {mapped_symbol}")
                        return spot_price

            # Try futures price as spot proxy
            futures_instruments = self._get_instruments_cached("NFO")
            for inst in futures_instruments:
                if (inst['name'] == index_symbol and
                    inst['instrument_type'] == 'FUT' and
                    inst['tradingsymbol'].startswith(index_symbol)):

                    quote_symbol = f"{inst['exchange']}:{inst['tradingsymbol']}"
                    logger.debug(f"🔍 Fetching futures quote for {quote_symbol}")

                    quote = self._fetch_quote_with_retry([quote_symbol], 'futures_quote')
                    if quote and quote_symbol in quote:
                        spot_price = quote[quote_symbol]['last_price']
                        logger.info(f"✅ Got spot price from futures: {spot_price} for {index_symbol}")
                        return spot_price

            # If no live data available, check if market is open
            market_hours = MarketHoursManager()
            is_open, market_status = market_hours.can_trade()

            if not is_open:
                logger.info(f"ℹ️  No live data for {index_symbol} - {market_status}")
            else:
                logger.warning(f"❌ No live spot price available for {index_symbol} (Market is open but no data)")
            return None

        except Exception as e:
            logger.warning(f"❌ Failed to get live spot price for {index_symbol}: {e}")
            return None

    def _get_index_spot_price(self, index_instrument: Dict) -> float:
        """Get current spot price for index instrument using only Kite API"""
        try:
            quote_symbol = f"{index_instrument['exchange']}:{index_instrument['tradingsymbol']}"
            logger.debug(f"🔍 Fetching quote for {quote_symbol}")

            quote = self._fetch_quote_with_retry([quote_symbol], 'index_spot')
            if quote and quote_symbol in quote:
                spot_price = quote[quote_symbol]['last_price']
                logger.info(f"✅ Got live spot price from instrument: {spot_price}")
                return spot_price

            # If direct quote failed, try to get from spot index
            clean_symbol = self._extract_index_from_futures(index_instrument['tradingsymbol'])
            spot_price = self._get_kite_spot_price(clean_symbol)

            if spot_price is not None:
                return spot_price

            # If no live data available, check if market is open before raising error
            market_hours = MarketHoursManager()
            is_open, market_status = market_hours.can_trade()

            if not is_open:
                logger.info(f"ℹ️  Market closed: {market_status}")
                logger.info(f"💡 No live data for {index_instrument['tradingsymbol']} - wait for market hours (9:15 AM - 3:30 PM IST)")
                return None
            else:
                logger.error(f"❌ No live data available for {index_instrument['tradingsymbol']}")
                logger.error("❌ Cannot proceed without Kite API data - check API permissions")
                return None

        except Exception as e:
            logger.error(f"❌ Failed to get spot price for {index_instrument['tradingsymbol']}: {e}")
            return None

    def _extract_index_from_futures(self, trading_symbol: str) -> str:
        """Extract clean index symbol from futures trading symbol"""
        # Remove common futures suffixes like 25SEPFUT, 25OCTFUT, etc.
        for index in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']:
            if trading_symbol.startswith(index):
                return index
        # Default fallback
        return 'NIFTY'

    def _parse_option_instrument(self, inst: Dict, index_symbol: str, expiry_date: str, lot_size: int) -> Optional[OptionContract]:
        """Create an OptionContract from live instrument metadata"""
        try:
            symbol = inst.get('tradingsymbol')
            if not symbol:
                return None

            option_type = inst.get('instrument_type')
            if option_type not in ('CE', 'PE'):
                # Fallback to detecting from trading symbol suffix
                if symbol.endswith('CE'):
                    option_type = 'CE'
                elif symbol.endswith('PE'):
                    option_type = 'PE'
                else:
                    return None

            strike_price = inst.get('strike')
            if strike_price is None or strike_price <= 0:
                # Fallback: extract trailing digits as strike if master data missing
                match = re.search(r'(\d+)$', symbol[:-2] if symbol.endswith(('CE', 'PE')) else symbol)
                if not match:
                    logger.debug(f"Failed to extract strike for {symbol}")
                    return None
                strike_price = float(match.group(1))

            option = OptionContract(symbol, float(strike_price), expiry_date, option_type, index_symbol, lot_size)

            last_price = inst.get('last_price')
            if isinstance(last_price, (int, float)) and last_price > 0:
                option.last_price = float(last_price)

            # Seed greeks with placeholder metrics until live data refreshes
            time_to_expiry = 7 / 365  # Assume 7 days to expiry
            volatility = 25.0  # Mock volatility
            option.calculate_greeks(option.last_price, time_to_expiry, volatility)
            option.calculate_moneyness(option.last_price)
            option.update_intrinsic_value(option.last_price)

            return option

        except Exception as e:
            logger.debug(f"Error parsing option {inst.get('tradingsymbol', 'UNKNOWN')}: {e}")
            return None

    def _process_option_quote_batch(self, batch: List[tuple[OptionContract, Dict]]) -> int:
        """Fetch live data for a batch of options"""
        if not batch:
            return 0

        symbols: Dict[str, tuple[OptionContract, Dict]] = {}
        for option, inst in batch:
            try:
                quote_symbol = f"{inst['exchange']}:{inst['tradingsymbol']}"
                symbols[quote_symbol] = (option, inst)
            except KeyError:
                continue

        if not symbols:
            return 0

        quotes = self._fetch_quote_with_retry(list(symbols.keys()), 'option_quote', max_attempts=3)
        updates = 0
        if not quotes:
            return updates

        for quote_symbol, data in quotes.items():
            mapping = symbols.get(quote_symbol)
            if not mapping:
                continue
            option, _ = mapping
            if self._apply_option_quote(option, data):
                updates += 1
        return updates

    def _apply_option_quote(self, option: OptionContract, data: Dict[str, Any]) -> bool:
        """Apply quote payload to option contract"""
        old_price = option.last_price
        option.last_price = data.get('last_price', option.last_price)
        option.open_interest = data.get('oi', option.open_interest)
        option.volume = data.get('volume', option.volume)
        option.implied_volatility = data.get('implied_volatility', option.implied_volatility)

        if option.last_price and option.last_price > 0 and option.last_price != old_price:
            logger.debug(
                "✅ Updated %s: price=₹%.2f, OI=%s",
                option.symbol,
                option.last_price,
                option.open_interest
            )
            return True
        return False

    def _update_option_with_live_data(self, option: OptionContract, inst: Dict):
        """Legacy single-option updater (uses batch helper under the hood)."""
        quote_symbol = f"{inst['exchange']}:{inst['tradingsymbol']}"
        quotes = self._fetch_quote_with_retry([quote_symbol], 'option_quote', max_attempts=2)
        if quotes and quote_symbol in quotes:
            return self._apply_option_quote(option, quotes[quote_symbol])
        return False


    def _get_next_expiry_date(self) -> str:
        """Get the next available expiry date dynamically"""
        try:
            from datetime import datetime, timedelta

            # Get current date
            today = datetime.now().date()

            # For options, typically we want the next Thursday (weekly expiry)
            # or last Thursday of the month (monthly expiry)

            # Find next Thursday
            days_until_thursday = (3 - today.weekday()) % 7  # 3 = Thursday
            if days_until_thursday == 0:
                days_until_thursday = 7  # If today is Thursday, get next Thursday

            next_thursday = today + timedelta(days=days_until_thursday)

            # If next Thursday is more than 5 days away, it might be better to use
            # the last Thursday of current month for monthly expiry
            if days_until_thursday > 5:
                # Calculate last Thursday of current month
                next_month = today.replace(day=28) + timedelta(days=4)  # Go to next month
                last_day = next_month.replace(day=1) - timedelta(days=1)  # Last day of current month

                # Find last Thursday of current month
                days_from_end = (last_day.weekday() - 3) % 7
                if days_from_end == 0:
                    days_from_end = 7
                last_thursday = last_day - timedelta(days=days_from_end)

                # Use monthly expiry if it's in the future and not too far
                if last_thursday > today and (last_thursday - today).days <= 28:
                    return last_thursday.strftime('%Y-%m-%d')

            return next_thursday.strftime('%Y-%m-%d')

        except Exception as e:
            logger.error(f"Error calculating next expiry date: {e}")
            # Fallback to a reasonable future date
            fallback_date = datetime.now().date() + timedelta(days=7)
            return fallback_date.strftime('%Y-%m-%d')

    def _create_mock_option_chain(self, index_symbol: str, _expiry_date: str, _spot_price: float = None) -> OptionChain:
        """Mock option chain creation is disabled - system uses only live Kite data"""
        logger.error(f"❌ Mock option chain disabled for {index_symbol} - only live Kite data allowed")
        return None

    def _calculate_atm_premium(self, spot_price: float, volatility: float, time_to_expiry: float, risk_free_rate: float) -> float:
        """Calculate ATM option premium using simplified Black-Scholes without SciPy"""
        try:
            S = float(spot_price)
            T = float(time_to_expiry)
            r = float(risk_free_rate)
            sigma = float(volatility) / 100.0

            if T <= 0 or sigma <= 0:
                return 0.0

            def _norm_cdf(x: float) -> float:
                return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

            d1 = (0.0 + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)

            # ATM call and put premiums are approximately equal
            call_premium = S * _norm_cdf(d1) - S * math.exp(-r * T) * _norm_cdf(d2)
            put_premium = S * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)

            return max(0.0, (call_premium + put_premium) / 2.0)

        except Exception:
            # Fallback calculation
            return max(0.0, spot_price * (volatility / 100.0) * math.sqrt(max(time_to_expiry, 1e-9)))

    def _calculate_option_premium(self, spot_price: float, strike_price: float, time_to_expiry: float,
                                 volatility: float, risk_free_rate: float, option_type: str, index_symbol: str) -> float:
        """Calculate realistic option premium with moneyness adjustments without SciPy"""
        try:
            S = float(spot_price)
            K = float(strike_price)
            T = float(time_to_expiry)
            r = float(risk_free_rate)
            sigma = float(volatility) / 100.0

            if T <= 0 or sigma <= 0:
                return max(0.0, S - K) if option_type == 'CE' else max(0.0, K - S)

            def _norm_cdf(x: float) -> float:
                return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

            d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)

            if option_type == 'CE':
                premium = S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
            else:
                premium = K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)

            # Add realistic minimum premiums based on index
            min_premium = {
                'NIFTY': 10.0,
                'BANKNIFTY': 50.0,
                'FINNIFTY': 20.0,
                'MIDCPNIFTY': 15.0
            }.get(index_symbol, 10.0)

            # Apply volatility smile (higher IV for OTM options)
            moneyness = (S - K) / S if option_type == 'CE' else (K - S) / S
            if abs(moneyness) > 0.05:  # OTM options
                premium *= 1.2  # 20% premium for OTM options
            elif abs(moneyness) < 0.02:  # ATM options
                premium *= 1.1  # 10% premium for ATM options

            return max(min_premium, premium)

        except Exception as e:
            logger.debug(f"Error calculating premium: {e}")
            # Fallback: simple time value calculation
            intrinsic = max(0.0, spot_price - strike_price) if option_type == 'CE' else max(0.0, strike_price - spot_price)
            time_value = spot_price * (volatility / 100.0) * math.sqrt(max(time_to_expiry, 1e-9)) * random.uniform(0.8, 1.2)
            return max(0.05, intrinsic + time_value)
