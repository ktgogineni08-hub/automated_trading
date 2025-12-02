#!/usr/bin/env python3
"""
Tests for Core Backtest Engine
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backtest_engine import BacktestEngine
from data.provider import DataProvider

class TestBacktestEngine:
    
    @pytest.fixture
    def mock_data_provider(self):
        dp = MagicMock(spec=DataProvider)
        
        # Create sample dataframe
        dates = pd.date_range(start='2024-01-01', periods=100, freq='5min')
        data = {
            'open': np.random.uniform(100, 110, 100),
            'high': np.random.uniform(110, 120, 100),
            'low': np.random.uniform(90, 100, 100),
            'close': np.random.uniform(100, 110, 100),
            'volume': np.random.randint(1000, 10000, 100)
        }
        df = pd.DataFrame(data, index=dates)
        dp.fetch_with_retry.return_value = df
        return dp

    def test_initialization(self, mock_data_provider):
        engine = BacktestEngine(mock_data_provider, initial_capital=100000.0)
        assert engine.dp == mock_data_provider
        assert engine.initial_capital == 100000.0

    def test_run_fast_backtest(self, mock_data_provider):
        engine = BacktestEngine(mock_data_provider)
        
        # Mock VectorizedBacktester to avoid complex logic during unit test
        with patch('core.backtest_engine.VectorizedBacktester') as MockBacktester:
            mock_instance = MockBacktester.return_value
            mock_instance.run.return_value = MagicMock(
                final_capital=110000.0,
                total_return_pct=10.0,
                total_trades=5,
                winning_trades=3,
                win_rate_pct=60.0,
                sharpe_ratio=1.5
            )
            
            # Run backtest
            engine.run_fast_backtest(['NIFTY 50'], interval='5minute', days=5)
            
            # Verify calls
            mock_data_provider.fetch_with_retry.assert_called_with('NIFTY 50', interval='5minute', days=5)
            mock_instance.run.assert_called()

    def test_normalize_interval(self):
        assert BacktestEngine._normalize_fast_interval('5m') == '5minute'
        assert BacktestEngine._normalize_fast_interval('1h') == '60minute'
        assert BacktestEngine._normalize_fast_interval('invalid') == '5minute'
