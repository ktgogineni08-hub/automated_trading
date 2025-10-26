# Weekly Contracts Fix - Final Pattern

## Issue: Weekly Contracts Not Detected as F&O

### Problem
Weekly contracts like `NIFTY25O0725350PE` and `BANKNIFTY25N212000CE` use **single-letter month codes** (O, N, etc.) instead of full month names (OCT, NOV).

Previous regex pattern only matched full month names:
```regex
\d{2}(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\d+(CE|PE|FUT)$
```

**Result**: Weekly contracts fell into "cash" branch → queried as `NSE:NIFTY25O0725350PE` → Kite rejected → returned `None` → fell back to entry price → **zero P&L**.

---

## Solution: Pattern Based on Suffix

### Final Pattern
```regex
(\d+(CE|PE)|FUT)$
```

**Logic**:
- Match digits followed by CE or PE at end
- OR match FUT at end
- This avoids false positives like "RELIANCE" (ends with "CE" but no digits before it)

### Test Results

| Symbol | Type | Pattern Match | Exchange | Result |
|--------|------|---------------|----------|--------|
| `NIFTY25OCT24800CE` | Monthly | ✅ Yes | NFO | ✅ |
| `BANKNIFTY25OCT53000PE` | Monthly | ✅ Yes | NFO | ✅ |
| `NIFTY25O0725350PE` | **Weekly** | ✅ Yes | NFO | ✅ |
| `BANKNIFTY25N212000CE` | **Weekly** | ✅ Yes | NFO | ✅ |
| `SENSEX25O1583000PE` | **Weekly** | ✅ Yes | BFO | ✅ |
| `NIFTY25OCTFUT` | Futures | ✅ Yes | NFO | ✅ |
| `RELIANCE` | Cash | ❌ No | NSE | ✅ |
| `TCS` | Cash | ❌ No | NSE | ✅ |
| `INFY` | Cash | ❌ No | NSE | ✅ |

---

## Implementation

### Location 1: `get_current_price` (Line 1895)
```python
def get_current_price(self, symbol: str) -> Optional[float]:
    if not self.kite:
        return None

    try:
        # Detect F&O: (digits + CE/PE) OR FUT at end
        import re
        fno_pattern = r'(\d+(CE|PE)|FUT)$'
        is_fno = bool(re.search(fno_pattern, symbol))

        if is_fno:
            # F&O - NFO or BFO
            if any(idx in symbol for idx in ['SENSEX', 'BANKEX']):
                exchange = 'BFO'
            else:
                exchange = 'NFO'
            quote_symbol = f"{exchange}:{symbol}"
        else:
            # Cash - NSE
            quote_symbol = f"NSE:{symbol}"

        # Fetch LTP
        quotes = self.kite.quote([quote_symbol])
        if quote_symbol in quotes:
            last_price = quotes[quote_symbol].get('last_price', 0)
            if last_price > 0:
                return last_price

        return None
    except Exception as e:
        return None
```

### Location 2: `place_live_order` (Line 2651)
```python
# Detect F&O
fno_pattern = r'(\d+(CE|PE)|FUT)$'
is_fno = bool(re.search(fno_pattern, symbol))

if is_fno:
    if any(idx in symbol for idx in ['SENSEX', 'BANKEX']):
        exchange = 'BFO'
    else:
        exchange = 'NFO'
    product = 'NRML'
else:
    exchange = 'NSE'
    product = 'MIS'

order_params = {
    'tradingsymbol': symbol,
    'exchange': exchange,
    'product': product,
    # ...
}
```

---

## Why This Works

### 1. Covers All Contract Types
- **Monthly**: `NIFTY25OCT24800CE` → Match `24800CE` (digits + CE)
- **Weekly**: `NIFTY25O0725350PE` → Match `25350PE` (digits + PE)
- **Futures**: `NIFTY25OCTFUT` → Match `FUT` (special case)

### 2. Avoids False Positives
- **RELIANCE**: No match (ends with "CE" but no digits before "CE")
- **TCS**: No match
- **INFY**: No match

### 3. Simple and Robust
- No need to enumerate all month codes
- No complex lookahead/lookbehind
- Works with any date format (OCT, O, etc.)

---

## Weekly Contract Examples

### NIFTY Weekly
```
NIFTY25O0725350PE
     ││││││││││└─ PE (put)
     │││││││││└── 25350 (strike)
     ││││││││└─── 07 (day)
     │││││││└──── O (October - single letter)
     ││││││└───── 25 (year)
     │└┴┴┴┴└────── NIFTY (index)
```

### BANKNIFTY Weekly
```
BANKNIFTY25N212000CE
         ││││││││││└─ CE (call)
         │││││││││└── 12000 (strike)
         ││││││││└─── 21 (day)
         │││││││└──── N (November - single letter)
         ││││││└───── 25 (year)
         │└┴┴┴┴└────── BANKNIFTY (index)
```

---

## Impact

### Before Fix
- Weekly contracts → Detected as cash
- Queried from NSE → Rejected
- Fell back to entry price
- **Zero P&L on exit**
- **Cash unchanged**
- **Risk controls broken**

### After Fix
- Weekly contracts → Detected as F&O ✅
- Queried from NFO/BFO ✅
- Live price fetched ✅
- **Accurate P&L** ✅
- **Cash updated correctly** ✅
- **Risk controls working** ✅

---

## Test Verification

All tests pass:
```bash
$ python3 test_position_closing.py

============================================================
TEST 3: Verify Exchange Detection Logic
============================================================
✅ NIFTY25OCT24800CE         → NFO (F&O - NIFTY monthly option)
✅ BANKNIFTY25OCT53000PE     → NFO (F&O - BANKNIFTY monthly option)
✅ SENSEX25OCT83000CE        → BFO (F&O - SENSEX monthly option)
✅ BANKEX25OCT63000PE        → BFO (F&O - BANKEX monthly option)
✅ NIFTY25O0725350PE         → NFO (F&O - NIFTY weekly option) ← FIXED!
✅ BANKNIFTY25N212000CE      → NFO (F&O - BANKNIFTY weekly option) ← FIXED!
✅ SENSEX25O1583000PE        → BFO (F&O - SENSEX weekly option) ← FIXED!
✅ NIFTY25OCTFUT             → NFO (F&O - NIFTY futures)
✅ RELIANCE                  → NSE (Cash equity)
✅ TCS                       → NSE (Cash equity)
✅ INFY                      → NSE (Cash equity)

✅ PASS: All exchange detection tests passed
```

---

## Deployment Status

**Status**: READY ✅

All contract types now supported:
- ✅ Monthly contracts (full month names)
- ✅ Weekly contracts (single-letter month codes)
- ✅ Futures contracts
- ✅ Cash equity

No remaining blockers for weekly expiry trading.

---

*Last Updated: 2025-10-07*
*Weekly Contracts Fix Complete*
