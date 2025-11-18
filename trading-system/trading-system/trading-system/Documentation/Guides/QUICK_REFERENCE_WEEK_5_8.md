# Quick Reference: Week 5-8 Components

**Quick start guide for Performance Monitor, Log Correlator, and Advanced Analytics**

---

## Performance Monitor

### Basic Setup

```python
from infrastructure.performance_monitor import get_performance_monitor, MetricType

monitor = get_performance_monitor()

# Start background monitoring
monitor.start_background_monitoring(interval_seconds=60)
```

### Establish Baselines (After 24h operation)

```python
# Establish baselines for key metrics
monitor.establish_baseline(MetricType.CPU_PERCENT)
monitor.establish_baseline(MetricType.MEMORY_MB)
monitor.establish_baseline(MetricType.API_LATENCY_MS)
monitor.establish_baseline(MetricType.ORDER_LATENCY_MS)
```

### Track Operations

```python
# Track any operation
with monitor.track_operation('fetch_market_data') as tracker:
    data = api.fetch_data()
    tracker.set_result({'symbols_fetched': len(data)})

# Track order placement
with monitor.track_operation('place_order') as tracker:
    order_id = broker.place_order(symbol, quantity, price)
    tracker.set_result({'order_id': order_id, 'status': 'success'})
```

### Check for Anomalies

```python
# Detect anomalies (automatic alerting)
anomalies = monitor.detect_anomalies()

for anomaly in anomalies:
    print(f"⚠️ Anomaly: {anomaly.metric_type.value}")
    print(f"   Value: {anomaly.value:.2f}")
    print(f"   Expected: {anomaly.baseline.mean:.2f} ± {anomaly.baseline.std:.2f}")
    print(f"   Z-score: {anomaly.z_score:.2f}")
```

### Memory Leak Detection

```python
# Check for memory leaks
monitor.detect_memory_leak()  # Auto-alerts if detected
```

---

## Log Correlator

### Basic Setup

```python
from infrastructure.log_correlator import LogCorrelator, LogEntry

correlator = LogCorrelator()
```

### Ingest Logs

```python
# Option 1: From log file
correlator.ingest_log_file('logs/trading_system.log')

# Option 2: Programmatically
entry = LogEntry(
    timestamp=datetime.now(),
    level='INFO',
    component='strategy',
    message='Signal generated: BUY RELIANCE @ 2450',
    correlation_id='TRADE_12345'
)
correlator.ingest_log_entry(entry)
```

### Track Trade Lifecycle

```python
# Get all logs for a specific trade
correlated = correlator.get_correlated_logs('TRADE_12345')

print(f"\n📊 Trade {correlated.correlation_id}")
print(f"   Components involved: {', '.join(correlated.components)}")
print(f"   Total logs: {len(correlated.entries)}")
print(f"   Errors: {correlated.error_count}")
print(f"   Duration: {correlated.duration_seconds:.2f}s\n")

# Print timeline
for entry in correlated.entries:
    timestamp = entry['timestamp']
    component = entry['component']
    message = entry['message']
    print(f"[{timestamp}] {component}: {message}")
```

### Find Error Patterns

```python
# Analyze recent errors
patterns = correlator.analyze_error_patterns(hours=24)

print("\n🔍 Top Error Patterns (Last 24h):\n")
for i, pattern in enumerate(patterns[:10], 1):
    print(f"{i}. {pattern['pattern']}")
    print(f"   Count: {pattern['count']}")
    print(f"   Last seen: {pattern['last_seen']}\n")
```

### Query Logs

```python
# Query with filters
logs = correlator.query_logs(
    start_time=datetime.now() - timedelta(hours=1),
    end_time=datetime.now(),
    level='ERROR',
    component='execution'
)

for log in logs:
    print(f"[{log['timestamp']}] {log['message']}")
```

---

## Advanced Analytics

### Basic Setup

```python
from analytics.advanced_analytics import get_analytics

analytics = get_analytics()
```

### Strategy Performance Prediction

```python
# Predict strategy performance for next 7 days
prediction = analytics.predict_strategy_performance('RSI_Fixed', lookback_days=30)

if prediction:
    print(f"\n📈 Strategy: {prediction.strategy_name}")
    print(f"   Recommendation: {prediction.recommendation.upper()}")
    print(f"   Confidence: {prediction.confidence.value}")
    print(f"   Predicted Win Rate: {prediction.predicted_win_rate:.1%}")
    print(f"   Predicted 7d Profit: ₹{prediction.predicted_profit:,.2f}")

    print(f"\n   Factors:")
    for key, value in prediction.factors.items():
        print(f"   - {key}: {value:.3f}")
else:
    print("⚠️ Insufficient data for prediction")
```

### Market Regime Detection

```python
import pandas as pd

# Get price data
price_data = pd.DataFrame({'close': historical_prices})

# Detect regime
regime = analytics.detect_market_regime(price_data, lookback_periods=50)

print(f"\n🌐 Market Regime: {regime.regime}")
print(f"   Confidence: {regime.confidence:.2%}")
print(f"   Volatility Forecast: {regime.volatility_forecast:.2%}")
print(f"\n   Recommended Strategies:")
for strategy in regime.recommended_strategies:
    print(f"   - {strategy}")
```

### Calculate Risk Metrics

```python
# Calculate Sharpe Ratio
returns = [0.01, 0.02, -0.01, 0.015, ...]  # Daily returns
sharpe = analytics.calculate_sharpe_ratio(returns, risk_free_rate=0.05)
print(f"Sharpe Ratio: {sharpe:.2f}")

# Calculate Sortino Ratio (downside deviation only)
sortino = analytics.calculate_sortino_ratio(returns, risk_free_rate=0.05)
print(f"Sortino Ratio: {sortino:.2f}")

# Calculate Maximum Drawdown
equity_curve = [10000, 10500, 11000, 10200, ...]  # Portfolio values
max_dd, start_idx, end_idx = analytics.calculate_max_drawdown(equity_curve)
print(f"Max Drawdown: {max_dd:.2%}")
print(f"Drawdown period: {start_idx} to {end_idx}")
```

### Generate Performance Report

```python
# Comprehensive performance report
report = analytics.generate_performance_report('RSI_Fixed', days=30)

print(f"\n{'='*70}")
print(f"📊 Performance Report: {report['strategy']}")
print(f"{'='*70}")
print(f"Period: {report['period_days']} days")
print(f"Total Trades: {report['total_trades']}")
print(f"Win Rate: {report['win_rate']:.1%}")
print(f"\nP&L:")
print(f"  Total: ₹{report['total_pnl']:,.2f}")
print(f"  Avg Profit: ₹{report['avg_profit']:,.2f}")
print(f"  Avg Loss: ₹{report['avg_loss']:,.2f}")
print(f"  Profit Factor: {report['profit_factor']:.2f}")
print(f"\nRisk Metrics:")
print(f"  Sharpe Ratio: {report['sharpe_ratio']:.2f}")
print(f"  Sortino Ratio: {report['sortino_ratio']:.2f}")
print(f"  Max Drawdown: {report['max_drawdown_pct']:.2f}%")
print(f"\nReturn: {report['return_pct']:.2f}%")

if report.get('prediction'):
    pred = report['prediction']
    print(f"\n🔮 Prediction ({pred.confidence.value}):")
    print(f"  Next 7d PnL: ₹{pred.predicted_profit:,.2f}")
    print(f"  Recommendation: {pred.recommendation.upper()}")
```

### Get Best Strategy Recommendation

```python
# Let analytics recommend best strategy for current conditions
best_strategy = analytics.recommend_strategy()

if best_strategy:
    print(f"\n✅ Recommended Strategy: {best_strategy}")

    # Get full prediction for recommended strategy
    prediction = analytics.predict_strategy_performance(best_strategy)
    if prediction:
        print(f"   Expected Win Rate: {prediction.predicted_win_rate:.1%}")
        print(f"   Expected 7d Profit: ₹{prediction.predicted_profit:,.2f}")
else:
    print("⚠️ No strategy recommendation available")
```

---

## Integration Example

### Complete Trading System Integration

```python
from infrastructure.performance_monitor import get_performance_monitor, MetricType
from infrastructure.log_correlator import LogCorrelator, LogEntry
from analytics.advanced_analytics import get_analytics
import pandas as pd
from datetime import datetime

# Initialize all components
monitor = get_performance_monitor()
correlator = LogCorrelator()
analytics = get_analytics()

# Start monitoring
monitor.start_background_monitoring(interval_seconds=60)

# Establish baselines (after 24h)
monitor.establish_baseline(MetricType.CPU_PERCENT)
monitor.establish_baseline(MetricType.MEMORY_MB)

def execute_trade(symbol, action, quantity, price):
    """Execute trade with full monitoring and logging"""
    trade_id = f"TRADE_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Log: Signal generated
    correlator.ingest_log_entry(LogEntry(
        timestamp=datetime.now(),
        level='INFO',
        component='strategy',
        message=f'Signal: {action} {symbol} @ {price}',
        correlation_id=trade_id
    ))

    # Track execution performance
    with monitor.track_operation('execute_trade') as tracker:
        try:
            # Risk check
            correlator.ingest_log_entry(LogEntry(
                timestamp=datetime.now(),
                level='INFO',
                component='risk_manager',
                message=f'Risk check passed for {trade_id}',
                correlation_id=trade_id
            ))

            # Execute order
            order_id = broker.place_order(symbol, action, quantity, price)

            # Log success
            correlator.ingest_log_entry(LogEntry(
                timestamp=datetime.now(),
                level='INFO',
                component='execution',
                message=f'Order placed: {order_id}',
                correlation_id=trade_id
            ))

            tracker.set_result({
                'trade_id': trade_id,
                'order_id': order_id,
                'status': 'success'
            })

            return order_id

        except Exception as e:
            # Log error
            correlator.ingest_log_entry(LogEntry(
                timestamp=datetime.now(),
                level='ERROR',
                component='execution',
                message=f'Order failed: {str(e)}',
                correlation_id=trade_id
            ))

            tracker.set_result({'status': 'failed', 'error': str(e)})
            raise

def daily_analysis():
    """Daily strategy analysis and recommendations"""

    # 1. Check for anomalies
    anomalies = monitor.detect_anomalies()
    if anomalies:
        print(f"\n⚠️ {len(anomalies)} performance anomalies detected!")
        for anomaly in anomalies:
            print(f"   - {anomaly.metric_type.value}: {anomaly.value:.2f} (Z={anomaly.z_score:.2f})")

    # 2. Check for memory leaks
    monitor.detect_memory_leak()

    # 3. Analyze error patterns
    patterns = correlator.analyze_error_patterns(hours=24)
    if patterns:
        print(f"\n🔍 Top 3 Error Patterns:")
        for pattern in patterns[:3]:
            print(f"   {pattern['count']}x: {pattern['pattern']}")

    # 4. Get market regime
    price_data = pd.DataFrame({'close': get_historical_prices()})
    regime = analytics.detect_market_regime(price_data)
    print(f"\n🌐 Market Regime: {regime.regime} (confidence: {regime.confidence:.2%})")

    # 5. Get best strategy
    best_strategy = analytics.recommend_strategy()
    print(f"\n✅ Recommended Strategy: {best_strategy}")

    # 6. Generate performance report
    analytics.print_performance_report(best_strategy, days=7)

# Run daily analysis
if __name__ == '__main__':
    daily_analysis()
```

---

## Common Use Cases

### 1. Debugging Failed Trades

```python
# Get all logs for failed trade
correlated = correlator.get_correlated_logs('TRADE_FAILED_12345')

print(f"Trade failed after {correlated.duration_seconds:.2f}s")
print(f"Components involved: {', '.join(correlated.components)}")

for entry in correlated.entries:
    if entry['level'] == 'ERROR':
        print(f"❌ {entry['timestamp']}: {entry['message']}")
```

### 2. Identifying Performance Degradation

```python
# Check if execution is slowing down
recent_ops = monitor.get_recent_operations('execute_trade', hours=1)
avg_duration = sum(op['duration_ms'] for op in recent_ops) / len(recent_ops)

if avg_duration > 5000:  # >5 seconds
    print(f"⚠️ Slow execution detected: {avg_duration/1000:.2f}s average")

    # Check for anomalies
    anomalies = monitor.detect_anomalies()
    for anomaly in anomalies:
        if anomaly.metric_type == MetricType.ORDER_LATENCY_MS:
            print(f"   Root cause: High order latency ({anomaly.value:.0f}ms)")
```

### 3. Strategy Selection Based on Market Conditions

```python
# Get current market regime
price_data = pd.DataFrame({'close': get_recent_prices()})
regime = analytics.detect_market_regime(price_data)

# Get predictions for all strategies
strategy_predictions = []
for strategy in ['RSI_Fixed', 'Bollinger_Fixed', 'MovingAverage_Fixed']:
    pred = analytics.predict_strategy_performance(strategy)
    if pred:
        strategy_predictions.append(pred)

# Filter by regime-appropriate strategies
suitable = [p for p in strategy_predictions
           if p.strategy_name in regime.recommended_strategies]

# Choose best
if suitable:
    best = max(suitable, key=lambda p: p.predicted_profit)
    print(f"✅ Using {best.strategy_name} for {regime.regime} market")
```

---

## Cheat Sheet

### Performance Monitor

| Task | Code |
|------|------|
| Start monitoring | `monitor.start_background_monitoring(60)` |
| Track operation | `with monitor.track_operation('name') as t: ...` |
| Establish baseline | `monitor.establish_baseline(MetricType.CPU_PERCENT)` |
| Detect anomalies | `anomalies = monitor.detect_anomalies()` |
| Check memory leak | `monitor.detect_memory_leak()` |

### Log Correlator

| Task | Code |
|------|------|
| Ingest log file | `correlator.ingest_log_file('path/to/file.log')` |
| Get correlated logs | `correlated = correlator.get_correlated_logs('TRADE_ID')` |
| Find error patterns | `patterns = correlator.analyze_error_patterns(hours=24)` |
| Query logs | `logs = correlator.query_logs(level='ERROR', component='execution')` |

### Advanced Analytics

| Task | Code |
|------|------|
| Predict strategy | `pred = analytics.predict_strategy_performance('RSI_Fixed')` |
| Detect regime | `regime = analytics.detect_market_regime(price_data)` |
| Calculate Sharpe | `sharpe = analytics.calculate_sharpe_ratio(returns)` |
| Get max drawdown | `dd, start, end = analytics.calculate_max_drawdown(equity)` |
| Recommend strategy | `best = analytics.recommend_strategy()` |
| Performance report | `analytics.print_performance_report('RSI_Fixed', days=30)` |

---

**For full documentation, see:**
- [Week 5-8 Enhancement Report](../Reports/WEEK_5_8_ENHANCEMENTS_COMPLETE.md)
- [Performance Monitor API](infrastructure/performance_monitor.py)
- [Log Correlator API](infrastructure/log_correlator.py)
- [Advanced Analytics API](analytics/advanced_analytics.py)
