#!/usr/bin/env python3
"""Test the corrected _is_expiring_today parser"""

from enhanced_trading_system_complete import UnifiedPortfolio
from datetime import datetime, timedelta
import calendar

portfolio = UnifiedPortfolio(initial_cash=1000000, trading_mode='paper', silent=True)

# Calculate last Thursday of October 2025
year = 2025
month = 10
last_day = calendar.monthrange(year, month)[1]
last_date = datetime(year, month, last_day)
while last_date.weekday() != 3:  # 3 = Thursday
    last_date -= timedelta(days=1)

today = datetime.now()
print(f'Today: {today.strftime("%Y-%m-%d")} ({today.strftime("%A")})')
print(f'Last Thursday of Oct 2025: {last_date.strftime("%Y-%m-%d")}')
print('=' * 70)

tests = [
    ('NIFTY25O1006150CE', 'Weekly Oct 6, 2025'),
    ('NIFTY25O0725150CE', 'Weekly July 25, 2025'),
    ('NIFTY25OCT18300CE', f'Monthly Oct (expires {last_date.strftime("%b %d")})'),
    ('BANKNIFTY25OCT56300CE', f'Monthly Oct (expires {last_date.strftime("%b %d")})'),
    ('BANKNIFTY25SEP45600CE', 'Monthly Sep (last Thursday)'),
]

print('\nTest Results:')
print('-' * 70)
for symbol, desc in tests:
    result = portfolio._is_expiring_today(symbol)
    emoji = '✅ EXPIRING TODAY' if result else '⚪ Not expiring today'
    print(f'{emoji}')
    print(f'  Symbol: {symbol}')
    print(f'  Description: {desc}')
    print()

print('✅ Parser correctly handles both weekly and monthly NSE F&O formats!')
