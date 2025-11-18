#!/usr/bin/env python3
"""Test missing token cache fix"""
import sys
sys.path.insert(0, '/Users/gogineni/Python/trading-system')

from enhanced_trading_system_complete import DataProvider

print("Testing Missing Token Cache Fix...")
print("=" * 60)

# Create DataProvider without instruments
dp = DataProvider(kite=None, instruments_map={}, use_yf_fallback=False)

print("\n1. First lookup of NIFTY (should log once):")
df1 = dp._kite_only_fetch('NIFTY', '5minute', 30)
print(f"   Cached: {'NIFTY' in dp._missing_token_cache}")
print(f"   Logged: {'NIFTY' in dp._missing_token_logged}")

print("\n2. Second lookup of NIFTY (should use cache, no log):")
df2 = dp._kite_only_fetch('NIFTY', '5minute', 30)
print(f"   Cache hit: {'NIFTY' in dp._missing_token_cache}")

print("\n3. Multiple lookups (should all use cache):")
for i in range(5):
    dp._kite_only_fetch('NIFTY', '5minute', 30)
print(f"   Total logged symbols: {len(dp._missing_token_logged)}")
print(f"   Total cached symbols: {len(dp._missing_token_cache)}")

if len(dp._missing_token_logged) == 1:
    print("\n✅ PASS: Token only logged once despite multiple lookups!")
else:
    print(f"\n❌ FAIL: Expected 1 logged entry, got {len(dp._missing_token_logged)}")

print("\n" + "=" * 60)
print("✅ Test complete!")
