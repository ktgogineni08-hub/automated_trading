#!/bin/bash
################################################################################
# Grafana Dashboard Import Script
# Automatically imports all dashboards into Grafana
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
DASHBOARDS_DIR="${PROJECT_ROOT}/dashboards"

GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-admin}"

# Banner
echo -e "${BLUE}"
cat << 'BANNER'
═══════════════════════════════════════════════════════════════════════
   _____ _____            ______          _   _   _
  / ____|  __ \     /\   |  ____|   /\   | \ | | /\
 | |  __| |__) |   /  \  | |__     /  \  |  \| |/  \
 | | |_ |  _  /   / /\ \ |  __|   / /\ \ | . ` / /\ \
 | |__| | | \ \  / ____ \| |     / ____ \| |\  / ____ \
  \_____|_|  \_\/_/    \_\_|    /_/    \_\_| \_/_/  \_\

       DASHBOARD IMPORT UTILITY
═══════════════════════════════════════════════════════════════════════
BANNER
echo -e "${NC}"

echo -e "${BLUE}Grafana URL: ${GRAFANA_URL}${NC}"
echo -e "${BLUE}Dashboards Directory: ${DASHBOARDS_DIR}${NC}\n"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v curl &> /dev/null; then
    echo -e "${RED}❌ curl not installed${NC}"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}⚠️  jq not installed (optional, but recommended for pretty output)${NC}"
    JQ_AVAILABLE=false
else
    JQ_AVAILABLE=true
fi

if [ ! -d "${DASHBOARDS_DIR}" ]; then
    echo -e "${RED}❌ Dashboards directory not found: ${DASHBOARDS_DIR}${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites met${NC}\n"

# Check Grafana connectivity
echo -e "${YELLOW}Testing Grafana connectivity...${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${GRAFANA_URL}/api/health" || echo "000")

if [ "$HTTP_CODE" != "200" ]; then
    echo -e "${RED}❌ Cannot connect to Grafana at ${GRAFANA_URL}${NC}"
    echo -e "${YELLOW}Please ensure Grafana is running:${NC}"
    echo -e "  docker-compose ps grafana"
    echo -e "  docker-compose logs grafana"
    exit 1
fi

echo -e "${GREEN}✅ Grafana is accessible${NC}\n"

# Test authentication
echo -e "${YELLOW}Testing Grafana authentication...${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -u "${GRAFANA_USER}:${GRAFANA_PASSWORD}" \
    "${GRAFANA_URL}/api/user" || echo "000")

if [ "$HTTP_CODE" != "200" ]; then
    echo -e "${RED}❌ Authentication failed${NC}"
    echo -e "${YELLOW}Please check GRAFANA_USER and GRAFANA_PASSWORD${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Authentication successful${NC}\n"

# Create folder for dashboards (optional)
echo -e "${YELLOW}Creating dashboard folder...${NC}"
FOLDER_RESPONSE=$(curl -s -X POST \
    -u "${GRAFANA_USER}:${GRAFANA_PASSWORD}" \
    -H "Content-Type: application/json" \
    -d '{"title":"Trading System"}' \
    "${GRAFANA_URL}/api/folders" 2>/dev/null || echo '{"message":"Folder may already exist"}')

if [ "$JQ_AVAILABLE" = true ]; then
    FOLDER_ID=$(echo "$FOLDER_RESPONSE" | jq -r '.id // empty')
    if [ -n "$FOLDER_ID" ]; then
        echo -e "${GREEN}✅ Created folder 'Trading System' (ID: ${FOLDER_ID})${NC}"
    else
        echo -e "${YELLOW}ℹ️  Using existing folder${NC}"
    fi
else
    echo -e "${YELLOW}ℹ️  Folder created or already exists${NC}"
fi

echo ""

# Import dashboards
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}IMPORTING DASHBOARDS${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}\n"

SUCCESS_COUNT=0
FAIL_COUNT=0
TOTAL_COUNT=0

for dashboard_file in "${DASHBOARDS_DIR}"/*.json; do
    if [ ! -f "$dashboard_file" ]; then
        continue
    fi

    TOTAL_COUNT=$((TOTAL_COUNT + 1))
    filename=$(basename "$dashboard_file")
    echo -e "${YELLOW}📊 Importing: ${filename}${NC}"

    # Read and prepare the dashboard JSON
    DASHBOARD_JSON=$(cat "$dashboard_file")

    # Import the dashboard
    RESPONSE=$(curl -s -X POST \
        -u "${GRAFANA_USER}:${GRAFANA_PASSWORD}" \
        -H "Content-Type: application/json" \
        -d "$DASHBOARD_JSON" \
        "${GRAFANA_URL}/api/dashboards/db")

    # Check response
    if [ "$JQ_AVAILABLE" = true ]; then
        STATUS=$(echo "$RESPONSE" | jq -r '.status // .message // "unknown"')
        DASH_URL=$(echo "$RESPONSE" | jq -r '.url // empty')

        if echo "$STATUS" | grep -qi "success"; then
            echo -e "${GREEN}   ✅ Success${NC}"
            if [ -n "$DASH_URL" ]; then
                echo -e "${GREEN}   🔗 URL: ${GRAFANA_URL}${DASH_URL}${NC}"
            fi
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            echo -e "${RED}   ❌ Failed: ${STATUS}${NC}"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    else
        # Basic check without jq
        if echo "$RESPONSE" | grep -q "success"; then
            echo -e "${GREEN}   ✅ Success${NC}"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            echo -e "${RED}   ❌ Failed${NC}"
            echo -e "${YELLOW}   Response: ${RESPONSE:0:100}...${NC}"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    fi

    echo ""
done

# Summary
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}IMPORT SUMMARY${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Successful: ${SUCCESS_COUNT}/${TOTAL_COUNT}${NC}"
if [ $FAIL_COUNT -gt 0 ]; then
    echo -e "${RED}❌ Failed: ${FAIL_COUNT}/${TOTAL_COUNT}${NC}"
fi
echo ""

# List available dashboards
echo -e "${YELLOW}Fetching dashboard list...${NC}"
DASH_LIST=$(curl -s -u "${GRAFANA_USER}:${GRAFANA_PASSWORD}" \
    "${GRAFANA_URL}/api/search?type=dash-db" || echo '[]')

if [ "$JQ_AVAILABLE" = true ]; then
    echo -e "\n${BLUE}Available Dashboards:${NC}"
    echo "$DASH_LIST" | jq -r '.[] | "  • \(.title) - \(.url)"' | while read -r line; do
        echo -e "${GREEN}$line${NC}"
    done
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Dashboard import completed!${NC}"
echo -e "${GREEN}Access Grafana at: ${GRAFANA_URL}${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════${NC}\n"

# Exit with appropriate code
if [ $FAIL_COUNT -gt 0 ]; then
    exit 1
fi

exit 0
