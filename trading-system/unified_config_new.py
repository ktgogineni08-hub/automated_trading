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
class TradingConfig:
    """Complete trading system configuration"""
    # Core configurations
    api: APIConfig
    risk: RiskConfig
    strategies: StrategyConfig

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
            # Try legacy JSON config
            legacy_path = Path(__file__).parent / "trading_config.json"
            if legacy_path.exists():
                logger.warning(
                    f"⚠️  Using legacy JSON config. Please migrate to {config_path}"
                )
                return cls._load_legacy_json(legacy_path)

            raise FileNotFoundError(
                f"Config file not found: {config_path}\n"
                f"Please create trading_config.yaml or run migration script"
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

        # Validate
        warnings = risk_config.validate()
        for warning in warnings:
            logger.warning(warning)

        instance = cls(
            api=api_config,
            risk=risk_config,
            strategies=strategy_config,
            raw_config=config
        )

        logger.info("✅ Configuration loaded and validated successfully")
        return instance

    @classmethod
    def _load_legacy_json(cls, json_path: Path) -> 'TradingConfig':
        """Load from legacy JSON format (backward compatibility)"""
        import json

        with open(json_path, 'r') as f:
            legacy_config = json.load(f)

        # Map legacy config to new structure
        api_config = APIConfig(
            api_key=legacy_config.get('api', {}).get('zerodha', {}).get('api_key', ''),
            api_secret=legacy_config.get('api', {}).get('zerodha', {}).get('api_secret', ''),
            token_file=legacy_config.get('api', {}).get('zerodha', {}).get('token_file', ''),
            request_delay=legacy_config.get('api', {}).get('zerodha', {}).get('request_delay', 0.25)
        )

        risk_controls = legacy_config.get('trading', {}).get('risk_controls', {})
        risk_config = RiskConfig(
            risk_per_trade_pct=legacy_config.get('trading', {}).get('risk_per_trade', 0.02),
            stop_loss_pct=0.03,
            take_profit_pct=0.10,
            max_daily_loss_pct=0.05,
            max_position_loss_pct=0.10,
            max_trades_per_day=risk_controls.get('max_trades_per_day', 150),
            max_open_positions=risk_controls.get('max_open_positions', 20),
            max_trades_per_symbol_per_day=risk_controls.get('max_trades_per_symbol_per_day', 8),
            max_sector_exposure=risk_controls.get('max_sector_exposure', 6),
            max_consecutive_losses=3,
            min_position_size_pct=0.10,
            max_position_size_pct=0.25,
            max_positions=legacy_config.get('trading', {}).get('max_positions', 25),
            atr_stop_multiplier=2.0,
            atr_target_multiplier=3.5,
            trailing_activation_multiplier=1.5,
            trailing_stop_multiplier=0.8
        )

        strategy_config = StrategyConfig(
            min_confidence=risk_controls.get('min_confidence', 0.70),
            aggregator_min_agreement=0.4,
            cooldown_minutes=10,
            stop_loss_cooldown_minutes=20
        )

        return cls(
            api=api_config,
            risk=risk_config,
            strategies=strategy_config,
            raw_config=legacy_config
        )

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

        For backward compatibility with old config access patterns
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
        """Get API configuration as dict (backward compatibility)"""
        return self.api.to_dict()

    def get_risk_config(self) -> Dict:
        """Get risk configuration as dict (backward compatibility)"""
        return self.risk.to_dict()

    def get_strategy_config(self) -> Dict:
        """Get strategy configuration as dict (backward compatibility)"""
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


# Backward compatibility: Module-level attributes
# This allows old code like `from config import max_positions` to work
def _init_module_attrs():
    """Initialize module-level attributes for backward compatibility"""
    try:
        config = get_config()

        # Expose commonly used config as module attributes
        globals()['max_positions'] = config.risk.max_positions
        globals()['max_trades_per_day'] = config.risk.max_trades_per_day
        globals()['max_open_positions'] = config.risk.max_open_positions
        globals()['risk_per_trade'] = config.risk.risk_per_trade_pct
        globals()['min_confidence'] = config.strategies.min_confidence

        logger.debug("✅ Module-level config attributes initialized")
    except Exception as e:
        logger.warning(f"⚠️  Could not initialize module attributes: {e}")


# Initialize on import (but don't fail if config doesn't exist)
try:
    _init_module_attrs()
except Exception:
    pass  # Config might not exist yet during migration


if __name__ == "__main__":
    # Test configuration loading
    print("Testing configuration loading...")
    config = get_config()
    print(f"✅ Config loaded successfully")
    print(f"   API Key: {config.api.api_key[:10]}..." if config.api.api_key else "   API Key: Not set")
    print(f"   Risk per trade: {config.risk.risk_per_trade_pct:.1%}")
    print(f"   Min confidence: {config.strategies.min_confidence:.1%}")
    print(f"   Max positions: {config.risk.max_positions}")
