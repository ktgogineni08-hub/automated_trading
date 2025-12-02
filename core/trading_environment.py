"""
Trading Environment
Phase 4 Tier 1: Advanced Machine Learning - Reinforcement Learning

OpenAI Gym-compatible trading environment for reinforcement learning agents.
Provides a realistic simulation of trading with proper reward shaping.

Features:
- Continuous and discrete action spaces
- Realistic transaction costs and slippage
- Multiple market regimes
- Portfolio management
- Customizable reward functions

Author: Trading System
Date: October 22, 2025
"""

import logging
from typing import Tuple, Dict, Optional, List
from enum import Enum
import numpy as np
import pandas as pd

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:
    # Fallback to older gym if gymnasium not available
    try:
        import gym
        from gym import spaces
        gymnasium = None
    except ImportError:
        gym = None
        spaces = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ActionSpace(Enum):
    """Type of action space"""
    DISCRETE = "discrete"  # Buy, Hold, Sell
    CONTINUOUS = "continuous"  # Position size from -1 to +1


class RewardFunction(Enum):
    """Reward function type"""
    PNL = "pnl"  # Profit and loss
    SHARPE = "sharpe"  # Sharpe ratio
    SORTINO = "sortino"  # Sortino ratio
    CALMAR = "calmar"  # Calmar ratio


class TradingEnvironment(gym.Env if gym else object):
    """
    OpenAI Gym-compatible trading environment for RL

    State space: [prices, technical indicators, portfolio state, market features]
    Action space: Discrete (buy/hold/sell) or Continuous (position size -1 to +1)
    Reward: Configurable (P&L, Sharpe, etc.)
    """

    metadata = {'render.modes': ['human']}

    def __init__(
        self,
        data: pd.DataFrame,
        initial_capital: float = 100000.0,
        transaction_cost_pct: float = 0.001,
        slippage_pct: float = 0.0005,
        action_space_type: ActionSpace = ActionSpace.CONTINUOUS,
        reward_function: RewardFunction = RewardFunction.SHARPE,
        lookback_window: int = 20,
        max_position_size: float = 1.0,
        enable_short_selling: bool = True,
        reward_scaling: float = 1.0,
    ):
        """
        Initialize trading environment

        Args:
            data: DataFrame with OHLCV and features
            initial_capital: Starting capital
            transaction_cost_pct: Transaction cost as percentage
            slippage_pct: Slippage as percentage
            action_space_type: Discrete or continuous actions
            reward_function: Type of reward function
            lookback_window: Number of past observations to include in state
            max_position_size: Maximum position size (as fraction of capital)
            enable_short_selling: Allow short positions
            reward_scaling: Scale reward values
        """
        super().__init__()

        if gym is None:
            raise ImportError("gym or gymnasium required. Install with: pip install gymnasium")

        self.data = data.copy()
        self.initial_capital = initial_capital
        self.transaction_cost_pct = transaction_cost_pct
        self.slippage_pct = slippage_pct
        self.action_space_type = action_space_type
        self.reward_function = reward_function
        self.lookback_window = lookback_window
        self.max_position_size = max_position_size
        self.enable_short_selling = enable_short_selling
        self.reward_scaling = reward_scaling

        # Validate data
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in self.data.columns:
                raise ValueError(f"Data must contain '{col}' column")

        # Environment state
        self.current_step = 0
        self.done = False

        # Portfolio state
        self.capital = initial_capital
        self.position = 0.0  # Current position size (-1 to +1)
        self.entry_price = 0.0
        self.portfolio_value = initial_capital

        # Performance tracking
        self.equity_history = []
        self.returns_history = []
        self.actions_history = []
        self.rewards_history = []

        # Define action and observation spaces
        self._define_spaces()

        logger.info(f"Trading environment initialized: {len(data)} steps, "
                   f"action_space={action_space_type.value}, "
                   f"reward={reward_function.value}")

    def _define_spaces(self):
        """Define action and observation spaces"""
        # Action space
        if self.action_space_type == ActionSpace.DISCRETE:
            # 0 = Sell/Short, 1 = Hold, 2 = Buy/Long
            self.action_space = spaces.Discrete(3)
        else:
            # Continuous: -1 (full short) to +1 (full long)
            self.action_space = spaces.Box(
                low=-1.0 if self.enable_short_selling else 0.0,
                high=1.0,
                shape=(1,),
                dtype=np.float32
            )

        # Observation space
        # [price features (OHLCV), technical indicators, portfolio state]
        n_price_features = 5  # OHLCV + close_pct_change
        n_technical_features = len([c for c in self.data.columns 
                                    if c not in ['open', 'high', 'low', 'close', 'volume']])
        n_portfolio_features = 3  # position, unrealized_pnl, cash_ratio

        n_features = n_price_features + n_technical_features + n_portfolio_features

        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(n_features * self.lookback_window,),
            dtype=np.float32
        )

        logger.debug(f"Observation space: {self.observation_space.shape}")
        logger.debug(f"Action space: {self.action_space}")

    def reset(self, seed: Optional[int] = None) -> Tuple:
        """
        Reset environment to initial state

        Returns:
            Tuple of (observation, info) for gymnasium, or just observation for gym
        """
        if seed is not None:
            np.random.seed(seed)

        # Reset state
        self.current_step = self.lookback_window
        self.done = False

        # Reset portfolio
        self.capital = self.initial_capital
        self.position = 0.0
        self.entry_price = 0.0
        self.portfolio_value = self.initial_capital

        # Reset history
        self.equity_history = [self.initial_capital]
        self.returns_history = []
        self.actions_history = []
        self.rewards_history = []

        obs = self._get_observation()

        # Return format depends on gym vs gymnasium
        if gymnasium is not None:
            return obs, {}
        else:
            return obs

    def step(self, action) -> Tuple:
        """
        Execute one step in the environment

        Args:
            action: Action to take

        Returns:
            Tuple of (observation, reward, done, truncated, info) for gymnasium
            or (observation, reward, done, info) for gym
        """
        if self.done:
            raise RuntimeError("Episode has ended. Call reset() to start a new episode.")

        # Convert action to position size
        target_position = self._action_to_position(action)

        # Execute trade
        current_price = self.data.iloc[self.current_step]['close']
        reward = self._execute_trade(target_position, current_price)

        # Update step
        self.current_step += 1

        # Check if done
        self.done = (
            self.current_step >= len(self.data) - 1 or
            self.portfolio_value <= 0.1 * self.initial_capital  # Stop if lost 90%
        )

        # Get next observation
        obs = self._get_observation()

        # Store history
        self.actions_history.append(action)
        self.rewards_history.append(reward)

        # Info dictionary
        info = {
            'portfolio_value': self.portfolio_value,
            'position': self.position,
            'step': self.current_step,
            'capital': self.capital
        }

        # Return format depends on gym vs gymnasium
        if gymnasium is not None:
            return obs, reward, self.done, False, info  # truncated=False
        else:
            return obs, reward, self.done, info

    def _action_to_position(self, action) -> float:
        """Convert action to target position size"""
        if self.action_space_type == ActionSpace.DISCRETE:
            # Map discrete action to position
            if action == 0:
                # Sell/Short
                target_position = -self.max_position_size if self.enable_short_selling else 0.0
            elif action == 1:
                # Hold
                target_position = self.position
            else:
                # Buy/Long
                target_position = self.max_position_size
        else:
            # Continuous action
            if isinstance(action, np.ndarray):
                target_position = float(action[0])
            else:
                target_position = float(action)

            # Clip to valid range
            min_pos = -self.max_position_size if self.enable_short_selling else 0.0
            target_position = np.clip(target_position, min_pos, self.max_position_size)

        return target_position

    def _execute_trade(self, target_position: float, current_price: float) -> float:
        """
        Execute trade and calculate reward

        Args:
            target_position: Target position size
            current_price: Current market price

        Returns:
            Reward for this step
        """
        # Calculate position change
        position_change = target_position - self.position

        # Calculate transaction costs
        trade_value = abs(position_change) * current_price * self.initial_capital
        transaction_cost = trade_value * self.transaction_cost_pct

        # Calculate slippage
        slippage = trade_value * self.slippage_pct

        # Calculate unrealized P&L from previous position
        if self.position != 0 and self.entry_price > 0:
            pnl = self.position * (current_price - self.entry_price) * self.initial_capital
        else:
            pnl = 0.0

        # Update portfolio
        self.capital -= (transaction_cost + slippage)

        # Update position
        if abs(position_change) > 1e-6:  # Only update if significant change
            # Close existing position if switching sides
            if np.sign(self.position) != np.sign(target_position) and abs(self.position) > 1e-6:
                self.capital += pnl  # Realize P&L
                self.entry_price = current_price
            elif abs(self.position) < 1e-6:
                # Opening new position
                self.entry_price = current_price
            else:
                # Adding to position - update weighted average entry price
                old_value = abs(self.position) * self.entry_price
                new_value = abs(position_change) * current_price
                total_position = abs(target_position)
                if total_position > 0:
                    self.entry_price = (old_value + new_value) / total_position

            self.position = target_position

        # Calculate current portfolio value
        if self.position != 0:
            unrealized_pnl = self.position * (current_price - self.entry_price) * self.initial_capital
        else:
            unrealized_pnl = 0.0

        self.portfolio_value = self.capital + unrealized_pnl

        # Calculate return
        if len(self.equity_history) > 0:
            prev_value = self.equity_history[-1]
            current_return = (self.portfolio_value - prev_value) / prev_value
        else:
            current_return = 0.0

        self.equity_history.append(self.portfolio_value)
        self.returns_history.append(current_return)

        # Calculate reward based on chosen reward function
        reward = self._calculate_reward(current_return, unrealized_pnl)

        return reward

    def _calculate_reward(self, current_return: float, unrealized_pnl: float) -> float:
        """Calculate reward based on selected reward function"""
        if self.reward_function == RewardFunction.PNL:
            # Simple P&L reward
            reward = unrealized_pnl / self.initial_capital * 100

        elif self.reward_function == RewardFunction.SHARPE:
            # Sharpe ratio-based reward
            if len(self.returns_history) > 2:
                returns = np.array(self.returns_history[-20:])  # Last 20 returns
                if returns.std() > 0:
                    sharpe = returns.mean() / returns.std() * np.sqrt(252)
                    reward = sharpe
                else:
                    reward = 0.0
            else:
                reward = current_return * 100

        elif self.reward_function == RewardFunction.SORTINO:
            # Sortino ratio-based reward (only penalize downside volatility)
            if len(self.returns_history) > 2:
                returns = np.array(self.returns_history[-20:])
                negative_returns = returns[returns < 0]
                if len(negative_returns) > 0:
                    downside_std = negative_returns.std()
                    if downside_std > 0:
                        sortino = returns.mean() / downside_std * np.sqrt(252)
                        reward = sortino
                    else:
                        reward = returns.mean() * 100
                else:
                    reward = returns.mean() * 100
            else:
                reward = current_return * 100

        elif self.reward_function == RewardFunction.CALMAR:
            # Calmar ratio-based reward (return / max drawdown)
            if len(self.equity_history) > 2:
                equity = np.array(self.equity_history)
                peak = np.maximum.accumulate(equity)
                drawdown = (equity - peak) / peak
                max_drawdown = abs(drawdown.min())

                if max_drawdown > 0.01:  # Avoid division by very small numbers
                    total_return = (equity[-1] - equity[0]) / equity[0]
                    calmar = total_return / max_drawdown
                    reward = calmar
                else:
                    reward = current_return * 100
            else:
                reward = current_return * 100

        else:
            reward = current_return * 100

        # Apply scaling
        reward *= self.reward_scaling

        return reward

    def _get_observation(self) -> np.ndarray:
        """
        Get current observation (state)

        Returns:
            Flattened numpy array of features
        """
        if self.current_step < self.lookback_window:
            # Pad with zeros if at start
            lookback_data = self.data.iloc[:self.current_step + 1]
            padding_needed = self.lookback_window - len(lookback_data)
        else:
            lookback_data = self.data.iloc[self.current_step - self.lookback_window + 1:self.current_step + 1]
            padding_needed = 0

        features_list = []

        for idx, row in lookback_data.iterrows():
            # Price features
            price_features = [
                row['open'],
                row['high'],
                row['low'],
                row['close'],
                row['volume']
            ]

            # Normalize prices
            close = row['close']
            normalized_prices = [p / close for p in price_features]

            # Technical features (already in data)
            technical_features = []
            for col in self.data.columns:
                if col not in ['open', 'high', 'low', 'close', 'volume']:
                    technical_features.append(row[col] if not pd.isna(row[col]) else 0.0)

            # Portfolio features
            unrealized_pnl = 0.0
            if self.position != 0 and self.entry_price > 0:
                unrealized_pnl = self.position * (close - self.entry_price) / self.entry_price

            portfolio_features = [
                self.position,
                unrealized_pnl,
                self.capital / self.initial_capital
            ]

            # Combine all features
            step_features = normalized_prices + technical_features + portfolio_features
            features_list.extend(step_features)

        # Pad if necessary
        if padding_needed > 0:
            n_features_per_step = len(features_list) // len(lookback_data) if len(lookback_data) > 0 else 8
            padding = [0.0] * (n_features_per_step * padding_needed)
            features_list = padding + features_list

        return np.array(features_list, dtype=np.float32)

    def render(self, mode='human'):
        """Render environment state"""
        if mode == 'human':
            current_price = self.data.iloc[self.current_step]['close']
            print(f"Step: {self.current_step}/{len(self.data)}")
            print(f"Portfolio Value: ${self.portfolio_value:,.2f}")
            print(f"Capital: ${self.capital:,.2f}")
            print(f"Position: {self.position:.2f}")
            print(f"Current Price: ${current_price:.2f}")
            print(f"Total Return: {(self.portfolio_value / self.initial_capital - 1) * 100:.2f}%")
            print("-" * 50)

    def get_episode_stats(self) -> Dict:
        """Get statistics for completed episode"""
        if len(self.equity_history) < 2:
            return {}

        equity = np.array(self.equity_history)
        returns = np.array(self.returns_history) if len(self.returns_history) > 0 else np.array([0.0])

        # Calculate metrics
        total_return = (equity[-1] - equity[0]) / equity[0]

        # Sharpe ratio
        if returns.std() > 0:
            sharpe = returns.mean() / returns.std() * np.sqrt(252)
        else:
            sharpe = 0.0

        # Max drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        max_drawdown = abs(drawdown.min())

        # Win rate
        if len(self.returns_history) > 0:
            wins = sum(1 for r in self.returns_history if r > 0)
            win_rate = wins / len(self.returns_history)
        else:
            win_rate = 0.0

        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'final_value': equity[-1],
            'total_steps': self.current_step,
            'total_reward': sum(self.rewards_history) if self.rewards_history else 0.0
        }


if __name__ == "__main__":
    print("Trading Environment Module")
    print("=" * 50)

    # Create sample data
    dates = pd.date_range(end='2025-10-22', periods=100, freq='D')
    data = pd.DataFrame({
        'open': np.random.uniform(95, 105, 100),
        'high': np.random.uniform(100, 110, 100),
        'low': np.random.uniform(90, 100, 100),
        'close': np.random.uniform(95, 105, 100),
        'volume': np.random.randint(1000000, 5000000, 100),
    }, index=dates)

    # Initialize environment
    env = TradingEnvironment(
        data=data,
        initial_capital=100000,
        action_space_type=ActionSpace.CONTINUOUS,
        reward_function=RewardFunction.SHARPE
    )

    print(f"\nEnvironment initialized")
    print(f"Action space: {env.action_space}")
    print(f"Observation space: {env.observation_space.shape}")

    # Run a few random steps
    print("\nRunning 5 random steps:")
    print("-" * 50)

    obs = env.reset()
    for i in range(5):
        action = env.action_space.sample()
        obs, reward, done, info = env.step(action)[:4]  # Handle both gym and gymnasium

        print(f"Step {i+1}:")
        print(f"  Action: {action}")
        print(f"  Reward: {reward:.4f}")
        print(f"  Portfolio Value: ${info['portfolio_value']:,.2f}")
        print(f"  Position: {info['position']:.2f}")

        if done:
            break

    # Get episode stats
    stats = env.get_episode_stats()
    print("\nEpisode Statistics:")
    for key, value in stats.items():
        if 'return' in key or 'rate' in key or 'drawdown' in key:
            print(f"  {key}: {value:.2%}")
        elif 'value' in key:
            print(f"  {key}: ${value:,.2f}")
        else:
            print(f"  {key}: {value:.4f}")

    print("\n" + "=" * 50)
    print("Trading environment module loaded successfully!")
