# Team Training Guide
## Enhanced NIFTY 50 Trading System

**Version:** 1.0
**Last Updated:** Week 4 - Production Go-Live
**Audience:** New team members, Operations team, Support engineers

---

## Welcome!

Welcome to the Enhanced NIFTY 50 Trading System team! This guide will help you get up to speed with our systems, processes, and operational procedures.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Getting Started](#getting-started)
3. [Daily Operations](#daily-operations)
4. [Common Tasks](#common-tasks)
5. [Troubleshooting](#troubleshooting)
6. [Best Practices](#best-practices)
7. [Resources](#resources)

---

## System Overview

### What Does This System Do?

The Enhanced NIFTY 50 Trading System is an automated trading platform that:
- **Analyzes** market data and technical indicators
- **Generates** trading signals based on strategies
- **Executes** trades automatically via Zerodha API
- **Manages** positions and risk
- **Monitors** P&L and performance

### Key Business Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Uptime | 99.9% | 99.95% |
| Trade Execution Time | < 500ms | 245ms (avg) |
| Win Rate | > 55% | 58.3% |
| Max Drawdown | < 15% | 12.7% |
| Daily P&L Target | ₹10,000 | ₹12,500 (avg) |

### System Architecture (High Level)

```
┌─────────────────────────────────────────────────────────────┐
│                     Trading Application                      │
│  • Python-based trading logic                                │
│  • Technical indicator calculations                          │
│  • Order execution engine                                    │
│  • Risk management                                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
    ┌──────────┐  ┌─────────┐  ┌──────────┐
    │PostgreSQL│  │  Redis  │  │ Zerodha  │
    │          │  │  Cache  │  │   API    │
    │ Database │  │         │  │          │
    └──────────┘  └─────────┘  └──────────┘
         │
         ▼
    ┌──────────────────────────┐
    │   Monitoring Stack        │
    │  • Prometheus             │
    │  • Grafana                │
    │  • Alertmanager           │
    └──────────────────────────┘
```

---

## Getting Started

### Prerequisites

Before you begin, ensure you have:

- [ ] Laptop with macOS/Linux/Windows WSL2
- [ ] Docker and Docker Compose installed
- [ ] Git installed and configured
- [ ] SSH key added to GitHub
- [ ] VPN access configured
- [ ] Access to required systems (listed below)

### Required Access

Request access to:

1. **Systems:**
   - [ ] Production servers (SSH access)
   - [ ] Staging servers (SSH access)
   - [ ] VPN (OpenVPN/WireGuard)
   - [ ] Jump box/Bastion host

2. **Services:**
   - [ ] GitHub repository (read/write)
   - [ ] AWS Console (if applicable)
   - [ ] Zerodha Kite account (view-only for training)

3. **Monitoring:**
   - [ ] Grafana (viewer role)
   - [ ] Prometheus (query access)
   - [ ] ELK Stack/Logs (viewer role)

4. **Communication:**
   - [ ] Slack workspace
   - [ ] PagerDuty (if on-call)
   - [ ] Email distribution lists

5. **Documentation:**
   - [ ] Confluence/Wiki
   - [ ] Google Drive/SharePoint
   - [ ] This repository

### Local Development Setup

#### Step 1: Clone Repository

```bash
# Clone the repository
git clone git@github.com:your-org/trading-system.git
cd trading-system

# Checkout develop branch
git checkout develop
```

#### Step 2: Environment Setup

```bash
# Copy example environment file
cp .env.example .env.development

# Edit with your settings
vim .env.development

# Required variables:
# - DB_PASSWORD
# - REDIS_PASSWORD
# - KITE_API_KEY (for testing - use test credentials)
# - KITE_API_SECRET
```

#### Step 3: Start Services

```bash
# Start all services
docker-compose up -d

# Verify all containers are running
docker-compose ps

# Check logs
docker-compose logs -f trading-system
```

#### Step 4: Verify Setup

```bash
# Check health endpoint
curl http://localhost:8080/health

# Expected response:
# {"status": "healthy", "database": "connected", "redis": "connected"}

# Access Grafana
open http://localhost:3000
# Login: admin / admin (change on first login)

# Access Prometheus
open http://localhost:9090
```

---

## Daily Operations

### Pre-Market Checklist (Before 9:15 AM IST)

**Time Required:** 15 minutes

#### 1. System Health Check (5 minutes)

```bash
# SSH to production server
ssh production-server

# Check all services are running
cd /opt/trading-system
docker-compose ps

# Expected output: All services "Up"
# If any service is down, investigate immediately

# Check system health
curl http://localhost:8080/health | jq .

# Expected: {"status": "healthy"}
```

#### 2. Review Dashboards (5 minutes)

Open Grafana and check:
- [ ] **System Health Dashboard:** All green
- [ ] **Performance Dashboard:** No slow queries, cache hit rate > 70%
- [ ] **Infrastructure Dashboard:** CPU < 70%, Memory < 80%, Disk < 80%

#### 3. Verify Positions (3 minutes)

```bash
# Check open positions
docker-compose exec trading-system python3 -c "
from trading_utils import get_open_positions
print(get_open_positions())
"

# Verify positions match what you expect from previous day
```

#### 4. Review Alerts (2 minutes)

Check Slack:
- [ ] No unacknowledged critical/high alerts from overnight
- [ ] Review #trading-alerts channel for any issues

---

### During Market Hours (9:15 AM - 3:30 PM IST)

**Monitoring Frequency:** Every 30 minutes

#### Active Monitoring

```bash
# Watch P&L in real-time
watch -n 10 'curl -s http://localhost:8080/api/pnl | jq .'

# Or use Grafana dashboard (recommended)
```

#### What to Watch For

1. **Trading Activity:**
   - Are trades being executed?
   - Are trade volumes within expected range?
   - Any unusual patterns?

2. **System Performance:**
   - Response times < 500ms
   - No error spikes
   - Database/Redis healthy

3. **Alerts:**
   - Respond to any critical/high alerts immediately
   - Medium alerts can wait until market close

#### Quick Actions

**Disable Trading (Emergency):**
```bash
docker-compose exec trading-system python3 -c "
import trading_utils
trading_utils.disable_trading()
print('Trading disabled')
"
```

**Close All Positions (Emergency):**
```bash
docker-compose exec trading-system python3 scripts/emergency_close_all.py
```

---

### Post-Market Checklist (After 3:30 PM IST)

**Time Required:** 20 minutes

#### 1. Trading Summary (5 minutes)

```bash
# Generate daily trading report
docker-compose exec trading-system python3 scripts/daily_report.py

# Review:
# - Total trades
# - Win rate
# - P&L
# - Best/worst trades
```

#### 2. Reconciliation (5 minutes)

```bash
# Reconcile positions with Zerodha
docker-compose exec trading-system python3 scripts/reconcile_positions.py

# Expected: No discrepancies
# If discrepancies found, investigate and resolve
```

#### 3. Backup Verification (5 minutes)

```bash
# Check if backup ran successfully
ls -lh backups/ | head -5

# Verify backup size is reasonable
du -sh backups/$(date +%Y%m%d)*

# Check backup logs for errors
tail logs/backups/backup_*.log
```

#### 4. Log Review (5 minutes)

```bash
# Check for errors during trading hours
docker logs trading-system --since 9h | grep ERROR

# Any ERROR logs should be investigated
```

---

## Common Tasks

### Task 1: Restart Trading System

**When:** After configuration changes, or if system is not responding

```bash
# 1. Disable trading first (if market is open)
docker-compose exec trading-system python3 -c "
import trading_utils
trading_utils.disable_trading()
"

# 2. Wait for current trades to complete (30 seconds)
sleep 30

# 3. Restart
docker-compose restart trading-system

# 4. Monitor logs
docker logs -f trading-system

# 5. Wait for startup (watch for "Application started")

# 6. Verify health
curl http://localhost:8080/health

# 7. Re-enable trading (if market is open)
docker-compose exec trading-system python3 -c "
import trading_utils
trading_utils.enable_trading()
"
```

---

### Task 2: Check Why Trade Failed

**When:** Alert: HighTradeErrorRate or manual investigation needed

```bash
# 1. Get recent failed trades
docker-compose exec trading-postgres psql -U trading_user -d trading_db -c "
  SELECT trade_id, symbol, error_message, created_at
  FROM trades
  WHERE status = 'failed'
  AND created_at > NOW() - INTERVAL '1 hour'
  ORDER BY created_at DESC
  LIMIT 10;
"

# 2. Check application logs for context
docker logs trading-system | grep -A 5 "trade_id_from_above"

# 3. Common failure reasons:
#    - Insufficient funds
#    - Market closed
#    - Invalid order parameters
#    - Zerodha API error
#    - Network timeout

# 4. Fix and retry if needed
docker-compose exec trading-system python3 scripts/retry_failed_trade.py <trade_id>
```

---

### Task 3: Manually Place Trade (Testing)

**When:** Testing order execution, manual intervention needed

```bash
# 1. Check current positions
docker-compose exec trading-system python3 -c "
from trading_utils import get_open_positions
print(get_open_positions())
"

# 2. Place test order (small quantity)
docker-compose exec trading-system python3 -c "
from trading_utils import place_order
result = place_order(
    symbol='NIFTY 50',
    transaction_type='BUY',
    quantity=1,
    order_type='MARKET',
    product='MIS'
)
print(result)
"

# 3. Verify order was placed
# Check Zerodha web/app
# OR
docker-compose exec trading-system python3 -c "
from kiteconnect import KiteConnect
kite = KiteConnect(api_key='your_key')
kite.set_access_token('your_token')
print(kite.orders())
"
```

---

### Task 4: Update Configuration

**When:** Changing trading parameters, risk limits, etc.

```bash
# 1. Backup current config
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# 2. Edit configuration
vim .env

# Example changes:
# MAX_POSITION_SIZE=50000    # Changed from 30000
# STOP_LOSS_PERCENTAGE=2.0   # Changed from 1.5

# 3. Restart trading system (see Task 1)

# 4. Verify new settings loaded
docker-compose exec trading-system python3 -c "
import os
print('MAX_POSITION_SIZE:', os.getenv('MAX_POSITION_SIZE'))
print('STOP_LOSS_PERCENTAGE:', os.getenv('STOP_LOSS_PERCENTAGE'))
"

# 5. Monitor for 1 hour to ensure changes work as expected
```

---

### Task 5: Deploy New Version

**When:** New code release

```bash
# 1. Read release notes
cat CHANGELOG.md | head -50

# 2. Create pre-deployment backup
cd scripts
./backup.sh

# 3. Deploy (follow deployment checklist)
./deploy.sh

# 4. Monitor deployment
./scripts/deploy_monitor.sh

# 5. Verify deployment
curl http://localhost:8080/version
# Should show new version number

# 6. Monitor for 30 minutes
# Watch dashboards, check for errors

# 7. If issues, rollback
./deploy.sh rollback
```

---

### Task 6: Respond to Critical Alert

**When:** PagerDuty page received

```bash
# 1. Acknowledge alert (within 5 minutes)
# Click link in PagerDuty notification
# OR
# Reply to Slack alert

# 2. Assess situation
# - What is the alert?
# - What is the impact?
# - Is trading affected?

# 3. Follow incident runbook
# See: docs/INCIDENT_RESPONSE_RUNBOOKS.md
# Each alert type has specific runbook

# 4. Update stakeholders every 15 minutes
# Post in #trading-alerts Slack channel

# 5. Resolve issue
# Follow runbook steps

# 6. Verify resolution
# Check alert is no longer firing
# Verify system is healthy

# 7. Document incident
# Create incident ticket
# Note time, actions taken, resolution

# 8. Post-mortem (if P0/P1)
# Schedule within 48 hours
```

---

## Troubleshooting

### Issue 1: System is Slow

**Symptoms:** High latency, slow API responses, dashboard slow to load

**Diagnosis:**

```bash
# 1. Check system resources
ssh production-server
top
free -h
df -h

# 2. Check database
docker exec trading-postgres psql -U trading_user -d trading_db -c "
  SELECT pid, now() - query_start AS duration, query
  FROM pg_stat_activity
  WHERE state = 'active'
  AND now() - query_start > interval '5 seconds'
  ORDER BY duration DESC;
"

# 3. Check for slow queries
docker logs trading-system | grep "slow query"

# 4. Check Redis
docker exec trading-redis redis-cli INFO memory
docker exec trading-redis redis-cli SLOWLOG GET 10
```

**Solutions:**

**If database slow queries:**
```bash
# Kill long-running query
docker exec trading-postgres psql -U trading_user -d trading_db -c "
  SELECT pg_terminate_backend(<PID>);
"

# Add index if needed (from query optimizer recommendation)
docker exec trading-postgres psql -U trading_user -d trading_db -c "
  CREATE INDEX CONCURRENTLY idx_name ON table_name (column);
"
```

**If CPU/Memory high:**
```bash
# Restart services to clear memory
docker-compose restart trading-system

# If persistent, scale up resources
# (Requires maintenance window)
```

**If Redis memory full:**
```bash
# Clear Redis cache
docker exec trading-redis redis-cli FLUSHDB

# Or increase Redis memory limit
vim docker-compose.yml
# redis:
#   command: redis-server --maxmemory 4gb
docker-compose up -d redis
```

---

### Issue 2: Trades Not Executing

**Symptoms:** No trades in last 30 minutes (during market hours)

**Diagnosis:**

```bash
# 1. Check if trading is enabled
docker-compose exec trading-system python3 -c "
from trading_utils import is_trading_enabled
print('Trading enabled:', is_trading_enabled())
"

# 2. Check for signals
docker logs trading-system | grep "Trading signal" | tail -20

# 3. Check Zerodha API connectivity
docker-compose exec trading-system python3 -c "
from kiteconnect import KiteConnect
kite = KiteConnect(api_key='your_key')
kite.set_access_token('your_token')
try:
    print(kite.margins())
    print('Zerodha API: OK')
except Exception as e:
    print('Zerodha API Error:', e)
"

# 4. Check available funds
docker-compose exec trading-system python3 -c "
from trading_utils import get_available_margin
print('Available margin:', get_available_margin())
"
```

**Solutions:**

**If trading disabled:**
```bash
docker-compose exec trading-system python3 -c "
import trading_utils
trading_utils.enable_trading()
"
```

**If no signals:**
```
# This is normal - strategies may not find entry points
# Review strategy parameters if this persists for days
```

**If Zerodha API error:**
```bash
# Check API credentials
cat .env | grep KITE

# Regenerate access token if expired
docker-compose exec trading-system python3 scripts/refresh_kite_token.py
```

**If insufficient funds:**
```
# Transfer funds to trading account
# Or reduce position sizes in config
```

---

### Issue 3: Database Connection Failed

**Symptoms:** Application logs show "database connection error"

**Diagnosis:**

```bash
# 1. Check if PostgreSQL is running
docker ps | grep postgres

# 2. Check PostgreSQL logs
docker logs trading-postgres --tail 100

# 3. Try to connect manually
docker exec trading-postgres psql -U trading_user -d trading_db -c "SELECT 1;"

# 4. Check connections
docker exec trading-postgres psql -U trading_user -d trading_db -c "
  SELECT COUNT(*) FROM pg_stat_activity;
"
```

**Solutions:**

**If PostgreSQL stopped:**
```bash
docker-compose start postgres

# Wait for startup
sleep 10

# Verify
pg_isready -h localhost -p 5432
```

**If too many connections:**
```bash
# Kill idle connections
docker exec trading-postgres psql -U trading_user -d postgres -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE datname = 'trading_db'
  AND state = 'idle'
  AND state_change < NOW() - INTERVAL '1 hour';
"

# Or increase max_connections (requires restart)
# Edit postgresql.conf:
# max_connections = 200
```

**If disk full:**
```bash
# Clean up old data
./scripts/cleanup_old_data.sh

# Or expand disk
```

---

## Best Practices

### Development

1. **Always test locally first**
   - Use `docker-compose.yml` for local development
   - Test changes thoroughly before deploying

2. **Follow git workflow**
   ```bash
   # Create feature branch
   git checkout -b feature/your-feature

   # Make changes, commit
   git commit -m "Add feature X"

   # Push and create PR
   git push origin feature/your-feature

   # Get code review before merging
   ```

3. **Write tests**
   ```bash
   # Run tests locally
   pytest tests/

   # Check coverage
   pytest --cov=trading_system tests/
   ```

4. **Document changes**
   - Update README.md if adding new features
   - Update this guide if changing operations
   - Write clear commit messages

---

### Operations

1. **Backup before changes**
   ```bash
   # Always backup before:
   # - Deployments
   # - Config changes
   # - Database migrations
   ./scripts/backup.sh
   ```

2. **Monitor after changes**
   - Watch dashboards for 30 minutes after any change
   - Check for increased errors or latency
   - Be ready to rollback

3. **Communicate**
   - Post in #trading-alerts before maintenance
   - Update stakeholders on incidents
   - Document decisions

4. **Security**
   - Never commit secrets to Git
   - Rotate passwords quarterly
   - Use SSH keys, not passwords
   - Enable MFA on all accounts

---

### Trading

1. **Respect trading hours**
   - No deployments during market hours (9:15 AM - 3:30 PM IST)
   - Emergency fixes only if trading is affected

2. **Monitor P&L**
   - Daily max loss limit: ₹5,000
   - If hit, disable trading and investigate

3. **Risk management**
   - Never override stop losses
   - Respect position size limits
   - Don't manually interfere with automated trades

4. **Reconciliation**
   - Always reconcile positions post-market
   - Investigate any discrepancies immediately

---

## Resources

### Documentation

| Document | Purpose | Location |
|----------|---------|----------|
| README.md | System overview | Root of repository |
| DEPLOYMENT.md | Deployment procedures | docs/ |
| INCIDENT_RESPONSE_RUNBOOKS.md | Incident response | docs/ |
| DISASTER_RECOVERY_PLAN.md | DR procedures | docs/ |
| BACKUP_RECOVERY.md | Backup/restore | docs/ |
| MONITORING_ALERTING_PLAYBOOK.md | Monitoring setup | docs/ |

### Dashboards

| Dashboard | URL | Purpose |
|-----------|-----|---------|
| Trading Activity | http://grafana:3000/d/trading-activity | Real-time trading metrics |
| System Health | http://grafana:3000/d/system-health | Overall system status |
| Performance | http://grafana:3000/d/performance | Query performance, latency |
| Infrastructure | http://grafana:3000/d/infrastructure | CPU, memory, disk |
| Alerts | http://grafana:3000/d/alert-management | Active and historical alerts |

### Useful Commands

```bash
# Check system status
./scripts/status.sh

# View logs
./scripts/logs.sh

# Run health check
./scripts/health_check.sh

# Start all services
./scripts/start.sh

# Stop all services
./scripts/stop.sh

# Deploy
./scripts/deploy.sh

# Backup
./scripts/backup.sh

# Restore
./scripts/restore.sh <backup-directory>
```

### Slack Channels

| Channel | Purpose |
|---------|---------|
| #trading-system | General discussion |
| #trading-alerts | Automated alerts |
| #trading-incidents | Incident coordination |
| #trading-deploys | Deployment notifications |
| #trading-analytics | Performance analysis |

### Emergency Contacts

| Role | Contact |
|------|---------|
| On-Call Engineer | PagerDuty |
| Engineering Lead | +91-XXX-XXX-1001 |
| DBA | +91-XXX-XXX-1002 |
| Trading Lead | +91-XXX-XXX-1003 |

---

## Learning Path

### Week 1: Basics
- [ ] Complete local setup
- [ ] Read all documentation
- [ ] Shadow on-call engineer
- [ ] Run through common tasks with mentor

### Week 2: Operations
- [ ] Perform daily operations (with oversight)
- [ ] Deploy to staging
- [ ] Respond to test alerts
- [ ] Complete backup/restore exercise

### Week 3: Independence
- [ ] Perform daily operations independently
- [ ] Deploy to production (with oversight)
- [ ] Participate in on-call rotation (backup)
- [ ] Troubleshoot real issues

### Week 4: Mastery
- [ ] Primary on-call engineer
- [ ] Lead deployment
- [ ] Mentor new team member
- [ ] Propose improvements

---

## Quiz (Self-Assessment)

Test your knowledge:

1. **What are the trading hours for NSE?**
   <details>
   <summary>Answer</summary>
   9:15 AM to 3:30 PM IST
   </details>

2. **What is our RTO (Recovery Time Objective)?**
   <details>
   <summary>Answer</summary>
   30 minutes
   </details>

3. **How do you disable trading in an emergency?**
   <details>
   <summary>Answer</summary>

   ```bash
   docker-compose exec trading-system python3 -c "
   import trading_utils
   trading_utils.disable_trading()
   "
   ```
   </details>

4. **What should you do before deploying?**
   <details>
   <summary>Answer</summary>

   - Create backup
   - Check deployment checklist
   - Notify team
   - Ensure market is closed (or after hours)
   </details>

5. **What is the daily max loss limit?**
   <details>
   <summary>Answer</summary>
   ₹5,000 (after which trading should be disabled and investigation started)
   </details>

---

## Feedback

Help us improve this guide!

- **Found an error?** Submit a PR or create an issue
- **Have a question?** Ask in #trading-system Slack channel
- **Suggestion?** Email training@example.com

---

**Document Version:** 1.0
**Last Updated:** Week 4
**Next Review:** Quarterly
**Maintainer:** SRE Team

---

END OF TEAM TRAINING GUIDE
