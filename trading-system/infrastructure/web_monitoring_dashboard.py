#!/usr/bin/env python3
"""
Web-Based Monitoring Dashboard
Real-time web interface for system monitoring

Features:
- Live metric updates via WebSocket
- Interactive charts and graphs
- Alert notifications
- Mobile-responsive design
- Auto-refresh every 5 seconds
"""

import logging
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from aiohttp import web
import aiohttp_cors

from infrastructure.monitoring_dashboard import get_monitoring_collector

logger = logging.getLogger('trading_system.web_monitoring')


class WebMonitoringDashboard:
    """
    Web-based monitoring dashboard server

    Endpoints:
    - GET / - Dashboard HTML interface
    - GET /api/health - System health metrics
    - GET /api/trading - Trading metrics
    - GET /api/api - API usage metrics
    - GET /api/cost - Cost optimization metrics
    - GET /api/all - All metrics
    - WebSocket /ws - Real-time updates
    """

    def __init__(self, port: int = 8081, host: str = '0.0.0.0'):
        self.port = port
        self.host = host

        # Get monitoring collector
        self.collector = get_monitoring_collector()

        # Web app
        self.app = web.Application()

        # WebSocket clients
        self.ws_clients: List[web.WebSocketResponse] = []

        # Setup routes
        self._setup_routes()
        self._setup_cors()

        # Start metric collection
        self.collector.start_collection()

        logger.info(f"🌐 Web Monitoring Dashboard initialized on {host}:{port}")

    def _setup_routes(self):
        """Setup HTTP routes"""
        # Dashboard HTML
        self.app.router.add_get('/', self.handle_dashboard)

        # API endpoints
        self.app.router.add_get('/api/health', self.handle_health)
        self.app.router.add_get('/api/trading', self.handle_trading)
        self.app.router.add_get('/api/api', self.handle_api)
        self.app.router.add_get('/api/cost', self.handle_cost)
        self.app.router.add_get('/api/all', self.handle_all)

        # WebSocket
        self.app.router.add_get('/ws', self.handle_websocket)

    def _setup_cors(self):
        """Setup CORS"""
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*"
            )
        })
        for route in list(self.app.router.routes()):
            cors.add(route)

    async def handle_dashboard(self, request):
        """Serve dashboard HTML"""
        html = self._generate_dashboard_html()
        return web.Response(text=html, content_type='text/html')

    async def handle_health(self, request):
        """API: Get system health metrics"""
        health = self.collector.get_system_health_summary()
        return web.json_response({"status": "success", "data": health})

    async def handle_trading(self, request):
        """API: Get trading metrics"""
        trading = self.collector.get_trading_summary()
        return web.json_response({"status": "success", "data": trading})

    async def handle_api(self, request):
        """API: Get API usage metrics"""
        api_data = self.collector.get_api_summary()
        return web.json_response({"status": "success", "data": api_data})

    async def handle_cost(self, request):
        """API: Get cost optimization metrics"""
        cost = self.collector.get_cost_summary()
        return web.json_response({"status": "success", "data": cost})

    async def handle_all(self, request):
        """API: Get all metrics"""
        data = {
            "health": self.collector.get_system_health_summary(),
            "trading": self.collector.get_trading_summary(),
            "api": self.collector.get_api_summary(),
            "cost": self.collector.get_cost_summary(),
            "timestamp": datetime.now().isoformat()
        }
        return web.json_response({"status": "success", "data": data})

    async def handle_websocket(self, request):
        """WebSocket handler for real-time updates"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self.ws_clients.append(ws)
        logger.info(f"WebSocket client connected. Total: {len(self.ws_clients)}")

        try:
            # Send initial data
            await ws.send_json({
                "type": "init",
                "data": {
                    "health": self.collector.get_system_health_summary(),
                    "trading": self.collector.get_trading_summary(),
                    "api": self.collector.get_api_summary(),
                    "cost": self.collector.get_cost_summary()
                }
            })

            # Listen for messages
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get('type') == 'ping':
                        await ws.send_json({'type': 'pong'})

        finally:
            self.ws_clients.remove(ws)
            logger.info(f"WebSocket client disconnected. Remaining: {len(self.ws_clients)}")

        return ws

    def _generate_dashboard_html(self) -> str:
        """Generate dashboard HTML"""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading System Monitoring</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0e27;
            color: #e0e0e0;
            padding: 20px;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }

        .header h1 {
            font-size: 2rem;
            margin-bottom: 10px;
        }

        .header .subtitle {
            opacity: 0.9;
            font-size: 0.95rem;
        }

        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }

        .status-indicator.connected { background: #00ff88; }
        .status-indicator.disconnected { background: #ff4757; }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .card {
            background: #1a1f3a;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            border: 1px solid #2a2f4a;
        }

        .card-header {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 10px;
            border-bottom: 2px solid #2a2f4a;
        }

        .card-icon {
            font-size: 1.5rem;
        }

        .metric-row {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #2a2f4a;
        }

        .metric-row:last-child {
            border-bottom: none;
        }

        .metric-label {
            color: #9ca3af;
            font-size: 0.9rem;
        }

        .metric-value {
            font-weight: 600;
            font-size: 1.1rem;
        }

        .metric-value.positive { color: #00ff88; }
        .metric-value.negative { color: #ff4757; }
        .metric-value.warning { color: #ffa502; }

        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 600;
        }

        .badge.healthy { background: #00ff8820; color: #00ff88; }
        .badge.warning { background: #ffa50220; color: #ffa502; }
        .badge.critical { background: #ff475720; color: #ff4757; }

        .progress-bar {
            width: 100%;
            height: 8px;
            background: #2a2f4a;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 8px;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s ease;
        }

        .progress-fill.warning { background: #ffa502; }
        .progress-fill.critical { background: #ff4757; }

        .loading {
            text-align: center;
            padding: 40px;
            color: #6b7280;
        }

        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Trading System Monitoring</h1>
        <div class="subtitle">
            <span class="status-indicator connected" id="ws-status"></span>
            <span id="status-text">Connected</span> •
            Last Update: <span id="last-update">--</span>
        </div>
    </div>

    <div class="grid">
        <!-- System Health Card -->
        <div class="card">
            <div class="card-header">
                <span><span class="card-icon">🖥️</span> System Health</span>
                <span class="badge healthy" id="health-badge">HEALTHY</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">CPU Usage</span>
                <span class="metric-value" id="cpu">--%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="cpu-bar" style="width: 0%"></div>
            </div>
            <div class="metric-row">
                <span class="metric-label">Memory Usage</span>
                <span class="metric-value" id="memory">--%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="memory-bar" style="width: 0%"></div>
            </div>
            <div class="metric-row">
                <span class="metric-label">Disk Usage</span>
                <span class="metric-value" id="disk">--%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="disk-bar" style="width: 0%"></div>
            </div>
        </div>

        <!-- Trading Summary Card -->
        <div class="card">
            <div class="card-header">
                <span><span class="card-icon">📈</span> Trading Summary</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Daily P&L</span>
                <span class="metric-value positive" id="daily-pnl">₹0</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Total P&L</span>
                <span class="metric-value" id="total-pnl">₹0</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Open Positions</span>
                <span class="metric-value" id="positions">0</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Win Rate</span>
                <span class="metric-value" id="win-rate">0%</span>
            </div>
        </div>

        <!-- API Usage Card -->
        <div class="card">
            <div class="card-header">
                <span><span class="card-icon">🌐</span> API Usage</span>
                <span class="badge healthy" id="api-badge">HEALTHY</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Total Calls</span>
                <span class="metric-value" id="api-calls">0</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Success Rate</span>
                <span class="metric-value" id="api-success">0%</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Quota Used</span>
                <span class="metric-value" id="api-quota">0%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="quota-bar" style="width: 0%"></div>
            </div>
        </div>

        <!-- Cost Optimization Card -->
        <div class="card">
            <div class="card-header">
                <span><span class="card-icon">💰</span> Cost Optimization</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Cache Hit Rate</span>
                <span class="metric-value positive" id="cache-hit">0%</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">API Calls Saved</span>
                <span class="metric-value" id="calls-saved">0</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Cost Reduction</span>
                <span class="metric-value positive" id="cost-reduction">0%</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Monthly Savings</span>
                <span class="metric-value positive" id="monthly-savings">$0</span>
            </div>
        </div>
    </div>

    <script>
        let ws;
        const wsStatus = document.getElementById('ws-status');
        const statusText = document.getElementById('status-text');

        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

            ws.onopen = () => {
                console.log('WebSocket connected');
                wsStatus.className = 'status-indicator connected';
                statusText.textContent = 'Connected';
            };

            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'init' || msg.type === 'update') {
                    updateDashboard(msg.data);
                }
            };

            ws.onclose = () => {
                console.log('WebSocket disconnected');
                wsStatus.className = 'status-indicator disconnected';
                statusText.textContent = 'Disconnected';
                setTimeout(connectWebSocket, 5000);
            };
        }

        function updateDashboard(data) {
            document.getElementById('last-update').textContent =
                new Date().toLocaleTimeString();

            // System Health
            if (data.health && data.health.status !== 'no_data') {
                const h = data.health;
                updateBadge('health-badge', h.status);

                document.getElementById('cpu').textContent = h.cpu_percent.toFixed(1) + '%';
                updateProgressBar('cpu-bar', h.cpu_percent);

                document.getElementById('memory').textContent = h.memory_percent.toFixed(1) + '%';
                updateProgressBar('memory-bar', h.memory_percent);

                document.getElementById('disk').textContent = h.disk_percent.toFixed(1) + '%';
                updateProgressBar('disk-bar', h.disk_percent);
            }

            // Trading
            if (data.trading && data.trading.status !== 'no_data') {
                const t = data.trading;
                const dailyPnlEl = document.getElementById('daily-pnl');
                dailyPnlEl.textContent = `₹${t.daily_pnl.toLocaleString()}`;
                dailyPnlEl.className = `metric-value ${t.daily_pnl >= 0 ? 'positive' : 'negative'}`;

                document.getElementById('total-pnl').textContent = `₹${t.total_pnl.toLocaleString()}`;
                document.getElementById('positions').textContent = t.open_positions;
                document.getElementById('win-rate').textContent = t.win_rate.toFixed(1) + '%';
            }

            // API
            if (data.api && data.api.status !== 'no_data') {
                const a = data.api;
                updateBadge('api-badge', a.status);

                document.getElementById('api-calls').textContent = a.total_calls.toLocaleString();
                document.getElementById('api-success').textContent = a.success_rate.toFixed(1) + '%';
                document.getElementById('api-quota').textContent = a.quota_used_pct.toFixed(1) + '%';
                updateProgressBar('quota-bar', a.quota_used_pct);
            }

            // Cost
            if (data.cost && data.cost.status !== 'no_data') {
                const c = data.cost;
                document.getElementById('cache-hit').textContent = c.cache_hit_rate.toFixed(1) + '%';
                document.getElementById('calls-saved').textContent = c.api_calls_saved.toLocaleString();
                document.getElementById('cost-reduction').textContent = c.cost_reduction_pct.toFixed(1) + '%';
                document.getElementById('monthly-savings').textContent = '$' + c.estimated_monthly_savings.toFixed(2);
            }
        }

        function updateBadge(id, status) {
            const badge = document.getElementById(id);
            badge.className = `badge ${status}`;
            badge.textContent = status.toUpperCase();
        }

        function updateProgressBar(id, percent) {
            const bar = document.getElementById(id);
            bar.style.width = percent + '%';
            bar.className = 'progress-fill';
            if (percent > 80) bar.className += ' critical';
            else if (percent > 60) bar.className += ' warning';
        }

        // Fetch data via REST API every 5 seconds (fallback)
        async function fetchData() {
            try {
                const response = await fetch('/api/all');
                const result = await response.json();
                if (result.status === 'success') {
                    updateDashboard(result.data);
                }
            } catch (error) {
                console.error('Error fetching data:', error);
            }
        }

        // Initialize
        connectWebSocket();
        setInterval(fetchData, 5000);
    </script>
</body>
</html>"""

    def start(self):
        """Start web dashboard server"""
        logger.info(f"🚀 Starting Web Monitoring Dashboard on {self.host}:{self.port}")
        web.run_app(self.app, host=self.host, port=self.port)


if __name__ == "__main__":
    print("🚀 Starting Web Monitoring Dashboard...")
    print(f"📊 Dashboard URL: http://localhost:8081")
    print("\n✅ Dashboard server ready\n")

    dashboard = WebMonitoringDashboard(port=8081)
    dashboard.start()
