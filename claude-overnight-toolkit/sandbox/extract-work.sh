#!/bin/bash
# =============================================================================
# Extract work from the sandbox back to the host
# =============================================================================
# Copies the agent's workspace changes as a git patch that you can review
# and selectively apply to your actual project.
#
# Usage:
#   ./extract-work.sh                  # Generate patch file
#   ./extract-work.sh --apply          # Generate and apply patch
# =============================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
PATCH_DIR="${SCRIPT_DIR}/patches"
PATCH_FILE="${PATCH_DIR}/sandbox_work_${TIMESTAMP}.patch"
APPLY=false

# Load container name from .env if available
CONTAINER_NAME="${CONTAINER_NAME:-my-sandbox}"
if [ -f "${SCRIPT_DIR}/.env" ]; then
    source "${SCRIPT_DIR}/.env"
fi

if [ "$1" = "--apply" ]; then
    APPLY=true
fi

if ! docker ps --format '{{.Names}}' | grep -q "${CONTAINER_NAME}"; then
    echo "ERROR: Sandbox container '${CONTAINER_NAME}' is not running."
    echo "Start it first: ./start-sandbox.sh"
    exit 1
fi

mkdir -p "$PATCH_DIR"

echo "=== Extracting work from sandbox ==="

# Get the baseline commit (first commit)
BASELINE=$(docker exec "${CONTAINER_NAME}" gosu agent git -C /workspace rev-list --max-parents=0 HEAD 2>/dev/null | head -1)

# Generate diff against baseline
docker exec "${CONTAINER_NAME}" gosu agent bash -c "cd /workspace && git diff ${BASELINE} HEAD" > "$PATCH_FILE"

if [ ! -s "$PATCH_FILE" ]; then
    echo "No changes detected."
    rm -f "$PATCH_FILE"
    exit 0
fi

LINES=$(wc -l < "$PATCH_FILE")
echo "Patch generated: ${PATCH_FILE} (${LINES} lines)"

# Sync common output directories
echo "Syncing output directories..."
for dir in experiments reports outputs data; do
    docker cp "${CONTAINER_NAME}:/workspace/${dir}/." "${PROJECT_DIR}/${dir}/" 2>/dev/null || true
done

# Show summary
echo ""
echo "Files changed:"
docker exec "${CONTAINER_NAME}" gosu agent bash -c "cd /workspace && git diff ${BASELINE} HEAD --stat | tail -10"

# Extract logs
LOG_FILE="${PATCH_DIR}/sandbox_log_${TIMESTAMP}.log"
docker exec "${CONTAINER_NAME}" cat /agent-logs/sandbox.log > "$LOG_FILE" 2>/dev/null || true
echo ""
echo "Sandbox log: ${LOG_FILE}"

CLAUDE_LOG="${PATCH_DIR}/claude_output_${TIMESTAMP}.log"
docker exec "${CONTAINER_NAME}" cat /agent-logs/claude-output.log > "$CLAUDE_LOG" 2>/dev/null || true
echo "Claude output: ${CLAUDE_LOG}"

if [ "$APPLY" = true ]; then
    echo ""
    echo "Applying patch to project..."
    cd "$PROJECT_DIR"
    git apply --stat "$PATCH_FILE"
    echo ""
    read -p "Apply these changes? [y/N] " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        git apply "$PATCH_FILE"
        echo "Changes applied successfully."
    else
        echo "Cancelled. Patch saved at: ${PATCH_FILE}"
    fi
else
    echo ""
    echo "To review the patch:"
    echo "  less ${PATCH_FILE}"
    echo ""
    echo "To apply the patch to your project:"
    echo "  cd ${PROJECT_DIR}"
    echo "  git apply ${PATCH_FILE}"
    echo ""
    echo "Or run: ./extract-work.sh --apply"
fi
