#!/usr/bin/env python3
"""Tests for connection_pool.py module"""

import pytest
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.connection_pool import (
    ConnectionStats,
    PooledConnection,
    ConnectionPool
)


class TestConnectionStats:
    """Test ConnectionStats"""

    def test_stats_initialization(self):
        stats = ConnectionStats()
        assert stats.created == 0
        assert stats.active == 0


class TestPooledConnection:
    """Test PooledConnection"""

    def test_pooled_connection_creation(self):
        conn = PooledConnection(connection="test_conn")
        assert conn.connection == "test_conn"
        assert conn.use_count == 0

    def test_mark_used(self):
        conn = PooledConnection(connection="test")
        conn.mark_used()
        assert conn.use_count == 1


class TestConnectionPool:
    """Test ConnectionPool"""

    def test_pool_initialization(self):
        def create(): return "connection"
        def close(c): pass
        
        pool = ConnectionPool(
            create_connection=create,
            close_connection=close,
            min_size=2,
            max_size=5
        )
        assert pool.min_size == 2
        assert pool.max_size == 5

    def test_pool_acquire_release(self):
        connections = []
        def create():
            conn = f"conn_{len(connections)}"
            connections.append(conn)
            return conn
        def close(c): pass
        
        pool = ConnectionPool(create, close, min_size=1, max_size=3)
        
        with pool.acquire() as conn:
            assert conn is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
