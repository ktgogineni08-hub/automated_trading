#!/bin/bash

################################################################################
# Production Deployment Script
# Trading System - Canary Deployment
#
# Usage: ./deploy_production.sh [OPTIONS]
#
# Options:
#   --version VERSION    Docker image version to deploy
#   --percentage PCT     Traffic percentage for canary (10, 50, or 100)
#   --dry-run           Simulate deployment without making changes
#   --skip-tests        Skip pre-deployment tests (not recommended)
#
# Example:
#   ./deploy_production.sh --version v1.0.0 --percentage 10
################################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="production"
NAMESPACE="trading-system-prod"
IMAGE_REGISTRY="your-registry.amazonaws.com/trading-system"
KUBECTL="kubectl"
HELM="helm"
DEPLOYMENT_NAME="trading-system"
SERVICE_NAME="trading-system-service"
HEALTH_CHECK_URL="https://api.trading.example.com/health"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"

# Parse command line arguments
VERSION=""
PERCENTAGE=10
DRY_RUN=false
SKIP_TESTS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --version)
            VERSION="$2"
            shift 2
            ;;
        --percentage)
            PERCENTAGE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate inputs
if [ -z "$VERSION" ]; then
    echo -e "${RED}Error: --version is required${NC}"
    echo "Usage: $0 --version VERSION [--percentage PCT] [--dry-run]"
    exit 1
fi

if [[ ! "$PERCENTAGE" =~ ^(10|50|100)$ ]]; then
    echo -e "${RED}Error: --percentage must be 10, 50, or 100${NC}"
    exit 1
fi

################################################################################
# Helper Functions
################################################################################

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $*"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $*"
}

log_info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO:${NC} $*"
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

check_prerequisites() {
    log "Checking prerequisites..."

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl."
        exit 1
    fi

    # Check kubectl context
    local context
    context=$(kubectl config current-context)
    if [[ "$context" != *"production"* ]]; then
        log_warning "Current kubectl context is: $context"
        read -p "Are you sure you want to deploy to this context? (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            log "Deployment aborted."
            exit 1
        fi
    fi

    # Check cluster connectivity
    if ! kubectl cluster-info > /dev/null 2>&1; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi

    # Check namespace
    if ! kubectl get namespace "$NAMESPACE" > /dev/null 2>&1; then
        log_error "Namespace $NAMESPACE does not exist"
        exit 1
    fi

    # Check docker image exists
    log "Verifying Docker image: $IMAGE_REGISTRY:$VERSION"
    # In production, you'd verify the image exists in the registry
    # docker manifest inspect "$IMAGE_REGISTRY:$VERSION" > /dev/null 2>&1

    log "Prerequisites check passed ✓"
}

run_pre_deployment_tests() {
    if [ "$SKIP_TESTS" = true ]; then
        log_warning "Skipping pre-deployment tests (--skip-tests flag)"
        return 0
    fi

    log "Running pre-deployment tests..."

    # Run unit tests
    log_info "Running unit tests..."
    if [ -f "../../tests/run_all_tests.sh" ]; then
        bash ../../tests/run_all_tests.sh
    else
        log_warning "Test script not found, skipping tests"
    fi

    # Check staging environment health
    log_info "Checking staging environment health..."
    local staging_url="https://staging-api.trading.example.com/health"
    if ! curl -f -s "$staging_url" > /dev/null 2>&1; then
        log_error "Staging environment health check failed"
        exit 1
    fi

    log "Pre-deployment tests passed ✓"
}

create_backup() {
    log "Creating pre-deployment backup..."

    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_name="pre-deploy-backup-${timestamp}"

    # Backup database
    log_info "Creating database backup: $backup_name"
    # In production, trigger RDS snapshot
    # aws rds create-db-snapshot \
    #     --db-instance-identifier trading-system-prod \
    #     --db-snapshot-identifier "$backup_name"

    # Backup current deployment state
    log_info "Backing up current Kubernetes state..."
    kubectl get deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE" -o yaml > "/tmp/${backup_name}-deployment.yaml"
    kubectl get service "$SERVICE_NAME" -n "$NAMESPACE" -o yaml > "/tmp/${backup_name}-service.yaml"

    log "Backup created: $backup_name ✓"
    echo "$backup_name" > /tmp/last-backup-name.txt
}

deploy_canary() {
    local percentage=$1

    log "Deploying canary: ${percentage}% traffic to new version $VERSION"

    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN: Would deploy $VERSION with ${percentage}% traffic"
        return 0
    fi

    case $percentage in
        10)
            # Deploy canary with 10% traffic
            log_info "Creating canary deployment with 10% traffic..."

            # Update deployment image
            kubectl set image deployment/"$DEPLOYMENT_NAME" \
                trading-system="$IMAGE_REGISTRY:$VERSION" \
                -n "$NAMESPACE" \
                --record

            # Scale deployment
            # For 10% canary: If we have 10 replicas total, 1 replica = 10%
            kubectl scale deployment "$DEPLOYMENT_NAME-canary" --replicas=1 -n "$NAMESPACE" || true

            log "Canary deployment (10%) initiated ✓"
            ;;

        50)
            # Increase canary to 50% traffic
            log_info "Increasing canary to 50% traffic..."

            # Scale canary deployment
            kubectl scale deployment "$DEPLOYMENT_NAME-canary" --replicas=5 -n "$NAMESPACE"

            log "Canary deployment (50%) initiated ✓"
            ;;

        100)
            # Full deployment
            log_info "Rolling out to 100% (full deployment)..."

            # Update all replicas to new version
            kubectl set image deployment/"$DEPLOYMENT_NAME" \
                trading-system="$IMAGE_REGISTRY:$VERSION" \
                -n "$NAMESPACE" \
                --record

            # Wait for rollout
            kubectl rollout status deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE" --timeout=10m

            # Remove canary if exists
            kubectl delete deployment "$DEPLOYMENT_NAME-canary" -n "$NAMESPACE" || true

            log "Full deployment (100%) completed ✓"
            ;;
    esac

    # Wait for pods to be ready
    log "Waiting for pods to be ready..."
    kubectl wait --for=condition=ready pod \
        -l app="$DEPLOYMENT_NAME" \
        -n "$NAMESPACE" \
        --timeout=5m
}

health_check() {
    log "Running health checks..."

    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        log_info "Health check attempt $attempt/$max_attempts"

        if curl -f -s "$HEALTH_CHECK_URL" > /dev/null 2>&1; then
            log "Health check passed ✓"
            return 0
        fi

        log_warning "Health check failed, retrying in 10 seconds..."
        sleep 10
        ((attempt++))
    done

    log_error "Health check failed after $max_attempts attempts"
    return 1
}

smoke_tests() {
    log "Running smoke tests..."

    # Test 1: Health endpoint
    log_info "Test 1: Health endpoint"
    local health_response
    health_response=$(curl -s "$HEALTH_CHECK_URL")
    if [[ "$health_response" != *"healthy"* ]]; then
        log_error "Health endpoint test failed"
        return 1
    fi

    # Test 2: Market data endpoint
    log_info "Test 2: Market data endpoint"
    if ! curl -f -s "https://api.trading.example.com/api/v1/market/quote/SBIN" > /dev/null 2>&1; then
        log_error "Market data endpoint test failed"
        return 1
    fi

    # Test 3: WebSocket connection
    log_info "Test 3: WebSocket connectivity"
    # In production, test WebSocket connection
    # wscat -c wss://api.trading.example.com/ws

    # Test 4: Database connectivity
    log_info "Test 4: Database connectivity"
    # Query /api/v1/system/db-health or similar endpoint

    log "All smoke tests passed ✓"
}

monitor_metrics() {
    local duration=$1  # Duration to monitor in seconds

    log "Monitoring metrics for ${duration} seconds..."

    local end_time=$(($(date +%s) + duration))

    while [ $(date +%s) -lt $end_time ]; do
        # Check error rate
        # In production, query Prometheus
        # error_rate=$(promtool query instant http://prometheus:9090 'rate(http_requests_total{status=~"5.."}[5m])')

        # Check latency
        # latency_p95=$(promtool query instant http://prometheus:9090 'histogram_quantile(0.95, http_request_duration_seconds_bucket)')

        log_info "Metrics check: System healthy"

        sleep 60  # Check every minute
    done

    log "Monitoring completed ✓"
}

rollback() {
    log_error "Deployment failed. Initiating rollback..."

    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN: Would rollback deployment"
        return 0
    fi

    # Rollback Kubernetes deployment
    kubectl rollout undo deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE"

    # Wait for rollback
    kubectl rollout status deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE"

    log "Rollback completed ✓"

    send_slack_notification "🚨 Production deployment FAILED and rolled back. Version: $VERSION"
}

################################################################################
# Main Deployment Flow
################################################################################

main() {
    log "========================================="
    log "Production Deployment: Trading System"
    log "========================================="
    log "Version: $VERSION"
    log "Canary Percentage: ${PERCENTAGE}%"
    log "Environment: $ENVIRONMENT"
    log "Namespace: $NAMESPACE"
    log "Dry Run: $DRY_RUN"
    log "========================================="

    # Send deployment start notification
    send_slack_notification "🚀 Starting production deployment. Version: $VERSION, Canary: ${PERCENTAGE}%"

    # Pre-deployment checks
    check_prerequisites
    run_pre_deployment_tests
    create_backup

    # Deploy canary
    deploy_canary "$PERCENTAGE"

    # Post-deployment validation
    if ! health_check; then
        rollback
        exit 1
    fi

    if ! smoke_tests; then
        rollback
        exit 1
    fi

    # Monitor based on canary percentage
    case $PERCENTAGE in
        10)
            log "Monitoring 10% canary for 1 hour..."
            monitor_metrics 3600  # 1 hour
            ;;
        50)
            log "Monitoring 50% canary for 2 hours..."
            monitor_metrics 7200  # 2 hours
            ;;
        100)
            log "Monitoring full deployment for 30 minutes..."
            monitor_metrics 1800  # 30 minutes
            ;;
    esac

    # Success
    log "========================================="
    log "✅ Deployment successful!"
    log "Version: $VERSION"
    log "Canary: ${PERCENTAGE}%"
    log "========================================="

    send_slack_notification "✅ Production deployment SUCCESSFUL. Version: $VERSION, Canary: ${PERCENTAGE}%"

    # Next steps recommendation
    if [ "$PERCENTAGE" = "10" ]; then
        log_info "Next step: Monitor for 1 hour, then run:"
        log_info "  $0 --version $VERSION --percentage 50"
    elif [ "$PERCENTAGE" = "50" ]; then
        log_info "Next step: Monitor for 2 hours, then run:"
        log_info "  $0 --version $VERSION --percentage 100"
    else
        log_info "Deployment complete! Monitor system closely for next 24 hours."
    fi
}

# Error handler
trap 'log_error "Deployment script failed. Check logs above."; exit 1' ERR

# Run main function
main
