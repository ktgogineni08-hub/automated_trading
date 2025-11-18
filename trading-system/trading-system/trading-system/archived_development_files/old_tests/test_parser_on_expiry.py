#!/usr/bin/env python3
"""Test _is_expiring_today by mocking datetime to simulate expiry dates"""

from datetime import datetime, date
import sys
import os
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_on_specific_date(test_date: date, symbol: str, expected_result: bool, description: str):
    """Test parser on a specific date by mocking datetime.now()"""

    # Mock datetime.now() to return our test date
    with patch('enhanced_trading_system_complete.datetime') as mock_datetime:
        # Set up the mock
        mock_datetime.now.return_value = datetime.combine(test_date, datetime.min.time())
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        from enhanced_trading_system_complete import UnifiedPortfolio
        portfolio = UnifiedPortfolio(initial_cash=100000, trading_mode='paper', silent=True)

        result = portfolio._is_expiring_today(symbol)

        status = "✓" if result == expected_result else "✗"
        print(f"{status} {symbol} on {test_date}")
        print(f"  {description}")
        print(f"  Expected: {expected_result}, Got: {result}")

        if result != expected_result:
            print(f"  ⚠️  MISMATCH!")
            return False
        return True

def main():
    print("Testing _is_expiring_today with mocked dates")
    print("=" * 80)

    all_passed = True

    # Test 1: Monthly option on its expiry day (Oct 31, 2024 = last Thursday of Oct)
    print("\n1. Monthly NIFTY option on expiry day:")
    all_passed &= test_on_specific_date(
        date(2024, 10, 31),
        "NIFTY24OCT19400CE",
        True,
        "Oct 31, 2024 is last Thursday → should return True"
    )

    # Test 2: Monthly option NOT on expiry day
    print("\n2. Monthly NIFTY option on Oct 19 (NOT expiry):")
    all_passed &= test_on_specific_date(
        date(2024, 10, 19),
        "NIFTY24OCT19400CE",
        False,
        "Oct 19, 2024 is NOT last Thursday → should return False (not treat '19' as day)"
    )

    # Test 3: Weekly option on its expiry day
    print("\n3. Weekly BANKNIFTY option on expiry day:")
    all_passed &= test_on_specific_date(
        date(2024, 12, 4),
        "BANKNIFTY24DEC0419500CE",
        True,
        "Dec 4, 2024 is the weekly expiry → should return True"
    )

    # Test 4: Weekly option NOT on expiry day
    print("\n4. Weekly BANKNIFTY option NOT on expiry day:")
    all_passed &= test_on_specific_date(
        date(2024, 12, 5),
        "BANKNIFTY24DEC0419500CE",
        False,
        "Dec 5, 2024 is NOT the weekly expiry → should return False"
    )

    # Test 5: Old format weekly on expiry day
    print("\n5. Old format weekly on expiry day:")
    all_passed &= test_on_specific_date(
        date(2025, 7, 25),
        "NIFTY25O0725",
        True,
        "Jul 25, 2025 is the expiry → should return True"
    )

    # Test 6: Stock option monthly on expiry day
    print("\n6. Stock option on monthly expiry:")
    all_passed &= test_on_specific_date(
        date(2024, 12, 26),
        "ITC24DEC440CE",
        True,
        "Dec 26, 2024 is last Thursday of Dec → should return True"
    )

    # Test 7: Edge case - symbol that starts with valid day digits but is monthly
    print("\n7. Edge case - NIFTY25JAN18500CE on Jan 30 (last Thu):")
    all_passed &= test_on_specific_date(
        date(2025, 1, 30),
        "NIFTY25JAN18500CE",
        True,
        "Jan 30, 2025 is last Thursday → monthly expiry, should return True"
    )

    # Test 8: Same symbol on Jan 18 (the digits in strike)
    print("\n8. Edge case - NIFTY25JAN18500CE on Jan 18 (NOT expiry):")
    all_passed &= test_on_specific_date(
        date(2025, 1, 18),
        "NIFTY25JAN18500CE",
        False,
        "Jan 18 is NOT last Thursday → should return False (not misparse '18' as day)"
    )

    print("\n" + "=" * 80)
    if all_passed:
        print("✅ All tests PASSED!")
    else:
        print("❌ Some tests FAILED!")

    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
