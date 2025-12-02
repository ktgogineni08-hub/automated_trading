# Guide: Cleanup Existing Duplicate Positions

**Status:** 🔴 URGENT - Before restarting trading system
**Created:** 2025-10-07

## Overview

Before you can safely restart the trading system with the duplicate prevention fixes, you need to clean up any existing duplicate positions in your Kite account.

## Step 1: Identify Duplicate Positions

### Option A: Via Kite Web/App
1. Log into Kite web interface: https://kite.zerodha.com
2. Go to **Portfolio → Positions**
3. Look for duplicate entries of the same symbol

### Option B: Via Python Script

Run this quick check:

```python
from kiteconnect import KiteConnect

# Your credentials
api_key = "YOUR_API_KEY"
access_token = "YOUR_ACCESS_TOKEN"

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

# Fetch positions
positions = kite.positions()
net_positions = positions.get('net', [])

# Group by symbol
from collections import defaultdict
position_groups = defaultdict(list)

for pos in net_positions:
    symbol = pos.get('tradingsymbol', '')
    qty = pos.get('quantity', 0)

    if qty != 0:  # Only active positions
        position_groups[symbol].append(pos)

# Find duplicates
print("DUPLICATE POSITIONS:")
print("=" * 80)
for symbol, positions_list in position_groups.items():
    if len(positions_list) > 1:
        print(f"\n🔴 {symbol}: {len(positions_list)} entries")
        total_qty = sum(p.get('quantity', 0) for p in positions_list)
        total_value = sum(p.get('value', 0) for p in positions_list)
        print(f"   Total Quantity: {total_qty}")
        print(f"   Total Value: ₹{total_value:,.2f}")

        for i, pos in enumerate(positions_list, 1):
            print(f"   Entry {i}: {pos.get('quantity')} shares @ ₹{pos.get('average_price'):.2f}")
```

## Step 2: Understand Your Positions

Based on your previous logs, you likely have duplicates like:

```
NIFTY25O1425250CE: 150 shares (should be 75)
NIFTY25O1425550PE: 150 shares (should be 75)
```

Each F&O position likely has:
- **Lot size:** 25 or 75 (depends on index)
- **Duplicate:** 2x the intended position
- **Risk:** 2x the intended risk

## Step 3: Choose Cleanup Strategy

### Strategy A: Close All & Start Fresh (RECOMMENDED)

**Pros:** Clean slate, no confusion
**Cons:** Realize current losses

```
1. Close all F&O positions
2. Wait for positions to settle
3. Restart trading system with fixes
4. System will open fresh positions
```

**How to close all:**
- Via Kite: Go to Positions → Click "Exit" on each position
- Note: You'll realize your current P&L (including the -28.74% loss)

### Strategy B: Keep 1 Set, Close Duplicates

**Pros:** Maintain market exposure
**Cons:** More complex, need to track carefully

```
1. For each duplicate pair:
   - Keep the FIRST entry (original position)
   - Close the SECOND entry (duplicate)

2. Verify final quantities match your strategy:
   - Straddle: 1 lot of CE + 1 lot of PE
   - Iron Condor: 1 lot each of 4 options
   - Strangle: 1 lot of CE + 1 lot of PE
```

**How to identify which to close:**
- Check entry time: Close the later one
- Check average price: Both should have similar prices if opened same time

## Step 4: Execute Cleanup

### Via Kite Web Interface

1. Go to **Positions** tab
2. For each position to close:
   ```
   Click on position → Exit → Market Order → Confirm
   ```
3. **Important:** Market orders execute immediately
4. Verify position is closed (quantity = 0)

### Via Kite API (Advanced)

```python
# Close a specific position
symbol = "NIFTY25O1425250CE"
quantity = 75  # Quantity to close
exchange = "NFO"
transaction_type = "SELL"  # SELL to close long, BUY to close short

order_id = kite.place_order(
    variety=kite.VARIETY_REGULAR,
    exchange=exchange,
    tradingsymbol=symbol,
    transaction_type=transaction_type,
    quantity=quantity,
    product=kite.PRODUCT_MIS,  # or PRODUCT_NRML
    order_type=kite.ORDER_TYPE_MARKET
)

print(f"Order placed: {order_id}")
```

## Step 5: Verify Cleanup

### Check 1: Position Count
```python
positions = kite.positions()
net_positions = positions.get('net', [])

active = [p for p in net_positions if p.get('quantity', 0) != 0]
print(f"Active positions: {len(active)}")

for pos in active:
    print(f"  {pos['tradingsymbol']}: {pos['quantity']} shares")
```

### Check 2: No Duplicates
```python
symbols = [p['tradingsymbol'] for p in active]
duplicates = [s for s in symbols if symbols.count(s) > 1]

if duplicates:
    print(f"🔴 Still have duplicates: {set(duplicates)}")
else:
    print(f"✅ No duplicates found!")
```

## Step 6: Calculate Impact

### Before Cleanup
```
Original Loss: -₹287,357 (-28.74%)
Duplicate positions: 2x risk exposure
```

### After Cleanup (Strategy A: Close All)
```
Realized Loss: -₹287,357 (locked in)
Position Risk: ₹0 (no exposure)
Ready to restart: YES ✅
```

### After Cleanup (Strategy B: Keep 1 Set)
```
Realized Loss: ~₹143,678 (half of duplicates)
Remaining Loss: ~₹143,678 (from kept positions)
Position Risk: 1x normal exposure
Ready to restart: YES ✅ (but monitor closely)
```

## Step 7: Restart Trading System

Once cleanup is complete:

1. **Verify fixes are in place:**
   ```bash
   cd /Users/gogineni/Python/trading-system
   grep -n "CRITICAL FIX: Check if.*position.*already exists" enhanced_trading_system_complete.py
   ```

   Should show 3 results (straddle, iron condor, strangle)

2. **Start monitoring script:**
   ```bash
   python test_duplicate_prevention.py &
   ```

3. **Start trading system:**
   ```bash
   python enhanced_trading_system_complete.py
   ```

4. **Watch for prevention messages:**
   ```
   ✅ "⚠️ Skipping [symbol] - position already exists!"
   ✅ "⚠️ SKIPPED: Already have N position(s) for [index]"
   ```

## Step 8: Monitor First Hour

**Critical monitoring period:** First 12 iterations (1 hour)

Watch for:
- ✅ No duplicate positions opened
- ✅ Prevention messages in logs
- ✅ Position sync working correctly
- 🔴 Any duplicate openings (STOP IMMEDIATELY)

## Emergency: If Duplicates Still Appear

If after all fixes you still see duplicates:

1. **STOP THE SYSTEM IMMEDIATELY** (Ctrl+C)

2. **Check git status:**
   ```bash
   git diff enhanced_trading_system_complete.py | grep "CRITICAL FIX"
   ```

3. **Verify all fixes are present:**
   - Line ~8030: Straddle checks
   - Line ~8156: Iron condor checks
   - Line ~8294: Strangle checks
   - Line ~9821: Index-level checks

4. **Report the issue** with logs showing the duplicate

## Recommendation

**I strongly recommend Strategy A (Close All & Start Fresh):**

✅ Advantages:
- Clean slate
- No confusion about which positions to keep
- System can rebuild portfolio correctly
- Fixes are fully effective from iteration 1

❌ Disadvantage:
- Realizes the -28.74% loss immediately

But this loss is **already incurred** - you're just making it official. The important thing is to **prevent future duplicates**, which the fixes now guarantee.

---

**Next Steps:**
1. Choose cleanup strategy (A or B)
2. Execute cleanup via Kite
3. Verify no duplicates remain
4. Restart system with monitoring
5. Watch for 1 hour to confirm fixes work

**Status:** Ready to execute cleanup
