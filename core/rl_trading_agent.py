"""
Reinforcement Learning Trading Agent
Phase 4 Tier 1: Advanced Machine Learning

Implements reinforcement learning agents for algorithmic trading:
- Deep Q-Network (DQN) for discrete action spaces
- Proximal Policy Optimization (PPO) for continuous actions
- Experience replay and target networks
- Policy evaluation and comparison

Author: Trading System
Date: October 22, 2025
"""

import hashlib
import hmac
import logging
import random
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Try to import ML libraries
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    import torch.nn.functional as F
    from torch.distributions import Normal
except ImportError:
    torch = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _write_checkpoint_hash(path: Path) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(path.suffix + '.sha256').write_text(digest, encoding='utf-8')


def _verify_checkpoint_hash(path: Path) -> None:
    hash_path = path.with_suffix(path.suffix + '.sha256')
    if not hash_path.exists():
        logger.warning("Checkpoint hash missing for %s; skipping integrity check", path)
        return
    expected = hash_path.read_text(encoding='utf-8').strip()
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if not hmac.compare_digest(expected, actual):
        raise ValueError(f"Integrity check failed for checkpoint {path}")


def _torch_load_safely(path: Path, device):
    if torch is None:
        raise RuntimeError("PyTorch not available")
    try:
        return torch.load(path, map_location=device, weights_only=True)
    except TypeError:
        return torch.load(path, map_location=device)


@dataclass
class RLConfig:
    """Configuration for RL agents"""
    # Network architecture
    hidden_sizes: List[int] = None
    activation: str = "relu"
    
    # Training hyperparameters
    learning_rate: float = 3e-4
    gamma: float = 0.99  # Discount factor
    batch_size: int = 64
    buffer_size: int = 100000
    
    # Exploration
    epsilon_start: float = 1.0
    epsilon_end: float = 0.01
    epsilon_decay: float = 0.995
    
    # DQN specific
    target_update_freq: int = 100
    double_dqn: bool = True
    
    # PPO specific
    ppo_epochs: int = 10
    ppo_clip: float = 0.2
    value_loss_coef: float = 0.5
    entropy_coef: float = 0.01
    
    # Training
    max_episodes: int = 1000
    max_steps_per_episode: int = 1000
    
    def __post_init__(self):
        if self.hidden_sizes is None:
            self.hidden_sizes = [256, 128, 64]


class ReplayBuffer:
    """Experience replay buffer for DQN"""
    
    def __init__(self, capacity: int):
        """
        Initialize replay buffer
        
        Args:
            capacity: Maximum number of experiences to store
        """
        self.buffer = deque(maxlen=capacity)
    
    def push(self, state, action, reward, next_state, done):
        """Add experience to buffer"""
        self.buffer.append((state, action, reward, next_state, done))
    
    def sample(self, batch_size: int) -> Tuple:
        """Sample random batch from buffer"""
        batch = random.sample(self.buffer, batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        
        return (
            np.array(states),
            np.array(actions),
            np.array(rewards),
            np.array(next_states),
            np.array(dones)
        )
    
    def __len__(self) -> int:
        return len(self.buffer)


class QNetwork(nn.Module):
    """Q-Network for DQN"""
    
    def __init__(self, state_dim: int, action_dim: int, hidden_sizes: List[int]):
        """
        Initialize Q-Network
        
        Args:
            state_dim: Dimension of state space
            action_dim: Dimension of action space
            hidden_sizes: List of hidden layer sizes
        """
        super().__init__()
        
        layers = []
        in_dim = state_dim
        
        for hidden_size in hidden_sizes:
            layers.append(nn.Linear(in_dim, hidden_size))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.2))
            in_dim = hidden_size
        
        layers.append(nn.Linear(in_dim, action_dim))
        
        self.network = nn.Sequential(*layers)
    
    def forward(self, state):
        """Forward pass"""
        return self.network(state)


class DQNAgent:
    """
    Deep Q-Network agent for trading
    
    Uses experience replay and target networks for stable learning
    """
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        config: Optional[RLConfig] = None
    ):
        """
        Initialize DQN agent
        
        Args:
            state_dim: Dimension of state space
            action_dim: Number of discrete actions
            config: RL configuration
        """
        if torch is None:
            raise ImportError("PyTorch required. Install with: pip install torch")
        
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.config = config or RLConfig()
        
        # Networks
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.q_network = QNetwork(state_dim, action_dim, self.config.hidden_sizes).to(self.device)
        self.target_network = QNetwork(state_dim, action_dim, self.config.hidden_sizes).to(self.device)
        self.target_network.load_state_dict(self.q_network.state_dict())
        
        # Optimizer
        self.optimizer = optim.Adam(self.q_network.parameters(), lr=self.config.learning_rate)
        
        # Replay buffer
        self.replay_buffer = ReplayBuffer(self.config.buffer_size)
        
        # Exploration
        self.epsilon = self.config.epsilon_start
        
        # Training stats
        self.training_step = 0
        self.episode = 0
        self.losses = []
        
        logger.info(f"DQN agent initialized (device: {self.device}, "
                   f"state_dim: {state_dim}, action_dim: {action_dim})")
    
    def select_action(self, state: np.ndarray, training: bool = True) -> int:
        """
        Select action using epsilon-greedy policy
        
        Args:
            state: Current state
            training: Whether in training mode (use exploration)
        
        Returns:
            Action index
        """
        if training and random.random() < self.epsilon:
            # Random action (exploration)
            return random.randrange(self.action_dim)
        
        # Greedy action (exploitation)
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.q_network(state_tensor)
            action = q_values.argmax(1).item()
        
        return action
    
    def train_step(self) -> Optional[float]:
        """
        Perform one training step
        
        Returns:
            Loss value or None if buffer not large enough
        """
        if len(self.replay_buffer) < self.config.batch_size:
            return None
        
        # Sample batch
        states, actions, rewards, next_states, dones = self.replay_buffer.sample(self.config.batch_size)
        
        # Convert to tensors
        states = torch.FloatTensor(states).to(self.device)
        actions = torch.LongTensor(actions).to(self.device)
        rewards = torch.FloatTensor(rewards).to(self.device)
        next_states = torch.FloatTensor(next_states).to(self.device)
        dones = torch.FloatTensor(dones).to(self.device)
        
        # Current Q values
        current_q_values = self.q_network(states).gather(1, actions.unsqueeze(1)).squeeze(1)
        
        # Next Q values
        with torch.no_grad():
            if self.config.double_dqn:
                # Double DQN: use main network to select action, target network to evaluate
                next_actions = self.q_network(next_states).argmax(1)
                next_q_values = self.target_network(next_states).gather(1, next_actions.unsqueeze(1)).squeeze(1)
            else:
                # Standard DQN
                next_q_values = self.target_network(next_states).max(1)[0]
            
            target_q_values = rewards + (1 - dones) * self.config.gamma * next_q_values
        
        # Calculate loss
        loss = F.smooth_l1_loss(current_q_values, target_q_values)
        
        # Optimize
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.q_network.parameters(), 1.0)
        self.optimizer.step()
        
        # Update target network
        self.training_step += 1
        if self.training_step % self.config.target_update_freq == 0:
            self.target_network.load_state_dict(self.q_network.state_dict())
        
        # Decay epsilon
        self.epsilon = max(self.config.epsilon_end, self.epsilon * self.config.epsilon_decay)
        
        self.losses.append(loss.item())
        
        return loss.item()
    
    def save(self, path: str):
        """Save agent to disk"""
        torch.save({
            'q_network': self.q_network.state_dict(),
            'target_network': self.target_network.state_dict(),
            'optimizer': self.optimizer.state_dict(),
            'training_step': self.training_step,
            'episode': self.episode,
            'epsilon': self.epsilon,
        }, path)
        logger.info(f"DQN agent saved to {path}")
    
    def load(self, path: str):
        """Load agent from disk"""
        try:
            checkpoint = torch.load(path, map_location=self.device, weights_only=True)
        except TypeError:
            # Fallback for older PyTorch versions
            checkpoint = torch.load(path, map_location=self.device)
        self.q_network.load_state_dict(checkpoint['q_network'])
        self.target_network.load_state_dict(checkpoint['target_network'])
        self.optimizer.load_state_dict(checkpoint['optimizer'])
        self.training_step = checkpoint['training_step']
        self.episode = checkpoint['episode']
        self.epsilon = checkpoint['epsilon']
        logger.info(f"DQN agent loaded from {path}")


class ActorCriticNetwork(nn.Module):
    """Actor-Critic network for PPO"""
    
    def __init__(self, state_dim: int, action_dim: int, hidden_sizes: List[int]):
        """
        Initialize Actor-Critic network
        
        Args:
            state_dim: Dimension of state space
            action_dim: Dimension of action space (1 for continuous)
            hidden_sizes: List of hidden layer sizes
        """
        super().__init__()
        
        # Shared layers
        shared_layers = []
        in_dim = state_dim
        
        for hidden_size in hidden_sizes[:-1]:
            shared_layers.append(nn.Linear(in_dim, hidden_size))
            shared_layers.append(nn.ReLU())
            shared_layers.append(nn.Dropout(0.2))
            in_dim = hidden_size
        
        self.shared = nn.Sequential(*shared_layers)
        
        # Actor head (policy)
        self.actor_mean = nn.Linear(in_dim, action_dim)
        self.actor_log_std = nn.Parameter(torch.zeros(action_dim))
        
        # Critic head (value function)
        self.critic = nn.Linear(in_dim, 1)
    
    def forward(self, state):
        """Forward pass"""
        shared_out = self.shared(state)
        
        # Actor output
        action_mean = torch.tanh(self.actor_mean(shared_out))  # Bound to [-1, 1]
        action_std = torch.exp(self.actor_log_std).expand_as(action_mean)
        
        # Critic output
        value = self.critic(shared_out)
        
        return action_mean, action_std, value


class PPOAgent:
    """
    Proximal Policy Optimization agent for trading
    
    Uses continuous action space for position sizing
    """
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int = 1,
        config: Optional[RLConfig] = None
    ):
        """
        Initialize PPO agent
        
        Args:
            state_dim: Dimension of state space
            action_dim: Dimension of action space (default: 1 for position size)
            config: RL configuration
        """
        if torch is None:
            raise ImportError("PyTorch required. Install with: pip install torch")
        
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.config = config or RLConfig()
        
        # Network
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.network = ActorCriticNetwork(state_dim, action_dim, self.config.hidden_sizes).to(self.device)
        
        # Optimizer
        self.optimizer = optim.Adam(self.network.parameters(), lr=self.config.learning_rate)
        
        # Experience storage
        self.states = []
        self.actions = []
        self.rewards = []
        self.values = []
        self.log_probs = []
        self.dones = []
        
        # Training stats
        self.episode = 0
        self.policy_losses = []
        self.value_losses = []
        
        logger.info(f"PPO agent initialized (device: {self.device}, "
                   f"state_dim: {state_dim}, action_dim: {action_dim})")
    
    def select_action(self, state: np.ndarray, training: bool = True) -> Tuple[np.ndarray, float, float]:
        """
        Select action from policy
        
        Args:
            state: Current state
            training: Whether in training mode
        
        Returns:
            Tuple of (action, log_prob, value)
        """
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            action_mean, action_std, value = self.network(state_tensor)
        
        # Sample action from distribution
        dist = Normal(action_mean, action_std)
        
        if training:
            action = dist.sample()
        else:
            action = action_mean  # Use mean action for evaluation
        
        log_prob = dist.log_prob(action).sum(dim=-1)
        
        return action.cpu().numpy()[0], log_prob.item(), value.item()
    
    def store_transition(self, state, action, reward, value, log_prob, done):
        """Store transition in memory"""
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.values.append(value)
        self.log_probs.append(log_prob)
        self.dones.append(done)
    
    def train_step(self) -> Tuple[float, float]:
        """
        Perform PPO training update
        
        Returns:
            Tuple of (policy_loss, value_loss)
        """
        if len(self.states) == 0:
            return 0.0, 0.0
        
        # Convert to tensors
        states = torch.FloatTensor(np.array(self.states)).to(self.device)
        actions = torch.FloatTensor(np.array(self.actions)).to(self.device)
        old_log_probs = torch.FloatTensor(self.log_probs).to(self.device)
        
        # Calculate returns and advantages
        returns = self._calculate_returns()
        returns = torch.FloatTensor(returns).to(self.device)
        
        values = torch.FloatTensor(self.values).to(self.device)
        advantages = returns - values
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # PPO update
        total_policy_loss = 0.0
        total_value_loss = 0.0
        
        for _ in range(self.config.ppo_epochs):
            # Get current policy outputs
            action_mean, action_std, current_values = self.network(states)
            
            # Calculate new log probs
            dist = Normal(action_mean, action_std)
            new_log_probs = dist.log_prob(actions).sum(dim=-1)
            entropy = dist.entropy().sum(dim=-1).mean()
            
            # Policy loss (PPO clip)
            ratio = torch.exp(new_log_probs - old_log_probs)
            clipped_ratio = torch.clamp(ratio, 1 - self.config.ppo_clip, 1 + self.config.ppo_clip)
            policy_loss = -torch.min(ratio * advantages, clipped_ratio * advantages).mean()
            
            # Value loss
            value_loss = F.mse_loss(current_values.squeeze(), returns)
            
            # Total loss
            loss = policy_loss + self.config.value_loss_coef * value_loss - self.config.entropy_coef * entropy
            
            # Optimize
            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.network.parameters(), 0.5)
            self.optimizer.step()
            
            total_policy_loss += policy_loss.item()
            total_value_loss += value_loss.item()
        
        avg_policy_loss = total_policy_loss / self.config.ppo_epochs
        avg_value_loss = total_value_loss / self.config.ppo_epochs
        
        self.policy_losses.append(avg_policy_loss)
        self.value_losses.append(avg_value_loss)
        
        # Clear memory
        self.clear_memory()
        
        return avg_policy_loss, avg_value_loss
    
    def _calculate_returns(self) -> np.ndarray:
        """Calculate discounted returns"""
        returns = []
        R = 0
        
        for reward, done in zip(reversed(self.rewards), reversed(self.dones)):
            if done:
                R = 0
            R = reward + self.config.gamma * R
            returns.insert(0, R)
        
        return np.array(returns)
    
    def clear_memory(self):
        """Clear stored experiences"""
        self.states = []
        self.actions = []
        self.rewards = []
        self.values = []
        self.log_probs = []
        self.dones = []
    
    def save(self, path: str):
        """Save agent to disk"""
        torch.save({
            'network': self.network.state_dict(),
            'optimizer': self.optimizer.state_dict(),
            'episode': self.episode,
        }, path)
        logger.info(f"PPO agent saved to {path}")
    
    def load(self, path: str):
        """Load agent from disk"""
        try:
            checkpoint = torch.load(path, map_location=self.device, weights_only=True)
        except TypeError:
            # Fallback for older PyTorch versions
            checkpoint = torch.load(path, map_location=self.device)
        self.network.load_state_dict(checkpoint['network'])
        self.optimizer.load_state_dict(checkpoint['optimizer'])
        self.episode = checkpoint['episode']
        logger.info(f"PPO agent loaded from {path}")


if __name__ == "__main__":
    print("RL Trading Agent Module")
    print("=" * 50)
    
    if torch is None:
        print("\nPyTorch not installed. Install with:")
        print("  pip install torch")
        exit(1)
    
    # Test DQN agent
    print("\nTesting DQN Agent:")
    print("-" * 50)
    
    state_dim = 60  # Example state dimension
    action_dim = 3  # Buy, Hold, Sell
    
    dqn_agent = DQNAgent(state_dim, action_dim)
    
    print(f"State dimension: {state_dim}")
    print(f"Action dimension: {action_dim}")
    print(f"Device: {dqn_agent.device}")
    print(f"Epsilon: {dqn_agent.epsilon:.3f}")
    
    # Test action selection
    test_state = np.random.randn(state_dim)
    action = dqn_agent.select_action(test_state)
    print(f"\nSelected action: {action}")
    
    # Test PPO agent
    print("\n" + "=" * 50)
    print("Testing PPO Agent:")
    print("-" * 50)
    
    ppo_agent = PPOAgent(state_dim, action_dim=1)
    
    print(f"State dimension: {state_dim}")
    print(f"Action dimension: {ppo_agent.action_dim}")
    print(f"Device: {ppo_agent.device}")
    
    # Test action selection
    action, log_prob, value = ppo_agent.select_action(test_state)
    print(f"\nSelected action: {action}")
    print(f"Log probability: {log_prob:.4f}")
    print(f"Value estimate: {value:.4f}")
    
    print("\n" + "=" * 50)
    print("RL trading agent module loaded successfully!")
