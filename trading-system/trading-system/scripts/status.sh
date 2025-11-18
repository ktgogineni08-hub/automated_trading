#!/usr/bin/env bash
# ==============================================================================
# Show Status Script
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}📊 Trading System Status${NC}"
echo ""

cd "$PROJECT_ROOT"

echo "Running Services:"
docker-compose ps

echo ""
echo "Resource Usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"

echo ""
echo "Service Health:"
docker-compose ps | grep -E "trading-system|postgres|redis" | while read line; do
    service=$(echo "$line" | awk '{print $1}')
    health=$(docker inspect --format='{{.State.Health.Status}}' "$service" 2>/dev/null || echo "N/A")
    echo "  $service: $health"
done
