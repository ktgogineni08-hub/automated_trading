# RB-001: Database Primary Down

**Severity:** P1 - Critical
**Estimated Time:** 5 minutes
**Skills Required:** Database Administration, Kubernetes
**Alert:** `PostgreSQLPrimaryDown`

---

## Symptoms

- Application cannot connect to database
- Dashboard shows "Database Connection Error"
- Prometheus alert: `PostgreSQLPrimaryDown`
- Trading engine unable to persist trades
- Logs show: `psycopg2.OperationalError: could not connect to server`

**Impact:** Complete trading halt, no new orders can be placed

---

## Prerequisites

- kubectl access to trading-system-prod namespace
- PostgreSQL admin credentials
- Access to database monitoring dashboards

---

## Diagnosis

### Step 1: Verify Primary is Actually Down

```bash
# Check pod status
kubectl get pods -n trading-system-prod | grep postgres-primary

# Expected if down:
# postgres-primary-0   0/1     Error   0          5m
```

### Step 2: Check Pod Logs

```bash
kubectl logs postgres-primary-0 -n trading-system-prod --tail=50
```

Look for:
- OOM (Out of Memory) kills
- Disk full errors
- Crash loops
- Database corruption messages

### Step 3: Check Replication Status

```bash
# Check if replicas are healthy
kubectl get pods -n trading-system-prod | grep postgres-replica

# Both replicas should be Running:
# postgres-replica-0   1/1     Running   0          2h
# postgres-replica-1   1/1     Running   0          2h
```

### Step 4: Check Automatic Failover

```bash
# Check if replicas have been promoted
kubectl exec -it postgres-replica-0 -n trading-system-prod -- \
  psql -U trading_user -d trading_system -c "SELECT pg_is_in_recovery();"

# If returns 'f' (false), replica has been promoted to primary
```

---

## Resolution

### Option 1: Automatic Failover Already Occurred (BEST CASE)

If automatic failover happened:

```bash
# 1. Verify new primary is accepting writes
kubectl exec -it postgres-replica-0 -n trading-system-prod -- \
  psql -U trading_user -d trading_system \
  -c "INSERT INTO health_check (timestamp, status) VALUES (NOW(), 'test');"

# 2. Update application to use new primary
# (If using service endpoint, this may be automatic)

# 3. Verify application connectivity
kubectl logs trading-system-xxxxx -n trading-system-prod | grep -i "database connected"

# 4. Monitor for 15 minutes
# Check Grafana dashboard for database metrics
```

**If successful, proceed to [Post-Resolution](#post-resolution)**

---

### Option 2: Manual Failover Required

If automatic failover didn't occur:

```bash
# 1. Choose healthiest replica
kubectl exec -it postgres-replica-0 -n trading-system-prod -- \
  psql -U trading_user -d trading_system \
  -c "SELECT pg_last_wal_receive_lsn();"

kubectl exec -it postgres-replica-1 -n trading-system-prod -- \
  psql -U trading_user -d trading_system \
  -c "SELECT pg_last_wal_receive_lsn();"

# Choose the one with higher LSN (more recent data)

# 2. Promote chosen replica
kubectl exec -it postgres-replica-0 -n trading-system-prod -- bash

# Inside pod:
sudo -u postgres pg_ctl promote -D /var/lib/postgresql/data/pgdata

# Wait 30 seconds for promotion
sleep 30

# 3. Verify promotion
sudo -u postgres psql -c "SELECT pg_is_in_recovery();"
# Should return 'f'

# 4. Update application connection string
kubectl set env deployment/trading-system \
  DATABASE_URL="postgresql://trading_user:password@postgres-replica-0:5432/trading_system" \
  -n trading-system-prod

# 5. Restart trading application
kubectl rollout restart deployment/trading-system -n trading-system-prod

# 6. Watch application come up
kubectl get pods -n trading-system-prod -w
```

---

### Option 3: Restart Primary (If corruption suspected)

**⚠️ ONLY if replicas are unhealthy or data corruption suspected**

```bash
# 1. Try to restart primary pod
kubectl delete pod postgres-primary-0 -n trading-system-prod

# 2. Wait for pod to restart
kubectl get pods -n trading-system-prod -w

# 3. If pod comes up healthy:
kubectl exec -it postgres-primary-0 -n trading-system-prod -- \
  psql -U trading_user -d trading_system -c "SELECT version();"

# 4. Verify replication is working
kubectl exec -it postgres-primary-0 -n trading-system-prod -- \
  psql -U trading_user -d trading_system \
  -c "SELECT * FROM pg_stat_replication;"

# Should show 2 replicas connected
```

---

### Option 4: Restore from Backup (LAST RESORT)

**⚠️ ONLY if all replicas failed AND primary is unrecoverable**
**⚠️ This will result in data loss (up to 1 hour RPO)**

```bash
# 1. Stop all applications
kubectl scale deployment/trading-system --replicas=0 -n trading-system-prod

# 2. Follow Disaster Recovery procedure
# See: Documentation/DISASTER_RECOVERY.md#data-restoration

# 3. Estimate data loss
# Check timestamp of latest backup
# Calculate: (current time) - (backup time) = data loss window

# 4. Notify stakeholders immediately
# Send to: trading-ops@example.com, engineering-leads@example.com

# 5. Proceed with restoration
# (See DR documentation for detailed steps)
```

---

## Verification

### Check 1: Database Accepts Writes

```bash
kubectl exec -it <new-primary-pod> -n trading-system-prod -- \
  psql -U trading_user -d trading_system \
  -c "INSERT INTO health_check (timestamp, status) VALUES (NOW(), 'post-recovery-test');"

# Should succeed without errors
```

### Check 2: Application Connected

```bash
# Check trading system logs
kubectl logs trading-system-xxxxx -n trading-system-prod | grep -i "database"

# Should see: "Database connection established"
```

### Check 3: Trading Functional

```bash
# Check if orders can be placed
# Access dashboard: http://dashboard.example.com
# Try placing a test order in paper trading mode

# Verify in database:
kubectl exec -it <primary-pod> -n trading-system-prod -- \
  psql -U trading_user -d trading_system \
  -c "SELECT * FROM orders ORDER BY created_at DESC LIMIT 5;"
```

### Check 4: Monitoring Dashboards

- Grafana: http://grafana.example.com
  - Check "Database Health" dashboard
  - Verify no replication lag
  - Confirm query latency is normal (<100ms)

- Prometheus: http://prometheus.example.com
  - Alert should auto-resolve within 2 minutes
  - Verify `pg_up{job="postgres-primary"}` = 1

---

## Post-Resolution

### Immediate Actions (Within 1 hour)

1. **Notify Stakeholders**
   ```
   SUBJECT: [RESOLVED] Database Primary Failure

   The database primary failure has been resolved.
   - Downtime: X minutes
   - Method: [Automatic failover / Manual failover / Restart]
   - Data loss: [None / Minimal / X minutes]

   Normal trading operations have resumed.
   ```

2. **Document Timeline**
   - Create incident ticket in Jira
   - Document all commands executed
   - Note what worked and what didn't

3. **Monitor Closely**
   - Watch for 1 hour minimum
   - Check for anomalies
   - Verify all features working

### Follow-up Actions (Within 24 hours)

1. **Rebuild Failed Primary**
   ```bash
   # If old primary is still down, rebuild it as a replica
   kubectl delete pvc postgres-data-postgres-primary-0 -n trading-system-prod
   kubectl delete pod postgres-primary-0 -n trading-system-prod

   # Pod will restart and sync from new primary
   ```

2. **Investigate Root Cause**
   - Check system logs
   - Review resource usage before failure
   - Check for OOM kills
   - Verify disk space
   - Review recent changes

3. **Schedule Post-Mortem**
   - Within 72 hours
   - Include all responders
   - Document lessons learned
   - Create action items

### Long-term Actions (Within 1 week)

1. **Update Runbooks**
   - Document any new findings
   - Add missing steps
   - Update estimated times

2. **Implement Preventive Measures**
   - If memory issue: Increase memory limits
   - If disk issue: Increase disk size or add cleanup jobs
   - If bug: Update PostgreSQL version
   - If network: Review network policies

3. **Test Improvements**
   - Schedule DR drill
   - Verify automatic failover works
   - Test monitoring alerts

---

## Escalation

### Escalate to Database Admin if:
- Cannot promote replica after 3 attempts
- Data corruption detected
- All replicas are unhealthy
- Unsure about data integrity

**Contact:**
- DBA Team: dba@example.com
- On-Call DBA: [Phone number from PagerDuty]

### Escalate to Engineering Lead if:
- Downtime > 15 minutes
- Data loss > 1 hour
- Multiple recovery attempts failed

**Contact:**
- Engineering Lead: [Phone]
- VP Engineering: [Phone] (if Engineering Lead unavailable)

---

## Related Documentation

- [Disaster Recovery Plan](../DISASTER_RECOVERY.md)
- [PostgreSQL HA Architecture](../architecture/HA_ARCHITECTURE.md)
- [Alert Escalation Policy](../ALERT_ESCALATION_POLICY.md)

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Nov 2025 | SRE Team | Initial version |
| 1.1 | Nov 2025 | DBA Team | Added verification steps |

---

**Last Tested:** October 2025
**Test Result:** ✅ Success (RTO: 3 minutes)
**Next Test:** January 2026
