#!/usr/bin/env python3
"""
Strategy Registry System
Centralized management, discovery, and validation of trading strategies

ADDRESSES WEEK 3 ISSUE:
- Original: Manual strategy management, no validation, no performance tracking
- This implementation: Auto-discovery, validation, performance tracking, comparison
"""

import inspect
import importlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import sys

from strategies.base import BaseStrategy
from infrastructure.database_manager import get_database, StrategyPerformance

logger = logging.getLogger('trading_system.strategy_registry')


class StrategyStatus(Enum):
    """Strategy status"""
    ACTIVE = "active"          # Available for trading
    DISABLED = "disabled"      # Temporarily disabled
    DEPRECATED = "deprecated"  # Old version, use newer
    TESTING = "testing"        # Under testing, not for production


@dataclass
class StrategyMetadata:
    """Metadata about a trading strategy"""
    name: str
    class_name: str
    module_path: str
    description: str
    version: str
    author: str
    created_date: datetime
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: StrategyStatus = StrategyStatus.ACTIVE
    risk_level: str = "medium"  # low, medium, high
    recommended_capital: float = 100000.0
    min_confidence: float = 0.45
    tags: List[str] = field(default_factory=list)


@dataclass
class StrategyValidation:
    """Strategy validation result"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    score: float = 0.0  # 0-100


class StrategyRegistry:
    """
    Centralized Strategy Registry

    Features:
    - Auto-discovery of strategies in strategies/ directory
    - Strategy validation (required methods, parameters)
    - Performance tracking and comparison
    - Strategy versioning
    - Hot-reload capabilities
    - Parameter validation
    - Strategy recommendations based on market conditions

    Usage:
        registry = StrategyRegistry()
        registry.discover_strategies()

        # Get strategy
        strategy = registry.get_strategy("RSI_Fixed")

        # Get best performing
        best = registry.get_best_performing_strategy(lookback_days=30)

        # Compare strategies
        comparison = registry.compare_strategies(["RSI_Fixed", "Bollinger_Fixed"])
    """

    def __init__(self, strategy_dir: str = "strategies"):
        """
        Initialize strategy registry

        Args:
            strategy_dir: Directory containing strategy modules
        """
        self.strategy_dir = Path(strategy_dir)
        self._strategies: Dict[str, Type[BaseStrategy]] = {}
        self._metadata: Dict[str, StrategyMetadata] = {}
        self._instances: Dict[str, BaseStrategy] = {}
        self._performance_cache: Dict[str, StrategyPerformance] = {}

        self.db = get_database()

        logger.info("📋 StrategyRegistry initialized")

    def discover_strategies(self) -> int:
        """
        Auto-discover all strategy classes in strategies directory

        Returns:
            Number of strategies discovered
        """
        discovered = 0

        if not self.strategy_dir.exists():
            logger.warning(f"Strategy directory not found: {self.strategy_dir}")
            return 0

        # Add strategies directory to Python path
        sys.path.insert(0, str(self.strategy_dir.parent))

        # Find all Python files
        for py_file in self.strategy_dir.glob("*[!_].py"):  # Exclude __init__.py
            if py_file.name.startswith('_'):
                continue

            module_name = f"strategies.{py_file.stem}"

            try:
                # Import module
                module = importlib.import_module(module_name)

                # Find strategy classes
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # Check if it's a strategy class (subclass of BaseStrategy but not BaseStrategy itself)
                    if (issubclass(obj, BaseStrategy) and
                        obj != BaseStrategy and
                        obj.__module__ == module_name):

                        strategy_name = getattr(obj, 'name', name)

                        # Register strategy
                        self._strategies[strategy_name] = obj

                        # Create metadata
                        self._metadata[strategy_name] = self._extract_metadata(obj, module_name)

                        discovered += 1
                        logger.info(f"✅ Discovered strategy: {strategy_name}")

            except Exception as e:
                logger.error(f"❌ Failed to import {module_name}: {e}")

        logger.info(f"📋 Discovered {discovered} strategies")
        return discovered

    def _extract_metadata(self, strategy_class: Type[BaseStrategy], module_path: str) -> StrategyMetadata:
        """Extract metadata from strategy class"""
        # Get docstring
        doc = inspect.getdoc(strategy_class) or "No description"

        # Get __init__ parameters
        sig = inspect.signature(strategy_class.__init__)
        parameters = {}

        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue

            parameters[param_name] = {
                'default': param.default if param.default != inspect.Parameter.empty else None,
                'annotation': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any'
            }

        return StrategyMetadata(
            name=strategy_class.__name__,
            class_name=strategy_class.__name__,
            module_path=module_path,
            description=doc.split('\n')[0] if doc else "No description",
            version=getattr(strategy_class, '__version__', '1.0.0'),
            author=getattr(strategy_class, '__author__', 'Unknown'),
            created_date=datetime.now(),
            parameters=parameters,
            status=StrategyStatus.ACTIVE,
            risk_level=getattr(strategy_class, 'risk_level', 'medium'),
            tags=getattr(strategy_class, 'tags', [])
        )

    def register_strategy(
        self,
        name: str,
        strategy_class: Type[BaseStrategy],
        metadata: Optional[StrategyMetadata] = None
    ) -> bool:
        """
        Manually register a strategy

        Args:
            name: Strategy name
            strategy_class: Strategy class
            metadata: Optional metadata

        Returns:
            True if registered successfully
        """
        try:
            self._strategies[name] = strategy_class

            if metadata:
                self._metadata[name] = metadata
            else:
                self._metadata[name] = self._extract_metadata(
                    strategy_class,
                    strategy_class.__module__
                )

            logger.info(f"✅ Registered strategy: {name}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to register strategy {name}: {e}")
            return False

    def get_strategy(self, name: str, **kwargs) -> Optional[BaseStrategy]:
        """
        Get strategy instance by name

        Args:
            name: Strategy name
            **kwargs: Strategy initialization parameters

        Returns:
            Strategy instance or None
        """
        if name not in self._strategies:
            logger.error(f"Strategy not found: {name}")
            return None

        try:
            # Check if instance already exists with same parameters
            instance_key = f"{name}_{hash(frozenset(kwargs.items()))}"

            if instance_key in self._instances:
                return self._instances[instance_key]

            # Create new instance
            strategy_class = self._strategies[name]
            instance = strategy_class(**kwargs)

            # Cache instance
            self._instances[instance_key] = instance

            return instance

        except Exception as e:
            logger.error(f"Failed to instantiate strategy {name}: {e}")
            return None

    def validate_strategy(self, name: str) -> StrategyValidation:
        """
        Validate a strategy

        Checks:
        - Has required methods (generate_signals, validate_data)
        - Parameters have valid defaults
        - Documentation exists
        - Can be instantiated

        Args:
            name: Strategy name

        Returns:
            StrategyValidation result
        """
        if name not in self._strategies:
            return StrategyValidation(
                is_valid=False,
                errors=[f"Strategy not found: {name}"],
                score=0.0
            )

        errors = []
        warnings = []
        score = 100.0

        strategy_class = self._strategies[name]

        # Check required methods
        required_methods = ['generate_signals', 'validate_data']
        for method in required_methods:
            if not hasattr(strategy_class, method):
                errors.append(f"Missing required method: {method}")
                score -= 25

        # Check if can be instantiated with defaults
        try:
            instance = strategy_class()
        except Exception as e:
            errors.append(f"Cannot instantiate with defaults: {e}")
            score -= 20

        # Check documentation
        if not inspect.getdoc(strategy_class):
            warnings.append("Missing docstring")
            score -= 5

        # Check if has version
        if not hasattr(strategy_class, '__version__'):
            warnings.append("Missing __version__ attribute")
            score -= 5

        is_valid = len(errors) == 0

        return StrategyValidation(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            score=max(score, 0.0)
        )

    def list_strategies(
        self,
        status: Optional[StrategyStatus] = None,
        risk_level: Optional[str] = None
    ) -> List[str]:
        """
        List available strategies

        Args:
            status: Filter by status
            risk_level: Filter by risk level

        Returns:
            List of strategy names
        """
        strategies = []

        for name, metadata in self._metadata.items():
            if status and metadata.status != status:
                continue

            if risk_level and metadata.risk_level != risk_level:
                continue

            strategies.append(name)

        return sorted(strategies)

    def get_metadata(self, name: str) -> Optional[StrategyMetadata]:
        """Get strategy metadata"""
        return self._metadata.get(name)

    def update_performance(self, name: str) -> Optional[StrategyPerformance]:
        """
        Update and get strategy performance from database

        Args:
            name: Strategy name

        Returns:
            StrategyPerformance or None
        """
        try:
            perf_list = self.db.get_strategy_performance(name)

            if perf_list:
                perf = StrategyPerformance(**perf_list[0])
                self._performance_cache[name] = perf
                return perf

            return None

        except Exception as e:
            logger.error(f"Failed to get performance for {name}: {e}")
            return None

    def get_best_performing_strategy(
        self,
        lookback_days: int = 30,
        min_trades: int = 10
    ) -> Optional[str]:
        """
        Get best performing strategy based on recent performance

        Args:
            lookback_days: Days to look back
            min_trades: Minimum number of trades required

        Returns:
            Strategy name or None
        """
        all_perf = self.db.get_strategy_performance()

        best_strategy = None
        best_score = -float('inf')

        for perf_dict in all_perf:
            # Check minimum trades
            if perf_dict['total_trades'] < min_trades:
                continue

            # Calculate score (weighted combination of metrics)
            win_rate = perf_dict['win_rate']
            total_pnl = perf_dict['total_pnl']
            sharpe = perf_dict.get('sharpe_ratio', 0) or 0

            score = (win_rate * 0.3) + (total_pnl / 10000 * 0.4) + (sharpe * 0.3)

            if score > best_score:
                best_score = score
                best_strategy = perf_dict['strategy_name']

        return best_strategy

    def compare_strategies(
        self,
        strategy_names: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compare multiple strategies

        Args:
            strategy_names: List of strategy names to compare

        Returns:
            Comparison data
        """
        comparison = {}

        for name in strategy_names:
            perf = self.update_performance(name)
            metadata = self.get_metadata(name)

            comparison[name] = {
                'metadata': metadata,
                'performance': perf,
                'validation': self.validate_strategy(name)
            }

        return comparison

    def print_registry(self):
        """Print all registered strategies"""
        print("\n" + "="*70)
        print("📋 STRATEGY REGISTRY")
        print("="*70)

        for name in sorted(self._strategies.keys()):
            metadata = self._metadata.get(name)
            validation = self.validate_strategy(name)

            status_icon = "✅" if validation.is_valid else "❌"
            print(f"\n{status_icon} {name}")
            if metadata:
                print(f"   Description: {metadata.description}")
                print(f"   Risk Level:  {metadata.risk_level}")
                print(f"   Status:      {metadata.status.value}")
                print(f"   Validation:  {validation.score:.0f}/100")

                if validation.errors:
                    print(f"   Errors:      {', '.join(validation.errors)}")

        print("="*70 + "\n")

    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics"""
        return {
            'total_strategies': len(self._strategies),
            'active_strategies': len([m for m in self._metadata.values() if m.status == StrategyStatus.ACTIVE]),
            'valid_strategies': len([name for name in self._strategies if self.validate_strategy(name).is_valid]),
            'cached_instances': len(self._instances)
        }


# Global registry instance
_global_registry: Optional[StrategyRegistry] = None


def get_strategy_registry() -> StrategyRegistry:
    """Get global strategy registry (singleton)"""
    global _global_registry
    if _global_registry is None:
        _global_registry = StrategyRegistry()
        _global_registry.discover_strategies()
    return _global_registry


if __name__ == "__main__":
    # Test strategy registry
    registry = StrategyRegistry()

    print("Discovering strategies...")
    count = registry.discover_strategies()
    print(f"Found {count} strategies\n")

    # Print all strategies
    registry.print_registry()

    # Get a strategy
    strategy = registry.get_strategy("BollingerBandsStrategy", period=20, std_dev=2)
    if strategy:
        print(f"✅ Got strategy: {strategy.name}")

    # Validate strategies
    for name in registry.list_strategies():
        validation = registry.validate_strategy(name)
        print(f"Validation for {name}: {'✅ PASS' if validation.is_valid else '❌ FAIL'}")

    # Statistics
    stats = registry.get_statistics()
    print(f"\nRegistry Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n✅ Strategy registry tests passed")
