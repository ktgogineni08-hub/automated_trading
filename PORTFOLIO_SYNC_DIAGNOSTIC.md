# Portfolio Sync Diagnostic Guide

## Issue Reported

**Console shows**:
```
Portfolio Status:
  Total Value: ₹951,862.44 (-4.81%)
  Cash Available: ₹343,591.77
  Active Positions: 7/15
  Unrealized P&L: 📉 ₹-42,038.48
```

**Dashboard shows**: Different values

---

## Possible Causes & Solutions

### Cause 1: Dashboard Cache (Most Likely)

**Symptom**: Dashboard shows old values even after console updates

**Why It Happens**:
- Browser caches the page
- JavaScript polling delay (2 second intervals)
- WebSocket connection issues

**Solution**:

1. **Hard Refresh Browser**:
   ```
   Chrome/Edge: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
   Firefox: Ctrl+F5 (Windows) or Cmd+Shift+R (Mac)
   Safari: Cmd+Option+R
   ```

2. **Clear Browser Cache**:
   ```
   Chrome: Settings → Privacy → Clear browsing data
   Select "Cached images and files"
   Click "Clear data"
   ```

3. **Force Dashboard Restart**:
   ```bash
   pkill -f enhanced_dashboard_server.py
   python enhanced_dashboard_server.py &
   sleep 3
   # Refresh browser
   ```

---

### Cause 2: Stale Price Data

**Symptom**: Console and dashboard use different prices for same positions

**Why It Happens**:
- Dashboard uses prices from previous API call
- Console just fetched fresh prices
- Race condition between price fetch and display

**Check This**:

Look at the logs for price fetch timing:
```bash
grep "Fetching current prices" logs/trading_*.log | tail -5
grep "Dashboard update" logs/trading_*.log | tail -5
```

**Expected Sequence**:
```
[10:30:15] 💰 Fetching current prices for 7 positions...
[10:30:16] 💰 Received prices for 7/7 positions
[10:30:16] 📊 Dashboard update: NIFTY25... using fetched price ₹45.20
[10:30:16] Portfolio Status: Total Value: ₹951,862.44
```

**Solution**:

The code already sends `current_prices` to dashboard (Line 9639):
```python
self.portfolio.send_dashboard_update(current_prices)
```

If still seeing old prices, check:
```bash
tail -20 logs/trading_*.log | grep -E "(Fetching|Dashboard update|using fetched price)"
```

---

### Cause 3: Multiple Trading System Instances

**Symptom**: Two different portfolios running simultaneously

**Why It Happens**:
- Started trading system twice by accident
- One process shows one portfolio, another shows different
- Dashboard shows data from one, console from the other

**Check This**:
```bash
ps aux | grep enhanced_trading_system_complete.py | grep -v grep
```

**Expected**: Only ONE process should be running

**If You See Multiple**:
```bash
# Kill all instances
pkill -f enhanced_trading_system_complete.py

# Wait
sleep 2

# Start fresh
python enhanced_trading_system_complete.py
```

---

### Cause 4: Dashboard Server Not Receiving Updates

**Symptom**: Dashboard shows initial state, never updates

**Why It Happens**:
- Dashboard connection failed
- API endpoint errors
- Network issues

**Check Dashboard Connection**:
```bash
# Check if dashboard is receiving data
curl http://localhost:8080/api/data | python -m json.tool
```

**Expected Output**:
```json
{
  "portfolio": {
    "total_value": 951862.44,
    "cash": 343591.77,
    "positions_count": 7,
    "total_pnl": -42038.48
  },
  "positions": [...]
}
```

**If API Returns Old Data**:
- Dashboard is receiving updates but displaying wrong
- Browser cache issue (see Cause 1)

**If API Returns Error**:
```bash
# Restart dashboard
pkill -f enhanced_dashboard_server.py
python enhanced_dashboard_server.py &
```

---

### Cause 5: State File Mismatch

**Symptom**: Dashboard reads from old state file

**Why It Happens**:
- Dashboard reads from `state/current_state.json`
- Trading system hasn't saved latest state yet
- File permissions issue

**Check State File**:
```bash
cat state/current_state.json | grep -E "(total_value|cash|positions_count)" | head -5
```

**Compare with Console**:
- If values match console → Dashboard not reading file
- If values don't match → State not saved yet

**Solution**:
```bash
# Check file timestamp
ls -la state/current_state.json

# Should be recent (within last minute)
# If old, state not being saved
```

**Force State Save**:
The system saves state automatically, but if needed:
```python
# In the trading system console (if in interactive mode):
self.portfolio.save_state_to_files()
```

---

### Cause 6: Calculation Difference

**Symptom**: Same prices, different calculations

**Why It Happens**:
- Console calculates unrealized P&L locally
- Dashboard calculates from API data
- Rounding differences
- Fee inclusion differences

**Debug This**:

Add this to see what's being sent:
```bash
grep "send_portfolio_update" logs/trading_*.log | tail -1
```

**Check Each Position**:

In your case with 7 positions, compare console vs dashboard for EACH position:

**Console shows**: (from logs)
```bash
grep "📈.*entry=" logs/trading_*.log | tail -7
```

**Dashboard shows**: Open browser console (F12), check Network tab:
```
Look for: /api/data
Check: positions array
```

**Manual Verification**:
```python
# For each position:
# Console: (current_price - entry_price) × shares = unrealized P&L
# Dashboard: Should show same calculation
```

---

## Quick Diagnostic Script

Run this to check all common issues:

```bash
#!/bin/bash
echo "=== Portfolio Sync Diagnostic ==="
echo ""

echo "1. Dashboard Process:"
ps aux | grep enhanced_dashboard_server.py | grep -v grep && echo "✅ Running" || echo "❌ Not running"
echo ""

echo "2. Trading System Process:"
ps aux | grep enhanced_trading_system_complete.py | grep -v grep && echo "✅ Running" || echo "❌ Not running"
echo ""

echo "3. Dashboard Response:"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080 && echo " ✅ Responding" || echo "❌ Not responding"
echo ""

echo "4. State File Age:"
if [ -f state/current_state.json ]; then
    echo "Last modified: $(stat -f "%Sm" state/current_state.json)"
else
    echo "❌ State file not found"
fi
echo ""

echo "5. Latest Dashboard Update (from logs):"
grep "Dashboard update" logs/trading_*.log | tail -1
echo ""

echo "6. Latest Price Fetch (from logs):"
grep "Fetching current prices" logs/trading_*.log | tail -1
echo ""

echo "7. Dashboard API Data:"
echo "Portfolio value from API:"
curl -s http://localhost:8080/api/data | python -c "import sys, json; data=json.load(sys.stdin); print(f\"Total Value: ₹{data['portfolio']['total_value']:,.2f}\")" 2>/dev/null || echo "❌ Failed to fetch"
echo ""
```

Save as `check_sync.sh`, make executable, and run:
```bash
chmod +x check_sync.sh
./check_sync.sh
```

---

## Step-by-Step Fix Procedure

### Step 1: Verify Current State

1. **Check console output**: Note exact values
   ```
   Total Value: ₹951,862.44
   Cash: ₹343,591.77
   Positions: 7
   Unrealized P&L: ₹-42,038.48
   ```

2. **Check dashboard**: Note exact values shown

3. **Calculate discrepancy**:
   ```
   Difference in Total Value: Dashboard - Console = ?
   Difference in Cash: Dashboard - Console = ?
   Difference in Unrealized P&L: Dashboard - Console = ?
   ```

### Step 2: Check Timing

1. **When did console update?** (timestamp from console output)
2. **When did dashboard update?** (check timestamp in dashboard footer)
3. **Time difference**: Should be < 2 seconds

If > 10 seconds → Dashboard not receiving updates

### Step 3: Force Refresh

1. **Hard refresh browser** (Ctrl+Shift+R)
2. **Wait 5 seconds**
3. **Check if values match now**

If YES → Browser cache was the issue
If NO → Continue to Step 4

### Step 4: Check Data Flow

1. **Verify dashboard is receiving updates**:
   ```bash
   tail -f logs/trading_*.log | grep -i dashboard
   ```

2. **Should see every ~60 seconds**:
   ```
   📊 Dashboard update: SYMBOL using fetched price ₹XX.XX
   ```

3. **If not seeing updates** → Dashboard connection broken

### Step 5: Restart Everything

```bash
# Stop everything
pkill -f enhanced_dashboard_server.py
pkill -f enhanced_trading_system_complete.py

# Wait
sleep 3

# Start dashboard first
python enhanced_dashboard_server.py &
sleep 3

# Open dashboard
open http://localhost:8080

# Start trading system
python enhanced_trading_system_complete.py
# Select F&O mode

# Wait for first iteration
# Check if values match
```

---

## Preventive Measures

### Always Start in This Order

1. **Dashboard first**
2. **Wait 3 seconds**
3. **Then trading system**

### Monitor Sync

Add this to your regular checks:
```bash
# Every few minutes, check if dashboard is updating
curl -s http://localhost:8080/api/data | \
  python -c "import sys, json; print(json.load(sys.stdin)['portfolio']['total_value'])"

# Should change as positions move
```

### Enable Debug Logging

Temporarily add more logging:
```bash
# In trading system, set verbose mode
python enhanced_trading_system_complete.py --verbose
```

---

## Common Patterns

### Pattern 1: Dashboard Lags Behind

**Symptoms**:
- Console: ₹951,862
- Dashboard: ₹955,000 (higher)
- Dashboard shows profit, console shows loss

**Cause**: Dashboard showing previous iteration before exits

**Fix**: Wait one more iteration (~60 seconds), should sync

---

### Pattern 2: Dashboard Ahead

**Symptoms**:
- Console: ₹951,862
- Dashboard: ₹940,000 (lower)
- Dashboard shows more loss

**Cause**: Dashboard has newer prices that console hasn't fetched yet

**Fix**: Shouldn't happen (console fetches first, then sends to dashboard)

**If it does**: Check for multiple trading system processes

---

### Pattern 3: Constant Offset

**Symptoms**:
- Always differs by same amount (e.g., ₹10,000)
- Difference doesn't change over time

**Cause**: One position not being counted/displayed

**Fix**:
- Check console shows 7 positions
- Check dashboard shows 7 positions
- If different → Position not being sent to dashboard

---

## Still Not Matching?

If after all troubleshooting they still don't match:

### Capture Exact State

```bash
# Capture console output
# When you see the mismatch, immediately:

# 1. Screenshot console
# 2. Screenshot dashboard
# 3. Capture logs:
tail -100 logs/trading_*.log > sync_issue_logs.txt

# 4. Capture state file:
cp state/current_state.json sync_issue_state.json

# 5. Capture API response:
curl http://localhost:8080/api/data > sync_issue_api.json
```

Then compare:
```bash
# Check state file
cat sync_issue_state.json | grep total_value

# Check API
cat sync_issue_api.json | python -m json.tool | grep total_value

# Should match console output: ₹951,862.44
```

---

## Most Likely Solution

Based on typical scenarios, try this FIRST:

1. **Hard refresh browser** (Ctrl+Shift+R / Cmd+Shift+R)
2. **Wait 5 seconds**
3. **Check if it matches now**

This fixes 80% of sync issues (browser cache).

If that doesn't work:

1. **Restart dashboard**: `pkill -f enhanced_dashboard_server.py && python enhanced_dashboard_server.py &`
2. **Refresh browser again**

This fixes another 15% of issues (stale dashboard state).

---

## Contact Info

If issue persists, provide:
- Console output (exact values)
- Dashboard screenshot
- Output of: `curl http://localhost:8080/api/data | python -m json.tool`
- Last 50 lines of logs: `tail -50 logs/trading_*.log`
