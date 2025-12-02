#!/usr/bin/env python3
"""
Unified Trading System
Main trading loop and strategy execution engine
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import logging

import pandas as pd
import numpy as np
from kiteconnect import KiteConnect

from unified_config import get_config
from utilities.structured_logger import get_logger, log_function_call
from trading_utils import (
    get_ist_now,
    format_ist_timestamp,
    safe_divide,
    safe_float_conversion,
    validate_symbol,
    CircuitBreaker,
)
from strategies.base import BaseStrategy
from strategies.moving_average import ImprovedMovingAverageCrossover
from strategies.rsi import EnhancedRSIStrategy
from strategies.bollinger import BollingerBandsStrategy
from strategies.volume_breakout import ImprovedVolumeBreakoutStrategy
from strategies.momentum import EnhancedMomentumStrategy
from core.signal_aggregator import EnhancedSignalAggregator
from core.regime_detector import MarketRegimeDetector
from core.portfolio import UnifiedPortfolio
from data.provider import DataProvider
from api_rate_limiter import wrap_kite_with_rate_limiter
from utilities.market_hours import MarketHoursManager
from utilities.state_managers import TradingStateManager
from utilities.dashboard import DashboardConnector
from advanced_market_manager import AdvancedMarketManager
from core.security_context import SecurityContext
from core.backtest_engine import BacktestEngine
from enhanced_technical_analysis import EnhancedTechnicalAnalysis
from models.ml_predictor import MLPredictor
from sebi_compliance import SEBIComplianceChecker

logger = get_logger(__name__)


class UnifiedTradingSystem:
    """Unified trading system supporting all modes"""

    def __init__(self, data_provider: DataProvider, kite: KiteConnect, initial_cash: float = None, max_positions: int = None, dashboard: DashboardConnector = None, trading_mode: str = 'paper', config_override: Dict = None):
        self.dp = data_provider
        self.dashboard = dashboard
        if kite and not hasattr(kite, "get_rate_limiter_stats"):
            kite = wrap_kite_with_rate_limiter(kite)
        self.kite = kite
        self.trading_mode = trading_mode
        self.config = config_override or {}
        self.system_config = get_config()
        self.market_regime_detector = MarketRegimeDetector(self.dp)

        # Initialize circuit breaker for API calls
        self.api_circuit_breaker = CircuitBreaker(
            failure_threshold=5,  # Open after 5 consecutive failures
            timeout=60.0  # Try again after 60 seconds
        )

        # Initialize market hours manager
        self.market_hours = MarketHoursManager()

        # Initialize enhanced state manager

        # Create unified portfolio (silence when fast backtest)
        security_cfg = self.system_config.get('security', {})
        if isinstance(self.config, dict):
            security_override = self.config.get('security', {})
            if isinstance(security_override, dict):
                security_cfg = {**security_cfg, **security_override}

        self.security_context = SecurityContext(security_cfg)
        try:
            self.security_context.ensure_client_authorized()
            logger.info(f"🔐 Security context initialized for client {self.security_context.client_id}")
        except PermissionError as exc:
            logger.critical(f"Security enforcement blocked startup: {exc}")
            raise

        self.portfolio = UnifiedPortfolio(
            initial_cash,
            dashboard,
            kite,
            trading_mode,
            silent=bool(self.config.get('fast_backtest')),
            security_context=self.security_context
        )

        self.sebi_compliance = SEBIComplianceChecker(kite=self.kite)
        self.technical_analyzer = EnhancedTechnicalAnalysis()
        self.ml_predictor = MLPredictor()

        # Load shared F&O portfolio state if available (for paper trading integration)
        if trading_mode == 'paper':
            try:
                from pathlib import Path
                state_file = Path('state/shared_portfolio_state.json')
                if state_file.exists():
                    import json
                    with open(state_file, 'r') as f:
                        state_data = json.load(f)
                        if state_data.get('trading_mode') == 'paper':
                            # Integrate F&O positions and cash into main portfolio
                            if state_data.get('positions'):
                                self.portfolio.positions.update(state_data['positions'])
                                logger.info(f"🔄 Integrated {len(state_data['positions'])} F&O positions into main portfolio")

                            # Update cash only if F&O trading has occurred (cash changed from default)
                            if state_data.get('cash', 1000000) != 1000000:
                                self.portfolio.cash = state_data['cash']
                                logger.info(f"💰 Updated portfolio cash to ₹{self.portfolio.cash:,.2f} from F&O trading")

                            logger.info("🔄 NIFTY 50 portfolio integrated with F&O trades!")
            except Exception as e:
                logger.warning(f"Could not load F&O integration state: {e}")

        # Apply profile settings for paper trading
        if trading_mode == 'paper' and 'trading_profile' in self.config:
            profile = self.config['trading_profile']
            if profile == 'Aggressive':
                # Override portfolio settings for optimized aggressive profile
                self.portfolio.min_position_size = 0.12   # 12% minimum for optimized
                self.portfolio.max_position_size = 0.30   # 30% maximum for optimized
                self.portfolio.risk_per_trade_pct = 0.018  # 1.8% risk per trade
                self.portfolio.atr_stop_multiplier = 1.9   # Optimized stops
                self.portfolio.atr_target_multiplier = 4.5  # Higher targets
                self.portfolio.trailing_activation_multiplier = 1.4
                self.portfolio.trailing_stop_multiplier = 0.65
                logger.info("⚡ Optimized Aggressive profile applied to portfolio settings")

        # Adjust strategies based on mode
        if trading_mode == 'live':
            # Conservative strategies for live trading
            self.strategies = [
                ImprovedMovingAverageCrossover(5, 15),  # Slower signals
                EnhancedRSIStrategy(14, 30, 70),       # More conservative RSI
                BollingerBandsStrategy(20, 2),
                EnhancedMomentumStrategy(15, 10, 0.02, 0.005, 35, 65, 15, 25),  # Conservative momentum for live
            ]
            self.aggregator = EnhancedSignalAggregator(min_agreement=0.4)  # Higher agreement
            self.max_positions = min(max_positions or self.system_config.risk.max_positions, 10)  # Conservative position limit
            self.cooldown_minutes = 30  # Longer cooldown
        else:
            # Full strategies for paper/backtest
            self.strategies = [
                ImprovedMovingAverageCrossover(3, 10),
                EnhancedRSIStrategy(7, 25, 75),
                BollingerBandsStrategy(20, 2),
                ImprovedVolumeBreakoutStrategy(1.3, 0.001),
                EnhancedMomentumStrategy(10, 7, 0.015, 0.003, 30, 70, 12, 20)  # Enhanced momentum with better signal quality
            ]
            # Adjust aggregator settings based on profile
            if trading_mode == 'paper' and self.config.get('trading_profile') == 'Aggressive':
                self.aggregator = EnhancedSignalAggregator(min_agreement=0.1)  # Lower agreement for aggressive
            else:
                self.aggregator = EnhancedSignalAggregator(min_agreement=0.4)
            # Apply profile-specific max positions for paper trading
        if trading_mode == 'paper' and self.config.get('trading_profile') == 'Aggressive':
            self.max_positions = self.config['max_positions']
        else:
            self.max_positions = max_positions or self.system_config.risk.max_positions
        self.cooldown_minutes = 10

        # Initialize aggregator with neutral market bias by default
        if hasattr(self, 'aggregator') and self.aggregator:
            self.aggregator.update_market_regime({'regime': 'neutral', 'bias': 'neutral'})

        self.symbols: List[str] = []

        # Default index tokens for trend analysis (loaded from unified config)
        self.market_index_tokens = self.system_config.market_indexes

        self.advanced_market_manager = AdvancedMarketManager(
            self.config,
            kite=self.kite,
            index_tokens=self.market_index_tokens
        )
        self.position_cooldown: Dict[str, datetime] = {}

        # Auto-adjustment settings
        self.auto_adjustment_enabled = True
        self.auto_stop_time = datetime.strptime(self.system_config.market_hours.end, "%H:%M").time()
        self.auto_stop_executed_today = False
        self.next_day_adjustments = {}  # Store adjustments for next day

        # Initialize Backtest Engine
        self.backtest_engine = BacktestEngine(self.dp, self.portfolio.initial_cash)

        # Persistence helpers
        state_dir = self.config.get('state_dir')
        try:
            self.state_manager = TradingStateManager(state_dir, security_context=self.security_context)
        except RuntimeError as exc:
            logger.critical(f"State manager initialization failed: {exc}")
            raise
        self.last_archive_day = None
        self.restored_state = False
        self.iteration_start = 0
        self.last_state_snapshot = None
        self.day_close_executed = None

        # PERFORMANCE FIX: State persistence throttling
        self._state_dirty = False  # Track if state changed
        self._last_state_persist = 0.0  # Timestamp of last persist
        self._min_persist_interval = 30.0  # Minimum seconds between persists (30s)
        self._state_changes_count = 0  # Track number of changes since last persist

        self._restore_saved_state()

        logger.info("🎯 UNIFIED TRADING SYSTEM INITIALIZED")
        logger.info(f"Mode: {trading_mode.upper()}")
        logger.info(f"Strategies: {len(self.strategies)}")
        logger.info(f"Max Positions: {self.max_positions}")

        # Additional risk controls
        self.stop_loss_cooldown_minutes = self.config.get('stop_loss_cooldown_minutes', max(self.cooldown_minutes * 2, 20))
        logger.info(f"Cooldown after stop-loss: {self.stop_loss_cooldown_minutes} minutes")

    def add_symbols(self, symbols: List[str]) -> None:
        """Add symbols for trading"""
        for symbol in symbols:
            s = validate_symbol(symbol)
            if s and s not in self.symbols:
                self.symbols.append(s)

    def run_fast_backtest(self, interval: str = "5minute", days: int = 30) -> None:
        """
        Run high-performance vectorized backtest
        """
        self.backtest_engine.run_fast_backtest(self.symbols, interval, days)



    def _restore_saved_state(self) -> None:
        saved_state = self.state_manager.load_state()
        if not saved_state:
            logger.info("💾 No saved trading state found – starting fresh.")
            return

        saved_mode = saved_state.get('mode')
        if saved_mode and saved_mode != self.trading_mode:
            logger.warning(f"Saved trading state is for mode '{saved_mode}', current mode '{self.trading_mode}'. Ignoring saved data.")
            return

        try:
            self.portfolio.load_from_dict(saved_state.get('portfolio', {}))
            self.iteration_start = int(saved_state.get('iteration', 0))
            self.last_archive_day = saved_state.get('last_archive_day')
            self.day_close_executed = saved_state.get('day_close_executed')

            cooldowns = {}
            now = datetime.now()
            for symbol, ts in saved_state.get('position_cooldown', {}).items():
                try:
                    dt_obj = datetime.fromisoformat(ts)
                    if dt_obj > now:
                        cooldowns[symbol] = dt_obj
                except Exception:
                    continue
            self.position_cooldown.update(cooldowns)

            self.restored_state = True
            self.last_state_snapshot = saved_state
            logger.info(
                f"💾 Restored trading state: iteration {self.iteration_start}, "
                f"cash ₹{self.portfolio.cash:,.2f}, open positions {len(self.portfolio.positions)}"
            )
        except Exception as exc:
            logger.error(f"Failed to apply saved trading state: {exc}")
            self.iteration_start = 0
            self.last_archive_day = None
            self.restored_state = False

    def _serialize_cooldowns(self) -> Dict:
        serialized = {}
        for symbol, dt_obj in self.position_cooldown.items():
            if isinstance(dt_obj, datetime):
                serialized[symbol] = dt_obj.isoformat()
        return serialized

    def _build_state_snapshot(self, iteration: int, total_value: float, price_map: Dict) -> Dict:
        trading_day = self.state_manager.current_trading_day()
        return {
            'mode': self.trading_mode,
            'iteration': int(iteration),
            'trading_day': trading_day,
            'last_update': datetime.now().isoformat(),
            'portfolio': self.portfolio.to_dict(),
            'position_cooldown': self._serialize_cooldowns(),
            'total_value': float(total_value),
            'last_prices': {symbol: float(price) for symbol, price in (price_map or {}).items()},
            'last_archive_day': self.last_archive_day,
            'day_close_executed': self.day_close_executed
        }

    def _persist_state(self, iteration: int, total_value: float, price_map: Dict, force: bool = False) -> None:
        """
        Persist state with throttling to reduce I/O

        PERFORMANCE FIX: Only persist if:
        - Force flag is set (critical moments like shutdown)
        - State is dirty AND throttle interval passed
        - End of day (for archival)

        Args:
            iteration: Current iteration number
            total_value: Portfolio total value
            price_map: Current price map
            force: Force immediate persist regardless of throttle
        """
        import time as time_module

        current_time = time_module.time()
        now_ist = datetime.now(self.state_manager.ist)

        # Build state snapshot
        state = self._build_state_snapshot(iteration, total_value, price_map)
        trading_day = state['trading_day']

        # Always archive at end of day
        if now_ist.time() >= self.market_hours.market_close:
            if self.last_archive_day != trading_day:
                self.state_manager.archive_state(state)
                self.last_archive_day = trading_day
                state['last_archive_day'] = trading_day
                logger.info(f"💾 Archived trading state for {trading_day}")
                # Force persist after archival
                force = True

        # Check if we should persist
        time_since_last_persist = current_time - self._last_state_persist
        should_persist = (
            force or
            (self._state_dirty and time_since_last_persist >= self._min_persist_interval)
        )

        if should_persist:
            self.state_manager.save_state(state)
            self.last_state_snapshot = state
            self._state_dirty = False
            self._last_state_persist = current_time
            self._state_changes_count = 0

            # Track metrics if available
            if hasattr(self.portfolio, 'increment_metric'):
                self.portfolio.increment_metric('state_saves')

            logger.debug(f"💾 State persisted (throttled: {time_since_last_persist:.1f}s since last)")
        else:
            # State changed but throttled
            self._state_dirty = True
            self._state_changes_count += 1

            # Track skipped saves
            if hasattr(self.portfolio, 'increment_metric'):
                self.portfolio.increment_metric('state_saves_skipped')

            logger.debug(f"⏭️  State persist skipped (throttle: {time_since_last_persist:.1f}s < {self._min_persist_interval}s, changes: {self._state_changes_count})")

    def mark_state_dirty(self):
        """Mark state as changed (for throttling logic)"""
        self._state_dirty = True
        self._state_changes_count += 1

    def _broadcast_restored_state(self) -> None:
        if not self.restored_state:
            return

        snapshot = self.last_state_snapshot or {}
        price_map = snapshot.get('last_prices', {})
        total_value = snapshot.get('total_value')
        if total_value is None:
            total_value = self.portfolio.calculate_total_value(price_map)

        pnl = total_value - self.portfolio.initial_cash
        win_rate = 0.0
        if self.portfolio.trades_count > 0:
            win_rate = (self.portfolio.winning_trades / self.portfolio.trades_count) * 100

        logger.info(
            f"🔁 Resuming session from iteration {self.iteration_start} | "
            f"Portfolio ₹{total_value:,.2f} | Cash ₹{self.portfolio.cash:,.2f} | "
            f"Positions {len(self.portfolio.positions)}"
        )

        if self.dashboard:
            positions_payload = {}
            for symbol, pos in self.portfolio.positions.items():
                current_price = price_map.get(symbol, pos["entry_price"])
                shares_held = pos["shares"]
                if shares_held >= 0:
                    cost_basis = float(pos.get('invested_amount', pos["entry_price"] * shares_held))
                    position_value = current_price * shares_held
                    unrealized_pnl = position_value - cost_basis
                else:
                    unrealized_pnl = (pos["entry_price"] - current_price) * abs(shares_held)
                positions_payload[symbol] = {
                    "shares": shares_held,
                    "entry_price": pos["entry_price"],
                    "current_price": current_price,
                    "unrealized_pnl": unrealized_pnl,
                    "sector": pos.get("sector", "Other")
                }

            self.dashboard.send_portfolio_update(
                total_value=total_value,
                cash=self.portfolio.cash,
                positions_count=len(self.portfolio.positions),
                total_pnl=pnl,
                positions=positions_payload
            )

            if self.portfolio.trades_count > 0:
                self.dashboard.send_performance_update(
                    trades_count=self.portfolio.trades_count,
                    win_rate=win_rate,
                    total_pnl=self.portfolio.total_pnl,
                    best_trade=self.portfolio.best_trade,
                    worst_trade=self.portfolio.worst_trade
                )

            self.dashboard.send_system_status(True, self.iteration_start, "resumed")

    def analyze_market_conditions_for_adjustment(self, symbol: str) -> Dict:
        """Analyze market conditions to determine if trade adjustments are needed"""
        try:
            # Fetch recent data for analysis
            df = self.dp.fetch_with_retry(symbol, interval="1day", days=5)
            if df.empty:
                return {'adjustment': 'hold', 'reason': 'no_data'}

            current_price = safe_float_conversion(df["close"].iloc[-1])
            yesterday_price = safe_float_conversion(df["close"].iloc[-2]) if len(df) > 1 else current_price

            # Calculate price change
            price_change_pct = ((current_price - yesterday_price) / yesterday_price) * 100

            # Calculate volatility
            if len(df) >= 5:
                returns = df['close'].pct_change().dropna()
                volatility = returns.std() * 100
            else:
                volatility = 2.0  # Default volatility

            # Decision logic based on market conditions
            if abs(price_change_pct) > 3:  # High price movement
                if price_change_pct > 3:
                    return {'adjustment': 'increase', 'reason': 'strong_bullish', 'factor': 1.2}
                else:
                    return {'adjustment': 'decrease', 'reason': 'strong_bearish', 'factor': 0.8}
            elif volatility > 3:  # High volatility
                return {'adjustment': 'decrease', 'reason': 'high_volatility', 'factor': 0.9}
            else:
                return {'adjustment': 'hold', 'reason': 'stable_market'}

        except Exception as e:
            logger.error(f"Error analyzing market conditions for {symbol}: {e}")
            return {'adjustment': 'hold', 'reason': 'analysis_error'}

    def adjust_trades_for_next_day(self):
        """Automatically adjust open trades based on market conditions"""
        if not self.auto_adjustment_enabled:
            return

        logger.info("🔄 Analyzing open positions for next-day adjustments...")

        adjustments_made = 0
        for symbol, position in list(self.portfolio.positions.items()):
            shares = int(position.get('shares', 0))
            if shares == 0:
                continue

            # Analyze market conditions for this symbol
            analysis = self.analyze_market_conditions_for_adjustment(symbol)
            adjustment_type = analysis.get('adjustment', 'hold')

            if adjustment_type == 'hold':
                continue

            # Calculate adjustment
            original_shares = shares
            if adjustment_type == 'increase':
                factor = analysis.get('factor', 1.2)
                new_shares = int(shares * factor)
                additional_shares = new_shares - shares

                if additional_shares > 0:
                    # Get current price for the additional purchase
                    try:
                        df = self.dp.fetch_with_retry(symbol, interval="5minute", days=1)
                        if not df.empty:
                            current_price = safe_float_conversion(df["close"].iloc[-1])

                            # Execute additional buy
                            trade = self.portfolio.execute_trade(
                                symbol, additional_shares, current_price, 'buy',
                                datetime.now(), 0.7, position.get('sector', 'Other'),
                                allow_immediate_sell=True, strategy='next_day_adjustment'
                            )

                            if trade:
                                logger.info(f"📈 Increased position in {symbol}: +{additional_shares} shares due to {analysis['reason']}")
                                adjustments_made += 1
                    except Exception as e:
                        logger.error(f"Error increasing position for {symbol}: {e}")

            elif adjustment_type == 'decrease':
                factor = analysis.get('factor', 0.8)
                new_shares = int(shares * factor)
                shares_to_sell = shares - new_shares

                if shares_to_sell > 0:
                    # Get current price for partial sale
                    try:
                        df = self.dp.fetch_with_retry(symbol, interval="5minute", days=1)
                        if not df.empty:
                            current_price = safe_float_conversion(df["close"].iloc[-1])

                            # Execute partial sell
                            trade = self.portfolio.execute_trade(
                                symbol, shares_to_sell, current_price, 'sell',
                                datetime.now(), 0.7, position.get('sector', 'Other'),
                                allow_immediate_sell=True, strategy='next_day_adjustment'
                            )

                            if trade:
                                logger.info(f"📉 Decreased position in {symbol}: -{shares_to_sell} shares due to {analysis['reason']}")
                                adjustments_made += 1
                    except Exception as e:
                        logger.error(f"Error decreasing position for {symbol}: {e}")

        if adjustments_made > 0:
            logger.info(f"✅ Completed {adjustments_made} position adjustments based on market conditions")
        else:
            logger.info("📊 No position adjustments needed - market conditions are stable")

    def auto_stop_all_trades(self, current_time: datetime = None):
        """Automatically save all trades at 3:30 PM for next day"""
        if current_time is None:
            current_time = datetime.now(self.market_hours.ist)

        # Check if it's 3:30 PM and we haven't executed auto-stop today
        if (current_time.time() >= self.auto_stop_time and
            not self.auto_stop_executed_today):

            logger.info("💾 AUTO-SAVE TRIGGERED: Saving all positions for next trading day at 3:30 PM")

            positions_saved = 0
            current_day = current_time.strftime('%Y-%m-%d')
            next_day = (current_time + timedelta(days=1)).strftime('%Y-%m-%d')

            # Save current positions for next day
            saved_positions = {}

            for symbol, position in list(self.portfolio.positions.items()):
                shares = int(position.get('shares', 0))
                if shares == 0:
                    continue

                try:
                    # Get current market price for valuation
                    df = self.dp.fetch_with_retry(symbol, interval="5minute", days=1)
                    if not df.empty:
                        current_price = safe_float_conversion(df["close"].iloc[-1])
                    else:
                        current_price = position.get('entry_price', 0)

                    if current_price <= 0:
                        current_price = position.get('entry_price', 0)

                    # Derive cost basis for accurate unrealized P&L
                    invested_amount = float(position.get('invested_amount', position.get('entry_price', current_price) * abs(shares)))
                    if shares >= 0:
                        position_value = current_price * shares
                        unrealized_pnl = position_value - invested_amount
                    else:
                        entry_price = position.get('entry_price', current_price)
                        unrealized_pnl = (entry_price - current_price) * abs(shares)

                    # Save position data for next day
                    saved_position = {
                        'symbol': symbol,
                        'shares': shares,
                        'entry_price': position.get('entry_price', current_price),
                        'current_price': current_price,
                        'sector': position.get('sector', 'Other'),
                        'confidence': position.get('confidence', 0.8),
                        'entry_time': position.get('entry_time', current_time).isoformat() if isinstance(position.get('entry_time'), datetime) else str(position.get('entry_time', current_time)),
                        'saved_at': current_time.isoformat(),
                        'saved_for_day': next_day,
                        'strategy': position.get('strategy', 'carry_forward'),
                        'unrealized_pnl': unrealized_pnl,
                        'invested_amount': invested_amount
                    }

                    saved_positions[symbol] = saved_position
                    positions_saved += 1

                    logger.info(f"💾 Saved position for next day: {symbol} - {shares} shares @ ₹{current_price:.2f} (Unrealized P&L: ₹{saved_position['unrealized_pnl']:.2f})")

                except Exception as e:
                    logger.error(f"Error saving position for {symbol}: {e}")

            # Save to file for next day restoration
            if saved_positions:
                self.save_positions_for_next_day(saved_positions, next_day)

            self.auto_stop_executed_today = True

            if positions_saved > 0:
                logger.info(f"💾 AUTO-SAVE COMPLETE: Saved {positions_saved} positions for next trading day ({next_day})")

                # Send dashboard notification if available
                if self.dashboard:
                    self.dashboard.send_system_status(
                        True, 0, f"auto_save_complete_{positions_saved}_positions"
                    )
            else:
                logger.info("💾 AUTO-SAVE: No positions to save")

    def save_positions_for_next_day(self, saved_positions: Dict, next_day: str):
        """Save positions to file for next day restoration"""
        try:
            import os
            import json

            # Create saved_trades directory
            os.makedirs('saved_trades', exist_ok=True)

            # Save positions with next day date as filename
            filename = f"saved_trades/positions_{next_day}.json"

            save_data = {
                'positions': saved_positions,
                'saved_at': datetime.now().isoformat(),
                'target_date': next_day,
                'total_positions': len(saved_positions),
                'total_value': sum(pos['current_price'] * pos['shares'] for pos in saved_positions.values()),
                'total_unrealized_pnl': sum(pos['unrealized_pnl'] for pos in saved_positions.values())
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2)

            logger.info(f"💾 Positions saved to {filename}")
            logger.info(f"💰 Total value: ₹{save_data['total_value']:,.2f}, Unrealized P&L: ₹{save_data['total_unrealized_pnl']:,.2f}")

        except Exception as e:
            logger.error(f"Error saving positions to file: {e}")

    def restore_positions_for_day(self, target_day: str = None) -> bool:
        """Restore saved positions for the current/target day"""
        try:
            import os
            import json

            if target_day is None:
                target_day = datetime.now().strftime('%Y-%m-%d')

            filename = f"saved_trades/positions_{target_day}.json"

            if not os.path.exists(filename):
                logger.info(f"📂 No saved positions found for {target_day}")
                return False

            with open(filename, 'r') as f:
                save_data = json.load(f)

            saved_positions = save_data.get('positions', {})

            if not saved_positions:
                logger.info(f"📂 No positions in saved file for {target_day}")
                return False

            logger.info(f"🔄 Restoring {len(saved_positions)} positions for {target_day}")

            restored_count = 0
            total_value = 0.0
            total_unrealized_pnl = 0.0

            for symbol, saved_pos in saved_positions.items():
                try:
                    # Get current market price
                    current_price = saved_pos['current_price']  # Start with saved price

                    try:
                        df = self.dp.fetch_with_retry(symbol, interval="5minute", days=1)
                        if not df.empty:
                            current_price = safe_float_conversion(df["close"].iloc[-1])
                    except Exception:
                        pass  # Use saved price if can't get current

                    invested_amount = float(saved_pos.get('invested_amount', saved_pos['entry_price'] * saved_pos['shares']))

                    # Restore position to portfolio
                    restored_position = {
                        'shares': saved_pos['shares'],
                        'entry_price': saved_pos['entry_price'],
                        'sector': saved_pos['sector'],
                        'confidence': saved_pos['confidence'],
                        'entry_time': datetime.fromisoformat(saved_pos['entry_time'].replace('Z', '+00:00')) if 'T' in saved_pos['entry_time'] else datetime.now(),
                        'strategy': saved_pos.get('strategy', 'restored'),
                        'restored_from': saved_pos['saved_for_day'],
                        'invested_amount': invested_amount
                    }

                    # Add to portfolio positions
                    self.portfolio.positions[symbol] = restored_position

                    # Update position entry times
                    if symbol not in self.portfolio.position_entry_times:
                        self.portfolio.position_entry_times[symbol] = restored_position['entry_time']

                    shares_held = saved_pos['shares']
                    current_value = current_price * shares_held
                    if shares_held >= 0:
                        unrealized_pnl = current_value - invested_amount
                    else:
                        unrealized_pnl = (saved_pos['entry_price'] - current_price) * abs(shares_held)

                    total_value += current_value
                    total_unrealized_pnl += unrealized_pnl
                    restored_count += 1

                    logger.info(f"🔄 Restored: {symbol} - {saved_pos['shares']} shares @ ₹{saved_pos['entry_price']:.2f} (Current: ₹{current_price:.2f}, P&L: ₹{unrealized_pnl:.2f})")

                except Exception as e:
                    logger.error(f"Error restoring position for {symbol}: {e}")

            if restored_count > 0:
                logger.info(f"✅ Successfully restored {restored_count} positions")
                logger.info(f"💰 Total portfolio value: ₹{total_value:,.2f}")
                logger.info(f"📊 Total unrealized P&L: ₹{total_unrealized_pnl:,.2f}")

                # Archive the used file
                archive_filename = f"saved_trades/positions_{target_day}_used.json"
                os.rename(filename, archive_filename)
                logger.info(f"📁 Archived used save file to {archive_filename}")

                return True
            else:
                logger.warning(f"⚠️ No positions could be restored for {target_day}")
                return False

        except Exception as e:
            logger.error(f"Error restoring positions: {e}")
            return False

    def user_stop_and_save_trades(self, reason: str = "user_stop"):
        """Manual stop that saves all trades for next day"""
        logger.info("👤 USER STOP TRIGGERED: Saving all positions for next trading day")

        current_time = datetime.now(self.market_hours.ist)
        next_day = (current_time + timedelta(days=1)).strftime('%Y-%m-%d')

        positions_saved = 0
        saved_positions = {}

        for symbol, position in list(self.portfolio.positions.items()):
            shares = int(position.get('shares', 0))
            if shares == 0:
                continue

            try:
                # Get current market price
                df = self.dp.fetch_with_retry(symbol, interval="5minute", days=1)
                if not df.empty:
                    current_price = safe_float_conversion(df["close"].iloc[-1])
                else:
                    current_price = position.get('entry_price', 0)

                if current_price <= 0:
                    current_price = position.get('entry_price', 0)

                invested_amount = float(position.get('invested_amount', position.get('entry_price', current_price) * abs(shares)))
                if shares >= 0:
                    position_value = current_price * shares
                    unrealized_pnl = position_value - invested_amount
                else:
                    entry_price = position.get('entry_price', current_price)
                    unrealized_pnl = (entry_price - current_price) * abs(shares)

                # Save position data
                saved_position = {
                    'symbol': symbol,
                    'shares': shares,
                    'entry_price': position.get('entry_price', current_price),
                    'current_price': current_price,
                    'sector': position.get('sector', 'Other'),
                    'confidence': position.get('confidence', 0.8),
                    'entry_time': position.get('entry_time', current_time).isoformat() if isinstance(position.get('entry_time'), datetime) else str(position.get('entry_time', current_time)),
                    'saved_at': current_time.isoformat(),
                    'saved_for_day': next_day,
                    'strategy': position.get('strategy', 'user_saved'),
                    'unrealized_pnl': unrealized_pnl,
                    'save_reason': reason,
                    'invested_amount': invested_amount
                }

                saved_positions[symbol] = saved_position
                positions_saved += 1

                logger.info(f"💾 User saved: {symbol} - {shares} shares @ ₹{current_price:.2f} (P&L: ₹{saved_position['unrealized_pnl']:.2f})")

            except Exception as e:
                logger.error(f"Error saving position for {symbol}: {e}")

        # Save to file
        if saved_positions:
            self.save_positions_for_next_day(saved_positions, next_day)
            logger.info(f"👤 USER STOP COMPLETE: Saved {positions_saved} positions for next trading day ({next_day})")
        else:
            logger.info("👤 USER STOP: No positions to save")

        return positions_saved

    def _close_positions_for_day(self, price_map: Dict, iteration: int, current_day: str) -> bool:
        if self.day_close_executed == current_day:
            return False

        had_positions = bool(self.portfolio.positions)

        now_ist = datetime.now(self.state_manager.ist)
        close_time = now_ist.replace(
            hour=self.market_hours.market_close.hour,
            minute=self.market_hours.market_close.minute,
            second=0,
            microsecond=0
        )
        if now_ist >= close_time:
            trigger = "market_close"
        else:
            trigger = "scheduled"

        if had_positions:
            expiring_positions = []
            non_expiring_positions = []

            # Categorize positions by expiry
            for symbol, position in list(self.portfolio.positions.items()):
                if self.is_expiring_today(symbol):
                    expiring_positions.append((symbol, position))
                else:
                    non_expiring_positions.append((symbol, position))

            # Handle expiring positions - must be closed
            if expiring_positions:
                logger.info(f"🔔 Closing {len(expiring_positions)} expiring positions at market close...")
                for symbol, position in expiring_positions:
                    shares = int(position["shares"])
                    if shares == 0:
                        continue

                    current_price = price_map.get(symbol)
                    if current_price is None:
                        try:
                            df = self.dp.fetch_with_retry(symbol, interval="5minute", days=1)
                            if not df.empty:
                                current_price = safe_float_conversion(df["close"].iloc[-1])
                        except Exception:
                            current_price = None

                    if current_price is None or current_price <= 0:
                        current_price = position.get("entry_price", 0)

                    # Execute trade to close expiring position
                    trade = self.portfolio.execute_trade(
                        symbol,
                        abs(shares),  # Close position regardless of long/short
                        current_price,
                        "sell" if shares > 0 else "buy",  # Opposite action to close
                        datetime.now(),
                        position.get("confidence", 0.5),
                        position.get("sector", "F&O")
                    )
                    if trade:
                        trade['iteration'] = iteration
                        trade['reason'] = 'expiry_close'
                        trade['trigger'] = trigger
                        self.state_manager.log_trade(trade, trading_day=current_day)
                        logger.info(f"💰 Closed expiring position: {symbol} - P&L: ₹{trade.get('pnl', 0):.2f}")

            # Handle non-expiring positions - preserve for next day
            if non_expiring_positions:
                logger.info(f"📋 Preserving {len(non_expiring_positions)} non-expiring positions for next trading day...")
                for symbol, position in non_expiring_positions:
                    logger.info(f"  → {symbol}: {position['shares']} shares @ ₹{position['entry_price']:.2f}")

            # Only close non-expiring positions if specifically configured to do so
            # By default, preserve them for next day
            close_all_positions = False  # Can be made configurable
            if close_all_positions and non_expiring_positions:
                logger.info("🔔 Also closing non-expiring positions as configured...")
                for symbol, position in non_expiring_positions:
                    shares = int(position["shares"])
                    if shares == 0:
                        continue

                    current_price = price_map.get(symbol)
                    if current_price is None:
                        try:
                            df = self.dp.fetch_with_retry(symbol, interval="5minute", days=1)
                            if not df.empty:
                                current_price = safe_float_conversion(df["close"].iloc[-1])
                        except Exception:
                            current_price = None

                    if current_price is None or current_price <= 0:
                        current_price = position.get("entry_price", 0)

                    trade = self.portfolio.execute_trade(
                        symbol,
                        abs(shares),
                        current_price,
                        "sell" if shares > 0 else "buy",
                        datetime.now(),
                        position.get("confidence", 0.5),
                        position.get("sector", "Other")
                    )
                    if trade:
                        trade['iteration'] = iteration
                        trade['reason'] = 'day_end_close'
                        trade['trigger'] = trigger
                        self.state_manager.log_trade(trade, trading_day=current_day)

        self.day_close_executed = current_day
        total_value = self.portfolio.calculate_total_value(price_map)
        pnl = total_value - self.portfolio.initial_cash
        win_rate = 0.0
        if self.portfolio.trades_count > 0:
            win_rate = (self.portfolio.winning_trades / self.portfolio.trades_count) * 100

        summary = {
            'trading_day': current_day,
            'closed_at': datetime.now().isoformat(),
            'total_value': total_value,
            'cash': self.portfolio.cash,
            'open_positions': len(self.portfolio.positions),
            'trades_count': self.portfolio.trades_count,
            'win_rate': win_rate,
            'total_pnl': self.portfolio.total_pnl,
            'best_trade': self.portfolio.best_trade,
            'worst_trade': self.portfolio.worst_trade
        }
        self.state_manager.write_daily_summary(current_day, summary)

        # CRITICAL: Archive all trades at end of day
        try:
            logger.info("📦 Starting end-of-day trade archival...")
            archive_result = self.portfolio.archive_end_of_day_trades()

            if archive_result['status'] == 'success':
                logger.info(
                    f"✅ Trade archival complete: {archive_result['trade_count']} trades → "
                    f"{archive_result['file_path']}"
                )
            elif archive_result['status'] == 'no_trades':
                logger.info("ℹ️  No trades to archive for today")
            else:
                logger.error(f"❌ Trade archival failed: {archive_result.get('errors')}")
        except Exception as archive_error:
            logger.error(f"❌ CRITICAL: Trade archival crashed: {archive_error}")
            traceback.print_exc()

        # Persist only the open positions for next trading day
        try:
            current_snapshot_time = now_ist
            carry_forward_day = (current_snapshot_time + timedelta(days=1)).strftime('%Y-%m-%d')
            open_positions_snapshot: Dict[str, Dict[str, Any]] = {}

            for symbol, position in list(self.portfolio.positions.items()):
                shares = int(position.get('shares', 0))
                if shares == 0:
                    continue

                current_price = price_map.get(symbol)
                if current_price is not None:
                    current_price = safe_float_conversion(current_price)
                if current_price is None:
                    try:
                        df = self.dp.fetch_with_retry(symbol, interval="5minute", days=1)
                        if not df.empty:
                            current_price = safe_float_conversion(df["close"].iloc[-1])
                    except Exception:
                        current_price = None

                fallback_entry_price = position.get("entry_price", current_price if current_price is not None else 0)
                fallback_entry_price = safe_float_conversion(fallback_entry_price) if fallback_entry_price is not None else 0.0

                if current_price is None or current_price <= 0:
                    current_price = fallback_entry_price

                invested_amount = float(
                    position.get(
                        'invested_amount',
                        fallback_entry_price * abs(shares)
                    )
                )
                if shares >= 0:
                    position_value = current_price * shares
                    unrealized_pnl = position_value - invested_amount
                else:
                    unrealized_pnl = (fallback_entry_price - current_price) * abs(shares)

                entry_time = position.get('entry_time')
                if isinstance(entry_time, datetime):
                    entry_time_iso = entry_time.isoformat()
                elif entry_time:
                    entry_time_iso = str(entry_time)
                else:
                    entry_time_iso = current_snapshot_time.isoformat()

                saved_position = {
                    'symbol': symbol,
                    'shares': shares,
                    'entry_price': fallback_entry_price,
                    'current_price': current_price,
                    'sector': position.get('sector', 'Other'),
                    'confidence': position.get('confidence', 0.8),
                    'entry_time': entry_time_iso,
                    'saved_at': current_snapshot_time.isoformat(),
                    'saved_for_day': carry_forward_day,
                    'strategy': position.get('strategy', 'carry_forward'),
                    'unrealized_pnl': unrealized_pnl,
                    'invested_amount': invested_amount
                }

                position_type = position.get('position_type')
                if position_type:
                    saved_position['position_type'] = position_type

                open_positions_snapshot[symbol] = saved_position

            if open_positions_snapshot:
                self.save_positions_for_next_day(open_positions_snapshot, carry_forward_day)
                logger.info(
                    f"💾 Day-end snapshot saved: {len(open_positions_snapshot)} open positions → "
                    f"saved_trades/positions_{carry_forward_day}.json"
                )
            else:
                logger.info("💾 Day-end snapshot: No open positions to save")
        except Exception as snapshot_error:
            logger.error(f"❌ Failed to save day-end open positions: {snapshot_error}", exc_info=True)

        if self.dashboard:
            self.dashboard.send_portfolio_update(
                total_value=total_value,
                cash=self.portfolio.cash,
                positions_count=len(self.portfolio.positions),
                total_pnl=pnl,
                positions={}
            )
            self.dashboard.send_system_status(True, iteration, "day_end")

        return had_positions

    def get_sector(self, symbol: str) -> str:
        """Get sector for symbol"""
        for sector, symbols in SECTOR_GROUPS.items():
            if symbol in symbols:
                return sector
        return "Other"

    def extract_expiry_date(self, symbol: str) -> Optional[datetime]:
        """Extract expiry date from symbol using market manager parser."""
        base_symbol = symbol[:-6] if symbol.endswith('_SHORT') else symbol

        reference_date = datetime.now(self.state_manager.ist).date() if hasattr(self, 'state_manager') else datetime.now().date()

        if hasattr(self, 'advanced_market_manager') and hasattr(self.advanced_market_manager, '_determine_expiry_date'):
            try:
                expiry_date = self.advanced_market_manager._determine_expiry_date(base_symbol, reference_date)
                if expiry_date:
                    return datetime.combine(expiry_date, datetime.min.time())
            except Exception as exc:
                logger.debug(f"Expiry parse fallback triggered for {base_symbol}: {exc}")

        # Fallback: basic regex for monthly style symbols
        match = re.search(r'(\d{2})([A-Z]{1,3})(\d{2})', base_symbol)
        if not match:
            return None

        year = 2000 + int(match.group(3))
        month_code = match.group(2)
        day = int(match.group(1))

        month_map = {
            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
        }

        month = month_map.get(month_code[:3])
        if not month:
            return None

        try:
            return datetime(year, month, day)
        except ValueError:
            return None

    def is_expiring_today(self, symbol: str) -> bool:
        """Check if option expires today"""
        base_symbol = symbol[:-6] if symbol.endswith('_SHORT') else symbol
        expiry_date = self.extract_expiry_date(base_symbol)
        if not expiry_date:
            return False

        today = datetime.now().date()
        return expiry_date.date() == today

    def scan_batch(self, batch: List[str], interval: str, batch_num: int, total_batches: int) -> Tuple[Dict, Dict]:
        """Scan a batch of symbols for signals"""
        signals = {}
        prices = {}
        logger.info(f"  Batch {batch_num}/{total_batches}: {', '.join(batch[:3])}...")

        for symbol in batch:
            try:
                df = self.dp.fetch_with_retry(symbol, interval=interval, days=5)
                if df.empty or len(df) < 50:
                    continue

                current_price = safe_float_conversion(df["close"].iloc[-1])
                prices[symbol] = current_price

                # Generate signals from all strategies
                strategy_signals = []
                for strategy in self.strategies:
                    sig = strategy.generate_signals(df, symbol)
                    strategy_signals.append(sig)

                # Check if this is an exit signal for existing position
                is_exit_signal = symbol in self.portfolio.positions

                # Aggregate signals (pass is_exit to allow exits regardless of regime)
                aggregated = self.aggregator.aggregate_signals(strategy_signals, symbol, is_exit=is_exit_signal)

                if aggregated['action'] != 'hold':
                    # Debug logging to show all signals
                    sector = self.get_sector(symbol)
                    logger.info(f"    {symbol} ({sector}): {aggregated['action'].upper()} @ ₹{current_price:.2f} ({aggregated['confidence']:.1%}) - {aggregated.get('reasons', ['N/A'])}")

                    # Disable trend filter for aggressive profile to allow more trades
                    if not hasattr(self, 'config') or self.config is None:
                        trend_filter_enabled = self.trading_mode != 'backtest'
                        trading_profile = None
                    else:
                        trend_filter_enabled = self.config.get('trend_filter_enabled', self.trading_mode != 'backtest')
                        trading_profile = self.config.get('trading_profile')

                    # CRITICAL FIX: Skip trend filter for exits (position liquidations)
                    # Only apply trend filter to NEW entry signals, not existing position exits
                    if trend_filter_enabled and not (self.trading_mode == 'paper' and trading_profile == 'Aggressive') and not is_exit_signal:
                        ema_fast = safe_float_conversion(df['close'].ewm(span=20, adjust=False).mean().iloc[-1])
                        ema_slow = safe_float_conversion(df['close'].ewm(span=50, adjust=False).mean().iloc[-1])
                        if is_zero(ema_fast) or is_zero(ema_slow):
                            logger.info(f"    {symbol}: Skipping due to NaN trend data")
                            continue
                        downtrend = current_price < ema_slow and ema_fast < ema_slow
                        uptrend = current_price > ema_slow and ema_fast > ema_slow

                        if aggregated['action'] == 'sell' and not downtrend:
                            logger.info(f"    {symbol}: Sell entry blocked - not in downtrend (new position only)")
                            continue
                        if aggregated['action'] == 'buy' and not uptrend:  # STRICTER: Always require uptrend for buys
                            logger.info(f"    {symbol}: Buy entry blocked - not in uptrend (new position only)")
                            continue

                    # Check minimum confidence threshold - ensure config is available
                    if not hasattr(self, 'config') or self.config is None:
                        logger.warning("Config not available, using default min_confidence")
                        min_confidence = 0.65  # INCREASED: Higher default (was 0.35)
                    else:
                        min_confidence = self.config.get('min_confidence', 0.65)  # INCREASED default (was 0.35)

                    # Ensure min_confidence is always defined
                    if 'min_confidence' not in locals():
                        min_confidence = 0.65  # INCREASED: Higher default (was 0.35)

                    # CRITICAL FIX: Don't filter exits by confidence - always allow position liquidations
                    # Only apply confidence threshold to NEW entry signals
                    if not is_exit_signal and aggregated['confidence'] < min_confidence:
                        logger.info(f"    {symbol}: Entry signal confidence {aggregated['confidence']:.1%} below threshold {min_confidence:.1%} (new position only)")
                        continue

                    aggregated['atr'] = self.technical_analyzer.calculate_atr(df)
                    aggregated['last_close'] = current_price
                    
                    # ML Enhancement
                    if self.ml_predictor.model:
                        ml_pred = self.ml_predictor.predict(df)
                        aggregated['ml_probability'] = ml_pred['probability']
                        aggregated['ml_direction'] = 'UP' if ml_pred['direction'] == 1 else 'DOWN'
                        
                        # Boost confidence if ML agrees with signal
                        if (aggregated['action'] == 'buy' and ml_pred['direction'] == 1) or \
                           (aggregated['action'] == 'sell' and ml_pred['direction'] == 0):
                            if ml_pred['confidence'] > 0.6: # Only boost if ML is confident
                                boost = 0.1
                                aggregated['confidence'] = min(1.0, aggregated['confidence'] + boost)
                                aggregated['reasons'].append(f"ML Confirmed ({ml_pred['probability']:.0%})")
                    
                    signals[symbol] = aggregated

                    # Send signal to dashboard
                    if self.dashboard:
                        self.dashboard.send_signal(
                            symbol=symbol,
                            action=aggregated['action'],
                            confidence=aggregated['confidence'],
                            price=current_price,
                            sector=sector,
                            reasons=aggregated.get('reasons', [])
                        )
            except Exception as e:
                logger.error("Error scanning %s: %s", symbol, e, exc_info=True)
                continue

        return signals, prices

    def run_nifty50_trading(self, interval: str = "5minute", check_interval: int = 30) -> None:
        """Run the trading system"""
        # Check market hours before starting trading
        can_trade, reason = self.market_hours.can_trade()
        if not can_trade:
            print(f"🚫 Trading system cannot start: {reason}")
            print("💡 The system will only trade during market hours (9:15 AM - 3:30 PM, weekdays)")
            return

        logger.info("="*60)
        logger.info(f"UNIFIED NIFTY 50 TRADING SYSTEM - {self.trading_mode.upper()} MODE")
        logger.info("="*60)
        logger.info(f"Capital: ₹{self.portfolio.initial_cash:,.2f}")
        logger.info(f"Symbols: {len(self.symbols)} stocks")
        logger.info(f"Max Positions: {self.max_positions}")
        logger.info(f"Strategies: {len(self.strategies)}")

        if self.dashboard and self.dashboard.is_connected:
            logger.info(f"📊 Dashboard: Connected to {self.dashboard.base_url}")
        else:
            logger.warning("⚠️ Dashboard: Not connected")

        logger.info(f"✅ {reason}")
        logger.info(f"Starting {self.trading_mode} trading...\n")
        iteration = self.iteration_start

        if self.restored_state:
            self._broadcast_restored_state()

        # CRITICAL FIX: Add circuit breaker to prevent cascading failures
        circuit_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=60)
        max_iterations = 10000  # Safety limit to prevent infinite loops

        try:
            while iteration < max_iterations:
                iteration += 1

                # CRITICAL FIX: Check circuit breaker before proceeding
                if not circuit_breaker.can_proceed():
                    logger.critical("🚨 Circuit breaker OPEN - pausing trading loop")
                    print("🚨 System paused due to repeated errors. Waiting 60s before retry...")
                    time.sleep(60)
                    continue

                try:
                    current_day = self.state_manager.current_trading_day()
                    if self.day_close_executed and self.day_close_executed != current_day:
                        self.day_close_executed = None

                    now_ist = datetime.now(self.state_manager.ist)
                    close_dt = now_ist.replace(
                        hour=self.market_hours.market_close.hour,
                        minute=self.market_hours.market_close.minute,
                        second=0,
                        microsecond=0
                    )
                    time_to_close = close_dt - now_ist

                    # Send system status to dashboard
                    if self.dashboard:
                        self.dashboard.send_system_status(True, iteration, "scanning")

                    logger.info(f"{'='*60}")
                    logger.info(f"Iteration {iteration} - {datetime.now().strftime('%H:%M:%S')}")
                    logger.info(f"{'='*60}")

                    regime_symbol = 'NIFTY'
                    if hasattr(self, 'config') and self.config:
                        regime_symbol = self.config.get('regime_symbol', regime_symbol)
                    market_regime = self.market_regime_detector.detect_regime(regime_symbol)
                    self.aggregator.update_market_regime(market_regime)
                    logger.info(
                        f"📊 Market Regime [{regime_symbol}]: {market_regime.get('regime', 'unknown').upper()} "
                        f"(ADX: {market_regime.get('adx', 0.0):.1f}, Bias: {market_regime.get('bias', 'neutral').upper()})"
                    )

                    # Check for auto-stop at 3:30 PM
                    if self.auto_adjustment_enabled:
                        self.auto_stop_all_trades(now_ist)

                    # Reset auto-stop flag for new day and restore saved positions
                    if current_day != getattr(self, '_last_trading_day', None):
                        self.auto_stop_executed_today = False
                        self._last_trading_day = current_day

                        # Restore saved positions from previous day at market open
                        if iteration > 1:  # Skip on first iteration
                            logger.info(f"🌅 New trading day detected: {current_day}")
                            self.restore_positions_for_day(current_day)

                            # Perform next-day adjustments at market open
                            self.adjust_trades_for_next_day()

                    # Check if we should bypass market hours for testing
                    # CRITICAL FIX #6: Default to FALSE - respect market hours unless explicitly overridden
                    if not hasattr(self, 'config') or self.config is None:
                        bypass_market_hours = False
                    else:
                        bypass_market_hours = self.config.get('bypass_market_hours', False)  # Respect market hours by default

                    # Use advanced market manager for enhanced market control
                    should_stop_trading, stop_reason = self.advanced_market_manager.should_stop_trading()
                    market_status = self.advanced_market_manager.get_market_status_display()

                    # CRITICAL FIX #6: Stop trading when markets are closed (unless bypass enabled)
                    if self.trading_mode != 'backtest' and should_stop_trading:
                        logger.info(f"🕒 {stop_reason.upper()}: {market_status['current_time']}")
                        logger.info(f"Market hours: {market_status['market_open_time']} to {market_status['market_close_time']}")
                        logger.info(f"📈 Current market trend: {market_status['market_trend'].upper()}")

                        # Allow bypass only if explicitly enabled
                        if bypass_market_hours:
                            logger.warning("⚠️ BYPASS ENABLED: Trading outside market hours for testing...")
                            logger.warning("⚠️ This uses stale market data and is NOT recommended!")
                            # Continue to scanning when bypass is enabled (skip the rest of this block)
                        else:
                            # STOP TRADING - markets are closed and bypass is not enabled

                            # Handle expiry position closure at 3:30 PM
                            if market_status['is_expiry_close_time'] and self.portfolio.positions:
                                logger.info("🔔 Closing expiring F&O positions at 3:30 PM...")
                                original_positions = self.portfolio.positions.copy()
                                updated_positions = self.advanced_market_manager.manage_positions_at_close(
                                    original_positions, close_expiry_only=True
                                )

                                # CRITICAL FIX: Apply position updates using execute_trade for live orders
                                for symbol, original_position in original_positions.items():
                                    if symbol not in updated_positions:
                                        position = self.portfolio.positions.get(symbol)
                                        if not position:
                                            continue

                                        shares = int(position.get('shares', 0))
                                        if shares == 0:
                                            continue

                                        base_symbol = symbol[:-6] if symbol.endswith('_SHORT') else symbol

                                        # Determine exit side (sell longs, buy to cover shorts)
                                        exit_side = 'sell' if shares > 0 else 'buy'
                                        quantity = abs(shares)

                                        # Fetch the latest tradable price; fall back to entry if unavailable
                                        market_price = self.portfolio.get_current_price(base_symbol)
                                        if market_price is None or market_price <= 0:
                                            try:
                                                df_retry = self.dp.fetch_with_retry(base_symbol, interval="5minute", days=1)
                                                if not df_retry.empty:
                                                    market_price = safe_float_conversion(df_retry['close'].iloc[-1])
                                            except Exception as fetch_exc:
                                                logger.debug(f"Price retry failed for {base_symbol}: {fetch_exc}")

                                        if market_price is None or market_price <= 0:
                                            market_price = position.get('entry_price', 0)

                                        if market_price <= 0:
                                            logger.critical(
                                                f"⚠️ Unable to obtain executable price for {base_symbol}; manual intervention required"
                                            )
                                            continue

                                        result = self.portfolio.execute_trade(
                                            symbol=base_symbol,
                                            shares=quantity,
                                            price=market_price,
                                            side=exit_side,
                                            timestamp=datetime.now(),
                                            confidence=position.get('confidence', 0.5),
                                            sector=position.get('sector', 'F&O'),
                                            allow_immediate_sell=True,
                                            strategy='expiry_close'
                                        )

                                        if result:
                                            direction = 'SELL' if exit_side == 'sell' else 'BUY TO COVER'
                                            logger.info(
                                                f"❌ {direction} {base_symbol}: {quantity} @ ₹{market_price:.2f} (expiry close)"
                                            )
                                        else:
                                            logger.warning(
                                                f"⚠️ Failed to auto-close expiring position {symbol}"
                                            )

                            # Save overnight positions if market is fully closed
                            if stop_reason == "market_closed":
                                current_day = datetime.now(self.advanced_market_manager.ist).strftime('%Y-%m-%d')
                                self.advanced_market_manager.save_overnight_state(self.portfolio.positions, current_day)

                                # Adjust remaining positions for market trend
                                if self.portfolio.positions:
                                    trend_symbol = getattr(self.advanced_market_manager, 'primary_trend_symbol', 'NIFTY')
                                    instrument_token = self.market_index_tokens.get(trend_symbol)
                                    current_trend = self.advanced_market_manager.analyze_market_trend(
                                        symbol=trend_symbol,
                                        kite=self.kite,
                                        instrument_token=instrument_token
                                    )
                                    adjusted_positions = self.advanced_market_manager.adjust_overnight_positions_for_trend(
                                        self.portfolio.positions, current_trend
                                    )
                                    self.portfolio.positions = adjusted_positions

                            if self.dashboard:
                                self.dashboard.send_system_status(True, iteration, stop_reason)
                            total_value = self.portfolio.calculate_total_value()
                            # CRITICAL FIX: Pass None for price_map, not market_status (which contains strings)
                            self._persist_state(iteration, total_value, None)

                            # Stop dashboard after market hours if needed
                            if self.advanced_market_manager.should_stop_dashboard():
                                logger.info("📊 Stopping dashboard after market hours...")
                                if self.dashboard:
                                    self.dashboard.send_system_status(False, iteration, "dashboard_stopped")

                            time.sleep(300)
                            continue

                    # Scan in batches
                    batch_size = 10
                    batches = [self.symbols[i:i+batch_size] for i in range(0, len(self.symbols), batch_size)]
                    all_signals = {}
                    all_prices = {}

                    for i, batch in enumerate(batches, 1):
                        batch_signals, batch_prices = self.scan_batch(batch, interval, i, len(batches))
                        all_signals.update(batch_signals)
                        all_prices.update(batch_prices)
                        time.sleep(0.3)

                    if all_signals:
                        buy_count = sum(1 for s in all_signals.values() if s['action'] == 'buy')
                        sell_count = sum(1 for s in all_signals.values() if s['action'] == 'sell')
                        logger.info(f"📊 Signal Summary: {len(all_signals)} total | {buy_count} BUY | {sell_count} SELL")

                    # Get profile settings for paper trading
                    if not hasattr(self, 'config') or self.config is None:
                        min_confidence = 0.65  # INCREASED: Higher default (was 0.35)
                        top_n = 2
                    else:
                        min_confidence = self.config.get('min_confidence', 0.65)  # INCREASED default (was 0.35)
                        top_n = self.config.get('top_n', 2)  # Allow more signals

                    # REMOVED: Aggressive profile confidence lowering - maintain quality standards
                    # Preventing weak signals that cause losses

                    # CRITICAL FIX: Separate exit signals from entry signals
                    # Exits should bypass top_n throttling to ensure positions can always close
                    exit_signals = []
                    entry_signals = []

                    for symbol, signal in all_signals.items():
                        if symbol in self.portfolio.positions:
                            exit_signals.append((symbol, signal))
                        else:
                            entry_signals.append((symbol, signal))

                    # Sort entry signals by confidence (exits processed first, don't need sorting)
                    sorted_entry_signals = sorted(entry_signals, key=lambda x: x[1]['confidence'], reverse=True)

                    # Apply top_n limit ONLY to entry signals, NOT to exits
                    if self.trading_mode == 'paper' and top_n > 1:
                        sorted_entry_signals = sorted_entry_signals[:top_n]

                    # Combine: exits first (always processed), then top entry signals
                    sorted_signals = exit_signals + sorted_entry_signals

                    # Debug: Show how many signals passed filters
                    if sorted_signals:
                        logger.info(f"📊 Processing {len(sorted_signals)} signals: {len(exit_signals)} exits + {len(sorted_entry_signals)} entries (top_n: {top_n}, min_conf: {min_confidence:.1%})")
                    else:
                        logger.info(f"📊 No signals met criteria (min_conf: {min_confidence:.1%}) - consider lowering threshold")

                    for symbol, signal in sorted_signals:
                        price = all_prices.get(symbol)
                        if price is None:
                            continue

                        if symbol in self.position_cooldown and datetime.now() < self.position_cooldown[symbol]:
                            continue

                        sector = self.get_sector(symbol)

                        # CRITICAL FIX: Don't filter exits by confidence
                        # Check if this is an exit (closing existing position) vs new entry
                        is_exit_trade = symbol in self.portfolio.positions

                        # Only apply confidence filter to NEW entries, not exits
                        if not is_exit_trade and signal['confidence'] < min_confidence:
                            logger.debug(f"    {symbol}: Entry confidence {signal['confidence']:.1%} below threshold {min_confidence:.1%} (skipping new entry)")
                            continue

                        if signal['action'] == 'buy' and symbol not in self.portfolio.positions:
                            can_open_more = len(self.portfolio.positions) < self.max_positions

                            if can_open_more:
                                if self.trading_mode != 'backtest' and time_to_close <= timedelta(minutes=20):
                                    continue
                                # Position sizing based on confidence
                                if signal['confidence'] >= 0.7:
                                    position_pct = self.portfolio.max_position_size
                                elif signal['confidence'] >= 0.5:
                                    position_pct = (self.portfolio.max_position_size + self.portfolio.min_position_size) / 2
                                else:
                                    position_pct = self.portfolio.min_position_size

                                position_value = self.portfolio.cash * position_pct
                                shares = int(position_value // price)

                                if shares > 0:
                                    trade = self.portfolio.execute_trade(
                                        symbol,
                                        shares,
                                        price,
                                        "buy",
                                        datetime.now(),
                                        signal['confidence'],
                                        sector,
                                        atr=signal.get('atr')
                                    )
                                    if trade:
                                        trade['iteration'] = iteration
                                        trade['reason'] = 'signal_buy'
                                        self.state_manager.log_trade(trade, trading_day=current_day)

                        elif signal['action'] == 'sell' and symbol in self.portfolio.positions:
                            shares = int(self.portfolio.positions[symbol]["shares"])
                            trade = self.portfolio.execute_trade(
                                symbol, shares, price, "sell", datetime.now(), signal['confidence'], sector
                            )
                            if trade:
                                trade['iteration'] = iteration
                                trade['reason'] = 'signal_sell'
                                self.state_manager.log_trade(trade, trading_day=current_day)
                            self.position_cooldown[symbol] = datetime.now() + timedelta(minutes=self.cooldown_minutes)

                    # Check for stop-loss and take-profit
                    for symbol, position in list(self.portfolio.positions.items()):
                        if symbol in all_prices:
                            current_price = all_prices[symbol]

                            # PROFESSIONAL TRAILING STOP: Use Guide-based logic (Section 6.3)
                            if self.trading_mode in ['live', 'paper']:
                                # Use professional trailing stop calculator
                                entry_price = position["entry_price"]
                                initial_stop = position["stop_loss"]
                                target_price = position.get("take_profit", entry_price * 1.02)
                                is_long = position.get("shares", 0) > 0

                                new_stop = self.portfolio.risk_manager.calculate_trailing_stop(
                                    entry_price=entry_price,
                                    current_price=current_price,
                                    initial_stop=initial_stop,
                                    target_price=target_price,
                                    is_long=is_long
                                )

                                # Update stop if it has moved
                                if new_stop != initial_stop:
                                    position["stop_loss"] = new_stop
                            else:
                                # Fallback: Original trailing stop logic for backtesting
                                atr_value = position.get("atr") if position is not None and isinstance(position, dict) else None
                                if atr_value and atr_value > 0 and current_price > position["entry_price"]:
                                    gain = current_price - position["entry_price"]
                                    if gain >= atr_value * self.portfolio.trailing_activation_multiplier:
                                        trailing_stop = current_price - atr_value * self.portfolio.trailing_stop_multiplier
                                        trailing_stop = max(trailing_stop, position["entry_price"] * 1.001)
                                        if trailing_stop > position["stop_loss"]:
                                            position["stop_loss"] = trailing_stop

                            if current_price <= position["stop_loss"] or current_price >= position["take_profit"]:
                                shares = int(position["shares"])
                                reason = "Stop Loss" if current_price <= position["stop_loss"] else "Take Profit"
                                logger.info(f"⚡ {reason} triggered for {symbol}")
                                sector = position.get("sector", "Other")
                                trade = self.portfolio.execute_trade(
                                    symbol,
                                    shares,
                                    current_price,
                                    "sell",
                                    datetime.now(),
                                    position["confidence"],
                                    sector
                                )
                                if trade:
                                    trade['iteration'] = iteration
                                    trade['reason'] = 'risk_exit'
                                    trade['trigger'] = 'stop_loss' if reason == 'Stop Loss' else 'take_profit'
                                    self.state_manager.log_trade(trade, trading_day=current_day)
                                    if reason == 'Stop Loss':
                                        self.position_cooldown[symbol] = datetime.now() + timedelta(minutes=self.stop_loss_cooldown_minutes)

                    if self.trading_mode != 'backtest' and time_to_close <= timedelta(minutes=5) and time_to_close > timedelta(minutes=-60):
                        if self._close_positions_for_day(all_prices, iteration, current_day):
                            all_prices = dict(all_prices)

                    # Calculate portfolio value
                    total_value = self.portfolio.calculate_total_value(all_prices)

                    pnl = total_value - self.portfolio.initial_cash
                    pnl_pct = (pnl / self.portfolio.initial_cash) * 100 if self.portfolio.initial_cash else 0

                    # Print portfolio status
                    logger.info("💰 Portfolio Status:")
                    logger.info(f"  Total Value: ₹{total_value:,.2f} ({pnl_pct:+.2f}%)")
                    logger.info(f"  Cash Available: ₹{self.portfolio.cash:,.2f}")
                    logger.info(f"  Positions: {len(self.portfolio.positions)}/{self.max_positions}")

                    # Send portfolio update to dashboard
                    if self.dashboard:
                        # Prepare current positions for dashboard
                        dashboard_positions = {}
                        for symbol, pos in self.portfolio.positions.items():
                            current_price = all_prices.get(symbol, pos["entry_price"])
                            shares_held = pos["shares"]
                            if shares_held >= 0:
                                cost_basis = float(pos.get('invested_amount', pos["entry_price"] * shares_held))
                                position_value = current_price * shares_held
                                unrealized_pnl = position_value - cost_basis
                            else:
                                unrealized_pnl = (pos["entry_price"] - current_price) * abs(shares_held)
                            dashboard_positions[symbol] = {
                                "shares": shares_held,
                                "entry_price": pos["entry_price"],
                                "current_price": current_price,
                                "unrealized_pnl": unrealized_pnl,
                                "sector": pos.get("sector", "Other")
                            }

                        self.dashboard.send_portfolio_update(
                            total_value=total_value,
                            cash=self.portfolio.cash,
                            positions_count=len(self.portfolio.positions),
                            total_pnl=pnl,
                            positions=dashboard_positions
                        )

                    if self.portfolio.trades_count > 0:
                        win_rate = (self.portfolio.winning_trades / self.portfolio.trades_count) * 100
                        logger.info("📈 Performance:")
                        logger.info(f"  Total Trades: {self.portfolio.trades_count}")
                        logger.info(f"  Win Rate: {win_rate:.1f}%")
                        logger.info(f"  Total P&L: ₹{self.portfolio.total_pnl:,.2f}")
                        logger.info(f"  Best Trade: ₹{self.portfolio.best_trade:,.2f}")
                        logger.info(f"  Worst Trade: ₹{self.portfolio.worst_trade:,.2f}")

                        # Send performance update to dashboard
                        if self.dashboard:
                            self.dashboard.send_performance_update(
                                trades_count=self.portfolio.trades_count,
                                win_rate=win_rate,
                                total_pnl=self.portfolio.total_pnl,
                                best_trade=self.portfolio.best_trade,
                                worst_trade=self.portfolio.worst_trade
                            )

                    self._persist_state(iteration, total_value, all_prices)

                    # CRITICAL FIX: Record success in circuit breaker
                    circuit_breaker.record_success()

                    logger.info(f"Next scan in {check_interval} seconds...")
                    time.sleep(check_interval)

                except Exception as iteration_error:
                    # CRITICAL FIX: Record failure in circuit breaker
                    circuit_breaker.record_failure()
                    logger.error(
                        f"❌ Trading loop error (iteration {iteration}): {type(iteration_error).__name__}: {iteration_error}",
                        exc_info=True
                    )
                    # Don't tight-loop on errors
                    time.sleep(5)
                    continue

            # Safety exit if max iterations reached
            if iteration >= max_iterations:
                logger.warning(f"⚠️ Max iterations ({max_iterations}) reached, exiting loop")

        except KeyboardInterrupt:
            logger.info("Stopped by user")
            total_value = self.portfolio.calculate_total_value()
            self._persist_state(iteration, total_value, {})
            if self.dashboard:
                self.dashboard.send_system_status(False, iteration, "stopped")

# ============================================================================
# F&O (FUTURES & OPTIONS) TRADING SYSTEM
# ============================================================================
