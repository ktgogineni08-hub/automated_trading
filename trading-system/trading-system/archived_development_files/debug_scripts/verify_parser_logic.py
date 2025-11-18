#!/usr/bin/env python3
"""Manual verification of parser logic"""

from datetime import datetime

def verify_symbol(symbol: str, expected_expiry: str, description: str):
    """Manually verify the parsing logic for a symbol"""
    print(f"\n{'='*70}")
    print(f"Symbol: {symbol}")
    print(f"Description: {description}")
    print(f"Expected expiry: {expected_expiry}")
    print(f"{'='*70}")

    import re

    # Extract underlying
    underlying_match = re.match(r'^([A-Z]+)', symbol)
    underlying = underlying_match.group(1)
    rest = symbol[underlying_match.end():]

    print(f"Underlying: {underlying}")
    print(f"Rest: {rest}")

    # Check old format
    old_weekly = re.match(r'(\d{2})O(\d{2})(\d{2})', rest)
    if old_weekly:
        yy, mm, dd = old_weekly.groups()
        print(f"✓ Old format: 20{yy}-{mm}-{dd}")
        return

    # Check new format
    new_format = re.match(r'(\d{2})([A-Z]{3})(.+?)(CE|PE)$', rest)
    if new_format:
        yy = new_format.group(1)
        mmm = new_format.group(2)
        middle = new_format.group(3)
        opt_type = new_format.group(4)

        print(f"YY={yy}, MMM={mmm}, Middle='{middle}' (len={len(middle)}), Type={opt_type}")

        month_map = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                     'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
        month = month_map[mmm]
        year = 2000 + int(yy)

        # Check if weekly pattern possible
        if len(middle) >= 5:
            day_str = middle[:2]
            strike_str = middle[2:]

            print(f"\nChecking weekly: day='{day_str}', strike='{strike_str}'")

            if strike_str.isdigit() and len(strike_str) >= 3:
                day = int(day_str)
                if 1 <= day <= 31:
                    try:
                        date = datetime(year, month, day)
                        weekday = date.weekday()
                        weekday_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][weekday]

                        print(f"  Potential date: {date.date()} ({weekday_name})")

                        # Check weekday rules
                        if underlying == 'BANKNIFTY' and weekday == 2:
                            print(f"  ✓ BANKNIFTY + Wednesday = WEEKLY")
                            print(f"  Expiry: {date.date()}")
                            return
                        elif underlying == 'FINNIFTY' and weekday == 1:
                            print(f"  ✓ FINNIFTY + Tuesday = WEEKLY")
                            print(f"  Expiry: {date.date()}")
                            return
                        elif weekday == 3:
                            print(f"  ✓ Thursday = WEEKLY")
                            print(f"  Expiry: {date.date()}")
                            return
                        else:
                            print(f"  ✗ {weekday_name} is not a weekly expiry day")
                            print(f"  → Digits '{day_str}' are part of strike, not a day")
                    except ValueError as e:
                        print(f"  Invalid date: {e}")
        else:
            print(f"\nMiddle length {len(middle)} < 5, no room for DD+strike")

        # Monthly
        print(f"\nTreating as MONTHLY")
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        last_date = datetime(year, month, last_day)

        while last_date.weekday() != 3:  # Find last Thursday
            from datetime import timedelta
            last_date -= timedelta(days=1)

        print(f"  Last Thursday of {month}/{year}: {last_date.date()}")
        print(f"  Expiry: {last_date.date()}")


# Test cases
verify_symbol(
    "NIFTY24OCT19400CE",
    "2024-10-31",
    "Monthly NIFTY - '19' is part of strike, not Oct 19"
)

verify_symbol(
    "BANKNIFTY24DEC0419500CE",
    "2024-12-04",
    "Weekly BANKNIFTY - Dec 4 is Wednesday"
)

verify_symbol(
    "NIFTY24NOV2819500PE",
    "2024-11-28",
    "Weekly NIFTY - Nov 28 is Thursday"
)

verify_symbol(
    "ITC24DEC440CE",
    "2024-12-26",
    "Monthly ITC stock option - 3-digit strike"
)

verify_symbol(
    "NIFTY25O0725",
    "2025-07-25",
    "Old format weekly - explicit date"
)

print("\n" + "="*70)
print("VERIFICATION COMPLETE")
print("="*70)
