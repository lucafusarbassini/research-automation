#!/bin/bash
# =============================================================================
# Start the Claude Agent Sandbox
# =============================================================================
# Usage:
#   ./start-sandbox.sh              # Start with defaults
#   ./start-sandbox.sh --hours 12   # Custom timeout
#   ./start-sandbox.sh --attach     # Start and immediately attach
# =============================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Defaults
ATTACH=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --hours)
            export SANDBOX_TIMEOUT_HOURS="$2"
            shift 2
            ;;
        --attach)
            ATTACH=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--hours N] [--attach]"
            echo ""
            echo "Options:"
            echo "  --hours N    Set sandbox timeout in hours (default: from .env or 10)"
            echo "  --attach     Attach to Claude session immediately after start"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check for .env file
if [ ! -f ".env" ]; then
    echo "WARNING: .env file not found. Using defaults."
    echo "To customize, copy the example:"
    echo "  cp .env.example .env"
    echo ""
fi

# Load .env if available
CONTAINER_NAME="${CONTAINER_NAME:-my-sandbox}"
if [ -f .env ]; then
    source .env
fi

echo "=== Starting Overnight Sandbox ==="
echo "Container: ${CONTAINER_NAME}"
echo "Timeout:   ${SANDBOX_TIMEOUT_HOURS:-10} hours"
echo ""

# Build and start
echo "Building sandbox image..."
docker compose -f docker-compose.sandbox.yml build

echo "Starting sandbox container..."
docker compose -f docker-compose.sandbox.yml up -d

echo ""
echo "Waiting for container to be ready..."
sleep 15

echo ""
echo "=== Sandbox Ready ==="
echo ""
echo "Commands:"
echo "  # Run Claude overnight loop (30 iterations, 60 min each):"
echo "  docker exec -d ${CONTAINER_NAME} gosu agent bash /workspace/sandbox/run-overnight.sh 30 60"
echo ""
echo "  # Watch output live:"
echo "  docker exec ${CONTAINER_NAME} tail -f /agent-logs/claude-output.log"
echo ""
echo "  # Attach interactively:"
echo "  docker exec -it ${CONTAINER_NAME} gosu agent bash"
echo ""
echo "  # Run Claude interactively:"
echo "  docker exec -it ${CONTAINER_NAME} gosu agent claude"
echo ""
echo "  # Extract work when done:"
echo "  ./extract-work.sh"
echo ""
echo "  # Stop the sandbox:"
echo "  ./stop-sandbox.sh"
echo ""

if [ "$ATTACH" = true ]; then
    echo "Attaching to sandbox..."
    sleep 3
    docker exec -it "${CONTAINER_NAME}" gosu agent claude
fi
