#!/usr/bin/env python3
"""Test the _is_expiring_today method in UnifiedPortfolio"""

from enhanced_trading_system_complete import UnifiedPortfolio
from datetime import datetime

print("Testing _is_expiring_today method in UnifiedPortfolio...")
print(f"Today's date: {datetime.now().strftime('%Y-%m-%d')}")
print("-" * 60)

# Create portfolio instance
portfolio = UnifiedPortfolio(initial_cash=1000000, trading_mode='paper', silent=True)

# Test with actual option symbols from user's positions
test_symbols = [
    ("NIFTY25O0725150CE", "July 25, 2025 - NOT today"),
    ("NIFTY25OCT06300CE", "October 6, 2025 - TODAY"),
    ("BANKNIFTY25OCT56500PE", "October ?? (not 6) - NOT today"),
    ("MIDCPNIFTY25OCT12975CE", "October ?? - NOT today"),
]

print("\nTest Results:")
print("-" * 60)

for symbol, description in test_symbols:
    try:
        result = portfolio._is_expiring_today(symbol)
        status = "✅ EXPIRING TODAY" if result else "⚪ Not expiring today"
        print(f"{symbol}")
        print(f"  {description}")
        print(f"  Result: {status}")
        print()
    except Exception as e:
        print(f"{symbol}")
        print(f"  {description}")
        print(f"  ❌ ERROR: {e}")
        print()

print("✅ Test completed successfully!")
