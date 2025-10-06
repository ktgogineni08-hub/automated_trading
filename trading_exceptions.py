"""
Custom exceptions for the trading system
"""
from typing import Optional


class TradingError(Exception):
    """Base exception for trading system"""
    pass


class ConfigurationError(TradingError):
    """Configuration related errors"""
    pass


class APIError(TradingError):
    """API related errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class DataError(TradingError):
    """Data related errors"""
    pass


class RiskManagementError(TradingError):
    """Risk management related errors"""
    pass


class MarketHoursError(TradingError):
    """Market hours related errors"""
    pass


class ValidationError(TradingError):
    """Input validation related errors"""
    pass
