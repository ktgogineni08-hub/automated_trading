# Disaster Recovery Plan

**Trading System - Business Continuity and Disaster Recovery**

Version: 1.0
Last Updated: November 2025
Owner: SRE Team / Infrastructure Team

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Recovery Objectives](#recovery-objectives)
3. [Disaster Scenarios](#disaster-scenarios)
4. [Recovery Procedures](#recovery-procedures)
5. [Backup Strategy](#backup-strategy)
6. [Failover Procedures](#failover-procedures)
7. [Data Recovery](#data-recovery)
8. [Communication Plan](#communication-plan)
9. [Testing & Validation](#testing--validation)
10. [Recovery Checklist](#recovery-checklist)

---

## Executive Summary

This Disaster Recovery (DR) plan defines procedures to recover the Trading System from catastrophic failures, ensuring minimal disruption to trading operations and data integrity.

### Critical Services

The following services are business-critical and must be recovered with highest priority:

1. **Trading Engine** - Order execution and strategy management
2. **Database (PostgreSQL)** - All persistent data
3. **Cache (Redis)** - Session state and market data
4. **Dashboard** - User interface and monitoring
5. **Market Data Pipeline** - Real-time data ingestion

### Business Impact

| Downtime | Business Impact | Financial Impact |
|----------|----------------|------------------|
| < 15 minutes | Minimal - Missed trading opportunities | Low (< ₹10K) |
| 15-60 minutes | Moderate - Multiple missed opportunities | Medium (₹10K-₹1L) |
| 1-4 hours | High - Significant trading halt | High (₹1L-₹10L) |
| > 4 hours | Critical - Daily trading compromised | Critical (> ₹10L) |

---

## Recovery Objectives

### RPO (Recovery Point Objective): **1 hour**

- **Definition:** Maximum acceptable data loss
- **Implementation:** Continuous replication + hourly backups
- **Worst Case:** Loss of last hour's trades

### RTO (Recovery Time Objective): **15 minutes**

- **Definition:** Maximum acceptable downtime
- **Implementation:** Hot standby + automated failover
- **Target:** System operational within 15 minutes of incident

### RTA (Recovery Time Actual)

Based on disaster recovery drills:

| Scenario | Target RTO | Actual RTA | Status |
|----------|-----------|------------|--------|
| Database Failover | 5 minutes | 3 minutes | ✅ Excellent |
| Redis Failover | 2 minutes | 1 minute | ✅ Excellent |
| Application Restart | 5 minutes | 4 minutes | ✅ Good |
| Full DR Activation | 15 minutes | 12 minutes | ✅ Good |
| Region Failover | 30 minutes | Not tested | ⚠️ Planned |

---

## Disaster Scenarios

### Scenario 1: Database Primary Failure

**Probability:** Medium
**Impact:** Critical
**RTO:** 5 minutes
**RPO:** 0 (streaming replication)

**Symptoms:**
- Database connection errors
- Application unable to persist trades
- Dashboard shows stale data
- Alert: `PostgreSQLPrimaryDown`

**Recovery:** [See PostgreSQL Failover](#postgresql-failover)

---

### Scenario 2: Complete Data Center Outage

**Probability:** Low
**Impact:** Critical
**RTO:** 30 minutes
**RPO:** 1 hour

**Symptoms:**
- All services unreachable
- Network connectivity lost
- Multiple critical alerts

**Recovery:** [See Region Failover](#region-failover)

---

### Scenario 3: Application Pod Crash Loop

**Probability:** Medium
**Impact:** High
**RTO:** 10 minutes
**RPO:** 0

**Symptoms:**
- Trading Engine restarting repeatedly
- Alert: `TradingSystemPodCrashLooping`
- Recent deployment or configuration change

**Recovery:** [See Application Recovery](#application-recovery)

---

### Scenario 4: Data Corruption

**Probability:** Low
**Impact:** Critical
**RTO:** 2 hours
**RPO:** 1 hour (latest backup)

**Symptoms:**
- Database integrity errors
- Inconsistent position data
- Invalid P&L calculations

**Recovery:** [See Data Restoration](#data-restoration)

---

### Scenario 5: Security Breach

**Probability:** Low
**Impact:** Critical
**RTO:** Variable
**RPO:** 0

**Symptoms:**
- Unauthorized access detected
- Alert: `SuspiciousActivity`
- Abnormal trading patterns

**Recovery:** [See Security Incident Response](#security-incident)

---

## Recovery Procedures

### PostgreSQL Failover

#### Automatic Failover (Preferred)

PostgreSQL streaming replication is configured with automatic failover.

**Process:**
1. Replication monitor detects primary failure
2. Replica automatically promoted to primary
3. Application reconnects to new primary
4. DNS/service endpoint updated

**Timeline:**
- Detection: 30 seconds
- Promotion: 1-2 minutes
- Application reconnect: 30 seconds
- **Total:** ~3 minutes

#### Manual Failover (If automatic fails)

```bash
# 1. SSH to replica server
ssh postgres-replica-0

# 2. Check replication status
sudo -u postgres psql -c "SELECT pg_is_in_recovery();"

# 3. Promote replica to primary
sudo -u postgres pg_ctl promote -D /var/lib/postgresql/data/pgdata

# 4. Verify promotion
sudo -u postgres psql -c "SELECT pg_is_in_recovery();"  # Should return 'f'

# 5. Update application connection string
kubectl set env deployment/trading-system \
  DATABASE_URL="postgresql://trading_user:password@postgres-replica-0:5432/trading_system"

# 6. Restart application pods
kubectl rollout restart deployment/trading-system -n trading-system-prod

# 7. Monitor application health
kubectl get pods -n trading-system-prod -w
```

**Verification:**
```bash
# Check database connectivity
psql -h postgres-replica-0 -U trading_user -d trading_system -c "SELECT NOW();"

# Verify write capability
psql -h postgres-replica-0 -U trading_user -d trading_system \
  -c "INSERT INTO health_check (timestamp) VALUES (NOW());"

# Check replication lag (should show no replicas initially)
psql -h postgres-replica-0 -U trading_user -d trading_system \
  -c "SELECT * FROM pg_stat_replication;"
```

---

### Redis Sentinel Failover

#### Automatic Failover (Preferred)

Redis Sentinel automatically promotes a replica when master fails.

**Process:**
1. Sentinel detects master failure (5 seconds)
2. Quorum vote among Sentinels (2 of 3 required)
3. Replica promoted to new master
4. Application reconnects automatically

**Timeline:**
- Detection: 5-10 seconds
- Vote + promotion: 5-10 seconds
- Client reconnect: 2-5 seconds
- **Total:** ~20 seconds

#### Manual Failover

```bash
# 1. Connect to Sentinel
kubectl exec -it redis-sentinel-0 -n trading-system-prod -- redis-cli -p 26379

# 2. Check master status
SENTINEL master mymaster

# 3. Force failover (if needed)
SENTINEL failover mymaster

# 4. Verify new master
SENTINEL get-master-addr-by-name mymaster

# 5. Check replica status
SENTINEL replicas mymaster
```

---

### Application Recovery

#### Pod Crash Loop

```bash
# 1. Check pod status
kubectl get pods -n trading-system-prod

# 2. View recent logs
kubectl logs trading-system-xxxxx -n trading-system-prod --tail=100

# 3. Check recent events
kubectl describe pod trading-system-xxxxx -n trading-system-prod

# 4. Common fixes:

# 4a. Rollback recent deployment
kubectl rollout undo deployment/trading-system -n trading-system-prod

# 4b. Fix configuration issue
kubectl edit configmap trading-system-config -n trading-system-prod

# 4c. Fix resource limits
kubectl edit deployment trading-system -n trading-system-prod
# Increase memory/CPU limits

# 5. Force pod restart
kubectl delete pod trading-system-xxxxx -n trading-system-prod

# 6. Monitor recovery
kubectl get pods -n trading-system-prod -w
```

---

### Data Restoration

#### From Latest Backup

```bash
# 1. Stop trading engine to prevent new writes
kubectl scale deployment/trading-system --replicas=0 -n trading-system-prod

# 2. Identify latest backup
aws s3 ls s3://trading-system-backups/postgres/ --recursive | sort | tail -10

# Example: postgres-backup-2025-11-01-08-00.sql.gz

# 3. Download backup
aws s3 cp s3://trading-system-backups/postgres/postgres-backup-2025-11-01-08-00.sql.gz /tmp/

# 4. Connect to database
kubectl exec -it postgres-primary-0 -n trading-system-prod -- bash

# 5. Drop existing database (CAREFUL!)
sudo -u postgres dropdb trading_system

# 6. Restore from backup
gunzip < /tmp/postgres-backup-2025-11-01-08-00.sql.gz | \
  sudo -u postgres psql trading_system

# 7. Verify data integrity
sudo -u postgres psql trading_system -c "SELECT COUNT(*) FROM trades;"
sudo -u postgres psql trading_system -c "SELECT MAX(created_at) FROM trades;"

# 8. Restart application
kubectl scale deployment/trading-system --replicas=3 -n trading-system-prod

# 9. Verify application health
kubectl get pods -n trading-system-prod
curl -f http://trading-system-service/health
```

#### Point-in-Time Recovery (PITR)

```bash
# 1. Stop all write operations
kubectl scale deployment/trading-system --replicas=0 -n trading-system-prod

# 2. Identify target recovery time
TARGET_TIME="2025-11-01 14:30:00"

# 3. Restore base backup
# (same as above)

# 4. Apply WAL files up to target time
sudo -u postgres pg_waldump /path/to/wal/files > /tmp/wal_analysis.txt

# 5. Restore to specific point
sudo -u postgres psql trading_system <<EOF
SELECT pg_create_restore_point('before_disaster');
-- Apply WAL segments
EOF

# 6. Verify data at target time
sudo -u postgres psql trading_system -c \
  "SELECT * FROM trades WHERE created_at <= '$TARGET_TIME' ORDER BY created_at DESC LIMIT 10;"
```

---

### Region Failover

**Current Status:** Single-region deployment
**Planned:** Q1 2026 multi-region

**When Multi-Region is Available:**

```bash
# 1. Declare disaster in primary region
# Update status page, notify stakeholders

# 2. Verify DR region health
kubectl --context=dr-region get nodes
kubectl --context=dr-region get pods -n trading-system-prod

# 3. Update DNS to point to DR region
# Change A record for api.trading-system.example.com
# TTL: 60 seconds

# 4. Verify DR database has latest data
# Check replication lag < 5 minutes

# 5. Start trading engine in DR region
kubectl --context=dr-region scale deployment/trading-system --replicas=3

# 6. Verify application functionality
curl -f https://api.trading-system.example.com/health

# 7. Monitor closely for 1 hour
# Check logs, metrics, alerts

# 8. Post-recovery: Sync data back to primary
# When primary region is restored
```

---

## Backup Strategy

### Database Backups

#### Full Backups

**Frequency:** Daily at 2 AM UTC
**Retention:** 30 days
**Location:** S3 bucket `s3://trading-system-backups/postgres/`

**Backup Script:**
```bash
#!/bin/bash
# /scripts/backup-database.sh

BACKUP_DIR="/var/backups/postgres"
S3_BUCKET="s3://trading-system-backups/postgres"
TIMESTAMP=$(date +%Y-%m-%d-%H-%M)
BACKUP_FILE="postgres-backup-${TIMESTAMP}.sql.gz"

# Create backup
sudo -u postgres pg_dump trading_system | gzip > "${BACKUP_DIR}/${BACKUP_FILE}"

# Upload to S3
aws s3 cp "${BACKUP_DIR}/${BACKUP_FILE}" "${S3_BUCKET}/"

# Verify backup
aws s3 ls "${S3_BUCKET}/${BACKUP_FILE}"

# Cleanup old local backups (keep 7 days)
find "${BACKUP_DIR}" -name "postgres-backup-*.sql.gz" -mtime +7 -delete

# Cleanup old S3 backups (keep 30 days)
aws s3 ls "${S3_BUCKET}/" | while read -r line; do
    createDate=$(echo $line | awk '{print $1" "$2}')
    createDate=$(date -d "$createDate" +%s)
    olderThan=$(date --date="30 days ago" +%s)
    if [[ $createDate -lt $olderThan ]]; then
        fileName=$(echo $line | awk '{print $4}')
        aws s3 rm "${S3_BUCKET}/${fileName}"
    fi
done

# Log completion
echo "Backup completed: ${BACKUP_FILE}" >> /var/log/backups.log
```

#### Continuous Backup (WAL Archiving)

**Configuration in `postgresql.conf`:**
```
wal_level = replica
archive_mode = on
archive_command = 'aws s3 cp %p s3://trading-system-backups/postgres-wal/%f'
archive_timeout = 300  # 5 minutes
```

---

### State File Backups

**Frequency:** Every 30 seconds (throttled)
**Retention:** 7 days
**Location:**
- Primary: `state/trading_state.json`
- Backup: `s3://trading-system-backups/state/`

---

### Configuration Backups

**Frequency:** On every change
**Retention:** Indefinite (Git version control)
**Location:** GitHub repository

```bash
# Backup Kubernetes configurations
kubectl get all -n trading-system-prod -o yaml > k8s-backup-$(date +%Y%m%d).yaml
git add k8s-backup-*.yaml
git commit -m "Backup Kubernetes configuration"
git push
```

---

## Communication Plan

### Incident Declaration

**Decision Criteria:**
- RTO exceeded (> 15 minutes downtime)
- Data loss risk
- Security breach
- Complete region outage

**Declaration Process:**
1. On-call engineer assesses impact
2. Escalate to Senior SRE if P1 incident
3. Activate incident response team
4. Notify stakeholders

---

### Stakeholder Communication

**Internal:**
- Engineering Team: Slack #incidents channel
- Management: Email + Phone call
- Trading Operations: Immediate notification

**External:**
- Clients: Status page update
- Regulators: Within 24 hours (if required)

**Communication Templates:**

**Initial Notification:**
```
SUBJECT: [P1 INCIDENT] Trading System Outage

The Trading System is currently experiencing an outage affecting [impacted services].

Impact: [Description]
Start Time: [Timestamp]
Estimated Recovery: [Time]
Current Status: [Investigating/Recovering/Restored]

We will provide updates every 30 minutes.

Incident Commander: [Name]
```

**Resolution Notification:**
```
SUBJECT: [RESOLVED] Trading System Restored

The Trading System has been fully restored.

Incident Summary:
- Duration: [X] hours
- Root Cause: [Brief description]
- Impact: [What was affected]
- Resolution: [What was done]

A detailed post-mortem will be published within 72 hours.
```

---

## Testing & Validation

### DR Drill Schedule

**Frequency:** Quarterly
**Next Drill:** February 2026

**Drill Types:**

1. **Tabletop Exercise** (Monthly)
   - Discussion-based
   - No actual failover
   - Duration: 1 hour

2. **Component Failover** (Quarterly)
   - Test database OR cache failover
   - Production-like environment
   - Duration: 2 hours

3. **Full DR Test** (Annually)
   - Complete DR activation
   - Non-production environment
   - Duration: 4 hours

---

### Test Results Log

| Date | Test Type | Component | Result | RTO Actual | Issues Found |
|------|-----------|-----------|--------|------------|--------------|
| 2025-10-15 | Component | PostgreSQL | ✅ Pass | 3 min | None |
| 2025-10-15 | Component | Redis | ✅ Pass | 1 min | None |
| 2025-09-01 | Tabletop | Full DR | ✅ Pass | N/A | Documentation gaps |
| 2025-08-01 | Component | App Restart | ✅ Pass | 4 min | None |

---

## Recovery Checklist

### Pre-Disaster Preparation

- [ ] Verify backups are running successfully
- [ ] Test restore from latest backup (monthly)
- [ ] Verify replication lag < 5 seconds
- [ ] Ensure on-call engineer has access to all systems
- [ ] Review and update DR documentation
- [ ] Verify alerting is working
- [ ] Test failover procedures in staging

### During Disaster

- [ ] Declare incident and notify team
- [ ] Assess scope and impact
- [ ] Activate appropriate recovery procedure
- [ ] Document all actions taken
- [ ] Provide regular status updates
- [ ] Verify data integrity after recovery
- [ ] Monitor system closely for 24 hours

### Post-Disaster

- [ ] Conduct post-mortem within 72 hours
- [ ] Document lessons learned
- [ ] Update DR procedures based on findings
- [ ] Communicate results to stakeholders
- [ ] File incident report
- [ ] Update runbooks
- [ ] Schedule follow-up DR drill

---

## Contact Information

### Emergency Contacts

| Role | Primary | Backup | Phone | Email |
|------|---------|--------|-------|-------|
| Incident Commander | On-Call SRE | Senior SRE | - | oncall@example.com |
| Database Admin | DBA Team | SRE Team | - | dba@example.com |
| Engineering Lead | Tech Lead | Director | - | eng-lead@example.com |
| Business Owner | VP Product | CTO | - | vp-product@example.com |

### Vendor Support

| Vendor | Support Type | Contact | SLA |
|--------|--------------|---------|-----|
| AWS | Infrastructure | AWS Support Console | 1 hour |
| Zerodha | API | support@zerodha.com | 2 hours |
| Database Vendor | PostgreSQL | Enterprise support | 4 hours |

---

## Appendix

### Related Documents

- [High Availability Architecture](./architecture/HA_ARCHITECTURE.md)
- [Alert Escalation Policy](./ALERT_ESCALATION_POLICY.md)
- [Runbook Index](./RUNBOOKS.md)
- [Security Incident Response](./SECURITY_INCIDENT_RESPONSE.md)

### Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Nov 2025 | SRE Team | Initial version |

---

**Document Classification:** Confidential
**Review Frequency:** Quarterly
**Next Review Date:** February 2026
**Approval:** CTO, VP Engineering

---

**END OF DISASTER RECOVERY PLAN**
