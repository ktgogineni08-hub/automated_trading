#!/usr/bin/env python3
"""
Trading System Logger
Comprehensive logging with trade tracking
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

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

        # Console handler (INFO and above by default - shows buy/sell data)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(self.simple_formatter)
        # Filter out performance messages from console
        console_handler.addFilter(lambda record: not record.msg.startswith('PERFORMANCE'))
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
        trade_handler.addFilter(lambda record: record.levelno == 25)  # TRADE level
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
# CUSTOM EXCEPTIONS - Now imported from trading_exceptions.py
# ============================================================================
# Exceptions are imported at the top of the file

# ============================================================================
# CONFIGURATION MANAGEMENT - Now imported from trading_config.py
# ============================================================================
# Note: TradingConfig usage has been moved to runtime initialization
# to avoid import-time dependencies. Configuration is now loaded
# when needed by the trading system main entry point.

# ============================================================================
