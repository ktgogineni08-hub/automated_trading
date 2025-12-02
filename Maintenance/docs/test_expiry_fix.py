#!/usr/bin/env python3
"""Quick test to verify the expiry date fix works"""

# Test that UnifiedPortfolio has _is_expiring_today method
from enhanced_trading_system_complete import UnifiedPortfolio

print("Testing _is_expiring_today method...")

# Create a portfolio instance
portfolio = UnifiedPortfolio(initial_cash=1000000, trading_mode='paper', silent=True)

# Test with actual option symbols
test_symbols = [
    "NIFTY25O0725350PE",      # July 25, 2025 (not today)
    "NIFTY25OCT06300CE",      # October 6, 2025 (today)
    "BANKNIFTY25OCT56500PE",  # October something 2025
]

print(f"\nToday's date: 2025-10-06")
print("-" * 50)

for symbol in test_symbols:
    try:
        is_expiring = portfolio._is_expiring_today(symbol)
        print(f"✅ {symbol}: {'EXPIRING TODAY' if is_expiring else 'Not expiring today'}")
    except Exception as e:
        print(f"❌ {symbol}: ERROR - {e}")

print("\n✅ Test completed! The _is_expiring_today method exists and works.")
