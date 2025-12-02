#!/usr/bin/env python3
"""
Comprehensive tests for health_server.py module
Tests HealthCheckHandler for Kubernetes health probes
"""

import pytest
import json
import io
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from http.server import HTTPServer
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.health_server import HealthCheckHandler


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_health_check():
    """Mock health_check_system module"""
    from datetime import datetime
    with patch('core.health_server.health_check_system') as mock:
        # Mock detailed_health method
        mock.detailed_health.return_value = {
            'status': 'healthy',
            'checks': {
                'database': {'status': 'ok'},
                'cache': {'status': 'ok'}
            }
        }
        # Mock liveness_probe method
        mock.liveness_probe.return_value = (True, {'status': 'alive'})

        # Mock readiness_probe method
        mock.readiness_probe.return_value = (True, {
            'status': 'ready',
            'checks': {
                'database': {'status': 'ok'},
                'cache': {'status': 'ok'}
            }
        })

        # Mock startup_time for version endpoint
        mock.startup_time = datetime(2025, 1, 1, 10, 0, 0)

        yield mock


@pytest.fixture
def handler():
    """Create HealthCheckHandler instance"""
    # Create mock request, client address, and server
    request = Mock()
    request.makefile = Mock(side_effect=lambda mode, bufsize=-1: io.BytesIO())
    client_address = ('127.0.0.1', 12345)
    server = Mock(spec=HTTPServer)

    handler = HealthCheckHandler(request, client_address, server)
    handler.wfile = io.BytesIO()
    handler.rfile = io.BytesIO()

    return handler


# ============================================================================
# Health Endpoint Tests
# ============================================================================

class TestHealthEndpoint:
    """Test /health endpoint"""

    def test_health_endpoint_healthy(self, handler, mock_health_check):
        """Test /health returns healthy status"""
        handler.path = '/health'

        with patch.object(handler, 'send_response') as mock_send:
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        mock_send.assert_called_once_with(200)
        mock_health_check.detailed_health.assert_called_once()

    def test_health_endpoint_unhealthy(self, handler):
        """Test /health returns unhealthy status"""
        with patch('core.health_server.health_check_system') as mock_check:
            mock_check.detailed_health.return_value = {
                'status': 'unhealthy',
                'checks': {
                    'database': {'status': 'error', 'message': 'Connection failed'}
                }
            }

            handler.path = '/health'

            with patch.object(handler, 'send_response') as mock_send:
                with patch.object(handler, 'send_header'):
                    with patch.object(handler, 'end_headers'):
                        handler.do_GET()

            mock_send.assert_called_once_with(503)

    def test_health_endpoint_returns_json(self, handler, mock_health_check):
        """Test /health returns JSON response"""
        handler.path = '/health'
        handler.wfile = io.BytesIO()

        with patch.object(handler, 'send_response'):
            with patch.object(handler, 'send_header') as mock_header:
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        # Check Content-Type header was set to JSON
        calls = [str(call) for call in mock_header.call_args_list]
        assert any('application/json' in str(call) for call in calls)


# ============================================================================
# Liveness Endpoint Tests
# ============================================================================

class TestLivenessEndpoint:
    """Test /health/live endpoint"""

    def test_liveness_always_returns_200(self, handler):
        """Test /health/live always returns 200 (process alive)"""
        handler.path = '/health/live'

        with patch.object(handler, 'send_response') as mock_send:
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        mock_send.assert_called_once_with(200)

    def test_liveness_returns_alive_status(self, handler):
        """Test /health/live returns alive status"""
        handler.path = '/health/live'
        handler.wfile = io.BytesIO()

        with patch.object(handler, 'send_response'):
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        response_data = handler.wfile.getvalue()
        response_json = json.loads(response_data.decode('utf-8'))

        assert response_json['status'] == 'alive'

    def test_liveness_calls_liveness_probe(self, handler, mock_health_check):
        """Test /health/live calls liveness_probe method"""
        handler.path = '/health/live'

        with patch.object(handler, 'send_response'):
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        # Liveness should call liveness_probe (not detailed_health)
        mock_health_check.liveness_probe.assert_called_once()
        mock_health_check.detailed_health.assert_not_called()


# ============================================================================
# Readiness Endpoint Tests
# ============================================================================

class TestReadinessEndpoint:
    """Test /health/ready endpoint"""

    def test_readiness_ready_state(self, handler, mock_health_check):
        """Test /health/ready returns 200 when ready"""
        handler.path = '/health/ready'

        with patch.object(handler, 'send_response') as mock_send:
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        mock_send.assert_called_once_with(200)
        mock_health_check.readiness_probe.assert_called_once()

    def test_readiness_not_ready_state(self, handler):
        """Test /health/ready returns 503 when not ready"""
        with patch('core.health_server.health_check_system') as mock_check:
            # Return False for is_ready
            mock_check.readiness_probe.return_value = (False, {
                'status': 'not ready',
                'checks': {'database': {'status': 'error'}}
            })

            handler.path = '/health/ready'

            with patch.object(handler, 'send_response') as mock_send:
                with patch.object(handler, 'send_header'):
                    with patch.object(handler, 'end_headers'):
                        handler.do_GET()

            mock_send.assert_called_once_with(503)

    def test_readiness_returns_health_checks(self, handler, mock_health_check):
        """Test /health/ready returns health check details"""
        handler.path = '/health/ready'
        handler.wfile = io.BytesIO()

        with patch.object(handler, 'send_response'):
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        response_data = handler.wfile.getvalue()
        response_json = json.loads(response_data.decode('utf-8'))

        assert 'checks' in response_json
        assert 'database' in response_json['checks']
        assert 'cache' in response_json['checks']


# ============================================================================
# Ping Endpoint Tests
# ============================================================================

class TestPingEndpoint:
    """Test /ping endpoint"""

    def test_ping_returns_200(self, handler):
        """Test /ping returns 200"""
        handler.path = '/ping'

        with patch.object(handler, 'send_response') as mock_send:
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        mock_send.assert_called_once_with(200)

    def test_ping_returns_pong(self, handler):
        """Test /ping returns pong message"""
        handler.path = '/ping'
        handler.wfile = io.BytesIO()

        with patch.object(handler, 'send_response'):
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        response_data = handler.wfile.getvalue()
        response_json = json.loads(response_data.decode('utf-8'))

        assert response_json['status'] == 'pong'


# ============================================================================
# Version Endpoint Tests
# ============================================================================

class TestVersionEndpoint:
    """Test /version endpoint"""

    def test_version_returns_200(self, handler):
        """Test /version returns 200"""
        handler.path = '/version'

        with patch.object(handler, 'send_response') as mock_send:
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        mock_send.assert_called_once_with(200)

    def test_version_returns_version_info(self, handler, mock_health_check):
        """Test /version returns version information"""
        handler.path = '/version'
        handler.wfile = io.BytesIO()

        with patch.object(handler, 'send_response'):
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        response_data = handler.wfile.getvalue()
        response_json = json.loads(response_data.decode('utf-8'))

        assert 'version' in response_json
        assert 'build' in response_json
        assert 'timestamp' in response_json

    def test_version_has_expected_fields(self, handler, mock_health_check):
        """Test /version has all expected fields"""
        handler.path = '/version'
        handler.wfile = io.BytesIO()

        with patch.object(handler, 'send_response'):
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        response_data = handler.wfile.getvalue()
        response_json = json.loads(response_data.decode('utf-8'))

        assert response_json['version'] == '1.0.0'
        assert response_json['build'] == 'production'
        assert isinstance(response_json['timestamp'], str)


# ============================================================================
# 404 Not Found Tests
# ============================================================================

class TestNotFound:
    """Test 404 handling"""

    def test_unknown_path_returns_404(self, handler):
        """Test unknown path returns 404"""
        handler.path = '/unknown'

        with patch.object(handler, 'send_response') as mock_send:
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        mock_send.assert_called_once_with(404)

    def test_404_returns_error_message(self, handler):
        """Test 404 returns error message"""
        handler.path = '/nonexistent'
        handler.wfile = io.BytesIO()

        with patch.object(handler, 'send_response'):
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        response_data = handler.wfile.getvalue()
        response_json = json.loads(response_data.decode('utf-8'))

        assert response_json['error'] == 'Not found'
        assert 'available_endpoints' in response_json


# ============================================================================
# Helper Method Tests
# ============================================================================

class TestHelperMethods:
    """Test helper methods"""

    def test_send_json_response(self, handler):
        """Test send_json_response helper"""
        handler.wfile = io.BytesIO()
        data = {'test': 'value', 'number': 42}

        with patch.object(handler, 'send_response'):
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.send_json_response(200, data)

        response_data = handler.wfile.getvalue()
        response_json = json.loads(response_data.decode('utf-8'))

        assert response_json == data

    def test_send_json_response_sets_headers(self, handler):
        """Test send_json_response sets correct headers"""
        handler.wfile = io.BytesIO()

        with patch.object(handler, 'send_response') as mock_send:
            with patch.object(handler, 'send_header') as mock_header:
                with patch.object(handler, 'end_headers'):
                    handler.send_json_response(200, {'test': 'data'})

        mock_send.assert_called_once_with(200)
        # Check Content-Type header
        calls = [call[0] for call in mock_header.call_args_list]
        assert ('Content-Type', 'application/json') in calls

    def test_log_message_suppressed(self, handler):
        """Test log_message is suppressed (no console spam)"""
        # log_message should not actually log anything
        # We just verify it doesn't raise an error
        handler.log_message("format %s", "test")
        # No assertion needed - just verify it doesn't crash


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_health_check_exception_handling(self, handler):
        """Test graceful handling of health check exceptions"""
        with patch('core.health_server.health_check_system') as mock_check:
            mock_check.detailed_health.side_effect = Exception("Health check failed")

            handler.path = '/health'

            # Should raise exception (not handled in current implementation)
            with pytest.raises(Exception):
                handler.do_GET()

    def test_path_with_query_params(self, handler):
        """Test path with query parameters"""
        handler.path = '/ping?test=value'

        with patch.object(handler, 'send_response') as mock_send:
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        # Should still match /ping endpoint
        mock_send.assert_called_once_with(200)

    def test_path_case_sensitivity(self, handler):
        """Test path case sensitivity"""
        handler.path = '/HEALTH'

        with patch.object(handler, 'send_response') as mock_send:
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        # Should not match (case-sensitive)
        mock_send.assert_called_once_with(404)

    def test_trailing_slash(self, handler, mock_health_check):
        """Test path with trailing slash"""
        handler.path = '/health/'

        with patch.object(handler, 'send_response') as mock_send:
            with patch.object(handler, 'send_header'):
                with patch.object(handler, 'end_headers'):
                    handler.do_GET()

        # Should not match (exact match required)
        mock_send.assert_called_once_with(404)


if __name__ == "__main__":
    # Run tests with: pytest test_health_server.py -v
    pytest.main([__file__, "-v", "--tb=short"])
