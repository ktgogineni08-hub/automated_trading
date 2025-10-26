#!/usr/bin/env python3
"""Debug the NEW parsing logic"""

from datetime import datetime, timedelta
import calendar
import re

def _is_expiring_today_new(symbol: str, test_date=None) -> bool:
    """New logic with length-based detection"""
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

        # Match: YY + MMM + (everything until CE/PE)
        new_format = re.match(r'(\d{2})([A-Z]{3})(.+?)(CE|PE)$', rest)
        if not new_format:
            print("❌ No new format match")
            return False

        year_suffix = int(new_format.group(1))
        month_abbr = new_format.group(2)
        middle = new_format.group(3)  # The part between MMM and CE/PE

        print(f"✓ New format match:")
        print(f"  YY={year_suffix}, MMM={month_abbr}")
        print(f"  Middle part: '{middle}' (length={len(middle)})")

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

        # NEW LOGIC: Check middle part length
        print(f"\n  Checking if weekly (length >= 5)...")
        if len(middle) >= 5:  # At least DD(2) + strike(3+)
            potential_day_str = middle[:2]
            potential_strike_str = middle[2:]

            print(f"    First 2 chars: '{potential_day_str}'")
            print(f"    Remaining: '{potential_strike_str}'")
            print(f"    Remaining is digit: {potential_strike_str.isdigit()}")
            print(f"    Remaining length: {len(potential_strike_str)}")

            # Check if this could be a day + strike pattern
            if potential_strike_str.isdigit() and len(potential_strike_str) >= 3:
                potential_day = int(potential_day_str)

                print(f"    Potential day: {potential_day}")
                print(f"    Day in range 1-31: {1 <= potential_day <= 31}")

                # Valid day range check
                if 1 <= potential_day <= 31:
                    try:
                        # Try to construct the date
                        expiry_date = datetime(year, month, potential_day)

                        print(f"    ✓ Valid date: {expiry_date.date()}")
                        print(f"    This is WEEKLY")
                        result = expiry_date.date() == today
                        print(f"    Result: {result}")
                        return result
                    except ValueError as e:
                        print(f"    Invalid date combination: {e}")
                        pass
        else:
            print(f"    Middle length {len(middle)} < 5, skipping weekly check")

        # If we get here, treat as monthly (last Thursday)
        print(f"\n  Treating as MONTHLY (last Thursday)...")
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
print("TESTING WITH NEW LENGTH-BASED LOGIC")
print("="*80)

# Test 1: Monthly on expiry day
print("\nTest 1: NIFTY24OCT19400CE on Oct 31, 2024 (last Thursday)")
result = _is_expiring_today_new("NIFTY24OCT19400CE", datetime(2024, 10, 31).date())
print(f"\nExpected: True, Got: {result} {'✓' if result else '✗'}")

# Test 2: Monthly NOT on expiry day (the tricky one - "19" is part of strike)
print("\n\nTest 2: NIFTY24OCT19400CE on Oct 19, 2024 (NOT expiry)")
result = _is_expiring_today_new("NIFTY24OCT19400CE", datetime(2024, 10, 19).date())
print(f"\nExpected: False, Got: {result} {'✓' if not result else '✗'}")

# Test 3: Weekly on expiry day
print("\n\nTest 3: BANKNIFTY24DEC0419500CE on Dec 4, 2024")
result = _is_expiring_today_new("BANKNIFTY24DEC0419500CE", datetime(2024, 12, 4).date())
print(f"\nExpected: True, Got: {result} {'✓' if result else '✗'}")

# Test 4: Stock option with 3-digit strike (monthly)
print("\n\nTest 4: ITC24DEC440CE on Dec 26, 2024 (last Thursday)")
result = _is_expiring_today_new("ITC24DEC440CE", datetime(2024, 12, 26).date())
print(f"\nExpected: True, Got: {result} {'✓' if result else '✗'}")

# Test 5: Old format
print("\n\nTest 5: NIFTY25O0725 on Jul 25, 2025")
result = _is_expiring_today_new("NIFTY25O0725", datetime(2025, 7, 25).date())
print(f"\nExpected: True, Got: {result} {'✓' if result else '✗'}")
