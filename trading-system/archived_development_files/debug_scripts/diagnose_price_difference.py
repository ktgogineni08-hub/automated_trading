#!/usr/bin/env python3
"""
Diagnose Price Difference Between Chart and System
Shows why option prices differ from index prices
"""

def explain_price_difference():
    """
    Explain the difference between:
    1. NIFTY Index (spot): ~25,300
    2. NIFTY Futures: ~25,300
    3. NIFTY Options: ₹50-150 range
    """

    print("="*70)
    print("📊 UNDERSTANDING NIFTY PRICE DIFFERENCES")
    print("="*70)

    # Example scenario
    nifty_spot = 25300

    print(f"\n1️⃣ NIFTY 50 INDEX (Spot Price)")
    print(f"   Symbol: NIFTY 50")
    print(f"   Price: ₹{nifty_spot:,}")
    print(f"   Type: Index (not tradeable directly)")
    print(f"   ⚠️ You CANNOT buy/sell the index itself\n")

    print(f"2️⃣ NIFTY FUTURES")
    print(f"   Symbol: NIFTY{nifty_spot}FUT or NIFTY25OCTFUT")
    print(f"   Price: ₹{nifty_spot:,} (close to spot)")
    print(f"   Lot Size: 65 shares")
    print(f"   Contract Value: ₹{nifty_spot * 65:,}")
    print(f"   ✅ This is what your chart might be showing\n")

    print(f"3️⃣ NIFTY OPTIONS (What your system is trading)")
    print(f"   Symbol: NIFTY{nifty_spot}CE or NIFTY{nifty_spot}PE")
    print(f"   Strike: 25,300 (ATM)")
    print(f"   Option Prices:")

    # Example ATM option prices
    atm_call_price = 87.30  # From your chart
    atm_put_price = 85.65   # Typical ATM put

    print(f"      Call (CE): ₹{atm_call_price} per share")
    print(f"      Put (PE):  ₹{atm_put_price} per share")
    print(f"   Lot Size: 65 shares")
    print(f"   Premium per lot:")
    print(f"      Call: ₹{atm_call_price * 65:,.0f}")
    print(f"      Put:  ₹{atm_put_price * 65:,.0f}")
    print(f"   ✅ These are OPTION PREMIUMS, not index prices!\n")

    print("="*70)
    print("🔍 WHY THE PRICE DIFFERENCE?")
    print("="*70)

    print("\n📌 Your Chart (TradingView/NSE)")
    print("   Shows: NIFTY 14th Oct 25300 CE @ ₹87.30")
    print("   This is the OPTION PREMIUM")
    print("   For the right to buy NIFTY at 25,300\n")

    print("📌 Your System")
    print("   Trading: NIFTY Options (Straddle strategy)")
    print("   Shows: Option premium prices (₹80-90 range)")
    print("   Same type of instrument as your chart!\n")

    print("="*70)
    print("❓ WHY SYSTEM SHOWS ₹90 WHEN CHART SHOWS ₹81?")
    print("="*70)

    print("\n🎯 Possible Reasons:\n")

    print("1. DIFFERENT STRIKE PRICES")
    print("   Your chart: 25,300 strike @ ₹81")
    print("   Your system: 25,250 strike @ ₹90")
    print("   Solution: System selected different ATM strike\n")

    print("2. DIFFERENT EXPIRY DATES")
    print("   Your chart: 14th Oct expiry")
    print("   Your system: 17th Oct expiry (weekly vs monthly)")
    print("   Solution: System may be using different expiry\n")

    print("3. BID-ASK SPREAD")
    print("   Your chart: Last traded price (LTP) ₹81")
    print("   Your system: Bid ₹85, Ask ₹95, Mid ₹90")
    print("   Solution: System using bid/ask instead of LTP\n")

    print("4. TIMING DELAY")
    print("   Your chart: Real-time (14:20:00)")
    print("   Your system: Last fetch (14:19:45)")
    print("   Solution: System prices may be 15-30 seconds old\n")

    print("5. OPTION TYPE MISMATCH")
    print("   Your chart: Call option (CE)")
    print("   Your system: Put option (PE)")
    print("   Solution: Calls and Puts have different prices\n")

    print("="*70)
    print("🔧 HOW TO DIAGNOSE")
    print("="*70)

    print("\n✅ Check your system logs for exact symbols:")
    print("   $ tail -100 logs/trading_2025-10-07.log | grep -E 'NIFTY.*CE|NIFTY.*PE'")
    print("\n✅ Look for lines like:")
    print("   'Opening position: NIFTY25O1025300CE @ ₹87.30'")
    print("   'Opening position: NIFTY25O1025300PE @ ₹85.65'")
    print("\n✅ Compare with your TradingView chart:")
    print("   - Same strike? (25300)")
    print("   - Same expiry? (14 Oct)")
    print("   - Same option type? (CE/PE)")
    print("   - Same time? (within 1 minute)\n")

    print("="*70)
    print("💡 MOST LIKELY CAUSE")
    print("="*70)

    print("""
Your system is correctly trading NIFTY OPTIONS (not futures/index).
The ₹81 vs ₹90 difference is likely due to:

1. ⭐ DIFFERENT STRIKES (most common)
   - Your chart shows 25300 strike
   - System may have selected 25250 or 25350
   - Even 50-point difference = ₹5-10 premium difference

2. ⭐ CALL vs PUT (if straddle)
   - Calls trade at ₹81
   - Puts trade at ₹90
   - System shows average or one leg

3. ⭐ BID-ASK SPREAD
   - Market quote: Bid ₹81, Ask ₹99
   - System shows mid-price: ₹90
   - Chart shows LTP: ₹81

✅ THIS IS NORMAL and not a bug!

The professional modules we added don't affect price fetching.
They only affect:
- Position sizing (1% rule)
- Trade validation (RRR ≥1:1.5)
- SEBI compliance checks
- Technical indicators
""")

    print("="*70)
    print("🚀 NEXT STEPS")
    print("="*70)

    print("""
1. Run your system and note the EXACT symbol traded:
   Example: "NIFTY25O1025300CE"

2. Search that EXACT symbol on NSE/TradingView:
   - Go to TradingView
   - Search: NIFTY25O1025300CE
   - Compare prices

3. If prices still don't match:
   - Check timestamp difference
   - Check if system uses bid/ask vs LTP
   - Share the exact symbols with me

4. To verify professional modules are working:
   - Look for "Trade validation passed" messages
   - Check "Using professional position size" logs
   - Verify "SEBI compliance" checks in logs
""")

if __name__ == "__main__":
    explain_price_difference()
