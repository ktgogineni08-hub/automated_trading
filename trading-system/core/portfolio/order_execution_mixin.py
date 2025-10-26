#!/usr/bin/env python3
"""Order execution mixin for UnifiedPortfolio."""

import logging
import re
import time
from datetime import datetime
from typing import Dict, Optional

from infrastructure.security import hash_sensitive_data
from trading_exceptions import ValidationError
from trading_utils import validate_financial_amount
from fno.indices import IndexConfig

logger = logging.getLogger('trading_system.portfolio')


class OrderExecutionMixin:
    def execute_trade(self, symbol: str, shares: int, price: float, side: str, timestamp: datetime = None, confidence: float = 0.5, sector: str = None, atr: float = None, allow_immediate_sell: bool = False, strategy: str = None) -> Optional[Dict]:
        """Execute trade based on trading mode"""
        # HIGH PRIORITY FIX: Comprehensive input sanitization
        # Using module-level import of re (line 16)

        # Sanitize symbol (alphanumeric + underscore for F&O symbols, uppercase)
        if not symbol or not isinstance(symbol, str):
            logger.error(f"❌ Invalid symbol: {symbol}")
            return None
        symbol = str(symbol).strip().upper()
        # Allow A-Z, 0-9, and underscore for F&O symbols like NIFTY24JAN19000CE or TEST_EXIT_CE
        if not re.match(r'^[A-Z0-9_]+$', symbol):
            logger.error(f"❌ Invalid symbol format: {symbol} (must be alphanumeric with optional underscores)")
            return None
        if len(symbol) > 30:
            logger.error(f"❌ Symbol too long: {symbol}")
            return None

        # Sanitize side
        if not side or not isinstance(side, str):
            logger.error(f"❌ Invalid side: {side}")
            return None
        side = str(side).strip().lower()
        if side not in ['buy', 'sell']:
            logger.error(f"❌ Invalid side: {side} (must be 'buy' or 'sell')")
            return None

        # Validate shares (integer, positive, reasonable range)
        try:
            shares = int(shares)
            if shares <= 0:
                logger.error(f"❌ Invalid shares: {shares} (must be positive)")
                return None
            if shares > 10000000:  # 10 million shares max
                logger.error(f"❌ Shares quantity too large: {shares}")
                return None
        except (ValueError, TypeError) as e:
            logger.error(f"❌ Invalid shares type: {shares}")
            return None

        # Validate price (float, positive, reasonable range)
        try:
            price = float(price)
            if price <= 0:
                logger.error(f"❌ Invalid price: {price} (must be positive)")
                return None
            if price > 10000000:  # 10 million per share max
                logger.error(f"❌ Price too large: {price}")
                return None
        except (ValueError, TypeError) as e:
            logger.error(f"❌ Invalid price type: {price}")
            return None

        # Validate confidence (0.0 to 1.0)
        try:
            confidence = float(confidence) if confidence is not None else 0.5
            confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
        except (ValueError, TypeError):
            confidence = 0.5

        if timestamp is None:
            timestamp = datetime.now()

        if self.security_context:
            try:
                self.security_context.ensure_client_authorized()
            except PermissionError as exc:
                logger.error(f"❌ Trade blocked due to KYC enforcement: {exc}")
                return None

        # Check market hours before executing any trade (except paper trading for testing)
        # CRITICAL: ALWAYS allow exits (sell trades) to protect portfolio, even outside market hours
        is_exit_trade = (side == "sell" and symbol in self.positions) or allow_immediate_sell

        if self.trading_mode != 'paper' and not is_exit_trade:
            can_trade, reason = self.market_hours_manager.can_trade()
            if not can_trade:
                if not self.silent:
                    print(f"🚫 Trade blocked: {reason}")
                return None
        elif is_exit_trade and self.trading_mode != 'paper':
            # Log that we're allowing an exit outside market hours
            can_trade, reason = self.market_hours_manager.can_trade()
            if not can_trade and not self.silent:
                logger.info(f"⚠️ Allowing exit trade outside market hours: {symbol} (risk management)")

        if side == "buy":
            if hasattr(self, "_ensure_daily_counters"):
                self._ensure_daily_counters(timestamp)

            # DISABLED: Daily trade limit check removed per user request
            # max_trades_per_day = getattr(self, "max_trades_per_day", None)
            # if max_trades_per_day and getattr(self, "_daily_trade_counter", 0) >= max_trades_per_day:
            #     logger.info(
            #         "🚫 Trade blocked: daily trade limit reached (%s/%s)",
            #         getattr(self, "_daily_trade_counter", 0),
            #         max_trades_per_day
            #     )
            #     return None

            # DISABLED: Per-symbol daily limit check removed per user request
            # symbol_buy_counts = getattr(self, "_daily_symbol_buy_counts", {}) or {}
            # max_trades_per_symbol = getattr(self, "max_trades_per_symbol_per_day", None)
            # if max_trades_per_symbol and symbol_buy_counts.get(symbol, 0) >= max_trades_per_symbol:
            #     logger.info(
            #         "🚫 Trade blocked: %s buy trades in %s today (limit %s)",
            #         symbol_buy_counts.get(symbol, 0),
            #         symbol,
            #         max_trades_per_symbol
            #     )
            #     return None

            min_entry_confidence = getattr(self, "min_entry_confidence", 0.0)
            if confidence < min_entry_confidence:
                logger.info(
                    "🚫 Trade blocked: confidence %.2f below minimum %.2f for %s",
                    confidence,
                    min_entry_confidence,
                    symbol
                )
                return None

            existing_position = self.positions.get(symbol)
            active_positions_limit = getattr(self, "max_open_positions_limit", None)
            if (
                active_positions_limit
                and not existing_position
                and hasattr(self, "_active_positions_count")
                and self._active_positions_count() >= active_positions_limit
            ):
                logger.info(
                    "🚫 Trade blocked: active position cap reached (%s/%s)",
                    self._active_positions_count(),
                    active_positions_limit
                )
                return None

            trade_sector = sector or (existing_position.get('sector') if existing_position else "Other")
            sector_limit = getattr(self, "max_sector_exposure", None)
            if (
                sector_limit
                and not existing_position
                and hasattr(self, "_sector_open_positions")
                and self._sector_open_positions(trade_sector) >= sector_limit
            ):
                logger.info(
                    "🚫 Trade blocked: sector %s exposure at limit (%s/%s)",
                    trade_sector,
                    self._sector_open_positions(trade_sector),
                    sector_limit
                )
                return None

            # VALIDATION FIX: Validate trade parameters
            try:
                validate_financial_amount(float(price), min_val=0.01, max_val=1000000.0)
                if shares <= 0:
                    raise ValidationError(f"Invalid shares quantity: {shares}")
                if shares > 1000000:
                    raise ValidationError(f"Shares quantity too large: {shares}")
            except ValidationError as e:
                logger.error(f"Trade validation failed: {e}")
                return None

            atr_value = atr if atr and atr > 0 else None

            # PROFESSIONAL VALIDATION: Use Guide-based risk management for FUTURES in live/paper modes
            # Skip validation for OPTIONS (CE/PE symbols) as they have different risk characteristics
            is_option = "CE" in symbol or "PE" in symbol

            if self.trading_mode in ['live', 'paper'] and atr_value and not is_option:
                # Calculate stop-loss and take-profit based on ATR
                stop_loss = price - (atr_value * self.atr_stop_multiplier)
                take_profit = price + (atr_value * self.atr_target_multiplier)

                # Extract lot size from symbol (for F&O contracts)
                lot_size = self._extract_lot_size(symbol) or shares

                # Run comprehensive pre-trade validation
                is_valid, rejection_reason, trade_profile = self.validate_trade_pre_execution(
                    symbol=symbol,
                    entry_price=price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    lot_size=lot_size,
                    side=side,
                    current_atr=atr_value
                )

                if not is_valid:
                    logger.warning(f"❌ Trade rejected: {rejection_reason}")
                    return None

                # Use professional position sizing if validation passed
                if trade_profile and trade_profile.max_lots_allowed > 0:
                    shares = trade_profile.max_lots_allowed * lot_size
                    logger.info(f"📊 Using professional position size: {shares} shares ({trade_profile.max_lots_allowed} lots)")
            elif is_option:
                logger.debug(f"📊 Skipping professional validation for option trade: {symbol}")

            # Fallback: Original risk-based position sizing for backtesting or when ATR unavailable
            if atr_value and self.trading_mode == 'backtest':
                max_loss_per_share = atr_value * self.atr_stop_multiplier
                if max_loss_per_share <= 0:
                    atr_value = None
                else:
                    risk_budget = max(self.cash * self.risk_per_trade_pct, 0)
                    allowed_shares = int(risk_budget // max_loss_per_share)
                    if allowed_shares <= 0:
                        return None
                    shares = min(shares, allowed_shares)
                    if shares <= 0:
                        return None

            # For live trading, place actual order and wait for confirmation
            if self.trading_mode == 'live':
                if not self._check_margin_requirement(symbol, shares, price, 'BUY'):
                    return None
                order_id = self.place_live_order(symbol, shares, price, "BUY")
                if not order_id:
                    return None
                filled_qty, execution_price = self._wait_for_order_completion(order_id, shares)
                if filled_qty <= 0 or execution_price is None or execution_price <= 0:
                    logger.error(f"Live buy order {order_id} not filled for {symbol}")
                    self.sync_positions_from_kite()
                    return None
                if filled_qty != shares:
                    logger.warning(
                        f"Partial fill for {symbol}: expected {shares}, filled {filled_qty}. Remaining was cancelled."
                    )
                    self.sync_positions_from_kite()
                    shares = filled_qty
            elif self.trading_mode == 'paper':
                # Use realistic pricing with bid-ask spreads and slippage
                pricing_result = self.pricing_engine.get_realistic_execution_price(
                    symbol=symbol,
                    side="buy",
                    base_price=price,
                    quantity=shares,
                    timestamp=timestamp or datetime.now()
                )
                execution_price = pricing_result['execution_price']
                logger.debug(
                    f"📊 Realistic pricing: {symbol} BUY @ ₹{price:.2f} → "
                    f"₹{execution_price:.2f} (impact: {pricing_result['impact_pct']:.2f}%)"
                )
            else:
                execution_price = price

            short_key = symbol
            existing_short = self.positions.get(short_key)
            if not existing_short or existing_short.get('shares', 0) >= 0:
                alt_key = f"{symbol}_SHORT"
                if alt_key in self.positions:
                    existing_short = self.positions[alt_key]
                    short_key = alt_key

            if existing_short and existing_short.get('shares', 0) < 0:
                shares_short = abs(existing_short['shares'])
                shares_to_cover = min(shares, shares_short)
                if shares_to_cover <= 0:
                    return None

                amount = shares_to_cover * execution_price
                fees = self.calculate_transaction_costs(amount, "buy", symbol=symbol)
                total_cost = amount + fees

                # THREAD SAFETY FIX: Atomic cash check and deduction
                with self._cash_lock:
                    if total_cost > self.cash:
                        if self.trading_mode == 'live':
                            logger.error(f"Insufficient cash to record live cover for {symbol}")
                        return None
                    self.cash -= total_cost

                invested_credit = float(existing_short.get('invested_amount', existing_short.get('entry_price', execution_price) * shares_short))
                credit_allocated = invested_credit * (shares_to_cover / shares_short) if shares_short else invested_credit

                pnl = credit_allocated - total_cost

                remaining_shares = shares_short - shares_to_cover
                if remaining_shares <= 0:
                    self.positions.pop(short_key, None)
                    self.position_entry_times.pop(short_key, None)
                else:
                    existing_short['shares'] = -remaining_shares
                    remaining_credit = max(0.0, invested_credit - credit_allocated)
                    existing_short['invested_amount'] = float(remaining_credit)

                self.total_pnl += pnl
                if pnl > self.best_trade:
                    self.best_trade = pnl
                if pnl < self.worst_trade:
                    self.worst_trade = pnl

                if pnl > 0:
                    self.winning_trades += 1
                    emoji = "🟢"
                else:
                    self.losing_trades += 1
                    emoji = "🔴"

                mode_icon = "🔴" if self.trading_mode == 'live' else "📝" if self.trading_mode == 'paper' else "📊"
                position_conf = existing_short.get('confidence', confidence)
                position_sector = existing_short.get('sector', sector or "F&O")
                atr_value = existing_short.get('atr')

                if not self.silent:
                    logger.info(f"{emoji} {mode_icon} [BUY TO COVER] {symbol}: {shares_to_cover} @ ₹{execution_price:.2f} | P&L: ₹{pnl:.2f}")

                if self.dashboard:
                    self.dashboard.send_trade(symbol, "buy", shares_to_cover, execution_price, pnl, position_sector, position_conf)

                trade_result = self.record_trade(
                    symbol=symbol,
                    side="buy",
                    shares=shares_to_cover,
                    price=execution_price,
                    fees=fees,
                    pnl=pnl,
                    timestamp=timestamp,
                    confidence=position_conf,
                    sector=position_sector,
                    atr_value=atr_value
                )

                self.send_dashboard_update()

                # CRITICAL FIX: Process remaining shares to go net-long
                # If user wanted to buy more than the short position, create a long position with remainder
                remaining_buy_shares = shares - shares_to_cover
                if remaining_buy_shares > 0:
                    # Continue to create a new long position with the remaining shares
                    logger.debug(f"📊 Short covered, continuing with {remaining_buy_shares} shares to go net-long")
                    shares = remaining_buy_shares  # Update shares for the long entry logic below
                else:
                    # All shares used to cover short, we're done
                    return trade_result

            amount = shares * execution_price
            fees = self.calculate_transaction_costs(amount, "buy", symbol=symbol)
            total_cost = amount + fees

            # THREAD SAFETY FIX: Atomic cash check and deduction
            with self._cash_lock:
                if total_cost > self.cash:
                    if self.trading_mode == 'live':
                        logger.error(f"Insufficient cash to record live buy for {symbol}")
                    return None
                self.cash -= total_cost

            entry_time = timestamp

            # Dynamic stop-loss and take-profit based on volatility & confidence
            if atr_value:
                # Get index-specific ATR multiplier if available
                index_symbol = self._extract_index_from_option(symbol)
                base_atr_multiplier = self.atr_stop_multiplier
                if index_symbol:
                    char = IndexConfig.get_characteristics(index_symbol)
                    if char:
                        base_atr_multiplier = char.atr_multiplier
                        logger.info(f"📊 Using index-specific ATR multiplier for {index_symbol}: {base_atr_multiplier}x")

                confidence_adj = max(0.8, 1 - max(0.0, 0.6 - confidence))
                stop_distance = atr_value * base_atr_multiplier * confidence_adj
                take_distance = atr_value * (self.atr_target_multiplier + max(0.0, confidence - 0.5))
                stop_loss = max(execution_price - stop_distance, execution_price * 0.9)
                take_profit = execution_price + take_distance
            else:
                if self.trading_mode == 'live':
                    stop_loss = execution_price * 0.97
                    take_profit = execution_price * 1.06
                else:
                    if confidence >= 0.7:
                        stop_loss = execution_price * 0.94
                        take_profit = execution_price * 1.12
                    elif confidence >= 0.5:
                        stop_loss = execution_price * 0.95
                        take_profit = execution_price * 1.10
                    else:
                        stop_loss = execution_price * 0.96
                        take_profit = execution_price * 1.08

            existing_long = self.positions.get(symbol)
            if existing_long and existing_long.get('shares', 0) > 0:
                existing_shares = int(existing_long.get('shares', 0))
                existing_cost = float(existing_long.get('invested_amount', existing_long.get('entry_price', execution_price) * existing_shares))
                total_shares = existing_shares + shares
                combined_cost = existing_cost + total_cost
                avg_price = combined_cost / total_shares if total_shares else execution_price

                existing_long['shares'] = total_shares
                existing_long['entry_price'] = avg_price
                existing_long['invested_amount'] = float(combined_cost)
                existing_long['stop_loss'] = min(existing_long.get('stop_loss', stop_loss), stop_loss)
                existing_long['take_profit'] = max(existing_long.get('take_profit', take_profit), take_profit)
                existing_long['confidence'] = max(existing_long.get('confidence', confidence), confidence)
                existing_long['sector'] = sector or existing_long.get('sector', 'Other')
                if atr_value is not None:
                    existing_long['atr'] = atr_value
                if strategy:
                    existing_long['strategy'] = strategy

                # THREAD SAFETY FIX: Atomic position update
                with self._position_lock:
                    self.positions[symbol] = existing_long
            else:
                # CRITICAL: Check for index correlation conflicts before adding new position
                # Extract index symbol from option symbol (e.g., NIFTY25O0725350PE -> NIFTY)
                index_symbol = self._extract_index_from_option(symbol)
                if index_symbol:
                    # THREAD SAFETY FIX: Protect position reads during correlation check
                    with self._position_lock:
                        # Get existing index positions
                        existing_indices = []
                        for pos_symbol in self.positions.keys():
                            pos_index = self._extract_index_from_option(pos_symbol)
                            if pos_index and pos_index not in existing_indices:
                                existing_indices.append(pos_index)

                    # Check for correlation conflict
                    has_conflict, warning_msg = IndexConfig.check_correlation_conflict(existing_indices, index_symbol)
                    if has_conflict:
                        logger.warning(warning_msg)
                        if not self.silent:
                            print(warning_msg)
                            print(f"   🛑 Skipping position to avoid excessive correlation risk")
                        # Return None to prevent position from being added
                        # Refund the cash since we're not taking the position
                        # THREAD SAFETY FIX: Atomic cash refund
                        with self._cash_lock:
                            self.cash += total_cost
                        return None

                # THREAD SAFETY FIX: Atomic position creation
                with self._position_lock:
                    self.positions[symbol] = {
                        "shares": shares,
                        "entry_price": execution_price,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "entry_time": entry_time,
                        "confidence": confidence,
                        "sector": sector or "Other",
                        "atr": atr_value,
                        "strategy": strategy or "unknown",
                        "invested_amount": float(total_cost)
                    }
                    self.position_entry_times[symbol] = entry_time
            self.trades_count += 1

            mode_icon = "🔴" if self.trading_mode == 'live' else "📝" if self.trading_mode == 'paper' else "📊"
            if not self.silent:
                logger.info(f"{mode_icon} [BUY] {symbol}: {shares} @ ₹{execution_price:.2f} | SL: ₹{stop_loss:.2f} | TP: ₹{take_profit:.2f}")

            # Send to dashboard
            if self.dashboard:
                self.dashboard.send_trade(symbol, "buy", shares, execution_price, None, sector, confidence)

            trade_result = self.record_trade(
                symbol=symbol,
                side="buy",
                shares=shares,
                price=execution_price,
                fees=fees,
                pnl=None,
                timestamp=timestamp,
                confidence=confidence,
                sector=sector,
                atr_value=atr_value
            )

            # Send updated portfolio status to dashboard
            self.send_dashboard_update()

            if self.trading_mode == 'live':
                self._place_protective_orders(symbol, shares, execution_price, stop_loss, take_profit)

            return trade_result

        elif side == "sell":
            if shares <= 0 or price <= 0:
                return None

            position = self.positions.get(symbol)
            shares_available = int(position.get("shares", 0)) if position else 0
            is_short_sell = position is None or shares_available <= 0

            # CRITICAL FIX: Do NOT cancel GTT before order confirmation
            # If order fails/timeout, position stays open without protection

            if not is_short_sell:
                if not allow_immediate_sell and not self.can_exit_position(symbol):
                    return None
                shares_to_sell = min(shares, shares_available)
            else:
                shares_to_sell = shares

            if shares_to_sell <= 0:
                return None

            # Place order and wait for confirmation
            if self.trading_mode == 'live' and (position is None or shares_available <= 0):
                if not self._check_margin_requirement(symbol, shares_to_sell, price, 'SELL'):
                    return None
                order_id = self.place_live_order(symbol, shares_to_sell, price, "SELL")
                if not order_id:
                    return None
                filled_qty, execution_price = self._wait_for_order_completion(order_id, shares_to_sell)
                if filled_qty <= 0 or execution_price is None or execution_price <= 0:
                    logger.error(f"Live sell order {order_id} not filled for {symbol}")
                    self.sync_positions_from_kite()
                    # CRITICAL: Do NOT cancel GTT here - order failed, position still open
                    return None
                if filled_qty != shares_to_sell:
                    logger.warning(
                        f"Partial sell fill for {symbol}: expected {shares_to_sell}, filled {filled_qty}."
                    )
                    self.sync_positions_from_kite()
                    shares_to_sell = filled_qty
            elif self.trading_mode == 'paper':
                # Use realistic pricing with bid-ask spreads and slippage
                pricing_result = self.pricing_engine.get_realistic_execution_price(
                    symbol=symbol,
                    side="sell",
                    base_price=price,
                    quantity=shares_to_sell,
                    timestamp=timestamp or datetime.now()
                )
                execution_price = pricing_result['execution_price']
                logger.debug(
                    f"📊 Realistic pricing: {symbol} SELL @ ₹{price:.2f} → "
                    f"₹{execution_price:.2f} (impact: {pricing_result['impact_pct']:.2f}%)"
                )
            else:
                execution_price = price

            # CRITICAL FIX: Cancel GTT ONLY after confirmed fill (for closing long positions)
            if self.trading_mode == 'live' and not is_short_sell:
                self._cancel_protective_orders(symbol)

            amount = shares_to_sell * execution_price
            fees = self.calculate_transaction_costs(amount, "sell", symbol=symbol)
            net = amount - fees

            # THREAD SAFETY FIX: Atomic cash addition
            with self._cash_lock:
                self.cash += net

            position_ref = position  # Preserve for trade recording after mutation

            if not is_short_sell and position:
                invested_amount = float(position.get('invested_amount', position['entry_price'] * shares_available))
                cost_per_share = invested_amount / shares_available if shares_available else position['entry_price']
                realized_cost = cost_per_share * shares_to_sell
                pnl = amount - fees - realized_cost
                sector = position.get("sector", "Other")
                confidence = position.get("confidence", 0.5)

                remaining_shares = shares_available - shares_to_sell

                # THREAD SAFETY FIX: Atomic position update/removal
                with self._position_lock:
                    if remaining_shares <= 0:
                        self.positions.pop(symbol, None)
                        self.position_entry_times.pop(symbol, None)
                    else:
                        position['shares'] = remaining_shares
                        remaining_cost = max(0.0, invested_amount - realized_cost)
                        position['invested_amount'] = float(remaining_cost)
            else:
                pnl = -fees
                sector = sector or "F&O"
                confidence = confidence if confidence is not None else 0.5
                short_symbol = f"{symbol}_SHORT"

                # THREAD SAFETY FIX: Atomic short position operations
                with self._position_lock:
                    existing_short_position = self.positions.get(short_symbol)

                    if existing_short_position:
                        current_short_shares = abs(existing_short_position.get('shares', 0))
                        total_credit = float(existing_short_position.get('invested_amount', 0.0))
                        new_total_shares = current_short_shares + shares_to_sell
                        if new_total_shares <= 0:
                            new_total_shares = shares_to_sell
                        avg_price = execution_price
                        if new_total_shares:
                            avg_price = (
                                existing_short_position.get('entry_price', execution_price) * current_short_shares + execution_price * shares_to_sell
                            ) / new_total_shares

                        existing_short_position['shares'] = -new_total_shares
                        existing_short_position['entry_price'] = avg_price
                        existing_short_position['timestamp'] = timestamp
                        existing_short_position['sector'] = sector
                        existing_short_position['invested_amount'] = float(total_credit + net)
                        existing_short_position['confidence'] = confidence
                        if atr is not None:
                            existing_short_position['atr'] = atr
                        if strategy:
                            existing_short_position['strategy'] = strategy
                    else:
                        self.positions[short_symbol] = {
                            "shares": -shares_to_sell,
                            "entry_price": execution_price,
                            "side": "short",
                            "timestamp": timestamp,
                            "sector": sector,
                            "invested_amount": float(net),
                            "confidence": confidence,
                            "atr": atr,
                            "strategy": strategy or "unknown"
                        }
                        self.position_entry_times[short_symbol] = timestamp

                    if short_symbol not in self.position_entry_times:
                        self.position_entry_times[short_symbol] = timestamp

            self.total_pnl += pnl

            if pnl > self.best_trade:
                self.best_trade = pnl
            if pnl < self.worst_trade:
                self.worst_trade = pnl

            if pnl > 0:
                self.winning_trades += 1
                emoji = "🟢"
            else:
                self.losing_trades += 1
                emoji = "🔴"

            mode_icon = "🔴" if self.trading_mode == 'live' else "📝" if self.trading_mode == 'paper' else "📊"
            if not self.silent:
                logger.info(f"{emoji} {mode_icon} [SELL] {symbol}: {shares_to_sell} @ ₹{execution_price:.2f} | P&L: ₹{pnl:.2f}")

            if self.dashboard:
                self.dashboard.send_trade(symbol, "sell", shares_to_sell, execution_price, pnl, sector, confidence)

            trade_result = self.record_trade(
                symbol=symbol,
                side="sell",
                shares=shares_to_sell,
                price=execution_price,
                fees=fees,
                pnl=pnl,
                timestamp=timestamp,
                confidence=confidence,
                sector=sector,
                atr_value=position_ref.get('atr') if position_ref is not None and isinstance(position_ref, dict) else None
            )

            self.send_dashboard_update()

            if self.trading_mode == 'live':
                remaining_position = self.positions.get(symbol)
                if remaining_position and remaining_position.get('shares', 0) > 0:
                    updated_stop = remaining_position.get('stop_loss', stop_loss if 'stop_loss' in locals() else execution_price * 0.95)
                    updated_target = remaining_position.get('take_profit', take_profit if 'take_profit' in locals() else execution_price * 1.05)
                    self._place_protective_orders(
                        symbol,
                        int(remaining_position.get('shares', 0)),
                        remaining_position.get('entry_price', execution_price),
                        updated_stop,
                        updated_target
                    )
                else:
                    self._cancel_protective_orders(symbol)

            return trade_result

        return None

        # ============================================================================
        # UNIFIED TRADING SYSTEM
        # ============================================================================
