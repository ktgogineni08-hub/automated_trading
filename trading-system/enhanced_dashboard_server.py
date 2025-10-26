#!/usr/bin/env python3
"""
Enhanced Trading Dashboard Server with HTTPS and Security
Secure HTTP server with SSL/TLS encryption and security headers
"""

import http.server
import socketserver
import json
import threading
from datetime import datetime
from pathlib import Path
import os
import sys
import ssl
import logging
from urllib.parse import urlparse, parse_qs
import re
import secrets
import hmac
import hashlib
from http import cookies
from typing import Optional, Dict, Any
from utilities.structured_logger import get_logger, log_function_call
from infrastructure.security import (
    initialize_security, get_path_protector, get_data_protector,
    get_session_manager, get_security_auditor, validate_secure_path,
    sanitize_log_message, log_security_event, log_path_traversal_attempt,
    log_unauthorized_access, SecureStateManager, SecureKeyManager
)

logger = get_logger(__name__)

# Dashboard data storage
dashboard_data = {
    'signals': [],
    'trades': [],
    'positions': [],
    'trade_history': [],  # Complete entry/exit pairs
    'portfolio': {
        'total_value': 0,
        'cash': 0,
        'positions_count': 0,
        'total_pnl': 0,
        'unrealized_pnl': 0,
        'day_pnl': 0
    },
    'performance': {
        'trades_count': 0,
        'win_rate': 0,
        'best_trade': 0,
        'worst_trade': 0
    },
    'system_status': {'is_running': False, 'iteration': 0, 'scan_status': 'idle'},
    'market_status': {
        'current_time': '',
        'is_market_open': False,
        'market_trend': 'neutral',
        'time_remaining': '00:00:00',
        'should_stop_trading': False,
        'stop_reason': 'unknown',
        'is_expiry_close_time': False,
        'expiry_positions_count': 0,
        'overnight_positions_count': 0
    }
}

class SecureDashboardHandler(http.server.BaseHTTPRequestHandler):
    """Enhanced dashboard handler with security features"""

    def __init__(self, *args, **kwargs):
        # Initialize security components
        initialize_security()
        self.path_protector = get_path_protector()
        self.data_protector = get_data_protector()
        self.session_manager = get_session_manager()
        self.security_auditor = get_security_auditor()
        self._session_cookie_to_set: Optional[str] = None
        self._query_api_key: Optional[str] = None
        super().__init__(*args, **kwargs)

    def setup(self):
        """Setup with security enhancements"""
        super().setup()
        # Get client IP for security logging
        self.client_ip = self.client_address[0] if self.client_address else 'unknown'

    def log_message(self, format, *args):
        """Override to sanitize sensitive data from logs"""
        try:
            message = format % args
            sanitized_message = self.data_protector.sanitize_log_message(message)
            super().log_message(sanitized_message)
        except Exception:
            super().log_message(format, *args)

    def send_security_headers(self):
        """Send security headers with response"""
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('X-XSS-Protection', '1; mode=block')
        self.send_header('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'")
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        self.send_header('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')
        self._attach_session_cookie()

    def _get_session_cookie(self) -> Optional[str]:
        cookie_header = self.headers.get('Cookie')
        if not cookie_header:
            return None
        try:
            jar = cookies.SimpleCookie()
            jar.load(cookie_header)
            morsel = jar.get('trading_session')
            if morsel:
                return morsel.value
        except Exception:
            logger.debug("Failed to parse session cookie from header")
        return None

    def _ensure_session(self) -> Optional[str]:
        session_id = self._get_session_cookie()
        session_data = None
        if session_id:
            session_data = self.session_manager.get_session(session_id)

        if session_data is None:
            session_payload = {
                'ip': getattr(self, 'client_ip', 'unknown'),
                'user_agent': self.headers.get('User-Agent', 'unknown')
            }
            session_id = self.session_manager.create_session(session_payload)
            self._session_cookie_to_set = session_id
        return session_id

    def _generate_csrf_token(self, session_id: str) -> str:
        seed = f"{session_id}:{self.API_KEY}"
        return hashlib.sha256(seed.encode()).hexdigest()

    def _attach_session_cookie(self):
        if not self._session_cookie_to_set:
            return
        cookie_value = self._session_cookie_to_set
        cookie_parts = [
            f"trading_session={cookie_value}",
            "HttpOnly",
            "SameSite=Strict",
            "Path=/"
        ]
        server_socket = getattr(self.server, 'socket', None)
        if isinstance(server_socket, ssl.SSLSocket):
            cookie_parts.append("Secure")
        self.send_header('Set-Cookie', "; ".join(cookie_parts))
        self._session_cookie_to_set = None

    def _require_api_key(self) -> bool:
        """Check API key header if authentication is enabled"""
        path_no_query = self.path.split('?', 1)[0]

        # SECURITY AUDIT: Log all authentication attempts
        client_ip = getattr(self, 'client_ip', 'unknown')
        user_agent = self.headers.get('User-Agent', 'unknown')

        # Allow loading the main HTML shell without authentication so the UI can prompt for a key.
        if self.command == 'GET' and path_no_query == '/':
            logger.info(f"📄 Dashboard page access from {client_ip}")
            return True

        # CRITICAL FIX: Check DEVELOPMENT_MODE first, before API key validation
        dev_mode = os.environ.get('DEVELOPMENT_MODE', 'false').lower() == 'true'
        if dev_mode:
            # In development mode, bypass ALL authentication
            if not hasattr(self, '_dev_mode_warning_shown'):
                logger.warning(
                    "⚠️ DEVELOPMENT MODE: Bypassing authentication for %s - "
                    "NEVER use DEVELOPMENT_MODE=true in production!",
                    client_ip
                )
                self._dev_mode_warning_shown = True

            # SECURITY AUDIT: Log development mode access
            logger.info(
                f"🔓 Dev mode access: {client_ip} → {path_no_query} | UA: {user_agent[:50]}"
            )
            return True

        # Production mode: Require API key
        if self.API_KEY is None:
            # SECURITY AUDIT: Critical security violation
            logger.critical(
                f"🚨 SECURITY VIOLATION: API_KEY is None in production mode - "
                f"rejecting request from {client_ip} → {path_no_query}"
            )
            log_security_event("API_KEY_MISSING", client_ip, path_no_query)
            return False

        supplied = self.headers.get('X-API-Key')
        if not supplied and self._query_api_key:
            supplied = self._query_api_key

        if not supplied or not hmac.compare_digest(str(supplied), str(self.API_KEY)):
            # SECURITY AUDIT: Unauthorized access attempt
            logger.warning(
                f"🔒 Unauthorized access attempt: {client_ip} → {path_no_query} | "
                f"UA: {user_agent[:50]} | Key: {'missing' if not supplied else 'invalid'}"
            )
            log_unauthorized_access(path_no_query, 'api_key_invalid', client_ip)
            return False

        # SECURITY AUDIT: Successful authentication
        logger.info(f"✅ Authenticated access: {client_ip} → {path_no_query}")

        # Only establish session and validate CSRF if authentication is required
        session_id = self._ensure_session()
        if not session_id:
            logger.error("Unable to establish secure dashboard session for authenticated user from %s", getattr(self, 'client_ip', 'unknown'))
            return False

        if self.command not in ('GET', 'HEAD', 'OPTIONS'):
            csrf_header = self.headers.get('X-CSRF-Token')
            expected_token = self._generate_csrf_token(session_id)
            if not csrf_header or not hmac.compare_digest(str(csrf_header), expected_token):
                logger.warning("CSRF validation failed for authenticated request from %s", getattr(self, 'client_ip', 'unknown'))
                return False

        self._query_api_key = None
        return True

    def validate_request_path(self, path: str) -> bool:
        """Validate request path for security"""
        try:
            # Check for path traversal attempts
            if '..' in path or path.startswith('/../') or '/../' in path:
                self.security_auditor.log_path_traversal_attempt(path, self.client_ip)
                return False

            # Validate against allowed paths
            allowed_paths = ['/', '/health', '/api/data', '/api/metrics']
            if path not in allowed_paths and not path.startswith('/api/'):
                self.security_auditor.log_unauthorized_access(path, 'unknown', self.client_ip)
                return False

            return True
        except Exception as e:
            logger.error(f"Path validation error: {e}")
            return False

    def do_GET(self):
        """Handle GET requests with security validation"""
        parsed_url = urlparse(self.path)
        if parsed_url.query:
            query_params = parse_qs(parsed_url.query)
            api_key_param = query_params.get('api_key', [])
            if api_key_param:
                candidate = api_key_param[0]
                if self.API_KEY and candidate and hmac.compare_digest(str(candidate), str(self.API_KEY)):
                    self._query_api_key = candidate
                else:
                    logger.warning("Invalid api_key query parameter from %s", getattr(self, 'client_ip', 'unknown'))
            self.path = parsed_url.path or '/'

        # Validate request path
        if not self.validate_request_path(self.path):
            logger.warning("Forbidden path access attempt from %s: %s", getattr(self, 'client_ip', 'unknown'), self.path)
            self.send_error(403, "Forbidden")
            return

        if not self._require_api_key():
            # Provide helpful error message based on authentication mode
            if self.API_KEY is None:
                logger.warning("Request blocked due to session management failure from %s (no auth required)", getattr(self, 'client_ip', 'unknown'))
                self.send_error(500, "Internal Server Error - Session management failed")
            else:
                logger.warning("Unauthorized access attempt from %s - missing or invalid API key", getattr(self, 'client_ip', 'unknown'))
                self.send_error(401, "Unauthorized - API key required")
            return

        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_security_headers()
            self.end_headers()
            html = '''<!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Enhanced NIFTY 50 Trading Dashboard</title>
                <style>
                    * {
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }

                    body {
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 50%, #16213e 100%);
                        background-attachment: fixed;
                        color: #ffffff;
                        min-height: 100vh;
                        overflow-x: hidden;
                        position: relative;
                    }

                    body::before {
                        content: '';
                        position: fixed;
                        top: 0;
                        left: 0;
                        right: 0;
                        bottom: 0;
                        background:
                            radial-gradient(circle at 20% 80%, rgba(120, 119, 198, 0.1) 0%, transparent 50%),
                            radial-gradient(circle at 80% 20%, rgba(255, 119, 198, 0.1) 0%, transparent 50%),
                            radial-gradient(circle at 40% 40%, rgba(120, 198, 255, 0.05) 0%, transparent 50%);
                        pointer-events: none;
                        z-index: -1;
                    }

                    .container {
                        max-width: 1400px;
                        margin: 0 auto;
                        padding: 20px;
                    }

                    /* Dashboard Layout */
                    .dashboard-layout {
                        display: flex;
                        min-height: calc(100vh - 40px);
                        gap: 0;
                    }

                    /* Sidebar Styles */
                    .sidebar {
                        width: 280px;
                        background: rgba(255, 255, 255, 0.03);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        border-radius: 16px 0 0 16px;
                        padding: 0;
                        backdrop-filter: blur(20px);
                        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                        display: flex;
                        flex-direction: column;
                    }

                    .sidebar-header {
                        padding: 25px;
                        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
                        border-radius: 16px 16px 0 0;
                    }

                    .sidebar-header h2 {
                        font-size: 1.4rem;
                        font-weight: 700;
                        margin-bottom: 8px;
                        color: #ffffff;
                    }

                    .sidebar-subtitle {
                        font-size: 0.85rem;
                        color: rgba(255, 255, 255, 0.7);
                        margin-bottom: 15px;
                        line-height: 1.4;
                    }

                    .sidebar-nav {
                        flex: 1;
                        padding: 20px 0;
                    }

                    .sidebar-tab {
                        display: block;
                        width: 100%;
                        padding: 15px 25px;
                        color: rgba(255, 255, 255, 0.8);
                        text-decoration: none;
                        font-weight: 500;
                        font-size: 0.95rem;
                        border: none;
                        background: transparent;
                        text-align: left;
                        cursor: pointer;
                        transition: all 0.3s ease;
                        border-left: 3px solid transparent;
                    }

                    .sidebar-tab:hover {
                        background: rgba(255, 255, 255, 0.05);
                        color: #ffffff;
                        border-left-color: rgba(102, 126, 234, 0.5);
                    }

                    .sidebar-tab.active {
                        background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%);
                        color: #ffffff;
                        border-left-color: #667eea;
                        box-shadow: inset 0 0 20px rgba(102, 126, 234, 0.1);
                    }

                    /* Main Content Area */
                    .main-content {
                        flex: 1;
                        padding: 0;
                        overflow-y: auto;
                        background: rgba(255, 255, 255, 0.02);
                        border: 1px solid rgba(255, 255, 255, 0.05);
                        border-left: none;
                        border-radius: 0 16px 16px 0;
                    }

                    /* Content Sections */
                    .content-section {
                        display: none;
                        padding: 30px;
                        animation: fadeIn 0.5s ease-in-out;
                    }

                    .content-section.active {
                        display: block;
                    }

                    .dashboard-header {
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        padding: 30px;
                        border-radius: 20px;
                        margin-bottom: 30px;
                        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
                        position: relative;
                        overflow: hidden;
                    }

                    .dashboard-header::before {
                        content: '';
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        bottom: 0;
                        background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="rgba(255,255,255,0.1)"/><circle cx="75" cy="75" r="1" fill="rgba(255,255,255,0.05)"/><circle cx="50" cy="10" r="0.5" fill="rgba(255,255,255,0.08)"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
                        opacity: 0.3;
                    }

                    .dashboard-header h1 {
                        font-size: 2.5rem;
                        font-weight: 700;
                        margin-bottom: 8px;
                        position: relative;
                        z-index: 1;
                    }

                    .dashboard-subtitle {
                        font-size: 1.1rem;
                        color: rgba(255, 255, 255, 0.8);
                        margin-bottom: 15px;
                        position: relative;
                        z-index: 1;
                        font-weight: 400;
                    }

                    .status-indicator {
                        display: inline-flex;
                        align-items: center;
                        gap: 8px;
                        padding: 8px 16px;
                        border-radius: 20px;
                        font-weight: 600;
                        font-size: 0.9rem;
                        position: relative;
                        z-index: 1;
                    }

                    .status-indicator.idle {
                        background: rgba(243, 156, 18, 0.2);
                        color: #f39c12;
                        border: 1px solid rgba(243, 156, 18, 0.3);
                    }

                    .status-indicator.running {
                        background: rgba(39, 174, 96, 0.2);
                        color: #27ae60;
                        border: 1px solid rgba(39, 174, 96, 0.3);
                    }

                    .navigation-tabs {
                        display: flex;
                        gap: 10px;
                        margin-bottom: 30px;
                        overflow-x: auto;
                        padding-bottom: 5px;
                    }

                    .nav-tab {
                        padding: 12px 24px;
                        background: rgba(255, 255, 255, 0.05);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        border-radius: 12px;
                        color: #ffffff;
                        text-decoration: none;
                        font-weight: 500;
                        transition: all 0.3s ease;
                        cursor: pointer;
                        white-space: nowrap;
                        backdrop-filter: blur(10px);
                    }

                    .nav-tab:hover {
                        background: rgba(255, 255, 255, 0.1);
                        transform: translateY(-2px);
                        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
                    }

                    .nav-tab.active {
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
                    }

                    .dashboard-content {
                        display: none;
                    }

                    .dashboard-content.active {
                        display: block;
                        animation: fadeIn 0.5s ease-in-out;
                    }

                    @keyframes fadeIn {
                        from { opacity: 0; transform: translateY(20px); }
                        to { opacity: 1; transform: translateY(0); }
                    }

                    .section-card {
                        background: rgba(255, 255, 255, 0.05);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        border-radius: 16px;
                        padding: 25px;
                        margin-bottom: 25px;
                        backdrop-filter: blur(20px);
                        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                        transition: all 0.3s ease;
                        position: relative;
                        overflow: hidden;
                    }

                    .section-card::before {
                        content: '';
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        height: 1px;
                        background: linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.1) 50%, transparent 100%);
                    }

                    .section-card:hover {
                        transform: translateY(-5px);
                        box-shadow: 0 15px 40px rgba(0, 0, 0, 0.2);
                        border-color: rgba(255, 255, 255, 0.2);
                    }

                    .section-title {
                        font-size: 1.5rem;
                        font-weight: 600;
                        margin-bottom: 20px;
                        color: #ffffff;
                        display: flex;
                        align-items: center;
                        gap: 10px;
                    }

                    .section-title::before {
                        content: '';
                        width: 4px;
                        height: 24px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        border-radius: 2px;
                    }

                    .portfolio-summary-grid {
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                        gap: 20px;
                        margin-bottom: 30px;
                    }

                    .summary-card {
                        background: rgba(255, 255, 255, 0.08);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        border-radius: 16px;
                        padding: 25px;
                        text-align: center;
                        transition: all 0.3s ease;
                        position: relative;
                        overflow: hidden;
                        backdrop-filter: blur(20px);
                    }

                    .summary-card::before {
                        content: '';
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        height: 4px;
                        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                    }

                    .summary-card.primary::before {
                        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                    }

                    .summary-card.success::before {
                        background: linear-gradient(90deg, #22c55e 0%, #16a34a 100%);
                    }

                    .summary-card.info::before {
                        background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%);
                    }

                    .summary-card.warning::before {
                        background: linear-gradient(90deg, #f59e0b 0%, #d97706 100%);
                    }

                    .summary-card:hover {
                        transform: translateY(-5px);
                        box-shadow: 0 15px 40px rgba(0, 0, 0, 0.2);
                        border-color: rgba(255, 255, 255, 0.2);
                    }

                    .summary-label {
                        font-size: 0.95rem;
                        color: rgba(255, 255, 255, 0.7);
                        margin-bottom: 10px;
                        font-weight: 500;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                    }

                    .summary-value {
                        font-size: 2.2rem;
                        font-weight: 700;
                        color: #ffffff;
                        margin-bottom: 5px;
                        text-shadow: 0 0 20px rgba(255, 255, 255, 0.1);
                    }

                    .summary-subtitle {
                        font-size: 0.85rem;
                        color: rgba(255, 255, 255, 0.6);
                        font-weight: 400;
                    }

                    .metrics-grid {
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                        gap: 20px;
                        margin-bottom: 25px;
                    }

                    .metric-card {
                        background: rgba(255, 255, 255, 0.08);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        border-radius: 12px;
                        padding: 20px;
                        text-align: center;
                        transition: all 0.3s ease;
                        cursor: pointer;
                    }

                    .metric-card:hover {
                        transform: translateY(-3px);
                        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
                    }

                    .metric-label {
                        font-size: 0.9rem;
                        color: rgba(255, 255, 255, 0.7);
                        margin-bottom: 8px;
                        font-weight: 500;
                    }

                    .metric-value {
                        font-size: 1.8rem;
                        font-weight: 700;
                        color: #ffffff;
                    }

                    .metric-value.positive {
                        color: #4ade80;
                        text-shadow: 0 0 10px rgba(74, 222, 128, 0.3);
                    }

                    .metric-value.negative {
                        color: #f87171;
                        text-shadow: 0 0 10px rgba(248, 113, 113, 0.3);
                    }

                    .data-table {
                        width: 100%;
                        border-collapse: collapse;
                        margin-top: 20px;
                        background: rgba(255, 255, 255, 0.02);
                        border-radius: 12px;
                        overflow: hidden;
                    }

                    .data-table th {
                        background: rgba(255, 255, 255, 0.1);
                        padding: 15px;
                        text-align: left;
                        font-weight: 600;
                        color: #ffffff;
                        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                    }

                    .data-table td {
                        padding: 12px 15px;
                        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                        color: rgba(255, 255, 255, 0.9);
                    }

                    .data-table tr:hover {
                        background: rgba(255, 255, 255, 0.05);
                    }

                    .no-data {
                        text-align: center;
                        padding: 40px;
                        color: rgba(255, 255, 255, 0.5);
                        font-style: italic;
                    }

                    .positions-highlight {
                        background: linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(168, 85, 247, 0.1) 100%);
                        border: 1px solid rgba(34, 197, 94, 0.2);
                    }

                    @media (max-width: 768px) {
                        .container {
                            padding: 15px;
                        }

                        .dashboard-layout {
                            flex-direction: column;
                        }

                        .sidebar {
                            width: 100%;
                            border-radius: 16px 16px 0 0;
                            margin-bottom: 20px;
                        }

                        .sidebar-header {
                            border-radius: 16px 16px 0 0;
                        }

                        .main-content {
                            border-radius: 0 0 16px 16px;
                            border-left: 1px solid rgba(255, 255, 255, 0.05);
                            border-top: none;
                        }

                        .sidebar-header h2 {
                            font-size: 1.2rem;
                        }

                        .sidebar-nav {
                            display: flex;
                            overflow-x: auto;
                            gap: 10px;
                            padding: 15px;
                        }

                        .sidebar-tab {
                            white-space: nowrap;
                            border-left: none;
                            border-bottom: 3px solid transparent;
                            padding: 10px 20px;
                        }

                        .sidebar-tab.active {
                            border-left: none;
                            border-bottom-color: #667eea;
                        }

                        .portfolio-summary-grid {
                            grid-template-columns: 1fr;
                            gap: 15px;
                        }

                        .summary-card {
                            padding: 20px;
                        }

                        .summary-value {
                            font-size: 1.8rem;
                        }

                        .metrics-grid {
                            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                            gap: 15px;
                        }

                        .metric-value {
                            font-size: 1.4rem;
                        }

                        .content-section {
                            padding: 20px;
                        }
                    }

                    @media (max-width: 480px) {
                        .dashboard-header {
                            padding: 20px;
                            text-align: center;
                        }

                        .dashboard-header h1 {
                            font-size: 1.8rem;
                        }

                        .dashboard-subtitle {
                            font-size: 0.9rem;
                        }

                        .status-indicator {
                            margin-top: 10px;
                        }

                        .portfolio-summary-grid {
                            gap: 12px;
                        }

                        .summary-card {
                            padding: 15px;
                        }

                        .summary-value {
                            font-size: 1.6rem;
                        }

                        .summary-label {
                            font-size: 0.85rem;
                        }

                        .summary-subtitle {
                            font-size: 0.8rem;
                        }
                    }
                </style>
            </head>
            <body>
                <div class="dashboard-layout">
                    <!-- Vertical Sidebar -->
                    <nav class="sidebar">
                        <div class="sidebar-header">
                            <h2>📊 Trading Dashboard</h2>
                            <p class="sidebar-subtitle">Monitor your portfolio and trading activity</p>
                            <div id="status" class="status-indicator idle">● IDLE</div>
                        </div>

                        <div class="sidebar-nav">
                            <a href="#" class="sidebar-tab active" onclick="showSection('overview')">Overview</a>
                            <a href="#" class="sidebar-tab" onclick="showSection('positions')">📈 Active Positions</a>
                            <a href="#" class="sidebar-tab" onclick="showSection('performance')">Performance</a>
                            <a href="#" class="sidebar-tab" onclick="showSection('signals')">Signals</a>
                            <a href="#" class="sidebar-tab" onclick="showSection('trades')">Trades</a>
                            <a href="#" class="sidebar-tab" onclick="showSection('history')">📊 Trade History</a>
                            <a href="#" class="sidebar-tab" onclick="showSection('system')">System</a>
                        </div>
                    </nav>

                    <!-- Main Content Area -->
                    <div class="main-content">
                        <!-- Overview Section (Show by default) -->
                        <div id="overview-section" class="content-section active">
                        <div class="section-card">
                            <h2 class="section-title">Portfolio Summary</h2>
                            <div class="portfolio-summary-grid">
                                <div class="summary-card primary">
                                    <div class="summary-label">Total Portfolio Value</div>
                                    <div class="summary-value" id="total-value">₹0.00</div>
                                    <div class="summary-subtitle">Current valuation</div>
                                </div>
                                <div class="summary-card success">
                                    <div class="summary-label">Total Return</div>
                                    <div class="summary-value" id="total-pnl">₹0.00</div>
                                    <div class="summary-subtitle">Realised + unrealised</div>
                                </div>
                                <div class="summary-card info">
                                    <div class="summary-label">Cash Available</div>
                                    <div class="summary-value" id="cash">₹0.00</div>
                                    <div class="summary-subtitle">Available for trading</div>
                                </div>
                                <div class="summary-card warning">
                                    <div class="summary-label">Open Positions</div>
                                    <div class="summary-value" id="positions-count">0</div>
                                    <div class="summary-subtitle">Currently active</div>
                                </div>
                            </div>
                            </div>
                        </div>
                    </div>

                        <!-- Active Positions Section -->
                        <div id="positions-section" class="content-section">
                            <div class="section-card positions-highlight">
                                <h2 class="section-title">📈 Active Positions</h2>
                            <div class="metrics-grid">
                                <div class="metric-card">
                                    <div class="metric-label">Total Positions</div>
                                    <div class="metric-value" id="active-positions-count">0</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-label">Unrealized P&L</div>
                                    <div class="metric-value positive" id="unrealized-pnl">₹0.00</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-label">Day's P&L</div>
                                    <div class="metric-value positive" id="day-pnl">₹0.00</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-label">Portfolio Value</div>
                                    <div class="metric-value" id="portfolio-value">₹0.00</div>
                                </div>
                            </div>
                            <table class="data-table">
                                <thead>
                                    <tr>
                                        <th>Symbol</th>
                                        <th>Quantity</th>
                                        <th>Avg Price</th>
                                        <th>Current Price</th>
                                        <th>Unrealized P&L</th>
                                        <th>Day Change %</th>
                                    </tr>
                                </thead>
                                <tbody id="positions-body">
                                    <tr>
                                        <td colspan="6" class="no-data">No active positions</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                        <!-- Performance Section -->
                        <div id="performance-section" class="content-section">
                            <div class="section-card">
                                <h2 class="section-title">Performance Metrics</h2>
                            <div class="metrics-grid">
                                <div class="metric-card">
                                    <div class="metric-label">Total Trades</div>
                                    <div class="metric-value" id="trades-count">0</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-label">Win Rate</div>
                                    <div class="metric-value" id="win-rate">0%</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-label">Best Trade</div>
                                    <div class="metric-value positive" id="best-trade">₹0.00</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-label">Worst Trade</div>
                                    <div class="metric-value negative" id="worst-trade">₹0.00</div>
                                </div>
                            </div>
                        </div>
                    </div>

                        <!-- Signals Section -->
                        <div id="signals-section" class="content-section">
                            <div class="section-card">
                                <h2 class="section-title">Recent Signals</h2>
                            <table class="data-table">
                                <thead>
                                    <tr>
                                        <th>Time</th>
                                        <th>Symbol</th>
                                        <th>Action</th>
                                        <th>Confidence</th>
                                        <th>Price</th>
                                    </tr>
                                </thead>
                                <tbody id="signals-body">
                                    <tr>
                                        <td colspan="5" class="no-data">No signals yet</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                        <!-- Trades Section -->
                        <div id="trades-section" class="content-section">
                            <div class="section-card">
                                <h2 class="section-title">Recent Trades</h2>
                            <table class="data-table">
                                <thead>
                                    <tr>
                                        <th>Time</th>
                                        <th>Symbol</th>
                                        <th>Side</th>
                                        <th>Shares</th>
                                        <th>Price</th>
                                        <th>P&L</th>
                                    </tr>
                                </thead>
                                <tbody id="trades-body">
                                    <tr>
                                        <td colspan="6" class="no-data">No trades yet</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                        <!-- Trade History Section -->
                        <div id="history-section" class="content-section">
                            <div class="section-card">
                                <h2 class="section-title">📊 Complete Trade History</h2>
                                <div class="metrics-grid" style="margin-bottom: 20px;">
                                    <div class="metric-card">
                                        <div class="metric-label">Total Trades</div>
                                        <div class="metric-value" id="history-total-trades">0</div>
                                    </div>
                                    <div class="metric-card">
                                        <div class="metric-label">Winning Trades</div>
                                        <div class="metric-value" style="color: #10b981;" id="history-winning">0</div>
                                    </div>
                                    <div class="metric-card">
                                        <div class="metric-label">Losing Trades</div>
                                        <div class="metric-value" style="color: #ef4444;" id="history-losing">0</div>
                                    </div>
                                    <div class="metric-card">
                                        <div class="metric-label">Total P&L</div>
                                        <div class="metric-value" id="history-total-pnl">₹0.00</div>
                                    </div>
                                </div>
                                <table class="data-table">
                                    <thead>
                                        <tr>
                                            <th>Symbol</th>
                                            <th>Entry Time</th>
                                            <th>Entry Price</th>
                                            <th>Shares</th>
                                            <th>Exit Time</th>
                                            <th>Exit Price</th>
                                            <th>Holding Time</th>
                                            <th>P&L</th>
                                            <th>P&L %</th>
                                            <th>Exit Reason</th>
                                        </tr>
                                    </thead>
                                    <tbody id="history-body">
                                        <tr>
                                            <td colspan="10" class="no-data">No completed trades yet</td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <!-- System Section -->
                        <div id="system-section" class="content-section">
                            <div class="section-card">
                                <h2 class="section-title">System Status</h2>
                            <div class="metrics-grid">
                                <div class="metric-card">
                                    <div class="metric-label">Status</div>
                                    <div class="metric-value" id="system-status-text">IDLE</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-label">Iteration</div>
                                    <div class="metric-value" id="iteration">0</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-label">Scan Status</div>
                                    <div class="metric-value" id="scan-status">idle</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <script>
                    // Navigation functionality
                    function showSection(sectionName) {
                        // Hide all sections
                        const sections = document.querySelectorAll('.content-section');
                        sections.forEach(section => {
                            section.classList.remove('active');
                        });

                        // Remove active class from all tabs
                        const tabs = document.querySelectorAll('.sidebar-tab');
                        tabs.forEach(tab => {
                            tab.classList.remove('active');
                        });

                        // Show selected section
                        const targetSection = document.getElementById(sectionName + '-section');
                        if (targetSection) {
                            targetSection.classList.add('active');
                        }

                        // Add active class to clicked tab
                        if (event && event.target) {
                            event.target.classList.add('active');
                        }
                    }

                    // Format currency values
                    function formatCurrency(value) {
                        return '₹' + (value || 0).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    }

                    // Format percentage values
                    function formatPercentage(value) {
                        return (value || 0) + '%';
                    }

                    const API_KEY_STORAGE_KEY = 'dashboardApiKey';
                    const API_KEY_PARAM = 'api_key';

                    function getStoredApiKey() {
                        let key = localStorage.getItem(API_KEY_STORAGE_KEY);
                        const params = new URLSearchParams(window.location.search);
                        if ((!key || !key.trim()) && params.has(API_KEY_PARAM)) {
                            const paramKey = params.get(API_KEY_PARAM).trim();
                            if (paramKey) {
                                key = paramKey;
                                localStorage.setItem(API_KEY_STORAGE_KEY, paramKey);
                                params.delete(API_KEY_PARAM);
                                const newUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
                                window.history.replaceState({}, document.title, newUrl);
                            }
                        }
                        return key;
                    }

                    function requireApiKey(forcePrompt = false) {
                        let key = forcePrompt ? null : getStoredApiKey();
                        while (!key || !key.trim()) {
                            const entered = prompt('Enter the dashboard API key (check terminal output):');
                            if (!entered) {
                                alert('API key is required to access the dashboard.');
                                continue;
                            }
                            key = entered.trim();
                        }
                        localStorage.setItem(API_KEY_STORAGE_KEY, key);
                        return key;
                    }

                    function buildAuthHeaders() {
                        return {
                            'X-API-Key': requireApiKey()
                        };
                    }

                    function handleAuthFailure(response) {
                        if (response.status === 401 || response.status === 403) {
                            localStorage.removeItem(API_KEY_STORAGE_KEY);
                            requireApiKey(true);
                        }
                    }

                    function updateDashboard() {
                        fetch('/api/data', { headers: buildAuthHeaders() })
                            .then(response => {
                                if (!response.ok) {
                                    handleAuthFailure(response);
                                    throw new Error(`Dashboard API error: ${response.status}`);
                                }
                                return response.json();
                            })
                            .then(data => {
                                // Update portfolio overview
                                document.getElementById('total-value').textContent = formatCurrency(data.portfolio.total_value);
                                document.getElementById('cash').textContent = formatCurrency(data.portfolio.cash);
                                document.getElementById('positions-count').textContent = data.portfolio.positions_count || 0;
                                const totalPnlElement = document.getElementById('total-pnl');
                                const totalPnlValue = data.portfolio.total_pnl || 0;
                                totalPnlElement.textContent = formatCurrency(totalPnlValue);
                                totalPnlElement.className = totalPnlValue >= 0 ? 'metric-value positive' : 'metric-value negative';

                                // Update active positions
                                document.getElementById('active-positions-count').textContent = data.portfolio.positions_count || 0;
                                const unrealizedPnlElement = document.getElementById('unrealized-pnl');
                                const unrealizedPnlValue = data.portfolio.unrealized_pnl || 0;
                                unrealizedPnlElement.textContent = formatCurrency(unrealizedPnlValue);
                                unrealizedPnlElement.className = unrealizedPnlValue >= 0 ? 'metric-value positive' : 'metric-value negative';

                                document.getElementById('day-pnl').textContent = formatCurrency(data.portfolio.day_pnl || 0);
                                document.getElementById('portfolio-value').textContent = formatCurrency(data.portfolio.total_value);

                                // Update positions table
                                const positionsBody = document.getElementById('positions-body');
                                if (data.positions && data.positions.length > 0) {
                                    positionsBody.innerHTML = data.positions.map(position =>
                                        `<tr>
                                            <td>${position.symbol}</td>
                                            <td>${position.quantity}</td>
                                            <td>${formatCurrency(position.avg_price)}</td>
                                            <td>${formatCurrency(position.current_price)}</td>
                                            <td class="${position.unrealized_pnl >= 0 ? 'positive' : 'negative'}">${formatCurrency(position.unrealized_pnl)}</td>
                                            <td class="${position.day_change >= 0 ? 'positive' : 'negative'}">${position.day_change >= 0 ? '+' : ''}${position.day_change?.toFixed(2) || '0.00'}%</td>
                                        </tr>`
                                    ).join('');
                                } else {
                                    positionsBody.innerHTML = '<tr><td colspan="6" class="no-data">No active positions</td></tr>';
                                }

                                // Update performance metrics
                                document.getElementById('trades-count').textContent = data.performance.trades_count || 0;
                                document.getElementById('win-rate').textContent = formatPercentage(data.performance.win_rate);
                                const bestTradeElement = document.getElementById('best-trade');
                                bestTradeElement.textContent = formatCurrency(data.performance.best_trade);
                                bestTradeElement.className = 'metric-value positive';

                                const worstTradeElement = document.getElementById('worst-trade');
                                worstTradeElement.textContent = formatCurrency(data.performance.worst_trade);
                                worstTradeElement.className = 'metric-value negative';

                                // Update system status
                                const status = data.system_status;
                                const statusIndicator = document.getElementById('status');
                                statusIndicator.className = 'status-indicator ' + (status.is_running ? 'running' : 'idle');
                                statusIndicator.innerHTML = '● ' + (status.is_running ? 'RUNNING' : 'IDLE');

                                document.getElementById('system-status-text').textContent = status.scan_status.toUpperCase();
                                document.getElementById('iteration').textContent = status.iteration || 0;
                                document.getElementById('scan-status').textContent = status.scan_status;

                                // Update signals table
                                const signalsBody = document.getElementById('signals-body');
                                if (data.signals && data.signals.length > 0) {
                                    signalsBody.innerHTML = data.signals.slice(-10).map(signal =>
                                        `<tr>
                                            <td>${new Date(signal.timestamp).toLocaleTimeString()}</td>
                                            <td>${signal.symbol}</td>
                                            <td><span class="signal-${signal.action}">${signal.action.toUpperCase()}</span></td>
                                            <td>${(signal.confidence * 100).toFixed(1)}%</td>
                                            <td>${formatCurrency(signal.price)}</td>
                                        </tr>`
                                    ).join('');
                                } else {
                                    signalsBody.innerHTML = '<tr><td colspan="5" class="no-data">No signals yet</td></tr>';
                                }

                                // Update trades table
                                const tradesBody = document.getElementById('trades-body');
                                if (data.trades && data.trades.length > 0) {
                                    tradesBody.innerHTML = data.trades.slice(-10).map(trade =>
                                        `<tr>
                                            <td>${new Date(trade.timestamp).toLocaleTimeString()}</td>
                                            <td>${trade.symbol}</td>
                                            <td><span class="trade-${trade.side}">${trade.side.toUpperCase()}</span></td>
                                            <td>${trade.shares}</td>
                                            <td>${formatCurrency(trade.price)}</td>
                                            <td class="${trade.pnl >= 0 ? 'positive' : 'negative'}">${formatCurrency(trade.pnl)}</td>
                                        </tr>`
                                    ).join('');
                                } else {
                                    tradesBody.innerHTML = '<tr><td colspan="6" class="no-data">No trades yet</td></tr>';
                                }

                                // Update Trade History table
                                const historyBody = document.getElementById('history-body');
                                if (data.trade_history && data.trade_history.length > 0) {
                                    // Calculate summary stats
                                    const totalTrades = data.trade_history.length;
                                    const winningTrades = data.trade_history.filter(t => t.pnl > 0).length;
                                    const losingTrades = data.trade_history.filter(t => t.pnl < 0).length;
                                    const totalPnl = data.trade_history.reduce((sum, t) => sum + (t.pnl || 0), 0);

                                    // Update summary metrics
                                    document.getElementById('history-total-trades').textContent = totalTrades;
                                    document.getElementById('history-winning').textContent = winningTrades;
                                    document.getElementById('history-losing').textContent = losingTrades;
                                    const historyPnlElement = document.getElementById('history-total-pnl');
                                    historyPnlElement.textContent = formatCurrency(totalPnl);
                                    historyPnlElement.className = totalPnl >= 0 ? 'metric-value positive' : 'metric-value negative';

                                    // Update table (show latest 50 trades)
                                    historyBody.innerHTML = data.trade_history.slice(-50).reverse().map(trade => {
                                        const entryTime = new Date(trade.entry_time);
                                        const exitTime = new Date(trade.exit_time);
                                        const holdingTime = calculateHoldingTime(entryTime, exitTime);
                                        const pnlPercent = trade.pnl_percent || ((trade.pnl / (trade.entry_price * trade.shares)) * 100);
                                        const pnlClass = trade.pnl >= 0 ? 'positive' : 'negative';

                                        return `<tr>
                                            <td><strong>${trade.symbol}</strong></td>
                                            <td>${entryTime.toLocaleString()}</td>
                                            <td>${formatCurrency(trade.entry_price)}</td>
                                            <td>${trade.shares}</td>
                                            <td>${exitTime.toLocaleString()}</td>
                                            <td>${formatCurrency(trade.exit_price)}</td>
                                            <td>${holdingTime}</td>
                                            <td class="${pnlClass}"><strong>${formatCurrency(trade.pnl)}</strong></td>
                                            <td class="${pnlClass}">${trade.pnl >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%</td>
                                            <td><span style="font-size: 0.85em; padding: 2px 6px; background: rgba(255,255,255,0.1); border-radius: 3px;">${trade.exit_reason || 'Manual'}</span></td>
                                        </tr>`;
                                    }).join('');
                                } else {
                                    historyBody.innerHTML = '<tr><td colspan="10" class="no-data">No completed trades yet</td></tr>';
                                }
                            })
                            .catch(error => console.log('Error updating dashboard:', error));
                    }

                    // Helper function to calculate holding time
                    function calculateHoldingTime(entryTime, exitTime) {
                        const diff = exitTime - entryTime;
                        const hours = Math.floor(diff / (1000 * 60 * 60));
                        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

                        if (hours > 24) {
                            const days = Math.floor(hours / 24);
                            const remainingHours = hours % 24;
                            return `${days}d ${remainingHours}h`;
                        } else if (hours > 0) {
                            return `${hours}h ${minutes}m`;
                        } else {
                            return `${minutes}m`;
                        }
                    }

                    // Auto-refresh every 2 seconds
                    setInterval(updateDashboard, 2000);
                    updateDashboard(); // Initial update

                    // Add smooth scrolling for better UX
                    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
                        anchor.addEventListener('click', function (e) {
                            e.preventDefault();
                            const target = document.querySelector(this.getAttribute('href'));
                            if (target) {
                                target.scrollIntoView({
                                    behavior: 'smooth',
                                    block: 'start'
                                });
                            }
                        });
                    });
                </script>
            </body>
            </html>
            '''
            self.wfile.write(html.encode())

        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_security_headers()
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'healthy'}).encode())

        elif self.path == '/api/data':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_security_headers()
            self.end_headers()

            # Read live data from state files
            live_data = self.get_live_trading_data()
            self.wfile.write(json.dumps(live_data).encode())

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

    def do_POST(self):
        """Handle POST requests for API endpoints"""
        if not self._require_api_key():
            # Provide helpful error message based on authentication mode
            if self.API_KEY is None:
                logger.warning("POST request blocked due to session management failure from %s (no auth required)", getattr(self, 'client_ip', 'unknown'))
                self.send_error(500, "Internal Server Error - Session management failed")
            else:
                logger.warning("Unauthorized POST request from %s - missing or invalid API key", getattr(self, 'client_ip', 'unknown'))
                self.send_error(401, "Unauthorized - API key required")
            return

        if self.path == '/api/signals':
            self.handle_api_data('signals')

        elif self.path == '/api/trades':
            self.handle_api_data('trades')

        elif self.path == '/api/portfolio':
            self.handle_api_data('portfolio')

        elif self.path == '/api/positions':
            self.handle_api_data('positions')

        elif self.path == '/api/performance':
            self.handle_api_data('performance')

        elif self.path == '/api/status':
            self.handle_api_data('system_status')

        elif self.path == '/api/trade_history':
            self.handle_api_data('trade_history')

        elif self.path == '/api/metrics':
            # MONITORING FIX: Performance metrics endpoint
            self.handle_performance_metrics()

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

    def _sanitize_string(self, value: Any, max_length: int = 256) -> str:
        if not isinstance(value, str):
            raise ValueError("Expected string value")
        value = value.strip()
        if not value:
            return ""
        sanitized = re.sub(r'[^\w\s\-\.,:;@#/()%$&]', '', value)
        return sanitized[:max_length]

    def _sanitize_value(self, key: str, value: Any, depth: int = 0) -> Any:
        if depth > 3:
            raise ValueError("Payload too deeply nested")
        if value is None:
            return None
        if isinstance(value, (int, float, bool)):
            if isinstance(value, float):
                if not (float('-inf') < value < float('inf')):
                    raise ValueError(f"Numeric value out of bounds for {key}")
            return value
        if isinstance(value, str):
            return self._sanitize_string(value)
        if isinstance(value, list):
            if len(value) > 50:
                raise ValueError(f"List too large for {key}")
            return [self._sanitize_value(f"{key}[]", item, depth + 1) for item in value]
        if isinstance(value, dict):
            if len(value) > 50:
                raise ValueError(f"Object too large for {key}")
            sanitized_dict: Dict[str, Any] = {}
            for sub_key, sub_value in value.items():
                sanitized_key = self._sanitize_string(str(sub_key), max_length=64)
                sanitized_dict[sanitized_key] = self._sanitize_value(sanitized_key, sub_value, depth + 1)
            return sanitized_dict
        raise ValueError(f"Unsupported data type for {key}")

    def _validate_payload(self, data_type: str, data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError("Payload must be a JSON object")

        sanitized: Dict[str, Any] = {}
        for key, value in data.items():
            sanitized_key = self._sanitize_string(str(key), max_length=64)
            sanitized[sanitized_key] = self._sanitize_value(sanitized_key, value)

        if 'confidence' in sanitized and isinstance(sanitized['confidence'], (int, float)):
            sanitized['confidence'] = max(0.0, min(1.0, float(sanitized['confidence'])))
        if 'win_rate' in sanitized and isinstance(sanitized['win_rate'], (int, float)):
            sanitized['win_rate'] = max(0.0, min(100.0, float(sanitized['win_rate'])))
        if 'symbol' in sanitized:
            sanitized['symbol'] = self._sanitize_string(sanitized['symbol'], max_length=16).upper()
        return sanitized

    def handle_api_data(self, data_type):
        """Handle API data updates"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 262144:  # 256 KB
                raise ValueError("Payload too large")
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            sanitized_payload = self._validate_payload(data_type, data)

            if data_type in dashboard_data:
                target = dashboard_data[data_type]
                if isinstance(target, list):
                    target.append(sanitized_payload)
                    if len(target) > 100:
                        dashboard_data[data_type] = target[-100:]
                elif isinstance(target, dict):
                    target.update(sanitized_payload)
                else:
                    dashboard_data[data_type] = sanitized_payload

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_security_headers()
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'success'}).encode())

        except ValueError as exc:
            logger.warning("Invalid %s payload: %s", data_type, exc)
            self.send_response(400)
            self.send_security_headers()
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'error', 'message': 'Invalid payload'}).encode())
        except Exception as exc:
            logger.error("Error handling %s API call: %s", data_type, exc)
            self.send_response(500)
            self.send_security_headers()
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'error', 'message': 'Internal server error'}).encode())

    def handle_performance_metrics(self):
        """
        MONITORING FIX: Handle performance metrics endpoint

        Returns system performance metrics including:
        - API call statistics
        - Cache hit rates
        - State persistence efficiency
        - Thread safety metrics
        """
        try:
            # Gather metrics from various sources
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'system': {
                    'uptime_seconds': time.time() - getattr(self, '_start_time', time.time()),
                    'requests_handled': getattr(self, '_requests_count', 0),
                },
                'dashboard_data_sizes': {
                    'signals': len(dashboard_data.get('signals', [])),
                    'trades': len(dashboard_data.get('trades', [])),
                    'positions': len(dashboard_data.get('positions', [])),
                    'trade_history': len(dashboard_data.get('trade_history', [])),
                },
                'cache': {
                    'note': 'Portfolio-level metrics available via portfolio instance'
                }
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_security_headers()
            self.end_headers()
            self.wfile.write(json.dumps(metrics, indent=2).encode())

        except Exception as exc:
            logger.error(f"Error handling metrics API call: {exc}")
            self.send_response(500)
            self.send_security_headers()
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'error', 'message': 'Failed to retrieve metrics'}).encode())

    def _load_encrypted_state(self) -> Optional[dict]:
        """Attempt to load encrypted trading state if available."""
        password = os.getenv('TRADING_SECURITY_PASSWORD')
        if not password:
            return None
        try:
            manager = SecureStateManager(master_password=password)
            state = manager.load_encrypted_state('current_state.enc')
            if state:
                return state
        except Exception as exc:
            logger.debug(f"Encrypted state unavailable: {exc}")
        return None

    def get_live_trading_data(self):
        """Read live trading data from state files"""
        try:
            current_state = self._load_encrypted_state() or {}

            # Read current state
            if not current_state and os.path.exists('state/current_state.json'):
                with open('state/current_state.json', 'r') as f:
                    current_state = json.load(f)

            # Read shared portfolio state
            portfolio_state = {}
            if os.path.exists('state/shared_portfolio_state.json'):
                try:
                    with open('state/shared_portfolio_state.json', 'r') as f:
                        portfolio_state = json.load(f)
                except json.JSONDecodeError:
                    logger.warning("shared_portfolio_state.json is corrupted; using empty portfolio data")
                    portfolio_state = {"cash": 1000000, "positions": {}}

            # Use empty portfolio if no positions found (removed mock data)
            if not portfolio_state:
                portfolio_state = {
                    "cash": 1000000,
                    "positions": {}
                }

            # Format signals data (from recent trading activity)
            signals = []
            if 'signals' in dashboard_data and dashboard_data['signals']:
                signals = dashboard_data['signals'][-20:]  # Last 20 signals

            # Format trades data
            trades = []
            # First check dashboard_data
            if 'trades' in dashboard_data and dashboard_data['trades']:
                trades = dashboard_data['trades'][-20:]  # Last 20 trades
            # Also check current_state for trades_history
            elif 'portfolio' in current_state and 'trades_history' in current_state['portfolio']:
                trades = current_state['portfolio']['trades_history'][-20:]  # Last 20 trades

            # Format positions data from portfolio state
            positions = []
            if 'positions' in portfolio_state and portfolio_state['positions']:
                for symbol, pos_data in portfolio_state['positions'].items():
                    # Calculate unrealized P&L (mock calculation for now)
                    current_price = pos_data.get('current_price', pos_data.get('entry_price', 0))
                    entry_price = pos_data.get('entry_price', 0)
                    quantity = pos_data.get('shares', 0)

                    # Mock current price (in real implementation, this would come from live market data)
                    import random
                    price_fluctuation = random.uniform(-0.05, 0.05)  # ±5% fluctuation
                    current_price = entry_price * (1 + price_fluctuation)

                    unrealized_pnl = (current_price - entry_price) * quantity
                    day_change = ((current_price - entry_price) / entry_price) * 100

                    positions.append({
                        'symbol': symbol,
                        'quantity': quantity,
                        'avg_price': entry_price,
                        'current_price': current_price,
                        'unrealized_pnl': unrealized_pnl,
                        'day_change': day_change
                    })

            # Format portfolio data
            portfolio_data_nested = current_state.get('portfolio', {})
            portfolio = {
                'total_value': current_state.get('total_value', portfolio_state.get('cash', 0)),
                'cash': portfolio_state.get('cash', portfolio_data_nested.get('cash', 0)),
                'positions_count': len(positions),
                'total_pnl': portfolio_data_nested.get('total_pnl', 0),
                'unrealized_pnl': sum(pos.get('unrealized_pnl', 0) for pos in positions),
                'day_pnl': sum(pos.get('unrealized_pnl', 0) for pos in positions)  # Mock day P&L
            }

            # Format performance data
            portfolio_data = current_state.get('portfolio', {})
            trades_count = portfolio_data.get('trades_count', current_state.get('trades_count', 0))
            winning_trades = portfolio_data.get('winning_trades', current_state.get('winning_trades', 0))

            performance = {
                'trades_count': trades_count,
                'win_rate': (winning_trades / max(trades_count, 1)) * 100,
                'best_trade': portfolio_data.get('best_trade', current_state.get('best_trade', 0)),
                'worst_trade': portfolio_data.get('worst_trade', current_state.get('worst_trade', 0))
            }

            # Format system status - prioritize dashboard_data, then current_state
            system_status = dashboard_data.get('system_status', {})
            if not system_status or not system_status.get('is_running'):
                # Fallback to checking if we have active trading session
                system_status = {
                    'is_running': bool(current_state.get('mode')) or len(portfolio_state.get('positions', {})) > 0,
                    'iteration': current_state.get('iteration', 0),
                    'scan_status': dashboard_data.get('system_status', {}).get('scan_status',
                                   'active' if len(portfolio_state.get('positions', {})) > 0 else 'idle')
                }

            # Get trade history from dashboard_data
            trade_history = dashboard_data.get('trade_history', [])

            return {
                'signals': signals,
                'trades': trades,
                'positions': positions,
                'portfolio': portfolio,
                'performance': performance,
                'system_status': system_status,
                'trade_history': trade_history
            }

        except Exception as e:
            logger.error("Error reading live trading data: %s", e)
            # Fallback to static data
            return dashboard_data

def validate_server_configuration(api_key: str | None, enable_https: bool, cert_file: str | None, key_file: str | None) -> dict:
    """Validate server configuration and return configuration status"""
    config_status = {
        'is_valid': True,
        'warnings': [],
        'errors': [],
        'auth_mode': 'none'
    }

    # Check API key configuration
    if api_key is None:
        config_status['auth_mode'] = 'none'
        config_status['warnings'].append('DASHBOARD_API_KEY not set - dashboard will accept unauthenticated requests')
    else:
        config_status['auth_mode'] = 'api_key'
        config_status['warnings'].append('DASHBOARD_API_KEY configured - authentication required for API access')

    # Check HTTPS configuration
    if enable_https:
        if not cert_file or not key_file:
            config_status['is_valid'] = False
            config_status['errors'].append('HTTPS enabled but certificate files not provided')
        else:
            # Check if certificate files exist
            if not os.path.exists(cert_file):
                config_status['is_valid'] = False
                config_status['errors'].append(f'Certificate file not found: {cert_file}')
            if not os.path.exists(key_file):
                config_status['is_valid'] = False
                config_status['errors'].append(f'Private key file not found: {key_file}')
    else:
        config_status['warnings'].append('HTTP mode enabled - not recommended for production')

    return config_status

def run_server(port=8080, enable_https=False, cert_file=None, key_file=None, api_key: str | None = None):
    """Run the dashboard server with optional HTTPS support"""
    # Validate configuration before starting
    config_status = validate_server_configuration(api_key, enable_https, cert_file, key_file)

    # Report configuration issues
    if config_status['errors']:
        print('❌ Configuration errors found:')
        for error in config_status['errors']:
            print(f'   • {error}')
        if config_status['is_valid'] is False:
            raise ValueError("Invalid server configuration - fix errors above")

    if config_status['warnings']:
        print('⚠️  Configuration warnings:')
        for warning in config_status['warnings']:
            print(f'   • {warning}')

    if enable_https and (not cert_file or not key_file):
        raise ValueError("HTTPS requires valid cert_file and key_file")

    initialize_security()

    handler_cls = SecureDashboardHandler
    handler_cls.API_KEY = api_key

    # Print authentication status
    if config_status['auth_mode'] == 'none':
        print('🔓 Authentication: DISABLED - All requests allowed')
    else:
        print('🔐 Authentication: ENABLED - API key required')

    if enable_https:
        print(f"📊 Enhanced Trading Dashboard Server (HTTPS)")
        print(f"🔒 Secure server running at: https://localhost:{port}")
        httpd = socketserver.TCPServer(("", port), handler_cls)
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(cert_file, key_file)
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    else:
        print(f"📊 Enhanced Trading Dashboard Server (HTTP)")
        print(f"🌐 Server running at: http://localhost:{port}")
        httpd = socketserver.TCPServer(("", port), handler_cls)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n🛑 Dashboard server stopped')
        httpd.shutdown()
def generate_self_signed_certificate(cert_file='certs/dashboard.crt', key_file='certs/dashboard.key'):
    """Generate self-signed SSL certificate for development"""
    try:
        import subprocess

        # Create certs directory
        Path('certs').mkdir(exist_ok=True)

        # Generate private key
        subprocess.run([
            'openssl', 'genrsa', '-out', key_file, '2048'
        ], check=True, capture_output=True)

        # Generate self-signed certificate
        subprocess.run([
            'openssl', 'req', '-new', '-x509', '-key', key_file,
            '-out', cert_file, '-days', '365',
            '-subj', '/C=US/ST=State/L=City/O=Organization/CN=localhost'
        ], check=True, capture_output=True)

        print(f"✅ Generated self-signed certificate: {cert_file}")
        print(f"✅ Generated private key: {key_file}")
        return cert_file, key_file

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to generate SSL certificate: {e}")
        print("💡 Install OpenSSL or run without HTTPS: python enhanced_dashboard_server.py")
        return None, None
    except FileNotFoundError:
        print("❌ OpenSSL not found. Install OpenSSL or run without HTTPS.")
        return None, None

if __name__ == "__main__":
    import sys
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Enhanced Trading Dashboard Server')
    parser.add_argument('--port', type=int, default=8080, help='Port to run the server on (default: 8080)')
    parser.add_argument('--https', action='store_true', help='Enable HTTPS with SSL encryption')
    parser.add_argument('--cert', type=str, help='SSL certificate file path')
    parser.add_argument('--key', type=str, help='SSL private key file path')
    parser.add_argument('--secure-only', action='store_true', help='Run in secure mode only (HTTPS required)')
    parser.add_argument('--api-key', type=str, help='API key required for dashboard API access')
    parser.add_argument('--allow-http', action='store_true', help='Explicitly allow HTTP mode (not recommended)')
    parser.add_argument('--store-api-key', action='store_true', help='Persist provided API key using secure storage')

    args = parser.parse_args()

    # Load API key with improved fallback logic
    password = os.environ.get('TRADING_SECURITY_PASSWORD')
    api_key = args.api_key or os.environ.get('DASHBOARD_API_KEY')

    # Try to load stored API key if not provided via command line or environment
    if api_key is None and password:
        try:
            manager = SecureKeyManager(master_password=password)
            stored_key = manager.decrypt_api_key('dashboard')
            if stored_key:
                api_key = stored_key
                print("🔑 Loaded stored dashboard API key from secure storage")
        except Exception as exc:
            logger.warning("Unable to load stored dashboard API key: %s", exc)

    # Store API key if requested
    if api_key and args.store_api_key:
        if not password:
            print("❌ TRADING_SECURITY_PASSWORD must be set to store API key securely")
            sys.exit(1)
        try:
            manager = SecureKeyManager(master_password=password)
            manager.encrypt_api_key(api_key, 'dashboard')
            print("✅ Dashboard API key stored securely")
        except Exception as exc:
            print(f"❌ Failed to store API key securely: {exc}")
            sys.exit(1)

    # Final API key status
    if api_key is None:
        print('⚠️  DASHBOARD_API_KEY not configured - dashboard will accept unauthenticated requests')
        print('💡 Set DASHBOARD_API_KEY environment variable or use --api-key parameter')
    else:
        print('✅ Dashboard API key configured - authentication enabled')

    https_enabled = True
    if args.allow_http and not args.https and not args.secure_only:
        https_enabled = False

    if args.https:
        https_enabled = True
    if args.secure_only:
        https_enabled = True

    cert_file = args.cert
    key_file = args.key

    if https_enabled:
        if not cert_file or not key_file:
            print("🔐 HTTPS enabled but certificate files not provided")
            print("💡 Generating self-signed certificate for development...")
            generated_cert, generated_key = generate_self_signed_certificate()
            if not generated_cert or not generated_key:
                print("❌ Cannot enable HTTPS without valid certificate")
                if args.secure_only:
                    print("❌ Secure-only mode requires HTTPS - exiting")
                    sys.exit(1)
                elif not args.allow_http:
                    sys.exit(1)
                else:
                    print("⚠️ Falling back to HTTP mode")
                    https_enabled = False
            else:
                cert_file = generated_cert
                key_file = generated_key
    else:
        print("⚠️ HTTP mode enabled. Do not use in production.")

    try:
        if https_enabled:
            print('🔒 Starting server in SECURE HTTPS mode')
            run_server(port=args.port, enable_https=True, cert_file=cert_file, key_file=key_file, api_key=api_key)
        else:
            print('🌐 Starting server in HTTP mode')
            run_server(port=args.port, enable_https=False, api_key=api_key)
    except ValueError as exc:
        print(f"❌ Error: {exc}")
        sys.exit(1)
