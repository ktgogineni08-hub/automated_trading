# Quick Reference Card
## Enhanced NIFTY 50 Trading System

**Print this card and keep it handy for daily operations**

---

## 🚨 EMERGENCY CONTACTS

| Role | Contact | Use For |
|------|---------|---------|
| **On-Call Engineer** | PagerDuty | Critical alerts (P0/P1) |
| **Engineering Lead** | +91-XXX-1001 | Escalation |
| **DBA** | +91-XXX-1002 | Database issues |
| **Trading Lead** | +91-XXX-1003 | Business decisions |

**War Room:** https://meet.google.com/emergency

---

## ⚡ EMERGENCY PROCEDURES

### Stop Trading Immediately
```bash
docker-compose exec trading-system python3 -c "
import trading_utils
trading_utils.disable_trading()
"
```

### Close All Positions
```bash
docker-compose exec trading-system python3 scripts/emergency_close_all.py
```

### Restart Trading System
```bash
docker-compose restart trading-system
```

### Check System Health
```bash
curl http://localhost:8080/health | jq .
```

---

## 📅 DAILY OPERATIONS

### Pre-Market (9:00 AM)
```bash
# 1. Health check
docker-compose ps

# 2. Check logs
docker logs trading-system --tail 50

# 3. Verify backups
ls -lh backups/ | head -3

# 4. Check dashboards
open http://localhost:3000
```

### Post-Market (3:30 PM)
```bash
# 1. Generate report
docker-compose exec trading-system python3 scripts/daily_report.py

# 2. Reconcile positions
docker-compose exec trading-system python3 scripts/reconcile_positions.py

# 3. Check backup
tail logs/backups/backup_*.log
```

---

## 🔍 COMMON ISSUES

### Issue: System is Slow
**Quick Fix:**
```bash
# Check resources
top
free -h

# Check slow queries
docker logs trading-system | grep "slow query"

# Clear Redis cache
docker exec trading-redis redis-cli FLUSHDB
```

### Issue: Trades Not Executing
**Quick Fix:**
```bash
# Check if trading enabled
docker-compose exec trading-system python3 -c "
from trading_utils import is_trading_enabled
print('Trading enabled:', is_trading_enabled())
"

# Check Zerodha API
curl https://api.kite.trade
```

### Issue: Database Connection Failed
**Quick Fix:**
```bash
# Check PostgreSQL
docker ps | grep postgres

# Restart if needed
docker-compose restart postgres

# Test connection
docker exec trading-postgres psql -U trading_user -d trading_db -c "SELECT 1;"
```

---

## 📊 DASHBOARDS

| Dashboard | URL | Use For |
|-----------|-----|---------|
| **Trading Activity** | http://localhost:3000/d/trading-activity | Real-time P&L, trades |
| **System Health** | http://localhost:3000/d/system-health | Overall status |
| **Performance** | http://localhost:3000/d/performance | Latency, queries |
| **Alerts** | http://localhost:3000/d/alert-management | Active alerts |

**Default Login:** admin / admin

---

## 🛠️ USEFUL COMMANDS

### Check Status
```bash
./scripts/status.sh                    # Overall status
docker-compose ps                      # Container status
docker stats                           # Resource usage
```

### View Logs
```bash
./scripts/logs.sh                      # All logs
docker logs trading-system -f          # App logs
docker logs trading-postgres -f        # DB logs
```

### Backup & Restore
```bash
./scripts/backup.sh                    # Create backup
./scripts/restore.sh backups/latest    # Restore
```

### Deploy
```bash
./scripts/deploy.sh                    # Deploy
./scripts/deploy.sh rollback           # Rollback
```

---

## 📈 KEY METRICS

### Target Metrics
- **Uptime:** 99.9%
- **P95 Latency:** < 500ms
- **Error Rate:** < 1%
- **Win Rate:** > 55%
- **Daily P&L:** > ₹10,000

### Check Metrics
```bash
# Latency
curl -w "@curl-format.txt" http://localhost:8080/api/status

# Error rate
docker logs trading-system | grep ERROR | wc -l

# P&L
curl http://localhost:8080/api/pnl | jq '.total_pnl'
```

---

## 🔐 SECURITY

### Secrets Location
- Environment: `.env` (NEVER commit!)
- AWS Secrets: `aws secretsmanager get-secret-value --secret-id trading-system`
- API Keys: Encrypted in database

### Access
- **SSH:** Use SSH keys only (no passwords)
- **VPN:** Required for production access
- **MFA:** Required for all critical systems

---

## 📞 ESCALATION PATH

```
Level 1 (0-10 min):  On-Call Engineer (PagerDuty)
         ↓
Level 2 (10-20 min): Senior SRE + DBA
         ↓
Level 3 (20-30 min): Engineering Lead + App Owner
         ↓
Level 4 (30+ min):   CTO + Business Owner → Activate DR
```

---

## 📚 DOCUMENTATION

| Document | Location | Use For |
|----------|----------|---------|
| **Runbooks** | docs/INCIDENT_RESPONSE_RUNBOOKS.md | Incident response |
| **DR Plan** | docs/DISASTER_RECOVERY_PLAN.md | Disaster recovery |
| **Training** | docs/TEAM_TRAINING_GUIDE.md | Onboarding |
| **Monitoring** | docs/MONITORING_ALERTING_PLAYBOOK.md | Alert response |

---

## ⏰ TRADING HOURS

**NSE Market Hours:** 9:15 AM - 3:30 PM IST

**Pre-Market:** 9:00 AM - 9:15 AM (system prep)
**Market Hours:** 9:15 AM - 3:30 PM (active monitoring)
**Post-Market:** 3:30 PM - 4:00 PM (reconciliation)

**No deployments during market hours!** (Emergency fixes only)

---

## 🎯 RESPONSE TIMES

| Severity | Acknowledge | Resolve |
|----------|-------------|---------|
| **P0 Critical** | < 5 min | < 30 min |
| **P1 High** | < 15 min | < 2 hours |
| **P2 Medium** | < 1 hour | < 8 hours |
| **P3 Low** | < 8 hours | Next day |

---

## 💡 TIPS

1. **Always check health before making changes**
2. **Backup before deployments**
3. **Monitor dashboards for 30 min after changes**
4. **Document everything in incident tickets**
5. **When in doubt, ask in #trading-system Slack**

---

## 🆘 "I DON'T KNOW WHAT TO DO"

1. **Don't panic** - Take a breath
2. **Check this card** - Common issues listed above
3. **Check dashboards** - Visual system status
4. **Check Slack** - #trading-alerts channel
5. **Ask for help** - Escalate if needed

**Remember:** It's better to ask than to guess!

---

## 📱 SLACK CHANNELS

- **#trading-system** - General discussion
- **#trading-alerts** - Automated alerts (monitor this!)
- **#trading-incidents** - Active incidents
- **#trading-deploys** - Deployment notifications

---

**Keep this card accessible at all times!**

*Version: 1.0 | Updated: Nov 1, 2025*
