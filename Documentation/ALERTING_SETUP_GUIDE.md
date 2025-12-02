# Alerting Setup Guide - PagerDuty & Opsgenie Integration

**Version:** 1.0
**Date:** November 2025
**Audience:** SRE Team, DevOps Engineers

---

## Overview

This guide provides step-by-step instructions to configure PagerDuty and Opsgenie integrations with the trading system's Alertmanager for incident management and on-call alerting.

---

## Prerequisites

Before starting, ensure you have:

- [ ] Admin access to PagerDuty account
- [ ] Admin access to Opsgenie account
- [ ] kubectl access to trading-system cluster
- [ ] Alertmanager deployed and running
- [ ] Prometheus exporting metrics

---

## Part 1: PagerDuty Setup

### Step 1: Create PagerDuty Service

1. **Log in to PagerDuty**
   - Navigate to: https://yourcompany.pagerduty.com
   - Go to **Services** → **Service Directory**

2. **Create New Service**
   - Click **+ New Service**
   - Service Name: `Trading System - Critical`
   - Description: `Critical alerts from trading system (P1 severity)`
   - Escalation Policy: Select or create (see below)
   - Click **Create Service**

3. **Get Integration Key**
   - In the new service, go to **Integrations** tab
   - Click **+ Add Integration**
   - Select **Events API v2**
   - Integration Name: `Alertmanager Critical`
   - Click **Add Integration**
   - **Copy the Integration Key** (starts with `R0xxxxx`)
   - Save this key securely - you'll need it later

4. **Create Additional Services**
   - Repeat for other severity levels:
     - `Trading System - High` (P2 alerts)
     - `Trading System - Medium` (P3 alerts)
   - Get integration keys for each

### Step 2: Configure PagerDuty Escalation Policy

1. **Create Escalation Policy**
   - Go to **People** → **Escalation Policies**
   - Click **+ New Escalation Policy**
   - Name: `Trading System On-Call`

2. **Define Escalation Levels**

   **Level 1: Primary On-Call (0 minutes)**
   - Add user or schedule
   - If no response: escalate after **15 minutes**

   **Level 2: Secondary On-Call (15 minutes)**
   - Add backup engineer
   - If no response: escalate after **15 minutes** (total 30 min)

   **Level 3: Team Lead (30 minutes)**
   - Add team lead or manager
   - If no response: escalate after **30 minutes** (total 60 min)

   **Level 4: Executive (60 minutes)**
   - Add CTO or VP Engineering
   - Final escalation point

3. **Configure Notification Rules**
   - Push notification: **Immediately**
   - SMS: **After 3 minutes**
   - Phone call: **After 5 minutes**

### Step 3: Create PagerDuty Schedule

1. **Create On-Call Schedule**
   - Go to **People** → **On-Call Schedules**
   - Click **+ New On-Call Schedule**
   - Name: `Trading System Primary`

2. **Configure Schedule**
   - Time Zone: `Asia/Kolkata`
   - Rotation Type: `Weekly`
   - Start Date: Next Monday
   - Handoff Time: 09:00 (market open time)

3. **Add Team Members**
   - Add 3-4 engineers to rotation
   - Preview schedule for next 4 weeks
   - Save schedule

4. **Link to Escalation Policy**
   - Edit escalation policy
   - Set Level 1 to use the new schedule

### Step 4: Test PagerDuty Integration

```bash
# Test using PagerDuty API
curl -X POST https://events.pagerduty.com/v2/enqueue \
  -H 'Content-Type: application/json' \
  -d '{
    "routing_key": "YOUR_INTEGRATION_KEY",
    "event_action": "trigger",
    "payload": {
      "summary": "Test Alert from Trading System",
      "severity": "critical",
      "source": "trading-system-test",
      "custom_details": {
        "alert": "This is a test alert",
        "environment": "staging"
      }
    }
  }'
```

**Expected Result:**
- Incident created in PagerDuty
- On-call engineer receives notification
- Incident shows in web UI and mobile app

---

## Part 2: Opsgenie Setup

### Step 1: Create Opsgenie Team

1. **Log in to Opsgenie**
   - Navigate to: https://yourcompany.app.opsgenie.com
   - Go to **Teams** in left sidebar

2. **Create New Team**
   - Click **Add Team**
   - Team Name: `Trading System SRE`
   - Description: `SRE team for trading system operations`
   - Add team members (5-10 engineers)
   - Save

### Step 2: Create Opsgenie Integration

1. **Navigate to Integrations**
   - Select **Trading System SRE** team
   - Go to **Integrations** tab
   - Click **Add Integration**

2. **Configure Prometheus Integration**
   - Search for `Prometheus`
   - Select **Prometheus** integration
   - Name: `Trading System Alertmanager`
   - Assigned Team: `Trading System SRE`
   - Click **Save Integration**

3. **Get API Key**
   - After creation, Opsgenie shows the API key
   - **Copy the API Key** (format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
   - Save securely

### Step 3: Configure Opsgenie Escalation

1. **Create Escalation Policy**
   - Go to team settings
   - Click **Escalations** → **Add Escalation**
   - Name: `Trading System Critical`

2. **Define Escalation Steps**

   **Step 1: Notify On-Call (0 minutes)**
   - Notify: On-call schedule
   - If not acked: proceed after **10 minutes**

   **Step 2: Notify Team Lead (10 minutes)**
   - Notify: Team lead
   - If not acked: proceed after **15 minutes**

   **Step 3: Notify All Team (25 minutes)**
   - Notify: All team members
   - If not acked: proceed after **20 minutes**

   **Step 4: Notify Executives (45 minutes)**
   - Notify: CTO, VP Engineering
   - Final escalation

3. **Save Escalation Policy**

### Step 4: Create On-Call Schedule

1. **Add Schedule**
   - Go to **On-Call** → **Schedules**
   - Click **Add Schedule**
   - Name: `Trading System Primary On-Call`

2. **Configure Rotation**
   - Timezone: `Asia/Kolkata (IST)`
   - Rotation Type: `Weekly`
   - Rotation starts: Next Monday at 09:00
   - Rotation length: 1 week

3. **Add Participants**
   - Add 3-4 team members
   - Set rotation order
   - Preview schedule

4. **Add Restrictions (Optional)**
   - Add override for holidays
   - Add restrictions for weekends (if needed)

### Step 5: Test Opsgenie Integration

```bash
# Test using Opsgenie API
curl -X POST https://api.opsgenie.com/v2/alerts \
  -H "Authorization: GenieKey YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Test Alert from Trading System",
    "description": "This is a test alert to verify Opsgenie integration",
    "priority": "P1",
    "tags": ["trading-system", "test", "staging"],
    "entity": "trading-system-api",
    "source": "Alertmanager",
    "details": {
      "environment": "staging",
      "alert_type": "test"
    }
  }'
```

**Expected Result:**
- Alert created in Opsgenie
- On-call engineer notified via app/SMS/call
- Alert visible in Opsgenie console

---

## Part 3: Kubernetes Secrets Setup

### Step 1: Create Secrets

```bash
# Navigate to infrastructure directory
cd /Users/gogineni/Python/trading-system/infrastructure

# Create namespace if not exists
kubectl create namespace trading-system-staging --dry-run=client -o yaml | kubectl apply -f -

# Create secrets for alerting integrations
kubectl create secret generic alertmanager-secrets \
  --from-literal=PAGERDUTY_SERVICE_KEY_CRITICAL="R0xxxxx" \
  --from-literal=PAGERDUTY_ROUTING_KEY_HIGH="R0yyyyy" \
  --from-literal=PAGERDUTY_ROUTING_KEY_MEDIUM="R0zzzzz" \
  --from-literal=OPSGENIE_API_KEY="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" \
  --from-literal=SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL" \
  --from-literal=EMAIL_SMTP_PASSWORD="your-smtp-password" \
  -n trading-system-staging

# Verify secret created
kubectl get secret alertmanager-secrets -n trading-system-staging

# For production, repeat with production namespace
kubectl create secret generic alertmanager-secrets \
  --from-literal=PAGERDUTY_SERVICE_KEY_CRITICAL="R0xxxxx" \
  --from-literal=PAGERDUTY_ROUTING_KEY_HIGH="R0yyyyy" \
  --from-literal=PAGERDUTY_ROUTING_KEY_MEDIUM="R0zzzzz" \
  --from-literal=OPSGENIE_API_KEY="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" \
  --from-literal=SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL" \
  --from-literal=EMAIL_SMTP_PASSWORD="your-smtp-password" \
  -n trading-system-prod
```

### Step 2: Mount Secrets in Alertmanager

Edit Alertmanager deployment to mount secrets as environment variables:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: alertmanager
  namespace: trading-system-staging
spec:
  template:
    spec:
      containers:
      - name: alertmanager
        image: prom/alertmanager:v0.26.0
        env:
        - name: PAGERDUTY_SERVICE_KEY_CRITICAL
          valueFrom:
            secretKeyRef:
              name: alertmanager-secrets
              key: PAGERDUTY_SERVICE_KEY_CRITICAL
        - name: PAGERDUTY_ROUTING_KEY_HIGH
          valueFrom:
            secretKeyRef:
              name: alertmanager-secrets
              key: PAGERDUTY_ROUTING_KEY_HIGH
        - name: OPSGENIE_API_KEY
          valueFrom:
            secretKeyRef:
              name: alertmanager-secrets
              key: OPSGENIE_API_KEY
        - name: SLACK_WEBHOOK_URL
          valueFrom:
            secretKeyRef:
              name: alertmanager-secrets
              key: SLACK_WEBHOOK_URL
        volumeMounts:
        - name: config
          mountPath: /etc/alertmanager
        - name: templates
          mountPath: /etc/alertmanager/templates
      volumes:
      - name: config
        configMap:
          name: alertmanager-config
      - name: templates
        configMap:
          name: alertmanager-templates
```

Apply the deployment:

```bash
kubectl apply -f alertmanager-deployment.yaml -n trading-system-staging
```

---

## Part 4: Configure Alertmanager

### Step 1: Deploy Alertmanager Configuration

```bash
# Create ConfigMap from alertmanager.yml
kubectl create configmap alertmanager-config \
  --from-file=/Users/gogineni/Python/trading-system/infrastructure/prometheus/alertmanager.yml \
  -n trading-system-staging \
  --dry-run=client -o yaml | kubectl apply -f -

# Create ConfigMap for notification templates
kubectl create configmap alertmanager-templates \
  --from-file=/Users/gogineni/Python/trading-system/infrastructure/prometheus/templates/notifications.tmpl \
  -n trading-system-staging \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart Alertmanager to pick up new config
kubectl rollout restart deployment alertmanager -n trading-system-staging

# Wait for rollout to complete
kubectl rollout status deployment alertmanager -n trading-system-staging
```

### Step 2: Verify Configuration

```bash
# Check Alertmanager pods
kubectl get pods -l app=alertmanager -n trading-system-staging

# Check Alertmanager logs
kubectl logs -l app=alertmanager -n trading-system-staging --tail=50

# Check configuration loaded correctly
kubectl exec -it -n trading-system-staging \
  $(kubectl get pod -l app=alertmanager -n trading-system-staging -o jsonpath='{.items[0].metadata.name}') \
  -- amtool config show

# Check routing tree
kubectl exec -it -n trading-system-staging \
  $(kubectl get pod -l app=alertmanager -n trading-system-staging -o jsonpath='{.items[0].metadata.name}') \
  -- amtool config routes show
```

Expected output should show:
- Routes configured for critical, high, medium, low severity
- Receivers: pagerduty-critical, opsgenie-high, slack-all, email-team
- Group by: alertname, cluster, service

---

## Part 5: Testing End-to-End

### Test 1: Critical Alert to PagerDuty

```bash
# Send test critical alert
kubectl exec -it -n trading-system-staging \
  $(kubectl get pod -l app=prometheus -n trading-system-staging -o jsonpath='{.items[0].metadata.name}') \
  -- curl -X POST http://alertmanager:9093/api/v1/alerts -d '[
  {
    "labels": {
      "alertname": "TestCriticalAlert",
      "severity": "critical",
      "service": "trading-system",
      "cluster": "staging"
    },
    "annotations": {
      "summary": "Test critical alert for PagerDuty",
      "description": "This is a test of the critical alerting path"
    },
    "startsAt": "2025-11-01T12:00:00.000Z"
  }
]'
```

**Verify:**
- [ ] Incident created in PagerDuty
- [ ] On-call engineer receives push notification
- [ ] On-call engineer receives SMS (after 3 min)
- [ ] On-call engineer receives phone call (after 5 min)
- [ ] Slack notification sent
- [ ] Email notification sent

### Test 2: High Alert to Opsgenie

```bash
# Send test high alert
kubectl exec -it -n trading-system-staging \
  $(kubectl get pod -l app=prometheus -n trading-system-staging -o jsonpath='{.items[0].metadata.name}') \
  -- curl -X POST http://alertmanager:9093/api/v1/alerts -d '[
  {
    "labels": {
      "alertname": "TestHighAlert",
      "severity": "high",
      "service": "trading-system",
      "cluster": "staging"
    },
    "annotations": {
      "summary": "Test high alert for Opsgenie",
      "description": "This is a test of the high severity alerting path"
    },
    "startsAt": "2025-11-01T12:00:00.000Z"
  }
]'
```

**Verify:**
- [ ] Alert created in Opsgenie
- [ ] On-call engineer receives app notification
- [ ] Slack notification sent
- [ ] Email notification sent

### Test 3: Medium Alert to Slack

```bash
# Send test medium alert
kubectl exec -it -n trading-system-staging \
  $(kubectl get pod -l app=prometheus -n trading-system-staging -o jsonpath='{.items[0].metadata.name}') \
  -- curl -X POST http://alertmanager:9093/api/v1/alerts -d '[
  {
    "labels": {
      "alertname": "TestMediumAlert",
      "severity": "medium",
      "service": "trading-system",
      "cluster": "staging"
    },
    "annotations": {
      "summary": "Test medium alert for Slack",
      "description": "This is a test of the medium severity alerting path"
    },
    "startsAt": "2025-11-01T12:00:00.000Z"
  }
]'
```

**Verify:**
- [ ] Slack notification sent
- [ ] Email notification sent
- [ ] No PagerDuty/Opsgenie incident (medium alerts don't page)

### Test 4: Escalation Flow

```bash
# Send critical alert and DON'T acknowledge
# Wait to observe escalation

# After 15 minutes: Check escalation to Level 2
# After 30 minutes: Check escalation to Level 3
# After 60 minutes: Check escalation to Level 4
```

**Verify:**
- [ ] Level 1 notified immediately
- [ ] Level 2 notified after 15 minutes
- [ ] Level 3 notified after 30 minutes
- [ ] Level 4 notified after 60 minutes

---

## Part 6: Slack Integration

### Step 1: Create Slack Incoming Webhook

1. **Go to Slack API**
   - Navigate to: https://api.slack.com/apps
   - Click **Create New App** → **From scratch**
   - App Name: `Trading System Alerts`
   - Workspace: Select your workspace

2. **Enable Incoming Webhooks**
   - Click **Incoming Webhooks** in left sidebar
   - Toggle **Activate Incoming Webhooks** to ON
   - Click **Add New Webhook to Workspace**
   - Select channel: `#trading-alerts` (create if doesn't exist)
   - Click **Allow**

3. **Copy Webhook URL**
   - Webhook URL format: `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX`
   - Save this URL - you'll add it to Kubernetes secrets

4. **Update Kubernetes Secret**
   ```bash
   kubectl patch secret alertmanager-secrets \
     -n trading-system-staging \
     -p '{"data":{"SLACK_WEBHOOK_URL":"'$(echo -n 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL' | base64)'"}}'
   ```

### Step 2: Create Slack Channel

1. **Create Channel**
   - Channel name: `#trading-alerts`
   - Description: `Automated alerts from trading system`
   - Make it public or private (recommend private)

2. **Add Team Members**
   - Add all SRE team members
   - Add dev team leads
   - Add on-call engineers

3. **Pin Important Links**
   - Grafana dashboard URL
   - Runbook index
   - Escalation policy
   - PagerDuty on-call schedule

### Step 3: Test Slack Integration

```bash
# Test Slack webhook directly
curl -X POST "https://hooks.slack.com/services/YOUR/WEBHOOK/URL" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Test alert from Trading System",
    "attachments": [
      {
        "color": "danger",
        "fields": [
          {
            "title": "Alert",
            "value": "TestAlert",
            "short": true
          },
          {
            "title": "Severity",
            "value": "critical",
            "short": true
          }
        ]
      }
    ]
  }'
```

**Expected Result:**
- Message appears in #trading-alerts channel

---

## Part 7: Email Alerts Setup

### Step 1: Configure SMTP

Update Alertmanager configuration with SMTP settings:

```yaml
global:
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@trading-system.com'
  smtp_auth_username: 'alerts@trading-system.com'
  smtp_auth_password: '{{ env "EMAIL_SMTP_PASSWORD" }}'
  smtp_require_tls: true
```

### Step 2: Update Email Receiver

Verify email receiver in alertmanager.yml:

```yaml
receivers:
  - name: 'email-team'
    email_configs:
      - to: 'sre-team@trading-system.com'
        headers:
          Subject: '{{ template "email.subject" . }}'
        html: '{{ template "email.html" . }}'
```

### Step 3: Test Email Alerts

```bash
# Send test alert that routes to email
kubectl exec -it -n trading-system-staging \
  $(kubectl get pod -l app=prometheus -n trading-system-staging -o jsonpath='{.items[0].metadata.name}') \
  -- curl -X POST http://alertmanager:9093/api/v1/alerts -d '[
  {
    "labels": {
      "alertname": "TestEmailAlert",
      "severity": "low",
      "service": "trading-system"
    },
    "annotations": {
      "summary": "Test email alert",
      "description": "Testing email notification flow"
    }
  }
]'
```

**Verify:**
- [ ] Email received by SRE team
- [ ] Email formatting correct (uses template)
- [ ] Links in email work (Grafana, runbooks)

---

## Part 8: Monitoring Alerting Health

### Metrics to Monitor

```promql
# Alert firing rate
rate(alertmanager_alerts_received_total[5m])

# Notification success rate
rate(alertmanager_notifications_total{integration="pagerduty"}[5m])
rate(alertmanager_notifications_failed_total{integration="pagerduty"}[5m])

# Alert latency (time from firing to notification)
alertmanager_notification_latency_seconds

# Inhibition rule hits
alertmanager_inhibition_rules_applied_total
```

### Create Monitoring Dashboard

Add Grafana dashboard panels:

1. **Alert Firing Rate** - Line graph
2. **Notification Success Rate** - Gauge (target > 99%)
3. **Failed Notifications** - Counter
4. **Alert Latency** - Histogram (p50, p95, p99)
5. **Active Alerts by Severity** - Bar chart

---

## Troubleshooting

### Issue: PagerDuty Incidents Not Creating

**Symptoms:** Alerts firing but no PagerDuty incidents

**Debugging:**
```bash
# Check Alertmanager logs
kubectl logs -l app=alertmanager -n trading-system-staging | grep pagerduty

# Check secret is mounted
kubectl exec -it -n trading-system-staging \
  $(kubectl get pod -l app=alertmanager -n trading-system-staging -o jsonpath='{.items[0].metadata.name}') \
  -- env | grep PAGERDUTY

# Test PagerDuty API directly
curl -X POST https://events.pagerduty.com/v2/enqueue \
  -H 'Content-Type: application/json' \
  -d '{"routing_key": "YOUR_KEY", "event_action": "trigger", "payload": {"summary": "test", "severity": "critical", "source": "test"}}'
```

**Common Fixes:**
- Verify integration key is correct
- Check PagerDuty service is not disabled
- Verify network connectivity from cluster to PagerDuty API

### Issue: Opsgenie Alerts Not Appearing

**Debugging:**
```bash
# Check Alertmanager logs
kubectl logs -l app=alertmanager -n trading-system-staging | grep opsgenie

# Test Opsgenie API
curl -X POST https://api.opsgenie.com/v2/alerts \
  -H "Authorization: GenieKey YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}'
```

**Common Fixes:**
- Verify API key is correct
- Check Opsgenie integration is enabled
- Verify team has permissions

### Issue: Slack Messages Not Posting

**Debugging:**
```bash
# Test webhook directly
curl -X POST "YOUR_SLACK_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"text": "test"}'
```

**Common Fixes:**
- Verify webhook URL is correct
- Check Slack app is installed in workspace
- Verify channel exists and bot has access

### Issue: Email Not Sending

**Debugging:**
```bash
# Check SMTP configuration
kubectl exec -it -n trading-system-staging \
  $(kubectl get pod -l app=alertmanager -n trading-system-staging -o jsonpath='{.items[0].metadata.name}') \
  -- amtool config show | grep smtp

# Check for SMTP errors in logs
kubectl logs -l app=alertmanager -n trading-system-staging | grep -i smtp
```

**Common Fixes:**
- Verify SMTP credentials
- Check SMTP server allows connections from cluster IPs
- Verify email addresses are correct
- Check spam/junk folders

---

## Maintenance

### Rotating API Keys

When rotating PagerDuty or Opsgenie API keys:

```bash
# 1. Generate new key in PagerDuty/Opsgenie UI

# 2. Update Kubernetes secret
kubectl patch secret alertmanager-secrets \
  -n trading-system-prod \
  -p '{"data":{"PAGERDUTY_SERVICE_KEY_CRITICAL":"'$(echo -n 'NEW_KEY' | base64)'"}}'

# 3. Restart Alertmanager
kubectl rollout restart deployment alertmanager -n trading-system-prod

# 4. Test with new key
# Send test alert and verify it works

# 5. Deactivate old key in PagerDuty/Opsgenie
```

### Updating On-Call Schedule

**PagerDuty:**
1. Go to On-Call Schedules
2. Edit schedule
3. Add/remove engineers or change rotation

**Opsgenie:**
1. Go to team On-Call page
2. Edit schedule
3. Modify rotation or participants

### Tuning Alert Thresholds

After initial deployment, monitor for:
- False positives (alerts that aren't actionable)
- False negatives (real issues not alerting)

Adjust thresholds in `alert_rules.yml`:

```yaml
# Before (too sensitive)
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01

# After (tuned)
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
  for: 3m  # Wait 3 minutes before firing
```

---

## Best Practices

1. **Alert Fatigue Prevention**
   - Only page for actionable items
   - Use Slack/email for info-only alerts
   - Group related alerts (30s grouping)
   - Set appropriate firing thresholds

2. **On-Call Rotation**
   - 1-week rotations (not too short, not too long)
   - Handoff during business hours
   - Document on-call responsibilities
   - Provide compensation (time off or pay)

3. **Escalation Policy**
   - Balance between rapid escalation and alert fatigue
   - 15 minutes for L1 → L2 is reasonable
   - Always have executive escalation as last resort
   - Test escalation flow quarterly

4. **Testing**
   - Test alerting weekly with low-severity test alerts
   - Full escalation drill quarterly
   - Document test results
   - Update runbooks based on learnings

5. **Documentation**
   - Keep runbooks up to date
   - Document all alert types
   - Link alerts to runbooks
   - Record resolution patterns

---

## Success Criteria

After completing this setup, verify:

- [x] PagerDuty incidents created for critical alerts
- [x] Opsgenie alerts created for high severity
- [x] Slack messages posted for all alerts
- [x] Email sent to SRE team
- [x] Escalation policy working correctly
- [x] On-call schedule populated
- [x] Test alerts successful
- [x] Monitoring dashboard showing alerting metrics
- [x] Team trained on alert handling
- [x] Runbooks linked in alert descriptions

---

## Appendix

### A. Alerting Severity Matrix

| Severity | Response Time | Notification | Escalation | Examples |
|----------|---------------|--------------|------------|----------|
| **Critical** | 5 minutes | PagerDuty + Slack + Email | Yes (15min) | System down, data loss |
| **High** | 15 minutes | Opsgenie + Slack + Email | Yes (30min) | High error rate, degraded performance |
| **Medium** | 30 minutes | Slack + Email | No | Elevated latency, cache miss rate |
| **Low** | 1 hour | Email only | No | Disk space warning, non-critical errors |
| **Info** | N/A | Slack only | No | Deployment notifications, backups complete |

### B. Contact Information

| Role | PagerDuty | Opsgenie | Email | Phone |
|------|-----------|----------|-------|-------|
| SRE Team Lead | Primary | Primary | sre-lead@company.com | +91-xxx-xxx-xxxx |
| Senior SRE | Schedule | Schedule | sre-1@company.com | +91-xxx-xxx-xxxx |
| DevOps Engineer | Schedule | Schedule | devops@company.com | +91-xxx-xxx-xxxx |
| CTO | Escalation L4 | Escalation L4 | cto@company.com | +91-xxx-xxx-xxxx |

### C. Useful Commands

```bash
# List active alerts
kubectl exec -it -n trading-system-prod \
  $(kubectl get pod -l app=alertmanager -n trading-system-prod -o jsonpath='{.items[0].metadata.name}') \
  -- amtool alert query

# Silence an alert
kubectl exec -it -n trading-system-prod \
  $(kubectl get pod -l app=alertmanager -n trading-system-prod -o jsonpath='{.items[0].metadata.name}') \
  -- amtool silence add alertname=HighErrorRate

# List silences
kubectl exec -it -n trading-system-prod \
  $(kubectl get pod -l app=alertmanager -n trading-system-prod -o jsonpath='{.items[0].metadata.name}') \
  -- amtool silence query

# Expire a silence
kubectl exec -it -n trading-system-prod \
  $(kubectl get pod -l app=alertmanager -n trading-system-prod -o jsonpath='{.items[0].metadata.name}') \
  -- amtool silence expire SILENCE_ID
```

---

**Document Version:** 1.0
**Last Updated:** November 2025
**Next Review:** February 2026
**Owner:** SRE Team
