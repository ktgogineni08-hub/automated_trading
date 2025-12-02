"""
Interactive Trading Dashboard
Phase 4 Tier 2: Interactive Dashboards & Visualization

Main Dash application for real-time trading monitoring and analysis.

Features:
- Real-time portfolio monitoring
- Interactive candlestick charts
- Performance analytics
- Risk metrics visualization
- Strategy comparison
- Trade history analysis

Author: Trading System
Date: October 22, 2025
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import dash
    from dash import dcc, html, Input, Output, State, callback
    import dash_bootstrap_components as dbc
    import plotly.graph_objs as go
    import plotly.express as px
except ImportError:
    print("ERROR: Dash dependencies not installed.")
    print("Install with: pip install dash dash-bootstrap-components plotly")
    sys.exit(1)

import pandas as pd
import numpy as np
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TradingDashboard:
    """
    Interactive trading dashboard using Dash and Plotly
    
    Provides real-time monitoring, analytics, and visualization
    """
    
    def __init__(
        self,
        title: str = "Advanced Trading Dashboard",
        host: str = "127.0.0.1",
        port: int = 8050,
        debug: bool = False,
        update_interval: int = 5000  # milliseconds
    ):
        """
        Initialize trading dashboard
        
        Args:
            title: Dashboard title
            host: Host address
            port: Port number
            debug: Enable debug mode
            update_interval: Real-time update interval in milliseconds
        """
        self.title = title
        self.host = host
        self.port = port
        self.debug = debug
        self.update_interval = update_interval
        
        # Initialize Dash app with Bootstrap theme
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
            suppress_callback_exceptions=True,
            title=self.title
        )
        
        # Initialize data storage (in production, use database or Redis)
        self.portfolio_data = self._generate_demo_portfolio_data()
        self.market_data = self._generate_demo_market_data()
        self.trades_data = self._generate_demo_trades_data()
        
        # Setup layout
        self._setup_layout()
        
        # Setup callbacks
        self._setup_callbacks()
        
        logger.info(f"Trading dashboard initialized on {host}:{port}")
    
    def _setup_layout(self):
        """Setup dashboard layout"""
        self.app.layout = dbc.Container([
            # Header
            dbc.Row([
                dbc.Col([
                    html.H1([
                        html.I(className="fas fa-chart-line me-3"),
                        self.title
                    ], className="text-primary mb-0"),
                    html.P(
                        f"Real-time Trading Analytics • Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        className="text-muted small",
                        id="last-update-time"
                    )
                ], width=12)
            ], className="mb-4 mt-3"),
            
            # Navigation tabs
            dbc.Row([
                dbc.Col([
                    dbc.Tabs([
                        dbc.Tab(label="📊 Portfolio", tab_id="portfolio", label_style={"fontSize": "16px"}),
                        dbc.Tab(label="📈 Market", tab_id="market", label_style={"fontSize": "16px"}),
                        dbc.Tab(label="🎯 Strategy", tab_id="strategy", label_style={"fontSize": "16px"}),
                        dbc.Tab(label="📋 Trades", tab_id="trades", label_style={"fontSize": "16px"}),
                        dbc.Tab(label="⚙️ Settings", tab_id="settings", label_style={"fontSize": "16px"}),
                    ], id="tabs", active_tab="portfolio")
                ], width=12)
            ], className="mb-4"),
            
            # Content area
            dbc.Row([
                dbc.Col([
                    html.Div(id="tab-content")
                ], width=12)
            ]),
            
            # Auto-refresh interval
            dcc.Interval(
                id='interval-component',
                interval=self.update_interval,
                n_intervals=0
            ),
            
            # Store for sharing data between callbacks
            dcc.Store(id='portfolio-store'),
            dcc.Store(id='market-store'),
            
        ], fluid=True, className="px-4")
    
    def _setup_callbacks(self):
        """Setup dashboard callbacks"""
        
        @self.app.callback(
            Output("tab-content", "children"),
            Input("tabs", "active_tab")
        )
        def render_tab_content(active_tab):
            """Render content based on active tab"""
            if active_tab == "portfolio":
                return self._get_portfolio_layout()
            elif active_tab == "market":
                return self._get_market_layout()
            elif active_tab == "strategy":
                return self._get_strategy_layout()
            elif active_tab == "trades":
                return self._get_trades_layout()
            elif active_tab == "settings":
                return self._get_settings_layout()
            return html.Div("Select a tab")
        
        @self.app.callback(
            [Output("last-update-time", "children"),
             Output("portfolio-store", "data"),
             Output("market-store", "data")],
            Input("interval-component", "n_intervals")
        )
        def update_data(n):
            """Update data periodically"""
            # In production, fetch real data here
            update_time = f"Real-time Trading Analytics • Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Simulate data updates
            portfolio_data = self.portfolio_data.to_dict('records')
            market_data = self.market_data.to_dict('records')
            
            return update_time, portfolio_data, market_data
    
    def _get_portfolio_layout(self) -> dbc.Container:
        """Get portfolio monitoring layout"""
        # Calculate portfolio metrics
        total_value = self.portfolio_data['market_value'].sum()
        total_pnl = self.portfolio_data['unrealized_pnl'].sum()
        pnl_pct = (total_pnl / (total_value - total_pnl)) * 100 if total_value > 0 else 0
        
        return dbc.Container([
            # Key metrics cards
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Portfolio Value", className="text-muted mb-2"),
                            html.H3(f"₹{total_value:,.2f}", className="text-primary mb-0"),
                            html.Small(f"{pnl_pct:+.2f}% today", className="text-success" if pnl_pct > 0 else "text-danger")
                        ])
                    ], className="shadow-sm")
                ], width=3),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Unrealized P&L", className="text-muted mb-2"),
                            html.H3(
                                f"₹{total_pnl:+,.2f}",
                                className="text-success mb-0" if total_pnl > 0 else "text-danger mb-0"
                            ),
                            html.Small("Across all positions", className="text-muted")
                        ])
                    ], className="shadow-sm")
                ], width=3),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Open Positions", className="text-muted mb-2"),
                            html.H3(f"{len(self.portfolio_data)}", className="text-info mb-0"),
                            html.Small("Active trades", className="text-muted")
                        ])
                    ], className="shadow-sm")
                ], width=3),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Win Rate", className="text-muted mb-2"),
                            html.H3("68.5%", className="text-success mb-0"),
                            html.Small("Last 30 days", className="text-muted")
                        ])
                    ], className="shadow-sm")
                ], width=3),
            ], className="mb-4"),
            
            # Portfolio allocation pie chart
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Portfolio Allocation", className="mb-0")),
                        dbc.CardBody([
                            dcc.Graph(
                                id="portfolio-allocation-chart",
                                figure=self._create_portfolio_allocation_chart(),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm")
                ], width=6),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("P&L by Symbol", className="mb-0")),
                        dbc.CardBody([
                            dcc.Graph(
                                id="pnl-by-symbol-chart",
                                figure=self._create_pnl_by_symbol_chart(),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm")
                ], width=6),
            ], className="mb-4"),
            
            # Holdings table
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Current Holdings", className="mb-0")),
                        dbc.CardBody([
                            self._create_holdings_table()
                        ])
                    ], className="shadow-sm")
                ], width=12)
            ])
        ], fluid=True)
    
    def _get_market_layout(self) -> dbc.Container:
        """Get market analysis layout"""
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H5("Live Market Data", className="mb-0 d-inline"),
                            dbc.Badge("LIVE", color="success", className="ms-2")
                        ]),
                        dbc.CardBody([
                            dcc.Graph(
                                id="candlestick-chart",
                                figure=self._create_candlestick_chart(),
                                style={'height': '500px'}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ], width=12)
            ]),
            
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Market Heatmap", className="mb-0")),
                        dbc.CardBody([
                            dcc.Graph(
                                id="market-heatmap",
                                figure=self._create_market_heatmap(),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm")
                ], width=12)
            ])
        ], fluid=True)
    
    def _get_strategy_layout(self) -> dbc.Container:
        """Get strategy comparison layout"""
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Strategy Performance Comparison", className="mb-0")),
                        dbc.CardBody([
                            dcc.Graph(
                                id="strategy-comparison-chart",
                                figure=self._create_strategy_comparison_chart(),
                                style={'height': '400px'}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ], width=12)
            ]),
            
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Risk-Return Analysis", className="mb-0")),
                        dbc.CardBody([
                            dcc.Graph(
                                id="risk-return-scatter",
                                figure=self._create_risk_return_scatter(),
                                config={'displayModeBar': True}
                            )
                        ])
                    ], className="shadow-sm")
                ], width=6),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Drawdown Analysis", className="mb-0")),
                        dbc.CardBody([
                            dcc.Graph(
                                id="drawdown-chart",
                                figure=self._create_drawdown_chart(),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm")
                ], width=6),
            ])
        ], fluid=True)
    
    def _get_trades_layout(self) -> dbc.Container:
        """Get trades history layout"""
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Recent Trades", className="mb-0")),
                        dbc.CardBody([
                            self._create_trades_table()
                        ])
                    ], className="shadow-sm mb-4")
                ], width=12)
            ]),
            
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Trade Distribution", className="mb-0")),
                        dbc.CardBody([
                            dcc.Graph(
                                id="trade-distribution",
                                figure=self._create_trade_distribution_chart(),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm")
                ], width=6),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Cumulative P&L", className="mb-0")),
                        dbc.CardBody([
                            dcc.Graph(
                                id="cumulative-pnl",
                                figure=self._create_cumulative_pnl_chart(),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm")
                ], width=6),
            ])
        ], fluid=True)
    
    def _get_settings_layout(self) -> dbc.Container:
        """Get settings layout"""
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Dashboard Settings", className="mb-0")),
                        dbc.CardBody([
                            html.H6("Refresh Interval", className="mb-2"),
                            dcc.Slider(
                                id='refresh-interval-slider',
                                min=1,
                                max=60,
                                step=1,
                                value=self.update_interval // 1000,
                                marks={i: f"{i}s" for i in [1, 5, 10, 30, 60]},
                                tooltip={"placement": "bottom", "always_visible": True}
                            ),
                            html.Hr(),
                            html.H6("Theme", className="mb-2 mt-4"),
                            dbc.RadioItems(
                                options=[
                                    {"label": "Light", "value": "light"},
                                    {"label": "Dark", "value": "dark"},
                                ],
                                value="light",
                                id="theme-selector",
                            ),
                            html.Hr(),
                            html.H6("Notifications", className="mb-2 mt-4"),
                            dbc.Checklist(
                                options=[
                                    {"label": "Enable trade alerts", "value": 1},
                                    {"label": "Enable price alerts", "value": 2},
                                    {"label": "Enable risk alerts", "value": 3},
                                ],
                                value=[1, 2, 3],
                                id="notification-settings",
                            ),
                        ])
                    ], className="shadow-sm")
                ], width=6)
            ])
        ], fluid=True)
    
    # Chart creation methods
    def _create_portfolio_allocation_chart(self) -> go.Figure:
        """Create portfolio allocation pie chart"""
        fig = px.pie(
            self.portfolio_data,
            values='market_value',
            names='symbol',
            title='',
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(
            showlegend=True,
            height=300,
            margin=dict(l=20, r=20, t=20, b=20)
        )
        return fig
    
    def _create_pnl_by_symbol_chart(self) -> go.Figure:
        """Create P&L by symbol bar chart"""
        fig = px.bar(
            self.portfolio_data,
            x='symbol',
            y='unrealized_pnl',
            title='',
            color='unrealized_pnl',
            color_continuous_scale=['red', 'yellow', 'green'],
            color_continuous_midpoint=0
        )
        fig.update_layout(
            showlegend=False,
            height=300,
            xaxis_title="Symbol",
            yaxis_title="P&L (₹)",
            margin=dict(l=20, r=20, t=20, b=20)
        )
        return fig
    
    def _create_candlestick_chart(self) -> go.Figure:
        """Create interactive candlestick chart"""
        fig = go.Figure(data=[go.Candlestick(
            x=self.market_data['timestamp'],
            open=self.market_data['open'],
            high=self.market_data['high'],
            low=self.market_data['low'],
            close=self.market_data['close'],
            name='Price'
        )])
        
        # Add volume bars
        fig.add_trace(go.Bar(
            x=self.market_data['timestamp'],
            y=self.market_data['volume'],
            name='Volume',
            yaxis='y2',
            marker_color='rgba(100, 100, 100, 0.3)'
        ))
        
        fig.update_layout(
            title='NIFTY 50 - Live Chart',
            yaxis_title='Price',
            yaxis2=dict(title='Volume', overlaying='y', side='right'),
            xaxis_rangeslider_visible=False,
            height=500,
            hovermode='x unified'
        )
        return fig
    
    def _create_market_heatmap(self) -> go.Figure:
        """Create market correlation heatmap"""
        # Generate sample correlation data
        symbols = ['NIFTY50', 'BANKNIFTY', 'RELIANCE', 'TCS', 'INFY', 'HDFC']
        corr_matrix = np.random.rand(len(symbols), len(symbols))
        corr_matrix = (corr_matrix + corr_matrix.T) / 2
        np.fill_diagonal(corr_matrix, 1)
        
        fig = go.Figure(data=go.Heatmap(
            z=corr_matrix,
            x=symbols,
            y=symbols,
            colorscale='RdYlGn',
            zmid=0,
            text=corr_matrix,
            texttemplate='%{text:.2f}',
            textfont={"size": 10},
            colorbar=dict(title="Correlation")
        ))
        
        fig.update_layout(
            title='Market Correlation Matrix',
            height=400,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        return fig
    
    def _create_strategy_comparison_chart(self) -> go.Figure:
        """Create strategy comparison chart"""
        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
        
        fig = go.Figure()
        
        strategies = ['Momentum', 'Mean Reversion', 'ML Enhanced', 'Sentiment']
        colors = ['blue', 'red', 'green', 'purple']
        
        for strategy, color in zip(strategies, colors):
            returns = np.random.randn(100).cumsum() * 0.02
            equity = 100000 * (1 + returns)
            
            fig.add_trace(go.Scatter(
                x=dates,
                y=equity,
                mode='lines',
                name=strategy,
                line=dict(color=color, width=2)
            ))
        
        fig.update_layout(
            title='Strategy Performance Over Time',
            xaxis_title='Date',
            yaxis_title='Equity (₹)',
            hovermode='x unified',
            height=400,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        return fig
    
    def _create_risk_return_scatter(self) -> go.Figure:
        """Create risk-return scatter plot"""
        strategies = ['Momentum', 'Mean Reversion', 'ML Enhanced', 'Sentiment', 'Buy & Hold']
        returns = np.random.uniform(10, 40, len(strategies))
        volatility = np.random.uniform(5, 25, len(strategies))
        sharpe = returns / volatility
        
        fig = go.Figure(data=go.Scatter(
            x=volatility,
            y=returns,
            mode='markers+text',
            marker=dict(
                size=sharpe * 20,
                color=sharpe,
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title="Sharpe Ratio")
            ),
            text=strategies,
            textposition="top center"
        ))
        
        fig.update_layout(
            title='Risk-Return Profile',
            xaxis_title='Volatility (%)',
            yaxis_title='Return (%)',
            height=300,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        return fig
    
    def _create_drawdown_chart(self) -> go.Figure:
        """Create drawdown chart"""
        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
        equity = 100000 * (1 + np.random.randn(100).cumsum() * 0.02)
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak * 100
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=drawdown,
            fill='tozeroy',
            name='Drawdown',
            line=dict(color='red')
        ))
        
        fig.update_layout(
            title='Portfolio Drawdown',
            xaxis_title='Date',
            yaxis_title='Drawdown (%)',
            height=300,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        return fig
    
    def _create_trade_distribution_chart(self) -> go.Figure:
        """Create trade P&L distribution histogram"""
        pnl_data = self.trades_data['pnl']
        
        fig = go.Figure(data=[go.Histogram(
            x=pnl_data,
            nbinsx=30,
            marker_color='rgba(100, 150, 200, 0.7)',
            name='Trades'
        )])
        
        fig.update_layout(
            title='Trade P&L Distribution',
            xaxis_title='P&L (₹)',
            yaxis_title='Frequency',
            height=300,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        return fig
    
    def _create_cumulative_pnl_chart(self) -> go.Figure:
        """Create cumulative P&L chart"""
        fig = go.Figure()
        
        cumulative_pnl = self.trades_data['pnl'].cumsum()
        
        fig.add_trace(go.Scatter(
            x=self.trades_data['timestamp'],
            y=cumulative_pnl,
            mode='lines',
            name='Cumulative P&L',
            line=dict(color='green', width=2),
            fill='tozeroy'
        ))
        
        fig.update_layout(
            title='Cumulative P&L Over Time',
            xaxis_title='Date',
            yaxis_title='Cumulative P&L (₹)',
            height=300,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        return fig
    
    def _create_holdings_table(self):
        """Create holdings table"""
        return dbc.Table.from_dataframe(
            self.portfolio_data[[
                'symbol', 'quantity', 'avg_price', 'ltp',
                'market_value', 'unrealized_pnl', 'pnl_pct'
            ]].round(2),
            striped=True,
            bordered=True,
            hover=True,
            responsive=True,
            className="mb-0"
        )
    
    def _create_trades_table(self):
        """Create trades table"""
        return dbc.Table.from_dataframe(
            self.trades_data[['timestamp', 'symbol', 'action', 'quantity', 'price', 'pnl']].head(20).round(2),
            striped=True,
            bordered=True,
            hover=True,
            responsive=True,
            className="mb-0"
        )
    
    # Demo data generation methods
    def _generate_demo_portfolio_data(self) -> pd.DataFrame:
        """Generate demo portfolio data"""
        symbols = ['RELIANCE', 'TCS', 'INFY', 'HDFC', 'ICICIBANK', 'SBIN']
        data = []
        
        for symbol in symbols:
            quantity = np.random.randint(10, 100)
            avg_price = np.random.uniform(500, 3000)
            ltp = avg_price * (1 + np.random.uniform(-0.05, 0.05))
            market_value = quantity * ltp
            unrealized_pnl = quantity * (ltp - avg_price)
            pnl_pct = (ltp / avg_price - 1) * 100
            
            data.append({
                'symbol': symbol,
                'quantity': quantity,
                'avg_price': avg_price,
                'ltp': ltp,
                'market_value': market_value,
                'unrealized_pnl': unrealized_pnl,
                'pnl_pct': pnl_pct
            })
        
        return pd.DataFrame(data)
    
    def _generate_demo_market_data(self) -> pd.DataFrame:
        """Generate demo market data"""
        dates = pd.date_range(end=datetime.now(), periods=100, freq='1H')
        base_price = 19500
        
        data = []
        for date in dates:
            open_price = base_price + np.random.uniform(-50, 50)
            close_price = open_price + np.random.uniform(-30, 30)
            high_price = max(open_price, close_price) + np.random.uniform(0, 20)
            low_price = min(open_price, close_price) - np.random.uniform(0, 20)
            volume = np.random.randint(1000000, 10000000)
            
            data.append({
                'timestamp': date,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume
            })
            
            base_price = close_price
        
        return pd.DataFrame(data)
    
    def _generate_demo_trades_data(self) -> pd.DataFrame:
        """Generate demo trades data"""
        dates = pd.date_range(end=datetime.now(), periods=50, freq='D')
        symbols = ['RELIANCE', 'TCS', 'INFY', 'HDFC', 'ICICIBANK']
        
        data = []
        for date in dates:
            symbol = np.random.choice(symbols)
            action = np.random.choice(['BUY', 'SELL'])
            quantity = np.random.randint(10, 100)
            price = np.random.uniform(500, 3000)
            pnl = np.random.uniform(-5000, 8000)
            
            data.append({
                'timestamp': date,
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'price': price,
                'pnl': pnl
            })
        
        return pd.DataFrame(data)
    
    def run(self):
        """Run the dashboard server"""
        logger.info(f"Starting dashboard on http://{self.host}:{self.port}")
        self.app.run_server(host=self.host, port=self.port, debug=self.debug)


if __name__ == "__main__":
    # Create and run dashboard
    dashboard = TradingDashboard(
        title="Advanced Trading Dashboard",
        host="127.0.0.1",
        port=8050,
        debug=True,
        update_interval=5000
    )
    
    print("\n" + "=" * 60)
    print("🚀 Trading Dashboard Starting...")
    print("=" * 60)
    print(f"\n📊 Access dashboard at: http://127.0.0.1:8050")
    print("\nFeatures:")
    print("  ✓ Real-time portfolio monitoring")
    print("  ✓ Interactive candlestick charts")
    print("  ✓ Strategy performance comparison")
    print("  ✓ Risk metrics visualization")
    print("  ✓ Trade history analysis")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 60 + "\n")
    
    dashboard.run()
