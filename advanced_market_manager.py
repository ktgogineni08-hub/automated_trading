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
from datetime import datetime, timedelta
from pathlib import Path
import pytz
import pandas as pd
import numpy as np
import yfinance as yf
import logging
from typing import Dict, List, Optional, Any, Tuple
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

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.ist = pytz.timezone('Asia/Kolkata')
        self.logger = self._setup_logging()

        # Market timings
        self.market_open_time = "09:15"
        self.market_close_time = "15:30"
        self.expiry_close_time = "15:30"  # F&O expiry positions close at 3:30 PM

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

        # Check if it's a trading day (Monday to Friday)
        is_trading_day = now.weekday() < 5

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

        return session.market_open <= now <= session.market_close

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

    def analyze_market_trend(self, symbol: str = "^NSEI") -> MarketTrend:
        """
        Analyze market trend using technical indicators
        Returns: MarketTrend (BULLISH, BEARISH, NEUTRAL)
        """
        try:
            # Fetch market data
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="3mo", interval="1d")

            if data.empty:
                self.logger.warning(f"No data available for {symbol}")
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

            current_bb_position = (current_price - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1])

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

            self.logger.info(f"📈 Market Trend Analysis for {symbol}:")
            self.logger.info(f"   RSI: {current_rsi:.2f}")
            self.logger.info(f"   Price: {current_price:.2f} | MA20: {current_ma_short:.2f} | MA50: {current_ma_long:.2f}")
            self.logger.info(f"   Bollinger Position: {current_bb_position:.2f}")
            self.logger.info(f"   Trend: {trend.value.upper()} (Bullish: {bullish_signals}, Bearish: {bearish_signals})")

            return trend

        except Exception as e:
            self.logger.error(f"Error analyzing market trend: {e}")
            return MarketTrend.NEUTRAL

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
        try:
            # Extract date from F&O symbol (e.g., NIFTY{DD}{MMM}{YY}{STRIKE}CE -> {DD}{MMM})
            import re
            date_pattern = r'(\d{2}[A-Z]{3})'
            match = re.search(date_pattern, symbol)

            if not match:
                return False

            expiry_str = match.group(1)

            # Convert to date (assuming current year)
            month_map = {
                'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
            }

            day = int(expiry_str[:2])
            month_str = expiry_str[2:]
            month = month_map.get(month_str)

            if month:
                expiry_date = current_date.replace(month=month, day=day)
                return expiry_date <= current_date

        except Exception as e:
            self.logger.warning(f"Could not determine expiry for {symbol}: {e}")

        return False

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
                new_shares = int(original_shares * adjustment_factor)
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
        current_trend = self.analyze_market_trend()

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
                'market_trend': self.analyze_market_trend().value,
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
                current_trend = self.analyze_market_trend()
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