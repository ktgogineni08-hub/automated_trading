#!/usr/bin/env python3
"""
Trading System Constants
Centralized configuration constants and magic numbers

This module contains all hardcoded values extracted from the codebase
for better maintainability and configurability.
"""

from typing import Dict, Any
from datetime import time as datetime_time

# =============================================================================
# API CONFIGURATION
# =============================================================================

class APIConfig:
    """API-related constants"""

    # Zerodha API Rate Limits
    MAX_REQUESTS_PER_SECOND = 3
    MAX_REQUESTS_PER_MINUTE = 1000
    MAX_REQUESTS_PER_HOUR = 3000
    MAX_REQUESTS_PER_DAY = 50000

    # API Timeouts
    DEFAULT_REQUEST_TIMEOUT = 30  # seconds
    CONNECTION_TIMEOUT = 10  # seconds
    REQUEST_DELAY = 0.25  # seconds between requests

    # Retry Configuration
    MAX_RETRIES = 3
    RETRY_BACKOFF_FACTOR = 2.0  # exponential backoff

    # Burst Protection
    BURST_SIZE = 5
    BURST_WINDOW = 0.1  # seconds


# =============================================================================
# TRADING CONFIGURATION
# =============================================================================

class TradingConfig:
    """Trading-related constants"""

    # Position Limits
    MAX_TRADES_PER_DAY = 150
    MAX_OPEN_POSITIONS = 20
    MAX_TRADES_PER_SYMBOL_PER_DAY = 8
    MAX_SECTOR_EXPOSURE = 6

    # Risk Management
    MIN_CONFIDENCE = 0.70  # 70% minimum confidence for signals
    MAX_POSITION_SIZE = 0.20  # 20% of portfolio max
    MIN_POSITION_SIZE = 0.10  # 10% of portfolio min
    RISK_PER_TRADE_PCT = 0.02  # 2% risk per trade
    MAX_DAILY_LOSS_PCT = 0.05  # 5% max daily loss

    # Stop Loss / Take Profit
    DEFAULT_STOP_LOSS_PCT = 0.02  # 2%
    DEFAULT_TAKE_PROFIT_PCT = 0.04  # 4%
    ATR_STOP_MULTIPLIER = 2.0
    ATR_TARGET_MULTIPLIER = 3.0
    TRAILING_ACTIVATION_MULTIPLIER = 1.5
    TRAILING_STOP_MULTIPLIER = 0.8

    # Market Hours (IST)
    MARKET_OPEN_TIME = datetime_time(9, 15)  # 9:15 AM
    MARKET_CLOSE_TIME = datetime_time(15, 30)  # 3:30 PM

    # Default Capital
    DEFAULT_INITIAL_CAPITAL = 1000000.0  # 10 lakhs

    # Commission & Slippage
    DEFAULT_COMMISSION = 0.0003  # 0.03%
    DEFAULT_SLIPPAGE = 0.0001  # 0.01%


# =============================================================================
# PERFORMANCE MONITORING
# =============================================================================

class PerformanceConfig:
    """Performance monitoring constants"""

    # Baseline Configuration
    BASELINE_WINDOW_HOURS = 24
    ANOMALY_THRESHOLD_SIGMA = 3.0
    MEMORY_LEAK_THRESHOLD_MB = 100
    SAMPLING_INTERVAL_SECONDS = 60

    # Performance Thresholds
    SLOW_OPERATION_THRESHOLD_MS = 1000  # 1 second
    SLOW_QUERY_THRESHOLD_MS = 100
    HIGH_MEMORY_THRESHOLD_PCT = 85
    HIGH_CPU_THRESHOLD_PCT = 80

    # Cache Configuration
    CACHE_TTL_SECONDS = 60
    CACHE_SIZE_MB = 100

    # Alert Cooldowns
    ALERT_COOLDOWN_SECONDS = 300  # 5 minutes

    # Query Limits
    DEFAULT_QUERY_LIMIT = 1000
    MAX_QUERY_LIMIT = 10000


# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

class DatabaseConfig:
    """Database-related constants"""

    # Connection Pooling
    MIN_POOL_SIZE = 2
    MAX_POOL_SIZE = 10
    CONNECTION_TIMEOUT = 30  # seconds

    # Query Configuration
    DEFAULT_STATEMENT_TIMEOUT = 30  # seconds
    SLOW_QUERY_THRESHOLD = 100  # milliseconds

    # Replication
    MAX_REPLICATION_LAG_SECONDS = 5.0
    REPLICATION_HEALTH_CHECK_INTERVAL = 30  # seconds

    # Performance
    CACHE_SIZE_PAGES = 10000  # ~80MB
    TEMP_BUFFERS = "128MB"
    WORK_MEM = "64MB"
    MAINTENANCE_WORK_MEM = "256MB"

    # Backup
    BACKUP_RETENTION_DAYS = 30
    WAL_RETENTION_HOURS = 48


# =============================================================================
# REDIS CONFIGURATION
# =============================================================================

class RedisConfig:
    """Redis-related constants"""

    # Connection
    DEFAULT_DB = 0
    SOCKET_TIMEOUT = 5  # seconds
    SOCKET_CONNECT_TIMEOUT = 5  # seconds
    HEALTH_CHECK_INTERVAL = 30  # seconds

    # State Management
    STATE_TTL_SECONDS = 86400  # 24 hours
    SESSION_TTL_SECONDS = 300  # 5 minutes
    LOCK_TIMEOUT_SECONDS = 10
    LOCK_BLOCKING_TIMEOUT = 5

    # Heartbeat
    HEARTBEAT_INTERVAL_SECONDS = 60
    SESSION_EXPIRY_SECONDS = 300

    # Cleanup
    STALE_SESSION_MAX_AGE_SECONDS = 300


# =============================================================================
# ALERTING CONFIGURATION
# =============================================================================

class AlertConfig:
    """Alerting-related constants"""

    # Alert Thresholds
    QUOTA_WARNING_THRESHOLD = 0.75  # 75%
    QUOTA_CRITICAL_THRESHOLD = 0.90  # 90%
    QUOTA_DANGER_THRESHOLD = 0.95  # 95%

    # Alert Suppression
    ALERT_SUPPRESSION_WINDOW_SECONDS = 300  # 5 minutes
    MAX_ALERTS_HISTORY = 1000

    # Execution Alerts
    SLOW_EXECUTION_THRESHOLD_MS = 5000  # 5 seconds
    HIGH_SLIPPAGE_THRESHOLD_PCT = 0.5  # 0.5%

    # Data Alerts
    STALE_DATA_THRESHOLD_SECONDS = 300  # 5 minutes

    # Risk Alerts
    POSITION_LIMIT_WARNING_PCT = 0.80  # 80% of limit
    DAILY_LOSS_ALERT_PCT = 0.05  # 5%
    UNREALIZED_LOSS_ALERT_PCT = 0.10  # 10%

    # Pattern Detection
    CONSECUTIVE_LOSSES_THRESHOLD = 5
    WIN_RATE_DEGRADATION_THRESHOLD = 0.15  # 15% drop
    POSITION_CONCENTRATION_THRESHOLD = 0.40  # 40%
    VOLUME_ANOMALY_THRESHOLD = 3.0  # 3x normal
    FLASH_CRASH_THRESHOLD = 0.02  # 2% in 1 minute
    DRAWDOWN_ACCELERATION_THRESHOLD = 0.05  # 5% rapid


# =============================================================================
# BACKTESTING CONFIGURATION
# =============================================================================

class BacktestConfig:
    """Backtesting-related constants"""

    # Parallelization
    DEFAULT_MAX_WORKERS = 4
    USE_PROCESSES = False  # Use threads by default

    # Simulation
    DEFAULT_MONTE_CARLO_SIMULATIONS = 1000
    MONTE_CARLO_VOLATILITY = 0.10  # 10%

    # Caching
    ENABLE_RESULT_CACHING = True

    # Parameter Optimization
    MAX_PARAMETER_COMBINATIONS = 1000
    TOP_N_RESULTS = 5


# =============================================================================
# OBJECT POOLING CONFIGURATION
# =============================================================================

class PoolConfig:
    """Object pooling constants"""

    # Pool Sizes
    TRADE_SIGNAL_POOL_SIZE = 1000
    TRADE_SIGNAL_MIN_SIZE = 50

    ORDER_DATA_POOL_SIZE = 500
    ORDER_DATA_MIN_SIZE = 25

    PRICE_DATA_POOL_SIZE = 2000
    PRICE_DATA_MIN_SIZE = 100

    # Pool Management
    POOL_ACQUISITION_TIMEOUT = 5.0  # seconds
    MAX_OBJECT_REUSE = 10000  # recycle after N uses


# =============================================================================
# ML/AI CONFIGURATION
# =============================================================================

class MLConfig:
    """Machine learning constants"""

    # Model Retraining
    MIN_RETRAINING_INTERVAL_HOURS = 24
    PERFORMANCE_DEGRADATION_THRESHOLD = 0.15  # 15% drop
    DATA_DRIFT_THRESHOLD = 0.10  # 10% distribution shift

    # Model Versioning
    MAX_MODEL_VERSIONS = 10
    MODEL_RETENTION_DAYS = 90

    # Training
    TRAINING_VALIDATION_SPLIT = 0.20  # 20%
    TRAINING_TEST_SPLIT = 0.10  # 10%
    MIN_TRAINING_SAMPLES = 1000

    # Performance
    MODEL_PREDICTION_TIMEOUT_MS = 100
    BATCH_PREDICTION_SIZE = 32


# =============================================================================
# RISK ANALYTICS CONFIGURATION
# =============================================================================

class RiskConfig:
    """Risk analytics constants"""

    # VaR Configuration
    DEFAULT_VAR_CONFIDENCE = 0.95  # 95%
    DEFAULT_VAR_HORIZON_DAYS = 1
    MONTE_CARLO_VAR_SIMULATIONS = 10000

    # Risk-Free Rate (Annual)
    RISK_FREE_RATE = 0.05  # 5%
    EXPECTED_MARKET_RETURN = 0.12  # 12%

    # Stress Test Scenarios
    MARKET_CRASH_SHOCK = -0.20  # -20%
    FLASH_CRASH_SHOCK = -0.05  # -5%
    VOLATILITY_SPIKE_SHOCK = -0.10  # -10%
    LIQUIDITY_CRISIS_SHOCK = -0.15  # -15%
    BLACK_SWAN_SHOCK = -0.30  # -30%


# =============================================================================
# F&O CONFIGURATION
# =============================================================================

class FNOConfig:
    """F&O trading constants"""

    # Lot Sizes
    LOT_SIZES = {
        'NIFTY': 50,
        'BANKNIFTY': 15,
        'FINNIFTY': 40,
        'MIDCPNIFTY': 75,
        'SENSEX': 10,
        'BANKEX': 15,
    }

    # Fallback Spot Prices
    FALLBACK_SPOT_PRICES = {
        'NIFTY': 25000,
        'BANKNIFTY': 53500,
        'FINNIFTY': 19500,
        'MIDCPNIFTY': 13000,
        'SENSEX': 82000,
        'BANKEX': 62000,
    }

    # Option Chain
    OPTION_CHAIN_LIMIT = 150
    OPTION_CHAIN_TIMEOUT = 30  # seconds

    # Target Profit
    MIN_TARGET_PROFIT = 5000  # ₹5,000
    MAX_TARGET_PROFIT = 10000  # ₹10,000


# =============================================================================
# DASHBOARD CONFIGURATION
# =============================================================================

class DashboardConfig:
    """Dashboard-related constants"""

    # Server Configuration
    DEFAULT_PORT = 8080
    DEFAULT_HOST = '0.0.0.0'

    # WebSocket
    WEBSOCKET_PING_INTERVAL = 30  # seconds
    WEBSOCKET_TIMEOUT = 60  # seconds
    MAX_WEBSOCKET_CONNECTIONS = 1000

    # Refresh Intervals
    PORTFOLIO_REFRESH_INTERVAL = 5  # seconds
    POSITIONS_REFRESH_INTERVAL = 5  # seconds
    ALERTS_REFRESH_INTERVAL = 30  # seconds

    # UI Configuration
    MAX_ALERTS_DISPLAY = 10
    MAX_POSITIONS_DISPLAY = 20
    CHART_HISTORY_POINTS = 100


# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

class LogConfig:
    """Logging-related constants"""

    # Log Levels
    DEFAULT_LOG_LEVEL = 'INFO'
    VERBOSE_LOG_LEVEL = 'DEBUG'

    # Log Rotation
    MAX_LOG_SIZE_MB = 50
    LOG_BACKUP_COUNT = 5
    LOG_RETENTION_DAYS = 30

    # Log Format
    DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Structured Logging
    ENABLE_JSON_LOGGING = False
    ENABLE_CORRELATION_IDS = True


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_all_constants() -> Dict[str, Any]:
    """
    Get all constants as a dictionary

    Returns:
        Dictionary of all constants
    """
    constants = {}

    for cls_name in dir():
        cls = globals()[cls_name]
        if isinstance(cls, type) and cls_name.endswith('Config'):
            constants[cls_name] = {}
            for attr in dir(cls):
                if not attr.startswith('_') and attr.isupper():
                    constants[cls_name][attr] = getattr(cls, attr)

    return constants


def print_constants():
    """Print all constants in a readable format"""
    constants = get_all_constants()

    print("\n" + "="*80)
    print("TRADING SYSTEM CONSTANTS")
    print("="*80)

    for config_class, values in constants.items():
        print(f"\n{config_class}:")
        print("-" * 40)
        for key, value in values.items():
            print(f"  {key:.<45} {value}")

    print("\n" + "="*80)


if __name__ == "__main__":
    # Print all constants
    print_constants()

    # Example usage
    print("\nExample Usage:")
    print(f"API max requests/second: {APIConfig.MAX_REQUESTS_PER_SECOND}")
    print(f"Trading max daily loss: {TradingConfig.MAX_DAILY_LOSS_PCT:.1%}")
    print(f"Database pool size: {DatabaseConfig.MIN_POOL_SIZE}-{DatabaseConfig.MAX_POOL_SIZE}")
    print(f"Redis state TTL: {RedisConfig.STATE_TTL_SECONDS}s ({RedisConfig.STATE_TTL_SECONDS/3600:.1f}h)")
