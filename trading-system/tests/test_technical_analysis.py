#!/usr/bin/env python3
"""
Tests for Enhanced Technical Analysis
"""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from enhanced_technical_analysis import EnhancedTechnicalAnalysis

class TestEnhancedTechnicalAnalysis:
    
    @pytest.fixture
    def analyzer(self):
        return EnhancedTechnicalAnalysis()
        
    @pytest.fixture
    def sample_data(self):
        dates = pd.date_range(start='2024-01-01', periods=20, freq='D')
        data = {
            'high': [105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124],
            'low':  [95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
            'close': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119]
        }
        return pd.DataFrame(data, index=dates)

    def test_calculate_atr(self, analyzer, sample_data):
        # Test with sufficient data
        atr = analyzer.calculate_atr(sample_data, period=14)
        assert isinstance(atr, float)
        assert atr > 0
        
        # Manual calculation check for last value
        # TR is always 10 in this synthetic data (High-Low=10, High-PrevClose=5, Low-PrevClose=5)
        # So ATR should be 10
        assert abs(atr - 10.0) < 0.1

    def test_calculate_atr_insufficient_data(self, analyzer, sample_data):
        # Test with insufficient data
        short_data = sample_data.iloc[:5]
        atr = analyzer.calculate_atr(short_data, period=14)
        assert atr == 0.0

    def test_calculate_atr_empty_data(self, analyzer):
        atr = analyzer.calculate_atr(pd.DataFrame(), period=14)
        assert atr == 0.0
