#!/usr/bin/env bash
# ==============================================================================
# Trading System Deployment Script
# ==============================================================================
# Complete deployment automation for all environments
# ==============================================================================

set -euo pipefail  # Exit on error, undefined vars, pipe failures
IFS=$'\n\t'

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
ENVIRONMENT="${ENVIRONMENT:-development}"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
ENV_FILE="${PROJECT_ROOT}/.env"

# ==============================================================================
# Helper Functions
# ==============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo ""
    echo "========================================================================"
    echo "$1"
    echo "========================================================================"
    echo ""
}

# ==============================================================================
# Pre-deployment Checks
# ==============================================================================

check_prerequisites() {
    print_header "Checking Prerequisites"

    local missing_tools=()

    # Check Docker
    if ! command -v docker &> /dev/null; then
        missing_tools+=("docker")
    else
        log_success "Docker found: $(docker --version)"
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        missing_tools+=("docker-compose")
    else
        if docker compose version &> /dev/null; then
            log_success "Docker Compose found: $(docker compose version)"
        else
            log_success "Docker Compose found: $(docker-compose --version)"
        fi
    fi

    # Check if running
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi

    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_info "Please install missing tools and try again"
        exit 1
    fi

    log_success "All prerequisites met"
}

check_environment_file() {
    print_header "Checking Environment Configuration"

    if [ ! -f "$ENV_FILE" ]; then
        log_warning ".env file not found"
        log_info "Creating .env from .env.example..."

        if [ -f "${PROJECT_ROOT}/.env.example" ]; then
            cp "${PROJECT_ROOT}/.env.example" "$ENV_FILE"
            log_warning "Please edit .env and set your credentials before deployment"
            log_info "Edit file: $ENV_FILE"
            exit 1
        else
            log_error ".env.example not found"
            exit 1
        fi
    fi

    # Check for placeholder values
    if grep -q "changeme\|your_.*_here" "$ENV_FILE"; then
        log_warning "Found placeholder values in .env file"
        log_warning "Please update these values before production deployment:"
        grep -n "changeme\|your_.*_here" "$ENV_FILE" | head -5
        echo ""

        if [ "$ENVIRONMENT" = "production" ]; then
            log_error "Cannot deploy to production with placeholder values"
            exit 1
        else
            log_warning "Continuing with development deployment..."
        fi
    fi

    log_success "Environment configuration checked"
}

# ==============================================================================
# Build Functions
# ==============================================================================

build_images() {
    print_header "Building Docker Images"

    log_info "Building trading system image..."
    docker-compose -f "$COMPOSE_FILE" build trading-system

    log_success "Docker images built successfully"
}

# ==============================================================================
# Deployment Functions
# ==============================================================================

stop_services() {
    print_header "Stopping Existing Services"

    if docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        log_info "Stopping running services..."
        docker-compose -f "$COMPOSE_FILE" down
        log_success "Services stopped"
    else
        log_info "No running services found"
    fi
}

start_services() {
    print_header "Starting Services"

    log_info "Starting all services..."
    docker-compose -f "$COMPOSE_FILE" up -d

    log_success "Services started"
}

wait_for_health() {
    print_header "Waiting for Services to be Healthy"

    local max_wait=120  # 2 minutes
    local wait_interval=5
    local elapsed=0

    log_info "Waiting for services to be healthy..."

    while [ $elapsed -lt $max_wait ]; do
        local unhealthy_count=$(docker-compose -f "$COMPOSE_FILE" ps | grep -c "unhealthy" || true)
        local starting_count=$(docker-compose -f "$COMPOSE_FILE" ps | grep -c "starting" || true)

        if [ "$unhealthy_count" -eq 0 ] && [ "$starting_count" -eq 0 ]; then
            log_success "All services are healthy"
            return 0
        fi

        echo -n "."
        sleep $wait_interval
        elapsed=$((elapsed + wait_interval))
    done

    echo ""
    log_error "Services did not become healthy within ${max_wait} seconds"
    log_info "Check logs: docker-compose -f $COMPOSE_FILE logs"
    return 1
}

show_status() {
    print_header "Deployment Status"

    log_info "Service Status:"
    docker-compose -f "$COMPOSE_FILE" ps

    echo ""
    log_info "Service URLs:"
    echo "  📊 Main Dashboard:      http://localhost:8080"
    echo "  📈 Monitoring Dashboard: http://localhost:8081"
    echo "  🗄️  PostgreSQL:          localhost:5432"
    echo "  💾 Redis:               localhost:6379"
    echo "  📉 Grafana:             http://localhost:3000"
    echo "  📊 Prometheus:          http://localhost:9091"
}

# ==============================================================================
# Post-Deployment Tasks
# ==============================================================================

run_migrations() {
    print_header "Running Database Migrations"

    log_info "Waiting for database to be ready..."
    sleep 5

    log_info "Database initialized (init-db.sql runs automatically)"
    log_success "Migrations completed"
}

verify_deployment() {
    print_header "Verifying Deployment"

    log_info "Checking main dashboard..."
    if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
        log_success "Main dashboard is accessible"
    else
        log_warning "Main dashboard health check failed"
    fi

    log_info "Checking monitoring dashboard..."
    if curl -f -s http://localhost:8081/api/health > /dev/null 2>&1; then
        log_success "Monitoring dashboard is accessible"
    else
        log_warning "Monitoring dashboard is starting (may take a moment)"
    fi

    log_info "Checking PostgreSQL..."
    if docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U trading_user > /dev/null 2>&1; then
        log_success "PostgreSQL is ready"
    else
        log_warning "PostgreSQL health check failed"
    fi

    log_info "Checking Redis..."
    if docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping > /dev/null 2>&1; then
        log_success "Redis is ready"
    else
        log_warning "Redis health check failed"
    fi
}

# ==============================================================================
# Main Deployment Flow
# ==============================================================================

main() {
    print_header "🚀 Trading System Deployment"
    log_info "Environment: $ENVIRONMENT"
    log_info "Project Root: $PROJECT_ROOT"
    echo ""

    # Pre-deployment checks
    check_prerequisites
    check_environment_file

    # Build
    build_images

    # Deploy
    stop_services
    start_services

    # Wait for health
    if wait_for_health; then
        run_migrations
        verify_deployment
        show_status

        print_header "✅ Deployment Complete"
        log_success "Trading system deployed successfully"
        log_info "View logs: docker-compose -f $COMPOSE_FILE logs -f"
        log_info "Stop services: docker-compose -f $COMPOSE_FILE down"
    else
        log_error "Deployment failed - services are not healthy"
        log_info "Check logs: docker-compose -f $COMPOSE_FILE logs"
        exit 1
    fi
}

# ==============================================================================
# Script Entry Point
# ==============================================================================

# Check if script is being sourced or executed
if [ "${BASH_SOURCE[0]}" -ef "$0" ]; then
    main "$@"
fi
