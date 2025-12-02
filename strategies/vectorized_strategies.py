import pandas as pd
import numpy as np
from core.vectorized_backtester import Strategy

class VectorizedMACrossover(Strategy):
    """Vectorized Moving Average Crossover"""
    def __init__(self, fast_period: int = 3, slow_period: int = 10):
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        
        # Calculate EMAs
        fast_ema = data['close'].ewm(span=self.fast_period, adjust=False).mean()
        slow_ema = data['close'].ewm(span=self.slow_period, adjust=False).mean()
        
        # Generate signals
        signals['signal'] = 0
        signals['signal'] = np.where(fast_ema > slow_ema, 1, -1)
        
        return pd.DataFrame({'signal': np.where(fast_ema > slow_ema, 1, -1)}, index=data.index)

class VectorizedRSI(Strategy):
    """Vectorized RSI Strategy"""
    def __init__(self, period: int = 14, buy_threshold: int = 30, sell_threshold: int = 70):
        self.period = period
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        
        # Buy when RSI < 30
        signals.loc[rsi < self.buy_threshold, 'signal'] = 1
        
        # Sell when RSI > 70
        signals.loc[rsi > self.sell_threshold, 'signal'] = -1
        
        return signals

class VectorizedBollingerBands(Strategy):
    """Vectorized Bollinger Bands Strategy"""
    def __init__(self, period: int = 20, std_dev: float = 2):
        self.period = period
        self.std_dev = std_dev

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        
        # Calculate Bands
        sma = data['close'].rolling(window=self.period).mean()
        std = data['close'].rolling(window=self.period).std()
        upper_band = sma + (std * self.std_dev)
        lower_band = sma - (std * self.std_dev)
        
        # Buy when price < lower band (Oversold)
        signals.loc[data['close'] < lower_band, 'signal'] = 1
        
        # Sell when price > upper band (Overbought)
        signals.loc[data['close'] > upper_band, 'signal'] = -1
        
        return signals

class VectorizedVolumeBreakout(Strategy):
    """Vectorized Volume Breakout Strategy"""
    def __init__(self, volume_multiplier: float = 1.3, price_threshold: float = 0.001):
        self.volume_multiplier = volume_multiplier
        self.price_threshold = price_threshold

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        
        # Volume MA
        vol_avg = data['volume'].rolling(window=20).mean()
        
        # Price Change
        price_change = data['close'].pct_change()
        
        # Conditions
        high_volume = data['volume'] > (vol_avg * self.volume_multiplier)
        price_up = price_change > self.price_threshold
        price_down = price_change < -self.price_threshold
        
        # Buy: High Vol + Price Up
        signals.loc[high_volume & price_up, 'signal'] = 1
        
        # Sell: High Vol + Price Down
        signals.loc[high_volume & price_down, 'signal'] = -1
        
        return signals

class VectorizedMomentum(Strategy):
    """Vectorized Momentum Strategy (Simplified)"""
    def __init__(self, momentum_period: int = 10, rsi_period: int = 14):
        self.momentum_period = momentum_period
        self.rsi_period = rsi_period

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0
        
        # Momentum
        momentum = data['close'].pct_change(self.momentum_period)
        
        # RSI
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # MACD
        ema_fast = data['close'].ewm(span=12, adjust=False).mean()
        ema_slow = data['close'].ewm(span=26, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=9, adjust=False).mean()
        
        # Buy: Positive Momentum + RSI < 70 + MACD > Signal
        buy_cond = (momentum > 0) & (rsi < 70) & (macd > signal_line)
        signals.loc[buy_cond, 'signal'] = 1
        
        # Sell: Negative Momentum + RSI > 30 + MACD < Signal
        sell_cond = (momentum < 0) & (rsi > 30) & (macd < signal_line)
        signals.loc[sell_cond, 'signal'] = -1
        
        return signals

class CombinedVectorizedStrategy(Strategy):
    """Combines multiple vectorized strategies"""
    def __init__(self, strategies):
        self.strategies = strategies

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        combined_signal = pd.Series(0, index=data.index)
        
        for strategy in self.strategies:
            s_sig = strategy.generate_signals(data)['signal']
            combined_signal += s_sig
            
        # Majority vote
        final_signal = pd.DataFrame(index=data.index)
        final_signal['signal'] = 0
        
        # If sum > 0 -> Buy/Hold Long
        # If sum < 0 -> Sell/Flat
        final_signal.loc[combined_signal > 0, 'signal'] = 1
        final_signal.loc[combined_signal < 0, 'signal'] = -1
        
        return final_signal
