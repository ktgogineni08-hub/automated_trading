#!/usr/bin/env python3
"""Debug version of _is_expiring_today to see what's happening"""

from datetime import datetime, timedelta
import calendar
import re

def _is_expiring_today_debug(symbol: str, test_date=None) -> bool:
    """Debug version with prints"""
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
        print(f"Underlying: {underlying}")
        print(f"Rest: {rest}")

        # Try old weekly format first (YYOmmdd)
        old_weekly = re.match(r'(\d{2})O(\d{2})(\d{2})', rest)
        if old_weekly:
            year_suffix = int(old_weekly.group(1))
            month = int(old_weekly.group(2))
            day = int(old_weekly.group(3))

            year = 2000 + year_suffix
            print(f"✓ Old weekly format matched: YY={year_suffix}, MM={month:02d}, DD={day:02d}")
            print(f"  Expiry date: {year}-{month:02d}-{day:02d}")

            if 1 <= month <= 12 and 1 <= day <= 31:
                try:
                    expiry_date = datetime(year, month, day)
                    result = expiry_date.date() == today
                    print(f"  Result: {result}")
                    return result
                except ValueError as e:
                    print(f"  Invalid date: {e}")
                    pass

        # For new format (YYMMMDD or YYMMM)
        base_match = re.match(r'(\d{2})([A-Z]{3})', rest)
        if not base_match:
            print("❌ No base match for YYMMM")
            return False

        year_suffix = int(base_match.group(1))
        month_abbr = base_match.group(2)
        print(f"✓ Base match: YY={year_suffix}, MMM={month_abbr}")

        month_map = {
            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
        }

        month = month_map.get(month_abbr)
        if not month:
            print(f"❌ Invalid month abbr: {month_abbr}")
            return False

        year = 2000 + year_suffix
        print(f"  Year: {year}, Month: {month}")

        # Check what follows the month
        after_month = rest[base_match.end():]
        print(f"  After month: '{after_month}'")

        # Try to extract potential day (first 2 digits after month)
        day_match = re.match(r'(\d{2})', after_month)
        if day_match:
            potential_day = int(day_match.group(1))
            print(f"  Found 2 digits: {potential_day:02d}")

            if 1 <= potential_day <= 31:
                try:
                    expiry_date = datetime(year, month, potential_day)
                    print(f"  Valid date: {expiry_date.date()}")
                    if expiry_date.date() == today:
                        print(f"  ✓ WEEKLY MATCH - expires today!")
                        return True
                    else:
                        print(f"  Weekly expiry is {expiry_date.date()}, not today")
                except ValueError as e:
                    print(f"  Invalid date combination: {e}")
                    pass

        # If no weekly match, treat as monthly (last Thursday)
        print(f"  Checking monthly expiry (last Thursday)...")
        last_day = calendar.monthrange(year, month)[1]
        last_date = datetime(year, month, last_day)

        while last_date.weekday() != 3:  # Thursday = 3
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


# Test cases
print("TESTING WITH SPECIFIC DATES")
print("="*80)

# Test 1: Monthly on expiry day
print("\nTest 1: NIFTY24OCT19400CE on Oct 31, 2024 (last Thursday)")
result = _is_expiring_today_debug("NIFTY24OCT19400CE", datetime(2024, 10, 31).date())
print(f"Expected: True, Got: {result} {'✓' if result else '✗'}")

# Test 2: Monthly NOT on expiry day (the tricky one)
print("\nTest 2: NIFTY24OCT19400CE on Oct 19, 2024 (NOT expiry)")
result = _is_expiring_today_debug("NIFTY24OCT19400CE", datetime(2024, 10, 19).date())
print(f"Expected: False, Got: {result} {'✓' if not result else '✗'}")

# Test 3: Weekly on expiry day
print("\nTest 3: BANKNIFTY24DEC0419500CE on Dec 4, 2024")
result = _is_expiring_today_debug("BANKNIFTY24DEC0419500CE", datetime(2024, 12, 4).date())
print(f"Expected: True, Got: {result} {'✓' if result else '✗'}")

# Test 4: Old format on expiry day
print("\nTest 4: NIFTY25O0725 on Jul 25, 2025")
result = _is_expiring_today_debug("NIFTY25O0725", datetime(2025, 7, 25).date())
print(f"Expected: True, Got: {result} {'✓' if result else '✗'}")
