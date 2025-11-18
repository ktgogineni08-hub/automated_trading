# Monitoring and Alerting Playbook
## Enhanced NIFTY 50 Trading System

**Version:** 1.0
**Last Updated:** Week 4 - Production Go-Live
**Owner:** SRE Team

---

## Table of Contents

1. [Overview](#overview)
2. [Monitoring Architecture](#monitoring-architecture)
3. [Alert Configuration](#alert-configuration)
4. [Alert Response Playbooks](#alert-response-playbooks)
5. [On-Call Procedures](#on-call-procedures)
6. [Alert Tuning](#alert-tuning)
7. [Metrics Reference](#metrics-reference)

---

## Overview

### Monitoring Philosophy

**Goals:**
- **Proactive detection** of issues before they impact trading
- **Rapid response** with clear, actionable alerts
- **Minimal false positives** to prevent alert fatigue
- **Comprehensive coverage** of all critical components

**Principles:**
- Monitor symptoms (user-facing issues) not causes
- Alert on what requires human intervention
- Every alert must be actionable
- Context is provided in alert messages
- Runbooks linked from alerts

---

## Monitoring Architecture

### Stack Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Trading Application                      │
│  (Exports metrics via /metrics endpoint)                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                      Prometheus                              │
│  - Scrapes metrics every 15s                                 │
│  - Stores time-series data (15 days retention)               │
│  - Evaluates alert rules every 30s                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                     Alertmanager                             │
│  - Routes alerts                                             │
│  - Deduplicates                                              │
│  - Groups related alerts                                     │
│  - Sends to notification channels                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┼────────────┬────────────┐
          ▼            ▼            ▼            ▼
       Slack      PagerDuty      Email        SMS
```

### Components

| Component | Purpose | Port | Data Retention |
|-----------|---------|------|----------------|
| Prometheus | Metrics collection & storage | 9090 | 15 days |
| Alertmanager | Alert routing & notification | 9093 | N/A |
| Grafana | Visualization & dashboards | 3000 | N/A |
| Node Exporter | System metrics | 9100 | N/A |
| PostgreSQL Exporter | Database metrics | 9187 | N/A |
| Redis Exporter | Cache metrics | 9121 | N/A |
| cAdvisor | Container metrics | 8080 | N/A |

---

## Alert Configuration

### Alert Severity Levels

| Level | Color | Response Time | Notification | Examples |
|-------|-------|---------------|--------------|----------|
| **Critical** (P0) | 🔴 Red | < 5 minutes | PagerDuty + SMS + Slack | Trading system down, Database unavailable |
| **High** (P1) | 🟠 Orange | < 15 minutes | PagerDuty + Slack | High error rate, Disk 90% full |
| **Medium** (P2) | 🟡 Yellow | < 1 hour | Slack | Slow queries, Memory high |
| **Low** (P3) | 🔵 Blue | Next business day | Slack | Backup warning, Certificate expiring |
| **Info** (P4) | ⚪ White | No action required | Slack | Deployment completed, Test passed |

### Alert States

- **Firing:** Alert condition is currently true
- **Pending:** Alert condition is true but hasn't exceeded `for` duration yet
- **Resolved:** Alert condition is no longer true

---

### Prometheus Alert Rules

File: `prometheus/alerts.yml`

```yaml
groups:
  # ═══════════════════════════════════════════════════════════════════
  # CRITICAL ALERTS (P0)
  # ═══════════════════════════════════════════════════════════════════

  - name: critical_alerts
    interval: 30s
    rules:

      # Trading System Down
      - alert: TradingSystemDown
        expr: up{job="trading-system"} == 0
        for: 1m
        labels:
          severity: critical
          component: trading-system
          runbook: https://docs.example.com/runbooks/system-down
        annotations:
          summary: "Trading system is down"
          description: "Trading system has been unreachable for more than 1 minute. RTO: 5 minutes."
          impact: "Trading is completely unavailable. Revenue impact: ₹50,000/minute"
          action: "1. Check container status\n2. Review logs\n3. Restart if needed\n4. Activate DR if primary site down"

      # Database Unavailable
      - alert: DatabaseUnavailable
        expr: health_check_database_up == 0
        for: 30s
        labels:
          severity: critical
          component: database
          runbook: https://docs.example.com/runbooks/database-failure
        annotations:
          summary: "PostgreSQL database is unavailable"
          description: "Database health check has failed for 30 seconds."
          impact: "All trading operations blocked. Cannot save or retrieve data."
          action: "1. Check PostgreSQL status\n2. Check disk space\n3. Review PostgreSQL logs\n4. Promote replica if primary failed"

      # Redis Unavailable
      - alert: RedisUnavailable
        expr: health_check_redis_up == 0
        for: 1m
        labels:
          severity: critical
          component: redis
          runbook: https://docs.example.com/runbooks/redis-failure
        annotations:
          summary: "Redis cache is unavailable"
          description: "Redis health check has failed for 1 minute."
          impact: "Performance degradation. Cache misses will increase database load."
          action: "1. Check Redis status\n2. Check memory usage\n3. Restart Redis if needed"

      # Data Corruption Detected
      - alert: DataCorruptionDetected
        expr: data_integrity_check_failed > 0
        for: 0s
        labels:
          severity: critical
          component: data-integrity
          runbook: https://docs.example.com/runbooks/data-corruption
        annotations:
          summary: "Data corruption detected"
          description: "Data integrity check has detected corruption: {{ $value }} issues found."
          impact: "Trading decisions may be based on incorrect data. Financial risk."
          action: "1. STOP TRADING IMMEDIATELY\n2. Verify scope of corruption\n3. Restore from backup\n4. Do NOT proceed until verified"

      # High Trade Error Rate
      - alert: HighTradeErrorRate
        expr: (sum(rate(trade_errors_total[5m])) / sum(rate(trades_total[5m]))) > 0.10
        for: 2m
        labels:
          severity: critical
          component: trading
          runbook: https://docs.example.com/runbooks/high-error-rate
        annotations:
          summary: "Trade error rate is {{ $value | humanizePercentage }}"
          description: "More than 10% of trades are failing."
          impact: "Unable to execute trades. Money at risk. Potential opportunity loss."
          action: "1. Check Zerodha API status\n2. Review trade logs\n3. Check network connectivity\n4. Verify order parameters"

  # ═══════════════════════════════════════════════════════════════════
  # HIGH ALERTS (P1)
  # ═══════════════════════════════════════════════════════════════════

  - name: high_alerts
    interval: 30s
    rules:

      # High Latency
      - alert: HighLatency
        expr: histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) > 1
        for: 5m
        labels:
          severity: high
          component: performance
        annotations:
          summary: "P95 latency is {{ $value }}s"
          description: "95th percentile latency has been above 1 second for 5 minutes."
          impact: "Slow response times. Potential missed trading opportunities."
          action: "1. Check database query performance\n2. Review slow query log\n3. Check system resources (CPU, memory)\n4. Consider scaling"

      # Disk Space Critical
      - alert: DiskSpaceCritical
        expr: (1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100 > 90
        for: 5m
        labels:
          severity: high
          component: infrastructure
        annotations:
          summary: "Disk space is {{ $value | humanize }}% full"
          description: "Disk usage on {{ $labels.mountpoint }} has exceeded 90%."
          impact: "Risk of system failure. Database writes may fail. Logs may stop."
          action: "1. Clean old logs\n2. Remove old backups\n3. Archive historical data\n4. Expand disk if needed"

      # Memory Pressure
      - alert: MemoryPressure
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 90
        for: 10m
        labels:
          severity: high
          component: infrastructure
        annotations:
          summary: "Memory usage is {{ $value | humanize }}%"
          description: "Available memory is below 10% for 10 minutes."
          impact: "Risk of OOM killer. System instability. Potential crashes."
          action: "1. Identify memory-hungry processes\n2. Check for memory leaks\n3. Restart services if needed\n4. Consider scaling up"

      # Replication Lag High
      - alert: ReplicationLagHigh
        expr: (pg_replication_lag_seconds > 60)
        for: 5m
        labels:
          severity: high
          component: database
        annotations:
          summary: "Database replication lag is {{ $value }}s"
          description: "Replica is {{ $value }} seconds behind primary."
          impact: "DR site not up-to-date. Higher RPO if primary fails."
          action: "1. Check network between primary and replica\n2. Check replica resources\n3. Review PostgreSQL replication logs"

  # ═══════════════════════════════════════════════════════════════════
  # MEDIUM ALERTS (P2)
  # ═══════════════════════════════════════════════════════════════════

  - name: medium_alerts
    interval: 1m
    rules:

      # Slow Queries
      - alert: SlowQueries
        expr: rate(slow_queries_total[5m]) > 5
        for: 10m
        labels:
          severity: medium
          component: performance
        annotations:
          summary: "{{ $value }} slow queries per second"
          description: "Query execution time exceeding threshold."
          impact: "Performance degradation. Increased latency."
          action: "1. Review slow query log\n2. Check query execution plans\n3. Add indexes if needed\n4. Optimize queries"

      # Cache Hit Rate Low
      - alert: CacheHitRateLow
        expr: (sum(rate(cache_hits_total[5m])) / sum(rate(cache_requests_total[5m]))) < 0.70
        for: 15m
        labels:
          severity: medium
          component: performance
        annotations:
          summary: "Cache hit rate is {{ $value | humanizePercentage }}"
          description: "Cache effectiveness is below 70%."
          impact: "Increased database load. Higher latency."
          action: "1. Review cache strategy\n2. Check Redis memory\n3. Adjust TTL values\n4. Warm up cache"

      # SSL Certificate Expiring
      - alert: SSLCertificateExpiring
        expr: (ssl_certificate_expiry_days < 30)
        for: 1h
        labels:
          severity: medium
          component: security
        annotations:
          summary: "SSL certificate expires in {{ $value }} days"
          description: "Certificate {{ $labels.domain }} is expiring soon."
          impact: "Service will become inaccessible when certificate expires."
          action: "1. Renew certificate\n2. Update configuration\n3. Restart services\n4. Verify new certificate"

  # ═══════════════════════════════════════════════════════════════════
  # LOW ALERTS (P3)
  # ═══════════════════════════════════════════════════════════════════

  - name: low_alerts
    interval: 5m
    rules:

      # Backup Not Completed
      - alert: BackupNotCompleted
        expr: (time() - backup_last_success_timestamp) > 86400
        for: 1h
        labels:
          severity: low
          component: backup
        annotations:
          summary: "Backup has not succeeded in 24 hours"
          description: "Last successful backup was {{ $value | humanizeDuration }} ago."
          impact: "Higher RPO if disaster occurs. Potential data loss."
          action: "1. Check backup logs\n2. Verify backup script\n3. Check disk space\n4. Run manual backup"

      # Container Restarts
      - alert: ContainerRestarts
        expr: rate(container_restart_count[1h]) > 3
        for: 10m
        labels:
          severity: low
          component: infrastructure
        annotations:
          summary: "Container {{ $labels.name }} restarting frequently"
          description: "Container has restarted {{ $value }} times in the last hour."
          impact: "Indicates instability. May lead to service disruption."
          action: "1. Check container logs\n2. Review resource limits\n3. Investigate crash cause\n4. Adjust health checks if needed"
```

---

### Alertmanager Configuration

File: `prometheus/alertmanager.yml`

```yaml
global:
  resolve_timeout: 5m
  slack_api_url: '${SLACK_WEBHOOK_URL}'
  pagerduty_url: 'https://events.pagerduty.com/v2/enqueue'

# Alert routing tree
route:
  receiver: 'default'
  group_by: ['alertname', 'component']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

  routes:
    # Critical alerts -> PagerDuty + Slack + SMS
    - match:
        severity: critical
      receiver: 'critical-alerts'
      group_wait: 10s
      repeat_interval: 1h
      continue: true

    # High alerts -> PagerDuty + Slack
    - match:
        severity: high
      receiver: 'high-alerts'
      group_wait: 30s
      repeat_interval: 2h
      continue: true

    # Medium alerts -> Slack only
    - match:
        severity: medium
      receiver: 'medium-alerts'
      repeat_interval: 6h

    # Low alerts -> Slack only, during business hours
    - match:
        severity: low
      receiver: 'low-alerts'
      repeat_interval: 24h

# Inhibition rules (suppress less severe alerts when more severe fires)
inhibit_rules:
  # If system is down, don't alert on high latency
  - source_match:
      alertname: 'TradingSystemDown'
    target_match:
      alertname: 'HighLatency'
    equal: ['instance']

  # If database is down, don't alert on slow queries
  - source_match:
      alertname: 'DatabaseUnavailable'
    target_match:
      component: 'database'
    equal: ['instance']

# Notification receivers
receivers:
  - name: 'default'
    slack_configs:
      - channel: '#trading-alerts'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}\n{{ end }}'

  - name: 'critical-alerts'
    pagerduty_configs:
      - service_key: '${PAGERDUTY_SERVICE_KEY}'
        severity: 'critical'
        description: '{{ .GroupLabels.alertname }}: {{ .CommonAnnotations.summary }}'
        details:
          group: '{{ .GroupLabels.alertname }}'
          impact: '{{ .CommonAnnotations.impact }}'
          action: '{{ .CommonAnnotations.action }}'
          runbook: '{{ .CommonAnnotations.runbook }}'

    slack_configs:
      - channel: '#critical-alerts'
        color: 'danger'
        title: '🔴 CRITICAL: {{ .GroupLabels.alertname }}'
        text: |
          *Summary:* {{ .CommonAnnotations.summary }}
          *Impact:* {{ .CommonAnnotations.impact }}
          *Action:* {{ .CommonAnnotations.action }}
          *Runbook:* {{ .CommonAnnotations.runbook }}
        actions:
          - type: button
            text: 'View Runbook'
            url: '{{ .CommonAnnotations.runbook }}'
          - type: button
            text: 'View Grafana'
            url: 'http://grafana:3000'
          - type: button
            text: 'Acknowledge'
            url: 'http://alertmanager:9093'

    opsgenie_configs:
      - api_key: '${OPSGENIE_API_KEY}'
        priority: 'P1'

  - name: 'high-alerts'
    pagerduty_configs:
      - service_key: '${PAGERDUTY_SERVICE_KEY}'
        severity: 'error'

    slack_configs:
      - channel: '#trading-alerts'
        color: 'warning'
        title: '🟠 HIGH: {{ .GroupLabels.alertname }}'
        text: '{{ .CommonAnnotations.summary }}\n{{ .CommonAnnotations.action }}'

  - name: 'medium-alerts'
    slack_configs:
      - channel: '#trading-alerts'
        color: '#FFFF00'
        title: '🟡 MEDIUM: {{ .GroupLabels.alertname }}'
        text: '{{ .CommonAnnotations.summary }}'

  - name: 'low-alerts'
    slack_configs:
      - channel: '#trading-alerts-low'
        color: 'good'
        title: '🔵 LOW: {{ .GroupLabels.alertname }}'
        text: '{{ .CommonAnnotations.summary }}'
```

---

## Alert Response Playbooks

### Playbook Format

Each alert should have a response playbook following this structure:

1. **Alert Details**
2. **Initial Assessment** (first 2 minutes)
3. **Investigation Steps**
4. **Resolution Steps**
5. **Escalation Path**
6. **Prevention**

---

### Example Playbook: TradingSystemDown

#### Alert Details
- **Severity:** Critical (P0)
- **SLA:** Respond within 5 minutes
- **Impact:** Trading completely unavailable

#### Initial Assessment (2 minutes)

```bash
# 1. Confirm alert (check from multiple locations)
curl http://trading.example.com/health
# Connection refused?

# 2. Check from monitoring server
ssh monitoring-server
curl http://trading-server:8080/health

# 3. Check container status
ssh trading-server
docker ps | grep trading-system
```

**Decision tree:**
- Container stopped? → Go to "Container Restart"
- Container running but not responding? → Go to "Application Hang"
- Server completely unreachable? → Go to "Server Failure"

#### Investigation Steps

**Container Restart:**
```bash
# Check why it stopped
docker logs trading-system --tail 100

# Common causes:
# - OOM killer
# - Application crash
# - Health check failure
```

**Application Hang:**
```bash
# Check resource usage
docker stats trading-system

# Check application logs
docker logs trading-system --tail 200

# Check for deadlocks/errors
docker exec trading-system ps aux
docker exec trading-system netstat -antup
```

**Server Failure:**
```bash
# Try to SSH
ssh trading-server
# No response?

# Check from out-of-band management
# IPMI / iDRAC / lights-out management

# Check monitoring
# Is server reporting any metrics at all?
```

#### Resolution Steps

**Container Restart (2 minutes):**
```bash
# 1. Restart container
docker-compose restart trading-system

# 2. Monitor startup
docker logs -f trading-system

# 3. Verify health
curl http://localhost:8080/health

# 4. Check positions are still correct
docker exec trading-postgres psql -U trading_user -d trading_db -c "
  SELECT * FROM positions WHERE status = 'open';
"

# 5. Resume trading if healthy
docker-compose exec trading-system python3 -c "
import trading_utils
trading_utils.enable_trading()
"
```

**Server Failure (30 minutes - activate DR):**
```bash
# Follow DR activation procedure
# See: docs/DISASTER_RECOVERY_PLAN.md

cd /opt/trading-system/scripts
./activate_dr.sh
```

#### Escalation Path

| Time Elapsed | Action |
|--------------|--------|
| 0 min | On-call engineer paged |
| 5 min | If not resolved, escalate to Senior SRE |
| 10 min | If not resolved, escalate to Engineering Lead |
| 15 min | If not resolved, activate DR site |
| 20 min | Notify management and trading team |

#### Prevention

- **Monitoring:** Proactive health checks every 30 seconds
- **Alerting:** Early warning on resource exhaustion
- **Redundancy:** Multiple application servers with load balancing
- **Automation:** Auto-restart on health check failure
- **Documentation:** Keep runbooks updated

---

### Example Playbook: HighLatency

#### Alert Details
- **Severity:** High (P1)
- **SLA:** Respond within 15 minutes
- **Impact:** Slow trading, potential missed opportunities

#### Initial Assessment (2 minutes)

```bash
# 1. Confirm latency is high
curl -w "@curl-format.txt" -s http://trading.example.com/api/positions

# curl-format.txt:
#   time_namelookup: %{time_namelookup}\n
#   time_connect: %{time_connect}\n
#   time_starttransfer: %{time_starttransfer}\n
#   time_total: %{time_total}\n

# 2. Check from Grafana
# Open Performance Dashboard
# Look at P95 latency graph

# 3. Identify bottleneck
# - Database queries slow?
# - API calls slow?
# - System resources maxed?
```

#### Investigation Steps

**Database Slow:**
```bash
# Check for slow queries
docker exec trading-postgres psql -U trading_user -d trading_db -c "
  SELECT pid, now() - pg_stat_activity.query_start AS duration, query
  FROM pg_stat_activity
  WHERE (now() - pg_stat_activity.query_start) > interval '1 second'
  ORDER BY duration DESC;
"

# Check database connections
docker exec trading-postgres psql -U trading_user -d trading_db -c "
  SELECT COUNT(*) FROM pg_stat_activity;
"

# Check for locks
docker exec trading-postgres psql -U trading_user -d trading_db -c "
  SELECT * FROM pg_locks WHERE NOT granted;
"
```

**System Resources:**
```bash
# Check CPU
top

# Check memory
free -h

# Check disk I/O
iostat -x 1

# Check network
iftop
```

#### Resolution Steps

**Kill Slow Query:**
```bash
# Identify PID from investigation step
docker exec trading-postgres psql -U trading_user -d trading_db -c "
  SELECT pg_terminate_backend(PID);
"
```

**Add Missing Index:**
```bash
# If query optimizer recommended index
docker exec trading-postgres psql -U trading_user -d trading_db -c "
  CREATE INDEX CONCURRENTLY idx_name ON table_name (column_name);
"
```

**Scale Resources:**
```bash
# If system resources maxed out
# Horizontal scaling (add more application servers)
docker-compose up -d --scale trading-system=3

# Or vertical scaling (increase resources)
# Requires restart - plan for off-hours
```

---

## On-Call Procedures

### On-Call Schedule

- **Primary On-Call:** Responds to all Critical and High alerts
- **Secondary On-Call:** Backup if primary doesn't respond in 5 minutes
- **Rotation:** Weekly rotation, Monday 9:00 AM

**Schedule Management:**
- PagerDuty: https://pagerduty.com/schedules
- Override: Use /pd_override in Slack
- Swap: Coordinate with team, update PagerDuty

### On-Call Checklist

**Start of Shift:**
- [ ] Acknowledge you're on-call in #trading-alerts channel
- [ ] Test pager (send test alert)
- [ ] Verify laptop/phone charged
- [ ] Review recent incidents
- [ ] Check current system status
- [ ] Verify access to all systems (VPN, SSH keys, passwords)

**During On-Call:**
- [ ] Respond to pages within SLA (5 min for P0, 15 min for P1)
- [ ] Document actions in incident ticket
- [ ] Update #trading-alerts with status every 15 minutes
- [ ] Escalate if stuck for 10 minutes
- [ ] Create follow-up tickets for root causes

**End of Shift:**
- [ ] Hand off any ongoing incidents
- [ ] Update incident tickets
- [ ] Brief next on-call person
- [ ] Document lessons learned

### Response Time SLAs

| Severity | Acknowledge | Update Frequency | Resolve Target |
|----------|-------------|------------------|----------------|
| P0 Critical | 5 minutes | Every 15 min | 30 min |
| P1 High | 15 minutes | Every 30 min | 2 hours |
| P2 Medium | 1 hour | Every 2 hours | 8 hours |
| P3 Low | 8 hours | Daily | Next sprint |

### Escalation Matrix

```
Level 1: On-Call SRE (0-10 minutes)
         ↓ (if not resolved in 10 min)
Level 2: Senior SRE + DBA (10-20 minutes)
         ↓ (if not resolved in 20 min)
Level 3: Engineering Lead + App Owner (20-30 minutes)
         ↓ (if not resolved in 30 min)
Level 4: CTO + Business Owner (30+ minutes)
         → Activate DR / Major Incident
```

---

## Alert Tuning

### Reducing False Positives

**Problem:** Alert fires but is not actually a problem

**Solutions:**

1. **Increase thresholds:**
```yaml
# Before
- alert: HighCPU
  expr: cpu_usage > 70

# After (tuned)
- alert: HighCPU
  expr: cpu_usage > 85
  for: 10m  # Must be sustained
```

2. **Add context:**
```yaml
# Before
- alert: HighErrorRate
  expr: error_rate > 0.01

# After
- alert: HighErrorRate
  expr: error_rate > 0.01 AND request_rate > 10
  # Only alert if we have significant traffic
```

3. **Ignore known events:**
```yaml
# Before
- alert: DeploymentInProgress
  expr: deployment_status == "in_progress"

# After
# Don't alert on deployment - it's expected
# Remove this alert
```

### Reducing Alert Fatigue

**Symptoms:**
- Too many alerts
- Ignoring low-priority alerts
- Delayed response to critical alerts

**Solutions:**

1. **Review alert history:**
```bash
# Which alerts fire most often?
curl -s http://alertmanager:9093/api/v1/alerts | jq '.data[] | .labels.alertname' | sort | uniq -c | sort -rn

# Which alerts are never acknowledged?
# Review PagerDuty analytics
```

2. **Consolidate related alerts:**
```yaml
# Before: 3 separate alerts
- alert: HighCPU
- alert: HighMemory
- alert: HighDisk

# After: 1 consolidated alert
- alert: ResourcePressure
  expr: cpu > 85 OR memory > 90 OR disk > 85
```

3. **Adjust severity:**
```yaml
# Before
- alert: CacheHitRateLow
  labels:
    severity: high  # Too severe

# After
- alert: CacheHitRateLow
  labels:
    severity: medium  # More appropriate
```

4. **Remove noisy alerts:**
```bash
# If an alert fires > 10 times/day but is never actionable
# Consider removing it or drastically changing thresholds
```

### Alert Tuning Process

**Monthly Review:**

1. **Gather Data:**
   - Total alerts fired
   - False positive rate
   - Mean time to acknowledge
   - Mean time to resolve

2. **Identify Issues:**
   - Alerts that fire too often (> 5/day)
   - Alerts never acknowledged
   - Alerts with no clear action

3. **Make Changes:**
   - Update thresholds
   - Change severity
   - Remove or consolidate
   - Add new alerts for blind spots

4. **Document:**
   - Record changes
   - Measure impact next month

---

## Metrics Reference

### Application Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `up` | Gauge | Service availability (1=up, 0=down) | 0 for > 1 min |
| `http_requests_total` | Counter | Total HTTP requests | N/A |
| `http_request_duration_seconds` | Histogram | Request latency | p95 > 1s for 5 min |
| `trades_total` | Counter | Total trades executed | N/A |
| `trade_errors_total` | Counter | Failed trades | > 10% error rate |
| `positions_open` | Gauge | Number of open positions | N/A |
| `portfolio_value` | Gauge | Current portfolio value | N/A |
| `pnl_total` | Gauge | Total P&L | N/A |

### Database Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `pg_up` | Gauge | PostgreSQL availability | 0 for > 30s |
| `pg_stat_database_numbackends` | Gauge | Active connections | > 80% of max |
| `pg_replication_lag_seconds` | Gauge | Replica lag | > 60s for 5 min |
| `pg_stat_database_xact_commit` | Counter | Committed transactions | N/A |
| `pg_stat_database_xact_rollback` | Counter | Rolled back transactions | > 10% of commits |

### System Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `node_cpu_seconds_total` | Counter | CPU time | Usage > 85% for 10 min |
| `node_memory_MemAvailable_bytes` | Gauge | Available memory | < 10% for 10 min |
| `node_filesystem_avail_bytes` | Gauge | Available disk space | < 10% for 5 min |
| `node_disk_io_time_seconds_total` | Counter | Disk I/O time | Wait > 50% for 10 min |
| `node_network_transmit_bytes_total` | Counter | Network TX | N/A |

---

## Appendix

### Useful Prometheus Queries

**Request rate:**
```promql
rate(http_requests_total[5m])
```

**Error rate:**
```promql
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
```

**P95 latency:**
```promql
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

**CPU usage:**
```promql
100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

**Memory usage:**
```promql
100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))
```

**Disk usage:**
```promql
100 * (1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes))
```

---

### Alert Testing

Test alerts before deploying:

```bash
# 1. Test alert expression in Prometheus
# Go to http://prometheus:9090/graph
# Enter alert expression
# Verify it triggers when expected

# 2. Test Alertmanager routing
curl -XPOST http://alertmanager:9093/api/v1/alerts -d '[
  {
    "labels": {
      "alertname": "TestAlert",
      "severity": "critical"
    },
    "annotations": {
      "summary": "Test alert"
    }
  }
]'

# 3. Verify notification received
# Check Slack, PagerDuty, etc.

# 4. Silence test alert
curl -XPOST http://alertmanager:9093/api/v1/silences -d '{
  "matchers": [
    {
      "name": "alertname",
      "value": "TestAlert",
      "isRegex": false
    }
  ],
  "startsAt": "2024-01-01T00:00:00Z",
  "endsAt": "2024-01-02T00:00:00Z",
  "createdBy": "test",
  "comment": "Testing alerts"
}'
```

---

### Contact Information

**Monitoring Team:**
- Slack: #monitoring
- Email: monitoring@example.com
- On-call: PagerDuty

**Escalation:**
- Level 1: On-Call SRE via PagerDuty
- Level 2: @sre-team in Slack
- Level 3: Engineering Lead +91-XXX-XXX-XXXX

---

**Document Version:** 1.0
**Last Review:** Week 4
**Next Review:** Monthly
**Owner:** SRE Team

---

END OF MONITORING AND ALERTING PLAYBOOK
