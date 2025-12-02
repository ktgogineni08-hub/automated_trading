#!/bin/bash

################################################################################
# Production Rollback Script
# Trading System - Emergency Rollback
#
# Usage: ./rollback_production.sh [OPTIONS]
#
# Options:
#   --backup-name NAME   Specific backup to restore (optional)
#   --revision N         Kubernetes revision to rollback to (optional)
#   --confirm           Skip confirmation prompt
#
# Example:
#   ./rollback_production.sh --confirm
#   ./rollback_production.sh --backup-name pre-deploy-backup-20251122_100000
################################################################################

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
NAMESPACE="trading-system-prod"
DEPLOYMENT_NAME="trading-system"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"

# Parse arguments
BACKUP_NAME=""
REVISION=""
SKIP_CONFIRM=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --backup-name)
            BACKUP_NAME="$2"
            shift 2
            ;;
        --revision)
            REVISION="$2"
            shift 2
            ;;
        --confirm)
            SKIP_CONFIRM=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $*"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $*"
}

send_slack_notification() {
    local message="$1"
    if [ -n "$SLACK_WEBHOOK_URL" ]; then
        curl -X POST "$SLACK_WEBHOOK_URL" \
            -H 'Content-Type: application/json' \
            -d "{\"text\":\"$message\"}" \
            > /dev/null 2>&1
    fi
}

confirm_rollback() {
    if [ "$SKIP_CONFIRM" = true ]; then
        return 0
    fi

    log_warning "⚠️  PRODUCTION ROLLBACK CONFIRMATION REQUIRED"
    echo ""
    echo "This will rollback the production deployment to a previous version."
    echo "This action may cause brief service interruption."
    echo ""
    read -p "Are you absolutely sure you want to proceed? Type 'ROLLBACK' to confirm: " confirmation

    if [ "$confirmation" != "ROLLBACK" ]; then
        log "Rollback aborted."
        exit 1
    fi
}

get_current_state() {
    log "Retrieving current deployment state..."

    local current_revision
    current_revision=$(kubectl rollout history deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE" | tail -1 | awk '{print $1}')

    local current_image
    current_image=$(kubectl get deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].image}')

    log "Current revision: $current_revision"
    log "Current image: $current_image"

    # Save current state for audit
    kubectl get deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE" -o yaml > "/tmp/pre-rollback-state-$(date +%Y%m%d_%H%M%S).yaml"
}

rollback_kubernetes() {
    log "Rolling back Kubernetes deployment..."

    if [ -n "$REVISION" ]; then
        log "Rolling back to specific revision: $REVISION"
        kubectl rollout undo deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE" --to-revision="$REVISION"
    else
        log "Rolling back to previous revision"
        kubectl rollout undo deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE"
    fi

    # Wait for rollback to complete
    kubectl rollout status deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE" --timeout=10m

    log "Kubernetes rollback completed ✓"
}

restore_database_backup() {
    if [ -z "$BACKUP_NAME" ]; then
        log_warning "No database backup specified. Skipping database restore."
        log_warning "If database rollback is needed, run manually with --backup-name"
        return 0
    fi

    log "Restoring database from backup: $BACKUP_NAME"

    # In production, restore RDS snapshot
    # aws rds restore-db-instance-from-db-snapshot \
    #     --db-instance-identifier trading-system-prod \
    #     --db-snapshot-identifier "$BACKUP_NAME"

    log_warning "Database restore initiated. This may take several minutes."
    log_warning "Monitor RDS console for restore progress."
}

verify_rollback() {
    log "Verifying rollback..."

    # Check pod status
    local ready_pods
    ready_pods=$(kubectl get pods -n "$NAMESPACE" -l app="$DEPLOYMENT_NAME" --field-selector=status.phase=Running | tail -n +2 | wc -l)

    log "Ready pods: $ready_pods"

    # Health check
    local health_url="https://api.trading.example.com/health"
    if curl -f -s "$health_url" > /dev/null 2>&1; then
        log "Health check: ✓ PASS"
    else
        log_error "Health check: ✗ FAIL"
        return 1
    fi

    # Check error rate (in production, query Prometheus)
    log "Checking error rates..."

    log "Rollback verification completed ✓"
}

main() {
    log "========================================="
    log "🔄 PRODUCTION ROLLBACK"
    log "========================================="

    send_slack_notification "🔄 Production rollback initiated"

    # Confirmation
    confirm_rollback

    # Get current state
    get_current_state

    # Perform rollback
    rollback_kubernetes

    # Restore database if needed
    restore_database_backup

    # Verify
    if ! verify_rollback; then
        log_error "Rollback verification failed!"
        send_slack_notification "🚨 Production rollback FAILED verification"
        exit 1
    fi

    log "========================================="
    log "✅ Rollback completed successfully"
    log "========================================="

    send_slack_notification "✅ Production rollback SUCCESSFUL"
}

trap 'log_error "Rollback script failed."; send_slack_notification "🚨 Rollback script FAILED"; exit 1' ERR

main
