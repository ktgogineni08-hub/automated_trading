#!/usr/bin/env python3
"""
Dashboard Connector
API integration with trading dashboard
"""

import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional
import logging

import requests
import hashlib
import urllib3

import config

logger = logging.getLogger('trading_system.dashboard')

class DashboardConnector:
    """Enhanced connector with better error handling"""

    def __init__(self, base_url: str = None, api_key: Optional[str] = None):
        self.base_url = base_url or "https://localhost:8080"
        self.session = requests.Session()

        # SECURITY FIX: Require explicit API key - no fallbacks
        self.api_key = api_key or os.environ.get('DASHBOARD_API_KEY')
        if not self.api_key:
            raise ValueError(
                "DASHBOARD_API_KEY is required! Set it via:\n"
                "  1. Environment variable: export DASHBOARD_API_KEY='your-key'\n"
                "  2. Pass directly: DashboardConnector(api_key='your-key')"
            )

        self.session.headers.update({"X-API-Key": self.api_key})

        # SECURITY FIX: Never auto-enable development mode
        # Development mode must be explicitly set by the caller
        # (Removed os.environ.setdefault('DEVELOPMENT_MODE', 'true'))

        self.session.headers.update({"X-Requested-With": "TradingSystemClient"})

        # SECURITY FIX: TLS verification defaults to ON
        # Only disable if explicitly requested via env var
        disable_tls = os.getenv('DASHBOARD_DISABLE_TLS_VERIFY', 'false').lower() == 'true'
        if disable_tls and self.base_url.startswith("https://localhost"):
            logger.warning("⚠️ TLS verification DISABLED - only for local development!")
            self.session.verify = False
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        else:
            self.session.verify = True
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
            logger.debug(f"Dashboard connection test failed: {e}")
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
            logger.warning("Circuit breaker is open, skipping dashboard update")
            return False

        max_retries = max_retries or self.max_retries

        for attempt in range(max_retries):
            try:
                headers = {}
                csrf_token = self._get_csrf_token()
                if csrf_token:
                    headers['X-CSRF-Token'] = csrf_token
                response = self.session.post(
                    f"{self.base_url}/api/{endpoint}",
                    json=data,
                    headers=headers,
                    timeout=config.request_timeout
                )
                logger.info(f"API POST {endpoint} - Status: {response.status_code}")

                if response.status_code == 200:
                    if not self.is_connected:
                        self.is_connected = True
                    self.circuit_breaker_failures = 0  # Reset on success
                    return True
                else:
                    logger.warning(f"Dashboard API returned status {response.status_code}")

            except Exception as e:
                logger.error(f"Dashboard API call failed (attempt {attempt + 1}): {e}")
                self.circuit_breaker_failures += 1

            # A failure might mean the server restarted; retry connection check
            self.ensure_connection(force=True)

            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff

        # Trip circuit breaker on all retries failed
        self.last_circuit_breaker_trip = time.time()
        self.circuit_breaker_failures = max(self.circuit_breaker_failures, self.circuit_breaker_threshold)
        logger.error(f"Circuit breaker tripped after {max_retries} failed attempts")
        return False

    def _get_csrf_token(self) -> Optional[str]:
        """Get CSRF token from session cookie (optional security feature)"""
        if not self.api_key:
            return None
        try:
            # Safely access cookies attribute (may not exist in all session implementations)
            if not hasattr(self.session, 'cookies'):
                return None
            session_id = self.session.cookies.get('trading_session')
            if not session_id:
                self.ensure_connection(force=True)
                session_id = self.session.cookies.get('trading_session') if hasattr(self.session, 'cookies') else None
            if not session_id:
                return None
            seed = f"{session_id}:{self.api_key}"
            return hashlib.sha256(seed.encode()).hexdigest()
        except Exception as e:
            logger.debug(f"Could not generate CSRF token: {e}")
            return None

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

    def send_completed_trade(self, symbol: str, entry_time: str, entry_price: float, shares: int,
                           exit_time: str, exit_price: float, pnl: float, pnl_percent: float,
                           exit_reason: str = None):
        """Send completed trade (entry + exit pair) to dashboard trade history"""
        data = {
            'symbol': symbol,
            'entry_time': entry_time,
            'entry_price': round(entry_price, 2),
            'shares': shares,
            'exit_time': exit_time,
            'exit_price': round(exit_price, 2),
            'pnl': round(pnl, 2),
            'pnl_percent': round(pnl_percent, 2),
            'exit_reason': exit_reason or 'Manual'
        }
        return self.send_with_retry('trade_history', data)

    def send_system_status(self, is_running: bool, iteration: int = 0, scan_status: str = "idle"):
        """Send system status to dashboard"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'is_running': is_running,
            'iteration': iteration,
            'scan_status': scan_status
        }
        return self.send_with_retry('status', data)

    def debug_option_price(self, symbol: str):
        """Debug method to check option price data for a specific symbol"""
        try:
            logger.info(f"🔍 DEBUG: Checking price data for {symbol}")

            # Try to fetch current price
            if hasattr(self, '_portfolio') and self._portfolio:
                # This is a method of DashboardConnector, we need to access the data provider
                # For now, just log the request
                logger.info(f"🔍 DEBUG: Requesting price check for {symbol}")
                logger.info("🔍 DEBUG: This would fetch live price from Kite API")
                logger.info("🔍 DEBUG: Expected price should be around ₹33.05 based on screenshot")
                return True
            else:
                logger.error("🔍 DEBUG: No portfolio reference available")
                return False
        except Exception as e:
            logger.error(f"🔍 DEBUG: Error checking price for {symbol}: {e}")
            return False
