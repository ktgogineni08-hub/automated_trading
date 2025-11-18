#!/usr/bin/env python3
"""
Integration Tests for Critical Fixes

Tests verify that all critical blockers have been fixed:
1. API Rate Limiter returns boolean
2. Price cache is initialized
3. Instruments bootstrap works
4. Dashboard security is enforced
5. State persistence throttling works
"""

import pytest
import os
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAPIRateLimiter:
    """Test API rate limiter fix"""

    def test_wait_returns_boolean(self):
        """Verify wait() returns bool instead of None"""
        from api_rate_limiter import APIRateLimiter

        limiter = APIRateLimiter(calls_per_second=10.0)

        # Should return True (not None!)
        result = limiter.wait('test_key')
        assert isinstance(result, bool), "wait() must return boolean"
        assert result is True, "wait() should return True on success"

    def test_wait_returns_false_on_underlying_timeout(self):
        """CRITICAL: Verify wait() returns False when underlying limiter times out"""
        from api_rate_limiter import APIRateLimiter

        limiter = APIRateLimiter(calls_per_second=1.0)

        # Mock the underlying limiter to return False
        with patch.object(limiter._limiter, 'wait', return_value=False):
            result = limiter.wait('test_key')
            # CRITICAL: Must return False, not True!
            assert result is False, "wait() must return False when underlying limiter times out!"

    def test_wait_propagates_underlying_result(self):
        """Verify wait() correctly propagates underlying limiter result"""
        from api_rate_limiter import APIRateLimiter

        limiter = APIRateLimiter(calls_per_second=1.0)

        # Test True case
        with patch.object(limiter._limiter, 'wait', return_value=True):
            assert limiter.wait('test') is True

        # Test False case
        with patch.object(limiter._limiter, 'wait', return_value=False):
            assert limiter.wait('test') is False, "CRITICAL: Must propagate False from underlying limiter!"

    def test_kite_wrapper_doesnt_raise_on_wait(self):
        """Verify KiteAPIWrapper doesn't raise TimeoutError on every call"""
        from api_rate_limiter import KiteAPIWrapper

        # Mock Kite instance
        mock_kite = Mock()
        mock_kite.quote = Mock(return_value={'NSE:SBIN': {'last_price': 500.0}})

        # Wrap with rate limiter
        wrapper = KiteAPIWrapper(mock_kite, calls_per_second=10.0)

        # This should NOT raise TimeoutError
        try:
            result = wrapper.quote(['NSE:SBIN'])
            assert result == {'NSE:SBIN': {'last_price': 500.0}}
        except TimeoutError:
            pytest.fail("KiteAPIWrapper raised TimeoutError - rate limiter is broken!")

    def test_kite_wrapper_raises_on_actual_timeout(self):
        """Verify KiteAPIWrapper raises TimeoutError when rate limit actually exceeded"""
        from api_rate_limiter import KiteAPIWrapper

        mock_kite = Mock()
        mock_kite.quote = Mock(return_value={'NSE:SBIN': {'last_price': 500.0}})

        wrapper = KiteAPIWrapper(mock_kite, calls_per_second=1.0)

        # Mock the limiter to return False (timeout)
        with patch.object(wrapper._limiter, 'wait', return_value=False):
            with pytest.raises(TimeoutError, match="Rate limit exceeded"):
                wrapper.quote(['NSE:SBIN'])


class TestPriceCache:
    """Test price cache initialization fix"""

    def test_price_cache_initialized(self):
        """Verify price_cache is initialized in UnifiedPortfolio"""
        from core.portfolio.portfolio import UnifiedPortfolio

        # Create portfolio
        portfolio = UnifiedPortfolio(
            initial_cash=100000,
            trading_mode='paper',
            silent=True
        )

        # Verify price_cache exists
        assert hasattr(portfolio, 'price_cache'), "price_cache attribute missing!"
        assert portfolio.price_cache is not None, "price_cache is None!"

        # Verify it has expected methods
        assert hasattr(portfolio.price_cache, 'get'), "price_cache.get() missing"
        assert hasattr(portfolio.price_cache, 'set'), "price_cache.set() missing"

    def test_price_cache_works(self):
        """Verify price cache can store and retrieve prices"""
        from core.portfolio.portfolio import UnifiedPortfolio

        portfolio = UnifiedPortfolio(
            initial_cash=100000,
            trading_mode='paper',
            silent=True
        )

        # Set a price
        portfolio.price_cache.set('SBIN', 500.75)

        # Retrieve it
        cached_price = portfolio.price_cache.get('SBIN')
        assert cached_price == 500.75, "Price cache not working!"

        # Check cache miss
        missing_price = portfolio.price_cache.get('NONEXISTENT')
        assert missing_price is None, "Cache should return None for miss"


class TestInstrumentsService:
    """Test instruments bootstrap fix"""

    def test_instruments_service_exists(self):
        """Verify InstrumentsService class exists"""
        from data.instruments_service import InstrumentsService

        # Should import successfully
        assert InstrumentsService is not None

    def test_instruments_service_can_use_cache(self):
        """Verify InstrumentsService can load from cache"""
        from data.instruments_service import InstrumentsService

        service = InstrumentsService(kite=None)  # No kite needed for cache

        # Should not crash even without Kite instance
        instruments = service.get_instruments_map('NSE')
        assert isinstance(instruments, dict)

    def test_bootstrap_instruments_function(self):
        """Verify bootstrap_instruments function exists in main.py"""
        # Import main module
        import main

        # Verify bootstrap_instruments function exists
        assert hasattr(main, 'bootstrap_instruments'), "bootstrap_instruments() missing from main.py!"

        # Verify it's callable
        assert callable(main.bootstrap_instruments), "bootstrap_instruments is not callable!"


class TestDashboardSecurity:
    """Test dashboard security fixes"""

    def test_dashboard_connector_requires_api_key(self):
        """Verify DashboardConnector requires API key (no fallback)"""
        from utilities.dashboard import DashboardConnector

        # Remove API key from environment
        old_key = os.environ.get('DASHBOARD_API_KEY')
        if 'DASHBOARD_API_KEY' in os.environ:
            del os.environ['DASHBOARD_API_KEY']

        try:
            # Should raise ValueError when no API key provided
            with pytest.raises(ValueError, match="DASHBOARD_API_KEY is required"):
                DashboardConnector()
        finally:
            # Restore old key
            if old_key:
                os.environ['DASHBOARD_API_KEY'] = old_key

    def test_dashboard_connector_accepts_explicit_key(self):
        """Verify DashboardConnector accepts explicit API key"""
        from utilities.dashboard import DashboardConnector

        # Should work with explicit key
        connector = DashboardConnector(api_key='test-key-12345')
        assert connector.api_key == 'test-key-12345'

    def test_tls_verification_enabled_by_default(self):
        """Verify TLS verification is ON by default"""
        from utilities.dashboard import DashboardConnector

        # Ensure DASHBOARD_DISABLE_TLS_VERIFY is not set
        old_value = os.environ.get('DASHBOARD_DISABLE_TLS_VERIFY')
        if 'DASHBOARD_DISABLE_TLS_VERIFY' in os.environ:
            del os.environ['DASHBOARD_DISABLE_TLS_VERIFY']

        try:
            connector = DashboardConnector(api_key='test-key')
            assert connector.session.verify is True, "TLS verification should be ON by default!"
        finally:
            if old_value:
                os.environ['DASHBOARD_DISABLE_TLS_VERIFY'] = old_value


class TestDashboardManager:
    """Test dashboard manager extraction"""

    def test_dashboard_manager_exists(self):
        """Verify DashboardManager class exists"""
        from infrastructure.dashboard_manager import DashboardManager

        manager = DashboardManager()
        assert manager is not None

    def test_dashboard_manager_validates_security(self):
        """Verify DashboardManager runs security validation"""
        from infrastructure.dashboard_manager import DashboardManager

        manager = DashboardManager()

        # Should have validation method
        assert hasattr(manager, 'validate_security_requirements')

        # Validation should return (bool, str)
        is_valid, error = manager.validate_security_requirements()
        assert isinstance(is_valid, bool)
        assert isinstance(error, str)


class TestConfigValidator:
    """Test configuration validator"""

    def test_config_validator_exists(self):
        """Verify ConfigurationValidator exists"""
        from infrastructure.config_validator import ConfigurationValidator

        validator = ConfigurationValidator(trading_mode='paper')
        assert validator is not None

    def test_config_validator_checks_env_vars(self):
        """Verify validator checks environment variables"""
        from infrastructure.config_validator import ConfigurationValidator

        validator = ConfigurationValidator(trading_mode='paper')
        is_valid, results = validator.validate_all()

        # Should have environment results
        env_results = [r for r in results if r.category == 'Environment']
        assert len(env_results) > 0, "Validator should check environment variables"

    def test_config_validator_fails_without_api_key(self):
        """Verify validator fails when DASHBOARD_API_KEY missing"""
        from infrastructure.config_validator import ConfigurationValidator

        # Remove API key
        old_key = os.environ.get('DASHBOARD_API_KEY')
        if 'DASHBOARD_API_KEY' in os.environ:
            del os.environ['DASHBOARD_API_KEY']

        try:
            validator = ConfigurationValidator(trading_mode='paper')
            is_valid, results = validator.validate_all()

            # Should have errors
            errors = [r for r in results if r.severity == 'error']
            assert len(errors) > 0, "Validator should report errors when API key missing"
            assert not is_valid, "Validation should fail without API key"
        finally:
            if old_key:
                os.environ['DASHBOARD_API_KEY'] = old_key

    def test_config_validator_checks_zerodha_credentials(self):
        """CRITICAL: Verify validator checks ZERODHA_API_KEY and ZERODHA_API_SECRET (not KITE_*)"""
        from infrastructure.config_validator import ConfigurationValidator

        # Save current env vars
        old_dashboard_key = os.environ.get('DASHBOARD_API_KEY')
        old_zerodha_key = os.environ.get('ZERODHA_API_KEY')
        old_zerodha_secret = os.environ.get('ZERODHA_API_SECRET')

        try:
            # Set dashboard key (required for all modes)
            os.environ['DASHBOARD_API_KEY'] = 'test-dashboard-key'

            # Remove Zerodha credentials
            for var in ['ZERODHA_API_KEY', 'ZERODHA_API_SECRET']:
                if var in os.environ:
                    del os.environ[var]

            # Validate in LIVE mode (requires Zerodha creds)
            validator = ConfigurationValidator(trading_mode='live')
            is_valid, results = validator.validate_all()

            # Check that it reports ZERODHA_* missing (not KITE_*)
            errors = [r for r in results if r.severity == 'error']
            error_names = [r.name for r in errors]

            # CRITICAL: Must check ZERODHA_API_KEY, not KITE_API_KEY
            assert 'ZERODHA_API_KEY' in error_names, "Validator must check ZERODHA_API_KEY (not KITE_API_KEY)!"
            assert 'ZERODHA_API_SECRET' in error_names, "Validator must check ZERODHA_API_SECRET (not KITE_ACCESS_TOKEN)!"

            # Should NOT check for KITE_* variables
            assert 'KITE_API_KEY' not in error_names, "Validator should NOT check KITE_API_KEY!"
            assert 'KITE_ACCESS_TOKEN' not in error_names, "Validator should NOT check KITE_ACCESS_TOKEN!"

            assert not is_valid, "Validation should fail without Zerodha credentials in live mode"

        finally:
            # Restore env vars
            if old_dashboard_key:
                os.environ['DASHBOARD_API_KEY'] = old_dashboard_key
            elif 'DASHBOARD_API_KEY' in os.environ:
                del os.environ['DASHBOARD_API_KEY']

            if old_zerodha_key:
                os.environ['ZERODHA_API_KEY'] = old_zerodha_key
            elif 'ZERODHA_API_KEY' in os.environ:
                del os.environ['ZERODHA_API_KEY']

            if old_zerodha_secret:
                os.environ['ZERODHA_API_SECRET'] = old_zerodha_secret
            elif 'ZERODHA_API_SECRET' in os.environ:
                del os.environ['ZERODHA_API_SECRET']

    def test_config_validator_passes_with_zerodha_credentials(self):
        """Verify validator passes when ZERODHA credentials are set"""
        from infrastructure.config_validator import ConfigurationValidator

        # Save current env vars
        old_vars = {
            'DASHBOARD_API_KEY': os.environ.get('DASHBOARD_API_KEY'),
            'ZERODHA_API_KEY': os.environ.get('ZERODHA_API_KEY'),
            'ZERODHA_API_SECRET': os.environ.get('ZERODHA_API_SECRET')
        }

        try:
            # Set all required credentials
            os.environ['DASHBOARD_API_KEY'] = 'test-dashboard-key-12345'
            os.environ['ZERODHA_API_KEY'] = 'test-zerodha-key-12345'
            os.environ['ZERODHA_API_SECRET'] = 'test-zerodha-secret-12345'

            # Validate in LIVE mode
            validator = ConfigurationValidator(trading_mode='live')
            is_valid, results = validator.validate_all()

            # Filter out warnings about directories that might not exist
            errors = [r for r in results if r.severity == 'error' and r.category != 'Directories']

            # Should not have critical errors about credentials
            cred_errors = [r for r in errors if 'ZERODHA' in r.name or 'DASHBOARD' in r.name]
            assert len(cred_errors) == 0, f"Should not have credential errors: {cred_errors}"

        finally:
            # Restore env vars
            for var, value in old_vars.items():
                if value:
                    os.environ[var] = value
                elif var in os.environ:
                    del os.environ[var]


class TestStatePersistenceThrottling:
    """Test state persistence throttling"""

    def test_trading_system_has_throttle_attributes(self):
        """Verify TradingSystem has throttling attributes"""
        from core.trading_system import UnifiedTradingSystem
        from data.provider import DataProvider

        # Create minimal system
        dp = DataProvider(kite=None, instruments_map={})
        system = UnifiedTradingSystem(
            data_provider=dp,
            kite=None,
            trading_mode='paper',
            config_override={'security': {'state_encryption': {'enabled': False}}}  # Disable encryption for testing
        )

        # Check throttle attributes
        assert hasattr(system, '_state_dirty')
        assert hasattr(system, '_last_state_persist')
        assert hasattr(system, '_min_persist_interval')
        assert hasattr(system, 'mark_state_dirty')

    def test_persist_state_has_force_parameter(self):
        """Verify _persist_state accepts force parameter"""
        from core.trading_system import UnifiedTradingSystem
        import inspect

        # Check method signature
        sig = inspect.signature(UnifiedTradingSystem._persist_state)
        params = list(sig.parameters.keys())

        assert 'force' in params, "_persist_state should have 'force' parameter for throttling"


class TestPerformanceMetrics:
    """Test performance metrics tracking"""

    def test_portfolio_has_metrics(self):
        """Verify UnifiedPortfolio has performance metrics"""
        from core.portfolio.portfolio import UnifiedPortfolio

        portfolio = UnifiedPortfolio(
            initial_cash=100000,
            trading_mode='paper',
            silent=True
        )

        # Check metrics exist
        assert hasattr(portfolio, 'performance_metrics')
        assert isinstance(portfolio.performance_metrics, dict)

        # Check expected metrics
        expected_metrics = [
            'api_calls', 'cache_hits', 'cache_misses',
            'state_saves', 'state_saves_skipped'
        ]
        for metric in expected_metrics:
            assert metric in portfolio.performance_metrics

    def test_metrics_can_be_incremented(self):
        """Verify metrics can be incremented"""
        from core.portfolio.portfolio import UnifiedPortfolio

        portfolio = UnifiedPortfolio(
            initial_cash=100000,
            trading_mode='paper',
            silent=True
        )

        # Increment a metric
        initial = portfolio.performance_metrics['api_calls']
        portfolio.increment_metric('api_calls', 5)

        # Verify it increased
        assert portfolio.performance_metrics['api_calls'] == initial + 5


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])
