#!/bin/bash
# =============================================================================
# Auto-backup: Continuously sync sandbox work to host
# =============================================================================
# Run in a separate terminal while the sandbox is working. Periodically
# copies experiment results, state files, and logs to the host.
#
# Usage:
#   ./auto-backup.sh [interval_minutes]
#   ./auto-backup.sh 15  # Backup every 15 minutes (default: 20)
# =============================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$SCRIPT_DIR"

# Load container name from .env if available
CONTAINER_NAME="${CONTAINER_NAME:-my-sandbox}"
if [ -f .env ]; then
    source .env
fi

INTERVAL=${1:-20}
BACKUP_DIR="./backups"
mkdir -p "$BACKUP_DIR"

echo "=== Auto-Backup Started ==="
echo "Container: ${CONTAINER_NAME}"
echo "Interval: ${INTERVAL} minutes"
echo "Press Ctrl+C to stop"
echo ""

while true; do
    if ! docker ps --format '{{.Names}}' | grep -q "${CONTAINER_NAME}"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sandbox not running. Waiting..."
        sleep 60
        continue
    fi

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Syncing..."

    # Sync experiment results, reports, and outputs to host
    for dir in experiments reports outputs; do
        mkdir -p "${PROJECT_DIR}/${dir}"
        docker cp "${CONTAINER_NAME}:/workspace/${dir}/." "${PROJECT_DIR}/${dir}/" 2>/dev/null || true
    done

    # Sync state files
    for f in memory.md progress.md todo.md; do
        docker cp "${CONTAINER_NAME}:/workspace/${f}" "${PROJECT_DIR}/${f}" 2>/dev/null || true
    done

    # Extract Claude output log
    docker exec "${CONTAINER_NAME}" cat /agent-logs/claude-output.log > "${BACKUP_DIR}/claude-output-latest.log" 2>/dev/null || true

    # Show recent git activity
    LAST_COMMIT=$(docker exec "${CONTAINER_NAME}" gosu agent git -C /workspace log --oneline -1 2>/dev/null || echo "none")
    echo "  Last commit: ${LAST_COMMIT}"
    echo "  Next backup in ${INTERVAL} minutes..."
    echo ""

    sleep $((INTERVAL * 60))
done
