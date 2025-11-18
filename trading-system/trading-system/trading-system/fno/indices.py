#!/usr/bin/env python3
"""
FNO Index Management
Index characteristics, configuration, and selection
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger('trading_system.fno.indices')


class IndexCharacteristics:
    """Index-specific characteristics for optimized trading"""

    def __init__(self, symbol: str, point_value: float, avg_daily_move: int,
                 volatility: str, atr_multiplier: float, priority: int):
        self.symbol = symbol
        self.point_value = point_value  # ₹ per point
        self.avg_daily_move = avg_daily_move  # Average point move per day
        self.volatility = volatility  # 'low', 'moderate', 'high', 'very_high'
        self.atr_multiplier = atr_multiplier  # ATR multiplier for stop-loss
        self.priority = priority  # Priority for ₹5-10k profit system (1=best, 6=worst)

    def points_needed_for_profit(self, target_profit: float, lot_size: int) -> float:
        """Calculate points needed to achieve target profit"""
        return target_profit / (self.point_value * lot_size)

    def achievable_in_timeframe(self, points_needed: float) -> str:
        """Estimate time to achieve given point move"""
        if points_needed <= self.avg_daily_move * 0.3:
            return "1-3 hours"
        elif points_needed <= self.avg_daily_move * 0.5:
            return "3-5 hours"
        elif points_needed <= self.avg_daily_move:
            return "Full day"
        else:
            return "Multiple days"

class IndexConfig:
    """Configuration for all supported indices based on market research"""

    # Index characteristics based on research findings
    CHARACTERISTICS = {
        'MIDCPNIFTY': IndexCharacteristics(
            symbol='MIDCPNIFTY',
            point_value=75,  # Highest!
            avg_daily_move=200,
            volatility='very_high',
            atr_multiplier=1.2,  # Tighter stop due to high volatility
            priority=1  # Best for ₹5-10k strategy
        ),
        'NIFTY': IndexCharacteristics(
            symbol='NIFTY',
            point_value=50,
            avg_daily_move=115,
            volatility='moderate',
            atr_multiplier=1.5,  # Standard
            priority=2  # Second best, most stable
        ),
        'FINNIFTY': IndexCharacteristics(
            symbol='FINNIFTY',
            point_value=40,
            avg_daily_move=175,
            volatility='moderate_high',
            atr_multiplier=1.4,
            priority=3  # Good alternative
        ),
        'BANKNIFTY': IndexCharacteristics(
            symbol='BANKNIFTY',
            point_value=15,
            avg_daily_move=350,
            volatility='very_high',
            atr_multiplier=2.0,  # Wider stop for high volatility
            priority=4  # Harder to achieve consistent ₹5-10k
        ),
        'BANKEX': IndexCharacteristics(
            symbol='BANKEX',
            point_value=15,
            avg_daily_move=275,
            volatility='high',
            atr_multiplier=2.0,
            priority=5  # Similar to Bank NIFTY
        ),
        'SENSEX': IndexCharacteristics(
            symbol='SENSEX',
            point_value=10,  # Lowest point value
            avg_daily_move=150,
            volatility='moderate',
            atr_multiplier=1.5,
            priority=6  # Not recommended for ₹5-10k strategy
        ),
    }

    # High correlation pairs - NEVER trade together
    HIGH_CORRELATION_PAIRS = [
        ('NIFTY', 'SENSEX'),  # 95% correlation
        ('BANKNIFTY', 'BANKEX'),  # 95% correlation
    ]

    # Medium correlation groups - Trade cautiously
    MEDIUM_CORRELATION_GROUPS = [
        ['NIFTY', 'BANKNIFTY', 'FINNIFTY'],
        ['SENSEX', 'BANKEX'],
    ]

    @classmethod
    def get_characteristics(cls, symbol: str) -> Optional[IndexCharacteristics]:
        """Get characteristics for an index symbol"""
        return cls.CHARACTERISTICS.get(symbol.upper())

    @classmethod
    def get_prioritized_indices(cls) -> List[str]:
        """Get indices sorted by priority for ₹5-10k strategy"""
        sorted_indices = sorted(
            cls.CHARACTERISTICS.items(),
            key=lambda x: x[1].priority
        )
        return [symbol for symbol, _ in sorted_indices]

    @classmethod
    def check_correlation_conflict(cls, existing_symbols: List[str], new_symbol: str) -> Tuple[bool, str]:
        """Check if new symbol conflicts with existing positions"""
        new_symbol = new_symbol.upper()
        existing_upper = [s.upper() for s in existing_symbols]

        # Check high correlation pairs
        for pair in cls.HIGH_CORRELATION_PAIRS:
            if new_symbol in pair:
                other = pair[0] if pair[1] == new_symbol else pair[1]
                if other in existing_upper:
                    return True, f"⚠️ HIGH CORRELATION: {new_symbol} has 95% correlation with {other} (already in portfolio)"

        # Check medium correlation groups
        for group in cls.MEDIUM_CORRELATION_GROUPS:
            if new_symbol in group:
                conflicts = [s for s in group if s in existing_upper and s != new_symbol]
                if len(conflicts) >= 2:  # Already have 2+ from same group
                    return True, f"⚠️ MEDIUM CORRELATION: {new_symbol} correlates with {', '.join(conflicts)} (excessive correlation)"

        return False, ""

    @classmethod
    def calculate_profit_target_points(cls, symbol: str, lot_size: int,
                                       target_profit: float) -> Optional[float]:
        """Calculate points needed for target profit"""
        char = cls.get_characteristics(symbol)
        if not char:
            return None
        return char.points_needed_for_profit(target_profit, lot_size)

class FNOIndex:
    """Represents a major index for F&O trading"""

    def __init__(self, symbol: str, name: str, lot_size: int, tick_size: float = 0.05):
        self.symbol = symbol
        self.name = name
        self.lot_size = lot_size
        self.tick_size = tick_size

        # Get index-specific characteristics
        self.characteristics = IndexConfig.get_characteristics(symbol)

    def __str__(self):
        return f"{self.symbol} ({self.name}) - Lot Size: {self.lot_size}"

    def get_profit_target_points(self, target_profit: float) -> Optional[float]:
        """Calculate points needed for target profit"""
        if not self.characteristics:
            return None
        return self.characteristics.points_needed_for_profit(target_profit, self.lot_size)

# Dynamic F&O Indices Discovery
class DynamicFNOIndices:
    """Dynamically discovers available F&O indices from Kite API"""

    def __init__(self, kite_connection=None):
        self.kite = kite_connection
        self._indices_cache = {}
        self._cache_timestamp = None
        self.cache_duration = 3600  # Cache for 1 hour

    def get_available_indices(self) -> Dict[str, FNOIndex]:
        """Get all available F&O indices from both NSE and BSE via Kite API"""
        from datetime import datetime, timedelta

        # Check if cache is valid
        if (self._cache_timestamp and
            datetime.now() - self._cache_timestamp < timedelta(seconds=self.cache_duration) and
            self._indices_cache):
            return self._indices_cache

        if not self.kite:
            logger.warning("❌ No Kite connection available for dynamic index discovery")
            return self._get_fallback_indices()

        try:
            # Get instruments from NSE F&O (NFO) - primary F&O exchange
            logger.info("🔄 Fetching live instruments from NSE F&O (NFO)...")
            nse_instruments = self.kite.instruments("NFO")  # NSE F&O
            all_instruments = nse_instruments
            logger.info(f"✅ Retrieved {len(nse_instruments)} NSE F&O instruments")

            # Try to get BSE F&O instruments if available (BFO)
            bse_instruments = []
            try:
                bse_instruments = self.kite.instruments("BFO")  # BSE F&O
                if bse_instruments:
                    all_instruments.extend(bse_instruments)
                    logger.info(f"✅ Retrieved {len(bse_instruments)} BSE F&O instruments")
                else:
                    logger.info("ℹ️ No BSE F&O instruments available")
            except Exception as e:
                logger.info(f"ℹ️ BSE F&O not accessible: {e}")

            # Try to get Commodity instruments if available (MCX)
            mcx_instruments = []
            try:
                mcx_instruments = self.kite.instruments("MCX")  # MCX Commodities
                if mcx_instruments:
                    # Filter for F&O instruments only
                    mcx_fo = [inst for inst in mcx_instruments if inst.get('instrument_type') in ['FUT', 'CE', 'PE']]
                    if mcx_fo:
                        all_instruments.extend(mcx_fo)
                        logger.info(f"✅ Retrieved {len(mcx_fo)} MCX F&O instruments")
            except Exception as e:
                logger.info(f"ℹ️ MCX instruments not accessible: {e}")

            logger.info(f"✅ Total F&O instruments: {len(all_instruments)} (NSE: {len(nse_instruments)}, BSE: {len(bse_instruments)}, MCX: {len(mcx_instruments)})")

            discovered_indices = {}

            # Analyze instruments to find index patterns
            index_patterns = {}

            for inst in all_instruments:
                if inst['instrument_type'] == 'FUT':
                    symbol = inst['tradingsymbol']
                    exchange = inst.get('exchange', 'NSE')

                    # Extract index name patterns
                    index_name = self._extract_index_name(symbol)
                    if index_name:
                        # Use exchange-specific key to avoid conflicts
                        key = f"{index_name}_{exchange}"
                        if key not in index_patterns:
                            index_patterns[key] = {
                                'index_name': index_name,
                                'exchange': exchange,
                                'count': 0,
                                'sample_instrument': inst,
                                'lot_size': inst.get('lot_size', 50)
                            }
                        index_patterns[key]['count'] += 1

            # Filter to get main indices (those with multiple expiries)
            for key, data in index_patterns.items():
                if data['count'] >= 2:  # At least 2 expiries = active index
                    index_name = data['index_name']
                    exchange = data['exchange']
                    display_name = self._get_display_name(index_name)
                    lot_size = data['lot_size']

                    # Use clean index name as key (prefer NSE, then BSE if NSE not available)
                    if index_name not in discovered_indices:
                        discovered_indices[index_name] = FNOIndex(
                            symbol=index_name,
                            name=f"{display_name} ({exchange})",
                            lot_size=lot_size
                        )
                        logger.info(f"✅ Discovered {exchange} index: {index_name} (Lot: {lot_size})")
                    elif exchange == 'NSE' and 'BSE' in discovered_indices[index_name].name:
                        # Prefer NSE over BSE if both available
                        discovered_indices[index_name] = FNOIndex(
                            symbol=index_name,
                            name=f"{display_name} (NSE)",
                            lot_size=lot_size
                        )

            # Filter indices for profit potential BEFORE returning
            profitable_indices = self._filter_profitable_indices(discovered_indices)

            logger.info(f"✅ Discovered {len(discovered_indices)} total F&O indices")
            logger.info(f"🎯 Selected {len(profitable_indices)} high-profit potential indices: {list(profitable_indices.keys())}")

            # Cache the filtered results
            self._indices_cache = profitable_indices
            self._cache_timestamp = datetime.now()

            return profitable_indices

        except Exception as e:
            logger.error(f"❌ Error discovering indices from Kite API: {e}")
            return self._get_fallback_indices()

    def _filter_profitable_indices(self, all_indices: Dict[str, FNOIndex]) -> Dict[str, FNOIndex]:
        """Filter indices to only those with high profit potential"""
        logger.info("🔍 Filtering indices for profit potential...")

        profitable_indices = {}
        profit_criteria = {
            # High priority indices (proven profit potential)
            'tier1': ['NIFTY', 'BANKNIFTY'],
            # Medium priority indices (good liquidity and volatility)
            'tier2': ['FINNIFTY', 'MIDCPNIFTY', 'SENSEX', 'BANKEX'],
            # Lower priority indices (trade only if exceptional signals)
            'tier3': ['NIFTYIT']
        }

        # Always include Tier 1 indices (highest profit potential)
        for index_name in profit_criteria['tier1']:
            if index_name in all_indices:
                profitable_indices[index_name] = all_indices[index_name]
                logger.info(f"✅ Tier 1 (Always): {index_name}")

        # Include Tier 2 if market conditions are favorable
        market_conditions = self._assess_market_conditions()
        if market_conditions.get('volatility_favorable', True):
            for index_name in profit_criteria['tier2']:
                if index_name in all_indices:
                    profitable_indices[index_name] = all_indices[index_name]
                    logger.info(f"✅ Tier 2 (Good conditions): {index_name}")

        # Include Tier 3 only if exceptional opportunity
        if market_conditions.get('exceptional_opportunity', False):
            for index_name in profit_criteria['tier3']:
                if index_name in all_indices:
                    profitable_indices[index_name] = all_indices[index_name]
                    logger.info(f"✅ Tier 3 (Exceptional): {index_name}")

        # Additional profit-based filtering
        filtered_indices = {}
        for index_name, index_info in profitable_indices.items():
            confidence_score = self._calculate_profit_confidence(index_name, index_info)

            if confidence_score >= 0.6:  # Only trade if 60%+ confidence
                filtered_indices[index_name] = index_info
                logger.info(f"🎯 Selected {index_name}: {confidence_score:.1%} profit confidence")
            else:
                logger.warning(f"❌ Filtered out {index_name}: {confidence_score:.1%} confidence (below 60%)")

        if not filtered_indices:
            # Fallback: at least include NIFTY and BANKNIFTY for safety
            logger.warning("⚠️ No indices passed profit filter, using safe defaults")
            for safe_index in ['NIFTY', 'BANKNIFTY']:
                if safe_index in all_indices:
                    filtered_indices[safe_index] = all_indices[safe_index]

        return filtered_indices

    def _assess_market_conditions(self) -> Dict[str, bool]:
        """Assess current market conditions for index selection"""
        try:
            current_hour = datetime.now().hour

            # Simple market condition assessment
            conditions = {
                'volatility_favorable': True,  # Default to favorable
                'exceptional_opportunity': False,  # Conservative default
                'market_hours': 9 <= current_hour <= 15,  # Market hours
                'high_volume_period': 9 <= current_hour <= 11 or 14 <= current_hour <= 15
            }

            # Add more sophisticated logic here based on:
            # - VIX levels
            # - Market trend
            # - Volume patterns
            # - Economic events

            return conditions
        except Exception as e:
            logger.warning(f"⚠️ Error assessing market conditions: {e}")
            return {'volatility_favorable': True, 'exceptional_opportunity': False}

    def _calculate_profit_confidence(self, index_name: str, index_info: FNOIndex) -> float:
        """Calculate profit confidence score for an index (0.0 to 1.0)"""
        try:
            confidence = 0.5  # Base confidence

            # Index-specific confidence adjustments
            index_confidence_map = {
                'NIFTY': 0.85,      # Highest liquidity, most predictable
                'BANKNIFTY': 0.80,  # High volatility, good for options
                'FINNIFTY': 0.70,   # Good liquidity, medium volatility
                'MIDCPNIFTY': 0.65, # Lower liquidity, higher risk
                'SENSEX': 0.62,     # BSE flagship index, moderate liquidity
                'BANKEX': 0.60,     # BSE banking index, thinner but tradable
                'NIFTYIT': 0.60     # Sector specific, variable
            }

            confidence = index_confidence_map.get(index_name, 0.5)

            # Adjust based on lot size (smaller lots = more accessible)
            if index_info.lot_size <= 25:
                confidence += 0.05
            elif index_info.lot_size >= 75:
                confidence -= 0.05

            # Adjust based on market hours
            current_hour = datetime.now().hour
            if 9 <= current_hour <= 15:  # Market hours
                confidence += 0.05
            else:
                confidence -= 0.15  # Avoid pre/post market

            # Adjust based on day of week
            weekday = datetime.now().weekday()
            if weekday in [0, 1, 2]:  # Monday, Tuesday, Wednesday - good volume
                confidence += 0.02
            elif weekday == 4:  # Friday - expiry day considerations
                confidence -= 0.03

            return max(0.0, min(1.0, confidence))  # Clamp between 0 and 1

        except Exception as e:
            logger.warning(f"⚠️ Error calculating confidence for {index_name}: {e}")
            return 0.5  # Default safe confidence

    def _extract_index_name(self, trading_symbol: str) -> Optional[str]:
        """Extract index name from futures trading symbol - supports ALL exchanges"""
        import re  # Local import ensures availability during dynamic discovery
        # List of indices that commonly have F&O contracts (realistic list)
        known_indices = [
            # NSE Major Indices (Confirmed F&O availability)
            'NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY',

            # NSE Sectoral Indices (Limited F&O availability)
            'NIFTYIT', 'NIFTYPHARMA', 'NIFTYAUTO', 'NIFTYFMCG', 'NIFTYMETAL',

            # BSE Indices (Limited availability, depends on broker)
            'SENSEX', 'BANKEX',

            # MCX Commodities (if MCX F&O access available)
            'CRUDEOIL', 'NATURALGAS', 'GOLD', 'SILVER', 'COPPER', 'ZINC',

            # Currency (CDS - if available)
            'USDINR', 'EURINR', 'GBPINR',

            # Others (rare F&O availability)
            'INDIAVIX'
        ]

        # Sort by length (longest first) to match more specific indices first
        for index in sorted(known_indices, key=len, reverse=True):
            if trading_symbol.upper().startswith(index.upper()):
                return index

        # If no direct match, extract alphabetic prefix manually
        upper_symbol = trading_symbol.upper()
        prefix_chars = []
        for ch in upper_symbol:
            if ch.isalpha():
                prefix_chars.append(ch)
            else:
                break

        potential_index = ''.join(prefix_chars)
        if len(potential_index) >= 4 and potential_index.isalpha():
            return potential_index

        return None

    def _get_display_name(self, index_symbol: str) -> str:
        """Get display name for index - supports ALL indices"""
        display_names = {
            # NSE Major Indices
            'NIFTY': 'NIFTY 50',
            'BANKNIFTY': 'Bank NIFTY',
            'FINNIFTY': 'Fin NIFTY',
            'MIDCPNIFTY': 'Midcap NIFTY',

            # NSE Sectoral Indices
            'NIFTYAUTO': 'NIFTY Auto',
            'NIFTYBANK': 'NIFTY Bank',
            'NIFTYCOMMODITIES': 'NIFTY Commodities',
            'NIFTYCONSUMPTION': 'NIFTY Consumption',
            'NIFTYCPSE': 'NIFTY CPSE',
            'NIFTYENERGY': 'NIFTY Energy',
            'NIFTYFIN': 'NIFTY Financial Services',
            'NIFTYFINSRV': 'NIFTY Financial Services',
            'NIFTYFMCG': 'NIFTY FMCG',
            'NIFTYINFRA': 'NIFTY Infrastructure',
            'NIFTYIT': 'NIFTY IT',
            'NIFTYMETAL': 'NIFTY Metal',
            'NIFTYPHARMA': 'NIFTY Pharma',
            'NIFTYPSE': 'NIFTY PSE',
            'NIFTYREALTY': 'NIFTY Realty',
            'NIFTYSERVSECTOR': 'NIFTY Service Sector',
            'NIFTYMEDIA': 'NIFTY Media',

            # BSE Major Indices
            'SENSEX': 'BSE SENSEX',
            'BANKEX': 'BSE BANKEX',

            # Commodity Indices
            'CRUDEOIL': 'Crude Oil',
            'NATURALGAS': 'Natural Gas',
            'GOLD': 'Gold',
            'SILVER': 'Silver',
            'COPPER': 'Copper',
            'ZINC': 'Zinc',
            'ALUMINIUM': 'Aluminium',
            'LEAD': 'Lead',
            'NICKEL': 'Nickel',

            # Currency
            'USDINR': 'USD-INR',
            'EURINR': 'EUR-INR',
            'GBPINR': 'GBP-INR',
            'JPYINR': 'JPY-INR',

            # Other NSE Indices
            'NIFTYNXT50': 'NIFTY Next 50',
            'CNXPHARMA': 'CNX Pharma',
            'CNXIT': 'CNX IT',
            'INDIAVIX': 'India VIX',

            # Additional sectoral
            'NIFTYPVTBANK': 'NIFTY Private Bank',
            'NIFTYMIDCAP': 'NIFTY Midcap',
            'NIFTYSMLCAP': 'NIFTY Smallcap'
        }
        return display_names.get(index_symbol.upper(), index_symbol)

    def _get_fallback_indices(self) -> Dict[str, FNOIndex]:
        """Fallback indices when API is not available - ONLY actually available F&O indices"""
        logger.warning("⚠️ Using fallback index configuration - live data unavailable")
        return {
            # NSE Major Indices (Confirmed F&O availability)
            'NIFTY': FNOIndex('NIFTY', 'NIFTY 50 (NSE)', 50),
            'BANKNIFTY': FNOIndex('BANKNIFTY', 'Bank NIFTY (NSE)', 15),
            'FINNIFTY': FNOIndex('FINNIFTY', 'Fin NIFTY (NSE)', 40),
            'MIDCPNIFTY': FNOIndex('MIDCPNIFTY', 'Midcap NIFTY (NSE)', 75),

            # NSE Sectoral Indices (Only those with confirmed F&O)
            'NIFTYIT': FNOIndex('NIFTYIT', 'NIFTY IT (NSE)', 75),

            # Note: BSE F&O (SENSEX, BANKEX) and Commodity F&O availability
            # depends on broker permissions and may not be available to all users
            # These will be dynamically discovered if available
        }

# Global instance will be initialized by FNODataProvider
DYNAMIC_FNO_INDICES = None
