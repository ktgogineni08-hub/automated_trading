#!/usr/bin/env bash
# ==============================================================================
# Stop Services Script
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${YELLOW}⏸️  Stopping Trading System...${NC}"

cd "$PROJECT_ROOT"
docker-compose down

echo -e "${GREEN}✅ Services stopped${NC}"
echo ""
echo "To remove volumes as well: docker-compose down -v"
echo "To start again: ./scripts/start.sh"
