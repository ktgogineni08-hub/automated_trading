"""
FNO (Futures & Options) Trading Module

Complete F&O trading system including:
- Index characteristics and configuration
- Option contracts and chains
- Data providers for options
- Trading strategies (Straddle, Iron Condor, Strangle, Butterfly)
- Broker integration with margin management
- Advanced analytics (IV, Greeks, ML predictions)
- Strategy selection based on market conditions
- Interactive terminal for F&O trading
"""

# Index Management
from fno.indices import (
    IndexCharacteristics,
    IndexConfig,
    FNOIndex,
    DynamicFNOIndices
)

# Options
from fno.options import (
    OptionContract,
    OptionChain
)

# Data Provider
from fno.data_provider import FNODataProvider

# Strategies
from fno.strategies import (
    FNOStrategy,
    StraddleStrategy,
    IronCondorStrategy
)

# Broker
from fno.broker import (
    FNOBroker,
    ImpliedVolatilityAnalyzer
)

# Analytics
from fno.analytics import (
    FNOAnalytics,
    StrikePriceOptimizer,
    ExpiryDateEvaluator,
    FNOMachineLearning,
    FNOBenchmarkTracker,
    FNOBacktester
)

# Strategy Selection
from fno.strategy_selector import IntelligentFNOStrategySelector

# Terminal
from fno.terminal import FNOTerminal

__all__ = [
    # Indices
    'IndexCharacteristics',
    'IndexConfig',
    'FNOIndex',
    'DynamicFNOIndices',
    # Options
    'OptionContract',
    'OptionChain',
    # Data
    'FNODataProvider',
    # Strategies
    'FNOStrategy',
    'StraddleStrategy',
    'IronCondorStrategy',
    # Broker
    'FNOBroker',
    # Analytics
    'FNOAnalytics',
    'ImpliedVolatilityAnalyzer',
    'StrikePriceOptimizer',
    'ExpiryDateEvaluator',
    'FNOMachineLearning',
    'FNOBenchmarkTracker',
    'FNOBacktester',
    # Selection
    'IntelligentFNOStrategySelector',
    # Terminal
    'FNOTerminal',
]
