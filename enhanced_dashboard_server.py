#!/usr/bin/env python3
"""
Enhanced Trading Dashboard Server
Simple HTTP server to receive and display trading system data
"""

import http.server
import socketserver
import json
import threading
from datetime import datetime
from pathlib import Path
import os
import sys

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

class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
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
                        event.target.classList.add('active');
                    }

                    // Format currency values
                    function formatCurrency(value) {
                        return '₹' + (value || 0).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    }

                    // Format percentage values
                    function formatPercentage(value) {
                        return (value || 0) + '%';
                    }

                    function updateDashboard() {
                        fetch('/api/data')
                            .then(response => response.json())
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
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'healthy'}).encode())

        elif self.path == '/api/data':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
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

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

    def handle_api_data(self, data_type):
        """Handle API data updates"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())

            # Debug logging for trade_history
            if data_type == 'trade_history':
                print(f"📊 Received trade history: {data.get('symbol', 'Unknown')} - P&L: ₹{data.get('pnl', 0):,.0f}")

            # Update dashboard data
            if data_type in dashboard_data:
                if not isinstance(dashboard_data[data_type], list):
                    dashboard_data[data_type].update(data)
                else:
                    # For lists, keep only recent items
                    dashboard_data[data_type].append(data)
                    if len(dashboard_data[data_type]) > 100:  # Keep last 100 items
                        dashboard_data[data_type] = dashboard_data[data_type][-100:]

                    # Debug logging
                    if data_type == 'trade_history':
                        print(f"✅ Trade history updated - Total: {len(dashboard_data[data_type])} trades")

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'success'}).encode())

        except Exception as e:
            print(f"Error handling {data_type} API call: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode())

    def get_live_trading_data(self):
        """Read live trading data from state files"""
        try:
            # Read current state
            current_state = {}
            if os.path.exists('state/current_state.json'):
                with open('state/current_state.json', 'r') as f:
                    current_state = json.load(f)

            # Read shared portfolio state
            portfolio_state = {}
            if os.path.exists('state/shared_portfolio_state.json'):
                try:
                    with open('state/shared_portfolio_state.json', 'r') as f:
                        portfolio_state = json.load(f)
                except json.JSONDecodeError:
                    print("Warning: shared_portfolio_state.json is corrupted, using empty portfolio data")
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
            print(f"Error reading live trading data: {e}")
            # Fallback to static data
            return dashboard_data

    def log_message(self, format, *args):
        """Override to reduce log noise"""
        return

def run_server(port=8080):
    """Run the dashboard server"""
    with socketserver.TCPServer(("", port), DashboardHandler) as httpd:
        print(f"📊 Enhanced Trading Dashboard Server")
        print(f"🌐 Server running at: http://localhost:{port}")
        print(f"📈 API endpoints available at: http://localhost:{port}/api/*")
        print(f"💻 Dashboard interface at: http://localhost:{port}")
        print(f"🛑 Press Ctrl+C to stop the server\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Dashboard server stopped")
            httpd.shutdown()

if __name__ == "__main__":
    import sys
    port = 8080  # Default to port 8080 to match trading system expectations
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Invalid port number, using default 8080")
    run_server(port=port)
