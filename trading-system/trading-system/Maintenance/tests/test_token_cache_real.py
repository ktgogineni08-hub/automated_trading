#!/usr/bin/env python3
"""Test missing token cache with realistic scenario"""
import sys
sys.path.insert(0, '/Users/gogineni/Python/trading-system')

from enhanced_trading_system_complete import DataProvider

print("Testing Missing Token Cache (Realistic Scenario)...")
print("=" * 60)

# Create mock kite object (just needs to exist)
class MockKite:
    pass

# Create DataProvider WITH kite but WITHOUT NIFTY token
# This simulates the actual issue: equity instruments don't have index tokens
dp = DataProvider(kite=MockKite(), instruments_map={'RELIANCE': 123}, use_yf_fallback=False)

print("\n1. First lookup of NIFTY (no token, should log once):")
try:
    df1 = dp._kite_only_fetch('NIFTY', '5minute', 30)
except:
    pass  # Expected to fail
print(f"   Cached: {'NIFTY' in dp._missing_token_cache}")
print(f"   Logged: {'NIFTY' in dp._missing_token_logged}")

print("\n2. Second lookup of NIFTY (should use cache):")
try:
    df2 = dp._kite_only_fetch('NIFTY', '5minute', 30)
except:
    pass
print(f"   Still cached: {'NIFTY' in dp._missing_token_cache}")

print("\n3. Five more lookups:")
for i in range(5):
    try:
        dp._kite_only_fetch('NIFTY', '5minute', 30)
    except:
        pass

print(f"\n   Total symbols logged: {len(dp._missing_token_logged)}")
print(f"   Total symbols cached: {len(dp._missing_token_cache)}")

if 'NIFTY' in dp._missing_token_cache and len(dp._missing_token_logged) == 1:
    print("\n✅ PASS: NIFTY cached and logged only once!")
else:
    print(f"\n❌ Unexpected: cache={len(dp._missing_token_cache)}, logged={len(dp._missing_token_logged)}")

print("\n" + "=" * 60)
print("✅ Test complete!")
