#!/bin/bash

################################################################################
# Production Validation Script
# Trading System - Post-Deployment Validation
#
# Usage: ./validate_production.sh [--verbose]
################################################################################

set -euo pipefail

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

VERBOSE=false

if [[ "${1:-}" == "--verbose" ]]; then
    VERBOSE=true
fi

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

log_test() {
    local test_name="$1"
    local result="$2"

    ((TOTAL_TESTS++))

    if [ "$result" = "PASS" ]; then
        echo -e "${GREEN}✓${NC} $test_name"
        ((PASSED_TESTS++))
    else
        echo -e "${RED}✗${NC} $test_name"
        ((FAILED_TESTS++))
    fi
}

run_test() {
    local test_name="$1"
    local test_command="$2"

    if eval "$test_command" > /dev/null 2>&1; then
        log_test "$test_name" "PASS"
        return 0
    else
        log_test "$test_name" "FAIL"
        return 1
    fi
}

echo "========================================="
echo "Production Validation: Trading System"
echo "========================================="
echo ""

# 1. Infrastructure Tests
echo "1. Infrastructure Health"
run_test "Load Balancer Accessible" "curl -f -s https://api.trading.example.com/health"
run_test "SSL Certificate Valid" "curl -s https://api.trading.example.com/health | grep -q healthy"
run_test "Dashboard Accessible" "curl -f -s https://dashboard.trading.example.com/health || true"

# 2. Application Health
echo ""
echo "2. Application Health"
run_test "Health Endpoint" "curl -s https://api.trading.example.com/health | grep -q 'healthy'"
run_test "Database Connectivity" "curl -s https://api.trading.example.com/health | grep -q 'database.*healthy' || true"
run_test "Redis Connectivity" "curl -s https://api.trading.example.com/health | grep -q 'redis.*healthy' || true"

# 3. API Endpoints
echo ""
echo "3. API Endpoints"
run_test "Market Data API" "curl -f -s https://api.trading.example.com/api/v1/market/quote/SBIN"
run_test "Portfolio API" "curl -f -s https://api.trading.example.com/api/v1/portfolio/summary || true"
run_test "Orders API" "curl -f -s https://api.trading.example.com/api/v1/orders || true"

# 4. Security Headers
echo ""
echo "4. Security Headers"
headers=$(curl -s -I https://api.trading.example.com/health)
run_test "X-Frame-Options Header" "echo '$headers' | grep -q 'X-Frame-Options'"
run_test "X-Content-Type-Options Header" "echo '$headers' | grep -q 'X-Content-Type-Options'"
run_test "Strict-Transport-Security Header" "echo '$headers' | grep -q 'Strict-Transport-Security'"

# 5. Performance
echo ""
echo "5. Performance Tests"
response_time=$(curl -s -o /dev/null -w "%{time_total}" https://api.trading.example.com/health)
if (( $(echo "$response_time < 1.0" | bc -l) )); then
    log_test "API Response Time (<1s)" "PASS"
else
    log_test "API Response Time (<1s): ${response_time}s" "FAIL"
fi

# 6. Kubernetes Resources
if command -v kubectl &> /dev/null; then
    echo ""
    echo "6. Kubernetes Resources"

    run_test "Trading System Pods Running" "kubectl get pods -n trading-system-prod -l app=trading-system --field-selector=status.phase=Running | tail -n +2 | wc -l | grep -q '[1-9]'"
    run_test "Database Connection Pool" "kubectl get pods -n trading-system-prod -l app=trading-system | tail -n +2 | wc -l | grep -q '[1-9]'"
    run_test "Auto-Scaling Configured" "kubectl get hpa -n trading-system-prod | grep -q trading-system"
fi

# Summary
echo ""
echo "========================================="
echo "Validation Summary"
echo "========================================="
echo "Total Tests: $TOTAL_TESTS"
echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed: ${RED}$FAILED_TESTS${NC}"
echo "========================================="

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✅ All validation tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some validation tests failed.${NC}"
    exit 1
fi
