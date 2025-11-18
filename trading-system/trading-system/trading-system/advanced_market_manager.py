#!/usr/bin/env python3
"""
Advanced Market Manager
Handles:
1. Market hours validation and auto-stop functionality
2. Expiry-based position closing at 3:30 PM
3. Market trend analysis for position adjustments
4. Overnight position management system
5. Market closed status display
"""

import sys
import os
import time
import json
import calendar
from datetime import datetime, timedelta, date
from pathlib import Path
import pytz
import pandas as pd
import holidays  # CRITICAL FIX: NSE holiday support
import numpy as np
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass
from enum import Enum

class MarketTrend(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"

class PositionType(Enum):
    EXPIRY = "expiry"
    OVERNIGHT = "overnight"

@dataclass
class MarketSession:
    date: str
    market_open: datetime
    market_close: datetime
    pre_close: datetime  # 3:30 PM for F&O expiry closure
    is_trading_day: bool

class AdvancedMarketManager:
    """Advanced market management with trend analysis and position handling"""

    DEFAULT_INDEX_TOKENS = {
        "NIFTY": 256265,
        "BANKNIFTY": 260105,
        "FINNIFTY": 9992609,
        "MIDCPNIFTY": 12318082,
        "SENSEX": 265  # BSE SENSEX index token
    }

    def __init__(self, config: Dict = None, kite=None, index_tokens: Optional[Dict[str, int]] = None):
        self.config = config or {}
        self.ist = pytz.timezone('Asia/Kolkata')
        self.kite = kite
        self.logger = self._setup_logging()

        def _cfg_get(key: str, default=None):
            if isinstance(self.config, dict):
                return self.config.get(key, default)
            return getattr(self.config, key, default)

        # Feature flag for market trend analysis
        # PRODUCTION DEFAULT: True - uses real Kite API data
        # Set to False ONLY for development/testing with synthetic data
        self.use_kite_for_trends = _cfg_get('use_kite_trends', True)

        # Warn if synthetic data mode is enabled
        if not self.use_kite_for_trends:
            self.logger.warning("⚠️ SYNTHETIC DATA MODE ENABLED - Market trends will use mock data, not real prices!")
            self.logger.warning("⚠️ This should ONLY be used for development/testing, NOT production trading!")

        # Index token map (can be overridden from config)
        configured_tokens_raw = _cfg_get('index_tokens', {}) or {}
        configured_tokens = configured_tokens_raw if isinstance(configured_tokens_raw, dict) else {}
        effective_tokens = AdvancedMarketManager.DEFAULT_INDEX_TOKENS.copy()
        if index_tokens:
            effective_tokens.update({str(k).upper(): v for k, v in index_tokens.items()})
        effective_tokens.update({str(k).upper(): v for k, v in configured_tokens.items()})
        self.index_tokens = effective_tokens

        # Primary symbol used for market trend analysis (defaults to NIFTY)
        configured_trend_symbol = _cfg_get('trend_index_symbol', None) or 'NIFTY'
        self.primary_trend_symbol = self._normalize_symbol(configured_trend_symbol)

        # Market timings
        self.market_open_time = "09:15"
        self.market_close_time = "15:30"
        self.expiry_close_time = "15:30"  # F&O expiry positions close at 3:30 PM

        # CRITICAL FIX: NSE holiday calendar
        try:
            self.nse_holidays = holidays.India()
            self.logger.info("✅ NSE holiday calendar loaded")
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to load NSE holiday calendar: {e}")
            self.nse_holidays = None

        # Position management
        self.overnight_positions = {}
        self.expiry_positions = {}

        # Trend analysis parameters
        self.trend_indicators = {
            'rsi_period': 14,
            'ma_short': 20,
            'ma_long': 50,
            'bollinger_period': 20
        }

        # CACHE: Synthetic market data to avoid random trends on every call
        # This ensures consistent trend analysis within a session when Kite API is not available
        self._cached_synthetic_data = None
        self._synthetic_data_generated_at = None
        self._synthetic_mode_warning_logged = False
        self.last_trend_metadata: Optional[Dict[str, Any]] = None

        self.logger.info("🚀 Advanced Market Manager initialized")

    def _setup_logging(self):
        """Setup logging for market manager"""
        logger = logging.getLogger('market_manager')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter('%(asctime)s - MARKET - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def get_current_session(self) -> MarketSession:
        """Get current market session details"""
        now = datetime.now(self.ist)
        current_date = now.date()

        # CRITICAL FIX: Check if it's a trading day (Monday to Friday AND not a NSE holiday)
        is_weekday = now.weekday() < 5
        is_holiday = self.nse_holidays and current_date in self.nse_holidays

        if is_holiday:
            self.logger.debug(f"🏖️ NSE Holiday: {self.nse_holidays.get(current_date)}")

        is_trading_day = is_weekday and not is_holiday

        # Create market timings for today
        market_open = datetime.combine(
            current_date,
            datetime.strptime(self.market_open_time, "%H:%M").time()
        )
        market_open = self.ist.localize(market_open)

        market_close = datetime.combine(
            current_date,
            datetime.strptime(self.market_close_time, "%H:%M").time()
        )
        market_close = self.ist.localize(market_close)

        pre_close = datetime.combine(
            current_date,
            datetime.strptime(self.expiry_close_time, "%H:%M").time()
        )
        pre_close = self.ist.localize(pre_close)

        return MarketSession(
            date=current_date.strftime("%Y-%m-%d"),
            market_open=market_open,
            market_close=market_close,
            pre_close=pre_close,
            is_trading_day=is_trading_day
        )

    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        session = self.get_current_session()
        now = datetime.now(self.ist)

        if not session.is_trading_day:
            return False

        # FIXED: Stop trading AT market close, not after
        return session.market_open <= now < session.market_close

    def is_expiry_close_time(self) -> bool:
        """Check if it's time to close expiring F&O positions (3:30 PM)"""
        session = self.get_current_session()
        now = datetime.now(self.ist)

        # Close expiry positions at or after 3:30 PM
        return now >= session.pre_close

    def should_stop_trading(self) -> Tuple[bool, str]:
        """
        Check if trading should stop
        Returns: (should_stop, reason)
        """
        session = self.get_current_session()
        now = datetime.now(self.ist)

        if not session.is_trading_day:
            return True, "market_closed_weekend"

        if now >= session.market_close:
            return True, "market_closed"

        return False, "market_open"

    def should_stop_dashboard(self) -> bool:
        """Check if dashboard should stop after market hours"""
        session = self.get_current_session()
        now = datetime.now(self.ist)

        # Stop dashboard 30 minutes after market close
        dashboard_stop_time = session.market_close + timedelta(minutes=30)
        return now >= dashboard_stop_time

    def analyze_market_trend(self, symbol: Optional[str] = None, kite=None, instrument_token: Optional[int] = None) -> MarketTrend:
        """
        Analyze market trend using technical indicators
        Returns: MarketTrend (BULLISH, BEARISH, NEUTRAL)

        Args:
            symbol: Symbol to analyze (used for fallback mode)
            kite: KiteConnect instance (optional, for real data)
            instrument_token: Instrument token for Kite API (optional)
        """
        try:
            kite = kite or self.kite
            if symbol is None:
                symbol = self.primary_trend_symbol

            normalized_symbol = self._normalize_symbol(symbol)
            resolved_instrument_token = instrument_token or self.index_tokens.get(normalized_symbol)

            # Fetch market data
            data = None

            if self.use_kite_for_trends and kite and resolved_instrument_token:
                # Use Kite API for real market data
                try:
                    to_date = datetime.now()
                    from_date = to_date - timedelta(days=90)  # 3 months

                    historical_data = kite.historical_data(
                        instrument_token=resolved_instrument_token,
                        from_date=from_date,
                        to_date=to_date,
                        interval="day"
                    )

                    if historical_data:
                        # Convert Kite data to DataFrame
                        data = pd.DataFrame(historical_data)
                        # Rename columns to match expected format
                        data = data.rename(columns={
                            'close': 'Close',
                            'open': 'Open',
                            'high': 'High',
                            'low': 'Low',
                            'volume': 'Volume'
                        })
                        self.logger.info(f"📊 Using real Kite data for {normalized_symbol}")
                except Exception as e:
                    self.logger.warning(f"Failed to fetch Kite data for {normalized_symbol}: {e}, using fallback")
                    data = None

            if data is None:
                # CRITICAL FIX: Fail closed with NEUTRAL trend instead of random synthetic data
                # Random synthetic data causes non-deterministic behavior in risk controls
                # In production, lack of market data should NOT allow trading

                if not self._synthetic_mode_warning_logged:
                    self.logger.error(f"❌ NO MARKET DATA AVAILABLE for {normalized_symbol}")
                    self.logger.error("❌ Returning NEUTRAL trend - trading will be restricted")
                    self._synthetic_mode_warning_logged = True

                # Persist diagnostic details for observability, but keep return type stable
                self.last_trend_metadata = {
                    'symbol': normalized_symbol,
                    'reason': 'missing_market_data',
                    'timestamp': datetime.now(self.ist).isoformat()
                }
                return MarketTrend.NEUTRAL

            # Calculate technical indicators
            close_prices = data['Close']

            # RSI
            rsi = self._calculate_rsi(close_prices, self.trend_indicators['rsi_period'])
            current_rsi = rsi.iloc[-1]

            # Moving Averages
            ma_short = close_prices.rolling(window=self.trend_indicators['ma_short']).mean()
            ma_long = close_prices.rolling(window=self.trend_indicators['ma_long']).mean()

            current_price = close_prices.iloc[-1]
            current_ma_short = ma_short.iloc[-1]
            current_ma_long = ma_long.iloc[-1]

            # Bollinger Bands
            bb_period = self.trend_indicators['bollinger_period']
            bb_middle = close_prices.rolling(window=bb_period).mean()
            bb_std = close_prices.rolling(window=bb_period).std()
            bb_upper = bb_middle + (bb_std * 2)
            bb_lower = bb_middle - (bb_std * 2)

            band_width = bb_upper.iloc[-1] - bb_lower.iloc[-1]
            if not np.isfinite(band_width) or abs(band_width) < 1e-6:
                self.logger.debug("Bollinger band width is near zero; defaulting position to neutral.")
                current_bb_position = 0.5
            else:
                current_bb_position = (current_price - bb_lower.iloc[-1]) / band_width
                current_bb_position = float(np.clip(current_bb_position, 0.0, 1.0))

            # Trend Analysis
            bullish_signals = 0
            bearish_signals = 0

            # RSI signals
            if current_rsi < 30:
                bullish_signals += 1  # Oversold, potential uptrend
            elif current_rsi > 70:
                bearish_signals += 1  # Overbought, potential downtrend

            # Moving Average signals
            if current_ma_short > current_ma_long:
                bullish_signals += 1
            else:
                bearish_signals += 1

            # Price vs MA signals
            if current_price > current_ma_short:
                bullish_signals += 1
            else:
                bearish_signals += 1

            # Bollinger Band signals
            if current_bb_position > 0.8:
                bearish_signals += 1  # Near upper band
            elif current_bb_position < 0.2:
                bullish_signals += 1  # Near lower band

            # Determine trend
            if bullish_signals > bearish_signals:
                trend = MarketTrend.BULLISH
            elif bearish_signals > bullish_signals:
                trend = MarketTrend.BEARISH
            else:
                trend = MarketTrend.NEUTRAL

            self.logger.info(f"📈 Market Trend Analysis for {normalized_symbol}:")
            self.logger.info(f"   RSI: {current_rsi:.2f}")
            self.logger.info(f"   Price: {current_price:.2f} | MA20: {current_ma_short:.2f} | MA50: {current_ma_long:.2f}")
            self.logger.info(f"   Bollinger Position: {current_bb_position:.2f}")
            self.logger.info(f"   Trend: {trend.value.upper()} (Bullish: {bullish_signals}, Bearish: {bearish_signals})")

            return trend

        except Exception as e:
            self.logger.error(f"Error analyzing market trend: {e}")
            return MarketTrend.NEUTRAL

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize index symbol names to match instrument token map"""
        if not symbol:
            return self.primary_trend_symbol

        normalized = symbol.upper().strip()
        if normalized.startswith('^'):
            normalized = normalized[1:]

        mapping = {
            'NSEI': 'NIFTY',
            'NSEBANK': 'BANKNIFTY',
            'NIFTY50': 'NIFTY',
            'NIFTY BANK': 'BANKNIFTY',
            'NIFTYBANK': 'BANKNIFTY'
        }
        return mapping.get(normalized, normalized)

    def _generate_synthetic_market_data(self) -> pd.DataFrame:
        """
        [DEPRECATED] Generate synthetic market data for testing/development

        CRITICAL FIX: This method is no longer used due to non-deterministic behavior.
        The system now fails closed with NEUTRAL trend when market data is unavailable.
        Kept for backward compatibility only.

        Creates realistic-looking OHLC data with trends
        """
        # Generate 90 days of data
        dates = pd.date_range(end=datetime.now(), periods=90, freq='D')

        # Start at a base price (e.g., NIFTY ~25000)
        base_price = 25000
        prices = []

        # Add some trend and noise
        for i in range(90):
            # Add slight upward trend + random walk
            trend = i * 10  # Slight upward bias
            noise = np.random.randn() * 200  # Daily volatility
            price = base_price + trend + noise
            prices.append(max(price, 20000))  # Floor at 20000

        close_prices = np.array(prices)

        # Generate OHLC from close
        data = pd.DataFrame({
            'Close': close_prices,
            'Open': close_prices * (1 + np.random.randn(90) * 0.005),
            'High': close_prices * (1 + abs(np.random.randn(90)) * 0.01),
            'Low': close_prices * (1 - abs(np.random.randn(90)) * 0.01),
            'Volume': np.random.randint(100000, 500000, 90)
        }, index=dates)

        return data

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def classify_positions(self, positions: Dict) -> Tuple[Dict, Dict]:
        """
        Classify positions into expiry and overnight categories
        Returns: (expiry_positions, overnight_positions)
        """
        expiry_positions = {}
        overnight_positions = {}

        current_date = datetime.now(self.ist).date()

        for symbol, position_data in positions.items():
            if symbol.endswith('_SHORT'):
                continue  # Skip short positions for classification

            # Check if it's an F&O position that expires today
            if self._is_expiry_position(symbol, current_date):
                expiry_positions[symbol] = position_data
                expiry_positions[symbol]['position_type'] = PositionType.EXPIRY.value
            else:
                overnight_positions[symbol] = position_data
                overnight_positions[symbol]['position_type'] = PositionType.OVERNIGHT.value

        return expiry_positions, overnight_positions

    def _is_expiry_position(self, symbol: str, current_date) -> bool:
        """Check if position expires today"""
        base_symbol = symbol[:-6] if symbol.endswith('_SHORT') else symbol
        try:
            expiry_date = self._determine_expiry_date(base_symbol, current_date)
            if expiry_date is None:
                return False
            return expiry_date <= current_date
        except Exception as exc:
            self.logger.warning(f"Could not determine expiry for {symbol}: {exc}")
            return False

    def _determine_expiry_date(self, symbol: str, reference_date) -> Optional[date]:
        """Derive the expiry date from an instrument symbol."""
        import re

        MONTH_MAP = {
            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
        }

        symbol = symbol.upper()
        if ':' in symbol:
            symbol = symbol.split(':', 1)[1]

        underlying_match = re.match(r'^([A-Z]+)', symbol)
        if not underlying_match:
            return None

        underlying = underlying_match.group(1)
        remainder = symbol[underlying_match.end():]

        # Legacy weekly pattern (YYOmmdd)
        legacy_weekly = re.match(r'(\d{2})O(\d{2})(\d{2})', remainder)
        if legacy_weekly:
            year = 2000 + int(legacy_weekly.group(1))
            month = int(legacy_weekly.group(2))
            day = int(legacy_weekly.group(3))
            try:
                return datetime(year, month, day).date()
            except ValueError:
                return None

        # Options (weekly/monthly) pattern
        option_pattern = re.match(r'(\d{2})([A-Z]{1,3})(\d{2})([^CPE]*)(CE|PE)$', remainder)
        if option_pattern:
            year = 2000 + int(option_pattern.group(1))
            month_code = option_pattern.group(2)
            day = int(option_pattern.group(3))

            month_candidates = self._resolve_month_candidates(month_code, MONTH_MAP)
            if not month_candidates:
                return None

            weekly_weekday, monthly_weekday = self._get_weekday_targets(underlying)
            candidates: List[Tuple[date, str]] = []

            for month in month_candidates:
                try:
                    candidate = datetime(year, month, day).date()
                except ValueError:
                    continue

                monthly_expiry = self._last_weekday_of_month(year, month, monthly_weekday)
                if candidate == monthly_expiry:
                    candidates.append((candidate, 'monthly'))
                elif candidate.weekday() == weekly_weekday:
                    candidates.append((candidate, 'weekly'))
                else:
                    candidates.append((candidate, 'unknown'))

            if candidates:
                for preference in ('monthly', 'weekly'):
                    filtered = [c for c in candidates if c[1] == preference]
                    if filtered:
                        return min(filtered, key=lambda c: abs((c[0] - reference_date).days))[0]

                return min(candidates, key=lambda c: abs((c[0] - reference_date).days))[0]

            return None

        # Futures format
        fut_pattern = re.match(r'(\d{2})([A-Z]{1,3})FUT$', remainder)
        if fut_pattern:
            year = 2000 + int(fut_pattern.group(1))
            month_code = fut_pattern.group(2)
            month_candidates = self._resolve_month_candidates(month_code, MONTH_MAP)
            if not month_candidates:
                return None

            expiry_dates = [
                self._last_weekday_of_month(year, month, 3)
                for month in month_candidates
            ]
            return min(expiry_dates, key=lambda d: abs((d - reference_date).days)) if expiry_dates else None

        return None

    def _resolve_month_candidates(self, month_code: str, month_map: Dict[str, int]) -> List[int]:
        code = month_code.upper()
        candidates: Set[int] = set()

        if code in month_map:
            candidates.add(month_map[code])
        else:
            candidates.update(
                month_map[abbr]
                for abbr in month_map
                if abbr.startswith(code)
            )
            if not candidates and len(code) == 1:
                candidates.update(
                    month_map[abbr]
                    for abbr in month_map
                    if abbr[0] == code[0]
                )

        return sorted(candidates)

    def _get_weekday_targets(self, underlying: str) -> Tuple[int, int]:
        underlying = underlying.upper()
        if 'FINNIFTY' in underlying:
            return 1, 1  # Tuesday
        if 'BANKNIFTY' in underlying:
            return 2, 2  # Wednesday
        return 3, 3  # Thursday default

    def _last_weekday_of_month(self, year: int, month: int, weekday: int) -> date:
        last_day = calendar.monthrange(year, month)[1]
        dt = datetime(year, month, last_day)
        while dt.weekday() != weekday:
            dt -= timedelta(days=1)
        return dt.date()

    def manage_positions_at_close(self, positions: Dict, close_expiry_only: bool = True) -> Dict:
        """
        Manage positions at market close
        Returns: Updated positions after closing
        """
        if not positions:
            return positions

        expiry_positions, overnight_positions = self.classify_positions(positions)

        self.logger.info(f"🔄 Managing positions at close:")
        self.logger.info(f"   Expiry positions: {len(expiry_positions)}")
        self.logger.info(f"   Overnight positions: {len(overnight_positions)}")

        # Always close expiry positions at 3:30 PM
        positions_to_close = []
        if self.is_expiry_close_time():
            positions_to_close.extend(expiry_positions.keys())
            self.logger.info(f"🔔 Closing {len(expiry_positions)} expiring positions at 3:30 PM")

        # If market is completely closed, close all positions (optional)
        session = self.get_current_session()
        now = datetime.now(self.ist)
        if now >= session.market_close and not close_expiry_only:
            positions_to_close.extend(overnight_positions.keys())
            self.logger.info(f"🔔 Closing all {len(overnight_positions)} remaining positions at market close")

        # Remove closed positions
        updated_positions = positions.copy()
        for symbol in positions_to_close:
            if symbol in updated_positions:
                del updated_positions[symbol]
                self.logger.info(f"❌ Closed position: {symbol}")

        return updated_positions

    def adjust_overnight_positions_for_trend(self, positions: Dict, current_trend: MarketTrend) -> Dict:
        """
        Adjust overnight positions based on market trend
        Returns: Adjusted positions
        """
        if not positions:
            return positions

        expiry_positions, overnight_positions = self.classify_positions(positions)

        self.logger.info(f"🎯 Adjusting overnight positions for {current_trend.value.upper()} trend")

        adjusted_positions = positions.copy()

        for symbol, position_data in overnight_positions.items():
            original_shares = position_data.get('shares', 0)

            # Trend-based adjustments
            if current_trend == MarketTrend.BULLISH:
                # Increase long positions, reduce short positions
                if original_shares > 0:  # Long position
                    adjustment_factor = 1.1  # Increase by 10%
                else:  # Short position
                    adjustment_factor = 0.9  # Reduce by 10%
            elif current_trend == MarketTrend.BEARISH:
                # Reduce long positions, increase short positions
                if original_shares > 0:  # Long position
                    adjustment_factor = 0.9  # Reduce by 10%
                else:  # Short position
                    adjustment_factor = 1.1  # Increase by 10%
            else:  # NEUTRAL
                adjustment_factor = 1.0  # No change

            # Apply adjustment
            if adjustment_factor != 1.0:
                new_shares = int(round(original_shares * adjustment_factor))
                if new_shares != original_shares:
                    adjusted_positions[symbol]['shares'] = new_shares
                    adjusted_positions[symbol]['trend_adjusted'] = True
                    adjusted_positions[symbol]['adjustment_factor'] = adjustment_factor

                    self.logger.info(f"📊 Adjusted {symbol}: {original_shares} -> {new_shares} shares ({adjustment_factor:.1f}x)")

        return adjusted_positions

    def get_market_status_display(self) -> Dict:
        """Get market status for display"""
        session = self.get_current_session()
        now = datetime.now(self.ist)
        should_stop, stop_reason = self.should_stop_trading()
        current_trend = self.analyze_market_trend(self.primary_trend_symbol)

        # Calculate time remaining
        if not should_stop:
            time_to_close = session.market_close - now
            time_remaining = str(time_to_close).split('.')[0]  # Remove microseconds
        else:
            time_remaining = "00:00:00"

        status = {
            'current_time': now.strftime('%Y-%m-%d %H:%M:%S IST'),
            'market_open_time': session.market_open.strftime('%H:%M'),
            'market_close_time': session.market_close.strftime('%H:%M'),
            'is_trading_day': session.is_trading_day,
            'is_market_open': self.is_market_open(),
            'should_stop_trading': should_stop,
            'stop_reason': stop_reason,
            'time_remaining': time_remaining,
            'is_expiry_close_time': self.is_expiry_close_time(),
            'market_trend': current_trend.value,
            'should_stop_dashboard': self.should_stop_dashboard()
        }

        return status

    def save_overnight_state(self, positions: Dict, trading_day: str):
        """Save overnight positions for next day"""
        try:
            overnight_file = Path("state") / f"overnight_positions_{trading_day}.json"
            overnight_file.parent.mkdir(exist_ok=True)

            expiry_positions, overnight_positions = self.classify_positions(positions)

            overnight_state = {
                'trading_day': trading_day,
                'saved_at': datetime.now(self.ist).isoformat(),
                'overnight_positions': overnight_positions,
                'market_trend': self.analyze_market_trend(self.primary_trend_symbol).value,
                'position_count': len(overnight_positions)
            }

            with open(overnight_file, 'w') as f:
                json.dump(overnight_state, f, indent=2)

            self.logger.info(f"💾 Saved {len(overnight_positions)} overnight positions for next day")

        except Exception as e:
            self.logger.error(f"Error saving overnight state: {e}")

    def load_overnight_state(self, trading_day: str) -> Optional[Dict]:
        """Load overnight positions from previous day"""
        try:
            overnight_file = Path("state") / f"overnight_positions_{trading_day}.json"

            if overnight_file.exists():
                with open(overnight_file, 'r') as f:
                    overnight_state = json.load(f)

                positions = overnight_state.get('overnight_positions', {})
                previous_trend = overnight_state.get('market_trend', 'neutral')

                self.logger.info(f"📂 Loaded {len(positions)} overnight positions from {trading_day}")
                self.logger.info(f"   Previous trend: {previous_trend}")

                # Adjust positions based on current trend
                current_trend = self.analyze_market_trend(self.primary_trend_symbol)
                if current_trend.value != previous_trend:
                    self.logger.info(f"🔄 Trend changed from {previous_trend} to {current_trend.value}")
                    positions = self.adjust_overnight_positions_for_trend(positions, current_trend)

                return positions

        except Exception as e:
            self.logger.error(f"Error loading overnight state: {e}")

        return None

# Example usage and testing
if __name__ == "__main__":
    print("🚀 Advanced Market Manager - Testing Mode")

    manager = AdvancedMarketManager()

    # Test market status
    status = manager.get_market_status_display()
    print(f"\n📊 Market Status:")
    for key, value in status.items():
        print(f"   {key}: {value}")

    # Test trend analysis
    trend = manager.analyze_market_trend()
    print(f"\n📈 Current Market Trend: {trend.value.upper()}")

    # Test position classification
    sample_positions = {
        "NIFTY25OCT24650CE": {"shares": 75, "entry_price": 126.22},
        "NIFTY25DEC24700CE": {"shares": 50, "entry_price": 200.15},
        "FINNIFTY25OCT26050CE": {"shares": 65, "entry_price": 107.81}
    }

    expiry, overnight = manager.classify_positions(sample_positions)
    print(f"\n🔄 Position Classification:")
    print(f"   Expiry: {list(expiry.keys())}")
    print(f"   Overnight: {list(overnight.keys())}")
