# NSE Option Symbol Parser - Final Fix

## Problem Statement

The `_is_expiring_today()` method needs to correctly identify when an NSE F&O option expires today, to enable time-based exit rules (2-hour and 4-hour exits on expiry day only).

### Critical Challenge

NSE option symbols have an ambiguous structure where monthly and weekly options can look similar:

- **Weekly**: `BANKNIFTY24DEC0419500CE` → `24DEC` + `04` (day) + `19500` (strike) + `CE`
- **Monthly**: `NIFTY24OCT19400CE` → `24OCT` + `19400` (strike, NO day field) + `CE`

Both have 5 digits after the month abbreviation, making it impossible to distinguish based on length alone.

## Solution

The parser now uses **weekday validation** to distinguish weekly from monthly options:

### Key Insight: Weekly options expire on specific weekdays

- **NIFTY** weekly options → **Thursday**
- **BANKNIFTY** weekly options → **Wednesday**
- **FINNIFTY** weekly options → **Tuesday**
- **All monthly** options → **Last Thursday** of the month

### Algorithm

```python
def _is_expiring_today(symbol):
    1. Extract underlying (NIFTY, BANKNIFTY, etc.)

    2. Try old weekly format (YYOmmdd):
       - Pattern: NIFTY25O0725
       - Parse: YY=25, MM=07, DD=25
       - Check if date == today

    3. Try new format (YYMMMDDSTRIKE or YYMMMSTRIKE):
       - Match: YY + MMM + (middle) + CE/PE
       - Example: "24DEC0419500CE" → middle="0419500"

    4. If middle >= 5 chars:
       - Try parsing first 2 chars as day
       - Check if remaining 3+ chars are valid strike
       - Construct date and check weekday:
         * If BANKNIFTY and Wednesday → weekly
         * If FINNIFTY and Tuesday → weekly
         * If any and Thursday → weekly
         * Otherwise → fall through to monthly

    5. Default to monthly (last Thursday of month)
```

## Test Cases

### 1. NIFTY Monthly Option
- Symbol: `NIFTY24OCT19400CE`
- Expiry: Oct 31, 2024 (last Thursday)
- On Oct 19: Returns False (19 is Saturday, part of strike "19400")
- On Oct 31: Returns True

### 2. NIFTY Weekly Option
- Symbol: `NIFTY24NOV2819500PE`
- Expiry: Nov 28, 2024 (Thursday)
- On Nov 27: Returns False
- On Nov 28: Returns True

### 3. BANKNIFTY Weekly Option
- Symbol: `BANKNIFTY24DEC0419500CE`
- Expiry: Dec 4, 2024 (Wednesday)
- On Dec 4: Returns True
- On Dec 5: Returns False

### 4. Stock Option (3-digit strike)
- Symbol: `ITC24DEC440CE`
- Expiry: Dec 26, 2024 (last Thursday)
- Middle part "440" < 5 chars → treated as monthly
- On Dec 26: Returns True

### 5. Old Format Weekly
- Symbol: `NIFTY25O0725`
- Expiry: Jul 25, 2025
- On Jul 25: Returns True

## Code Location

File: `enhanced_trading_system_complete.py`
Method: `UnifiedPortfolio._is_expiring_today()` (lines 1875-1995)

## Impact

- ✅ Correctly identifies expiry day for time-based exits
- ✅ Prevents misclassification of monthly options as weekly
- ✅ Handles ambiguous symbols like NIFTY24OCT19400CE correctly
- ✅ Supports NIFTY (Thu), BANKNIFTY (Wed), FINNIFTY (Tue)
- ✅ Works with 3-5 digit strikes (stocks and indices)
- ✅ Backwards compatible with old YYOmmdd format

## Why This Works

The weekday check is reliable because:
1. NSE **always** schedules weekly expiries on specific weekdays (Wed/Thu/Tue)
2. If first 2 digits after month form a date that's NOT the expected weekday, they must be part of the strike
3. Monthly options always expire on last Thursday, never conflicting with weekly patterns
4. This handles edge cases like "19" in "19400" which is Oct 19 (Saturday) - clearly not a weekly expiry day

## Example: NIFTY24OCT19400CE

On Oct 19, 2024:
1. Extract: underlying="NIFTY", middle="19400"
2. Check if "19" + "400" pattern:
   - potential_day=19
   - Date: Oct 19, 2024 = Saturday
   - Is Saturday a NIFTY weekly expiry? NO (only Thursday)
   - Fall through to monthly
3. Monthly expiry: Last Thursday = Oct 31
4. Oct 19 ≠ Oct 31
5. Return False ✓

On Oct 31, 2024:
1-3. Same fallthrough logic
4. Oct 31 == Oct 31
5. Return True ✓
