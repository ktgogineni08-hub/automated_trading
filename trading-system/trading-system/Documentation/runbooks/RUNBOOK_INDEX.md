# Trading System Runbooks

**Operational Runbooks for Troubleshooting and Maintenance**

Version: 1.0
Last Updated: November 2025

---

## Purpose

This directory contains operational runbooks for common scenarios, troubleshooting procedures, and maintenance tasks for the Trading System.

## How to Use Runbooks

1. **Identify the Issue:** Use alerts, logs, or user reports
2. **Find the Appropriate Runbook:** Use the index below
3. **Follow Steps Sequentially:** Don't skip steps
4. **Document Actions:** Note what you tried and results
5. **Escalate if Needed:** Don't hesitate to escalate

---

## Runbook Categories

### 🔴 Critical Issues (P1)

| Runbook | Scenario | Est. Time |
|---------|----------|-----------|
| [RB-001: Database Primary Down](./RB-001-database-primary-down.md) | PostgreSQL primary failure | 5 min |
| [RB-002: All Pods Down](./RB-002-all-pods-down.md) | Complete application outage | 10 min |
| [RB-003: Redis Master Down](./RB-003-redis-master-down.md) | Redis master failure | 3 min |
| [RB-004: High Error Rate](./RB-004-high-error-rate.md) | API error rate > 5% | 15 min |
| [RB-005: Trading Halted](./RB-005-trading-halted.md) | No orders executing | 20 min |

### 🟠 High Priority Issues (P2)

| Runbook | Scenario | Est. Time |
|---------|----------|-----------|
| [RB-010: High Latency](./RB-010-high-latency.md) | Response time > 1s | 15 min |
| [RB-011: Database Connection Pool Exhausted](./RB-011-db-pool-exhausted.md) | Connection errors | 10 min |
| [RB-012: High Memory Usage](./RB-012-high-memory-usage.md) | Memory > 85% | 15 min |
| [RB-013: Disk Space Critical](./RB-013-disk-space-critical.md) | Disk > 90% | 10 min |
| [RB-014: Replication Lag High](./RB-014-replication-lag.md) | Lag > 5 minutes | 20 min |

### 🟡 Warning Issues (P3)

| Runbook | Scenario | Est. Time |
|---------|----------|-----------|
| [RB-020: Cache Hit Rate Low](./RB-020-cache-hit-rate-low.md) | Cache < 70% | 30 min |
| [RB-021: Slow Queries](./RB-021-slow-queries.md) | Query time > 1s | 30 min |
| [RB-022: Pod Restart Loop](./RB-022-pod-restart-loop.md) | Pods restarting frequently | 20 min |
| [RB-023: Certificate Expiring](./RB-023-cert-expiring.md) | Cert expires < 30 days | 15 min |

### 🔧 Maintenance Tasks

| Runbook | Task | Est. Time |
|---------|------|-----------|
| [RB-030: Deploy New Version](./RB-030-deploy-new-version.md) | Application deployment | 30 min |
| [RB-031: Database Backup Restore](./RB-031-db-backup-restore.md) | Restore from backup | 45 min |
| [RB-032: Scale Application](./RB-032-scale-application.md) | Increase/decrease replicas | 10 min |
| [RB-033: Rotate Secrets](./RB-033-rotate-secrets.md) | Update API keys/passwords | 20 min |
| [RB-034: Update Configuration](./RB-034-update-configuration.md) | Change config values | 15 min |

### 🛡️ Security Incidents

| Runbook | Scenario | Est. Time |
|---------|----------|-----------|
| [RB-040: Unauthorized Access Detected](./RB-040-unauthorized-access.md) | Security alert | 30 min |
| [RB-041: API Key Compromised](./RB-041-api-key-compromised.md) | Rotate compromised credentials | 15 min |
| [RB-042: DDoS Attack](./RB-042-ddos-attack.md) | Abnormal traffic | 30 min |

### 📊 Performance Optimization

| Runbook | Task | Est. Time |
|---------|------|-----------|
| [RB-050: Optimize Database Queries](./RB-050-optimize-queries.md) | Query performance tuning | 1 hour |
| [RB-051: Clear Cache](./RB-051-clear-cache.md) | Redis cache management | 5 min |
| [RB-052: Analyze Slow Endpoints](./RB-052-slow-endpoints.md) | API performance analysis | 45 min |

---

## Quick Reference

### Common Commands

```bash
# Check pod status
kubectl get pods -n trading-system-prod

# View logs
kubectl logs -f trading-system-xxx -n trading-system-prod

# Check database status
kubectl exec -it postgres-primary-0 -n trading-system-prod -- \
  psql -U trading_user -d trading_system -c "SELECT version();"

# Check Redis status
kubectl exec -it redis-master-0 -n trading-system-prod -- redis-cli INFO

# Restart application
kubectl rollout restart deployment/trading-system -n trading-system-prod

# Scale application
kubectl scale deployment/trading-system --replicas=5 -n trading-system-prod
```

### Useful Links

- [Grafana Dashboards](http://grafana.example.com)
- [Prometheus](http://prometheus.example.com)
- [Kibana Logs](http://kibana.example.com)
- [Alert Manager](http://alertmanager.example.com)
- [PagerDuty](https://yourcompany.pagerduty.com)

---

## Runbook Template

When creating new runbooks, use this structure:

```markdown
# RB-XXX: Title

**Severity:** P1/P2/P3
**Estimated Time:** X minutes
**Skills Required:** [System Admin / Database / Security]

## Symptoms

- List observable symptoms
- Include relevant alerts
- Metrics that trigger this

## Prerequisites

- Required access/permissions
- Tools needed
- Before you begin checks

## Diagnosis

Step-by-step investigation:

1. Check X
2. Verify Y
3. Analyze Z

## Resolution

### Option 1: Quick Fix (Preferred)

1. Step 1
2. Step 2
3. Verification

### Option 2: Alternative Fix

(If Option 1 doesn't work)

## Verification

- How to verify the fix worked
- What to monitor
- Success criteria

## Post-Resolution

- Follow-up actions
- Documentation updates
- Root cause analysis

## Escalation

Escalate to [Role] if:
- Condition 1
- Condition 2

Contact: [email/phone]
```

---

## Contributing

To add or update runbooks:

1. Follow the template structure
2. Test the runbook in staging
3. Get peer review
4. Update this index
5. Notify the team

---

**Document Owner:** SRE Team
**Review Frequency:** Monthly
**Last Review:** November 2025
