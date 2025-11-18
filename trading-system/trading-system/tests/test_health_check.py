#!/usr/bin/env python3
"""
Comprehensive tests for health_check.py module
Tests HealthCheckSystem for Kubernetes health probes
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from datetime import datetime, timedelta, timezone
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.health_check import (
    HealthStatus,
    ComponentHealth,
    HealthCheckSystem,
    check_database_connection,
    check_redis_connection,
    check_zerodha_api
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def health_system():
    """Create fresh HealthCheckSystem instance"""
    return HealthCheckSystem()


@pytest.fixture
def component():
    """Create ComponentHealth instance"""
    return ComponentHealth("test_component")


# ============================================================================
# ComponentHealth Tests
# ============================================================================

class TestComponentHealth:
    """Test ComponentHealth class"""

    def test_initialization(self, component):
        """Test ComponentHealth initialization"""
        assert component.name == "test_component"
        assert component.status == HealthStatus.HEALTHY
        assert component.message == ""
        assert component.last_check is None
        assert component.check_duration_ms == 0

    def test_to_dict(self, component):
        """Test ComponentHealth to_dict conversion"""
        component.status = HealthStatus.UNHEALTHY
        component.message = "Test error"
        component.last_check = datetime(2025, 1, 1, 10, 0, 0)
        component.check_duration_ms = 15.5

        result = component.to_dict()

        assert result['name'] == "test_component"
        assert result['status'] == "unhealthy"
        assert result['message'] == "Test error"
        assert result['last_check'] == "2025-01-01T10:00:00"
        assert result['check_duration_ms'] == 15.5

    def test_to_dict_no_last_check(self, component):
        """Test to_dict with None last_check"""
        result = component.to_dict()

        assert result['last_check'] is None


# ============================================================================
# HealthCheckSystem Initialization Tests
# ============================================================================

class TestHealthCheckSystemInitialization:
    """Test HealthCheckSystem initialization"""

    def test_initialization(self, health_system):
        """Test HealthCheckSystem initialization"""
        assert health_system.startup_time is not None
        assert health_system.component_checks == {}
        assert health_system.dependencies == {}

    def test_startup_time_is_recent(self, health_system):
        """Test that startup_time is recent"""
        time_diff = (datetime.now(timezone.utc) - health_system.startup_time).total_seconds()
        assert time_diff < 1  # Started within last second


# ============================================================================
# Dependency Registration Tests
# ============================================================================

class TestDependencyRegistration:
    """Test dependency registration"""

    def test_register_dependency(self, health_system):
        """Test registering a dependency"""
        check_func = Mock(return_value=(True, "OK"))

        health_system.register_dependency("database", check_func)

        assert "database" in health_system.dependencies
        assert health_system.dependencies["database"] == check_func
        assert "database" in health_system.component_checks
        assert health_system.component_checks["database"].name == "database"

    def test_register_multiple_dependencies(self, health_system):
        """Test registering multiple dependencies"""
        db_check = Mock(return_value=(True, "DB OK"))
        redis_check = Mock(return_value=(True, "Redis OK"))

        health_system.register_dependency("database", db_check)
        health_system.register_dependency("redis", redis_check)

        assert len(health_system.dependencies) == 2
        assert len(health_system.component_checks) == 2


# ============================================================================
# Liveness Probe Tests
# ============================================================================

class TestLivenessProbe:
    """Test liveness probe functionality"""

    @patch('core.health_check.psutil')
    def test_liveness_probe_healthy(self, mock_psutil, health_system):
        """Test liveness probe when system is healthy"""
        mock_psutil.cpu_percent.return_value = 50.0
        mock_memory = Mock()
        mock_memory.percent = 60.0
        mock_psutil.virtual_memory.return_value = mock_memory

        is_alive, data = health_system.liveness_probe()

        assert is_alive is True
        assert data['status'] == 'alive'
        assert 'uptime_seconds' in data
        assert data['memory_percent'] == 60.0
        assert data['cpu_percent'] == 50.0
        assert 'response_time_ms' in data
        assert 'timestamp' in data

    @patch('core.health_check.psutil')
    def test_liveness_probe_critical_memory(self, mock_psutil, health_system):
        """Test liveness probe with critical memory shortage"""
        mock_memory = Mock()
        mock_memory.percent = 96.0
        mock_psutil.virtual_memory.return_value = mock_memory

        is_alive, data = health_system.liveness_probe()

        assert is_alive is False
        assert data['status'] == 'unhealthy'
        assert data['reason'] == 'Critical memory shortage'
        assert data['memory_percent'] == 96.0

    @patch('core.health_check.psutil')
    def test_liveness_probe_psutil_exception(self, mock_psutil, health_system):
        """Test liveness probe when psutil raises exception"""
        mock_psutil.cpu_percent.side_effect = Exception("System error")

        is_alive, data = health_system.liveness_probe()

        assert is_alive is False
        assert data['status'] == 'unhealthy'
        assert 'Cannot access system resources' in data['reason']

    @patch('core.health_check.psutil')
    def test_liveness_probe_general_exception(self, mock_psutil, health_system):
        """Test liveness probe with unexpected exception"""
        mock_psutil.virtual_memory.side_effect = RuntimeError("Unexpected error")

        is_alive, data = health_system.liveness_probe()

        assert is_alive is False
        assert data['status'] == 'unhealthy'
        assert 'Cannot access system resources' in data['reason']


# ============================================================================
# Readiness Probe Tests
# ============================================================================

class TestReadinessProbe:
    """Test readiness probe functionality"""

    @patch('core.health_check.psutil')
    def test_readiness_probe_all_ready(self, mock_psutil, health_system):
        """Test readiness probe when all dependencies are ready"""
        # Mock psutil
        mock_memory = Mock()
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = Mock()
        mock_disk.percent = 60.0
        mock_psutil.disk_usage.return_value = mock_disk
        mock_psutil.cpu_percent.return_value = 40.0

        # Register healthy dependency
        db_check = Mock(return_value=(True, "Database OK"))
        health_system.register_dependency("database", db_check)

        is_ready, data = health_system.readiness_probe()

        assert is_ready is True
        assert data['status'] == 'ready'
        assert 'components' in data
        assert data['components']['database']['status'] == 'healthy'
        assert data['system']['memory_percent'] == 50.0
        assert data['system']['disk_percent'] == 60.0

    @patch('core.health_check.psutil')
    def test_readiness_probe_unhealthy_dependency(self, mock_psutil, health_system):
        """Test readiness probe with unhealthy dependency"""
        # Mock psutil
        mock_memory = Mock()
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = Mock()
        mock_disk.percent = 60.0
        mock_psutil.disk_usage.return_value = mock_disk
        mock_psutil.cpu_percent.return_value = 40.0

        # Register unhealthy dependency
        db_check = Mock(return_value=(False, "Connection failed"))
        health_system.register_dependency("database", db_check)

        is_ready, data = health_system.readiness_probe()

        assert is_ready is False
        assert data['status'] == 'not_ready'
        assert data['components']['database']['status'] == 'unhealthy'
        assert 'Connection failed' in data['components']['database']['message']

    @patch('core.health_check.psutil')
    def test_readiness_probe_dependency_exception(self, mock_psutil, health_system):
        """Test readiness probe when dependency check raises exception"""
        # Mock psutil
        mock_memory = Mock()
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = Mock()
        mock_disk.percent = 60.0
        mock_psutil.disk_usage.return_value = mock_disk

        # Register dependency that raises exception
        db_check = Mock(side_effect=Exception("Database error"))
        health_system.register_dependency("database", db_check)

        is_ready, data = health_system.readiness_probe()

        assert is_ready is False
        assert data['status'] == 'not_ready'
        assert 'Check error' in data['components']['database']['message']

    @patch('core.health_check.psutil')
    def test_readiness_probe_high_memory(self, mock_psutil, health_system):
        """Test readiness probe with high memory usage"""
        # Mock psutil
        mock_memory = Mock()
        mock_memory.percent = 92.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = Mock()
        mock_disk.percent = 60.0
        mock_psutil.disk_usage.return_value = mock_disk
        mock_psutil.cpu_percent.return_value = 40.0

        is_ready, data = health_system.readiness_probe()

        assert is_ready is False
        assert data['status'] == 'not_ready'
        assert 'memory' in data['components']
        assert data['components']['memory']['status'] == 'unhealthy'

    @patch('core.health_check.psutil')
    def test_readiness_probe_high_disk(self, mock_psutil, health_system):
        """Test readiness probe with high disk usage"""
        # Mock psutil
        mock_memory = Mock()
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = Mock()
        mock_disk.percent = 95.0
        mock_psutil.disk_usage.return_value = mock_disk
        mock_psutil.cpu_percent.return_value = 40.0

        is_ready, data = health_system.readiness_probe()

        assert is_ready is False
        assert data['status'] == 'not_ready'
        assert 'disk' in data['components']
        assert data['components']['disk']['status'] == 'unhealthy'

    @patch('core.health_check.psutil')
    def test_readiness_probe_exception(self, mock_psutil, health_system):
        """Test readiness probe with general exception"""
        mock_psutil.virtual_memory.side_effect = Exception("System error")

        is_ready, data = health_system.readiness_probe()

        assert is_ready is False
        assert data['status'] == 'not_ready'
        assert 'Readiness check failed' in data['reason']

    @patch('core.health_check.psutil')
    def test_readiness_probe_check_duration(self, mock_psutil, health_system):
        """Test that readiness probe records check duration"""
        # Mock psutil
        mock_memory = Mock()
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = Mock()
        mock_disk.percent = 60.0
        mock_psutil.disk_usage.return_value = mock_disk
        mock_psutil.cpu_percent.return_value = 40.0

        # Register dependency
        db_check = Mock(return_value=(True, "OK"))
        health_system.register_dependency("database", db_check)

        is_ready, data = health_system.readiness_probe()

        assert 'check_duration_ms' in data
        assert data['check_duration_ms'] >= 0
        assert data['components']['database']['check_duration_ms'] >= 0


# ============================================================================
# Detailed Health Tests
# ============================================================================

class TestDetailedHealth:
    """Test detailed health functionality"""

    @patch('core.health_check.psutil')
    def test_detailed_health_healthy(self, mock_psutil, health_system):
        """Test detailed health when system is healthy"""
        # Mock psutil for all calls
        mock_memory = Mock()
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = Mock()
        mock_disk.percent = 60.0
        mock_psutil.disk_usage.return_value = mock_disk
        mock_psutil.cpu_percent.return_value = 40.0

        # Register healthy dependency
        db_check = Mock(return_value=(True, "Database OK"))
        health_system.register_dependency("database", db_check)

        health_data = health_system.detailed_health()

        assert health_data['status'] == 'healthy'
        assert 'uptime_seconds' in health_data
        assert 'uptime_human' in health_data
        assert 'liveness' in health_data
        assert 'readiness' in health_data
        assert health_data['version'] == '1.0.0'
        assert health_data['environment'] == 'production'
        assert isinstance(health_data['warnings'], list)

    @patch('core.health_check.psutil')
    def test_detailed_health_degraded(self, mock_psutil, health_system):
        """Test detailed health when system is degraded"""
        # Mock psutil
        mock_memory = Mock()
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = Mock()
        mock_disk.percent = 60.0
        mock_psutil.disk_usage.return_value = mock_disk
        mock_psutil.cpu_percent.return_value = 40.0

        # Register unhealthy dependency (degrades readiness)
        db_check = Mock(return_value=(False, "Database down"))
        health_system.register_dependency("database", db_check)

        health_data = health_system.detailed_health()

        assert health_data['status'] == 'degraded'

    @patch('core.health_check.psutil')
    def test_detailed_health_warnings(self, mock_psutil, health_system):
        """Test detailed health warnings for high resource usage"""
        # Mock psutil with high resource usage
        mock_memory = Mock()
        mock_memory.percent = 85.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = Mock()
        mock_disk.percent = 85.0
        mock_psutil.disk_usage.return_value = mock_disk
        mock_psutil.cpu_percent.return_value = 40.0

        health_data = health_system.detailed_health()

        assert len(health_data['warnings']) >= 2
        assert any('memory' in w.lower() for w in health_data['warnings'])
        assert any('disk' in w.lower() for w in health_data['warnings'])


# ============================================================================
# Default Check Functions Tests
# ============================================================================

class TestDefaultCheckFunctions:
    """Test default dependency check functions"""

    def test_check_database_connection(self):
        """Test database connection check (placeholder)"""
        is_healthy, message = check_database_connection()

        assert is_healthy is True
        assert "OK" in message

    def test_check_redis_connection(self):
        """Test Redis connection check (placeholder)"""
        is_healthy, message = check_redis_connection()

        assert is_healthy is True
        assert "OK" in message

    def test_check_zerodha_api(self):
        """Test Zerodha API check (placeholder)"""
        is_healthy, message = check_zerodha_api()

        assert is_healthy is True
        assert "accessible" in message


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Test integration scenarios"""

    @patch('core.health_check.psutil')
    def test_full_health_check_workflow(self, mock_psutil, health_system):
        """Test complete health check workflow"""
        # Mock psutil
        mock_memory = Mock()
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = Mock()
        mock_disk.percent = 60.0
        mock_psutil.disk_usage.return_value = mock_disk
        mock_psutil.cpu_percent.return_value = 40.0

        # Register multiple dependencies
        db_check = Mock(return_value=(True, "Database OK"))
        redis_check = Mock(return_value=(True, "Redis OK"))
        api_check = Mock(return_value=(True, "API OK"))

        health_system.register_dependency("database", db_check)
        health_system.register_dependency("redis", redis_check)
        health_system.register_dependency("zerodha_api", api_check)

        # Run all checks
        is_alive, _ = health_system.liveness_probe()
        is_ready, readiness_data = health_system.readiness_probe()
        health_data = health_system.detailed_health()

        assert is_alive is True
        assert is_ready is True
        assert health_data['status'] == 'healthy'
        assert len(readiness_data['components']) == 3

    @patch('core.health_check.psutil')
    def test_mixed_health_states(self, mock_psutil, health_system):
        """Test system with mixed healthy/unhealthy components"""
        # Mock psutil
        mock_memory = Mock()
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = Mock()
        mock_disk.percent = 60.0
        mock_psutil.disk_usage.return_value = mock_disk
        mock_psutil.cpu_percent.return_value = 40.0

        # Register mixed dependencies
        db_check = Mock(return_value=(True, "Database OK"))
        redis_check = Mock(return_value=(False, "Redis connection failed"))

        health_system.register_dependency("database", db_check)
        health_system.register_dependency("redis", redis_check)

        is_ready, data = health_system.readiness_probe()

        assert is_ready is False
        assert data['components']['database']['status'] == 'healthy'
        assert data['components']['redis']['status'] == 'unhealthy'


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    @patch('core.health_check.psutil')
    def test_exactly_90_percent_memory(self, mock_psutil, health_system):
        """Test memory at exactly 90% threshold"""
        mock_memory = Mock()
        mock_memory.percent = 90.0
        mock_psutil.virtual_memory.return_value = mock_memory

        mock_disk = Mock()
        mock_disk.percent = 60.0
        mock_psutil.disk_usage.return_value = mock_disk
        mock_psutil.cpu_percent.return_value = 40.0

        is_ready, data = health_system.readiness_probe()

        # At exactly 90%, should not be considered critical (> 90)
        assert is_ready is True

    @patch('core.health_check.psutil')
    def test_exactly_95_percent_memory_liveness(self, mock_psutil, health_system):
        """Test liveness probe at exactly 95% memory"""
        mock_memory = Mock()
        mock_memory.percent = 95.0
        mock_psutil.virtual_memory.return_value = mock_memory

        is_alive, data = health_system.liveness_probe()

        # At exactly 95%, should still be alive (> 95 triggers failure)
        assert is_alive is True

    def test_no_dependencies_registered(self, health_system):
        """Test readiness probe with no dependencies"""
        with patch('core.health_check.psutil') as mock_psutil:
            mock_memory = Mock()
            mock_memory.percent = 50.0
            mock_psutil.virtual_memory.return_value = mock_memory

            mock_disk = Mock()
            mock_disk.percent = 60.0
            mock_psutil.disk_usage.return_value = mock_disk
            mock_psutil.cpu_percent.return_value = 40.0

            is_ready, data = health_system.readiness_probe()

            assert is_ready is True
            assert len(data['components']) == 0

    def test_component_check_duration_recorded(self, health_system):
        """Test that component check duration is properly recorded"""
        with patch('core.health_check.psutil') as mock_psutil:
            mock_memory = Mock()
            mock_memory.percent = 50.0
            mock_psutil.virtual_memory.return_value = mock_memory

            mock_disk = Mock()
            mock_disk.percent = 60.0
            mock_psutil.disk_usage.return_value = mock_disk
            mock_psutil.cpu_percent.return_value = 40.0

            # Register slow dependency
            def slow_check():
                time.sleep(0.01)  # 10ms delay
                return True, "OK"

            health_system.register_dependency("slow_service", slow_check)

            is_ready, data = health_system.readiness_probe()

            # Check duration should be at least 10ms
            assert data['components']['slow_service']['check_duration_ms'] >= 10


if __name__ == "__main__":
    # Run tests with: pytest test_health_check.py -v
    pytest.main([__file__, "-v", "--tb=short"])
