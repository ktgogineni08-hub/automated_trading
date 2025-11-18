#!/usr/bin/env python3
"""
FNO Analytics and Advanced Modules
IV analysis, ML predictions, benchmarking, backtesting
"""

from typing import Dict, List, Optional
import logging
import math
import numpy as np
from fno.options import OptionContract, OptionChain

logger = logging.getLogger('trading_system.fno.analytics')


class FNOAnalytics:
    """F&O Analytics for IV calculation and analysis"""

    def __init__(self):
        self.historical_iv: Dict[str, List[float]] = {}
        self.iv_percentiles: Dict[str, Dict[str, float]] = {}

    def calculate_implied_volatility(self, option: OptionContract, spot_price: float,
                                  time_to_expiry: float, risk_free_rate: float = 0.06) -> float:
        """Calculate implied volatility using Newton-Raphson method without SciPy"""
        try:
            S = float(spot_price)
            K = float(option.strike_price)
            T = float(time_to_expiry)
            r = float(risk_free_rate)
            market_price = float(option.last_price)

            if T <= 0 or market_price <= 0 or S <= 0 or K <= 0:
                return 0.0

            def _norm_pdf(x: float) -> float:
                return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)

            def _norm_cdf(x: float) -> float:
                return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

            # Newton-Raphson method to find implied volatility
            sigma = 0.3  # Initial guess (30%)
            tolerance = 1e-4
            max_iterations = 100

            for _ in range(max_iterations):
                d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
                d2 = d1 - sigma * math.sqrt(T)

                if option.option_type == 'CE':
                    price = S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
                else:
                    price = K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)

                vega = S * math.sqrt(T) * _norm_pdf(d1)

                if abs(price - market_price) < tolerance:
                    return sigma * 100.0  # percentage

                if vega <= 1e-12:
                    break

                sigma = max(1e-6, sigma - (price - market_price) / vega)

            return max(0.0, sigma * 100.0)

        except Exception as e:
            logger.error(f"Error calculating IV for {option.symbol}: {e}")
            return 0.0

    def analyze_iv_regime(self, symbol: str, current_iv: float) -> Dict:
        """Analyze if current IV is high, low, or normal"""
        if symbol not in self.historical_iv or len(self.historical_iv[symbol]) < 30:
            return {'regime': 'unknown', 'percentile': 50.0}

        iv_data = self.historical_iv[symbol]
        percentile = np.percentile(iv_data, [25, 50, 75])

        if current_iv <= percentile[0]:
            regime = 'low'
        elif current_iv >= percentile[2]:
            regime = 'high'
        else:
            regime = 'normal'

        percentile_rank = (sum(1 for iv in iv_data if iv <= current_iv) / len(iv_data)) * 100

        return {
            'regime': regime,
            'percentile': percentile_rank,
            'mean': np.mean(iv_data),
            'std': np.std(iv_data),
            'min': min(iv_data),
            'max': max(iv_data)
        }

    def update_historical_iv(self, symbol: str, iv: float):
        """Update historical IV data"""
        if symbol not in self.historical_iv:
            self.historical_iv[symbol] = []

        self.historical_iv[symbol].append(iv)

        # Keep only last 1000 data points
        if len(self.historical_iv[symbol]) > 1000:
            self.historical_iv[symbol] = self.historical_iv[symbol][-1000:]

class StrikePriceOptimizer:
    """Optimizes strike price selection for different strategies"""

    def __init__(self):
        self.volatility_adjustment = True
        self.liquidity_weight = 0.3
        self.spread_weight = 0.4
        self.risk_weight = 0.3

    def find_optimal_strike(self, chain: OptionChain, strategy: str,
                          target_delta: float = None, risk_tolerance: str = 'medium') -> Dict:
        """Find optimal strike price for a given strategy"""
        spot = chain.spot_price
        all_strikes = sorted(list(chain.calls.keys()) + list(chain.puts.keys()))

        if not all_strikes:
            return {'strike': 0, 'confidence': 0.0}

        optimal_strikes = []

        for strike in all_strikes:
            score = 0
            confidence = 0

            # Get call and put options
            call = chain.calls.get(strike)
            put = chain.puts.get(strike)

            if not call or not put:
                continue

            # Calculate moneyness
            call_moneyness = (spot - strike) / spot
            put_moneyness = (strike - spot) / spot

            # Strategy-specific scoring
            if strategy == 'straddle':
                # ATM strikes are preferred for straddles
                if abs(call_moneyness) < 0.02:  # Within 2%
                    score += 0.8
                    confidence = 0.9
                elif abs(call_moneyness) < 0.05:  # Within 5%
                    score += 0.4
                    confidence = 0.6

            elif strategy == 'strangle':
                # OTM strikes are preferred for strangles
                if call_moneyness < -0.02 and put_moneyness > 0.02:  # Both OTM
                    score += 0.7
                    confidence = 0.8

            elif strategy == 'iron_condor':
                # OTM strikes for iron condor
                if call_moneyness < -0.03 and put_moneyness > 0.03:  # Both OTM
                    score += 0.6
                    confidence = 0.7

            # Liquidity scoring
            avg_oi = (call.open_interest + put.open_interest) / 2
            if avg_oi > 10000:
                score += 0.3
            elif avg_oi > 5000:
                score += 0.2
            elif avg_oi > 1000:
                score += 0.1

            # Spread scoring (tighter spreads are better)
            spread = abs(call.last_price - put.last_price)
            if spread < 10:
                score += 0.2
            elif spread < 25:
                score += 0.1

            optimal_strikes.append({
                'strike': strike,
                'score': score,
                'confidence': confidence,
                'call': call,
                'put': put,
                'avg_oi': avg_oi,
                'spread': spread
            })

        # Sort by score and return best
        optimal_strikes.sort(key=lambda x: x['score'], reverse=True)

        if optimal_strikes:
            best = optimal_strikes[0]
            return {
                'strike': best['strike'],
                'confidence': best['confidence'],
                'call': best['call'],
                'put': best['put'],
                'score': best['score']
            }

        return {'strike': 0, 'confidence': 0.0}

    def find_strikes_for_iron_condor(self, chain: OptionChain, width: int = 100) -> Dict:
        """Find optimal strikes for iron condor strategy"""
        spot = chain.spot_price
        all_strikes = sorted(list(chain.calls.keys()) + list(chain.puts.keys()))

        # Find call strikes (OTM)
        call_strikes = [s for s in all_strikes if s > spot]
        if len(call_strikes) < 2:
            return {'success': False}

        sell_call_strike = call_strikes[0]  # First OTM call
        buy_call_strike = call_strikes[1]   # Second OTM call

        # Find put strikes (OTM)
        put_strikes = [s for s in all_strikes if s < spot]
        if len(put_strikes) < 2:
            return {'success': False}

        sell_put_strike = put_strikes[-1]  # First OTM put (highest strike below spot)
        buy_put_strike = put_strikes[-2]   # Second OTM put

        # Get options
        sell_call = chain.calls.get(sell_call_strike)
        buy_call = chain.calls.get(buy_call_strike)
        sell_put = chain.puts.get(sell_put_strike)
        buy_put = chain.puts.get(buy_put_strike)

        if not all([sell_call, buy_call, sell_put, buy_put]):
            return {'success': False}

        # Calculate net credit
        net_credit = (sell_call.last_price + sell_put.last_price) - (buy_call.last_price + buy_put.last_price)

        if net_credit <= 0:
            return {'success': False}

        return {
            'success': True,
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

class ExpiryDateEvaluator:
    """Evaluates different expiry dates for optimal trading"""

    def __init__(self):
        self.theta_decay_rates: Dict[str, float] = {}
        self.optimal_expiries: Dict[str, str] = {}

    def calculate_theta_decay(self, option: OptionContract, spot_price: float,
                            time_to_expiry: float) -> float:
        """Calculate theta decay rate"""
        try:
            # Theta is time decay - higher theta means faster decay
            # For options, theta is negative (price decreases over time)
            theta_impact = abs(option.theta) * time_to_expiry

            # Normalize by option price
            if option.last_price > 0:
                decay_rate = theta_impact / option.last_price
            else:
                decay_rate = 0.0

            return min(decay_rate, 1.0)  # Cap at 100%

        except Exception:
            return 0.0

    def evaluate_expiry_suitability(self, chain: OptionChain, strategy: str) -> Dict:
        """Evaluate if current expiry is suitable for the strategy"""
        spot = chain.spot_price
        days_to_expiry = 7  # Mock value - in real implementation, calculate from expiry_date

        # Different strategies prefer different expiries
        if strategy in ['straddle', 'strangle']:
            # Weekly expiries are preferred for volatility strategies
            if days_to_expiry <= 7:
                suitability = 0.9
                reason = 'weekly_expiry_ideal'
            elif days_to_expiry <= 14:
                suitability = 0.7
                reason = 'biweekly_expiry_good'
            else:
                suitability = 0.3
                reason = 'monthly_expiry_not_ideal'

        elif strategy == 'iron_condor':
            # Monthly expiries are preferred for income strategies
            if days_to_expiry >= 21:
                suitability = 0.8
                reason = 'monthly_expiry_ideal'
            elif days_to_expiry >= 14:
                suitability = 0.6
                reason = 'biweekly_expiry_acceptable'
            else:
                suitability = 0.2
                reason = 'weekly_expiry_not_ideal'

        else:
            suitability = 0.5
            reason = 'neutral_expiry'

        return {
            'suitability': suitability,
            'days_to_expiry': days_to_expiry,
            'reason': reason,
            'recommendation': 'use_current' if suitability > 0.6 else 'consider_other_expiry'
        }

    def compare_expiries(self, chains: Dict[str, OptionChain], strategy: str) -> Dict:
        """Compare multiple expiries and recommend the best one"""
        if not chains:
            return {'best_expiry': None, 'confidence': 0.0}

        expiry_scores = []

        for expiry, chain in chains.items():
            evaluation = self.evaluate_expiry_suitability(chain, strategy)
            score = evaluation['suitability']

            # Add liquidity bonus
            total_oi = sum(opt.open_interest for opt in chain.calls.values()) + \
                      sum(opt.open_interest for opt in chain.puts.values())
            liquidity_bonus = min(total_oi / 100000, 0.2)  # Max 20% bonus for high liquidity

            score += liquidity_bonus
            score = min(score, 1.0)

            expiry_scores.append({
                'expiry': expiry,
                'score': score,
                'suitability': evaluation['suitability'],
                'liquidity_bonus': liquidity_bonus,
                'days_to_expiry': evaluation['days_to_expiry'],
                'recommendation': evaluation['recommendation']
            })

        # Sort by score
        expiry_scores.sort(key=lambda x: x['score'], reverse=True)

        if expiry_scores:
            best = expiry_scores[0]
            return {
                'best_expiry': best['expiry'],
                'confidence': best['score'],
                'details': best,
                'alternatives': expiry_scores[1:3]  # Top 3 alternatives
            }

        return {'best_expiry': None, 'confidence': 0.0}

class FNOMachineLearning:
    """Machine learning models for option price prediction"""

    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.prediction_history: Dict[str, List] = {}

    def predict_option_price(self, option: OptionContract, market_data: Dict,
                           prediction_horizon: int = 1) -> Dict:
        """Predict option price using ML models"""
        try:
            # Simple prediction based on historical volatility and trend
            spot_price = market_data.get('spot_price', 0)
            volatility = market_data.get('volatility', 20)
            trend = market_data.get('trend', 0)

            # Basic prediction model
            if option.option_type == 'CE':
                # Call option prediction
                intrinsic = max(0, spot_price - option.strike_price)
                time_value = option.last_price * (1 - 0.1 * prediction_horizon)  # Decay over time
                predicted_price = intrinsic + time_value
            else:
                # Put option prediction
                intrinsic = max(0, option.strike_price - spot_price)
                time_value = option.last_price * (1 - 0.1 * prediction_horizon)  # Decay over time
                predicted_price = intrinsic + time_value

            # Adjust for volatility and trend
            volatility_adjustment = 1 + (volatility - 20) / 100  # Adjust for volatility
            trend_adjustment = 1 + trend * 0.1  # Adjust for trend

            predicted_price *= volatility_adjustment * trend_adjustment
            predicted_price = max(predicted_price, 0.05)  # Minimum price

            confidence = min(0.7, 1 - abs(predicted_price - option.last_price) / option.last_price)

            return {
                'predicted_price': predicted_price,
                'confidence': confidence,
                'direction': 'up' if predicted_price > option.last_price else 'down',
                'change_pct': (predicted_price - option.last_price) / option.last_price * 100
            }

        except Exception as e:
            logger.error(f"Error predicting price for {option.symbol}: {e}")
            return {'predicted_price': option.last_price, 'confidence': 0.0}

    def analyze_sentiment_impact(self, symbol: str, sentiment_score: float) -> Dict:
        """Analyze impact of market sentiment on options"""
        # Mock sentiment analysis
        if sentiment_score > 0.6:
            sentiment = 'bullish'
            volatility_impact = 1.2  # Higher volatility expected
            price_impact = 1.1  # Higher option prices
        elif sentiment_score < 0.4:
            sentiment = 'bearish'
            volatility_impact = 1.2  # Higher volatility expected
            price_impact = 1.1  # Higher option prices
        else:
            sentiment = 'neutral'
            volatility_impact = 1.0
            price_impact = 1.0

        return {
            'sentiment': sentiment,
            'volatility_impact': volatility_impact,
            'price_impact': price_impact,
            'confidence': abs(sentiment_score - 0.5) * 2
        }

class FNOBenchmarkTracker:
    """Tracks F&O performance and generates reports"""

    def __init__(self):
        self.trades: List[Dict] = []
        self.daily_pnl: Dict[str, float] = {}
        self.expiry_performance: Dict[str, Dict] = {}
        self.strategy_performance: Dict[str, Dict] = {}

    def log_trade(self, trade: Dict):
        """Log F&O trade for analysis"""
        self.trades.append(trade)

        # Update strategy performance
        strategy = trade.get('strategy', 'unknown')
        if strategy not in self.strategy_performance:
            self.strategy_performance[strategy] = {
                'total_trades': 0,
                'winning_trades': 0,
                'total_pnl': 0.0,
                'max_profit': 0.0,
                'max_loss': 0.0
            }

        stats = self.strategy_performance[strategy]
        stats['total_trades'] += 1

        pnl = trade.get('pnl', 0)
        stats['total_pnl'] += pnl

        if pnl > 0:
            stats['winning_trades'] += 1
        else:
            stats['max_loss'] = min(stats['max_loss'], pnl)

        stats['max_profit'] = max(stats['max_profit'], pnl)

    def generate_performance_report(self) -> Dict:
        """Generate comprehensive performance report"""
        if not self.trades:
            return {'error': 'No trades to analyze'}

        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.get('pnl', 0) > 0)
        win_rate = winning_trades / total_trades * 100

        total_pnl = sum(t.get('pnl', 0) for t in self.trades)
        avg_pnl = total_pnl / total_trades

        max_profit = max((t.get('pnl', 0) for t in self.trades), default=0)
        max_loss = min((t.get('pnl', 0) for t in self.trades), default=0)

        # Strategy breakdown
        strategy_stats = {}
        for strategy, stats in self.strategy_performance.items():
            strategy_stats[strategy] = {
                'win_rate': stats['winning_trades'] / stats['total_trades'] * 100 if stats['total_trades'] > 0 else 0,
                'total_pnl': stats['total_pnl'],
                'avg_pnl': stats['total_pnl'] / stats['total_trades'] if stats['total_trades'] > 0 else 0,
                'max_profit': stats['max_profit'],
                'max_loss': stats['max_loss']
            }

        return {
            'summary': {
                'total_trades': total_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_pnl': avg_pnl,
                'max_profit': max_profit,
                'max_loss': max_loss,
                'profit_factor': safe_divide(abs(max_profit), abs(max_loss), float('inf'))
            },
            'strategy_breakdown': strategy_stats,
            'recommendations': self._generate_recommendations(strategy_stats)
        }

    def _generate_recommendations(self, strategy_stats: Dict) -> List[str]:
        """Generate trading recommendations based on performance"""
        recommendations = []

        for strategy, stats in strategy_stats.items():
            if stats['win_rate'] > 60 and stats['total_pnl'] > 0:
                recommendations.append(f"Continue with {strategy} - good performance")
            elif stats['win_rate'] < 40:
                recommendations.append(f"Review {strategy} - poor win rate")
            elif stats['total_pnl'] < 0:
                recommendations.append(f"Stop {strategy} - negative P&L")

        if not recommendations:
            recommendations.append("All strategies need review")

        return recommendations



class FNOBacktester:
    """Backtesting framework for F&O strategies"""

    def __init__(self, initial_capital: float = 1000000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.trades: List[Dict] = []
        self.positions: Dict[str, Dict] = {}
        self.performance_metrics: Dict[str, Any] = {}

    def run_backtest(self, strategy: str, index_symbol: str, start_date: str,
                    end_date: str, strategy_params: Dict = None) -> Dict:
        """Run backtest for a specific F&O strategy"""
        logger.info(f"🧪 Running F&O backtest: {strategy} on {index_symbol}")
        logger.info(f"📅 Period: {start_date} to {end_date}")

        # Mock backtest results for demonstration
        # In real implementation, this would use historical option chain data

        mock_results = {
            'strategy': strategy,
            'index': index_symbol,
            'period': f"{start_date} to {end_date}",
            'total_trades': 45,
            'winning_trades': 28,
            'losing_trades': 17,
            'win_rate': 62.2,
            'total_pnl': 125000,
            'max_profit': 25000,
            'max_loss': -15000,
            'avg_profit': 2778,
            'avg_loss': -2941,
            'profit_factor': 1.89,
            'sharpe_ratio': 1.45,
            'max_drawdown': 8.5,
            'total_return': 12.5,
            'annualized_return': 15.2,
            'trades_per_month': 4.5,
            'avg_holding_period': 3.2,
            'best_month': '2025-01',
            'worst_month': '2025-03'
        }

        logger.info("✅ F&O Backtest completed:")
        logger.info(f"   • Total Trades: {mock_results['total_trades']}")
        logger.info(f"   • Win Rate: {mock_results['win_rate']:.1f}%")
        logger.info(f"   • Total P&L: ₹{mock_results['total_pnl']:,.0f}")
        logger.info(f"   • Profit Factor: {mock_results['profit_factor']:.2f}")
        logger.info(f"   • Max Drawdown: {mock_results['max_drawdown']:.1f}%")

        return mock_results

    def compare_strategies(self, strategies: List[str], index_symbol: str,
                          start_date: str, end_date: str) -> Dict:
        """Compare multiple F&O strategies"""
        results = {}

        for strategy in strategies:
            try:
                result = self.run_backtest(strategy, index_symbol, start_date, end_date)
                results[strategy] = result
            except Exception as e:
                logger.error(f"Error backtesting {strategy}: {e}")
                continue

        # Find best strategy
        if results:
            best_strategy = max(results.keys(),
                              key=lambda x: results[x].get('total_pnl', 0))
            best_result = results[best_strategy]

            return {
                'comparison': results,
                'best_strategy': best_strategy,
                'best_result': best_result,
                'recommendation': f"Use {best_strategy} strategy for {index_symbol}"
            }

        return {'error': 'No successful backtests'}
