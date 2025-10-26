#!/usr/bin/env python3
"""Test FINNIFTY monthly expiry detection"""

from datetime import datetime
import calendar

def find_last_weekday(year: int, month: int, target_weekday: int) -> datetime:
    """Find last occurrence of target_weekday in given month"""
    last_day = calendar.monthrange(year, month)[1]
    dt = datetime(year, month, last_day)
    while dt.weekday() != target_weekday:
        from datetime import timedelta
        dt -= timedelta(days=1)
    return dt

# Test FINNIFTY monthly expiry for Oct 2024
print("FINNIFTY Monthly Expiry Schedule")
print("=" * 70)

# October 2024
oct_2024_last_tuesday = find_last_weekday(2024, 10, 1)  # Tuesday = 1
oct_2024_last_thursday = find_last_weekday(2024, 10, 3)  # Thursday = 3

print(f"\nOctober 2024:")
print(f"  Last Tuesday:  {oct_2024_last_tuesday.date()} (FINNIFTY monthly)")
print(f"  Last Thursday: {oct_2024_last_thursday.date()} (NIFTY monthly)")
print(f"  Difference: {(oct_2024_last_thursday - oct_2024_last_tuesday).days} days")

# Verify
weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
print(f"\nVerification:")
print(f"  Oct {oct_2024_last_tuesday.day}, 2024 is a {weekdays[oct_2024_last_tuesday.weekday()]} ✓")
print(f"  Oct {oct_2024_last_thursday.day}, 2024 is a {weekdays[oct_2024_last_thursday.weekday()]} ✓")

print("\n" + "=" * 70)
print("CRITICAL: FINNIFTY24OCT19000CE must expire on Oct 29 (Tue), NOT Oct 31 (Thu)")
print("=" * 70)

# Test more months
print("\nFINNIFTY Monthly Expiries for 2024-2025:")
print("-" * 70)

test_months = [
    (2024, 10, "Oct 2024"),
    (2024, 11, "Nov 2024"),
    (2024, 12, "Dec 2024"),
    (2025, 1, "Jan 2025"),
]

for year, month, label in test_months:
    last_tuesday = find_last_weekday(year, month, 1)
    print(f"{label}: {last_tuesday.date()} ({weekdays[last_tuesday.weekday()]})")

print("\n" + "=" * 70)
print("BANKNIFTY and FINNIFTY Monthly Schedule:")
print("=" * 70)

print("\nOctober 2024:")
banknifty_expiry = find_last_weekday(2024, 10, 2)  # Wednesday
finnifty_expiry = find_last_weekday(2024, 10, 1)  # Tuesday
nifty_expiry = find_last_weekday(2024, 10, 3)  # Thursday

print(f"  FINNIFTY24OCT19000CE  → {finnifty_expiry.date()} ({weekdays[finnifty_expiry.weekday()]})")
print(f"  BANKNIFTY24OCT45000CE → {banknifty_expiry.date()} ({weekdays[banknifty_expiry.weekday()]})")
print(f"  NIFTY24OCT19400CE     → {nifty_expiry.date()} ({weekdays[nifty_expiry.weekday()]})")
