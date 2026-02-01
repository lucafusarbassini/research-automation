#!/bin/bash
# Enhanced overnight autonomous research mode with auto-debug and monitoring
set -euo pipefail

MAX_ITERATIONS=${1:-20}
TASK_FILE=${2:-state/TODO.md}
MAX_RETRIES=3
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="state/sessions"
LOG_FILE="$LOG_DIR/overnight_${TIMESTAMP}.log"
METRICS_FILE="$LOG_DIR/overnight_${TIMESTAMP}_metrics.json"

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"
}

check_resources() {
    local disk_pct
    disk_pct=$(df /workspace 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%' || echo "0")
    local mem_available
    mem_available=$(free -m 2>/dev/null | awk '/Mem:/{print $7}' || echo "0")

    if [ "$disk_pct" -gt 90 ]; then
        log "WARNING: Disk usage at ${disk_pct}%"
        return 1
    fi
    if [ "$mem_available" -lt 512 ]; then
        log "WARNING: Low memory (${mem_available}MB available)"
        return 1
    fi
    return 0
}

snapshot_on_error() {
    local iteration=$1
    local snapshot_dir="state/snapshots/error_${TIMESTAMP}_iter${iteration}"
    mkdir -p "$snapshot_dir"
    cp state/*.md "$snapshot_dir/" 2>/dev/null || true
    cp "$LOG_FILE" "$snapshot_dir/" 2>/dev/null || true
    log "Error snapshot saved to $snapshot_dir"
}

# --- Main ---

log "=== Enhanced Overnight Mode ==="
log "Max iterations: $MAX_ITERATIONS"
log "Task file: $TASK_FILE"
log "Max retries per iteration: $MAX_RETRIES"

if [ ! -f "$TASK_FILE" ]; then
    log "ERROR: Task file not found: $TASK_FILE"
    exit 1
fi

TASKS=$(cat "$TASK_FILE")
SUCCESSES=0
FAILURES=0

for i in $(seq 1 "$MAX_ITERATIONS"); do
    log "--- Iteration $i/$MAX_ITERATIONS ---"

    # Resource check
    if ! check_resources; then
        log "Resource check failed. Pausing for 60s..."
        sleep 60
        if ! check_resources; then
            log "Resources still insufficient. Stopping."
            break
        fi
    fi

    # Run with retries
    RETRY=0
    SUCCESS=false
    while [ "$RETRY" -lt "$MAX_RETRIES" ]; do
        if claude --dangerously-skip-permissions -p "$TASKS" >> "$LOG_FILE" 2>&1; then
            SUCCESS=true
            break
        else
            RETRY=$((RETRY + 1))
            log "Attempt $RETRY/$MAX_RETRIES failed"

            if [ "$RETRY" -lt "$MAX_RETRIES" ]; then
                # Auto-debug: ask Claude to diagnose the error
                LAST_ERROR=$(tail -20 "$LOG_FILE")
                claude --dangerously-skip-permissions -p \
                    "The previous task failed with this output. Diagnose and fix:\n$LAST_ERROR" \
                    >> "$LOG_FILE" 2>&1 || true
                sleep 10
            fi
        fi
    done

    if [ "$SUCCESS" = true ]; then
        SUCCESSES=$((SUCCESSES + 1))
        log "Iteration $i: SUCCESS"
    else
        FAILURES=$((FAILURES + 1))
        log "Iteration $i: FAILED after $MAX_RETRIES retries"
        snapshot_on_error "$i"
    fi

    # Check for completion signal
    if [ -f "state/DONE" ]; then
        log "DONE signal detected. Stopping."
        break
    fi

    # Brief pause
    sleep 5
done

# Write metrics
cat > "$METRICS_FILE" << EOF
{
  "started": "${TIMESTAMP}",
  "ended": "$(date -Iseconds)",
  "iterations": $i,
  "successes": $SUCCESSES,
  "failures": $FAILURES,
  "task_file": "$TASK_FILE"
}
EOF

log ""
log "=== Overnight Summary ==="
log "Iterations: $i | Successes: $SUCCESSES | Failures: $FAILURES"
log "Metrics: $METRICS_FILE"

# Notify if configured
if [ -n "${NOTIFICATION_WEBHOOK:-}" ]; then
    curl -s -X POST "$NOTIFICATION_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"Overnight run complete: $SUCCESSES/$i succeeded\"}" || true
fi
