#!/bin/bash
# Automated Deployment Script for Trading System
# Phase 4 Tier 5: GitOps & Automation
#
# Usage:
#   ./deploy.sh <environment> <region>
#
# Examples:
#   ./deploy.sh prod us-east-1
#   ./deploy.sh staging eu-west-1

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${1:-dev}"
REGION="${2:-us-east-1}"
NAMESPACE="trading-system"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local required_tools=("kubectl" "docker" "helm" "argocd")
    local missing_tools=()
    
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_info "Install missing tools and try again"
        exit 1
    fi
    
    log_success "All prerequisites satisfied"
}

validate_environment() {
    log_info "Validating environment: $ENVIRONMENT"
    
    if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $ENVIRONMENT"
        log_info "Valid environments: dev, staging, prod"
        exit 1
    fi
    
    log_success "Environment validated"
}

check_cluster_connection() {
    log_info "Checking cluster connection..."
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        log_info "Configure kubectl and try again"
        exit 1
    fi
    
    local current_context=$(kubectl config current-context)
    log_success "Connected to cluster: $current_context"
}

create_namespace() {
    log_info "Creating namespace: $NAMESPACE"
    
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_warn "Namespace $NAMESPACE already exists"
    else
        kubectl create namespace "$NAMESPACE"
        log_success "Namespace created"
    fi
    
    # Label namespace
    kubectl label namespace "$NAMESPACE" \
        environment="$ENVIRONMENT" \
        region="$REGION" \
        managed-by=argocd \
        --overwrite
}

deploy_secrets() {
    log_info "Deploying secrets..."
    
    # Check if secrets file exists
    local secrets_file="$PROJECT_ROOT/k8s/secrets-$ENVIRONMENT.yml"
    
    if [ -f "$secrets_file" ]; then
        kubectl apply -f "$secrets_file" -n "$NAMESPACE"
        log_success "Secrets deployed"
    else
        log_warn "Secrets file not found: $secrets_file"
        log_info "Create secrets manually or use external secrets operator"
    fi
}

deploy_configmaps() {
    log_info "Deploying ConfigMaps..."
    
    local configmap_file="$PROJECT_ROOT/k8s/configmap.yml"
    
    if [ -f "$configmap_file" ]; then
        kubectl apply -f "$configmap_file" -n "$NAMESPACE"
        log_success "ConfigMaps deployed"
    else
        log_warn "ConfigMap file not found: $configmap_file"
    fi
}

deploy_infrastructure() {
    log_info "Deploying infrastructure components..."
    
    # Deploy storage
    if [ -f "$PROJECT_ROOT/k8s/storage.yml" ]; then
        kubectl apply -f "$PROJECT_ROOT/k8s/storage.yml" -n "$NAMESPACE"
        log_success "Storage deployed"
    fi
    
    # Deploy multi-region configuration
    if [ -d "$PROJECT_ROOT/k8s/multi-region" ]; then
        kubectl apply -f "$PROJECT_ROOT/k8s/multi-region/" -n "$NAMESPACE"
        log_success "Multi-region configuration deployed"
    fi
}

deploy_application() {
    log_info "Deploying application..."
    
    # Deploy using ArgoCD
    if command -v argocd &> /dev/null; then
        log_info "Deploying via ArgoCD..."
        
        # Apply ArgoCD application
        kubectl apply -f "$PROJECT_ROOT/gitops/applications/trading-system-app.yml"
        
        # Wait for sync
        log_info "Waiting for ArgoCD to sync..."
        argocd app sync "trading-system-$ENVIRONMENT" --timeout 600
        argocd app wait "trading-system-$ENVIRONMENT" --health --timeout 600
        
        log_success "Application deployed via ArgoCD"
    else
        log_warn "ArgoCD not available, deploying directly..."
        kubectl apply -f "$PROJECT_ROOT/k8s/deployment.yml" -n "$NAMESPACE"
        kubectl apply -f "$PROJECT_ROOT/k8s/service.yml" -n "$NAMESPACE"
        log_success "Application deployed directly"
    fi
}

wait_for_deployment() {
    log_info "Waiting for deployment to be ready..."
    
    if kubectl rollout status deployment/trading-system -n "$NAMESPACE" --timeout=600s; then
        log_success "Deployment is ready"
    else
        log_error "Deployment failed to become ready"
        exit 1
    fi
}

run_smoke_tests() {
    log_info "Running smoke tests..."
    
    # Get service endpoint
    local service_url=$(kubectl get svc trading-system -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "localhost")
    
    # Health check
    log_info "Testing health endpoint..."
    if kubectl exec -n "$NAMESPACE" deployment/trading-system -- curl -f http://localhost:8000/health &> /dev/null; then
        log_success "Health check passed"
    else
        log_warn "Health check failed (might not be exposed)"
    fi
    
    # Check pod status
    local ready_pods=$(kubectl get pods -n "$NAMESPACE" -l app=trading-system -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | tr ' ' '\n' | grep -c "True" || echo "0")
    local total_pods=$(kubectl get pods -n "$NAMESPACE" -l app=trading-system --no-headers | wc -l | tr -d ' ')
    
    log_info "Ready pods: $ready_pods/$total_pods"
    
    if [ "$ready_pods" -eq "$total_pods" ] && [ "$total_pods" -gt 0 ]; then
        log_success "All pods are ready"
    else
        log_warn "Not all pods are ready"
    fi
}

display_info() {
    log_info "Deployment complete!"
    echo ""
    echo "=========================================="
    echo "Deployment Information"
    echo "=========================================="
    echo "Environment: $ENVIRONMENT"
    echo "Region: $REGION"
    echo "Namespace: $NAMESPACE"
    echo ""
    echo "Commands:"
    echo "  View pods: kubectl get pods -n $NAMESPACE"
    echo "  View logs: kubectl logs -f deployment/trading-system -n $NAMESPACE"
    echo "  Port forward: kubectl port-forward svc/trading-system -n $NAMESPACE 8000:80"
    echo "  Dashboard: kubectl port-forward svc/trading-dashboard -n $NAMESPACE 8050:80"
    echo ""
    
    # Get service URLs
    local lb_hostname=$(kubectl get svc trading-system -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "N/A")
    if [ "$lb_hostname" != "N/A" ]; then
        echo "Load Balancer: http://$lb_hostname"
    fi
    
    echo "=========================================="
}

rollback_deployment() {
    log_error "Deployment failed! Rolling back..."
    
    if kubectl rollout undo deployment/trading-system -n "$NAMESPACE" &> /dev/null; then
        log_success "Rollback initiated"
    else
        log_warn "Rollback failed or not applicable"
    fi
}

# Main deployment flow
main() {
    echo ""
    echo "=========================================="
    echo "Trading System Deployment"
    echo "=========================================="
    echo ""
    
    # Trap errors for rollback
    trap 'rollback_deployment' ERR
    
    # Run deployment steps
    check_prerequisites
    validate_environment
    check_cluster_connection
    create_namespace
    deploy_secrets
    deploy_configmaps
    deploy_infrastructure
    deploy_application
    wait_for_deployment
    run_smoke_tests
    display_info
    
    log_success "Deployment completed successfully!"
}

# Run main function
main "$@"
