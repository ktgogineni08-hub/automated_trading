#!/usr/bin/env python3
"""
Intelligent FNO Strategy Selector
Analyzes market conditions and selects optimal F&O strategy
"""

from typing import Dict, Optional, TYPE_CHECKING
import logging
import random
import re
from datetime import datetime
from kiteconnect import KiteConnect

from fno.options import OptionChain
from fno.data_provider import FNODataProvider
from fno.strategies import StraddleStrategy, IronCondorStrategy
from fno.analytics import (
    StrikePriceOptimizer,
    ExpiryDateEvaluator,
    FNOMachineLearning,
    FNOBenchmarkTracker,
)
from fno.broker import ImpliedVolatilityAnalyzer
import utilities.market_hours as market_hours_module
MarketHoursManager = market_hours_module.MarketHoursManager
from core.regime_detector import MarketRegimeDetector
from fno.indices import IndexConfig

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from core.portfolio import UnifiedPortfolio
    from data.provider import DataProvider
    from core.regime_detector import MarketRegimeDetector

logger = logging.getLogger('trading_system.fno.strategy_selector')


class IntelligentFNOStrategySelector:
    """Intelligently selects and executes the best F&O strategies based on market conditions"""

    def __init__(
        self,
        kite: KiteConnect = None,
        portfolio: Optional['UnifiedPortfolio'] = None,
        price_data_provider: Optional['DataProvider'] = None,
        regime_detector: Optional['MarketRegimeDetector'] = None
    ):
        self.data_provider = FNODataProvider(kite=kite)
        self.portfolio = portfolio  # Add portfolio attribute
        self.strategies = {
            'straddle': StraddleStrategy(),
            'iron_condor': IronCondorStrategy(),
            'strangle': None  # Will be created dynamically
        }
        self.analyzer = ImpliedVolatilityAnalyzer()
        self.optimizer = StrikePriceOptimizer()
        self.expiry_evaluator = ExpiryDateEvaluator()
        self.ml_predictor = FNOMachineLearning()
        self.benchmark_tracker = FNOBenchmarkTracker()
        self.price_data_provider = price_data_provider
        self.regime_detector = regime_detector or MarketRegimeDetector(price_data_provider)

        self._index_patterns = ['MIDCPNIFTY', 'BANKNIFTY', 'FINNIFTY', 'NIFTY', 'BANKEX', 'SENSEX']

    def _extract_index_from_symbol(self, symbol: str) -> Optional[str]:
        symbol_upper = (symbol or '').upper()
        for index in self._index_patterns:
            if symbol_upper.startswith(index):
                return index
        match = re.match(r'([A-Z]+)', symbol_upper)
        if match:
            token = match.group(1)
            if token in self._index_patterns:
                return token
        return None

    def _get_sector_for_symbol(self, symbol: str, index_symbol: Optional[str] = None) -> str:
        """Get sector name for a symbol - uses index name as sector for F&O"""
        if index_symbol:
            return index_symbol  # Use index as sector (e.g., "NIFTY", "BANKNIFTY")
        # Try to extract from symbol
        extracted = self._extract_index_from_symbol(symbol)
        return extracted if extracted else "F&O"

    def _can_trade_index(self, portfolio: Optional['UnifiedPortfolio'], index_symbol: Optional[str]) -> tuple[bool, Optional[str]]:
        if not portfolio or not index_symbol:
            return True, None

        extractor = getattr(portfolio, '_extract_index_from_option', None)
        existing_indices: list[str] = []
        for pos_symbol in getattr(portfolio, 'positions', {}).keys():
            idx = None
            if extractor:
                try:
                    idx = extractor(pos_symbol)
                except Exception:
                    idx = None
            if not idx:
                idx = self._extract_index_from_symbol(pos_symbol)
            if idx and idx not in existing_indices:
                existing_indices.append(idx)

        conflict, warning = IndexConfig.check_correlation_conflict(existing_indices, index_symbol)
        if conflict:
            logger.warning(warning)
            return False, warning
        return True, None

    def analyze_market_conditions(self, index_symbol: str) -> Dict:
        """Analyze current market conditions to determine best strategy"""
        try:
            # Import datetime at the method level
            from datetime import datetime

            # Check market hours first
            market_hours = market_hours_module.MarketHoursManager()
            if not market_hours.is_market_open():
                current_time = datetime.now(market_hours.ist).strftime("%H:%M:%S")
                logger.warning(f"🕒 Markets are closed (Current time: {current_time} IST)")
                logger.info("🕘 Market hours: 09:15 - 15:30 IST (Monday to Friday)")
                # FIXED: Stop analysis when markets are closed (user request)
                return {
                    'error': 'markets_closed',
                    'message': 'Markets are closed - analysis stopped',
                    'current_time': current_time
                }

            # Fetch option chain
            chain = self.data_provider.fetch_option_chain(index_symbol)
            if not chain:
                return {'error': 'Failed to fetch option chain'}

            if getattr(chain, 'is_mock', False):
                logger.error(f"❌ Rejected {index_symbol}: only live option chain data allowed")
                return {
                    'error': 'mock_option_chain_rejected',
                    'mock_chain': True,
                    'index': index_symbol
                }

            spot_price = chain.spot_price

            # Get market data for analysis
            market_data = self._get_market_data(index_symbol, spot_price)

            # Detect broader market regime for routing
            market_regime = self.regime_detector.detect_regime(index_symbol)

            # Analyze volatility regime
            iv_regime = self._analyze_volatility_regime(chain, index_symbol)

            # Analyze trend and momentum with regime context
            trend_analysis = self._analyze_trend_momentum(index_symbol, market_regime)

            # Analyze option liquidity
            liquidity_analysis = self._analyze_liquidity(chain)

            # Determine market state with descriptive metadata
            market_state_key, market_state_details = self._determine_market_state(
                iv_regime, trend_analysis, market_data
            )

            # Select optimal strategy
            strategy_recommendation = self._select_optimal_strategy(
                market_state_key, iv_regime, trend_analysis, liquidity_analysis, chain, market_regime
            )

            return {
                'market_state': market_state_key,
                'market_state_details': market_state_details,
                'iv_regime': iv_regime,
                'trend_analysis': trend_analysis,
                'liquidity_analysis': liquidity_analysis,
                'strategy_recommendation': strategy_recommendation,
                'market_regime': market_regime,
                'spot_price': spot_price,
                'option_chain': chain,  # Include option chain for fallback strategies
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error analyzing market conditions: {e}")
            return {'error': str(e)}

    def _get_market_data(self, index_symbol: str, spot_price: float) -> Dict:
        """Get comprehensive market data for analysis"""
        try:
            # Calculate basic metrics
            # In real implementation, this would fetch from market data APIs
            return {
                'spot_price': spot_price,
                'daily_range': spot_price * 0.02,  # 2% daily range assumption
                'volume': random.randint(1000000, 5000000),  # Mock volume
                'vix_level': random.uniform(15, 35),  # Mock VIX
                'market_sentiment': random.choice(['bullish', 'bearish', 'neutral'])
            }
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return {}

    def _analyze_volatility_regime(self, chain: OptionChain, index_symbol: str) -> Dict:
        """Analyze current volatility regime"""
        try:
            # Calculate average IV across strikes
            ivs = []
            for option in list(chain.calls.values()) + list(chain.puts.values()):
                if option.implied_volatility > 0:
                    ivs.append(option.implied_volatility)

            if not ivs:
                return {'regime': 'unknown', 'level': 20.0, 'confidence': 0.0}

            avg_iv = sum(ivs) / len(ivs)

            # Determine regime based on IV levels
            if avg_iv < 18:
                regime = 'low_volatility'
                confidence = 0.8
            elif avg_iv > 30:
                regime = 'high_volatility'
                confidence = 0.8
            else:
                regime = 'normal_volatility'
                confidence = 0.6

            return {
                'regime': regime,
                'level': avg_iv,
                'confidence': confidence,
                'percentile': min(100, max(0, (avg_iv - 15) / (35 - 15) * 100))
            }

        except Exception as e:
            logger.error(f"Error analyzing volatility regime: {e}")
            return {'regime': 'unknown', 'level': 20.0, 'confidence': 0.0}

    def _analyze_trend_momentum(self, index_symbol: str, regime_hint: Optional[Dict] = None) -> Dict:
        """Analyze trend and momentum using regime metrics"""
        try:
            regime_data = regime_hint or self.regime_detector.detect_regime(index_symbol)

            bias = regime_data.get('bias', 'neutral') or 'neutral'
            adx_value = float(regime_data.get('adx', 0.0) or 0.0)
            short_slope = float(regime_data.get('short_slope', 0.0) or 0.0)
            trend_strength = float(regime_data.get('trend_strength', 0.0) or 0.0) / 100.0

            if bias == 'bullish':
                trend = 'bullish'
            elif bias == 'bearish':
                trend = 'bearish'
            else:
                trend = 'sideways'

            # Momentum proxy from slope scaled to manageable range
            momentum_score = short_slope * 1000
            confidence = regime_data.get('confidence', 0.0) or min(1.0, adx_value / 50.0)

            return {
                'trend': trend,
                'trend_strength': trend_strength,
                'momentum_score': momentum_score,
                'confidence': confidence,
                'adx': adx_value,
                'regime_bias': bias
            }

        except Exception as e:
            logger.error(f"Error analyzing trend: {e}")
            return {
                'trend': 'sideways',
                'trend_strength': 0.0,
                'momentum_score': 0.0,
                'confidence': 0.0,
                'adx': 0.0,
                'regime_bias': 'neutral'
            }

    def _analyze_liquidity(self, chain: OptionChain) -> Dict:
        """Analyze option liquidity"""
        try:
            total_oi = sum(opt.open_interest for opt in chain.calls.values()) + \
                      sum(opt.open_interest for opt in chain.puts.values())

            avg_spread = 0
            spreads = []
            for strike in chain.calls:
                if strike in chain.puts:
                    call_price = chain.calls[strike].last_price
                    put_price = chain.puts[strike].last_price
                    spread = abs(call_price - put_price)
                    spreads.append(spread)

            if spreads:
                avg_spread = sum(spreads) / len(spreads)

            return {
                'total_open_interest': total_oi,
                'average_spread': avg_spread,
                'liquidity_score': min(1.0, total_oi / 1000000),  # Normalize to 0-1
                'spread_efficiency': max(0, 1 - avg_spread / 50)  # Lower spread = higher efficiency
            }

        except Exception as e:
            logger.error(f"Error analyzing liquidity: {e}")
            return {'total_open_interest': 0, 'average_spread': 0, 'liquidity_score': 0.0, 'spread_efficiency': 0.0}

    def _determine_market_state(self, iv_regime: Dict, trend_analysis: Dict,
                                market_data: Dict) -> tuple[str, Dict]:
        """Determine overall market state and provide descriptive context"""
        try:
            # Combine multiple factors to determine market state
            volatility_factor = 1 if iv_regime['regime'] == 'high_volatility' else 0.5
            trend_factor = 1 if trend_analysis['trend'] != 'sideways' else 0.3
            sentiment_factor = 1 if market_data.get('market_sentiment') != 'neutral' else 0.5

            combined_score = (volatility_factor + trend_factor + sentiment_factor) / 3

            if combined_score > 0.7:
                state = 'volatile_trending'
            elif combined_score > 0.5:
                state = 'moderately_active'
            else:
                state = 'calm_sideways'

            descriptions = {
                'volatile_trending': 'High volatility with strong directional bias',
                'moderately_active': 'Moderate volatility with tradable swings',
                'calm_sideways': 'Low volatility and range-bound conditions',
                'unknown': 'Insufficient data to classify market state'
            }

            details = {
                'state': state,
                'description': descriptions.get(state, state.replace('_', ' ').title()),
                'score': round(combined_score, 3),
                'factors': {
                    'volatility': volatility_factor,
                    'trend': trend_factor,
                    'sentiment': sentiment_factor
                },
                'sentiment': market_data.get('market_sentiment'),
                'vix_level': market_data.get('vix_level'),
                'trend_strength': trend_analysis.get('trend_strength'),
                'iv_regime': iv_regime.get('regime')
            }

            return state, details

        except Exception:
            fallback_details = {
                'state': 'unknown',
                'description': 'Insufficient data to classify market state',
                'score': 0.0,
                'factors': {
                    'volatility': 0.0,
                    'trend': 0.0,
                    'sentiment': 0.0
                },
                'sentiment': market_data.get('market_sentiment'),
                'vix_level': market_data.get('vix_level'),
                'trend_strength': trend_analysis.get('trend_strength'),
                'iv_regime': iv_regime.get('regime')
            }
            return 'unknown', fallback_details

    def select_strategy(self, chain: OptionChain) -> Optional[Dict]:
        """
        Public method to select optimal strategy based on option chain analysis.
        This is the main interface for strategy selection.

        Args:
            chain: OptionChain to analyze

        Returns:
            Dictionary containing strategy recommendation or None if no suitable strategy found
        """
        try:
            if not chain:
                logger.warning("No option chain provided for strategy selection")
                return None

            # Get market data for analysis
            market_data = self._get_market_data(chain.underlying, chain.spot_price)

            # Detect overall market regime
            market_regime = self.regime_detector.detect_regime(chain.underlying)

            # Analyze volatility regime
            iv_regime = self._analyze_volatility_regime(chain, chain.underlying)

            # Analyze trend and momentum
            trend_analysis = self._analyze_trend_momentum(chain.underlying, market_regime)

            # Analyze option liquidity
            liquidity_analysis = self._analyze_liquidity(chain)

            # Determine market state
            market_state_key, market_state_details = self._determine_market_state(
                iv_regime, trend_analysis, market_data
            )

            # Select optimal strategy
            strategy_recommendation = self._select_optimal_strategy(
                market_state_key, iv_regime, trend_analysis, liquidity_analysis, chain, market_regime
            )

            logger.info(f"Strategy selected: {strategy_recommendation.get('strategy', 'None')} "
                             f"(confidence: {strategy_recommendation.get('confidence', 0):.1%})")

            # Enrich recommendation with market context when available
            if strategy_recommendation is not None:
                strategy_recommendation.setdefault('context', {})
                strategy_recommendation['context'].update({
                    'market_state': market_state_key,
                    'market_state_details': market_state_details,
                    'iv_regime': iv_regime,
                    'trend_analysis': trend_analysis,
                    'liquidity_analysis': liquidity_analysis,
                    'market_regime': market_regime
                })

            return strategy_recommendation

        except Exception as e:
            logger.error(f"Error in strategy selection: {e}")
            return None

    def _validate_signal_strength(self, market_state: str, iv_regime: Dict,
                                 trend_analysis: Dict, liquidity_analysis: Dict) -> float:
        """Validate signal strength to avoid fake signals"""
        try:
            signal_strength = 0.0

            # Market state confidence
            if market_state in ['volatile_trending', 'calm_sideways']:
                signal_strength += 0.3
            elif market_state == 'moderately_active':
                signal_strength += 0.2

            # IV regime confidence
            if iv_regime.get('regime') in ['high_volatility', 'low_volatility']:
                signal_strength += 0.25
            elif iv_regime.get('regime') == 'normal_volatility':
                signal_strength += 0.15

            # Trend analysis confidence
            trend_strength = trend_analysis.get('trend_strength', 0.0)
            if trend_strength > 0.7:
                signal_strength += 0.25
            elif trend_strength > 0.4:
                signal_strength += 0.15

            # Liquidity confidence
            liquidity_score = liquidity_analysis.get('liquidity_score', 0.0)
            if liquidity_score > 0.7:
                signal_strength += 0.2
            elif liquidity_score > 0.4:
                signal_strength += 0.1

            # Cap at 1.0
            return min(signal_strength, 1.0)

        except Exception as e:
            logger.error(f"Error validating signal strength: {e}")
            return 0.5  # Default moderate strength

    def _select_optimal_strategy(self, market_state: str, iv_regime: Dict,
                                trend_analysis: Dict, liquidity_analysis: Dict,
                                chain: OptionChain, market_regime: Dict) -> Dict:
        """Select the optimal strategy based on market conditions with enhanced signal validation"""
        try:
            strategies = []

            # Enhanced signal validation to avoid fake signals
            signal_strength = self._validate_signal_strength(market_state, iv_regime, trend_analysis, liquidity_analysis)

            # Only proceed if signals are strong enough
            if signal_strength < 0.3:
                logger.warning(f"⚠️ Signal strength too weak ({signal_strength:.2f}) - avoiding potentially fake signals")
                strategies.append({
                    'name': 'straddle',  # Conservative fallback
                    'confidence': 0.4,
                    'reason': 'Weak signals detected - using conservative straddle strategy'
                })
            else:
                logger.info(f"✅ Signal validation passed - strength: {signal_strength:.2f}")

            bias = market_regime.get('bias', 'neutral') if isinstance(market_regime, dict) else 'neutral'
            adx_value = float(market_regime.get('adx', 0.0)) if isinstance(market_regime, dict) else 0.0
            is_trending = bias in ('bullish', 'bearish') and adx_value >= 20

            # Strategy selection logic based on market conditions
            if market_state == 'volatile_trending':
                if trend_analysis['trend'] == 'bullish':
                    strategies.append({
                        'name': 'call_butterfly',
                        'confidence': 0.85,
                        'reason': 'High volatility with bullish trend favors call structures'
                    })
                elif trend_analysis['trend'] == 'bearish':
                    strategies.append({
                        'name': 'put_butterfly',
                        'confidence': 0.85,
                        'reason': 'High volatility with bearish trend favors put structures'
                    })
                elif not is_trending:
                    strategies.append({
                        'name': 'strangle',
                        'confidence': 0.7,
                        'reason': 'High volatility favors strangle strategy'
                    })

            elif market_state == 'moderately_active':
                if iv_regime['regime'] == 'high_volatility' and not is_trending:
                    strategies.append({
                        'name': 'iron_condor',
                        'confidence': 0.6,
                        'reason': 'Moderate activity with high IV favors iron condor'
                    })
                elif not is_trending:
                    strategies.append({
                        'name': 'straddle',
                        'confidence': 0.5,
                        'reason': 'Moderate activity favors straddle strategy'
                    })

            elif market_state == 'calm_sideways' and not is_trending:
                strategies.append({
                    'name': 'iron_condor',
                    'confidence': 0.7,
                    'reason': 'Calm sideways market favors iron condor for income'
                })

            if is_trending:
                directional = 'call_butterfly' if bias == 'bullish' else 'put_butterfly'
                if not any(s['name'] == directional for s in strategies):
                    strategies.append({
                        'name': directional,
                        'confidence': max(0.6, signal_strength),
                        'reason': f'Regime routing favors {bias} directional exposure'
                    })

            # Add fallback strategies
            if not strategies:
                if is_trending:
                    directional = 'call_butterfly' if bias == 'bullish' else 'put_butterfly'
                    strategies.append({
                        'name': directional,
                        'confidence': 0.5,
                        'reason': 'Directional regime fallback'
                    })
                else:
                    strategies.append({
                        'name': 'iron_condor',
                        'confidence': 0.4,
                        'reason': 'Default strategy for stable income'
                    })

            if is_trending:
                allowed = {'call_butterfly'} if bias == 'bullish' else {'put_butterfly'}
                filtered = [s for s in strategies if s['name'] in allowed]
                if filtered:
                    strategies = filtered
                else:
                    logger.warning(f"⚠️ No strategies aligned with {bias} regime - awaiting directional opportunities")
                    strategies = [{
                        'name': 'call_butterfly' if bias == 'bullish' else 'put_butterfly',
                        'confidence': 0.4,
                        'reason': 'Directional bias enforced despite limited data'
                    }]

            # Sort by confidence and return best
            strategies.sort(key=lambda x: x['confidence'], reverse=True)
            best_strategy = strategies[0]

            execution_details = self._get_strategy_execution_details(
                best_strategy['name'], chain, trend_analysis
            )

            return {
                'strategy': best_strategy['name'],
                'confidence': best_strategy['confidence'],
                'reason': best_strategy['reason'],
                'execution_details': execution_details,
                'alternatives': strategies[1:3],
                'regime_bias': bias,
                'is_trending': is_trending
            }

        except Exception as e:
            logger.error(f"Error selecting optimal strategy: {e}")
            return {
                'strategy': 'iron_condor',
                'confidence': 0.3,
                'reason': 'Fallback strategy due to error',
                'execution_details': {},
                'alternatives': []
            }

    def _get_strategy_execution_details(self, strategy_name: str, chain: OptionChain,
                                     trend_analysis: Dict) -> Dict:
        """Get detailed execution parameters for selected strategy"""
        try:
            if strategy_name == 'straddle':
                return self._get_straddle_details(chain)
            elif strategy_name == 'iron_condor':
                return self._get_iron_condor_details(chain)
            elif strategy_name == 'strangle':
                return self._get_strangle_details(chain, trend_analysis)
            elif strategy_name == 'call_butterfly':
                return self._get_butterfly_details(chain, 'call')
            elif strategy_name == 'put_butterfly':
                return self._get_butterfly_details(chain, 'put')
            else:
                return self._get_iron_condor_details(chain)  # Default fallback

        except Exception as e:
            logger.error(f"Error getting execution details for {strategy_name}: {e}")
            return {}

    def _get_straddle_details(self, chain: OptionChain) -> Dict:
        """Get straddle execution details - finds best available strike with live data"""
        if not chain:
            logger.error("Option chain is None in _get_straddle_details")
            return {}

        atm_strike = chain.get_atm_strike()

        # First try exact ATM
        call_option = chain.calls.get(atm_strike)
        put_option = chain.puts.get(atm_strike)

        # Check if ATM options have live data
        if call_option and put_option and call_option.last_price > 0 and put_option.last_price > 0:
            total_premium = call_option.last_price + put_option.last_price
            return {
                'strike': atm_strike,
                'call_option': call_option,
                'put_option': put_option,
                'total_premium': total_premium,
                'breakeven_upper': atm_strike + total_premium,
                'breakeven_lower': atm_strike - total_premium
            }

        # If ATM doesn't have live data, find nearest strikes with live data
        logger.info(f"ATM strike {atm_strike} lacks live data, searching for alternatives...")

        # Get strikes sorted by distance from ATM
        all_strikes = sorted(set(chain.calls.keys()) | set(chain.puts.keys()))
        strikes_by_distance = sorted(all_strikes, key=lambda x: abs(x - atm_strike))

        # Try each strike until we find one with live data for both call and put
        for strike in strikes_by_distance:
            call_option = chain.calls.get(strike)
            put_option = chain.puts.get(strike)

            if call_option and put_option and call_option.last_price > 0 and put_option.last_price > 0:
                total_premium = call_option.last_price + put_option.last_price
                logger.info(f"✅ Using strike {strike} instead of ATM {atm_strike} (has live data)")
                return {
                    'strike': strike,
                    'call_option': call_option,
                    'put_option': put_option,
                    'total_premium': total_premium,
                    'breakeven_upper': strike + total_premium,
                    'breakeven_lower': strike - total_premium
                }

        # Last resort: find any call and put with live data, even if different strikes (synthetic straddle)
        logger.info("Trying synthetic straddle with nearest available options...")

        live_calls = {s: opt for s, opt in chain.calls.items() if opt.last_price > 0}
        live_puts = {s: opt for s, opt in chain.puts.items() if opt.last_price > 0}

        if live_calls and live_puts:
            # Find the call and put closest to ATM
            best_call_strike = min(live_calls.keys(), key=lambda x: abs(x - atm_strike))
            best_put_strike = min(live_puts.keys(), key=lambda x: abs(x - atm_strike))

            call_option = live_calls[best_call_strike]
            put_option = live_puts[best_put_strike]

            # Use average strike for breakeven calculation
            avg_strike = (best_call_strike + best_put_strike) / 2
            total_premium = call_option.last_price + put_option.last_price

            logger.info(f"✅ Using synthetic straddle: {best_call_strike}CE + {best_put_strike}PE")
            return {
                'strike': avg_strike,
                'call_option': call_option,
                'put_option': put_option,
                'total_premium': total_premium,
                'breakeven_upper': avg_strike + total_premium,
                'breakeven_lower': avg_strike - total_premium,
                'synthetic': True,  # Flag to indicate this is not a pure straddle
                'call_strike': best_call_strike,
                'put_strike': best_put_strike
            }

        logger.warning("No options found with live data for straddle strategy")
        return {}

    def _get_iron_condor_details(self, chain: OptionChain) -> Dict:
        """Get iron condor execution details"""
        spot = chain.spot_price
        all_strikes = sorted(list(chain.calls.keys()) + list(chain.puts.keys()))

        # Find OTM strikes
        call_strikes = [s for s in all_strikes if s > spot]
        put_strikes = [s for s in all_strikes if s < spot]

        if len(call_strikes) < 2 or len(put_strikes) < 2:
            return {}

        sell_call_strike = call_strikes[0]
        buy_call_strike = call_strikes[1]
        sell_put_strike = put_strikes[-1]
        buy_put_strike = put_strikes[-2]

        sell_call = chain.calls.get(sell_call_strike)
        buy_call = chain.calls.get(buy_call_strike)
        sell_put = chain.puts.get(sell_put_strike)
        buy_put = chain.puts.get(buy_put_strike)

        if not all([sell_call, buy_call, sell_put, buy_put]):
            return {}

        net_credit = (sell_call.last_price + sell_put.last_price) - (buy_call.last_price + buy_put.last_price)

        return {
            'sell_call_strike': sell_call_strike,
            'buy_call_strike': buy_call_strike,
            'sell_put_strike': sell_put_strike,
            'buy_put_strike': buy_put_strike,
            'sell_call': sell_call,
            'buy_call': buy_call,
            'sell_put': sell_put,
            'buy_put': buy_put,
            'net_credit': net_credit,
            'max_profit': net_credit,
            'max_loss': (buy_call_strike - sell_call_strike + sell_put_strike - buy_put_strike) - net_credit
        }

    def _get_strangle_details(self, chain: OptionChain, trend_analysis: Dict) -> Dict:
        """Get strangle execution details"""
        if not chain:
            logger.error("Option chain is None in _get_strangle_details")
            return {}

        spot = chain.spot_price
        all_strikes = sorted(list(chain.calls.keys()) + list(chain.puts.keys()))

        # Find OTM strikes (3-5% away from spot)
        otm_pct = 0.03
        call_strike = min([s for s in all_strikes if s > spot * (1 + otm_pct)], default=None)
        put_strike = max([s for s in all_strikes if s < spot * (1 - otm_pct)], default=None)

        if not call_strike or not put_strike:
            return {}

        call_option = chain.calls.get(call_strike)
        put_option = chain.puts.get(put_strike)

        if not call_option or not put_option:
            return {}

        total_premium = call_option.last_price + put_option.last_price

        return {
            'call_strike': call_strike,
            'put_strike': put_strike,
            'call_option': call_option,
            'put_option': put_option,
            'total_premium': total_premium,
            'breakeven_upper': call_strike + total_premium,
            'breakeven_lower': put_strike - total_premium
        }

    def _get_butterfly_details(self, chain: OptionChain, option_type: str) -> Dict:
        """Get butterfly spread execution details with improved validation"""
        spot = chain.spot_price
        all_strikes = sorted(list(chain.calls.keys()) + list(chain.puts.keys()))

        # Validate we have enough strikes
        if option_type == 'call':
            strikes = [s for s in all_strikes if s > spot]
            if len(strikes) < 3:
                logger.info(f"ℹ️ Call butterfly unavailable: only {len(strikes)} strikes above spot {spot} (need 3+)")
                return {}

            # Find optimal strikes with better spacing
            # Look for strikes that are reasonably spaced (not too close together)
            min_spacing = spot * 0.01  # At least 1% spacing between strikes

            buy_lower = strikes[0]
            sell_middle = None
            buy_upper = None

            # Find middle strike that's at least min_spacing away from lower
            for i in range(1, len(strikes)):
                if strikes[i] - buy_lower >= min_spacing:
                    sell_middle = strikes[i]
                    break

            if not sell_middle:
                logger.info("ℹ️ Insufficient strikes available for call butterfly strategy")
                return {}

            # Find upper strike that's at least min_spacing away from middle
            for i in range(strikes.index(sell_middle) + 1, len(strikes)):
                if strikes[i] - sell_middle >= min_spacing:
                    buy_upper = strikes[i]
                    break

            if not buy_upper:
                logger.info("ℹ️ Insufficient upper strikes available for call butterfly strategy")
                return {}

            logger.info(f"Selected call butterfly strikes: {buy_lower} -> {sell_middle} -> {buy_upper}")

        else:  # put butterfly
            strikes = [s for s in all_strikes if s < spot]
            if len(strikes) < 3:
                logger.info(f"ℹ️ Put butterfly unavailable: only {len(strikes)} strikes below spot {spot} (need 3+)")
                return {}

            # Find optimal strikes for put butterfly
            min_spacing = spot * 0.01  # At least 1% spacing between strikes

            buy_upper = strikes[-1]  # Highest strike (closest to spot)
            sell_middle = None
            buy_lower = None

            # Find middle strike that's at least min_spacing below upper
            for i in range(len(strikes) - 2, -1, -1):  # Go backwards from second-to-last
                if buy_upper - strikes[i] >= min_spacing:
                    sell_middle = strikes[i]
                    break

            if not sell_middle:
                logger.info("ℹ️ Insufficient strikes available for put butterfly strategy")
                return {}

            # Find lower strike that's at least min_spacing below middle
            for i in range(strikes.index(sell_middle) - 1, -1, -1):
                if sell_middle - strikes[i] >= min_spacing:
                    buy_lower = strikes[i]
                    break

            if not buy_lower:
                logger.info("ℹ️ Insufficient lower strikes available for put butterfly strategy")
                return {}

            logger.info(f"Selected put butterfly strikes: {buy_lower} -> {sell_middle} -> {buy_upper}")

        # Get option contracts
        if option_type == 'call':
            buy_lower_opt = chain.calls.get(buy_lower)
            sell_middle_opt = chain.calls.get(sell_middle)
            buy_upper_opt = chain.calls.get(buy_upper)
        else:
            buy_lower_opt = chain.puts.get(buy_lower)
            sell_middle_opt = chain.puts.get(sell_middle)
            buy_upper_opt = chain.puts.get(buy_upper)

        # Validate all options exist and have valid prices
        if not all([buy_lower_opt, sell_middle_opt, buy_upper_opt]):
            missing = []
            if not buy_lower_opt: missing.append("buy_lower")
            if not sell_middle_opt: missing.append("sell_middle")
            if not buy_upper_opt: missing.append("buy_upper")
            logger.warning(f"Missing option contracts: {missing}")
            return {}

        # Validate option prices are positive and realistic
        options = [buy_lower_opt, sell_middle_opt, buy_upper_opt]
        for opt in options:
            if opt.last_price <= 0 or opt.last_price > 10000:  # Add upper bound check
                logger.info(f"ℹ️ Butterfly strategy unavailable: {opt.symbol} price {opt.last_price} invalid")
                return {}
            # Also check if price is suspiciously low (likely stale data)
            if opt.last_price < 0.5 and 'CE' in opt.symbol:
                logger.info(f"ℹ️ Butterfly strategy skipped: {opt.symbol} price {opt.last_price} too low")
                return {}

        # Calculate net debit and validate
        if option_type == 'call':
            net_debit = buy_lower_opt.last_price + buy_upper_opt.last_price - sell_middle_opt.last_price
        else:
            net_debit = buy_lower_opt.last_price + buy_upper_opt.last_price - sell_middle_opt.last_price

        if net_debit <= 0:
            logger.warning(f"Invalid net debit for {option_type} butterfly: {net_debit}")
            return {}

        # Calculate max profit and loss correctly
        if option_type == 'call':
            strike_diff = sell_middle - buy_lower
        else:
            strike_diff = buy_upper - sell_middle

        max_profit = max(0, strike_diff - net_debit)
        max_loss = net_debit

        logger.info(f"Butterfly calculation: Strike diff={strike_diff}, Net debit={net_debit}, Max profit={max_profit}, Max loss={max_loss}")

        return {
            'option_type': option_type,
            'buy_lower_strike': buy_lower,
            'sell_middle_strike': sell_middle,
            'buy_upper_strike': buy_upper,
            'buy_lower': buy_lower_opt,
            'sell_middle': sell_middle_opt,
            'buy_upper': buy_upper_opt,
            'net_debit': net_debit,
            'max_profit': max_profit,
            'max_loss': max_loss
        }

    def execute_optimal_strategy(self, index_symbol: str, capital: float = 100000, portfolio: Optional["UnifiedPortfolio"] = None) -> Dict:
        """Execute the optimal strategy based on current market conditions"""
        try:
            logger.info(f"🔍 Analyzing market conditions for {index_symbol}...")

            # Analyze market conditions
            analysis = self.analyze_market_conditions(index_symbol)

            if 'error' in analysis:
                if analysis.get('error') in ['mock_option_chain', 'mock_option_chain_rejected']:
                    logger.error(f"❌ Aborting strategy for {index_symbol}: only live data allowed")
                    return {
                        'success': False,
                        'error': 'live_data_required',
                        'message': 'Live option chain required; mock data rejected.'
                    }
                logger.error(f"Failed to analyze market conditions: {analysis['error']}")
                return {'success': False, 'error': analysis['error']}

            # Get strategy recommendation
            recommendation = analysis['strategy_recommendation']

            logger.info(f"🎯 Recommended Strategy: {recommendation['strategy']}")
            logger.info(f"   • Confidence: {recommendation['confidence']:.1%}")
            logger.info(f"   • Reason: {recommendation['reason']}")

            # Execute the strategy
            execution_result = self._execute_strategy(
                recommendation['strategy'],
                recommendation['execution_details'],
                capital,
                analysis,
                portfolio
            )

            # If primary strategy fails, try fallback strategies
            if not execution_result['success']:
                error_code = execution_result.get('error')
                if error_code == 'net_credit_nonpositive':
                    logger.info("ℹ️ Iron condor skipped: net credit not positive. Trying fallbacks...")
                elif error_code == 'correlation_blocked':
                    logger.info("ℹ️ Strategy blocked by correlation rules. Trying fallbacks...")
                else:
                    logger.warning(f"Primary strategy {recommendation['strategy']} failed: {error_code}")
                    logger.info("🔄 Trying fallback strategies...")

                # Define fallback strategy order
                fallback_strategies = ['straddle', 'strangle']

                # Remove the failed strategy from fallbacks
                if recommendation['strategy'] in fallback_strategies:
                    fallback_strategies.remove(recommendation['strategy'])

                for fallback_strategy in fallback_strategies:
                    logger.info(f"🔄 Trying fallback strategy: {fallback_strategy}")

                    # Get execution details for fallback strategy
                    fallback_details = self._get_strategy_execution_details(
                        fallback_strategy,
                        analysis.get('option_chain'),
                        analysis.get('trend_analysis', {})
                    )

                    if fallback_details:
                        fallback_result = self._execute_strategy(
                            fallback_strategy,
                            fallback_details,
                            capital,
                            analysis,
                            portfolio
                        )

                        if fallback_result['success']:
                            logger.info(f"✅ Fallback strategy {fallback_strategy} executed successfully!")
                            # Update result to show it was a fallback
                            fallback_result['fallback_from'] = recommendation['strategy']
                            fallback_result['original_strategy'] = recommendation['strategy']
                            fallback_result['strategy'] = fallback_strategy
                            execution_result = fallback_result
                            break
                        else:
                            fallback_error = fallback_result.get('error')
                            if fallback_error == 'correlation_blocked':
                                logger.info("ℹ️ Fallback skipped due to correlation constraints")
                                continue
                            if fallback_error == 'net_credit_nonpositive':
                                logger.info("ℹ️ Fallback iron condor skipped: net credit not positive")
                                continue
                            logger.warning(f"Fallback strategy {fallback_strategy} also failed: {fallback_error}")

            if execution_result['success']:
                state_details = analysis.get('market_state_details') or {}
                state_desc = state_details.get('description')
                if not state_desc:
                    state_key = analysis.get('market_state')
                    if isinstance(state_key, str):
                        state_desc = state_key.replace('_', ' ').title()
                    else:
                        state_desc = 'Unknown'

                logger.info("✅ Strategy executed successfully!")
                logger.info(f"   • Market State: {state_desc}")
                logger.info(f"   • IV Regime: {analysis['iv_regime']['regime']}")
                logger.info(f"   • Trend: {analysis['trend_analysis']['trend']}")

                # Send F&O strategy completion to dashboard
                if portfolio and hasattr(portfolio, 'dashboard') and portfolio.dashboard:
                    strategy_name = execution_result.get('strategy', recommendation['strategy'])
                    max_profit = execution_result.get('max_profit', 0)
                    max_loss = execution_result.get('max_loss', 0)
                    lots = execution_result.get('lots', 0)

                    # Send a special trade signal for F&O strategy completion
                    portfolio.dashboard.send_signal(
                        symbol=f"{index_symbol}_{strategy_name.upper()}",
                        action="EXECUTED",
                        confidence=recommendation['confidence'],
                        price=max_profit,  # Using max_profit as the "price" for display
                        sector=index_symbol,  # FIXED: Use index as sector
                        reasons=[
                            f"Strategy: {strategy_name}",
                            f"Lots: {lots}",
                            f"Max Profit: ₹{max_profit:,.2f}",
                            f"Max Loss: ₹{max_loss:,.2f}",
                            f"Market: {state_desc}",
                            recommendation['reason']
                        ]
                    )

                # Log the trade
                trade_record = {
                    'timestamp': datetime.now().isoformat(),
                    'strategy': execution_result.get('strategy', recommendation['strategy']),
                    'index': index_symbol,
                    'market_state': analysis['market_state'],
                    'market_state_details': state_details,
                    'confidence': recommendation['confidence'],
                    'execution_details': execution_result,
                    'analysis_summary': {
                        'iv_level': analysis['iv_regime']['level'],
                        'trend': analysis['trend_analysis']['trend'],
                        'liquidity_score': analysis['liquidity_analysis']['liquidity_score']
                    }
                }
                self.benchmark_tracker.log_trade(trade_record)
            else:
                error_code = execution_result.get('error')
                if error_code == 'net_credit_nonpositive':
                    logger.info("ℹ️ Strategy skipped: iron condor net credit was not positive")
                elif error_code == 'correlation_blocked':
                    logger.info("ℹ️ Strategy skipped due to correlation safeguards")
                else:
                    logger.error("❌ All strategies failed to execute")

            return execution_result

        except Exception as e:
            logger.error(f"Error executing optimal strategy: {e}")
            return {'success': False, 'error': str(e)}

    def _execute_strategy(self, strategy_name: str, execution_details: Dict,
                         capital: float, analysis: Dict, portfolio: Optional["UnifiedPortfolio"] = None) -> Dict:
        """Execute the selected strategy"""
        try:
            if strategy_name == 'straddle':
                return self._execute_straddle(execution_details, capital, portfolio)
            elif strategy_name == 'iron_condor':
                return self._execute_iron_condor(execution_details, capital, portfolio)
            elif strategy_name == 'strangle':
                return self._execute_strangle(execution_details, capital, portfolio)
            elif strategy_name in ['call_butterfly', 'put_butterfly']:
                return self._execute_butterfly(execution_details, capital, portfolio)
            else:
                return {'success': False, 'error': f'Unknown strategy: {strategy_name}'}

        except Exception as e:
            logger.error(f"Error executing strategy {strategy_name}: {e}")
            return {'success': False, 'error': str(e)}

    def _execute_straddle(self, details: Dict, capital: float, portfolio: Optional["UnifiedPortfolio"] = None) -> Dict:
        """Execute straddle strategy using portfolio system"""
        try:
            if not portfolio:
                if hasattr(self, 'portfolio') and self.portfolio:
                    portfolio = self.portfolio
                else:
                    return {'success': False, 'error': 'Portfolio not provided'}

            call_option = details.get('call_option')
            put_option = details.get('put_option')

            if not call_option or not put_option:
                return {'success': False, 'error': 'Missing option details'}

            index_symbol = self._extract_index_from_symbol(call_option.symbol)
            allowed, warning = self._can_trade_index(portfolio, index_symbol)
            if not allowed:
                return {
                    'success': False,
                    'error': 'correlation_blocked',
                    'message': warning,
                    'index': index_symbol
                }

            # FIXED: Use index name as sector instead of generic "F&O"
            sector = self._get_sector_for_symbol(call_option.symbol, index_symbol)

            total_premium = details['total_premium']
            max_loss_per_lot = total_premium * call_option.lot_size
            risk_amount = capital * 0.15
            lots = int(risk_amount // max_loss_per_lot)

            if lots <= 0:
                min_lot_cost = max_loss_per_lot
                if min_lot_cost <= capital * 0.50:
                    lots = 1
                    logger.info(f"Using minimum 1 lot (cost: ₹{min_lot_cost:.2f})")
                else:
                    return {
                        'success': False,
                        'error': f'Position size too small. Cost per lot: ₹{min_lot_cost:.2f}, Available risk capital: ₹{capital * 0.50:.2f}'
                    }

            # Execute trades using portfolio system
            logger.info("📈 Executing Straddle:")
            logger.info(f"   • Strike: ₹{details['strike']:,}")
            logger.info(f"   • Call: {call_option.symbol} @ ₹{call_option.last_price:.2f}")
            logger.info(f"   • Put: {put_option.symbol} @ ₹{put_option.last_price:.2f}")
            logger.info(f"   • Lots: {lots}")
            logger.info(f"   • Total Premium: ₹{total_premium:.2f}")
            logger.info(f"   • Max Loss per Lot: ₹{max_loss_per_lot:.2f}")
            logger.info(f"   • Risk Amount Used: ₹{max_loss_per_lot * lots:.2f} ({(max_loss_per_lot * lots / capital * 100):.1f}% of capital)")


            # Execute call option purchase
            call_trade = portfolio.execute_trade(
                symbol=call_option.symbol,
                shares=lots * call_option.lot_size,
                price=call_option.last_price,
                side="buy",
                confidence=0.8,
                sector=sector,
                strategy="straddle",
                atr=max_loss_per_lot / (lots * call_option.lot_size) * 0.1  # Mock ATR
            )

            # Execute put option purchase
            put_trade = portfolio.execute_trade(
                symbol=put_option.symbol,
                shares=lots * put_option.lot_size,
                price=put_option.last_price,
                side="buy",
                confidence=0.8,
                sector=sector,
                strategy="straddle",
                atr=max_loss_per_lot / (lots * put_option.lot_size) * 0.1  # Mock ATR
            )

            if call_trade and put_trade:
                logger.info("✅ Straddle positions opened successfully!")

                # Calculate realistic max profit for straddle
                strike_price = details['strike']
                premium_paid = total_premium * lots

                # Calculate realistic max profit for straddle based on breakeven points
                # Straddle profits when price moves beyond breakeven points
                breakeven_upper = details.get('breakeven_upper', strike_price + total_premium)
                breakeven_lower = details.get('breakeven_lower', strike_price - total_premium)

                # Target realistic move: 10% beyond breakeven points
                target_move_percent = 0.10  # 10% beyond breakeven
                profit_per_point = lots * call_option.lot_size

                # Calculate profit for move beyond upper breakeven
                target_upper = breakeven_upper * (1 + target_move_percent)
                profit_upper = (target_upper - breakeven_upper) * profit_per_point

                # Calculate profit for move beyond lower breakeven
                target_lower = breakeven_lower * (1 - target_move_percent)
                profit_lower = (breakeven_lower - target_lower) * profit_per_point

                # Use the higher of the two potential profits
                max_profit_estimate = max(profit_upper, profit_lower)

                # Ensure minimum 3:1 risk-reward ratio for straddle
                min_viable_profit = premium_paid * 3.0
                max_profit_estimate = max(max_profit_estimate, min_viable_profit)

                return {
                    'success': True,
                    'strategy': 'straddle',
                    'lots': lots,
                    'total_premium': total_premium * lots,
                    'max_loss': max_loss_per_lot * lots,
                    'max_profit': max_profit_estimate,
                    'breakeven_upper': details['breakeven_upper'],
                    'breakeven_lower': details['breakeven_lower'],
                    'call_trade': call_trade,
                    'put_trade': put_trade
                }
            else:
                return {'success': False, 'error': 'Failed to execute option trades'}

        except Exception as e:
            logger.error(f"Error executing straddle strategy: {e}")
            return {'success': False, 'error': str(e)}

    def _execute_iron_condor(self, details: Dict, capital: float, portfolio: Optional["UnifiedPortfolio"] = None) -> Dict:
        """Execute iron condor strategy using portfolio system"""
        try:
            if not portfolio:
                # Try to use self.portfolio if available (for backward compatibility)
                if hasattr(self, 'portfolio') and self.portfolio:
                    portfolio = self.portfolio
                else:
                    return {'success': False, 'error': 'Portfolio not provided'}

            sell_call = details.get('sell_call')
            buy_call = details.get('buy_call')
            sell_put = details.get('sell_put')
            buy_put = details.get('buy_put')

            if not all([sell_call, buy_call, sell_put, buy_put]):
                return {'success': False, 'error': 'Missing option details'}

            base_option = sell_call or sell_put or buy_call or buy_put
            index_symbol = self._extract_index_from_symbol(base_option.symbol) if base_option else None
            allowed, warning = self._can_trade_index(portfolio, index_symbol)
            if not allowed:
                return {
                    'success': False,
                    'error': 'correlation_blocked',
                    'message': warning,
                    'index': index_symbol
                }

            # FIXED: Use index name as sector
            sector = self._get_sector_for_symbol(base_option.symbol if base_option else '', index_symbol)

            net_credit = details['net_credit']
            max_loss = details['max_loss']

            if net_credit <= 0:
                return {
                    'success': False,
                    'error': 'net_credit_nonpositive',
                    'message': 'Iron condor skipped: net credit not positive'
                }

            # Calculate position size
            risk_amount = capital * 0.02  # 2% risk per trade
            lots = int(risk_amount // max_loss)

            if lots <= 0:
                return {'success': False, 'error': 'Position size too small'}

            logger.info("📊 Executing Iron Condor:")
            logger.info(f"   • Sell Call: {sell_call.symbol} @ ₹{sell_call.last_price:.2f}")
            logger.info(f"   • Buy Call: {buy_call.symbol} @ ₹{buy_call.last_price:.2f}")
            logger.info(f"   • Sell Put: {sell_put.symbol} @ ₹{sell_put.last_price:.2f}")
            logger.info(f"   • Buy Put: {buy_put.symbol} @ ₹{buy_put.last_price:.2f}")
            logger.info(f"   • Lots: {lots}")
            logger.info(f"   • Net Credit: ₹{net_credit:.2f}")
            logger.info(f"   • Max Profit: ₹{details['max_profit']:.2f}")
            logger.info(f"   • Max Loss: ₹{max_loss:.2f}")

            # Execute trades using portfolio system
            trades = []

            # Sell call option (short position)
            sell_call_trade = portfolio.execute_trade(
                symbol=sell_call.symbol,
                shares=lots * sell_call.lot_size,
                price=sell_call.last_price,
                side="sell",
                confidence=0.7,
                sector=sector,
                strategy="iron_condor",
                atr=max_loss / (lots * sell_call.lot_size) * 0.1
            )
            if sell_call_trade:
                trades.append(sell_call_trade)

            # Buy call option (long position)
            buy_call_trade = portfolio.execute_trade(
                symbol=buy_call.symbol,
                shares=lots * buy_call.lot_size,
                price=buy_call.last_price,
                side="buy",
                confidence=0.7,
                sector=sector,
                strategy="iron_condor",
                atr=max_loss / (lots * buy_call.lot_size) * 0.1
            )
            if buy_call_trade:
                trades.append(buy_call_trade)

            # Sell put option (short position)
            sell_put_trade = portfolio.execute_trade(
                symbol=sell_put.symbol,
                shares=lots * sell_put.lot_size,
                price=sell_put.last_price,
                side="sell",
                confidence=0.7,
                sector=sector,
                strategy="iron_condor",
                atr=max_loss / (lots * sell_put.lot_size) * 0.1
            )
            if sell_put_trade:
                trades.append(sell_put_trade)

            # Buy put option (long position)
            buy_put_trade = portfolio.execute_trade(
                symbol=buy_put.symbol,
                shares=lots * buy_put.lot_size,
                price=buy_put.last_price,
                side="buy",
                confidence=0.7,
                sector=sector,
                strategy="iron_condor",
                atr=max_loss / (lots * buy_put.lot_size) * 0.1
            )
            if buy_put_trade:
                trades.append(buy_put_trade)

            if len(trades) == 4:
                logger.info("✅ Iron Condor positions opened successfully!")
                return {
                    'success': True,
                    'strategy': 'iron_condor',
                    'lots': lots,
                    'net_credit': net_credit * lots,
                    'max_profit': details['max_profit'] * lots,
                    'max_loss': max_loss * lots,
                    'trades': trades
                }
            else:
                return {'success': False, 'error': f'Only {len(trades)} out of 4 trades executed'}

        except Exception as e:
            logger.error(f"Error executing iron condor strategy: {e}")
            return {'success': False, 'error': str(e)}

    def _execute_strangle(self, details: Dict, capital: float, portfolio: Optional["UnifiedPortfolio"] = None) -> Dict:
        """Execute strangle strategy using portfolio system"""
        try:
            if not portfolio:
                # Try to use self.portfolio if available (for backward compatibility)
                if hasattr(self, 'portfolio') and self.portfolio:
                    portfolio = self.portfolio
                else:
                    return {'success': False, 'error': 'Portfolio not provided'}

            call_option = details.get('call_option')
            put_option = details.get('put_option')

            if not call_option or not put_option:
                return {'success': False, 'error': 'Missing option details'}

            index_symbol = self._extract_index_from_symbol(call_option.symbol)
            allowed, warning = self._can_trade_index(portfolio, index_symbol)
            if not allowed:
                return {
                    'success': False,
                    'error': 'correlation_blocked',
                    'message': warning,
                    'index': index_symbol
                }

            # FIXED: Use index name as sector
            sector = self._get_sector_for_symbol(call_option.symbol, index_symbol)

            # Calculate position size
            total_premium = details['total_premium']
            max_loss_per_lot = total_premium * call_option.lot_size
            risk_amount = capital * 0.12  # 12% risk per trade for F&O
            lots = int(risk_amount // max_loss_per_lot)

            if lots <= 0:
                min_lot_cost = max_loss_per_lot
                if min_lot_cost <= capital * 0.40:  # Allow up to 40% of capital for 1 lot
                    lots = 1
                    logger.info(f"Using minimum 1 lot (cost: ₹{min_lot_cost:.2f})")
                else:
                    return {'success': False, 'error': f'Position size too small. Cost per lot: ₹{min_lot_cost:.2f}, Available risk capital: ₹{capital * 0.40:.2f}'}

            logger.info("📈 Executing Strangle:")
            logger.info(f"   • Call Strike: ₹{details['call_strike']:,}")
            logger.info(f"   • Put Strike: ₹{details['put_strike']:,}")
            logger.info(f"   • Call: {call_option.symbol} @ ₹{call_option.last_price:.2f}")
            logger.info(f"   • Put: {put_option.symbol} @ ₹{put_option.last_price:.2f}")
            logger.info(f"   • Lots: {lots}")
            logger.info(f"   • Total Premium: ₹{total_premium:.2f}")
            logger.info(f"   • Max Loss per Lot: ₹{max_loss_per_lot:.2f}")
            logger.info(
                f"   • Risk Amount Used: ₹{max_loss_per_lot * lots:.2f} ({(max_loss_per_lot * lots / capital * 100):.1f}% of capital)"
            )

            # Execute trades using portfolio system with error handling
            try:
                # Execute call option purchase
                call_trade = portfolio.execute_trade(
                    symbol=call_option.symbol,
                    shares=lots * call_option.lot_size,
                    price=call_option.last_price,
                    side="buy",
                    confidence=0.75,
                    sector=sector,
                    strategy="strangle",
                    atr=max_loss_per_lot / (lots * call_option.lot_size) * 0.1  # Mock ATR
                )

                # Execute put option purchase
                put_trade = portfolio.execute_trade(
                    symbol=put_option.symbol,
                    shares=lots * put_option.lot_size,
                    price=put_option.last_price,
                    side="buy",
                    confidence=0.75,
                    sector=sector,
                    strategy="strangle",
                    atr=max_loss_per_lot / (lots * put_option.lot_size) * 0.1  # Mock ATR
                )

                if call_trade and put_trade:
                    logger.info("✅ Strangle positions opened successfully!")

                    # Calculate realistic max profit for strangle based on breakeven points
                    premium_paid = total_premium * lots
                    breakeven_upper = details.get('breakeven_upper', details.get('call_strike', details['strike']) + total_premium)
                    breakeven_lower = details.get('breakeven_lower', details.get('put_strike', details['strike']) - total_premium)

                    # Target move: 12% beyond breakeven points for strangle
                    target_move_percent = 0.12  # 12% beyond breakeven
                    profit_per_point = lots * call_option.lot_size

                    # Calculate profit for move beyond breakeven points
                    target_upper = breakeven_upper * (1 + target_move_percent)
                    profit_upper = (target_upper - breakeven_upper) * profit_per_point

                    target_lower = breakeven_lower * (1 - target_move_percent)
                    profit_lower = (breakeven_lower - target_lower) * profit_per_point

                    # Use the higher of the two potential profits
                    max_profit_estimate = max(profit_upper, profit_lower)

                    # Ensure minimum 3.5:1 risk-reward ratio for strangle
                    min_viable_profit = premium_paid * 3.5
                    max_profit_estimate = max(max_profit_estimate, min_viable_profit)

                    return {
                        'success': True,
                        'strategy': 'strangle',
                        'lots': lots,
                        'total_premium': total_premium * lots,
                        'max_loss': max_loss_per_lot * lots,
                        'max_profit': max_profit_estimate,
                        'breakeven_upper': details['breakeven_upper'],
                        'breakeven_lower': details['breakeven_lower'],
                        'call_trade': call_trade,
                        'put_trade': put_trade
                    }
                else:
                    return {'success': False, 'error': 'Failed to execute option trades'}

            except Exception as e:
                logger.error(f"Error executing strangle strategy trades: {e}")
                return {'success': False, 'error': f'Trade execution failed: {str(e)}'}

        except Exception as e:
            logger.error(f"Error executing strangle strategy: {e}")
            return {'success': False, 'error': str(e)}

    def _execute_butterfly(self, details: Dict, capital: float, portfolio: Optional["UnifiedPortfolio"] = None) -> Dict:
        """Execute butterfly spread strategy with enhanced error handling"""
        try:
            if not portfolio:
                # Try to use self.portfolio if available (for backward compatibility)
                if hasattr(self, 'portfolio') and self.portfolio:
                    portfolio = self.portfolio
                else:
                    # Create a default portfolio if none provided
                    portfolio = UnifiedPortfolio(initial_cash=capital, trading_mode='paper')
                    logger.info("Created default portfolio for butterfly execution")

            # Validate portfolio has required methods
            if not hasattr(portfolio, 'execute_trade'):
                return {'success': False, 'error': 'Portfolio does not have execute_trade method'}

            option_type = details.get('option_type', 'call')  # Default to call if missing
            if option_type == 'call':
                buy_lower = details.get('buy_lower')
                sell_middle = details.get('sell_middle')
                buy_upper = details.get('buy_upper')
            else:
                buy_upper = details.get('buy_upper')
                sell_middle = details.get('sell_middle')
                buy_lower = details.get('buy_lower')

            if not all([buy_lower, sell_middle, buy_upper]):
                return {'success': False, 'error': 'Missing option details'}

            # FIXED: Use index name as sector
            base_option = buy_lower or sell_middle or buy_upper
            index_symbol = self._extract_index_from_symbol(base_option.symbol) if base_option else None
            sector = self._get_sector_for_symbol(base_option.symbol if base_option else '', index_symbol)

            net_debit = details['net_debit']
            max_loss = details['max_loss']

            # Calculate position size based on available capital and actual cash requirements
            risk_amount = capital * 0.02  # 2% risk per trade

            # Calculate the maximum cash requirement for the strategy
            # For butterfly: net cash needed = (buy_lower + buy_upper - sell_middle) * lot_size * lots
            # But to be safe, assume we need cash for buys before getting sell proceeds
            cash_per_lot = (buy_lower.last_price + buy_upper.last_price) * buy_lower.lot_size
            max_affordable_lots = int(portfolio.cash // cash_per_lot) if cash_per_lot > 0 else 0

            # Use the smaller of risk-based lots or affordable lots
            lots_by_risk = int(risk_amount // max_loss) if max_loss > 0 else 1
            lots = min(max_affordable_lots, lots_by_risk, 10)  # Cap at 10 lots for safety

            logger.info("💰 Position sizing calculation:")
            logger.info(f"   • Cash per lot: ₹{cash_per_lot:.2f}")
            logger.info(f"   • Available cash: ₹{portfolio.cash:.2f}")
            logger.info(f"   • Max affordable lots: {max_affordable_lots}")
            logger.info(f"   • Risk-based lots: {lots_by_risk}")
            logger.info(f"   • Final lots: {lots}")

            if lots <= 0:
                return {'success': False, 'error': f'Position size too small or insufficient cash. Cash needed: ₹{cash_per_lot:.2f}, Available: ₹{portfolio.cash:.2f}'}

            option_type = details['option_type']
            logger.info(f"🦋 Executing {option_type.upper()} Butterfly:")
            logger.info(f"   • Buy Lower: {buy_lower.symbol} @ ₹{buy_lower.last_price:.2f}")
            logger.info(f"   • Sell Middle: {sell_middle.symbol} @ ₹{sell_middle.last_price:.2f}")
            logger.info(f"   • Buy Upper: {buy_upper.symbol} @ ₹{buy_upper.last_price:.2f}")
            logger.info(f"   • Lots: {lots}")
            logger.info(f"   • Net Debit: ₹{net_debit:.2f}")
            logger.info(f"   • Max Profit: ₹{details['max_profit']:.2f}")
            logger.info(f"   • Max Loss: ₹{max_loss:.2f}")

            # Execute trades using portfolio system with detailed error tracking
            trades = []
            failed_trades = []

            # Buy lower strike option
            try:
                logger.info(f"🔄 Attempting to buy lower strike: {buy_lower.symbol} @ ₹{buy_lower.last_price:.2f}")
                logger.info(f"   • Shares: {lots * buy_lower.lot_size}")
                logger.info(f"   • Portfolio cash before: ₹{portfolio.cash:.2f}")

                lower_trade = portfolio.execute_trade(
                    symbol=buy_lower.symbol,
                    shares=lots * buy_lower.lot_size,
                    price=buy_lower.last_price,
                    side="buy",
                    confidence=0.6,
                    sector=sector,
                    strategy=option_type + "_butterfly",
                    atr=max_loss / (lots * buy_lower.lot_size) * 0.1
                )

                logger.info(f"   • Portfolio cash after: ₹{portfolio.cash:.2f}")

                if lower_trade:
                    trades.append(lower_trade)
                    logger.info(f"✅ Lower strike trade executed: {buy_lower.symbol}")
                else:
                    failed_trades.append(f"Lower strike ({buy_lower.symbol})")
                    logger.error(f"❌ Lower strike trade failed: {buy_lower.symbol}")
                    logger.error(f"   • Trade returned: {lower_trade}")
                    logger.error(f"   • Symbol exists in portfolio: {buy_lower.symbol in portfolio.positions}")
                    logger.error(f"   • Required cash for trade: ₹{buy_lower.last_price * lots * buy_lower.lot_size:.2f}")
            except Exception as e:
                failed_trades.append(f"Lower strike ({buy_lower.symbol}): {str(e)}")
                logger.error(f"❌ Lower strike trade exception: {buy_lower.symbol} - {e}")
                logger.error(f"   • Exception type: {type(e).__name__}")
                logger.error(f"   • Exception args: {e.args}")
                import traceback
                logger.error(f"   • Full traceback: {traceback.format_exc()}")

            # Sell middle strike option
            try:
                logger.info(f"🔄 Attempting to sell middle strike: {sell_middle.symbol} @ ₹{sell_middle.last_price:.2f}")
                logger.info(f"   • Shares: {lots * sell_middle.lot_size}")
                logger.info("   • Allow immediate sell: True")
                logger.info(f"   • Portfolio positions before: {len(portfolio.positions)}")

                middle_trade = portfolio.execute_trade(
                    symbol=sell_middle.symbol,
                    shares=lots * sell_middle.lot_size,
                    price=sell_middle.last_price,
                    side="sell",
                    confidence=0.6,
                    sector=sector,
                    strategy=option_type + "_butterfly",
                    atr=max_loss / (lots * sell_middle.lot_size) * 0.1,
                    allow_immediate_sell=True
                )

                logger.info(f"   • Portfolio positions after: {len(portfolio.positions)}")

                if middle_trade:
                    trades.append(middle_trade)
                    logger.info(f"✅ Middle strike trade executed: {sell_middle.symbol}")
                else:
                    failed_trades.append(f"Middle strike ({sell_middle.symbol})")
                    logger.error(f"❌ Middle strike trade failed: {sell_middle.symbol}")
                    logger.error(f"   • Trade returned: {middle_trade}")
                    logger.error(f"   • Symbol exists in portfolio: {sell_middle.symbol in portfolio.positions}")
                    logger.error(f"   • Portfolio cash: ₹{portfolio.cash:.2f}")
                    logger.error(f"   • Required cash for trade: ₹{sell_middle.last_price * lots * sell_middle.lot_size:.2f}")
            except Exception as e:
                failed_trades.append(f"Middle strike ({sell_middle.symbol}): {str(e)}")
                logger.error(f"❌ Middle strike trade exception: {sell_middle.symbol} - {e}")
                logger.error(f"   • Exception type: {type(e).__name__}")
                logger.error(f"   • Exception args: {e.args}")
                import traceback
                logger.error(f"   • Full traceback: {traceback.format_exc()}")

            # Buy upper strike option
            try:
                logger.info(f"🔄 Attempting to buy upper strike: {buy_upper.symbol} @ ₹{buy_upper.last_price:.2f}")
                logger.info(f"   • Shares: {lots * buy_upper.lot_size}")
                logger.info(f"   • Portfolio cash before: ₹{portfolio.cash:.2f}")

                upper_trade = portfolio.execute_trade(
                    symbol=buy_upper.symbol,
                    shares=lots * buy_upper.lot_size,
                    price=buy_upper.last_price,
                    side="buy",
                    confidence=0.6,
                    sector=sector,
                    strategy=option_type + "_butterfly",
                    atr=max_loss / (lots * buy_upper.lot_size) * 0.1
                )

                logger.info(f"   • Portfolio cash after: ₹{portfolio.cash:.2f}")

                if upper_trade:
                    trades.append(upper_trade)
                    logger.info(f"✅ Upper strike trade executed: {buy_upper.symbol}")
                else:
                    failed_trades.append(f"Upper strike ({buy_upper.symbol})")
                    logger.error(f"❌ Upper strike trade failed: {buy_upper.symbol}")
                    logger.error(f"   • Trade returned: {upper_trade}")
                    logger.error(f"   • Symbol exists in portfolio: {buy_upper.symbol in portfolio.positions}")
                    logger.error(f"   • Required cash for trade: ₹{buy_upper.last_price * lots * buy_upper.lot_size:.2f}")
            except Exception as e:
                failed_trades.append(f"Upper strike ({buy_upper.symbol}): {str(e)}")
                logger.error(f"❌ Upper strike trade exception: {buy_upper.symbol} - {e}")
                logger.error(f"   • Exception type: {type(e).__name__}")
                logger.error(f"   • Exception args: {e.args}")
                import traceback
                logger.error(f"   • Full traceback: {traceback.format_exc()}")

            if len(trades) == 3:
                # Calculate actual net debit from executed trades
                actual_net_debit = 0
                for trade in trades:
                    if trade and 'pnl' in trade:
                        # For butterfly strategies, the initial "P&L" from individual trades is misleading
                        # The real P&L will be calculated when the entire strategy is closed
                        pass

                # Calculate the real butterfly spread cost
                lower_cost = buy_lower.last_price * lots * buy_lower.lot_size
                middle_credit = sell_middle.last_price * lots * sell_middle.lot_size
                upper_cost = buy_upper.last_price * lots * buy_upper.lot_size
                actual_net_debit = lower_cost - middle_credit + upper_cost

                logger.info("✅ Butterfly positions opened successfully!")
                logger.info("⚠️  NOTE: Individual leg P&L shown above is misleading for spreads")
                logger.info("📊 Actual butterfly cost breakdown:")
                logger.info(f"   • Lower strike cost: ₹{lower_cost:.2f}")
                logger.info(f"   • Middle strike credit: ₹{middle_credit:.2f}")
                logger.info(f"   • Upper strike cost: ₹{upper_cost:.2f}")
                logger.info(f"   • Net debit (actual): ₹{actual_net_debit:.2f}")
                logger.info("💡 Real P&L will be calculated when entire strategy is closed")

                return {
                    'success': True,
                    'strategy': f'{option_type}_butterfly',
                    'lots': lots,
                    'net_debit': actual_net_debit,
                    'max_profit': details['max_profit'] * lots,
                    'max_loss': max_loss * lots,
                    'trades': trades,
                    'breakdown': {
                        'lower_cost': lower_cost,
                        'middle_credit': middle_credit,
                        'upper_cost': upper_cost
                    }
                }
            else:
                error_msg = f'Only {len(trades)} out of 3 trades executed. Failed trades: {", ".join(failed_trades)}'
                logger.error(f"Butterfly execution failed: {error_msg}")
                return {'success': False, 'error': error_msg}

        except Exception as e:
            logger.error(f"Butterfly execution exception: {e}")
            return {'success': False, 'error': str(e)}

class MarketConditionAnalyzer:
    """Analyzes market conditions for intelligent strategy selection"""

    def __init__(self):
        self.volatility_thresholds = {
            'low': 18,
            'normal': 25,
            'high': 30
        }
        self.trend_thresholds = {
            'weak': 0.3,
            'moderate': 0.6,
            'strong': 0.8
        }

    def analyze_overall_market_state(self, index_symbol: str) -> Dict:
        """Analyze overall market state including multiple factors"""
        try:
            # This would integrate with various market data sources
            # For now, return mock analysis
            return {
                'market_state': 'neutral',
                'volatility_level': 'normal',
                'trend_direction': 'sideways',
                'sentiment': 'neutral',
                'risk_appetite': 'moderate',
                'confidence': 0.7
            }
        except Exception as e:
            logger.error(f"Error analyzing market state: {e}")
            return {'market_state': 'unknown', 'confidence': 0.0}
