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
