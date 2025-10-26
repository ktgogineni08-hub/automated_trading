# Configuration System Unification

## Current State (Week 1 Improvements)

### Primary Configuration: `config.py`
**Status:** ✅ Enhanced and recommended for use

The main configuration file used by core trading modules:
- **Used by:** `core/trading_system.py`, `core/signal_aggregator.py`, `core/portfolio/portfolio.py`, `utilities/dashboard.py`, `data/provider.py`
- **Features:**
  - Environment variable override support (`ZERODHA_API_KEY`, `ZERODHA_API_SECRET`, `DASHBOARD_PORT`)
  - Validation method for paper/backtest/live modes
  - Path expansion (handles `~`, environment variables, relative paths)
  - Dot notation access (`config.get("api.zerodha.api_key")`)
  - JSON persistence with merge functionality
  - Module-level attributes for backward compatibility

**Week 1 Enhancements:**
1. ✅ Added environment variable override support
2. ✅ Added `validate()` method for configuration validation
3. ✅ Improved error messages
4. ✅ Better type hints

### Secondary Configuration Files

#### `trading_config.py`
**Status:** ⚠️ Legacy - Used by documentation and archived files
- **Used by:** Legacy files in `Documentation/`, `Legacy/`, `Maintenance/`
- **Recommendation:** Migrate usage to `config.py` for consistency
- **Action:** Can be deprecated in Week 2-3

#### `unified_config.py`
**Status:** ⚠️ Partial adoption - Modern design but limited usage
- **Used by:** `core/enhanced_risk_manager.py`, tests
- **Features:** Dataclass-based, enums, separate RiskConfig
- **Recommendation:** Consider as inspiration for future config refactoring
- **Action:** Evaluate for Week 2-3 migration or integration

#### `trading_config.json`
**Status:** ✅ Active - Data storage for `config.py`
- **Purpose:** Persistent storage of configuration values
- **Used by:** `config.py` (TradingConfig class)

#### `trading_mode_config.json`
**Status:** ⚠️ Purpose unclear - investigate usage
- **Action:** Determine if still needed or can be removed

## Environment Variable Support

### Supported Variables (as of Week 1):
```bash
# API Credentials
export ZERODHA_API_KEY="your_api_key"
export ZERODHA_API_SECRET="your_api_secret"

# Dashboard
export DASHBOARD_PORT="8080"
export DASHBOARD_API_KEY="your_dashboard_key"  # For dashboard authentication

# Security
export DATA_ENCRYPTION_KEY="your_encryption_key"
export TRADING_SECURITY_PASSWORD="your_password"

# Development
export DEVELOPMENT_MODE="true"  # Enables development features
```

## Usage Examples

### Basic Usage
```python
from config import get_config

config = get_config()

# Get values
api_key = config.get("api.zerodha.api_key")
port = config.get("dashboard.port", 8080)

# Validate before running
is_valid, errors = config.validate(mode="paper")
if not is_valid:
    for error in errors:
        print(f"❌ {error}")
    exit(1)

# Check trading hours
if config.is_trading_time():
    print("Market is open!")
```

### Validation in Different Modes
```python
# Paper trading - lenient validation
is_valid, errors = config.validate(mode="paper")

# Live trading - strict validation (requires API keys)
is_valid, errors = config.validate(mode="live")

# Strict validation even in paper mode
is_valid, errors = config.validate(mode="paper", strict=True)
```

## Week 2-3 Unification Plan

### Phase 1: Assessment (Week 2)
1. ✅ Document current configuration usage (DONE - this file)
2. ⏳ Audit all imports of `trading_config.py` and `unified_config.py`
3. ⏳ Identify configuration values that differ between files
4. ⏳ Create migration compatibility layer

### Phase 2: Migration (Week 2-3)
1. ⏳ Add adapter methods to `config.py` for legacy code
2. ⏳ Update imports in non-legacy files to use `config.py`
3. ⏳ Add deprecation warnings to `trading_config.py`
4. ⏳ Test all modules with unified config

### Phase 3: Consolidation (Week 3)
1. ⏳ Remove or archive `trading_config.py` usage
2. ⏳ Integrate best features from `unified_config.py`
3. ⏳ Add configuration schema validation (JSON Schema)
4. ⏳ Create configuration migration tools

### Phase 4: Enhancement (Month 2)
1. ⏳ Add configuration profiles (dev, staging, production)
2. ⏳ Implement configuration hot-reload
3. ⏳ Add configuration versioning
4. ⏳ Create web UI for configuration management

## Configuration Validation

### Validation Levels:

**Paper Mode (Default):**
- ✅ Validates trading parameters
- ✅ Validates directory structure
- ✅ Validates dashboard port
- ⚠️ Does not require API credentials

**Backtest Mode:**
- ✅ Same as paper mode
- ✅ Additional validation for backtest parameters

**Live Mode (Strict):**
- ✅ All paper mode validations
- ✅ Requires valid API key (length > 10)
- ✅ Requires valid API secret (length > 10)
- ✅ Ensures key and secret are different
- ✅ Validates risk parameters are conservative

## Configuration Priority Order

1. **Environment Variables** (highest priority)
2. **trading_config.json** (if exists)
3. **Default Values** (fallback)

This ensures:
- Production secrets stay in environment variables
- User preferences persist in JSON
- Sensible defaults for new installations

## Best Practices

### DO:
✅ Use environment variables for secrets in production
✅ Call `config.validate()` before starting trading
✅ Use dot notation for accessing nested values
✅ Check `config.is_trading_time()` before trading
✅ Create directories with `config.create_directories()`

### DON'T:
❌ Hardcode API keys in configuration files
❌ Commit `trading_config.json` with real credentials to git
❌ Modify config at runtime without calling `save_config()`
❌ Skip validation in live mode
❌ Use different config systems in the same codebase

## Migration Guide

### From `trading_config.py`:
```python
# OLD
from trading_config import TradingConfig
config = TradingConfig()
capital = config.initial_capital

# NEW
from config import get_config
config = get_config()
capital = config.get("trading.default_capital", 1000000)
```

### From `unified_config.py`:
```python
# OLD
from unified_config import get_config, TradingMode
config = get_config()
risk = config.risk.risk_per_trade_pct

# NEW
from config import get_config
config = get_config()
risk = config.get("trading.risk_per_trade", 0.02)
```

## Testing Configuration

```bash
# Test configuration loading
python config.py

# Validate configuration
python -c "from config import get_config; is_valid, errors = get_config().validate('paper'); print('Valid!' if is_valid else errors)"
```

## Summary

**Week 1 Status:**
- ✅ Primary config enhanced with validation
- ✅ Environment variable support added
- ✅ Documentation created
- ⚠️ Legacy configs still in use (non-critical)

**Next Steps:**
- Week 2: Complete migration assessment
- Week 3: Migrate core modules to unified config
- Month 2: Full consolidation and advanced features

---
*Last Updated: 2025-10-25*
*Status: Week 1 Complete*
