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

# Import centralized constants
try:
    from constants import (
        APIConfig, TradingConfig as TradingConst, DatabaseConfig, RedisConfig,
        AlertConfig, FNOConfig, DashboardConfig, LogConfig
    )
    CONSTANTS_AVAILABLE = True
except ImportError:
    CONSTANTS_AVAILABLE = False
    # Fallback to hardcoded values if constants.py not available

class TradingConfig:
    """Centralized configuration management for the trading system"""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(__file__).parent
        self.config_file = self.config_dir / "trading_config.json"
        self.load_config()

    def load_config(self):
        """Load configuration from file or set defaults, with environment variable override"""
        default_token_path = str((Path.home() / ".config" / "trading-system" / "zerodha_token.json"))

        # Support environment variable overrides
        env_api_key = os.getenv('ZERODHA_API_KEY', '')
        env_api_secret = os.getenv('ZERODHA_API_SECRET', '')
        env_dashboard_port = os.getenv('DASHBOARD_PORT', '')

        default_config = {
            "api": {
                "zerodha": {
                    "api_key": env_api_key or "",
                    "api_secret": env_api_secret or "",
                    "token_file": default_token_path,
                    "request_delay": 0.25  # Rate limiting
                }
            },
            "dashboard": {
                "port": int(env_dashboard_port) if env_dashboard_port else 8080,
                "host": "localhost",
                "auto_open_browser": True
            },
            "trading": {
                "default_capital": 1000000,  # 10L
                "risk_per_trade": 0.02,      # 2% per trade
                "max_positions": 10,
                "risk_controls": {
                    "max_trades_per_day": 150,
                    "max_open_positions": 20,
                    "max_trades_per_symbol_per_day": 8,
                    "max_sector_exposure": 6,
                    "min_confidence": 0.70  # FIXED: Lowered from 0.8 to allow more trades
                },
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
            },
            "security": {
                "client_id": "CLIENT_001",
                "require_kyc": True,
                "enforce_aml": True,
                "kyc_data_dir": "kyc_data",
                "aml_data_dir": "aml_data",
                "protected_data_dir": "protected_data",
                "data_encryption_env": "DATA_ENCRYPTION_KEY",
                "aml_alert_threshold": 75,
                "state_encryption": {
                    "enabled": True,
                    "password_env": "TRADING_SECURITY_PASSWORD",
                    "filename": "current_state.enc"
                }
            }
        }

        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    saved_config = json.load(f)
                # Merge saved config with defaults (defaults for missing keys)
                self.config = self._merge_configs(default_config, saved_config)
                # Expand any ~ paths to full paths
                self._expand_paths()
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

    def _expand_paths(self):
        """
        Expand ~ and environment variables in ALL file paths for portability

        Handles:
        - Tilde expansion (~/ → /home/user/)
        - Environment variables ($VAR or ${VAR})
        - Relative paths (converted to absolute)

        Applied to: token_file, log directories, state directories, etc.
        """
        def expand_path(path_str: str) -> str:
            """Expand a single path string"""
            if not path_str or not isinstance(path_str, str):
                return path_str

            # First expand environment variables ($VAR, ${VAR})
            expanded = os.path.expandvars(path_str)

            # Then expand user home directory (~)
            expanded = os.path.expanduser(expanded)

            # Convert to absolute path if relative
            # (but skip if it looks like just a filename without path separators)
            if os.path.sep in expanded or expanded.startswith('.'):
                expanded = os.path.abspath(expanded)

            return expanded

        # Expand API token file path
        if 'api' in self.config and 'zerodha' in self.config['api']:
            token_file = self.config['api']['zerodha'].get('token_file', '')
            if token_file:
                self.config['api']['zerodha']['token_file'] = expand_path(token_file)

        # Expand directory paths
        if 'directories' in self.config:
            for dir_key in self.config['directories']:
                dir_path = self.config['directories'][dir_key]
                if dir_path:
                    self.config['directories'][dir_key] = expand_path(dir_path)

        # Expand logging file path
        if 'logging' in self.config and 'file' in self.config['logging']:
            log_file = self.config['logging']['file']
            if log_file and (os.path.sep in log_file or log_file.startswith('~')):
                self.config['logging']['file'] = expand_path(log_file)

        # Expand security directories if present
        security_cfg = self.config.get('security', {})
        for dir_key in ['kyc_data_dir', 'aml_data_dir', 'protected_data_dir']:
            dir_path = security_cfg.get(dir_key)
            if dir_path:
                security_cfg[dir_key] = expand_path(dir_path)
        state_enc = security_cfg.get('state_encryption', {})
        enc_filename = state_enc.get('filename')
        if enc_filename and (os.path.sep in enc_filename or enc_filename.startswith('~')):
            state_enc['filename'] = expand_path(enc_filename)
        if state_enc:
            security_cfg['state_encryption'] = state_enc
        if security_cfg:
            self.config['security'] = security_cfg

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
            full_path.mkdir(parents=True, exist_ok=True)

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

    def get_security_config(self) -> Dict[str, Any]:
        """Get security configuration"""
        return self.get("security", {})

    def validate(self, mode: str = "paper", strict: bool = False) -> tuple[bool, list[str]]:
        """
        Validate configuration for the given trading mode

        Args:
            mode: Trading mode - "paper", "backtest", or "live"
            strict: If True, enforce strict validation (e.g., require API keys even in paper mode)

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Live mode requires API credentials
        if mode == "live" or strict:
            api_key = self.get("api.zerodha.api_key", "")
            api_secret = self.get("api.zerodha.api_secret", "")

            if not api_key or len(api_key) < 10:
                errors.append("API key is missing or invalid (required for live trading)")
            if not api_secret or len(api_secret) < 10:
                errors.append("API secret is missing or invalid (required for live trading)")
            if api_key == api_secret and api_key:
                errors.append("API key and secret should not be identical")

        # Validate trading parameters
        risk_per_trade = self.get("trading.risk_per_trade", 0)
        if not (0 < risk_per_trade <= 0.1):
            errors.append(f"Risk per trade ({risk_per_trade}) should be between 0 and 0.1 (0-10%)")

        max_positions = self.get("trading.max_positions", 0)
        if max_positions < 1:
            errors.append(f"Max positions ({max_positions}) must be at least 1")

        # Validate directories exist or can be created
        try:
            self.create_directories()
        except Exception as e:
            errors.append(f"Cannot create directories: {e}")

        # Validate dashboard port
        port = self.get("dashboard.port", 0)
        if not (1024 <= port <= 65535):
            errors.append(f"Dashboard port ({port}) should be between 1024 and 65535")

        return (len(errors) == 0, errors)

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

# ============================================================================
# MODULE-LEVEL ATTRIBUTES (For backward compatibility with extracted modules)
# ============================================================================

# Cache settings
cache_ttl_seconds = 60  # Cache TTL in seconds

# Portfolio settings
initial_capital = 1000000  # 10 lakh default
min_position_size = 0.10  # 10% minimum position size
max_position_size = 0.20  # 20% maximum position size

# Risk management
risk_per_trade_pct = 0.02  # 2% risk per trade
atr_stop_multiplier = 2.0
atr_target_multiplier = 3.0
trailing_activation_multiplier = 1.5
trailing_stop_multiplier = 0.8

# Signal aggregation
signal_agreement_threshold = 0.5  # 50% strategies must agree

# Performance monitoring
enable_performance_monitoring = True

# Logging
log_level = "INFO"
log_dir = "logs"

# Trading limits
max_positions = 10
max_daily_loss_pct = 0.05  # 5% max daily loss
request_timeout = 30  # Seconds for HTTP/API timeouts
