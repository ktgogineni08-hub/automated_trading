#!/bin/bash
################################################################################
# Backup Scheduler Setup
# Configures automated backups via cron
################################################################################

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="${SCRIPT_DIR}/backup.sh"
LOG_DIR="${SCRIPT_DIR}/../logs/backups"

# Banner
echo -e "${BLUE}"
cat << 'BANNER'
═══════════════════════════════════════════════════════════════════════
  ____             _                  _____      _              _       _
 |  _ \           | |                / ____|    | |            | |     | |
 | |_) | __ _  ___| | ___   _ _ __ | (___   ___| |__   ___  __| |_   _| | ___ _ __
 |  _ < / _` |/ __| |/ / | | | '_ \ \___ \ / __| '_ \ / _ \/ _` | | | | |/ _ \ '__|
 | |_) | (_| | (__|   <| |_| | |_) |____) | (__| | | |  __/ (_| | |_| | |  __/ |
 |____/ \__,_|\___|_|\_\\__,_| .__/_____/ \___|_| |_|\___|\__,_|\__,_|_|\___|_|
                             | |
                             |_|
═══════════════════════════════════════════════════════════════════════
BANNER
echo -e "${NC}"

# Show usage
usage() {
    cat << EOF
Usage: $0 [SCHEDULE]

Configure automated backup schedule using cron.

Schedules:
  daily       Backup every day at 2:00 AM
  hourly      Backup every hour
  custom      Specify custom cron expression

Examples:
  $0 daily
  $0 hourly
  $0 custom "0 */6 * * *"  # Every 6 hours

Current cron jobs:
EOF
    crontab -l 2>/dev/null | grep -i backup || echo "  No backup jobs configured"
    echo ""
}

# Check if cron is available
if ! command -v crontab &> /dev/null; then
    echo -e "${RED}❌ crontab not available${NC}"
    echo -e "${YELLOW}Install cron or use systemd timers instead${NC}"
    exit 1
fi

# Check if backup script exists
if [ ! -f "$BACKUP_SCRIPT" ]; then
    echo -e "${RED}❌ Backup script not found: ${BACKUP_SCRIPT}${NC}"
    exit 1
fi

# Make backup script executable
chmod +x "$BACKUP_SCRIPT"

# Create log directory
mkdir -p "$LOG_DIR"

# Get schedule
SCHEDULE="${1:-}"
CRON_EXPR=""

case "$SCHEDULE" in
    daily)
        CRON_EXPR="0 2 * * *"
        echo -e "${BLUE}Setting up daily backup at 2:00 AM${NC}"
        ;;
    hourly)
        CRON_EXPR="0 * * * *"
        echo -e "${BLUE}Setting up hourly backup${NC}"
        ;;
    custom)
        CRON_EXPR="${2:-}"
        if [ -z "$CRON_EXPR" ]; then
            echo -e "${RED}❌ Custom cron expression required${NC}\n"
            usage
            exit 1
        fi
        echo -e "${BLUE}Setting up custom backup schedule: ${CRON_EXPR}${NC}"
        ;;
    "")
        usage
        exit 0
        ;;
    *)
        echo -e "${RED}❌ Unknown schedule: ${SCHEDULE}${NC}\n"
        usage
        exit 1
        ;;
esac

# Build cron job
LOG_FILE="${LOG_DIR}/backup_\$(date +\%Y\%m\%d_\%H\%M\%S).log"
CRON_JOB="${CRON_EXPR} ${BACKUP_SCRIPT} >> ${LOG_FILE} 2>&1"

echo ""
echo -e "${YELLOW}Cron job to be added:${NC}"
echo -e "  ${CRON_JOB}"
echo ""

read -p "Add this cron job? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}Cancelled${NC}"
    exit 0
fi

# Add to crontab
(crontab -l 2>/dev/null | grep -v "${BACKUP_SCRIPT}"; echo "$CRON_JOB") | crontab -

echo -e "${GREEN}✅ Backup schedule configured${NC}"
echo ""

# Show current crontab
echo -e "${BLUE}Current backup schedule:${NC}"
crontab -l | grep -i backup || echo "  No backup jobs found"
echo ""

# Additional recommendations
cat << EOF
${BLUE}═══════════════════════════════════════════════════════════════════════${NC}
${BLUE}BACKUP RECOMMENDATIONS${NC}
${BLUE}═══════════════════════════════════════════════════════════════════════${NC}

1. Monitor Backup Logs:
   tail -f ${LOG_DIR}/backup_*.log

2. Test Restore Process:
   ${SCRIPT_DIR}/restore.sh <backup_directory>

3. Off-site Backup:
   Configure remote backup sync to S3, Azure, or another server:

   ${YELLOW}# Example: Sync to S3${NC}
   aws s3 sync ${SCRIPT_DIR}/../backups/ s3://your-bucket/trading-backups/

   ${YELLOW}# Example: Sync to remote server${NC}
   rsync -avz ${SCRIPT_DIR}/../backups/ user@remote:/backups/trading-system/

4. Backup Alerts:
   Add monitoring to alert on backup failures:

   ${YELLOW}# Add to cron (send email on failure)${NC}
   ${CRON_EXPR} ${BACKUP_SCRIPT} || mail -s "Backup Failed" admin@example.com

5. Backup Retention:
   Default retention: 7 days
   Modify in backup.sh: RETENTION_DAILY, RETENTION_WEEKLY, RETENTION_MONTHLY

6. Verify Backups:
   Run test restores monthly to ensure backup integrity

${BLUE}═══════════════════════════════════════════════════════════════════════${NC}

EOF

echo -e "${GREEN}Backup scheduler setup complete!${NC}\n"

exit 0
