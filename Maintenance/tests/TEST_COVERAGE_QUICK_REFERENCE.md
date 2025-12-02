# Test Coverage Quick Reference
## Trading System - Core & Strategies

### Current State (November 2025)

**Overall Coverage:** 45.5% (7,632 / 16,792 lines tested)

| Category | Files | Lines | Tested | Coverage |
|----------|-------|-------|--------|----------|
| **CORE** | 28 | 15,206 | 7,632 | 45% |
| **STRATEGIES** | 9 | 1,627 | 915 | 56% |
| **TESTS** | 15 | 3,952 | - | - |

---

## Core Modules Status

### TESTED (10 modules, 7,632 lines)
```
trading_system.py              1,934  ✓
vectorized_backtester.py        702  ✓
ml_integration.py               664  ✓
advanced_analytics.py           611  ✓
advanced_risk_manager.py        602  ✓
config_validator.py             515  ✓
exception_handler.py            531  ✓
input_sanitizer.py              565  ✓
secure_path_handler.py          455  ✓
security_context.py             138  ✓
```

### CRITICAL UNTESTED (3 modules, 1,754 lines)
```
data_encryption.py              611  ✗ SECURITY
connection_pool.py              595  ✗ INFRA
async_rate_limiter.py           548  ✗ RATE LIMITING
```

### HIGH PRIORITY UNTESTED (5 modules, 3,085 lines)
```
realtime_data_pipeline.py       771  ✗
sentiment_analyzer.py           722  ✗
ml_retraining_pipeline.py       630  ✗
trading_environment.py          586  ✗
enhanced_risk_manager.py        579  ✗
```

### OTHER UNTESTED (10 modules, 3,630 lines)
```
rl_trading_agent.py             585  ✗
strategy_registry.py            515  ✗
metrics_exporter.py             511  ✗
correlation_tracker.py          505  ✗
caching.py                      434  ✗
health_check.py                 300  ✗
regime_detector.py              223  ✗
signal_aggregator.py            158  ✗
health_server.py                102  ✗
transaction.py                   94  ✗
```

---

## Strategy Modules Status

### TESTED (3 modules, 915 lines - Fixed versions)
```
bollinger_fixed.py              298  ✓ (5 tests)
rsi_fixed.py                    346  ✓ (4 tests)
moving_average_fixed.py         271  ✓ (4 tests)
```

### UNTESTED (6 modules, 691 lines)
```
momentum.py                     281  ✗ (Not even fixed version)
bollinger.py                     98  ✗ (Original)
rsi.py                           91  ✗ (Original)
volume_breakout.py               91  ✗ (Not even fixed version)
moving_average.py                84  ✗ (Original)
base.py                          46  ✗ (Base class)
```

---

## Implementation Phases

### Phase 1: CRITICAL (Weeks 1-2)
**Target: +40-55 tests, +800-1000 LOC test code**

1. data_encryption.py (15-20 tests)
2. connection_pool.py (15-20 tests)
3. async_rate_limiter.py (12-15 tests)

**Expected Coverage:** 45% → 55-60%

### Phase 2: HIGH PRIORITY (Weeks 3-4)
**Target: +45-60 tests, +900-1200 LOC test code**

4. realtime_data_pipeline.py (20-25 tests)
5. ml_retraining_pipeline.py (15-20 tests)
6. sentiment_analyzer.py (10-15 tests)

**Expected Coverage:** 55-60% → 65-70%

### Phase 3: MEDIUM PRIORITY (Weeks 5-6)
**Target: +45-65 tests, +800-1000 LOC test code**

7. trading_environment.py (15-20 tests)
8. strategy_registry.py (10-15 tests)
9. Other modules (20-30 tests)

**Expected Coverage:** 65-70% → 80-85%

### Phase 4: STRATEGY FOCUS (Weeks 7-8)
**Target: +60-80 tests, +1200-1500 LOC test code**

10. Base strategy (8-10 tests)
11. All 5 original strategies (40-50 tests)
12. Strategy integration (15-20 tests)

**Expected Coverage:** 80-85% → 95%+ core, 98%+ strategies

---

## Key Files to Test

### CRITICAL (MUST TEST - Production blockers)
- **data_encryption.py** - Security critical, 611 LOC
- **connection_pool.py** - Infrastructure critical, 595 LOC
- **async_rate_limiter.py** - Rate limiting critical, 548 LOC

### HIGH (SHOULD TEST - System stability)
- **realtime_data_pipeline.py** - Data ingestion, 771 LOC
- **sentiment_analyzer.py** - Signal generation, 722 LOC
- **ml_retraining_pipeline.py** - Model management, 630 LOC
- **trading_environment.py** - Environment setup, 586 LOC
- **enhanced_risk_manager.py** - Risk calculations, 579 LOC

### MEDIUM (NICE TO TEST - Supportive)
- **rl_trading_agent.py** - RL trading, 585 LOC
- **strategy_registry.py** - Strategy management, 515 LOC
- **metrics_exporter.py** - Metrics collection, 511 LOC
- **correlation_tracker.py** - Correlation analysis, 505 LOC
- **caching.py** - Caching logic, 434 LOC

### STRATEGIES (MUST COMPLETE)
- **base.py** - Base class, 46 LOC
- **bollinger.py** - Original, 98 LOC
- **rsi.py** - Original, 91 LOC
- **moving_average.py** - Original, 84 LOC
- **volume_breakout.py** - Original, 91 LOC
- **momentum.py** - Original, 281 LOC

---

## Test Execution

### Run All Tests
```bash
cd /Users/gogineni/Python/trading-system
pytest tests/ -v
```

### Run With Coverage
```bash
pytest tests/ --cov=core --cov=strategies --cov-report=html
```

### Run Specific Module Tests
```bash
# Core module
pytest tests/test_core_modules.py -v

# Strategy tests
pytest tests/test_week1_2_critical_fixes.py::TestBollingerBandsFixed -v
```

### Generate Coverage Report
```bash
pytest --cov=core --cov=strategies --cov-report=term-missing
```

---

## Coverage Goals

| Target | Current | Goal | Status |
|--------|---------|------|--------|
| Overall | 45.5% | 95%+ | Gap: 49.5% |
| Core | 45% | 95%+ | Gap: 50% |
| Strategies | 56% | 98%+ | Gap: 42% |
| Critical modules | 0% | 100% | Gap: 100% |
| High modules | 0% | 95%+ | Gap: 95%+ |

---

## Test Files

### Existing (15 files)
1. test_core_modules.py (604 LOC, 31 tests)
2. test_week1_2_critical_fixes.py (531 LOC, 33 tests)
3. test_week5_8_enhancements.py (544 LOC, 25 tests)
4. test_phase1_critical_fixes.py (459 LOC, 37 tests)
5. test_critical_fixes.py (457 LOC, 24 tests)
6. test_week5_8_simple.py (215 LOC, 12 tests)
7. test_all_weeks_implementation.py (509 LOC, 5 tests)
8. test_integration_dashboard_and_tokens.py (154 LOC, 2 tests)
9. test_portfolio_mixins.py (98 LOC, 3 tests)
10. test_dashboard_connector.py (97 LOC, 3 tests)
11. test_security_integration.py (118 LOC, 3 tests)
12. test_main_modes.py (59 LOC, 2 tests)
13. test_state_manager.py (55 LOC, 2 tests)
14. test_trading_loop_profile.py (44 LOC, 1 test)
15. test_rate_limiter.py (23 LOC, 2 tests)

### To Create (12 files)
1. test_data_encryption.py (15-20 tests)
2. test_connection_pool.py (15-20 tests)
3. test_async_rate_limiter.py (12-15 tests)
4. test_realtime_data_pipeline.py (20-25 tests)
5. test_ml_retraining_pipeline.py (15-20 tests)
6. test_sentiment_analyzer.py (10-15 tests)
7. test_trading_environment.py (15-20 tests)
8. test_strategy_registry.py (10-15 tests)
9. test_base_strategy.py (8-10 tests)
10. test_strategies_all.py (40-50 tests)
11. test_strategy_integration.py (15-20 tests)
12. test_other_core_modules.py (20-30 tests)

---

## Configuration Needed

### pytest.ini
```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = --cov=core --cov=strategies --cov-report=term-missing --cov-fail-under=45
```

### .coveragerc
```ini
[run]
branch = True

[report]
precision = 2
skip_covered = False

[coverage:coverage]
parallel = True
```

---

## Success Criteria

- Overall coverage: 95%+
- Core logic coverage: 95%+
- Strategy coverage: 98%+
- Critical modules: 100%
- High priority modules: 95%+
- Test execution time: < 2 minutes
- Test flakiness: < 1%

---

**Last Updated:** November 1, 2025
**Status:** Ready for Implementation
**Priority:** HIGH - Required for production deployment
