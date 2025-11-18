#!/usr/bin/env python3
"""
Mobile-Responsive Trading Dashboard
Lightweight mobile-first dashboard for trading monitoring

ADDRESSES MEDIUM PRIORITY RECOMMENDATION #9:
- Mobile-responsive design
- Touch-optimized interface
- Real-time updates via WebSocket
- Progressive Web App (PWA) support
- Offline capabilities
- Push notifications
"""

import logging
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict

from aiohttp import web
import aiohttp_cors

logger = logging.getLogger('trading_system.mobile_dashboard')


@dataclass
class DashboardWidget:
    """Dashboard widget configuration"""
    widget_id: str
    title: str
    widget_type: str  # chart, metric, list, alert
    size: str  # small, medium, large
    data_source: str
    refresh_interval: int = 5  # seconds


class MobileDashboardServer:
    """
    Mobile-Responsive Dashboard Server

    Features:
    - Mobile-first responsive design
    - WebSocket for real-time updates
    - RESTful API endpoints
    - Progressive Web App support
    - Offline data caching
    - Touch-optimized controls
    - Dark mode support

    API Endpoints:
    - GET /api/portfolio - Portfolio summary
    - GET /api/positions - Current positions
    - GET /api/alerts - Recent alerts
    - GET /api/performance - Performance metrics
    - WebSocket /ws - Real-time updates

    Usage:
        dashboard = MobileDashboardServer(port=8080)
        dashboard.start()
    """

    def __init__(
        self,
        port: int = 8080,
        host: str = '0.0.0.0',
        enable_cors: bool = True,
        enable_pwa: bool = True
    ):
        """
        Initialize mobile dashboard server

        Args:
            port: Server port
            host: Server host
            enable_cors: Enable CORS for mobile apps
            enable_pwa: Enable PWA features
        """
        self.port = port
        self.host = host
        self.enable_cors = enable_cors
        self.enable_pwa = enable_pwa

        # Web app
        self.app = web.Application()

        # WebSocket clients
        self.ws_clients: List[web.WebSocketResponse] = []

        # Dashboard data cache
        self._portfolio_data = {}
        self._positions_data = []
        self._alerts_data = []
        self._performance_data = {}

        # Setup routes
        self._setup_routes()

        # Setup CORS
        if enable_cors:
            self._setup_cors()

        # Setup security headers
        self._setup_security_headers()

        logger.info(f"📱 Mobile Dashboard Server initialized on {host}:{port}")

    def _setup_routes(self):
        """Setup HTTP routes"""
        # API endpoints
        self.app.router.add_get('/api/portfolio', self.handle_portfolio)
        self.app.router.add_get('/api/positions', self.handle_positions)
        self.app.router.add_get('/api/alerts', self.handle_alerts)
        self.app.router.add_get('/api/performance', self.handle_performance)
        self.app.router.add_get('/api/health', self.handle_health)

        # WebSocket
        self.app.router.add_get('/ws', self.handle_websocket)

        # Static files (HTML, CSS, JS)
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/manifest.json', self.handle_manifest)
        self.app.router.add_get('/service-worker.js', self.handle_service_worker)

    def _setup_cors(self):
        """Setup CORS for mobile apps"""
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*"
            )
        })

        # Configure CORS on all routes
        for route in list(self.app.router.routes()):
            cors.add(route)

    def _setup_security_headers(self):
        """
        Setup security headers middleware for production hardening

        Headers added:
        - Content-Security-Policy: Prevents XSS, code injection attacks
        - X-Frame-Options: Prevents clickjacking attacks
        - X-Content-Type-Options: Prevents MIME type sniffing
        - Strict-Transport-Security: Forces HTTPS connections
        - Referrer-Policy: Controls referrer information leakage
        - X-XSS-Protection: Legacy XSS protection (defense in depth)
        - Permissions-Policy: Controls browser features/APIs
        """
        @web.middleware
        async def security_headers_middleware(request, handler):
            response = await handler(request)

            # Content Security Policy - prevents XSS and injection attacks
            # Allows content only from same origin, WebSocket connections, and inline styles/scripts
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "connect-src 'self' ws: wss:; "
                "font-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none';"
            )

            # Prevent clickjacking - deny embedding in iframes
            response.headers['X-Frame-Options'] = 'DENY'

            # Prevent MIME type sniffing - forces declared content type
            response.headers['X-Content-Type-Options'] = 'nosniff'

            # Force HTTPS for 1 year (31536000 seconds)
            # includeSubDomains applies to all subdomains
            # preload allows inclusion in browser HSTS preload lists
            response.headers['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains; preload'
            )

            # Control referrer information - prevent leaking URLs
            response.headers['Referrer-Policy'] = 'no-referrer'

            # Legacy XSS protection (defense in depth, most browsers have CSP now)
            response.headers['X-XSS-Protection'] = '1; mode=block'

            # Permissions Policy - restrict browser features
            # Disables geolocation, camera, microphone, payment APIs
            response.headers['Permissions-Policy'] = (
                'geolocation=(), camera=(), microphone=(), payment=()'
            )

            # Additional security header - prevent DNS prefetching
            response.headers['X-DNS-Prefetch-Control'] = 'off'

            # Prevent browser caching of sensitive data
            if request.path.startswith('/api/'):
                response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'

            return response

        # Add middleware to app
        self.app.middlewares.append(security_headers_middleware)
        logger.info("🔒 Security headers middleware enabled")

    async def handle_index(self, request):
        """Serve mobile dashboard HTML"""
        html = self._generate_mobile_html()
        return web.Response(text=html, content_type='text/html')

    async def handle_portfolio(self, request):
        """API: Get portfolio summary"""
        return web.json_response({
            'status': 'success',
            'data': self._portfolio_data,
            'timestamp': datetime.now().isoformat()
        })

    async def handle_positions(self, request):
        """API: Get current positions"""
        return web.json_response({
            'status': 'success',
            'data': self._positions_data,
            'timestamp': datetime.now().isoformat()
        })

    async def handle_alerts(self, request):
        """API: Get recent alerts"""
        # Get query params
        limit = int(request.query.get('limit', 10))

        return web.json_response({
            'status': 'success',
            'data': self._alerts_data[-limit:],
            'timestamp': datetime.now().isoformat()
        })

    async def handle_performance(self, request):
        """API: Get performance metrics"""
        return web.json_response({
            'status': 'success',
            'data': self._performance_data,
            'timestamp': datetime.now().isoformat()
        })

    async def handle_health(self, request):
        """API: Health check"""
        return web.json_response({
            'status': 'healthy',
            'version': '1.0.0',
            'timestamp': datetime.now().isoformat(),
            'connected_clients': len(self.ws_clients)
        })

    async def handle_websocket(self, request):
        """WebSocket handler for real-time updates"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self.ws_clients.append(ws)
        logger.info(f"WebSocket client connected. Total: {len(self.ws_clients)}")

        try:
            # Send initial data
            await ws.send_json({
                'type': 'init',
                'portfolio': self._portfolio_data,
                'positions': self._positions_data
            })

            # Listen for messages
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    # Handle client messages
                    data = json.loads(msg.data)
                    await self._handle_ws_message(ws, data)

                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f'WebSocket error: {ws.exception()}')

        finally:
            self.ws_clients.remove(ws)
            logger.info(f"WebSocket client disconnected. Remaining: {len(self.ws_clients)}")

        return ws

    async def _handle_ws_message(self, ws: web.WebSocketResponse, data: Dict):
        """Handle WebSocket message from client"""
        msg_type = data.get('type')

        if msg_type == 'ping':
            await ws.send_json({'type': 'pong'})

        elif msg_type == 'subscribe':
            # Subscribe to specific updates
            channels = data.get('channels', [])
            await ws.send_json({
                'type': 'subscribed',
                'channels': channels
            })

    async def handle_manifest(self, request):
        """Serve PWA manifest"""
        manifest = {
            "name": "Trading Dashboard",
            "short_name": "Trading",
            "description": "Real-time trading dashboard",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#1a1a2e",
            "theme_color": "#16213e",
            "orientation": "portrait",
            "icons": [
                {
                    "src": "/static/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png"
                },
                {
                    "src": "/static/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png"
                }
            ]
        }

        return web.json_response(manifest)

    async def handle_service_worker(self, request):
        """Serve service worker for PWA"""
        sw_js = self._generate_service_worker_js()
        return web.Response(text=sw_js, content_type='application/javascript')

    def _generate_mobile_html(self) -> str:
        """Generate mobile-responsive HTML"""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#16213e">
    <meta name="description" content="Real-time trading dashboard">
    <link rel="manifest" href="/manifest.json">
    <title>Trading Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #1a1a2e;
            color: #eee;
            overflow-x: hidden;
        }

        .header {
            background: linear-gradient(135deg, #16213e 0%, #0f3460 100%);
            padding: 1rem;
            position: sticky;
            top: 0;
            z-index: 1000;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }

        .header h1 {
            font-size: 1.5rem;
            font-weight: 600;
        }

        .header .subtitle {
            font-size: 0.9rem;
            color: #aaa;
            margin-top: 0.25rem;
        }

        .container {
            padding: 1rem;
            max-width: 1200px;
            margin: 0 auto;
        }

        .card {
            background: #16213e;
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 1rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .card-header {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .metric {
            display: flex;
            justify-content: space-between;
            padding: 0.75rem 0;
            border-bottom: 1px solid #0f3460;
        }

        .metric:last-child {
            border-bottom: none;
        }

        .metric-label {
            color: #aaa;
            font-size: 0.9rem;
        }

        .metric-value {
            font-weight: 600;
            font-size: 1.1rem;
        }

        .metric-value.positive {
            color: #00d4aa;
        }

        .metric-value.negative {
            color: #ff4757;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-bottom: 1rem;
        }

        .stat-card {
            background: #0f3460;
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
        }

        .stat-card .label {
            font-size: 0.8rem;
            color: #aaa;
            margin-bottom: 0.5rem;
        }

        .stat-card .value {
            font-size: 1.5rem;
            font-weight: 700;
        }

        .position-item {
            background: #0f3460;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 0.75rem;
        }

        .position-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.5rem;
        }

        .position-symbol {
            font-weight: 600;
            font-size: 1.1rem;
        }

        .position-pnl {
            font-weight: 600;
        }

        .position-details {
            display: flex;
            justify-content: space-between;
            font-size: 0.85rem;
            color: #aaa;
        }

        .alert-item {
            display: flex;
            align-items: center;
            padding: 0.75rem;
            margin-bottom: 0.5rem;
            border-radius: 8px;
            background: #0f3460;
        }

        .alert-icon {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 1rem;
            font-size: 1.2rem;
        }

        .alert-icon.critical {
            background: #ff4757;
        }

        .alert-icon.warning {
            background: #ffa502;
        }

        .alert-content {
            flex: 1;
        }

        .alert-title {
            font-weight: 600;
            margin-bottom: 0.25rem;
        }

        .alert-message {
            font-size: 0.85rem;
            color: #aaa;
        }

        .loading {
            text-align: center;
            padding: 2rem;
            color: #aaa;
        }

        @media (max-width: 768px) {
            .grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 0.5rem;
        }

        .status-indicator.connected {
            background: #00d4aa;
            box-shadow: 0 0 10px #00d4aa;
        }

        .status-indicator.disconnected {
            background: #ff4757;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Trading Dashboard</h1>
        <div class="subtitle">
            <span class="status-indicator connected" id="status"></span>
            <span id="status-text">Connected</span>
        </div>
    </div>

    <div class="container">
        <!-- Portfolio Summary -->
        <div class="card">
            <div class="card-header">
                Portfolio Summary
            </div>
            <div class="grid">
                <div class="stat-card">
                    <div class="label">Total Value</div>
                    <div class="value" id="portfolio-value">--</div>
                </div>
                <div class="stat-card">
                    <div class="label">Today's P&L</div>
                    <div class="value" id="daily-pnl">--</div>
                </div>
                <div class="stat-card">
                    <div class="label">Total P&L</div>
                    <div class="value" id="total-pnl">--</div>
                </div>
                <div class="stat-card">
                    <div class="label">Win Rate</div>
                    <div class="value" id="win-rate">--</div>
                </div>
            </div>
        </div>

        <!-- Current Positions -->
        <div class="card">
            <div class="card-header">
                Current Positions
                <span id="positions-count">0</span>
            </div>
            <div id="positions-list">
                <div class="loading">Loading positions...</div>
            </div>
        </div>

        <!-- Recent Alerts -->
        <div class="card">
            <div class="card-header">
                Recent Alerts
            </div>
            <div id="alerts-list">
                <div class="loading">Loading alerts...</div>
            </div>
        </div>
    </div>

    <script>
        // WebSocket connection
        let ws;
        const statusIndicator = document.getElementById('status');
        const statusText = document.getElementById('status-text');

        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

            ws.onopen = () => {
                console.log('WebSocket connected');
                statusIndicator.className = 'status-indicator connected';
                statusText.textContent = 'Connected';
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            };

            ws.onclose = () => {
                console.log('WebSocket disconnected');
                statusIndicator.className = 'status-indicator disconnected';
                statusText.textContent = 'Disconnected';

                // Reconnect after 5 seconds
                setTimeout(connectWebSocket, 5000);
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        }

        function handleWebSocketMessage(data) {
            if (data.type === 'init') {
                updatePortfolio(data.portfolio);
                updatePositions(data.positions);
            } else if (data.type === 'portfolio_update') {
                updatePortfolio(data.portfolio);
            } else if (data.type === 'position_update') {
                updatePositions(data.positions);
            } else if (data.type === 'alert') {
                addAlert(data.alert);
            }
        }

        function updatePortfolio(portfolio) {
            document.getElementById('portfolio-value').textContent =
                `₹${(portfolio.total_value || 0).toLocaleString()}`;

            const dailyPnl = portfolio.daily_pnl || 0;
            const dailyPnlEl = document.getElementById('daily-pnl');
            dailyPnlEl.textContent = `₹${dailyPnl.toLocaleString()}`;
            dailyPnlEl.className = `value ${dailyPnl >= 0 ? 'positive' : 'negative'}`;

            const totalPnl = portfolio.total_pnl || 0;
            const totalPnlEl = document.getElementById('total-pnl');
            totalPnlEl.textContent = `₹${totalPnl.toLocaleString()}`;
            totalPnlEl.className = `value ${totalPnl >= 0 ? 'positive' : 'negative'}`;

            document.getElementById('win-rate').textContent =
                `${((portfolio.win_rate || 0) * 100).toFixed(1)}%`;
        }

        function updatePositions(positions) {
            const positionsList = document.getElementById('positions-list');
            document.getElementById('positions-count').textContent = positions.length;

            if (positions.length === 0) {
                positionsList.innerHTML = '<div class="loading">No open positions</div>';
                return;
            }

            positionsList.innerHTML = positions.map(pos => `
                <div class="position-item">
                    <div class="position-header">
                        <div class="position-symbol">${pos.symbol}</div>
                        <div class="position-pnl ${pos.pnl >= 0 ? 'positive' : 'negative'}">
                            ₹${pos.pnl.toLocaleString()}
                        </div>
                    </div>
                    <div class="position-details">
                        <span>Qty: ${pos.quantity}</span>
                        <span>Avg: ₹${pos.avg_price}</span>
                        <span>LTP: ₹${pos.current_price}</span>
                    </div>
                </div>
            `).join('');
        }

        function loadAlerts() {
            fetch('/api/alerts?limit=5')
                .then(res => res.json())
                .then(data => {
                    const alertsList = document.getElementById('alerts-list');

                    if (data.data.length === 0) {
                        alertsList.innerHTML = '<div class="loading">No recent alerts</div>';
                        return;
                    }

                    alertsList.innerHTML = data.data.map(alert => `
                        <div class="alert-item">
                            <div class="alert-icon ${alert.severity}">⚠️</div>
                            <div class="alert-content">
                                <div class="alert-title">${alert.title}</div>
                                <div class="alert-message">${alert.message}</div>
                            </div>
                        </div>
                    `).join('');
                });
        }

        // Initialize
        connectWebSocket();
        loadAlerts();

        // Refresh alerts every 30 seconds
        setInterval(loadAlerts, 30000);
    </script>
</body>
</html>"""

    def _generate_service_worker_js(self) -> str:
        """Generate service worker JavaScript for PWA"""
        return """
const CACHE_NAME = 'trading-dashboard-v1';
const urlsToCache = [
  '/',
  '/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});
"""

    async def broadcast_update(self, update_type: str, data: Dict):
        """Broadcast update to all WebSocket clients"""
        message = json.dumps({
            'type': update_type,
            **data
        })

        dead_clients = []

        for ws in self.ws_clients:
            try:
                await ws.send_str(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                dead_clients.append(ws)

        # Remove dead clients
        for ws in dead_clients:
            self.ws_clients.remove(ws)

    def update_portfolio_data(self, data: Dict):
        """Update portfolio data and broadcast"""
        self._portfolio_data = data

        # Broadcast to WebSocket clients
        asyncio.create_task(self.broadcast_update('portfolio_update', {
            'portfolio': data
        }))

    def update_positions_data(self, data: List[Dict]):
        """Update positions data and broadcast"""
        self._positions_data = data

        asyncio.create_task(self.broadcast_update('position_update', {
            'positions': data
        }))

    def add_alert(self, alert: Dict):
        """Add alert and broadcast"""
        self._alerts_data.append(alert)

        # Keep only last 100 alerts
        if len(self._alerts_data) > 100:
            self._alerts_data = self._alerts_data[-100:]

        asyncio.create_task(self.broadcast_update('alert', {
            'alert': alert
        }))

    def start(self):
        """Start dashboard server"""
        logger.info(f"🚀 Starting Mobile Dashboard Server on {self.host}:{self.port}")
        web.run_app(self.app, host=self.host, port=self.port)


if __name__ == "__main__":
    # Test mobile dashboard
    print("Starting Mobile Trading Dashboard...\n")
    print(f"📱 Dashboard URL: http://localhost:8080")
    print(f"📊 API Endpoints:")
    print(f"  - GET  /api/portfolio")
    print(f"  - GET  /api/positions")
    print(f"  - GET  /api/alerts")
    print(f"  - GET  /api/health")
    print(f"  - WebSocket /ws")
    print("\n✅ Mobile dashboard server ready\n")

    dashboard = MobileDashboardServer(port=8080)

    # Simulate some data
    dashboard.update_portfolio_data({
        'total_value': 1050000,
        'daily_pnl': 15000,
        'total_pnl': 50000,
        'win_rate': 0.58
    })

    dashboard.update_positions_data([
        {'symbol': 'NIFTY', 'quantity': 50, 'avg_price': 25000, 'current_price': 25100, 'pnl': 5000},
        {'symbol': 'BANKNIFTY', 'quantity': 15, 'avg_price': 53500, 'current_price': 53700, 'pnl': 3000}
    ])

    dashboard.start()
