"""
Sentiment Trading Example
Phase 4 Tier 1: Advanced Machine Learning - Sentiment Analysis

This example demonstrates how to integrate sentiment analysis with trading strategies
to improve signal accuracy and decision-making.

Features:
- Multi-source news fetching
- Real-time sentiment analysis
- Sentiment-enhanced trading signals
- Backtesting with sentiment data
- Performance comparison (with vs without sentiment)

Author: Trading System
Date: October 22, 2025
"""

import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.sentiment_analyzer import (
    SentimentAnalyzer, SentimentAggregator, SentimentSource, SentimentLabel
)
from integrations.news_api_client import NewsAPIClient, NewsArticle
from core.vectorized_backtester import VectorizedBacktester, Strategy, BacktestConfig
from core.ml_integration import FeatureEngineering

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SentimentEnhancedStrategy(Strategy):
    """
    Trading strategy enhanced with sentiment analysis

    Combines technical indicators with sentiment scores for improved signals
    """

    def __init__(
        self,
        sentiment_weight: float = 0.3,
        technical_weight: float = 0.7,
        sentiment_threshold: float = 60.0,  # Minimum sentiment for trades
        use_sentiment_filter: bool = True
    ):
        """
        Initialize sentiment-enhanced strategy

        Args:
            sentiment_weight: Weight for sentiment signal (0-1)
            technical_weight: Weight for technical signal (0-1)
            sentiment_threshold: Minimum sentiment score to allow trades
            use_sentiment_filter: If True, block trades against strong sentiment
        """
        self.sentiment_weight = sentiment_weight
        self.technical_weight = technical_weight
        self.sentiment_threshold = sentiment_threshold
        self.use_sentiment_filter = use_sentiment_filter

        # Normalize weights
        total = sentiment_weight + technical_weight
        self.sentiment_weight /= total
        self.technical_weight /= total

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals combining technical and sentiment analysis

        Expected columns in data:
        - close, high, low, volume (OHLCV data)
        - sentiment_score (0-100 scale)
        - sentiment_trend (improving/declining/stable)

        Returns:
            DataFrame with 'signal' column (1=buy, 0=hold, -1=sell)
        """
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0

        # Generate technical signals
        technical_signals = self._generate_technical_signals(data)

        # Get sentiment signals
        sentiment_signals = self._generate_sentiment_signals(data)

        # Combine signals
        combined_signals = (
            technical_signals * self.technical_weight +
            sentiment_signals * self.sentiment_weight
        )

        # Apply sentiment filter if enabled
        if self.use_sentiment_filter and 'sentiment_score' in data.columns:
            # Block long trades when sentiment is very bearish
            combined_signals = combined_signals.where(
                (combined_signals <= 0) | (data['sentiment_score'] > 30),
                0
            )

            # Block short trades when sentiment is very bullish
            combined_signals = combined_signals.where(
                (combined_signals >= 0) | (data['sentiment_score'] < 70),
                0
            )

        # Convert to discrete signals
        signals['signal'] = 0
        signals.loc[combined_signals > 0.3, 'signal'] = 1  # Buy
        signals.loc[combined_signals < -0.3, 'signal'] = -1  # Sell

        return signals

    def _generate_technical_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals from technical indicators"""
        # Calculate technical indicators
        close = data['close']

        # Moving averages
        sma_20 = close.rolling(window=20).mean()
        sma_50 = close.rolling(window=50).mean()

        # RSI
        rsi = self._calculate_rsi(close, period=14)

        # MACD
        macd, signal = self._calculate_macd(close)

        # Generate signal components
        trend_signal = np.where(sma_20 > sma_50, 1, -1)
        momentum_signal = np.where((rsi > 30) & (rsi < 70), 
                                  np.where(rsi > 50, 1, -1), 0)
        macd_signal = np.where(macd > signal, 1, -1)

        # Combine technical signals
        technical_signal = pd.Series(
            (trend_signal + momentum_signal + macd_signal) / 3.0,
            index=data.index
        )

        return technical_signal

    def _generate_sentiment_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals from sentiment data"""
        if 'sentiment_score' not in data.columns:
            return pd.Series(0, index=data.index)

        sentiment = data['sentiment_score']

        # Convert sentiment (0-100) to signal (-1 to +1)
        # 0-40: bearish (-1 to 0)
        # 40-60: neutral (0)
        # 60-100: bullish (0 to +1)
        signal = (sentiment - 50) / 50.0  # Maps 0-100 to -1 to +1

        # Apply trend adjustment if available
        if 'sentiment_trend' in data.columns:
            trend_adjustment = data['sentiment_trend'].map({
                'improving': 0.2,
                'declining': -0.2,
                'stable': 0.0
            }).fillna(0.0)

            signal = signal + trend_adjustment

        # Clamp to -1 to +1
        signal = signal.clip(-1, 1)

        return signal

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()

        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_macd(
        self,
        prices: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> tuple:
        """Calculate MACD indicator"""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()

        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal, adjust=False).mean()

        return macd, signal_line


def generate_sample_data_with_sentiment(
    days: int = 730,
    initial_price: float = 100.0,
    volatility: float = 0.02
) -> pd.DataFrame:
    """
    Generate sample OHLCV data with simulated sentiment scores

    In real usage, sentiment would come from actual news analysis
    """
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')

    # Generate price data (random walk)
    np.random.seed(42)
    returns = np.random.normal(0.0005, volatility, days)
    prices = initial_price * np.exp(np.cumsum(returns))

    # Generate OHLCV
    data = pd.DataFrame({
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, days)),
        'high': prices * (1 + np.random.uniform(0, 0.02, days)),
        'low': prices * (1 + np.random.uniform(-0.02, 0, days)),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, days)
    }, index=dates)

    # Generate correlated sentiment scores
    # Sentiment tends to follow price trends with some noise
    price_momentum = data['close'].pct_change(20).fillna(0)

    # Base sentiment from momentum
    sentiment_base = 50 + (price_momentum * 500)  # Scale momentum to sentiment

    # Add noise and random events
    sentiment_noise = np.random.normal(0, 10, days)
    random_events = np.random.choice([0, 20, -20], days, p=[0.9, 0.05, 0.05])

    data['sentiment_score'] = (sentiment_base + sentiment_noise + random_events).clip(0, 100)

    # Generate sentiment trend
    sentiment_change = data['sentiment_score'].diff(5).fillna(0)
    data['sentiment_trend'] = 'stable'
    data.loc[sentiment_change > 5, 'sentiment_trend'] = 'improving'
    data.loc[sentiment_change < -5, 'sentiment_trend'] = 'declining'

    # Add confidence (simulated)
    data['sentiment_confidence'] = np.random.uniform(0.6, 0.95, days)

    return data


def example_1_basic_sentiment_analysis():
    """Example 1: Basic sentiment analysis on sample texts"""
    print("\n" + "=" * 80)
    print("Example 1: Basic Sentiment Analysis")
    print("=" * 80)

    # Initialize sentiment analyzer
    # Note: Set use_finbert=True if you have transformers installed and GPU available
    analyzer = SentimentAnalyzer(use_finbert=False, use_vader=True)

    # Sample news headlines
    headlines = [
        "Apple stock surges 5% on record earnings, analysts upgrade price target",
        "Market crashes as recession fears intensify amid weak economic data",
        "Tesla announces new factory, stock remains flat on mixed outlook",
        "Tech sector rallies as AI investments drive unprecedented growth",
        "Banking crisis deepens with third major bank failure this month"
    ]

    symbols = ["AAPL", "SPY", "TSLA", "QQQ", "XLF"]

    print("\nAnalyzing news headlines:")
    print("-" * 80)

    results = []
    for headline, symbol in zip(headlines, symbols):
        sentiment = analyzer.analyze_text(headline, source=SentimentSource.NEWS)
        results.append({
            'symbol': symbol,
            'headline': headline[:60] + "..." if len(headline) > 60 else headline,
            'score': sentiment.score,
            'label': sentiment.label.value,
            'confidence': sentiment.confidence
        })

        print(f"\nSymbol: {symbol}")
        print(f"Headline: {headline}")
        print(f"Score: {sentiment.score:.1f}/100 | Label: {sentiment.label.value} | "
              f"Confidence: {sentiment.confidence:.2f}")

    # Convert to DataFrame for easy viewing
    results_df = pd.DataFrame(results)
    print("\n" + "=" * 80)
    print("Summary:")
    print(results_df.to_string(index=False))


def example_2_sentiment_aggregation():
    """Example 2: Aggregate sentiment from multiple sources"""
    print("\n" + "=" * 80)
    print("Example 2: Sentiment Aggregation")
    print("=" * 80)

    # Initialize
    analyzer = SentimentAnalyzer(use_finbert=False, use_vader=True)
    aggregator = SentimentAggregator(analyzer)

    # Simulate multiple news articles for AAPL
    symbol = "AAPL"
    news_texts = [
        "Apple reports record revenue, iPhone sales exceed expectations",
        "Apple CEO announces major AI initiative, stock gains momentum",
        "Analysts bullish on Apple's services growth and margin expansion",
        "Apple faces supply chain challenges but maintains strong outlook",
        "New Apple products generate excitement, pre-orders break records"
    ]

    print(f"\nAnalyzing multiple news articles for {symbol}:")
    print("-" * 80)

    # Analyze each article
    for i, text in enumerate(news_texts, 1):
        sentiment = analyzer.analyze_text(text, source=SentimentSource.NEWS)
        aggregator.add_sentiment(symbol, sentiment)

        print(f"\nArticle {i}: {text[:50]}...")
        print(f"  Score: {sentiment.score:.1f} | Label: {sentiment.label.value}")

    # Get aggregated sentiment
    agg_sentiment = aggregator.get_aggregated_sentiment(symbol)

    print("\n" + "-" * 80)
    print("Aggregated Sentiment:")
    print(f"  Symbol: {agg_sentiment.symbol}")
    print(f"  Overall Score: {agg_sentiment.overall_score:.1f}/100")
    print(f"  Overall Label: {agg_sentiment.overall_label.value}")
    print(f"  Trend: {agg_sentiment.sentiment_trend}")
    print(f"  Data Points: {agg_sentiment.data_points}")
    print(f"  Confidence: {agg_sentiment.confidence:.2f}")

    # Get trading signal
    signal = analyzer.get_sentiment_signal(agg_sentiment)
    print(f"\n  Trading Signal: {signal}/100 ", end="")
    if signal > 30:
        print("(Strong Buy)")
    elif signal > 10:
        print("(Buy)")
    elif signal < -30:
        print("(Strong Sell)")
    elif signal < -10:
        print("(Sell)")
    else:
        print("(Hold)")


def example_3_sentiment_enhanced_backtesting():
    """Example 3: Backtest with sentiment-enhanced strategy"""
    print("\n" + "=" * 80)
    print("Example 3: Sentiment-Enhanced Backtesting")
    print("=" * 80)

    # Generate sample data with sentiment
    print("\nGenerating sample data with sentiment scores...")
    data = generate_sample_data_with_sentiment(days=730, volatility=0.015)

    print(f"Data period: {data.index[0].date()} to {data.index[-1].date()}")
    print(f"Average sentiment score: {data['sentiment_score'].mean():.1f}/100")

    # Initialize backtester
    config = BacktestConfig(
        initial_capital=100000,
        transaction_cost_pct=0.001,
        slippage_pct=0.0005
    )
    backtester = VectorizedBacktester(config)

    # Test 1: Strategy WITHOUT sentiment
    print("\n" + "-" * 80)
    print("Test 1: Technical-Only Strategy")
    print("-" * 80)

    # Remove sentiment data for technical-only test
    data_no_sentiment = data.copy()
    data_no_sentiment['sentiment_score'] = 50  # Neutral sentiment
    data_no_sentiment['sentiment_trend'] = 'stable'

    strategy_no_sentiment = SentimentEnhancedStrategy(
        sentiment_weight=0.0,
        technical_weight=1.0,
        use_sentiment_filter=False
    )

    results_no_sentiment = backtester.run(strategy_no_sentiment, data_no_sentiment)

    print(f"\nTotal Return: {results_no_sentiment.total_return_pct:.2%}")
    print(f"Sharpe Ratio: {results_no_sentiment.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {results_no_sentiment.max_drawdown_pct:.2%}")
    print(f"Win Rate: {results_no_sentiment.win_rate_pct:.2%}")
    print(f"Total Trades: {results_no_sentiment.total_trades}")

    # Test 2: Strategy WITH sentiment
    print("\n" + "-" * 80)
    print("Test 2: Sentiment-Enhanced Strategy")
    print("-" * 80)

    strategy_with_sentiment = SentimentEnhancedStrategy(
        sentiment_weight=0.3,
        technical_weight=0.7,
        use_sentiment_filter=True
    )

    results_with_sentiment = backtester.run(strategy_with_sentiment, data)

    print(f"\nTotal Return: {results_with_sentiment.total_return_pct:.2%}")
    print(f"Sharpe Ratio: {results_with_sentiment.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {results_with_sentiment.max_drawdown_pct:.2%}")
    print(f"Win Rate: {results_with_sentiment.win_rate_pct:.2%}")
    print(f"Total Trades: {results_with_sentiment.total_trades}")

    # Compare results
    print("\n" + "-" * 80)
    print("Performance Comparison:")
    print("-" * 80)

    comparison = pd.DataFrame({
        'Metric': ['Total Return', 'Sharpe Ratio', 'Max Drawdown', 'Win Rate', 'Total Trades'],
        'Technical Only': [
            f"{results_no_sentiment.total_return_pct:.2%}",
            f"{results_no_sentiment.sharpe_ratio:.2f}",
            f"{results_no_sentiment.max_drawdown_pct:.2%}",
            f"{results_no_sentiment.win_rate_pct:.2%}",
            f"{results_no_sentiment.total_trades}"
        ],
        'With Sentiment': [
            f"{results_with_sentiment.total_return_pct:.2%}",
            f"{results_with_sentiment.sharpe_ratio:.2f}",
            f"{results_with_sentiment.max_drawdown_pct:.2%}",
            f"{results_with_sentiment.win_rate_pct:.2%}",
            f"{results_with_sentiment.total_trades}"
        ]
    })

    print(comparison.to_string(index=False))

    # Calculate improvement
    return_improvement = (
        (results_with_sentiment.total_return_pct - results_no_sentiment.total_return_pct) /
        abs(results_no_sentiment.total_return_pct) * 100
    )
    sharpe_improvement = (
        (results_with_sentiment.sharpe_ratio - results_no_sentiment.sharpe_ratio) /
        abs(results_no_sentiment.sharpe_ratio) * 100
    )

    print(f"\nImprovement with Sentiment:")
    print(f"  Return: {return_improvement:+.1f}%")
    print(f"  Sharpe: {sharpe_improvement:+.1f}%")

    # Visualize results
    try:
        fig, axes = plt.subplots(2, 1, figsize=(12, 8))

        # Plot equity curves
        axes[0].plot(results_no_sentiment.equity_curve.index,
                    results_no_sentiment.equity_curve.values,
                    label='Technical Only', linewidth=2)
        axes[0].plot(results_with_sentiment.equity_curve.index,
                    results_with_sentiment.equity_curve.values,
                    label='With Sentiment', linewidth=2)
        axes[0].set_title('Equity Curve Comparison', fontsize=14, fontweight='bold')
        axes[0].set_ylabel('Portfolio Value ($)')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        # Plot sentiment score over time
        axes[1].plot(data.index, data['sentiment_score'], 
                    label='Sentiment Score', color='purple', alpha=0.7)
        axes[1].axhline(y=50, color='gray', linestyle='--', alpha=0.5, label='Neutral')
        axes[1].fill_between(data.index, 0, data['sentiment_score'],
                            where=(data['sentiment_score'] > 60),
                            color='green', alpha=0.2, label='Bullish')
        axes[1].fill_between(data.index, 0, data['sentiment_score'],
                            where=(data['sentiment_score'] < 40),
                            color='red', alpha=0.2, label='Bearish')
        axes[1].set_title('Sentiment Score Over Time', fontsize=14, fontweight='bold')
        axes[1].set_xlabel('Date')
        axes[1].set_ylabel('Sentiment Score (0-100)')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('sentiment_trading_results.png', dpi=150, bbox_inches='tight')
        print("\nPlot saved as 'sentiment_trading_results.png'")

    except Exception as e:
        logger.warning(f"Could not create plot: {e}")


def example_4_real_time_sentiment_monitoring():
    """Example 4: Real-time sentiment monitoring simulation"""
    print("\n" + "=" * 80)
    print("Example 4: Real-Time Sentiment Monitoring (Simulation)")
    print("=" * 80)

    # Initialize
    analyzer = SentimentAnalyzer(use_finbert=False, use_vader=True)
    aggregator = SentimentAggregator(analyzer)

    # Symbols to monitor
    symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA']

    # Simulate incoming news stream
    simulated_news = [
        ("AAPL", "Apple unveils revolutionary new product line with AI capabilities"),
        ("GOOGL", "Google announces breakthrough in quantum computing technology"),
        ("MSFT", "Microsoft cloud revenue soars, exceeding analyst expectations"),
        ("AMZN", "Amazon faces regulatory scrutiny, stock price under pressure"),
        ("TSLA", "Tesla production targets missed, delivery numbers disappoint"),
        ("AAPL", "Apple expands into healthcare with new wearable device"),
        ("GOOGL", "Alphabet reports strong advertising growth in Q3 results"),
        ("MSFT", "Azure platform gains market share against competitors"),
        ("AMZN", "AWS growth slows, raising concerns about cloud competition"),
        ("TSLA", "Musk announces ambitious expansion plans for Tesla factories"),
    ]

    print(f"\nMonitoring {len(symbols)} symbols...")
    print("Simulating incoming news stream...")
    print("-" * 80)

    # Process news stream
    for symbol, news_text in simulated_news:
        sentiment = analyzer.analyze_text(news_text, source=SentimentSource.NEWS)
        aggregator.add_sentiment(symbol, sentiment)

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] New article for {symbol}")
        print(f"  Headline: {news_text[:60]}...")
        print(f"  Sentiment: {sentiment.score:.1f}/100 ({sentiment.label.value})")

    # Display aggregated sentiments for all symbols
    print("\n" + "=" * 80)
    print("Current Aggregated Sentiments:")
    print("=" * 80)

    all_sentiments = aggregator.get_all_aggregated_sentiments()

    summary_data = []
    for symbol in symbols:
        if symbol in all_sentiments:
            agg = all_sentiments[symbol]
            signal = analyzer.get_sentiment_signal(agg)

            summary_data.append({
                'Symbol': symbol,
                'Score': f"{agg.overall_score:.1f}",
                'Label': agg.overall_label.value,
                'Trend': agg.sentiment_trend,
                'Articles': agg.data_points,
                'Signal': f"{signal:+d}",
                'Confidence': f"{agg.confidence:.2f}"
            })

    summary_df = pd.DataFrame(summary_data)
    print("\n" + summary_df.to_string(index=False))

    # Investment recommendations based on sentiment
    print("\n" + "=" * 80)
    print("Trading Recommendations:")
    print("-" * 80)

    for symbol in symbols:
        if symbol in all_sentiments:
            agg = all_sentiments[symbol]
            signal = analyzer.get_sentiment_signal(agg)

            recommendation = "HOLD"
            if signal > 30 and agg.confidence > 0.6:
                recommendation = "BUY"
            elif signal < -30 and agg.confidence > 0.6:
                recommendation = "SELL"

            print(f"{symbol}: {recommendation:6s} (Signal: {signal:+3d}, "
                  f"Sentiment: {agg.overall_score:.0f}, "
                  f"Trend: {agg.sentiment_trend})")


def main():
    """Run all sentiment trading examples"""
    print("\n")
    print("=" * 80)
    print(" SENTIMENT TRADING EXAMPLES")
    print(" Phase 4 Tier 1: Advanced Machine Learning")
    print("=" * 80)

    try:
        # Run examples
        example_1_basic_sentiment_analysis()
        example_2_sentiment_aggregation()
        example_3_sentiment_enhanced_backtesting()
        example_4_real_time_sentiment_monitoring()

        print("\n" + "=" * 80)
        print("All examples completed successfully!")
        print("=" * 80)

        print("\nKey Takeaways:")
        print("  1. Sentiment analysis provides additional signal beyond technical indicators")
        print("  2. Aggregating sentiment from multiple sources improves accuracy")
        print("  3. Combining sentiment with technical analysis can enhance performance")
        print("  4. Real-time sentiment monitoring enables proactive decision-making")

        print("\nNext Steps:")
        print("  - Integrate real news APIs (NewsAPI, Alpha Vantage)")
        print("  - Use FinBERT for superior financial sentiment analysis")
        print("  - Add social media sentiment (Twitter, Reddit)")
        print("  - Implement real-time sentiment streaming")

    except Exception as e:
        logger.error(f"Example failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
