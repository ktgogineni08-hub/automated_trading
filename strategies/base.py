#!/usr/bin/env python3
"""
Base Strategy Class
Foundation for all trading strategies
"""

import pandas as pd
from typing import Dict


class BaseStrategy:
    """Base class for all trading strategies"""

    def __init__(self, name: str):
        self.name = name

    def generate_signals(self, data: pd.DataFrame, symbol: str = None) -> Dict:
        """
        Generate trading signals from data

        Args:
            data: OHLCV DataFrame
            symbol: Trading symbol (optional)

        Returns:
            Dict with keys: 'signal', 'strength', 'reason'
            - signal: 1 (buy), -1 (sell), 0 (hold)
            - strength: 0.0-1.0 confidence level
            - reason: Human-readable explanation
        """
        raise NotImplementedError("Subclasses must implement generate_signals")

    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        Validate input data has required columns

        Args:
            data: DataFrame to validate

        Returns:
            True if data is valid, False otherwise
        """
        if data is None or data.empty:
            return False
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        return all(col in data.columns for col in required_columns)
