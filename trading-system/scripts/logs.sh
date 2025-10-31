#!/usr/bin/env bash
# ==============================================================================
# View Logs Script
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

SERVICE="${1:-}"

cd "$PROJECT_ROOT"

if [ -z "$SERVICE" ]; then
    # Show all logs
    docker-compose logs -f --tail=100
else
    # Show specific service logs
    docker-compose logs -f --tail=100 "$SERVICE"
fi
