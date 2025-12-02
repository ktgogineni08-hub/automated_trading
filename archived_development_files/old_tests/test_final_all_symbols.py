#!/usr/bin/env python3
"""Final comprehensive test - ALL NSE F&O symbol types"""

from enhanced_trading_system_complete import UnifiedPortfolio
from datetime import datetime, timedelta
import calendar
from unittest.mock import patch

portfolio = UnifiedPortfolio(initial_cash=1000000, trading_mode='paper', silent=True)

def get_last_thursday(year, month):
    last_day = calendar.monthrange(year, month)[1]
    last_date = datetime(year, month, last_day)
    while last_date.weekday() != 3:
        last_date -= timedelta(days=1)
    return last_date

print('='  * 70)
print('FINAL COMPREHENSIVE NSE F&O SYMBOL PARSER TEST')
print('=' * 70)

tests = [
    # Index options (4-5 digit strikes)
    ('BANKNIFTY24DEC0419500CE', datetime(2024, 12, 4), 'Index weekly (new format)'),
    ('NIFTY24NOV2819500PE', datetime(2024, 11, 28), 'Index weekly (new format)'),
    ('NIFTY25O0725150CE', datetime(2025, 7, 25), 'Index weekly (old format)'),
    ('NIFTY24OCT18300CE', get_last_thursday(2024, 10), 'Index monthly'),

    # Stock options (3-digit strikes)
    ('ITC24DEC04440CE', datetime(2024, 12, 4), 'Stock weekly'),
    ('LT24NOV28980PE', datetime(2024, 11, 28), 'Stock weekly'),
    ('RELIANCE24OCT480CE', get_last_thursday(2024, 10), 'Stock monthly'),
]

passed = 0
failed = 0

for symbol, expected_date, desc in tests:
    with patch('datetime.datetime') as mock_dt:
        mock_dt.now.return_value = expected_date
        mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

        result = portfolio._is_expiring_today(symbol)

        if result:
            status = '✅ PASS'
            passed += 1
        else:
            status = '❌ FAIL'
            failed += 1

        print(f'{status} | {symbol}')
        print(f'        {desc}')
        print(f'        Expected expiry: {expected_date.strftime("%Y-%m-%d")}')

print()
print('=' * 70)
print(f'Results: {passed} passed, {failed} failed out of {len(tests)} tests')

if failed == 0:
    print('✅ ALL TESTS PASSED! Parser correctly handles all NSE F&O formats.')
    print()
    print('Supported formats:')
    print('  1. Index weekly (new): YYMMMDD + 4-5 digit strike')
    print('  2. Index weekly (old): YYOmmdd + 3-5 digit strike')
    print('  3. Index monthly: YYMMM + 4-5 digit strike')
    print('  4. Stock weekly: YYMMMDD + 3 digit strike')
    print('  5. Stock monthly: YYMMM + 3 digit strike')
else:
    print(f'❌ {failed} test(s) failed')
