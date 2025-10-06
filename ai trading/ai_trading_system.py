#!/usr/bin/env python3
"""
AI-Powered Trading System
Advanced Machine Learning Integration for Enhanced Trading Performance
Built on top of the existing NIFTY 50 Trading System
"""

import sys
import os
import numpy as np
import pandas as pd
# TensorFlow imports with fallback
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, Model
    from tensorflow.keras.layers import LSTM, Dense, Dropout, Input, Attention, MultiHeadAttention, LayerNormalization, Embedding
    from tensorflow.keras.optimizers import Adam
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    print("⚠️ TensorFlow not available. Using scikit-learn fallback models.")
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib
import pickle
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
import warnings
import requests
from bs4 import BeautifulSoup
import re
from textblob import TextBlob
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor
import asyncio
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

# Import existing system components
try:
    from enhanced_trading_system_complete import TradingLogger, safe_float_conversion, validate_symbol
    from zerodha_token_manager import ZerodhaTokenManager
except ImportError:
    # Fallback if not available
    class TradingLogger:
        def __init__(self, log_dir="logs"):
            self.logger = logging.getLogger('ai_trading')
            self.logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            self.logger.addHandler(handler)

        def logger(self):
            return self.logger

    def safe_float_conversion(value, default=0.0):
        try:
            return float(value) if value is not None and not pd.isna(value) else default
        except:
            return default

    def validate_symbol(symbol):
        return symbol.strip().upper() if symbol else ""

# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================
@dataclass
class AIModelConfig:
    """Configuration for AI models"""
    # Model Architecture
    lstm_units: List[int] = field(default_factory=lambda: [50, 30, 20])
    dropout_rate: float = 0.2
    epochs: int = 100
    batch_size: int = 32
    validation_split: float = 0.2

    # Data Configuration
    sequence_length: int = 60
    prediction_horizon: int = 5
    feature_columns: List[str] = field(default_factory=lambda: [
        'close', 'volume', 'rsi', 'macd', 'bb_upper', 'bb_lower',
        'sma_20', 'sma_50', 'ema_12', 'ema_26', 'atr', 'volatility'
    ])

    # Training Configuration
    learning_rate: float = 0.001
    patience: int = 10
    min_delta: float = 0.0001

    # Model Storage
    model_dir: str = "ai_models"
    scaler_dir: str = "ai_scalers"

    # Sentiment Analysis
    sentiment_sources: List[str] = field(default_factory=lambda: [
        'news', 'twitter', 'reddit', 'economic_indicators'
    ])

    # RL Configuration
    gamma: float = 0.95  # Discount factor
    epsilon: float = 1.0  # Exploration rate
    epsilon_min: float = 0.01
    epsilon_decay: float = 0.995
    learning_rate_rl: float = 0.001

# ============================================================================
# AI TRADING SYSTEM CORE
# ============================================================================
class AITradingSystem:
    """Advanced AI-powered trading system with ML integration"""

    def __init__(self, config: AIModelConfig = None):
        self.config = config or AIModelConfig()
        self.logger = TradingLogger()
        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, Any] = {}
        self.feature_importance: Dict[str, Dict] = {}

        # Create directories
        Path(self.config.model_dir).mkdir(exist_ok=True)
        Path(self.config.scaler_dir).mkdir(exist_ok=True)

        # Initialize TensorFlow
        self._setup_tensorflow()

        self.logger.logger.info("🤖 AI Trading System initialized")

    def _setup_tensorflow(self):
        """Setup TensorFlow environment"""
        try:
            # Enable GPU if available
            gpus = tf.config.experimental.list_physical_devices('GPU')
            if gpus:
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
                self.logger.logger.info(f"✅ GPU acceleration enabled: {len(gpus)} GPU(s) detected")
            else:
                self.logger.logger.info("✅ CPU mode enabled")

            # Set random seeds for reproducibility
            tf.random.set_seed(42)
            np.random.seed(42)

        except Exception as e:
            self.logger.logger.warning(f"TensorFlow setup warning: {e}")

# ============================================================================
# FEATURE ENGINEERING
# ============================================================================
class FeatureEngineer:
    """Advanced feature engineering for ML models"""

    def __init__(self):
        self.logger = TradingLogger()

    def create_technical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create comprehensive technical indicators"""
        if df is None or df.empty:
            return pd.DataFrame()

        try:
            df = df.copy()

            # Basic price features
            df['returns'] = df['close'].pct_change()
            df['log_returns'] = np.log(df['close'] / df['close'].shift(1))

            # Moving averages
            for period in [5, 10, 20, 50, 200]:
                df[f'sma_{period}'] = df['close'].rolling(period).mean()
                df[f'ema_{period}'] = df['close'].ewm(span=period).mean()

            # RSI
            df['rsi'] = self._calculate_rsi(df['close'], 14)

            # MACD
            df['macd'], df['macd_signal'], df['macd_hist'] = self._calculate_macd(df['close'])

            # Bollinger Bands
            df['bb_middle'], df['bb_upper'], df['bb_lower'] = self._calculate_bollinger_bands(df['close'])

            # ATR
            df['atr'] = self._calculate_atr(df)

            # Volatility
            df['volatility'] = df['returns'].rolling(20).std()

            # Volume features
            df['volume_sma'] = df['volume'].rolling(20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']

            # Price momentum
            for period in [5, 10, 20]:
                df[f'momentum_{period}'] = (df['close'] / df['close'].shift(period)) - 1

            # Support and resistance levels
            df['support'] = df['low'].rolling(20).min()
            df['resistance'] = df['high'].rolling(20).max()

            # Trend indicators
            df['trend_sma'] = (df['close'] > df['sma_20']).astype(int)
            df['trend_ema'] = (df['close'] > df['ema_20']).astype(int)

            # Gap features
            df['gap_up'] = (df['low'] > df['close'].shift(1)).astype(int)
            df['gap_down'] = (df['high'] < df['close'].shift(1)).astype(int)

            # Price patterns
            df['higher_high'] = (df['high'] > df['high'].shift(1)).astype(int)
            df['lower_low'] = (df['low'] < df['low'].shift(1)).astype(int)

            # Fill NaN values
            df = df.fillna(method='bfill').fillna(method='ffill').fillna(0)

            return df

        except Exception as e:
            self.logger.logger.error(f"Error in feature engineering: {e}")
            return pd.DataFrame()

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        """Calculate MACD indicator"""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal).mean()
        histogram = macd - signal_line
        return macd, signal_line, histogram

    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: float = 2):
        """Calculate Bollinger Bands"""
        middle = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return middle, upper, lower

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close']
        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()

# ============================================================================
# PREDICTIVE MODELING
# ============================================================================
class PredictiveModels:
    """Advanced predictive models for trading"""

    def __init__(self, config: AIModelConfig):
        self.config = config
        self.logger = TradingLogger()
        self.feature_engineer = FeatureEngineer()

    def build_lstm_model(self, input_shape: Tuple[int, int]) -> Any:
        """Build LSTM model for time series prediction"""
        if not TENSORFLOW_AVAILABLE:
            # Fallback to scikit-learn model
            from sklearn.ensemble import RandomForestRegressor
            return RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )

        model = Sequential([
            LSTM(self.config.lstm_units[0], return_sequences=True, input_shape=input_shape),
            Dropout(self.config.dropout_rate),
            LSTM(self.config.lstm_units[1], return_sequences=True),
            Dropout(self.config.dropout_rate),
            LSTM(self.config.lstm_units[2]),
            Dropout(self.config.dropout_rate),
            Dense(1)  # Predict next price
        ])

        model.compile(
            optimizer=Adam(learning_rate=self.config.learning_rate),
            loss='mse',
            metrics=['mae', 'mape']
        )

        return model

    def build_transformer_model(self, input_shape: Tuple[int, int]) -> Any:
        """Build Transformer model for time series prediction"""
        inputs = Input(shape=input_shape)

        # Multi-head attention
        attention = MultiHeadAttention(num_heads=8, key_dim=64)(inputs, inputs)
        attention = LayerNormalization(epsilon=1e-6)(attention + inputs)

        # Feed forward
        ffn = Dense(128, activation='relu')(attention)
        ffn = Dense(input_shape[-1])(ffn)
        ffn = LayerNormalization(epsilon=1e-6)(ffn + attention)

        # Output
        outputs = Dense(1)(ffn)

        model = Model(inputs=inputs, outputs=outputs)
        model.compile(
            optimizer=Adam(learning_rate=self.config.learning_rate),
            loss='mse',
            metrics=['mae', 'mape']
        )

        return model

    def prepare_data(self, df: pd.DataFrame) -> Tuple[np.array, np.array, StandardScaler]:
        """Prepare data for training"""
        # Create features
        df_features = self.feature_engineer.create_technical_features(df)

        # Select relevant features
        feature_cols = [col for col in self.config.feature_columns if col in df_features.columns]
        if not feature_cols:
            feature_cols = ['close', 'volume']

        data = df_features[feature_cols].values

        # Scale data
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(data)

        # Create sequences
        X, y = [], []
        for i in range(len(scaled_data) - self.config.sequence_length - self.config.prediction_horizon):
            X.append(scaled_data[i:(i + self.config.sequence_length)])
            y.append(scaled_data[i + self.config.sequence_length + self.config.prediction_horizon, 0])  # Predict close price

        X = np.array(X)
        y = np.array(y)

        return X, y, scaler

    def train_model(self, symbol: str, df: pd.DataFrame, model_type: str = 'lstm') -> Dict:
        """Train predictive model for a symbol"""
        try:
            self.logger.logger.info(f"Training {model_type} model for {symbol}")

            # Prepare data
            X, y, scaler = self.prepare_data(df)

            if len(X) < 100:
                self.logger.logger.warning(f"Insufficient data for {symbol}")
                return {'error': 'Insufficient data'}

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            # Build model
            if model_type == 'lstm':
                model = self.build_lstm_model((X.shape[1], X.shape[2]))
            elif model_type == 'transformer':
                model = self.build_transformer_model((X.shape[1], X.shape[2]))
            else:
                raise ValueError(f"Unknown model type: {model_type}")

            # Train model
            if TENSORFLOW_AVAILABLE and hasattr(model, 'fit'):
                # TensorFlow/Keras model
                history = model.fit(
                    X_train, y_train,
                    epochs=self.config.epochs,
                    batch_size=self.config.batch_size,
                    validation_split=self.config.validation_split,
                    verbose=0,
                    callbacks=[
                        tf.keras.callbacks.EarlyStopping(
                            patience=self.config.patience,
                            min_delta=self.config.min_delta,
                            restore_best_weights=True
                        )
                    ]
                )

                # Evaluate model
                y_pred = model.predict(X_test, verbose=0)
                metrics = {
                    'mse': mean_squared_error(y_test, y_pred),
                    'mae': mean_absolute_error(y_test, y_pred),
                    'r2': r2_score(y_test, y_pred),
                    'training_loss': history.history['loss'][-1],
                    'validation_loss': history.history['val_loss'][-1]
                }

                # Save model and scaler
                model_path = f"{self.config.model_dir}/{symbol}_{model_type}_model.h5"
                scaler_path = f"{self.config.scaler_dir}/{symbol}_{model_type}_scaler.pkl"

                model.save(model_path)
                joblib.dump(scaler, scaler_path)
            else:
                # Scikit-learn model
                model.fit(X_train, y_train)
                y_pred = model.predict(X_test)
                metrics = {
                    'mse': mean_squared_error(y_test, y_pred),
                    'mae': mean_absolute_error(y_test, y_pred),
                    'r2': r2_score(y_test, y_pred),
                    'training_loss': 0,
                    'validation_loss': 0
                }

                # Save model and scaler
                model_path = f"{self.config.model_dir}/{symbol}_{model_type}_model.pkl"
                scaler_path = f"{self.config.scaler_dir}/{symbol}_{model_type}_scaler.pkl"

                joblib.dump(model, model_path)
                joblib.dump(scaler, scaler_path)

            self.logger.logger.info(f"✅ Model trained for {symbol}: MSE={metrics['mse']:.6f}")

            return {
                'model_path': model_path,
                'scaler_path': scaler_path,
                'metrics': metrics,
                'training_samples': len(X_train),
                'test_samples': len(X_test)
            }

        except Exception as e:
            self.logger.logger.error(f"Error training model for {symbol}: {e}")
            return {'error': str(e)}

    def predict_price(self, symbol: str, df: pd.DataFrame, model_type: str = 'lstm') -> Dict:
        """Predict future price for a symbol"""
        try:
            # Load model and scaler
            model_path = f"{self.config.model_dir}/{symbol}_{model_type}_model.h5"
            if not os.path.exists(model_path):
                model_path = f"{self.config.model_dir}/{symbol}_{model_type}_model.pkl"

            scaler_path = f"{self.config.scaler_dir}/{symbol}_{model_type}_scaler.pkl"

            if not os.path.exists(model_path) or not os.path.exists(scaler_path):
                return {'error': 'Model not trained'}

            if TENSORFLOW_AVAILABLE and model_path.endswith('.h5'):
                # TensorFlow model
                model = tf.keras.models.load_model(model_path)
            else:
                # Scikit-learn model
                model = joblib.load(model_path)

            scaler = joblib.load(scaler_path)

            # Prepare latest data
            X, _, _ = self.prepare_data(df)

            if len(X) == 0:
                return {'error': 'Insufficient data for prediction'}

            # Get latest sequence
            latest_sequence = X[-1:]

            # Make prediction
            if TENSORFLOW_AVAILABLE and hasattr(model, 'predict'):
                # TensorFlow model
                prediction_scaled = model.predict(latest_sequence, verbose=0)
                prediction = scaler.inverse_transform(
                    np.column_stack([prediction_scaled.flatten(), np.zeros((len(prediction_scaled), len(self.config.feature_columns)-1))])
                )[0, 0]
            else:
                # Scikit-learn model
                prediction = model.predict(latest_sequence.reshape(1, -1))[0]

            current_price = df['close'].iloc[-1]

            return {
                'current_price': current_price,
                'predicted_price': prediction,
                'change': (prediction - current_price) / current_price,
                'confidence': 0.8,  # Placeholder - could be calculated from prediction variance
                'model_type': model_type
            }

        except Exception as e:
            self.logger.logger.error(f"Error predicting price for {symbol}: {e}")
            return {'error': str(e)}

# ============================================================================
# SENTIMENT ANALYSIS
# ============================================================================
class SentimentAnalyzer:
    """Advanced sentiment analysis for trading signals"""

    def __init__(self):
        self.logger = TradingLogger()
        self.sentiment_cache: Dict[str, Dict] = {}

    def get_news_sentiment(self, symbol: str) -> Dict:
        """Get sentiment from news sources"""
        try:
            # This is a simplified implementation
            # In production, you would integrate with news APIs like Alpha Vantage, NewsAPI, etc.

            # Mock news sentiment for demonstration
            # In real implementation, fetch from news APIs
            mock_sentiment = {
                'score': np.random.uniform(-1, 1),
                'magnitude': np.random.uniform(0, 1),
                'sources': ['financial_news', 'market_analysis'],
                'timestamp': datetime.now().isoformat()
            }

            return mock_sentiment

        except Exception as e:
            self.logger.logger.error(f"Error getting news sentiment for {symbol}: {e}")
            return {'score': 0, 'magnitude': 0, 'error': str(e)}

    def get_social_sentiment(self, symbol: str) -> Dict:
        """Get sentiment from social media"""
        try:
            # Mock social media sentiment
            # In production, integrate with Twitter API, Reddit API, etc.

            mock_sentiment = {
                'twitter_score': np.random.uniform(-1, 1),
                'reddit_score': np.random.uniform(-1, 1),
                'combined_score': np.random.uniform(-1, 1),
                'volume': np.random.randint(100, 1000),
                'timestamp': datetime.now().isoformat()
            }

            return mock_sentiment

        except Exception as e:
            self.logger.logger.error(f"Error getting social sentiment for {symbol}: {e}")
            return {'combined_score': 0, 'error': str(e)}

    def analyze_text_sentiment(self, text: str) -> Dict:
        """Analyze sentiment of text using TextBlob"""
        try:
            blob = TextBlob(text)
            return {
                'polarity': blob.sentiment.polarity,
                'subjectivity': blob.sentiment.subjectivity,
                'sentiment': 'positive' if blob.sentiment.polarity > 0.1 else 'negative' if blob.sentiment.polarity < -0.1 else 'neutral'
            }
        except Exception as e:
            return {'polarity': 0, 'subjectivity': 0, 'sentiment': 'neutral', 'error': str(e)}

    def get_combined_sentiment(self, symbol: str) -> Dict:
        """Get combined sentiment from all sources"""
        try:
            news_sentiment = self.get_news_sentiment(symbol)
            social_sentiment = self.get_social_sentiment(symbol)

            # Combine sentiments with weights
            news_weight = 0.6
            social_weight = 0.4

            combined_score = (
                news_sentiment.get('score', 0) * news_weight +
                social_sentiment.get('combined_score', 0) * social_weight
            )

            return {
                'symbol': symbol,
                'combined_score': combined_score,
                'news_sentiment': news_sentiment,
                'social_sentiment': social_sentiment,
                'overall_sentiment': 'bullish' if combined_score > 0.2 else 'bearish' if combined_score < -0.2 else 'neutral',
                'confidence': min(news_sentiment.get('magnitude', 0), social_sentiment.get('volume', 0)) / 1000,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.logger.error(f"Error getting combined sentiment for {symbol}: {e}")
            return {'combined_score': 0, 'overall_sentiment': 'neutral', 'error': str(e)}

# ============================================================================
# REINFORCEMENT LEARNING STRATEGIES
# ============================================================================
class RLTradingAgent:
    """Reinforcement Learning agent for trading decisions"""

    def __init__(self, state_size: int, action_size: int = 3):
        self.state_size = state_size
        self.action_size = action_size  # 0: hold, 1: buy, 2: sell
        self.memory = []
        self.gamma = 0.95  # Discount factor
        self.epsilon = 1.0  # Exploration rate
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        self.learning_rate = 0.001

        self.model = self._build_model()
        self.logger = TradingLogger()

    def _build_model(self) -> Any:
        """Build neural network for RL agent"""
        if not TENSORFLOW_AVAILABLE:
            # Fallback to scikit-learn model
            from sklearn.ensemble import RandomForestRegressor
            return RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )

        model = Sequential([
            Dense(64, input_dim=self.state_size, activation='relu'),
            Dropout(0.2),
            Dense(32, activation='relu'),
            Dropout(0.2),
            Dense(16, activation='relu'),
            Dense(self.action_size, activation='linear')
        ])

        model.compile(loss='mse', optimizer=Adam(learning_rate=self.learning_rate))
        return model

    def remember(self, state, action, reward, next_state, done):
        """Store experience in memory"""
        self.memory.append((state, action, reward, next_state, done))

    def act(self, state):
        """Choose action using epsilon-greedy policy"""
        if np.random.rand() <= self.epsilon:
            return np.random.randint(self.action_size)

        act_values = self.model.predict(state.reshape(1, -1), verbose=0)
        return np.argmax(act_values[0])

    def replay(self, batch_size):
        """Train model using experience replay"""
        if len(self.memory) < batch_size:
            return

        minibatch = np.random.choice(len(self.memory), batch_size, replace=False)

        for idx in minibatch:
            state, action, reward, next_state, done = self.memory[idx]

            target = reward
            if not done:
                target = reward + self.gamma * np.amax(self.model.predict(next_state.reshape(1, -1), verbose=0)[0])

            target_f = self.model.predict(state.reshape(1, -1), verbose=0)
            target_f[0][action] = target

            self.model.fit(state.reshape(1, -1), target_f, epochs=1, verbose=0)

        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def load(self, name):
        """Load trained model"""
        self.model.load_weights(name)

    def save(self, name):
        """Save trained model"""
        self.model.save_weights(name)

# ============================================================================
# AI TRADING STRATEGY INTEGRATION
# ============================================================================
class AIStrategyIntegrator:
    """Integrate AI models with existing trading strategies"""

    def __init__(self, config: AIModelConfig):
        self.config = config
        self.predictive_models = PredictiveModels(config)
        self.sentiment_analyzer = SentimentAnalyzer()
        self.rl_agent = None
        self.logger = TradingLogger()

    def generate_ai_signals(self, symbol: str, df: pd.DataFrame) -> Dict:
        """Generate trading signals using AI models"""
        try:
            signals = {}

            # Price prediction signal
            price_pred = self.predictive_models.predict_price(symbol, df)
            if 'error' not in price_pred:
                price_change = price_pred['change']
                if price_change > 0.02:  # 2% upside
                    signals['price_signal'] = {'action': 'buy', 'confidence': 0.7, 'reason': f'AI predicts {price_change:.1%} upside'}
                elif price_change < -0.02:  # 2% downside
                    signals['price_signal'] = {'action': 'sell', 'confidence': 0.7, 'reason': f'AI predicts {abs(price_change):.1%} downside'}

            # Sentiment signal
            sentiment = self.sentiment_analyzer.get_combined_sentiment(symbol)
            if sentiment['combined_score'] > 0.3:
                signals['sentiment_signal'] = {'action': 'buy', 'confidence': 0.6, 'reason': f'Strong positive sentiment ({sentiment["combined_score"]:.2f})'}
            elif sentiment['combined_score'] < -0.3:
                signals['sentiment_signal'] = {'action': 'sell', 'confidence': 0.6, 'reason': f'Strong negative sentiment ({sentiment["combined_score"]:.2f})'}

            # Combine signals
            combined_signal = self._combine_signals(signals)

            return {
                'symbol': symbol,
                'ai_signals': signals,
                'combined_action': combined_signal['action'],
                'combined_confidence': combined_signal['confidence'],
                'reasons': combined_signal['reasons'],
                'price_prediction': price_pred,
                'sentiment': sentiment
            }

        except Exception as e:
            self.logger.logger.error(f"Error generating AI signals for {symbol}: {e}")
            return {'error': str(e)}

    def _combine_signals(self, signals: Dict) -> Dict:
        """Combine multiple AI signals into single trading decision"""
        if not signals:
            return {'action': 'hold', 'confidence': 0.0, 'reasons': []}

        actions = []
        confidences = []
        reasons = []

        for signal_type, signal in signals.items():
            actions.append(signal['action'])
            confidences.append(signal['confidence'])
            reasons.append(signal['reason'])

        # Simple majority voting with confidence weighting
        buy_count = actions.count('buy')
        sell_count = actions.count('sell')
        hold_count = actions.count('hold')

        if buy_count > sell_count and buy_count > hold_count:
            action = 'buy'
            confidence = np.mean([c for a, c in zip(actions, confidences) if a == 'buy'])
        elif sell_count > buy_count and sell_count > hold_count:
            action = 'sell'
            confidence = np.mean([c for a, c in zip(actions, confidences) if a == 'sell'])
        else:
            action = 'hold'
            confidence = 0.0

        return {
            'action': action,
            'confidence': confidence,
            'reasons': reasons
        }

    def get_rl_trading_signal(self, symbol: str, market_state: np.array) -> Dict:
        """Get trading signal from reinforcement learning agent"""
        if self.rl_agent is None:
            return {'action': 'hold', 'confidence': 0.0, 'reason': 'RL agent not initialized'}

        try:
            action = self.rl_agent.act(market_state)

            action_map = {0: 'hold', 1: 'buy', 2: 'sell'}
            confidence = 0.8 if self.rl_agent.epsilon < 0.1 else 0.5  # Higher confidence when not exploring

            return {
                'action': action_map[action],
                'confidence': confidence,
                'reason': f'RL agent decision (epsilon: {self.rl_agent.epsilon:.3f})'
            }

        except Exception as e:
            self.logger.logger.error(f"Error getting RL signal for {symbol}: {e}")
            return {'action': 'hold', 'confidence': 0.0, 'reason': f'RL error: {str(e)}'}

# ============================================================================
# MAIN AI TRADING SYSTEM
# ============================================================================
class AIMarketPredictor:
    """Main AI market prediction system"""

    def __init__(self, config: AIModelConfig = None):
        self.config = config or AIModelConfig()
        self.predictive_models = PredictiveModels(self.config)
        self.sentiment_analyzer = SentimentAnalyzer()
        self.strategy_integrator = AIStrategyIntegrator(self.config)
        self.feature_engineer = FeatureEngineer()
        self.logger = TradingLogger()

        # Initialize RL agent
        state_size = len(self.config.feature_columns) * self.config.sequence_length
        self.strategy_integrator.rl_agent = RLTradingAgent(state_size)

        self.logger.logger.info("🚀 AI Market Predictor initialized")

    def train_models_for_symbols(self, symbols: List[str], data_provider) -> Dict:
        """Train AI models for multiple symbols"""
        results = {}

        for symbol in symbols:
            try:
                self.logger.logger.info(f"Training AI models for {symbol}")

                # Fetch data
                df = data_provider.fetch_with_retry(symbol, interval="5minute", days=60)
                if df.empty:
                    results[symbol] = {'error': 'No data available'}
                    continue

                # Train LSTM model
                lstm_result = self.predictive_models.train_model(symbol, df, 'lstm')
                results[f'{symbol}_lstm'] = lstm_result

                # Train Transformer model
                transformer_result = self.predictive_models.train_model(symbol, df, 'transformer')
                results[f'{symbol}_transformer'] = transformer_result

                self.logger.logger.info(f"✅ AI models trained for {symbol}")

            except Exception as e:
                self.logger.logger.error(f"Error training models for {symbol}: {e}")
                results[symbol] = {'error': str(e)}

        return results

    def get_ai_predictions(self, symbols: List[str], data_provider) -> Dict:
        """Get AI predictions for multiple symbols"""
        predictions = {}

        for symbol in symbols:
            try:
                # Fetch latest data
                df = data_provider.fetch_with_retry(symbol, interval="5minute", days=30)
                if df.empty:
                    predictions[symbol] = {'error': 'No data available'}
                    continue

                # Get AI signals
                ai_signals = self.strategy_integrator.generate_ai_signals(symbol, df)
                predictions[symbol] = ai_signals

            except Exception as e:
                self.logger.logger.error(f"Error getting AI predictions for {symbol}: {e}")
                predictions[symbol] = {'error': str(e)}

        return predictions

    def get_market_insights(self, symbols: List[str], data_provider) -> Dict:
        """Get comprehensive market insights using AI"""
        insights = {
            'predictions': {},
            'sentiment': {},
            'risk_metrics': {},
            'recommendations': []
        }

        try:
            # Get predictions
            predictions = self.get_ai_predictions(symbols, data_provider)
            insights['predictions'] = predictions

            # Get sentiment analysis
            for symbol in symbols:
                sentiment = self.sentiment_analyzer.get_combined_sentiment(symbol)
                insights['sentiment'][symbol] = sentiment

            # Generate recommendations
            insights['recommendations'] = self._generate_trading_recommendations(predictions, insights['sentiment'])

            return insights

        except Exception as e:
            self.logger.logger.error(f"Error generating market insights: {e}")
            return {'error': str(e)}

    def _generate_trading_recommendations(self, predictions: Dict, sentiment: Dict) -> List[Dict]:
        """Generate trading recommendations based on AI analysis"""
        recommendations = []

        for symbol, pred in predictions.items():
            if 'error' in pred:
                continue

            sent = sentiment.get(symbol, {})

            # Combine prediction and sentiment
            combined_score = 0
            confidence = 0.5

            if 'combined_action' in pred and pred['combined_action'] != 'hold':
                if pred['combined_action'] == 'buy':
                    combined_score += 1
                else:
                    combined_score -= 1
                confidence = max(confidence, pred.get('combined_confidence', 0.5))

            if 'overall_sentiment' in sent:
                if sent['overall_sentiment'] == 'bullish':
                    combined_score += 0.5
                elif sent['overall_sentiment'] == 'bearish':
                    combined_score -= 0.5

            # Generate recommendation
            if combined_score > 0.5:
                action = 'BUY'
                reason = 'Strong AI and sentiment signals'
            elif combined_score < -0.5:
                action = 'SELL'
                reason = 'Strong negative AI and sentiment signals'
            else:
                action = 'HOLD'
                reason = 'Mixed or weak signals'

            recommendations.append({
                'symbol': symbol,
                'action': action,
                'confidence': confidence,
                'reason': reason,
                'ai_signals': pred,
                'sentiment': sent
            })

        return recommendations

# ============================================================================
# INTEGRATION WITH EXISTING SYSTEM
# ============================================================================
class AIEnhancedTradingSystem:
    """Enhanced trading system with AI integration"""

    def __init__(self, existing_system=None):
        self.existing_system = existing_system
        self.ai_predictor = AIMarketPredictor()
        self.logger = TradingLogger()

    def get_enhanced_signals(self, symbol: str, df: pd.DataFrame) -> Dict:
        """Get enhanced signals combining traditional and AI strategies"""
        try:
            # Get traditional signals (if existing system available)
            traditional_signals = {'action': 'hold', 'confidence': 0.0, 'reasons': []}

            if self.existing_system:
                # This would integrate with the existing strategy classes
                # For now, using placeholder
                pass

            # Get AI signals
            ai_signals = self.ai_predictor.strategy_integrator.generate_ai_signals(symbol, df)

            # Combine signals
            combined = self._combine_traditional_and_ai_signals(traditional_signals, ai_signals)

            return {
                'symbol': symbol,
                'traditional_signals': traditional_signals,
                'ai_signals': ai_signals,
                'combined_signal': combined,
                'enhancement_factor': ai_signals.get('combined_confidence', 0.0) / max(traditional_signals['confidence'], 0.1)
            }

        except Exception as e:
            self.logger.logger.error(f"Error getting enhanced signals for {symbol}: {e}")
            return {'error': str(e)}

    def _combine_traditional_and_ai_signals(self, traditional: Dict, ai: Dict) -> Dict:
        """Combine traditional and AI signals intelligently"""
        # Weighted combination based on confidence
        traditional_weight = traditional['confidence']
        ai_weight = ai.get('combined_confidence', 0.0)

        total_weight = traditional_weight + ai_weight
        if total_weight == 0:
            return {'action': 'hold', 'confidence': 0.0, 'reasons': []}

        # Combine actions
        if traditional['action'] == ai.get('combined_action', 'hold'):
            action = traditional['action']
            confidence = (traditional_weight + ai_weight) / 2
        else:
            # Different actions - choose based on higher confidence
            if ai_weight > traditional_weight:
                action = ai.get('combined_action', 'hold')
                confidence = ai_weight
            else:
                action = traditional['action']
                confidence = traditional_weight

        reasons = traditional['reasons'] + ai.get('reasons', [])

        return {
            'action': action,
            'confidence': confidence,
            'reasons': reasons
        }

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def create_ai_trading_system(existing_system=None) -> AIEnhancedTradingSystem:
    """Factory function to create AI-enhanced trading system"""
    return AIEnhancedTradingSystem(existing_system)

def train_ai_models_for_nifty50(data_provider, symbols: List[str] = None) -> Dict:
    """Train AI models for NIFTY 50 symbols"""
    if symbols is None:
        symbols = [
            "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN",
            "INFY", "TCS", "WIPRO", "HCLTECH", "TECHM",
            "RELIANCE", "LT", "BHARTIARTL", "MARUTI", "M&M"
        ]

    ai_predictor = AIMarketPredictor()
    return ai_predictor.train_models_for_symbols(symbols, data_provider)

def get_ai_market_insights(symbols: List[str], data_provider) -> Dict:
    """Get AI-powered market insights"""
    ai_predictor = AIMarketPredictor()
    return ai_predictor.get_market_insights(symbols, data_provider)

# ============================================================================
# MAIN EXECUTION
# ============================================================================
if __name__ == "__main__":
    print("🤖 AI Trading System")
    print("=" * 50)
    print("Advanced Machine Learning for Trading")
    print("Features:")
    print("• Predictive Price Modeling (LSTM/Transformer)")
    print("• Sentiment Analysis")
    print("• Reinforcement Learning Strategies")
    print("• Feature Engineering")
    print("• Risk-Adjusted AI Models")
    print("=" * 50)

    # Example usage
    try:
        # Initialize AI system
        ai_system = AIMarketPredictor()

        print("✅ AI Trading System initialized successfully!")
        print("💡 Use train_ai_models_for_nifty50() to train models")
        print("💡 Use get_ai_market_insights() for predictions")

    except Exception as e:
        print(f"❌ Error initializing AI system: {e}")
        print("Make sure TensorFlow and required dependencies are installed")