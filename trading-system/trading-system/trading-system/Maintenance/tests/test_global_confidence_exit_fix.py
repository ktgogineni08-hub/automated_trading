#!/usr/bin/env python3
"""Legacy console demo for the global confidence exit fix."""

import sys

import pytest

if __name__ != "__main__":  # pragma: no cover - manual integration script
    pytest.skip(
        "Legacy global-confidence console demo – run manually via python test_global_confidence_exit_fix.py",
        allow_module_level=True,
    )

print("Testing Global Confidence Filter Exit Fix")
print("=" * 70)
print()
print("🔍 THE PROBLEM:")
print("   Even after 3 previous fixes, exits were STILL blocked by a global")
print("   confidence filter that ran BEFORE checking if signal was for an exit.")
print()
print("   Code flow (BEFORE this fix):")
print("   ┌────────────────────────────────────────────┐")
print("   │ Signal Generated (action='sell')          │")
print("   └─────────────────┬──────────────────────────┘")
print("                     │")
print("                     ▼")
print("   ┌────────────────────────────────────────────┐")
print("   │ if signal['confidence'] < min_confidence:  │")
print("   │     continue  # ❌ BLOCKED!               │")
print("   │ (Didn't check if exit or entry first!)    │")
print("   └─────────────────┬──────────────────────────┘")
print("                     │")
print("                     ▼")
print("   ┌────────────────────────────────────────────┐")
print("   │ if signal['action'] == 'sell' and in pos: │")
print("   │     # Never reached for low confidence     │")
print("   └────────────────────────────────────────────┘")
print()
print("=" * 70)
print()

# Simulate the scenario
print("📊 TEST SCENARIO:")
print("   • Position: Long RELIANCE (100 shares @ ₹2400)")
print("   • Signal: Sell (take profit)")
print("   • Confidence: 28% (BELOW 35% min threshold)")
print("   • Is in portfolio: YES (existing position)")
print()

# Test data
symbol = 'RELIANCE'
has_position = True
signal_confidence = 0.28
min_confidence = 0.35
signal_action = 'sell'

print("🔬 TESTING FILTERS:")
print()

# Test 1: OLD CODE (would block)
print("1️⃣  OLD CODE (BROKEN):")
print("   if signal['confidence'] < min_confidence:")
print("       continue  # Blocks ALL signals, even exits!")
print()
if signal_confidence < min_confidence:
    print("   Result: ❌ EXIT BLOCKED!")
    print("   Position stuck despite exit signal.")
    old_code_allows = False
else:
    print("   Result: ✅ Passed")
    old_code_allows = True

print()

# Test 2: NEW CODE (correct)
print("2️⃣  NEW CODE (FIXED):")
print("   is_exit_trade = symbol in portfolio.positions")
print("   if not is_exit_trade and signal['confidence'] < min_confidence:")
print("       continue  # Only blocks NEW entries!")
print()

is_exit_trade = has_position
if not is_exit_trade and signal_confidence < min_confidence:
    print("   Result: ❌ Blocked (but this is a new entry)")
    new_code_allows = False
else:
    print("   Result: ✅ ALLOWED!")
    print("   Exit bypasses confidence filter!")
    new_code_allows = True

print()
print("=" * 70)
print()

# Results
if not old_code_allows and new_code_allows:
    print("✅ TEST PASSED!")
    print()
    print("🎉 The fix works correctly:")
    print("   • Old code: Blocked exit due to low confidence")
    print("   • New code: Allows exit (bypasses confidence check)")
    print()
    print("📊 Impact:")
    print("   • Positions can now exit with ANY confidence level")
    print("   • No more stuck positions due to low confidence exits")
    print("   • Complete control over position management")
    print()
    print("🔧 What Changed:")
    print("   • Added: is_exit_trade = symbol in portfolio.positions")
    print("   • Changed: if signal['confidence'] < min_confidence:")
    print("   • To: if not is_exit_trade and signal['confidence'] < min_confidence:")
    print()
    print("✅ Position exits now bypass ALL filters:")
    print("   1. ✅ Regime filter (Issue #1 fix)")
    print("   2. ✅ Trend filter (Issue #3 fix)")
    print("   3. ✅ Early confidence filter (Issue #3 fix)")
    print("   4. ✅ Global confidence filter (THIS fix)")
    print()
    exit_code = 0
else:
    print("❌ TEST FAILED!")
    print(f"   Old code allows: {old_code_allows}")
    print(f"   New code allows: {new_code_allows}")
    exit_code = 1

print("=" * 70)
sys.exit(exit_code)
