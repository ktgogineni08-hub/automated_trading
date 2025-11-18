#!/usr/bin/env python3
"""
Comprehensive tests for security_context.py module
Tests SecurityContext coordination of KYC, AML, and data protection
"""

import pytest
import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock dependencies before importing
mock_aml_module = MagicMock()
mock_aml_transaction_class = MagicMock()
mock_aml_module.AMLTransaction = mock_aml_transaction_class
mock_aml_module.AMLMonitor = MagicMock

sys.modules['aml_monitor'] = mock_aml_module
sys.modules['client_data_protection'] = MagicMock()
sys.modules['kyc_manager'] = MagicMock()

from core.security_context import SecurityContext


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_kyc_manager():
    """Mock KYCManager"""
    mock = MagicMock()
    mock.check_kyc_compliance.return_value = (True, "Compliant")
    return mock


@pytest.fixture
def mock_aml_monitor():
    """Mock AMLMonitor"""
    mock = MagicMock()
    mock.get_client_risk_score.return_value = 50.0
    return mock


@pytest.fixture
def mock_data_protection():
    """Mock ClientDataProtection"""
    mock = MagicMock()
    return mock


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing"""
    kyc_dir = tempfile.mkdtemp()
    aml_dir = tempfile.mkdtemp()
    protected_data_dir = tempfile.mkdtemp()

    yield {
        'kyc_data_dir': kyc_dir,
        'aml_data_dir': aml_dir,
        'protected_data_dir': protected_data_dir
    }

    # Cleanup
    import shutil
    shutil.rmtree(kyc_dir, ignore_errors=True)
    shutil.rmtree(aml_dir, ignore_errors=True)
    shutil.rmtree(protected_data_dir, ignore_errors=True)


@pytest.fixture
def security_context(mock_kyc_manager, mock_aml_monitor, mock_data_protection, temp_dirs):
    """Create SecurityContext with mocked dependencies"""
    with patch('core.security_context.KYCManager', return_value=mock_kyc_manager):
        with patch('core.security_context.AMLMonitor', return_value=mock_aml_monitor):
            with patch('core.security_context.ClientDataProtection', return_value=mock_data_protection):
                config = {
                    'client_id': 'TEST_CLIENT',
                    'require_kyc': True,
                    'enforce_aml': True,
                    'aml_alert_threshold': 75.0,
                    **temp_dirs
                }
                ctx = SecurityContext(config=config)
                ctx.kyc_manager = mock_kyc_manager
                ctx.aml_monitor = mock_aml_monitor
                ctx.data_protection = mock_data_protection
                return ctx


# ============================================================================
# Initialization Tests
# ============================================================================

class TestInitialization:
    """Test SecurityContext initialization"""

    def test_initialization_default_config(self, mock_kyc_manager, mock_aml_monitor, mock_data_protection):
        """Test initialization with default configuration"""
        with patch('core.security_context.KYCManager', return_value=mock_kyc_manager):
            with patch('core.security_context.AMLMonitor', return_value=mock_aml_monitor):
                with patch('core.security_context.ClientDataProtection', return_value=mock_data_protection):
                    ctx = SecurityContext()

                    assert ctx.require_kyc is True
                    assert ctx.enforce_aml is True
                    assert ctx.aml_alert_threshold == 75

    def test_initialization_custom_config(self, mock_kyc_manager, mock_aml_monitor, mock_data_protection, temp_dirs):
        """Test initialization with custom configuration"""
        with patch('core.security_context.KYCManager', return_value=mock_kyc_manager):
            with patch('core.security_context.AMLMonitor', return_value=mock_aml_monitor):
                with patch('core.security_context.ClientDataProtection', return_value=mock_data_protection):
                    config = {
                        'client_id': 'CUSTOM_CLIENT',
                        'require_kyc': False,
                        'enforce_aml': False,
                        'aml_alert_threshold': 85.0,
                        **temp_dirs
                    }
                    ctx = SecurityContext(config=config)

                    assert ctx.client_id == 'CUSTOM_CLIENT'
                    assert ctx.require_kyc is False
                    assert ctx.enforce_aml is False
                    assert ctx.aml_alert_threshold == 85.0

    def test_initialization_client_id_from_env(self, mock_kyc_manager, mock_aml_monitor, mock_data_protection):
        """Test client ID fallback to environment variable"""
        with patch.dict(os.environ, {'TRADING_CLIENT_ID': 'ENV_CLIENT'}):
            with patch('core.security_context.KYCManager', return_value=mock_kyc_manager):
                with patch('core.security_context.AMLMonitor', return_value=mock_aml_monitor):
                    with patch('core.security_context.ClientDataProtection', return_value=mock_data_protection):
                        ctx = SecurityContext(config={})

                        assert ctx.client_id == 'ENV_CLIENT'

    def test_initialization_creates_directories(self, mock_kyc_manager, mock_aml_monitor, mock_data_protection):
        """Test that initialization creates required directories"""
        temp_base = tempfile.mkdtemp()

        config = {
            'kyc_data_dir': os.path.join(temp_base, 'kyc'),
            'aml_data_dir': os.path.join(temp_base, 'aml'),
            'protected_data_dir': os.path.join(temp_base, 'protected')
        }

        with patch('core.security_context.KYCManager', return_value=mock_kyc_manager):
            with patch('core.security_context.AMLMonitor', return_value=mock_aml_monitor):
                with patch('core.security_context.ClientDataProtection', return_value=mock_data_protection):
                    ctx = SecurityContext(config=config)

                    assert os.path.exists(config['kyc_data_dir'])
                    assert os.path.exists(config['aml_data_dir'])
                    assert os.path.exists(config['protected_data_dir'])

        # Cleanup
        import shutil
        shutil.rmtree(temp_base, ignore_errors=True)


# ============================================================================
# Encryption Key Resolution Tests
# ============================================================================

class TestEncryptionKeyResolution:
    """Test encryption key resolution logic"""

    def test_encryption_key_from_config_string(self, mock_kyc_manager, mock_aml_monitor):
        """Test encryption key from config (string)"""
        config = {'data_encryption_key': 'test_key_string'}

        with patch('core.security_context.KYCManager', return_value=mock_kyc_manager):
            with patch('core.security_context.AMLMonitor', return_value=mock_aml_monitor):
                with patch('core.security_context.ClientDataProtection') as mock_cdp:
                    ctx = SecurityContext(config=config)

                    # Verify ClientDataProtection was initialized
                    assert mock_cdp.called

    def test_encryption_key_from_config_bytes(self, mock_kyc_manager, mock_aml_monitor):
        """Test encryption key from config (bytes)"""
        config = {'data_encryption_key': b'test_key_bytes'}

        with patch('core.security_context.KYCManager', return_value=mock_kyc_manager):
            with patch('core.security_context.AMLMonitor', return_value=mock_aml_monitor):
                with patch('core.security_context.ClientDataProtection') as mock_cdp:
                    ctx = SecurityContext(config=config)

                    # Verify ClientDataProtection was initialized
                    assert mock_cdp.called

    def test_encryption_key_from_custom_env(self, mock_kyc_manager, mock_aml_monitor):
        """Test encryption key from custom environment variable"""
        config = {'data_encryption_env': 'CUSTOM_KEY_VAR'}

        with patch.dict(os.environ, {'CUSTOM_KEY_VAR': 'custom_env_key'}):
            with patch('core.security_context.KYCManager', return_value=mock_kyc_manager):
                with patch('core.security_context.AMLMonitor', return_value=mock_aml_monitor):
                    with patch('core.security_context.ClientDataProtection') as mock_cdp:
                        ctx = SecurityContext(config=config)

                        # Verify ClientDataProtection was initialized
                        assert mock_cdp.called

    def test_encryption_key_from_default_env(self, mock_kyc_manager, mock_aml_monitor):
        """Test encryption key from default environment variable"""
        with patch.dict(os.environ, {'DATA_ENCRYPTION_KEY': 'default_env_key'}):
            with patch('core.security_context.KYCManager', return_value=mock_kyc_manager):
                with patch('core.security_context.AMLMonitor', return_value=mock_aml_monitor):
                    with patch('core.security_context.ClientDataProtection') as mock_cdp:
                        ctx = SecurityContext(config={})

                        # Verify ClientDataProtection was initialized
                        assert mock_cdp.called

    def test_encryption_key_none_generates_warning(self, mock_kyc_manager, mock_aml_monitor, mock_data_protection):
        """Test that missing encryption key generates warning"""
        with patch.dict(os.environ, {}, clear=True):
            with patch('core.security_context.KYCManager', return_value=mock_kyc_manager):
                with patch('core.security_context.AMLMonitor', return_value=mock_aml_monitor):
                    with patch('core.security_context.ClientDataProtection', return_value=mock_data_protection):
                        with patch('core.security_context.logger') as mock_logger:
                            ctx = SecurityContext(config={})

                            # Should have logged a warning
                            mock_logger.warning.assert_called_once()
                            assert 'ephemeral key' in str(mock_logger.warning.call_args[0][0])


# ============================================================================
# KYC Authorization Tests
# ============================================================================

class TestKYCAuthorization:
    """Test KYC authorization checks"""

    def test_ensure_client_authorized_success(self, security_context):
        """Test authorized client passes check"""
        security_context.kyc_manager.check_kyc_compliance.return_value = (True, "Compliant")

        # Should not raise
        security_context.ensure_client_authorized()

    def test_ensure_client_authorized_failure(self, security_context):
        """Test unauthorized client raises PermissionError"""
        security_context.kyc_manager.check_kyc_compliance.return_value = (False, "Document expired")

        with pytest.raises(PermissionError) as exc_info:
            security_context.ensure_client_authorized()

        assert "KYC compliance failed" in str(exc_info.value)
        assert "Document expired" in str(exc_info.value)

    def test_ensure_client_authorized_kyc_disabled(self, security_context):
        """Test authorization check skipped when KYC disabled"""
        security_context.require_kyc = False
        security_context.kyc_manager.check_kyc_compliance.return_value = (False, "Should not check")

        # Should not raise even though KYC would fail
        security_context.ensure_client_authorized()

        # Should not have called check_kyc_compliance
        security_context.kyc_manager.check_kyc_compliance.assert_not_called()


# ============================================================================
# AML Recording Tests
# ============================================================================

class TestAMLRecording:
    """Test AML trade recording"""

    def test_record_trade_for_aml_basic(self, security_context):
        """Test recording basic trade for AML"""
        trade = {
            'price': 100.0,
            'shares': 10,
            'symbol': 'RELIANCE',
            'side': 'buy',
            'timestamp': datetime(2025, 1, 1, 10, 0, 0)
        }

        security_context.record_trade_for_aml(trade)

        security_context.aml_monitor.record_transaction.assert_called_once()

    def test_record_trade_for_aml_with_all_fields(self, security_context):
        """Test recording trade with all fields"""
        trade = {
            'price': 250.50,
            'shares': 20,
            'symbol': 'TCS',
            'side': 'sell',
            'counterparty': 'Exchange',
            'timestamp': datetime(2025, 1, 1, 12, 0, 0)
        }

        security_context.record_trade_for_aml(trade)

        # Verify transaction was recorded
        security_context.aml_monitor.record_transaction.assert_called_once()

    def test_record_trade_for_aml_timestamp_datetime(self, security_context):
        """Test AML recording with datetime timestamp"""
        now = datetime(2025, 1, 1, 12, 0, 0)
        trade = {
            'price': 100.0,
            'shares': 5,
            'timestamp': now
        }

        security_context.record_trade_for_aml(trade)

        # Verify transaction was recorded
        security_context.aml_monitor.record_transaction.assert_called_once()

    def test_record_trade_for_aml_timestamp_string(self, security_context):
        """Test AML recording with string timestamp"""
        trade = {
            'price': 100.0,
            'shares': 5,
            'timestamp': '2025-01-01T12:00:00'
        }

        security_context.record_trade_for_aml(trade)

        # Verify transaction was recorded
        security_context.aml_monitor.record_transaction.assert_called_once()

    def test_record_trade_for_aml_high_risk_score_logs_error(self, security_context):
        """Test that high risk score logs error"""
        security_context.aml_monitor.get_client_risk_score.return_value = 80.0
        security_context.aml_alert_threshold = 75.0

        trade = {'price': 100.0, 'shares': 10}

        with patch('core.security_context.logger') as mock_logger:
            security_context.record_trade_for_aml(trade)

            # Should log error
            mock_logger.error.assert_called_once()
            assert 'AML risk score' in str(mock_logger.error.call_args[0][0])

    def test_record_trade_for_aml_approaching_threshold_logs_warning(self, security_context):
        """Test that approaching threshold logs warning"""
        security_context.aml_alert_threshold = 100.0
        security_context.aml_monitor.get_client_risk_score.return_value = 85.0  # 85% of 100

        trade = {'price': 100.0, 'shares': 10}

        with patch('core.security_context.logger') as mock_logger:
            security_context.record_trade_for_aml(trade)

            # Should log warning
            mock_logger.warning.assert_called_once()
            assert 'approaching threshold' in str(mock_logger.warning.call_args[0][0])

    def test_record_trade_for_aml_disabled(self, security_context):
        """Test AML recording skipped when disabled"""
        security_context.enforce_aml = False

        trade = {'price': 100.0, 'shares': 10}

        security_context.record_trade_for_aml(trade)

        # Should not have recorded transaction
        security_context.aml_monitor.record_transaction.assert_not_called()

    def test_record_trade_for_aml_negative_values(self, security_context):
        """Test AML recording with negative values (uses abs)"""
        trade = {
            'price': -100.0,  # Negative price
            'shares': -10     # Negative shares
        }

        security_context.record_trade_for_aml(trade)

        # Verify transaction was recorded (abs values used internally)
        security_context.aml_monitor.record_transaction.assert_called_once()


# ============================================================================
# Data Logging Tests
# ============================================================================

class TestDataLogging:
    """Test data access logging"""

    def test_log_state_access_success(self, security_context):
        """Test successful state access logging"""
        security_context.log_state_access('read', 'portfolio_001')

        security_context.data_protection.log_data_access.assert_called_once_with(
            user_id='TEST_CLIENT',
            action='read',
            data_type='portfolio',
            record_id='portfolio_001',
            purpose='state_persistence'
        )

    def test_log_state_access_default_record_id(self, security_context):
        """Test state access logging with default record ID"""
        security_context.log_state_access('write')

        call_kwargs = security_context.data_protection.log_data_access.call_args[1]
        assert call_kwargs['record_id'] == 'trading_state'

    def test_log_state_access_handles_exception(self, security_context):
        """Test that logging exceptions are handled gracefully"""
        security_context.data_protection.log_data_access.side_effect = Exception("Logging failed")

        # Should not raise exception
        security_context.log_state_access('read')


# ============================================================================
# State Encryption Settings Tests
# ============================================================================

class TestStateEncryptionSettings:
    """Test state encryption settings"""

    def test_get_state_encryption_settings_empty(self, security_context):
        """Test getting empty state encryption settings"""
        security_context.state_encryption_config = {}

        settings = security_context.get_state_encryption_settings()

        assert settings == {}

    def test_get_state_encryption_settings_with_config(self, mock_kyc_manager, mock_aml_monitor, mock_data_protection):
        """Test getting state encryption settings from config"""
        config = {
            'state_encryption': {
                'algorithm': 'AES-256',
                'mode': 'GCM'
            }
        }

        with patch('core.security_context.KYCManager', return_value=mock_kyc_manager):
            with patch('core.security_context.AMLMonitor', return_value=mock_aml_monitor):
                with patch('core.security_context.ClientDataProtection', return_value=mock_data_protection):
                    ctx = SecurityContext(config=config)

                    settings = ctx.get_state_encryption_settings()

                    assert settings == {'algorithm': 'AES-256', 'mode': 'GCM'}

    def test_get_state_encryption_settings_returns_copy(self, mock_kyc_manager, mock_aml_monitor, mock_data_protection):
        """Test that settings returns a copy, not reference"""
        config = {
            'state_encryption': {'key': 'value'}
        }

        with patch('core.security_context.KYCManager', return_value=mock_kyc_manager):
            with patch('core.security_context.AMLMonitor', return_value=mock_aml_monitor):
                with patch('core.security_context.ClientDataProtection', return_value=mock_data_protection):
                    ctx = SecurityContext(config=config)

                    settings1 = ctx.get_state_encryption_settings()
                    settings1['new_key'] = 'new_value'

                    settings2 = ctx.get_state_encryption_settings()

                    # Modifying settings1 should not affect settings2
                    assert 'new_key' not in settings2


if __name__ == "__main__":
    # Run tests with: pytest test_security_context.py -v
    pytest.main([__file__, "-v", "--tb=short"])
