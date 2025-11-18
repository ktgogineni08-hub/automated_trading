#!/usr/bin/env python3
"""
Advanced AI Backtesting Engine
Comprehensive backtesting framework for ML-powered trading strategies
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import json
import pickle
from typing import Dict, List, Optional, Tuple, Any
import logging
from dataclasses import dataclass, field
import warnings
import matplotlib.pyplot as plt
import seaborn as sns
from concurrent.futures import ThreadPoolExecutor
import itertools
warnings.filterwarnings('ignore')

# Import existing components
try:
    from ai_trading_system import AIMarketPredictor, AIModelConfig, TradingLogger
    from ai_model_performance import ModelPerformanceTracker, ModelValidator
    from enhanced_trading_system_complete import UnifiedPortfolio, safe_float_conversion
except ImportError:
    class AIMarketPredictor:
        def __init__(self):
            pass

    class AIModelConfig:
        def __init__(self):
            self.sequence_length = 60
            self.prediction_horizon = 5

    class TradingLogger:
        def __init__(self):
            self.logger = logging.getLogger('backtesting')
            handler = logging.StreamHandler()
            self.logger.addHandler(handler)

        def logger(self):
            return self.logger

    class ModelPerformanceTracker:
        def __init__(self):
            pass

    class ModelValidator:
        def __init__(self):
            pass

    class UnifiedPortfolio:
        def __init__(self):
            self.cash = 100000
            self.positions = {}
            self.trades_count = 0
            self.total_pnl = 0

        def execute_trade(self, symbol, shares, price, side, timestamp=None, confidence=0.5, sector=None):
            return {'symbol': symbol, 'side': side, 'shares': shares, 'price': price}

    def safe_float_conversion(value, default=0.0):
        try:
            return float(value) if value is not None and not pd.isna(value) else default
        except:
            return default

# ============================================================================
# BACKTESTING CONFIGURATION
# ============================================================================
@dataclass
class BacktestConfig:
    """Configuration for AI backtesting"""
    # Time parameters - using dynamic defaults
    start_date: str = None  # Will be set dynamically
    end_date: str = None    # Will be set dynamically
    symbols: List[str] = field(default_factory=lambda: ["HDFCBANK", "ICICIBANK", "TCS", "INFY", "RELIANCE"])

    # Capital and risk
    initial_capital: float = 1000000.0
    max_positions: int = 10
    risk_per_trade: float = 0.02  # 2% of capital per trade

    # AI model parameters
    model_types: List[str] = field(default_factory=lambda: ['lstm', 'transformer'])
    confidence_threshold: float = 0.6
    prediction_horizon: int = 5

    # Trading parameters
    position_size_method: str = 'fixed'  # 'fixed', 'kelly', 'volatility'
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.15
    trailing_stop: bool = True

    # Backtesting parameters
    transaction_costs: float = 0.001  # 0.1% transaction costs
    slippage: float = 0.001  # 0.1% slippage
    benchmark_symbol: str = 'NIFTY'  # Benchmark for comparison

    # Walk-forward parameters
    walk_forward_window: int = 252  # Trading days
    retrain_frequency: int = 30    # Retrain every 30 days

    # Output parameters
    save_results: bool = True
    results_dir: str = "ai_backtest_results"
    generate_plots: bool = True

    def __post_init__(self):
        """Set dynamic defaults if not provided"""
        if self.start_date is None:
            # Default to 1 year ago
            from datetime import datetime, timedelta
            end_date = datetime.now().date() if self.end_date is None else datetime.strptime(self.end_date, '%Y-%m-%d').date()
            start_date = end_date - timedelta(days=365)
            self.start_date = start_date.strftime('%Y-%m-%d')

        if self.end_date is None:
            # Default to today
            from datetime import datetime
            self.end_date = datetime.now().strftime('%Y-%m-%d')

# ============================================================================
# AI BACKTESTING ENGINE
# ============================================================================
class AIBacktestingEngine:
    """Advanced backtesting engine for AI trading strategies"""

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.logger = TradingLogger()
        self.ai_predictor = AIMarketPredictor()
        self.performance_tracker = ModelPerformanceTracker()
        self.validator = ModelValidator()

        # Create results directory
        if self.config.save_results:
            Path(self.config.results_dir).mkdir(exist_ok=True)

        self.logger.info("🤖 AI Backtesting Engine initialized")

    def run_ai_backtest(self, data_provider) -> Dict:
        """Run comprehensive AI backtest"""
        try:
            self.logger.info("🚀 Starting AI Backtest")
            self.logger.info(f"Symbols: {', '.join(self.config.symbols)}")
            self.logger.info(f"Period: {self.config.start_date} to {self.config.end_date}")
            self.logger.info(f"Initial Capital: ₹{self.config.initial_capital:,.0f}")

            # Initialize portfolio
            portfolio = UnifiedPortfolio(
                initial_cash=self.config.initial_capital,
                trading_mode='backtest'
            )

            # Get historical data
            all_data = {}
            for symbol in self.config.symbols:
                try:
                    df = data_provider.fetch_with_retry(symbol, interval="5minute", days=365)
                    if not df.empty:
                        all_data[symbol] = df
                    else:
                        self.logger.warning(f"No data for {symbol}")
                except Exception as e:
                    self.logger.error(f"Error fetching data for {symbol}: {e}")

            if not all_data:
                return {'error': 'No data available for backtesting'}

            # Run walk-forward backtest
            results = self._walk_forward_backtest(all_data, portfolio)

            # Generate comprehensive report
            report = self._generate_backtest_report(results, portfolio)

            # Save results
            if self.config.save_results:
                self._save_backtest_results(report)

            # Generate plots
            if self.config.generate_plots:
                self._generate_performance_plots(report)

            self.logger.info("✅ AI Backtest completed successfully!")
            return report

        except Exception as e:
            self.logger.error(f"Error in AI backtest: {e}")
            return {'error': str(e)}

    def _walk_forward_backtest(self, all_data: Dict, portfolio: UnifiedPortfolio) -> Dict:
        """Run walk-forward backtest with model retraining"""
        try:
            results = {
                'trades': [],
                'daily_returns': [],
                'portfolio_values': [],
                'predictions': {},
                'model_performance': {}
            }

            # Convert dates to datetime
            start_date = pd.to_datetime(self.config.start_date)
            end_date = pd.to_datetime(self.config.end_date)

            # Get all trading days
            all_dates = set()
            for symbol, df in all_data.items():
                symbol_dates = df.index.date
                all_dates.update(symbol_dates)

            trading_days = sorted([d for d in all_dates if start_date.date() <= d <= end_date.date()])

            if len(trading_days) < self.config.walk_forward_window:
                return {'error': 'Insufficient data for walk-forward analysis'}

            # Walk-forward loop
            current_date_idx = self.config.walk_forward_window

            while current_date_idx < len(trading_days):
                current_date = trading_days[current_date_idx]
                train_end_date = trading_days[current_date_idx - 1]

                # Check if we need to retrain models
                retrain_needed = (
                    current_date_idx == self.config.walk_forward_window or
                    (current_date_idx - self.config.walk_forward_window) % self.config.retrain_frequency == 0
                )

                if retrain_needed:
                    self.logger.info(f"🔄 Retraining models for date: {current_date}")

                    # Retrain models for each symbol
                    for symbol, df in all_data.items():
                        try:
                            # Get training data up to current date
                            train_data = df[df.index.date <= train_end_date]

                            if len(train_data) > 100:  # Minimum data requirement
                                # Train LSTM model
                                lstm_result = self.ai_predictor.predictive_models.train_model(
                                    symbol, train_data, 'lstm'
                                )
                                results['model_performance'][f'{symbol}_lstm'] = lstm_result

                                # Train Transformer model
                                transformer_result = self.ai_predictor.predictive_models.train_model(
                                    symbol, train_data, 'transformer'
                                )
                                results['model_performance'][f'{symbol}_transformer'] = transformer_result

                        except Exception as e:
                            self.logger.error(f"Error training model for {symbol}: {e}")

                # Get predictions for current date
                current_predictions = {}
                for symbol, df in all_data.items():
                    try:
                        # Get data up to current date
                        current_data = df[df.index.date <= current_date]

                        if len(current_data) > 50:  # Minimum data for prediction
                            # Get AI predictions
                            ai_signals = self.ai_predictor.strategy_integrator.generate_ai_signals(
                                symbol, current_data
                            )

                            if 'combined_action' in ai_signals and ai_signals['combined_confidence'] >= self.config.confidence_threshold:
                                current_predictions[symbol] = ai_signals

                    except Exception as e:
                        self.logger.error(f"Error getting predictions for {symbol}: {e}")

                # Execute trades based on predictions
                daily_trades = self._execute_ai_trades(
                    current_predictions, all_data, current_date, portfolio
                )

                results['trades'].extend(daily_trades)

                # Record portfolio state
                portfolio_value = portfolio.calculate_total_value()
                results['portfolio_values'].append({
                    'date': current_date,
                    'value': portfolio_value,
                    'cash': portfolio.cash,
                    'positions': len(portfolio.positions)
                })

                # Calculate daily return
                if len(results['portfolio_values']) > 1:
                    prev_value = results['portfolio_values'][-2]['value']
                    daily_return = (portfolio_value - prev_value) / prev_value
                    results['daily_returns'].append(daily_return)

                current_date_idx += 1

            return results

        except Exception as e:
            self.logger.error(f"Error in walk-forward backtest: {e}")
            return {'error': str(e)}

    def _execute_ai_trades(self, predictions: Dict, all_data: Dict,
                          current_date: datetime.date, portfolio: UnifiedPortfolio) -> List[Dict]:
        """Execute trades based on AI predictions"""
        try:
            trades = []

            for symbol, prediction in predictions.items():
                try:
                    # Get current market data
                    df = all_data[symbol]
                    current_data = df[df.index.date == current_date]

                    if current_data.empty:
                        continue

                    current_price = safe_float_conversion(current_data['close'].iloc[-1])
                    if current_price <= 0:
                        continue

                    action = prediction['combined_action']
                    confidence = prediction['combined_confidence']

                    # Calculate position size
                    position_size = self._calculate_position_size(
                        symbol, current_price, confidence, portfolio
                    )

                    if position_size <= 0:
                        continue

                    shares = int(position_size // current_price)

                    if shares <= 0:
                        continue

                    # Execute trade
                    if action == 'buy' and symbol not in portfolio.positions:
                        # Check if we can open new position
                        if len(portfolio.positions) < self.config.max_positions:
                            trade = portfolio.execute_trade(
                                symbol=symbol,
                                shares=shares,
                                price=current_price,
                                side='buy',
                                confidence=confidence,
                                sector='AI'
                            )

                            if trade:
                                trades.append({
                                    **trade,
                                    'date': current_date,
                                    'ai_prediction': prediction
                                })

                    elif action == 'sell' and symbol in portfolio.positions:
                        # Close existing position
                        position = portfolio.positions[symbol]
                        trade = portfolio.execute_trade(
                            symbol=symbol,
                            shares=position['shares'],
                            price=current_price,
                            side='sell',
                            confidence=confidence,
                            sector='AI'
                        )

                        if trade:
                            trades.append({
                                **trade,
                                'date': current_date,
                                'ai_prediction': prediction
                            })

                except Exception as e:
                    self.logger.error(f"Error executing AI trade for {symbol}: {e}")

            return trades

        except Exception as e:
            self.logger.error(f"Error executing AI trades: {e}")
            return []

    def _calculate_position_size(self, symbol: str, price: float,
                               confidence: float, portfolio: UnifiedPortfolio) -> float:
        """Calculate optimal position size based on AI confidence and risk management"""
        try:
            # Base position size
            base_size = portfolio.cash * self.config.risk_per_trade

            # Adjust based on confidence
            confidence_multiplier = min(confidence * 2, 1.5)  # Max 1.5x for high confidence

            # Adjust based on volatility (simplified)
            volatility_multiplier = 1.0  # Could be calculated from historical volatility

            position_value = base_size * confidence_multiplier * volatility_multiplier

            return position_value

        except Exception as e:
            self.logger.error(f"Error calculating position size for {symbol}: {e}")
            return 0.0

    def _generate_backtest_report(self, results: Dict, portfolio: UnifiedPortfolio) -> Dict:
        """Generate comprehensive backtest report"""
        try:
            if 'error' in results:
                return results

            # Calculate performance metrics
            portfolio_values = [pv['value'] for pv in results['portfolio_values']]
            daily_returns = results['daily_returns']

            if not portfolio_values or not daily_returns:
                return {'error': 'No portfolio data available'}

            # Basic metrics
            initial_value = self.config.initial_capital
            final_value = portfolio_values[-1]
            total_return = (final_value - initial_value) / initial_value

            # Risk metrics
            returns_array = np.array(daily_returns)
            sharpe_ratio = np.mean(returns_array) / np.std(returns_array) if np.std(returns_array) > 0 else 0
            max_drawdown = self._calculate_max_drawdown(portfolio_values)

            # Trade metrics
            trades = results['trades']
            winning_trades = [t for t in trades if 'pnl' in t and t['pnl'] > 0]
            losing_trades = [t for t in trades if 'pnl' in t and t['pnl'] <= 0]

            win_rate = len(winning_trades) / len(trades) if trades else 0
            avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0

            # AI-specific metrics
            ai_predictions = results['predictions']
            successful_predictions = 0
            total_predictions = 0

            for symbol, pred_list in ai_predictions.items():
                for pred in pred_list:
                    total_predictions += 1
                    if pred.get('success', False):
                        successful_predictions += 1

            prediction_accuracy = successful_predictions / total_predictions if total_predictions > 0 else 0

            report = {
                'summary': {
                    'initial_capital': initial_value,
                    'final_capital': final_value,
                    'total_return': total_return,
                    'total_return_pct': total_return * 100,
                    'sharpe_ratio': sharpe_ratio,
                    'max_drawdown': max_drawdown,
                    'max_drawdown_pct': max_drawdown * 100,
                    'total_trades': len(trades),
                    'winning_trades': len(winning_trades),
                    'losing_trades': len(losing_trades),
                    'win_rate': win_rate,
                    'avg_win': avg_win,
                    'avg_loss': avg_loss,
                    'profit_factor': abs(avg_win * len(winning_trades) / (avg_loss * len(losing_trades))) if losing_trades else float('inf')
                },
                'ai_metrics': {
                    'prediction_accuracy': prediction_accuracy,
                    'total_predictions': total_predictions,
                    'successful_predictions': successful_predictions,
                    'model_performance': results['model_performance']
                },
                'risk_metrics': {
                    'volatility': np.std(returns_array),
                    'var_95': np.percentile(returns_array, 5),  # 95% Value at Risk
                    'var_99': np.percentile(returns_array, 1),  # 99% Value at Risk
                    'calmar_ratio': total_return / max_drawdown if max_drawdown > 0 else float('inf')
                },
                'trades': trades,
                'portfolio_history': results['portfolio_values'],
                'daily_returns': daily_returns,
                'config': self.config.__dict__,
                'generated_at': datetime.now().isoformat()
            }

            return report

        except Exception as e:
            self.logger.error(f"Error generating backtest report: {e}")
            return {'error': str(e)}

    def _calculate_max_drawdown(self, portfolio_values: List[float]) -> float:
        """Calculate maximum drawdown"""
        try:
            peak = portfolio_values[0]
            max_drawdown = 0

            for value in portfolio_values:
                if value > peak:
                    peak = value
                drawdown = (peak - value) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

            return max_drawdown

        except Exception as e:
            self.logger.error(f"Error calculating max drawdown: {e}")
            return 0.0

    def _save_backtest_results(self, report: Dict):
        """Save backtest results to files"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # Save main report
            report_file = f"{self.config.results_dir}/ai_backtest_report_{timestamp}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            # Save trades to CSV
            if 'trades' in report and report['trades']:
                trades_df = pd.DataFrame(report['trades'])
                trades_file = f"{self.config.results_dir}/ai_trades_{timestamp}.csv"
                trades_df.to_csv(trades_file, index=False)

            # Save portfolio history to CSV
            if 'portfolio_history' in report and report['portfolio_history']:
                portfolio_df = pd.DataFrame(report['portfolio_history'])
                portfolio_file = f"{self.config.results_dir}/ai_portfolio_history_{timestamp}.csv"
                portfolio_df.to_csv(portfolio_file, index=False)

            self.logger.info(f"✅ Backtest results saved to {self.config.results_dir}")

        except Exception as e:
            self.logger.error(f"Error saving backtest results: {e}")

    def _generate_performance_plots(self, report: Dict):
        """Generate performance visualization plots"""
        try:
            if 'error' in report:
                return

            # Portfolio value over time
            portfolio_history = report['portfolio_history']
            dates = [pd.to_datetime(ph['date']) for ph in portfolio_history]
            values = [ph['value'] for ph in portfolio_history]

            plt.figure(figsize=(12, 8))

            # Plot 1: Portfolio Value
            plt.subplot(2, 2, 1)
            plt.plot(dates, values)
            plt.title('Portfolio Value Over Time')
            plt.xlabel('Date')
            plt.ylabel('Portfolio Value (₹)')
            plt.grid(True)

            # Plot 2: Daily Returns
            plt.subplot(2, 2, 2)
            daily_returns = report['daily_returns']
            plt.plot(daily_returns)
            plt.title('Daily Returns')
            plt.xlabel('Trading Day')
            plt.ylabel('Return')
            plt.grid(True)

            # Plot 3: Drawdown
            plt.subplot(2, 2, 3)
            portfolio_values = [ph['value'] for ph in portfolio_history]
            peak = np.maximum.accumulate(portfolio_values)
            drawdown = (peak - portfolio_values) / peak
            plt.plot(dates, drawdown)
            plt.title('Portfolio Drawdown')
            plt.xlabel('Date')
            plt.ylabel('Drawdown')
            plt.grid(True)

            # Plot 4: Trade Distribution
            plt.subplot(2, 2, 4)
            if 'trades' in report and report['trades']:
                pnls = [t.get('pnl', 0) for t in report['trades'] if 'pnl' in t]
                plt.hist(pnls, bins=50, alpha=0.7)
                plt.title('Trade P&L Distribution')
                plt.xlabel('P&L (₹)')
                plt.ylabel('Frequency')
                plt.grid(True)

            plt.tight_layout()

            # Save plot
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            plot_file = f"{self.config.results_dir}/ai_backtest_plots_{timestamp}.png"
            plt.savefig(plot_file, dpi=300, bbox_inches='tight')

            self.logger.info(f"✅ Performance plots saved to {plot_file}")

        except Exception as e:
            self.logger.error(f"Error generating performance plots: {e}")

# ============================================================================
# PARAMETER OPTIMIZATION
# ============================================================================
class AIParameterOptimizer:
    """Optimize AI model parameters using grid search or random search"""

    def __init__(self):
        self.logger = TradingLogger()

    def grid_search_optimization(self, data_provider, symbol: str,
                               param_grid: Dict, n_folds: int = 5) -> Dict:
        """Grid search for optimal parameters"""
        try:
            # Generate all parameter combinations
            keys = list(param_grid.keys())
            values = list(param_grid.values())
            param_combinations = list(itertools.product(*values))

            best_params = None
            best_score = -float('inf')
            results = []

            for params in param_combinations:
                param_dict = dict(zip(keys, params))

                try:
                    # Create config with current parameters
                    config = AIModelConfig()
                    for key, value in param_dict.items():
                        if hasattr(config, key):
                            setattr(config, key, value)

                    # Initialize AI predictor with current config
                    ai_predictor = AIMarketPredictor(config)

                    # Get data
                    df = data_provider.fetch_with_retry(symbol, interval="5minute", days=180)
                    if df.empty:
                        continue

                    # Cross-validation
                    validator = ModelValidator()
                    cv_results = validator.time_series_cross_validation(
                        ai_predictor.predictive_models.build_lstm_model((60, 20)),
                        df.values, df['close'].values, n_folds
                    )

                    if 'error' in cv_results:
                        continue

                    # Calculate combined score
                    score = cv_results.get('cv_r2_mean', 0) * 0.7 + (1 - cv_results.get('cv_mse_mean', 1)) * 0.3

                    results.append({
                        'params': param_dict,
                        'cv_results': cv_results,
                        'score': score
                    })

                    if score > best_score:
                        best_score = score
                        best_params = param_dict

                except Exception as e:
                    self.logger.error(f"Error testing parameters {param_dict}: {e}")
                    continue

            return {
                'best_params': best_params,
                'best_score': best_score,
                'all_results': results
            }

        except Exception as e:
            self.logger.error(f"Error in grid search optimization: {e}")
            return {'error': str(e)}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def run_ai_backtest(config: BacktestConfig = None, data_provider=None) -> Dict:
    """Run AI backtest with default configuration"""
    engine = AIBacktestingEngine(config)
    return engine.run_ai_backtest(data_provider)

def optimize_ai_parameters(data_provider, symbol: str, param_grid: Dict = None) -> Dict:
    """Optimize AI model parameters"""
    if param_grid is None:
        param_grid = {
            'lstm_units': [[50, 30, 20], [64, 32, 16], [100, 50, 25]],
            'dropout_rate': [0.1, 0.2, 0.3],
            'learning_rate': [0.001, 0.01, 0.0001]
        }

    optimizer = AIParameterOptimizer()
    return optimizer.grid_search_optimization(data_provider, symbol, param_grid)

# ============================================================================
# MAIN EXECUTION
# ============================================================================
if __name__ == "__main__":
    print("🔬 AI Backtesting Engine")
    print("=" * 50)
    print("Advanced Features:")
    print("• Walk-Forward Backtesting")
    print("• AI Model Retraining")
    print("• Comprehensive Performance Metrics")
    print("• Risk Analysis")
    print("• Parameter Optimization")
    print("• Visualization & Reporting")
    print("=" * 50)

    # Example usage
    try:
        config = BacktestConfig()
        engine = AIBacktestingEngine(config)

        print("✅ AI Backtesting Engine initialized!")
        print("💡 Use run_ai_backtest() to start backtesting")
        print("💡 Use optimize_ai_parameters() for parameter optimization")

    except Exception as e:
        print(f"❌ Error initializing backtesting engine: {e}")