# Test Environment Setup - Quick Start Guide

**Status**: Environment configuration required before running full test suite
**Current**: Critical tests (24/24) passing ✅
**Next**: Configure environment variables for broader test suite

---

## Current Situation

You have successfully completed all critical fixes and corrections:
- ✅ 24/24 critical fix tests passing
- ✅ API rate limiter fixed
- ✅ Config validator checking correct credentials (ZERODHA_*)
- ✅ All documentation updated

**However**, to run the broader test suite (14 test files), you need to configure environment variables.

---

## What You Need to Do

### Option 1: Quick Automated Setup (Recommended - 2 minutes)

Run the interactive setup script:

```bash
cd /Users/gogineni/Python/trading-system
source scripts/setup_test_env.sh
```

**Steps**:
1. Choose option **1** (Testing/Development)
2. Script will auto-generate safe test credentials
3. Choose **y** when asked to save to `.env` file
4. Done! Variables are configured.

---

### Option 2: Quick Manual Setup (30 seconds)

Copy and paste these commands:

```bash
cd /Users/gogineni/Python/trading-system

# Set test credentials (safe for paper trading)
export DASHBOARD_API_KEY="test_dashboard_key_$(openssl rand -hex 16)"
export ZERODHA_API_KEY="test_api_key_1234567890abcdef"
export ZERODHA_API_SECRET="test_api_secret_1234567890abcdef"
export TRADING_MODE="paper"

# Verify configuration
./scripts/verify_env.sh
```

**Note**: These variables only persist in your current terminal session.

---

### Option 3: Permanent Configuration (5 minutes)

Create a `.env` file for persistent configuration:

```bash
cd /Users/gogineni/Python/trading-system

# Copy template
cp .env.example .env

# Edit .env file
# Replace the placeholder values:
#   DASHBOARD_API_KEY=your_dashboard_api_key_here_min_32_chars
#   ZERODHA_API_KEY=your_api_key_here
#   ZERODHA_API_SECRET=your_api_secret_here

# For testing, you can use:
#   DASHBOARD_API_KEY=test_dashboard_key_abc123def456ghi789jkl012
#   ZERODHA_API_KEY=test_api_key_1234567890abcdef
#   ZERODHA_API_SECRET=test_api_secret_1234567890abcdef
#   TRADING_MODE=paper

# Load variables
source .env

# Verify
./scripts/verify_env.sh
```

---

## Verification

After setup, run the verification script:

```bash
./scripts/verify_env.sh
```

**Expected output**:
```
==========================================
✓ ALL CHECKS PASSED!
==========================================

Your environment is properly configured.

Next steps:
  1. Run critical tests:
     pytest tests/test_critical_fixes.py -v

  2. Run full test suite:
     pytest tests/ -v
```

---

## Running Tests After Setup

### Critical Tests (Already Passing)
```bash
pytest tests/test_critical_fixes.py -v
# Expected: 24 passed
```

### Full Test Suite
```bash
# All tests
pytest tests/ -v

# Quick mode
pytest tests/ -q

# Specific test files
pytest tests/test_rate_limiter.py -v
pytest tests/test_security_integration.py -v
pytest tests/test_dashboard_connector.py -v
```

---

## Minimum Required Variables

For the test suite to run without errors, you need these **3 variables**:

| Variable | Example Value | Required For |
|----------|--------------|--------------|
| `DASHBOARD_API_KEY` | `test_dashboard_key_abc123...` | Dashboard tests, config validation |
| `ZERODHA_API_KEY` | `test_api_key_1234567890abcdef` | API credential validation |
| `ZERODHA_API_SECRET` | `test_api_secret_1234567890abcdef` | API credential validation |

**Note**: For paper trading tests, dummy values are sufficient. Real credentials only needed for live trading.

---

## Important Notes

### Critical Fix Applied ✅
The config validator now checks for **ZERODHA_API_KEY** and **ZERODHA_API_SECRET** (not KITE_*). This is why these specific variable names are required.

### Safe for Testing
Using dummy credentials with `TRADING_MODE=paper` is completely safe. No real trading will occur.

### Variables Scope
- Environment variables set with `export` only last for the current terminal session
- To persist across sessions, save to `.env` file and `source .env` each time
- Or add to `~/.bashrc` or `~/.zshrc` for permanent configuration

---

## Troubleshooting

### "Variables disappear when I close terminal"
**Solution**: Save to `.env` file and run `source .env` each time you open a new terminal.

### "verify_env.sh shows errors"
**Solution**: Make sure you used `export` before each variable:
```bash
export DASHBOARD_API_KEY="..."  # Correct
DASHBOARD_API_KEY="..."         # Wrong (not exported)
```

### "Tests still fail after setting variables"
**Solution**:
1. Verify variables are set: `echo $DASHBOARD_API_KEY`
2. Run verification: `./scripts/verify_env.sh`
3. Check you're in the correct directory: `pwd` should show `/Users/gogineni/Python/trading-system`

---

## Summary

**Choose your path**:

| If you want... | Use this method |
|----------------|-----------------|
| Fastest setup | Option 2 (Manual - 30 seconds) |
| Guided setup | Option 1 (Automated script) |
| Persistent config | Option 3 (.env file) |

**After setup**:
1. Run `./scripts/verify_env.sh` ✓
2. Run `pytest tests/test_critical_fixes.py -v` ✓
3. Run `pytest tests/ -v` for full suite ✓

---

**Ready to proceed?** Choose Option 1, 2, or 3 above and follow the steps!

For detailed documentation, see: [ENVIRONMENT_SETUP_GUIDE.md](ENVIRONMENT_SETUP_GUIDE.md)
