#!/usr/bin/env bash
# ==============================================================================
# Quick Start Script
# ==============================================================================
# Quickly start all services without full deployment process
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 Starting Trading System...${NC}"

cd "$PROJECT_ROOT"
docker-compose up -d

echo -e "${GREEN}✅ Services started${NC}"
echo ""
echo "Service URLs:"
echo "  📊 Main Dashboard:       http://localhost:8080"
echo "  📈 Monitoring Dashboard: http://localhost:8081"
echo "  📉 Grafana:              http://localhost:3000"
echo ""
echo "View logs: docker-compose logs -f"
echo "Stop services: ./scripts/stop.sh"
