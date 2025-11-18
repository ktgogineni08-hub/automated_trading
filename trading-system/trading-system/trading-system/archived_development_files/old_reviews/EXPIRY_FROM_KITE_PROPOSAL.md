# Use Kite Expiry Data Instead of Regex Parsing

**Date:** 2025-10-07
**Status:** 💡 PROPOSAL

## The Problem with Current Approach

We're doing **complex regex parsing** to extract expiry dates from option symbols:
- 103 lines of code
- Complex edge case handling
- Weekday calculations
- Monthly vs weekly detection
- Easily breaks if NSE changes symbol format

## The Simple Solution

**Kite API already provides expiry dates!**

```python
instruments = kite.instruments("NFO")

# Each instrument has:
{
    'tradingsymbol': 'NIFTY24JAN19000CE',
    'expiry': '2024-01-25',  # ← Already provided by Kite!
    'strike': 19000.0,
    'instrument_type': 'CE',
    'exchange': 'NFO',
    ...
}
```

## Proposed Implementation

### 1. Build Expiry Cache from Kite Instruments

```python
class KiteDataProvider:
    def __init__(self, kite):
        self.kite = kite
        self._expiry_cache = {}  # symbol -> expiry_date
        self._cache_ttl = 86400  # 24 hours
        self._cache_time = 0

    def get_expiry_date(self, symbol: str) -> Optional[datetime]:
        """
        Get expiry date from Kite instruments data (cached)

        Much simpler and more reliable than regex parsing!
        """
        # Refresh cache if expired
        if time.time() - self._cache_time > self._cache_ttl:
            self._refresh_expiry_cache()

        # Lookup expiry from cache
        expiry_str = self._expiry_cache.get(symbol)
        if expiry_str:
            return datetime.strptime(expiry_str, '%Y-%m-%d')

        return None

    def _refresh_expiry_cache(self):
        """Build expiry cache from Kite instruments"""
        try:
            instruments = self.kite.instruments("NFO")

            self._expiry_cache = {
                inst['tradingsymbol']: inst['expiry']
                for inst in instruments
                if inst.get('expiry')  # Only F&O instruments have expiry
            }

            self._cache_time = time.time()
            logger.logger.info(f"✅ Cached expiry dates for {len(self._expiry_cache)} instruments")
        except Exception as e:
            logger.logger.error(f"Failed to refresh expiry cache: {e}")

    def is_expiring_today(self, symbol: str) -> bool:
        """Check if option expires today"""
        expiry_date = self.get_expiry_date(symbol)
        if not expiry_date:
            return False

        return expiry_date.date() == datetime.now().date()
```

### 2. Replace All Regex Parsing

**Portfolio._is_expiring_today()** - Replace 87 lines with 2 lines:
```python
def _is_expiring_today(self, symbol: str) -> bool:
    """Return True when the option symbol corresponds to today's expiry."""
    return self.kite_data_provider.is_expiring_today(symbol)
```

**AdvancedMarketManager.extract_expiry_date()** - Replace 103 lines with 2 lines:
```python
def extract_expiry_date(self, symbol: str) -> Optional[datetime]:
    """Extract expiry date from Kite instruments data"""
    return self.data_provider.get_expiry_date(symbol)
```

## Benefits

### 1. **Reliability**
- ✅ Kite's data is authoritative (comes from NSE)
- ✅ No risk of regex parsing errors
- ✅ Handles all symbol formats automatically
- ✅ Works even if NSE changes symbol conventions

### 2. **Simplicity**
- ✅ 190 lines of regex code → 20 lines of caching
- ✅ No edge case handling needed
- ✅ No weekday calculations
- ✅ No monthly vs weekly detection

### 3. **Performance**
- ✅ Cache built once per day
- ✅ O(1) lookup instead of regex matching
- ✅ Single instruments() API call for all symbols

### 4. **Maintainability**
- ✅ Less code to maintain
- ✅ Fewer bugs possible
- ✅ Easier to understand
- ✅ Future-proof

## Comparison

### Current Approach (Regex)
```python
# 103 lines of code in extract_expiry_date()
# 87 lines of code in _is_expiring_today()
# Total: 190 lines

# Complex logic:
- Extract underlying index
- Handle legacy format (YYOmmdd)
- Handle modern format (YYMMM[DD]STRIKE)
- Month string to number mapping
- Calculate last weekday of month
- Detect weekly vs monthly
- Validate strike value heuristic
- Handle edge cases
```

**Issues:**
- ❌ Breaks if NSE changes format
- ❌ Edge cases (NIFTY25JAN23000CE)
- ❌ Requires testing every possible format
- ❌ Maintenance burden

### Proposed Approach (Kite Data)
```python
# 20 lines of code total

def get_expiry_date(symbol):
    if time.time() - cache_time > ttl:
        refresh_cache()
    return expiry_cache.get(symbol)

def refresh_cache():
    instruments = kite.instruments("NFO")
    expiry_cache = {i['tradingsymbol']: i['expiry'] for i in instruments}
```

**Benefits:**
- ✅ Uses authoritative data from NSE
- ✅ No parsing needed
- ✅ No edge cases
- ✅ Minimal maintenance

## Implementation Plan

### Phase 1: Add Expiry Cache (30 minutes)
1. Add `_expiry_cache` to KiteDataProvider
2. Add `get_expiry_date()` method
3. Add `_refresh_expiry_cache()` method
4. Add cache TTL management

### Phase 2: Update Callers (15 minutes)
1. Replace `Portfolio._is_expiring_today()` implementation
2. Replace `AdvancedMarketManager.extract_expiry_date()` implementation
3. Update any other callers

### Phase 3: Testing (30 minutes)
1. Test with live Kite connection
2. Verify expiry dates match NSE
3. Test cache refresh logic
4. Test with all three indices

### Phase 4: Cleanup (15 minutes)
1. Remove old regex parsing code
2. Update documentation
3. Mark old test files as deprecated

**Total Time:** ~90 minutes

## Risks & Mitigation

### Risk 1: Instruments API Rate Limit
- **Impact:** LOW
- **Mitigation:** Cache for 24 hours, only refresh once per day
- **Fallback:** Keep regex parsing as backup (but log warning)

### Risk 2: Kite API Down
- **Impact:** MEDIUM
- **Mitigation:** Cache persists until next refresh
- **Fallback:** Use last known cache, log warning

### Risk 3: Symbol Not in Instruments
- **Impact:** LOW
- **Mitigation:** Return None, log warning, fall back to monthly expiry assumption
- **Monitoring:** Track cache miss rate

## Why This Wasn't Done Before?

Good question! Possible reasons:
1. Didn't know Kite provides expiry field
2. Assumed instruments() API was too slow
3. Tried to minimize API calls
4. Copied pattern from other codebases
5. Regex seemed "clever" at the time

**But:** Using authoritative data is ALWAYS better than parsing!

## Recommendation

**Implement this change immediately** because:
1. Simpler code = fewer bugs
2. Uses NSE's authoritative data
3. Future-proof against symbol format changes
4. Reduces maintenance burden
5. Improves reliability

## Next Steps

User decision:
- [ ] Implement this approach (recommended)
- [ ] Keep regex approach (not recommended)
- [ ] Hybrid: Use Kite data primarily, regex as fallback

---

**Note:** The regex fixes we just did are still valuable if Kite API is unavailable, but using Kite data should be the PRIMARY method.
