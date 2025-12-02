#!/usr/bin/env python3
"""Test the latest _is_expiring_today implementation with real-world symbols"""

from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enhanced_trading_system_complete import UnifiedPortfolio

def test_symbol_parsing():
    """Test parsing of various NSE option symbols"""

    portfolio = UnifiedPortfolio(initial_cash=100000, trading_mode='paper')

    # Test cases with expected results
    test_cases = [
        # Symbol, Description, Expected on which date
        ("NIFTY24OCT19400CE", "Monthly NIFTY (Oct 2024, last Thursday)", "2024-10-31"),
        ("BANKNIFTY24DEC0419500CE", "Weekly BANKNIFTY (Dec 4, 2024)", "2024-12-04"),
        ("NIFTY24NOV2819500PE", "Weekly NIFTY (Nov 28, 2024)", "2024-11-28"),
        ("ITC24DEC440CE", "Stock option monthly (Dec 2024)", "2024-12-26"),  # Last Thursday of Dec 2024
        ("NIFTY25O0725", "Old format weekly (Jul 25, 2025)", "2025-07-25"),
    ]

    print("Testing symbol parser with today's date:", datetime.now().date())
    print("=" * 80)

    for symbol, description, expected_date in test_cases:
        result = portfolio._is_expiring_today(symbol)
        expected_obj = datetime.strptime(expected_date, "%Y-%m-%d").date()
        is_today = expected_obj == datetime.now().date()

        status = "✓" if result == is_today else "✗"
        print(f"\n{status} {symbol}")
        print(f"  Description: {description}")
        print(f"  Expected expiry: {expected_date}")
        print(f"  Should expire today: {is_today}")
        print(f"  Parser returned: {result}")

        if result != is_today:
            print(f"  ⚠️  MISMATCH!")

    print("\n" + "=" * 80)

    # Specific test for the problematic case mentioned by reviewer
    print("\n🔍 Detailed test for NIFTY24OCT19400CE:")
    print("This is a MONTHLY option (Oct 2024), should expire on last Thursday (Oct 31)")
    print("Today is:", datetime.now().date())

    result = portfolio._is_expiring_today("NIFTY24OCT19400CE")
    print(f"Parser returns: {result}")

    if datetime.now().date() == datetime(2024, 10, 31).date():
        print("✓ Today IS Oct 31, should return True")
        if result:
            print("✓ CORRECT!")
        else:
            print("✗ WRONG - returned False when should be True")
    else:
        print(f"✓ Today is NOT Oct 31, should return False")
        if not result:
            print("✓ CORRECT!")
        else:
            print("✗ WRONG - returned True when should be False")
            print("⚠️  This suggests the parser is treating '19' as day 19!")

if __name__ == "__main__":
    test_symbol_parsing()
