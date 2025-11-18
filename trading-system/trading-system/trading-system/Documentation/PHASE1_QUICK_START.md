# Phase 1 Critical Fixes - Quick Start Guide

## ⚡ 5-Minute Setup

### 1. Set Environment Variables (REQUIRED)

Create a `.env` file or add to your shell profile:

```bash
# Copy this template and fill in your actual values
export ZERODHA_API_KEY="YOUR_ACTUAL_KEY_HERE"
export ZERODHA_API_SECRET="YOUR_ACTUAL_SECRET_HERE"
export TRADING_SECURITY_PASSWORD="YourStrongPassword123!@#"
export DATA_ENCRYPTION_KEY="$(openssl rand -hex 32)"
export DASHBOARD_API_KEY="$(openssl rand -hex 32)"
export DEVELOPMENT_MODE="false"  # NEVER set to true in production
```

### 2. Validate Configuration

```bash
python -m core.config_validator --mode live
```

**Expected Output:**
```
✅ Configuration validation successful
```

### 3. Run Tests

```bash
pytest tests/test_phase1_critical_fixes.py -v
```

**Expected:** All tests pass

### 4. Update Your Code

**Minimum Required Changes:**

```python
# At the top of your main application file
from core.config_validator import validate_config_or_exit
from core.input_sanitizer import sanitize_log, sanitize_symbol
from core.secure_path_handler import get_secure_token_path
from core.exception_handler import safe_execute

# At application startup (REQUIRED)
validate_config_or_exit(mode='live')  # or 'paper'

# When logging user input (REQUIRED)
logger.info(sanitize_log(user_input))

# When getting token path (REQUIRED - replaces Path.home())
token_path = get_secure_token_path()

# For critical API calls (RECOMMENDED)
@safe_execute("api_call", default_return=None, use_circuit_breaker=True)
def fetch_data():
    return kite.quote("NSE:RELIANCE")
```

---

## 🔍 Common Issues & Solutions

### Issue: "ZERODHA_API_KEY is not set"

**Solution:**
```bash
export ZERODHA_API_KEY="your_actual_key"
python -m core.config_validator --mode paper
```

### Issue: "API key contains placeholder text"

**Solution:** Replace with actual Zerodha API key from your account.

### Issue: "Path traversal detected"

**Solution:** Use `validate_path()` or allowed directories only:
```python
from core.secure_path_handler import validate_path
safe_path = validate_path("logs/trading.log")
```

### Issue: "Circuit breaker is OPEN"

**Solution:** Wait for timeout (default 60s) or fix underlying API issue.

---

## 📊 Quick Reference

### Sanitize User Input
```python
from core.input_sanitizer import sanitize_log, sanitize_symbol

safe_msg = sanitize_log(user_input)
safe_symbol = sanitize_symbol("RELIANCE")
```

### Validate Paths
```python
from core.secure_path_handler import validate_path, get_secure_token_path

safe_path = validate_path("logs/file.log")
token_path = get_secure_token_path()
```

### Handle Exceptions
```python
from core.exception_handler import safe_execute, retry

@safe_execute("operation", default_return=None)
def risky_operation():
    ...

@retry(max_attempts=3, delay_seconds=1.0)
def api_call():
    ...
```

---

## ✅ Pre-Deployment Checklist

Run this before deploying to production:

```bash
# 1. Validate config
python -m core.config_validator --mode live --strict

# 2. Run tests
pytest tests/test_phase1_critical_fixes.py

# 3. Check environment
env | grep -E 'ZERODHA|TRADING|DASHBOARD|DEVELOPMENT'

# 4. Verify DEVELOPMENT_MODE is false or unset
echo $DEVELOPMENT_MODE  # Should be empty or "false"
```

**All checks must pass before production deployment.**

---

## 🆘 Emergency Rollback

If Phase 1 fixes cause issues:

1. **Temporarily bypass validation** (NOT RECOMMENDED):
   ```bash
   export DEVELOPMENT_MODE="true"
   ```

2. **Use fallback configuration:**
   ```python
   # In your code, wrap validation
   try:
       validate_config_or_exit(mode='paper')
   except ConfigValidationError:
       logger.warning("Using fallback configuration")
   ```

3. **Report issue** with:
   - Output of `python -m core.config_validator`
   - Relevant logs from `logs/trading_errors_*.log`
   - Steps to reproduce

---

## 📖 Full Documentation

For complete details, see:
- **[PHASE1_CRITICAL_FIXES.md](PHASE1_CRITICAL_FIXES.md)** - Complete documentation
- **[test_phase1_critical_fixes.py](../tests/test_phase1_critical_fixes.py)** - Test suite
- Individual module docstrings in `core/` directory

---

**Quick Start Version:** 1.0
**Last Updated:** 2025-10-21
