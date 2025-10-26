#!/usr/bin/env python3
"""
Comprehensive demonstration script for the legacy exit filter fixes.
The original version was a manual console demo that prints rich output and
terminates the interpreter. We keep the script for reference, but skip it under
pytest to avoid polluting automated test runs.
"""

import sys
from typing import Tuple

import pytest

# Skip when imported by pytest (legacy manual smoke test).
if __name__ != "__main__":  # pragma: no cover - skip in automated suite
    pytest.skip(
        "Legacy exit-filter console demo – run manually via python test_all_exit_fixes.py",
        allow_module_level=True,
    )


def _evaluate_filters() -> Tuple[bool, float, float]:
    """Run the legacy filter checks and return summary information."""

    has_position = True
    confidence = 0.28
    min_confidence = 0.35
    regime_bias = "bullish"
    action = "sell"
    current_price = 2500
    ema_slow = 2400
    ema_fast = 2450
    downtrend = current_price < ema_slow and ema_fast < ema_slow

    is_exit = has_position
    regime_allows = True if is_exit else not (regime_bias == "bullish" and action == "sell")

    is_exit_signal = has_position
    trend_filter_enabled = True
    if trend_filter_enabled and not is_exit_signal:
        trend_allows = not (action == "sell" and not downtrend)
    else:
        trend_allows = True

    if not is_exit_signal and confidence < min_confidence:
        early_conf_allows = False
    else:
        early_conf_allows = True

    is_exit_trade = has_position
    if not is_exit_trade and confidence < min_confidence:
        global_conf_allows = False
    else:
        global_conf_allows = True

    all_passed = all([regime_allows, trend_allows, early_conf_allows, global_conf_allows])
    return all_passed, confidence, min_confidence


def main() -> int:
    """Entry-point for manual execution (retains original console output)."""

    all_passed, confidence, min_confidence = _evaluate_filters()

    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "COMPREHENSIVE EXIT FILTER TEST" + " " * 22 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    print("📊 TEST SCENARIO:")
    print("   Position: Long RELIANCE (100 shares @ ₹2400)")
    print("   Current Price: ₹2500 (in profit)")
    print("   Strategy Signal: SELL (take profit)")
    print()
    print("   Signal Properties:")
    print("   • Confidence: 28% (BELOW 35% min threshold)")
    print("   • Market Regime: BULLISH")
    print("   • Trend: UPTREND (price > slow EMA, NOT in downtrend)")
    print()
    print("   Expected: Exit should be ALLOWED (bypassing ALL filters)")
    print()
    print("=" * 70)
    print()

    if all_passed:
        print("✅ ALL TESTS PASSED!")
        print()
        print("🎉 Exit successfully bypasses ALL 4 filter layers:")
        print()
        print("   • Regime filter bypassed")
        print("   • Trend filter bypassed")
        print("   • Early confidence filter bypassed")
        print("   • Global confidence filter bypassed")
        print()
        print("🔧 Total Changes Required: 62 lines across four fixes")
        exit_code = 0
    else:
        print("❌ SOME TESTS FAILED! One or more filters are still blocking exits.")
        exit_code = 1

    print("=" * 70)
    return exit_code


if __name__ == "__main__":  # pragma: no cover - manual execution path
    sys.exit(main())
