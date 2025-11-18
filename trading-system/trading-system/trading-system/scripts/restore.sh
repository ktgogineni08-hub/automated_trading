#!/bin/bash
################################################################################
# Automated Restore Script
# Restores trading system from backup
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

# Command line arguments
BACKUP_DIR="${1:-}"
RESTORE_DATABASE="${RESTORE_DATABASE:-true}"
RESTORE_REDIS="${RESTORE_REDIS:-true}"
RESTORE_CONFIG="${RESTORE_CONFIG:-true}"
DRY_RUN="${DRY_RUN:-false}"

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

# Banner
echo -e "${BLUE}"
cat << 'BANNER'
═══════════════════════════════════════════════════════════════════════
  _____           _                  _____           _
 |  __ \         | |                / ____|         | |
 | |__) |___  ___| |_ ___  _ __ ___| (___  _   _ ___| |_ ___ _ __ ___
 |  _  // _ \/ __| __/ _ \| '__/ _ \\___ \| | | / __| __/ _ \ '_ ` _ \
 | | \ \  __/\__ \ || (_) | | |  __/____) | |_| \__ \ ||  __/ | | | | |
 |_|  \_\___||___/\__\___/|_|  \___|_____/ \__, |___/\__\___|_| |_| |_|
                                            __/ |
                                           |___/
═══════════════════════════════════════════════════════════════════════
BANNER
echo -e "${NC}"

# Show usage
usage() {
    cat << EOF
Usage: $0 <backup_directory> [OPTIONS]

Restore trading system from a backup directory.

Arguments:
  backup_directory    Path to backup directory (e.g., backups/20240101_120000)

Options:
  RESTORE_DATABASE=false   Skip database restore
  RESTORE_REDIS=false      Skip Redis restore
  RESTORE_CONFIG=false     Skip configuration restore
  DRY_RUN=true            Show what would be restored without actually doing it

Examples:
  # Full restore
  $0 backups/20240101_120000

  # Database only
  RESTORE_REDIS=false RESTORE_CONFIG=false $0 backups/20240101_120000

  # Dry run
  DRY_RUN=true $0 backups/20240101_120000

Available backups:
EOF
    ls -1 "${BACKUP_ROOT}" 2>/dev/null | grep -E "^[0-9]{8}_[0-9]{6}$" | sort -r | head -10 || echo "  No backups found"
    echo ""
}

# Validate backup directory
if [ -z "$BACKUP_DIR" ]; then
    echo -e "${RED}❌ No backup directory specified${NC}\n"
    usage
    exit 1
fi

if [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${RED}❌ Backup directory not found: ${BACKUP_DIR}${NC}\n"
    usage
    exit 1
fi

# Show backup info
echo -e "${BLUE}Backup Directory: ${BACKUP_DIR}${NC}"
echo -e "${BLUE}Dry Run: ${DRY_RUN}${NC}\n"

if [ -f "${BACKUP_DIR}/metadata/backup_info.json" ]; then
    echo -e "${YELLOW}Backup Information:${NC}"
    if command -v jq &> /dev/null; then
        cat "${BACKUP_DIR}/metadata/backup_info.json" | jq .
    else
        cat "${BACKUP_DIR}/metadata/backup_info.json"
    fi
    echo ""
fi

# Confirmation
if [ "$DRY_RUN" = "false" ]; then
    echo -e "${RED}⚠️  WARNING: This will overwrite existing data!${NC}"
    echo -e "${YELLOW}Components to restore:${NC}"
    [ "$RESTORE_DATABASE" = "true" ] && echo -e "  • PostgreSQL Database"
    [ "$RESTORE_REDIS" = "true" ] && echo -e "  • Redis Data"
    [ "$RESTORE_CONFIG" = "true" ] && echo -e "  • Configuration Files"
    echo ""

    read -p "Are you sure you want to continue? (yes/no): " -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo -e "${YELLOW}Restore cancelled${NC}"
        exit 0
    fi
fi

# Function: Restore Database
restore_database() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}DATABASE RESTORE${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}\n"

    # Find backup file
    local backup_file=$(find "${BACKUP_DIR}/database" -name "${DB_NAME}_*.sql.gz" -type f | head -1)

    if [ -z "$backup_file" ]; then
        echo -e "${RED}❌ No database backup found${NC}\n"
        return 1
    fi

    echo -e "${YELLOW}Found database backup: $(basename ${backup_file})${NC}"
    local size=$(du -h "${backup_file}" | cut -f1)
    echo -e "  Size: ${size}"

    # Verify checksum
    if [ -f "${backup_file}.sha256" ]; then
        echo -e "${YELLOW}Verifying checksum...${NC}"
        cd "$(dirname ${backup_file})"
        if sha256sum -c "$(basename ${backup_file}).sha256" &> /dev/null; then
            echo -e "${GREEN}✅ Checksum verified${NC}"
        else
            echo -e "${RED}❌ Checksum verification failed${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️  No checksum file found, skipping verification${NC}"
    fi

    if [ "$DRY_RUN" = "true" ]; then
        echo -e "${YELLOW}[DRY RUN] Would restore database from ${backup_file}${NC}\n"
        return 0
    fi

    # Check if container is running
    if ! docker ps | grep -q trading-postgres; then
        echo -e "${RED}❌ PostgreSQL container not running${NC}"
        echo -e "${YELLOW}Start it with: docker-compose up -d postgres${NC}\n"
        return 1
    fi

    # Stop trading system to prevent writes
    echo -e "${YELLOW}Stopping trading system...${NC}"
    docker-compose stop trading-system 2>/dev/null || true

    # Terminate existing connections
    echo -e "${YELLOW}Terminating existing database connections...${NC}"
    docker exec trading-postgres psql -U "${DB_USER}" -d postgres -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${DB_NAME}' AND pid <> pg_backend_pid();" \
        2>/dev/null || true

    # Drop and recreate database
    echo -e "${YELLOW}Dropping existing database...${NC}"
    docker exec trading-postgres psql -U "${DB_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${DB_NAME};" || true

    # Restore from backup
    echo -e "${YELLOW}Restoring database...${NC}"
    gunzip -c "${backup_file}" | docker exec -i trading-postgres psql -U "${DB_USER}" -d postgres

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Database restored successfully${NC}"

        # Verify restore
        echo -e "${YELLOW}Verifying restore...${NC}"
        local table_count=$(docker exec trading-postgres psql -U "${DB_USER}" -d "${DB_NAME}" -t -c \
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';")

        echo -e "  Tables found: ${table_count}"

        if [ "${table_count}" -gt 0 ]; then
            echo -e "${GREEN}✅ Restore verification passed${NC}"
        else
            echo -e "${RED}❌ Restore verification failed - no tables found${NC}"
            return 1
        fi
    else
        echo -e "${RED}❌ Database restore failed${NC}"
        return 1
    fi

    echo ""
}

# Function: Restore Redis
restore_redis() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}REDIS RESTORE${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}\n"

    # Find backup file
    local backup_file=$(find "${BACKUP_DIR}/redis" -name "dump_*.rdb.gz" -type f | head -1)

    if [ -z "$backup_file" ]; then
        echo -e "${RED}❌ No Redis backup found${NC}\n"
        return 1
    fi

    echo -e "${YELLOW}Found Redis backup: $(basename ${backup_file})${NC}"
    local size=$(du -h "${backup_file}" | cut -f1)
    echo -e "  Size: ${size}"

    # Verify checksum
    if [ -f "${backup_file}.sha256" ]; then
        echo -e "${YELLOW}Verifying checksum...${NC}"
        cd "$(dirname ${backup_file})"
        if sha256sum -c "$(basename ${backup_file}).sha256" &> /dev/null; then
            echo -e "${GREEN}✅ Checksum verified${NC}"
        else
            echo -e "${RED}❌ Checksum verification failed${NC}"
            return 1
        fi
    fi

    if [ "$DRY_RUN" = "true" ]; then
        echo -e "${YELLOW}[DRY RUN] Would restore Redis from ${backup_file}${NC}\n"
        return 0
    fi

    # Check if container is running
    if ! docker ps | grep -q trading-redis; then
        echo -e "${RED}❌ Redis container not running${NC}"
        echo -e "${YELLOW}Start it with: docker-compose up -d redis${NC}\n"
        return 1
    fi

    # Stop trading system
    echo -e "${YELLOW}Stopping trading system...${NC}"
    docker-compose stop trading-system 2>/dev/null || true

    # Stop Redis
    echo -e "${YELLOW}Stopping Redis...${NC}"
    docker-compose stop redis

    # Extract and copy dump.rdb
    echo -e "${YELLOW}Restoring Redis data...${NC}"
    local temp_dir=$(mktemp -d)
    gunzip -c "${backup_file}" > "${temp_dir}/dump.rdb"
    docker cp "${temp_dir}/dump.rdb" trading-redis:/data/dump.rdb
    rm -rf "${temp_dir}"

    # Start Redis
    echo -e "${YELLOW}Starting Redis...${NC}"
    docker-compose start redis

    # Wait for Redis to be ready
    echo -e "${YELLOW}Waiting for Redis to be ready...${NC}"
    sleep 3

    # Verify
    if [ -n "${REDIS_PASSWORD}" ]; then
        local key_count=$(docker exec trading-redis redis-cli -a "${REDIS_PASSWORD}" DBSIZE 2>/dev/null | grep -oE '[0-9]+' || echo 0)
    else
        local key_count=$(docker exec trading-redis redis-cli DBSIZE 2>/dev/null | grep -oE '[0-9]+' || echo 0)
    fi

    echo -e "  Keys found: ${key_count}"
    echo -e "${GREEN}✅ Redis restored successfully${NC}\n"
}

# Function: Restore Configuration
restore_config() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}CONFIGURATION RESTORE${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}\n"

    # Find config backup
    local config_backup=$(find "${BACKUP_DIR}/config" -name "config_*.tar.gz" -type f | head -1)

    if [ -z "$config_backup" ]; then
        echo -e "${RED}❌ No configuration backup found${NC}\n"
        return 1
    fi

    echo -e "${YELLOW}Found configuration backup: $(basename ${config_backup})${NC}"

    if [ "$DRY_RUN" = "true" ]; then
        echo -e "${YELLOW}[DRY RUN] Would restore configuration from ${config_backup}${NC}"
        echo -e "${YELLOW}[DRY RUN] Contents:${NC}"
        tar -tzf "${config_backup}" | head -20
        echo ""
        return 0
    fi

    # Backup current config
    echo -e "${YELLOW}Backing up current configuration...${NC}"
    local backup_timestamp=$(date +%Y%m%d_%H%M%S)
    mkdir -p "${PROJECT_ROOT}/config_backups"
    [ -f "${PROJECT_ROOT}/.env" ] && cp "${PROJECT_ROOT}/.env" "${PROJECT_ROOT}/config_backups/.env.${backup_timestamp}"

    # Extract config
    echo -e "${YELLOW}Restoring configuration files...${NC}"
    local temp_dir=$(mktemp -d)
    tar -xzf "${config_backup}" -C "${temp_dir}"

    # Restore files selectively
    if [ -f "${temp_dir}/config/.env" ]; then
        echo -e "  → .env"
        cp "${temp_dir}/config/.env" "${PROJECT_ROOT}/"
    fi

    if [ -f "${temp_dir}/config/docker-compose.yml" ]; then
        echo -e "  → docker-compose.yml"
        cp "${temp_dir}/config/docker-compose.yml" "${PROJECT_ROOT}/"
    fi

    if [ -d "${temp_dir}/config/prometheus" ]; then
        echo -e "  → prometheus/"
        cp -r "${temp_dir}/config/prometheus" "${PROJECT_ROOT}/"
    fi

    if [ -d "${temp_dir}/config/dashboards" ]; then
        echo -e "  → dashboards/"
        cp -r "${temp_dir}/config/dashboards" "${PROJECT_ROOT}/"
    fi

    rm -rf "${temp_dir}"

    echo -e "${GREEN}✅ Configuration restored successfully${NC}"
    echo -e "${YELLOW}⚠️  Previous config backed up to: config_backups/${NC}\n"
}

# Function: Post-restore steps
post_restore() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}POST-RESTORE STEPS${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}\n"

    if [ "$DRY_RUN" = "true" ]; then
        echo -e "${YELLOW}[DRY RUN] Post-restore steps skipped${NC}\n"
        return 0
    fi

    echo -e "${YELLOW}Starting services...${NC}"
    docker-compose up -d

    echo -e "${YELLOW}Waiting for services to be ready...${NC}"
    sleep 5

    # Health check
    echo -e "${YELLOW}Running health checks...${NC}"
    if docker-compose exec -T trading-system python3 -c "import trading_utils; print('OK')" 2>/dev/null; then
        echo -e "${GREEN}✅ Trading system healthy${NC}"
    else
        echo -e "${YELLOW}⚠️  Trading system not responding, may need more time${NC}"
    fi

    echo ""
}

# Main execution
main() {
    local start_time=$(date +%s)

    # Execute restores
    [ "$RESTORE_DATABASE" = "true" ] && restore_database
    [ "$RESTORE_REDIS" = "true" ] && restore_redis
    [ "$RESTORE_CONFIG" = "true" ] && restore_config

    # Post-restore
    [ "$DRY_RUN" = "false" ] && post_restore

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}RESTORE SUMMARY${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}\n"

    echo -e "${GREEN}Restore completed in ${duration} seconds${NC}"

    if [ "$DRY_RUN" = "false" ]; then
        echo -e "\n${YELLOW}Next steps:${NC}"
        echo -e "  1. Verify data integrity"
        echo -e "  2. Check application logs: docker-compose logs -f trading-system"
        echo -e "  3. Test trading functionality"
        echo -e "  4. Monitor system health: http://localhost:3000"
    fi

    echo ""
}

# Run main
main

exit 0
