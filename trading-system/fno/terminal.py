#!/usr/bin/env python3
"""
FNO Interactive Terminal
Command-line interface for F&O trading operations
"""

from typing import Dict, Optional, TYPE_CHECKING, List
from datetime import datetime, timedelta
import time
import logging
import os
from pathlib import Path

from kiteconnect import KiteConnect

from fno.options import OptionChain
from fno.data_provider import FNODataProvider
from fno.strategy_selector import IntelligentFNOStrategySelector
from fno.broker import FNOBroker
from utilities.structured_logger import get_logger, log_function_call
from fno.analytics import (
    StrikePriceOptimizer,
    ExpiryDateEvaluator,
)
from fno.analytics import (
    FNOMachineLearning,
    FNOBenchmarkTracker,
    FNOBacktester,
)
from fno.broker import ImpliedVolatilityAnalyzer
from fno.strategies import StraddleStrategy, IronCondorStrategy
from fno.indices import IndexConfig
from input_validator import get_validated_int, get_validated_float
from utilities.market_hours import MarketHoursManager

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from core.portfolio import UnifiedPortfolio

logger = get_logger(__name__)


class FNOTerminal:
    """Terminal interface for F&O trading"""

    def __init__(self, kite: KiteConnect = None, portfolio: Optional["UnifiedPortfolio"] = None):
        self.fno_broker = FNOBroker()
        self.data_provider = FNODataProvider(kite=kite)
        self.portfolio = portfolio or UnifiedPortfolio(initial_cash=1000000, trading_mode='paper')
        self.strategies = {
            'straddle': StraddleStrategy(),
            'iron_condor': IronCondorStrategy()
        }

        # Initialize market hours manager
        self.market_hours = MarketHoursManager()

        # Enable auto-adjustment features
        self.auto_adjustment_enabled = True
        self.auto_stop_executed_today = False
        self._last_fno_trading_day = None
        self.analyzer = ImpliedVolatilityAnalyzer()
        self.optimizer = StrikePriceOptimizer()
        self.expiry_evaluator = ExpiryDateEvaluator()
        self.ml_predictor = FNOMachineLearning()
        self.benchmark_tracker = FNOBenchmarkTracker()
        self.backtester = FNOBacktester()
        self.intelligent_selector = IntelligentFNOStrategySelector(kite=kite, portfolio=self.portfolio)

        # Automated paper trading configuration
        self.auto_paper_trading_enabled = (self.portfolio.trading_mode == 'paper')
        self.auto_trade_confidence_threshold = 0.6  # Minimum confidence required to auto-trade
        self.auto_trade_cooldown = timedelta(minutes=15)  # Avoid rapid-fire trades on same index
        self._last_auto_trade: Dict[str, datetime] = {}
        self._emotional_bias_memory: Dict[str, float] = {}

    def _reset_portfolio_state(self, clear_saved_state: bool = True) -> None:
        """Reset in-memory portfolio and optionally remove persisted state files."""
        initial_cash = getattr(self.portfolio, 'initial_cash', 1000000.0)
        self.portfolio.initial_cash = initial_cash
        self.portfolio.cash = initial_cash
        self.portfolio.positions.clear()
        self.portfolio.position_entry_times.clear()
        self.portfolio.trades_count = 0
        self.portfolio.winning_trades = 0
        self.portfolio.losing_trades = 0
        self.portfolio.total_pnl = 0.0
        self.portfolio.best_trade = 0.0
        self.portfolio.worst_trade = 0.0
        self.portfolio.trades_history.clear()
        self.portfolio.portfolio_history.clear()
        self.portfolio.daily_profit = 0.0

        self._last_auto_trade.clear()
        self._emotional_bias_memory.clear()

        if clear_saved_state:
            for path in [
                Path('state/shared_portfolio_state.json'),
                Path('state/current_state.json'),
                Path('state/fno_system_state.json')
            ]:
                try:
                    if path.exists():
                        path.unlink()
                        logger.info(f"🗑️ Removed saved F&O state file: {path}")
                except Exception as exc:
                    logger.warning(f"⚠️ Could not remove state file {path}: {exc}")
    def display_menu(self):
        """Display F&O trading menu"""
        print("\n" + "="*60)
        print("🎯 F&O (FUTURES & OPTIONS) TRADING SYSTEM")
        print("="*60)
        print("📈 Major Indices:")
        available_indices = self.data_provider.get_available_indices()
        for symbol, index in available_indices.items():
            print(f"   {symbol}: {index.name} (Lot: {index.lot_size})")

        print("\n🤖 Intelligent Strategies (Auto-Selected):")
        print("   1. Auto Strategy Selection (AI-Powered)")
        print("   2. 🔄 Continuous F&O Monitoring (Auto Trading)")
        print("   3. Market Analysis & Strategy Recommendation")

        print("\n📊 Manual Strategies:")
        print("   4. Straddle (ATM Call + Put)")
        print("   5. Iron Condor (OTM Call/Put Spreads)")
        print("   6. Strangle (OTM Call + Put)")
        print("   7. Butterfly Spreads (Call/Put)")
        print("   8. Covered Call")
        print("   9. Protective Put")

        print("\n🔧 Tools:")
        print("   10. Option Chain Analysis")
        print("   11. Greeks Calculator")
        print("   12. Implied Volatility Analysis")
        print("   13. Backtesting")
        print("   14. Performance Report")

        print("\n⚙️ Settings:")
        print("   15. Risk Management")
        print("   16. Position Sizing")
        print("   17. 🔄 Reset Portfolio to ₹10,00,000")

        print("\n🧪 Utilities:")
        print("   18. Quick Single Scan (Manual Review)")

        print("\n❌ Exit F&O System")
        print("="*60)

    def run_option_chain_analysis(self):
        """Run option chain analysis"""
        print("\n📊 OPTION CHAIN ANALYSIS")
        print("-" * 40)

        # Select index
        print("Available indices:")
        available_indices = self.data_provider.get_available_indices()
        indices_list = list(available_indices.items())
        for i, (symbol, index) in enumerate(indices_list, 1):
            print(f"   {i}. {symbol} - {index.name}")

        try:
            choice = get_validated_int(
                f"Select index (1-{len(indices_list)}): ",
                min_val=1,
                max_val=len(indices_list)
            )

            index_symbol = indices_list[choice - 1][0]
            print(f"🔍 Analyzing {index_symbol} option chain...")

            # Fetch option chain
            chain = self.data_provider.fetch_option_chain(index_symbol)

            if not chain:
                print("❌ Failed to fetch option chain")
                return

            # Display analysis
            print(f"\n📈 {index_symbol} Option Chain Analysis:")
            print(f"   • Spot Price: ₹{chain.spot_price:,.2f}")
            print(f"   • Total Strikes: {len(chain.calls) + len(chain.puts)}")
            print(f"   • ATM Strike: ₹{chain.get_atm_strike():,.0f}")

            # High OI strikes
            high_oi = chain.get_high_oi_strikes(3)
            print("🔥 High Open Interest Strikes:")
            for strike, oi in high_oi:
                print(f"   • ₹{strike:,.0f}: {oi:,}")

            # Max pain
            max_pain = chain.calculate_max_pain()
            print(f"💀 Max Pain Point: ₹{max_pain:,.0f}")

            # Strategy recommendations
            print("🎯 Strategy Recommendations:")
            for strategy_name, strategy in self.strategies.items():
                analysis = strategy.analyze_option_chain(chain)
                if analysis.get('confidence', 0) > 0.5:
                    print(f"   • {strategy_name.upper()}: {analysis['confidence']:.1%} confidence")

        except Exception as e:
            print(f"❌ Error: {e}")

    def run_live_trading(self):
        """Run live F&O trading"""
        # Check market hours before starting
        can_trade, reason = self.market_hours.can_trade()
        if not can_trade:
            print(f"🚫 Live trading cannot start: {reason}")
            print("💡 Live trading is only allowed during market hours (9:15 AM - 3:30 PM, weekdays)")
            return

        print("\n🔴 LIVE F&O TRADING MODE")
        print("-" * 40)
        print("⚠️  WARNING: This will execute real F&O trades!")
        print("⚠️  You can lose significant money!")

        confirm = input("Type 'CONFIRM' to proceed with real trading: ").strip().upper()
        if confirm != 'CONFIRM':
            print("❌ Live trading cancelled")
            return

        print("🚀 Starting F&O Live Trading...")
        print("💰 Available Margin: ₹{self.fno_broker.available_margin:,.2f}")

        # CRITICAL: Sync existing positions from Kite broker on startup
        print("\n🔄 Syncing positions from Kite broker...")
        sync_result = self.portfolio.sync_positions_from_kite()
        if sync_result.get('total_positions', 0) > 0:
            print(f"✅ Found {sync_result['total_positions']} existing positions in broker account")
            if sync_result.get('added'):
                print(f"   ➕ Added: {', '.join(sync_result['added'])}")
            if sync_result.get('updated'):
                print(f"   🔄 Updated: {', '.join(sync_result['updated'])}")
        else:
            print("📊 No existing positions found in broker account")

        # CRITICAL FIX: Main trading loop with safety limits
        max_scans = 500  # Safety limit (500 scans * 5min = ~41 hours max)
        scan_count = 0
        last_successful_trade_time = time.time()
        max_idle_time = 7200  # 2 hours without trades - possible system issue

        try:
            while scan_count < max_scans:
                scan_count += 1

                # Check market hours on each iteration
                can_trade, reason = self.market_hours.can_trade()
                if not can_trade:
                    print(f"🔒 Trading session ended: {reason}")

                    # AUTOMATIC ARCHIVAL: Save trades and positions at market close
                    if "POST-MARKET" in reason or "3:30 PM" in reason:
                        self._perform_end_of_day_archival()

                    break

                # CRITICAL FIX: Safety check - if no trades for 2 hours during market, investigate
                if scan_count > 10 and time.time() - last_successful_trade_time > max_idle_time:
                    logger.warning(
                        f"⚠️ No trades for {max_idle_time/3600:.1f} hours - possible system issue"
                    )
                    user_choice = input("Continue scanning? (y/n): ").strip().lower()
                    if user_choice != 'y':
                        break

                print("\n🔍 Scanning for F&O opportunities...")

                # Get available indices
                available_indices = self.data_provider.get_available_indices()

                # Prioritize indices for ₹5-10k profit strategy
                prioritized_order = IndexConfig.get_prioritized_indices()
                indices_to_scan = []

                # First add prioritized indices that are available
                for symbol in prioritized_order:
                    if symbol in available_indices:
                        indices_to_scan.append(symbol)

                # Then add any remaining indices
                for symbol in available_indices.keys():
                    if symbol not in indices_to_scan:
                        indices_to_scan.append(symbol)

                logger.info(f"📊 Scanning {len(indices_to_scan)} indices in priority order: {', '.join(indices_to_scan[:3])}...")

                # Scan indices in priority order
                for index_symbol in indices_to_scan:
                    try:
                        chain = self.data_provider.fetch_option_chain(index_symbol)
                        if not chain:
                            continue

                        # Analyze each strategy
                        for strategy_name, strategy in self.strategies.items():
                            analysis = strategy.analyze_option_chain(chain)

                            strategy_confidence = analysis.get('confidence', 0)
                            # Get index confidence from indices provider
                            index_info = self.data_provider.get_available_indices().get(index_symbol)
                            if index_info and hasattr(self.data_provider, 'indices_provider'):
                                index_confidence = self.data_provider.indices_provider._calculate_profit_confidence(index_symbol, index_info)
                            else:
                                index_confidence = 0.5  # Default confidence
                            combined_confidence = (strategy_confidence * 0.7) + (index_confidence * 0.3)

                            if combined_confidence > 0.65:  # High combined confidence threshold
                                # Get index characteristics for display
                                index_info = available_indices.get(index_symbol)
                                char = IndexConfig.get_characteristics(index_symbol)

                                print(f"🎯 {strategy_name.upper()} opportunity on {index_symbol}:")
                                print(f"   • Strategy Confidence: {strategy_confidence:.1%}")
                                print(f"   • Index Confidence: {index_confidence:.1%}")
                                print(f"   • Combined Confidence: {combined_confidence:.1%}")
                                print(f"   • Potential P&L: ₹{analysis.get('max_profit', 0):.0f}")

                                # Show index-specific info for ₹5-10k strategy
                                if char and index_info:
                                    points_5k = char.points_needed_for_profit(5000, index_info.lot_size)
                                    points_10k = char.points_needed_for_profit(10000, index_info.lot_size)
                                    time_est = char.achievable_in_timeframe(points_5k)
                                    print(f"   • Index Priority: #{char.priority} for ₹5-10k strategy")
                                    print(f"   • Points for ₹5k: {points_5k:.0f} pts ({time_est})")
                                    print(f"   • Points for ₹10k: {points_10k:.0f} pts")
                                    print(f"   • Volatility: {char.volatility.replace('_', ' ').title()}")

                                # Only proceed if we have very high confidence
                                if combined_confidence > 0.75:
                                    print(f"   ⭐ EXCEPTIONAL OPPORTUNITY - Auto-executing")
                                else:
                                    print(f"   🎯 HIGH CONFIDENCE - Recommended")
                            elif combined_confidence > 0.50:
                                print(f"   ⚪ {index_symbol}: {strategy_name} @ {combined_confidence:.1%} (moderate confidence)")
                            else:
                                print(f"   ❌ {index_symbol}: {strategy_name} @ {combined_confidence:.1%} (low confidence - skipped)")
                                continue  # Skip low confidence opportunities

                            # Ask for confirmation only for high confidence trades
                            if combined_confidence > 0.65:
                                trade = input(f"Execute {strategy_name} trade? (y/N): ").strip().lower()
                                if trade == 'y':
                                    self._execute_strategy(chain, strategy_name, analysis)

                    except Exception as e:
                        logger.error(f"Error analyzing {index_symbol}: {e}")
                        continue

                print("⏰ Next scan in 30 seconds...")
                time.sleep(30)

        except KeyboardInterrupt:
            print("🛑 F&O trading stopped by user")

    def _execute_strategy(self, chain: OptionChain, strategy_name: str, analysis: Dict):
        """Execute F&O strategy"""
        try:
            if strategy_name == 'straddle':
                # Execute straddle
                call_option = analysis.get('call_option')
                put_option = analysis.get('put_option')

                if call_option and put_option:
                    print(f"📈 Executing Straddle on {chain.underlying}:")
                    print(f"   • Strike: ₹{analysis.get('strike'):,}")
                    print(f"   • Call: {call_option.symbol} @ ₹{call_option.last_price:.2f}")
                    print(f"   • Put: {put_option.symbol} @ ₹{put_option.last_price:.2f}")
                    print(f"   • Total Premium: ₹{analysis.get('total_premium'):.2f}")
                    print(f"   • Breakeven: ₹{analysis.get('breakeven_lower'):.0f} - ₹{analysis.get('breakeven_upper'):.0f}")

                    # For demo purposes, just log the trade
                    trade_record = {
                        'timestamp': datetime.now().isoformat(),
                        'strategy': 'straddle',
                        'index': chain.underlying,
                        'strike': analysis.get('strike'),
                        'call_option': call_option.symbol,
                        'put_option': put_option.symbol,
                        'premium': analysis.get('total_premium'),
                        'breakeven_upper': analysis.get('breakeven_upper'),
                        'breakeven_lower': analysis.get('breakeven_lower'),
                        'confidence': analysis.get('confidence', 0.0)
                    }
                    self.benchmark_tracker.log_trade(trade_record)
                    print("✅ Straddle trade logged successfully!")

            elif strategy_name == 'iron_condor':
                # Execute iron condor
                sell_call = analysis.get('sell_call')
                buy_call = analysis.get('buy_call')
                sell_put = analysis.get('sell_put')
                buy_put = analysis.get('buy_put')

                if all([sell_call, buy_call, sell_put, buy_put]):
                    print(f"📊 Executing Iron Condor on {chain.underlying}:")
                    print(f"   • Sell Call: {sell_call.symbol} @ ₹{sell_call.last_price:.2f}")
                    print(f"   • Buy Call: {buy_call.symbol} @ ₹{buy_call.last_price:.2f}")
                    print(f"   • Sell Put: {sell_put.symbol} @ ₹{sell_put.last_price:.2f}")
                    print(f"   • Buy Put: {buy_put.symbol} @ ₹{buy_put.last_price:.2f}")
                    print(f"   • Net Credit: ₹{analysis.get('net_credit'):.2f}")
                    print(f"   • Max Profit: ₹{analysis.get('max_profit'):.2f}")
                    print(f"   • Max Loss: ₹{analysis.get('max_loss'):.2f}")

                    # For demo purposes, just log the trade
                    trade_record = {
                        'timestamp': datetime.now().isoformat(),
                        'strategy': 'iron_condor',
                        'index': chain.underlying,
                        'sell_call_strike': analysis.get('sell_call_strike'),
                        'buy_call_strike': analysis.get('buy_call_strike'),
                        'sell_put_strike': analysis.get('sell_put_strike'),
                        'buy_put_strike': analysis.get('buy_put_strike'),
                        'net_credit': analysis.get('net_credit'),
                        'max_profit': analysis.get('max_profit'),
                        'max_loss': analysis.get('max_loss'),
                        'confidence': analysis.get('confidence', 0.0)
                    }
                    self.benchmark_tracker.log_trade(trade_record)
                    print("✅ Iron Condor trade logged successfully!")

        except Exception as e:
            logger.error(f"Error executing strategy: {e}")
            print(f"❌ Error executing strategy: {e}")

    def run_auto_strategy_selection(self):
        """Evaluate prioritized indices and present top actionable strategy."""
        print("\n🤖 AUTO STRATEGY SELECTION")
        print("-" * 40)

        available = self.data_provider.get_available_indices()
        if not available:
            print("⚠️ No indices available from data provider." )
            return

        candidates = [sym for sym in IndexConfig.get_prioritized_indices() if sym in available]
        if not candidates:
            candidates = list(available.keys())

        best = None
        for symbol in candidates:
            analysis = self.intelligent_selector.analyze_market_conditions(symbol)
            if analysis.get('error'):
                continue
            recommendation = analysis.get('strategy_recommendation', {})
            confidence = recommendation.get('confidence', 0.0)
            if best is None or confidence > best[0]:
                best = (confidence, symbol, analysis)

        if not best:
            print("⚠️ Unable to compute strategy recommendations right now.")
            return

        confidence, symbol, analysis = best
        self._print_strategy_summary(symbol, analysis)
        self._auto_execute_paper_trade(symbol, analysis)

    def run_market_analysis(self):
        """Deep-dive market analysis for a selected index."""
        indices = list(self.data_provider.get_available_indices().keys())
        if not indices:
            print("⚠️ No indices available. Try refreshing the dashboard.")
            return

        print("\n🧭 MARKET ANALYSIS & RECOMMENDATION")
        print("-" * 40)
        for idx, symbol in enumerate(indices, 1):
            print(f"   {idx}. {symbol}")

        selection = get_validated_int(f"Select index (1-{len(indices)}): ", 1, len(indices))
        symbol = indices[selection - 1]
        analysis = self.intelligent_selector.analyze_market_conditions(symbol)
        if analysis.get('error'):
            print(f"❌ Failed to analyze {symbol}: {analysis['error']}")
            return

        self._print_strategy_summary(symbol, analysis, verbose=True)

    def run_continuous_monitoring(self):
        """Run continuous F&O monitoring with automated strategy execution."""
        print("\n🔄 CONTINUOUS F&O MONITORING (AUTO TRADING)")
        print("=" * 80)
        print("🤖 AI-powered monitoring of prioritized indices with auto execution")
        print("📊 Restores portfolio state and saves progress every iteration")
        print("⏸️ Press Ctrl+C at any time to stop safely")
        print("=" * 80)

        can_trade, reason = self.market_hours.can_trade()
        if can_trade:
            print(f"\n✅ {reason}")
        else:
            print(f"\n⚠️ {reason}")
            time_to_open = self.market_hours.time_until_market_open()
            if time_to_open:
                print(f"ℹ️  {time_to_open}")

            # FIXED: Stop system when markets are closed (user request)
            if "POST-MARKET" in reason:
                print("🛑 Markets have closed for the day.")
                print("📦 Performing end-of-day archival...")

                # CRITICAL: Call archival BEFORE returning
                self._perform_end_of_day_archival()

                print("   • Restart tomorrow during market hours (9:15 AM - 3:30 PM)")
                return

            # If pre-market, allow user to choose
            print("   • System can monitor signals but cannot execute trades until market opens.")
            continue_choice = input("Continue monitoring? (y/n) [n]: ").strip().lower()
            if continue_choice not in ['y', 'yes']:
                print("👋 Exiting. Restart during market hours to trade.")
                return

        if self.portfolio.positions:
            print("\n📂 Existing portfolio state detected:")
            print(f"   • Positions: {len(self.portfolio.positions)}")
            print(f"   • Cash: ₹{self.portfolio.cash:,.2f}")
            resume_choice = input("Resume with existing positions? (y/n) [y]: ").strip().lower()
            if resume_choice in ['n', 'no']:
                self._reset_portfolio_state(clear_saved_state=True)
                print("✅ Portfolio reset to initial cash. Starting fresh session.")
        else:
            # Ensure shared state files don't linger on a fresh start
            self._reset_portfolio_state(clear_saved_state=False)

        try:
            min_confidence = get_validated_float(
                "Minimum confidence threshold (%) [60]: ",
                min_val=0.0,
                max_val=100.0,
                default=60.0
            ) / 100
            check_interval = get_validated_int(
                "Check interval in seconds [300] (min 30): ",
                min_val=30,
                max_val=3600,
                default=300
            )
            max_positions = get_validated_int(
                "Maximum concurrent F&O positions [5]: ",
                min_val=1,
                max_val=20,
                default=5
            )
            capital_per_trade = get_validated_float(
                "Capital per trade (₹) [200000]: ",
                min_val=10000.0,
                max_val=100000000.0,
                default=200000.0
            )
        except (KeyboardInterrupt, EOFError):
            print("\n⚠️ Configuration input cancelled. Using default values.")
            min_confidence = 0.60
            check_interval = 300
            max_positions = 5
            capital_per_trade = 200000.0

        print("\n📋 Monitoring configuration:")
        print(f"   • Minimum confidence: {min_confidence:.0%}")
        print(f"   • Check interval: {check_interval}s")
        print(f"   • Max positions: {max_positions}")
        print(f"   • Capital per trade: ₹{capital_per_trade:,.0f}")
        print("=" * 80)

        iteration = 0
        try:
            while True:
                iteration += 1
                self.iteration = iteration
                now_ist = datetime.now(self.market_hours.ist)
                print(f"\n🔍 Iteration {iteration} — {now_ist.strftime('%Y-%m-%d %H:%M:%S')} IST")
                print("-" * 70)

                if self.portfolio.dashboard:
                    try:
                        self.portfolio.dashboard.send_system_status(True, iteration, "scanning")
                    except Exception as exc:
                        logger.debug(f"Dashboard status update failed: {exc}")

                current_prices: Dict[str, float] = {}
                executed_trades: List[Dict[str, any]] = []
                if self.portfolio.positions:
                    symbols = list(self.portfolio.positions.keys())
                    try:
                        current_prices = self.data_provider.get_current_option_prices(symbols)
                    except Exception as exc:
                        logger.warning(f"⚠️ Failed to fetch position quotes: {exc}")
                        current_prices = {}

                    position_analysis = self.portfolio.monitor_positions(current_prices)
                    exit_results = self.portfolio.execute_position_exits(position_analysis)
                    if exit_results:
                        print("🔄 Executed exits:")
                        for result in exit_results:
                            emoji = "✅" if result['pnl'] >= 0 else "❌"
                            print(
                                f"   {emoji} {result['symbol']}: {result['exit_reason']} "
                                f"| P&L ₹{result['pnl']:,.2f} ({result['pnl_percent']:+.1f}%)"
                            )

                open_positions = len(self.portfolio.positions)
                if open_positions >= max_positions:
                    print(f"📊 Positions: {open_positions}/{max_positions} (max reached)")
                    print("⏳ Waiting for exits before opening new trades.")
                else:
                    available_slots = max_positions - open_positions
                    prioritized = IndexConfig.get_prioritized_indices()
                    available_indices = self.data_provider.get_available_indices()
                    candidates = [sym for sym in prioritized if sym in available_indices]
                    if not candidates:
                        candidates = list(available_indices.keys())

                    signals_executed = 0
                    for symbol in candidates:
                        if len(self.portfolio.positions) >= max_positions:
                            break

                        analysis = self.intelligent_selector.analyze_market_conditions(symbol)
                        if analysis.get('error'):
                            logger.debug(f"{symbol} analysis error: {analysis['error']}")
                            continue

                        recommendation = analysis.get('strategy_recommendation', {}) or {}
                        confidence = float(recommendation.get('confidence', 0.0))
                        if confidence < min_confidence:
                            logger.debug(
                                f"{symbol} skipped — confidence {confidence:.2f} below threshold {min_confidence:.2f}"
                            )
                            continue

                        capital_to_use = min(capital_per_trade, max(self.portfolio.cash, 0.0))
                        if capital_to_use <= 0:
                            print("⚠️ Insufficient cash available for new trades. Waiting for exits.")
                            break

                        result = self.intelligent_selector.execute_optimal_strategy(
                            symbol,
                            capital_to_use,
                            self.portfolio
                        )

                        if result.get('success'):
                            strategy_name = result.get('strategy', recommendation.get('strategy', 'unknown')).replace('_', ' ').title()
                            lots = result.get('lots', 0)
                            max_profit = result.get('max_profit')
                            max_loss = result.get('max_loss')
                            print(f"🎯 Executed {strategy_name} on {symbol} — lots: {lots}, risk ₹{max_loss:,.0f}, reward ₹{max_profit:,.0f}")
                            executed_trades.append({
                                'symbol': symbol,
                                'strategy': strategy_name,
                                'lots': lots,
                                'max_profit': max_profit,
                                'max_loss': max_loss
                            })
                            signals_executed += 1
                            time.sleep(1)  # brief pause to respect rate limits
                        else:
                            error_msg = result.get('error', 'unknown error')
                            if error_msg == 'net_credit_nonpositive':
                                print(f"ℹ️ Skipped {symbol} iron condor: net credit not positive")
                            elif error_msg == 'correlation_blocked':
                                warning = result.get('message') or 'Correlation safeguard triggered'
                                print(f"ℹ️ Skipped {symbol}: {warning}")
                            else:
                                print(f"❌ Failed to execute {symbol}: {error_msg}")

                        if signals_executed >= available_slots:
                            break

                    if signals_executed == 0:
                        print(f"⚪ No actionable signals met the {min_confidence:.0%} confidence threshold.")

                if executed_trades:
                    print("📈 Trades this iteration:")
                    for trade in executed_trades:
                        print(
                            f"   • {trade['symbol']} — {trade['strategy']} | lots: {trade['lots']} | "
                            f"Risk: ₹{trade['max_loss']:,.0f} | Reward: ₹{trade['max_profit']:,.0f}"
                        )
                else:
                    print("📭 No new trades executed this iteration.")

                # Portfolio summary
                total_value = self.portfolio.calculate_total_value(current_prices)
                unrealized = 0.0
                for sym, pos in self.portfolio.positions.items():
                    current_price = current_prices.get(sym, pos.get('entry_price', 0.0))
                    shares = pos.get('shares', 0)
                    entry_price = pos.get('entry_price', 0.0)
                    invested = pos.get('invested_amount', entry_price * shares)
                    unrealized += (current_price * shares) - invested

                print("💼 Portfolio status:")
                print(f"   • Cash: ₹{self.portfolio.cash:,.2f}")
                print(f"   • Total value: ₹{total_value:,.2f}")
                print(f"   • Active positions: {len(self.portfolio.positions)}")
                print(f"   • Unrealized P&L: ₹{unrealized:,.2f}")
                print(f"   • Lifetime trades: {self.portfolio.trades_count} "
                      f"(Wins: {self.portfolio.winning_trades}, Losses: {self.portfolio.losing_trades})")
                if executed_trades:
                    last_trade = executed_trades[-1]
                    print(f"   • Last trade: {last_trade['symbol']} {last_trade['strategy']} lots={last_trade['lots']}")

                try:
                    self.portfolio.send_dashboard_update(current_prices)
                except Exception as exc:
                    logger.debug(f"Dashboard portfolio update failed: {exc}")

                try:
                    self.portfolio.save_state_to_files()
                except Exception as exc:
                    logger.debug(f"Portfolio state save failed: {exc}")

                print(f"⏳ Waiting {check_interval}s for next scan (Ctrl+C to stop)...")
                try:
                    time.sleep(check_interval)
                except KeyboardInterrupt:
                    raise

        except KeyboardInterrupt:
            print("\n🛑 Continuous monitoring stopped by user.")
        finally:
            try:
                self.portfolio.save_state_to_files()
            except Exception as exc:
                logger.debug(f"Final portfolio save failed: {exc}")

            if self.portfolio.dashboard:
                try:
                    self.portfolio.dashboard.send_system_status(False, iteration, "stopped")
                except Exception:
                    pass

    def run_single_scan(self):
        """Run a single pass of intelligent monitoring for prioritized indices."""
        print("\n🧪 QUICK F&O SCAN (single iteration)")
        prioritized = IndexConfig.get_prioritized_indices()
        available = self.data_provider.get_available_indices()
        indices = [symbol for symbol in prioritized if symbol in available]

        if not indices:
            print("⚠️ No prioritized indices available from data provider.")
            return

        for symbol in indices:
            print(f"\n🔍 Analyzing {symbol} ...")
            analysis = self.intelligent_selector.analyze_market_conditions(symbol)
            if analysis.get('error'):
                print(f"❌ Failed to analyze {symbol}: {analysis['error']}")
                continue

            recommendation = analysis.get('strategy_recommendation', {}) or {}
            strategy = recommendation.get('strategy', 'hold').replace('_', ' ').title()
            confidence = recommendation.get('confidence', 0.0)

            market_state_info = analysis.get('market_state_details')
            market_state_key = analysis.get('market_state')
            if not market_state_info or not isinstance(market_state_info, dict):
                description = market_state_key or 'N/A'
                market_state = description.replace('_', ' ').title() if isinstance(description, str) else 'N/A'
            else:
                market_state = market_state_info.get('description') or (
                    market_state_key.replace('_', ' ').title() if isinstance(market_state_key, str) else 'N/A'
                )

            iv_regime = analysis.get('iv_regime', {}).get('regime', 'unknown')

            print(f"   • Strategy: {strategy} ({confidence:.0%} confidence)")
            print(f"   • Market state: {market_state}")
            print(f"   • IV regime: {iv_regime}")

            self._auto_execute_paper_trade(symbol, analysis)

            if recommendation.get('actionable'):
                print("   ✅ Actionable opportunity detected.")

    def run_strangle_strategy(self):
        """Analyze a long strangle opportunity."""
        print("\n🎯 STRANGLE STRATEGY EXECUTION")
        print("-" * 40)
        indices = list(self.data_provider.get_available_indices().keys())
        if not indices:
            print("⚠️ No indices available for analysis.")
            return
        for idx, symbol in enumerate(indices, 1):
            print(f"   {idx}. {symbol}")

        selection = get_validated_int(f"Select index (1-{len(indices)}): ", 1, len(indices))
        symbol = indices[selection - 1]

        chain = self.data_provider.fetch_option_chain(symbol)
        if not chain:
            print("❌ Failed to fetch option chain")
            return

        atm = chain.get_atm_strike()
        call_strikes = sorted(s for s in chain.calls if s > atm)
        put_strikes = sorted((s for s in chain.puts if s < atm), reverse=True)
        if not call_strikes or not put_strikes:
            print("⚠️ Not enough OTM strikes to build a strangle")
            return

        call_option = chain.calls[call_strikes[0]]
        put_option = chain.puts[put_strikes[0]]
        total_premium = call_option.last_price + put_option.last_price
        upper_be = call_option.strike_price + total_premium
        lower_be = put_option.strike_price - total_premium

        print(f"✅ Long strangle setup on {symbol}")
        print(f"   • Buy Call Strike: ₹{call_option.strike_price:.0f} (Premium ₹{call_option.last_price:.2f})")
        print(f"   • Buy Put Strike: ₹{put_option.strike_price:.0f} (Premium ₹{put_option.last_price:.2f})")
        print(f"   • Total Premium: ₹{total_premium:.2f}")
        print(f"   • Breakeven Range: ₹{lower_be:.0f} – ₹{upper_be:.0f}")

    def run_butterfly_strategy(self):
        """Suggest a call butterfly using ATM ±1 strikes."""
        print("\n🦋 BUTTERFLY STRATEGY SETUP")
        print("-" * 40)
        indices = list(self.data_provider.get_available_indices().keys())
        if not indices:
            print("⚠️ No indices available for analysis.")
            return
        for idx, symbol in enumerate(indices, 1):
            print(f"   {idx}. {symbol}")

        selection = get_validated_int(f"Select index (1-{len(indices)}): ", 1, len(indices))
        symbol = indices[selection - 1]
        chain = self.data_provider.fetch_option_chain(symbol)
        if not chain:
            print("❌ Failed to fetch option chain")
            return

        atm = chain.get_atm_strike()
        strikes = sorted(chain.calls.keys())
        if atm not in strikes:
            strikes.append(atm)
            strikes.sort()
        try:
            atm_index = strikes.index(atm)
        except ValueError:
            print("⚠️ Could not determine ATM strike")
            return

        if atm_index == 0 or atm_index >= len(strikes) - 1:
            print("⚠️ Not enough surrounding strikes for butterfly")
            return

        lower = strikes[max(0, atm_index - 1)]
        upper = strikes[min(len(strikes) - 1, atm_index + 1)]
        buy_lower = chain.calls.get(lower)
        sell_atm = chain.calls.get(atm)
        buy_upper = chain.calls.get(upper)
        if not all([buy_lower, sell_atm, buy_upper]):
            print("⚠️ Required call strikes not available")
            return

        net_cost = buy_lower.last_price + buy_upper.last_price - 2 * sell_atm.last_price
        max_profit = (sell_atm.strike_price - lower) - net_cost

        print(f"✅ Call butterfly on {symbol}")
        print(f"   • Buy 1 {lower:.0f} CE @ ₹{buy_lower.last_price:.2f}")
        print(f"   • Sell 2 {atm:.0f} CE @ ₹{sell_atm.last_price:.2f}")
        print(f"   • Buy 1 {upper:.0f} CE @ ₹{buy_upper.last_price:.2f}")
        print(f"   • Net Cost: ₹{net_cost:.2f}")
        print(f"   • Max Profit (approx): ₹{max_profit:.2f}")

    def run_covered_call_flow(self):
        """Guide user through covered call decision making."""
        print("\n🛡️ COVERED CALL CHECKLIST")
        print("-" * 40)
        if not self.portfolio.positions:
            print("⚠️ No equity positions found in portfolio to cover.")
            return

        for symbol, pos in self.portfolio.positions.items():
            shares = pos.get('shares', 0)
            entry = pos.get('entry_price', 0)
            print(f"   • {symbol}: {shares} shares @ ₹{entry:.2f}")
        print("\n📝 Identify which underlying you want to cover and use option chain analysis (Option 10) to select an OTM call.")

    def run_protective_put_flow(self):
        """Guide user through protective put decision making."""
        print("\n🛡️ PROTECTIVE PUT CHECKLIST")
        print("-" * 40)
        if not self.portfolio.positions:
            print("⚠️ No equity positions found in portfolio to hedge.")
            return
        for symbol, pos in self.portfolio.positions.items():
            shares = pos.get('shares', 0)
            entry = pos.get('entry_price', 0)
            print(f"   • {symbol}: {shares} shares @ ₹{entry:.2f}")
        print("\n📝 Use option chain analysis to choose a suitable OTM put for downside protection.")

    def run_greeks_calculator(self):
        """Compute option Greeks for a chosen strike."""
        print("\n📐 OPTIONS GREEKS CALCULATOR")
        indices = list(self.data_provider.get_available_indices().keys())
        if not indices:
            print("⚠️ No indices available.")
            return
        for idx, symbol in enumerate(indices, 1):
            print(f"   {idx}. {symbol}")
        selection = get_validated_int(f"Select index (1-{len(indices)}): ", 1, len(indices))
        symbol = indices[selection - 1]

        chain = self.data_provider.fetch_option_chain(symbol)
        if not chain:
            print("❌ Failed to fetch option chain")
            return

        strike = get_validated_int("Enter strike price to evaluate: ")
        option = chain.calls.get(float(strike)) or chain.puts.get(float(strike))
        if not option:
            print("⚠️ Strike not found in current option chain.")
            return

        days_to_expiry = max((chain.timestamp - datetime.now()).days, 1)
        option.calculate_greeks(chain.spot_price, days_to_expiry / 365.0, max(option.implied_volatility, 15))
        print(f"✅ Greeks for {option.symbol}")
        print(f"   • Delta: {option.delta:.4f}\n   • Gamma: {option.gamma:.4f}\n   • Theta: {option.theta:.4f}\n   • Vega: {option.vega:.4f}\n   • Rho: {option.rho:.4f}")

    def run_iv_analysis(self):
        """Summarize implied volatility regime for prioritized indices."""
        print("\n📈 IMPLIED VOLATILITY ANALYSIS")
        print("-" * 40)
        indices = IndexConfig.get_prioritized_indices()
        for symbol in indices:
            chain = self.data_provider.fetch_option_chain(symbol)
            if not chain:
                print(f"⚠️ {symbol}: option chain unavailable")
                continue
            atm = chain.get_atm_strike()
            option = chain.calls.get(atm) or next(iter(chain.calls.values()), None)
            if not option:
                print(f"⚠️ {symbol}: ATM option missing")
                continue
            iv = option.implied_volatility
            if iv <= 15:
                regime = "Low"
            elif iv <= 28:
                regime = "Moderate"
            else:
                regime = "High"
            print(f"   • {symbol}: IV {iv:.1f}% ({regime})")

    def run_backtest_menu(self):
        """Run a mock backtest via analytics helper."""
        print("\n🧪 BACKTEST STRATEGY")
        indices = IndexConfig.get_prioritized_indices()
        for idx, symbol in enumerate(indices, 1):
            print(f"   {idx}. {symbol}")
        selection = get_validated_int(f"Select index (1-{len(indices)}): ", 1, len(indices))
        symbol = indices[selection - 1]
        start_date = input("Enter start date (YYYY-MM-DD): ").strip() or "2025-01-01"
        end_date = input("Enter end date (YYYY-MM-DD): ").strip() or "2025-03-31"
        strategy = input("Strategy (straddle/iron_condor): ").strip().lower() or "straddle"
        results = self.backtester.run_backtest(strategy, symbol, start_date, end_date)
        if results.get('error'):
            print(f"❌ Backtest failed: {results['error']}")
            return
        for key, value in results.items():
            print(f"   • {key.replace('_', ' ').title()}: {value}")

    def run_performance_report(self):
        """Display aggregated performance metrics from the portfolio."""
        print("\n📊 PERFORMANCE REPORT")
        print("-" * 40)
        total_value = self.portfolio.calculate_total_value()
        print(f"   • Cash: ₹{self.portfolio.cash:,.2f}")
        print(f"   • Total Value: ₹{total_value:,.2f}")
        print(f"   • Open Positions: {len(self.portfolio.positions)}")
        print(f"   • Total P&L: ₹{self.portfolio.total_pnl:,.2f}")

    def show_risk_management_settings(self):
        """Display current risk parameters."""
        print("\n⚙️ RISK MANAGEMENT SETTINGS")
        print(f"   • Risk per trade: {self.portfolio.risk_per_trade_pct*100:.2f}%")
        print(f"   • ATR stop multiplier: {self.portfolio.atr_stop_multiplier:.2f}")
        print(f"   • ATR target multiplier: {self.portfolio.atr_target_multiplier:.2f}")
        print(f"   • Max positions: {self.portfolio.max_position_size*100:.1f}% of capital per trade")

    def configure_position_sizing(self):
        """Allow user to adjust position sizing parameters."""
        print("\n📏 POSITION SIZING")
        try:
            new_risk = float(input("Risk per trade (%) [blank to skip]: ") or self.portfolio.risk_per_trade_pct*100)
            self.portfolio.risk_per_trade_pct = max(0.001, new_risk / 100.0)
            print(f"✅ Risk per trade updated to {self.portfolio.risk_per_trade_pct*100:.2f}%")
        except ValueError:
            print("⚠️ Invalid input, keeping previous settings.")

    def reset_portfolio_menu(self):
        """Reset portfolio state to default capital."""
        confirm = input("Reset portfolio to ₹10,00,000? (y/N): ").strip().lower()
        if confirm == 'y':
            self.portfolio.cash = self.portfolio.initial_cash
            self.portfolio.positions.clear()
            print("✅ Portfolio reset to initial capital.")
        else:
            print("↩️ Reset cancelled.")

    def _print_strategy_summary(self, symbol: str, analysis: Dict, verbose: bool = False):
        recommendation = analysis.get('strategy_recommendation', {}) or {}
        strategy = str(recommendation.get('strategy', 'hold')).replace('_', ' ').title()
        confidence = recommendation.get('confidence', 0.0)
        market_state_info = analysis.get('market_state') or {}
        if isinstance(market_state_info, dict):
            market_state = market_state_info.get('description', 'unknown')
        else:
            market_state = str(market_state_info)
        print(f"\n📌 {symbol} Strategy Recommendation")
        print(f"   • Suggested Strategy: {strategy} ({confidence:.0%} confidence)")
        print(f"   • Market State: {market_state}")
        if verbose:
            iv_regime = analysis.get('iv_regime') or {}
            if isinstance(iv_regime, dict):
                regime = iv_regime.get('regime', 'unknown')
                percentile = iv_regime.get('percentile', 'N/A')
            else:
                regime = str(iv_regime)
                percentile = 'N/A'
            print(f"   • IV Regime: {regime} ({percentile} percentile)")
            trend = analysis.get('trend_analysis') or {}
            if isinstance(trend, dict):
                bias = trend.get('bias', 'neutral')
                momentum = trend.get('momentum_score', 'N/A')
            else:
                bias = str(trend)
                momentum = 'N/A'
            print(f"   • Trend Bias: {bias}\n   • Momentum Score: {momentum}")

    def _auto_execute_paper_trade(self, index_symbol: str, analysis: Dict) -> None:
        """Automatically execute high-confidence strategies in paper mode."""
        if not self.auto_paper_trading_enabled or not analysis:
            return

        recommendation = analysis.get('strategy_recommendation') or {}
        strategy = recommendation.get('strategy')
        execution_details = recommendation.get('execution_details')

        if not strategy or not execution_details:
            return

        confidence = float(recommendation.get('confidence', 0.0))
        market_state_details = analysis.get('market_state_details') or {}
        state_score = float(market_state_details.get('score', confidence))

        # Blend strategy confidence with market-state context
        combined_confidence = (confidence + state_score) / 2.0

        if combined_confidence < self.auto_trade_confidence_threshold:
            return

        now = datetime.now()
        last_trade = self._last_auto_trade.get(index_symbol)
        if last_trade and (now - last_trade) < self.auto_trade_cooldown:
            return

        # Avoid stacking multiple unresolved positions on the same index
        existing_symbols = [
            sym for sym in self.portfolio.positions.keys()
            if sym.upper().startswith(index_symbol.upper())
        ]
        if existing_symbols:
            logger.debug(
                "Skipping auto trade for %s: open paper positions detected (%s)",
                index_symbol,
                ", ".join(existing_symbols[:3])
            )
            return

        capital_available = max(self.portfolio.cash, 0.0)
        if capital_available <= 0:
            logger.info(f"⚠️ Skipping auto trade for {index_symbol}: no available paper capital.")
            return

        try:
            result = self.intelligent_selector._execute_strategy(
                strategy,
                execution_details,
                capital_available,
                analysis,
                self.portfolio
            )
        except Exception as exc:
            logger.error(f"❌ Auto trade execution failed for {index_symbol}: {exc}")
            return

        if not result.get('success'):
            logger.info(f"🤖 Auto trade skipped for {index_symbol}: {result.get('error', 'unknown error')}")
            return

        self._last_auto_trade[index_symbol] = now
        lots = result.get('lots')
        lots_msg = ""
        if lots is not None:
            lots_msg = f" ({lots} lot{'s' if lots != 1 else ''})"

        max_loss = result.get('max_loss')
        max_profit = result.get('max_profit')
        risk_line = ""
        if max_loss is not None and max_profit is not None:
            risk_line = f"   • Risk: ₹{max_loss:,.2f} | Reward potential: ₹{max_profit:,.2f}\n"

        sentiment = self._simulate_trader_emotion(index_symbol, combined_confidence, result)

        print(f"   🤖 Auto-executed {strategy.replace('_', ' ').title()} on {index_symbol}{lots_msg}")
        if risk_line:
            print(risk_line, end="")
        print(f"   • Simulated trader sentiment: {sentiment}")
        logger.info(
            "🤖 Paper trade executed automatically: %s | Strategy=%s | Confidence=%.2f",
            index_symbol,
            strategy,
            combined_confidence
        )

    def _simulate_trader_emotion(self, index_symbol: str, confidence: float, trade_result: Dict) -> str:
        """
        Produce a lightweight emotional response simulation to highlight decision psychology.
        Tracks recent outcomes to bias future emotions.
        """
        # Update memory with recent P&L impact
        pnl_hint = 0.0
        for key in ('max_profit', 'max_loss'):
            value = trade_result.get(key)
            if isinstance(value, (int, float)) and value:
                if key == 'max_profit':
                    pnl_hint += value
                else:
                    pnl_hint -= abs(value)

        momentum = self._emotional_bias_memory.get(index_symbol, 0.0)
        momentum = (momentum * 0.6) + (pnl_hint * 0.0001)
        self._emotional_bias_memory[index_symbol] = momentum

        emotional_score = min(max(confidence + momentum, 0.0), 1.0)
        if emotional_score >= 0.80:
            return "Confident and focused"
        if emotional_score >= 0.65:
            return "Cautiously optimistic"
        if emotional_score >= 0.55:
            return "Alert and watchful"
        return "Anxious and risk-aware"

    def run(self):
        """Interactive loop for the F&O terminal."""
        while True:
            self.display_menu()
            choice = input("Select option (1-18 or 'q' to exit): ").strip().lower()

            if choice in {"q", "quit", "exit"}:
                print("👋 Exiting F&O terminal")
                break

            try:
                option = int(choice)
            except ValueError:
                print("❌ Invalid selection")
                continue

            actions = {
                1: self.run_auto_strategy_selection,
                2: self.run_continuous_monitoring,
                3: self.run_market_analysis,
                4: self.run_straddle_strategy,
                5: self.run_iron_condor_strategy,
                6: self.run_strangle_strategy,
                7: self.run_butterfly_strategy,
                8: self.run_covered_call_flow,
                9: self.run_protective_put_flow,
                10: self.run_option_chain_analysis,
                11: self.run_greeks_calculator,
                12: self.run_iv_analysis,
                13: self.run_backtest_menu,
                14: self.run_performance_report,
                15: self.show_risk_management_settings,
                16: self.configure_position_sizing,
                17: self.reset_portfolio_menu,
                18: self.run_single_scan,
            }
            action = actions.get(option)
            if action:
                action()
            else:
                print("⚠️ Option not yet implemented in CLI mode.")

    def run_straddle_strategy(self):
        """Run straddle strategy execution"""
        print("\n🎯 STRADDLE STRATEGY EXECUTION")
        print("-" * 40)

        # Select index
        indices = list(self.data_provider.get_available_indices().keys())
        print("Available indices:")
        for i, index in enumerate(indices, 1):
            print(f"   {i}. {index}")

        try:
            choice = int(input("Select index (1-6): ").strip())
            if choice < 1 or choice > len(indices):
                print("❌ Invalid choice")
                return

            index_symbol = indices[choice - 1]
            print(f"🔍 Analyzing {index_symbol} for straddle opportunities...")

            # Fetch option chain
            chain = self.data_provider.fetch_option_chain(index_symbol)
            if not chain:
                print("❌ Failed to fetch option chain")
                return

            # Analyze straddle
            straddle = StraddleStrategy()
            analysis = straddle.analyze_option_chain(chain)

            if analysis.get('confidence', 0) > 0.5:
                print("✅ Straddle opportunity found!")
                print(f"   • Strike: ₹{analysis['strike']:,.0f}")
                print(f"   • Call Premium: ₹{analysis['call_option'].last_price:.2f}")
                print(f"   • Put Premium: ₹{analysis['put_option'].last_price:.2f}")
                print(f"   • Total Premium: ₹{analysis['total_premium']:.2f}")
                print(f"   • Confidence: {analysis['confidence']:.1%}")
                print(f"   • Expected Move: ₹{analysis['expected_move']:.0f}")

                # Ask for execution
                execute = input("Execute straddle trade? (y/N): ").strip().lower()
                if execute == 'y':
                    self._execute_strategy(chain, 'straddle', analysis)
            else:
                print("❌ No favorable straddle opportunity found")

        except Exception as e:
            print(f"❌ Error: {e}")

    def run_iron_condor_strategy(self):
        """Run iron condor strategy execution"""
        print("\n🎯 IRON CONDOR STRATEGY EXECUTION")
        print("-" * 40)

        # Select index
        indices = list(self.data_provider.get_available_indices().keys())
        print("Available indices:")
        for i, index in enumerate(indices, 1):
            print(f"   {i}. {index}")

        try:
            choice = int(input("Select index (1-6): ").strip())
            if choice < 1 or choice > len(indices):
                print("❌ Invalid choice")
                return

            index_symbol = indices[choice - 1]
            print(f"🔍 Analyzing {index_symbol} for iron condor opportunities...")

            # Fetch option chain
            chain = self.data_provider.fetch_option_chain(index_symbol)
            if not chain:
                print("❌ Failed to fetch option chain")
                return

            # Analyze iron condor
            condor = IronCondorStrategy()
            analysis = condor.analyze_option_chain(chain)

            if analysis.get('confidence', 0) > 0.4:
                print("✅ Iron Condor opportunity found!")
                print(f"   • Sell Call Strike: ₹{analysis['sell_call_strike']:,.0f}")
                print(f"   • Buy Call Strike: ₹{analysis['buy_call_strike']:,.0f}")
                print(f"   • Sell Put Strike: ₹{analysis['sell_put_strike']:,.0f}")
                print(f"   • Buy Put Strike: ₹{analysis['buy_put_strike']:,.0f}")
                print(f"   • Net Credit: ₹{analysis['net_credit']:.2f}")
                print(f"   • Max Profit: ₹{analysis['max_profit']:.2f}")
                print(f"   • Max Loss: ₹{analysis['max_loss']:.2f}")
                print(f"   • Risk/Reward: {analysis['risk_reward']:.2f}")

                # Ask for execution
                execute = input("Execute iron condor trade? (y/N): ").strip().lower()
                if execute == 'y':
                    self._execute_strategy(chain, 'iron_condor', analysis)
            else:
                print("❌ No favorable iron condor opportunity found")

        except Exception as e:
            print(f"❌ Error: {e}")

    def save_system_state(self, filename: str = "fno_system_state.json"):
        """Save complete F&O trading system state for persistence"""
        try:
            import os
            import json
            os.makedirs('state', exist_ok=True)

            # Get comprehensive system state with proper datetime serialization
            system_state = {
                'timestamp': datetime.now().isoformat(),
                'trading_mode': self.portfolio.trading_mode,
                'iteration': getattr(self, 'iteration', 0),
                'portfolio': self.portfolio.to_dict(),
                'configuration': {
                    'min_confidence': getattr(self, 'min_confidence', 0.60),
                    'check_interval': getattr(self, 'check_interval', 300),
                    'max_positions': getattr(self, 'max_positions', 5),
                    'capital_per_trade': getattr(self, 'capital_per_trade', 200000)
                },
                'available_indices': list(self.data_provider.get_available_indices().keys()),
                'last_market_analysis': getattr(self, 'last_market_analysis', {})
            }

            # Ensure all datetime objects are properly serialized
            def serialize_datetime(obj):
                """Custom JSON serializer that handles datetime objects"""
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

            filepath = f'state/{filename}'
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(system_state, f, indent=2, default=serialize_datetime)

            logger.info(f"💾 System state saved to {filepath}")
            print(f"💾 System state saved: {len(self.portfolio.positions)} positions, ₹{self.portfolio.cash:,.2f} cash")
            return True

        except Exception as e:
            logger.error(f"Failed to save system state: {e}")
            print(f"❌ Failed to save state: {e}")
            return False

    def load_system_state(self, filename: str = "fno_system_state.json") -> bool:
        """Load complete F&O trading system state for resumption"""
        try:
            import os
            import json

            filepath = f'state/{filename}'
            if not os.path.exists(filepath):
                print(f"ℹ️ No saved state found at {filepath}")
                return False

            # First, try to validate the JSON file
            try:
                with open(filepath, 'r') as f:
                    system_state = json.load(f)
            except json.JSONDecodeError as e:
                print(f"⚠️ Corrupted state file detected: {e}")
                print("🗑️ Cleaning up corrupted state file and starting fresh...")
                try:
                    os.remove(filepath)
                    print("✅ Corrupted state file removed - starting fresh session")
                except Exception:
                    print("⚠️ Could not remove corrupted file")
                return False
            except Exception as e:
                print(f"⚠️ Error reading state file: {e}")
                print("🗑️ Attempting to clean up and start fresh...")
                try:
                    os.remove(filepath)
                    print("✅ State file removed - starting fresh session")
                except Exception:
                    print("⚠️ Could not remove file")
                return False

            # Validate that the loaded data has expected structure
            if not isinstance(system_state, dict):
                print("⚠️ Invalid state file format - starting fresh")
                return False

            # Restore portfolio state
            portfolio_data = system_state.get('portfolio', {})
            if portfolio_data and isinstance(portfolio_data, dict):
                try:
                    self.portfolio.load_from_dict(portfolio_data)
                    print(f"✅ Portfolio restored: {len(self.portfolio.positions)} positions, ₹{self.portfolio.cash:,.2f} cash")
                except Exception as e:
                    print(f"⚠️ Error loading portfolio data: {e}")
                    print("📊 Continuing with empty portfolio...")
                    self.portfolio = UnifiedPortfolio(initial_cash=1000000, trading_mode='paper')

            # Restore configuration
            config = system_state.get('configuration', {})
            if config and isinstance(config, dict):
                self.min_confidence = config.get('min_confidence', 0.60)
                self.check_interval = config.get('check_interval', 300)
                self.max_positions = config.get('max_positions', 5)
                self.capital_per_trade = config.get('capital_per_trade', 200000)
                print(f"✅ Configuration restored: {self.min_confidence:.0%} confidence, {self.max_positions} max positions")

            # Restore iteration counter
            self.iteration = system_state.get('iteration', 0)

            # Restore other state
            saved_time = system_state.get('timestamp', '')
            trading_mode = system_state.get('trading_mode', 'paper')

            print(f"✅ System state loaded from {saved_time}")
            print(f"✅ Trading mode: {trading_mode}")

            # Send updated state to dashboard
            try:
                self.portfolio.send_dashboard_update()
            except Exception as e:
                print(f"⚠️ Could not update dashboard: {e}")

            return True

        except Exception as e:
            logger.error(f"Failed to load system state: {e}")
            print(f"❌ Failed to load state: {e}")
            print("🔄 Starting with fresh session...")
            return False

    def auto_save_state(self):
        """Automatically save state during trading"""
        try:
            # Save every 10 iterations or when significant changes occur
            if hasattr(self, 'iteration') and (self.iteration % 10 == 0 or len(self.portfolio.positions) > 0):
                self.save_system_state()
        except Exception as e:
            logger.warning(f"Auto-save failed: {e}")

    def close_all_positions(self, reason: str = "manual_close"):
        """Close all F&O positions immediately"""
        if not self.portfolio.positions:
            print("📊 No positions to close")
            return

        positions_closed = 0
        total_pnl = 0.0

        for symbol, position in list(self.portfolio.positions.items()):
            shares = int(position.get('shares', 0))
            if shares == 0:
                continue

            try:
                # Get current market price
                current_price = position.get('entry_price', 0)
                try:
                    # Try to get real-time price if available
                    if hasattr(self, 'data_provider'):
                        quote = self.data_provider.kite.quote([symbol])
                        if symbol in quote and 'last_price' in quote[symbol]:
                            current_price = float(quote[symbol]['last_price'])
                except Exception:
                    pass

                # Execute trade to close position
                trade = self.portfolio.execute_trade(
                    symbol,
                    abs(shares),
                    current_price,
                    "sell" if shares > 0 else "buy",
                    datetime.now(),
                    0.8,
                    position.get('sector', 'F&O'),
                    allow_immediate_sell=True,
                    strategy=reason
                )

                if trade:
                    positions_closed += 1
                    pnl = trade.get('pnl', 0)
                    total_pnl += pnl
                    print(f"🛑 Closed {symbol}: {shares} shares, P&L: ₹{pnl:.2f}")

            except Exception as e:
                print(f"❌ Error closing position for {symbol}: {e}")

        if positions_closed > 0:
            print(f"✅ Closed {positions_closed} positions, Total P&L: ₹{total_pnl:.2f}")
        else:
            print("❌ No positions were successfully closed")

    def adjust_fno_positions_for_market(self):
        """Adjust F&O positions based on market conditions for next day"""
        if not self.portfolio.positions:
            print("📊 No positions to adjust")
            return

        print("🔄 Analyzing F&O positions for market-based adjustments...")
        adjustments_made = 0

        for symbol, position in list(self.portfolio.positions.items()):
            shares = int(position.get('shares', 0))
            if shares == 0:
                continue

            try:
                # Get current market data
                current_price = position.get('entry_price', 0)
                volatility = 0.0

                try:
                    # Get real-time price and calculate volatility
                    quote = self.data_provider.kite.quote([symbol])
                    if symbol in quote:
                        current_price = float(quote[symbol]['last_price'])
                        day_change = quote[symbol].get('net_change', 0)
                        if current_price > 0:
                            volatility = abs(day_change / current_price) * 100
                except Exception:
                    pass

                # Decision logic for F&O adjustments
                adjustment_needed = False
                action = "hold"
                factor = 1.0  # Initialize with default value

                if volatility > 5:  # High volatility - reduce position
                    action = "reduce"
                    factor = 0.7
                    adjustment_needed = True
                elif volatility < 1:  # Low volatility - can increase if profitable
                    entry_price = position.get('entry_price', current_price)
                    if current_price > entry_price * 1.02:  # 2% profit
                        action = "increase"
                        factor = 1.3
                        adjustment_needed = True

                if adjustment_needed:
                    if action == "reduce":
                        shares_to_sell = int(shares * (1 - factor))
                        if shares_to_sell > 0:
                            trade = self.portfolio.execute_trade(
                                symbol, shares_to_sell, current_price, 'sell',
                                datetime.now(), 0.7, 'F&O',
                                allow_immediate_sell=True, strategy='market_adjustment'
                            )
                            if trade:
                                print(f"📉 Reduced {symbol}: -{shares_to_sell} shares (high volatility)")
                                adjustments_made += 1

                    elif action == "increase":
                        additional_shares = int(shares * (factor - 1))
                        if additional_shares > 0:
                            trade = self.portfolio.execute_trade(
                                symbol, additional_shares, current_price, 'buy',
                                datetime.now(), 0.7, 'F&O',
                                allow_immediate_sell=True, strategy='market_adjustment'
                            )
                            if trade:
                                print(f"📈 Increased {symbol}: +{additional_shares} shares (profitable + stable)")
                                adjustments_made += 1

            except Exception as e:
                print(f"❌ Error adjusting {symbol}: {e}")

        if adjustments_made > 0:
            print(f"✅ Completed {adjustments_made} F&O position adjustments")
        else:
            print("📊 No F&O position adjustments needed")

    def save_fno_positions_for_next_day(self, reason: str = "auto_save"):
        """Save F&O positions for next day restoration"""
        if not self.portfolio.positions:
            print("📊 No F&O positions to save")
            return 0

        print(f"💾 Saving F&O positions (Reason: {reason})")

        # FIXED: Use TODAY's date, not tomorrow's (user request)
        import pytz
        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(ist)
        today = current_time.strftime('%Y-%m-%d')  # Changed from next_day to today

        positions_saved = 0
        saved_positions = {}

        for symbol, position in list(self.portfolio.positions.items()):
            shares = int(position.get('shares', 0))
            if shares == 0:
                continue

            try:
                # Get current market price
                current_price = position.get('entry_price', 0)
                try:
                    if hasattr(self, 'data_provider'):
                        quote = self.data_provider.kite.quote([symbol])
                        if symbol in quote and 'last_price' in quote[symbol]:
                            current_price = float(quote[symbol]['last_price'])
                except Exception:
                    pass

                invested_amount = float(position.get('invested_amount', position.get('entry_price', current_price) * abs(shares)))
                if shares >= 0:
                    position_value = current_price * shares
                    unrealized_pnl = position_value - invested_amount
                else:
                    entry_price = position.get('entry_price', current_price)
                    unrealized_pnl = (entry_price - current_price) * abs(shares)

                # Save F&O position data
                saved_position = {
                    'symbol': symbol,
                    'shares': shares,
                    'entry_price': position.get('entry_price', current_price),
                    'current_price': current_price,
                    'sector': position.get('sector', 'F&O'),
                    'confidence': position.get('confidence', 0.8),
                    'entry_time': position.get('entry_time', current_time).isoformat() if isinstance(position.get('entry_time'), datetime) else str(position.get('entry_time', current_time)),
                    'saved_at': current_time.isoformat(),
                    'saved_for_day': today,  # Fixed: use today instead of next_day
                    'strategy': position.get('strategy', 'fno_saved'),
                    'unrealized_pnl': unrealized_pnl,
                    'save_reason': reason,
                    'position_type': 'F&O',
                    'invested_amount': invested_amount
                }

                saved_positions[symbol] = saved_position
                positions_saved += 1

                print(f"💾 Saved F&O: {symbol} - {shares} shares @ ₹{current_price:.2f} (P&L: ₹{saved_position['unrealized_pnl']:.2f})")

            except Exception as e:
                print(f"❌ Error saving F&O position for {symbol}: {e}")

        # Save to file
        if saved_positions:
            self._save_fno_positions_to_file(saved_positions, today)
            print(f"✅ Saved {positions_saved} F&O positions for {today}")
        else:
            print("📊 No F&O positions were saved")

        return positions_saved

    def _perform_end_of_day_archival(self):
        """
        Perform comprehensive end-of-day archival
        - Archives all completed trades to trade_archives/
        - Saves open F&O positions to saved_trades/
        Called automatically at 3:30 PM market close
        """
        import pytz

        print("\n" + "="*70)
        print("📦 END-OF-DAY ARCHIVAL - Market Closed at 3:30 PM")
        print("="*70)

        ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(ist)
        trading_day = now_ist.strftime('%Y-%m-%d')

        # 1. Archive all completed trades
        print(f"\n📊 Archiving trades for {trading_day}...")
        try:
            archive_result = self.portfolio.archive_end_of_day_trades()

            if archive_result['status'] == 'success':
                print(f"✅ Trade Archive Complete:")
                print(f"   • Trades archived: {archive_result['trade_count']}")
                print(f"   • Primary: {archive_result['file_path']}")
                if archive_result.get('backup_path'):
                    print(f"   • Backup: {archive_result['backup_path']}")
                if archive_result.get('open_positions_saved', 0) > 0:
                    print(f"   • Open positions: {archive_result['open_positions_saved']}")
            elif archive_result['status'] == 'no_trades':
                print("ℹ️  No trades to archive today")
            else:
                print(f"⚠️  Archive status: {archive_result['status']}")
                if archive_result.get('errors'):
                    print(f"   Errors: {archive_result['errors']}")

        except Exception as e:
            print(f"❌ Trade archival failed: {e}")
            logger.error(f"End-of-day trade archival error: {e}", exc_info=True)

        # 2. Save open F&O positions (FIXED: save with today's date, not tomorrow's)
        print(f"\n💼 Saving F&O positions for {trading_day}...")
        try:
            positions_saved = self.save_fno_positions_for_next_day("auto_save_market_close")

            if positions_saved > 0:
                print(f"✅ F&O Position Save Complete:")
                print(f"   • Positions saved: {positions_saved}")
                print(f"   • Saved for date: {trading_day}")  # Fixed: show today's date
            else:
                print("ℹ️  No open F&O positions to save")

        except Exception as e:
            print(f"❌ Position save failed: {e}")
            logger.error(f"End-of-day position save error: {e}", exc_info=True)

        # 3. Display final summary
        print(f"\n📈 Final Trading Summary:")
        print(f"   • Total value: ₹{self.portfolio.calculate_total_value():,.2f}")
        print(f"   • Cash balance: ₹{self.portfolio.cash:,.2f}")
        print(f"   • Active positions: {len(self.portfolio.positions)}")
        print(f"   • Total trades today: {self.portfolio.trades_count}")
        if hasattr(self.portfolio, 'winning_trades') and hasattr(self.portfolio, 'losing_trades'):
            total_closed = self.portfolio.winning_trades + self.portfolio.losing_trades
            if total_closed > 0:
                win_rate = (self.portfolio.winning_trades / total_closed * 100)
                print(f"   • Win rate: {win_rate:.1f}% ({self.portfolio.winning_trades}W/{self.portfolio.losing_trades}L)")

        print("\n" + "="*70)
        print("🌅 System ready for next trading day")
        print("="*70 + "\n")

    def _save_fno_positions_to_file(self, saved_positions: Dict, save_date: str):
        """Save F&O positions to file"""
        try:
            import os
            import json

            # Create saved_trades directory
            os.makedirs('saved_trades', exist_ok=True)

            # Save F&O positions with specific filename (FIXED: use save_date)
            filename = f"saved_trades/fno_positions_{save_date}.json"

            save_data = {
                'fno_positions': saved_positions,
                'saved_at': datetime.now().isoformat(),
                'target_date': save_date,  # Fixed: use save_date instead of next_day
                'total_positions': len(saved_positions),
                'total_value': sum(pos['current_price'] * pos['shares'] for pos in saved_positions.values()),
                'total_unrealized_pnl': sum(pos['unrealized_pnl'] for pos in saved_positions.values()),
                'position_type': 'F&O'
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2)

            print(f"💾 F&O positions saved to {filename}")
            print(f"💰 Total F&O value: ₹{save_data['total_value']:,.2f}, Unrealized P&L: ₹{save_data['total_unrealized_pnl']:,.2f}")

        except Exception as e:
            print(f"❌ Error saving F&O positions to file: {e}")

    def restore_fno_positions_for_day(self, target_day: str = None) -> bool:
        """Restore saved F&O positions for the current/target day"""
        try:
            import os
            import json

            if target_day is None:
                target_day = datetime.now().strftime('%Y-%m-%d')

            filename = f"saved_trades/fno_positions_{target_day}.json"

            if not os.path.exists(filename):
                print(f"📂 No saved F&O positions found for {target_day}")
                return False

            with open(filename, 'r') as f:
                save_data = json.load(f)

            saved_positions = save_data.get('fno_positions', {})

            if not saved_positions:
                print(f"📂 No F&O positions in saved file for {target_day}")
                return False

            print(f"🔄 Restoring {len(saved_positions)} F&O positions for {target_day}")

            restored_count = 0
            total_value = 0.0
            total_unrealized_pnl = 0.0

            for symbol, saved_pos in saved_positions.items():
                try:
                    # Get current market price
                    current_price = saved_pos['current_price']  # Start with saved price

                    try:
                        if hasattr(self, 'data_provider'):
                            quote = self.data_provider.kite.quote([symbol])
                            if symbol in quote and 'last_price' in quote[symbol]:
                                current_price = float(quote[symbol]['last_price'])
                    except Exception:
                        pass  # Use saved price if can't get current

                    invested_amount = float(saved_pos.get('invested_amount', saved_pos['entry_price'] * saved_pos['shares']))

                    # Restore F&O position to portfolio
                    restored_position = {
                        'shares': saved_pos['shares'],
                        'entry_price': saved_pos['entry_price'],
                        'sector': saved_pos['sector'],
                        'confidence': saved_pos['confidence'],
                        'entry_time': datetime.fromisoformat(saved_pos['entry_time'].replace('Z', '+00:00')) if 'T' in saved_pos['entry_time'] else datetime.now(),
                        'strategy': saved_pos.get('strategy', 'fno_restored'),
                        'restored_from': saved_pos['saved_for_day'],
                        'invested_amount': invested_amount
                    }

                    # Add to portfolio positions
                    self.portfolio.positions[symbol] = restored_position

                    shares_held = saved_pos['shares']
                    current_value = current_price * shares_held
                    if shares_held >= 0:
                        unrealized_pnl = current_value - invested_amount
                    else:
                        unrealized_pnl = (saved_pos['entry_price'] - current_price) * abs(shares_held)

                    total_value += current_value
                    total_unrealized_pnl += unrealized_pnl
                    restored_count += 1

                    print(f"🔄 Restored F&O: {symbol} - {saved_pos['shares']} shares @ ₹{saved_pos['entry_price']:.2f} (Current: ₹{current_price:.2f}, P&L: ₹{unrealized_pnl:.2f})")

                except Exception as e:
                    print(f"❌ Error restoring F&O position for {symbol}: {e}")

            if restored_count > 0:
                print(f"✅ Successfully restored {restored_count} F&O positions")
                print(f"💰 Total F&O portfolio value: ₹{total_value:,.2f}")
                print(f"📊 Total F&O unrealized P&L: ₹{total_unrealized_pnl:,.2f}")

                # Archive the used file
                archive_filename = f"saved_trades/fno_positions_{target_day}_used.json"
                os.rename(filename, archive_filename)
                print(f"📁 Archived used F&O save file to {archive_filename}")

                return True
            else:
                print(f"⚠️ No F&O positions could be restored for {target_day}")
                return False

        except Exception as e:
            print(f"❌ Error restoring F&O positions: {e}")
            return False

    def user_stop_fno_and_save(self, reason: str = "user_stop"):
        """Manual F&O stop that saves all trades for next day"""
        print(f"👤 USER STOP F&O: Saving all F&O positions for next trading day")
        return self.save_fno_positions_for_next_day(reason)

    def run_continuous_fno_monitoring(self):
        """Backward-compatible wrapper for continuous monitoring."""
        self.run_continuous_monitoring()
