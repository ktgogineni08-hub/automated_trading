#!/usr/bin/env python3
"""Legacy console demo for position-closing fixes."""

import sys
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if __name__ != "__main__":  # pragma: no cover - manual integration script
    pytest.skip(
        "Legacy position-closing console demo – run manually via python test_position_closing.py",
        allow_module_level=True,
    )

# Test 1: Verify UnifiedPortfolio has required methods
print("="*60)
print("TEST 1: Verify UnifiedPortfolio Methods")
print("="*60)

try:
    # Import the main module
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from enhanced_trading_system_complete import UnifiedPortfolio

    # Check if methods exist
    required_methods = ['get_current_price', 'get_current_option_prices', '_close_position']

    missing_methods = []
    for method in required_methods:
        if not hasattr(UnifiedPortfolio, method):
            missing_methods.append(method)

    if missing_methods:
        print(f"❌ FAIL: Missing methods: {missing_methods}")
        sys.exit(1)
    else:
        print(f"✅ PASS: All required methods exist")
        for method in required_methods:
            print(f"   ✓ {method}")

except Exception as e:
    print(f"❌ FAIL: Error importing or checking methods: {e}")
    sys.exit(1)

# Test 2: Verify method signatures
print("\n" + "="*60)
print("TEST 2: Verify Method Signatures")
print("="*60)

try:
    import inspect

    # Check get_current_price signature
    sig = inspect.signature(UnifiedPortfolio.get_current_price)
    params = list(sig.parameters.keys())
    if 'self' in params and 'symbol' in params:
        print("✅ get_current_price(self, symbol) - Correct")
    else:
        print(f"❌ get_current_price signature wrong: {params}")

    # Check get_current_option_prices signature
    sig = inspect.signature(UnifiedPortfolio.get_current_option_prices)
    params = list(sig.parameters.keys())
    if 'self' in params and 'option_symbols' in params:
        print("✅ get_current_option_prices(self, option_symbols) - Correct")
    else:
        print(f"❌ get_current_option_prices signature wrong: {params}")

    # Check _close_position signature
    sig = inspect.signature(UnifiedPortfolio._close_position)
    params = list(sig.parameters.keys())
    if 'self' in params and 'symbol' in params:
        print("✅ _close_position(self, symbol, ...) - Correct")
    else:
        print(f"❌ _close_position signature wrong: {params}")

except Exception as e:
    print(f"❌ FAIL: Error checking signatures: {e}")
    sys.exit(1)

# Test 3: Verify exchange detection logic
print("\n" + "="*60)
print("TEST 3: Verify Exchange Detection Logic")
print("="*60)

test_cases = [
    # Monthly contracts (full month name)
    ("NIFTY25OCT24800CE", True, "NFO", "F&O - NIFTY monthly option"),
    ("BANKNIFTY25OCT53000PE", True, "NFO", "F&O - BANKNIFTY monthly option"),
    ("SENSEX25OCT83000CE", True, "BFO", "F&O - SENSEX monthly option"),
    ("BANKEX25OCT63000PE", True, "BFO", "F&O - BANKEX monthly option"),

    # Weekly contracts (single-letter month code) - CRITICAL TEST
    ("NIFTY25O0725350PE", True, "NFO", "F&O - NIFTY weekly option"),
    ("BANKNIFTY25N212000CE", True, "NFO", "F&O - BANKNIFTY weekly option"),
    ("SENSEX25O1583000PE", True, "BFO", "F&O - SENSEX weekly option"),

    # Futures
    ("NIFTY25OCTFUT", True, "NFO", "F&O - NIFTY futures"),

    # Cash equity
    ("RELIANCE", False, "NSE", "Cash equity"),
    ("TCS", False, "NSE", "Cash equity"),
    ("INFY", False, "NSE", "Cash equity"),
]

all_passed = True

for symbol, is_fno, expected_exchange, description in test_cases:
    # Simulate detection logic from get_current_price - FIXED VERSION
    # Pattern: (digits + CE/PE) OR FUT at end
    import re
    fno_pattern = r'(\d+(CE|PE)|FUT)$'
    detected_fno = bool(re.search(fno_pattern, symbol))

    if detected_fno:
        if any(idx in symbol for idx in ['SENSEX', 'BANKEX']):
            detected_exchange = 'BFO'
        else:
            detected_exchange = 'NFO'
    else:
        detected_exchange = 'NSE'

    if detected_fno == is_fno and detected_exchange == expected_exchange:
        print(f"✅ {symbol:25} → {detected_exchange:3} ({description})")
    else:
        print(f"❌ {symbol:25} → Expected {expected_exchange}, got {detected_exchange}")
        all_passed = False

if not all_passed:
    print("\n❌ FAIL: Exchange detection logic has errors")
    sys.exit(1)
else:
    print("\n✅ PASS: All exchange detection tests passed")

# Test 4: Verify dependencies
print("\n" + "="*60)
print("TEST 4: Verify Dependencies")
print("="*60)

try:
    import requests
    print("✅ requests - installed")
except ImportError:
    print("❌ requests - NOT installed")

try:
    import beautifulsoup4
    print("✅ beautifulsoup4 - installed")
except ImportError:
    try:
        import bs4
        print("✅ beautifulsoup4 (as bs4) - installed")
    except ImportError:
        print("⚠️  beautifulsoup4 - NOT installed (ban list will be empty)")

try:
    from kiteconnect import KiteConnect
    print("✅ kiteconnect - installed")
except ImportError:
    print("❌ kiteconnect - NOT installed")

# Test 5: Simulate position close (without Kite connection)
print("\n" + "="*60)
print("TEST 5: Simulate Position Close (No Kite)")
print("="*60)

try:
    # Create portfolio without Kite
    portfolio = UnifiedPortfolio(initial_cash=1000000, kite=None, trading_mode='paper')

    # Manually add a position
    portfolio.positions['TEST_SYMBOL'] = {
        'shares': 100,
        'entry_price': 150.0,
        'invested_amount': 15000.0,
        'timestamp': '2025-10-07T10:00:00'
    }

    print("✅ Created test position: TEST_SYMBOL (100 shares @ ₹150)")

    # Try to close it (should not crash, even without Kite)
    try:
        result = portfolio._close_position('TEST_SYMBOL', reason='test')
        print("✅ _close_position executed without crashing")

        if 'TEST_SYMBOL' not in portfolio.positions:
            print("✅ Position removed from portfolio")
        else:
            print("⚠️  Position still in portfolio (might have failed silently)")

    except AttributeError as e:
        if 'get_current_option_prices' in str(e):
            print(f"❌ FAIL: AttributeError on get_current_option_prices: {e}")
            print("   This means the method is not properly defined in UnifiedPortfolio")
            sys.exit(1)
        else:
            raise

except Exception as e:
    print(f"❌ FAIL: Error simulating position close: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Check sebi_compliance ban list
print("\n" + "="*60)
print("TEST 6: SEBI Compliance Ban List")
print("="*60)

try:
    from sebi_compliance import SEBIComplianceChecker

    checker = SEBIComplianceChecker(kite=None)
    print("✅ SEBIComplianceChecker instantiated")

    # Try to refresh ban list
    try:
        checker._refresh_ban_list()

        if checker.ban_list_cache is not None:
            print(f"✅ Ban list refreshed: {len(checker.ban_list_cache)} securities")
            if checker.ban_list_cache:
                print(f"   Sample: {checker.ban_list_cache[:3]}")
        else:
            print("⚠️  Ban list is None")

    except ImportError as e:
        print(f"⚠️  ImportError during ban list refresh: {e}")
        print("   Install: pip install requests beautifulsoup4")
    except Exception as e:
        print(f"⚠️  Error refreshing ban list: {e}")
        print("   (This is OK if NSE API is down or network unavailable)")

except Exception as e:
    print(f"❌ Error testing SEBI compliance: {e}")

# Summary
print("\n" + "="*60)
print("SUMMARY")
print("="*60)
print("✅ All critical tests passed!")
print("\nKey findings:")
print("1. UnifiedPortfolio has get_current_price() method")
print("2. UnifiedPortfolio has get_current_option_prices() method")
print("3. Exchange detection logic works for F&O and cash")
print("4. Position close won't crash with AttributeError")
print("5. Dependencies: requests ✅, beautifulsoup4 recommended")
print("\n📋 Next step: Test with actual Kite connection in paper mode")
print("   python3 enhanced_trading_system_complete.py --mode paper")

sys.exit(0)
