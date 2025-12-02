#!/bin/bash
################################################################################
# Automated Backup Script
# Performs comprehensive backups of the trading system
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
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_ROOT="${BACKUP_ROOT:-${PROJECT_ROOT}/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"

# Retention settings (days)
RETENTION_DAILY=7
RETENTION_WEEKLY=30
RETENTION_MONTHLY=90

# Load environment
if [ -f "${PROJECT_ROOT}/.env" ]; then
    set -a
    source "${PROJECT_ROOT}/.env"
    set +a
fi

# Database configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-trading_db}"
DB_USER="${DB_USER:-trading_user}"
DB_PASSWORD="${DB_PASSWORD:-}"

# Redis configuration
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"

# Backup types
BACKUP_DATABASE="${BACKUP_DATABASE:-true}"
BACKUP_REDIS="${BACKUP_REDIS:-true}"
BACKUP_CONFIG="${BACKUP_CONFIG:-true}"
BACKUP_LOGS="${BACKUP_LOGS:-true}"

# Banner
echo -e "${BLUE}"
cat << 'BANNER'
═══════════════════════════════════════════════════════════════════════
  ____             _                  _____           _
 |  _ \           | |                / ____|         | |
 | |_) | __ _  ___| | ___   _ _ __ | (___  _   _ ___| |_ ___ _ __ ___
 |  _ < / _` |/ __| |/ / | | | '_ \ \___ \| | | / __| __/ _ \ '_ ` _ \
 | |_) | (_| | (__|   <| |_| | |_) |____) | |_| \__ \ ||  __/ | | | | |
 |____/ \__,_|\___|_|\_\\__,_| .__/|_____/ \__, |___/\__\___|_| |_| |_|
                             | |            __/ |
                             |_|           |___/
═══════════════════════════════════════════════════════════════════════
BANNER
echo -e "${NC}"

echo -e "${BLUE}Backup Directory: ${BACKUP_DIR}${NC}"
echo -e "${BLUE}Timestamp: ${TIMESTAMP}${NC}\n"

# Create backup directory
echo -e "${YELLOW}Creating backup directory...${NC}"
mkdir -p "${BACKUP_DIR}"/{database,redis,config,logs,metadata}
echo -e "${GREEN}✅ Backup directory created${NC}\n"

# Backup metadata
echo -e "${YELLOW}Writing backup metadata...${NC}"
cat > "${BACKUP_DIR}/metadata/backup_info.json" << EOF
{
  "timestamp": "${TIMESTAMP}",
  "date": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "hostname": "$(hostname)",
  "user": "$(whoami)",
  "backup_type": "full",
  "components": {
    "database": ${BACKUP_DATABASE},
    "redis": ${BACKUP_REDIS},
    "config": ${BACKUP_CONFIG},
    "logs": ${BACKUP_LOGS}
  },
  "versions": {
    "postgres": "$(docker exec trading-postgres psql --version 2>/dev/null | head -1 || echo 'unknown')",
    "redis": "$(docker exec trading-redis redis-server --version 2>/dev/null || echo 'unknown')"
  }
}
EOF
echo -e "${GREEN}✅ Metadata written${NC}\n"

# Function: Backup Database
backup_database() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}DATABASE BACKUP${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}\n"

    local backup_file="${BACKUP_DIR}/database/${DB_NAME}_${TIMESTAMP}.sql"
    local backup_file_compressed="${backup_file}.gz"

    echo -e "${YELLOW}Starting PostgreSQL backup...${NC}"
    echo -e "  Database: ${DB_NAME}"
    echo -e "  Host: ${DB_HOST}:${DB_PORT}"
    echo -e "  File: $(basename ${backup_file_compressed})"
    echo ""

    # Use pg_dump via docker exec
    if docker ps | grep -q trading-postgres; then
        docker exec trading-postgres pg_dump \
            -U "${DB_USER}" \
            -d "${DB_NAME}" \
            --clean \
            --if-exists \
            --create \
            --format=plain \
            --verbose \
            2>&1 | gzip > "${backup_file_compressed}"

        if [ $? -eq 0 ]; then
            local size=$(du -h "${backup_file_compressed}" | cut -f1)
            echo -e "${GREEN}✅ Database backup completed (${size})${NC}"

            # Verify backup
            echo -e "${YELLOW}Verifying backup integrity...${NC}"
            if gunzip -t "${backup_file_compressed}" 2>/dev/null; then
                echo -e "${GREEN}✅ Backup integrity verified${NC}"
            else
                echo -e "${RED}❌ Backup integrity check failed${NC}"
                return 1
            fi

            # Generate checksum
            echo -e "${YELLOW}Generating checksum...${NC}"
            cd "${BACKUP_DIR}/database"
            sha256sum "$(basename ${backup_file_compressed})" > "$(basename ${backup_file_compressed}).sha256"
            echo -e "${GREEN}✅ Checksum generated${NC}"
        else
            echo -e "${RED}❌ Database backup failed${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️  PostgreSQL container not running, skipping database backup${NC}"
    fi

    echo ""
}

# Function: Backup Redis
backup_redis() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}REDIS BACKUP${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}\n"

    local backup_file="${BACKUP_DIR}/redis/dump_${TIMESTAMP}.rdb"
    local backup_file_compressed="${backup_file}.gz"

    echo -e "${YELLOW}Starting Redis backup...${NC}"
    echo -e "  Host: ${REDIS_HOST}:${REDIS_PORT}"
    echo -e "  File: $(basename ${backup_file_compressed})"
    echo ""

    if docker ps | grep -q trading-redis; then
        # Trigger Redis save
        echo -e "${YELLOW}Triggering Redis BGSAVE...${NC}"
        if [ -n "${REDIS_PASSWORD}" ]; then
            docker exec trading-redis redis-cli -a "${REDIS_PASSWORD}" BGSAVE > /dev/null 2>&1
        else
            docker exec trading-redis redis-cli BGSAVE > /dev/null 2>&1
        fi

        # Wait for save to complete
        sleep 2
        while docker exec trading-redis redis-cli LASTSAVE 2>/dev/null | grep -q "loading"; do
            echo -e "${YELLOW}  Waiting for BGSAVE to complete...${NC}"
            sleep 1
        done

        # Copy dump.rdb
        docker cp trading-redis:/data/dump.rdb "${backup_file}"

        if [ -f "${backup_file}" ]; then
            # Compress
            gzip "${backup_file}"

            local size=$(du -h "${backup_file_compressed}" | cut -f1)
            echo -e "${GREEN}✅ Redis backup completed (${size})${NC}"

            # Generate checksum
            echo -e "${YELLOW}Generating checksum...${NC}"
            cd "${BACKUP_DIR}/redis"
            sha256sum "$(basename ${backup_file_compressed})" > "$(basename ${backup_file_compressed}).sha256"
            echo -e "${GREEN}✅ Checksum generated${NC}"
        else
            echo -e "${RED}❌ Redis backup failed${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️  Redis container not running, skipping Redis backup${NC}"
    fi

    echo ""
}

# Function: Backup Configuration
backup_config() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}CONFIGURATION BACKUP${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}\n"

    echo -e "${YELLOW}Backing up configuration files...${NC}"

    # Environment files
    if [ -f "${PROJECT_ROOT}/.env" ]; then
        echo -e "  → .env"
        cp "${PROJECT_ROOT}/.env" "${BACKUP_DIR}/config/"
    fi

    if [ -f "${PROJECT_ROOT}/.env.production" ]; then
        echo -e "  → .env.production"
        cp "${PROJECT_ROOT}/.env.production" "${BACKUP_DIR}/config/"
    fi

    # Docker Compose
    if [ -f "${PROJECT_ROOT}/docker-compose.yml" ]; then
        echo -e "  → docker-compose.yml"
        cp "${PROJECT_ROOT}/docker-compose.yml" "${BACKUP_DIR}/config/"
    fi

    # Prometheus configuration
    if [ -d "${PROJECT_ROOT}/prometheus" ]; then
        echo -e "  → prometheus/"
        cp -r "${PROJECT_ROOT}/prometheus" "${BACKUP_DIR}/config/"
    fi

    # Grafana dashboards
    if [ -d "${PROJECT_ROOT}/dashboards" ]; then
        echo -e "  → dashboards/"
        cp -r "${PROJECT_ROOT}/dashboards" "${BACKUP_DIR}/config/"
    fi

    # Certificates
    if [ -d "${PROJECT_ROOT}/certs" ]; then
        echo -e "  → certs/"
        cp -r "${PROJECT_ROOT}/certs" "${BACKUP_DIR}/config/"
    fi

    # Application config
    if [ -d "${PROJECT_ROOT}/config" ]; then
        echo -e "  → config/"
        cp -r "${PROJECT_ROOT}/config" "${BACKUP_DIR}/config/"
    fi

    # Compress config directory
    echo -e "${YELLOW}Compressing configuration...${NC}"
    cd "${BACKUP_DIR}"
    tar -czf "config_${TIMESTAMP}.tar.gz" config/
    rm -rf config/
    mkdir -p config
    mv "config_${TIMESTAMP}.tar.gz" config/

    local size=$(du -h "${BACKUP_DIR}/config/config_${TIMESTAMP}.tar.gz" | cut -f1)
    echo -e "${GREEN}✅ Configuration backup completed (${size})${NC}\n"
}

# Function: Backup Logs
backup_logs() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}LOGS BACKUP${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}\n"

    echo -e "${YELLOW}Backing up recent logs...${NC}"

    # Application logs (last 7 days)
    if [ -d "${PROJECT_ROOT}/logs" ]; then
        echo -e "  → Application logs (last 7 days)"
        find "${PROJECT_ROOT}/logs" -type f -mtime -7 -exec cp {} "${BACKUP_DIR}/logs/" \; 2>/dev/null || true
    fi

    # Container logs
    echo -e "  → Container logs"
    for container in trading-system trading-postgres trading-redis; do
        if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            docker logs --tail 10000 "${container}" > "${BACKUP_DIR}/logs/${container}_${TIMESTAMP}.log" 2>&1 || true
        fi
    done

    # Compress logs
    if [ "$(ls -A ${BACKUP_DIR}/logs)" ]; then
        echo -e "${YELLOW}Compressing logs...${NC}"
        cd "${BACKUP_DIR}"
        tar -czf "logs_${TIMESTAMP}.tar.gz" logs/
        rm -rf logs/
        mkdir -p logs
        mv "logs_${TIMESTAMP}.tar.gz" logs/

        local size=$(du -h "${BACKUP_DIR}/logs/logs_${TIMESTAMP}.tar.gz" | cut -f1)
        echo -e "${GREEN}✅ Logs backup completed (${size})${NC}"
    else
        echo -e "${YELLOW}⚠️  No logs to backup${NC}"
    fi

    echo ""
}

# Function: Cleanup old backups
cleanup_old_backups() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}CLEANUP OLD BACKUPS${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}\n"

    echo -e "${YELLOW}Cleaning up old backups...${NC}"

    # Keep daily backups for RETENTION_DAILY days
    echo -e "  → Removing daily backups older than ${RETENTION_DAILY} days"
    find "${BACKUP_ROOT}" -maxdepth 1 -type d -name "20*" -mtime +${RETENTION_DAILY} -exec rm -rf {} \; 2>/dev/null || true

    # List remaining backups
    echo -e "\n${YELLOW}Remaining backups:${NC}"
    du -sh "${BACKUP_ROOT}"/20* 2>/dev/null | sort -r | head -10 || echo "  No backups found"

    echo -e "\n${GREEN}✅ Cleanup completed${NC}\n"
}

# Function: Create backup summary
create_summary() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}BACKUP SUMMARY${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}\n"

    local total_size=$(du -sh "${BACKUP_DIR}" | cut -f1)

    cat > "${BACKUP_DIR}/metadata/backup_summary.txt" << EOF
Backup Summary
══════════════════════════════════════════════════════════════════════

Backup Time: $(date)
Backup Directory: ${BACKUP_DIR}
Total Size: ${total_size}

Components Backed Up:
$([ "$BACKUP_DATABASE" = "true" ] && echo "  ✅ PostgreSQL Database" || echo "  ⊘ PostgreSQL Database")
$([ "$BACKUP_REDIS" = "true" ] && echo "  ✅ Redis Data" || echo "  ⊘ Redis Data")
$([ "$BACKUP_CONFIG" = "true" ] && echo "  ✅ Configuration Files" || echo "  ⊘ Configuration Files")
$([ "$BACKUP_LOGS" = "true" ] && echo "  ✅ Application Logs" || echo "  ⊘ Application Logs")

Backup Contents:
$(tree -L 2 "${BACKUP_DIR}" 2>/dev/null || find "${BACKUP_DIR}" -maxdepth 2 -type f -o -type d)

Restore Instructions:
  See: ${PROJECT_ROOT}/scripts/restore.sh
  Or: ${PROJECT_ROOT}/docs/BACKUP_RECOVERY.md

═══════════════════════════════════════════════════════════════════════
EOF

    cat "${BACKUP_DIR}/metadata/backup_summary.txt"
}

# Main execution
main() {
    local start_time=$(date +%s)

    # Execute backups
    [ "$BACKUP_DATABASE" = "true" ] && backup_database
    [ "$BACKUP_REDIS" = "true" ] && backup_redis
    [ "$BACKUP_CONFIG" = "true" ] && backup_config
    [ "$BACKUP_LOGS" = "true" ] && backup_logs

    # Cleanup
    cleanup_old_backups

    # Summary
    create_summary

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    echo -e "${GREEN}Backup completed in ${duration} seconds${NC}"
    echo -e "${GREEN}Backup location: ${BACKUP_DIR}${NC}\n"
}

# Run main
main

exit 0
