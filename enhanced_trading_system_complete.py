#!/usr/bin/env python3
"""
Enhanced NIFTY 50 Trading System - Complete All-in-One System
Combines mode selection menu + full trading functionality
Supports Paper Trading, Live Trading, and Backtesting
All improvements and fixes integrated for maximum profits
"""

import sys
import os
import subprocess
import time
import webbrowser
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque
import pytz
import pandas as pd
import numpy as np
import random
import yfinance as yf
from kiteconnect import KiteConnect

# Import token manager from current directory
from zerodha_token_manager import ZerodhaTokenManager

# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================
NIFTY_50_SYMBOLS = [
    "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN",
    "INDUSINDBK", "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE",
    "INFY", "TCS", "WIPRO", "HCLTECH", "TECHM", "LTIM",
    "RELIANCE", "ONGC", "NTPC", "POWERGRID", "COALINDIA", "BPCL",
    "ADANIENT", "ADANIPORTS",
    "HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "ASIANPAINT",
    "TITAN", "PIDILITIND",
    "MARUTI", "M&M", "TATAMOTORS", "HEROMOTOCO", "EICHERMOT", "BAJAJ-AUTO",
    "SUNPHARMA", "DRREDDY", "DIVISLAB", "CIPLA", "APOLLOHOSP",
    "TATASTEEL", "JSWSTEEL", "HINDALCO", "GRASIM", "ULTRACEMCO", "SHREECEM",
    "BHARTIARTL", "LT"
]

SECTOR_GROUPS = {
    "Banking": ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN", "INDUSINDBK"],
    "IT": ["INFY", "TCS", "WIPRO", "HCLTECH", "TECHM", "LTIM"],
    "Energy": ["RELIANCE", "ONGC", "NTPC", "POWERGRID", "COALINDIA", "BPCL", "ADANIENT"],
    "FMCG": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA"],
    "Auto": ["MARUTI", "M&M", "TATAMOTORS", "HEROMOTOCO", "EICHERMOT", "BAJAJ-AUTO"],
    "Pharma": ["SUNPHARMA", "DRREDDY", "DIVISLAB", "CIPLA", "APOLLOHOSP"],
    "Metals": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "GRASIM"],
    "Finance": ["BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE"]
}

# ============================================================================
# DASHBOARD INTEGRATION
# ============================================================================
class DashboardConnector:
    """Enhanced connector with better error handling"""
    
    def __init__(self, base_url="http://localhost:5173"):
        self.base_url = base_url
        self.session = requests.Session()
        self.is_connected = False
        self.last_connection_check = 0
        self.connection_check_interval = 5  # seconds
        self.ensure_connection()
        self.failed_sends = 0
        self.max_retries = 3
        
    def test_connection(self):
        """Test if dashboard is accessible"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def ensure_connection(self, force=False):
        """Ensure the dashboard connection is alive, retrying if needed"""
        now = time.time()
        if force or not self.is_connected or (now - self.last_connection_check) > self.connection_check_interval:
            self.is_connected = self.test_connection()
            self.last_connection_check = now
        return self.is_connected

    def send_with_retry(self, endpoint, data, max_retries=3):
        """Send data with automatic retry"""
        if not self.ensure_connection():
            # try one immediate forced reconnect before bailing
            if not self.ensure_connection(force=True):
                return False
        
        for attempt in range(max_retries):
            try:
                response = self.session.post(
                    f"{self.base_url}/api/{endpoint}",
                    json=data,
                    timeout=2
                )
                if response.status_code == 200:
                    if not self.is_connected:
                        self.is_connected = True
                    return True
            except:
                pass
            # A failure might mean the server restarted; retry connection check
            self.ensure_connection(force=True)
        return False
    
    def send_signal(self, symbol, action, confidence, price, sector=None, reasons=None):
        """Send signal to dashboard"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'action': action.upper(),
            'confidence': round(confidence, 3),
            'price': round(price, 2),
            'sector': sector or 'Other',
            'reasons': reasons or []
        }
        return self.send_with_retry('signals', data)
    
    def send_trade(self, symbol, side, shares, price, pnl=None, sector=None, confidence=0.5):
        """Send trade execution to dashboard"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'side': side.upper(),
            'shares': shares,
            'price': round(price, 2),
            'amount': round(shares * price, 2),
            'pnl': round(pnl, 2) if pnl is not None else None,
            'sector': sector or 'Other',
            'confidence': round(confidence, 3)
        }
        return self.send_with_retry('trades', data)
    
    def send_portfolio_update(self, total_value, cash, positions_count, total_pnl, positions=None):
        """Send portfolio update to dashboard"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'total_value': round(total_value, 2),
            'cash': round(cash, 2),
            'positions_count': positions_count,
            'total_pnl': round(total_pnl, 2),
            'positions': positions or {}
        }
        return self.send_with_retry('portfolio', data)
    
    def send_performance_update(self, trades_count, win_rate, total_pnl, best_trade, worst_trade):
        """Send performance metrics to dashboard"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'trades_count': trades_count,
            'win_rate': round(win_rate, 2),
            'total_pnl': round(total_pnl, 2),
            'best_trade': round(best_trade, 2),
            'worst_trade': round(worst_trade, 2),
            'avg_pnl': round(total_pnl / trades_count, 2) if trades_count > 0 else 0
        }
        return self.send_with_retry('performance', data)
    
    def send_system_status(self, is_running, iteration=0, scan_status="idle"):
        """Send system status to dashboard"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'is_running': is_running,
            'iteration': iteration,
            'scan_status': scan_status
        }
        return self.send_with_retry('status', data)


class TradingStateManager:
    """Handles persistence of trading state and trade history across sessions."""

    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent / "state"
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.archive_dir = self.base_dir / "archive"
        self.archive_dir.mkdir(exist_ok=True)

        self.trades_dir = self.base_dir / "trades"
        self.trades_dir.mkdir(exist_ok=True)

        self.state_path = self.base_dir / "current_state.json"
        self.ist = pytz.timezone('Asia/Kolkata')

    def current_trading_day(self):
        return datetime.now(self.ist).strftime('%Y-%m-%d')

    def load_state(self):
        if not self.state_path.exists():
            return {}
        try:
            with self.state_path.open('r', encoding='utf-8') as handle:
                return json.load(handle)
        except Exception as exc:
            print(f"⚠️ Failed to load saved trading state: {exc}")
            return {}

    def save_state(self, state):
        try:
            temp_path = self.state_path.with_suffix('.tmp')
            with temp_path.open('w', encoding='utf-8') as handle:
                json.dump(state, handle, indent=2)
            temp_path.replace(self.state_path)
        except Exception as exc:
            print(f"⚠️ Failed to persist trading state: {exc}")

    def archive_state(self, state):
        trading_day = state.get('trading_day') or self.current_trading_day()
        archive_path = self.archive_dir / f"state_{trading_day}.json"
        try:
            with archive_path.open('w', encoding='utf-8') as handle:
                json.dump(state, handle, indent=2)
        except Exception as exc:
            print(f"⚠️ Failed to archive trading state: {exc}")

    def log_trade(self, trade, trading_day=None):
        day = trading_day or self.current_trading_day()
        trades_path = self.trades_dir / f"trades_{day}.jsonl"
        try:
            with trades_path.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(trade) + "\n")
        except Exception as exc:
            print(f"⚠️ Failed to log trade: {exc}")

    def write_daily_summary(self, trading_day, summary):
        summary_path = self.archive_dir / f"summary_{trading_day}.json"
        try:
            with summary_path.open('w', encoding='utf-8') as handle:
                json.dump(summary, handle, indent=2)
        except Exception as exc:
            print(f"⚠️ Failed to write daily summary: {exc}")

# ============================================================================
# MARKET COMPONENTS
# ============================================================================
class MarketHours:
    def __init__(self):
        self.ist = pytz.timezone('Asia/Kolkata')
        self.market_open = datetime.strptime("09:15", "%H:%M").time()
        self.market_close = datetime.strptime("15:30", "%H:%M").time()

    def is_market_open(self):
        now = datetime.now(self.ist)
        if now.weekday() >= 5:
            return False
        current_time = now.time()
        return self.market_open <= current_time <= self.market_close

class EnhancedRateLimiter:
    def __init__(self, max_requests_per_second=1, max_requests_per_minute=50):
        self.max_per_second = max_requests_per_second
        self.max_per_minute = max_requests_per_minute
        self.second_bucket = deque(maxlen=max_requests_per_second)
        self.minute_bucket = deque(maxlen=max_requests_per_minute)

    def can_make_request(self):
        now = time.time()
        second_ago = now - 1
        minute_ago = now - 60
        recent_second = [t for t in self.second_bucket if t > second_ago]
        if len(recent_second) >= self.max_per_second:
            return False
        recent_minute = [t for t in self.minute_bucket if t > minute_ago]
        if len(recent_minute) >= self.max_per_minute:
            return False
        return True

    def wait_if_needed(self):
        while not self.can_make_request():
            time.sleep(0.1)

    def record_request(self):
        now = time.time()
        self.second_bucket.append(now)
        self.minute_bucket.append(now)

# ============================================================================
# TRADING STRATEGIES
# ============================================================================
class ImprovedMovingAverageCrossover:
    def __init__(self, short_window=3, long_window=10):
        self.name = "Fast_MA_Crossover"
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> dict:
        if data is None or data.empty or len(data) < self.long_window + 5:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}
        
        ema_short = data["close"].ewm(span=self.short_window, adjust=False).mean()
        ema_long = data["close"].ewm(span=self.long_window, adjust=False).mean()
        
        current_short = ema_short.iloc[-1]
        current_long = ema_long.iloc[-1]
        prev_short = ema_short.iloc[-2]
        prev_long = ema_long.iloc[-2]
        
        currently_above = current_short > current_long
        previously_above = prev_short > prev_long
        
        bullish_cross = not previously_above and currently_above
        bearish_cross = previously_above and not currently_above
        
        separation = abs(current_short - current_long) / current_long if current_long != 0 else 0.0
        strength = min(separation * 100, 1.0)
        
        if bullish_cross and strength > 0.1:
            return {'signal': 1, 'strength': strength, 'reason': 'bullish_crossover'}
        elif bearish_cross and strength > 0.1:
            return {'signal': -1, 'strength': strength, 'reason': 'bearish_crossover'}
        elif currently_above and separation > 0.003:
            return {'signal': 1, 'strength': strength * 0.8, 'reason': 'bullish_trend'}
        elif not currently_above and separation > 0.003:
            return {'signal': -1, 'strength': strength * 0.8, 'reason': 'bearish_trend'}
        
        return {'signal': 0, 'strength': 0.0, 'reason': 'no_signal'}

class EnhancedRSIStrategy:
    def __init__(self, period=7, oversold=25, overbought=75):
        self.name = "Enhanced_RSI"
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> dict:
        if data is None or data.empty or len(data) < self.period + 5:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}
        
        delta = data["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        avg_gain = gain.ewm(span=self.period, adjust=False).mean()
        avg_loss = loss.ewm(span=self.period, adjust=False).mean()
        
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0
        
        if current_rsi <= self.oversold:
            strength = (self.oversold - current_rsi) / self.oversold
            return {'signal': 1, 'strength': min(strength * 2, 1.0), 'reason': f'oversold_{current_rsi:.0f}'}
        elif current_rsi >= self.overbought:
            strength = (current_rsi - self.overbought) / (100 - self.overbought)
            return {'signal': -1, 'strength': min(strength * 2, 1.0), 'reason': f'overbought_{current_rsi:.0f}'}
        
        return {'signal': 0, 'strength': 0.0, 'reason': 'neutral'}

class BollingerBandsStrategy:
    def __init__(self, period=20, std_dev=2):
        self.name = "Bollinger_Bands"
        self.period = period
        self.std_dev = std_dev

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> dict:
        if data is None or data.empty or len(data) < self.period + 5:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}
        
        close_prices = data['close']
        sma = close_prices.rolling(self.period).mean()
        std = close_prices.rolling(self.period).std()
        
        upper_band = sma + (std * self.std_dev)
        lower_band = sma - (std * self.std_dev)
        
        current_price = close_prices.iloc[-1]
        current_upper = upper_band.iloc[-1]
        current_lower = lower_band.iloc[-1]
        
        if current_price <= current_lower:
            strength = min((current_lower - current_price) / current_lower * 100, 1.0)
            return {'signal': 1, 'strength': strength, 'reason': 'oversold_at_lower_band'}
        elif current_price >= current_upper:
            strength = min((current_price - current_upper) / current_upper * 100, 1.0)
            return {'signal': -1, 'strength': strength, 'reason': 'overbought_at_upper_band'}
        
        return {'signal': 0, 'strength': 0.0, 'reason': 'no_signal'}

class ImprovedVolumeBreakoutStrategy:
    def __init__(self, volume_multiplier=1.3, price_threshold=0.001):
        self.name = "Volume_Price_Breakout"
        self.volume_multiplier = volume_multiplier
        self.price_threshold = price_threshold

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> dict:
        if data is None or data.empty or len(data) < 20:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}
        
        vol_avg = data['volume'].rolling(20).mean().iloc[-1]
        current_vol = data['volume'].iloc[-1]
        price_change = (data['close'].iloc[-1] - data['close'].iloc[-2]) / data['close'].iloc[-2]
        
        if current_vol > vol_avg * self.volume_multiplier:
            if price_change > self.price_threshold:
                strength = min((current_vol / vol_avg - 1) * 0.3 + abs(price_change) * 50, 1.0)
                return {'signal': 1, 'strength': strength, 'reason': 'volume_breakout_up'}
            elif price_change < -self.price_threshold:
                strength = min((current_vol / vol_avg - 1) * 0.3 + abs(price_change) * 50, 1.0)
                return {'signal': -1, 'strength': strength, 'reason': 'volume_breakout_down'}
        
        return {'signal': 0, 'strength': 0.0, 'reason': 'no_volume_signal'}

class EnhancedSignalAggregator:
    def __init__(self, min_agreement=0.2):
        self.min_agreement = min_agreement
        self.signal_history = {}

    def aggregate_signals(self, strategy_signals: list, symbol: str) -> dict:
        if not strategy_signals:
            return {'action': 'hold', 'confidence': 0.0, 'reasons': []}
        
        buy_signals = []
        sell_signals = []
        reasons = []
        
        for sig in strategy_signals:
            if not isinstance(sig, dict):
                continue
            if sig.get('signal') == 1:
                buy_signals.append(sig.get('strength', 0.0))
                reasons.append(sig.get('reason', ''))
            elif sig.get('signal') == -1:
                sell_signals.append(sig.get('strength', 0.0))
                reasons.append(sig.get('reason', ''))
        
        buy_confidence = float(np.mean(buy_signals)) if buy_signals else 0.0
        sell_confidence = float(np.mean(sell_signals)) if sell_signals else 0.0
        
        total_strategies = len([s for s in strategy_signals if isinstance(s, dict)])
        buy_agreement = len(buy_signals) / total_strategies if total_strategies > 0 else 0
        sell_agreement = len(sell_signals) / total_strategies if total_strategies > 0 else 0
        
        if buy_agreement >= self.min_agreement and buy_confidence > 0.15:
            confidence = buy_confidence * (0.6 + buy_agreement * 0.4)
            return {'action': 'buy', 'confidence': confidence, 'reasons': reasons}
        elif sell_agreement >= self.min_agreement and sell_confidence > 0.15:
            confidence = sell_confidence * (0.6 + sell_agreement * 0.4)
            return {'action': 'sell', 'confidence': confidence, 'reasons': reasons}
        
        return {'action': 'hold', 'confidence': 0.0, 'reasons': []}

# ============================================================================
# DATA PROVIDER
# ============================================================================
class DataProvider:
    def __init__(self, kite=None, instruments_map=None, use_yf_fallback=True):
        self.kite = kite
        self.instruments = instruments_map or {}
        self.use_yf = use_yf_fallback
        self.rate_limiter = EnhancedRateLimiter()
        self.cache = {}
        self.cache_ttl = 30

    def fetch_with_retry(self, symbol, interval="5minute", days=5, max_retries=3):
        cache_key = f"{symbol}_{interval}_{days}"
        if cache_key in self.cache:
            timestamp, data = self.cache[cache_key]
            if (time.time() - timestamp) < self.cache_ttl:
                return data
        
        token = self.instruments.get(symbol)
        for attempt in range(max_retries):
            try:
                self.rate_limiter.wait_if_needed()
                if token and self.kite:
                    end = datetime.now()
                    start = end - timedelta(days=days)
                    self.rate_limiter.record_request()
                    candles = self.kite.historical_data(token, start, end, interval)
                    if candles:
                        df = pd.DataFrame(candles)
                        if "date" in df.columns:
                            df["date"] = pd.to_datetime(df["date"])
                            df.set_index("date", inplace=True)
                        df = df.rename(columns={"open":"open","high":"high","low":"low","close":"close","volume":"volume"})
                        expected_cols = ["open","high","low","close","volume"]
                        for c in expected_cols:
                            if c not in df.columns:
                                df[c] = np.nan
                        df = df[expected_cols]
                        self.cache[cache_key] = (time.time(), df)
                        return df
                if self.use_yf:
                    df = self._yfinance_fetch(symbol, interval, days)
                    if not df.empty:
                        self.cache[cache_key] = (time.time(), df)
                        return df
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
        return pd.DataFrame()

    def _yfinance_fetch(self, symbol, interval, days):
        yf_interval = {
            "1minute":"1m","5minute":"5m","15minute":"15m",
            "30minute":"30m","60minute":"60m","day":"1d"
        }.get(interval, "5m")
        ticker = symbol if symbol.endswith((".NS", ".BO")) else symbol + ".NS"
        try:
            df = yf.download(ticker, period=f"{days}d", interval=yf_interval, progress=False, threads=False)
            if not df.empty:
                df = df.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
                expected = ["open","high","low","close","volume"]
                for c in expected:
                    if c not in df.columns:
                        df[c] = np.nan
                return df[expected]
        except Exception:
            pass
        return pd.DataFrame()

# ============================================================================
# UNIFIED PORTFOLIO
# ============================================================================
class UnifiedPortfolio:
    """Unified portfolio that handles all trading modes"""
    
    def __init__(self, initial_cash=1_000_000, dashboard=None, kite=None, trading_mode='paper', silent=False):
        self.initial_cash = float(initial_cash)
        self.cash = float(initial_cash)
        self.positions = {}
        self.dashboard = dashboard
        self.kite = kite
        self.trading_mode = trading_mode
        self.silent = silent
        
        # Trading tracking
        self.trades_count = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0
        self.best_trade = 0
        self.worst_trade = 0
        self.trades_history = []
        self.portfolio_history = []
        self.daily_profit = 0.0
        self.daily_target = None
        
        # Position management
        self.position_entry_times = {}
        self.min_holding_period = timedelta(minutes=15)
        
        # Mode-specific settings
        if trading_mode == 'live':
            self.min_position_size = 0.05  # 5% minimum for live
            self.max_position_size = 0.15  # 15% maximum for live (conservative)
            if not self.silent:
                print("🔴 LIVE TRADING MODE - Real money at risk!")
        elif trading_mode == 'paper':
            self.min_position_size = 0.10  # 10% minimum for paper
            self.max_position_size = 0.30  # 30% maximum for paper
            if not self.silent:
                print("📝 PAPER TRADING MODE - Safe simulation!")
        else:  # backtesting
            self.min_position_size = 0.10
            self.max_position_size = 0.25
            if not self.silent:
                print("📊 BACKTESTING MODE - Historical analysis!")
        
        # Transaction costs
        self.brokerage_rate = 0.0002  # 0.02%
        self.brokerage_max = 20.0
        self.transaction_charges = 0.0000325
        self.gst_rate = 0.18
        self.stt_rate = 0.001

        # Risk management defaults
        if trading_mode == 'live':
            self.risk_per_trade_pct = 0.005  # risk 0.5% of available cash per trade
            self.atr_stop_multiplier = 1.5
            self.atr_target_multiplier = 2.2
            self.trailing_activation_multiplier = 1.1
            self.trailing_stop_multiplier = 0.9
        else:
            self.risk_per_trade_pct = 0.01
            self.atr_stop_multiplier = 1.6
            self.atr_target_multiplier = 3.5
            self.trailing_activation_multiplier = 1.2
            self.trailing_stop_multiplier = 0.8

    def calculate_total_value(self, price_map=None):
        """Return current total portfolio value using latest prices when available."""
        price_map = price_map or {}
        positions_value = sum(
            pos["shares"] * price_map.get(symbol, pos["entry_price"])
            for symbol, pos in self.positions.items()
        )
        return self.cash + positions_value

    def record_trade(self, symbol, side, shares, price, fees, pnl=None, timestamp=None, confidence=0.0, sector='Other', atr_value=None):
        """Store trade details in history and return the serialized record."""
        if timestamp is None:
            timestamp = datetime.now()
        trade_record = {
            "timestamp": timestamp.isoformat(),
            "symbol": symbol,
            "side": side,
            "shares": int(shares),
            "price": float(price),
            "fees": float(fees),
            "mode": self.trading_mode,
            "confidence": float(confidence) if confidence is not None else None,
            "sector": sector or "Other",
            "cash_balance": float(self.cash)
        }
        if pnl is not None:
            trade_record["pnl"] = float(pnl)
        if atr_value is not None:
            trade_record["atr"] = float(atr_value)
        if pnl is not None:
            ts = timestamp or datetime.now()
            if isinstance(ts, datetime):
                if ts.tzinfo is None:
                    ts = pytz.timezone('Asia/Kolkata').localize(ts)
                else:
                    ts = ts.astimezone(pytz.timezone('Asia/Kolkata'))
                trade_record['trading_day'] = ts.strftime('%Y-%m-%d')
            self.daily_profit += pnl
        self.trades_history.append(trade_record)
        return trade_record

    def to_dict(self):
        """Serialize portfolio state for persistence."""
        serialized_positions = {}
        for symbol, pos in self.positions.items():
            serialized = dict(pos)
            entry_time = serialized.get('entry_time')
            if isinstance(entry_time, datetime):
                serialized['entry_time'] = entry_time.isoformat()
            serialized_positions[symbol] = serialized
        serialized_entry_times = {
            symbol: ts.isoformat()
            for symbol, ts in self.position_entry_times.items()
        }
        return {
            'initial_cash': self.initial_cash,
            'cash': self.cash,
            'positions': serialized_positions,
            'trades_count': self.trades_count,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'total_pnl': self.total_pnl,
            'best_trade': self.best_trade,
            'worst_trade': self.worst_trade,
            'trades_history': self.trades_history,
            'position_entry_times': serialized_entry_times
        }

    def load_from_dict(self, data):
        """Restore portfolio state from persisted snapshot."""
        if not data:
            return
        self.initial_cash = float(data.get('initial_cash', self.initial_cash))
        self.cash = float(data.get('cash', self.cash))

        restored_positions = {}
        entry_times = {}
        for symbol, pos in data.get('positions', {}).items():
            restored = dict(pos)
            entry_time_str = restored.get('entry_time')
            entry_time = None
            if entry_time_str:
                try:
                    entry_time = datetime.fromisoformat(entry_time_str)
                except Exception:
                    entry_time = None
            if entry_time is None:
                entry_time = datetime.now()
            restored['entry_time'] = entry_time
            restored['shares'] = int(restored.get('shares', 0))
            for key in ['entry_price', 'stop_loss', 'take_profit', 'confidence']:
                if key in restored and restored[key] is not None:
                    restored[key] = float(restored[key])
            restored_positions[symbol] = restored
            entry_times[symbol] = entry_time

        # Override with explicitly stored entry times when available
        stored_entry_times = data.get('position_entry_times', {})
        for symbol, entry_time_str in stored_entry_times.items():
            try:
                entry_time = datetime.fromisoformat(entry_time_str)
                entry_times[symbol] = entry_time
                if symbol in restored_positions:
                    restored_positions[symbol]['entry_time'] = entry_time
            except Exception:
                continue

        self.positions = restored_positions
        self.position_entry_times = entry_times
        self.trades_count = int(data.get('trades_count', self.trades_count))
        self.winning_trades = int(data.get('winning_trades', self.winning_trades))
        self.losing_trades = int(data.get('losing_trades', self.losing_trades))
        self.total_pnl = float(data.get('total_pnl', self.total_pnl))
        self.best_trade = float(data.get('best_trade', self.best_trade))
        self.worst_trade = float(data.get('worst_trade', self.worst_trade))
        self.trades_history = list(data.get('trades_history', self.trades_history))

    def calculate_transaction_costs(self, amount: float, trade_type: str) -> float:
        """Calculate realistic transaction costs"""
        brokerage = min(amount * self.brokerage_rate, self.brokerage_max)
        trans_charges = amount * self.transaction_charges
        gst = (brokerage + trans_charges) * self.gst_rate
        
        if trade_type == "buy":
            return brokerage + trans_charges + gst
        else:
            stt = amount * self.stt_rate
            return brokerage + trans_charges + gst + stt
    
    def place_live_order(self, symbol, quantity, price, side):
        """Place actual order for live trading"""
        if not self.kite or self.trading_mode != 'live':
            return False
        
        try:
            order_params = {
                'tradingsymbol': symbol,
                'exchange': 'NSE',
                'transaction_type': side.upper(),
                'quantity': quantity,
                'order_type': 'MARKET',
                'product': 'MIS',
                'validity': 'DAY'
            }
            
            print(f"🔴 PLACING LIVE ORDER: {side} {quantity} {symbol} @ ₹{price:.2f}")
            order_id = self.kite.place_order(**order_params)
            
            if order_id:
                print(f"✅ LIVE ORDER PLACED: Order ID {order_id}")
                return order_id
            else:
                print("❌ Failed to place live order")
                return False
                
        except Exception as e:
            print(f"❌ Error placing live order: {e}")
            return False
    
    def simulate_order_execution(self, symbol, shares, price, side):
        """Simulate order execution for paper trading"""
        if self.trading_mode != 'paper':
            return price
        
        # Simulate realistic slippage (0.1% to 0.3%)
        slippage = random.uniform(0.001, 0.003)
        if side == "buy":
            execution_price = price * (1 + slippage)
        else:
            execution_price = price * (1 - slippage)
        
            if not self.silent:
                print(f"📝 [PAPER {side.upper()}] {symbol}: {shares} @ ₹{execution_price:.2f} (slippage: {slippage*100:.2f}%)")
        return execution_price
    
    def can_exit_position(self, symbol):
        if symbol not in self.position_entry_times:
            return True
        time_held = datetime.now() - self.position_entry_times[symbol]
        return time_held >= self.min_holding_period
    
    def execute_trade(self, symbol, shares, price, side, timestamp=None, confidence=0.5, sector=None, atr=None):
        """Execute trade based on trading mode"""
        if timestamp is None:
            timestamp = datetime.now()
        
        if side == "buy":
            if shares <= 0 or price <= 0:
                return False

            atr_value = atr if atr and atr > 0 else None
            if atr_value:
                max_loss_per_share = atr_value * self.atr_stop_multiplier
                if max_loss_per_share <= 0:
                    atr_value = None
                else:
                    risk_budget = max(self.cash * self.risk_per_trade_pct, 0)
                    allowed_shares = int(risk_budget // max_loss_per_share)
                    if allowed_shares <= 0:
                        return False
                    shares = min(shares, allowed_shares)
                    if shares <= 0:
                        return False

            # For live trading, place actual order
            if self.trading_mode == 'live':
                order_id = self.place_live_order(symbol, shares, price, "BUY")
                if not order_id:
                    return False
            
            # For paper trading, simulate execution
            if self.trading_mode == 'paper':
                execution_price = self.simulate_order_execution(symbol, shares, price, "buy")
            else:
                execution_price = price
            
            amount = shares * execution_price
            fees = self.calculate_transaction_costs(amount, "buy")
            total_cost = amount + fees

            if total_cost > self.cash:
                return False

            self.cash -= total_cost
            entry_time = timestamp

            # Dynamic stop-loss and take-profit based on volatility & confidence
            # Check for profile-specific settings (for paper trading)
            stop_loss_pct = getattr(self, 'config', {}).get('stop_loss_pct')
            take_profit_pct = getattr(self, 'config', {}).get('take_profit_pct')

            if atr_value:
                confidence_adj = max(0.8, 1 - max(0.0, 0.6 - confidence))
                stop_distance = atr_value * self.atr_stop_multiplier * confidence_adj
                take_distance = atr_value * (self.atr_target_multiplier + max(0.0, confidence - 0.5))
                stop_loss = max(execution_price - stop_distance, execution_price * 0.9)
                take_profit = execution_price + take_distance
            elif stop_loss_pct and take_profit_pct:
                # Use profile-specific stop loss and take profit
                stop_loss = execution_price * (1 - stop_loss_pct)
                take_profit = execution_price * (1 + take_profit_pct)
            else:
                if self.trading_mode == 'live':
                    stop_loss = execution_price * 0.97
                    take_profit = execution_price * 1.06
                else:
                    if confidence >= 0.7:
                        stop_loss = execution_price * 0.94
                        take_profit = execution_price * 1.12
                    elif confidence >= 0.5:
                        stop_loss = execution_price * 0.95
                        take_profit = execution_price * 1.10
                    else:
                        stop_loss = execution_price * 0.96
                        take_profit = execution_price * 1.08

            self.positions[symbol] = {
                "shares": shares,
                "entry_price": execution_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "entry_time": entry_time,
                "confidence": confidence,
                "sector": sector or "Other",
                "atr": atr_value
            }
            
            self.position_entry_times[symbol] = entry_time
            self.trades_count += 1
            
            mode_icon = "🔴" if self.trading_mode == 'live' else "📝" if self.trading_mode == 'paper' else "📊"
            if not self.silent:
                print(f"{mode_icon} [BUY] {symbol}: {shares} @ ₹{execution_price:.2f} | SL: ₹{stop_loss:.2f} | TP: ₹{take_profit:.2f}")
            
            # Send to dashboard
            if self.dashboard:
                self.dashboard.send_trade(symbol, "buy", shares, execution_price, None, sector, confidence)
            
            return self.record_trade(
                symbol=symbol,
                side="buy",
                shares=shares,
                price=execution_price,
                fees=fees,
                pnl=None,
                timestamp=timestamp,
                confidence=confidence,
                sector=sector,
                atr_value=atr_value
            )
            
        elif side == "sell":
            if symbol not in self.positions or shares <= 0 or price <= 0:
                return False
            
            if not self.can_exit_position(symbol):
                return False
            
            position = self.positions[symbol]
            
            # For live trading, place actual order
            if self.trading_mode == 'live':
                order_id = self.place_live_order(symbol, shares, price, "SELL")
                if not order_id:
                    return False
            
            # For paper trading, simulate execution
            if self.trading_mode == 'paper':
                execution_price = self.simulate_order_execution(symbol, shares, price, "sell")
            else:
                execution_price = price
            
            amount = shares * execution_price
            fees = self.calculate_transaction_costs(amount, "sell")
            net = amount - fees
            self.cash += net
            
            pnl = (execution_price - position["entry_price"]) * shares - fees
            self.total_pnl += pnl
            
            # Track performance
            if pnl > self.best_trade:
                self.best_trade = pnl
            if pnl < self.worst_trade:
                self.worst_trade = pnl
            
            if pnl > 0:
                self.winning_trades += 1
                emoji = "🟢"
            else:
                self.losing_trades += 1
                emoji = "🔴"
            
            sector = position.get("sector", "Other")
            confidence = position.get("confidence", 0.5)
            
            del self.positions[symbol]
            if symbol in self.position_entry_times:
                del self.position_entry_times[symbol]
            
            mode_icon = "🔴" if self.trading_mode == 'live' else "📝" if self.trading_mode == 'paper' else "📊"
            if not self.silent:
                print(f"{emoji} {mode_icon} [SELL] {symbol}: {shares} @ ₹{execution_price:.2f} | P&L: ₹{pnl:.2f}")
            
            # Send to dashboard
            if self.dashboard:
                self.dashboard.send_trade(symbol, "sell", shares, execution_price, pnl, sector, confidence)
            
            return self.record_trade(
                symbol=symbol,
                side="sell",
                shares=shares,
                price=execution_price,
                fees=fees,
                pnl=pnl,
                timestamp=timestamp,
                confidence=confidence,
                sector=sector,
                atr_value=position.get('atr')
            )
        
        return False

# ============================================================================
# UNIFIED TRADING SYSTEM
# ============================================================================
class UnifiedTradingSystem:
    """Unified trading system supporting all modes"""
    
    def __init__(self, data_provider, kite, initial_cash=1_000_000, max_positions=25, dashboard=None, trading_mode='paper', config=None):
        self.dp = data_provider
        self.dashboard = dashboard
        self.kite = kite
        self.trading_mode = trading_mode
        self.config = config or {}

        # Create unified portfolio (silence when fast backtest)
        self.portfolio = UnifiedPortfolio(initial_cash, dashboard, kite, trading_mode, silent=bool(self.config.get('fast_backtest')))

        # Apply profile settings for paper trading
        if trading_mode == 'paper' and 'trading_profile' in self.config:
            profile = self.config['trading_profile']
            if profile == 'Aggressive':
                # Override portfolio settings for aggressive profile
                self.portfolio.min_position_size = 0.15  # 15% minimum for aggressive
                self.portfolio.max_position_size = 0.40  # 40% maximum for aggressive
                self.portfolio.risk_per_trade_pct = 0.015  # 1.5% risk per trade
                self.portfolio.atr_stop_multiplier = 1.8   # Tighter stops
                self.portfolio.atr_target_multiplier = 4.0  # Higher targets
                self.portfolio.trailing_activation_multiplier = 1.3
                self.portfolio.trailing_stop_multiplier = 0.75
                # Store config reference for stop loss/take profit calculations
                self.portfolio.config = self.config
                print("⚡ Aggressive profile applied to portfolio settings")

        # Adjust strategies based on mode
        if trading_mode == 'live':
            # Conservative strategies for live trading
            self.strategies = [
                ImprovedMovingAverageCrossover(5, 15),  # Slower signals
                EnhancedRSIStrategy(14, 30, 70),       # More conservative RSI
                BollingerBandsStrategy(20, 2),
            ]
            self.aggregator = EnhancedSignalAggregator(min_agreement=0.4)  # Higher agreement
            self.max_positions = min(max_positions, 10)  # Conservative position limit
            self.cooldown_minutes = 30  # Longer cooldown
        else:
            # Full strategies for paper/backtest
            self.strategies = [
                ImprovedMovingAverageCrossover(3, 10),
                EnhancedRSIStrategy(7, 25, 75),
                BollingerBandsStrategy(20, 2),
                ImprovedVolumeBreakoutStrategy(1.3, 0.001)
            ]
            # Adjust aggregator settings based on profile
            if trading_mode == 'paper' and self.config.get('trading_profile') == 'Aggressive':
                self.aggregator = EnhancedSignalAggregator(min_agreement=0.1)  # Lower agreement for aggressive
            else:
                self.aggregator = EnhancedSignalAggregator(min_agreement=0.4)
            # Apply profile-specific max positions for paper trading
            if trading_mode == 'paper' and 'max_positions' in self.config:
                self.max_positions = self.config['max_positions']
            else:
                self.max_positions = max_positions
            self.cooldown_minutes = 10
        
        self.symbols = []
        self.market_hours = MarketHours()
        self.position_cooldown = {}

        # Persistence helpers
        state_dir = self.config.get('state_dir')
        self.state_manager = TradingStateManager(state_dir)
        self.last_archive_day = None
        self.restored_state = False
        self.iteration_start = 0
        self.last_state_snapshot = None
        self.day_close_executed = None
        self._restore_saved_state()

        print(f"🎯 UNIFIED TRADING SYSTEM INITIALIZED")
        print(f"Mode: {trading_mode.upper()}")
        print(f"Strategies: {len(self.strategies)}")
        print(f"Max Positions: {self.max_positions}")

        # Additional risk controls
        self.stop_loss_cooldown_minutes = self.config.get('stop_loss_cooldown_minutes', max(self.cooldown_minutes * 2, 20))
        print(f"Cooldown after stop-loss: {self.stop_loss_cooldown_minutes} minutes")

    def add_symbols(self, symbols):
        """Add symbols for trading"""
        for symbol in symbols:
            s = symbol.strip().upper()
            if s and s not in self.symbols:
                self.symbols.append(s)

    @staticmethod
    def _normalize_fast_interval(interval: str) -> str:
        if not interval:
            return '5minute'
        interval = interval.lower().strip()
        mapping = {
            '5': '5minute', '5m': '5minute', '5min': '5minute', '5minute': '5minute',
            '10': '10minute', '10m': '10minute', '10min': '10minute', '10minute': '10minute',
            '15': '15minute', '15m': '15minute', '15min': '15minute', '15minute': '15minute',
            '30': '30minute', '30m': '30minute', '30min': '30minute', '30minute': '30minute',
            '60': '60minute', '60m': '60minute', '60min': '60minute', '1h': '60minute', '1hour': '60minute', '60minute': '60minute'
        }
        return mapping.get(interval, '5minute')

    @staticmethod
    def _interval_to_pandas(interval: str) -> str:
        return {
            '5minute': '5T',
            '10minute': '10T',
            '15minute': '15T',
            '30minute': '30T',
            '60minute': '60T'
        }.get(interval, '5T')


    def run_fast_backtest(self, interval="5minute", days=30):
        """One-pass backtest over historical bars; prints aggregate summary only."""
        interval = self._normalize_fast_interval(interval)
        pandas_interval = self._interval_to_pandas(interval)

        print("\n⚡ Running fast backtest (one-pass)…")
        start_time = time.time()
        trades_before = self.portfolio.trades_count

        min_conf = float(self.config.get('fast_min_confidence', 0.65))
        top_n = int(self.config.get('fast_top_n', 1))
        max_pos_cap = int(self.config.get('fast_max_positions', min(self.max_positions, 8)))

        df_map = {}
        for sym in self.symbols:
            try:
                df = self.dp.fetch_with_retry(sym, interval=interval, days=days)
                if df.empty:
                    continue
                idx = df.index
                if isinstance(idx, pd.DatetimeIndex) and idx.tz is not None:
                    try:
                        idx = idx.tz_convert('Asia/Kolkata').tz_localize(None)
                    except Exception:
                        try:
                            idx = idx.tz_localize(None)
                        except Exception:
                            pass
                    df.index = idx
                if isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.DatetimeIndex(df.index)
                for col in ("open", "high", "low", "close"):
                    if col not in df.columns:
                        raise ValueError("missing OHLC data")
                prev_close = df['close'].shift(1)
                tr = pd.concat([
                    (df['high'] - df['low']).abs(),
                    (df['high'] - prev_close).abs(),
                    (df['low'] - prev_close).abs()
                ], axis=1).max(axis=1)
                df['ATR'] = tr.rolling(14).mean()
                df_map[sym] = df
            except Exception:
                continue
        if not df_map:
            print("❌ No historical data available for fast backtest")
            return

        all_times = sorted({pd.Timestamp(ts) for df in df_map.values() for ts in df.index})
        if not all_times:
            print("❌ No timestamps found for fast backtest")
            return

        resampled_prices = {sym: df['close'].copy() for sym, df in df_map.items()}
        resampled_atr = {sym: df['ATR'].copy() for sym, df in df_map.items()}
        if interval != '5minute':
            try:
                resampled_prices = {sym: series.resample(pandas_interval).last().dropna() for sym, series in resampled_prices.items()}
                resampled_atr = {sym: series.resample(pandas_interval).last().dropna() for sym, series in resampled_atr.items()}
                all_times = sorted({pd.Timestamp(ts) for series in resampled_prices.values() for ts in series.index})
            except Exception as exc:
                print(f"⚠️ Resample failed ({exc}), falling back to raw interval")
                resampled_prices = {sym: df['close'] for sym, df in df_map.items()}
                resampled_atr = {sym: df['ATR'] for sym, df in df_map.items()}
        else:
            resampled_prices = {sym: df['close'] for sym, df in df_map.items()}
            resampled_atr = {sym: df['ATR'] for sym, df in df_map.items()}

        for ts in all_times:
            prices = {}
            atr_snapshot = {}
            for sym, series in resampled_prices.items():
                if ts in series.index:
                    try:
                        prices[sym] = float(series.loc[ts])
                        atr_val = resampled_atr.get(sym, pd.Series()).get(ts)
                        if atr_val is not None and not pd.isna(atr_val):
                            atr_snapshot[sym] = float(atr_val)
                    except Exception:
                        continue

            for sym, pos in list(self.portfolio.positions.items()):
                if sym not in prices:
                    continue
                cp = prices[sym]
                atr_val = atr_snapshot.get(sym)
                if atr_val and cp > pos['entry_price']:
                    gain = cp - pos['entry_price']
                    if gain >= atr_val * self.portfolio.trailing_activation_multiplier:
                        trailing_stop = cp - atr_val * self.portfolio.trailing_stop_multiplier
                        trailing_stop = max(trailing_stop, pos['entry_price'] * 1.001)
                        if trailing_stop > pos['stop_loss']:
                            pos['stop_loss'] = trailing_stop
                if cp <= pos.get('stop_loss', -1) or cp >= pos.get('take_profit', 10**12):
                    self.portfolio.execute_trade(sym, int(pos['shares']), cp, 'sell', ts, pos.get('confidence', 0.5), pos.get('sector', 'Other'))

            sell_queue = []
            buy_candidates = []
            for sym, df in df_map.items():
                if sym not in prices:
                    continue
                try:
                    upto = df.loc[:ts]
                except Exception:
                    continue
                if len(upto) < 50:
                    continue
                current_price = prices[sym]
                strategy_signals = []
                for strategy in self.strategies:
                    strategy_signals.append(strategy.generate_signals(upto, sym))
                aggregated = self.aggregator.aggregate_signals(strategy_signals, sym)
                conf = float(aggregated.get('confidence', 0.0) or 0.0)
                if aggregated['action'] == 'sell' and sym in self.portfolio.positions:
                    sell_queue.append(sym)
                elif aggregated['action'] == 'buy' and sym not in self.portfolio.positions and conf >= min_conf:
                    buy_candidates.append((sym, conf, current_price, atr_snapshot.get(sym)))

            for sym in sell_queue:
                cp = prices.get(sym)
                if cp is None:
                    continue
                shares = int(self.portfolio.positions[sym]['shares']) if sym in self.portfolio.positions else 0
                if shares > 0:
                    self.portfolio.execute_trade(sym, shares, cp, 'sell', ts, 0.5, self.get_sector(sym))

            buy_candidates.sort(key=lambda x: x[1], reverse=True)
            for sym, conf, cp, atr_val in buy_candidates[:top_n]:
                if len(self.portfolio.positions) >= min(max_pos_cap, self.max_positions):
                    break
                position_pct = self.portfolio.min_position_size
                if conf >= 0.7:
                    position_pct = self.portfolio.max_position_size
                elif conf >= 0.5:
                    position_pct = (self.portfolio.max_position_size + self.portfolio.min_position_size) / 2
                position_value = self.portfolio.cash * position_pct
                shares = int(position_value // cp)
                if shares > 0:
                    self.portfolio.execute_trade(sym, shares, cp, 'buy', ts, conf, self.get_sector(sym), atr=atr_val)

        last_prices = {sym: float(df.iloc[-1]['close']) for sym, df in df_map.items() if not df.empty}
        for sym, pos in list(self.portfolio.positions.items()):
            cp = last_prices.get(sym, pos['entry_price'])
            self.portfolio.execute_trade(sym, int(pos['shares']), cp, 'sell', all_times[-1], pos.get('confidence', 0.5), pos.get('sector', 'Other'))

        final_value = self.portfolio.calculate_total_value(last_prices)
        elapsed = time.time() - start_time

        trades = self.portfolio.trades_count - trades_before
        wins = getattr(self.portfolio, 'winning_trades', 0)
        win_rate = (wins / self.portfolio.trades_count * 100) if self.portfolio.trades_count else 0.0
        print("\n===== FAST BACKTEST SUMMARY =====")
        print(f"Symbols: {len(self.symbols)} | Bars: {len(all_times)} | Trades: {trades}")
        print(f"Final Portfolio Value: ₹{final_value:,.2f}")
        print(f"Total P&L: ₹{self.portfolio.total_pnl:,.2f} | Win rate: {win_rate:.1f}%")
        print(f"Best Trade: ₹{self.portfolio.best_trade:,.2f} | Worst Trade: ₹{self.portfolio.worst_trade:,.2f}")
        print(f"Elapsed: {elapsed:.2f}s")

        summary = {
            'timestamp': datetime.now().isoformat(),
            'mode': 'fast_backtest',
            'interval': interval,
            'days': days,
            'symbols': len(self.symbols),
            'bars': len(all_times),
            'trades': trades,
            'win_rate': win_rate,
            'final_value': final_value,
            'total_pnl': self.portfolio.total_pnl,
            'best_trade': self.portfolio.best_trade,
            'worst_trade': self.portfolio.worst_trade,
            'settings': {
                'min_confidence': min_conf,
                'top_n': top_n,
                'max_positions': max_pos_cap
            }
        }
        results_dir = Path('backtest_results')
        results_dir.mkdir(exist_ok=True)
        summary_path = results_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        summary_path.write_text(json.dumps(summary, indent=2))
        print(f"Summary saved to {summary_path}")

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        if df is None or df.empty or len(df) < period + 2:
            return 0.0
        high = df['high']
        low = df['low']
        close = df['close']
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(period).mean().iloc[-1]
        if pd.isna(atr):
            atr = true_range.tail(period).mean()
        return float(atr) if atr and not np.isnan(atr) else 0.0

    def _restore_saved_state(self):
        saved_state = self.state_manager.load_state()
        if not saved_state:
            print("💾 No saved trading state found – starting fresh.")
            return

        saved_mode = saved_state.get('mode')
        if saved_mode and saved_mode != self.trading_mode:
            print(f"⚠️ Saved trading state is for mode '{saved_mode}', current mode '{self.trading_mode}'. Ignoring saved data.")
            return

        try:
            self.portfolio.load_from_dict(saved_state.get('portfolio', {}))
            self.iteration_start = int(saved_state.get('iteration', 0))
            self.last_archive_day = saved_state.get('last_archive_day')
            self.day_close_executed = saved_state.get('day_close_executed')

            cooldowns = {}
            now = datetime.now()
            for symbol, ts in saved_state.get('position_cooldown', {}).items():
                try:
                    dt_obj = datetime.fromisoformat(ts)
                    if dt_obj > now:
                        cooldowns[symbol] = dt_obj
                except Exception:
                    continue
            self.position_cooldown.update(cooldowns)

            self.restored_state = True
            self.last_state_snapshot = saved_state
            print(
                f"💾 Restored trading state: iteration {self.iteration_start}, "
                f"cash ₹{self.portfolio.cash:,.2f}, open positions {len(self.portfolio.positions)}"
            )
        except Exception as exc:
            print(f"⚠️ Failed to apply saved trading state: {exc}")
            self.iteration_start = 0
            self.last_archive_day = None
            self.restored_state = False

    def _serialize_cooldowns(self):
        serialized = {}
        for symbol, dt_obj in self.position_cooldown.items():
            if isinstance(dt_obj, datetime):
                serialized[symbol] = dt_obj.isoformat()
        return serialized

    def _build_state_snapshot(self, iteration, total_value, price_map):
        trading_day = self.state_manager.current_trading_day()
        return {
            'mode': self.trading_mode,
            'iteration': int(iteration),
            'trading_day': trading_day,
            'last_update': datetime.now().isoformat(),
            'portfolio': self.portfolio.to_dict(),
            'position_cooldown': self._serialize_cooldowns(),
            'total_value': float(total_value),
            'last_prices': {symbol: float(price) for symbol, price in (price_map or {}).items()},
            'last_archive_day': self.last_archive_day,
            'day_close_executed': self.day_close_executed
        }

    def _persist_state(self, iteration, total_value, price_map):
        state = self._build_state_snapshot(iteration, total_value, price_map)
        now_ist = datetime.now(self.state_manager.ist)
        trading_day = state['trading_day']

        if now_ist.time() >= self.market_hours.market_close:
            if self.last_archive_day != trading_day:
                self.state_manager.archive_state(state)
                self.last_archive_day = trading_day
                state['last_archive_day'] = trading_day
                print(f"💾 Archived trading state for {trading_day}")
        self.state_manager.save_state(state)
        self.last_state_snapshot = state

    def _broadcast_restored_state(self):
        if not self.restored_state:
            return

        snapshot = self.last_state_snapshot or {}
        price_map = snapshot.get('last_prices', {})
        total_value = snapshot.get('total_value')
        if total_value is None:
            total_value = self.portfolio.calculate_total_value(price_map)

        pnl = total_value - self.portfolio.initial_cash
        win_rate = 0.0
        if self.portfolio.trades_count > 0:
            win_rate = (self.portfolio.winning_trades / self.portfolio.trades_count) * 100

        print(
            f"🔁 Resuming session from iteration {self.iteration_start} | "
            f"Portfolio ₹{total_value:,.2f} | Cash ₹{self.portfolio.cash:,.2f} | "
            f"Positions {len(self.portfolio.positions)}"
        )

        if self.dashboard:
            positions_payload = {}
            for symbol, pos in self.portfolio.positions.items():
                current_price = price_map.get(symbol, pos["entry_price"])
                unrealized_pnl = (current_price - pos["entry_price"]) * pos["shares"]
                positions_payload[symbol] = {
                    "shares": pos["shares"],
                    "entry_price": pos["entry_price"],
                    "current_price": current_price,
                    "unrealized_pnl": unrealized_pnl,
                    "sector": pos.get("sector", "Other")
                }

            self.dashboard.send_portfolio_update(
                total_value=total_value,
                cash=self.portfolio.cash,
                positions_count=len(self.portfolio.positions),
                total_pnl=pnl,
                positions=positions_payload
            )

            if self.portfolio.trades_count > 0:
                self.dashboard.send_performance_update(
                    trades_count=self.portfolio.trades_count,
                    win_rate=win_rate,
                    total_pnl=self.portfolio.total_pnl,
                    best_trade=self.portfolio.best_trade,
                    worst_trade=self.portfolio.worst_trade
                )

            self.dashboard.send_system_status(True, self.iteration_start, "resumed")

    def _close_positions_for_day(self, price_map, iteration, current_day):
        if self.day_close_executed == current_day:
            return False

        had_positions = bool(self.portfolio.positions)

        now_ist = datetime.now(self.state_manager.ist)
        close_time = now_ist.replace(
            hour=self.market_hours.market_close.hour,
            minute=self.market_hours.market_close.minute,
            second=0,
            microsecond=0
        )
        if now_ist >= close_time:
            trigger = "market_close"
        else:
            trigger = "scheduled"

        if had_positions:
            print("\n🔔 Market close approaching – unwinding open positions...")
            for symbol, position in list(self.portfolio.positions.items()):
                shares = int(position["shares"])
                if shares <= 0:
                    continue

                current_price = price_map.get(symbol)
                if current_price is None:
                    try:
                        df = self.dp.fetch_with_retry(symbol, interval="5minute", days=1)
                        if not df.empty:
                            current_price = float(df["close"].iloc[-1])
                    except Exception:
                        current_price = None

                if current_price is None or current_price <= 0:
                    current_price = position.get("entry_price", 0)

                trade = self.portfolio.execute_trade(
                    symbol,
                    shares,
                    current_price,
                    "sell",
                    datetime.now(),
                    position.get("confidence", 0.5),
                    position.get("sector", "Other")
                )
                if trade:
                    trade['iteration'] = iteration
                    trade['reason'] = 'day_end_close'
                    trade['trigger'] = trigger
                    self.state_manager.log_trade(trade, trading_day=current_day)

        self.day_close_executed = current_day
        total_value = self.portfolio.calculate_total_value(price_map)
        pnl = total_value - self.portfolio.initial_cash
        win_rate = 0.0
        if self.portfolio.trades_count > 0:
            win_rate = (self.portfolio.winning_trades / self.portfolio.trades_count) * 100

        summary = {
            'trading_day': current_day,
            'closed_at': datetime.now().isoformat(),
            'total_value': total_value,
            'cash': self.portfolio.cash,
            'open_positions': len(self.portfolio.positions),
            'trades_count': self.portfolio.trades_count,
            'win_rate': win_rate,
            'total_pnl': self.portfolio.total_pnl,
            'best_trade': self.portfolio.best_trade,
            'worst_trade': self.portfolio.worst_trade
        }
        self.state_manager.write_daily_summary(current_day, summary)

        if self.dashboard:
            self.dashboard.send_portfolio_update(
                total_value=total_value,
                cash=self.portfolio.cash,
                positions_count=len(self.portfolio.positions),
                total_pnl=pnl,
                positions={}
            )
            self.dashboard.send_system_status(True, iteration, "day_end")

        return had_positions
    def get_sector(self, symbol):
        """Get sector for symbol"""
        for sector, symbols in SECTOR_GROUPS.items():
            if symbol in symbols:
                return sector
        return "Other"
    
    def scan_batch(self, batch, interval, batch_num, total_batches):
        """Scan a batch of symbols for signals"""
        signals = {}
        prices = {}
        print(f"\n  Batch {batch_num}/{total_batches}: {', '.join(batch[:3])}...")
        
        for symbol in batch:
            try:
                df = self.dp.fetch_with_retry(symbol, interval=interval, days=5)
                if df.empty or len(df) < 50:
                    continue
                
                current_price = float(df["close"].iloc[-1])
                prices[symbol] = current_price
                
                # Generate signals from all strategies
                strategy_signals = []
                for strategy in self.strategies:
                    sig = strategy.generate_signals(df, symbol)
                    strategy_signals.append(sig)
                
                # Aggregate signals
                aggregated = self.aggregator.aggregate_signals(strategy_signals, symbol)
                
                if aggregated['action'] != 'hold':
                    # Disable trend filter for aggressive profile to allow more trades
                    trend_filter_enabled = self.config.get('trend_filter_enabled', self.trading_mode != 'backtest')
                    if trend_filter_enabled and not (self.trading_mode == 'paper' and self.config.get('trading_profile') == 'Aggressive'):
                        ema_fast = df['close'].ewm(span=20, adjust=False).mean().iloc[-1]
                        ema_slow = df['close'].ewm(span=50, adjust=False).mean().iloc[-1]
                        if np.isnan(ema_fast) or np.isnan(ema_slow):
                            continue
                        downtrend = current_price < ema_slow and ema_fast < ema_slow
                        uptrend = current_price > ema_slow and ema_fast > ema_slow

                        if aggregated['action'] == 'sell' and not downtrend:
                            continue
                        if aggregated['action'] == 'buy' and not uptrend and aggregated['confidence'] < 0.6:
                            continue

                    aggregated['atr'] = self._calculate_atr(df)
                    aggregated['last_close'] = current_price
                    signals[symbol] = aggregated
                    sector = self.get_sector(symbol)
                    print(f"    {symbol} ({sector}): {aggregated['action'].upper()} @ ₹{current_price:.2f} ({aggregated['confidence']:.1%})")
                    
                    # Send signal to dashboard
                    if self.dashboard:
                        self.dashboard.send_signal(
                            symbol=symbol,
                            action=aggregated['action'],
                            confidence=aggregated['confidence'],
                            price=current_price,
                            sector=sector,
                            reasons=aggregated.get('reasons', [])
                        )
            except Exception:
                continue
        
        return signals, prices
    
    def run_nifty50_trading(self, interval="5minute", check_interval=30):
        """Run the trading system"""
        print("\n" + "="*60)
        print(f"UNIFIED NIFTY 50 TRADING SYSTEM - {self.trading_mode.upper()} MODE")
        print("="*60)
        print(f"Capital: ₹{self.portfolio.initial_cash:,.2f}")
        print(f"Symbols: {len(self.symbols)} stocks")
        print(f"Max Positions: {self.max_positions}")
        print(f"Strategies: {len(self.strategies)}")
        
        if self.dashboard and self.dashboard.is_connected:
            print(f"📊 Dashboard: Connected to {self.dashboard.base_url}")
        else:
            print("⚠️ Dashboard: Not connected")
        
        print(f"\nStarting {self.trading_mode} trading...\n")
        iteration = self.iteration_start

        if self.restored_state:
            self._broadcast_restored_state()

        try:
            while True:
                iteration += 1
                current_day = self.state_manager.current_trading_day()
                if self.day_close_executed and self.day_close_executed != current_day:
                    self.day_close_executed = None

                now_ist = datetime.now(self.state_manager.ist)
                close_dt = now_ist.replace(
                    hour=self.market_hours.market_close.hour,
                    minute=self.market_hours.market_close.minute,
                    second=0,
                    microsecond=0
                )
                time_to_close = close_dt - now_ist
                
                # Send system status to dashboard
                if self.dashboard:
                    self.dashboard.send_system_status(True, iteration, "scanning")
                
                print(f"\n{'='*60}")
                print(f"Iteration {iteration} - {datetime.now().strftime('%H:%M:%S')}")
                print(f"{'='*60}")
                
                # Check if we should bypass market hours for testing
                bypass_market_hours = self.config.get('bypass_market_hours', False)

                if self.trading_mode != 'backtest' and not self.market_hours.is_market_open() and not bypass_market_hours:
                    # Debug market hours
                    now_ist = datetime.now(self.market_hours.ist)
                    current_time = now_ist.time()
                    print(f"Market closed. Current IST time: {now_ist.strftime('%H:%M:%S')} (weekday: {now_ist.weekday()})")
                    print(f"Market hours: {self.market_hours.market_open.strftime('%H:%M')} to {self.market_hours.market_close.strftime('%H:%M')}")
                    if bypass_market_hours:
                        print("⚠️ Bypassing market hours for testing...")
                    if self.dashboard:
                        self.dashboard.send_system_status(True, iteration, "market_closed")
                    total_value = self.portfolio.calculate_total_value()
                    self._persist_state(iteration, total_value, {})
                    time.sleep(300)
                    continue
                
                # Scan in batches
                batch_size = 10
                batches = [self.symbols[i:i+batch_size] for i in range(0, len(self.symbols), batch_size)]
                all_signals = {}
                all_prices = {}
                
                for i, batch in enumerate(batches, 1):
                    batch_signals, batch_prices = self.scan_batch(batch, interval, i, len(batches))
                    all_signals.update(batch_signals)
                    all_prices.update(batch_prices)
                    time.sleep(0.3)
                
                if all_signals:
                    buy_count = sum(1 for s in all_signals.values() if s['action'] == 'buy')
                    sell_count = sum(1 for s in all_signals.values() if s['action'] == 'sell')
                    print(f"\n📊 Signal Summary: {len(all_signals)} total | {buy_count} BUY | {sell_count} SELL")
                
                # Get profile settings for paper trading
                min_confidence = self.config.get('min_confidence', 0.45)
                top_n = self.config.get('top_n', 1)

                # Adjust for aggressive profile - lower confidence threshold
                if self.trading_mode == 'paper' and self.config.get('trading_profile') == 'Aggressive':
                    min_confidence = min(min_confidence, 0.4)  # Lower threshold for aggressive mode

                # Process signals (sorted by confidence)
                sorted_signals = sorted(all_signals.items(), key=lambda x: x[1]['confidence'], reverse=True)

                # Apply top_n limit for paper trading with profile
                if self.trading_mode == 'paper' and top_n > 1:
                    sorted_signals = sorted_signals[:top_n]

                for symbol, signal in sorted_signals:
                    price = all_prices.get(symbol)
                    if price is None:
                        continue

                    if symbol in self.position_cooldown and datetime.now() < self.position_cooldown[symbol]:
                        continue

                    sector = self.get_sector(symbol)

                    if signal['confidence'] < min_confidence:
                        continue

                    if signal['action'] == 'buy' and symbol not in self.portfolio.positions:
                        can_open_more = len(self.portfolio.positions) < self.max_positions

                        if can_open_more:
                            if self.trading_mode != 'backtest' and time_to_close <= timedelta(minutes=20):
                                continue
                            # Position sizing based on confidence
                            if signal['confidence'] >= 0.7:
                                position_pct = self.portfolio.max_position_size
                            elif signal['confidence'] >= 0.5:
                                position_pct = (self.portfolio.max_position_size + self.portfolio.min_position_size) / 2
                            else:
                                position_pct = self.portfolio.min_position_size

                            position_value = self.portfolio.cash * position_pct
                            shares = int(position_value // price)

                            if shares > 0:
                                trade = self.portfolio.execute_trade(
                                    symbol,
                                    shares,
                                    price,
                                    "buy",
                                    datetime.now(),
                                    signal['confidence'],
                                    sector,
                                    atr=signal.get('atr')
                                )
                                if trade:
                                    trade['iteration'] = iteration
                                    trade['reason'] = 'signal_buy'
                                    self.state_manager.log_trade(trade, trading_day=current_day)
                    
                    elif signal['action'] == 'sell' and symbol in self.portfolio.positions:
                        shares = int(self.portfolio.positions[symbol]["shares"])
                        trade = self.portfolio.execute_trade(
                            symbol, shares, price, "sell", datetime.now(), signal['confidence'], sector
                        )
                        if trade:
                            trade['iteration'] = iteration
                            trade['reason'] = 'signal_sell'
                            self.state_manager.log_trade(trade, trading_day=current_day)
                        self.position_cooldown[symbol] = datetime.now() + timedelta(minutes=self.cooldown_minutes)
                
                # Check for stop-loss and take-profit
                for symbol, position in list(self.portfolio.positions.items()):
                    if symbol in all_prices:
                        current_price = all_prices[symbol]
                        atr_value = position.get("atr")
                        if atr_value and atr_value > 0 and current_price > position["entry_price"]:
                            gain = current_price - position["entry_price"]
                            if gain >= atr_value * self.portfolio.trailing_activation_multiplier:
                                trailing_stop = current_price - atr_value * self.portfolio.trailing_stop_multiplier
                                trailing_stop = max(trailing_stop, position["entry_price"] * 1.001)
                                if trailing_stop > position["stop_loss"]:
                                    position["stop_loss"] = trailing_stop
                        if current_price <= position["stop_loss"] or current_price >= position["take_profit"]:
                            shares = int(position["shares"])
                            reason = "Stop Loss" if current_price <= position["stop_loss"] else "Take Profit"
                            print(f"⚡ {reason} triggered for {symbol}")
                            sector = position.get("sector", "Other")
                            trade = self.portfolio.execute_trade(
                                symbol,
                                shares,
                                current_price,
                                "sell",
                                datetime.now(),
                                position["confidence"],
                                sector
                            )
                            if trade:
                                trade['iteration'] = iteration
                                trade['reason'] = 'risk_exit'
                                trade['trigger'] = 'stop_loss' if reason == 'Stop Loss' else 'take_profit'
                                self.state_manager.log_trade(trade, trading_day=current_day)
                                if reason == 'Stop Loss':
                                    self.position_cooldown[symbol] = datetime.now() + timedelta(minutes=self.stop_loss_cooldown_minutes)

                if self.trading_mode != 'backtest' and time_to_close <= timedelta(minutes=5) and time_to_close > timedelta(minutes=-60):
                    if self._close_positions_for_day(all_prices, iteration, current_day):
                        all_prices = dict(all_prices)

                # Calculate portfolio value
                total_value = self.portfolio.calculate_total_value(all_prices)
                
                pnl = total_value - self.portfolio.initial_cash
                pnl_pct = (pnl / self.portfolio.initial_cash) * 100 if self.portfolio.initial_cash else 0
                
                # Print portfolio status
                print(f"\n💰 Portfolio Status:")
                print(f"  Total Value: ₹{total_value:,.2f} ({pnl_pct:+.2f}%)")
                print(f"  Cash Available: ₹{self.portfolio.cash:,.2f}")
                print(f"  Positions: {len(self.portfolio.positions)}/{self.max_positions}")
                
                # Send portfolio update to dashboard
                if self.dashboard:
                    # Prepare current positions for dashboard
                    dashboard_positions = {}
                    for symbol, pos in self.portfolio.positions.items():
                        current_price = all_prices.get(symbol, pos["entry_price"])
                        unrealized_pnl = (current_price - pos["entry_price"]) * pos["shares"]
                        dashboard_positions[symbol] = {
                            "shares": pos["shares"],
                            "entry_price": pos["entry_price"],
                            "current_price": current_price,
                            "unrealized_pnl": unrealized_pnl,
                            "sector": pos.get("sector", "Other")
                        }
                    
                    self.dashboard.send_portfolio_update(
                        total_value=total_value,
                        cash=self.portfolio.cash,
                        positions_count=len(self.portfolio.positions),
                        total_pnl=pnl,
                        positions=dashboard_positions
                    )
                
                if self.portfolio.trades_count > 0:
                    win_rate = (self.portfolio.winning_trades / self.portfolio.trades_count) * 100
                    print(f"\n📈 Performance:")
                    print(f"  Total Trades: {self.portfolio.trades_count}")
                    print(f"  Win Rate: {win_rate:.1f}%")
                    print(f"  Total P&L: ₹{self.portfolio.total_pnl:,.2f}")
                    print(f"  Best Trade: ₹{self.portfolio.best_trade:,.2f}")
                    print(f"  Worst Trade: ₹{self.portfolio.worst_trade:,.2f}")
                    
                    # Send performance update to dashboard
                    if self.dashboard:
                        self.dashboard.send_performance_update(
                            trades_count=self.portfolio.trades_count,
                            win_rate=win_rate,
                            total_pnl=self.portfolio.total_pnl,
                            best_trade=self.portfolio.best_trade,
                            worst_trade=self.portfolio.worst_trade
                        )
                
                self._persist_state(iteration, total_value, all_prices)

                print(f"\nNext scan in {check_interval} seconds...")
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            print("\n\nStopped by user")
            total_value = self.portfolio.calculate_total_value()
            self._persist_state(iteration, total_value, {})
            if self.dashboard:
                self.dashboard.send_system_status(False, iteration, "stopped")

# ============================================================================
# MODE SELECTION AND LAUNCHER FUNCTIONS
# ============================================================================
def ensure_correct_directory():
    """Ensure we're running from the correct directory"""
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    print(f"📁 Working directory: {os.getcwd()}")

def start_dashboard():
    """Start dashboard server"""
    print("📊 Starting Dashboard...")
    
    try:
        dashboard_process = subprocess.Popen(
            [sys.executable, "enhanced_dashboard_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        time.sleep(3)  # Wait for server to start
        
        try:
            webbrowser.open("http://localhost:5173")
            print("✅ Dashboard started at: http://localhost:5173")
        except:
            print("��� Dashboard started at: http://localhost:5173 (open manually)")
        
        return dashboard_process
    except Exception as e:
        print(f"⚠️ Dashboard failed to start: {e}")
        return None

def run_trading_system_directly(trading_mode, config):
    """Run the trading system directly without subprocess"""
    print(f"🎯 STARTING {trading_mode.upper()} TRADING SYSTEM")
    print("="*60)
    
    # Initialize dashboard
    print("\n📊 Connecting to Dashboard...")
    dashboard = DashboardConnector(base_url="http://localhost:5173")
    
    if dashboard.is_connected:
        print("✅ Dashboard connected")
        dashboard.send_system_status(True, 0, f"{trading_mode}_mode")
    else:
        print("⚠️ Dashboard not connected")
    
    # Initialize Zerodha connection
    print("\n🔐 Setting up Zerodha Authentication...")
    API_KEY = "b0umi99jeas93od0"
    API_SECRET = "8jyer3zt5stm0udso2ir6yqclefot475"
    
    kite = None
    try:
        token_manager = ZerodhaTokenManager(API_KEY, API_SECRET)
        kite = token_manager.get_authenticated_kite()
        
        if kite:
            print("✅ Zerodha authentication successful")
            
            if trading_mode == 'live':
                # Verify account for live trading
                profile = kite.profile()
                margins = kite.margins()
                available_cash = margins.get('equity', {}).get('available', {}).get('cash', 0)
                
                print(f"👤 Account: {profile.get('user_name')}")
                print(f"💰 Available Cash: ₹{available_cash:,.2f}")
                
                max_capital = config.get('max_capital', 100000)
                if available_cash < max_capital:
                    print(f"⚠️ Warning: Available cash (₹{available_cash:,.2f}) < Max capital (₹{max_capital:,.2f})")
        else:
            print("⚠️ Zerodha authentication failed, using yfinance fallback")
        
    except Exception as e:
        print(f"⚠️ Authentication error: {e}")
        print("📊 Using yfinance for market data")
    
    # Load instruments
    print("\n📋 Loading instruments...")
    instruments = {}
    if kite:
        try:
            dump = kite.instruments("NSE")
            df = pd.DataFrame(dump)
            instruments = dict(zip(df["tradingsymbol"], df["instrument_token"]))
            print(f"✅ Loaded {len(instruments)} instruments")
        except Exception as e:
            print(f"⚠️ Failed to load instruments: {e}")
    
    # Create data provider
    dp = DataProvider(kite=kite, instruments_map=instruments, use_yf_fallback=True)
    
    # Get initial capital from config
    initial_cash = config.get('initial_capital', config.get('virtual_capital', config.get('max_capital', 1000000)))
    
    # Create unified trading system
    system = UnifiedTradingSystem(
        data_provider=dp,
        kite=kite,
        initial_cash=initial_cash,
        max_positions=25,
        dashboard=dashboard,
        trading_mode=trading_mode,
        config=config
    )
    
    # Symbol selection based on mode
    if trading_mode == 'live':
        # Conservative symbols for live trading
        conservative_symbols = [
            "HDFCBANK", "ICICIBANK", "TCS", "INFY", "RELIANCE",
            "SBIN", "KOTAKBANK", "WIPRO", "HCLTECH", "ONGC"
        ]
        system.add_symbols(conservative_symbols)
        print(f"✅ Added {len(conservative_symbols)} conservative symbols for live trading")
    else:
        # Full symbol set for paper/backtest
        system.add_symbols(NIFTY_50_SYMBOLS[:30])
        print(f"✅ Added top 30 NIFTY stocks")
    
    # Trading parameters
    interval = config.get('fast_interval', '5minute') if config.get('fast_backtest') else '5minute'
    check_interval = 60 if trading_mode == 'live' else 30
    
    print(f"\n🚀 STARTING {trading_mode.upper()} TRADING")
    print("="*50)
    print(f"✅ Mode: {trading_mode.upper()}")
    print(f"✅ Initial Capital: ₹{initial_cash:,.2f}")
    print(f"✅ Symbols: {len(system.symbols)} stocks")
    print(f"✅ Max Positions: {system.max_positions}")
    print(f"✅ Check Interval: {check_interval}s")
    print(f"✅ Dashboard: {'Connected' if dashboard.is_connected else 'Offline'}")
    
    if dashboard.is_connected:
        print(f"📊 Monitor at: http://localhost:5173")
    
    mode_warnings = {
        'live': "🔴 LIVE TRADING - REAL MONEY AT RISK!",
        'paper': "📝 PAPER TRADING - Safe Learning Environment!",
        'backtest': "📊 BACKTESTING - Historical Analysis!"
    }
    
    print(f"\n{mode_warnings.get(trading_mode, '')}")
    
    try:
        if trading_mode == 'backtest' and config.get('fast_backtest'):
            # Derive days span from config dates if available
            days_span = 30
            try:
                if 'start_date' in config and 'end_date' in config:
                    sd = datetime.strptime(config['start_date'], '%Y-%m-%d')
                    ed = datetime.strptime(config['end_date'], '%Y-%m-%d')
                    days_span = max(1, (ed - sd).days)
            except Exception:
                pass
            system.run_fast_backtest(interval=interval, days=days_span)
        else:
            system.run_nifty50_trading(interval=interval, check_interval=check_interval)
    except KeyboardInterrupt:
        print(f"\n🛑 {trading_mode.upper()} trading stopped by user")
        
        if system.portfolio.positions:
            print(f"\n⚠️ You have {len(system.portfolio.positions)} open positions:")
            for symbol, pos in system.portfolio.positions.items():
                print(f"   {symbol}: {pos['shares']} shares @ ₹{pos['entry_price']:.2f}")
            
            if trading_mode == 'live':
                print("💡 Consider closing positions manually if needed")

def run_paper_trading():
    """Run paper trading mode"""
    print("\n📝 PAPER TRADING MODE")
    print("="*50)
    print("✅ Safe simulation with real market data")
    print("✅ No financial risk")
    print("✅ Perfect for testing strategies")
    print("✅ Virtual capital: ₹10,00,000")

    # Ask for trading profile
    try:
        profile = input("Select trading profile [1=Quality, 2=Balanced, 3=Aggressive]: ").strip() or '1'
    except Exception:
        profile = '1'

    # Configure profile settings
    if profile == '3':
        # Aggressive profile settings
        min_confidence = 0.69
        top_n = 4
        max_positions = 25
        stop_loss_pct = 0.02  # 2% stop loss
        take_profit_pct = 0.12  # 12% take profit
        profile_name = 'Aggressive'
        print("⚡ Aggressive Profile Selected:")
        print(f"   • Min Confidence: {min_confidence} (Lowered for more trades)")
        print(f"   • Top N Signals: {top_n}")
        print(f"   • Max Positions: {max_positions}")
        print(f"   • Stop Loss: {stop_loss_pct:.0%}")
        print(f"   • Take Profit: {take_profit_pct:.0%}")
        print(f"   • Signal Agreement: 10% (vs 40% for other profiles)")
        print(f"   • Trend Filter: Disabled (allows more opportunities)")
    elif profile == '2':
        # Balanced profile settings
        min_confidence = 0.6
        top_n = 2
        max_positions = 15
        stop_loss_pct = 0.05  # 5% stop loss
        take_profit_pct = 0.12  # 12% take profit
        profile_name = 'Balanced'
        print("⚖️ Balanced Profile Selected:")
        print(f"   • Min Confidence: {min_confidence}")
        print(f"   • Top N Signals: {top_n}")
        print(f"   • Max Positions: {max_positions}")
        print(f"   • Stop Loss: {stop_loss_pct:.0%}")
        print(f"   • Take Profit: {take_profit_pct:.0%}")
    else:
        # Quality profile settings (default)
        min_confidence = 0.55
        top_n = 1
        max_positions = 10
        stop_loss_pct = 0.03  # 3% stop loss
        take_profit_pct = 0.08  # 8% take profit
        profile_name = 'Quality'
        print("🎯 Quality Profile Selected:")
        print(f"   • Min Confidence: {min_confidence}")
        print(f"   • Top N Signals: {top_n}")
        print(f"   • Max Positions: {max_positions}")
        print(f"   • Stop Loss: {stop_loss_pct:.0%}")
        print(f"   • Take Profit: {take_profit_pct:.0%}")

    # Start dashboard
    dashboard_process = start_dashboard()

    # Configuration for paper trading
    config = {
        'virtual_capital': 1000000,
        'use_real_data': True,
        'simulate_trades': True,
        'live_trading': False,
        'paper_trading': True,
        'trading_profile': profile_name,
        'min_confidence': min_confidence,
        'top_n': top_n,
        'max_positions': max_positions,
        'stop_loss_pct': stop_loss_pct,
        'take_profit_pct': take_profit_pct
    }
    
    print("\n🚀 Starting Paper Trading System...")
    
    try:
        # Run the trading system directly
        run_trading_system_directly('paper', config)
        
    except KeyboardInterrupt:
        print("\n🛑 Paper trading stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if dashboard_process:
            dashboard_process.terminate()

def run_live_trading():
    """Run live trading mode"""
    print("\n🔴 LIVE TRADING MODE")
    print("="*50)
    print("⚠️  WARNING: REAL MONEY WILL BE USED!")
    print("⚠️  Actual trades will be executed!")
    print("⚠️  You can lose real money!")
    
    # Final confirmation
    print("\n" + "���" * 30)
    confirm = input("Type 'START LIVE TRADING' to proceed with real money: ").strip()
    if confirm != "START LIVE TRADING":
        print("❌ Live trading cancelled")
        return
    
    # Get trading parameters
    try:
        max_capital = float(input("Maximum capital to use (₹) [100000]: ").strip() or "100000")
        max_position = float(input("Max position size (%) [10]: ").strip() or "10") / 100
    except:
        max_capital = 100000
        max_position = 0.10
    
    # Start dashboard
    dashboard_process = start_dashboard()
    
    # Configuration for live trading
    config = {
        'max_capital': max_capital,
        'max_position_size': max_position,
        'stop_loss': 0.05,
        'order_type': 'MARKET',
        'live_trading': True,
        'paper_trading': False
    }
    
    print(f"\n🔴 Starting Live Trading System...")
    print(f"💰 Max Capital: ₹{max_capital:,.2f}")
    print(f"📊 Max Position: {max_position:.1%}")
    
    try:
        # Run the trading system directly
        run_trading_system_directly('live', config)
        
    except KeyboardInterrupt:
        print("\n🛑 Live trading stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if dashboard_process:
            dashboard_process.terminate()

def run_backtesting():
    """Run backtesting mode"""
    print("\n📊 BACKTESTING MODE")
    print("="*50)
    print("⚡ Fast strategy testing on historical data")
    print("📈 Comprehensive performance analytics")
    
    # Get backtesting parameters
    try:
        days_back = int(input("Days of history to test [30]: ").strip() or "30")
        initial_capital = float(input("Initial capital (₹) [1000000]: ").strip() or "1000000")
    except:
        days_back = 30
        initial_capital = 1000000
    
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    # Start dashboard (optional for backtesting)
    dashboard_process = start_dashboard()
    
    # Configuration for backtesting
    config = {
        'start_date': start_date,
        'end_date': end_date,
        'initial_capital': initial_capital,
        'historical_data': True,
        'live_trading': False,
        'paper_trading': False
    }
    
    # Ask for fast backtest mode
    try:
        fast = input("Run fast backtest (one-pass, summary only)? [y/N]: ").strip().lower() == 'y'
    except Exception:
        fast = False
    if fast:
        config['fast_backtest'] = True
        interval_choice = input("Fast backtest interval [5minute]: ").strip()
        config['fast_interval'] = UnifiedTradingSystem._normalize_fast_interval(interval_choice)
        try:
            profile = input("Select fast profile [1=Quality, 2=Balanced, 3=Aggressive]: ").strip() or '1'
        except Exception:
            profile = '1'
        if profile == '3':
            config['fast_min_confidence'] = 0.69
            config['fast_top_n'] = 4
            config['fast_max_positions'] = 25
            config['stop_loss'] = 0.02 # 7% stop loss
            config['take_profit'] = 0.25# 12% take profit
            profile_name = 'Aggressive'
        elif profile == '2':
            config['fast_min_confidence'] = 0.6
            config['fast_top_n'] = 2
            config['fast_max_positions'] = 10
            config['stop_loss'] = 0.05  # 5% stop loss
            config['take_profit'] = 0.08 # 8% take profit
            profile_name = 'Balanced'
        else:
            config['fast_min_confidence'] = 0.55
            config['fast_top_n'] = 1
            config['fast_max_positions'] = 8
            config['stop_loss'] = 0.03  # 3% stop loss
            config['take_profit'] = 0.05 # 5% take profit
            profile_name = 'Quality'
        print(
            f"⚙️ Fast settings ({profile_name}): interval={config['fast_interval']}, "
            f"min_conf={config['fast_min_confidence']}, top_n={config['fast_top_n']}, "
            f"max_positions={config['fast_max_positions']}"
            f"sl={config['stop_loss']:.0%}, tp={config['take_profit']:.0%}"
        )
    else:
        config['fast_backtest'] = False
    
    print(f"\n📊 Starting Backtesting...")
    print(f"📅 Period: {start_date} to {end_date}")
    print(f"💰 Initial Capital: ₹{initial_capital:,.2f}")
    
    try:
        # Run the trading system directly
        run_trading_system_directly('backtest', config)
        
    except KeyboardInterrupt:
        print("\n🛑 Backtesting stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if dashboard_process:
            dashboard_process.terminate()

def main():
    # Ensure we're in the correct directory
    ensure_correct_directory()
    
    print("🎯 ENHANCED NIFTY 50 TRADING SYSTEM")
    print("="*60)
    print("🚀 All improvements integrated for maximum profits!")
    print("📊 Dashboard integration with real-time monitoring")
    print("🔧 Enhanced token management and error handling")
    print("="*60)
    print()
    print("Select Trading Mode:")
    print("1. 📝 Paper Trading (Safe Simulation)")
    print("2. 🔴 Live Trading (Real Money)")  
    print("3. 📊 Backtesting (Historical Analysis)")
    print("="*60)
    
    while True:
        try:
            choice = input("Select mode (1/2/3): ").strip()
            
            if choice == "1":
                run_paper_trading()
                break
            elif choice == "2":
                run_live_trading()
                break
            elif choice == "3":
                run_backtesting()
                break
            else:
                print("❌ Please enter 1, 2, or 3")
                
        except KeyboardInterrupt:
            print("\n🛑 Cancelled by user")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            break

def test_aggressive_profile():
    """Test function to verify aggressive profile implementation"""
    print("🧪 Testing Aggressive Profile Implementation")
    print("="*50)

    # Test aggressive profile configuration
    config = {
        'virtual_capital': 1000000,
        'use_real_data': True,
        'simulate_trades': True,
        'live_trading': False,
        'paper_trading': True,
        'trading_profile': 'Aggressive',
        'min_confidence': 0.69,
        'top_n': 4,
        'max_positions': 25,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.25
    }

    print("✅ Aggressive profile configuration:")
    print(f"   • Trading Profile: {config['trading_profile']}")
    print(f"   • Min Confidence: {config['min_confidence']}")
    print(f"   • Top N Signals: {config['top_n']}")
    print(f"   • Max Positions: {config['max_positions']}")
    print(f"   • Stop Loss: {config['stop_loss_pct']:.0%}")
    print(f"   • Take Profit: {config['take_profit_pct']:.0%}")

    # Test UnifiedTradingSystem with aggressive profile
    try:
        # Initialize components (minimal setup for testing)
        dp = DataProvider(use_yf_fallback=True)
        system = UnifiedTradingSystem(
            data_provider=dp,
            kite=None,
            initial_cash=1000000,
            max_positions=25,
            dashboard=None,
            trading_mode='paper',
            config=config
        )

        print("✅ UnifiedTradingSystem initialized with aggressive profile")
        print(f"   • Max Positions: {system.max_positions}")
        print(f"   • Portfolio Min Position Size: {system.portfolio.min_position_size}")
        print(f"   • Portfolio Max Position Size: {system.portfolio.max_position_size}")
        print(f"   • Portfolio Risk Per Trade: {system.portfolio.risk_per_trade_pct}")

        # Test signal processing with profile settings
        min_conf = system.config.get('min_confidence', 0.45)
        top_n = system.config.get('top_n', 1)

        print("✅ Signal processing settings:")
        print(f"   • Min Confidence: {min_conf}")
        print(f"   • Top N: {top_n}")

        print("\n🎉 Aggressive profile test completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Error testing aggressive profile: {e}")
        return False

def test_paper_trading_with_signals():
    """Test paper trading with simulated signals to verify trading logic"""
    print("🧪 Testing Paper Trading with Simulated Signals")
    print("="*50)

    # Test configuration with lower confidence thresholds for testing
    config = {
        'virtual_capital': 1000000,
        'use_real_data': True,
        'simulate_trades': True,
        'live_trading': False,
        'paper_trading': True,
        'trading_profile': 'Aggressive',
        'min_confidence': 0.3,  # Lower threshold for testing
        'top_n': 4,
        'max_positions': 25,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.25,
        'bypass_market_hours': True  # Allow testing outside market hours
    }

    print("✅ Test configuration:")
    print(f"   • Trading Profile: {config['trading_profile']}")
    print(f"   • Min Confidence: {config['min_confidence']} (lowered for testing)")
    print(f"   • Top N Signals: {config['top_n']}")
    print(f"   • Max Positions: {config['max_positions']}")
    print(f"   • Bypass Market Hours: {config.get('bypass_market_hours', False)}")

    try:
        # Initialize components
        dp = DataProvider(use_yf_fallback=True)
        system = UnifiedTradingSystem(
            data_provider=dp,
            kite=None,
            initial_cash=1000000,
            max_positions=25,
            dashboard=None,
            trading_mode='paper',
            config=config
        )

        # Add some test symbols
        test_symbols = ["HDFCBANK", "ICICIBANK", "TCS", "INFY", "RELIANCE"]
        system.add_symbols(test_symbols)
        print(f"✅ Added {len(test_symbols)} test symbols")

        # Test signal generation with mock data
        print("\n🔍 Testing signal generation...")
        signals, prices = system.scan_batch(test_symbols[:3], "5minute", 1, 1)

        print(f"✅ Generated {len(signals)} signals from {len(prices)} price updates")

        if signals:
            print("📊 Sample signals:")
            for symbol, signal in list(signals.items())[:3]:
                print(f"   • {symbol}: {signal['action'].upper()} @ {signal['confidence']:.1%}")

        print("\n🎉 Signal testing completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Error testing paper trading: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Run test if no arguments provided, otherwise run main
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        test_aggressive_profile()
    else:
        main()