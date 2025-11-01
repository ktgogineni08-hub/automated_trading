#!/bin/bash

# Quick validation script - checks that all key files exist

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "Trading System - Quick File Validation"
echo "======================================="
echo ""

passed=0
failed=0

check() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1"
        ((passed++))
    else
        echo -e "${RED}✗${NC} $1"
        ((failed++))
    fi
}

# High Availability
check "infrastructure/kubernetes/production/postgres-statefulset.yaml"
check "infrastructure/kubernetes/production/redis-sentinel.yaml"
check "infrastructure/scripts/test-postgres-failover.sh"
check "infrastructure/scripts/test-redis-failover.sh"

# Alerting
check "infrastructure/prometheus/alertmanager.yml"
check "infrastructure/prometheus/templates/notifications.tmpl"
check "Documentation/ALERT_ESCALATION_POLICY.md"

# Documentation
check "Documentation/architecture/C4_CONTEXT_DIAGRAM.md"
check "Documentation/architecture/C4_CONTAINER_DIAGRAM.md"
check "Documentation/architecture/C4_COMPONENT_DIAGRAM.md"
check "Documentation/api/openapi.yaml"
check "Documentation/DISASTER_RECOVERY.md"
check "Documentation/runbooks/RUNBOOK_INDEX.md"

# Performance
check "utilities/cache_warmer.py"
check "utilities/prefetch_manager.py"

# Security
check "security/hmac_auth.py"
check "security/ip_whitelist.py"
check "security/secrets_rotation.py"

# Deployment
check "Documentation/DEPLOYMENT_PLAN.md"
check "Documentation/ALERTING_SETUP_GUIDE.md"
check "Documentation/TEAM_TRAINING_GUIDE.md"
check "Documentation/DEPLOYMENT_READINESS_CHECKLIST.md"
check "Documentation/IMPLEMENTATION_SUMMARY.md"

# Dashboards
check "monitoring/grafana/dashboards/trading-activity-dashboard.json"
check "monitoring/grafana/dashboards/system-health-dashboard.json"
check "monitoring/grafana/import-dashboards.sh"

echo ""
echo "Summary: $passed passed, $failed failed"

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}All files present!${NC}"
    exit 0
else
    echo -e "${RED}Some files missing!${NC}"
    exit 1
fi
