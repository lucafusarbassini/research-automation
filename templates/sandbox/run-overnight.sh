#!/bin/bash
# =============================================================================
# ricet Overnight Loop — runs Claude N times with per-iteration timeout
# =============================================================================
# Each iteration has a hard timeout to prevent stalls. If Claude gets stuck
# (context window, API errors, etc.), the timeout kills it and the loop
# advances to the next iteration. Auto-commits after each iteration.
#
# Usage (from host):
#   docker exec -d ricet-sandbox gosu agent bash /workspace/sandbox/run-overnight.sh
#   docker exec -d ricet-sandbox gosu agent bash /workspace/sandbox/run-overnight.sh 30 60
#
# Watch output:
#   docker exec ricet-sandbox tail -f /agent-logs/claude-output.log
#
# Args:
#   $1 = number of iterations (default: 30)
#   $2 = timeout per iteration in minutes (default: 60)
# =============================================================================

set -e
cd /workspace

ITERATIONS=${1:-30}
TIMEOUT_MIN=${2:-60}
PROMPT_FILE="/workspace/martinprompt.md"
LOGFILE="/agent-logs/claude-output.log"

if [ ! -f "$PROMPT_FILE" ]; then
    echo "ERROR: $PROMPT_FILE not found!" | tee -a "$LOGFILE"
    echo "Create martinprompt.md in your project root with the agent instructions." | tee -a "$LOGFILE"
    exit 1
fi

PROMPT=$(cat "$PROMPT_FILE")

echo "=== ricet Overnight Loop Starting ===" | tee -a "$LOGFILE"
echo "Iterations: ${ITERATIONS}" | tee -a "$LOGFILE"
echo "Timeout per iteration: ${TIMEOUT_MIN} minutes" | tee -a "$LOGFILE"
echo "" | tee -a "$LOGFILE"

for i in $(seq 1 "$ITERATIONS"); do
    echo "=== Iteration ${i}/${ITERATIONS} ===" | tee -a "$LOGFILE"
    START=$(date +%s)

    # Run Claude with hard timeout and line-buffered output
    stdbuf -oL timeout "${TIMEOUT_MIN}m" claude --dangerously-skip-permissions --model opus -p "$PROMPT" 2>&1 | tee -a "$LOGFILE" || {
        EXIT_CODE=$?
        if [ "$EXIT_CODE" -eq 124 ]; then
            echo "" | tee -a "$LOGFILE"
            echo "[LOOP] Iteration ${i} TIMED OUT after ${TIMEOUT_MIN} minutes." | tee -a "$LOGFILE"
        else
            echo "" | tee -a "$LOGFILE"
            echo "[LOOP] Iteration ${i} exited with code ${EXIT_CODE}." | tee -a "$LOGFILE"
        fi
    }

    ELAPSED=$(( ($(date +%s) - START) / 60 ))
    echo "[LOOP] Iteration ${i} ran for ${ELAPSED} minutes." | tee -a "$LOGFILE"

    # Auto-commit any uncommitted work after each iteration
    git add -A 2>/dev/null
    git commit -m "ricet overnight: auto-commit after iteration ${i} (${ELAPSED}min)" 2>/dev/null || true

    # Brief pause between iterations
    sleep 5
done

echo "=== ricet Overnight Loop Complete: ${ITERATIONS} iterations ===" | tee -a "$LOGFILE"
