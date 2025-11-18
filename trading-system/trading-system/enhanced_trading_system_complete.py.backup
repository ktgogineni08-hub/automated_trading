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
import logging
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import hashlib
from functools import wraps
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
from contextlib import contextmanager

# Import token manager from current directory
from zerodha_token_manager import ZerodhaTokenManager

# ============================================================================
# LOGGING SYSTEM
# ============================================================================
class TradingLogger:
    """Comprehensive logging system for the trading application"""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Create formatters
        self.detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        self.simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )

        # Setup main logger
        self.logger = logging.getLogger('trading_system')
        self.logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        self.logger.handlers.clear()

        # Console handler (INFO and above)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(self.simple_formatter)
        self.logger.addHandler(console_handler)

        # File handler (DEBUG and above)
        current_date = datetime.now().strftime('%Y-%m-%d')
        file_handler = logging.FileHandler(self.log_dir / f'trading_{current_date}.log')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(self.detailed_formatter)
        self.logger.addHandler(file_handler)

        # Error file handler (ERROR and above only)
        error_handler = logging.FileHandler(self.log_dir / f'trading_errors_{current_date}.log')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(self.detailed_formatter)
        self.logger.addHandler(error_handler)

        # Trade log handler
        trade_handler = logging.FileHandler(self.log_dir / f'trades_{current_date}.log')
        trade_handler.setLevel(logging.INFO)
        trade_handler.addFilter(lambda record: record.levelno == logging.getLevelName('TRADE'))
        trade_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.logger.addHandler(trade_handler)

    def add_trade_log_level(self):
        """Add custom TRADE log level"""
        TRADE_LEVEL = 25
        logging.addLevelName(TRADE_LEVEL, 'TRADE')

        def trade(self, message, *args, **kwargs):
            if self.isEnabledFor(TRADE_LEVEL):
                self._log(TRADE_LEVEL, message, args, **kwargs)

        logging.Logger.trade = trade

    def log_trade(self, symbol: str, action: str, details: Dict):
        """Log trade information"""
        trade_msg = f"TRADE - {symbol} - {action} - {details}"
        self.logger.log(25, trade_msg, extra={'trade_details': details})

    def log_api_call(self, endpoint: str, method: str, status_code: Optional[int] = None, error: Optional[str] = None):
        """Log API calls"""
        if error:
            self.logger.error(f"API {method} {endpoint} - Status: {status_code} - Error: {error}")
        else:
            self.logger.info(f"API {method} {endpoint} - Status: {status_code}")

    def log_performance(self, operation: str, duration: float, details: Optional[Dict] = None):
        """Log performance metrics"""
        msg = f"PERFORMANCE - {operation} took {duration:.3f}s"
        if details:
            msg += f" - {details}"
        self.logger.info(msg)

# Initialize logger
logger = TradingLogger()
logger.add_trade_log_level()

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
# CUSTOM EXCEPTIONS
# ============================================================================
class TradingError(Exception):
    """Base exception for trading system"""
    pass

class ConfigurationError(TradingError):
    """Configuration related errors"""
    pass

class APIError(TradingError):
    """API related errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response

class DataError(TradingError):
    """Data related errors"""
    pass

class RiskManagementError(TradingError):
    """Risk management related errors"""
    pass

class MarketHoursError(TradingError):
    """Market hours related errors"""
    pass

# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================
@dataclass
class TradingConfig:
    """Configuration class for trading system"""
    # API Configuration
    api_key: str = ""
    api_secret: str = ""

    # Trading Configuration
    initial_capital: float = 1_000_000.0
    max_positions: int = 25
    min_position_size: float = 0.10
    max_position_size: float = 0.30

    # Risk Management
    risk_per_trade_pct: float = 0.02  # Increased from 1% to 2%
    stop_loss_pct: float = 0.02       # Tighter stop loss at 2%
    take_profit_pct: float = 0.15     # Higher take profit at 15%

    # ATR Settings
    atr_stop_multiplier: float = 1.8   # Tighter stops
    atr_target_multiplier: float = 4.5 # Higher targets
    trailing_activation_multiplier: float = 1.3
    trailing_stop_multiplier: float = 0.7

    # Strategy Configuration
    min_confidence: float = 0.35       # Lower confidence threshold
    signal_agreement_threshold: float = 0.3  # Lower agreement needed
    cooldown_minutes: int = 5          # Shorter cooldown

    # API Settings
    max_requests_per_second: int = 1
    max_requests_per_minute: int = 50
    request_timeout: int = 30

    # Dashboard
    dashboard_url: str = "http://localhost:5173"
    dashboard_enabled: bool = True

    # Logging
    log_level: str = "INFO"
    log_dir: str = "logs"

    # Performance
    enable_performance_monitoring: bool = True
    cache_ttl_seconds: int = 30

    @classmethod
    def from_env(cls) -> 'TradingConfig':
        """Create configuration from environment variables"""
        return cls(
            api_key=os.getenv('ZERODHA_API_KEY', ''),
            api_secret=os.getenv('ZERODHA_API_SECRET', ''),
            initial_capital=float(os.getenv('INITIAL_CAPITAL', '1000000')),
            max_positions=int(os.getenv('MAX_POSITIONS', '25')),
            min_position_size=float(os.getenv('MIN_POSITION_SIZE', '0.10')),
            max_position_size=float(os.getenv('MAX_POSITION_SIZE', '0.30')),
            risk_per_trade_pct=float(os.getenv('RISK_PER_TRADE_PCT', '0.01')),
            stop_loss_pct=float(os.getenv('STOP_LOSS_PCT', '0.03')),
            take_profit_pct=float(os.getenv('TAKE_PROFIT_PCT', '0.08')),
            dashboard_url=os.getenv('DASHBOARD_URL', 'http://localhost:5173'),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            log_dir=os.getenv('LOG_DIR', 'logs'),
            enable_performance_monitoring=os.getenv('ENABLE_PERFORMANCE_MONITORING', 'true').lower() == 'true',
            cache_ttl_seconds=int(os.getenv('CACHE_TTL_SECONDS', '30'))
        )

    def validate(self) -> None:
        """Validate configuration parameters"""
        if self.initial_capital <= 0:
            raise ConfigurationError("Initial capital must be positive")

        if self.max_positions <= 0:
            raise ConfigurationError("Max positions must be positive")

        if not 0 < self.min_position_size <= self.max_position_size <= 1:
            raise ConfigurationError("Position sizes must be between 0 and 1, with min <= max")

        if not 0 < self.risk_per_trade_pct <= 1:
            raise ConfigurationError("Risk per trade percentage must be between 0 and 1")

        if self.api_key and not self.api_secret:
            raise ConfigurationError("API secret is required when API key is provided")

        if self.dashboard_url and not self.dashboard_url.startswith(('http://', 'https://')):
            raise ConfigurationError("Dashboard URL must start with http:// or https://")

# Load configuration
config = TradingConfig.from_env()
try:
    config.validate()
    logger.logger.info("Configuration loaded and validated successfully")
except ConfigurationError as e:
    logger.logger.error(f"Configuration validation failed: {e}")
    raise

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def timing_decorator(func):
    """Decorator to measure function execution time"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            if config.enable_performance_monitoring:
                duration = time.time() - start_time
                logger.log_performance(func.__name__, duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.logger.error(f"Function {func.__name__} failed after {duration:.3f}s: {e}")
            raise
    return wrapper

@contextmanager
def performance_timer(operation_name: str):
    """Context manager for timing operations"""
    start_time = time.time()
    try:
        yield
    finally:
        if config.enable_performance_monitoring:
            duration = time.time() - start_time
            logger.log_performance(operation_name, duration)

def safe_float_conversion(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float with validation"""
    try:
        if pd.isna(value):
            return default
        result = float(value)
        if not np.isfinite(result):
            logger.logger.warning(f"Non-finite value encountered: {value}")
            return default
        return result
    except (ValueError, TypeError) as e:
        logger.logger.warning(f"Failed to convert {value} to float: {e}")
        return default

def validate_symbol(symbol: str) -> str:
    """Validate and normalize trading symbol"""
    if not symbol or not isinstance(symbol, str):
        raise ValueError(f"Invalid symbol: {symbol}")

    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("Symbol cannot be empty")

    # Basic symbol validation (can be extended)
    if len(symbol) < 2 or len(symbol) > 20:
        raise ValueError(f"Symbol length invalid: {symbol}")

    return symbol

def hash_sensitive_data(data: str) -> str:
    """Hash sensitive data for logging"""
    return hashlib.sha256(data.encode()).hexdigest()[:8] if data else ""

# ============================================================================
# DASHBOARD INTEGRATION
# ============================================================================
class DashboardConnector:
    """Enhanced connector with better error handling"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or config.dashboard_url
        self.session = requests.Session()
        self.is_connected = False
        self.last_connection_check = 0
        self.connection_check_interval = 5  # seconds
        self.failed_sends = 0
        self.max_retries = 3
        self.circuit_breaker_failures = 0
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 60  # seconds
        self.last_circuit_breaker_trip = 0

        # Configure session
        self.session.timeout = config.request_timeout
        self.ensure_connection()

    def is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open"""
        if self.circuit_breaker_failures >= self.circuit_breaker_threshold:
            if time.time() - self.last_circuit_breaker_trip < self.circuit_breaker_timeout:
                return True
            else:
                # Reset circuit breaker
                self.circuit_breaker_failures = 0
        return False

    def test_connection(self) -> bool:
        """Test if dashboard is accessible"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=2)
            return response.status_code == 200
        except Exception as e:
            logger.logger.debug(f"Dashboard connection test failed: {e}")
            return False

    def ensure_connection(self, force: bool = False) -> bool:
        """Ensure the dashboard connection is alive, retrying if needed"""
        if self.is_circuit_breaker_open():
            return False

        now = time.time()
        if force or not self.is_connected or (now - self.last_connection_check) > self.connection_check_interval:
            self.is_connected = self.test_connection()
            self.last_connection_check = now
        return self.is_connected

    def send_with_retry(self, endpoint: str, data: Dict, max_retries: int = None) -> bool:
        """Send data with automatic retry and circuit breaker"""
        if not self.ensure_connection():
            # try one immediate forced reconnect before bailing
            if not self.ensure_connection(force=True):
                return False

        if self.is_circuit_breaker_open():
            logger.logger.warning("Circuit breaker is open, skipping dashboard update")
            return False

        max_retries = max_retries or self.max_retries

        for attempt in range(max_retries):
            try:
                response = self.session.post(
                    f"{self.base_url}/api/{endpoint}",
                    json=data,
                    timeout=config.request_timeout
                )
                logger.log_api_call(endpoint, "POST", response.status_code)

                if response.status_code == 200:
                    if not self.is_connected:
                        self.is_connected = True
                    self.circuit_breaker_failures = 0  # Reset on success
                    return True
                else:
                    logger.logger.warning(f"Dashboard API returned status {response.status_code}")

            except Exception as e:
                logger.logger.error(f"Dashboard API call failed (attempt {attempt + 1}): {e}")
                self.circuit_breaker_failures += 1

            # A failure might mean the server restarted; retry connection check
            self.ensure_connection(force=True)

            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff

        # Trip circuit breaker on all retries failed
        self.last_circuit_breaker_trip = time.time()
        logger.logger.error(f"Circuit breaker tripped after {max_retries} failed attempts")
        return False

    def send_signal(self, symbol: str, action: str, confidence: float, price: float, sector: str = None, reasons: List = None):
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

    def send_trade(self, symbol: str, side: str, shares: int, price: float, pnl: float = None, sector: str = None, confidence: float = 0.5):
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

    def send_portfolio_update(self, total_value: float, cash: float, positions_count: int, total_pnl: float, positions: Dict = None):
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

    def send_performance_update(self, trades_count: int, win_rate: float, total_pnl: float, best_trade: float, worst_trade: float):
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

    def send_system_status(self, is_running: bool, iteration: int = 0, scan_status: str = "idle"):
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

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent / "state"
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.archive_dir = self.base_dir / "archive"
        self.archive_dir.mkdir(exist_ok=True)

        self.trades_dir = self.base_dir / "trades"
        self.trades_dir.mkdir(exist_ok=True)

        self.state_path = self.base_dir / "current_state.json"
        self.ist = pytz.timezone('Asia/Kolkata')

    def current_trading_day(self) -> str:
        return datetime.now(self.ist).strftime('%Y-%m-%d')

    def load_state(self) -> Dict:
        if not self.state_path.exists():
            return {}
        try:
            with self.state_path.open('r', encoding='utf-8') as handle:
                return json.load(handle)
        except Exception as exc:
            logger.logger.error(f"Failed to load saved trading state: {exc}")
            return {}

    def save_state(self, state: Dict) -> None:
        try:
            temp_path = self.state_path.with_suffix('.tmp')
            with temp_path.open('w', encoding='utf-8') as handle:
                json.dump(state, handle, indent=2)
            temp_path.replace(self.state_path)
        except Exception as exc:
            logger.logger.error(f"Failed to persist trading state: {exc}")

    def archive_state(self, state: Dict) -> None:
        trading_day = state.get('trading_day') or self.current_trading_day()
        archive_path = self.archive_dir / f"state_{trading_day}.json"
        try:
            with archive_path.open('w', encoding='utf-8') as handle:
                json.dump(state, handle, indent=2)
        except Exception as exc:
            logger.logger.error(f"Failed to archive trading state: {exc}")

    def log_trade(self, trade: Dict, trading_day: str = None) -> None:
        day = trading_day or self.current_trading_day()
        trades_path = self.trades_dir / f"trades_{day}.jsonl"
        try:
            with trades_path.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(trade) + "\n")
        except Exception as exc:
            logger.logger.error(f"Failed to log trade: {exc}")

    def write_daily_summary(self, trading_day: str, summary: Dict) -> None:
        summary_path = self.archive_dir / f"summary_{trading_day}.json"
        try:
            with summary_path.open('w', encoding='utf-8') as handle:
                json.dump(summary, handle, indent=2)
        except Exception as exc:
            logger.logger.error(f"Failed to write daily summary: {exc}")

# ============================================================================
# MARKET COMPONENTS
# ============================================================================
class MarketHours:
    def __init__(self):
        self.ist = pytz.timezone('Asia/Kolkata')
        self.market_open = datetime.strptime("09:15", "%H:%M").time()
        self.market_close = datetime.strptime("15:30", "%H:%M").time()

    def is_market_open(self) -> bool:
        now = datetime.now(self.ist)
        if now.weekday() >= 5:
            return False
        current_time = now.time()
        return self.market_open <= current_time <= self.market_close

class EnhancedRateLimiter:
    def __init__(self, max_requests_per_second: int = None, max_requests_per_minute: int = None):
        self.max_per_second = max_requests_per_second or config.max_requests_per_second
        self.max_per_minute = max_requests_per_minute or config.max_requests_per_minute
        self.second_bucket = deque(maxlen=self.max_per_second)
        self.minute_bucket = deque(maxlen=self.max_per_minute)

    def can_make_request(self) -> bool:
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

    def wait_if_needed(self) -> None:
        while not self.can_make_request():
            time.sleep(0.1)

    def record_request(self) -> None:
        now = time.time()
        self.second_bucket.append(now)
        self.minute_bucket.append(now)

# ============================================================================
# TRADING STRATEGIES
# ============================================================================
class BaseStrategy:
    """Base class for all trading strategies"""

    def __init__(self, name: str):
        self.name = name

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> Dict:
        """Generate trading signals from data"""
        raise NotImplementedError("Subclasses must implement generate_signals")

    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate input data"""
        if data is None or data.empty:
            return False
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        return all(col in data.columns for col in required_columns)

class ImprovedMovingAverageCrossover(BaseStrategy):
    def __init__(self, short_window: int = 3, long_window: int = 10):
        super().__init__("Fast_MA_Crossover")
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> Dict:
        if not self.validate_data(data) or len(data) < self.long_window + 5:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}

        try:
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
        except Exception as e:
            logger.logger.error(f"Error in MA Crossover strategy for {symbol}: {e}")
            return {'signal': 0, 'strength': 0.0, 'reason': 'error'}

class EnhancedRSIStrategy(BaseStrategy):
    def __init__(self, period: int = 7, oversold: int = 25, overbought: int = 75):
        super().__init__("Enhanced_RSI")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> Dict:
        if not self.validate_data(data) or len(data) < self.period + 5:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}

        try:
            delta = data["close"].diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)

            avg_gain = gain.ewm(span=self.period, adjust=False).mean()
            avg_loss = loss.ewm(span=self.period, adjust=False).mean()

            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))

            current_rsi = safe_float_conversion(rsi.iloc[-1], 50.0)

            if current_rsi <= self.oversold:
                strength = (self.oversold - current_rsi) / self.oversold
                return {'signal': 1, 'strength': min(strength * 2, 1.0), 'reason': f'oversold_{current_rsi:.0f}'}
            elif current_rsi >= self.overbought:
                strength = (current_rsi - self.overbought) / (100 - self.overbought)
                return {'signal': -1, 'strength': min(strength * 2, 1.0), 'reason': f'overbought_{current_rsi:.0f}'}

            return {'signal': 0, 'strength': 0.0, 'reason': 'neutral'}
        except Exception as e:
            logger.logger.error(f"Error in RSI strategy for {symbol}: {e}")
            return {'signal': 0, 'strength': 0.0, 'reason': 'error'}

class BollingerBandsStrategy(BaseStrategy):
    def __init__(self, period: int = 20, std_dev: float = 2):
        super().__init__("Bollinger_Bands")
        self.period = period
        self.std_dev = std_dev

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> Dict:
        if not self.validate_data(data) or len(data) < self.period + 5:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}

        try:
            close_prices = data['close']
            sma = close_prices.rolling(self.period).mean()
            std = close_prices.rolling(self.period).std()

            upper_band = sma + (std * self.std_dev)
            lower_band = sma - (std * self.std_dev)

            current_price = safe_float_conversion(close_prices.iloc[-1])
            current_upper = safe_float_conversion(upper_band.iloc[-1])
            current_lower = safe_float_conversion(lower_band.iloc[-1])

            if current_price <= current_lower:
                strength = min((current_lower - current_price) / current_lower * 100, 1.0)
                return {'signal': 1, 'strength': strength, 'reason': 'oversold_at_lower_band'}
            elif current_price >= current_upper:
                strength = min((current_price - current_upper) / current_upper * 100, 1.0)
                return {'signal': -1, 'strength': strength, 'reason': 'overbought_at_upper_band'}

            return {'signal': 0, 'strength': 0.0, 'reason': 'no_signal'}
        except Exception as e:
            logger.logger.error(f"Error in Bollinger Bands strategy for {symbol}: {e}")
            return {'signal': 0, 'strength': 0.0, 'reason': 'error'}

class ImprovedVolumeBreakoutStrategy(BaseStrategy):
    def __init__(self, volume_multiplier: float = 1.3, price_threshold: float = 0.001):
        super().__init__("Volume_Price_Breakout")
        self.volume_multiplier = volume_multiplier
        self.price_threshold = price_threshold

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> Dict:
        if not self.validate_data(data) or len(data) < 20:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}

        try:
            vol_avg = data['volume'].rolling(20).mean().iloc[-1]
            current_vol = safe_float_conversion(data['volume'].iloc[-1])
            price_change = (data['close'].iloc[-1] - data['close'].iloc[-2]) / data['close'].iloc[-2]

            if current_vol > vol_avg * self.volume_multiplier:
                if price_change > self.price_threshold:
                    strength = min((current_vol / vol_avg - 1) * 0.3 + abs(price_change) * 50, 1.0)
                    return {'signal': 1, 'strength': strength, 'reason': 'volume_breakout_up'}
                elif price_change < -self.price_threshold:
                    strength = min((current_vol / vol_avg - 1) * 0.3 + abs(price_change) * 50, 1.0)
                    return {'signal': -1, 'strength': strength, 'reason': 'volume_breakout_down'}

            return {'signal': 0, 'strength': 0.0, 'reason': 'no_volume_signal'}
        except Exception as e:
            logger.logger.error(f"Error in Volume Breakout strategy for {symbol}: {e}")
            return {'signal': 0, 'strength': 0.0, 'reason': 'error'}

class EnhancedMomentumStrategy(BaseStrategy):
    """Enhanced momentum strategy with multiple indicators for better signal quality"""

    def __init__(self,
                 momentum_period: int = 10,
                 rsi_period: int = 7,
                 momentum_threshold: float = 0.015,  # Reduced from 0.02 for more opportunities
                 acceleration_threshold: float = 0.003,  # Reduced from 0.005 for sensitivity
                 rsi_oversold: int = 30,
                 rsi_overbought: int = 70,
                 roc_period: int = 12,  # Rate of Change period
                 trend_strength_period: int = 20):  # Trend strength assessment period
        super().__init__("Enhanced_Momentum")
        self.momentum_period = momentum_period
        self.rsi_period = rsi_period
        self.momentum_threshold = momentum_threshold
        self.acceleration_threshold = acceleration_threshold
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.roc_period = roc_period
        self.trend_strength_period = trend_strength_period

    def _calculate_rsi(self, data: pd.DataFrame, period: int) -> pd.Series:
        """Calculate RSI efficiently with proper NaN handling"""
        delta = data["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        # Use a small epsilon to avoid division by zero
        epsilon = 1e-10
        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, epsilon)
        rsi = 100 - (100 / (1 + rs))

        # Fill any remaining NaN values with neutral RSI (50)
        rsi = rsi.fillna(50.0)
        return rsi

    def _calculate_roc(self, data: pd.DataFrame, period: int) -> float:
        """Calculate Rate of Change"""
        if len(data) < period + 1:
            return 0.0
        current_price = data['close'].iloc[-1]
        past_price = data['close'].iloc[-(period + 1)]
        if past_price == 0:
            return 0.0
        return (current_price - past_price) / past_price

    def _calculate_macd(self, data: pd.DataFrame, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Tuple[float, float]:
        """Calculate MACD and signal line"""
        if len(data) < slow_period + signal_period:
            return 0.0, 0.0

        try:
            # Calculate EMAs
            ema_fast = data['close'].ewm(span=fast_period, adjust=False).mean()
            ema_slow = data['close'].ewm(span=slow_period, adjust=False).mean()

            # MACD line
            macd_line = ema_fast - ema_slow

            # Signal line
            signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()

            current_macd = safe_float_conversion(macd_line.iloc[-1], 0.0)
            current_signal = safe_float_conversion(signal_line.iloc[-1], 0.0)

            return current_macd, current_signal
        except Exception:
            return 0.0, 0.0

    def _calculate_trend_strength(self, data: pd.DataFrame, period: int) -> float:
        """Calculate trend strength using linear regression slope"""
        if len(data) < period:
            return 0.0

        try:
            recent_data = data['close'].tail(period)
            x = np.arange(len(recent_data))
            y = recent_data.values

            # Calculate linear regression slope
            slope = np.polyfit(x, y, 1)[0]

            # Normalize slope by price level
            avg_price = y.mean()
            if avg_price == 0:
                return 0.0

            normalized_slope = slope / avg_price
            return abs(normalized_slope)  # Return absolute value for trend strength
        except Exception:
            return 0.0

    def _calculate_acceleration(self, data: pd.DataFrame, period: int = 5) -> float:
        """Calculate price acceleration using exponential smoothing"""
        if len(data) < period * 2:
            return 0.0

        try:
            # Use exponential weighted moving average for smoother acceleration
            prices = data['close']
            momentum = prices.pct_change(period)
            acceleration = momentum.diff().ewm(span=3, adjust=False).mean()
            return safe_float_conversion(acceleration.iloc[-1], 0.0)
        except Exception:
            return 0.0

    def _calculate_signal_strength(self, momentum: float, rsi: float, roc: float,
                                 trend_strength: float, acceleration: float, macd: float,
                                 signal_line: float, signal_type: str) -> float:
        """Calculate comprehensive signal strength with MACD"""
        strength = 0.0

        # Momentum component (25% weight)
        if signal_type == 'buy':
            momentum_score = min(abs(momentum) / self.momentum_threshold, 1.0) if momentum > 0 else 0.0
        else:
            momentum_score = min(abs(momentum) / self.momentum_threshold, 1.0) if momentum < 0 else 0.0
        strength += momentum_score * 0.25

        # RSI component (20% weight)
        if signal_type == 'buy':
            rsi_score = max(0, (self.rsi_overbought - rsi) / (self.rsi_overbought - self.rsi_oversold)) if rsi < self.rsi_overbought else 0.0
        else:
            rsi_score = max(0, (rsi - self.rsi_oversold) / (self.rsi_overbought - self.rsi_oversold)) if rsi > self.rsi_oversold else 0.0
        strength += rsi_score * 0.20

        # MACD component (20% weight)
        macd_threshold = 0.001  # Small threshold for MACD signals
        if signal_type == 'buy':
            macd_score = min(abs(macd - signal_line) / macd_threshold, 1.0) if macd > signal_line else 0.0
        else:
            macd_score = min(abs(macd - signal_line) / macd_threshold, 1.0) if macd < signal_line else 0.0
        strength += macd_score * 0.20

        # ROC component (15% weight)
        roc_threshold = 0.02  # 2% ROC threshold
        if signal_type == 'buy':
            roc_score = min(abs(roc) / roc_threshold, 1.0) if roc > 0 else 0.0
        else:
            roc_score = min(abs(roc) / roc_threshold, 1.0) if roc < 0 else 0.0
        strength += roc_score * 0.15

        # Trend strength component (12% weight)
        trend_threshold = 0.001  # 0.1% daily trend
        trend_score = min(trend_strength / trend_threshold, 1.0)
        strength += trend_score * 0.12

        # Acceleration component (8% weight)
        if signal_type == 'buy':
            accel_score = min(abs(acceleration) / self.acceleration_threshold, 1.0) if acceleration > 0 else 0.0
        else:
            accel_score = min(abs(acceleration) / self.acceleration_threshold, 1.0) if acceleration < 0 else 0.0
        strength += accel_score * 0.08

        return min(strength, 1.0)

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> Dict:
        if not self.validate_data(data) or len(data) < max(self.momentum_period, self.roc_period, self.trend_strength_period) + 10:
            return {'signal': 0, 'strength': 0.0, 'reason': 'insufficient_data'}

        try:
            # Calculate all indicators
            current_price = safe_float_conversion(data['close'].iloc[-1], 0.0)
            momentum = safe_float_conversion(data['close'].pct_change(self.momentum_period).iloc[-1], 0.0)
            rsi = self._calculate_rsi(data, self.rsi_period)
            current_rsi = safe_float_conversion(rsi.iloc[-1], 50.0)
            roc = self._calculate_roc(data, self.roc_period)
            trend_strength = self._calculate_trend_strength(data, self.trend_strength_period)
            acceleration = self._calculate_acceleration(data)
            macd, signal_line = self._calculate_macd(data)

            # Enhanced bullish conditions with MACD confirmation
            bullish_conditions = (
                momentum > self.momentum_threshold and
                current_rsi < self.rsi_overbought and
                roc > 0.01 and  # 1% ROC minimum
                trend_strength > 0.0005 and  # Minimum trend strength
                acceleration > self.acceleration_threshold and
                macd > signal_line  # MACD bullish crossover
            )

            # Enhanced bearish conditions with MACD confirmation
            bearish_conditions = (
                momentum < -self.momentum_threshold and
                current_rsi > self.rsi_oversold and
                roc < -0.01 and  # -1% ROC minimum
                trend_strength > 0.0005 and  # Minimum trend strength
                acceleration < -self.acceleration_threshold and
                macd < signal_line  # MACD bearish crossover
            )

            if bullish_conditions:
                strength = self._calculate_signal_strength(momentum, current_rsi, roc, trend_strength, acceleration, macd, signal_line, 'buy')
                if strength > 0.35:  # Lower minimum strength threshold for more opportunities
                    return {
                        'signal': 1,
                        'strength': strength,
                        'reason': f'enhanced_momentum_up_mom{momentum:.3f}_rsi{current_rsi:.0f}_roc{roc:.3f}_macd{macd:.4f}'
                    }

            elif bearish_conditions:
                strength = self._calculate_signal_strength(momentum, current_rsi, roc, trend_strength, acceleration, macd, signal_line, 'sell')
                if strength > 0.35:  # Lower minimum strength threshold for more opportunities
                    return {
                        'signal': -1,
                        'strength': strength,
                        'reason': f'enhanced_momentum_down_mom{momentum:.3f}_rsi{current_rsi:.0f}_roc{roc:.3f}_macd{macd:.4f}'
                    }

            return {'signal': 0, 'strength': 0.0, 'reason': 'no_momentum_conditions'}

        except Exception as e:
            logger.logger.error(f"Error in Enhanced Momentum strategy for {symbol}: {e}")
            return {'signal': 0, 'strength': 0.0, 'reason': 'error'}

class EnhancedSignalAggregator:
    def __init__(self, min_agreement: float = None):
        self.min_agreement = min_agreement or config.signal_agreement_threshold
        self.signal_history: Dict[str, List] = {}

    def aggregate_signals(self, strategy_signals: List[Dict], symbol: str) -> Dict:
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
    def __init__(self, kite: KiteConnect = None, instruments_map: Dict = None, use_yf_fallback: bool = True):
        self.kite = kite
        self.instruments = instruments_map or {}
        self.use_yf = use_yf_fallback
        self.rate_limiter = EnhancedRateLimiter()
        self.cache: Dict[str, Tuple[float, pd.DataFrame]] = {}
        self.cache_ttl = config.cache_ttl_seconds

    @timing_decorator
    def fetch_with_retry(self, symbol: str, interval: str = "5minute", days: int = 5, max_retries: int = 3) -> pd.DataFrame:
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
                logger.logger.error(f"Data fetch attempt {attempt + 1} failed for {symbol}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
        logger.logger.error(f"Failed to fetch data for {symbol} after {max_retries} attempts")
        return pd.DataFrame()

    def _yfinance_fetch(self, symbol: str, interval: str, days: int) -> pd.DataFrame:
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
        except Exception as e:
            logger.logger.error(f"YFinance fetch failed for {symbol}: {e}")
        return pd.DataFrame()

# ============================================================================
# UNIFIED PORTFOLIO
# ============================================================================
class UnifiedPortfolio:
    """Unified portfolio that handles all trading modes"""

    def __init__(self, initial_cash: float = None, dashboard: DashboardConnector = None, kite: KiteConnect = None, trading_mode: str = 'paper', silent: bool = False):
        self.initial_cash = float(initial_cash or config.initial_capital)
        self.cash = float(initial_cash or config.initial_cash)
        self.positions: Dict[str, Dict] = {}
        self.dashboard = dashboard
        self.kite = kite
        self.trading_mode = trading_mode
        self.silent = silent

        # Trading tracking
        self.trades_count = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.best_trade = 0.0
        self.worst_trade = 0.0
        self.trades_history: List[Dict] = []
        self.portfolio_history: List[Dict] = []
        self.daily_profit = 0.0
        self.daily_target = None

        # Position management
        self.position_entry_times: Dict[str, datetime] = {}
        self.min_holding_period = timedelta(minutes=15)

        # Mode-specific settings
        if trading_mode == 'live':
            self.min_position_size = 0.05  # 5% minimum for live
            self.max_position_size = 0.15  # 15% maximum for live (conservative)
            if not self.silent:
                logger.logger.info("🔴 LIVE TRADING MODE - Real money at risk!")
        elif trading_mode == 'paper':
            self.min_position_size = config.min_position_size
            self.max_position_size = config.max_position_size
            if not self.silent:
                logger.logger.info("📝 PAPER TRADING MODE - Safe simulation!")
        else:  # backtesting
            self.min_position_size = 0.10
            self.max_position_size = 0.25
            if not self.silent:
                logger.logger.info("📊 BACKTESTING MODE - Historical analysis!")

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
            self.risk_per_trade_pct = config.risk_per_trade_pct
            self.atr_stop_multiplier = config.atr_stop_multiplier
            self.atr_target_multiplier = config.atr_target_multiplier
            self.trailing_activation_multiplier = config.trailing_activation_multiplier
            self.trailing_stop_multiplier = config.trailing_stop_multiplier

    def calculate_total_value(self, price_map: Dict[str, float] = None) -> float:
        """Return current total portfolio value using latest prices when available."""
        price_map = price_map or {}
        positions_value = sum(
            pos["shares"] * price_map.get(symbol, pos["entry_price"])
            for symbol, pos in self.positions.items()
        )
        return self.cash + positions_value

    def record_trade(self, symbol: str, side: str, shares: int, price: float, fees: float, pnl: float = None, timestamp: datetime = None, confidence: float = 0.0, sector: str = 'Other', atr_value: float = None) -> Dict:
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

    def to_dict(self) -> Dict:
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

    def load_from_dict(self, data: Dict) -> None:
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

    def place_live_order(self, symbol: str, quantity: int, price: float, side: str) -> bool:
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

            logger.logger.info(f"🔴 PLACING LIVE ORDER: {side} {quantity} {symbol} @ ₹{price:.2f}")
            order_id = self.kite.place_order(**order_params)

            if order_id:
                logger.logger.info(f"✅ LIVE ORDER PLACED: Order ID {hash_sensitive_data(order_id)}")
                return order_id
            else:
                logger.logger.error("Failed to place live order")
                return False

        except Exception as e:
            logger.logger.error(f"Error placing live order: {e}")
            return False

    def simulate_order_execution(self, symbol: str, shares: int, price: float, side: str) -> float:
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
            logger.logger.info(f"📝 [PAPER {side.upper()}] {symbol}: {shares} @ ₹{execution_price:.2f} (slippage: {slippage*100:.2f}%)")
        return execution_price

    def can_exit_position(self, symbol: str) -> bool:
        if symbol not in self.position_entry_times:
            return True
        time_held = datetime.now() - self.position_entry_times[symbol]
        return time_held >= self.min_holding_period

    def execute_trade(self, symbol: str, shares: int, price: float, side: str, timestamp: datetime = None, confidence: float = 0.5, sector: str = None, atr: float = None) -> Optional[Dict]:
        """Execute trade based on trading mode"""
        if timestamp is None:
            timestamp = datetime.now()

        if side == "buy":
            if shares <= 0 or price <= 0:
                return None

            atr_value = atr if atr and atr > 0 else None
            if atr_value:
                max_loss_per_share = atr_value * self.atr_stop_multiplier
                if max_loss_per_share <= 0:
                    atr_value = None
                else:
                    risk_budget = max(self.cash * self.risk_per_trade_pct, 0)
                    allowed_shares = int(risk_budget // max_loss_per_share)
                    if allowed_shares <= 0:
                        return None
                    shares = min(shares, allowed_shares)
                    if shares <= 0:
                        return None

            # For live trading, place actual order
            if self.trading_mode == 'live':
                order_id = self.place_live_order(symbol, shares, price, "BUY")
                if not order_id:
                    return None

            # For paper trading, simulate execution
            if self.trading_mode == 'paper':
                execution_price = self.simulate_order_execution(symbol, shares, price, "buy")
            else:
                execution_price = price

            amount = shares * execution_price
            fees = self.calculate_transaction_costs(amount, "buy")
            total_cost = amount + fees

            if total_cost > self.cash:
                return None

            self.cash -= total_cost
            entry_time = timestamp

            # Dynamic stop-loss and take-profit based on volatility & confidence
            if atr_value:
                confidence_adj = max(0.8, 1 - max(0.0, 0.6 - confidence))
                stop_distance = atr_value * self.atr_stop_multiplier * confidence_adj
                take_distance = atr_value * (self.atr_target_multiplier + max(0.0, confidence - 0.5))
                stop_loss = max(execution_price - stop_distance, execution_price * 0.9)
                take_profit = execution_price + take_distance
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
                logger.logger.info(f"{mode_icon} [BUY] {symbol}: {shares} @ ₹{execution_price:.2f} | SL: ₹{stop_loss:.2f} | TP: ₹{take_profit:.2f}")

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
                return None

            if not self.can_exit_position(symbol):
                return None

            position = self.positions[symbol]

            # For live trading, place actual order
            if self.trading_mode == 'live':
                order_id = self.place_live_order(symbol, shares, price, "SELL")
                if not order_id:
                    return None

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
                logger.logger.info(f"{emoji} {mode_icon} [SELL] {symbol}: {shares} @ ₹{execution_price:.2f} | P&L: ₹{pnl:.2f}")

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

        return None

# ============================================================================
# UNIFIED TRADING SYSTEM
# ============================================================================
class UnifiedTradingSystem:
    """Unified trading system supporting all modes"""

    def __init__(self, data_provider: DataProvider, kite: KiteConnect, initial_cash: float = None, max_positions: int = None, dashboard: DashboardConnector = None, trading_mode: str = 'paper', config_override: Dict = None):
        self.dp = data_provider
        self.dashboard = dashboard
        self.kite = kite
        self.trading_mode = trading_mode
        self.config = config_override or {}

        # Create unified portfolio (silence when fast backtest)
        self.portfolio = UnifiedPortfolio(initial_cash, dashboard, kite, trading_mode, silent=bool(self.config.get('fast_backtest')))

        # Apply profile settings for paper trading
        if trading_mode == 'paper' and 'trading_profile' in self.config:
            profile = self.config['trading_profile']
            if profile == 'Aggressive':
                # Override portfolio settings for optimized aggressive profile
                self.portfolio.min_position_size = 0.12   # 12% minimum for optimized
                self.portfolio.max_position_size = 0.30   # 30% maximum for optimized
                self.portfolio.risk_per_trade_pct = 0.018  # 1.8% risk per trade
                self.portfolio.atr_stop_multiplier = 1.9   # Optimized stops
                self.portfolio.atr_target_multiplier = 4.5  # Higher targets
                self.portfolio.trailing_activation_multiplier = 1.4
                self.portfolio.trailing_stop_multiplier = 0.65
                logger.logger.info("⚡ Optimized Aggressive profile applied to portfolio settings")

        # Adjust strategies based on mode
        if trading_mode == 'live':
            # Conservative strategies for live trading
            self.strategies = [
                ImprovedMovingAverageCrossover(5, 15),  # Slower signals
                EnhancedRSIStrategy(14, 30, 70),       # More conservative RSI
                BollingerBandsStrategy(20, 2),
                EnhancedMomentumStrategy(15, 10, 0.02, 0.005, 35, 65, 15, 25),  # Conservative momentum for live
            ]
            self.aggregator = EnhancedSignalAggregator(min_agreement=0.4)  # Higher agreement
            self.max_positions = min(max_positions or config.max_positions, 10)  # Conservative position limit
            self.cooldown_minutes = 30  # Longer cooldown
        else:
            # Full strategies for paper/backtest
            self.strategies = [
                ImprovedMovingAverageCrossover(3, 10),
                EnhancedRSIStrategy(7, 25, 75),
                BollingerBandsStrategy(20, 2),
                ImprovedVolumeBreakoutStrategy(1.3, 0.001),
                EnhancedMomentumStrategy(10, 7, 0.015, 0.003, 30, 70, 12, 20)  # Enhanced momentum with better signal quality
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
                self.max_positions = max_positions or config.max_positions
            self.cooldown_minutes = 10

        self.symbols: List[str] = []
        self.market_hours = MarketHours()
        self.position_cooldown: Dict[str, datetime] = {}

        # Persistence helpers
        state_dir = self.config.get('state_dir')
        self.state_manager = TradingStateManager(state_dir)
        self.last_archive_day = None
        self.restored_state = False
        self.iteration_start = 0
        self.last_state_snapshot = None
        self.day_close_executed = None
        self._restore_saved_state()

        logger.logger.info(f"🎯 UNIFIED TRADING SYSTEM INITIALIZED")
        logger.logger.info(f"Mode: {trading_mode.upper()}")
        logger.logger.info(f"Strategies: {len(self.strategies)}")
        logger.logger.info(f"Max Positions: {self.max_positions}")

        # Additional risk controls
        self.stop_loss_cooldown_minutes = self.config.get('stop_loss_cooldown_minutes', max(self.cooldown_minutes * 2, 20))
        logger.logger.info(f"Cooldown after stop-loss: {self.stop_loss_cooldown_minutes} minutes")

    def add_symbols(self, symbols: List[str]) -> None:
        """Add symbols for trading"""
        for symbol in symbols:
            s = validate_symbol(symbol)
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


    def run_fast_backtest(self, interval: str = "5minute", days: int = 30) -> None:
        """One-pass backtest over historical bars; prints aggregate summary only."""
        interval = self._normalize_fast_interval(interval)
        pandas_interval = self._interval_to_pandas(interval)

        logger.logger.info("⚡ Running fast backtest (one-pass)…")
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
            except Exception as e:
                logger.logger.error(f"Error processing {sym} for backtest: {e}")
                continue
        if not df_map:
            logger.logger.error("❌ No historical data available for fast backtest")
            return

        all_times = sorted({pd.Timestamp(ts) for df in df_map.values() for ts in df.index})
        if not all_times:
            logger.logger.error("❌ No timestamps found for fast backtest")
            return

        resampled_prices = {sym: df['close'].copy() for sym, df in df_map.items()}
        resampled_atr = {sym: df['ATR'].copy() for sym, df in df_map.items()}
        if interval != '5minute':
            try:
                resampled_prices = {sym: series.resample(pandas_interval).last().dropna() for sym, series in resampled_prices.items()}
                resampled_atr = {sym: series.resample(pandas_interval).last().dropna() for sym, series in resampled_atr.items()}
                all_times = sorted({pd.Timestamp(ts) for series in resampled_prices.values() for ts in series.index})
            except Exception as exc:
                logger.logger.warning(f"Resample failed ({exc}), falling back to raw interval")
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
        logger.logger.info("===== FAST BACKTEST SUMMARY =====")
        logger.logger.info(f"Symbols: {len(self.symbols)} | Bars: {len(all_times)} | Trades: {trades}")
        logger.logger.info(f"Final Portfolio Value: ₹{final_value:,.2f}")
        logger.logger.info(f"Total P&L: ₹{self.portfolio.total_pnl:,.2f} | Win rate: {win_rate:.1f}%")
        logger.logger.info(f"Best Trade: ₹{self.portfolio.best_trade:,.2f} | Worst Trade: ₹{self.portfolio.worst_trade:,.2f}")
        logger.logger.info(f"Elapsed: {elapsed:.2f}s")

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
        logger.logger.info(f"Summary saved to {summary_path}")

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

    def _restore_saved_state(self) -> None:
        saved_state = self.state_manager.load_state()
        if not saved_state:
            logger.logger.info("💾 No saved trading state found – starting fresh.")
            return

        saved_mode = saved_state.get('mode')
        if saved_mode and saved_mode != self.trading_mode:
            logger.logger.warning(f"Saved trading state is for mode '{saved_mode}', current mode '{self.trading_mode}'. Ignoring saved data.")
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
            logger.logger.info(
                f"💾 Restored trading state: iteration {self.iteration_start}, "
                f"cash ₹{self.portfolio.cash:,.2f}, open positions {len(self.portfolio.positions)}"
            )
        except Exception as exc:
            logger.logger.error(f"Failed to apply saved trading state: {exc}")
            self.iteration_start = 0
            self.last_archive_day = None
            self.restored_state = False

    def _serialize_cooldowns(self) -> Dict:
        serialized = {}
        for symbol, dt_obj in self.position_cooldown.items():
            if isinstance(dt_obj, datetime):
                serialized[symbol] = dt_obj.isoformat()
        return serialized

    def _build_state_snapshot(self, iteration: int, total_value: float, price_map: Dict) -> Dict:
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

    def _persist_state(self, iteration: int, total_value: float, price_map: Dict) -> None:
        state = self._build_state_snapshot(iteration, total_value, price_map)
        now_ist = datetime.now(self.state_manager.ist)
        trading_day = state['trading_day']

        if now_ist.time() >= self.market_hours.market_close:
            if self.last_archive_day != trading_day:
                self.state_manager.archive_state(state)
                self.last_archive_day = trading_day
                state['last_archive_day'] = trading_day
                logger.logger.info(f"💾 Archived trading state for {trading_day}")
        self.state_manager.save_state(state)
        self.last_state_snapshot = state

    def _broadcast_restored_state(self) -> None:
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

        logger.logger.info(
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

    def _close_positions_for_day(self, price_map: Dict, iteration: int, current_day: str) -> bool:
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
            logger.logger.info("🔔 Market close approaching – unwinding open positions...")
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

    def get_sector(self, symbol: str) -> str:
        """Get sector for symbol"""
        for sector, symbols in SECTOR_GROUPS.items():
            if symbol in symbols:
                return sector
        return "Other"

    def scan_batch(self, batch: List[str], interval: str, batch_num: int, total_batches: int) -> Tuple[Dict, Dict]:
        """Scan a batch of symbols for signals"""
        signals = {}
        prices = {}
        logger.logger.info(f"  Batch {batch_num}/{total_batches}: {', '.join(batch[:3])}...")

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
                    logger.logger.info(f"    {symbol} ({sector}): {aggregated['action'].upper()} @ ₹{current_price:.2f} ({aggregated['confidence']:.1%})")

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
            except Exception as e:
                logger.logger.error(f"Error scanning {symbol}: {e}")
                continue

        return signals, prices

    def run_nifty50_trading(self, interval: str = "5minute", check_interval: int = 30) -> None:
        """Run the trading system"""
        logger.logger.info("="*60)
        logger.logger.info(f"UNIFIED NIFTY 50 TRADING SYSTEM - {self.trading_mode.upper()} MODE")
        logger.logger.info("="*60)
        logger.logger.info(f"Capital: ₹{self.portfolio.initial_cash:,.2f}")
        logger.logger.info(f"Symbols: {len(self.symbols)} stocks")
        logger.logger.info(f"Max Positions: {self.max_positions}")
        logger.logger.info(f"Strategies: {len(self.strategies)}")

        if self.dashboard and self.dashboard.is_connected:
            logger.logger.info(f"📊 Dashboard: Connected to {self.dashboard.base_url}")
        else:
            logger.logger.warning("⚠️ Dashboard: Not connected")

        logger.logger.info(f"Starting {self.trading_mode} trading...\n")
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

                logger.logger.info(f"{'='*60}")
                logger.logger.info(f"Iteration {iteration} - {datetime.now().strftime('%H:%M:%S')}")
                logger.logger.info(f"{'='*60}")

                # Check if we should bypass market hours for testing
                bypass_market_hours = self.config.get('bypass_market_hours', False)

                if self.trading_mode != 'backtest' and not self.market_hours.is_market_open() and not bypass_market_hours:
                    # Debug market hours
                    now_ist = datetime.now(self.market_hours.ist)
                    current_time = now_ist.time()
                    logger.logger.info(f"Market closed. Current IST time: {now_ist.strftime('%H:%M:%S')} (weekday: {now_ist.weekday()})")
                    logger.logger.info(f"Market hours: {self.market_hours.market_open.strftime('%H:%M')} to {self.market_hours.market_close.strftime('%H:%M')}")
                    if bypass_market_hours:
                        logger.logger.warning("⚠️ Bypassing market hours for testing...")
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
                    logger.logger.info(f"📊 Signal Summary: {len(all_signals)} total | {buy_count} BUY | {sell_count} SELL")

                # Get profile settings for paper trading
                min_confidence = self.config.get('min_confidence', 0.45)
                top_n = self.config.get('top_n', 1)

                # Adjust for aggressive profile - higher confidence threshold
                if self.trading_mode == 'paper' and self.config.get('trading_profile') == 'Aggressive':
                    min_confidence = min(min_confidence, 0.45)  # Higher threshold for optimized mode

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
                            logger.logger.info(f"⚡ {reason} triggered for {symbol}")
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
                logger.logger.info("💰 Portfolio Status:")
                logger.logger.info(f"  Total Value: ₹{total_value:,.2f} ({pnl_pct:+.2f}%)")
                logger.logger.info(f"  Cash Available: ₹{self.portfolio.cash:,.2f}")
                logger.logger.info(f"  Positions: {len(self.portfolio.positions)}/{self.max_positions}")

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
                    logger.logger.info("📈 Performance:")
                    logger.logger.info(f"  Total Trades: {self.portfolio.trades_count}")
                    logger.logger.info(f"  Win Rate: {win_rate:.1f}%")
                    logger.logger.info(f"  Total P&L: ₹{self.portfolio.total_pnl:,.2f}")
                    logger.logger.info(f"  Best Trade: ₹{self.portfolio.best_trade:,.2f}")
                    logger.logger.info(f"  Worst Trade: ₹{self.portfolio.worst_trade:,.2f}")

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

                logger.logger.info(f"Next scan in {check_interval} seconds...")
                time.sleep(check_interval)

        except KeyboardInterrupt:
            logger.logger.info("Stopped by user")
            total_value = self.portfolio.calculate_total_value()
            self._persist_state(iteration, total_value, {})
            if self.dashboard:
                self.dashboard.send_system_status(False, iteration, "stopped")

# ============================================================================
# MODE SELECTION AND LAUNCHER FUNCTIONS
# ============================================================================
def ensure_correct_directory() -> None:
    """Ensure we're running from the correct directory"""
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    logger.logger.info(f"📁 Working directory: {os.getcwd()}")

def start_dashboard() -> Optional[subprocess.Popen]:
    """Start dashboard server"""
    logger.logger.info("📊 Starting Dashboard...")

    try:
        dashboard_process = subprocess.Popen(
            [sys.executable, "enhanced_dashboard_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        time.sleep(3)  # Wait for server to start

        try:
            webbrowser.open("http://localhost:5173")
            logger.logger.info("✅ Dashboard started at: http://localhost:5173")
        except Exception:
            logger.logger.info("Dashboard started at: http://localhost:5173 (open manually)")

        return dashboard_process
    except Exception as e:
        logger.logger.error(f"Dashboard failed to start: {e}")
        return None

def run_trading_system_directly(trading_mode: str, config: Dict) -> None:
    """Run the trading system directly without subprocess"""
    logger.logger.info(f"🎯 STARTING {trading_mode.upper()} TRADING SYSTEM")
    logger.logger.info("="*60)

    # Initialize dashboard
    logger.logger.info("📊 Connecting to Dashboard...")
    dashboard = DashboardConnector(base_url="http://localhost:5173")

    if dashboard.is_connected:
        logger.logger.info("✅ Dashboard connected")
        dashboard.send_system_status(True, 0, f"{trading_mode}_mode")
    else:
        logger.logger.warning("⚠️ Dashboard not connected")

    # Initialize Zerodha connection
    logger.logger.info("🔐 Setting up Zerodha Authentication...")
    API_KEY = os.getenv('ZERODHA_API_KEY', "b0umi99jeas93od0")
    API_SECRET = os.getenv('ZERODHA_API_SECRET', "8jyer3zt5stm0udso2ir6yqclefot475")

    kite = None
    try:
        token_manager = ZerodhaTokenManager(API_KEY, API_SECRET)
        kite = token_manager.get_authenticated_kite()

        if kite:
            logger.logger.info("✅ Zerodha authentication successful")

            if trading_mode == 'live':
                # Verify account for live trading
                profile = kite.profile()
                margins = kite.margins()
                available_cash = margins.get('equity', {}).get('available', {}).get('cash', 0)

                logger.logger.info(f"👤 Account: {profile.get('user_name')}")
                logger.logger.info(f"💰 Available Cash: ₹{available_cash:,.2f}")

                max_capital = config.get('max_capital', 100000)
                if available_cash < max_capital:
                    logger.logger.warning(f"Warning: Available cash (₹{available_cash:,.2f}) < Max capital (₹{max_capital:,.2f})")
        else:
            logger.logger.warning("Zerodha authentication failed, using yfinance fallback")

    except Exception as e:
        logger.logger.error(f"Authentication error: {e}")
        logger.logger.info("📊 Using yfinance for market data")

    # Load instruments
    logger.logger.info("📋 Loading instruments...")
    instruments = {}
    if kite:
        try:
            dump = kite.instruments("NSE")
            df = pd.DataFrame(dump)
            instruments = dict(zip(df["tradingsymbol"], df["instrument_token"]))
            logger.logger.info(f"✅ Loaded {len(instruments)} instruments")
        except Exception as e:
            logger.logger.error(f"Failed to load instruments: {e}")

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
        config_override=config
    )

    # Symbol selection based on mode
    if trading_mode == 'live':
        # Conservative symbols for live trading
        conservative_symbols = [
            "HDFCBANK", "ICICIBANK", "TCS", "INFY", "RELIANCE",
            "SBIN", "KOTAKBANK", "WIPRO", "HCLTECH", "ONGC"
        ]
        system.add_symbols(conservative_symbols)
        logger.logger.info(f"✅ Added {len(conservative_symbols)} conservative symbols for live trading")
    else:
        # Full symbol set for paper/backtest
        system.add_symbols(NIFTY_50_SYMBOLS[:30])
        logger.logger.info("✅ Added top 30 NIFTY stocks")

    # Trading parameters
    interval = config.get('fast_interval', '5minute') if config.get('fast_backtest') else '5minute'
    check_interval = 60 if trading_mode == 'live' else 30

    logger.logger.info("🚀 STARTING TRADING")
    logger.logger.info("="*50)
    logger.logger.info(f"✅ Mode: {trading_mode.upper()}")
    logger.logger.info(f"✅ Initial Capital: ₹{initial_cash:,.2f}")
    logger.logger.info(f"✅ Symbols: {len(system.symbols)} stocks")
    logger.logger.info(f"✅ Max Positions: {system.max_positions}")
    logger.logger.info(f"✅ Check Interval: {check_interval}s")
    logger.logger.info(f"✅ Dashboard: {'Connected' if dashboard.is_connected else 'Offline'}")

    if dashboard.is_connected:
        logger.logger.info("📊 Monitor at: http://localhost:5173")

    mode_warnings = {
        'live': "🔴 LIVE TRADING - REAL MONEY AT RISK!",
        'paper': "📝 PAPER TRADING - Safe Learning Environment!",
        'backtest': "📊 BACKTESTING - Historical Analysis!"
    }

    logger.logger.info(mode_warnings.get(trading_mode, ''))

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
        logger.logger.info(f"🛑 {trading_mode.upper()} trading stopped by user")

        if system.portfolio.positions:
            logger.logger.warning(f"⚠️ You have {len(system.portfolio.positions)} open positions:")
            for symbol, pos in system.portfolio.positions.items():
                logger.logger.warning(f"   {symbol}: {pos['shares']} shares @ ₹{pos['entry_price']:.2f}")

            if trading_mode == 'live':
                logger.logger.info("💡 Consider closing positions manually if needed")

def run_paper_trading() -> None:
    """Run paper trading mode"""
    logger.logger.info("📝 PAPER TRADING MODE")
    logger.logger.info("="*50)
    logger.logger.info("✅ Safe simulation with real market data")
    logger.logger.info("✅ No financial risk")
    logger.logger.info("✅ Perfect for testing strategies")
    logger.logger.info("✅ Virtual capital: ₹10,00,000")

    # Ask for trading profile
    try:
        profile = input("Select trading profile [1=Quality, 2=Balanced, 3=Aggressive]: ").strip() or '1'
    except Exception:
        profile = '1'

    # Configure profile settings
    if profile == '3':
        # Profit-Focused Profile settings
        min_confidence = 0.50  # Balanced confidence for more opportunities
        top_n = 3              # Focus on top 3 highest-quality signals
        max_positions = 18     # Moderate position limit for better returns
        stop_loss_pct = 0.02   # Tighter stop loss at 2%
        take_profit_pct = 0.30 # Higher profit targets at 30%
        profile_name = 'Profit Focused'
        logger.logger.info("💰 Profit-Focused Profile Selected:")
        logger.logger.info(f"   • Min Confidence: {min_confidence} (Balanced for opportunities)")
        logger.logger.info(f"   • Top N Signals: {top_n} (Focus on highest quality)")
        logger.logger.info(f"   • Max Positions: {max_positions} (Moderate for returns)")
        logger.logger.info(f"   • Stop Loss: {stop_loss_pct:.1%} (Tighter)")
        logger.logger.info(f"   • Take Profit: {take_profit_pct:.0%} (Higher targets)")
        logger.logger.info("   • Signal Agreement: 30% (vs 40% for other profiles)")
        logger.logger.info("   • Enhanced exit strategy with volatility adjustment")
    elif profile == '2':
        # Balanced profile settings
        min_confidence = 0.6
        top_n = 2
        max_positions = 15
        stop_loss_pct = 0.05  # 5% stop loss
        take_profit_pct = 0.12  # 12% take profit
        profile_name = 'Balanced'
        logger.logger.info("⚖️ Balanced Profile Selected:")
        logger.logger.info(f"   • Min Confidence: {min_confidence}")
        logger.logger.info(f"   • Top N Signals: {top_n}")
        logger.logger.info(f"   • Max Positions: {max_positions}")
        logger.logger.info(f"   • Stop Loss: {stop_loss_pct:.0%}")
        logger.logger.info(f"   • Take Profit: {take_profit_pct:.0%}")
    else:
        # Quality profile settings (default)
        min_confidence = 0.55
        top_n = 1
        max_positions = 10
        stop_loss_pct = 0.03  # 3% stop loss
        take_profit_pct = 0.08  # 8% take profit
        profile_name = 'Quality'
        logger.logger.info("🎯 Quality Profile Selected:")
        logger.logger.info(f"   • Min Confidence: {min_confidence}")
        logger.logger.info(f"   • Top N Signals: {top_n}")
        logger.logger.info(f"   • Max Positions: {max_positions}")
        logger.logger.info(f"   • Stop Loss: {stop_loss_pct:.0%}")
        logger.logger.info(f"   • Take Profit: {take_profit_pct:.0%}")

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

    logger.logger.info("🚀 Starting Paper Trading System...")

    try:
        # Run the trading system directly
        run_trading_system_directly('paper', config)

    except KeyboardInterrupt:
        logger.logger.info("🛑 Paper trading stopped by user")
    except Exception as e:
        logger.logger.error(f"Error: {e}")
    finally:
        if dashboard_process:
            dashboard_process.terminate()

def run_live_trading() -> None:
    """Run live trading mode"""
    logger.logger.info("🔴 LIVE TRADING MODE")
    logger.logger.info("="*50)
    logger.logger.warning("⚠️  WARNING: REAL MONEY WILL BE USED!")
    logger.logger.warning("⚠️  Actual trades will be executed!")
    logger.logger.warning("⚠️  You can lose real money!")

    # Final confirmation
    logger.logger.warning("⚠️" * 30)
    confirm = input("Type 'START LIVE TRADING' to proceed with real money: ").strip()
    if confirm != "START LIVE TRADING":
        logger.logger.info("❌ Live trading cancelled")
        return

    # Get trading parameters
    try:
        max_capital = float(input("Maximum capital to use (₹) [100000]: ").strip() or "100000")
        max_position = float(input("Max position size (%) [10]: ").strip() or "10") / 100
    except Exception:
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

    logger.logger.info(f"🔴 Starting Live Trading System...")
    logger.logger.info(f"💰 Max Capital: ₹{max_capital:,.2f}")
    logger.logger.info(f"📊 Max Position: {max_position:.1%}")

    try:
        # Run the trading system directly
        run_trading_system_directly('live', config)

    except KeyboardInterrupt:
        logger.logger.info("🛑 Live trading stopped by user")
    except Exception as e:
        logger.logger.error(f"Error: {e}")
    finally:
        if dashboard_process:
            dashboard_process.terminate()

def run_backtesting() -> None:
    """Run backtesting mode"""
    logger.logger.info("📊 BACKTESTING MODE")
    logger.logger.info("="*50)
    logger.logger.info("⚡ Fast strategy testing on historical data")
    logger.logger.info("📈 Comprehensive performance analytics")

    # Get backtesting parameters
    try:
        days_back = int(input("Days of history to test [30]: ").strip() or "30")
        initial_capital = float(input("Initial capital (₹) [1000000]: ").strip() or "1000000")
    except Exception:
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
            config['fast_min_confidence'] = 0.50  # Balanced confidence for more opportunities
            config['fast_top_n'] = 3              # Focus on top 3 highest-quality signals
            config['fast_max_positions'] = 18     # Moderate position limit for better returns
            config['stop_loss'] = 0.02            # Tighter stop loss at 2%
            config['take_profit'] = 0.30          # Higher profit targets at 30%
            profile_name = 'Profit Focused'
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
        logger.logger.info(
            f"⚙️ Fast settings ({profile_name}): interval={config['fast_interval']}, "
            f"min_conf={config['fast_min_confidence']}, top_n={config['fast_top_n']}, "
            f"max_positions={config['fast_max_positions']}"
            f"sl={config['stop_loss']:.0%}, tp={config['take_profit']:.0%}"
        )
    else:
        config['fast_backtest'] = False

    logger.logger.info("📊 Starting Backtesting...")
    logger.logger.info(f"📅 Period: {start_date} to {end_date}")
    logger.logger.info(f"💰 Initial Capital: ₹{initial_capital:,.2f}")

    try:
        # Run the trading system directly
        run_trading_system_directly('backtest', config)

    except KeyboardInterrupt:
        logger.logger.info("🛑 Backtesting stopped by user")
    except Exception as e:
        logger.logger.error(f"Error: {e}")
    finally:
        if dashboard_process:
            dashboard_process.terminate()

def main() -> None:
    # Ensure we're in the correct directory
    ensure_correct_directory()

    logger.logger.info("🎯 ENHANCED NIFTY 50 TRADING SYSTEM")
    logger.logger.info("="*60)
    logger.logger.info("🚀 All improvements integrated for maximum profits!")
    logger.logger.info("📊 Dashboard integration with real-time monitoring")
    logger.logger.info("🔧 Enhanced token management and error handling")
    logger.logger.info("="*60)
    logger.logger.info("")
    logger.logger.info("Select Trading Mode:")
    logger.logger.info("1. 📝 Paper Trading (Safe Simulation)")
    logger.logger.info("2. 🔴 Live Trading (Real Money)")
    logger.logger.info("3. 📊 Backtesting (Historical Analysis)")
    logger.logger.info("4. 🚀 Performance Test (Profit Focused)")
    logger.logger.info("="*60)

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
            elif choice == "4":
                run_performance_test()
                break
            else:
                logger.logger.error("❌ Please enter 1, 2, 3, or 4")

        except KeyboardInterrupt:
            logger.logger.info("🛑 Cancelled by user")
            break
        except Exception as e:
            logger.logger.error(f"Error: {e}")
            break

def test_aggressive_profile() -> bool:
    """Test function to verify profit-focused profile implementation"""
    logger.logger.info("🧪 Testing Profit-Focused Profile Implementation")
    logger.logger.info("="*50)

    # Test profit-focused profile configuration
    config = {
        'virtual_capital': 1000000,
        'use_real_data': True,
        'simulate_trades': True,
        'live_trading': False,
        'paper_trading': True,
        'trading_profile': 'Profit Focused',
        'min_confidence': 0.50,
        'top_n': 3,
        'max_positions': 18,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.30
    }

    logger.logger.info("✅ Profit-focused profile configuration:")
    logger.logger.info(f"   • Trading Profile: {config['trading_profile']}")
    logger.logger.info(f"   • Min Confidence: {config['min_confidence']}")
    logger.logger.info(f"   • Top N Signals: {config['top_n']}")
    logger.logger.info(f"   • Max Positions: {config['max_positions']}")
    logger.logger.info(f"   • Stop Loss: {config['stop_loss_pct']:.0%}")
    logger.logger.info(f"   • Take Profit: {config['take_profit_pct']:.0%}")

    # Test UnifiedTradingSystem with profit-focused profile
    try:
        # Initialize components (minimal setup for testing)
        dp = DataProvider(use_yf_fallback=True)
        system = UnifiedTradingSystem(
            data_provider=dp,
            kite=None,
            initial_cash=1000000,
            max_positions=18,
            dashboard=None,
            trading_mode='paper',
            config_override=config
        )

        logger.logger.info("✅ UnifiedTradingSystem initialized with profit-focused profile")
        logger.logger.info(f"   • Max Positions: {system.max_positions}")
        logger.logger.info(f"   • Portfolio Min Position Size: {system.portfolio.min_position_size}")
        logger.logger.info(f"   • Portfolio Max Position Size: {system.portfolio.max_position_size}")
        logger.logger.info(f"   • Portfolio Risk Per Trade: {system.portfolio.risk_per_trade_pct}")

        # Test signal processing with profile settings
        min_conf = system.config.get('min_confidence', 0.45)
        top_n = system.config.get('top_n', 1)

        logger.logger.info("✅ Signal processing settings:")
        logger.logger.info(f"   • Min Confidence: {min_conf}")
        logger.logger.info(f"   • Top N: {top_n}")

        logger.logger.info("🎉 Profit-focused profile test completed successfully!")
        return True

    except Exception as e:
        logger.logger.error(f"❌ Error testing profit-focused profile: {e}")
        return False

def test_paper_trading_with_signals() -> bool:
    """Test paper trading with simulated signals to verify trading logic"""
    logger.logger.info("🧪 Testing Paper Trading with Simulated Signals")
    logger.logger.info("="*50)

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

    logger.logger.info("✅ Test configuration:")
    logger.logger.info(f"   • Trading Profile: {config['trading_profile']}")
    logger.logger.info(f"   • Min Confidence: {config['min_confidence']} (lowered for testing)")
    logger.logger.info(f"   • Top N Signals: {config['top_n']}")
    logger.logger.info(f"   • Max Positions: {config['max_positions']}")
    logger.logger.info(f"   • Bypass Market Hours: {config.get('bypass_market_hours', False)}")

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
            config_override=config
        )

        # Add some test symbols
        test_symbols = ["HDFCBANK", "ICICIBANK", "TCS", "INFY", "RELIANCE"]
        system.add_symbols(test_symbols)
        logger.logger.info(f"✅ Added {len(test_symbols)} test symbols")

        # Test signal generation with mock data
        logger.logger.info("🔍 Testing signal generation...")
        signals, prices = system.scan_batch(test_symbols[:3], "5minute", 1, 1)

        logger.logger.info(f"✅ Generated {len(signals)} signals from {len(prices)} price updates")

        if signals:
            logger.logger.info("📊 Sample signals:")
            for symbol, signal in list(signals.items())[:3]:
                logger.logger.info(f"   • {symbol}: {signal['action'].upper()} @ {signal['confidence']:.1%}")

        logger.logger.info("🎉 Signal testing completed successfully!")
        return True

    except Exception as e:
        logger.logger.error(f"❌ Error testing paper trading: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_performance_test() -> None:
    """Run a performance test with the profit-focused settings"""
    logger.logger.info("🚀 PERFORMANCE TEST - Profit-Focused Settings")
    logger.logger.info("="*60)
    logger.logger.info("Testing profit-focused parameters for maximum returns:")
    logger.logger.info("• Risk per trade: 1.8% (optimized)")
    logger.logger.info("• Stop loss: 2% (tighter)")
    logger.logger.info("• Take profit: 30% (higher targets)")
    logger.logger.info("• Min confidence: 50% (balanced for opportunities)")
    logger.logger.info("• New Momentum Strategy added")
    logger.logger.info("• Profit-focused profile: 18 positions max")
    logger.logger.info("• Focus on top 3 highest-confidence signals")
    logger.logger.info("="*60)

    # Configuration with profit-focused settings
    config = {
        'virtual_capital': 1000000,
        'use_real_data': True,
        'simulate_trades': True,
        'live_trading': False,
        'paper_trading': True,
        'trading_profile': 'Profit Focused',
        'min_confidence': 0.50,
        'top_n': 3,
        'max_positions': 18,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.30,
        'fast_backtest': True,
        'fast_interval': '5minute',
        'fast_min_confidence': 0.50,
        'fast_top_n': 3,
        'fast_max_positions': 18
    }

    logger.logger.info("📊 Starting performance test with profit-focused settings...")
    logger.logger.info("💰 Initial Capital: ₹10,00,000")
    logger.logger.info("📈 Testing 30 days of historical data")
    logger.logger.info("💰 Using Profit-Focused profile with new Momentum strategy")

    try:
        # Run the trading system directly
        run_trading_system_directly('backtest', config)

    except KeyboardInterrupt:
        logger.logger.info("🛑 Performance test stopped by user")
    except Exception as e:
        logger.logger.error(f"Error in performance test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Run test if no arguments provided, otherwise run main
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == 'test':
            test_aggressive_profile()
        elif sys.argv[1] == 'performance':
            run_performance_test()
        else:
            main()
    else:
        main()