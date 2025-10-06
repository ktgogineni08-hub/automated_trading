# 🎯 Enhanced NIFTY 50 Trading System

An advanced algorithmic trading system for Indian stock markets with F&O trading capabilities, real-time dashboard, and comprehensive risk management.

## 🚀 Features

### Core Trading Features
- **📈 NIFTY 50 Trading**: Automated trading on NIFTY 50 stocks
- **🎯 F&O Trading**: Futures & Options strategies (Straddle, Strangle, Butterfly, Iron Condor)
- **📝 Paper Trading**: Safe simulation mode for testing strategies
- **📊 Backtesting**: Historical data analysis and strategy validation
- **🔴 Live Trading**: Real money trading with comprehensive risk management

### Advanced Features
- **🤖 AI-Powered Strategy Selection**: Intelligent market analysis and strategy recommendation
- **📊 Real-time Dashboard**: Web-based monitoring and control interface
- **🔧 Enhanced Token Management**: Automatic Zerodha API authentication
- **⚡ Live Data Integration**: Real-time market data from Zerodha Kite API
- **🛡️ Risk Management**: Position sizing, stop-loss, and portfolio protection
- **📱 Multi-Mode Interface**: Hierarchical menu system for different trading modes

## 📋 Prerequisites

- **Python 3.8+** (Tested with Python 3.9+)
- **Zerodha Kite API** account with API access
- **Active internet connection** for real-time data

## 🛠️ Quick Installation

### Option 1: Automated Installation (Recommended)
```bash
# Clone or download the trading system files
cd trading-system

# Run the automated installer
python trading_system_installer.py
```

### Option 2: Manual Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p logs state backtest_results

# Run health check
python system_health_check.py
```

## 🔐 Authentication Setup

1. **Get your Zerodha API credentials** (API Key and Secret)
2. **Run the token manager**:
   ```bash
   python zerodha_token_manager.py
   ```
3. **Follow the authentication flow** in your browser
4. **Token will be saved automatically** for future use

## 🚀 Usage

### Quick Start
```bash
# Launch unified interface
python launch.py
```

### Direct Launch Options
```bash
# Full trading system with menu
python enhanced_trading_system_complete.py

# Paper trading only
python launch_paper_trading.py

# Dashboard only
python launch_dashboard.py
```

### Trading Modes

#### 1. NIFTY 50 Trading
- **Paper Trading**: Safe simulation with virtual money
- **Backtesting**: Test strategies on historical data
- **Live Trading**: Real money trading with risk management

#### 2. F&O Trading (Futures & Options)
- **Advanced Strategies**: Straddle, Strangle, Butterfly, Iron Condor
- **Live Data Analysis**: Real-time option chain analysis
- **Intelligent Selection**: AI-powered strategy recommendations
- **Risk Controls**: Automatic position sizing and risk management

## 📊 Dashboard

Access the real-time dashboard at: `http://localhost:8080`

**Features:**
- Portfolio overview and P&L tracking
- Real-time trade monitoring
- Performance metrics and analytics
- System status and health monitoring

## ⚙️ Configuration

Configuration is managed through `config.py`:

```python
from config import get_config

cfg = get_config()
capital = cfg.get('trading.default_capital')  # ₹10,00,000
risk_per_trade = cfg.get('trading.risk_per_trade')  # 2%
```

### Key Settings
- **Default Capital**: ₹10,00,000 (10 Lakhs)
- **Risk Per Trade**: 2% of capital
- **Trading Hours**: 09:15 - 15:30
- **Dashboard Port**: 8080
- **Option Chain Limit**: 150 options (performance optimized)

## 🧠 AI Strategy Selection

The system uses intelligent market analysis to select optimal strategies:

### Market Conditions Analysis
- **Volatility Assessment**: ATR, Bollinger Bands width
- **Trend Analysis**: Moving averages, momentum indicators
- **Support/Resistance**: Key levels identification
- **Option Greeks**: Delta, Gamma, Theta analysis

### Strategy Recommendations
- **High Volatility**: Strangle, Long Straddle
- **Low Volatility**: Iron Condor, Short Straddle
- **Trending Markets**: Directional strategies
- **Range-bound**: Butterfly, Iron Condor

## 📁 File Structure

```
trading-system/
├── 🎯 enhanced_trading_system_complete.py  # Main trading system
├── 🔐 zerodha_token_manager.py            # Authentication manager
├── 📊 enhanced_dashboard_server.py         # Web dashboard
├── ⚙️ config.py                          # Configuration management
├── 🏥 system_health_check.py             # System diagnostics
├── 🛠️ trading_system_installer.py        # Automated installer
├── 🚀 launch.py                          # Unified launcher
├── 🚀 launch_paper_trading.py            # Paper trading launcher
├── 🚀 launch_dashboard.py                # Dashboard launcher
├── 🚀 launch_trading_system.py           # System launcher
├── 📋 requirements.txt                    # Dependencies
├── 📊 trading_config.json                # Runtime configuration
├── 🔑 zerodha_tokens.json                # API tokens (auto-generated)
├── 📈 instruments.csv                    # Market instruments data
├── 📁 logs/                             # System logs
├── 📁 state/                            # Trading state data
└── 📁 backtest_results/                 # Backtest outputs
```

## 🧪 Testing

### Health Check
```bash
python system_health_check.py
```

### Strategy Testing
```bash
# Test butterfly strategy fix
python test_butterfly_fix.py

# Test all fixes together
python test_all_fixes.py

# Test new menu structure
python test_new_menu.py
```

## 🛡️ Risk Management

### Position Sizing
- **Maximum risk per trade**: 2% of capital
- **Position size calculation**: Based on ATR and volatility
- **Maximum positions**: 10 concurrent positions

### Stop Loss & Take Profit
- **Dynamic stops**: Based on ATR and support/resistance
- **Trailing stops**: For trending positions
- **Time-based exits**: Option expiry management

### Portfolio Protection
- **Daily loss limits**: Automatic trading halt
- **Drawdown protection**: Progressive position size reduction
- **Volatility filters**: Skip trading in extreme market conditions

## 📊 Performance Monitoring

### Real-time Metrics
- **Portfolio value** and P&L tracking
- **Win rate** and average trade metrics
- **Sharpe ratio** and risk-adjusted returns
- **Maximum drawdown** monitoring

### Logging & Reporting
- **Detailed trade logs** in `logs/` directory
- **Performance CSV exports** for analysis
- **System diagnostics** and error tracking

## 🔧 Troubleshooting

### Common Issues

#### 1. Import Errors
```bash
# Check Python version
python --version

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

#### 2. API Authentication Issues
```bash
# Re-run token manager
python zerodha_token_manager.py

# Check token expiry in zerodha_tokens.json
```

#### 3. Dashboard Not Loading
```bash
# Check if port 8080 is available
netstat -an | grep 8080

# Try different port
python enhanced_dashboard_server.py
```

#### 4. No Live Data
```bash
# Verify API connectivity
python zerodha_token_manager.py

# Check instruments file
ls -la instruments.*
```

### System Diagnostics
```bash
# Run comprehensive health check
python system_health_check.py

# Check system diagnostics
cat system_diagnostics.json
```

## 🚨 Important Disclaimers

⚠️ **This is a trading system that involves real financial risk:**

1. **Paper trading recommended first**: Always test strategies with paper trading before live trading
2. **Risk management is crucial**: Never risk more than you can afford to lose
3. **Market volatility**: F&O trading can result in significant losses
4. **System reliability**: Technology failures can impact trading performance
5. **Regulatory compliance**: Ensure compliance with local trading regulations

## 📞 Support

For issues and improvements:
1. **Run health check**: `python system_health_check.py`
2. **Check logs**: Review files in `logs/` directory
3. **System diagnostics**: Check `system_diagnostics.json`

## 🎯 Roadmap

### Planned Features
- [ ] **Multi-broker support** (Beyond Zerodha)
- [ ] **Advanced ML models** for prediction
- [ ] **Portfolio optimization** algorithms
- [ ] **Social trading** features
- [ ] **Mobile app** integration
- [ ] **Cloud deployment** options

## ⚖️ License

This trading system is for educational and personal use. Please ensure compliance with local financial regulations and trading rules.

---

**🎉 Happy Trading! Remember: Always trade responsibly and manage your risk appropriately.**