#!/usr/bin/env python3
"""
Unified Configuration System for Trading Platform
Consolidates all configuration sources into a single source of truth
Addresses critical configuration fragmentation issues
"""

import os
import json
import warnings
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
from datetime import time
from enum import Enum


class TradingMode(Enum):
    """Trading mode enumeration"""
    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"


class ConfigValidationError(Exception):
    """Raised when configuration validation fails"""
    pass


@dataclass
class RiskConfig:
    """Risk management configuration"""
    # Core risk parameters - SINGLE SOURCE OF TRUTH
    risk_per_trade_pct: float = 0.015  # 1.5% per trade (conservative default)
    stop_loss_pct: float = 0.03        # 3% stop loss
    take_profit_pct: float = 0.10      # 10% take profit
    max_daily_loss_pct: float = 0.05   # 5% max daily loss
    max_position_loss_pct: float = 0.10  # 10% max loss per position

    # Position sizing
    min_position_size_pct: float = 0.10  # 10% of capital min
    max_position_size_pct: float = 0.25  # 25% of capital max
    max_positions: int = 25

    # ATR-based stops
    atr_stop_multiplier: float = 2.0
    atr_target_multiplier: float = 3.5
    trailing_activation_multiplier: float = 1.5
    trailing_stop_multiplier: float = 0.8

    # Safety limits
    max_trades_per_day: int = 150
    max_open_positions: int = 20
    max_trades_per_symbol_per_day: int = 8
    max_sector_exposure: int = 6
    max_consecutive_losses: int = 3

    def validate(self) -> List[str]:
        """Validate risk parameters and return warnings"""
        warnings_list = []

        # Critical validations
        if not 0 < self.risk_per_trade_pct <= 0.05:
            raise ConfigValidationError(
                f"risk_per_trade_pct must be between 0 and 5% (got {self.risk_per_trade_pct:.1%})"
            )

        if not 0 < self.stop_loss_pct <= 0.20:
            raise ConfigValidationError(
                f"stop_loss_pct must be between 0 and 20% (got {self.stop_loss_pct:.1%})"
            )

        if not 0 < self.max_daily_loss_pct <= 0.15:
            raise ConfigValidationError(
                f"max_daily_loss_pct must be between 0 and 15% (got {self.max_daily_loss_pct:.1%})"
            )

        # Warning-level validations
        if self.risk_per_trade_pct > 0.02:
            warnings_list.append(
                f"⚠️  risk_per_trade_pct ({self.risk_per_trade_pct:.1%}) > 2% - aggressive setting"
            )

        if self.max_position_size_pct > 0.20:
            warnings_list.append(
                f"⚠️  max_position_size_pct ({self.max_position_size_pct:.1%}) > 20% - concentrated risk"
            )

        if self.max_positions > 30:
            warnings_list.append(
                f"⚠️  max_positions ({self.max_positions}) > 30 - difficult to manage"
            )

        return warnings_list


@dataclass
class StrategyConfig:
    """Strategy configuration"""
    min_confidence: float = 0.45  # Minimum confidence for signal
    signal_agreement_threshold: float = 0.40  # Multiple strategy agreement
    cooldown_minutes: int = 15  # Cooldown between trades on same symbol

    # Strategy-specific parameters
    rsi_period: int = 7
    rsi_oversold: int = 25
    rsi_overbought: int = 75

    ma_short_window: int = 3
    ma_long_window: int = 10

    bollinger_period: int = 20
    bollinger_std_dev: float = 2.0

    # Signal confirmation
    require_confirmation: bool = True  # NEW: Require confirmation signals
    confirmation_bars: int = 2  # NEW: Number of bars for confirmation

    def validate(self) -> List[str]:
        """Validate strategy parameters"""
        warnings_list = []

        if not 0 < self.min_confidence <= 1.0:
            raise ConfigValidationError(
                f"min_confidence must be between 0 and 1 (got {self.min_confidence})"
            )

        if self.ma_short_window >= self.ma_long_window:
            raise ConfigValidationError(
                f"ma_short_window ({self.ma_short_window}) must be < ma_long_window ({self.ma_long_window})"
            )

        if self.min_confidence < 0.40:
            warnings_list.append(
                f"⚠️  min_confidence ({self.min_confidence}) < 0.40 - may generate excessive signals"
            )

        return warnings_list


@dataclass
class APIConfig:
    """API configuration"""
    zerodha_api_key: str = ""
    zerodha_api_secret: str = ""
    zerodha_token_file: str = ""

    # Rate limiting
    max_requests_per_second: int = 3  # Zerodha limit
    max_requests_per_minute: int = 60
    request_timeout: int = 30
    request_delay: float = 0.33  # 3 requests per second

    # Circuit breaker
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60

    def validate(self) -> List[str]:
        """Validate API configuration"""
        warnings_list = []

        if not self.zerodha_api_key:
            warnings_list.append("⚠️  zerodha_api_key not set - set via environment variable")

        if not self.zerodha_api_secret:
            warnings_list.append("⚠️  zerodha_api_secret not set - set via environment variable")

        if self.max_requests_per_second > 3:
            warnings_list.append(
                f"⚠️  max_requests_per_second ({self.max_requests_per_second}) > 3 - may exceed Zerodha limits"
            )

        return warnings_list


@dataclass
class CacheConfig:
    """Cache configuration for memory management"""
    # Memory limits
    max_cache_size_mb: int = 2048  # 2GB max
    max_instruments: int = 1000  # Limit cached instruments

    # TTL settings
    cache_ttl_seconds: int = 60
    instrument_cache_ttl_seconds: int = 3600  # 1 hour

    # Eviction policy
    eviction_policy: str = "lru"  # Least Recently Used

    def validate(self) -> List[str]:
        """Validate cache configuration"""
        warnings_list = []

        if self.max_cache_size_mb > 4096:
            warnings_list.append(
                f"⚠️  max_cache_size_mb ({self.max_cache_size_mb}MB) > 4GB - may cause memory issues"
            )

        if self.max_instruments > 2000:
            warnings_list.append(
                f"⚠️  max_instruments ({self.max_instruments}) > 2000 - may cause performance issues"
            )

        return warnings_list


@dataclass
class AlertConfig:
    """Alert management configuration"""
    # Alert thresholds
    slow_execution_threshold_ms: int = 5000  # 5 seconds
    stale_data_threshold_seconds: int = 300  # 5 minutes
    consecutive_failures_threshold: int = 3

    # Alert channels (future expansion)
    enable_console_alerts: bool = True
    enable_log_alerts: bool = True
    enable_email_alerts: bool = False
    enable_sms_alerts: bool = False

    # Alert severity levels
    alert_on_critical: bool = True
    alert_on_high: bool = True
    alert_on_medium: bool = True
    alert_on_low: bool = False

    def validate(self) -> List[str]:
        """Validate alert configuration"""
        return []  # No critical validations needed


@dataclass
class UnifiedTradingConfig:
    """
    Unified Trading Configuration - SINGLE SOURCE OF TRUTH

    This replaces:
    - config.py (legacy)
    - trading_config.py (duplicate)
    - trading_config.json (duplicate)
    - Various hardcoded configs throughout codebase
    """

    # Sub-configurations
    risk: RiskConfig = field(default_factory=RiskConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    api: APIConfig = field(default_factory=APIConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)

    # Trading mode
    mode: TradingMode = TradingMode.PAPER

    # Capital settings
    initial_capital: float = 1_000_000.0  # 10 Lakhs

    # Dashboard
    dashboard_port: int = 8080
    dashboard_host: str = "localhost"
    dashboard_auto_open: bool = True

    # Logging
    log_level: str = "INFO"
    log_dir: str = "logs"
    log_max_size_mb: int = 50
    log_backup_count: int = 5

    # Directories
    state_dir: str = "state"
    backtest_results_dir: str = "backtest_results"

    # Trading hours
    market_open: time = field(default_factory=lambda: time(9, 15))
    market_close: time = field(default_factory=lambda: time(15, 30))

    # F&O settings
    fno_indices: List[str] = field(default_factory=lambda: ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX", "BANKEX"])
    option_chain_limit: int = 150
    option_chain_timeout: int = 30

    # Safety features
    require_confirmation_live: bool = True
    enable_performance_monitoring: bool = True

    @classmethod
    def from_env(cls) -> 'UnifiedTradingConfig':
        """
        Create configuration from environment variables

        Environment variables:
        - ZERODHA_API_KEY
        - ZERODHA_API_SECRET
        - ZERODHA_TOKEN_FILE
        - TRADING_MODE (paper/live/backtest)
        - INITIAL_CAPITAL
        - RISK_PER_TRADE_PCT
        - LOG_LEVEL
        """
        # Determine token file path
        default_token_path = str(Path.home() / ".config" / "trading-system" / "zerodha_token.json")
        token_file = os.getenv('ZERODHA_TOKEN_FILE', default_token_path)

        # Create sub-configs from environment
        risk_config = RiskConfig(
            risk_per_trade_pct=cls._safe_float_env('RISK_PER_TRADE_PCT', 0.015),
            stop_loss_pct=cls._safe_float_env('STOP_LOSS_PCT', 0.03),
            take_profit_pct=cls._safe_float_env('TAKE_PROFIT_PCT', 0.10),
            max_daily_loss_pct=cls._safe_float_env('MAX_DAILY_LOSS_PCT', 0.05),
            max_positions=cls._safe_int_env('MAX_POSITIONS', 25),
        )

        api_config = APIConfig(
            zerodha_api_key=os.getenv('ZERODHA_API_KEY', ''),
            zerodha_api_secret=os.getenv('ZERODHA_API_SECRET', ''),
            zerodha_token_file=token_file,
        )

        cache_config = CacheConfig(
            max_cache_size_mb=cls._safe_int_env('MAX_CACHE_SIZE_MB', 2048),
            max_instruments=cls._safe_int_env('MAX_CACHED_INSTRUMENTS', 1000),
        )

        # Determine trading mode
        mode_str = os.getenv('TRADING_MODE', 'paper').lower()
        mode = TradingMode.PAPER if mode_str == 'paper' else (
            TradingMode.LIVE if mode_str == 'live' else TradingMode.BACKTEST
        )

        return cls(
            risk=risk_config,
            strategy=StrategyConfig(),
            api=api_config,
            cache=cache_config,
            alerts=AlertConfig(),
            mode=mode,
            initial_capital=cls._safe_float_env('INITIAL_CAPITAL', 1_000_000.0),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
        )

    @classmethod
    def from_file(cls, config_path: Path) -> 'UnifiedTradingConfig':
        """Load configuration from JSON file"""
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r') as f:
            data = json.load(f)

        # Parse nested configs
        risk_config = RiskConfig(**data.get('risk', {})) if 'risk' in data else RiskConfig()
        strategy_config = StrategyConfig(**data.get('strategy', {})) if 'strategy' in data else StrategyConfig()
        api_config = APIConfig(**data.get('api', {})) if 'api' in data else APIConfig()
        cache_config = CacheConfig(**data.get('cache', {})) if 'cache' in data else CacheConfig()
        alert_config = AlertConfig(**data.get('alerts', {})) if 'alerts' in data else AlertConfig()

        return cls(
            risk=risk_config,
            strategy=strategy_config,
            api=api_config,
            cache=cache_config,
            alerts=alert_config,
            mode=TradingMode(data.get('mode', 'paper')),
            initial_capital=data.get('initial_capital', 1_000_000.0),
            dashboard_port=data.get('dashboard_port', 8080),
            log_level=data.get('log_level', 'INFO'),
        )

    def save_to_file(self, config_path: Path):
        """Save configuration to JSON file"""
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'risk': asdict(self.risk),
            'strategy': asdict(self.strategy),
            'api': asdict(self.api),
            'cache': asdict(self.cache),
            'alerts': asdict(self.alerts),
            'mode': self.mode.value,
            'initial_capital': self.initial_capital,
            'dashboard_port': self.dashboard_port,
            'dashboard_host': self.dashboard_host,
            'log_level': self.log_level,
            'log_dir': self.log_dir,
            'state_dir': self.state_dir,
            'fno_indices': self.fno_indices,
        }

        with open(config_path, 'w') as f:
            json.dump(data, f, indent=2)

    def validate(self) -> bool:
        """
        Validate entire configuration

        Returns:
            True if valid (may have warnings)

        Raises:
            ConfigValidationError: If critical validation fails
        """
        all_warnings = []

        # Validate each sub-config
        all_warnings.extend(self.risk.validate())
        all_warnings.extend(self.strategy.validate())
        all_warnings.extend(self.api.validate())
        all_warnings.extend(self.cache.validate())
        all_warnings.extend(self.alerts.validate())

        # Print warnings
        if all_warnings:
            print("\n" + "="*70)
            print("⚠️  CONFIGURATION WARNINGS")
            print("="*70)
            for warning in all_warnings:
                print(warning)
            print("="*70 + "\n")

        # Cross-config validations
        if self.mode == TradingMode.LIVE:
            if self.risk.risk_per_trade_pct > 0.02:
                warnings.warn(
                    f"LIVE mode with risk_per_trade_pct={self.risk.risk_per_trade_pct:.1%} > 2% - "
                    "consider reducing for live trading"
                )

            if not self.api.zerodha_api_key or not self.api.zerodha_api_secret:
                raise ConfigValidationError(
                    "LIVE mode requires ZERODHA_API_KEY and ZERODHA_API_SECRET"
                )

        return True

    def get_risk_per_trade_for_mode(self) -> float:
        """
        Get risk per trade adjusted for trading mode

        Returns different risk levels based on mode:
        - Paper: configured value
        - Live: min(configured, 0.015) - capped at 1.5%
        - Backtest: configured value
        """
        if self.mode == TradingMode.LIVE:
            # Cap live trading at 1.5% regardless of config
            return min(self.risk.risk_per_trade_pct, 0.015)
        return self.risk.risk_per_trade_pct

    def print_summary(self):
        """Print configuration summary"""
        print("\n" + "="*70)
        print("📊 TRADING SYSTEM CONFIGURATION")
        print("="*70)
        print(f"Mode:               {self.mode.value.upper()}")
        print(f"Initial Capital:    ₹{self.initial_capital:,.0f}")
        print()
        print("RISK MANAGEMENT:")
        print(f"  Risk per Trade:   {self.get_risk_per_trade_for_mode():.2%}")
        print(f"  Stop Loss:        {self.risk.stop_loss_pct:.2%}")
        print(f"  Take Profit:      {self.risk.take_profit_pct:.2%}")
        print(f"  Max Daily Loss:   {self.risk.max_daily_loss_pct:.2%}")
        print(f"  Max Positions:    {self.risk.max_positions}")
        print()
        print("STRATEGY:")
        print(f"  Min Confidence:   {self.strategy.min_confidence:.2f}")
        print(f"  Require Confirm:  {self.strategy.require_confirmation}")
        print(f"  Cooldown:         {self.strategy.cooldown_minutes} min")
        print()
        print("CACHE & PERFORMANCE:")
        print(f"  Max Cache:        {self.cache.max_cache_size_mb} MB")
        print(f"  Max Instruments:  {self.cache.max_instruments}")
        print(f"  Cache TTL:        {self.cache.cache_ttl_seconds}s")
        print()
        print("API:")
        print(f"  Rate Limit:       {self.api.max_requests_per_second} req/s")
        print(f"  Circuit Breaker:  {self.api.enable_circuit_breaker}")
        print("="*70 + "\n")

    @staticmethod
    def _safe_float_env(key: str, default: float) -> float:
        """Safely get float from environment"""
        try:
            return float(os.getenv(key, default))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_int_env(key: str, default: int) -> int:
        """Safely get int from environment"""
        try:
            return int(os.getenv(key, default))
        except (ValueError, TypeError):
            return default


# Global configuration instance
_config_instance: Optional[UnifiedTradingConfig] = None


def get_config(force_reload: bool = False) -> UnifiedTradingConfig:
    """
    Get the global configuration instance (singleton pattern)

    Args:
        force_reload: Force reload from environment/file

    Returns:
        UnifiedTradingConfig instance
    """
    global _config_instance

    if _config_instance is None or force_reload:
        # Try to load from file first, then fall back to environment
        config_file = Path("unified_config.json")

        if config_file.exists():
            _config_instance = UnifiedTradingConfig.from_file(config_file)
        else:
            _config_instance = UnifiedTradingConfig.from_env()

        # Validate configuration
        _config_instance.validate()

    return _config_instance


def set_config(config: UnifiedTradingConfig):
    """Set the global configuration instance"""
    global _config_instance
    config.validate()
    _config_instance = config


# Backward compatibility helpers
def get(key: str, default: Any = None) -> Any:
    """
    Get configuration value by key path (backward compatibility)

    Examples:
        get('trading.risk_per_trade') -> 0.015
        get('api.zerodha_api_key') -> 'xxx'
    """
    config = get_config()

    # Map old config paths to new structure
    key_mapping = {
        'trading.risk_per_trade': lambda c: c.get_risk_per_trade_for_mode(),
        'trading.default_capital': lambda c: c.initial_capital,
        'trading.max_positions': lambda c: c.risk.max_positions,
        'trading.risk_controls.min_confidence': lambda c: c.strategy.min_confidence,
        'api.zerodha.api_key': lambda c: c.api.zerodha_api_key,
        'api.zerodha.api_secret': lambda c: c.api.zerodha_api_secret,
        'api.zerodha.token_file': lambda c: c.api.zerodha_token_file,
        'dashboard.port': lambda c: c.dashboard_port,
        'logging.level': lambda c: c.log_level,
    }

    if key in key_mapping:
        return key_mapping[key](config)

    return default


if __name__ == "__main__":
    # Test configuration
    print("Creating unified configuration from environment...")
    config = UnifiedTradingConfig.from_env()
    config.print_summary()

    # Save example config
    example_file = Path("unified_config.example.json")
    config.save_to_file(example_file)
    print(f"✅ Example configuration saved to: {example_file}")
