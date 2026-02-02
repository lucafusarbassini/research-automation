#!/bin/bash
# Overnight autonomous research mode
set -euo pipefail

MAX_ITERATIONS=${1:-20}
TASK_FILE=${2:-state/TODO.md}
LOG_FILE="state/sessions/overnight_$(date +%Y%m%d_%H%M%S).log"

echo "=== Overnight Mode ===" | tee "$LOG_FILE"
echo "Max iterations: $MAX_ITERATIONS" | tee -a "$LOG_FILE"
echo "Task file: $TASK_FILE" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE" | tee -a "$LOG_FILE"
echo "Started: $(date -Iseconds)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

if [ ! -f "$TASK_FILE" ]; then
    echo "ERROR: Task file not found: $TASK_FILE" | tee -a "$LOG_FILE"
    exit 1
fi

TASKS=$(cat "$TASK_FILE")

for i in $(seq 1 "$MAX_ITERATIONS"); do
    echo "--- Iteration $i/$MAX_ITERATIONS ($(date +%H:%M:%S)) ---" | tee -a "$LOG_FILE"

    # Run Claude with task
    if claude --dangerously-skip-permissions -p "$TASKS" >> "$LOG_FILE" 2>&1; then
        echo "Iteration $i: SUCCESS" | tee -a "$LOG_FILE"
    else
        echo "Iteration $i: ERROR (exit code $?)" | tee -a "$LOG_FILE"

        # Snapshot state on error for debugging
        SNAPSHOT_DIR="state/snapshots/error_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$SNAPSHOT_DIR"
        cp -r state/*.md "$SNAPSHOT_DIR/" 2>/dev/null || true
        echo "State snapshot saved to $SNAPSHOT_DIR" | tee -a "$LOG_FILE"
    fi

    # Check for completion signal
    if [ -f "state/DONE" ]; then
        echo "DONE signal detected. Stopping." | tee -a "$LOG_FILE"
        break
    fi

    # Brief pause between iterations
    sleep 5
done

echo "" | tee -a "$LOG_FILE"
echo "Overnight mode finished at $(date -Iseconds)" | tee -a "$LOG_FILE"
echo "Total iterations: $i" | tee -a "$LOG_FILE"

# ---------------------------------------------------------------------------
# Send notification summary via Python notification system
# ---------------------------------------------------------------------------
ERRORS=$(grep -c "ERROR" "$LOG_FILE" 2>/dev/null || echo 0)
SUCCESSES=$(grep -c "SUCCESS" "$LOG_FILE" 2>/dev/null || echo 0)

SUMMARY="Overnight run complete. Iterations: $i/$MAX_ITERATIONS, Successes: $SUCCESSES, Errors: $ERRORS. Log: $LOG_FILE"

# Also append summary to PROGRESS.md
if [ -f "state/PROGRESS.md" ]; then
    echo "" >> state/PROGRESS.md
    echo "## Overnight Run $(date +%Y-%m-%d)" >> state/PROGRESS.md
    echo "" >> state/PROGRESS.md
    echo "$SUMMARY" >> state/PROGRESS.md
fi

# Send via Python notification system (Slack, email, desktop)
python3 -c "
from core.notifications import notify
notify('$SUMMARY', title='ricet overnight', level='success' if $ERRORS == 0 else 'warning')
" 2>/dev/null || echo "Notification delivery failed (channels may not be configured)" | tee -a "$LOG_FILE"
