#!/usr/bin/env python3
"""
Market Hours Manager
IST timezone-aware market hours validation
"""

from datetime import datetime, time
import pytz
from typing import Tuple
import logging

from trading_utils import get_ist_now

logger = logging.getLogger('trading_system.market_hours')

class MarketHoursManager:
    """Enhanced market hours management with trading restrictions"""

    def __init__(self):
        # LOW PRIORITY FIX: Removed redundant import - using time from top
        self.ist = pytz.timezone('Asia/Kolkata')
        self.market_open = time(9, 15)  # 9:15 AM
        self.market_close = time(15, 30)  # 3:30 PM

    def is_market_open(self) -> bool:
        """Check if Indian stock market is currently open"""
        now = get_ist_now()
        current_time = now.time().replace(tzinfo=None)
        current_weekday = now.weekday()  # 0=Monday, 6=Sunday

        # Market hours: 9:15 AM to 3:30 PM IST, Monday to Friday
        # FIXED: Use < instead of <= for market_close to stop trading AT 3:30 PM, not after
        is_weekday = current_weekday < 5  # Monday to Friday
        is_trading_hours = self.market_open <= current_time < self.market_close

        return is_weekday and is_trading_hours

    def can_trade(self) -> tuple[bool, str]:
        """Check if trading is allowed and return reason"""
        if not self.is_market_open():
            now = get_ist_now()
            current_time = now.time().replace(tzinfo=None)
            current_weekday = now.weekday()

            if current_weekday >= 5:  # Weekend
                return False, "❌ WEEKEND - Market closed"
            elif current_time < self.market_open:
                return False, "❌ PRE-MARKET - Trading starts at 9:15 AM"
            elif current_time > self.market_close:
                return False, "❌ POST-MARKET - Trading ended at 3:30 PM"
            else:
                return False, "❌ MARKET CLOSED"

        return True, "✅ TRADING ALLOWED - Market is open"

    def time_until_market_open(self) -> str:
        """Get time until market opens"""
        now = get_ist_now().replace(tzinfo=None)

        if now.weekday() >= 5:  # Weekend
            days_until_monday = 7 - now.weekday()
            return f"{days_until_monday} days until Monday"

        if now.time() < self.market_open:
            # Market opens today
            market_open_today = datetime.combine(now.date(), self.market_open)
            time_diff = market_open_today - now
            hours, remainder = divmod(int(time_diff.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            return f"{hours}h {minutes}m until market open"

        return "Market is open or closed for the day"

    def should_save_data(self) -> bool:
        """Check if data should be saved (after market hours)"""
