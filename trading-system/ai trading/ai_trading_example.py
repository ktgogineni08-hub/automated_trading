#!/usr/bin/env python3
"""
AI Trading System - Usage Examples and Integration Guide
Comprehensive examples showing how to use the AI trading system
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# Import AI Trading System components
try:
    from ai_trading_system import (
        create_ai_trading_system, train_ai_models_for_nifty50,
        get_ai_market_insights, AIMarketPredictor, AIModelConfig
    )
    from ai_model_performance import (
        create_performance_tracker, validate_model_performance,
        generate_performance_dashboard
    )
    from ai_backtesting_engine import (
        run_ai_backtest, optimize_ai_parameters, BacktestConfig
    )
    from enhanced_trading_system_complete import DataProvider
except ImportError as e:
    print(f"❌ Error importing AI components: {e}")
    print("Make sure all AI components are installed and available")
    sys.exit(1)

# ============================================================================
# EXAMPLE 1: BASIC AI MODEL TRAINING
# ============================================================================
def example_basic_training():
    """Example: Train AI models for NIFTY 50 stocks"""
    print("🤖 Example 1: Basic AI Model Training")
    print("=" * 50)

    try:
        # Initialize data provider
        data_provider = DataProvider(use_yf_fallback=True)

        # Define symbols to train
        symbols = ["HDFCBANK", "ICICIBANK", "TCS", "INFY", "RELIANCE"]

        print(f"📈 Training AI models for: {', '.join(symbols)}")

        # Train models
        results = train_ai_models_for_nifty50(data_provider, symbols)

        print("✅ Training completed!")
        print(f"📊 Results: {len(results)} models trained")

        # Display results summary
        for symbol, result in results.items():
            if 'error' not in result:
                metrics = result.get('metrics', {})
                print(f"  {symbol}: MSE={metrics.get('mse', 0):.6f}, R²={metrics.get('r2_score', 0):.4f}")
            else:
                print(f"  {symbol}: ❌ {result['error']}")

        return results

    except Exception as e:
        print(f"❌ Error in basic training: {e}")
        return {}

# ============================================================================
# EXAMPLE 2: AI MARKET PREDICTIONS
# ============================================================================
def example_market_predictions():
    """Example: Get AI-powered market predictions"""
    print("\n🔮 Example 2: AI Market Predictions")
    print("=" * 50)

    try:
        # Initialize data provider
        data_provider = DataProvider(use_yf_fallback=True)

        # Define symbols
        symbols = ["HDFCBANK", "ICICIBANK", "TCS"]

        print(f"🔍 Getting AI predictions for: {', '.join(symbols)}")

        # Get market insights
        insights = get_ai_market_insights(symbols, data_provider)

        if 'error' in insights:
            print(f"❌ Error: {insights['error']}")
            return {}

        print("✅ AI Analysis completed!")

        # Display predictions
        predictions = insights.get('predictions', {})
        for symbol, pred in predictions.items():
            if 'error' not in pred:
                action = pred.get('combined_action', 'HOLD')
                confidence = pred.get('combined_confidence', 0)
                print(f"  {symbol}: {action} ({confidence:.1%})")

                # Show price prediction if available
                price_pred = pred.get('price_prediction', {})
                if 'predicted_price' in price_pred:
                    current = price_pred.get('current_price', 0)
                    predicted = price_pred.get('predicted_price', 0)
                    change = (predicted - current) / current
                    print(f"    Price: ₹{current:.2f} → ₹{predicted:.2f} ({change:+.1%})")

                # Show sentiment
                sentiment = pred.get('sentiment', {})
                if 'overall_sentiment' in sentiment:
                    sent = sentiment['overall_sentiment']
                    score = sentiment.get('combined_score', 0)
                    print(f"    Sentiment: {sent.upper()} ({score:+.2f})")
            else:
                print(f"  {symbol}: ❌ {pred['error']}")

        return insights

    except Exception as e:
        print(f"❌ Error in market predictions: {e}")
        return {}

# ============================================================================
# EXAMPLE 3: COMPREHENSIVE BACKTESTING
# ============================================================================
def example_comprehensive_backtest():
    """Example: Run comprehensive AI backtest"""
    print("\n📊 Example 3: Comprehensive AI Backtest")
    print("=" * 50)

    try:
        # Configure backtest with dynamic dates
        from datetime import datetime, timedelta
        today = datetime.now().date()
        default_start = (today - timedelta(days=180)).strftime('%Y-%m-%d')  # 6 months ago
        default_end = today.strftime('%Y-%m-%d')  # Today

        config = BacktestConfig(
            start_date=default_start,
            end_date=default_end,
            symbols=["HDFCBANK", "ICICIBANK", "TCS", "INFY"],
            initial_capital=1000000,
            max_positions=5,
            confidence_threshold=0.6,
            save_results=True,
            generate_plots=True
        )

        print("⚙️ Backtest Configuration:")
        print(f"  Period: {config.start_date} to {config.end_date}")
        print(f"  Symbols: {', '.join(config.symbols)}")
        print(f"  Capital: ₹{config.initial_capital:,.0f}")
        print(f"  Max Positions: {config.max_positions}")
        print(f"  Confidence Threshold: {config.confidence_threshold}")

        # Initialize data provider
        data_provider = DataProvider(use_yf_fallback=True)

        # Run backtest
        print("\n🚀 Running AI Backtest...")
        results = run_ai_backtest(config, data_provider)

        if 'error' in results:
            print(f"❌ Backtest failed: {results['error']}")
            return {}

        # Display results
        summary = results.get('summary', {})
        print("\n✅ Backtest Results:")
        print(f"  Initial Capital: ₹{summary.get('initial_capital', 0):,.0f}")
        print(f"  Final Capital: ₹{summary.get('final_capital', 0):,.0f}")
        print(f"  Total Return: {summary.get('total_return_pct', 0):.2f}%")
        print(f"  Sharpe Ratio: {summary.get('sharpe_ratio', 0):.3f}")
        print(f"  Max Drawdown: {summary.get('max_drawdown_pct', 0):.2f}%")
        print(f"  Total Trades: {summary.get('total_trades', 0)}")
        print(f"  Win Rate: {summary.get('win_rate', 0):.1%}")

        # AI-specific metrics
        ai_metrics = results.get('ai_metrics', {})
        print("\n🤖 AI Performance:")
        print(f"  Prediction Accuracy: {ai_metrics.get('prediction_accuracy', 0):.1%}")
        print(f"  Total Predictions: {ai_metrics.get('total_predictions', 0)}")

        return results

    except Exception as e:
        print(f"❌ Error in comprehensive backtest: {e}")
        return {}

# ============================================================================
# EXAMPLE 4: MODEL PERFORMANCE VALIDATION
# ============================================================================
def example_model_validation():
    """Example: Validate and track model performance"""
    print("\n📈 Example 4: Model Performance Validation")
    print("=" * 50)

    try:
        # Initialize performance tracker
        tracker = create_performance_tracker()

        # Mock predictions and actual values for demonstration
        # In real usage, these would come from your model predictions
        symbols = ["HDFCBANK", "ICICIBANK"]
        model_types = ["lstm", "transformer"]

        for symbol in symbols:
            for model_type in model_types:
                # Generate mock data
                np.random.seed(42)
                actual_values = np.random.uniform(100, 200, 100)
                predictions = actual_values * (1 + np.random.normal(0, 0.02, 100))

                # Validate model
                report = validate_model_performance(
                    symbol, model_type, predictions, actual_values
                )

                if 'error' not in report:
                    metrics = report.get('latest_metrics', {})
                    print(f"  {symbol}_{model_type}:")
                    print(f"    Accuracy: {metrics.get('accuracy', 0):.3f}")
                    print(f"    Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.3f}")
                    print(f"    MSE: {metrics.get('mse', 0):.4f}")
                else:
                    print(f"  {symbol}_{model_type}: ❌ {report['error']}")

        # Generate performance dashboard
        dashboard = generate_performance_dashboard(symbols)
        print("\n📊 Performance Dashboard Summary:")
        for model_key, metrics in dashboard.items():
            print(f"  {model_key}: {metrics.get('latest_accuracy', 0):.3f} accuracy")

        return dashboard

    except Exception as e:
        print(f"❌ Error in model validation: {e}")
        return {}

# ============================================================================
# EXAMPLE 5: PARAMETER OPTIMIZATION
# ============================================================================
def example_parameter_optimization():
    """Example: Optimize AI model parameters"""
    print("\n🔧 Example 5: Parameter Optimization")
    print("=" * 50)

    try:
        # Initialize data provider
        data_provider = DataProvider(use_yf_fallback=True)

        # Define parameter grid for optimization
        param_grid = {
            'lstm_units': [[50, 30, 20], [64, 32, 16]],
            'dropout_rate': [0.1, 0.2],
            'learning_rate': [0.001, 0.01]
        }

        print("🔍 Optimizing parameters for HDFCBANK...")
        print(f"Parameter grid: {param_grid}")

        # Run optimization
        results = optimize_ai_parameters(data_provider, "HDFCBANK", param_grid)

        if 'error' in results:
            print(f"❌ Optimization failed: {results['error']}")
            return {}

        # Display best parameters
        best_params = results.get('best_params', {})
        best_score = results.get('best_score', 0)

        print("\n✅ Optimization Results:")
        print(f"  Best Score: {best_score:.4f}")
        print(f"  Best Parameters: {best_params}")

        # Display all results
        all_results = results.get('all_results', [])
        print(f"\n📊 All Results ({len(all_results)} combinations):")
        for i, result in enumerate(all_results[:5]):  # Show top 5
            params = result.get('params', {})
            score = result.get('score', 0)
            print(f"  {i+1}. Score: {score:.4f}, Params: {params}")

        return results

    except Exception as e:
        print(f"❌ Error in parameter optimization: {e}")
        return {}

# ============================================================================
# EXAMPLE 6: INTEGRATION WITH EXISTING SYSTEM
# ============================================================================
def example_system_integration():
    """Example: Integrate AI with existing trading system"""
    print("\n🔗 Example 6: System Integration")
    print("=" * 50)

    try:
        # Initialize existing system (mock)
        class MockExistingSystem:
            def __init__(self):
                self.positions = {}
                self.cash = 1000000

        existing_system = MockExistingSystem()

        # Create AI-enhanced system
        ai_enhanced_system = create_ai_trading_system(existing_system)

        print("✅ AI-Enhanced Trading System created!")

        # Mock market data
        mock_data = pd.DataFrame({
            'close': np.random.uniform(100, 200, 100),
            'volume': np.random.randint(1000, 10000, 100),
            'high': np.random.uniform(105, 205, 100),
            'low': np.random.uniform(95, 195, 100)
        })

        # Get enhanced signals
        symbol = "HDFCBANK"
        enhanced_signals = ai_enhanced_system.get_enhanced_signals(symbol, mock_data)

        if 'error' not in enhanced_signals:
            print("\n🤖 Enhanced Signals:")
            print(f"  Symbol: {enhanced_signals['symbol']}")
            print(f"  Traditional Action: {enhanced_signals['traditional_signals']['action']}")
            print(f"  AI Action: {enhanced_signals['ai_signals']['combined_action']}")
            print(f"  Combined Action: {enhanced_signals['combined_signal']['action']}")
            print(f"  Confidence: {enhanced_signals['combined_signal']['confidence']:.1%}")
            print(f"  Enhancement Factor: {enhanced_signals['enhancement_factor']:.2f}x")
        else:
            print(f"❌ Error: {enhanced_signals['error']}")

        return enhanced_signals

    except Exception as e:
        print(f"❌ Error in system integration: {e}")
        return {}

# ============================================================================
# EXAMPLE 7: SENTIMENT ANALYSIS
# ============================================================================
def example_sentiment_analysis():
    """Example: AI-powered sentiment analysis"""
    print("\n📰 Example 7: Sentiment Analysis")
    print("=" * 50)

    try:
        from ai_trading_system import SentimentAnalyzer

        # Initialize sentiment analyzer
        sentiment_analyzer = SentimentAnalyzer()

        # Analyze sentiment for symbols
        symbols = ["HDFCBANK", "ICICIBANK", "TCS"]

        print("🔍 Analyzing sentiment...")

        for symbol in symbols:
            sentiment = sentiment_analyzer.get_combined_sentiment(symbol)

            if 'error' not in sentiment:
                print(f"\n  {symbol}:")
                print(f"    Overall Sentiment: {sentiment.get('overall_sentiment', 'neutral').upper()}")
                print(f"    Combined Score: {sentiment.get('combined_score', 0):+.3f}")
                print(f"    Confidence: {sentiment.get('confidence', 0):.1%}")

                # News sentiment
                news_sent = sentiment.get('news_sentiment', {})
                if 'score' in news_sent:
                    print(f"    News Score: {news_sent['score']:+.3f}")

                # Social sentiment
                social_sent = sentiment.get('social_sentiment', {})
                if 'combined_score' in social_sent:
                    print(f"    Social Score: {social_sent['combined_score']:+.3f}")
            else:
                print(f"  {symbol}: ❌ {sentiment['error']}")

        return sentiment

    except Exception as e:
        print(f"❌ Error in sentiment analysis: {e}")
        return {}

# ============================================================================
# MAIN EXECUTION
# ============================================================================
def run_all_examples():
    """Run all examples"""
    print("🚀 AI Trading System - Complete Examples")
    print("=" * 60)
    print("This will demonstrate all AI trading capabilities")
    print("=" * 60)

    # Note: In real usage, you would need actual data provider and API keys
    # These examples use mock data for demonstration

    examples = [
        ("Basic Training", example_basic_training),
        ("Market Predictions", example_market_predictions),
        ("Sentiment Analysis", example_sentiment_analysis),
        ("Model Validation", example_model_validation),
        ("System Integration", example_system_integration),
    ]

    results = {}

    for name, example_func in examples:
        try:
            print(f"\n{'='*60}")
            result = example_func()
            results[name] = result
            print(f"✅ {name} completed successfully!")
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            results[name] = {'error': str(e)}

    print(f"\n{'='*60}")
    print("🎉 All examples completed!")
    print("=" * 60)

    return results

def run_single_example(example_number: int):
    """Run a single example"""
    examples = [
        example_basic_training,
        example_market_predictions,
        example_comprehensive_backtest,
        example_model_validation,
        example_parameter_optimization,
        example_system_integration,
        example_sentiment_analysis,
    ]

    if 1 <= example_number <= len(examples):
        example_func = examples[example_number - 1]
        example_name = [
            "Basic Training", "Market Predictions", "Comprehensive Backtest",
            "Model Validation", "Parameter Optimization", "System Integration",
            "Sentiment Analysis"
        ][example_number - 1]

        print(f"🚀 Running {example_name}")
        print("=" * 50)

        try:
            result = example_func()
            print(f"✅ {example_name} completed successfully!")
            return result
        except Exception as e:
            print(f"❌ {example_name} failed: {e}")
            return {'error': str(e)}
    else:
        print(f"❌ Invalid example number. Choose 1-{len(examples)}")
        return {'error': 'Invalid example number'}

# ============================================================================
# USAGE INSTRUCTIONS
# ============================================================================
def print_usage_instructions():
    """Print detailed usage instructions"""
    print("\n📚 AI Trading System - Usage Instructions")
    print("=" * 60)
    print("""
1. BASIC USAGE:
   from ai_trading_system import AIMarketPredictor, AIModelConfig

   # Initialize AI predictor
   config = AIModelConfig()
   ai_predictor = AIMarketPredictor(config)

   # Train models
   results = ai_predictor.train_models_for_symbols(['HDFCBANK'], data_provider)

   # Get predictions
   insights = ai_predictor.get_market_insights(['HDFCBANK'], data_provider)

2. BACKTESTING:
   from ai_backtesting_engine import run_ai_backtest, BacktestConfig

   # Use dynamic dates for backtest configuration
   from datetime import datetime, timedelta
   today = datetime.now().date()
   dynamic_start = (today - timedelta(days=365)).strftime('%Y-%m-%d')  # 1 year ago
   dynamic_end = today.strftime('%Y-%m-%d')  # Today

   config = BacktestConfig(
       start_date=dynamic_start,
       end_date=dynamic_end,
       initial_capital=1000000
   )
   results = run_ai_backtest(config, data_provider)

3. PERFORMANCE TRACKING:
   from ai_model_performance import validate_model_performance

   report = validate_model_performance('HDFCBANK', 'lstm', predictions, actuals)

4. INTEGRATION:
   from ai_trading_system import create_ai_trading_system

   ai_system = create_ai_trading_system(existing_system)
   signals = ai_system.get_enhanced_signals('HDFCBANK', market_data)

5. INSTALLATION:
   pip install -r ai_requirements.txt

6. CONFIGURATION:
   - Set up your data provider (Zerodha API or Yahoo Finance)
   - Configure model parameters in AIModelConfig
   - Adjust risk parameters in BacktestConfig
   - Set up logging and monitoring

7. MONITORING:
   - Check ai_models/ directory for trained models
   - Review ai_backtest_results/ for backtest reports
   - Monitor performance with ai_model_performance.py
    """)

# ============================================================================
# MAIN EXECUTION
# ============================================================================
if __name__ == "__main__":
    print("🤖 AI Trading System - Examples & Integration Guide")
    print("=" * 60)

    if len(sys.argv) > 1:
        if sys.argv[1] == "all":
            results = run_all_examples()
        elif sys.argv[1] == "help":
            print_usage_instructions()
        elif sys.argv[1].isdigit():
            example_num = int(sys.argv[1])
            result = run_single_example(example_num)
        else:
            print("❌ Invalid argument. Use 'all', 'help', or example number (1-7)")
    else:
        print("Choose an option:")
        print("1. Run all examples")
        print("2. Run specific example (1-7)")
        print("3. Show usage instructions")
        print("4. Exit")

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            results = run_all_examples()
        elif choice == "2":
            try:
                example_num = int(input("Enter example number (1-7): "))
                result = run_single_example(example_num)
            except ValueError:
                print("❌ Please enter a valid number")
        elif choice == "3":
            print_usage_instructions()
        else:
            print("👋 Goodbye!")