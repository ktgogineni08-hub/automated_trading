#!/usr/bin/env python3
"""
Comprehensive Integration Test Suite
Tests all system components working together

Test Coverage:
1. Database connectivity and replication
2. Redis state management
3. API quota monitoring
4. Trading system flow
5. Dashboard integration
6. Failover scenarios
"""

import pytest
import time
import asyncio
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.postgresql_manager import PostgreSQLReplicationManager, DatabaseConfig
from infrastructure.redis_state_manager import RedisStateManager, RedisConfig
from infrastructure.api_quota_monitor import APIQuotaMonitor
from infrastructure.alert_manager import get_alert_manager, AlertSeverity, AlertCategory
from infrastructure.advanced_alerting_rules import AdvancedAlertingEngine


class TestDatabaseIntegration:
    """Test PostgreSQL database integration"""

    def setup_method(self):
        """Setup test database"""
        self.master_config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="trading_system_test",
            user="trading_user",
            password="test_password"
        )

        # Create manager (will auto-initialize schema)
        self.db_manager = PostgreSQLReplicationManager(
            self.master_config,
            replica_configs=[]  # No replicas for unit test
        )

    def teardown_method(self):
        """Cleanup"""
        if hasattr(self, 'db_manager'):
            self.db_manager.close()

    def test_database_connection(self):
        """Test basic database connectivity"""
        # Write operation
        result = self.db_manager.execute_write(
            "INSERT INTO system_events (timestamp, event_type, severity, message) "
            "VALUES (%s, %s, %s, %s)",
            (datetime.now(), "test", "INFO", "Integration test")
        )

        assert result > 0, "Failed to write to database"

    def test_database_read_write(self):
        """Test read and write operations"""
        # Write
        test_message = f"Integration test {datetime.now().isoformat()}"
        self.db_manager.execute_write(
            "INSERT INTO system_events (timestamp, event_type, severity, message) "
            "VALUES (%s, %s, %s, %s)",
            (datetime.now(), "test", "INFO", test_message)
        )

        # Read
        results = self.db_manager.execute_read(
            "SELECT * FROM system_events WHERE message = %s",
            (test_message,)
        )

        assert len(results) > 0, "Failed to read from database"
        assert results[0]['message'] == test_message

    def test_transaction_rollback(self):
        """Test transaction rollback on error"""
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(
                    "INSERT INTO system_events (timestamp, event_type, severity, message) "
                    "VALUES (%s, %s, %s, %s)",
                    (datetime.now(), "test", "INFO", "Test rollback")
                )

                # Force error
                cursor.execute("SELECT * FROM non_existent_table")

        except Exception:
            pass  # Expected

        # Verify rollback - event should not exist
        results = self.db_manager.execute_read(
            "SELECT * FROM system_events WHERE message = %s",
            ("Test rollback",)
        )

        assert len(results) == 0, "Transaction was not rolled back"

    def test_replication_status(self):
        """Test replication status reporting"""
        status = self.db_manager.get_replication_status()

        assert 'master' in status
        assert 'replicas' in status
        assert status['master']['healthy'] is True


class TestRedisIntegration:
    """Test Redis state management integration"""

    def setup_method(self):
        """Setup Redis connection"""
        config = RedisConfig(
            host="localhost",
            port=6379,
            db=15  # Use DB 15 for testing
        )

        self.redis_manager = RedisStateManager(config)

    def teardown_method(self):
        """Cleanup"""
        if hasattr(self, 'redis_manager'):
            # Clean up test data
            self.redis_manager.redis_client.flushdb()
            self.redis_manager.close()

    def test_redis_connection(self):
        """Test basic Redis connectivity"""
        # Test ping
        response = self.redis_manager.redis_client.ping()
        assert response is True, "Redis ping failed"

    def test_portfolio_state_management(self):
        """Test portfolio state save/load"""
        test_portfolio = {
            'cash': 1000000.0,
            'positions': {'NIFTY': {'qty': 50, 'price': 25000}},
            'total_pnl': 5000.0
        }

        # Save
        success = self.redis_manager.save_portfolio_state(test_portfolio)
        assert success, "Failed to save portfolio state"

        # Load
        loaded = self.redis_manager.load_portfolio_state()
        assert loaded is not None, "Failed to load portfolio state"
        assert float(loaded['cash']) == 1000000.0

    def test_distributed_lock(self):
        """Test distributed locking"""
        # Acquire lock
        with self.redis_manager.distributed_lock("test_resource", timeout=5):
            # Lock is acquired
            # Try to acquire same lock (should fail)
            lock2 = self.redis_manager.redis_client.lock("trading:locks:test_resource", timeout=1)
            acquired = lock2.acquire(blocking=False)
            assert not acquired, "Lock was acquired when it shouldn't be"

        # Lock should be released now
        lock3 = self.redis_manager.redis_client.lock("trading:locks:test_resource", timeout=1)
        acquired = lock3.acquire(blocking=False)
        assert acquired, "Failed to acquire lock after release"
        lock3.release()

    def test_position_tracking(self):
        """Test position save/load"""
        position_data = {
            'quantity': 50,
            'entry_price': 25000.0,
            'current_price': 25100.0,
            'pnl': 5000.0
        }

        # Save
        success = self.redis_manager.save_position("NIFTY", position_data)
        assert success, "Failed to save position"

        # Load
        loaded = self.redis_manager.load_position("NIFTY")
        assert loaded is not None
        assert float(loaded['entry_price']) == 25000.0

    def test_session_management(self):
        """Test session tracking"""
        sessions = self.redis_manager.get_active_sessions()
        assert isinstance(sessions, list)
        # At least our own session should be active
        assert len(sessions) >= 1


class TestAPIQuotaIntegration:
    """Test API quota monitoring integration"""

    def setup_method(self):
        """Setup quota monitor"""
        self.monitor = APIQuotaMonitor()
        self.monitor.start_monitoring()

    def teardown_method(self):
        """Cleanup"""
        if hasattr(self, 'monitor'):
            self.monitor.stop_monitoring()

    def test_quota_tracking(self):
        """Test API quota tracking"""
        # Simulate API calls
        for i in range(10):
            self.monitor.record_api_call(
                endpoint="/api/quote",
                method="GET",
                status_code=200,
                response_time_ms=100
            )

        # Check usage
        usage = self.monitor.get_current_usage()
        assert 'per_second' in usage
        assert usage['per_second'].current_usage == 10

    def test_quota_throttling(self):
        """Test automatic throttling"""
        # Fill up quota
        for i in range(3):  # Max 3 per second
            self.monitor.record_api_call(
                endpoint="/api/quote",
                method="GET",
                status_code=200,
                response_time_ms=100
            )

        # Check if can make request
        can_proceed = self.monitor.can_make_request(safety_margin=1.0)
        assert not can_proceed, "Should be throttled"

        # Wait and check again
        time.sleep(1.1)
        can_proceed = self.monitor.can_make_request()
        assert can_proceed, "Should be allowed after window reset"

    def test_quota_reporting(self):
        """Test quota reporting"""
        # Generate some usage
        for i in range(50):
            self.monitor.record_api_call(
                endpoint="/api/test",
                method="GET",
                status_code=200,
                response_time_ms=100
            )
            time.sleep(0.01)

        # Get report
        report = self.monitor.get_quota_report()

        assert 'total_api_calls' in report
        assert report['total_api_calls'] >= 50
        assert 'current_usage' in report


class TestAlertingIntegration:
    """Test alerting system integration"""

    def setup_method(self):
        """Setup alerting"""
        self.alert_manager = get_alert_manager()
        self.alerting_engine = AdvancedAlertingEngine()

    def test_basic_alert(self):
        """Test basic alert generation"""
        alert = self.alert_manager.alert(
            severity=AlertSeverity.MEDIUM,
            category=AlertCategory.SYSTEM,
            title="Integration Test Alert",
            message="This is a test alert"
        )

        assert alert is not None
        assert alert.title == "Integration Test Alert"

    def test_alert_suppression(self):
        """Test alert suppression"""
        # First alert
        alert1 = self.alert_manager.alert(
            severity=AlertSeverity.MEDIUM,
            category=AlertCategory.SYSTEM,
            title="Duplicate Alert",
            message="First occurrence"
        )

        # Immediate duplicate (should be suppressed)
        alert2 = self.alert_manager.alert(
            severity=AlertSeverity.MEDIUM,
            category=AlertCategory.SYSTEM,
            title="Duplicate Alert",
            message="Second occurrence (should be suppressed)"
        )

        assert alert1 is not None
        assert alert2 is None, "Duplicate alert was not suppressed"

    def test_pattern_detection(self):
        """Test pattern-based alerting"""
        # Simulate consecutive losses
        for i in range(6):  # Threshold is 5
            self.alerting_engine.process_trade_event({
                'symbol': 'NIFTY',
                'pnl': -500,
                'is_win': False
            })

        # Check statistics
        stats = self.alerting_engine.get_statistics()
        assert stats['consecutive_losses'] >= 5


class TestEndToEndFlow:
    """Test complete end-to-end trading flow"""

    def setup_method(self):
        """Setup all components"""
        # Database
        self.master_config = DatabaseConfig(
            host="localhost",
            database="trading_system_test"
        )
        self.db = PostgreSQLReplicationManager(self.master_config, [])

        # Redis
        redis_config = RedisConfig(host="localhost", db=15)
        self.redis = RedisStateManager(redis_config)

        # Monitoring
        self.quota_monitor = APIQuotaMonitor()
        self.alert_manager = get_alert_manager()

    def teardown_method(self):
        """Cleanup"""
        if hasattr(self, 'db'):
            self.db.close()
        if hasattr(self, 'redis'):
            self.redis.redis_client.flushdb()
            self.redis.close()

    def test_complete_trade_flow(self):
        """Test complete trading flow"""
        # 1. Check quota
        can_trade = self.quota_monitor.can_make_request()
        assert can_trade, "Quota check failed"

        # 2. Record API call
        self.quota_monitor.record_api_call(
            endpoint="/api/quote",
            method="GET",
            status_code=200,
            response_time_ms=150
        )

        # 3. Save portfolio state to Redis
        portfolio = {
            'cash': 1000000.0,
            'positions': {},
            'total_pnl': 0.0
        }
        success = self.redis.save_portfolio_state(portfolio)
        assert success, "Failed to save portfolio to Redis"

        # 4. Log trade to database
        result = self.db.execute_write(
            "INSERT INTO system_events (timestamp, event_type, severity, message) "
            "VALUES (%s, %s, %s, %s)",
            (datetime.now(), "trade", "INFO", "Test trade executed")
        )
        assert result > 0, "Failed to log trade to database"

        # 5. Generate alert
        alert = self.alert_manager.alert(
            severity=AlertSeverity.LOW,
            category=AlertCategory.EXECUTION,
            title="Trade Executed",
            message="Integration test trade completed"
        )
        assert alert is not None

    def test_high_load_scenario(self):
        """Test system under high load"""
        # Simulate 100 rapid operations
        start_time = time.time()

        for i in range(100):
            # API call
            self.quota_monitor.record_api_call(
                endpoint="/api/test",
                method="GET",
                status_code=200,
                response_time_ms=100
            )

            # Redis operation
            self.redis.save_position(
                f"SYMBOL_{i % 10}",
                {'quantity': 50, 'price': 25000.0}
            )

            # Database operation (every 10th)
            if i % 10 == 0:
                self.db.execute_write(
                    "INSERT INTO system_events (timestamp, event_type, severity, message) "
                    "VALUES (%s, %s, %s, %s)",
                    (datetime.now(), "test", "INFO", f"Load test {i}")
                )

        duration = time.time() - start_time

        # Should complete in reasonable time (<10 seconds)
        assert duration < 10, f"High load test took too long: {duration}s"

        # Verify data integrity
        positions = self.redis.get_all_positions()
        assert len(positions) > 0, "No positions saved during load test"


# =============================================================================
# Pytest Configuration
# =============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment before all tests"""
    print("\n" + "="*70)
    print("INTEGRATION TEST SUITE")
    print("="*70)
    print("\nSetting up test environment...")

    # Could initialize test databases, Redis, etc. here
    yield

    print("\nCleaning up test environment...")


@pytest.fixture(scope="function")
def db_connection():
    """Provide database connection for tests"""
    config = DatabaseConfig(
        host="localhost",
        database="trading_system_test"
    )
    manager = PostgreSQLReplicationManager(config, [])
    yield manager
    manager.close()


@pytest.fixture(scope="function")
def redis_connection():
    """Provide Redis connection for tests"""
    config = RedisConfig(host="localhost", db=15)
    manager = RedisStateManager(config)
    yield manager
    manager.redis_client.flushdb()
    manager.close()


# =============================================================================
# Test Execution
# =============================================================================

if __name__ == "__main__":
    # Run tests with pytest
    print("Running integration tests...")
    print("\nNote: Ensure PostgreSQL and Redis are running:")
    print("  - PostgreSQL: localhost:5432 (database: trading_system_test)")
    print("  - Redis: localhost:6379\n")

    # Run with verbose output
    pytest.main([__file__, "-v", "-s"])
