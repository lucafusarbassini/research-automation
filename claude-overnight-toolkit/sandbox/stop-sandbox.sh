#!/bin/bash
# =============================================================================
# Stop the sandbox container
# =============================================================================
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Stopping Sandbox ==="
docker compose -f docker-compose.sandbox.yml down

echo "Sandbox stopped."
echo ""
echo "To extract work before cleanup:"
echo "  ./extract-work.sh"
echo ""
echo "To remove persistent volumes (DESTROYS workspace):"
echo "  docker compose -f docker-compose.sandbox.yml down -v"
