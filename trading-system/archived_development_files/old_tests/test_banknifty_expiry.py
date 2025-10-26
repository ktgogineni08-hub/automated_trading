#!/usr/bin/env python3
"""Check BANKNIFTY expiry pattern"""

from datetime import datetime

# Check what day of week various dates are
dates_to_check = [
    ("2024-12-04", "BANKNIFTY24DEC04 expiry"),
    ("2024-12-26", "Monthly Dec 2024 last Thursday"),
    ("2024-11-28", "NIFTY24NOV28 expiry"),
]

weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

for date_str, description in dates_to_check:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = weekdays[dt.weekday()]
    print(f"{date_str} ({description}): {weekday}")

print("\n" + "="*60)
print("FINDING:")
print("- NIFTY weekly options expire on Thursdays")
print("- BANKNIFTY weekly options expire on Wednesdays!")
print("="*60)
