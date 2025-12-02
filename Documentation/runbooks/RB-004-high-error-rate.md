# RB-004: High API Error Rate

**Severity:** P1 - Critical
**Estimated Time:** 15 minutes
**Skills Required:** System Administration, Application Debugging
**Alert:** `HighErrorRate`

---

## Symptoms

- HTTP 5xx error rate > 1%
- Dashboard unresponsive or showing errors
- Users reporting "Internal Server Error"
- Prometheus alert: `HighErrorRate`
- Logs showing frequent exceptions

**Impact:** Degraded user experience, potential trading disruptions

---

## Prerequisites

- kubectl access to trading-system-prod namespace
- Access to Grafana dashboards
- Access to Kibana logs
- Understanding of application architecture

---

## Diagnosis

### Step 1: Identify Error Type

```bash
# Check recent error logs
kubectl logs -l app=trading-system -n trading-system-prod --tail=100 | grep -i error

# Common error patterns to look for:
# - Database connection errors
# - Redis connection errors
# - External API (Zerodha) errors
# - Out of memory errors
# - Timeout errors
```

### Step 2: Check Error Distribution

Access Grafana:  http://grafana.example.com

**Dashboard: Performance Metrics**
- Look at "HTTP Status Codes" panel
- Check which endpoints have errors
- Verify if errors are widespread or specific to one endpoint

### Step 3: Check System Resources

```bash
# Check pod resource usage
kubectl top pods -n trading-system-prod

# Look for:
# - Memory usage > 80%
# - CPU usage > 90%
# - Pods being OOM killed
```

### Step 4: Check Dependencies

```bash
# Database connectivity
kubectl exec -it postgres-primary-0 -n trading-system-prod -- \
  psql -U trading_user -d trading_system -c "SELECT 1;"

# Redis connectivity
kubectl exec -it redis-master-0 -n trading-system-prod -- redis-cli PING

# External API status
curl -v https://api.kite.trade/  # or check status page
```

### Step 5: Check Recent Changes

```bash
# Check recent deployments
kubectl rollout history deployment/trading-system -n trading-system-prod

# Check recent configuration changes
kubectl get events -n trading-system-prod --sort-by='.lastTimestamp' | head -20
```

---

## Resolution

### Scenario 1: Database Connection Errors

**Symptoms in logs:**
```
psycopg2.OperationalError: could not connect to server
Connection pool exhausted
```

**Resolution:**
```bash
# Check database health
kubectl exec -it postgres-primary-0 -n trading-system-prod -- \
  psql -U trading_user -d trading_system \
  -c "SELECT count(*) FROM pg_stat_activity;"

# If connection pool exhausted:
kubectl exec -it postgres-primary-0 -n trading-system-prod -- \
  psql -U trading_user -d trading_system \
  -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Kill idle connections if needed
kubectl exec -it postgres-primary-0 -n trading-system-prod -- \
  psql -U trading_user -d trading_system \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND query_start < now() - interval '5 minutes';"

# Restart application to reset connection pool
kubectl rollout restart deployment/trading-system -n trading-system-prod
```

---

### Scenario 2: Redis Connection Errors

**Symptoms in logs:**
```
redis.exceptions.ConnectionError: Error connecting to Redis
Could not connect to Redis
```

**Resolution:**
```bash
# Check Redis health
kubectl exec -it redis-master-0 -n trading-system-prod -- redis-cli INFO

# Check for memory issues
kubectl exec -it redis-master-0 -n trading-system-prod -- \
  redis-cli INFO memory | grep used_memory_human

# If Redis is down, check sentinel status
kubectl exec -it redis-sentinel-0 -n trading-system-prod -- \
  redis-cli -p 26379 SENTINEL master mymaster

# Force reconnect by restarting trading system
kubectl rollout restart deployment/trading-system -n trading-system-prod
```

---

### Scenario 3: External API (Zerodha) Errors

**Symptoms in logs:**
```
requests.exceptions.Timeout
HTTPError: 429 Too Many Requests
HTTPError: 503 Service Unavailable
```

**Resolution:**
```bash
# Check Zerodha API status
curl -I https://api.kite.trade/

# Check rate limiter status
kubectl logs -l app=trading-system -n trading-system-prod | grep "rate limit"

# If rate limited:
# 1. Verify rate limiter configuration
# 2. Check if requests are being properly throttled
# 3. Temporarily reduce trading frequency if needed

# Enable circuit breaker if not already enabled
kubectl set env deployment/trading-system \
  CIRCUIT_BREAKER_ENABLED=true \
  -n trading-system-prod

# Monitor recovery
kubectl logs -f trading-system-xxxxx -n trading-system-prod | grep -i "circuit"
```

---

### Scenario 4: Out of Memory (OOM)

**Symptoms:**
- Pods restarting frequently
- kubectl describe pod shows "OOMKilled"
- Memory usage at 100% before crash

**Resolution:**
```bash
# Check memory limits
kubectl describe deployment trading-system -n trading-system-prod | grep -A 5 "Limits"

# Increase memory limits
kubectl set resources deployment/trading-system \
  --limits=memory=3Gi \
  --requests=memory=1Gi \
  -n trading-system-prod

# Monitor memory usage
kubectl top pods -l app=trading-system -n trading-system-prod -w

# If memory leak suspected:
# 1. Check for growing caches
# 2. Review recent code changes
# 3. Restart pods as temporary fix
kubectl rollout restart deployment/trading-system -n trading-system-prod
```

---

### Scenario 5: Recent Bad Deployment

**Symptoms:**
- Errors started immediately after deployment
- Specific feature/endpoint failing
- New code recently deployed

**Resolution:**
```bash
# Check deployment history
kubectl rollout history deployment/trading-system -n trading-system-prod

# Rollback to previous version
kubectl rollout undo deployment/trading-system -n trading-system-prod

# Or rollback to specific revision
kubectl rollout undo deployment/trading-system --to-revision=5 -n trading-system-prod

# Watch rollback progress
kubectl rollout status deployment/trading-system -n trading-system-prod

# Verify errors stopped
# Check Grafana dashboard for error rate
```

---

### Scenario 6: Timeout Errors

**Symptoms in logs:**
```
ReadTimeout: request timed out
Operation timed out after 30000 milliseconds
```

**Resolution:**
```bash
# Check application timeout settings
kubectl get configmap trading-system-config -n trading-system-prod -o yaml

# Increase timeout temporarily
kubectl edit configmap trading-system-config -n trading-system-prod
# Update timeout values

# Restart to apply changes
kubectl rollout restart deployment/trading-system -n trading-system-prod

# Identify slow operations
kubectl logs -l app=trading-system -n trading-system-prod | grep -i "slow"

# Check database query performance
kubectl exec -it postgres-primary-0 -n trading-system-prod -- \
  psql -U trading_user -d trading_system \
  -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"
```

---

## Quick Fixes (Try First)

### Fix 1: Restart Application

```bash
# Simple restart often fixes transient issues
kubectl rollout restart deployment/trading-system -n trading-system-prod

# Wait for rollout to complete
kubectl rollout status deployment/trading-system -n trading-system-prod

# Verify error rate decreased
# Check Grafana after 2-3 minutes
```

### Fix 2: Clear Caches

```bash
# Clear Redis cache
kubectl exec -it redis-master-0 -n trading-system-prod -- redis-cli FLUSHDB

# Note: This will clear all cached data
# Application will repopulate cache from database
```

### Fix 3: Scale Up

```bash
# Temporarily increase replicas
kubectl scale deployment/trading-system --replicas=5 -n trading-system-prod

# Distribute load across more pods
# Monitor if errors decrease
```

---

## Verification

### Check 1: Error Rate Decreased

```bash
# Via Prometheus
curl 'http://prometheus.example.com/api/v1/query?query=rate(http_requests_total{status=~"5.."}[5m])'

# Should be < 0.01 (1%)
```

### Check 2: Application Health

```bash
# Check health endpoint
kubectl exec -it trading-system-xxxxx -n trading-system-prod -- \
  curl -f http://localhost:8000/health

# Should return HTTP 200 with status: "healthy"
```

### Check 3: User Experience

- Access dashboard: http://dashboard.example.com
- Navigate through key features
- Try placing test order (paper trading)
- Verify no errors displayed

### Check 4: Monitoring Dashboards

- Grafana: Error rate should be < 0.1%
- No active critical alerts
- Response times normal (p95 < 500ms)

---

## Post-Resolution

### Immediate (Within 30 minutes)

1. **Notify Team**
   ```
   Error rate has returned to normal.
   Root cause: [identified cause]
   Fix applied: [what was done]
   Monitoring for next hour.
   ```

2. **Continue Monitoring**
   - Watch error rate for 1 hour
   - Check for any recurring patterns
   - Verify all dependencies healthy

3. **Document**
   - Create incident ticket
   - Note exact error messages
   - Document fix that worked

### Follow-up (Within 24 hours)

1. **Root Cause Analysis**
   - Why did errors start?
   - What was the trigger?
   - Could it have been prevented?

2. **Permanent Fix**
   - If temporary fix applied, plan permanent solution
   - Update configuration
   - Code fix if needed

3. **Update Monitoring**
   - Add alerts for root cause
   - Improve error detection
   - Update dashboards

### Long-term (Within 1 week)

1. **Improve Resilience**
   - Add retry logic if missing
   - Implement circuit breakers
   - Improve error handling

2. **Update Documentation**
   - Update this runbook with findings
   - Add new error patterns discovered
   - Document preventive measures

---

## Prevention

### Best Practices

1. **Always deploy to staging first**
2. **Monitor error rates during deployment**
3. **Have rollback plan ready**
4. **Implement gradual rollouts (canary/blue-green)**
5. **Maintain comprehensive logging**
6. **Regular load testing**

### Monitoring Improvements

```yaml
# Add more specific alerts
- alert: APIErrorRateHigh
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01
  for: 2m
  labels:
    severity: warning

- alert: APIErrorRateCritical
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
  for: 1m
  labels:
    severity: critical
```

---

## Escalation

### Escalate to Senior SRE if:
- Error rate not improving after 15 minutes
- Multiple resolution attempts failed
- Root cause unclear
- Data integrity concerns

**Contact:** senior-sre@example.com, [Phone]

### Escalate to Engineering Lead if:
- Suspected code bug
- Need emergency code fix
- Rollback not possible

**Contact:** eng-lead@example.com, [Phone]

---

## Related Runbooks

- [RB-001: Database Primary Down](./RB-001-database-primary-down.md)
- [RB-003: Redis Master Down](./RB-003-redis-master-down.md)
- [RB-010: High Latency](./RB-010-high-latency.md)
- [RB-030: Deploy New Version](./RB-030-deploy-new-version.md)

---

## Appendix: Common Error Messages

| Error Message | Likely Cause | Quick Fix |
|--------------|--------------|-----------|
| `psycopg2.OperationalError` | Database connection issue | Check database, restart app |
| `redis.exceptions.ConnectionError` | Redis connection issue | Check Redis, restart app |
| `requests.exceptions.Timeout` | External API slow/down | Check API status, increase timeout |
| `OOMKilled` | Out of memory | Increase memory limits |
| `429 Too Many Requests` | Rate limit exceeded | Check rate limiter |
| `Connection refused` | Service not listening | Check service status |

---

**Last Tested:** October 2025
**Test Result:** ✅ Success
**Next Review:** December 2025
