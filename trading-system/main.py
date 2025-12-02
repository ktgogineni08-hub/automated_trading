#!/usr/bin/env python3
"""
Enhanced Trading System - Main Entry Point
Modular architecture with clean separation of concerns
"""

import sys
import os
import time
import logging
import subprocess
import secrets
import argparse
from pathlib import Path
from typing import Optional

# Import our modular components
from utilities.logger import TradingLogger
from utilities.dashboard import DashboardConnector
from zerodha_token_manager import ZerodhaTokenManager
from core.portfolio import UnifiedPortfolio
from core.trading_system import UnifiedTradingSystem
from fno.terminal import FNOTerminal
from fno.strategy_selector import IntelligentFNOStrategySelector
from fno.indices import IndexConfig
from utilities.structured_logger import get_logger, log_function_call

# Initialize logger
logger = get_logger(__name__)


def ensure_correct_directory():
    """Ensure we're running from the correct directory"""
    script_dir = Path(__file__).parent.resolve()
    os.chdir(script_dir)
    logger.info(f"Working directory: {script_dir}")


def setup_zerodha_authentication() -> Optional[object]:
    """
    Setup Zerodha API authentication
    
    Returns:
        KiteConnect instance or None
    """
    logger.info("🔐 Setting up Zerodha Authentication...")
    
    # Load credentials from environment variables
    API_KEY = os.getenv('ZERODHA_API_KEY')
    API_SECRET = os.getenv('ZERODHA_API_SECRET')
    interactive = sys.stdin.isatty()

    # If not in environment, prompt user only when interactive.
    if not API_KEY or not API_SECRET:
        logger.info("ℹ️  No credentials found in environment")

        if interactive:
            response = input("\n🔐 Enter API credentials? (y/n, default=y): ").strip().lower()

            if response != 'n':
                print("\n🔐 Please enter your Zerodha API credentials:")
                API_KEY = input("   API Key: ").strip()
                API_SECRET = input("   API Secret: ").strip()

                if API_KEY and API_SECRET:
                    logger.info("✅ API credentials entered manually")
                else:
                    logger.warning("⚠️  No credentials provided - limited functionality")
            else:
                logger.info("   Continuing without broker connection (limited functionality)")
        else:
            logger.warning(
                "⚠️  Zerodha credentials missing and interactive input unavailable. "
                "Set ZERODHA_API_KEY and ZERODHA_API_SECRET for live trading."
            )
    
    # Authenticate with Zerodha
    if API_KEY and API_SECRET:
        try:
            token_manager = ZerodhaTokenManager(API_KEY, API_SECRET)
            kite = token_manager.get_authenticated_kite()
            
            if kite:
                logger.info("✅ Zerodha authentication successful")
                return kite
            else:
                logger.error("❌ Zerodha authentication failed")
                return None
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
    
    return None


def ensure_dashboard_api_key(interactive: bool = True) -> str:
    """
    Ensure DASHBOARD_API_KEY is set.

    Returns:
        API key string (possibly generated for this session)
    """
    if existing:
        return existing

    def _generate_key() -> str:
        return secrets.token_urlsafe(24)

    if interactive and sys.stdin.isatty():
        print("\n🔐 Dashboard API protection")
        print("The dashboard requires an API key for authenticated access.")
        entered = input("Enter a custom key or press Enter to auto-generate one: ").strip()
        api_key = entered or _generate_key()
        if not entered:
            print(f"✅ Generated temporary dashboard key: {api_key}")
            print("   Tip: export DASHBOARD_API_KEY to reuse this key in future sessions.")
    else:
        api_key = _generate_key()
        logger.info("Generated temporary DASHBOARD_API_KEY for this session.")

    os.environ["DASHBOARD_API_KEY"] = api_key
    return api_key


def display_main_menu():
    """Display main trading type selection menu"""
    print("🎯 ENHANCED TRADING SYSTEM")
    print("=" * 60)
    print("🚀 Modular architecture with professional features")
    print("📊 Dashboard integration with real-time monitoring")
    print("🔧 Enhanced error handling and state management")
    print("=" * 60)
    print("")
    print("Select Trading Type:")
    print("1. 📈 NIFTY 50 Trading (Equities)")
    print("2. 🎯 F&O Trading (Futures & Options)")
    print("3. 🚪 Exit")
    print("=" * 60)


def display_nifty_menu():
    """Display NIFTY 50 trading mode menu"""
    print("\n📈 NIFTY 50 TRADING OPTIONS:")
    print("=" * 40)
    print("1. 📝 Paper Trading (Safe Simulation)")
    print("2. 📊 Backtesting (Historical Analysis)")
    print("3. 🔴 Live Trading (Real Money)")
    print("=" * 40)


def display_fno_menu():
    """Display F&O trading mode menu with index recommendations"""
    print("\n🎯 F&O TRADING OPTIONS:")
    print("=" * 60)
    print("📊 INDEX RECOMMENDATIONS FOR ₹5-10K PROFIT STRATEGY:")
    print("-" * 60)
    
    # Show prioritized indices
    try:
        prioritized = IndexConfig.get_prioritized_indices()
        for i, idx in enumerate(prioritized[:3], 1):  # Show top 3
            char = IndexConfig.get_characteristics(idx)
            if char:
                print(f"{i}. {idx:12s} - Points needed: {char.points_needed_for_profit(5000, 50):.0f}-{char.points_needed_for_profit(10000, 50):.0f} pts")
                print(f"   {'':12s}   Priority #{char.priority} | {char.volatility.replace('_', ' ').title()} volatility")
    except Exception as e:
        logger.warning(f"Could not load index recommendations: {e}")
    
    print("\n⚠️  CORRELATION WARNING:")
    print("   • NEVER trade NIFTY + SENSEX together (95% correlation)")
    print("   • NEVER trade Bank NIFTY + BANKEX together (95% correlation)")
    print("   • Avoid more than 3-4 positions simultaneously")
    print("=" * 60)
    print("\nMODE SELECTION:")
    print("1. 📝 Paper Trading (Safe Simulation)")
    print("2. 📊 Backtesting (Historical Analysis)")
    print("3. 🔴 Live Trading (Real Money)")
    print("=" * 60)


def bootstrap_instruments(kite):
    """
    CRITICAL FIX: Bootstrap instruments before trading

    Returns:
        Dict mapping symbol -> instrument_token
    """
    from data.instruments_service import get_instruments_service

    if not kite:
        logger.warning("⚠️ No Kite connection - running without instruments")
        return {}

    try:
        logger.info("📡 Bootstrapping instruments from Zerodha...")
        instruments_service = get_instruments_service(kite=kite)
        instruments = instruments_service.get_instruments_map('NSE')

        logger.info(f"✅ Loaded {len(instruments)} NSE instruments")
        return instruments
    except Exception as e:
        logger.error(f"❌ Failed to bootstrap instruments: {e}")
        return {}


def run_paper_trading(kite):
    """Run NIFTY 50 paper trading"""
    logger.info("Starting NIFTY 50 Paper Trading...")
    print("📝 PAPER TRADING MODE - Safe simulation!")

    # CRITICAL FIX: Bootstrap instruments
    instruments = bootstrap_instruments(kite)

    # Create trading system
    from data.provider import DataProvider
    data_provider = DataProvider(kite=kite, instruments_map=instruments)
    
    from unified_config import get_config
    config = get_config()
    
    trading_system = UnifiedTradingSystem(
        data_provider=data_provider,
        kite=kite,
        initial_cash=config.get('trading.capital.initial', 1000000),
        trading_mode='paper'
    )
    
    # Run trading
    try:
        trading_system.run_nifty50_trading(interval="5minute", check_interval=30)
    except KeyboardInterrupt:
        logger.info("Trading stopped by user")
        trading_system.portfolio.save_state_to_files()


def run_backtesting(kite):
    """Run NIFTY 50 backtesting"""
    logger.info("Starting NIFTY 50 Backtesting...")
    print("📊 BACKTESTING MODE - Historical analysis!")

    # CRITICAL FIX: Bootstrap instruments
    instruments = bootstrap_instruments(kite)

    # Create trading system
    from data.provider import DataProvider
    data_provider = DataProvider(kite=kite, instruments_map=instruments)
    
    trading_system = UnifiedTradingSystem(
        data_provider=data_provider,
        kite=kite,
        initial_cash=1000000,
        trading_mode='backtest'
    )
    
    # Run backtest
    try:
        trading_system.run_fast_backtest(interval="5minute", days=30)
    except Exception as e:
        logger.exception("Backtesting error")


def run_live_trading(kite):
    """Run NIFTY 50 live trading"""
    logger.info("Starting NIFTY 50 Live Trading...")
    print("🔴 LIVE TRADING MODE - Real money at risk!")

    # Confirmation
    confirm = input("⚠️ Are you sure you want to trade with real money? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print("❌ Live trading cancelled")
        return

    # CRITICAL FIX: Bootstrap instruments
    instruments = bootstrap_instruments(kite)

    # Create portfolio
    portfolio = UnifiedPortfolio(
        initial_cash=1000000,
        kite=kite,
        trading_mode='live',
        silent=False
    )

    # Create trading system
    from data.provider import DataProvider
    data_provider = DataProvider(kite=kite, instruments_map=instruments)
    
    from unified_config import get_config
    config = get_config()

    trading_system = UnifiedTradingSystem(
        data_provider=data_provider,
        kite=kite,
        initial_cash=config.get('trading.capital.initial', 1000000),
        trading_mode='live'
    )
    
    # Run trading
    try:
        trading_system.run_nifty50_trading(interval="5minute", check_interval=30)
    except KeyboardInterrupt:
        logger.info("Trading stopped by user")
        portfolio.save_state_to_files()


def run_fno_trading(kite, mode: str, dashboard: Optional[DashboardConnector] = None):
    """
    Run F&O trading in specified mode
    
    Args:
        kite: KiteConnect instance
        mode: 'paper', 'backtest', or 'live'
        dashboard: Dashboard connector (optional)
    """
    from unified_config import get_config
    config = get_config()

    # Create portfolio
    fno_portfolio = UnifiedPortfolio(
        initial_cash=config.get('trading.capital.initial', 1000000),
        dashboard=dashboard,
        kite=kite,
        trading_mode=mode,
        silent=False
    )
    
    # Load existing state for paper trading
    if mode == 'paper':
        try:
            state_file = Path('state/shared_portfolio_state.json')
            if state_file.exists():
                import json
                with open(state_file, 'r') as f:
                    state_data = json.load(f)
                    if state_data.get('trading_mode') == 'paper':
                        fno_portfolio.cash = state_data.get('cash', 1000000)
                        fno_portfolio.positions = state_data.get('positions', {})
                        print(f"📝 Restored portfolio state!")
                        print(f"💰 Current cash: ₹{fno_portfolio.cash:,.2f}")
                        print(f"📊 Current positions: {len(fno_portfolio.positions)}")
                        
                        # Ask if user wants to reset
                        reset_choice = input("\n💭 Reset portfolio to ₹10,00,000? (yes/no) [no]: ").strip().lower()
                        if reset_choice in ['yes', 'y']:
                            fno_portfolio.initial_cash = 1000000.0
                            fno_portfolio.cash = 1000000.0
                            fno_portfolio.positions = {}
                            fno_portfolio.position_entry_times = {}
                            fno_portfolio.trades_count = 0
                            fno_portfolio.winning_trades = 0
                            fno_portfolio.losing_trades = 0
                            fno_portfolio.total_pnl = 0.0
                            fno_portfolio.best_trade = 0.0
                            fno_portfolio.worst_trade = 0.0
                            fno_portfolio.trades_history = []
                            fno_portfolio.portfolio_history = []
                            fno_portfolio.daily_profit = 0.0
                            for state_path in [
                                Path('state/shared_portfolio_state.json'),
                                Path('state/current_state.json'),
                                Path('state/fno_system_state.json')
                            ]:
                                try:
                                    if state_path.exists():
                                        state_path.unlink()
                                        logger.info(f"🗑️ Removed saved state file: {state_path}")
                                except Exception as exc:
                                    logger.warning(f"⚠️ Could not remove {state_path}: {exc}")
                            fno_portfolio.save_state_to_files()
                            print("✅ Portfolio reset to ₹10,00,000!")
        except Exception as e:
            print(f"⚠️ Could not load previous state: {e}")
    
    # Create and run F&O terminal
    fno_terminal = FNOTerminal(kite=kite, portfolio=fno_portfolio)
    fno_terminal.intelligent_selector = IntelligentFNOStrategySelector(
        kite=kite,
        portfolio=fno_portfolio
    )
    
    try:
        fno_terminal.run()
    except KeyboardInterrupt:
        logger.info("F&O trading stopped by user")
    finally:
        fno_portfolio.save_state_to_files()


def start_dashboard(use_https: bool = True) -> Optional[subprocess.Popen]:
    """
    REFACTOR: Start dashboard using centralized DashboardManager

    Returns:
        Dashboard process if successful, None otherwise
    """
    from infrastructure.dashboard_manager import DashboardManager

    logger.info("📊 Starting Dashboard...")

    # Ensure API key exists for dashboard authentication
    try:
        ensure_dashboard_api_key(interactive=sys.stdin.isatty())
    except Exception as exc:
        logger.warning(f"Could not ensure DASHBOARD_API_KEY: {exc}")

    try:
        manager = DashboardManager()
        base_url = os.environ.get(
            'DASHBOARD_BASE_URL',
            'https://localhost:8080' if use_https else 'http://localhost:8080'
        )
        os.environ['DASHBOARD_BASE_URL'] = base_url
        return manager.start(base_url=base_url, use_https=use_https, open_browser=True)
    except Exception as e:
        logger.error(f"Dashboard failed to start: {e}")
        return None


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Enhanced Trading System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --mode paper              # Start F&O paper trading directly
  python main.py --mode backtest           # Start F&O backtesting
  python main.py --mode live               # Start F&O live trading
  python main.py                           # Show interactive menu
        """
    )
    parser.add_argument(
        '--mode',
        choices=['paper', 'backtest', 'live'],
        help='Trading mode (bypasses interactive menu)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--skip-auth',
        action='store_true',
        help='Skip Zerodha authentication (for paper/backtest modes)'
    )
    return parser.parse_args()



    # Use correlation context for tracking requests
    # with logger.correlation_context() as corr_id:
    #     logger.info("Processing request", request_id=corr_id)

def main():
    """Main entry point"""
    # Parse command line arguments
    args = parse_arguments()

    # Ensure correct directory
    ensure_correct_directory()

    # Setup verbose logging if requested
    if args.verbose:
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(logging.INFO)

    # VALIDATION: Check configuration before proceeding
    # VALIDATION: Check configuration before proceeding
    from core.config_validator import validate_config

    logger.info("🔍 Validating configuration...")
    result = validate_config(mode=args.mode or 'paper', verbose=True)
    
    if not result.is_valid:
        logger.error("❌ Configuration validation failed - cannot proceed")
        print("\n⚠️  Please fix the configuration errors above before running the system.\n")
        return

    logger.info("✅ Configuration validated successfully")

    # Setup Zerodha authentication (skip if requested and in paper/backtest mode)
    kite = None
    if not args.skip_auth or args.mode == 'live':
        kite = setup_zerodha_authentication()
    else:
        logger.info("🔐 Skipping Zerodha authentication (--skip-auth)")

    # If mode specified via CLI, run directly without menu
    if args.mode:
        # Start dashboard
        dashboard = None
        try:
            print("📊 Starting dashboard...")
            dashboard_process = start_dashboard(use_https=(args.mode == 'live'))
            dashboard_url = os.environ.get(
                'DASHBOARD_BASE_URL',
                'https://localhost:8080' if args.mode == 'live' else 'http://localhost:8080'
            )
            time.sleep(2)
            dashboard = DashboardConnector(base_url=dashboard_url, api_key=os.getenv("DASHBOARD_API_KEY"))
            if dashboard.is_connected:
                print("✅ Dashboard connected")
                print(f"📊 Monitor at: {dashboard_url}")
            else:
                print("⚠️ Dashboard connection failed - continuing without dashboard")
                dashboard = None
        except Exception as e:
            logger.warning(f"Dashboard startup failed: {e}")
            dashboard = None

        # Run F&O trading in specified mode
        if args.mode == 'paper':
            print("📝 PAPER TRADING MODE (CLI)")
            run_fno_trading(kite, 'paper', dashboard)
        elif args.mode == 'backtest':
            print("📊 BACKTESTING MODE (CLI)")
            run_fno_trading(kite, 'backtest', dashboard)
        elif args.mode == 'live':
            print("🔴 LIVE TRADING MODE (CLI)")
            print("⚠️  WARNING: Trading with real money!")
            run_fno_trading(kite, 'live', dashboard)
        return

    # Main menu loop (interactive mode)
    while True:
        try:
            display_main_menu()
            trading_type = input("Select trading type (1/2/3): ").strip()
            
            if trading_type == "1":
                # NIFTY 50 Trading
                display_nifty_menu()
                nifty_mode = input("Select NIFTY 50 mode (1/2/3): ").strip()
                
                if nifty_mode == "1":
                    run_paper_trading(kite)
                    break
                elif nifty_mode == "2":
                    run_backtesting(kite)
                    break
                elif nifty_mode == "3":
                    run_live_trading(kite)
                    break
                else:
                    print("❌ Please enter 1, 2, or 3")
                    continue
                    
            elif trading_type == "2":
                # F&O Trading
                display_fno_menu()
                fno_mode = input("Select F&O mode (1/2/3): ").strip()
                
                # Start dashboard (optional)
                dashboard = None
                try:
                    print("📊 Starting dashboard...")
                    dashboard_process = start_dashboard(use_https=(fno_mode == "3"))
                    dashboard_url = os.environ.get(
                        'DASHBOARD_BASE_URL',
                        'https://localhost:8080' if fno_mode == "3" else 'http://localhost:8080'
                    )
                    time.sleep(2)
                    dashboard = DashboardConnector(base_url=dashboard_url, api_key=os.getenv("DASHBOARD_API_KEY"))
                    if dashboard.is_connected:
                        print("✅ Dashboard connected")
                        print(f"📊 Monitor at: {dashboard_url}")
                    else:
                        print("⚠️ Dashboard connection failed - continuing without dashboard")
                        dashboard = None
                except Exception as e:
                    logger.warning(f"Dashboard startup failed: {e}")
                    dashboard = None
                
                # Run F&O trading
                if fno_mode == "1":
                    print("📝 PAPER TRADING MODE")
                    run_fno_trading(kite, 'paper', dashboard)
                    break
                elif fno_mode == "2":
                    print("📊 BACKTESTING MODE")
                    run_fno_trading(kite, 'backtest', dashboard)
                    break
                elif fno_mode == "3":
                    print("🔴 LIVE TRADING MODE")
                    confirm = input("⚠️ Trade with real money? (yes/no): ").strip().lower()
                    if confirm in ['yes', 'y']:
                        run_fno_trading(kite, 'live', dashboard)
                    else:
                        print("❌ Live trading cancelled")
                        continue
                    break
                else:
                    print("❌ Please enter 1, 2, or 3")
                    continue
                    
            elif trading_type == "3":
                print("👋 Exiting trading system. Goodbye!")
                break
            else:
                print("❌ Please enter 1, 2, or 3")
                continue
                
        except KeyboardInterrupt:
            print("\n\n👋 Trading system interrupted. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            print(f"❌ Error: {e}")
            break


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
