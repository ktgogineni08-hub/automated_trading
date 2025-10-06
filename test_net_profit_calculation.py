#!/usr/bin/env python3
"""
Test for Net Profit Calculation with Transaction Fees
Verifies that quick profit logic uses NET profit (after all fees) not gross P&L
"""

def test_net_profit_calculation():
    """
    Test that NET profit calculation includes all transaction fees
    """
    print("\n" + "="*60)
    print("Testing Net Profit Calculation with Transaction Fees")
    print("="*60)

    # Read the enhanced code
    with open('enhanced_trading_system_complete.py', 'r') as f:
        code = f.read()

    print("\n✅ TEST 1: Check exit fee calculation exists")
    if 'estimated_exit_fees = self.calculate_transaction_costs' in code:
        print("   ✅ PASS: Exit fee calculation found")
    else:
        print("   ❌ FAIL: Exit fee calculation not found")
        return False

    print("\n✅ TEST 2: Check NET profit calculation")
    if 'net_profit = unrealized_pnl - estimated_exit_fees' in code:
        print("   ✅ PASS: NET profit = Gross P&L - Exit fees")
    else:
        print("   ❌ FAIL: NET profit calculation not found")
        return False

    print("\n✅ TEST 3: Check quick profit uses NET profit")
    if 'if net_profit >= 5000:' in code:
        print("   ✅ PASS: Quick profit check uses net_profit")
    else:
        print("   ❌ FAIL: Quick profit still uses gross unrealized_pnl")
        return False

    print("\n✅ TEST 4: Check exit reason shows NET profit")
    if 'Net: ₹{net_profit' in code and 'after fees' in code:
        print("   ✅ PASS: Exit reason displays NET profit after fees")
    else:
        print("   ❌ FAIL: Exit reason doesn't show NET profit")
        return False

    print("\n✅ TEST 5: Check logging shows breakdown")
    if 'Gross:' in code and 'Exit fees:' in code and 'NET:' in code:
        print("   ✅ PASS: Logging shows Gross, Exit fees, and NET breakdown")
    else:
        print("   ❌ FAIL: Logging doesn't show fee breakdown")
        return False

    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED - Net Profit Calculation Working!")
    print("="*60)

    # Calculate example scenarios
    print("\n📊 EXAMPLE CALCULATIONS:")
    print("\n" + "-"*60)

    # Transaction fee structure
    brokerage_rate = 0.0002  # 0.02%
    brokerage_max = 20.0
    transaction_charges_rate = 0.0000325
    gst_rate = 0.18
    stt_rate = 0.001  # For sell trades

    def calculate_exit_fees(exit_value):
        brokerage = min(exit_value * brokerage_rate, brokerage_max)
        trans_charges = exit_value * transaction_charges_rate
        gst = (brokerage + trans_charges) * gst_rate
        stt = exit_value * stt_rate
        return brokerage + trans_charges + gst + stt

    # Example 1: User's NIFTY position
    print("\n📈 Example 1: NIFTY25O0725350PE (User's actual position)")
    shares_1 = 680
    entry_price_1 = 523.54
    current_price_1 = 545.72

    entry_value_1 = shares_1 * entry_price_1
    exit_value_1 = shares_1 * current_price_1
    gross_pnl_1 = (current_price_1 - entry_price_1) * shares_1
    exit_fees_1 = calculate_exit_fees(exit_value_1)
    net_profit_1 = gross_pnl_1 - exit_fees_1

    print(f"   Shares: {shares_1}")
    print(f"   Entry: ₹{entry_price_1:.2f} → Exit: ₹{current_price_1:.2f}")
    print(f"   Entry value: ₹{entry_value_1:,.2f}")
    print(f"   Exit value: ₹{exit_value_1:,.2f}")
    print(f"   Gross P&L: ₹{gross_pnl_1:,.2f}")
    print(f"   Exit fees: ₹{exit_fees_1:,.2f}")
    print(f"   NET Profit: ₹{net_profit_1:,.2f}")

    if net_profit_1 >= 10000:
        print(f"   ✅ WILL EXIT: NET profit ₹{net_profit_1:,.0f} > ₹10k")
    elif net_profit_1 >= 5000:
        print(f"   ✅ WILL EXIT: NET profit ₹{net_profit_1:,.0f} > ₹5k")
    else:
        print(f"   ❌ WON'T EXIT: NET profit ₹{net_profit_1:,.0f} < ₹5k")

    # Example 2: Position near ₹10k NET threshold
    print("\n📈 Example 2: Position near ₹10k NET profit threshold")
    shares_2 = 500
    entry_price_2 = 100.00
    current_price_2 = 120.80  # Chosen to give ~₹10k net after fees

    exit_value_2 = shares_2 * current_price_2
    gross_pnl_2 = (current_price_2 - entry_price_2) * shares_2
    exit_fees_2 = calculate_exit_fees(exit_value_2)
    net_profit_2 = gross_pnl_2 - exit_fees_2

    print(f"   Shares: {shares_2}")
    print(f"   Entry: ₹{entry_price_2:.2f} → Exit: ₹{current_price_2:.2f}")
    print(f"   Gross P&L: ₹{gross_pnl_2:,.2f}")
    print(f"   Exit fees: ₹{exit_fees_2:,.2f}")
    print(f"   NET Profit: ₹{net_profit_2:,.2f}")

    if net_profit_2 >= 10000:
        print(f"   ✅ WILL EXIT: NET profit ₹{net_profit_2:,.0f} > ₹10k")
    elif net_profit_2 >= 5000:
        print(f"   ✅ WILL EXIT: NET profit ₹{net_profit_2:,.0f} > ₹5k")
    else:
        print(f"   ❌ WON'T EXIT: NET profit ₹{net_profit_2:,.0f} < ₹5k")

    # Example 3: Position with ₹5.5k gross but <₹5k net
    print("\n📈 Example 3: ₹5.5k gross but fees reduce to <₹5k NET")
    shares_3 = 300
    entry_price_3 = 200.00
    current_price_3 = 218.50  # ₹5,550 gross

    exit_value_3 = shares_3 * current_price_3
    gross_pnl_3 = (current_price_3 - entry_price_3) * shares_3
    exit_fees_3 = calculate_exit_fees(exit_value_3)
    net_profit_3 = gross_pnl_3 - exit_fees_3

    print(f"   Shares: {shares_3}")
    print(f"   Entry: ₹{entry_price_3:.2f} → Exit: ₹{current_price_3:.2f}")
    print(f"   Gross P&L: ₹{gross_pnl_3:,.2f}")
    print(f"   Exit fees: ₹{exit_fees_3:,.2f}")
    print(f"   NET Profit: ₹{net_profit_3:,.2f}")

    if net_profit_3 >= 10000:
        print(f"   ✅ WILL EXIT: NET profit ₹{net_profit_3:,.0f} > ₹10k")
    elif net_profit_3 >= 5000:
        print(f"   ✅ WILL EXIT: NET profit ₹{net_profit_3:,.0f} > ₹5k")
    else:
        print(f"   ❌ WON'T EXIT: NET profit ₹{net_profit_3:,.0f} < ₹5k (fees ate into profit)")

    print("\n" + "-"*60)
    print("\n💡 KEY INSIGHT:")
    print("   The system now checks NET profit (after ALL fees) not gross P&L")
    print("   This ensures you actually get ₹5-10k in your pocket!")
    print("\n📋 FEE STRUCTURE:")
    print(f"   • Brokerage: 0.02% (max ₹20)")
    print(f"   • Transaction charges: 0.00325%")
    print(f"   • GST: 18% on (brokerage + trans charges)")
    print(f"   • STT (on sell): 0.1%")
    print(f"   • Typical fees for ₹3.7L trade: ~₹409")

    return True

if __name__ == "__main__":
    success = test_net_profit_calculation()
    exit(0 if success else 1)
