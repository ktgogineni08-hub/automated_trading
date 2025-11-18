"""
Configuration management for trading system
"""
import os
from dataclasses import dataclass
from typing import Optional
from trading_exceptions import ConfigurationError


@dataclass
class TradingConfig:
    """Configuration class for trading system with improved risk defaults"""
    # API Configuration
    api_key: str = ""
    api_secret: str = ""

    # Trading Configuration
    initial_capital: float = 1_000_000.0
    max_positions: int = 25
    min_position_size: float = 0.10
    max_position_size: float = 0.25  # Reduced from 0.30 to 0.25

    # Risk Management - More Conservative Defaults
    risk_per_trade_pct: float = 0.015  # 1.5% per trade (reduced from 2%)
    stop_loss_pct: float = 0.03       # 3% stop loss (increased from 2% for safety)
    take_profit_pct: float = 0.10     # 10% take profit (reduced from 15% to be more realistic)
    max_daily_loss_pct: float = 0.05  # NEW: 5% max daily loss limit
    max_position_loss_pct: float = 0.10  # NEW: 10% max loss per position

    # ATR Settings - More Balanced
    atr_stop_multiplier: float = 2.0   # Slightly looser stops (from 1.8)
    atr_target_multiplier: float = 3.5 # More realistic targets (from 4.5)
    trailing_activation_multiplier: float = 1.5  # Increased for better activation
    trailing_stop_multiplier: float = 0.8  # Slightly looser trailing stop

    # Strategy Configuration - More Conservative
    min_confidence: float = 0.45       # Higher confidence threshold (from 0.35)
    signal_agreement_threshold: float = 0.40  # Higher agreement needed (from 0.30)
    cooldown_minutes: int = 15         # Longer cooldown (from 5) to avoid overtrading

    # API Settings
    max_requests_per_second: int = 1
    max_requests_per_minute: int = 50
    request_timeout: int = 30

    # Dashboard
    dashboard_url: str = "http://localhost:8080"
    dashboard_enabled: bool = True

    # Logging
    log_level: str = "INFO"
    log_dir: str = "logs"

    # Performance
    enable_performance_monitoring: bool = True
    cache_ttl_seconds: int = 60  # Increased from 30 to reduce API calls

    # Safety Features
    enable_circuit_breaker: bool = True
    max_consecutive_losses: int = 3  # Stop trading after 3 consecutive losses
    require_confirmation_live: bool = True  # Always require confirmation for live trades

    @classmethod
    def from_env(cls) -> 'TradingConfig':
        """Create configuration from environment variables with type safety"""
        return cls(
            api_key=os.getenv('ZERODHA_API_KEY', ''),
            api_secret=os.getenv('ZERODHA_API_SECRET', ''),
            initial_capital=cls._safe_float_env('INITIAL_CAPITAL', 1000000.0),
            max_positions=cls._safe_int_env('MAX_POSITIONS', 25),
            min_position_size=cls._safe_float_env('MIN_POSITION_SIZE', 0.10),
            max_position_size=cls._safe_float_env('MAX_POSITION_SIZE', 0.25),
            risk_per_trade_pct=cls._safe_float_env('RISK_PER_TRADE_PCT', 0.015),
            stop_loss_pct=cls._safe_float_env('STOP_LOSS_PCT', 0.03),
            take_profit_pct=cls._safe_float_env('TAKE_PROFIT_PCT', 0.10),
            max_daily_loss_pct=cls._safe_float_env('MAX_DAILY_LOSS_PCT', 0.05),
            dashboard_url=os.getenv('DASHBOARD_URL', 'http://localhost:8080'),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            log_dir=os.getenv('LOG_DIR', 'logs'),
            enable_performance_monitoring=os.getenv('ENABLE_PERFORMANCE_MONITORING', 'true').lower() == 'true',
            cache_ttl_seconds=cls._safe_int_env('CACHE_TTL_SECONDS', 60)
        )

    @staticmethod
    def _safe_float_env(key: str, default: float) -> float:
        """Safely parse float from environment variable"""
        try:
            value = os.getenv(key)
            return float(value) if value else default
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_int_env(key: str, default: int) -> int:
        """Safely parse int from environment variable"""
        try:
            value = os.getenv(key)
            return int(value) if value else default
        except (ValueError, TypeError):
            return default

    def validate(self) -> None:
        """Validate configuration parameters with comprehensive checks"""
        if self.initial_capital <= 0:
            raise ConfigurationError("Initial capital must be positive")

        if self.initial_capital < 100000:
            raise ConfigurationError("Initial capital should be at least ₹1,00,000 for proper diversification")

        if self.max_positions <= 0:
            raise ConfigurationError("Max positions must be positive")

        if self.max_positions > 50:
            raise ConfigurationError("Max positions should not exceed 50 to maintain manageable portfolio")

        if not 0 < self.min_position_size <= self.max_position_size <= 1:
            raise ConfigurationError("Position sizes must be between 0 and 1, with min <= max")

        if self.max_position_size > 0.30:
            raise ConfigurationError("Max position size should not exceed 30% for proper risk management")

        if not 0 < self.risk_per_trade_pct <= 0.05:
            raise ConfigurationError("Risk per trade should be between 0% and 5%")

        if not 0.01 <= self.stop_loss_pct <= 0.20:
            raise ConfigurationError("Stop loss should be between 1% and 20%")

        if not 0.05 <= self.take_profit_pct <= 0.50:
            raise ConfigurationError("Take profit should be between 5% and 50%")

        if self.take_profit_pct < self.stop_loss_pct:
            raise ConfigurationError("Take profit should be greater than stop loss for positive risk-reward ratio")

        if not 0 < self.min_confidence <= 1:
            raise ConfigurationError("Min confidence must be between 0 and 1")

        if not 0 < self.signal_agreement_threshold <= 1:
            raise ConfigurationError("Signal agreement threshold must be between 0 and 1")

        if self.cooldown_minutes < 0:
            raise ConfigurationError("Cooldown minutes cannot be negative")

        if self.cooldown_minutes < 5:
            raise ConfigurationError("Cooldown should be at least 5 minutes to avoid overtrading")

        if self.api_key and not self.api_secret:
            raise ConfigurationError("API secret is required when API key is provided")

        if self.dashboard_url and not self.dashboard_url.startswith(('http://', 'https://')):
            raise ConfigurationError("Dashboard URL must start with http:// or https://")

        if self.cache_ttl_seconds < 10:
            raise ConfigurationError("Cache TTL should be at least 10 seconds")

        if self.request_timeout < 5:
            raise ConfigurationError("Request timeout should be at least 5 seconds")

    def get_risk_reward_ratio(self) -> float:
        """Calculate risk-reward ratio"""
        return self.take_profit_pct / self.stop_loss_pct if self.stop_loss_pct > 0 else 0.0

    def is_safe_for_live_trading(self) -> tuple[bool, list[str]]:
        """Check if configuration is safe for live trading"""
        warnings = []

        if self.risk_per_trade_pct > 0.02:
            warnings.append(f"Risk per trade ({self.risk_per_trade_pct:.1%}) is high - recommended max 2%")

        if self.max_position_size > 0.25:
            warnings.append(f"Max position size ({self.max_position_size:.1%}) is high - recommended max 25%")

        if self.stop_loss_pct < 0.02:
            warnings.append(f"Stop loss ({self.stop_loss_pct:.1%}) is very tight - may trigger frequently")

        if self.cooldown_minutes < 10:
            warnings.append(f"Cooldown ({self.cooldown_minutes} min) is short - may cause overtrading")

        if self.get_risk_reward_ratio() < 2.0:
            warnings.append(f"Risk-reward ratio ({self.get_risk_reward_ratio():.2f}) is below 2:1")

        return len(warnings) == 0, warnings

    def to_dict(self) -> dict:
        """Convert configuration to dictionary"""
        return {
            'initial_capital': self.initial_capital,
            'max_positions': self.max_positions,
            'risk_per_trade_pct': self.risk_per_trade_pct,
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'min_confidence': self.min_confidence,
            'risk_reward_ratio': self.get_risk_reward_ratio()
        }

    def __repr__(self) -> str:
        """String representation of config"""
        return (
            f"TradingConfig(capital=₹{self.initial_capital:,.0f}, "
            f"positions={self.max_positions}, "
            f"risk={self.risk_per_trade_pct:.1%}, "
            f"SL={self.stop_loss_pct:.1%}, "
            f"TP={self.take_profit_pct:.1%}, "
            f"RR={self.get_risk_reward_ratio():.2f})"
        )
