#!/usr/bin/env python3
"""
Safe Trading System Launcher
Integrates all safety checks and robust components
"""

import sys
import os
import logging
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import all new safety modules
from production_safety_validator import validate_production_safety
from api_rate_limiter import wrap_kite_with_rate_limiter
from thread_safe_portfolio import ThreadSafePortfolio
from order_logger import get_order_logger
from robust_trading_loop import RobustTradingLoop
from trading_utils import setup_graceful_shutdown
from trading_config import TradingConfig
from zerodha_token_manager import ZerodhaTokenManager
from advanced_market_manager import AdvancedMarketManager

logger = logging.getLogger('trading_system')


def setup_logging(log_level=logging.INFO):
    """Setup comprehensive logging"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(simple_formatter)
    root_logger.addHandler(console)

    # File handler
    from datetime import datetime
    log_file = log_dir / f"trading_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)

    # Error file handler
    error_file = log_dir / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
    error_handler = logging.FileHandler(error_file)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)

    logger.info("✅ Logging configured")


def initialize_system():
    """Initialize all system components with safety checks"""

    print("\n" + "=" * 80)
    print("🚀 SAFE TRADING SYSTEM LAUNCHER")
    print("=" * 80)

    # Step 1: Load configuration
    print("\n📋 Step 1: Loading Configuration...")
    try:
        config = TradingConfig()
        print("✅ Configuration loaded")
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return None

    # Step 2: Run safety validation
    print("\n🔒 Step 2: Running Safety Validation...")
    if not validate_production_safety(config):
        print("\n❌ SAFETY VALIDATION FAILED!")
        print("   Fix all critical and high priority issues before proceeding.")

        response = input("\nContinue anyway? (type 'YES' to proceed, anything else to exit): ")
        if response.strip().upper() != 'YES':
            print("Exiting for safety.")
            return None
        else:
            print("⚠️  WARNING: Proceeding despite safety validation failures!")

    # Step 3: Initialize API with rate limiting
    print("\n🔌 Step 3: Initializing API Connection...")
    try:
        api_key = os.getenv('ZERODHA_API_KEY')
        api_secret = os.getenv('ZERODHA_API_SECRET')

        if not api_key or not api_secret:
            # Try from config
            api_key, api_secret = config.get_api_credentials()

        if not api_key or not api_secret:
            print("❌ API credentials not found!")
            print("   Set ZERODHA_API_KEY and ZERODHA_API_SECRET environment variables")
            return None

        # Initialize token manager
        token_manager = ZerodhaTokenManager(api_key, api_secret)
        kite = token_manager.get_authenticated_kite()

        # Wrap with rate limiter
        kite_safe = wrap_kite_with_rate_limiter(kite, calls_per_second=3.0)
        print("✅ API connection established (rate-limited)")

    except Exception as e:
        print(f"❌ API initialization failed: {e}")
        return None

    # Step 4: Initialize portfolio (thread-safe)
    print("\n💼 Step 4: Initializing Portfolio...")
    try:
        initial_cash = config.get('trading.default_capital', 1000000)
        max_position_pct = config.get('trading.max_position_pct', 0.20)
        max_positions = config.get('trading.max_positions', 10)

        portfolio = ThreadSafePortfolio(
            initial_cash=initial_cash,
            max_position_pct=max_position_pct,
            max_total_positions=max_positions
        )
        print(f"✅ Portfolio initialized: ₹{initial_cash:,.2f}")

    except Exception as e:
        print(f"❌ Portfolio initialization failed: {e}")
        return None

    # Step 5: Initialize order logger
    print("\n📝 Step 5: Initializing Order Logger...")
    try:
        order_logger = get_order_logger("logs/orders")
        print("✅ Order logger ready")
    except Exception as e:
        print(f"❌ Order logger initialization failed: {e}")
        return None

    # Step 6: Initialize market manager
    print("\n📊 Step 6: Initializing Market Manager...")
    try:
        market_manager = AdvancedMarketManager(config, kite_safe)
        print("✅ Market manager initialized")

        # Check market status
        status = market_manager.get_market_status_display()
        print(f"   Market: {'OPEN' if status['is_market_open'] else 'CLOSED'}")
        print(f"   Time: {status['current_time']}")

    except Exception as e:
        print(f"❌ Market manager initialization failed: {e}")
        return None

    # Step 7: Setup graceful shutdown
    print("\n🛑 Step 7: Setting Up Graceful Shutdown...")
    try:
        def cleanup():
            logger.info("Running cleanup...")
            # Save portfolio state
            try:
                from safe_file_ops import atomic_write_json
                portfolio_state = {
                    'statistics': portfolio.get_statistics(),
                    'positions': {k: v.__dict__ for k, v in portfolio.get_all_positions().items()},
                    'trade_count': len(portfolio.get_trade_history())
                }
                atomic_write_json('state/portfolio_state.json', portfolio_state)
                logger.info("Portfolio state saved")
            except Exception as e:
                logger.error(f"Failed to save portfolio state: {e}")

        shutdown_handler = setup_graceful_shutdown(cleanup)
        print("✅ Graceful shutdown configured")

    except Exception as e:
        print(f"❌ Shutdown handler setup failed: {e}")
        return None

    print("\n" + "=" * 80)
    print("✅ ALL SYSTEMS INITIALIZED SUCCESSFULLY")
    print("=" * 80 + "\n")

    return {
        'config': config,
        'kite': kite_safe,
        'portfolio': portfolio,
        'order_logger': order_logger,
        'market_manager': market_manager,
        'shutdown_handler': shutdown_handler
    }


def run_trading_system():
    """Main function to run trading system"""

    # Setup logging
    setup_logging(log_level=logging.INFO)

    # Initialize all components
    components = initialize_system()

    if components is None:
        print("❌ System initialization failed. Exiting.")
        return 1

    # Extract components
    config = components['config']
    kite = components['kite']
    portfolio = components['portfolio']
    order_logger = components['order_logger']
    market_manager = components['market_manager']
    shutdown_handler = components['shutdown_handler']

    # Create robust trading loop
    print("🔄 Starting Trading Loop...")
    logger.info("=" * 80)
    logger.info("TRADING SYSTEM STARTED")
    logger.info("=" * 80)

    trading_loop = RobustTradingLoop(
        market_manager=market_manager,
        shutdown_handler=shutdown_handler,
        circuit_breaker_threshold=5,
        circuit_breaker_timeout=300.0
    )

    # Define data fetching function
    def fetch_market_data():
        """Fetch market data with rate limiting"""
        try:
            # Get symbols to track
            symbols = ['SBIN', 'INFY', 'RELIANCE']  # Example
            quotes = kite.quote([f'NSE:{s}' for s in symbols])
            return quotes
        except Exception as e:
            logger.error(f"Failed to fetch market data: {e}")
            raise

    # Define strategy execution function
    def execute_trading_strategy(market_data):
        """Execute trading strategy"""
        try:
            logger.info(f"Executing strategy with {len(market_data)} symbols")

            # Your trading logic here
            # This is a placeholder - implement your actual strategy

            # Example: Log portfolio status
            stats = portfolio.get_statistics()
            logger.info(f"Portfolio: Cash=₹{stats['cash']:,.2f}, Positions={stats['position_count']}")

        except Exception as e:
            logger.error(f"Strategy execution failed: {e}", exc_info=True)
            raise

    # Run the trading loop
    try:
        trading_loop.run(
            fetch_data_func=fetch_market_data,
            execute_strategy_func=execute_trading_strategy,
            iteration_delay=60.0  # 60 seconds between iterations
        )
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.critical(f"Trading loop crashed: {e}", exc_info=True)
        return 1

    # Print final statistics
    print("\n" + "=" * 80)
    print("📊 FINAL STATISTICS")
    print("=" * 80)

    loop_stats = trading_loop.get_statistics()
    for key, value in loop_stats.items():
        print(f"{key}: {value}")

    portfolio_stats = portfolio.get_statistics()
    print(f"\nPortfolio:")
    for key, value in portfolio_stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:,.2f}")
        else:
            print(f"  {key}: {value}")

    print("=" * 80)
    print("✅ SYSTEM SHUTDOWN COMPLETE")
    print("=" * 80 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(run_trading_system())
