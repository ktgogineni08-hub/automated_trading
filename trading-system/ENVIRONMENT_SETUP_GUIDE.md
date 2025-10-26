# Environment Setup Guide for Testing

This guide explains how to configure your environment to run the trading system test suite.

---

## Quick Start (TL;DR)

**For automated setup** (recommended):
```bash
cd /Users/gogineni/Python/trading-system
source scripts/setup_test_env.sh
```

**For manual setup**:
```bash
# Minimum required for testing
export DASHBOARD_API_KEY="test_dashboard_key_$(openssl rand -hex 16)"
export ZERODHA_API_KEY="test_api_key_1234567890abcdef"
export ZERODHA_API_SECRET="test_api_secret_1234567890abcdef"
export TRADING_MODE="paper"

# Verify configuration
./scripts/verify_env.sh

# Run tests
pytest tests/test_critical_fixes.py -v
```

---

## Required Environment Variables

### 1. DASHBOARD_API_KEY (Required)
**Purpose**: Authentication for dashboard API access

**Configuration**:
```bash
# Generate a secure random key
export DASHBOARD_API_KEY=$(openssl rand -hex 32)

# Or use Python
export DASHBOARD_API_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

**Validation**: Minimum 20 characters recommended

**Critical**: This variable is now **REQUIRED** by the configuration validator. Do not use placeholder values like "your_key_here".

---

### 2. ZERODHA_API_KEY (Required)
**Purpose**: Zerodha Kite API authentication (primary key)

**For Testing** (paper trading):
```bash
export ZERODHA_API_KEY="test_api_key_1234567890abcdef"
```

**For Production** (live trading):
```bash
# Get from: https://kite.zerodha.com/connect/login
export ZERODHA_API_KEY="your_actual_zerodha_api_key"
```

**Critical**: The config validator now checks for `ZERODHA_API_KEY`, not `KITE_API_KEY`.

---

### 3. ZERODHA_API_SECRET (Required)
**Purpose**: Zerodha Kite API authentication (secret key)

**For Testing** (paper trading):
```bash
export ZERODHA_API_SECRET="test_api_secret_1234567890abcdef"
```

**For Production** (live trading):
```bash
export ZERODHA_API_SECRET="your_actual_zerodha_api_secret"
```

**Critical**: The config validator now checks for `ZERODHA_API_SECRET`, not `KITE_ACCESS_TOKEN`.

---

### 4. TRADING_MODE (Recommended)
**Purpose**: Specifies trading mode (paper/live)

**Configuration**:
```bash
export TRADING_MODE="paper"  # Safe simulation mode (default)
# OR
export TRADING_MODE="live"   # Real trading with actual money
```

**Default**: If not set, defaults to "paper"

---

## Optional Environment Variables

### State Encryption
```bash
# Enable encrypted state persistence
export TRADING_SECURITY_PASSWORD="your_secure_password_here"
```

### Client Data Encryption
```bash
# Enable encrypted storage of KYC/PII data
export DATA_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

### Logging Configuration
```bash
export LOG_LEVEL="INFO"        # DEBUG, INFO, WARNING, ERROR, CRITICAL
export LOG_DIR="logs"          # Log file directory
```

### Development/Testing Flags
```bash
# WARNING: Only for testing!
export FORCE_DEVELOPMENT_MODE="false"
export DASHBOARD_DISABLE_TLS_VERIFY="false"
```

---

## Setup Methods

### Method 1: Interactive Setup Script (Recommended)

The setup script guides you through configuration:

```bash
cd /Users/gogineni/Python/trading-system
source scripts/setup_test_env.sh
```

**Features**:
- Interactive prompts
- Auto-generates test credentials
- Option to save to `.env` file
- Validates input

**Usage**:
1. Choose mode: Testing (1) or Production (2)
2. Follow prompts to enter/generate credentials
3. Optionally save to `.env` file

---

### Method 2: Manual Configuration

**Step 1**: Copy the example file
```bash
cp .env.example .env
```

**Step 2**: Edit `.env` with your values
```bash
# Edit with your preferred editor
nano .env
# OR
vim .env
# OR
code .env
```

**Step 3**: Load the environment
```bash
source .env
```

---

### Method 3: Direct Export (Temporary)

For quick one-time testing:

```bash
# Minimal test configuration
export DASHBOARD_API_KEY="test_dashboard_key_$(openssl rand -hex 16)"
export ZERODHA_API_KEY="test_api_key_1234567890abcdef"
export ZERODHA_API_SECRET="test_api_secret_1234567890abcdef"
export TRADING_MODE="paper"
```

**Note**: These variables only persist in the current shell session.

---

## Verification

### Verify Your Configuration

Run the verification script to check all environment variables:

```bash
./scripts/verify_env.sh
```

**The script checks**:
- Required variables are set
- Values are not placeholders
- Values meet minimum length requirements
- Security flags (development mode, TLS verification)
- Trading mode validity

**Example Output**:
```
==========================================
Trading System Environment Verification
==========================================

REQUIRED VARIABLES (for testing):
-------------------------------------------
Checking DASHBOARD_API_KEY (Dashboard authentication)... OK
  ✓ Set to: test_dashboard_k... (35 chars)
Checking ZERODHA_API_KEY (Zerodha API access)... OK
  ✓ Set to: test_api_key_123... (31 chars)
Checking ZERODHA_API_SECRET (Zerodha API secret)... OK
  ✓ Set to: test_api_secret_... (34 chars)

==========================================
✓ ALL CHECKS PASSED!
==========================================
```

---

## Running Tests

### Run Critical Fixes Tests Only

After configuring environment:

```bash
cd /Users/gogineni/Python/trading-system
pytest tests/test_critical_fixes.py -v
```

**Expected**: 24/24 tests passing

---

### Run Full Test Suite

```bash
# All tests with verbose output
pytest tests/ -v

# Quick mode (less verbose)
pytest tests/ -q

# With coverage report
pytest tests/ --cov=. --cov-report=term-missing

# Specific test file
pytest tests/test_rate_limiter.py -v
```

---

## Troubleshooting

### Issue: Tests fail with "DASHBOARD_API_KEY is missing"

**Cause**: The config validator now requires DASHBOARD_API_KEY

**Solution**:
```bash
export DASHBOARD_API_KEY="test_dashboard_key_$(openssl rand -hex 16)"
./scripts/verify_env.sh
```

---

### Issue: Tests fail with "ZERODHA_API_KEY is missing"

**Cause**: The config validator checks ZERODHA_API_KEY (not KITE_API_KEY)

**Solution**:
```bash
export ZERODHA_API_KEY="test_api_key_1234567890abcdef"
export ZERODHA_API_SECRET="test_api_secret_1234567890abcdef"
./scripts/verify_env.sh
```

---

### Issue: Variable set but still shows as missing

**Cause**: Variable not exported to child processes

**Solution**:
```bash
# Wrong (local variable only):
DASHBOARD_API_KEY="test_key"

# Correct (exported to environment):
export DASHBOARD_API_KEY="test_key"
```

---

### Issue: Variables disappear after closing terminal

**Cause**: Environment variables are session-specific

**Solutions**:

**Option 1**: Save to `.env` and source it each time
```bash
source .env
```

**Option 2**: Add to shell profile (permanent)
```bash
# For bash
echo 'export DASHBOARD_API_KEY="your_key"' >> ~/.bashrc
source ~/.bashrc

# For zsh
echo 'export DASHBOARD_API_KEY="your_key"' >> ~/.zshrc
source ~/.zshrc
```

**Option 3**: Use the setup script (can save to `.env`)
```bash
source scripts/setup_test_env.sh
```

---

## Security Best Practices

### For Testing/Development

✅ **DO**:
- Use dummy credentials with `TRADING_MODE=paper`
- Generate random keys for DASHBOARD_API_KEY
- Keep test credentials in `.env` (git-ignored)
- Use the provided setup scripts

❌ **DON'T**:
- Commit `.env` file to git
- Use production credentials for testing
- Share your API keys

---

### For Production

✅ **DO**:
- Use actual Zerodha credentials from official portal
- Set `TRADING_MODE=live` explicitly
- Enable state encryption (TRADING_SECURITY_PASSWORD)
- Enable data encryption (DATA_ENCRYPTION_KEY)
- Use strong, unique passwords
- Rotate credentials regularly
- Keep credentials in secure vault (not .env file)

❌ **DON'T**:
- Use test/dummy credentials
- Commit credentials to version control
- Share API keys with anyone
- Disable TLS verification in production
- Force development mode in production

---

## Summary Checklist

Before running tests, ensure:

- [ ] DASHBOARD_API_KEY is set (min 20 chars)
- [ ] ZERODHA_API_KEY is set (any value for testing)
- [ ] ZERODHA_API_SECRET is set (any value for testing)
- [ ] TRADING_MODE is "paper" for testing
- [ ] Variables are **exported** (not just set)
- [ ] Run `./scripts/verify_env.sh` to validate
- [ ] All checks pass (0 errors)

---

## Quick Reference

| Task | Command |
|------|---------|
| Interactive setup | `source scripts/setup_test_env.sh` |
| Verify configuration | `./scripts/verify_env.sh` |
| Load .env file | `source .env` |
| Run critical tests | `pytest tests/test_critical_fixes.py -v` |
| Run all tests | `pytest tests/ -v` |
| Generate random key | `openssl rand -hex 32` |

---

## Files Reference

| File | Purpose |
|------|---------|
| [.env.example](.env.example) | Template with all variables documented |
| [scripts/setup_test_env.sh](scripts/setup_test_env.sh) | Interactive setup script |
| [scripts/verify_env.sh](scripts/verify_env.sh) | Environment verification script |
| .env | Your local configuration (git-ignored) |

---

**Last Updated**: October 26, 2025
**Version**: 1.0
**Related**: COMPREHENSIVE_FIXES_REPORT.md, CRITICAL_CORRECTIONS_SUMMARY.md
