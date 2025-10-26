#!/usr/bin/env python3
"""Legacy console demo for the option expiry parser."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Tuple

import pytest

# Ensure project root on path for manual runs
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if __name__ != "__main__":  # pragma: no cover - integration demo
    pytest.skip(
        "Legacy parser console demo – run manually via python test_final_parser.py",
        allow_module_level=True,
    )

from enhanced_trading_system_complete import UnifiedPortfolio


def run_parser_case(symbol: str, test_date_str: str, expected: bool, description: str) -> bool:
    """Test parser on a specific symbol and date"""
    portfolio = UnifiedPortfolio(initial_cash=100000, trading_mode='paper', silent=True)

    test_date = datetime.strptime(test_date_str, "%Y-%m-%d").date()

    # Monkey patch datetime in the method
    import enhanced_trading_system_complete
    original_datetime = enhanced_trading_system_complete.datetime

    class MockDatetime:
        @staticmethod
        def now():
            class MockNow:
                @staticmethod
                def date():
                    return test_date
            return MockNow()

        def __call__(self, *args, **kwargs):
            return original_datetime(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(original_datetime, name)

    enhanced_trading_system_complete.datetime = MockDatetime()

    try:
        result = portfolio._is_expiring_today(symbol)
        weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][test_date.weekday()]
        status = "✓" if result == expected else "✗"
        print(f"{status} {description}")
        print(f"  Symbol: {symbol}")
        print(f"  Date: {test_date} ({weekday})")
        print(f"  Expected: {expected}, Got: {result}")

        if result != expected:
            print("  ⚠️  MISMATCH!")
            return False
        return True
    finally:
        enhanced_trading_system_complete.datetime = original_datetime


def main() -> int:
    """Execute the legacy console demo."""

    print("COMPREHENSIVE PARSER TEST")
    print("=" * 80)

    cases = [
        ("NIFTY24OCT19400CE", "2024-10-31", True, "NIFTY monthly on last Thursday"),
        ("NIFTY24OCT19400CE", "2024-10-19", False, "NIFTY monthly NOT on expiry (19 is Saturday, part of strike)"),
        ("NIFTY24NOV2819500PE", "2024-11-28", True, "NIFTY weekly on Thursday Nov 28"),
        ("NIFTY24NOV2819500PE", "2024-11-27", False, "NIFTY weekly NOT on expiry day"),
        ("BANKNIFTY24DEC0419500CE", "2024-12-04", True, "BANKNIFTY weekly on Wednesday Dec 4"),
        ("BANKNIFTY24DEC0419500CE", "2024-12-05", False, "BANKNIFTY weekly NOT on expiry day"),
        ("ITC24DEC440CE", "2024-12-26", True, "ITC monthly on last Thursday"),
        ("ITC24DEC440CE", "2024-12-04", False, "ITC monthly NOT on expiry"),
        ("NIFTY25O0725", "2025-07-25", True, "Old format NIFTY on Jul 25"),
        ("NIFTY25O0725", "2025-07-24", False, "Old format NIFTY NOT on expiry"),
    ]

    all_passed = True
    for idx, case in enumerate(cases, start=1):
        if idx in {1, 3, 5, 7, 9}:
            print()
            section = (idx + 1) // 2
            titles = [
                "Monthly options",
                "NIFTY weekly options (Thursday)",
                "BANKNIFTY weekly options (Wednesday)",
                "Stock options (monthly)",
                "Old format weekly",
            ]
            print(f"{section}. {titles[section - 1]}:")
        all_passed &= run_parser_case(*case)

    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
        return 0

    print("❌ SOME TESTS FAILED!")
    return 1


if __name__ == "__main__":  # pragma: no cover - manual execution path
    sys.exit(main())
