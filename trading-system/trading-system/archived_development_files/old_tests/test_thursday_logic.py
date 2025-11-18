#!/usr/bin/env python3
"""Test the Thursday-based parsing logic"""

from datetime import datetime, timedelta
import calendar
import re

def _is_expiring_today_thursday(symbol: str, test_date=None) -> bool:
    """Thursday-based logic"""
    try:
        today = test_date or datetime.now().date()
        print(f"\n{'='*60}")
        print(f"Testing: {symbol}")
        print(f"Today: {today}")
        print(f"{'='*60}")

        # Extract underlying
        underlying_match = re.match(r'^([A-Z]+)', symbol)
        if not underlying_match:
            print("❌ No underlying match")
            return False

        underlying = underlying_match.group(1)
        rest = symbol[underlying_match.end():]
        print(f"Underlying: {underlying}, Rest: {rest}")

        # Try old weekly format first
        old_weekly = re.match(r'(\d{2})O(\d{2})(\d{2})', rest)
        if old_weekly:
            year_suffix = int(old_weekly.group(1))
            month = int(old_weekly.group(2))
            day = int(old_weekly.group(3))
            year = 2000 + year_suffix

            if 1 <= month <= 12 and 1 <= day <= 31:
                try:
                    expiry_date = datetime(year, month, day)
                    result = expiry_date.date() == today
                    print(f"Old format: {expiry_date.date()}, Result: {result}")
                    return result
                except ValueError:
                    pass

        # Match new format
        new_format = re.match(r'(\d{2})([A-Z]{3})(.+?)(CE|PE)$', rest)
        if not new_format:
            print("❌ No new format match")
            return False

        year_suffix = int(new_format.group(1))
        month_abbr = new_format.group(2)
        middle = new_format.group(3)

        print(f"YY={year_suffix}, MMM={month_abbr}, Middle='{middle}' (len={len(middle)})")

        month_map = {
            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
        }

        month = month_map.get(month_abbr)
        if not month:
            return False

        year = 2000 + year_suffix

        # Check for weekly pattern (DD + strike)
        if len(middle) >= 5:
            potential_day_str = middle[:2]
            potential_strike_str = middle[2:]

            print(f"Checking weekly: day='{potential_day_str}', strike='{potential_strike_str}'")

            if potential_strike_str.isdigit() and len(potential_strike_str) >= 3:
                potential_day = int(potential_day_str)

                if 1 <= potential_day <= 31:
                    try:
                        expiry_date = datetime(year, month, potential_day)
                        weekday = expiry_date.weekday()
                        weekday_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][weekday]

                        print(f"  Potential date: {expiry_date.date()} ({weekday_name})")

                        # Check if Thursday
                        if weekday == 3:
                            print(f"  ✓ It's a Thursday - WEEKLY option")
                            result = expiry_date.date() == today
                            print(f"  Result: {result}")
                            return result
                        else:
                            print(f"  ✗ Not a Thursday - probably monthly (strike starts with {potential_day_str})")
                    except ValueError as e:
                        print(f"  Invalid date: {e}")

        # Treat as monthly
        print(f"Treating as MONTHLY")
        last_day = calendar.monthrange(year, month)[1]
        last_date = datetime(year, month, last_day)

        while last_date.weekday() != 3:
            last_date -= timedelta(days=1)

        print(f"  Last Thursday: {last_date.date()}")
        result = last_date.date() == today
        print(f"  Result: {result}")
        return result

    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


print("TESTING WITH THURSDAY CHECK")
print("="*80)

# Test 1: Monthly on expiry day
print("\n1. NIFTY24OCT19400CE on Oct 31, 2024 (should be monthly)")
result = _is_expiring_today_thursday("NIFTY24OCT19400CE", datetime(2024, 10, 31).date())
print(f"Expected: True, Got: {result} {'✓' if result else '✗'}")

# Test 2: Monthly NOT on expiry, but "19" is Oct 19 (Saturday - NOT Thursday)
print("\n2. NIFTY24OCT19400CE on Oct 19, 2024 (should NOT trigger)")
result = _is_expiring_today_thursday("NIFTY24OCT19400CE", datetime(2024, 10, 19).date())
print(f"Expected: False, Got: {result} {'✓' if not result else '✗'}")

# Test 3: Weekly on expiry (Dec 4 is Wednesday in 2024 - wait let me check)
print("\n3. BANKNIFTY24DEC0419500CE on Dec 4, 2024")
# Let's check what day Dec 4, 2024 is
dec4 = datetime(2024, 12, 4)
print(f"   (Dec 4, 2024 is a {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][dec4.weekday()]})")
result = _is_expiring_today_thursday("BANKNIFTY24DEC0419500CE", datetime(2024, 12, 4).date())
print(f"Expected: True, Got: {result} {'✓' if result else '✗'}")

# Test 4: Weekly on a different date - Nov 28, 2024
print("\n4. NIFTY24NOV2819500PE on Nov 28, 2024")
nov28 = datetime(2024, 11, 28)
print(f"   (Nov 28, 2024 is a {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][nov28.weekday()]})")
result = _is_expiring_today_thursday("NIFTY24NOV2819500PE", datetime(2024, 11, 28).date())
print(f"Expected: True, Got: {result} {'✓' if result else '✗'}")

# Test 5: Stock option (3-digit strike)
print("\n5. ITC24DEC440CE on Dec 26, 2024 (monthly)")
result = _is_expiring_today_thursday("ITC24DEC440CE", datetime(2024, 12, 26).date())
print(f"Expected: True, Got: {result} {'✓' if result else '✗'}")

# Test 6: Old format
print("\n6. NIFTY25O0725 on Jul 25, 2025")
result = _is_expiring_today_thursday("NIFTY25O0725", datetime(2025, 7, 25).date())
print(f"Expected: True, Got: {result} {'✓' if result else '✗'}")
