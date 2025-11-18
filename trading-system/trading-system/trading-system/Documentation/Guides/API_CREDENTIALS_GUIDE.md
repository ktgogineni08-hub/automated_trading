# API Credentials Guide

## Overview

The trading system now supports **three ways** to provide Zerodha API credentials:

1. **Environment Variables** (Recommended for production)
2. **Interactive Input** (Quick testing and manual entry)
3. **No Credentials** (Paper mode and backtesting)

---

## Method 1: Environment Variables (Recommended)

### Setup Once
```bash
export ZERODHA_API_KEY="your_api_key_here"
export ZERODHA_API_SECRET="your_api_secret_here"
```

### Make Permanent (Optional)
Add to your `.bashrc` or `.zshrc`:
```bash
echo 'export ZERODHA_API_KEY="your_api_key_here"' >> ~/.bashrc
echo 'export ZERODHA_API_SECRET="your_api_secret_here"' >> ~/.bashrc
source ~/.bashrc
```

### Or Use Setup Script
```bash
./setup_credentials.sh
```

### Pros
- ✅ Secure (not visible in code)
- ✅ Convenient (set once, use everywhere)
- ✅ Production-ready
- ✅ No prompts during startup

### Cons
- ⚠️ Requires shell configuration

---

## Method 2: Interactive Input ⭐ **NEW**

### How It Works

When you run the system without environment variables, you'll be prompted:

#### Paper Trading Mode
```
🔐 Setting up Zerodha Authentication...
ℹ️  No credentials found in environment

📝 Enter API credentials? (y/n, default=n):
```

- **Press 'n' or Enter**: Continue without credentials (paper mode only)
- **Press 'y'**: Enter credentials manually

#### Live Trading Mode
```
🔐 Setting up Zerodha Authentication...
⚠️  No credentials found in environment

🔴 LIVE TRADING requires API credentials
   Option 1: Set environment variables (ZERODHA_API_KEY, ZERODHA_API_SECRET)
   Option 2: Enter them now

🔐 Enter API credentials now? (y/n):
```

- **Press 'y'**: Enter credentials (required for live mode)
- **Press 'n'**: Exit with error (live mode needs credentials)

### Example Session
```
🔐 Setting up Zerodha Authentication...
ℹ️  No credentials found in environment

📝 Enter API credentials? (y/n, default=n): y

🔐 Please enter your Zerodha API credentials:
   API Key: abc123xyz
   API Secret: secret456def

✅ API credentials entered manually
✅ Zerodha authentication successful
👤 Account: John Doe
💰 Available Cash: ₹50,000.00
```

### Pros
- ✅ Quick and easy for testing
- ✅ No file configuration needed
- ✅ Can enter different credentials each run
- ✅ Good for demonstrations

### Cons
- ⚠️ Must enter every time you run
- ⚠️ Visible in terminal (use in private terminal)
- ⚠️ Not suitable for automated scripts

---

## Method 3: No Credentials (Paper Mode Only)

### When To Use
- Testing the system
- Learning how it works
- Backtesting with historical data
- Developing new features

### Limitations
- ❌ Cannot connect to Zerodha broker
- ❌ No real-time market data
- ❌ Cannot place actual orders
- ✅ Paper trading with synthetic data works

### Example
```
🔐 Setting up Zerodha Authentication...
ℹ️  No credentials found in environment

📝 Enter API credentials? (y/n, default=n): n

ℹ️  Paper trading mode - running without broker connection
📝 PAPER TRADING MODE - Safe Learning Environment!
```

---

## Comparison Table

| Feature | Environment Variables | Interactive Input | No Credentials |
|---------|----------------------|-------------------|----------------|
| **Ease of Setup** | Medium | Easy | Very Easy |
| **Security** | High | Medium | N/A |
| **Convenience** | High | Low | High |
| **Production Use** | ✅ Yes | ❌ No | ❌ No |
| **Paper Trading** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Live Trading** | ✅ Yes | ✅ Yes | ❌ No |
| **Automation** | ✅ Yes | ❌ No | ✅ Yes (paper only) |
| **Terminal Privacy** | ✅ Hidden | ⚠️ Visible | ✅ N/A |

---

## Security Best Practices

### ✅ DO
- Use environment variables for production
- Clear terminal history after entering credentials
- Use private/secure terminal sessions
- Keep credentials confidential
- Rotate API keys periodically

### ❌ DON'T
- Share terminals after entering credentials
- Save credentials in shell history
- Use same credentials across multiple systems
- Enter credentials in public/shared terminals
- Commit credentials to git repositories

---

## Usage Examples

### Example 1: Quick Test with Interactive Input
```bash
# No environment variables set
python3 enhanced_trading_system_complete.py

# When prompted:
# 📝 Enter API credentials? (y/n, default=n): y
# Enter your keys...
```

### Example 2: Production with Environment Variables
```bash
# Set credentials once
export ZERODHA_API_KEY="abc123xyz"
export ZERODHA_API_SECRET="secret456def"

# Run system (no prompts)
python3 enhanced_trading_system_complete.py
```

### Example 3: Paper Trading Without Credentials
```bash
# No environment variables
python3 enhanced_trading_system_complete.py

# When prompted:
# 📝 Enter API credentials? (y/n, default=n): n
# Paper mode continues...
```

### Example 4: Automation Script
```bash
#!/bin/bash
# automated_trading.sh

# Export credentials from secure vault
export ZERODHA_API_KEY=$(get_from_vault api_key)
export ZERODHA_API_SECRET=$(get_from_vault api_secret)

# Run trading system (no prompts)
python3 enhanced_trading_system_complete.py --mode live
```

---

## Troubleshooting

### "No credentials found" appears every time
**Solution**: Set environment variables permanently in `.bashrc` or `.zshrc`

### "Authentication failed" after entering credentials
**Possible causes**:
1. Incorrect API key or secret
2. API keys disabled on Zerodha
3. Network connectivity issues
4. Zerodha API service down

**Solution**: Verify credentials on Kite Connect dashboard

### Interactive prompt doesn't appear
**Possible causes**:
1. Running in non-interactive environment (cron, systemd)
2. Input redirected from file

**Solution**: Use environment variables for non-interactive environments

### Credentials visible in terminal history
**Solution**: Clear history after entering:
```bash
history -d -1  # Delete last command (bash)
# Or
history delete --last  # Delete last command (fish)
```

---

## Migration Guide

### From Hardcoded Credentials (Old System)
**Before** (INSECURE):
```python
API_KEY = "abc123xyz"  # ❌ Hardcoded
API_SECRET = "secret456"  # ❌ Hardcoded
```

**After** (SECURE):
```bash
# Option 1: Environment variables
export ZERODHA_API_KEY="abc123xyz"
export ZERODHA_API_SECRET="secret456"

# Option 2: Interactive input when prompted
# Enter manually each run
```

### From Config Files
**Before**:
```json
{
  "api_key": "abc123xyz",
  "api_secret": "secret456"
}
```

**After**:
```bash
# Load from secure config to environment
export ZERODHA_API_KEY=$(jq -r .api_key secure_config.json)
export ZERODHA_API_SECRET=$(jq -r .api_secret secure_config.json)
```

---

## FAQ

### Q: Which method should I use?
**A**:
- **Production/Live Trading**: Environment variables
- **Quick Testing**: Interactive input
- **Learning/Development**: No credentials (paper mode)

### Q: Are my credentials safe with interactive input?
**A**: They are safer than hardcoding, but:
- Visible in terminal while typing
- May appear in terminal history
- Use environment variables for production

### Q: Can I use interactive input in automated scripts?
**A**: No, interactive input requires manual entry. Use environment variables for automation.

### Q: What happens if I enter wrong credentials?
**A**: Authentication will fail with a clear error message. You can restart and try again.

### Q: Can I skip credentials in live mode?
**A**: No, live trading requires valid credentials to connect to Zerodha and place real orders.

### Q: How do I change credentials mid-session?
**A**: You must restart the trading system. Credentials are loaded once at startup.

---

## Quick Reference

### Start with Environment Variables
```bash
export ZERODHA_API_KEY="your_key"
export ZERODHA_API_SECRET="your_secret"
python3 enhanced_trading_system_complete.py
```

### Start with Interactive Input
```bash
python3 enhanced_trading_system_complete.py
# Answer 'y' when prompted
# Enter credentials manually
```

### Start Without Credentials (Paper Mode)
```bash
python3 enhanced_trading_system_complete.py
# Answer 'n' when prompted
# Or just press Enter
```

---

**Last Updated**: 2025-10-08
**Version**: 1.2
**Note**: Interactive input feature added for user convenience while maintaining security.
