"""
News API Client
Phase 4 Tier 1: Advanced Machine Learning - Sentiment Analysis

This module provides integration with various financial news APIs to fetch
real-time news articles for sentiment analysis.

Supported APIs:
- NewsAPI (https://newsapi.org/)
- Alpha Vantage News Sentiment (https://www.alphavantage.co/)
- Financial news aggregators

Features:
- Multi-source news fetching
- Rate limiting and caching
- News article filtering and ranking
- Symbol-specific news extraction

Author: Trading System
Date: October 22, 2025
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import time
import re
from collections import defaultdict, deque

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NewsSource(Enum):
    """News source providers"""
    NEWSAPI = "newsapi"
    ALPHAVANTAGE = "alphavantage"
    FINNHUB = "finnhub"
    YAHOO = "yahoo"


@dataclass
class NewsArticle:
    """News article data structure"""
    title: str
    description: str
    content: str
    source: str
    author: Optional[str]
    published_at: datetime
    url: str
    symbol: Optional[str] = None
    relevance_score: float = 1.0
    sentiment_score: Optional[float] = None


class NewsAPIClient:
    """
    Multi-source news API client with rate limiting and caching

    Supports fetching financial news from multiple providers
    """

    def __init__(
        self,
        newsapi_key: Optional[str] = None,
        alphavantage_key: Optional[str] = None,
        finnhub_key: Optional[str] = None,
        cache_ttl: int = 300,  # 5 minutes
        rate_limit_calls: int = 10,
        rate_limit_period: int = 60,
    ):
        """
        Initialize news API client

        Args:
            newsapi_key: NewsAPI.org API key
            alphavantage_key: Alpha Vantage API key
            finnhub_key: Finnhub API key
            cache_ttl: Cache time-to-live in seconds
            rate_limit_calls: Max API calls per period
            rate_limit_period: Rate limit period in seconds
        """
        self.newsapi_key = newsapi_key
        self.alphavantage_key = alphavantage_key
        self.finnhub_key = finnhub_key

        self.cache_ttl = cache_ttl
        self.rate_limit_calls = rate_limit_calls
        self.rate_limit_period = rate_limit_period

        # Initialize HTTP session with retry logic
        self.session = self._create_session()

        # Cache for news articles
        self.news_cache = {}  # (source, query) -> (timestamp, articles)

        # Rate limiting
        self.api_calls = defaultdict(lambda: deque(maxlen=rate_limit_calls))

        # Financial news sources for NewsAPI
        self.financial_sources = [
            "bloomberg", "cnbc", "financial-times", "fortune",
            "reuters", "the-wall-street-journal", "business-insider"
        ]

        logger.info(f"News API client initialized (NewsAPI: {bool(newsapi_key)}, "
                   f"AlphaVantage: {bool(alphavantage_key)}, Finnhub: {bool(finnhub_key)})")

    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry logic"""
        session = requests.Session()

        # Retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "OPTIONS"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _check_rate_limit(self, source: str) -> bool:
        """
        Check if we can make an API call without exceeding rate limit

        Args:
            source: API source name

        Returns:
            True if call is allowed, False otherwise
        """
        now = time.time()

        # Remove old calls outside the rate limit window
        while self.api_calls[source] and now - self.api_calls[source][0] > self.rate_limit_period:
            self.api_calls[source].popleft()

        # Check if we can make a new call
        if len(self.api_calls[source]) >= self.rate_limit_calls:
            return False

        # Record this call
        self.api_calls[source].append(now)
        return True

    def _get_cached_news(self, cache_key: tuple) -> Optional[List[NewsArticle]]:
        """Get cached news if available and not expired"""
        if cache_key not in self.news_cache:
            return None

        timestamp, articles = self.news_cache[cache_key]

        # Check if cache expired
        if time.time() - timestamp > self.cache_ttl:
            del self.news_cache[cache_key]
            return None

        return articles

    def _cache_news(self, cache_key: tuple, articles: List[NewsArticle]):
        """Cache news articles"""
        self.news_cache[cache_key] = (time.time(), articles)

    def fetch_news_newsapi(
        self,
        query: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        language: str = "en",
        page_size: int = 100
    ) -> List[NewsArticle]:
        """
        Fetch news from NewsAPI.org

        Args:
            query: Search query (e.g., symbol name or company)
            from_date: Start date for news
            to_date: End date for news
            language: Language code
            page_size: Number of articles to fetch

        Returns:
            List of NewsArticle objects
        """
        if not self.newsapi_key:
            logger.warning("NewsAPI key not provided")
            return []

        # Check cache
        cache_key = ("newsapi", query, from_date, to_date)
        cached = self._get_cached_news(cache_key)
        if cached:
            logger.debug(f"Returning cached NewsAPI results for: {query}")
            return cached

        # Check rate limit
        if not self._check_rate_limit("newsapi"):
            logger.warning("NewsAPI rate limit exceeded")
            return []

        # Set date range (default: last 7 days)
        if not from_date:
            from_date = datetime.now() - timedelta(days=7)
        if not to_date:
            to_date = datetime.now()

        # Build API request
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "from": from_date.strftime("%Y-%m-%d"),
            "to": to_date.strftime("%Y-%m-%d"),
            "language": language,
            "sortBy": "relevancy",
            "pageSize": page_size,
            "apiKey": self.newsapi_key
        }

        # Add financial sources filter
        if not any(kw in query.lower() for kw in ["stock", "market", "trading"]):
            params["sources"] = ",".join(self.financial_sources)

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data["status"] != "ok":
                logger.error(f"NewsAPI error: {data.get('message', 'Unknown error')}")
                return []

            articles = []
            for article_data in data.get("articles", []):
                try:
                    # Parse published date
                    published_at = datetime.fromisoformat(
                        article_data["publishedAt"].replace("Z", "+00:00")
                    )

                    article = NewsArticle(
                        title=article_data.get("title", ""),
                        description=article_data.get("description", ""),
                        content=article_data.get("content", ""),
                        source=article_data.get("source", {}).get("name", "Unknown"),
                        author=article_data.get("author"),
                        published_at=published_at,
                        url=article_data.get("url", ""),
                        relevance_score=1.0
                    )
                    articles.append(article)
                except Exception as e:
                    logger.warning(f"Failed to parse article: {e}")
                    continue

            logger.info(f"Fetched {len(articles)} articles from NewsAPI for query: {query}")

            # Cache results
            self._cache_news(cache_key, articles)

            return articles

        except requests.exceptions.RequestException as e:
            logger.error(f"NewsAPI request failed: {e}")
            return []

    def fetch_news_alphavantage(
        self,
        symbol: str,
        time_from: Optional[str] = None,
        topics: Optional[List[str]] = None
    ) -> List[NewsArticle]:
        """
        Fetch news from Alpha Vantage News Sentiment API

        Args:
            symbol: Stock ticker symbol
            time_from: Time filter (format: YYYYMMDDTHHMM)
            topics: List of topics to filter (e.g., ["earnings", "technology"])

        Returns:
            List of NewsArticle objects
        """
        if not self.alphavantage_key:
            logger.warning("Alpha Vantage API key not provided")
            return []

        # Check cache
        cache_key = ("alphavantage", symbol, time_from)
        cached = self._get_cached_news(cache_key)
        if cached:
            logger.debug(f"Returning cached Alpha Vantage results for: {symbol}")
            return cached

        # Check rate limit
        if not self._check_rate_limit("alphavantage"):
            logger.warning("Alpha Vantage rate limit exceeded")
            return []

        # Build API request
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": symbol,
            "apikey": self.alphavantage_key,
            "limit": 50
        }

        if time_from:
            params["time_from"] = time_from

        if topics:
            params["topics"] = ",".join(topics)

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if "feed" not in data:
                logger.error(f"Alpha Vantage error: {data.get('Note', 'Unknown error')}")
                return []

            articles = []
            for article_data in data.get("feed", []):
                try:
                    # Parse published date
                    time_published = article_data.get("time_published", "")
                    published_at = datetime.strptime(time_published, "%Y%m%dT%H%M%S")

                    # Extract ticker sentiment
                    ticker_sentiment = None
                    for ticker_data in article_data.get("ticker_sentiment", []):
                        if ticker_data.get("ticker") == symbol:
                            ticker_sentiment = float(ticker_data.get("ticker_sentiment_score", 0))
                            break

                    # Relevance score from ticker
                    relevance_score = 1.0
                    for ticker_data in article_data.get("ticker_sentiment", []):
                        if ticker_data.get("ticker") == symbol:
                            relevance_score = float(ticker_data.get("relevance_score", 1.0))
                            break

                    article = NewsArticle(
                        title=article_data.get("title", ""),
                        description=article_data.get("summary", ""),
                        content=article_data.get("summary", ""),
                        source=article_data.get("source", "Alpha Vantage"),
                        author=article_data.get("authors", [None])[0] if article_data.get("authors") else None,
                        published_at=published_at,
                        url=article_data.get("url", ""),
                        symbol=symbol,
                        relevance_score=relevance_score,
                        sentiment_score=ticker_sentiment
                    )
                    articles.append(article)
                except Exception as e:
                    logger.warning(f"Failed to parse Alpha Vantage article: {e}")
                    continue

            logger.info(f"Fetched {len(articles)} articles from Alpha Vantage for symbol: {symbol}")

            # Cache results
            self._cache_news(cache_key, articles)

            return articles

        except requests.exceptions.RequestException as e:
            logger.error(f"Alpha Vantage request failed: {e}")
            return []

    def fetch_news_multi_source(
        self,
        symbol: str,
        company_name: Optional[str] = None,
        days_back: int = 7
    ) -> List[NewsArticle]:
        """
        Fetch news from all available sources

        Args:
            symbol: Stock ticker symbol
            company_name: Company name for better search results
            days_back: Number of days to look back

        Returns:
            Combined list of NewsArticle objects from all sources
        """
        all_articles = []

        # NewsAPI query (use company name if available)
        if self.newsapi_key:
            query = company_name if company_name else symbol
            from_date = datetime.now() - timedelta(days=days_back)
            newsapi_articles = self.fetch_news_newsapi(query, from_date=from_date)
            all_articles.extend(newsapi_articles)

        # Alpha Vantage
        if self.alphavantage_key:
            alphavantage_articles = self.fetch_news_alphavantage(symbol)
            all_articles.extend(alphavantage_articles)

        # Remove duplicates based on title similarity
        unique_articles = self._deduplicate_articles(all_articles)

        # Sort by relevance and date
        unique_articles.sort(key=lambda x: (x.relevance_score, x.published_at), reverse=True)

        logger.info(f"Fetched total of {len(unique_articles)} unique articles for {symbol}")

        return unique_articles

    def _deduplicate_articles(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Remove duplicate articles based on title similarity"""
        if not articles:
            return []

        unique = []
        seen_titles = set()

        for article in articles:
            # Normalize title for comparison
            normalized_title = re.sub(r'[^a-z0-9]', '', article.title.lower())

            # Check for similar titles
            is_duplicate = False
            for seen_title in seen_titles:
                # Simple similarity check (could be improved with fuzzy matching)
                if self._title_similarity(normalized_title, seen_title) > 0.8:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique.append(article)
                seen_titles.add(normalized_title)

        return unique

    def _title_similarity(self, title1: str, title2: str) -> float:
        """Calculate simple similarity between two titles"""
        # Simple word overlap ratio
        words1 = set(title1.split())
        words2 = set(title2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union)

    def extract_symbol_mentions(self, text: str, symbols: List[str]) -> Dict[str, int]:
        """
        Extract symbol mentions from text

        Args:
            text: Text to search
            symbols: List of symbols to look for

        Returns:
            Dictionary mapping symbol to mention count
        """
        text_lower = text.lower()
        mentions = {}

        for symbol in symbols:
            # Count mentions of symbol (with word boundaries)
            pattern = r'\b' + re.escape(symbol.lower()) + r'\b'
            count = len(re.findall(pattern, text_lower))
            if count > 0:
                mentions[symbol] = count

        return mentions


if __name__ == "__main__":
    # Example usage (requires API keys)
    print("News API Client Module")
    print("=" * 50)

    # Initialize client (with demo mode - no real API calls)
    client = NewsAPIClient()

    print("\nNews API client initialized")
    print(f"NewsAPI available: {bool(client.newsapi_key)}")
    print(f"Alpha Vantage available: {bool(client.alphavantage_key)}")
    print(f"Rate limit: {client.rate_limit_calls} calls per {client.rate_limit_period}s")

    # Example: Create a demo article
    demo_article = NewsArticle(
        title="Apple Stock Surges on Strong Earnings Report",
        description="Apple Inc. reported better-than-expected earnings...",
        content="Apple Inc. reported strong quarterly earnings that beat analyst expectations...",
        source="Demo Source",
        author="John Doe",
        published_at=datetime.now(),
        url="https://example.com/article",
        symbol="AAPL",
        relevance_score=0.95
    )

    print("\nDemo News Article:")
    print(f"Title: {demo_article.title}")
    print(f"Source: {demo_article.source}")
    print(f"Published: {demo_article.published_at.strftime('%Y-%m-%d %H:%M')}")
    print(f"Symbol: {demo_article.symbol}")
    print(f"Relevance: {demo_article.relevance_score:.2f}")

    print("\n" + "=" * 50)
    print("News API client module loaded successfully!")
    print("\nTo use with real APIs, provide API keys:")
    print("  NewsAPI: https://newsapi.org/")
    print("  Alpha Vantage: https://www.alphavantage.co/")
