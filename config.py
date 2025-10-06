#!/usr/bin/env python3
"""
Trading System Configuration Management
Centralized configuration for the entire trading system
"""

import os
import json
from pathlib import Path
from datetime import datetime, time
from typing import Dict, Any, Optional

class TradingConfig:
    """Centralized configuration management for the trading system"""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(__file__).parent
        self.config_file = self.config_dir / "trading_config.json"
        self.load_config()

    def load_config(self):
        """Load configuration from file or set defaults"""
        default_config = {
            "api": {
                "zerodha": {
                    "api_key": "b0umi99jeas93od0",
                    "api_secret": "8jyer3zt5stm0udso2ir6yqclefot475",
                    "token_file": "zerodha_tokens.json",
                    "request_delay": 0.25  # Rate limiting
                }
            },
            "dashboard": {
                "port": 8080,
                "host": "localhost",
                "auto_open_browser": True
            },
            "trading": {
                "default_capital": 1000000,  # 10L
                "risk_per_trade": 0.02,      # 2% per trade
                "max_positions": 10,
                "trading_hours": {
                    "start": "09:15",
                    "end": "15:30"
                },
                "option_chain_limit": 150,   # Performance limit
                "option_chain_timeout": 30   # Seconds
            },
            "fno": {
                "indices": ["NIFTY", "BANKNIFTY", "FINNIFTY"],
                "lot_sizes": {
                    "NIFTY": 50,
                    "BANKNIFTY": 15,
                    "FINNIFTY": 40
                },
                "fallback_spot_prices": {
                    "NIFTY": 25000,
                    "BANKNIFTY": 53500,
                    "FINNIFTY": 19500
                }
            },
            "logging": {
                "level": "INFO",
                "file": "trading_system.log",
                "max_size_mb": 50,
                "backup_count": 5
            },
            "directories": {
                "logs": "logs",
                "state": "state",
                "backtest_results": "backtest_results"
            }
        }

        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    saved_config = json.load(f)
                # Merge saved config with defaults (defaults for missing keys)
                self.config = self._merge_configs(default_config, saved_config)
            except Exception as e:
                print(f"⚠️ Error loading config file: {e}")
                print("📋 Using default configuration")
                self.config = default_config
        else:
            self.config = default_config
            self.save_config()  # Save default config

    def _merge_configs(self, default: Dict[str, Any], saved: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge saved config with defaults"""
        result = default.copy()
        for key, value in saved.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result

    def save_config(self):
        """Save current configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving config: {e}")

    def get(self, key_path: str, default=None):
        """Get configuration value using dot notation (e.g., 'api.zerodha.api_key')"""
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def set(self, key_path: str, value):
        """Set configuration value using dot notation"""
        keys = key_path.split('.')
        config = self.config
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value
        self.save_config()

    def is_trading_time(self) -> bool:
        """Check if current time is within trading hours"""
        now = datetime.now().time()
        start_str = self.get("trading.trading_hours.start", "09:15")
        end_str = self.get("trading.trading_hours.end", "15:30")

        start_time = time.fromisoformat(start_str)
        end_time = time.fromisoformat(end_str)

        return start_time <= now <= end_time

    def create_directories(self):
        """Create necessary directories"""
        dirs = self.get("directories", {})
        for dir_key, dir_path in dirs.items():
            full_path = self.config_dir / dir_path
            full_path.mkdir(exist_ok=True)

    def get_api_credentials(self) -> tuple:
        """Get Zerodha API credentials"""
        api_key = self.get("api.zerodha.api_key")
        api_secret = self.get("api.zerodha.api_secret")
        return api_key, api_secret

    def get_dashboard_config(self) -> Dict[str, Any]:
        """Get dashboard configuration"""
        return self.get("dashboard", {})

    def get_trading_config(self) -> Dict[str, Any]:
        """Get trading configuration"""
        return self.get("trading", {})

    def get_fno_config(self) -> Dict[str, Any]:
        """Get F&O configuration"""
        return self.get("fno", {})

# Global config instance
config = TradingConfig()

def get_config() -> TradingConfig:
    """Get the global configuration instance"""
    return config

if __name__ == "__main__":
    # Test configuration
    print("🔧 Testing Trading System Configuration")
    print("="*50)

    cfg = TradingConfig()

    print(f"API Key: {cfg.get('api.zerodha.api_key', 'Not set')}")
    print(f"Dashboard Port: {cfg.get('dashboard.port', 'Not set')}")
    print(f"Default Capital: ₹{cfg.get('trading.default_capital', 0):,}")
    print(f"Trading Hours: {cfg.get('trading.trading_hours.start')} - {cfg.get('trading.trading_hours.end')}")
    print(f"Is Trading Time: {cfg.is_trading_time()}")

    # Create directories
    cfg.create_directories()
    print(f"✅ Configuration loaded and directories created")