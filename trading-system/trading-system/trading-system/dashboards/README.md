# Grafana Dashboards

This directory contains comprehensive operational dashboards for monitoring the Enhanced NIFTY 50 Trading System.

## Available Dashboards

### 1. Trading Activity Dashboard (`trading_activity_dashboard.json`)
**Purpose:** Monitor real-time trading operations, positions, and P&L

**Key Metrics:**
- Today's P&L (total, realized, unrealized)
- Active positions and portfolio allocation
- Trade volume and success rate
- Risk metrics (exposure %, max drawdown, VaR)
- Win rate trends
- Average trade size

**Use Cases:**
- Real-time trading monitoring during market hours
- End-of-day P&L analysis
- Risk exposure monitoring
- Portfolio rebalancing decisions

**Refresh Rate:** 5 seconds

---

### 2. System Health Dashboard (`system_health_dashboard.json`)
**Purpose:** Monitor overall system health and component status

**Key Metrics:**
- System uptime and status
- Component health (Database, Redis, API, Trading System)
- Active alerts count
- CPU, Memory, Disk usage
- Network traffic
- Database connections and Redis memory
- Health check response times
- Recent error logs

**Use Cases:**
- Daily system health checks
- Incident investigation
- Capacity planning
- Performance troubleshooting

**Refresh Rate:** 10 seconds

---

### 3. Performance Metrics Dashboard (`performance_metrics_dashboard.json`)
**Purpose:** Monitor application and database performance

**Key Metrics:**
- Request latency percentiles (p50, p90, p95, p99)
- Query execution times
- Cache hit rate
- Requests per second by endpoint
- Slow query detection
- Database query rates
- Connection pool utilization
- API error rates
- Zerodha API latency
- Trade execution time

**Use Cases:**
- Performance optimization
- Query tuning
- API latency investigation
- Cache effectiveness analysis
- SLA monitoring

**Refresh Rate:** 10 seconds

---

### 4. Alert Management Dashboard (`alert_management_dashboard.json`)
**Purpose:** Centralized alert monitoring and incident management

**Key Metrics:**
- Active alerts (total and by severity)
- Average alert duration
- Alert firing timeline
- Alerts by component and severity
- Alert rate over time
- MTTD (Mean Time To Detect)
- MTTR (Mean Time To Resolve)
- Alert success rate
- Top frequent alerts
- Runbook links

**Use Cases:**
- Incident response coordination
- Alert fatigue reduction
- MTTD/MTTR tracking
- Post-mortem analysis
- Alert tuning

**Refresh Rate:** 30 seconds

---

### 5. Infrastructure Dashboard (`infrastructure_dashboard.json`)
**Purpose:** Monitor infrastructure resources and capacity

**Key Metrics:**
- CPU, Memory, Disk, Load average (gauges)
- Disk I/O and IOPS
- Network throughput and errors
- Docker container status and resource usage
- PostgreSQL connections, transactions, cache hit ratio
- Redis memory, operations, connected clients
- Resource utilization summary
- 7-day capacity forecast

**Use Cases:**
- Infrastructure capacity planning
- Resource optimization
- Container orchestration
- Database performance monitoring
- Network troubleshooting

**Refresh Rate:** 30 seconds

---

## Installation

### Method 1: Import via Grafana UI

1. Access Grafana at `http://localhost:3000` (default credentials: admin/admin)
2. Navigate to **Dashboards** → **Import**
3. Click **Upload JSON file**
4. Select the dashboard JSON file you want to import
5. Select **Prometheus** as the data source
6. Click **Import**

### Method 2: Import via API

```bash
#!/bin/bash
GRAFANA_URL="http://localhost:3000"
GRAFANA_API_KEY="your-api-key"

# Import all dashboards
for dashboard in trading-system/dashboards/*.json; do
    echo "Importing $(basename $dashboard)..."
    curl -X POST \
        -H "Authorization: Bearer ${GRAFANA_API_KEY}" \
        -H "Content-Type: application/json" \
        -d @"${dashboard}" \
        "${GRAFANA_URL}/api/dashboards/db"
done
```

### Method 3: Automated Import Script

```bash
#!/bin/bash
# Save this as scripts/import_dashboards.sh

set -euo pipefail

GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-admin}"
DASHBOARDS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../dashboards" && pwd)"

echo "Importing Grafana dashboards..."

for dashboard in "${DASHBOARDS_DIR}"/*.json; do
    filename=$(basename "$dashboard")
    echo "  → Importing ${filename}..."

    curl -s -X POST \
        -u "${GRAFANA_USER}:${GRAFANA_PASSWORD}" \
        -H "Content-Type: application/json" \
        -d @"${dashboard}" \
        "${GRAFANA_URL}/api/dashboards/db" \
        | jq -r '.status, .message'
done

echo "✅ Dashboard import completed!"
```

---

## Configuration

### Prometheus Data Source

All dashboards require Prometheus as a data source. Ensure Prometheus is configured in Grafana:

1. Go to **Configuration** → **Data Sources**
2. Add Prometheus data source
3. Set URL to `http://prometheus:9090` (or your Prometheus URL)
4. Click **Save & Test**

### Required Metrics

The dashboards expect the following metrics to be available in Prometheus:

#### Trading Metrics
- `trading_pnl_total`, `trading_pnl_realized`, `trading_pnl_unrealized`
- `trading_position_open`, `trading_position_value`
- `trading_trades_total`, `trading_trades_profitable_total`
- `trading_risk_exposure_percentage`, `trading_risk_max_drawdown_percentage`

#### System Metrics
- `up`, `process_start_time_seconds`
- `health_check_database_up`, `health_check_redis_up`, `health_check_api_up`
- `health_check_response_time_ms`

#### Performance Metrics
- `query_execution_time_ms`, `slow_queries_total`
- `cache_hits_total`, `cache_misses_total`, `cache_requests_total`
- `http_requests_total`, `http_request_duration_seconds_bucket`
- `db_connection_pool_active_connections`, `db_connection_pool_idle_connections`

#### Infrastructure Metrics (via Node Exporter)
- `node_cpu_seconds_total`, `node_memory_*`, `node_filesystem_*`
- `node_disk_*`, `node_network_*`, `node_load*`

#### Database Metrics (via PostgreSQL Exporter)
- `pg_stat_database_*`, `pg_stat_activity_*`, `pg_settings_*`

#### Redis Metrics (via Redis Exporter)
- `redis_memory_*`, `redis_commands_processed_total`, `redis_connected_clients`

#### Container Metrics (via cAdvisor)
- `container_cpu_usage_seconds_total`, `container_memory_usage_bytes`

---

## Dashboard Variables

Many dashboards include template variables for filtering:

### Trading Activity Dashboard
- No variables (shows all trading data)

### System Health Dashboard
- **Instance:** Filter by specific instance

### Performance Metrics Dashboard
- **Time Window:** Adjust aggregation window (5m, 15m, 1h, 6h)

### Alert Management Dashboard
- **Severity:** Filter alerts by severity level
- **Component:** Filter alerts by component

### Infrastructure Dashboard
- **Node:** Select specific node
- **Container:** Filter by container name

---

## Best Practices

### 1. Dashboard Organization
- Create a **Trading Operations** folder for trading-related dashboards
- Create an **Infrastructure** folder for system and infrastructure dashboards
- Star your most-used dashboards for quick access

### 2. Alert Integration
- Configure alert notifications in Grafana to send to Slack/Email/PagerDuty
- Set up alert rules for critical metrics (P&L thresholds, system health)
- Use the Alert Management Dashboard as your central incident command center

### 3. Custom Time Ranges
- Use the time picker in the top right to adjust the time range
- Common ranges: Last 15 minutes, Last 1 hour, Last 6 hours, Today
- Use "Zoom in" by selecting a region on any graph

### 4. Dashboard Annotations
- Enable annotations to mark deployments, incidents, or important events
- Annotations will appear as vertical lines on all time-series graphs

### 5. Exporting Data
- Use the "Inspect" feature on any panel to export data as CSV
- Use the "Share" feature to create shareable links or snapshots

---

## Troubleshooting

### No Data Displayed

**Issue:** Dashboard panels show "No data"

**Solutions:**
1. Verify Prometheus is running: `docker-compose ps prometheus`
2. Check Prometheus targets: `http://localhost:9090/targets`
3. Verify the data source is configured correctly in Grafana
4. Check if the trading system is running and exporting metrics

### Metrics Not Found

**Issue:** Panel shows "Metric not found" error

**Solutions:**
1. Ensure the trading system has the Prometheus exporter enabled
2. Check if the metric name matches what's exported by your application
3. Verify the metric is being scraped by Prometheus: `http://localhost:9090/graph`

### Slow Dashboard Loading

**Issue:** Dashboard takes a long time to load

**Solutions:**
1. Reduce the time range (use Last 1 hour instead of Last 24 hours)
2. Increase the refresh rate (30s instead of 5s)
3. Disable unused panels
4. Check Prometheus query performance: `http://localhost:9090/graph`

### Permission Denied

**Issue:** Cannot import or modify dashboards

**Solutions:**
1. Ensure you're logged in with admin credentials
2. Check user permissions in Grafana settings
3. If using API key, ensure it has Editor or Admin role

---

## Customization

### Adding New Panels

1. Click the **Add panel** button in the dashboard
2. Select **Add a new panel**
3. Configure your query using PromQL
4. Adjust visualization type (Graph, Stat, Table, etc.)
5. Set field options (units, thresholds, colors)
6. Save the dashboard

### Modifying Existing Panels

1. Click the panel title
2. Select **Edit**
3. Modify the query or visualization settings
4. Click **Apply** to save changes
5. Save the dashboard

### Creating Alert Rules

1. Edit a panel
2. Go to the **Alert** tab
3. Click **Create alert rule from this panel**
4. Configure alert conditions
5. Set notification channels
6. Save the alert rule

---

## Maintenance

### Regular Updates

1. **Daily:** Review the Alert Management Dashboard for any firing alerts
2. **Weekly:** Check the System Health Dashboard for capacity issues
3. **Monthly:** Review the Performance Metrics Dashboard for optimization opportunities
4. **Quarterly:** Update thresholds based on observed patterns

### Dashboard Versioning

- Export dashboards regularly as backup
- Use Git to version control dashboard JSON files
- Document any custom modifications in this README

### Performance Optimization

- Archive old dashboards that are no longer used
- Disable auto-refresh on dashboards when not actively monitoring
- Use recording rules in Prometheus for expensive queries
- Implement data retention policies in Prometheus

---

## Support

### Documentation
- Grafana Docs: https://grafana.com/docs/
- Prometheus Docs: https://prometheus.io/docs/
- PromQL Guide: https://prometheus.io/docs/prometheus/latest/querying/basics/

### Common PromQL Queries

**CPU Usage:**
```promql
100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

**Memory Usage:**
```promql
100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))
```

**Request Rate:**
```promql
sum(rate(http_requests_total[5m]))
```

**P95 Latency:**
```promql
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

**Error Rate:**
```promql
100 * (sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])))
```

---

## Dashboard Screenshots

After importing, the dashboards will look similar to:

### Trading Activity Dashboard
- Top row: P&L, Active Positions, Total Trades, Win Rate (stat panels)
- Middle rows: P&L over time, Trade volume, Active positions table, Portfolio allocation pie chart
- Bottom rows: Risk metrics bar gauge, Trade success rate, Average trade size

### System Health Dashboard
- Top row: System Status, Uptime, Database/Redis/API Status, Active Alerts
- Middle rows: CPU/Memory/Disk/Network usage over time
- Bottom rows: Component health table, Recent error logs

### Performance Metrics Dashboard
- Top row: Avg Query Time, Cache Hit Rate, Requests/sec, P95 Latency
- Middle rows: Latency percentiles, Request rate by endpoint
- Bottom rows: Slow queries table, Query recommendations

### Alert Management Dashboard
- Top row: Active Alerts, Critical Alerts, Avg Alert Duration, 24h Alert Count
- Middle: Active alerts table, Alert firing timeline
- Bottom: MTTD/MTTR trends, Top frequent alerts

### Infrastructure Dashboard
- Compute section: CPU/Memory/Disk/Load gauges
- Storage section: Disk I/O and IOPS
- Network section: Throughput and errors
- Database/Redis sections: Connection, transaction, and performance metrics
- Capacity planning: 7-day forecast

---

## License

These dashboards are part of the Enhanced NIFTY 50 Trading System and are provided as-is for operational monitoring purposes.
