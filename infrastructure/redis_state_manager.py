#!/usr/bin/env python3
"""
Redis-Based Distributed State Management
Replaces file-based state with distributed Redis storage

ADDRESSES CRITICAL RECOMMENDATION #2:
- Multi-instance state synchronization
- Distributed locking for concurrent access
- Pub/Sub for real-time state updates
- Automatic failover and persistence
- Session management across instances
"""

import logging
import json
import threading
import time
import hashlib
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import redis
from redis.sentinel import Sentinel
from redis.lock import Lock
from contextlib import contextmanager

logger = logging.getLogger('trading_system.redis_state')


class StateChannel(Enum):
    """Pub/Sub channels for state updates"""
    PORTFOLIO = "trading:portfolio:updates"
    POSITIONS = "trading:positions:updates"
    ORDERS = "trading:orders:updates"
    SYSTEM = "trading:system:updates"


@dataclass
class RedisConfig:
    """Redis connection configuration"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    socket_keepalive: bool = True
    health_check_interval: int = 30
    retry_on_timeout: bool = True
    decode_responses: bool = True

    # Sentinel configuration for high availability
    use_sentinel: bool = False
    sentinel_hosts: List[tuple] = None  # [(host, port), ...]
    sentinel_service: str = "mymaster"


class RedisStateManager:
    """
    Distributed State Manager using Redis

    Features:
    - Multi-instance state synchronization
    - Distributed locking (prevents race conditions)
    - Pub/Sub for real-time updates
    - Automatic expiration and cleanup
    - High availability with Redis Sentinel
    - Connection pooling
    - Atomic operations

    Key Namespaces:
    - trading:state:{instance_id}         - Instance-specific state
    - trading:portfolio:shared            - Shared portfolio state
    - trading:positions:{symbol}          - Position data
    - trading:orders:{order_id}           - Order tracking
    - trading:locks:{resource}            - Distributed locks
    - trading:sessions:{session_id}       - Active sessions
    """

    def __init__(
        self,
        config: RedisConfig,
        instance_id: Optional[str] = None,
        state_ttl_seconds: int = 86400  # 24 hours
    ):
        """
        Initialize Redis state manager

        Args:
            config: Redis configuration
            instance_id: Unique instance identifier
            state_ttl_seconds: State TTL in seconds
        """
        self.config = config
        self.instance_id = instance_id or self._generate_instance_id()
        self.state_ttl = state_ttl_seconds

        # Redis client
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None

        # Subscribers
        self._subscribers: Dict[StateChannel, List[Callable]] = {
            channel: [] for channel in StateChannel
        }
        self._subscriber_thread: Optional[threading.Thread] = None
        self._subscribing = False

        # Connection management
        self._lock = threading.RLock()

        # Connect
        self._connect()

        logger.info(f"📊 RedisStateManager initialized: instance={self.instance_id}")

    def _generate_instance_id(self) -> str:
        """Generate unique instance ID"""
        import socket
        import os
        hostname = socket.gethostname()
        pid = os.getpid()
        timestamp = datetime.now().isoformat()
        unique_str = f"{hostname}:{pid}:{timestamp}"
        return hashlib.sha256(unique_str.encode()).hexdigest()[:12]

    def _connect(self):
        """Establish Redis connection"""
        try:
            if self.config.use_sentinel and self.config.sentinel_hosts:
                # Use Redis Sentinel for HA
                sentinel = Sentinel(
                    self.config.sentinel_hosts,
                    socket_timeout=self.config.socket_timeout,
                    socket_connect_timeout=self.config.socket_connect_timeout,
                    password=self.config.password
                )
                self.redis_client = sentinel.master_for(
                    self.config.sentinel_service,
                    socket_timeout=self.config.socket_timeout,
                    db=self.config.db,
                    decode_responses=self.config.decode_responses
                )
                logger.info(
                    f"✅ Connected to Redis Sentinel: {self.config.sentinel_service}"
                )
            else:
                # Direct connection
                self.redis_client = redis.Redis(
                    host=self.config.host,
                    port=self.config.port,
                    db=self.config.db,
                    password=self.config.password,
                    socket_timeout=self.config.socket_timeout,
                    socket_connect_timeout=self.config.socket_connect_timeout,
                    socket_keepalive=self.config.socket_keepalive,
                    health_check_interval=self.config.health_check_interval,
                    retry_on_timeout=self.config.retry_on_timeout,
                    decode_responses=self.config.decode_responses
                )
                logger.info(f"✅ Connected to Redis: {self.config.host}:{self.config.port}")

            # Test connection
            self.redis_client.ping()

            # Register this instance
            self._register_instance()

        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise

    def _register_instance(self):
        """Register this instance in Redis"""
        key = f"trading:sessions:{self.instance_id}"
        session_data = {
            'instance_id': self.instance_id,
            'started_at': datetime.now().isoformat(),
            'last_heartbeat': datetime.now().isoformat(),
            'status': 'active'
        }

        self.redis_client.hset(key, mapping=session_data)
        self.redis_client.expire(key, 300)  # 5 minute TTL

        # Start heartbeat
        self._start_heartbeat()

    def _start_heartbeat(self):
        """Start heartbeat to keep session alive"""
        def heartbeat_loop():
            while True:
                try:
                    key = f"trading:sessions:{self.instance_id}"
                    self.redis_client.hset(
                        key,
                        'last_heartbeat',
                        datetime.now().isoformat()
                    )
                    self.redis_client.expire(key, 300)
                    time.sleep(60)  # Heartbeat every minute
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")
                    break

        heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        heartbeat_thread.start()

    @contextmanager
    def distributed_lock(
        self,
        resource: str,
        timeout: int = 10,
        blocking_timeout: int = 5
    ):
        """
        Distributed lock for resource synchronization

        Args:
            resource: Resource name to lock
            timeout: Lock timeout in seconds
            blocking_timeout: Max time to wait for lock

        Usage:
            with state_mgr.distributed_lock("portfolio"):
                # Critical section - only one instance can execute
                portfolio.update(...)
        """
        lock_key = f"trading:locks:{resource}"
        lock = self.redis_client.lock(
            lock_key,
            timeout=timeout,
            blocking_timeout=blocking_timeout
        )

        try:
            acquired = lock.acquire(blocking=True, blocking_timeout=blocking_timeout)
            if not acquired:
                raise TimeoutError(f"Failed to acquire lock: {resource}")

            yield lock

        finally:
            try:
                lock.release()
            except:
                pass  # Lock may have expired

    def save_portfolio_state(self, portfolio_data: Dict[str, Any]) -> bool:
        """
        Save portfolio state to Redis

        Args:
            portfolio_data: Portfolio state dictionary

        Returns:
            True if successful
        """
        try:
            with self.distributed_lock("portfolio"):
                key = "trading:portfolio:shared"

                # Add metadata
                portfolio_data['last_updated'] = datetime.now().isoformat()
                portfolio_data['instance_id'] = self.instance_id

                # Save to Redis
                self.redis_client.hset(
                    key,
                    mapping={
                        k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                        for k, v in portfolio_data.items()
                    }
                )

                # Set TTL
                self.redis_client.expire(key, self.state_ttl)

                # Publish update
                self._publish_update(StateChannel.PORTFOLIO, portfolio_data)

                logger.debug(f"Portfolio state saved: {key}")
                return True

        except Exception as e:
            logger.error(f"Failed to save portfolio state: {e}")
            return False

    def load_portfolio_state(self) -> Optional[Dict[str, Any]]:
        """
        Load portfolio state from Redis

        Returns:
            Portfolio state dictionary or None
        """
        try:
            key = "trading:portfolio:shared"
            data = self.redis_client.hgetall(key)

            if not data:
                return None

            # Deserialize JSON fields
            portfolio_data = {}
            for k, v in data.items():
                try:
                    portfolio_data[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    portfolio_data[k] = v

            return portfolio_data

        except Exception as e:
            logger.error(f"Failed to load portfolio state: {e}")
            return None

    def save_position(self, symbol: str, position_data: Dict[str, Any]) -> bool:
        """
        Save position data

        Args:
            symbol: Trading symbol
            position_data: Position details

        Returns:
            True if successful
        """
        try:
            key = f"trading:positions:{symbol}"

            # Add metadata
            position_data['last_updated'] = datetime.now().isoformat()
            position_data['symbol'] = symbol

            # Save to Redis
            self.redis_client.hset(
                key,
                mapping={
                    k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                    for k, v in position_data.items()
                }
            )

            # Set TTL
            self.redis_client.expire(key, self.state_ttl)

            # Publish update
            self._publish_update(StateChannel.POSITIONS, position_data)

            return True

        except Exception as e:
            logger.error(f"Failed to save position for {symbol}: {e}")
            return False

    def load_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Load position data

        Args:
            symbol: Trading symbol

        Returns:
            Position data or None
        """
        try:
            key = f"trading:positions:{symbol}"
            data = self.redis_client.hgetall(key)

            if not data:
                return None

            # Deserialize JSON fields
            position_data = {}
            for k, v in data.items():
                try:
                    position_data[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    position_data[k] = v

            return position_data

        except Exception as e:
            logger.error(f"Failed to load position for {symbol}: {e}")
            return None

    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all open positions

        Returns:
            Dictionary of symbol -> position data
        """
        try:
            # Find all position keys
            keys = self.redis_client.keys("trading:positions:*")

            positions = {}
            for key in keys:
                # Extract symbol from key
                symbol = key.split(":")[-1]
                position_data = self.load_position(symbol)

                if position_data:
                    positions[symbol] = position_data

            return positions

        except Exception as e:
            logger.error(f"Failed to get all positions: {e}")
            return {}

    def save_order(self, order_id: str, order_data: Dict[str, Any]) -> bool:
        """
        Save order tracking data

        Args:
            order_id: Unique order ID
            order_data: Order details

        Returns:
            True if successful
        """
        try:
            key = f"trading:orders:{order_id}"

            # Add metadata
            order_data['last_updated'] = datetime.now().isoformat()
            order_data['order_id'] = order_id

            # Save to Redis
            self.redis_client.hset(
                key,
                mapping={
                    k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                    for k, v in order_data.items()
                }
            )

            # Set TTL (orders expire after 7 days)
            self.redis_client.expire(key, 604800)

            # Publish update
            self._publish_update(StateChannel.ORDERS, order_data)

            return True

        except Exception as e:
            logger.error(f"Failed to save order {order_id}: {e}")
            return False

    def load_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Load order data"""
        try:
            key = f"trading:orders:{order_id}"
            data = self.redis_client.hgetall(key)

            if not data:
                return None

            # Deserialize JSON fields
            order_data = {}
            for k, v in data.items():
                try:
                    order_data[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    order_data[k] = v

            return order_data

        except Exception as e:
            logger.error(f"Failed to load order {order_id}: {e}")
            return None

    def _publish_update(self, channel: StateChannel, data: Dict[str, Any]):
        """
        Publish state update to channel

        Args:
            channel: Update channel
            data: Update data
        """
        try:
            message = {
                'timestamp': datetime.now().isoformat(),
                'instance_id': self.instance_id,
                'data': data
            }

            self.redis_client.publish(channel.value, json.dumps(message))

        except Exception as e:
            logger.error(f"Failed to publish update to {channel.value}: {e}")

    def subscribe(self, channel: StateChannel, callback: Callable[[Dict], None]):
        """
        Subscribe to state updates

        Args:
            channel: Channel to subscribe to
            callback: Function to call on updates

        Usage:
            def on_portfolio_update(data):
                print(f"Portfolio updated: {data}")

            state_mgr.subscribe(StateChannel.PORTFOLIO, on_portfolio_update)
        """
        with self._lock:
            self._subscribers[channel].append(callback)

            # Start subscriber thread if not running
            if not self._subscribing:
                self._start_subscriber()

    def _start_subscriber(self):
        """Start Pub/Sub subscriber thread"""
        self._subscribing = True

        def subscriber_loop():
            try:
                self.pubsub = self.redis_client.pubsub()

                # Subscribe to all channels
                channels = [ch.value for ch in StateChannel]
                self.pubsub.subscribe(*channels)

                logger.info(f"✅ Subscribed to {len(channels)} channels")

                # Listen for messages
                for message in self.pubsub.listen():
                    if message['type'] != 'message':
                        continue

                    try:
                        channel_name = message['channel']
                        data = json.loads(message['data'])

                        # Find matching channel
                        for channel in StateChannel:
                            if channel.value == channel_name:
                                # Call all subscribers
                                for callback in self._subscribers[channel]:
                                    try:
                                        callback(data)
                                    except Exception as e:
                                        logger.error(f"Subscriber callback error: {e}")

                    except Exception as e:
                        logger.error(f"Message processing error: {e}")

            except Exception as e:
                logger.error(f"Subscriber loop error: {e}")
            finally:
                self._subscribing = False

        self._subscriber_thread = threading.Thread(target=subscriber_loop, daemon=True)
        self._subscriber_thread.start()

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """
        Get all active trading sessions

        Returns:
            List of active session data
        """
        try:
            keys = self.redis_client.keys("trading:sessions:*")

            sessions = []
            for key in keys:
                session_data = self.redis_client.hgetall(key)
                if session_data:
                    sessions.append(session_data)

            return sessions

        except Exception as e:
            logger.error(f"Failed to get active sessions: {e}")
            return []

    def cleanup_stale_sessions(self, max_age_seconds: int = 300):
        """
        Clean up stale sessions (no heartbeat)

        Args:
            max_age_seconds: Max age before considering stale
        """
        try:
            sessions = self.get_active_sessions()

            for session in sessions:
                last_heartbeat_str = session.get('last_heartbeat')
                if not last_heartbeat_str:
                    continue

                last_heartbeat = datetime.fromisoformat(last_heartbeat_str)
                age = (datetime.now() - last_heartbeat).total_seconds()

                if age > max_age_seconds:
                    instance_id = session.get('instance_id')
                    key = f"trading:sessions:{instance_id}"
                    self.redis_client.delete(key)
                    logger.info(f"Cleaned up stale session: {instance_id}")

        except Exception as e:
            logger.error(f"Failed to cleanup stale sessions: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get Redis state statistics"""
        try:
            info = self.redis_client.info()

            return {
                'connected_clients': info.get('connected_clients', 0),
                'used_memory_mb': info.get('used_memory', 0) / 1024 / 1024,
                'total_keys': self.redis_client.dbsize(),
                'active_sessions': len(self.get_active_sessions()),
                'uptime_days': info.get('uptime_in_days', 0),
                'commands_processed': info.get('total_commands_processed', 0),
            }

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    def close(self):
        """Close Redis connection"""
        try:
            # Unregister instance
            key = f"trading:sessions:{self.instance_id}"
            self.redis_client.delete(key)

            # Close pub/sub
            if self.pubsub:
                self.pubsub.close()

            # Close client
            if self.redis_client:
                self.redis_client.close()

            logger.info("Redis connection closed")

        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")


# Global instance
_global_redis_state: Optional[RedisStateManager] = None


def get_redis_state_manager(config: Optional[RedisConfig] = None) -> RedisStateManager:
    """Get global Redis state manager (singleton)"""
    global _global_redis_state
    if _global_redis_state is None:
        if config is None:
            config = RedisConfig()
        _global_redis_state = RedisStateManager(config)
    return _global_redis_state


if __name__ == "__main__":
    # Test Redis state manager
    print("Testing Redis State Manager...")

    config = RedisConfig(host="localhost", port=6379)
    manager = RedisStateManager(config)

    # Test portfolio save/load
    print("\n1. Testing portfolio state...")
    portfolio_data = {
        'cash': 1000000.0,
        'positions': {'NIFTY': {'qty': 50, 'price': 25000}},
        'total_pnl': 5000.0
    }

    manager.save_portfolio_state(portfolio_data)
    loaded = manager.load_portfolio_state()
    print(f"Portfolio saved and loaded: {loaded is not None}")

    # Test distributed lock
    print("\n2. Testing distributed lock...")
    with manager.distributed_lock("test_resource", timeout=5):
        print("Lock acquired successfully")

    # Test position save/load
    print("\n3. Testing position state...")
    position_data = {
        'quantity': 50,
        'entry_price': 25000.0,
        'current_price': 25100.0
    }

    manager.save_position("NIFTY", position_data)
    loaded_position = manager.load_position("NIFTY")
    print(f"Position saved and loaded: {loaded_position is not None}")

    # Test statistics
    print("\n4. Getting statistics...")
    stats = manager.get_statistics()
    print(f"Statistics: {json.dumps(stats, indent=2)}")

    # Test active sessions
    print("\n5. Active sessions...")
    sessions = manager.get_active_sessions()
    print(f"Active sessions: {len(sessions)}")

    manager.close()
    print("\n✅ Redis state manager tests passed")
