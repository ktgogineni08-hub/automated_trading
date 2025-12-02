#!/usr/bin/env python3
"""Test expiry date extraction to identify the bug"""

import re
from datetime import datetime

def extract_expiry_date_CURRENT_BUGGY(symbol: str):
    """CURRENT BUGGY VERSION - extracts wrong date"""
    try:
        # This matches FIRST occurrence of DD+MMM (wrong!)
        match = re.search(r'(\d{2})([A-Z]{3})', symbol)
        if not match:
            return None

        day = int(match.group(1))
        month_abbr = match.group(2)
        current_year = datetime.now().year

        month_map = {
            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
        }

        month = month_map.get(month_abbr)
        if not month:
            return None

        expiry_date = datetime(current_year, month, day)
        return expiry_date
    except Exception as e:
        print(f"Error: {e}")
        return None

# Test cases
test_symbols = [
    "NIFTY25O0725150CE",      # Oct 25, 2025 (weekly)
    "NIFTY24JAN19000CE",      # Jan 2024 monthly
    "BANKNIFTY24125WED40000PE",  # Jan 25, 2024 (weekly)
    "FINNIFTY24FEB18000CE",   # Feb 2024 monthly
]

print("=" * 80)
print("TESTING CURRENT BUGGY VERSION")
print("=" * 80)

for symbol in test_symbols:
    result = extract_expiry_date_CURRENT_BUGGY(symbol)
    print(f"\nSymbol: {symbol}")
    print(f"Extracted: {result}")
    print(f"Expected: Should extract the actual expiry date from symbol")

    # Show what the regex is actually matching
    match = re.search(r'(\d{2})([A-Z]{3})', symbol)
    if match:
        print(f"Regex matched: '{match.group(0)}' -> day={match.group(1)}, month={match.group(2)}")
        print(f"❌ BUG: This is matching the YEAR part (25=2025), not the expiry date!")

print("\n" + "=" * 80)
print("EXPECTED BEHAVIOR:")
print("=" * 80)
print("NIFTY25O0725150CE should parse as:")
print("  - 25 = year 2025")
print("  - O07 = Oct 07 (weekly expiry)")
print("  - 25150 = strike 25150")
print("  - CE = Call Option")
print("\nExpiry Date: October 7, 2025")
