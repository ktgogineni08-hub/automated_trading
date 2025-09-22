#!/usr/bin/env python3
"""
Integration tests for core components
"""

import unittest
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add the current directory to the path so we can import the main module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enhanced_trading_system_complete import (
    DataProvider,
    UnifiedPortfolio,
    DashboardConnector,
    TradingStateManager,
    EnhancedRateLimiter,
    MarketHours,
    TradingConfig,
    APIError,
    DataError,
    RiskManagementError
)

class TestDataProvider(unittest.TestCase):
    """Test DataProvider integration"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = TradingConfig()
        self.dp = DataProvider(use_yf_fallback=True)

    @patch('yfinance.download')
    def test_yfinance_fetch_success(self, mock_download):
        """Test successful yfinance data fetch"""
        # Mock successful yfinance response
        mock_df = pd.DataFrame({
            'Open': [100, 101, 102],
            'High': [105, 106, 107],
            'Low': [95, 96, 97],
            'Close': [102, 103, 104],
            'Volume': [1000, 1100, 1200]
        })
        mock_download.return_value = mock_df

        result = self.dp._yfinance_fetch("AAPL", "5m", 1)

        self.assertFalse(result.empty)
        self.assertEqual(len(result), 3)
        self.assertIn('open', result.columns)
        self.assertIn('close', result.columns)
        mock_download.assert_called_once()

    @patch('yfinance.download')
    def test_yfinance_fetch_failure(self, mock_download):
        """Test yfinance fetch failure handling"""
        mock_download.side_effect = Exception("API Error")

        result = self.dp._yfinance_fetch("INVALID", "5m", 1)

        self.assertTrue(result.empty)
        mock_download.assert_called_once()

    def test_cache_functionality(self):
        """Test caching functionality"""
        # First call should fetch data
        with patch.object(self.dp, '_yfinance_fetch') as mock_fetch:
            mock_df = pd.DataFrame({
                'open': [100, 101],
                'high': [105, 106],
                'low': [95, 96],
                'close': [102, 103],
                'volume': [1000, 1100]
            })
            mock_fetch.return_value = mock_df

            result1 = self.dp.fetch_with_retry("AAPL", "5m", 1)
            self.assertFalse(result1.empty)
            mock_fetch.assert_called_once()

            # Second call should use cache
            result2 = self.dp.fetch_with_retry("AAPL", "5m", 1)
            self.assertFalse(result2.empty)
            self.assertEqual(mock_fetch.call_count, 1)  # Should not call again

    def test_rate_limiter_integration(self):
        """Test rate limiter integration"""
        # Test that rate limiter methods exist and can be called
        self.assertTrue(hasattr(self.dp.rate_limiter, 'wait_if_needed'))
        self.assertTrue(hasattr(self.dp.rate_limiter, 'record_request'))
        self.assertTrue(hasattr(self.dp.rate_limiter, 'can_make_request'))

        # Test that rate limiter allows requests initially
        self.assertTrue(self.dp.rate_limiter.can_make_request())

        # Test wait_if_needed doesn't block initially
        self.dp.rate_limiter.wait_if_needed()  # Should not block

        # Test record_request works
        self.dp.rate_limiter.record_request()

class TestUnifiedPortfolio(unittest.TestCase):
    """Test UnifiedPortfolio integration"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = TradingConfig()
        self.portfolio = UnifiedPortfolio(initial_cash=1000000, trading_mode='paper')

    def test_portfolio_initialization(self):
        """Test portfolio initialization"""
        self.assertEqual(self.portfolio.initial_cash, 1000000)
        self.assertEqual(self.portfolio.cash, 1000000)
        self.assertEqual(self.portfolio.trading_mode, 'paper')
        self.assertEqual(len(self.portfolio.positions), 0)

    def test_buy_trade_execution(self):
        """Test buy trade execution"""
        # Execute buy trade
        trade = self.portfolio.execute_trade(
            symbol="AAPL",
            shares=10,
            price=150.0,
            side="buy",
            confidence=0.7,
            sector="IT"
        )

        self.assertIsNotNone(trade)
        self.assertEqual(trade['symbol'], "AAPL")
        self.assertEqual(trade['side'], "buy")
        self.assertEqual(trade['shares'], 10)
        self.assertLess(self.portfolio.cash, 1000000)  # Cash should be reduced
        self.assertIn("AAPL", self.portfolio.positions)

    def test_sell_trade_execution(self):
        """Test sell trade execution"""
        # First buy some shares
        buy_trade = self.portfolio.execute_trade("AAPL", 10, 150.0, "buy", confidence=0.7, sector="IT")
        self.assertIsNotNone(buy_trade)

        # Manually set entry time to past to bypass minimum holding period
        past_time = datetime.now() - timedelta(minutes=30)
        self.portfolio.position_entry_times["AAPL"] = past_time

        # Then sell them
        trade = self.portfolio.execute_trade("AAPL", 10, 155.0, "sell", confidence=0.7, sector="IT")

        self.assertIsNotNone(trade)
        self.assertEqual(trade['symbol'], "AAPL")
        self.assertEqual(trade['side'], "sell")
        self.assertGreater(self.portfolio.cash, 1000000 * 0.98)  # Cash should be increased
        self.assertNotIn("AAPL", self.portfolio.positions)

    def test_portfolio_value_calculation(self):
        """Test portfolio value calculation"""
        # Add a position
        self.portfolio.execute_trade("AAPL", 10, 150.0, "buy", confidence=0.7, sector="IT")

        # Calculate total value
        total_value = self.portfolio.calculate_total_value({"AAPL": 160.0})

        # Check that total value is reasonable (should be close to original + profit)
        self.assertGreater(total_value, 1000000)  # Should have made profit
        self.assertLess(total_value, 1002000)     # But not too much profit

    def test_risk_management(self):
        """Test risk management features"""
        # Test with ATR-based position sizing
        trade = self.portfolio.execute_trade(
            symbol="AAPL",
            shares=100,  # Large position
            price=150.0,
            side="buy",
            confidence=0.7,
            sector="IT",
            atr=5.0  # ATR value
        )

        # Position should be reduced due to risk management
        self.assertIsNotNone(trade)
        self.assertLessEqual(trade['shares'], 100)

class TestDashboardConnector(unittest.TestCase):
    """Test DashboardConnector integration"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = TradingConfig()
        self.dashboard = DashboardConnector("http://localhost:5173")

    @patch('requests.Session.post')
    def test_successful_signal_send(self, mock_post):
        """Test successful signal sending"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = self.dashboard.send_signal("AAPL", "buy", 0.8, 150.0, "IT", ["reason1"])

        self.assertTrue(result)
        mock_post.assert_called_once()

    @patch('requests.Session.post')
    def test_failed_signal_send(self, mock_post):
        """Test failed signal sending"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        result = self.dashboard.send_signal("AAPL", "buy", 0.8, 150.0)

        self.assertFalse(result)

    def test_circuit_breaker(self):
        """Test circuit breaker functionality"""
        # Simulate multiple failures
        self.dashboard.circuit_breaker_failures = 5
        self.dashboard.last_circuit_breaker_trip = time.time() - 30  # Set trip time to 30 seconds ago

        self.assertTrue(self.dashboard.is_circuit_breaker_open())

        # Test circuit breaker reset after timeout
        self.dashboard.last_circuit_breaker_trip = 0
        self.dashboard.circuit_breaker_failures = 10

        # Mock time to be after timeout
        with patch('time.time', return_value=100):
            self.dashboard.last_circuit_breaker_trip = 0
            self.assertFalse(self.dashboard.is_circuit_breaker_open())

class TestTradingStateManager(unittest.TestCase):
    """Test TradingStateManager integration"""

    def setUp(self):
        """Set up test fixtures"""
        self.state_manager = TradingStateManager("test_state")

        # Clean up any existing test state
        if self.state_manager.base_dir.exists():
            import shutil
            shutil.rmtree(self.state_manager.base_dir)

        self.state_manager.base_dir.mkdir(parents=True)

    def tearDown(self):
        """Clean up test fixtures"""
        if self.state_manager.base_dir.exists():
            import shutil
            shutil.rmtree(self.state_manager.base_dir)

    def test_state_persistence(self):
        """Test state save and load"""
        test_state = {
            'portfolio': {'cash': 900000, 'positions': {}},
            'iteration': 5,
            'trading_day': '2023-01-01'
        }

        # Save state
        self.state_manager.save_state(test_state)

        # Load state
        loaded_state = self.state_manager.load_state()

        self.assertEqual(loaded_state['iteration'], 5)
        self.assertEqual(loaded_state['trading_day'], '2023-01-01')

    def test_trade_logging(self):
        """Test trade logging"""
        # Ensure trades directory exists
        self.state_manager.trades_dir.mkdir(exist_ok=True)

        test_trade = {
            'symbol': 'AAPL',
            'side': 'buy',
            'shares': 10,
            'price': 150.0
        }

        self.state_manager.log_trade(test_trade, '2023-01-01')

        # Check if trade file was created
        trades_file = self.state_manager.trades_dir / "trades_2023-01-01.jsonl"
        self.assertTrue(trades_file.exists())

        # Check if content was written
        content = trades_file.read_text()
        self.assertIn('AAPL', content)
        self.assertIn('buy', content)

class TestRateLimiter(unittest.TestCase):
    """Test EnhancedRateLimiter integration"""

    def setUp(self):
        """Set up test fixtures"""
        self.rate_limiter = EnhancedRateLimiter(max_requests_per_second=2, max_requests_per_minute=10)

    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        # Record requests up to limit
        for i in range(2):
            self.assertTrue(self.rate_limiter.can_make_request())
            self.rate_limiter.record_request()

        # Should be blocked now
        self.assertFalse(self.rate_limiter.can_make_request())

        # Wait and should be allowed again
        import time
        time.sleep(1.1)
        self.assertTrue(self.rate_limiter.can_make_request())

class TestMarketHours(unittest.TestCase):
    """Test MarketHours integration"""

    def setUp(self):
        """Set up test fixtures"""
        self.market_hours = MarketHours()

    def test_market_open_detection(self):
        """Test market open detection"""
        # Test weekday during market hours
        test_time = datetime(2023, 1, 2, 12, 0)  # Monday 12:00
        with patch('enhanced_trading_system_complete.datetime') as mock_datetime:
            mock_datetime.now.return_value = test_time.replace(tzinfo=self.market_hours.ist)
            self.assertTrue(self.market_hours.is_market_open())

        # Test weekend
        test_time = datetime(2023, 1, 7, 12, 0)  # Saturday 12:00
        with patch('enhanced_trading_system_complete.datetime') as mock_datetime:
            mock_datetime.now.return_value = test_time.replace(tzinfo=self.market_hours.ist)
            self.assertFalse(self.market_hours.is_market_open())

        # Test before market open
        test_time = datetime(2023, 1, 2, 8, 0)  # Monday 8:00 (before 9:15)
        with patch('enhanced_trading_system_complete.datetime') as mock_datetime:
            mock_datetime.now.return_value = test_time.replace(tzinfo=self.market_hours.ist)
            self.assertFalse(self.market_hours.is_market_open())

        # Test after market close
        test_time = datetime(2023, 1, 2, 16, 0)  # Monday 16:00 (after 15:30)
        with patch('enhanced_trading_system_complete.datetime') as mock_datetime:
            mock_datetime.now.return_value = test_time.replace(tzinfo=self.market_hours.ist)
            self.assertFalse(self.market_hours.is_market_open())

class TestErrorHandling(unittest.TestCase):
    """Test error handling integration"""

    def test_api_error_handling(self):
        """Test API error handling"""
        with self.assertRaises(APIError):
            raise APIError("Test API error", 500, "Internal Server Error")

    def test_data_error_handling(self):
        """Test data error handling"""
        with self.assertRaises(DataError):
            raise DataError("Test data error")

    def test_risk_management_error_handling(self):
        """Test risk management error handling"""
        with self.assertRaises(RiskManagementError):
            raise RiskManagementError("Test risk management error")

class TestConfigurationIntegration(unittest.TestCase):
    """Test configuration integration"""

    def setUp(self):
        """Set up test fixtures"""
        # Set test environment variables
        os.environ['ZERODHA_API_KEY'] = 'test_key'
        os.environ['ZERODHA_API_SECRET'] = 'test_secret'
        os.environ['INITIAL_CAPITAL'] = '500000'

    def tearDown(self):
        """Clean up test fixtures"""
        if 'ZERODHA_API_KEY' in os.environ:
            del os.environ['ZERODHA_API_KEY']
        if 'ZERODHA_API_SECRET' in os.environ:
            del os.environ['ZERODHA_API_SECRET']
        if 'INITIAL_CAPITAL' in os.environ:
            del os.environ['INITIAL_CAPITAL']

    def test_config_from_env_integration(self):
        """Test configuration loading from environment"""
        config = TradingConfig.from_env()

        self.assertEqual(config.api_key, 'test_key')
        self.assertEqual(config.api_secret, 'test_secret')
        self.assertEqual(config.initial_capital, 500000.0)

if __name__ == '__main__':
    # Set up test environment
    os.environ.setdefault('LOG_LEVEL', 'ERROR')  # Reduce log noise during tests

    # Run tests
    unittest.main(verbosity=2)