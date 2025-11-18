# Disaster Recovery Plan
## Enhanced NIFTY 50 Trading System

**Version:** 1.0
**Last Updated:** Week 4 - Production Go-Live
**Classification:** CONFIDENTIAL
**Owner:** Trading System Team

---

## Executive Summary

This Disaster Recovery (DR) Plan outlines procedures to restore the Enhanced NIFTY 50 Trading System following a disaster that renders the primary system unavailable. The plan ensures business continuity with minimal data loss and downtime.

### Key Metrics

| Metric | Target | Maximum Acceptable |
|--------|--------|-------------------|
| **RTO** (Recovery Time Objective) | 30 minutes | 2 hours |
| **RPO** (Recovery Point Objective) | 1 hour | 4 hours |
| **Maximum Downtime During Trading Hours** | 15 minutes | 1 hour |
| **Data Loss Tolerance** | < 10 trades | < 50 trades |

### Disaster Scenarios Covered

1. Database failure/corruption
2. Application server failure
3. Complete data center outage
4. Network connectivity loss
5. Cloud provider outage
6. Cyber attack/ransomware
7. Natural disasters

---

## Table of Contents

1. [Disaster Classification](#disaster-classification)
2. [DR Infrastructure](#dr-infrastructure)
3. [Recovery Procedures](#recovery-procedures)
4. [Failover Procedures](#failover-procedures)
5. [Testing and Validation](#testing-and-validation)
6. [Roles and Responsibilities](#roles-and-responsibilities)
7. [Communication Plan](#communication-plan)
8. [Post-Recovery](#post-recovery)

---

## Disaster Classification

### Severity Levels

#### Level 1: CRITICAL (P0)
**Impact:** Trading system completely unavailable during market hours

**Examples:**
- Complete data center failure
- Database irreversibly corrupted
- Ransomware attack encrypting all systems
- Natural disaster (fire, flood)

**Response:** Immediate DR site activation

**Notification:** All stakeholders within 5 minutes

**Recovery Target:** < 30 minutes

---

#### Level 2: HIGH (P1)
**Impact:** Partial system unavailability, degraded performance

**Examples:**
- Primary database server failure (replica available)
- Application server failure (load balancer redirects)
- Network degradation
- Partial data corruption

**Response:** Failover to redundant systems

**Notification:** Key stakeholders within 15 minutes

**Recovery Target:** < 1 hour

---

#### Level 3: MEDIUM (P2)
**Impact:** Non-critical component failure, minimal trading impact

**Examples:**
- Monitoring system failure
- Dashboard unavailability
- Report generation failure
- Log aggregation issues

**Response:** Standard incident response

**Notification:** Team members within 1 hour

**Recovery Target:** < 4 hours

---

#### Level 4: LOW (P3)
**Impact:** No immediate trading impact

**Examples:**
- Development environment issues
- Documentation portal down
- Non-critical alerting issues

**Response:** Normal business hours resolution

**Notification:** Ticket system

**Recovery Target:** Next business day

---

## DR Infrastructure

### Primary Site

**Location:** Mumbai Data Center (Primary)

**Components:**
- Trading Application Server (2x)
- PostgreSQL Primary Database
- Redis Primary Instance
- Load Balancer
- Monitoring Stack (Prometheus, Grafana)

**Connectivity:**
- Zerodha API: Direct connection
- Internet: 1 Gbps dedicated line
- Backup: 500 Mbps broadband

---

### DR Site

**Location:** Bangalore Data Center (Secondary)

**Components:**
- Standby Trading Application Server (1x)
- PostgreSQL Replica Database (streaming replication)
- Redis Replica Instance (Redis Sentinel)
- Load Balancer
- Monitoring Stack (read-only)

**Connectivity:**
- Zerodha API: Direct connection (separate credentials)
- Internet: 1 Gbps dedicated line
- VPN to Primary Site: 100 Mbps

**Replication:**
- Database: Real-time streaming replication (< 1 second lag)
- Redis: Redis Sentinel with automatic failover
- Configuration: rsync every 5 minutes
- Logs: Forwarded real-time via Logstash

---

### Backup Infrastructure

**Local Backups:**
- Location: Network Attached Storage (NAS) at Primary Site
- Frequency: Hourly during trading hours, daily otherwise
- Retention: 7 days

**Off-site Backups:**
- Location: AWS S3 (Mumbai region)
- Frequency: Daily at 2:00 AM
- Retention: 90 days
- Encryption: AES-256

**Backup DR Site:**
- Location: AWS S3 (Singapore region - cross-region replication)
- Frequency: Continuous replication from Mumbai S3
- Retention: 90 days

---

## Recovery Procedures

### Procedure 1: Database Failure Recovery

**Scenario:** Primary PostgreSQL database is corrupted or unavailable

#### Detection
```bash
# Monitor shows database down
pg_isready -h localhost -p 5432
# Connection refused

# Or health check fails
curl http://localhost:8080/health
# {"status": "unhealthy", "database": "down"}
```

#### Assessment (2 minutes)
```bash
# Check database logs
docker logs trading-postgres --tail 100

# Check disk space
df -h

# Check for corruption
docker exec trading-postgres pg_checksums -D /var/lib/postgresql/data
```

#### Recovery Steps

**Option A: Restart Database (5 minutes)**
```bash
# If minor issue, try restart
docker-compose restart postgres

# Wait for startup
sleep 10

# Verify
pg_isready -h localhost -p 5432
```

**Option B: Promote Replica (10 minutes)**
```bash
# On DR site
ssh dr-server

# Promote replica to primary
docker exec postgres-replica pg_ctl promote -D /var/lib/postgresql/data

# Update connection strings
export DB_HOST=dr-database-hostname

# Restart trading system pointing to new primary
docker-compose up -d trading-system

# Verify
psql -h dr-database-hostname -U trading_user -d trading_db -c "SELECT 1"
```

**Option C: Restore from Backup (15 minutes)**
```bash
# Find latest backup
ls -lt backups/ | head -1

# Restore
cd scripts
./restore.sh ../backups/<latest-timestamp>

# Verify
docker exec trading-postgres psql -U trading_user -d trading_db -c "\dt"
```

#### Validation
```bash
# Check trade data
psql -h localhost -U trading_user -d trading_db -c "
  SELECT COUNT(*) as total_trades,
         MAX(created_at) as latest_trade
  FROM trades;
"

# Verify positions
psql -h localhost -U trading_user -d trading_db -c "
  SELECT symbol, quantity, entry_price
  FROM positions
  WHERE status = 'open';
"

# Test trading functionality
docker-compose exec trading-system python3 -c "
import trading_utils
print('Can place order:', trading_utils.test_order_placement())
"
```

---

### Procedure 2: Application Server Failure

**Scenario:** Trading application server crashes or becomes unresponsive

#### Detection
```bash
# Health check fails
curl http://localhost:8080/health
# Connection timeout

# Or container stopped
docker ps | grep trading-system
# No output
```

#### Assessment (1 minute)
```bash
# Check container status
docker ps -a | grep trading-system

# Check logs
docker logs trading-system --tail 100

# Check system resources
top
df -h
free -h
```

#### Recovery Steps

**Option A: Restart Container (2 minutes)**
```bash
# Restart trading system
docker-compose restart trading-system

# Monitor startup
docker logs -f trading-system

# Verify
curl http://localhost:8080/health
```

**Option B: Rebuild Container (5 minutes)**
```bash
# Stop and remove
docker-compose stop trading-system
docker-compose rm -f trading-system

# Rebuild
docker-compose up -d --build trading-system

# Verify
docker ps | grep trading-system
curl http://localhost:8080/health
```

**Option C: Failover to DR (10 minutes)**
```bash
# Update load balancer to point to DR
ssh load-balancer

# Edit NGINX config
vim /etc/nginx/conf.d/trading.conf
# Change upstream to DR server IP

# Reload NGINX
nginx -t && nginx -s reload

# Verify
curl http://trading.example.com/health
```

#### Validation
```bash
# Test API endpoints
curl http://localhost:8080/api/positions
curl http://localhost:8080/api/portfolio

# Check active positions
curl http://localhost:8080/api/positions | jq '.open_positions'

# Verify trading is enabled
curl http://localhost:8080/api/status | jq '.trading_enabled'
```

---

### Procedure 3: Complete Data Center Outage

**Scenario:** Primary data center completely unavailable (power, fire, natural disaster)

#### Detection
- All monitoring alerts firing
- Cannot reach primary site via any network path
- Physical confirmation of outage

#### Assessment (5 minutes)
```bash
# From laptop/mobile (outside primary DC)
# Try to reach primary
ping primary-server.example.com
# No response

# Try to reach DR
ping dr-server.example.com
# Successful

# Check DR replication lag
ssh dr-server
psql -h localhost -U trading_user -d trading_db -c "
  SELECT NOW() - pg_last_xact_replay_timestamp() AS replication_lag;
"
```

#### Recovery Steps: Full DR Activation (30 minutes)

**Step 1: Activate DR Database (5 minutes)**
```bash
# SSH to DR site
ssh dr-server

# Promote replica to primary
cd /opt/trading-system
./scripts/promote_replica.sh

# Verify promotion
psql -h localhost -U trading_user -d trading_db -c "
  SELECT pg_is_in_recovery();
"
# Should return 'f' (false) = not in recovery = primary
```

**Step 2: Start DR Application (5 minutes)**
```bash
# On DR site
cd /opt/trading-system

# Load environment
source .env.production

# Update config to use local database
export DB_HOST=localhost
export REDIS_HOST=localhost

# Start all services
docker-compose up -d

# Verify
docker-compose ps
```

**Step 3: Update DNS/Load Balancer (5 minutes)**
```bash
# Update DNS to point to DR site
# Option A: AWS Route 53
aws route53 change-resource-record-sets \
  --hosted-zone-id Z123456 \
  --change-batch file://dr-dns-update.json

# Option B: Manual DNS update (if using other provider)
# Login to DNS provider and update A record
# trading.example.com -> <DR-IP-ADDRESS>

# Verify DNS propagation
dig trading.example.com +short
# Should show DR IP
```

**Step 4: Configure External Connections (5 minutes)**
```bash
# On DR site
# Verify Zerodha API connectivity
curl https://api.kite.trade

# Test Zerodha authentication
docker-compose exec trading-system python3 -c "
from kiteconnect import KiteConnect
kite = KiteConnect(api_key='your-api-key')
print('API accessible:', kite.margins())
"

# Update any webhook URLs
# (if Zerodha postback configured)
```

**Step 5: Validate and Enable Trading (5 minutes)**
```bash
# Check positions match
psql -h localhost -U trading_user -d trading_db -c "
  SELECT symbol, quantity, entry_price, current_price
  FROM positions
  WHERE status = 'open';
"

# Reconcile with Zerodha
docker-compose exec trading-system python3 scripts/reconcile_positions.py

# If all looks good, enable trading
docker-compose exec trading-system python3 -c "
import trading_utils
trading_utils.enable_trading()
print('Trading enabled on DR site')
"
```

**Step 6: Notify Stakeholders (5 minutes)**
```bash
# Send notifications
cat <<EOF | mail -s "DR Activation: Trading System Now Running on DR Site" \
  trading-team@example.com,management@example.com

DR Activation Complete

Event: Primary data center outage
Time: $(date)
Action: Activated DR site in Bangalore

Status:
- Database: Running on DR site
- Trading System: Active
- API: Accessible at https://trading.example.com
- Trading: ENABLED

Data Loss: Estimated < 2 minutes (last replication: $(date -d '2 minutes ago'))

Next Steps:
1. Monitor DR site for 1 hour
2. Assess primary site damage
3. Plan primary site restoration

On-call team: +91-XXX-XXX-XXXX
EOF
```

#### Validation
```bash
# Comprehensive DR validation
cd /opt/trading-system/scripts
./validate_dr_site.sh

# Manual checks
# 1. Database
psql -h localhost -U trading_user -d trading_db -c "
  SELECT COUNT(*) FROM trades WHERE created_at > NOW() - INTERVAL '1 day';
  SELECT COUNT(*) FROM positions WHERE status = 'open';
"

# 2. Redis
docker exec trading-redis redis-cli DBSIZE

# 3. Trading system
curl http://localhost:8080/health
curl http://localhost:8080/api/status

# 4. Place test order (small quantity)
docker-compose exec trading-system python3 scripts/test_order.py \
  --symbol NIFTY50 --quantity 1 --type test

# 5. Monitor for 15 minutes
watch -n 10 'curl -s http://localhost:8080/health | jq .'
```

---

### Procedure 4: Cyber Attack / Ransomware

**Scenario:** Systems compromised by malware or ransomware

#### Detection
- Unusual file encryption
- Ransom notes displayed
- Systems behaving abnormally
- Security alerts

#### Immediate Actions (CRITICAL - First 10 minutes)

**DO NOT:**
- Pay ransom
- Try to decrypt files
- Delete encrypted files
- Shut down systems (may destroy evidence)

**DO:**
```bash
# 1. ISOLATE infected systems immediately
# Disconnect from network
ip link set eth0 down

# 2. Preserve evidence
# Take memory dump
dd if=/dev/mem of=/tmp/memory_dump.img

# Take disk snapshot
lvcreate --size 100G --snapshot --name compromised_snapshot /dev/vg0/root

# 3. Document everything
echo "Incident detected at: $(date)" >> /tmp/incident_log.txt
ps aux >> /tmp/incident_log.txt
netstat -antup >> /tmp/incident_log.txt
ls -lR /opt/trading-system >> /tmp/incident_log.txt
```

#### Recovery Steps (30 minutes)

**Step 1: Activate Clean DR Site**
```bash
# Immediately switch to DR site (confirmed clean)
# Follow "Complete Data Center Outage" procedure above

# DO NOT restore from backups yet (may be infected)
```

**Step 2: Forensic Analysis**
```bash
# Engage security team
# Analyze attack vector
# Identify patient zero
# Check backup integrity
```

**Step 3: Clean Restoration**
```bash
# Only after security team confirms backups are clean
# Rebuild primary site from scratch

# 1. Wipe all systems
# 2. Fresh OS installation
# 3. Fresh Docker installation
# 4. Deploy from Git (verified clean commit)
# 5. Restore data from pre-incident backup
```

**Step 4: Security Hardening**
```bash
# Implement recommended security measures
# Update all passwords
# Enable MFA
# Review access logs
# Apply security patches
```

---

## Failover Procedures

### Automatic Failover

**Database (PostgreSQL Streaming Replication):**

Automatic failover handled by Patroni or pg_auto_failover:

```yaml
# patroni.yml
scope: trading-system
name: postgres-primary

postgresql:
  listen: 0.0.0.0:5432
  connect_address: postgres-primary:5432
  data_dir: /var/lib/postgresql/data
  authentication:
    replication:
      username: replicator
      password: ${REPLICATION_PASSWORD}
  parameters:
    wal_level: replica
    hot_standby: "on"
    max_wal_senders: 10
    max_replication_slots: 10

patroni:
  ttl: 30
  loop_wait: 10
  retry_timeout: 30
  maximum_lag_on_failover: 1048576

tags:
  nofailover: false
  noloadbalance: false
  clonefrom: false
```

**Redis (Redis Sentinel):**

Automatic failover configured:

```conf
# sentinel.conf
sentinel monitor trading-redis redis-primary 6379 2
sentinel auth-pass trading-redis ${REDIS_PASSWORD}
sentinel down-after-milliseconds trading-redis 5000
sentinel parallel-syncs trading-redis 1
sentinel failover-timeout trading-redis 10000
```

### Manual Failover

**When to use manual failover:**
- Planned maintenance
- DR testing
- Performance issues on primary
- Suspected but not confirmed primary failure

**Steps:**

```bash
# 1. Disable trading (prevent new orders)
docker-compose exec trading-system python3 -c "
import trading_utils
trading_utils.disable_trading()
"

# 2. Wait for in-flight orders to complete (max 30 seconds)
sleep 30

# 3. Stop primary application
docker-compose stop trading-system

# 4. Promote DR database
ssh dr-server
docker exec postgres-replica pg_ctl promote

# 5. Start DR application
docker-compose up -d trading-system

# 6. Update load balancer / DNS
# (see Procedure 3, Step 3 above)

# 7. Re-enable trading
docker-compose exec trading-system python3 -c "
import trading_utils
trading_utils.enable_trading()
"

# 8. Monitor for 1 hour
watch -n 30 'curl -s http://localhost:8080/health | jq .'
```

---

## Testing and Validation

### DR Testing Schedule

| Test Type | Frequency | Duration | Participants |
|-----------|-----------|----------|--------------|
| DR Site Health Check | Weekly | 15 min | SRE Team |
| Database Failover Test | Monthly | 1 hour | DBA + SRE |
| Application Failover Test | Monthly | 2 hours | Dev + SRE |
| Full DR Activation | Quarterly | 4 hours | All teams |
| Cyber Attack Simulation | Annually | 8 hours | Security + All |

### DR Test Procedure

**Monthly DR Test (First Saturday of each month, 10:00 AM - market closed)**

```bash
#!/bin/bash
# dr_test.sh

echo "=== DR Test Started at $(date) ==="

# 1. Verify DR site health
echo "1. Checking DR site health..."
ssh dr-server "cd /opt/trading-system && docker-compose ps"

# 2. Check replication lag
echo "2. Checking replication lag..."
ssh dr-server "psql -h localhost -U trading_user -d trading_db -c '
  SELECT NOW() - pg_last_xact_replay_timestamp() AS lag;
'"

# 3. Perform test failover
echo "3. Performing test failover..."
ssh dr-server "cd /opt/trading-system && ./scripts/promote_replica.sh"

# 4. Validate DR site
echo "4. Validating DR site..."
curl https://dr-trading.example.com/health

# 5. Test order placement (test mode)
echo "5. Testing order placement..."
curl -X POST https://dr-trading.example.com/api/test/order \
  -H "Content-Type: application/json" \
  -d '{"symbol":"NIFTY50","quantity":1,"type":"test"}'

# 6. Document results
echo "6. Documenting results..."
cat > dr_test_results_$(date +%Y%m%d).txt <<EOF
DR Test Results
Date: $(date)
Duration: ${SECONDS} seconds

Health Check: PASS
Replication Lag: ${LAG}
Failover: PASS
Order Test: PASS

Issues Found: None
Recommendations: None

Next Test: $(date -d 'next month' +%Y-%m-%d)
EOF

# 7. Failback to primary
echo "7. Failing back to primary..."
ssh primary-server "cd /opt/trading-system && ./scripts/restore_primary.sh"

echo "=== DR Test Completed at $(date) ==="
```

### Success Criteria

DR test is considered successful if:

- [x] DR site health check passes
- [x] Replication lag < 5 seconds
- [x] Failover completes in < 30 minutes
- [x] All services start successfully on DR site
- [x] Test orders can be placed
- [x] Database data matches primary (within RPO)
- [x] Failback to primary succeeds
- [x] No data loss during test

---

## Roles and Responsibilities

### Incident Commander (IC)
**Primary:** Senior SRE Lead
**Backup:** Trading System Architect
**Contact:** +91-XXX-XXX-1001

**Responsibilities:**
- Declare disaster and severity level
- Activate DR plan
- Coordinate all recovery activities
- Make go/no-go decisions
- Communicate with stakeholders

---

### Database Administrator (DBA)
**Primary:** Database Lead
**Backup:** Senior Database Engineer
**Contact:** +91-XXX-XXX-1002

**Responsibilities:**
- Assess database health
- Execute database failover/recovery
- Verify data integrity
- Manage replication
- Restore from backups if needed

---

### System Administrator (SysAdmin)
**Primary:** Infrastructure Lead
**Backup:** Senior SysAdmin
**Contact:** +91-XXX-XXX-1003

**Responsibilities:**
- Assess infrastructure health
- Manage server failover
- Update DNS/load balancers
- Provision new infrastructure if needed
- Monitor system resources

---

### Application Owner
**Primary:** Trading System Lead Developer
**Backup:** Senior Developer
**Contact:** +91-XXX-XXX-1004

**Responsibilities:**
- Assess application health
- Restart/rebuild application
- Verify application functionality
- Test trading operations
- Approve trading resumption

---

### Security Lead
**Primary:** Information Security Officer
**Backup:** Security Engineer
**Contact:** +91-XXX-XXX-1005

**Responsibilities:**
- Assess security implications
- Identify attack vectors (if cyber attack)
- Approve system restoration
- Coordinate forensics
- Implement security hardening

---

### Business Stakeholder
**Primary:** Head of Trading
**Backup:** Trading Manager
**Contact:** +91-XXX-XXX-1006

**Responsibilities:**
- Business impact assessment
- Trading resumption approval
- Client communication
- Risk management decisions
- Post-mortem participation

---

## Communication Plan

### Communication Matrix

| Audience | Disaster Level | Medium | Frequency | Template |
|----------|----------------|--------|-----------|----------|
| Incident Team | All | Slack #incidents | Real-time | Status updates |
| Management | P0, P1 | Email + Phone | Every 30 min | Executive summary |
| Trading Team | P0, P1 | Email + SMS | Every 15 min | Trading status |
| Clients | P0 (if extended) | Email | At resolution | Service restoration |
| Regulators | P0 (if required) | Email + Phone | ASAP | Regulatory notice |

### Communication Templates

#### Initial Alert (Within 5 minutes of disaster declaration)

```
SUBJECT: [P0 INCIDENT] Trading System Disaster - DR Activation

INCIDENT SUMMARY:
Incident ID: INC-2024-001
Severity: P0 - CRITICAL
Start Time: 2024-01-01 10:30 IST
Status: DR activation in progress

IMPACT:
- Trading system unavailable on primary site
- Failover to DR site initiated
- Estimated recovery time: 30 minutes
- Estimated data loss: < 2 minutes of trades

ACTIONS TAKEN:
- Primary site confirmed down
- DR site activation initiated
- Incident Commander: [Name]
- War room: https://meet.google.com/xxx-xxxx-xxx

NEXT UPDATE: 10:45 IST (in 15 minutes)

Incident Commander: [Name]
Contact: +91-XXX-XXX-XXXX
```

#### Status Update (Every 15-30 minutes)

```
SUBJECT: [P0 INCIDENT] Update #2 - Trading System DR Activation

STATUS UPDATE:
Incident ID: INC-2024-001
Update Time: 2024-01-01 10:45 IST
Elapsed Time: 15 minutes

PROGRESS:
✅ DR database promoted to primary
✅ DR application started
🔄 DNS update in progress
⏳ Validation pending

CURRENT STATUS:
- DR site: 90% operational
- ETA to full recovery: 10-15 minutes
- Data loss: Confirmed < 2 minutes

BLOCKERS: None

NEXT UPDATE: 11:00 IST (in 15 minutes)
```

#### Resolution Notice

```
SUBJECT: [RESOLVED] Trading System DR Activation Complete

INCIDENT RESOLVED:
Incident ID: INC-2024-001
Resolution Time: 2024-01-01 11:00 IST
Total Duration: 30 minutes

SUMMARY:
- Primary site failure due to [reason]
- DR site successfully activated
- Trading resumed at 11:00 IST
- Data loss: 0 trades (all data replicated)

CURRENT STATE:
- Trading: ACTIVE on DR site (Bangalore)
- Status: Fully operational
- Monitoring: Enhanced monitoring for 24 hours
- Primary site: Assessment in progress

POST-MORTEM:
Scheduled for: 2024-01-02 14:00 IST
Meeting: [Calendar invite to follow]

Thank you for your patience during this incident.

Incident Commander: [Name]
```

---

## Post-Recovery

### Immediate Post-Recovery (First 24 hours)

**Hour 0-1: Stabilization**
```bash
# Enhance monitoring
# Increase metric collection frequency
# Add extra alerting
# Assign on-call engineer for 24h watch

# Monitor key metrics
watch -n 30 '
  curl -s http://localhost:8080/metrics | grep -E "trade|order|position"
'
```

**Hour 1-4: Validation**
```bash
# Verify all data
# Check for any anomalies
# Compare with expected state
# Reconcile with Zerodha

./scripts/full_system_validation.sh > validation_report.txt
```

**Hour 4-24: Monitoring**
```bash
# Continue enhanced monitoring
# Review logs every 2 hours
# Check for any degraded performance
# Prepare for primary site assessment
```

---

### Root Cause Analysis (Within 72 hours)

**RCA Template:**

```markdown
# Incident Post-Mortem

## Incident Summary
- **Incident ID:** INC-2024-001
- **Date:** 2024-01-01
- **Duration:** 30 minutes
- **Severity:** P0
- **Incident Commander:** [Name]

## Impact
- **Downtime:** 30 minutes
- **Data Loss:** 0 trades
- **Trades Affected:** 0
- **Revenue Impact:** ₹0 (no active trading at time)
- **Users Affected:** 0 (system down but no active users)

## Timeline
| Time | Event |
|------|-------|
| 10:30 | Primary site alerts fire - database unresponsive |
| 10:32 | Incident Commander declares P0 disaster |
| 10:35 | DR activation initiated |
| 10:40 | DR database promoted, application started |
| 10:50 | DNS updated to DR site |
| 10:55 | Validation complete |
| 11:00 | Trading resumed on DR site |

## Root Cause
[Detailed technical analysis of what caused the disaster]

## What Went Well
- DR site activation completed within RTO (30 min target, 30 min actual)
- No data loss (within RPO)
- Team coordination excellent
- Communication timely and clear

## What Went Wrong
- [Any issues during recovery]
- [Areas where we exceeded RTO/RPO]
- [Communication gaps if any]

## Action Items
| Action | Owner | Due Date | Priority |
|--------|-------|----------|----------|
| Fix root cause | [Name] | [Date] | P0 |
| Update DR procedure | [Name] | [Date] | P1 |
| Add preventive monitoring | [Name] | [Date] | P1 |

## Lessons Learned
1. [Key lesson 1]
2. [Key lesson 2]
3. [Key lesson 3]

## Follow-up
- Post-mortem meeting: [Date & Time]
- Action items review: Weekly until complete
- DR test with lessons applied: [Date]
```

---

### Primary Site Restoration

Once primary site is fixed:

```bash
#!/bin/bash
# restore_primary.sh

# 1. Verify primary site is fixed
ssh primary-server "docker-compose ps"

# 2. Setup replication FROM DR TO PRIMARY
# (DR is now the source of truth)
ssh primary-server "
  cd /opt/trading-system
  ./scripts/setup_replication_from_dr.sh
"

# 3. Wait for replication to catch up
while true; do
  LAG=$(ssh primary-server "psql -t -c 'SELECT NOW() - pg_last_xact_replay_timestamp()'")
  echo "Replication lag: $LAG"
  [ "$LAG" -lt 1 ] && break
  sleep 10
done

# 4. Plan failback window (market closed)
echo "Primary site ready for failback"
echo "Schedule failback for next market close"

# 5. During failback window
# Stop DR application
ssh dr-server "docker-compose stop trading-system"

# Promote primary
ssh primary-server "docker exec postgres-standby pg_ctl promote"

# Start primary application
ssh primary-server "docker-compose up -d"

# Update DNS back to primary
aws route53 change-resource-record-sets \
  --hosted-zone-id Z123456 \
  --change-batch file://primary-dns-update.json

# Verify
curl https://trading.example.com/health

# Reconfigure DR as standby again
ssh dr-server "./scripts/setup_replication_from_primary.sh"

echo "Failback complete - primary site restored"
```

---

## Appendices

### Appendix A: Emergency Contacts

| Role | Name | Primary Phone | Secondary | Email |
|------|------|---------------|-----------|-------|
| Incident Commander | [Name] | +91-XXX-1001 | +91-YYY-1001 | ic@example.com |
| DBA | [Name] | +91-XXX-1002 | +91-YYY-1002 | dba@example.com |
| SysAdmin | [Name] | +91-XXX-1003 | +91-YYY-1003 | sysadmin@example.com |
| App Owner | [Name] | +91-XXX-1004 | +91-YYY-1004 | appowner@example.com |
| Security | [Name] | +91-XXX-1005 | +91-YYY-1005 | security@example.com |
| Business | [Name] | +91-XXX-1006 | +91-YYY-1006 | business@example.com |

**Escalation Path:**
1. Incident Commander → Head of Engineering → CTO
2. Business Owner → Head of Trading → CEO

---

### Appendix B: Vendor Contacts

| Vendor | Service | Support Phone | Email | SLA |
|--------|---------|---------------|-------|-----|
| Zerodha | Trading API | 080-4719-0000 | support@zerodha.com | 24x7 |
| AWS | Cloud Infrastructure | +1-XXX-XXX-XXXX | aws-support@example.com | 24x7 |
| Data Center | Colocation | +91-XXX-XXX-XXXX | noc@datacenter.com | 24x7 |

---

### Appendix C: DR Checklist

**Pre-Disaster Checklist (Monthly verification):**
- [ ] DR site accessible
- [ ] Replication lag < 5 seconds
- [ ] DR backups up to date
- [ ] DNS failover tested
- [ ] Contact list updated
- [ ] Documentation current
- [ ] DR test completed successfully

**During Disaster Checklist:**
- [ ] Disaster declared and severity assigned
- [ ] Incident Commander notified
- [ ] War room established
- [ ] Initial alert sent
- [ ] Assessment complete
- [ ] Recovery procedure identified
- [ ] DR activation initiated
- [ ] Stakeholders notified every 15 min
- [ ] Validation complete
- [ ] Trading resumed
- [ ] Resolution notice sent

**Post-Disaster Checklist:**
- [ ] Enhanced monitoring enabled
- [ ] Full system validation run
- [ ] No anomalies found
- [ ] RCA initiated
- [ ] Post-mortem scheduled
- [ ] Action items assigned
- [ ] DR site ready for next disaster
- [ ] Primary site restoration planned

---

### Appendix D: Quick Reference

**Most Common Disasters and Recovery Time:**

| Disaster | Recovery Procedure | RTO | Commands |
|----------|-------------------|-----|----------|
| Database down | Restart or promote replica | 10 min | `docker-compose restart postgres` |
| App crash | Restart container | 2 min | `docker-compose restart trading-system` |
| Server down | Failover to DR | 30 min | `./scripts/activate_dr.sh` |
| Network down | Wait or failover | 15-30 min | `./scripts/check_network.sh` |
| Data corruption | Restore from backup | 15 min | `./scripts/restore.sh backups/latest` |

---

**Document Version History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-01-01 | Trading System Team | Initial version |

---

**Next Review Date:** 2024-04-01 (Quarterly)

**Document Owner:** Trading System Team

**Approval:**
- Engineering Lead: _________________ Date: _______
- Trading Lead: _________________ Date: _______
- CTO: _________________ Date: _______

---

END OF DISASTER RECOVERY PLAN
