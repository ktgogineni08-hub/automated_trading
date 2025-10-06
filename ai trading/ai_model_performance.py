#!/usr/bin/env python3
"""
AI Model Performance Tracking and Validation
Comprehensive evaluation and monitoring for ML trading models
"""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_squared_error, mean_absolute_error, r2_score,
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)
from sklearn.model_selection import cross_val_score, TimeSeriesSplit
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from pathlib import Path
import json
import pickle
from typing import Dict, List, Optional, Tuple, Any
import logging
from dataclasses import dataclass, field
import warnings
warnings.filterwarnings('ignore')

# Import existing components
try:
    from ai_trading_system import AIModelConfig, TradingLogger
except ImportError:
    class AIModelConfig:
        def __init__(self):
            self.model_dir = "ai_models"
            self.sequence_length = 60
            self.prediction_horizon = 5

    class TradingLogger:
        def __init__(self):
            self.logger = logging.getLogger('model_performance')
            handler = logging.StreamHandler()
            self.logger.addHandler(handler)

        def logger(self):
            return self.logger

# ============================================================================
# PERFORMANCE METRICS
# ============================================================================
@dataclass
class ModelMetrics:
    """Comprehensive model performance metrics"""
    symbol: str
    model_type: str
    timestamp: datetime

    # Regression metrics
    mse: float = 0.0
    rmse: float = 0.0
    mae: float = 0.0
    mape: float = 0.0
    r2_score: float = 0.0

    # Classification metrics (for directional predictions)
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0

    # Trading-specific metrics
    directional_accuracy: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0

    # Model characteristics
    training_time: float = 0.0
    prediction_time: float = 0.0
    model_size_mb: float = 0.0

    # Additional metadata
    feature_importance: Dict[str, float] = field(default_factory=dict)
    confusion_matrix: List[List[int]] = field(default_factory=list)
    predictions: List[float] = field(default_factory=list)
    actual_values: List[float] = field(default_factory=list)

class ModelPerformanceTracker:
    """Track and analyze ML model performance"""

    def __init__(self):
        self.logger = TradingLogger()
        self.metrics_history: Dict[str, List[ModelMetrics]] = {}
        self.performance_reports: Dict[str, Dict] = {}

    def calculate_regression_metrics(self, y_true: np.array, y_pred: np.array) -> Dict:
        """Calculate comprehensive regression metrics"""
        try:
            mse = mean_squared_error(y_true, y_pred)
            rmse = np.sqrt(mse)
            mae = mean_absolute_error(y_true, y_pred)
            mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
            r2 = r2_score(y_true, y_pred)

            return {
                'mse': mse,
                'rmse': rmse,
                'mae': mae,
                'mape': mape,
                'r2_score': r2
            }
        except Exception as e:
            self.logger.logger.error(f"Error calculating regression metrics: {e}")
            return {'mse': 0, 'rmse': 0, 'mae': 0, 'mape': 0, 'r2_score': 0}

    def calculate_directional_accuracy(self, y_true: np.array, y_pred: np.array) -> float:
        """Calculate directional accuracy (up/down predictions)"""
        try:
            # Calculate price changes
            y_true_changes = np.diff(y_true)
            y_pred_changes = np.diff(y_pred)

            # Determine directions
            y_true_dir = (y_true_changes > 0).astype(int)
            y_pred_dir = (y_pred_changes > 0).astype(int)

            # Calculate accuracy
            correct_directions = np.sum(y_true_dir == y_pred_dir)
            total_predictions = len(y_true_dir)

            return correct_directions / total_predictions if total_predictions > 0 else 0.0
        except Exception as e:
            self.logger.logger.error(f"Error calculating directional accuracy: {e}")
            return 0.0

    def calculate_trading_metrics(self, predictions: np.array, actual_prices: np.array,
                                initial_capital: float = 100000) -> Dict:
        """Calculate trading-specific performance metrics"""
        try:
            # Simulate trading based on predictions
            portfolio_value = initial_capital
            position = 0
            trades = []
            portfolio_values = [portfolio_value]

            for i in range(1, len(predictions)):
                current_price = actual_prices[i-1]
                predicted_price = predictions[i]
                actual_next_price = actual_prices[i]

                # Simple trading logic: buy if predicted > current, sell if predicted < current
                if predicted_price > current_price and position == 0:
                    # Buy
                    position = portfolio_value / current_price
                    portfolio_value = 0
                    trades.append(('buy', current_price))
                elif predicted_price < current_price and position > 0:
                    # Sell
                    portfolio_value = position * current_price
                    position = 0
                    trades.append(('sell', current_price))

                # Update portfolio value
                if position > 0:
                    portfolio_value = position * actual_next_price
                portfolio_values.append(portfolio_value)

            # Calculate metrics
            returns = np.diff(portfolio_values) / np.array(portfolio_values[:-1])
            sharpe_ratio = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0

            max_value = max(portfolio_values)
            min_value = min(portfolio_values)
            max_drawdown = (max_value - min_value) / max_value if max_value > 0 else 0

            win_trades = [t for t in trades if t[0] == 'sell']
            win_rate = len(win_trades) / len(trades) if trades else 0

            return {
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'win_rate': win_rate,
                'total_trades': len(trades),
                'final_portfolio_value': portfolio_values[-1]
            }
        except Exception as e:
            self.logger.logger.error(f"Error calculating trading metrics: {e}")
            return {'sharpe_ratio': 0, 'max_drawdown': 0, 'win_rate': 0, 'total_trades': 0}

    def evaluate_model(self, symbol: str, model_type: str, y_true: np.array,
                      y_pred: np.array, actual_prices: np.array,
                      training_time: float = 0, prediction_time: float = 0) -> ModelMetrics:
        """Comprehensive model evaluation"""
        try:
            # Basic regression metrics
            reg_metrics = self.calculate_regression_metrics(y_true, y_pred)

            # Directional accuracy
            directional_acc = self.calculate_directional_accuracy(y_true, y_pred)

            # Trading metrics
            trading_metrics = self.calculate_trading_metrics(y_pred, actual_prices)

            # Classification metrics (for directional prediction)
            y_true_dir = (np.diff(y_true) > 0).astype(int)
            y_pred_dir = (np.diff(y_pred) > 0).astype(int)

            if len(y_true_dir) > 0 and len(y_pred_dir) > 0:
                accuracy = accuracy_score(y_true_dir, y_pred_dir)
                precision = precision_score(y_true_dir, y_pred_dir, average='weighted', zero_division=0)
                recall = recall_score(y_true_dir, y_pred_dir, average='weighted', zero_division=0)
                f1 = f1_score(y_true_dir, y_pred_dir, average='weighted', zero_division=0)
            else:
                accuracy = precision = recall = f1 = 0.0

            # Model size (placeholder - would need actual model size)
            model_size = 0.0

            metrics = ModelMetrics(
                symbol=symbol,
                model_type=model_type,
                timestamp=datetime.now(),
                **reg_metrics,
                directional_accuracy=directional_acc,
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                f1_score=f1,
                **trading_metrics,
                training_time=training_time,
                prediction_time=prediction_time,
                model_size_mb=model_size
            )

            # Store in history
            key = f"{symbol}_{model_type}"
            if key not in self.metrics_history:
                self.metrics_history[key] = []
            self.metrics_history[key].append(metrics)

            return metrics

        except Exception as e:
            self.logger.logger.error(f"Error evaluating model {symbol}_{model_type}: {e}")
            return ModelMetrics(symbol, model_type, datetime.now())

    def generate_performance_report(self, symbol: str, model_type: str) -> Dict:
        """Generate comprehensive performance report"""
        try:
            key = f"{symbol}_{model_type}"
            if key not in self.metrics_history or not self.metrics_history[key]:
                return {'error': 'No performance data available'}

            metrics_list = self.metrics_history[key]
            latest_metrics = metrics_list[-1]

            # Calculate trends
            if len(metrics_list) > 1:
                prev_metrics = metrics_list[-2]
                trends = {
                    'mse_trend': 'improving' if latest_metrics.mse < prev_metrics.mse else 'degrading',
                    'accuracy_trend': 'improving' if latest_metrics.accuracy > prev_metrics.accuracy else 'degrading',
                    'sharpe_trend': 'improving' if latest_metrics.sharpe_ratio > prev_metrics.sharpe_ratio else 'degrading'
                }
            else:
                trends = {'mse_trend': 'stable', 'accuracy_trend': 'stable', 'sharpe_trend': 'stable'}

            # Overall assessment
            overall_score = (
                latest_metrics.r2_score * 0.3 +
                latest_metrics.directional_accuracy * 0.3 +
                latest_metrics.sharpe_ratio * 0.2 +
                latest_metrics.win_rate * 0.2
            )

            assessment = self._assess_model_performance(latest_metrics, overall_score)

            report = {
                'symbol': symbol,
                'model_type': model_type,
                'latest_metrics': latest_metrics.__dict__,
                'trends': trends,
                'overall_score': overall_score,
                'assessment': assessment,
                'history_count': len(metrics_list),
                'generated_at': datetime.now().isoformat()
            }

            self.performance_reports[key] = report
            return report

        except Exception as e:
            self.logger.logger.error(f"Error generating performance report for {symbol}_{model_type}: {e}")
            return {'error': str(e)}

    def _assess_model_performance(self, metrics: ModelMetrics, overall_score: float) -> str:
        """Assess overall model performance"""
        if overall_score > 0.7:
            return "Excellent"
        elif overall_score > 0.5:
            return "Good"
        elif overall_score > 0.3:
            return "Fair"
        elif overall_score > 0.1:
            return "Poor"
        else:
            return "Very Poor"

    def save_performance_report(self, symbol: str, model_type: str, filepath: str = None):
        """Save performance report to file"""
        try:
            report = self.generate_performance_report(symbol, model_type)
            if 'error' in report:
                self.logger.logger.error(f"Cannot save report: {report['error']}")
                return False

            if filepath is None:
                reports_dir = Path("ai_performance_reports")
                reports_dir.mkdir(exist_ok=True)
                filepath = f"{reports_dir}/{symbol}_{model_type}_report.json"

            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            self.logger.logger.info(f"Performance report saved to {filepath}")
            return True

        except Exception as e:
            self.logger.logger.error(f"Error saving performance report: {e}")
            return False

    def plot_performance_metrics(self, symbol: str, model_type: str, save_path: str = None):
        """Plot performance metrics over time"""
        try:
            key = f"{symbol}_{model_type}"
            if key not in self.metrics_history:
                self.logger.logger.error(f"No performance data for {symbol}_{model_type}")
                return False

            metrics_list = self.metrics_history[key]

            # Create plots
            fig, axes = plt.subplots(2, 2, figsize=(12, 10))
            fig.suptitle(f'Model Performance: {symbol} - {model_type}')

            # Extract data
            dates = [m.timestamp for m in metrics_list]
            mse_values = [m.mse for m in metrics_list]
            accuracy_values = [m.accuracy for m in metrics_list]
            sharpe_values = [m.sharpe_ratio for m in metrics_list]
            win_rates = [m.win_rate for m in metrics_list]

            # Plot MSE
            axes[0, 0].plot(dates, mse_values, marker='o')
            axes[0, 0].set_title('Mean Squared Error')
            axes[0, 0].tick_params(axis='x', rotation=45)

            # Plot Accuracy
            axes[0, 1].plot(dates, accuracy_values, marker='o', color='green')
            axes[0, 1].set_title('Directional Accuracy')
            axes[0, 1].tick_params(axis='x', rotation=45)

            # Plot Sharpe Ratio
            axes[1, 0].plot(dates, sharpe_values, marker='o', color='red')
            axes[1, 0].set_title('Sharpe Ratio')
            axes[1, 0].tick_params(axis='x', rotation=45)

            # Plot Win Rate
            axes[1, 1].plot(dates, win_rates, marker='o', color='orange')
            axes[1, 1].set_title('Win Rate')
            axes[1, 1].tick_params(axis='x', rotation=45)

            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                self.logger.logger.info(f"Performance plots saved to {save_path}")
            else:
                plt.show()

            return True

        except Exception as e:
            self.logger.logger.error(f"Error plotting performance metrics: {e}")
            return False

# ============================================================================
# MODEL VALIDATION
# ============================================================================
class ModelValidator:
    """Advanced model validation and cross-validation"""

    def __init__(self):
        self.logger = TradingLogger()

    def time_series_cross_validation(self, model, X: np.array, y: np.array,
                                   n_splits: int = 5) -> Dict:
        """Time series cross-validation"""
        try:
            tscv = TimeSeriesSplit(n_splits=n_splits)

            mse_scores = []
            mae_scores = []
            r2_scores = []

            for train_idx, test_idx in tscv.split(X):
                X_train, X_test = X[train_idx], X[test_idx]
                y_train, y_test = y[train_idx], y[test_idx]

                model.fit(X_train, y_train, epochs=50, batch_size=32, verbose=0)

                y_pred = model.predict(X_test, verbose=0)

                mse_scores.append(mean_squared_error(y_test, y_pred))
                mae_scores.append(mean_absolute_error(y_test, y_pred))
                r2_scores.append(r2_score(y_test, y_pred))

            return {
                'cv_mse_mean': np.mean(mse_scores),
                'cv_mse_std': np.std(mse_scores),
                'cv_mae_mean': np.mean(mae_scores),
                'cv_mae_std': np.std(mae_scores),
                'cv_r2_mean': np.mean(r2_scores),
                'cv_r2_std': np.std(r2_scores)
            }

        except Exception as e:
            self.logger.logger.error(f"Error in time series cross-validation: {e}")
            return {'error': str(e)}

    def walk_forward_validation(self, model, X: np.array, y: np.array,
                              train_size: float = 0.7) -> Dict:
        """Walk-forward validation for time series"""
        try:
            split_idx = int(len(X) * train_size)

            X_train, X_test = X[:split_idx], X[split_idx:]
            y_train, y_test = y[:split_idx], y[split_idx:]

            # Train on initial data
            model.fit(X_train, y_train, epochs=100, batch_size=32, verbose=0)

            # Walk-forward predictions
            predictions = []
            actuals = []

            for i in range(len(X_test)):
                # Predict next value
                X_window = X_test[i:i+1]
                y_pred = model.predict(X_window, verbose=0)[0][0]
                y_actual = y_test[i]

                predictions.append(y_pred)
                actuals.append(y_actual)

                # Retrain with new data point (optional - can be expensive)
                # This is a simplified version

            predictions = np.array(predictions)
            actuals = np.array(actuals)

            return {
                'walk_forward_mse': mean_squared_error(actuals, predictions),
                'walk_forward_mae': mean_absolute_error(actuals, predictions),
                'walk_forward_r2': r2_score(actuals, predictions),
                'predictions_count': len(predictions)
            }

        except Exception as e:
            self.logger.logger.error(f"Error in walk-forward validation: {e}")
            return {'error': str(e)}

    def validate_model_stability(self, model, X: np.array, y: np.array,
                               n_iterations: int = 10) -> Dict:
        """Test model stability across multiple runs"""
        try:
            metrics_list = []

            for i in range(n_iterations):
                # Split data differently each time
                idx = np.random.permutation(len(X))
                X_shuffled = X[idx]
                y_shuffled = y[idx]

                split_idx = int(len(X_shuffled) * 0.8)
                X_train, X_test = X_shuffled[:split_idx], X_shuffled[split_idx:]
                y_train, y_test = y_shuffled[:split_idx], y_shuffled[split_idx:]

                # Train model
                model_copy = model.__class__()  # Create new instance
                model_copy.fit(X_train, y_train, epochs=50, batch_size=32, verbose=0)

                # Evaluate
                y_pred = model_copy.predict(X_test, verbose=0)

                metrics = {
                    'mse': mean_squared_error(y_test, y_pred),
                    'mae': mean_absolute_error(y_test, y_pred),
                    'r2': r2_score(y_test, y_pred)
                }
                metrics_list.append(metrics)

            # Calculate stability metrics
            mse_values = [m['mse'] for m in metrics_list]
            mae_values = [m['mae'] for m in metrics_list]
            r2_values = [m['r2'] for m in metrics_list]

            return {
                'stability_mse_mean': np.mean(mse_values),
                'stability_mse_std': np.std(mse_values),
                'stability_mae_mean': np.mean(mae_values),
                'stability_mae_std': np.std(mae_values),
                'stability_r2_mean': np.mean(r2_values),
                'stability_r2_std': np.std(r2_values),
                'coefficient_of_variation_mse': np.std(mse_values) / np.mean(mse_values) if np.mean(mse_values) > 0 else 0
            }

        except Exception as e:
            self.logger.logger.error(f"Error in model stability validation: {e}")
            return {'error': str(e)}

# ============================================================================
# PERFORMANCE MONITORING
# ============================================================================
class AIModelMonitor:
    """Monitor AI model performance in production"""

    def __init__(self):
        self.logger = TradingLogger()
        self.performance_tracker = ModelPerformanceTracker()
        self.validator = ModelValidator()
        self.alert_thresholds = {
            'accuracy_drop': 0.1,  # 10% drop in accuracy
            'mse_increase': 2.0,   # 2x increase in MSE
            'sharpe_negative': True  # Alert if Sharpe ratio becomes negative
        }

    def monitor_model_performance(self, symbol: str, model_type: str,
                                current_predictions: np.array, actual_values: np.array) -> Dict:
        """Monitor model performance and generate alerts"""
        try:
            # Evaluate current performance
            metrics = self.performance_tracker.evaluate_model(
                symbol, model_type, actual_values, current_predictions, actual_values
            )

            # Check for performance degradation
            alerts = []
            key = f"{symbol}_{model_type}"

            if key in self.performance_tracker.metrics_history and len(self.performance_tracker.metrics_history[key]) > 1:
                prev_metrics = self.performance_tracker.metrics_history[key][-2]

                # Check accuracy drop
                if metrics.accuracy < prev_metrics.accuracy - self.alert_thresholds['accuracy_drop']:
                    alerts.append(f"Accuracy dropped by {(prev_metrics.accuracy - metrics.accuracy)*100:.1f}%")

                # Check MSE increase
                if metrics.mse > prev_metrics.mse * self.alert_thresholds['mse_increase']:
                    alerts.append(f"MSE increased by {((metrics.mse / prev_metrics.mse) - 1)*100:.1f}%")

                # Check Sharpe ratio
                if self.alert_thresholds['sharpe_negative'] and metrics.sharpe_ratio < 0:
                    alerts.append("Sharpe ratio became negative")

            # Generate monitoring report
            report = {
                'symbol': symbol,
                'model_type': model_type,
                'current_metrics': metrics.__dict__,
                'alerts': alerts,
                'alert_count': len(alerts),
                'status': 'healthy' if len(alerts) == 0 else 'degraded' if len(alerts) < 3 else 'critical'
            }

            return report

        except Exception as e:
            self.logger.logger.error(f"Error monitoring model performance: {e}")
            return {'error': str(e)}

    def generate_monitoring_dashboard(self, symbols: List[str], save_path: str = None):
        """Generate monitoring dashboard"""
        try:
            # This would create a comprehensive dashboard
            # For now, return summary statistics
            summary = {}

            for symbol in symbols:
                for model_type in ['lstm', 'transformer']:
                    key = f"{symbol}_{model_type}"
                    if key in self.performance_tracker.metrics_history:
                        metrics_list = self.performance_tracker.metrics_history[key]
                        latest = metrics_list[-1]

                        summary[key] = {
                            'latest_accuracy': latest.accuracy,
                            'latest_sharpe': latest.sharpe_ratio,
                            'latest_mse': latest.mse,
                            'trend': 'improving' if len(metrics_list) > 1 and latest.accuracy > metrics_list[-2].accuracy else 'stable'
                        }

            if save_path:
                # Save summary to file
                with open(save_path, 'w') as f:
                    json.dump(summary, f, indent=2, default=str)

            return summary

        except Exception as e:
            self.logger.logger.error(f"Error generating monitoring dashboard: {e}")
            return {'error': str(e)}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def create_performance_tracker() -> ModelPerformanceTracker:
    """Create model performance tracker"""
    return ModelPerformanceTracker()

def validate_model_performance(symbol: str, model_type: str, predictions: np.array,
                            actual_values: np.array) -> Dict:
    """Quick model validation"""
    tracker = ModelPerformanceTracker()
    metrics = tracker.evaluate_model(symbol, model_type, actual_values, predictions, actual_values)
    return tracker.generate_performance_report(symbol, model_type)

def generate_performance_dashboard(symbols: List[str], save_path: str = None) -> Dict:
    """Generate performance dashboard for multiple models"""
    monitor = AIModelMonitor()
    return monitor.generate_monitoring_dashboard(symbols, save_path)

# ============================================================================
# MAIN EXECUTION
# ============================================================================
if __name__ == "__main__":
    print("📊 AI Model Performance Tracking")
    print("=" * 50)
    print("Features:")
    print("• Comprehensive Model Evaluation")
    print("• Time Series Cross-Validation")
    print("• Walk-Forward Validation")
    print("• Trading Performance Metrics")
    print("• Performance Monitoring & Alerts")
    print("• Automated Reporting")
    print("=" * 50)

    # Example usage
    try:
        tracker = ModelPerformanceTracker()
        validator = ModelValidator()
        monitor = AIModelMonitor()

        print("✅ AI Model Performance System initialized!")
        print("💡 Use validate_model_performance() for quick evaluation")
        print("💡 Use generate_performance_dashboard() for comprehensive reports")

    except Exception as e:
        print(f"❌ Error initializing performance system: {e}")