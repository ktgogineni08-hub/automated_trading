import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
import sys

# Mock dependencies
sys.modules['kiteconnect'] = MagicMock()
sys.modules['cryptography'] = MagicMock()
sys.modules['cryptography.fernet'] = MagicMock()
sys.modules['cryptography.hazmat'] = MagicMock()
sys.modules['cryptography.hazmat.primitives'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.hashes'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.kdf'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.kdf.pbkdf2'] = MagicMock()
sys.modules['cryptography.hazmat.backends'] = MagicMock()
sys.modules['yaml'] = MagicMock()
sys.modules['holidays'] = MagicMock()

from core.trading_system import UnifiedTradingSystem
from data.provider import DataProvider

class TestSystemBacktest(unittest.TestCase):
    def setUp(self):
        # Mock internal components of UnifiedTradingSystem
        self.patcher1 = patch('core.trading_system.TradingStateManager')
        self.MockStateManager = self.patcher1.start()
        
        self.patcher2 = patch('core.trading_system.AdvancedMarketManager')
        self.MockAMM = self.patcher2.start()
        
        self.patcher3 = patch('core.trading_system.MarketRegimeDetector')
        self.MockMRD = self.patcher3.start()

        self.mock_dp = MagicMock(spec=DataProvider)
        self.mock_kite = MagicMock()
        
        # Create sample data
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        self.sample_df = pd.DataFrame({
            'open': np.random.rand(100) * 100,
            'high': np.random.rand(100) * 100,
            'low': np.random.rand(100) * 100,
            'close': np.linspace(100, 150, 100), # Upward trend
            'volume': np.random.randint(100, 1000, 100)
        }, index=dates)
        
        self.mock_dp.fetch_with_retry.return_value = self.sample_df
        
        # Initialize system
        self.system = UnifiedTradingSystem(
            data_provider=self.mock_dp,
            kite=self.mock_kite,
            initial_cash=100000,
            trading_mode='backtest'
        )
        self.system.symbols = ['TEST_SYM']

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        self.patcher3.stop()

    def test_vectorized_backtest_execution(self):
        # Run backtest
        # We expect it to print results and not crash
        try:
            self.system.run_fast_backtest(days=30)
        except Exception as e:
            self.fail(f"Backtest failed with exception: {e}")

if __name__ == '__main__':
    unittest.main()
