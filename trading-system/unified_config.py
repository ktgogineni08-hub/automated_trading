#!/usr/bin/env python3
"""
Unified Configuration System
Single source of truth for all trading system configuration
Loads from trading_config.yaml with environment variable expansion
"""

import os
import re
import yaml
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails"""
    pass


@dataclass
class APIConfig:
    """API configuration"""
    api_key: str
    api_secret: str
    token_file: str
    request_delay: float = 0.25

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RiskConfig:
    """Risk management configuration - SINGLE SOURCE OF TRUTH"""
    # Core risk parameters
    risk_per_trade_pct: float
    stop_loss_pct: float
    take_profit_pct: float
    max_daily_loss_pct: float
    max_position_loss_pct: float

    # Position limits
    max_trades_per_day: int
    max_open_positions: int
    max_trades_per_symbol_per_day: int
    max_sector_exposure: int
    max_consecutive_losses: int

    # Position sizing
    min_position_size_pct: float
    max_position_size_pct: float
    max_positions: int

    # ATR-based stops
    atr_stop_multiplier: float
    atr_target_multiplier: float
    trailing_activation_multiplier: float
    trailing_stop_multiplier: float

    def validate(self) -> List[str]:
        """Validate risk parameters"""
        warnings_list = []

        # Critical validations
        if not 0 < self.risk_per_trade_pct <= 0.05:
            raise ConfigValidationError(
                f"risk_per_trade_pct must be 0-5% (got {self.risk_per_trade_pct:.1%})"
            )

        if not 0 < self.stop_loss_pct <= 0.20:
            raise ConfigValidationError(
                f"stop_loss_pct must be 0-20% (got {self.stop_loss_pct:.1%})"
            )

        if not 0 < self.max_daily_loss_pct <= 0.15:
            raise ConfigValidationError(
                f"max_daily_loss_pct must be 0-15% (got {self.max_daily_loss_pct:.1%})"
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

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class StrategyConfig:
    """Strategy configuration"""
    min_confidence: float
    aggregator_min_agreement: float
    cooldown_minutes: int
    stop_loss_cooldown_minutes: int

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class MarketHoursConfig:
    """Market hours configuration"""
    start: str
    end: str
    timezone: str

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DashboardConfig:
    """Dashboard configuration"""
    host: str
    port: int
    auto_open_browser: bool
    api_key: str
    ssl_enabled: bool
    cert_file: Optional[str]
    key_file: Optional[str]

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TradingConfig:
    """Complete trading system configuration"""
    # Core configurations
    api: APIConfig
    risk: RiskConfig
    strategies: StrategyConfig
    market_hours: MarketHoursConfig
    dashboard: DashboardConfig
    market_indexes: Dict[str, int]

    # Raw configuration data
    raw_config: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> 'TradingConfig':
        """
        Load configuration from YAML file with environment variable expansion

        Args:
            config_path: Path to config file (defaults to trading_config.yaml)

        Returns:
            TradingConfig instance
        """
        if config_path is None:
            config_path = Path(__file__).parent / "trading_config.yaml"

        if not config_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {config_path}\n"
                f"Please create trading_config.yaml"
            )

        logger.info(f"📋 Loading configuration from {config_path}")

        # Load YAML
        with open(config_path, 'r') as f:
            raw_config = yaml.safe_load(f)

        # Expand environment variables
        config = cls._expand_env_vars(raw_config)

        # Build typed config objects
        api_config = APIConfig(
            api_key=config['api']['zerodha']['api_key'],
            api_secret=config['api']['zerodha']['api_secret'],
            token_file=os.path.expanduser(config['api']['zerodha']['token_file']),
            request_delay=config['api']['zerodha']['request_delay']
        )

        risk_config = RiskConfig(
            risk_per_trade_pct=config['trading']['risk']['risk_per_trade_pct'],
            stop_loss_pct=config['trading']['risk']['stop_loss_pct'],
            take_profit_pct=config['trading']['risk']['take_profit_pct'],
            max_daily_loss_pct=config['trading']['risk']['max_daily_loss_pct'],
            max_position_loss_pct=config['trading']['risk']['max_position_loss_pct'],
            max_trades_per_day=config['trading']['risk']['max_trades_per_day'],
            max_open_positions=config['trading']['risk']['max_open_positions'],
            max_trades_per_symbol_per_day=config['trading']['risk']['max_trades_per_symbol_per_day'],
            max_sector_exposure=config['trading']['risk']['max_sector_exposure'],
            max_consecutive_losses=config['trading']['risk']['max_consecutive_losses'],
            min_position_size_pct=config['trading']['risk']['min_position_size_pct'],
            max_position_size_pct=config['trading']['risk']['max_position_size_pct'],
            max_positions=config['trading']['risk']['max_positions'],
            atr_stop_multiplier=config['trading']['risk']['atr_stop_multiplier'],
            atr_target_multiplier=config['trading']['risk']['atr_target_multiplier'],
            trailing_activation_multiplier=config['trading']['risk']['trailing_activation_multiplier'],
            trailing_stop_multiplier=config['trading']['risk']['trailing_stop_multiplier']
        )

        strategy_config = StrategyConfig(
            min_confidence=config['trading']['strategies']['min_confidence'],
            aggregator_min_agreement=config['trading']['strategies']['aggregator_min_agreement'],
            cooldown_minutes=config['trading']['strategies']['cooldown_minutes'],
            stop_loss_cooldown_minutes=config['trading']['strategies']['stop_loss_cooldown_minutes']
        )

        market_hours_config = MarketHoursConfig(
            start=config['trading']['hours']['start'],
            end=config['trading']['hours']['end'],
            timezone=config['trading']['hours']['timezone']
        )

        dashboard_config = DashboardConfig(
            host=config['dashboard']['host'],
            port=int(config['dashboard']['port']),
            auto_open_browser=config['dashboard']['auto_open_browser'],
            api_key=config['dashboard']['api_key'],
            ssl_enabled=config['dashboard']['ssl']['enabled'],
            cert_file=config['dashboard']['ssl'].get('cert_file'),
            key_file=config['dashboard']['ssl'].get('key_file')
        )

        market_indexes = config.get('market_indexes', {})

        # Validate
        warnings = risk_config.validate()
        for warning in warnings:
            logger.warning(warning)

        instance = cls(
            api=api_config,
            risk=risk_config,
            strategies=strategy_config,
            market_hours=market_hours_config,
            dashboard=dashboard_config,
            market_indexes=market_indexes,
            raw_config=config
        )

        logger.info("✅ Configuration loaded and validated successfully")
        return instance

    @staticmethod
    def _expand_env_vars(config: Any) -> Any:
        """Recursively expand ${VAR} and ${VAR:default} in config"""

        def expand_value(value):
            if isinstance(value, str):
                # Match ${VAR} or ${VAR:default}
                pattern = r'\$\{([^}:]+)(?::([^}]+))?\}'

                def replace(match):
                    var_name = match.group(1)
                    default = match.group(2)
                    env_value = os.getenv(var_name, default or '')
                    return env_value

                return re.sub(pattern, replace, value)
            elif isinstance(value, dict):
                return {k: expand_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [expand_value(item) for item in value]
            else:
                return value

        return expand_value(config)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key path (e.g., 'trading.risk.max_positions')
        """
        keys = key.split('.')
        value = self.raw_config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    def get_api_config(self) -> Dict:
        """Get API configuration as dict"""
        return self.api.to_dict()

    def get_risk_config(self) -> Dict:
        """Get risk configuration as dict"""
        return self.risk.to_dict()

    def get_strategy_config(self) -> Dict:
        """Get strategy configuration as dict"""
        return self.strategies.to_dict()

    def get_security_config(self) -> Dict:
        """Get security configuration"""
        return self.get('security', {})

    def to_dict(self) -> Dict:
        """Convert entire config to dictionary"""
        return self.raw_config


# Global config instance (singleton pattern)
_config: Optional[TradingConfig] = None
_config_lock = None


def get_config(reload: bool = False) -> TradingConfig:
    """
    Get global config instance (singleton pattern)

    Args:
        reload: Force reload configuration from disk

    Returns:
        TradingConfig instance
    """
    global _config

    if _config is None or reload:
        _config = TradingConfig.load()

    return _config


def reload_config():
    """Reload configuration from disk"""
    global _config
    _config = TradingConfig.load()
    logger.info("🔄 Configuration reloaded")
    return _config


if __name__ == "__main__":
    # Test configuration loading
    print("Testing configuration loading...")
    config = get_config()
    print(f"✅ Config loaded successfully")
    print(f"   API Key: {config.api.api_key[:10]}..." if config.api.api_key else "   API Key: Not set")
    print(f"   Risk per trade: {config.risk.risk_per_trade_pct:.1%}")
    print(f"   Min confidence: {config.strategies.min_confidence:.1%}")
    print(f"   Max positions: {config.risk.max_positions}")
    print(f"   Market Hours: {config.market_hours.start} - {config.market_hours.end}")
    print(f"   Dashboard Host: {config.dashboard.host}")
