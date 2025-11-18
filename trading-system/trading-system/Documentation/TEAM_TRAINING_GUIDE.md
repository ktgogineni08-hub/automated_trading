# Trading System - Team Training Guide

**Version:** 1.0
**Date:** November 2025
**Duration:** 4 hours (can be split into 2x 2-hour sessions)
**Audience:** Developers, SRE Engineers, On-Call Engineers

---

## Training Overview

This training program prepares team members to operate, monitor, and troubleshoot the trading system in production. By the end of training, participants will be able to:

- ✅ Understand the trading system architecture
- ✅ Navigate monitoring dashboards and logs
- ✅ Respond to alerts using runbooks
- ✅ Perform common operational tasks
- ✅ Execute disaster recovery procedures
- ✅ Participate in on-call rotation

---

## Prerequisites

Before training, ensure you have:

- [ ] Access to Kubernetes cluster (`kubectl` configured)
- [ ] Access to Grafana dashboards
- [ ] Access to PagerDuty/Opsgenie
- [ ] Access to Slack #trading-alerts channel
- [ ] GitHub repository access
- [ ] This training guide printed or accessible

---

## Session 1: Architecture & Monitoring (2 hours)

### Module 1.1: System Architecture (30 minutes)

#### Learning Objectives
- Understand high-level system components
- Identify data flows
- Recognize single points of failure (eliminated)

#### Materials
- [C4 Context Diagram](architecture/C4_CONTEXT_DIAGRAM.md)
- [C4 Container Diagram](architecture/C4_CONTAINER_DIAGRAM.md)
- [C4 Component Diagram](architecture/C4_COMPONENT_DIAGRAM.md)

#### Key Concepts

**1. System Components (15 min)**

Review the C4 diagrams and discuss:

**Trading Engine:**
- 7 concurrent strategies
- Signal aggregation
- Risk management
- Order execution

**Portfolio Manager:**
- Position tracking
- Real-time P&L calculation
- Compliance checks

**Data Pipeline:**
- WebSocket connection to Zerodha
- Redis caching (60s TTL)
- Time-series storage

**High Availability:**
- PostgreSQL: 1 primary + 2 replicas (streaming replication)
- Redis: 1 master + 2 replicas + 3 Sentinel nodes
- Trading System: 2-10 pods (HPA)

**2. Data Flows (10 min)**

Walk through three critical flows:

**Market Data Flow:**
```
Zerodha WebSocket → Data Pipeline → Redis Cache → Trading Engine
                                  → TimeSeries DB
```

**Order Execution Flow:**
```
Trading Engine → Risk Check → Compliance Check → Zerodha API → NSE
              → PostgreSQL (audit)
              → Portfolio Manager (position update)
```

**Alert Flow:**
```
Trading System → Prometheus → Alertmanager → PagerDuty/Opsgenie/Slack
```

**3. Q&A (5 min)**

Sample questions to test understanding:
- What happens if PostgreSQL primary goes down?
- How long is market data cached?
- What's the maximum number of trading system pods?

---

### Module 1.2: Monitoring Dashboards (30 minutes)

#### Learning Objectives
- Navigate Grafana dashboards
- Interpret key metrics
- Identify anomalies

#### Hands-On Exercise

**Step 1: Access Grafana**
```bash
# Port-forward to Grafana (if not exposed externally)
kubectl port-forward svc/grafana 3000:3000 -n trading-system-prod

# Open browser: http://localhost:3000
# Login with credentials (from password manager)
```

**Step 2: Explore Dashboards**

Navigate through these 5 dashboards:

**1. Trading Activity Dashboard**

Metrics to observe:
- `trading_open_positions` - Current open positions (target: 0-20)
- `trading_orders_total` - Orders placed today
- `trading_pnl_total` - Realized + unrealized P&L
- `trading_signals_generated` - Strategy signals

**What's normal:**
- Open positions: 5-15 during market hours
- Orders: 20-150 per day
- P&L: Should trend upward over time

**What's abnormal:**
- 0 orders for > 30 minutes during market hours
- Open positions > 20 (breaches limit)
- P&L dropping > 2% in 1 hour

**2. Performance Metrics Dashboard**

Metrics to observe:
- `http_request_duration_seconds` (p50, p95, p99)
- `trading_strategy_execution_seconds`
- `redis_cache_hit_ratio`
- `database_query_duration_seconds`

**What's normal:**
- API latency p95: < 250ms
- Cache hit ratio: > 80%
- Database query p95: < 50ms

**What's abnormal:**
- API latency p95: > 500ms (investigate slowness)
- Cache hit ratio: < 60% (cache not warming properly)
- Database query p95: > 200ms (database performance issue)

**3. System Health Dashboard**

Metrics to observe:
- `up{job="trading-system"}` - Pod health
- `up{job="postgres-primary"}` - Database health
- `up{job="redis-master"}` - Cache health
- `container_cpu_usage_seconds_total` - CPU usage
- `container_memory_working_set_bytes` - Memory usage

**What's normal:**
- All `up` metrics = 1 (healthy)
- CPU usage: 30-60%
- Memory usage: < 1.5 GB per pod

**What's abnormal:**
- Any `up` metric = 0 (service down - page immediately)
- CPU usage: > 80% sustained (may need scaling)
- Memory usage: > 1.8 GB (potential memory leak)

**4. Business Analytics Dashboard**

Metrics to observe:
- Daily P&L trend
- Win rate by strategy
- Sharpe ratio (risk-adjusted return)
- Maximum drawdown

**5. Alert Management Dashboard**

Metrics to observe:
- `alertmanager_alerts_active` - Currently firing alerts
- `alertmanager_notifications_total` - Notification count
- `alertmanager_notifications_failed_total` - Failed notifications

**Step 3: Practice Exercises (10 min)**

**Exercise 1:** What is the current P&L?
- Navigate to Trading Activity dashboard
- Find `trading_pnl_total` panel
- Note the current value

**Exercise 2:** Is the cache performing well?
- Navigate to Performance Metrics dashboard
- Find `redis_cache_hit_ratio` panel
- Is it above 80%? If not, why might that be?

**Exercise 3:** Are all systems healthy?
- Navigate to System Health dashboard
- Check all `up` metrics
- Identify any unhealthy services

---

### Module 1.3: Log Analysis (30 minutes)

#### Learning Objectives
- Search logs in ELK/Kibana
- Filter and query logs
- Correlate logs with alerts

#### Hands-On Exercise

**Step 1: Access Kibana**
```bash
# Port-forward to Kibana
kubectl port-forward svc/kibana 5601:5601 -n trading-system-prod

# Open browser: http://localhost:5601
```

**Step 2: Create Log Queries**

**Query 1: Find all ERROR logs**
```
level: ERROR AND service: trading-system
```

**Query 2: Find order execution logs**
```
message: "order" AND status: "COMPLETE"
```

**Query 3: Find logs for specific symbol**
```
symbol: "RELIANCE" AND timestamp > now-1h
```

**Query 4: Find slow database queries**
```
service: portfolio-manager AND query_duration_ms > 100
```

**Step 3: Practice Exercises (15 min)**

**Exercise 1:** Find the last 10 orders placed
- Use query: `message: "order placed"`
- Sort by timestamp descending
- Identify which strategy placed each order

**Exercise 2:** Find any authentication failures
- Use query: `level: ERROR AND message: "authentication"`
- Are there any? (There shouldn't be in normal operation)

**Exercise 3:** Correlate alert with logs
- Trigger a test alert
- Find corresponding logs that triggered the alert
- Practice this correlation workflow

---

### Module 1.4: API Documentation (30 minutes)

#### Learning Objectives
- Navigate OpenAPI documentation
- Test API endpoints
- Understand authentication

#### Hands-On Exercise

**Step 1: Access Swagger UI**
```bash
# Port-forward to Swagger UI
kubectl port-forward svc/swagger-ui 8080:8080 -n trading-system-prod

# Open browser: http://localhost:8080
```

**Step 2: Explore API Endpoints**

Review these key endpoint groups:

**Portfolio Endpoints:**
- `GET /api/v1/portfolio/positions` - Get all positions
- `GET /api/v1/portfolio/summary` - Portfolio summary
- `GET /api/v1/portfolio/performance` - Performance metrics

**Order Endpoints:**
- `GET /api/v1/orders` - Order history
- `POST /api/v1/orders` - Place order (manual)
- `GET /api/v1/orders/{order_id}` - Order details

**Strategy Endpoints:**
- `GET /api/v1/strategies` - List strategies
- `PATCH /api/v1/strategies/{id}` - Update strategy config

**Step 3: Test API Call (Using HMAC Auth)**

**Generate HMAC signature:**
```python
from security.hmac_auth import HMACAuthenticator

# Initialize (get secret from password manager)
auth = HMACAuthenticator(secret_key="your-secret-key")

# Sign request
headers = auth.sign_request(
    method="GET",
    path="/api/v1/portfolio/positions",
    body=""
)

print(headers)
# Output:
# {
#   'X-Signature': 'abc123...',
#   'X-Timestamp': '1698765432',
#   'X-Nonce': 'xyz789...'
# }
```

**Make request:**
```bash
# Use generated headers
curl -X GET "http://api-server/api/v1/portfolio/positions" \
  -H "X-Signature: abc123..." \
  -H "X-Timestamp: 1698765432" \
  -H "X-Nonce: xyz789..."
```

**Step 4: Practice Exercises (15 min)**

**Exercise 1:** Get current positions
- Use API endpoint to fetch positions
- Identify number of open positions
- Calculate total portfolio value

**Exercise 2:** Check strategy status
- Use API to list all strategies
- Identify which strategies are active
- Note any strategies in "error" state

---

## Session 2: Operations & Incident Response (2 hours)

### Module 2.1: Runbook Training (45 minutes)

#### Learning Objectives
- Navigate runbook index
- Execute runbook procedures
- Document incident actions

#### Materials
- [Runbook Index](runbooks/RUNBOOK_INDEX.md)
- [RB-001: Database Primary Down](runbooks/RB-001-database-primary-down.md)
- [RB-002: High Error Rate](runbooks/RB-004-high-error-rate.md)
- [Disaster Recovery Plan](DISASTER_RECOVERY.md)

#### Hands-On Exercise

**Step 1: Navigate Runbook Index (5 min)**

Review runbook organization:
- P1 (Critical): 8 runbooks
- P2 (High): 12 runbooks
- P3 (Medium): 6+ runbooks

**Step 2: Practice Runbook Execution (30 min)**

**Scenario 1: Database Primary Down (P1)**

Simulate this incident:
```bash
# Instructor: Simulate database failure (staging only!)
kubectl delete pod postgres-primary-0 -n trading-system-staging --grace-period=0 --force
```

**Your task:** Follow RB-001 to resolve

**Steps:**
1. Acknowledge alert in PagerDuty
2. Open runbook: [RB-001](runbooks/RB-001-database-primary-down.md)
3. Verify issue:
   ```bash
   kubectl get pods -n trading-system-staging | grep postgres
   ```
4. Check if replica can be promoted:
   ```bash
   kubectl exec -it postgres-replica-0 -n trading-system-staging -- \
     psql -U postgres -c "SELECT pg_is_in_recovery();"
   ```
5. Observe automatic recovery (StatefulSet recreates pod)
6. Verify replication restored:
   ```bash
   kubectl exec -it postgres-primary-0 -n trading-system-staging -- \
     psql -U postgres -c "SELECT * FROM pg_stat_replication;"
   ```
7. Document actions in incident report
8. Resolve alert in PagerDuty

**Time to resolve:** Target < 5 minutes

**Scenario 2: High Error Rate (P2)**

Simulate this incident:
```bash
# Instructor: Trigger high error rate (deploy buggy code to staging)
kubectl set env deployment/trading-system FORCE_ERROR_RATE=0.15 -n trading-system-staging
```

**Your task:** Follow RB-004 to investigate

**Steps:**
1. Acknowledge alert in Opsgenie
2. Open runbook: [RB-004](runbooks/RB-004-high-error-rate.md)
3. Check error rate:
   - Go to Grafana Performance Metrics dashboard
   - Find error rate panel (should show > 10%)
4. Identify error types in logs:
   ```bash
   kubectl logs -l app=trading-system -n trading-system-staging | grep ERROR | tail -20
   ```
5. Identify root cause (bad environment variable)
6. Fix:
   ```bash
   kubectl set env deployment/trading-system FORCE_ERROR_RATE- -n trading-system-staging
   ```
7. Verify error rate returns to normal
8. Document root cause
9. Resolve alert

**Time to resolve:** Target < 15 minutes

**Step 3: Group Discussion (10 min)**

Discuss:
- What went well in the exercises?
- What was confusing or unclear?
- How can we improve runbooks?
- What additional runbooks are needed?

---

### Module 2.2: Failover Testing (30 minutes)

#### Learning Objectives
- Trigger controlled failovers
- Verify automatic recovery
- Measure recovery time

#### Hands-On Exercise

**Step 1: PostgreSQL Failover Test**

```bash
# Navigate to scripts directory
cd /Users/gogineni/Python/trading-system/infrastructure/scripts

# Run automated test
./test-postgres-failover.sh

# Observe output:
# - Primary pod deleted
# - StatefulSet recreates primary
# - Replication verified
# - RTO measured
```

**Expected Results:**
- Primary recovers in < 2 minutes
- No data loss
- Replication restored automatically

**Step 2: Redis Failover Test**

```bash
# Run Redis Sentinel failover test
./test-redis-failover.sh

# Observe output:
# - Master pod deleted
# - Sentinel elects new master
# - Application reconnects
# - RTO measured
```

**Expected Results:**
- New master elected in < 30 seconds
- Zero data loss (AOF persistence)
- Application reconnects automatically

**Step 3: Application Pod Failover**

```bash
# Delete one trading-system pod
kubectl delete pod -l app=trading-system -n trading-system-staging --force --grace-period=0

# Observe in real-time:
kubectl get pods -l app=trading-system -n trading-system-staging -w

# Check metrics in Grafana
# - Brief spike in latency
# - No increase in error rate
# - Requests route to healthy pods
```

**Expected Results:**
- New pod starts in < 1 minute
- No failed requests (load balancer routes to healthy pods)
- Cache warming completes automatically

---

### Module 2.3: Alert Response (30 minutes)

#### Learning Objectives
- Receive and acknowledge alerts
- Use escalation policy
- Communicate incidents

#### Hands-On Exercise

**Step 1: Receive Test Alert**

Instructor sends test alert:
```bash
kubectl exec -it -n trading-system-staging \
  $(kubectl get pod -l app=prometheus -n trading-system-staging -o jsonpath='{.items[0].metadata.name}') \
  -- curl -X POST http://alertmanager:9093/api/v1/alerts -d '[
  {
    "labels": {
      "alertname": "TrainingTestAlert",
      "severity": "high",
      "service": "trading-system"
    },
    "annotations": {
      "summary": "Training exercise test alert",
      "description": "This is a test alert for training purposes",
      "runbook_url": "https://docs/runbooks/RB-004"
    }
  }
]'
```

**Step 2: Respond to Alert**

**Your task:**
1. **Receive notification** (Opsgenie app, Slack, Email)
2. **Acknowledge in Opsgenie** (within 5 minutes)
3. **Open runbook** (use `runbook_url` from alert)
4. **Post in Slack**:
   ```
   🚨 Investigating TrainingTestAlert
   Severity: High
   Runbook: https://docs/runbooks/RB-004
   ETA: 10 minutes
   ```
5. **Investigate** (simulated - just wait 2 minutes)
6. **Resolve** in Opsgenie
7. **Post resolution in Slack**:
   ```
   ✅ TrainingTestAlert resolved
   Root cause: Test alert for training
   Duration: 5 minutes
   No impact to production
   ```

**Step 3: Practice Escalation**

Instructor sends critical alert and team member does NOT acknowledge:

**Observer task:** Watch escalation flow
- Level 1 notified immediately
- After 15 minutes → Level 2 notified
- After 30 minutes → Level 3 notified

**Discussion:** When is it appropriate to escalate?

---

### Module 2.4: Security Operations (15 minutes)

#### Learning Objectives
- Rotate secrets
- Verify IP whitelist
- Monitor security events

#### Hands-On Exercise

**Step 1: Test Secrets Rotation (Dry Run)**

```bash
# Navigate to scripts
cd /Users/gogineni/Python/trading-system/security

# Run secrets rotation in dry-run mode
python secrets_rotation.py all --dry-run --namespace trading-system-staging

# Output shows what WOULD be rotated (without actually doing it)
```

**Expected Output:**
```
[INFO] Starting database password rotation
[DRY RUN] Would rotate database password
[INFO] Starting Redis password rotation
[DRY RUN] Would rotate Redis password
[INFO] Starting API keys rotation
[DRY RUN] Would rotate internal API keys
⚠ Zerodha API keys require manual rotation
```

**Step 2: Verify IP Whitelist**

```python
# Test IP whitelist functionality
from security.ip_whitelist import IPWhitelist

# Initialize with allowed IPs
whitelist = IPWhitelist(allowed_ips=['10.0.0.0/8', '172.16.0.0/12', '192.168.1.100'])

# Test various IPs
print(whitelist.is_allowed('10.1.2.3'))      # True (in 10.0.0.0/8)
print(whitelist.is_allowed('172.16.5.10'))   # True (in 172.16.0.0/12)
print(whitelist.is_allowed('192.168.1.100')) # True (exact match)
print(whitelist.is_allowed('8.8.8.8'))       # False (not whitelisted)
print(whitelist.is_allowed('203.0.113.1'))   # False (not whitelisted)
```

**Step 3: Review Security Audit Logs**

```bash
# Query PostgreSQL for security events
kubectl exec -it postgres-primary-0 -n trading-system-staging -- \
  psql -U postgres -d trading_system -c \
  "SELECT * FROM audit_logs WHERE event_type IN ('authentication_failure', 'authorization_failure', 'ip_blocked') ORDER BY timestamp DESC LIMIT 10;"
```

---

## Certification Checklist

After completing training, verify each team member can:

### Architecture & Monitoring
- [ ] Explain system architecture using C4 diagrams
- [ ] Navigate all 5 Grafana dashboards
- [ ] Interpret key metrics (latency, error rate, throughput)
- [ ] Search logs in Kibana
- [ ] Access Swagger API documentation

### Operations
- [ ] Execute at least 2 runbooks successfully
- [ ] Trigger and observe PostgreSQL failover
- [ ] Trigger and observe Redis failover
- [ ] Acknowledge and resolve alerts
- [ ] Post incident updates in Slack
- [ ] Use HMAC authentication to call API

### Incident Response
- [ ] Respond to alert within 5 minutes
- [ ] Navigate to correct runbook
- [ ] Document incident actions
- [ ] Escalate when appropriate
- [ ] Communicate status effectively

### Security
- [ ] Run secrets rotation (dry-run)
- [ ] Verify IP whitelist functionality
- [ ] Review security audit logs

---

## Post-Training Assessment

### Quiz (10 questions, 80% to pass)

1. **What is the RTO for PostgreSQL failover?**
   - a) < 1 minute
   - b) < 5 minutes ✓
   - c) < 15 minutes
   - d) < 30 minutes

2. **How many Redis Sentinel nodes are deployed?**
   - a) 1
   - b) 2
   - c) 3 ✓
   - d) 5

3. **What is the cache TTL for market data?**
   - a) 30 seconds
   - b) 60 seconds ✓
   - c) 5 minutes
   - d) 15 minutes

4. **Which alerts go to PagerDuty?**
   - a) All alerts
   - b) Critical and High
   - c) Only Critical ✓
   - d) None (only Opsgenie)

5. **What's the maximum number of open positions?**
   - a) 10
   - b) 15
   - c) 20 ✓
   - d) Unlimited

6. **Where are API endpoints documented?**
   - a) GitHub README
   - b) Swagger UI / OpenAPI ✓
   - c) Confluence
   - d) Not documented

7. **What authentication does the API use?**
   - a) Basic Auth
   - b) OAuth 2.0
   - c) HMAC-SHA256 ✓
   - d) No authentication

8. **How often should secrets be rotated?**
   - a) Monthly
   - b) Quarterly ✓
   - c) Annually
   - d) Never

9. **What's the target cache hit rate?**
   - a) > 50%
   - b) > 70%
   - c) > 80% ✓
   - d) > 95%

10. **Who is notified in Level 4 escalation?**
    - a) All engineers
    - b) Team lead
    - c) Executives (CTO/VP) ✓
    - d) External support

**Answer Key:** 1-b, 2-c, 3-b, 4-c, 5-c, 6-b, 7-c, 8-b, 9-c, 10-c

---

## On-Call Readiness

Once certified, team members are ready for on-call duties. Before first shift:

### Required Access
- [ ] PagerDuty account with mobile app
- [ ] Opsgenie account with mobile app
- [ ] Slack mobile notifications enabled
- [ ] VPN access (for remote troubleshooting)
- [ ] kubectl configured on laptop
- [ ] Password manager access to all credentials

### Required Knowledge
- [ ] Completed training and passed quiz
- [ ] Shadowed experienced on-call engineer for 1 week
- [ ] Executed at least 3 runbooks successfully
- [ ] Participated in incident response exercise

### Required Equipment
- [ ] Laptop with battery backup
- [ ] Reliable internet (home + mobile hotspot)
- [ ] Phone with PagerDuty/Opsgenie apps
- [ ] Access to on-call runbook (printed backup)

---

## Quick Reference Card

**Print this card and keep it handy during on-call shifts**

### Emergency Contacts
- **On-Call Lead:** +91-xxx-xxx-xxxx
- **Team Lead:** +91-xxx-xxx-xxxx
- **CTO:** +91-xxx-xxx-xxxx

### Critical Commands

**Check system health:**
```bash
kubectl get pods -n trading-system-prod
```

**View recent logs:**
```bash
kubectl logs -l app=trading-system -n trading-system-prod --tail=50
```

**Check database replication:**
```bash
kubectl exec -it postgres-primary-0 -n trading-system-prod -- \
  psql -U postgres -c "SELECT * FROM pg_stat_replication;"
```

**Check Redis Sentinel:**
```bash
kubectl exec -it redis-sentinel-0 -n trading-system-prod -- \
  redis-cli -p 26379 SENTINEL masters
```

**Restart trading system:**
```bash
kubectl rollout restart deployment/trading-system -n trading-system-prod
```

### Grafana Dashboards
- Trading Activity: http://grafana/d/trading-activity
- System Health: http://grafana/d/system-health
- Performance: http://grafana/d/performance

### Runbooks
- Runbook Index: /Documentation/runbooks/RUNBOOK_INDEX.md
- RB-001 (Critical): Database Primary Down
- RB-002 (Critical): Trading System Down
- RB-004 (High): High Error Rate

### Escalation Policy
- **Level 1:** You (0 min)
- **Level 2:** Backup engineer (15 min)
- **Level 3:** Team lead (30 min)
- **Level 4:** CTO/VP (60 min)

### Incident Communication Template
```
🚨 Investigating [AlertName]
Severity: [P1/P2/P3]
Impact: [description]
ETA: [minutes]
Runbook: [URL]
```

---

## Continuous Learning

### Recommended Reading
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - All recent improvements
- [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md) - DR procedures
- [ALERT_ESCALATION_POLICY.md](ALERT_ESCALATION_POLICY.md) - Escalation details
- Zerodha Kite API docs: https://kite.trade/docs/

### Monthly Activities
- Review new runbooks
- Participate in failover drills
- Attend post-mortem meetings
- Share on-call learnings

### Quarterly Activities
- Complete refresher training
- Update runbooks based on experience
- Practice full DR scenario
- Review and update escalation policy

---

## Training Feedback

After training, please provide feedback:

**What worked well?**

**What was confusing?**

**What additional topics should be covered?**

**Suggestions for improvement:**

---

## Training Completion Certificate

---

**This certifies that**

**_______________________________**
(Team Member Name)

**has successfully completed Trading System Operations Training**

**Date:** ______________

**Trainer:** ______________

**Score:** ______ / 10 (Quiz)

**Authorized for on-call duties:** [ ] Yes [ ] No

**Signature:** ______________

---

---

**Document Version:** 1.0
**Last Updated:** November 2025
**Next Review:** February 2026
**Training Coordinator:** SRE Team Lead
