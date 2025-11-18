#!/usr/bin/env python3
"""Comprehensive test to validate expiry date extraction fix"""

import re
import calendar
from datetime import datetime, timedelta
from typing import Optional

class logger:
    """Mock logger for testing"""
    @staticmethod
    def debug(msg):
        pass

def extract_expiry_date_FIXED(symbol: str) -> Optional[datetime]:
    """
    FIXED VERSION: Extract expiry date from option symbol using correct parsing
    """
    try:
        # Extract underlying index
        underlying_match = re.match(r'^([A-Z]+)', symbol)
        if not underlying_match:
            return None

        underlying = underlying_match.group(1)
        remainder = symbol[underlying_match.end():]

        # Legacy weekly format: UNDERLYING + YYOmmdd (e.g., NIFTY25O0725...)
        legacy_weekly = re.match(r'(\d{2})O(\d{2})(\d{2})', remainder)
        if legacy_weekly:
            year = 2000 + int(legacy_weekly.group(1))
            month = int(legacy_weekly.group(2))
            day = int(legacy_weekly.group(3))
            try:
                return datetime(year, month, day)
            except ValueError:
                return None

        # Modern format: YY + MMM + [DD]STRIKE + CE/PE
        match = re.match(r'(\d{2})([A-Z]{3})([^CPE]+)(CE|PE)$', remainder)
        if not match:
            return None

        year = 2000 + int(match.group(1))
        month_abbr = match.group(2)
        middle = match.group(3)

        month_lookup = {
            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
        }
        month = month_lookup.get(month_abbr)
        if not month:
            return None

        # Determine underlying-specific expiry schedules
        if 'FINNIFTY' in underlying:
            weekly_target_weekday = 1  # Tuesday
            monthly_target_weekday = 1
        elif 'BANKNIFTY' in underlying:
            weekly_target_weekday = 2  # Wednesday
            monthly_target_weekday = 2
        else:
            weekly_target_weekday = 3  # Thursday (NIFTY default)
            monthly_target_weekday = 3

        # Calculate monthly expiry (last occurrence of target weekday)
        monthly_last_day = calendar.monthrange(year, month)[1]
        monthly_expiry_dt = datetime(year, month, monthly_last_day)
        while monthly_expiry_dt.weekday() != monthly_target_weekday:
            monthly_expiry_dt -= timedelta(days=1)

        # Check if middle part contains a day value (weekly expiry)
        if middle and middle.isdigit():
            if len(middle) >= 4:  # DDSTRIKE format (e.g., 2519000)
                day_fragment = middle[:2]
                strike_fragment = middle[2:]
                if strike_fragment and strike_fragment.isdigit():
                    day_value = int(day_fragment)
                    strike_value = int(strike_fragment)

                    # CRITICAL: Distinguish weekly from monthly options
                    # Weekly: NIFTY25FEB2023000CE -> middle=2023000, day=20, strike=23000 (valid!)
                    # Monthly: NIFTY25JAN23000CE -> middle=23000, day=23, strike=000 (invalid!)
                    #
                    # Heuristic: Weekly options have strikes >= 10000
                    # If strike < 10000, it's likely the "day" is part of the strike price
                    if strike_value >= 10000 and 1 <= day_value <= 31:
                        # Check if this is a valid weekly expiry (not monthly)
                        try:
                            candidate_dt = datetime(year, month, day_value)
                            # If it matches target weekday and is NOT monthly expiry, it's weekly
                            if (candidate_dt.weekday() == weekly_target_weekday and
                                candidate_dt.day != monthly_expiry_dt.day):
                                return candidate_dt
                        except ValueError:
                            pass

        # Default to monthly expiry
        return monthly_expiry_dt

    except Exception as e:
        return None


# Test cases with expected results
test_cases = [
    # Format: (symbol, expected_date_str, description, expected_weekday_name)
    ("NIFTY25O0725150CE", "2025-07-25", "Legacy weekly Oct 25, 2025", "Friday"),
    ("NIFTY24JAN19000CE", "2024-01-25", "Monthly Jan 2024 (last Thu)", "Thursday"),
    ("NIFTY24JAN1119000CE", "2024-01-11", "Weekly Jan 11, 2024", "Thursday"),
    ("BANKNIFTY24JAN40000PE", "2024-01-31", "BANKNIFTY monthly Jan (last Wed)", "Wednesday"),
    ("BANKNIFTY24JAN1040000PE", "2024-01-10", "BANKNIFTY weekly Jan 10, 2024", "Wednesday"),
    ("FINNIFTY24FEB18000CE", "2024-02-27", "FINNIFTY monthly Feb (last Tue)", "Tuesday"),
    ("FINNIFTY24FEB0618000CE", "2024-02-06", "FINNIFTY weekly Feb 06, 2024", "Tuesday"),
    ("NIFTY25JAN23000CE", "2025-01-30", "NIFTY monthly Jan 2025 (last Thu)", "Thursday"),
    ("NIFTY25FEB2023000CE", "2025-02-20", "NIFTY weekly Feb 20, 2025", "Thursday"),
]

print("=" * 100)
print("COMPREHENSIVE EXPIRY DATE EXTRACTION TEST")
print("=" * 100)

passed = 0
failed = 0

for symbol, expected_date_str, description, expected_weekday in test_cases:
    result = extract_expiry_date_FIXED(symbol)
    expected_date = datetime.strptime(expected_date_str, "%Y-%m-%d")

    status = "✅ PASS" if (result and result.date() == expected_date.date()) else "❌ FAIL"

    if result and result.date() == expected_date.date():
        passed += 1
        weekday_name = result.strftime("%A")
        print(f"{status} | {symbol:25} | {description:40}")
        print(f"       Expected: {expected_date_str} ({expected_weekday})")
        print(f"       Got:      {result.date()} ({weekday_name})")
    else:
        failed += 1
        print(f"{status} | {symbol:25} | {description:40}")
        print(f"       Expected: {expected_date_str} ({expected_weekday})")
        print(f"       Got:      {result.date() if result else 'None'}")
    print()

print("=" * 100)
print(f"RESULTS: {passed}/{len(test_cases)} passed, {failed}/{len(test_cases)} failed")
print("=" * 100)

if failed == 0:
    print("✅ ALL TESTS PASSED - Expiry date extraction is working correctly!")
else:
    print("❌ SOME TESTS FAILED - Review the fix")
