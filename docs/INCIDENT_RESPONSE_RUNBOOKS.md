# Incident Response Runbooks
## Enhanced NIFTY 50 Trading System

**Version:** 1.0.0
**Last Updated:** October 31, 2025
**Emergency Contact:** [On-Call Team]

---

## Quick Reference

### Severity Levels

| Severity | Description | Response Time | Examples |
|----------|-------------|---------------|----------|
| **P0 - CRITICAL** | System down, trading stopped | < 15 minutes | Complete outage, data loss |
| **P1 - HIGH** | Major functionality impaired | < 1 hour | Database down, high error rate |
| **P2 - MEDIUM** | Degraded performance | < 4 hours | Slow queries, elevated latency |
| **P3 - LOW** | Minor issues, no impact | < 24 hours | UI glitch, non-critical warning |

### On-Call Contacts

```
Primary On-Call:   [Name] - [Phone] - [Slack: @handle]
Secondary On-Call: [Name] - [Phone] - [Slack: @handle]
Manager On-Call:   [Name] - [Phone] - [Slack: @handle]
Escalation:        [CTO] - [Phone] - [Slack: @handle]
```

### Quick Commands

```bash
# Check system status
./scripts/status.sh

# View live logs
./scripts/logs.sh trading-system -f

# Restart service
docker-compose restart trading-system

# Emergency stop
docker-compose down

# Database backup
./scripts/backup.sh

# Health check
curl http://localhost:8080/health | jq
```

---

## Incident Response Framework

### 1. Detection
- Alert received (Prometheus, Grafana, logs)
- User report
- Monitoring dashboard shows anomaly
- Automated health check failure

### 2. Triage
- Assess severity (P0-P3)
- Determine impact (users affected, trading impact)
- Identify affected components
- Check recent changes

### 3. Response
- Follow specific runbook
- Document actions taken
- Communicate status
- Implement fix or workaround

### 4. Resolution
- Verify fix
- Monitor stability
- Update status
- Close incident

### 5. Post-Mortem
- Root cause analysis
- Timeline of events
- Lessons learned
- Action items for prevention

---

## Runbook 1: System Down / Complete Outage

**Severity:** P0 - CRITICAL
**Response Time:** < 15 minutes

### Symptoms
- Trading system not responding
- Health check failing: `curl http://localhost:8080/health` returns error
- All containers stopped
- Users cannot access dashboard

### Investigation Steps

1. **Check if services are running**
   ```bash
   docker-compose ps
   ```

2. **Check system resources**
   ```bash
   df -h              # Disk space
   free -h            # Memory
   top                # CPU usage
   docker stats       # Container stats
   ```

3. **Check recent logs**
   ```bash
   docker-compose logs --tail=100 trading-system
   docker-compose logs --tail=100 postgres
   docker-compose logs --tail=100 redis
   ```

4. **Check for recent deployments**
   ```bash
   git log -1
   docker images | head -5
   ```

### Resolution Steps

#### Scenario A: Services Stopped

```bash
# 1. Try to start services
docker-compose up -d

# 2. Check if they started successfully
docker-compose ps

# 3. Verify health
curl http://localhost:8080/health

# 4. Check logs for errors
docker-compose logs -f
```

#### Scenario B: Out of Disk Space

```bash
# 1. Check disk usage
df -h

# 2. Clean up Docker
docker system prune -a -f
docker volume prune -f

# 3. Clean up logs
find /var/log -name "*.log" -mtime +7 -delete

# 4. Restart services
docker-compose restart
```

#### Scenario C: Out of Memory

```bash
# 1. Identify memory hog
docker stats --no-stream

# 2. Restart heavy services
docker-compose restart trading-system

# 3. Consider scaling down
# Reduce connection pool sizes in .env
# Reduce cache size

# 4. Restart with new config
docker-compose down && docker-compose up -d
```

#### Scenario D: Configuration Error

```bash
# 1. Check environment variables
docker-compose exec trading-system env | grep -E "POSTGRES|REDIS|ZERODHA"

# 2. Verify .env file
cat .env | grep -v "^#" | grep -v "^$"

# 3. Fix configuration
vim .env

# 4. Restart services
docker-compose down && docker-compose up -d
```

### Communication Template

```
**INCIDENT ALERT - P0**
Status: [INVESTIGATING / IDENTIFIED / FIXING / RESOLVED]
Impact: Trading system completely down
Affected: All users
Started: [Timestamp]
ETA: [Estimate]

Details: [Brief description]
Actions: [What we're doing]

Updates: [Channel or status page]
```

### Post-Resolution

- [ ] Verify all services healthy
- [ ] Run smoke tests
- [ ] Monitor for 30 minutes
- [ ] Update stakeholders
- [ ] Schedule post-mortem
- [ ] Document incident report

---

## Runbook 2: Database Connection Failure

**Severity:** P1 - HIGH
**Response Time:** < 1 hour

### Symptoms
- Errors: "Connection refused", "Too many connections"
- Trading system logs show database errors
- Dashboard shows database health as UNHEALTHY
- Queries timing out

### Investigation Steps

1. **Check if PostgreSQL is running**
   ```bash
   docker-compose ps postgres
   docker-compose logs postgres --tail=50
   ```

2. **Test database connectivity**
   ```bash
   PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U trading_user -d trading_system -c "SELECT 1;"
   ```

3. **Check connection pool**
   ```bash
   # View active connections
   PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U trading_user -d trading_system -c \
     "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

   # View connection limit
   PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U trading_user -d trading_system -c \
     "SHOW max_connections;"
   ```

4. **Check database logs**
   ```bash
   docker-compose logs postgres | grep -i "error\|fatal\|connection"
   ```

### Resolution Steps

#### Scenario A: PostgreSQL Container Down

```bash
# 1. Restart PostgreSQL
docker-compose restart postgres

# 2. Wait for startup (check logs)
docker-compose logs -f postgres

# 3. Verify database is ready
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U trading_user -d trading_system -c "SELECT version();"

# 4. Restart trading system
docker-compose restart trading-system
```

#### Scenario B: Connection Pool Exhausted

```bash
# 1. Kill idle connections
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U trading_user -d trading_system -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND state_change < now() - interval '5 minutes';"

# 2. Increase connection limit (temporary)
# Edit .env
POSTGRES_MAX_POOL_SIZE=100

# 3. Restart trading system
docker-compose restart trading-system

# 4. Monitor connection usage
watch -n 5 'docker-compose exec postgres psql -U trading_user -d trading_system -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"'
```

#### Scenario C: Database Corruption

```bash
# 1. Stop trading system immediately
docker-compose stop trading-system

# 2. Backup current database
./scripts/backup.sh emergency

# 3. Check database integrity
docker-compose exec postgres pg_checksums -D /var/lib/postgresql/data

# 4. If corruption detected, restore from backup
./scripts/restore.sh latest

# 5. Verify restoration
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U trading_user -d trading_system -c "SELECT COUNT(*) FROM trades;"

# 6. Restart trading system
docker-compose start trading-system
```

### Prevention

- Set up connection pool monitoring
- Configure connection pool limits appropriately
- Enable statement timeout
- Set up database replication for HA
- Regular backup verification

---

## Runbook 3: High Error Rate

**Severity:** P1 - HIGH
**Response Time:** < 1 hour

### Symptoms
- Error rate > 5% in monitoring dashboard
- Multiple 500 errors in logs
- Users reporting failures
- Alert: "HighAPIErrorRate"

### Investigation Steps

1. **Check error logs**
   ```bash
   docker-compose logs trading-system --tail=200 | grep -i "error\|exception\|traceback"
   ```

2. **Check error rate by endpoint**
   ```bash
   # If you have access to application logs
   grep "ERROR" /app/logs/*.log | awk '{print $NF}' | sort | uniq -c | sort -rn
   ```

3. **Check external dependencies**
   ```bash
   # Test Zerodha API
   curl -I https://api.kite.trade

   # Test database
   PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U trading_user -d trading_system -c "SELECT 1;"

   # Test Redis
   redis-cli -h localhost -p 6379 -a $REDIS_PASSWORD ping
   ```

4. **Check recent deployments**
   ```bash
   git log -5 --oneline
   docker images | head
   ```

### Resolution Steps

#### Scenario A: External API Failures (Zerodha)

```bash
# 1. Check API quota
python3 << EOF
from infrastructure.api_quota_monitor import get_quota_monitor
monitor = get_quota_monitor()
monitor.print_status()
EOF

# 2. Enable circuit breaker if not already enabled
# Check application config

# 3. Consider fallback mode
# - Pause new orders
# - Allow position closures only
# - Notify users of degraded service

# 4. Monitor API recovery
# Watch for error rate to decrease
```

#### Scenario B: Database Performance Issues

```bash
# 1. Check slow queries
python3 << EOF
from infrastructure.query_optimizer import get_query_optimizer
optimizer = get_query_optimizer()
optimizer.print_report()
EOF

# 2. Check database load
docker-compose exec postgres psql -U trading_user -d trading_system -c \
  "SELECT pid, usename, state, query_start, LEFT(query, 60) FROM pg_stat_activity WHERE state != 'idle';"

# 3. Kill long-running queries
# Identify problematic query PID from above
docker-compose exec postgres psql -U trading_user -d trading_system -c \
  "SELECT pg_terminate_backend(PID);"

# 4. Apply query optimizations
# Review and apply recommendations from query optimizer
```

#### Scenario C: Memory Leak / Resource Exhaustion

```bash
# 1. Check memory usage
docker stats --no-stream trading-system

# 2. Check for memory leaks
docker-compose logs trading-system | grep -i "memory\|oom"

# 3. Restart service to reclaim memory
docker-compose restart trading-system

# 4. Monitor memory usage
watch -n 10 'docker stats --no-stream trading-system | grep -v CONTAINER'

# 5. Consider reducing cache size if needed
# Edit .env: CACHE_SIZE=5000 (reduce from 10000)
# Restart: docker-compose restart trading-system
```

#### Scenario D: Code Bug in Recent Deployment

```bash
# 1. Confirm recent deployment correlation
git log -1

# 2. Review recent changes
git diff HEAD~1 HEAD

# 3. Decision: Hotfix vs Rollback
# If simple fix available: Deploy hotfix
# If complex or unclear: Rollback

# 4. Rollback if necessary
git revert HEAD
docker-compose build trading-system
docker-compose up -d trading-system

# 5. Verify error rate decreases
# Monitor for 15 minutes
```

### Post-Resolution

- Review error logs for root cause
- Update error handling if needed
- Add monitoring for specific error type
- Update alerting thresholds if appropriate

---

## Runbook 4: Trading Execution Failures

**Severity:** P0 - CRITICAL
**Response Time:** < 15 minutes

### Symptoms
- Orders not being placed
- Trades failing with errors
- Alert: "HighTradeFailureRate"
- Users reporting cannot trade

### Investigation Steps

1. **Check trading system status**
   ```bash
   curl http://localhost:8080/health | jq
   ./scripts/status.sh
   ```

2. **Check Zerodha API connectivity**
   ```bash
   # Test API health
   curl https://api.kite.trade

   # Check API credentials
   env | grep ZERODHA_API
   ```

3. **Check recent trade logs**
   ```bash
   docker-compose logs trading-system | grep -i "trade\|order" | tail -50
   ```

4. **Check database for recent trades**
   ```bash
   PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U trading_user -d trading_system -c \
     "SELECT order_id, symbol, status, status_message FROM orders ORDER BY order_timestamp DESC LIMIT 10;"
   ```

### Resolution Steps

#### Scenario A: API Credentials Invalid

```bash
# 1. Verify API credentials are set
echo "API Key: ${ZERODHA_API_KEY:0:10}..."
echo "API Secret: ${ZERODHA_API_SECRET:0:10}..."

# 2. Check if access token is valid
# Access tokens expire daily - regenerate if needed

# 3. Update credentials in .env
vim .env

# 4. Restart trading system
docker-compose restart trading-system

# 5. Test with small order
# Manual verification needed
```

#### Scenario B: API Quota Exceeded

```bash
# 1. Check quota usage
python3 << EOF
from infrastructure.api_quota_monitor import get_quota_monitor
monitor = get_quota_monitor()
print(f"Quota used: {monitor.get_usage_percentage()}%")
EOF

# 2. If quota exceeded:
# - Wait for quota reset (check Zerodha rate limits)
# - Reduce trading frequency
# - Optimize API calls

# 3. Enable aggressive caching temporarily
# Edit constants.py to increase cache TTL

# 4. Restart with new settings
docker-compose restart trading-system
```

#### Scenario C: Insufficient Funds

```bash
# 1. Check account balance
# Via Zerodha dashboard or API

# 2. If legitimate:
# - Reduce position sizes
# - Close some positions
# - Add funds to account

# 3. If error:
# - Check balance calculation logic
# - Review recent trades
# - Verify position tracking
```

#### Scenario D: Market Closed / Circuit Breaker

```bash
# 1. Check market status
date  # Verify current time
# Market hours: 9:15 AM - 3:30 PM IST

# 2. Check for circuit breakers
# Via NSE/BSE websites

# 3. If market closed:
# - Normal behavior, no action needed
# - Ensure system handles gracefully

# 4. If circuit breaker:
# - System should auto-pause
# - Verify circuit breaker detection working
```

### Emergency Actions

If trading must be stopped immediately:

```bash
# 1. Enable maintenance mode
# Set in .env:
MAINTENANCE_MODE=true

# 2. Restart trading system
docker-compose restart trading-system

# 3. Verify no new trades
docker-compose logs trading-system | grep -i "order"

# 4. Close all positions manually if needed
# Via Zerodha Kite dashboard
```

### Post-Resolution

- Verify trading resumed successfully
- Check all pending orders
- Review position reconciliation
- Update risk parameters if needed
- Notify trading team

---

## Runbook 5: Performance Degradation

**Severity:** P2 - MEDIUM
**Response Time:** < 4 hours

### Symptoms
- Response times > 1000ms
- Alert: "SlowResponseTime"
- Dashboard sluggish
- Users reporting slowness

### Investigation Steps

1. **Check system resources**
   ```bash
   docker stats --no-stream
   df -h
   free -h
   ```

2. **Check query performance**
   ```bash
   python3 << EOF
   from infrastructure.query_optimizer import get_query_optimizer
   stats = get_query_optimizer().get_statistics()
   print(f"Avg query time: {stats['avg_query_time_ms']}ms")
   print(f"Slow queries: {stats['slow_query_count']}")
   EOF
   ```

3. **Check cache performance**
   ```bash
   # Check Redis
   redis-cli -a $REDIS_PASSWORD INFO stats | grep hits

   # Check application cache
   # Review query optimizer report
   ```

4. **Check recent load**
   ```bash
   # Check concurrent users
   docker-compose logs trading-system | grep "WebSocket client connected" | wc -l
   ```

### Resolution Steps

#### Scenario A: High Database Load

```bash
# 1. Review slow queries
python3 -c "from infrastructure.query_optimizer import get_query_optimizer; get_query_optimizer().print_report()"

# 2. Apply missing indexes
# Generate recommendations
# Apply via psql

# 3. Increase cache TTL temporarily
# Edit application config

# 4. Consider read replica for SELECT queries
# Implement if HA setup available
```

#### Scenario B: Memory Pressure

```bash
# 1. Check memory usage by component
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"

# 2. Reduce cache sizes
# Edit .env
CACHE_SIZE=5000  # Reduce from 10000
REDIS_MAX_MEMORY=128mb  # Reduce from 256mb

# 3. Restart services
docker-compose restart
```

#### Scenario C: High CPU Usage

```bash
# 1. Identify CPU-intensive process
docker stats

# 2. Check for inefficient queries
# Review query optimizer report

# 3. Check for infinite loops in code
# Review recent changes

# 4. Scale horizontally if needed
# Add more trading-system instances
```

### Optimization Actions

```bash
# 1. Apply query optimizations
./scripts/optimize_queries.sh

# 2. Clear old data
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U trading_user -d trading_system << EOF
-- Archive old trades
DELETE FROM api_calls WHERE request_timestamp < NOW() - INTERVAL '30 days';
DELETE FROM system_metrics WHERE collected_at < NOW() - INTERVAL '7 days';
VACUUM ANALYZE;
EOF

# 3. Restart with optimizations
docker-compose restart trading-system
```

---

## Runbook 6: Data Integrity Issues

**Severity:** P1 - HIGH
**Response Time:** < 1 hour

### Symptoms
- Position mismatch between system and broker
- P&L calculations incorrect
- Missing trades in database
- Duplicate records

### Investigation Steps

1. **Compare positions: System vs Broker**
   ```bash
   # Export system positions
   PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U trading_user -d trading_system -c \
     "SELECT symbol, quantity, avg_price FROM positions WHERE status = 'ACTIVE';" > system_positions.txt

   # Compare with broker positions (manual via Kite)
   ```

2. **Check for missing trades**
   ```bash
   PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U trading_user -d trading_system -c \
     "SELECT COUNT(*), DATE(entry_time) FROM trades GROUP BY DATE(entry_time) ORDER BY DATE(entry_time) DESC LIMIT 7;"
   ```

3. **Check for duplicates**
   ```bash
   PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U trading_user -d trading_system -c \
     "SELECT order_id, COUNT(*) FROM orders GROUP BY order_id HAVING COUNT(*) > 1;"
   ```

### Resolution Steps

#### Scenario A: Position Reconciliation

```bash
# 1. Stop trading immediately
# Set MAINTENANCE_MODE=true

# 2. Export broker positions
# Via Zerodha API or dashboard

# 3. Run reconciliation script
python3 << EOF
# Compare and reconcile positions
# Update database to match broker
# Log discrepancies
EOF

# 4. Verify reconciliation
# Manual review required

# 5. Resume trading only after verification
```

#### Scenario B: Missing Trades

```bash
# 1. Check trade execution logs
docker-compose logs trading-system | grep "order.*executed"

# 2. Query Zerodha API for trade history
# Compare with database

# 3. Insert missing trades manually
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U trading_user -d trading_system << EOF
-- Insert missing trade
INSERT INTO trades (trade_id, symbol, ...) VALUES (...);
EOF

# 4. Recalculate P&L
# Run P&L recalculation script
```

#### Scenario C: Duplicate Records

```bash
# 1. Identify duplicates
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U trading_user -d trading_system -c \
  "SELECT order_id, COUNT(*), array_agg(id) FROM orders GROUP BY order_id HAVING COUNT(*) > 1;"

# 2. Review duplicates
# Determine which record is correct

# 3. Delete duplicates (keep correct one)
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U trading_user -d trading_system << EOF
DELETE FROM orders WHERE id = [duplicate_id];
EOF

# 4. Add unique constraint to prevent future duplicates
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U trading_user -d trading_system << EOF
ALTER TABLE orders ADD CONSTRAINT orders_order_id_unique UNIQUE (order_id);
EOF
```

### Post-Resolution

- Run full data integrity check
- Review audit logs
- Update data validation logic
- Schedule regular reconciliation

---

## Communication Templates

### Incident Start

```
🚨 INCIDENT ALERT

Severity: [P0/P1/P2/P3]
Status: INVESTIGATING
Component: [Trading System / Database / API]
Impact: [Description]
Started: [Timestamp]
On-Call: [Name]

We are investigating [brief description].
Updates every 15 minutes or when status changes.

Status Page: [URL]
```

### Incident Update

```
📢 INCIDENT UPDATE #[N]

Status: [INVESTIGATING / IDENTIFIED / FIXING]
Time: [Timestamp]

Update:
[What we've learned]
[What we're doing now]
[Expected resolution time]

Next update: [Time]
```

### Incident Resolved

```
✅ INCIDENT RESOLVED

Duration: [Start time] to [End time] ([Duration])
Root Cause: [Brief description]

Resolution:
[What was done]

Impact:
[What was affected]
[Number of users/trades affected]

Next Steps:
- [ ] Post-mortem scheduled for [date/time]
- [ ] Preventive measures being implemented

Thank you for your patience.
```

---

## Escalation Procedures

### When to Escalate

**Escalate to Secondary On-Call if:**
- Primary cannot resolve in 30 minutes
- Primary needs additional expertise
- Multiple systems affected

**Escalate to Manager if:**
- Incident duration > 2 hours
- Data loss suspected
- Financial impact significant
- Customer escalation

**Escalate to Executive Team if:**
- Regulatory implications
- Major financial impact (> $10,000)
- Security breach
- Extended outage (> 4 hours)
- Media attention

### Escalation Contacts

```
L1 - On-Call Engineer: [Phone/Slack]
L2 - Senior Engineer: [Phone/Slack]
L3 - Engineering Manager: [Phone/Slack]
L4 - CTO: [Phone/Slack]
L5 - CEO: [Phone/Slack]
```

---

## Post-Incident Procedures

### 1. Incident Report (Within 24 hours)

**Required Sections:**
- Incident summary
- Timeline of events
- Impact assessment
- Root cause analysis
- Resolution steps taken
- Lessons learned
- Action items

### 2. Post-Mortem Meeting (Within 72 hours)

**Attendees:**
- On-call engineer
- Engineering team
- Product/Trading team
- Management (for P0/P1)

**Agenda:**
- Review incident timeline
- Discuss what went well
- Discuss what could be improved
- Identify action items
- Assign owners and due dates

### 3. Follow-Up Actions

**Immediate (< 1 week):**
- Implement quick fixes
- Update runbooks
- Add monitoring/alerts
- Update documentation

**Short-term (1-4 weeks):**
- Implement preventive measures
- Improve testing
- Update procedures
- Train team

**Long-term (1-3 months):**
- Architectural improvements
- Tool improvements
- Process improvements

---

## Prevention & Continuous Improvement

### Regular Reviews

- **Weekly:** Review incidents from past week
- **Monthly:** Review trends and patterns
- **Quarterly:** Review runbook effectiveness
- **Annually:** Comprehensive process review

### Metrics to Track

- Mean Time To Detect (MTTD)
- Mean Time To Acknowledge (MTTA)
- Mean Time To Resolve (MTTR)
- Incident frequency by type
- Repeat incidents
- Post-mortem action item completion rate

### Continuous Improvement

1. **Update Runbooks**
   - After each incident
   - Based on team feedback
   - When system changes

2. **Improve Monitoring**
   - Add alerts for new failure modes
   - Reduce false positives
   - Improve alert messaging

3. **Automate Recovery**
   - Auto-restart failed services
   - Auto-scale on high load
   - Self-healing capabilities

4. **Team Training**
   - Regular incident drills
   - Runbook walkthroughs
   - Knowledge sharing sessions

---

## Document Control

**Version:** 1.0.0
**Last Updated:** October 31, 2025
**Next Review:** Monthly
**Owner:** DevOps Team
**Approved By:** [CTO]

**Change History:**
- 2025-10-31: Initial version created
- [Future updates logged here]

---

**END OF RUNBOOK**

*Keep this document updated and accessible at all times. Lives depend on it... or at least, money does!* 💰
