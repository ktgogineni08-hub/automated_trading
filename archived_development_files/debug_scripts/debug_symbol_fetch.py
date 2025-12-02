#!/usr/bin/env python3
"""Debug script to test symbol fetching for NIFTY25O1425550PE"""

# The symbol format analysis
symbol = "NIFTY25O1425550PE"

print("=" * 80)
print("SYMBOL FORMAT ANALYSIS")
print("=" * 80)
print(f"Symbol: {symbol}")
print()

# Parse the symbol
import re

# Check if it matches legacy format
legacy_match = re.match(r'^([A-Z]+)(\d{2})O(\d{2})(\d{2})(\d+)(CE|PE)$', symbol)

if legacy_match:
    print("✅ Matches LEGACY format: UNDERLYING + YYOmmdd + STRIKE + CE/PE")
    print()
    print(f"Underlying: {legacy_match.group(1)}")
    print(f"Year: 20{legacy_match.group(2)}")
    print(f"Month: {legacy_match.group(3)}")
    print(f"Day: {legacy_match.group(4)}")
    print(f"Strike: {legacy_match.group(5)}")
    print(f"Type: {legacy_match.group(6)}")
    print()
    print(f"Expiry Date: 2025-10-14 (October 14, 2025)")
else:
    print("❌ Does NOT match legacy format")

print()
print("=" * 80)
print("KITE API SYMBOL FORMAT")
print("=" * 80)
print("For Kite quote API, the symbol should be:")
print(f"  NFO:{symbol}")
print()
print("Expected instrument lookup:")
print(f"  tradingsymbol: {symbol}")
print(f"  exchange: NFO")
print(f"  instrument_type: PE")
print(f"  strike: 25550")
print(f"  expiry: 2025-10-14")
print()

print("=" * 80)
print("POTENTIAL ISSUES")
print("=" * 80)
print("1. Symbol not found in instruments cache")
print("   - Cache may be stale")
print("   - Symbol may be using different format in Kite")
print()
print("2. Quote fetch using wrong format")
print("   - Should use: NFO:NIFTY25O1425550PE")
print("   - NOT just: NIFTY25O1425550PE")
print()
print("3. Price from wrong field")
print("   - Should use: quote['last_price']")
print("   - NOT: quote['ohlc']['close'] or bid/ask")
print()

print("=" * 80)
print("DEBUGGING STEPS")
print("=" * 80)
print("1. Check if symbol exists in Kite instruments:")
print("   instruments = kite.instruments('NFO')")
print(f"   found = [i for i in instruments if i['tradingsymbol'] == '{symbol}']")
print()
print("2. Try fetching quote directly:")
print(f"   quote = kite.quote(['NFO:{symbol}'])")
print(f"   price = quote['NFO:{symbol}']['last_price']")
print()
print("3. Check what system is using:")
print("   - Look at logs for quote fetch")
print("   - Check if exchange prefix is added")
print("   - Verify LTP is being used")
print()
