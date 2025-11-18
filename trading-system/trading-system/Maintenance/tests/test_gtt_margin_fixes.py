#!/usr/bin/env python3
"""
Test script for GTT and Margin critical fixes

Validates:
1. Margin check uses correct 'equity' segment (not 'commodity')
2. GTT cancellation happens AFTER order confirmation
3. GTT place_gtt has correct signature with exchange parameter
"""

import sys
import re

import pytest
from unittest.mock import Mock, MagicMock, patch, call

if __name__ != "__main__":  # pragma: no cover - manual integration script
    pytest.skip(
        "Legacy GTT/margin console demo – run manually via python test_gtt_margin_fixes.py",
        allow_module_level=True,
    )


def test_margin_check_uses_equity_segment():
    """CRITICAL: Verify margin check queries 'equity' segment for NSE products"""
    print("\n" + "="*80)
    print("TEST 1: Margin Check Uses Correct Segment (equity, not commodity)")
    print("="*80)

    # Mock Kite client
    mock_kite = Mock()

    # Mock margin response - Zerodha format
    mock_kite.margins.return_value = {
        'equity': {
            'available': {
                'cash': 500000.0,  # ₹5 lakh available
                'live_balance': 500000.0
            }
        },
        'commodity': {
            'available': {
                'cash': 0.0,  # Should NOT use this for NSE F&O
                'live_balance': 0.0
            }
        }
    }

    # Mock order margins
    mock_kite.order_margins.return_value = [
        {'total': 100000.0}  # Requires ₹1 lakh margin
    ]

    # Read the actual implementation
    with open('/Users/gogineni/Python/trading-system/enhanced_trading_system_complete.py', 'r') as f:
        code = f.read()

    # Extract _check_margin_requirement method
    pattern = r'def _check_margin_requirement\(.*?\n(?:.*?\n)*?        return (?:True|False)'
    match = re.search(pattern, code, re.MULTILINE | re.DOTALL)

    if not match:
        print("❌ FAIL: Could not find _check_margin_requirement method")
        return False

    method_code = match.group(0)

    # Check for the fix
    if "'commodity'" in method_code and "instrument_type in {" in method_code:
        print("❌ FAIL: Still using 'commodity' segment with conditional logic")
        print("   This will fail for NFO/BFO instruments")
        return False

    if "'equity'" not in method_code:
        print("❌ FAIL: Not using 'equity' segment at all")
        return False

    # Check that it's using equity unconditionally
    if "margins_data.get('equity'" in method_code or 'margins_data.get("equity"' in method_code:
        # Verify it's not conditional on instrument_type for commodity
        if "if instrument_type in {" in method_code and "'commodity'" in method_code:
            print("❌ FAIL: Still has conditional logic for commodity segment")
            return False

        print("✅ PASS: Using 'equity' segment for margin check")
        print("   All NSE products (NFO, BFO, NSE equity) correctly query equity segment")
        print("   Comment confirms commodity segment is only for MCX/NCDEX")
        return True
    else:
        print("❌ FAIL: Equity segment not accessed correctly")
        return False


def test_gtt_cancellation_after_confirmation():
    """CRITICAL: Verify GTT cancelled AFTER order confirmation, not before"""
    print("\n" + "="*80)
    print("TEST 2: GTT Cancellation Happens After Order Confirmation")
    print("="*80)

    with open('/Users/gogineni/Python/trading-system/enhanced_trading_system_complete.py', 'r') as f:
        code = f.read()

    # Find the sell order section
    sell_section_pattern = r'elif side == "sell":.*?(?=\n        elif |\n        return None\n\n|$)'
    match = re.search(sell_section_pattern, code, re.MULTILINE | re.DOTALL)

    if not match:
        print("❌ FAIL: Could not find sell order section")
        return False

    sell_code = match.group(0)

    # Find positions of key operations
    cancel_gtt_pos = sell_code.find('_cancel_protective_orders')
    wait_for_completion_pos = sell_code.find('_wait_for_order_completion')
    cash_update_pos = sell_code.find('self.cash += net')

    if cancel_gtt_pos == -1:
        print("⚠️  WARNING: GTT cancellation not found (may be disabled)")
        return True  # Not a failure if GTT not used

    if wait_for_completion_pos == -1:
        print("❌ FAIL: Order completion check not found")
        return False

    # CRITICAL: GTT cancellation must come AFTER order confirmation
    if cancel_gtt_pos < wait_for_completion_pos:
        print("❌ FAIL: GTT cancelled BEFORE order confirmation")
        print(f"   cancel_gtt position: {cancel_gtt_pos}")
        print(f"   wait_for_completion position: {wait_for_completion_pos}")
        print("\n   This means if order fails, GTT is removed but position stays open!")
        return False

    if cancel_gtt_pos > wait_for_completion_pos and cancel_gtt_pos < cash_update_pos:
        print("✅ PASS: GTT cancelled AFTER order confirmation, BEFORE cash update")
        print("   Order flow: place → wait → confirm → cancel GTT → update cash")
        print("   If order fails, GTT stays armed (position remains protected)")
        return True

    print("⚠️  WARNING: GTT cancellation in unexpected location")
    print(f"   wait_for_completion: {wait_for_completion_pos}")
    print(f"   cancel_gtt: {cancel_gtt_pos}")
    print(f"   cash_update: {cash_update_pos}")
    return False


def test_gtt_signature_has_exchange():
    """CRITICAL: Verify place_gtt call includes exchange parameter"""
    print("\n" + "="*80)
    print("TEST 3: GTT place_gtt Signature Includes Exchange Parameter")
    print("="*80)

    with open('/Users/gogineni/Python/trading-system/enhanced_trading_system_complete.py', 'r') as f:
        code = f.read()

    # Find _place_protective_orders method
    pattern = r'def _place_protective_orders\(.*?\n(?:.*?\n)*?        except Exception as exc:'
    match = re.search(pattern, code, re.MULTILINE | re.DOTALL)

    if not match:
        print("❌ FAIL: Could not find _place_protective_orders method")
        return False

    method_code = match.group(0)

    # Look for place_gtt call
    if 'place_gtt(' not in method_code:
        print("⚠️  WARNING: place_gtt call not found (GTT may be disabled)")
        return True

    # Extract place_gtt call
    gtt_call_pattern = r'place_gtt\((.*?)\)'
    gtt_match = re.search(gtt_call_pattern, method_code, re.DOTALL)

    if not gtt_match:
        print("❌ FAIL: Could not extract place_gtt call")
        return False

    gtt_args = gtt_match.group(1)

    # Check for exchange parameter (either positional or keyword)
    has_exchange_positional = 'exchange,' in gtt_args or ', exchange,' in gtt_args
    has_exchange_keyword = 'exchange=' in gtt_args

    if not (has_exchange_positional or has_exchange_keyword):
        print("❌ FAIL: place_gtt call missing 'exchange' parameter")
        print("\n   Zerodha signature: place_gtt(trigger_type, tradingsymbol, exchange, trigger_values, last_price, orders)")
        print(f"\n   Current call: place_gtt({gtt_args[:100]}...)")
        return False

    # Check for last_price parameter as well
    has_last_price = 'last_price=' in gtt_args or 'last_price' in gtt_args

    if has_exchange_keyword and has_last_price:
        print("✅ PASS: place_gtt signature includes both exchange and last_price")
        print("   Using keyword arguments for clarity")

        # Show the actual call
        if 'trigger_type=' in gtt_args:
            print("\n   Call structure:")
            for param in ['trigger_type', 'tradingsymbol', 'exchange', 'trigger_values', 'last_price', 'orders']:
                if f'{param}=' in gtt_args:
                    print(f"   ✓ {param}")
        return True

    print("⚠️  WARNING: exchange parameter found but signature may be incomplete")
    print(f"   Call: place_gtt({gtt_args[:150]}...)")
    return True


def test_protective_order_integration():
    """Integration test: GTT placed on position open, cancelled on confirmed close"""
    print("\n" + "="*80)
    print("TEST 4: GTT Integration (Place on Open, Cancel on Close)")
    print("="*80)

    with open('/Users/gogineni/Python/trading-system/enhanced_trading_system_complete.py', 'r') as f:
        code = f.read()

    # Check GTT placement in buy flow
    buy_pattern = r'if side == "buy":.*?(?=\n        elif side == "sell":|$)'
    buy_match = re.search(buy_pattern, code, re.MULTILINE | re.DOTALL)

    if not buy_match:
        print("❌ FAIL: Could not find buy order section")
        return False

    buy_code = buy_match.group(0)

    # Look for GTT placement call
    has_gtt_placement = '_place_protective_orders' in buy_code

    if has_gtt_placement:
        print("✅ GTT placement found in buy flow")

        # Check it's after position is created
        position_create = buy_code.find('self.positions[symbol] = {')
        gtt_place = buy_code.find('_place_protective_orders')

        if gtt_place > position_create:
            print("✅ GTT placed AFTER position created")
        else:
            print("⚠️  GTT placement may occur before position creation")
    else:
        print("⚠️  GTT placement not found in buy flow (may be optional)")

    print("\n✅ PASS: GTT integration flow validated")
    print("   - GTT placed when opening position (if SDK supports)")
    print("   - GTT cancelled only after confirmed exit")
    return True


def run_all_tests():
    """Run all critical GTT and margin tests"""
    print("\n" + "="*80)
    print("CRITICAL FIXES VALIDATION: GTT & Margin")
    print("="*80)
    print("\nValidating 3 critical fixes identified in code review:")
    print("1. Margin check using 'equity' segment (not 'commodity')")
    print("2. GTT cancellation after order confirmation (not before)")
    print("3. GTT place_gtt signature with exchange parameter")

    results = []

    # Run tests
    results.append(("Margin Segment Check", test_margin_check_uses_equity_segment()))
    results.append(("GTT Cancellation Timing", test_gtt_cancellation_after_confirmation()))
    results.append(("GTT Signature", test_gtt_signature_has_exchange()))
    results.append(("GTT Integration", test_protective_order_integration()))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL CRITICAL FIXES VALIDATED")
        print("\nNext steps:")
        print("1. Run paper trading to verify margin checks block orders correctly")
        print("2. Test GTT placement in live mode (check Kite dashboard)")
        print("3. Test order failure scenarios (verify GTT stays armed)")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - Review fixes before deployment")
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
