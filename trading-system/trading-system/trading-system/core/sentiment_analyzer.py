"""
Sentiment Analysis Module
Phase 4 Tier 1: Advanced Machine Learning

This module provides sentiment analysis capabilities for financial news and social media,
using state-of-the-art NLP models including FinBERT (BERT fine-tuned for financial sentiment).

Features:
- Multi-source sentiment aggregation (news, Twitter, Reddit)
- Real-time sentiment scoring (0-100 scale: bearish to bullish)
- Sentiment trend analysis
- Integration with ML signal scorer
- Caching layer for performance

Author: Trading System
Date: October 22, 2025
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re
from collections import defaultdict, deque
import time

import pandas as pd
import numpy as np

# NLP libraries
try:
    import nltk
    from nltk.sentiment import SentimentIntensityAnalyzer
    from nltk.tokenize import word_tokenize
    from nltk.corpus import stopwords
except ImportError:
    nltk = None

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
    import torch
except ImportError:
    torch = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SentimentSource(Enum):
    """Source of sentiment data"""
    NEWS = "news"
    TWITTER = "twitter"
    REDDIT = "reddit"
    COMBINED = "combined"


class SentimentLabel(Enum):
    """Sentiment classification labels"""
    VERY_BEARISH = "very_bearish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    VERY_BULLISH = "very_bullish"


@dataclass
class SentimentData:
    """Sentiment data for a single text item"""
    text: str
    score: float  # 0-100 scale (0=very bearish, 50=neutral, 100=very bullish)
    label: SentimentLabel
    source: SentimentSource
    timestamp: datetime
    confidence: float  # 0-1
    metadata: Dict = None


@dataclass
class AggregatedSentiment:
    """Aggregated sentiment for a symbol"""
    symbol: str
    overall_score: float  # 0-100 scale
    overall_label: SentimentLabel
    source_scores: Dict[SentimentSource, float]
    sentiment_trend: str  # "improving", "declining", "stable"
    data_points: int
    timestamp: datetime
    confidence: float


class SentimentAnalyzer:
    """
    Advanced sentiment analysis engine using multiple NLP models

    Supports:
    - FinBERT (BERT fine-tuned for financial sentiment)
    - VADER (Valence Aware Dictionary and sEntiment Reasoner)
    - Custom financial lexicon
    """

    def __init__(
        self,
        use_finbert: bool = True,
        use_vader: bool = True,
        cache_size: int = 1000,
        sentiment_window: int = 100,  # Keep last N sentiments for trend analysis
    ):
        """
        Initialize sentiment analyzer

        Args:
            use_finbert: Use FinBERT model (requires transformers + GPU recommended)
            use_vader: Use VADER sentiment analyzer
            cache_size: Maximum number of cached sentiment scores
            sentiment_window: Number of recent sentiments to keep for trend analysis
        """
        self.use_finbert = use_finbert
        self.use_vader = use_vader
        self.cache_size = cache_size
        self.sentiment_window = sentiment_window

        # Initialize models
        self.finbert_pipeline = None
        self.vader_analyzer = None

        if self.use_finbert:
            self._initialize_finbert()

        if self.use_vader:
            self._initialize_vader()

        # Initialize caches and history
        self.sentiment_cache = {}  # text_hash -> SentimentData
        self.sentiment_history = defaultdict(lambda: deque(maxlen=sentiment_window))  # symbol -> deque of scores

        # Financial sentiment lexicon (custom)
        self.financial_lexicon = self._build_financial_lexicon()

        logger.info(f"Sentiment analyzer initialized (FinBERT: {use_finbert}, VADER: {use_vader})")

    def _initialize_finbert(self):
        """Initialize FinBERT model for financial sentiment analysis"""
        try:
            if torch is None:
                logger.warning("PyTorch not available. FinBERT disabled.")
                self.use_finbert = False
                return

            model_name = "ProsusAI/finbert"
            logger.info(f"Loading FinBERT model: {model_name}")

            # Check if GPU is available
            device = 0 if torch.cuda.is_available() else -1
            if device == 0:
                logger.info("GPU detected - using GPU acceleration for FinBERT")
            else:
                logger.info("No GPU detected - using CPU for FinBERT (slower)")

            self.finbert_pipeline = pipeline(
                "sentiment-analysis",
                model=model_name,
                tokenizer=model_name,
                device=device,
                top_k=None
            )

            logger.info("FinBERT model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load FinBERT: {e}")
            self.use_finbert = False

    def _initialize_vader(self):
        """Initialize VADER sentiment analyzer"""
        try:
            if nltk is None:
                logger.warning("NLTK not available. VADER disabled.")
                self.use_vader = False
                return

            # Download required NLTK data
            try:
                nltk.data.find('vader_lexicon')
            except LookupError:
                logger.info("Downloading VADER lexicon...")
                nltk.download('vader_lexicon', quiet=True)

            try:
                nltk.data.find('punkt')
            except LookupError:
                nltk.download('punkt', quiet=True)

            try:
                nltk.data.find('stopwords')
            except LookupError:
                nltk.download('stopwords', quiet=True)

            self.vader_analyzer = SentimentIntensityAnalyzer()
            logger.info("VADER analyzer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize VADER: {e}")
            self.use_vader = False

    def _build_financial_lexicon(self) -> Dict[str, float]:
        """
        Build custom financial sentiment lexicon

        Returns:
            Dictionary mapping financial terms to sentiment scores (-1 to +1)
        """
        lexicon = {
            # Positive terms
            "bullish": 0.8, "rally": 0.7, "surge": 0.7, "soar": 0.8,
            "profit": 0.6, "gain": 0.6, "growth": 0.5, "upside": 0.6,
            "beat": 0.7, "outperform": 0.7, "upgrade": 0.6, "buy": 0.5,
            "strong": 0.5, "momentum": 0.5, "breakout": 0.6, "recovery": 0.5,

            # Negative terms
            "bearish": -0.8, "crash": -0.9, "plunge": -0.8, "tumble": -0.7,
            "loss": -0.6, "decline": -0.5, "fall": -0.5, "downside": -0.6,
            "miss": -0.7, "underperform": -0.7, "downgrade": -0.6, "sell": -0.5,
            "weak": -0.5, "concern": -0.4, "breakdown": -0.6, "recession": -0.8,
            "risk": -0.4, "volatility": -0.3, "uncertainty": -0.4,

            # Neutral/context-dependent
            "volatile": -0.2, "flat": 0.0, "stable": 0.2, "hold": 0.0,
        }
        return lexicon

    def analyze_text(
        self,
        text: str,
        source: SentimentSource = SentimentSource.NEWS,
        use_cache: bool = True
    ) -> SentimentData:
        """
        Analyze sentiment of a single text

        Args:
            text: Text to analyze
            source: Source of the text
            use_cache: Use cached result if available

        Returns:
            SentimentData object with analysis results
        """
        # Check cache
        text_hash = hash(text)
        if use_cache and text_hash in self.sentiment_cache:
            return self.sentiment_cache[text_hash]

        # Preprocess text
        cleaned_text = self._preprocess_text(text)

        # Get sentiment scores from available models
        scores = []
        confidences = []

        # FinBERT sentiment
        if self.use_finbert and self.finbert_pipeline:
            finbert_score, finbert_conf = self._get_finbert_sentiment(cleaned_text)
            scores.append(finbert_score)
            confidences.append(finbert_conf)

        # VADER sentiment
        if self.use_vader and self.vader_analyzer:
            vader_score, vader_conf = self._get_vader_sentiment(cleaned_text)
            scores.append(vader_score)
            confidences.append(vader_conf)

        # Lexicon-based sentiment
        lexicon_score = self._get_lexicon_sentiment(cleaned_text)
        scores.append(lexicon_score)
        confidences.append(0.5)  # Medium confidence for lexicon

        # Combine scores (weighted average based on confidence)
        if not scores:
            # Fallback to neutral
            final_score = 50.0
            final_confidence = 0.0
        else:
            weights = np.array(confidences)
            weights = weights / weights.sum()
            final_score = np.average(scores, weights=weights)
            final_confidence = np.mean(confidences)

        # Determine sentiment label
        label = self._score_to_label(final_score)

        # Create sentiment data
        sentiment_data = SentimentData(
            text=text,
            score=final_score,
            label=label,
            source=source,
            timestamp=datetime.now(),
            confidence=final_confidence,
            metadata={"cleaned_text": cleaned_text}
        )

        # Cache result
        if len(self.sentiment_cache) >= self.cache_size:
            # Remove oldest entry
            self.sentiment_cache.pop(next(iter(self.sentiment_cache)))
        self.sentiment_cache[text_hash] = sentiment_data

        return sentiment_data

    def analyze_batch(
        self,
        texts: List[str],
        sources: Optional[List[SentimentSource]] = None
    ) -> List[SentimentData]:
        """
        Analyze sentiment of multiple texts efficiently

        Args:
            texts: List of texts to analyze
            sources: List of sources (one per text, or None for all NEWS)

        Returns:
            List of SentimentData objects
        """
        if sources is None:
            sources = [SentimentSource.NEWS] * len(texts)

        results = []
        for text, source in zip(texts, sources):
            sentiment = self.analyze_text(text, source=source)
            results.append(sentiment)

        return results

    def aggregate_sentiment(
        self,
        symbol: str,
        sentiments: List[SentimentData],
        weights: Optional[Dict[SentimentSource, float]] = None
    ) -> AggregatedSentiment:
        """
        Aggregate multiple sentiment data points into overall sentiment

        Args:
            symbol: Stock symbol
            sentiments: List of sentiment data points
            weights: Optional weights for different sources

        Returns:
            AggregatedSentiment object
        """
        if not sentiments:
            return AggregatedSentiment(
                symbol=symbol,
                overall_score=50.0,
                overall_label=SentimentLabel.NEUTRAL,
                source_scores={},
                sentiment_trend="stable",
                data_points=0,
                timestamp=datetime.now(),
                confidence=0.0
            )

        # Default weights
        if weights is None:
            weights = {
                SentimentSource.NEWS: 0.5,
                SentimentSource.TWITTER: 0.3,
                SentimentSource.REDDIT: 0.2,
                SentimentSource.COMBINED: 1.0
            }

        # Group by source
        source_sentiments = defaultdict(list)
        for sentiment in sentiments:
            source_sentiments[sentiment.source].append(sentiment)

        # Calculate source-specific scores
        source_scores = {}
        for source, source_data in source_sentiments.items():
            scores = [s.score for s in source_data]
            confidences = [s.confidence for s in source_data]

            # Weighted average
            weights_arr = np.array(confidences)
            if weights_arr.sum() > 0:
                weights_arr = weights_arr / weights_arr.sum()
                source_score = np.average(scores, weights=weights_arr)
            else:
                source_score = np.mean(scores)

            source_scores[source] = source_score

        # Calculate overall score
        overall_score = 0.0
        total_weight = 0.0
        for source, score in source_scores.items():
            weight = weights.get(source, 0.5)
            overall_score += score * weight
            total_weight += weight

        if total_weight > 0:
            overall_score /= total_weight
        else:
            overall_score = 50.0

        # Calculate overall confidence
        overall_confidence = np.mean([s.confidence for s in sentiments])

        # Determine label
        overall_label = self._score_to_label(overall_score)

        # Analyze sentiment trend
        sentiment_trend = self._analyze_sentiment_trend(symbol, overall_score)

        return AggregatedSentiment(
            symbol=symbol,
            overall_score=overall_score,
            overall_label=overall_label,
            source_scores=source_scores,
            sentiment_trend=sentiment_trend,
            data_points=len(sentiments),
            timestamp=datetime.now(),
            confidence=overall_confidence
        )

    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for sentiment analysis"""
        # Convert to lowercase
        text = text.lower()

        # Remove URLs
        text = re.sub(r'http\S+|www\S+', '', text)

        # Remove mentions and hashtags (keep the text)
        text = re.sub(r'[@#]', '', text)

        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^a-zA-Z0-9\s.,!?]', '', text)

        # Remove extra whitespace
        text = ' '.join(text.split())

        return text

    def _get_finbert_sentiment(self, text: str) -> Tuple[float, float]:
        """
        Get sentiment from FinBERT model

        Returns:
            Tuple of (score 0-100, confidence 0-1)
        """
        try:
            # Truncate text if too long (BERT max is 512 tokens)
            max_length = 500
            if len(text) > max_length:
                text = text[:max_length]

            result = self.finbert_pipeline(text)[0]

            # FinBERT returns: positive, negative, neutral
            # Map to 0-100 scale
            label_scores = {item['label'].lower(): item['score'] for item in result}

            positive = label_scores.get('positive', 0.0)
            negative = label_scores.get('negative', 0.0)
            neutral = label_scores.get('neutral', 0.0)

            # Score: 0-50 for bearish, 50 for neutral, 50-100 for bullish
            if positive > negative:
                score = 50.0 + (positive * 50.0)
            else:
                score = 50.0 - (negative * 50.0)

            # Confidence is the maximum probability
            confidence = max(positive, negative, neutral)

            return score, confidence
        except Exception as e:
            logger.error(f"FinBERT analysis failed: {e}")
            return 50.0, 0.0

    def _get_vader_sentiment(self, text: str) -> Tuple[float, float]:
        """
        Get sentiment from VADER

        Returns:
            Tuple of (score 0-100, confidence 0-1)
        """
        try:
            scores = self.vader_analyzer.polarity_scores(text)
            compound = scores['compound']  # -1 to +1

            # Map compound score to 0-100 scale
            # compound: -1 to +1 -> score: 0 to 100
            score = (compound + 1.0) * 50.0

            # Confidence based on absolute value of compound
            confidence = abs(compound)

            return score, confidence
        except Exception as e:
            logger.error(f"VADER analysis failed: {e}")
            return 50.0, 0.0

    def _get_lexicon_sentiment(self, text: str) -> float:
        """
        Get sentiment using custom financial lexicon

        Returns:
            Score 0-100
        """
        words = text.lower().split()

        scores = []
        for word in words:
            if word in self.financial_lexicon:
                scores.append(self.financial_lexicon[word])

        if not scores:
            return 50.0

        # Average lexicon sentiment
        avg_sentiment = np.mean(scores)  # -1 to +1

        # Map to 0-100 scale
        score = (avg_sentiment + 1.0) * 50.0

        return score

    def _score_to_label(self, score: float) -> SentimentLabel:
        """Convert sentiment score to label"""
        if score < 20:
            return SentimentLabel.VERY_BEARISH
        elif score < 40:
            return SentimentLabel.BEARISH
        elif score < 60:
            return SentimentLabel.NEUTRAL
        elif score < 80:
            return SentimentLabel.BULLISH
        else:
            return SentimentLabel.VERY_BULLISH

    def _analyze_sentiment_trend(self, symbol: str, current_score: float) -> str:
        """
        Analyze sentiment trend for a symbol

        Returns:
            "improving", "declining", or "stable"
        """
        # Add current score to history
        self.sentiment_history[symbol].append(current_score)

        # Need at least 5 data points for trend
        if len(self.sentiment_history[symbol]) < 5:
            return "stable"

        # Get recent scores
        recent_scores = list(self.sentiment_history[symbol])

        # Simple trend analysis: compare recent average to older average
        mid_point = len(recent_scores) // 2
        old_avg = np.mean(recent_scores[:mid_point])
        new_avg = np.mean(recent_scores[mid_point:])

        diff = new_avg - old_avg

        # Threshold for considering a trend
        threshold = 5.0

        if diff > threshold:
            return "improving"
        elif diff < -threshold:
            return "declining"
        else:
            return "stable"

    def get_sentiment_signal(self, aggregated_sentiment: AggregatedSentiment) -> int:
        """
        Convert aggregated sentiment to trading signal

        Returns:
            Signal strength: -100 (strong sell) to +100 (strong buy)
        """
        score = aggregated_sentiment.overall_score
        confidence = aggregated_sentiment.confidence

        # Base signal from score (convert from 0-100 to -100 to +100)
        base_signal = (score - 50.0) * 2.0

        # Adjust based on trend
        trend_adjustment = 0.0
        if aggregated_sentiment.sentiment_trend == "improving":
            trend_adjustment = 10.0
        elif aggregated_sentiment.sentiment_trend == "declining":
            trend_adjustment = -10.0

        # Combine and apply confidence
        signal = (base_signal + trend_adjustment) * confidence

        # Clamp to -100 to +100
        signal = max(-100, min(100, signal))

        return int(signal)


class SentimentAggregator:
    """
    Aggregates sentiment from multiple sources in real-time
    """

    def __init__(self, analyzer: SentimentAnalyzer):
        """
        Initialize sentiment aggregator

        Args:
            analyzer: SentimentAnalyzer instance
        """
        self.analyzer = analyzer
        self.symbol_sentiments = defaultdict(list)  # symbol -> list of SentimentData
        self.last_update = {}  # symbol -> timestamp

    def add_sentiment(self, symbol: str, sentiment: SentimentData):
        """Add a sentiment data point for a symbol"""
        self.symbol_sentiments[symbol].append(sentiment)
        self.last_update[symbol] = datetime.now()

        # Keep only recent sentiments (last 24 hours)
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.symbol_sentiments[symbol] = [
            s for s in self.symbol_sentiments[symbol]
            if s.timestamp > cutoff_time
        ]

    def get_aggregated_sentiment(
        self,
        symbol: str,
        time_window: Optional[timedelta] = None
    ) -> Optional[AggregatedSentiment]:
        """
        Get aggregated sentiment for a symbol

        Args:
            symbol: Stock symbol
            time_window: Optional time window to consider (default: all available)

        Returns:
            AggregatedSentiment or None if no data
        """
        if symbol not in self.symbol_sentiments:
            return None

        sentiments = self.symbol_sentiments[symbol]

        # Filter by time window if specified
        if time_window:
            cutoff_time = datetime.now() - time_window
            sentiments = [s for s in sentiments if s.timestamp > cutoff_time]

        if not sentiments:
            return None

        return self.analyzer.aggregate_sentiment(symbol, sentiments)

    def get_all_aggregated_sentiments(self) -> Dict[str, AggregatedSentiment]:
        """Get aggregated sentiments for all tracked symbols"""
        results = {}
        for symbol in self.symbol_sentiments.keys():
            aggregated = self.get_aggregated_sentiment(symbol)
            if aggregated:
                results[symbol] = aggregated
        return results


if __name__ == "__main__":
    # Example usage
    print("Sentiment Analyzer Module")
    print("=" * 50)

    # Initialize analyzer
    analyzer = SentimentAnalyzer(use_finbert=False, use_vader=True)

    # Test texts
    test_texts = [
        "Apple stock surges on strong earnings beat and positive outlook",
        "Market crash as recession fears grow amid weak economic data",
        "Company announces flat quarterly results with stable guidance",
        "Investors bullish on tech sector as AI momentum accelerates",
        "Bearish sentiment grows as volatility spikes and losses mount"
    ]

    print("\nAnalyzing sample texts:")
    print("-" * 50)

    for text in test_texts:
        sentiment = analyzer.analyze_text(text)
        print(f"\nText: {text[:60]}...")
        print(f"Score: {sentiment.score:.1f}/100")
        print(f"Label: {sentiment.label.value}")
        print(f"Confidence: {sentiment.confidence:.2f}")

    # Test aggregation
    print("\n" + "=" * 50)
    print("Testing sentiment aggregation:")
    print("-" * 50)

    sentiments = analyzer.analyze_batch(test_texts)
    aggregated = analyzer.aggregate_sentiment("AAPL", sentiments)

    print(f"\nSymbol: {aggregated.symbol}")
    print(f"Overall Score: {aggregated.overall_score:.1f}/100")
    print(f"Overall Label: {aggregated.overall_label.value}")
    print(f"Data Points: {aggregated.data_points}")
    print(f"Confidence: {aggregated.confidence:.2f}")
    print(f"Trend: {aggregated.sentiment_trend}")

    # Get trading signal
    signal = analyzer.get_sentiment_signal(aggregated)
    print(f"\nTrading Signal: {signal}/100")

    print("\n" + "=" * 50)
    print("Sentiment analyzer module loaded successfully!")
