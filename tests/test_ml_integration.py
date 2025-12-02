#!/usr/bin/env python3
"""
Test ML Integration
"""

import pytest
import pandas as pd
import numpy as np
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.trading_system import UnifiedTradingSystem
from models.ml_predictor import MLPredictor

class TestMLIntegration:
    
    @pytest.fixture
    def mock_components(self):
        dp = MagicMock()
        kite = MagicMock()
        return dp, kite

    def test_ml_predictor_loading(self):
        """Test if MLPredictor loads the model"""
        predictor = MLPredictor()
        # It should have loaded the model we trained earlier
        assert predictor.model is not None
        assert predictor.scaler is not None

    def test_ml_prediction_output(self):
        """Test if predict returns correct structure"""
        predictor = MLPredictor()
        
        # Create dummy data
        dates = pd.date_range(start='2024-01-01', periods=100, freq='5min')
        df = pd.DataFrame({
            'open': np.random.rand(100) * 100,
            'high': np.random.rand(100) * 100,
            'low': np.random.rand(100) * 100,
            'close': np.random.rand(100) * 100,
            'volume': np.random.randint(100, 1000, 100)
        }, index=dates)
        
        result = predictor.predict(df)
        
        assert 'probability' in result
        assert 'direction' in result
        assert 'confidence' in result
        assert 0 <= result['probability'] <= 1
        assert result['direction'] in [0, 1]

    @patch('core.trading_system.UnifiedPortfolio')
    @patch('core.trading_system.MarketHoursManager')
    @patch('core.trading_system.TradingStateManager')
    def test_system_integration(self, mock_state_manager, mock_hours, mock_portfolio, mock_components):
        """Test if UnifiedTradingSystem initializes MLPredictor"""
        dp, kite = mock_components
        
        # Mock security context to avoid permission error
        with patch('core.trading_system.SecurityContext') as MockSecurity:
            MockSecurity.return_value.ensure_client_authorized.return_value = True
            
            system = UnifiedTradingSystem(dp, kite, initial_cash=100000)
            
            assert hasattr(system, 'ml_predictor')
            assert isinstance(system.ml_predictor, MLPredictor)
            assert system.ml_predictor.model is not None
