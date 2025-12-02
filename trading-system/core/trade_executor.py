#!/usr/bin/env python3
"""
Trade Executor
Encapsulates trade execution logic, separating it from the main portfolio management.
"""

import logging
import re
import time
from datetime import datetime
from typing import Dict, Optional, Tuple, List, Any

from infrastructure.security import hash_sensitive_data
from trading_exceptions import ValidationError
from trading_utils import validate_financial_amount, poll_with_backoff
from fno.indices import IndexConfig

logger = logging.getLogger('trading_system.executor')

class TradeExecutor:
    """
    Handles trade execution, validation, and order placement.
    """

    def __init__(self, portfolio: Any):
        self.portfolio = portfolio
        self.kite = portfolio.kite
        self.trading_mode = portfolio.trading_mode
        self.market_hours_manager = portfolio.market_hours_manager
        self.security_context = portfolio.security_context
        self.pricing_engine = portfolio.pricing_engine
        self.dashboard = portfolio.dashboard
        self.silent = portfolio.silent
        
        # Transaction costs constants
        self.gst_rate = 0.18
        self.stt_rate = 0.001

    def execute_trade(self, symbol: str, shares: int, price: float, side: str, timestamp: datetime = None, confidence: float = 0.5, sector: str = None, atr: float = None, allow_immediate_sell: bool = False, strategy: str = None) -> Optional[Dict]:
        """Execute trade based on trading mode"""
        
        # Sanitize symbol
        if not symbol or not isinstance(symbol, str):
            logger.error(f"❌ Invalid symbol: {symbol}")
            return None
        symbol = str(symbol).strip().upper()
        if not re.match(r'^[A-Z0-9_]+$', symbol):
            logger.error(f"❌ Invalid symbol format: {symbol}")
            return None
            
        # Sanitize side
        if not side or not isinstance(side, str):
            logger.error(f"❌ Invalid side: {side}")
            return None
        side = str(side).strip().lower()
        if side not in ['buy', 'sell']:
            logger.error(f"❌ Invalid side: {side}")
            return None

        # Validate shares and price
        try:
            shares = int(shares)
            if shares <= 0: return None
            price = float(price)
            if price <= 0: return None
        except (ValueError, TypeError):
            return None

        if timestamp is None:
            timestamp = datetime.now()

        if self.security_context:
            try:
                self.security_context.ensure_client_authorized()
            except PermissionError as exc:
                logger.error(f"❌ Trade blocked due to KYC enforcement: {exc}")
                return None

        # Check market hours
        is_exit_trade = (side == "sell" and symbol in self.portfolio.positions) or allow_immediate_sell
        if self.trading_mode != 'paper' and not is_exit_trade:
            can_trade, reason = self.market_hours_manager.can_trade()
            if not can_trade:
                if not self.silent:
                    print(f"🚫 Trade blocked: {reason}")
                return None

        if side == "buy":
            return self._execute_buy(symbol, shares, price, timestamp, confidence, sector, atr, strategy)
        elif side == "sell":
            return self._execute_sell(symbol, shares, price, timestamp, confidence, sector, atr, strategy, allow_immediate_sell)
            
        return None

    def _execute_buy(self, symbol: str, shares: int, price: float, timestamp: datetime, confidence: float, sector: str, atr: float, strategy: str) -> Optional[Dict]:
        # RESTORED: Pre-trade validation (Compliance & Risk)
        atr_value = atr if atr and atr > 0 else None
        is_option = "CE" in symbol or "PE" in symbol

        if self.trading_mode in ['live', 'paper'] and atr_value and not is_option:
            # Calculate stop-loss and take-profit based on ATR
            stop_loss = price - (atr_value * self.portfolio.atr_stop_multiplier)
            take_profit = price + (atr_value * self.portfolio.atr_target_multiplier)

            # Extract lot size
            lot_size = self._extract_lot_size(symbol) or shares

            # Run comprehensive pre-trade validation via Portfolio's ComplianceMixin
            is_valid, rejection_reason, trade_profile = self.portfolio.validate_trade_pre_execution(
                symbol=symbol,
                entry_price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                lot_size=lot_size,
                side="buy",
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

        # Calculate execution price
        execution_price = price
        if self.trading_mode == 'live':
            if not self._check_margin_requirement(symbol, shares, price, 'BUY'):
                return None
            order_id = self.place_live_order(symbol, shares, price, "BUY")
            if not order_id: return None
            filled_qty, exec_price = self._wait_for_order_completion(order_id, shares)
            if filled_qty <= 0 or not exec_price: return None
            shares = filled_qty
            execution_price = exec_price
        elif self.trading_mode == 'paper':
            pricing_result = self.pricing_engine.get_realistic_execution_price(symbol, "buy", price, shares, timestamp)
            execution_price = pricing_result['execution_price']

        # Handle Short Covering
        short_key = symbol
        existing_short = self.portfolio.positions.get(short_key)
        if not existing_short or existing_short.get('shares', 0) >= 0:
            alt_key = f"{symbol}_SHORT"
            if alt_key in self.portfolio.positions:
                existing_short = self.portfolio.positions[alt_key]
                short_key = alt_key

        if existing_short and existing_short.get('shares', 0) < 0:
            shares_short = abs(existing_short['shares'])
            shares_to_cover = min(shares, shares_short)
            
            amount = shares_to_cover * execution_price
            fees = self.calculate_transaction_costs(amount, "buy", symbol=symbol)
            total_cost = amount + fees
            
            with self.portfolio._cash_lock:
                if total_cost > self.portfolio.cash:
                    return None
                self.portfolio.cash -= total_cost
                
            invested_credit = float(existing_short.get('invested_amount', existing_short.get('entry_price', execution_price) * shares_short))
            credit_allocated = invested_credit * (shares_to_cover / shares_short) if shares_short else invested_credit
            pnl = credit_allocated - total_cost

            with self.portfolio._position_lock:
                remaining_shares = shares_short - shares_to_cover
                if remaining_shares <= 0:
                    self.portfolio.positions.pop(short_key, None)
                    self.portfolio.position_entry_times.pop(short_key, None)
                else:
                    existing_short['shares'] = -remaining_shares
                    remaining_credit = max(0.0, invested_credit - credit_allocated)
                    existing_short['invested_amount'] = float(remaining_credit)
            
            self.portfolio.total_pnl += pnl
            if pnl > 0: self.portfolio.winning_trades += 1
            else: self.portfolio.losing_trades += 1

            self.portfolio.record_trade(symbol, "buy", shares_to_cover, execution_price, fees, pnl, timestamp, confidence, sector, atr)
            
            remaining_buy_shares = shares - shares_to_cover
            if remaining_buy_shares <= 0:
                return {'status': 'filled', 'shares': shares_to_cover, 'price': execution_price}
            shares = remaining_buy_shares

        # New Long Position
        amount = shares * execution_price
        fees = self.calculate_transaction_costs(amount, "buy", symbol=symbol)
        total_cost = amount + fees

        with self.portfolio._cash_lock:
            if total_cost > self.portfolio.cash:
                return None
            self.portfolio.cash -= total_cost

        with self.portfolio._position_lock:
            existing_long = self.portfolio.positions.get(symbol)
            if existing_long and existing_long.get('shares', 0) > 0:
                existing_shares = existing_long['shares']
                existing_cost = existing_long.get('invested_amount', existing_long['entry_price'] * existing_shares)
                total_shares = existing_shares + shares
                combined_cost = existing_cost + total_cost
                avg_price = combined_cost / total_shares if total_shares else execution_price
                
                existing_long['shares'] = total_shares
                existing_long['entry_price'] = avg_price
                existing_long['invested_amount'] = float(combined_cost)
            else:
                # Check correlation
                index_symbol = self._extract_index_from_option(symbol)
                if index_symbol:
                    existing_indices = []
                    for pos_symbol in self.portfolio.positions.keys():
                        pos_index = self._extract_index_from_option(pos_symbol)
                        if pos_index and pos_index not in existing_indices:
                            existing_indices.append(pos_index)
                    
                    has_conflict, warning_msg = IndexConfig.check_correlation_conflict(existing_indices, index_symbol)
                    if has_conflict:
                        logger.warning(warning_msg)
                        with self.portfolio._cash_lock:
                            self.portfolio.cash += total_cost
                        return None

                self.portfolio.positions[symbol] = {
                    "shares": shares,
                    "entry_price": execution_price,
                    "entry_time": timestamp,
                    "confidence": confidence,
                    "sector": sector or "Other",
                    "strategy": strategy or "unknown",
                    "invested_amount": float(total_cost)
                }
                self.portfolio.position_entry_times[symbol] = timestamp

        self.portfolio.trades_count += 1
        
        if self.trading_mode == 'live':
             stop_loss = execution_price * 0.95 
             take_profit = execution_price * 1.05
             self._place_protective_orders(symbol, shares, execution_price, stop_loss, take_profit)

        return self.portfolio.record_trade(symbol, "buy", shares, execution_price, fees, None, timestamp, confidence, sector, atr)

    def _execute_sell(self, symbol: str, shares: int, price: float, timestamp: datetime, confidence: float, sector: str, atr: float, strategy: str, allow_immediate_sell: bool) -> Optional[Dict]:
        position = self.portfolio.positions.get(symbol)
        shares_available = int(position.get("shares", 0)) if position else 0
        is_short_sell = position is None or shares_available <= 0
        
        if not is_short_sell:
            if not allow_immediate_sell and not self.portfolio.can_exit_position(symbol):
                return None
            shares_to_sell = min(shares, shares_available)
        else:
            shares_to_sell = shares
            
        if shares_to_sell <= 0: return None

        execution_price = price
        if self.trading_mode == 'live':
             if not self._check_margin_requirement(symbol, shares_to_sell, price, 'SELL'): return None
             order_id = self.place_live_order(symbol, shares_to_sell, price, "SELL")
             if not order_id: return None
             filled_qty, exec_price = self._wait_for_order_completion(order_id, shares_to_sell)
             if filled_qty <= 0 or not exec_price: return None
             shares_to_sell = filled_qty
             execution_price = exec_price
        elif self.trading_mode == 'paper':
             pricing_result = self.pricing_engine.get_realistic_execution_price(symbol, "sell", price, shares_to_sell, timestamp)
             execution_price = pricing_result['execution_price']

        if self.trading_mode == 'live' and not is_short_sell:
            self._cancel_protective_orders(symbol)

        amount = shares_to_sell * execution_price
        fees = self.calculate_transaction_costs(amount, "sell", symbol=symbol)
        net = amount - fees
        
        with self.portfolio._cash_lock:
            self.portfolio.cash += net
            
        pnl = 0.0
        if not is_short_sell and position:
            invested_amount = float(position.get('invested_amount', position['entry_price'] * shares_available))
            cost_per_share = invested_amount / shares_available if shares_available else position['entry_price']
            realized_cost = cost_per_share * shares_to_sell
            pnl = amount - fees - realized_cost
            
            with self.portfolio._position_lock:
                remaining_shares = shares_available - shares_to_sell
                if remaining_shares <= 0:
                    self.portfolio.positions.pop(symbol, None)
                    self.portfolio.position_entry_times.pop(symbol, None)
                else:
                    position['shares'] = remaining_shares
                    position['invested_amount'] = max(0.0, invested_amount - realized_cost)
        else:
            pnl = -fees
            short_symbol = f"{symbol}_SHORT"
            with self.portfolio._position_lock:
                if short_symbol in self.portfolio.positions:
                    self.portfolio.positions[short_symbol]['shares'] -= shares_to_sell
                else:
                    self.portfolio.positions[short_symbol] = {
                        "shares": -shares_to_sell,
                        "entry_price": execution_price,
                        "entry_time": timestamp,
                        "side": "short",
                        "invested_amount": float(net),
                        "confidence": confidence,
                        "sector": sector or "F&O"
                    }
                    self.portfolio.position_entry_times[short_symbol] = timestamp

        self.portfolio.total_pnl += pnl
        if pnl > 0: self.portfolio.winning_trades += 1
        else: self.portfolio.losing_trades += 1
        
        return self.portfolio.record_trade(symbol, "sell", shares_to_sell, execution_price, fees, pnl, timestamp, confidence, sector, atr)

    def calculate_transaction_costs(self, amount: float, trade_type: str, symbol: Optional[str] = None) -> float:
        exchange, _, instrument_type = self._determine_order_context(symbol) if symbol else ('NSE', 'MIS', 'equity')
        
        # Simplified fee structure for brevity, ideally load from config or use full table
        brokerage = min(amount * 0.0002, 20.0)
        stt = amount * 0.001 if trade_type == 'sell' else 0
        if instrument_type == 'index_option':
             stt = amount * 0.0005 if trade_type == 'sell' else 0
             brokerage = 20.0 # Flat fee often
        
        return brokerage + stt

    def place_live_order(self, symbol: str, quantity: int, price: float, side: str) -> Optional[str]:
        if not self.kite or self.trading_mode != 'live': return None
        try:
             exchange, product, _ = self._determine_order_context(symbol)
             order_id = self.kite.place_order(
                 tradingsymbol=symbol,
                 exchange=exchange,
                 transaction_type=side.upper(),
                 quantity=quantity,
                 order_type='MARKET',
                 product=product,
                 validity='DAY'
             )
             return order_id
        except Exception as e:
             logger.error(f"Error placing live order: {e}")
             return None

    def _wait_for_order_completion(self, order_id: str, expected_quantity: int, timeout: int = 15, poll_interval: float = 1.0, cancel_on_timeout: bool = True) -> Tuple[int, Optional[float]]:
        """Wait for order fill; return (filled_quantity, average_price)."""
        if not self.kite:
            return 0, None

        def _extract_fill_data(events: List[Dict]) -> Tuple[int, Optional[float], str]:
            fill_qty = 0
            avg_price = None
            status = ''
            for event in events:
                try:
                    fill_qty = max(fill_qty, int(float(event.get('filled_quantity') or event.get('filled_qty') or 0)))
                except (TypeError, ValueError):
                    pass
                price_candidate = event.get('average_price') or event.get('averageprice') or event.get('averagePrice')
                if price_candidate is not None:
                    try:
                        avg_price = float(price_candidate)
                    except (TypeError, ValueError):
                        pass
                status = str(event.get('status', '')).upper()
            return fill_qty, avg_price, status

        def check_order_status():
            try:
                history = self.kite.order_history(order_id) or []
                filled_qty, avg_price, last_status = _extract_fill_data(history)

                if last_status in {'COMPLETE', 'FILLED'} or filled_qty >= expected_quantity:
                    return (filled_qty, avg_price, 'COMPLETE')

                if last_status in {'REJECTED', 'CANCELLED'}:
                    message = history[-1].get('status_message') if history else 'No message'
                    logger.error(f"Order {order_id} {last_status}: {message}")
                    return (filled_qty, None, 'FAILED')

                return None  # Still pending
            except Exception as exc:
                logger.warning(f"Order status check failed for {order_id}: {exc}")
                return None

        result = poll_with_backoff(
            check_order_status,
            timeout=timeout,
            initial_interval=poll_interval,
            max_interval=min(5.0, timeout/6)
        )

        if result:
            filled_qty, avg_price, status = result
            if status == 'COMPLETE':
                return filled_qty, avg_price
            elif status == 'FAILED':
                return filled_qty, None

        if cancel_on_timeout:
            try:
                variety = getattr(self.kite, 'VARIETY_REGULAR', 'regular')
                self.kite.cancel_order(variety=variety, order_id=order_id)
                logger.warning(f"Order {order_id} cancelled after timeout")
            except Exception as exc:
                logger.error(f"Failed to cancel order {order_id} after timeout: {exc}")

        return 0, None

    def _check_margin_requirement(self, symbol: str, quantity: int, price: float, side: str) -> bool:
        """Validate sufficient margin/cash before placing live order."""
        if not self.kite:
            return True

        exchange, product, instrument_type = self._determine_order_context(symbol)

        try:
            order_params = {
                'exchange': exchange,
                'tradingsymbol': symbol.upper(),
                'transaction_type': side.upper(),
                'quantity': quantity,
                'price': price if price else 0,
                'product': product,
                'order_type': 'MARKET'
            }
            margin_info = self.kite.order_margins([order_params])
            required_margin = margin_info[0].get('total', 0.0) if margin_info else 0.0
        except Exception as exc:
            logger.warning(f"⚠️ Could not fetch margin requirement for {symbol}: {exc}")
            required_margin = price * quantity

        available_cash = self.portfolio.cash
        try:
            margins_data = self.kite.margins()
            equity_margin = margins_data.get('equity', {})
            available_cash = equity_margin.get('available', {}).get('cash', available_cash)
        except Exception as exc:
            logger.warning(f"⚠️ Failed to fetch broker margins, using local cash: {exc}")

        if required_margin > available_cash:
            logger.error(f"❌ Insufficient margin for {symbol}: required ₹{required_margin:,.2f}, available ₹{available_cash:,.2f}")
            return False

        return True

    def _determine_order_context(self, symbol: str) -> Tuple[str, str, str]:
        symbol = symbol.upper()
        is_option = "CE" in symbol or "PE" in symbol
        is_future = symbol.endswith("FUT")

        if is_option or is_future:
            if any(idx in symbol for idx in ['SENSEX', 'BANKEX']):
                exchange = 'BFO'
            else:
                exchange = 'NFO'
            product = 'NRML'
            instrument_type = 'index_option' if is_option else 'index_future' # Simplified
        else:
            exchange = 'NSE'
            product = 'MIS'
            instrument_type = 'equity'

        return exchange, product, instrument_type

    def _extract_index_from_option(self, symbol: str) -> Optional[str]:
        index_patterns = ['MIDCPNIFTY', 'BANKNIFTY', 'FINNIFTY', 'NIFTY', 'BANKEX', 'SENSEX']
        symbol_upper = symbol.upper()
        for index in index_patterns:
            if symbol_upper.startswith(index):
                return index
        return None
        
    def _extract_lot_size(self, symbol: str) -> Optional[int]:
        """
        Extract lot size from F&O symbol based on SEBI specifications
        """
        index_name = self._extract_index_from_option(symbol)
        if index_name and hasattr(self.portfolio, 'sebi_compliance'):
            return self.portfolio.sebi_compliance.LOT_SIZES.get(index_name)
        return None

    def _place_protective_orders(self, symbol: str, quantity: int, entry_price: float, stop_loss: float, take_profit: float) -> None:
        """Place protective stop/target orders (GTT) for live positions."""
        if not self.kite or self.trading_mode != 'live':
            return

        try:
            exchange, _, _ = self._determine_order_context(symbol)
            
            # Cancel existing GTTs for this symbol to avoid duplicates
            self._cancel_protective_orders(symbol)

            # Place Stop Loss GTT
            sl_trigger = stop_loss
            sl_price = stop_loss * 0.99 # Market order slightly below trigger
            
            self.kite.place_gtt(
                trigger_type=self.kite.GTT_TYPE_SINGLE,
                tradingsymbol=symbol,
                exchange=exchange,
                trigger_values=[sl_trigger],
                last_price=entry_price,
                orders=[{
                    'transaction_type': self.kite.TRANSACTION_TYPE_SELL,
                    'quantity': quantity,
                    'price': sl_price,
                    'order_type': self.kite.ORDER_TYPE_LIMIT,
                    'product': self.kite.PRODUCT_NRML
                }]
            )
            logger.info(f"🛡️ Placed Stop Loss GTT for {symbol} at ₹{sl_trigger:.2f}")

            # Place Target GTT
            target_trigger = take_profit
            target_price = take_profit * 1.01
            
            self.kite.place_gtt(
                trigger_type=self.kite.GTT_TYPE_SINGLE,
                tradingsymbol=symbol,
                exchange=exchange,
                trigger_values=[target_trigger],
                last_price=entry_price,
                orders=[{
                    'transaction_type': self.kite.TRANSACTION_TYPE_SELL,
                    'quantity': quantity,
                    'price': target_price,
                    'order_type': self.kite.ORDER_TYPE_LIMIT,
                    'product': self.kite.PRODUCT_NRML
                }]
            )
            logger.info(f"🎯 Placed Target GTT for {symbol} at ₹{target_trigger:.2f}")

        except Exception as e:
            logger.error(f"❌ Failed to place protective orders for {symbol}: {e}")

    def _cancel_protective_orders(self, symbol: str) -> None:
        """Cancel existing GTT orders for a symbol."""
        if not self.kite:
            return

        try:
            gtts = self.kite.get_gtts()
            for gtt in gtts:
                if gtt.get('condition', {}).get('tradingsymbol') == symbol:
                    self.kite.delete_gtt(gtt['id'])
                    logger.info(f"🗑️ Cancelled GTT {gtt['id']} for {symbol}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to cancel GTTs for {symbol}: {e}")
