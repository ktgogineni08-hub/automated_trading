#!/bin/bash

# Deployment Validation Script
# Validates that all implementation files are present and correctly configured

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
total_checks=0
passed_checks=0
failed_checks=0
warning_checks=0

# Base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "========================================="
echo "Trading System Deployment Validator"
echo "========================================="
echo ""
echo "Base directory: $BASE_DIR"
echo ""

# Function to check if file exists
check_file() {
    local file="$1"
    local description="$2"

    ((total_checks++))

    echo -n "Checking: $description... "

    if [ -f "$BASE_DIR/$file" ]; then
        echo -e "${GREEN}✓ Found${NC}"
        ((passed_checks++))
        return 0
    else
        echo -e "${RED}✗ Missing${NC}"
        echo "  Expected: $BASE_DIR/$file"
        ((failed_checks++))
        return 1
    fi
}

# Function to check if file is executable
check_executable() {
    local file="$1"
    local description="$2"

    ((total_checks++))

    echo -n "Checking: $description is executable... "

    if [ -x "$BASE_DIR/$file" ]; then
        echo -e "${GREEN}✓ Executable${NC}"
        ((passed_checks++))
        return 0
    else
        echo -e "${YELLOW}⚠ Not executable${NC}"
        echo "  Run: chmod +x $BASE_DIR/$file"
        ((warning_checks++))
        return 1
    fi
}

# Function to validate YAML syntax
check_yaml_syntax() {
    local file="$1"
    local description="$2"

    ((total_checks++))

    echo -n "Validating: $description syntax... "

    if ! command -v python3 &> /dev/null; then
        echo -e "${YELLOW}⚠ Python3 not found, skipping${NC}"
        ((warning_checks++))
        return 1
    fi

    if python3 -c "import yaml; yaml.safe_load(open('$BASE_DIR/$file'))" 2>/dev/null; then
        echo -e "${GREEN}✓ Valid YAML${NC}"
        ((passed_checks++))
        return 0
    else
        echo -e "${RED}✗ Invalid YAML${NC}"
        ((failed_checks++))
        return 1
    fi
}

# Function to validate JSON syntax
check_json_syntax() {
    local file="$1"
    local description="$2"

    ((total_checks++))

    echo -n "Validating: $description syntax... "

    if ! command -v jq &> /dev/null; then
        echo -e "${YELLOW}⚠ jq not found, skipping${NC}"
        ((warning_checks++))
        return 1
    fi

    if jq empty "$BASE_DIR/$file" 2>/dev/null; then
        echo -e "${GREEN}✓ Valid JSON${NC}"
        ((passed_checks++))
        return 0
    else
        echo -e "${RED}✗ Invalid JSON${NC}"
        ((failed_checks++))
        return 1
    fi
}

# Function to check Python syntax
check_python_syntax() {
    local file="$1"
    local description="$2"

    ((total_checks++))

    echo -n "Validating: $description syntax... "

    if ! command -v python3 &> /dev/null; then
        echo -e "${YELLOW}⚠ Python3 not found, skipping${NC}"
        ((warning_checks++))
        return 1
    fi

    if python3 -m py_compile "$BASE_DIR/$file" 2>/dev/null; then
        echo -e "${GREEN}✓ Valid Python${NC}"
        ((passed_checks++))
        return 0
    else
        echo -e "${RED}✗ Syntax error${NC}"
        ((failed_checks++))
        return 1
    fi
}

echo -e "${BLUE}=== Phase 1: High Availability Infrastructure ===${NC}"
echo ""

check_file "infrastructure/kubernetes/production/postgres-statefulset.yaml" "PostgreSQL StatefulSet"
check_yaml_syntax "infrastructure/kubernetes/production/postgres-statefulset.yaml" "PostgreSQL StatefulSet"

check_file "infrastructure/kubernetes/production/redis-sentinel.yaml" "Redis Sentinel"
check_yaml_syntax "infrastructure/kubernetes/production/redis-sentinel.yaml" "Redis Sentinel"

check_file "infrastructure/scripts/test-postgres-failover.sh" "PostgreSQL failover test script"
check_executable "infrastructure/scripts/test-postgres-failover.sh" "PostgreSQL failover test script"

check_file "infrastructure/scripts/test-redis-failover.sh" "Redis failover test script"
check_executable "infrastructure/scripts/test-redis-failover.sh" "Redis failover test script"

check_file "monitoring/prometheus/alert_rules.yml" "Enhanced alert rules"
check_yaml_syntax "monitoring/prometheus/alert_rules.yml" "Enhanced alert rules"

check_file "docker-compose.yml" "Docker Compose configuration"
check_yaml_syntax "docker-compose.yml" "Docker Compose configuration"

echo ""
echo -e "${BLUE}=== Phase 2: Monitoring & Alerting ===${NC}"
echo ""

check_file "infrastructure/prometheus/alertmanager.yml" "Alertmanager configuration"
check_yaml_syntax "infrastructure/prometheus/alertmanager.yml" "Alertmanager configuration"

check_file "infrastructure/prometheus/templates/notifications.tmpl" "Notification templates"

check_file "Documentation/ALERT_ESCALATION_POLICY.md" "Escalation policy"

echo ""
echo -e "${BLUE}=== Phase 3: Documentation ===${NC}"
echo ""

check_file "Documentation/architecture/C4_CONTEXT_DIAGRAM.md" "C4 Context Diagram"
check_file "Documentation/architecture/C4_CONTAINER_DIAGRAM.md" "C4 Container Diagram"
check_file "Documentation/architecture/C4_COMPONENT_DIAGRAM.md" "C4 Component Diagram"

check_file "Documentation/api/openapi.yaml" "OpenAPI specification"
check_yaml_syntax "Documentation/api/openapi.yaml" "OpenAPI specification"

check_file "Documentation/DISASTER_RECOVERY.md" "Disaster Recovery plan"

check_file "Documentation/runbooks/RUNBOOK_INDEX.md" "Runbook index"
check_file "Documentation/runbooks/RB-001-database-primary-down.md" "Runbook RB-001"
check_file "Documentation/runbooks/RB-004-high-error-rate.md" "Runbook RB-004"

echo ""
echo -e "${BLUE}=== Phase 4: Performance Optimization ===${NC}"
echo ""

check_file "utilities/cache_warmer.py" "Cache warmer"
check_python_syntax "utilities/cache_warmer.py" "Cache warmer"

check_file "utilities/prefetch_manager.py" "Prefetch manager"
check_python_syntax "utilities/prefetch_manager.py" "Prefetch manager"

echo ""
echo -e "${BLUE}=== Phase 5: Security Hardening ===${NC}"
echo ""

check_file "security/hmac_auth.py" "HMAC authentication"
check_python_syntax "security/hmac_auth.py" "HMAC authentication"

check_file "security/ip_whitelist.py" "IP whitelist"
check_python_syntax "security/ip_whitelist.py" "IP whitelist"

check_file "security/secrets_rotation.py" "Secrets rotation"
check_python_syntax "security/secrets_rotation.py" "Secrets rotation"

echo ""
echo -e "${BLUE}=== Phase 6: Deployment & Training ===${NC}"
echo ""

check_file "Documentation/DEPLOYMENT_PLAN.md" "Deployment plan"
check_file "Documentation/ALERTING_SETUP_GUIDE.md" "Alerting setup guide"
check_file "Documentation/TEAM_TRAINING_GUIDE.md" "Team training guide"
check_file "Documentation/DEPLOYMENT_READINESS_CHECKLIST.md" "Deployment readiness checklist"
check_file "Documentation/IMPLEMENTATION_SUMMARY.md" "Implementation summary"

check_file "monitoring/grafana/dashboards/trading-activity-dashboard.json" "Trading Activity dashboard"
check_json_syntax "monitoring/grafana/dashboards/trading-activity-dashboard.json" "Trading Activity dashboard"

check_file "monitoring/grafana/dashboards/system-health-dashboard.json" "System Health dashboard"
check_json_syntax "monitoring/grafana/dashboards/system-health-dashboard.json" "System Health dashboard"

check_file "monitoring/grafana/import-dashboards.sh" "Dashboard import script"
check_executable "monitoring/grafana/import-dashboards.sh" "Dashboard import script"

echo ""
echo "========================================="
echo "Validation Summary"
echo "========================================="
echo ""
echo "Total checks:   $total_checks"
echo -e "${GREEN}Passed:         $passed_checks${NC}"
echo -e "${YELLOW}Warnings:       $warning_checks${NC}"
echo -e "${RED}Failed:         $failed_checks${NC}"
echo ""

# Calculate success rate
if [ $total_checks -gt 0 ]; then
    success_rate=$((passed_checks * 100 / total_checks))
    echo "Success rate:   $success_rate%"
    echo ""
fi

# Final status
if [ $failed_checks -eq 0 ]; then
    echo -e "${GREEN}✓ All critical checks passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review: cat Documentation/DEPLOYMENT_PLAN.md"
    echo "  2. Deploy to staging: kubectl apply -f infrastructure/kubernetes/production/"
    echo "  3. Run tests: cd infrastructure/scripts && ./test-postgres-failover.sh"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Please fix the issues above.${NC}"
    echo ""
    exit 1
fi
