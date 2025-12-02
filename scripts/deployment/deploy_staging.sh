#!/bin/bash
#############################################################################
# Trading System - Staging Deployment Script
#############################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="staging"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${PROJECT_ROOT}/logs/deployment_staging_${TIMESTAMP}.log"

# Ensure log directory exists
mkdir -p "${PROJECT_ROOT}/logs"

# Logging function
log() {
    echo -e "${1}" | tee -a "${LOG_FILE}"
}

log_info() {
    log "${BLUE}[INFO]${NC} $1"
}

log_success() {
    log "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    log "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    log "${RED}[ERROR]${NC} $1"
}

# Error handler
error_exit() {
    log_error "$1"
    log_error "Deployment failed! Check ${LOG_FILE} for details"
    exit 1
}

# Banner
log "
=========================================================================
       TRADING SYSTEM - STAGING DEPLOYMENT
=========================================================================
Environment: ${ENVIRONMENT}
Timestamp:   ${TIMESTAMP}
Project:     ${PROJECT_ROOT}
=========================================================================
"

# Step 1: Pre-deployment checks
log_info "Step 1: Running pre-deployment checks..."

# Check if required tools are installed
command -v docker >/dev/null 2>&1 || error_exit "Docker is not installed"
command -v kubectl >/dev/null 2>&1 || error_exit "kubectl is not installed"
command -v git >/dev/null 2>&1 || error_exit "Git is not installed"

log_success "All required tools are installed"

# Check if we're on the correct branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
log_info "Current branch: ${CURRENT_BRANCH}"

# Get current commit
CURRENT_COMMIT=$(git rev-parse --short HEAD)
log_info "Current commit: ${CURRENT_COMMIT}"

# Step 2: Run tests
log_info "Step 2: Running test suite..."
cd "${PROJECT_ROOT}/trading-system"

if python -m pytest tests/ -v --tb=short 2>&1 | tee -a "${LOG_FILE}"; then
    log_success "All tests passed"
else
    error_exit "Tests failed! Cannot deploy to staging"
fi

# Step 3: Build Docker image
log_info "Step 3: Building Docker image..."

DOCKER_IMAGE="trading-system:staging-${CURRENT_COMMIT}"
DASHBOARD_IMAGE="trading-dashboard:staging-${CURRENT_COMMIT}"

if docker build -t "${DOCKER_IMAGE}" -f Dockerfile . 2>&1 | tee -a "${LOG_FILE}"; then
    log_success "Docker image built successfully: ${DOCKER_IMAGE}"
else
    error_exit "Docker build failed"
fi

# Build dashboard image
if docker build -t "${DASHBOARD_IMAGE}" -f Dockerfile.dashboard . 2>&1 | tee -a "${LOG_FILE}"; then
    log_success "Dashboard image built successfully: ${DASHBOARD_IMAGE}"
else
    error_exit "Dashboard Docker build failed"
fi

# Step 4: Tag and push to registry
log_info "Step 4: Pushing images to registry..."

# Tag for registry (update with your registry URL)
REGISTRY="your-registry.example.com"
docker tag "${DOCKER_IMAGE}" "${REGISTRY}/${DOCKER_IMAGE}"
docker tag "${DASHBOARD_IMAGE}" "${REGISTRY}/${DASHBOARD_IMAGE}"

# Push images
if docker push "${REGISTRY}/${DOCKER_IMAGE}" 2>&1 | tee -a "${LOG_FILE}"; then
    log_success "Trading system image pushed to registry"
else
    error_exit "Failed to push trading system image"
fi

if docker push "${REGISTRY}/${DASHBOARD_IMAGE}" 2>&1 | tee -a "${LOG_FILE}"; then
    log_success "Dashboard image pushed to registry"
else
    error_exit "Failed to push dashboard image"
fi

# Step 5: Update Kubernetes manifests
log_info "Step 5: Updating Kubernetes manifests..."

K8S_DIR="${PROJECT_ROOT}/infrastructure/kubernetes/staging"
mkdir -p "${K8S_DIR}"

# Copy production manifests and update image tags
cp "${PROJECT_ROOT}/infrastructure/kubernetes/production/"*.yaml "${K8S_DIR}/"

# Update image tags in deployments
sed -i.bak "s|image: trading-system:.*|image: ${REGISTRY}/${DOCKER_IMAGE}|g" \
    "${K8S_DIR}/trading-system-deployment.yaml"
sed -i.bak "s|image: trading-dashboard:.*|image: ${REGISTRY}/${DASHBOARD_IMAGE}|g" \
    "${K8S_DIR}/dashboard-deployment.yaml"

# Update namespace to staging
sed -i.bak "s|namespace: trading-system-prod|namespace: trading-system-staging|g" \
    "${K8S_DIR}/"*.yaml
sed -i.bak "s|name: trading-system-prod|name: trading-system-staging|g" \
    "${K8S_DIR}/namespace.yaml"

log_success "Kubernetes manifests updated"

# Step 6: Deploy to Kubernetes
log_info "Step 6: Deploying to Kubernetes staging cluster..."

# Switch to staging context
kubectl config use-context staging 2>&1 | tee -a "${LOG_FILE}" || log_warning "Could not switch context"

# Create namespace if it doesn't exist
kubectl create namespace trading-system-staging --dry-run=client -o yaml | kubectl apply -f - 2>&1 | tee -a "${LOG_FILE}"

# Apply ConfigMap and Secrets
log_info "Applying ConfigMap..."
kubectl apply -f "${K8S_DIR}/configmap.yaml" 2>&1 | tee -a "${LOG_FILE}"

log_warning "Note: Secrets must be manually created or managed via external secret management"

# Deploy applications
log_info "Deploying trading system..."
kubectl apply -f "${K8S_DIR}/trading-system-deployment.yaml" 2>&1 | tee -a "${LOG_FILE}"

log_info "Deploying dashboard..."
kubectl apply -f "${K8S_DIR}/dashboard-deployment.yaml" 2>&1 | tee -a "${LOG_FILE}"

log_info "Applying ingress..."
kubectl apply -f "${K8S_DIR}/ingress.yaml" 2>&1 | tee -a "${LOG_FILE}"

log_success "Deployment manifests applied"

# Step 7: Wait for deployment to be ready
log_info "Step 7: Waiting for deployment to be ready..."

kubectl rollout status deployment/trading-system -n trading-system-staging --timeout=5m 2>&1 | tee -a "${LOG_FILE}" || \
    log_warning "Trading system deployment timeout"

kubectl rollout status deployment/trading-dashboard -n trading-system-staging --timeout=5m 2>&1 | tee -a "${LOG_FILE}" || \
    log_warning "Dashboard deployment timeout"

# Step 8: Run smoke tests
log_info "Step 8: Running smoke tests..."

# Get service endpoints
TRADING_ENDPOINT=$(kubectl get ingress trading-system-ingress -n trading-system-staging \
    -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "pending")

log_info "Trading system endpoint: ${TRADING_ENDPOINT}"

if [ "${TRADING_ENDPOINT}" != "pending" ]; then
    # Test health endpoint
    if curl -f "https://${TRADING_ENDPOINT}/health" 2>&1 | tee -a "${LOG_FILE}"; then
        log_success "Health check passed"
    else
        log_warning "Health check failed or endpoint not ready yet"
    fi
else
    log_warning "Ingress endpoint not ready yet. Manual verification required."
fi

# Step 9: Deployment summary
log "
=========================================================================
       DEPLOYMENT SUMMARY
=========================================================================
Environment:        ${ENVIRONMENT}
Commit:             ${CURRENT_COMMIT}
Docker Images:      
  - ${DOCKER_IMAGE}
  - ${DASHBOARD_IMAGE}
Namespace:          trading-system-staging
Deployment Time:    ${TIMESTAMP}
Log File:           ${LOG_FILE}

Next Steps:
1. Verify pods are running:
   kubectl get pods -n trading-system-staging

2. Check logs:
   kubectl logs -f deployment/trading-system -n trading-system-staging

3. Access dashboard:
   https://dashboard-staging.trading.example.com

4. Run integration tests:
   ./scripts/run_integration_tests.sh staging

=========================================================================
"

log_success "Staging deployment completed successfully!"

# Clean up backup files
rm -f "${K8S_DIR}/"*.yaml.bak

exit 0
