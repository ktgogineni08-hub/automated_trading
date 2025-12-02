# Backup and Recovery Guide

Comprehensive guide for backing up and restoring the Enhanced NIFTY 50 Trading System.

---

## Table of Contents

1. [Overview](#overview)
2. [Backup Strategy](#backup-strategy)
3. [Backup Components](#backup-components)
4. [Automated Backups](#automated-backups)
5. [Manual Backups](#manual-backups)
6. [Restore Procedures](#restore-procedures)
7. [Disaster Recovery](#disaster-recovery)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Overview

### What Gets Backed Up

The backup system covers all critical components:

- **PostgreSQL Database:** All trading data, positions, orders, portfolio history
- **Redis Cache:** Session data, cached calculations, temporary data
- **Configuration Files:** Environment files, Docker Compose, dashboards, certificates
- **Application Logs:** Recent logs for audit and debugging

### Backup Tools

- `scripts/backup.sh` - Main backup script
- `scripts/restore.sh` - Restore script
- `scripts/schedule_backups.sh` - Automated scheduling

### Storage Location

Default: `trading-system/backups/`

Each backup is stored in a timestamped directory:
```
backups/
├── 20240101_020000/
│   ├── database/
│   │   ├── trading_db_20240101_020000.sql.gz
│   │   └── trading_db_20240101_020000.sql.gz.sha256
│   ├── redis/
│   │   ├── dump_20240101_020000.rdb.gz
│   │   └── dump_20240101_020000.rdb.gz.sha256
│   ├── config/
│   │   └── config_20240101_020000.tar.gz
│   ├── logs/
│   │   └── logs_20240101_020000.tar.gz
│   └── metadata/
│       ├── backup_info.json
│       └── backup_summary.txt
├── 20240102_020000/
└── ...
```

---

## Backup Strategy

### Backup Types

#### 1. Full Backup
- **Frequency:** Daily at 2:00 AM
- **Includes:** All components (database, Redis, config, logs)
- **Retention:** 7 days
- **Purpose:** Complete system recovery

#### 2. Incremental Backup
- **Frequency:** Every hour during trading hours (9:15 AM - 3:30 PM)
- **Includes:** Database only (changed data)
- **Retention:** 24 hours
- **Purpose:** Minimize data loss during trading

#### 3. Pre-Deployment Backup
- **Frequency:** Before each deployment
- **Includes:** All components
- **Retention:** 30 days
- **Purpose:** Rollback capability

### Retention Policy

| Backup Type | Retention Period | Storage Location |
|-------------|------------------|------------------|
| Daily       | 7 days          | Local            |
| Weekly      | 30 days         | Local + Remote   |
| Monthly     | 90 days         | Remote (S3/Azure)|
| Pre-Deploy  | 30 days         | Local + Remote   |

### 3-2-1 Backup Rule

The system follows the 3-2-1 backup rule:
- **3** copies of data (production + 2 backups)
- **2** different storage types (local disk + remote cloud)
- **1** off-site copy (S3, Azure, or remote server)

---

## Backup Components

### 1. PostgreSQL Database

**What's included:**
- All tables: `trades`, `positions`, `orders`, `portfolio`, `alerts`, `api_calls`, `system_metrics`
- Schema definitions
- Indexes and constraints
- Functions and triggers

**Backup method:** `pg_dump` with gzip compression

**Average size:** 50-100 MB (compressed)

**RTO:** < 15 minutes

**RPO:** 1 hour during trading, 24 hours otherwise

### 2. Redis Cache

**What's included:**
- All keys in all databases
- Session data
- Cached query results
- Temporary trading state

**Backup method:** Redis `BGSAVE` to RDB file

**Average size:** 10-50 MB (compressed)

**RTO:** < 5 minutes

**RPO:** 1 hour (non-critical data, can be regenerated)

### 3. Configuration Files

**What's included:**
- `.env` and `.env.production`
- `docker-compose.yml`
- Prometheus configuration
- Grafana dashboards
- SSL certificates
- Application config files

**Backup method:** Tar with gzip compression

**Average size:** < 5 MB

**RTO:** < 5 minutes

**RPO:** On change (manual backup before modifications)

### 4. Application Logs

**What's included:**
- Last 7 days of application logs
- Container logs (last 10,000 lines)
- System logs

**Backup method:** Tar with gzip compression

**Average size:** 50-200 MB

**RTO:** N/A (logs only)

**RPO:** N/A

---

## Automated Backups

### Setup

Configure automated daily backups:

```bash
cd trading-system/scripts
./schedule_backups.sh daily
```

This creates a cron job that runs at 2:00 AM every day.

### Alternative Schedules

**Hourly backups:**
```bash
./schedule_backups.sh hourly
```

**Custom schedule:**
```bash
./schedule_backups.sh custom "0 */6 * * *"  # Every 6 hours
```

### Verify Schedule

Check configured backups:
```bash
crontab -l | grep backup
```

### Monitor Backups

View backup logs:
```bash
tail -f logs/backups/backup_*.log
```

### Off-site Sync

#### AWS S3 Sync

Add to cron for automated off-site backup:

```bash
# Edit crontab
crontab -e

# Add this line (runs at 3:00 AM, after local backup)
0 3 * * * aws s3 sync /path/to/trading-system/backups/ s3://your-bucket/trading-backups/ --delete

# Or use AWS CLI with lifecycle policies
aws s3api put-bucket-lifecycle-configuration \
  --bucket your-bucket \
  --lifecycle-configuration file://lifecycle.json
```

**lifecycle.json:**
```json
{
  "Rules": [
    {
      "Id": "Delete old backups",
      "Status": "Enabled",
      "Prefix": "trading-backups/",
      "Expiration": {
        "Days": 90
      }
    }
  ]
}
```

#### Azure Blob Storage Sync

```bash
# Using azcopy
azcopy sync /path/to/trading-system/backups/ \
  "https://yourstorageaccount.blob.core.windows.net/backups/?<SAS-token>" \
  --recursive --delete-destination
```

#### Remote Server Sync

```bash
# Using rsync over SSH
rsync -avz --delete \
  /path/to/trading-system/backups/ \
  user@remote-server:/backups/trading-system/
```

---

## Manual Backups

### Full Backup

Run a complete backup manually:

```bash
cd trading-system/scripts
./backup.sh
```

### Selective Backups

**Database only:**
```bash
BACKUP_REDIS=false BACKUP_CONFIG=false BACKUP_LOGS=false ./backup.sh
```

**Configuration only:**
```bash
BACKUP_DATABASE=false BACKUP_REDIS=false BACKUP_LOGS=false ./backup.sh
```

### Pre-Deployment Backup

Always backup before deployments:

```bash
# Tag backup as pre-deployment
BACKUP_TYPE=pre-deployment ./backup.sh

# Deploy
./deploy.sh

# If deployment fails, restore from backup
./restore.sh backups/<timestamp>
```

### Verify Backup

Check backup contents:

```bash
# View metadata
cat backups/20240101_020000/metadata/backup_summary.txt

# Verify database backup integrity
gunzip -t backups/20240101_020000/database/*.sql.gz

# Check checksums
cd backups/20240101_020000/database
sha256sum -c *.sha256
```

---

## Restore Procedures

### Pre-Restore Checklist

Before restoring:

1. ✅ Stop trading activity (set `TRADING_ENABLED=false`)
2. ✅ Notify team members
3. ✅ Identify backup to restore from
4. ✅ Verify backup integrity (checksums)
5. ✅ Review backup metadata
6. ✅ Ensure sufficient disk space

### Full System Restore

Restore all components:

```bash
cd trading-system/scripts
./restore.sh backups/20240101_020000
```

The script will:
1. Show backup information
2. Ask for confirmation
3. Stop the trading system
4. Restore database
5. Restore Redis
6. Restore configuration
7. Restart services
8. Run health checks

### Selective Restore

**Database only:**
```bash
RESTORE_REDIS=false RESTORE_CONFIG=false \
  ./restore.sh backups/20240101_020000
```

**Redis only:**
```bash
RESTORE_DATABASE=false RESTORE_CONFIG=false \
  ./restore.sh backups/20240101_020000
```

**Configuration only:**
```bash
RESTORE_DATABASE=false RESTORE_REDIS=false \
  ./restore.sh backups/20240101_020000
```

### Dry Run

Test restore without making changes:

```bash
DRY_RUN=true ./restore.sh backups/20240101_020000
```

This shows what would be restored without actually restoring it.

### Point-in-Time Recovery (PITR)

For PostgreSQL point-in-time recovery:

1. **Enable WAL archiving** (in `postgresql.conf`):
```conf
wal_level = replica
archive_mode = on
archive_command = 'cp %p /path/to/archive/%f'
```

2. **Restore base backup:**
```bash
./restore.sh backups/20240101_020000
```

3. **Apply WAL files to target time:**
```bash
# Create recovery.conf
cat > recovery.conf << EOF
restore_command = 'cp /path/to/archive/%f %p'
recovery_target_time = '2024-01-01 14:30:00'
EOF

# Restart PostgreSQL
docker-compose restart postgres
```

### Post-Restore Verification

After restore, verify:

```bash
# 1. Check service status
docker-compose ps

# 2. Verify database tables
docker exec trading-postgres psql -U trading_user -d trading_db -c "\dt"

# 3. Check Redis keys
docker exec trading-redis redis-cli DBSIZE

# 4. Test trading system
docker-compose exec trading-system python3 -c "
import trading_utils
print('Database connection:', trading_utils.test_db_connection())
print('Redis connection:', trading_utils.test_redis_connection())
"

# 5. Check recent trades
docker exec trading-postgres psql -U trading_user -d trading_db -c \
  "SELECT COUNT(*) FROM trades WHERE created_at > NOW() - INTERVAL '7 days';"

# 6. Verify system health
curl http://localhost:8080/health

# 7. Check Grafana dashboards
open http://localhost:3000
```

---

## Disaster Recovery

### Disaster Scenarios

#### Scenario 1: Database Corruption

**Symptoms:**
- PostgreSQL won't start
- Data inconsistencies
- Corrupted tables

**Recovery:**
```bash
# 1. Stop trading
docker-compose stop trading-system

# 2. Restore from last good backup
./restore.sh backups/<last-good-backup>

# 3. Verify data integrity
docker exec trading-postgres psql -U trading_user -d trading_db -c "
  SELECT COUNT(*) FROM trades;
  SELECT MAX(created_at) FROM trades;
"

# 4. Resume trading
docker-compose start trading-system
```

**RTO:** < 15 minutes
**RPO:** Up to 1 hour

---

#### Scenario 2: Complete Server Failure

**Symptoms:**
- Server hardware failure
- Data center outage
- Complete disk failure

**Recovery:**

1. **Provision new server**
2. **Install Docker and Docker Compose**
3. **Clone repository:**
```bash
git clone https://github.com/your-org/trading-system.git
cd trading-system
```

4. **Restore from off-site backup:**
```bash
# Download from S3
aws s3 sync s3://your-bucket/trading-backups/latest/ backups/latest/

# Or from remote server
rsync -avz user@backup-server:/backups/trading-system/latest/ backups/latest/
```

5. **Restore system:**
```bash
cd scripts
./restore.sh ../backups/latest
```

6. **Start services:**
```bash
docker-compose up -d
```

7. **Verify and resume:**
```bash
./scripts/health_check.sh
# If healthy, enable trading
```

**RTO:** 1-2 hours
**RPO:** Up to 24 hours (last off-site backup)

---

#### Scenario 3: Data Center Disaster

**Symptoms:**
- Complete data center unavailable
- Regional outage

**Recovery:**

**Prerequisites:**
- Multi-region deployment
- Real-time replication to DR site
- Automated failover

**Steps:**

1. **Activate DR site:**
```bash
# On DR server
cd trading-system
./scripts/failover_to_dr.sh
```

2. **Verify DR system:**
```bash
./scripts/health_check.sh
curl https://dr-trading.example.com/health
```

3. **Update DNS:**
```bash
# Point production domain to DR IP
aws route53 change-resource-record-sets \
  --hosted-zone-id Z123456 \
  --change-batch file://failover-dns.json
```

4. **Monitor DR system:**
```bash
# Access DR Grafana
open https://dr-trading.example.com:3000
```

5. **Resume trading:**
```bash
# Enable trading on DR
docker-compose exec trading-system \
  python3 -c "import trading_utils; trading_utils.enable_trading()"
```

**RTO:** < 30 minutes
**RPO:** Near-zero (with replication)

---

## Best Practices

### 1. Regular Testing

**Monthly Restore Test:**
```bash
#!/bin/bash
# test_restore.sh

# Get latest backup
LATEST=$(ls -1d backups/*/ | sort -r | head -1)

# Test restore on staging
DRY_RUN=false RESTORE_DATABASE=true RESTORE_REDIS=true \
  ./restore.sh "${LATEST}"

# Verify data
# ... run verification queries ...

# Report results
echo "Restore test completed for ${LATEST}"
```

**Schedule:**
```bash
# Run on first Sunday of each month
0 2 1-7 * 0 [ $(date +\%u) -eq 7 ] && /path/to/test_restore.sh
```

### 2. Monitoring

**Backup Success Monitoring:**

Add to Prometheus:
```yaml
# prometheus/alerts.yml
groups:
  - name: backup
    rules:
      - alert: BackupFailed
        expr: time() - backup_last_success_timestamp > 86400
        for: 1h
        labels:
          severity: critical
        annotations:
          summary: "Backup has not succeeded in 24 hours"
```

**Track metrics:**
```python
# In backup.sh, export metrics
backup_duration_seconds{type="full"} 245
backup_size_bytes{component="database"} 52428800
backup_last_success_timestamp 1704081600
```

### 3. Encryption

**Encrypt backups at rest:**

```bash
# Modify backup.sh to encrypt
gpg --encrypt --recipient admin@example.com \
  backups/20240101_020000/database/trading_db_20240101_020000.sql.gz

# Decrypt for restore
gpg --decrypt \
  backups/20240101_020000/database/trading_db_20240101_020000.sql.gz.gpg \
  > temp.sql.gz
```

**S3 server-side encryption:**
```bash
aws s3 sync backups/ s3://your-bucket/backups/ \
  --sse AES256
```

### 4. Backup Validation

**Automated validation script:**

```bash
#!/bin/bash
# validate_backup.sh

BACKUP_DIR=$1

# Check all components exist
[ -d "${BACKUP_DIR}/database" ] || exit 1
[ -d "${BACKUP_DIR}/redis" ] || exit 1
[ -d "${BACKUP_DIR}/config" ] || exit 1

# Verify checksums
cd "${BACKUP_DIR}/database"
sha256sum -c *.sha256 || exit 1

cd "${BACKUP_DIR}/redis"
sha256sum -c *.sha256 || exit 1

# Test decompression
gunzip -t "${BACKUP_DIR}"/database/*.sql.gz || exit 1
gunzip -t "${BACKUP_DIR}"/redis/*.rdb.gz || exit 1

echo "Backup validation passed"
```

### 5. Documentation

Keep a backup runbook:

```markdown
# BACKUP RUNBOOK

## Emergency Contacts
- DBA: John Doe (john@example.com, +1-555-0100)
- SysAdmin: Jane Smith (jane@example.com, +1-555-0101)
- On-call: +1-555-0199

## Quick Reference
- Backup location: /path/to/trading-system/backups
- Off-site: s3://your-bucket/trading-backups
- Schedule: Daily 2:00 AM
- Retention: 7 days local, 90 days remote

## Recovery Time Objectives
- Database: 15 minutes
- Full system: 30 minutes
- DR failover: 30 minutes

## Recovery Point Objectives
- Trading hours: 1 hour
- Non-trading: 24 hours
```

---

## Troubleshooting

### Backup Issues

#### Problem: Backup script fails with "disk full"

**Solution:**
```bash
# Check disk usage
df -h

# Clean old backups manually
rm -rf backups/older_than_7_days

# Adjust retention in backup.sh
RETENTION_DAILY=3  # Reduce from 7 to 3 days
```

---

#### Problem: Database backup timeout

**Solution:**
```bash
# Increase timeout in backup.sh
timeout 3600 docker exec trading-postgres pg_dump ...

# Or backup specific tables only
pg_dump --table=trades --table=positions ...
```

---

#### Problem: Redis backup fails

**Solution:**
```bash
# Check Redis memory
docker exec trading-redis redis-cli INFO memory

# If memory is full, increase maxmemory
docker exec trading-redis redis-cli CONFIG SET maxmemory 2gb

# Trigger save manually
docker exec trading-redis redis-cli BGSAVE
```

---

### Restore Issues

#### Problem: Restore fails with "database already exists"

**Solution:**
```bash
# Manually drop database
docker exec trading-postgres psql -U trading_user -d postgres -c \
  "DROP DATABASE IF EXISTS trading_db;"

# Re-run restore
./restore.sh backups/20240101_020000
```

---

#### Problem: Restored database missing recent data

**Solution:**
```bash
# Check backup timestamp
cat backups/20240101_020000/metadata/backup_info.json

# Find more recent backup
ls -ltr backups/

# Restore from correct backup
./restore.sh backups/<correct-timestamp>
```

---

#### Problem: Redis restore shows 0 keys

**Solution:**
```bash
# Check if dump.rdb was correctly copied
docker exec trading-redis ls -lh /data/dump.rdb

# Verify Redis loaded the file
docker exec trading-redis redis-cli INFO persistence

# If not, restart Redis
docker-compose restart redis
```

---

### Performance Issues

#### Problem: Backups taking too long

**Solution:**
```bash
# Use parallel compression
pg_dump ... | pigz > backup.sql.gz

# Backup only changed data (incremental)
pg_dump --data-only --table=trades \
  --where="created_at > NOW() - INTERVAL '1 hour'"

# Increase backup parallelism
pg_dump --jobs=4 ...
```

---

## Appendix

### Backup Script Reference

**Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKUP_ROOT` | `./backups` | Backup storage location |
| `BACKUP_DATABASE` | `true` | Include database in backup |
| `BACKUP_REDIS` | `true` | Include Redis in backup |
| `BACKUP_CONFIG` | `true` | Include config in backup |
| `BACKUP_LOGS` | `true` | Include logs in backup |
| `RETENTION_DAILY` | `7` | Days to keep daily backups |
| `RETENTION_WEEKLY` | `30` | Days to keep weekly backups |
| `RETENTION_MONTHLY` | `90` | Days to keep monthly backups |

### Restore Script Reference

**Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `RESTORE_DATABASE` | `true` | Restore database |
| `RESTORE_REDIS` | `true` | Restore Redis |
| `RESTORE_CONFIG` | `true` | Restore configuration |
| `DRY_RUN` | `false` | Show what would be restored |

### Useful Commands

```bash
# List all backups
ls -lh backups/

# Check backup sizes
du -sh backups/*/

# Find largest backups
du -sh backups/*/ | sort -h | tail -5

# Count backups
ls -1d backups/*/ | wc -l

# Delete backups older than 30 days
find backups/ -maxdepth 1 -type d -mtime +30 -exec rm -rf {} \;

# Verify all backup checksums
for dir in backups/*/; do
  echo "Checking $dir"
  (cd "$dir/database" && sha256sum -c *.sha256)
  (cd "$dir/redis" && sha256sum -c *.sha256)
done
```

---

## Support

For backup and recovery issues:

1. Check logs: `logs/backups/backup_*.log`
2. Review this documentation
3. Contact DBA team
4. Escalate to infrastructure team if needed

---

**Last Updated:** Week 4, Production Go-Live Phase
**Version:** 1.0
**Maintainer:** Trading System Team
