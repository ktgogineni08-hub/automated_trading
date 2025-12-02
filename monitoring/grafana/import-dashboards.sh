#!/bin/bash

# Grafana Dashboard Import Script
# Imports all trading system dashboards into Grafana

set -e

# Configuration
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
GRAFANA_API_KEY="${GRAFANA_API_KEY:-}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-admin}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Dashboard directory
DASHBOARD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/dashboards" && pwd)"

echo "========================================="
echo "Grafana Dashboard Import Tool"
echo "========================================="
echo ""

# Check if Grafana is accessible
echo "Checking Grafana connectivity..."
if ! curl -s -f "${GRAFANA_URL}/api/health" > /dev/null; then
    echo -e "${RED}✗ Cannot connect to Grafana at ${GRAFANA_URL}${NC}"
    echo "  Make sure Grafana is running and accessible."
    echo "  You can port-forward with: kubectl port-forward svc/grafana 3000:3000 -n trading-system-prod"
    exit 1
fi
echo -e "${GREEN}✓ Grafana is accessible${NC}"
echo ""

# Determine authentication method
if [ -n "$GRAFANA_API_KEY" ]; then
    AUTH_HEADER="Authorization: Bearer $GRAFANA_API_KEY"
    echo "Using API key authentication"
else
    echo "Using basic authentication (user: $GRAFANA_USER)"
    AUTH_HEADER="Authorization: Basic $(echo -n "${GRAFANA_USER}:${GRAFANA_PASSWORD}" | base64)"
fi
echo ""

# Function to import a dashboard
import_dashboard() {
    local dashboard_file="$1"
    local dashboard_name=$(basename "$dashboard_file" .json)

    echo -n "Importing ${dashboard_name}... "

    # Read dashboard JSON
    dashboard_json=$(cat "$dashboard_file")

    # Create import payload
    import_payload=$(jq -n \
        --argjson dashboard "$dashboard_json" \
        '{
            dashboard: $dashboard.dashboard,
            overwrite: true,
            inputs: [],
            folderId: 0
        }')

    # Import to Grafana
    response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -H "$AUTH_HEADER" \
        -d "$import_payload" \
        "${GRAFANA_URL}/api/dashboards/db")

    # Check response
    if echo "$response" | jq -e '.status == "success"' > /dev/null 2>&1; then
        dashboard_url=$(echo "$response" | jq -r '.url')
        echo -e "${GREEN}✓ Success${NC}"
        echo "  URL: ${GRAFANA_URL}${dashboard_url}"
    else
        echo -e "${RED}✗ Failed${NC}"
        echo "  Error: $(echo "$response" | jq -r '.message // "Unknown error"')"
        return 1
    fi
}

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${RED}✗ jq is not installed${NC}"
    echo "  Install with: brew install jq (macOS) or apt-get install jq (Linux)"
    exit 1
fi

# Import all dashboards
echo "Importing dashboards from: $DASHBOARD_DIR"
echo ""

success_count=0
failed_count=0

for dashboard_file in "$DASHBOARD_DIR"/*.json; do
    if [ -f "$dashboard_file" ]; then
        if import_dashboard "$dashboard_file"; then
            ((success_count++))
        else
            ((failed_count++))
        fi
        echo ""
    fi
done

# Summary
echo "========================================="
echo "Import Summary"
echo "========================================="
echo -e "${GREEN}Successful: $success_count${NC}"
if [ $failed_count -gt 0 ]; then
    echo -e "${RED}Failed: $failed_count${NC}"
fi
echo ""

if [ $success_count -gt 0 ]; then
    echo "Dashboards are now available at:"
    echo "  ${GRAFANA_URL}/dashboards"
    echo ""
    echo "Direct links:"
    echo "  - Trading Activity: ${GRAFANA_URL}/d/trading-activity"
    echo "  - System Health: ${GRAFANA_URL}/d/system-health"
fi

exit 0
