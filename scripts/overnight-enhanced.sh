#!/bin/bash
# Enhanced overnight autonomous research mode with auto-debug and monitoring
#
# Docker is REQUIRED by default for safety isolation. The script will
# automatically re-launch itself inside the ricet Docker container unless
# it detects it is already running inside one.
#
# To bypass Docker (advanced users only), pass --no-docker as the 3rd arg:
#   ./overnight-enhanced.sh 20 state/TODO.md --no-docker
set -euo pipefail

MAX_ITERATIONS=${1:-20}
TASK_FILE=${2:-state/TODO.md}
NO_DOCKER=${3:-}
MAX_RETRIES=3
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="state/sessions"
LOG_FILE="$LOG_DIR/overnight_${TIMESTAMP}.log"
METRICS_FILE="$LOG_DIR/overnight_${TIMESTAMP}_metrics.json"

# ---------------------------------------------------------------------------
# Docker enforcement: re-launch inside container unless already inside one
# ---------------------------------------------------------------------------
INSIDE_CONTAINER=false
if [ -f /.dockerenv ] || [ -f /run/.containerenv ]; then
    INSIDE_CONTAINER=true
fi

if [ "$INSIDE_CONTAINER" = false ] && [ "$NO_DOCKER" != "--no-docker" ]; then
    # Verify Docker is available
    if ! command -v docker &>/dev/null; then
        echo "ERROR: Docker is required for overnight mode."
        echo ""
        echo "Overnight mode runs with elevated permissions (--dangerously-skip-permissions)"
        echo "which allows Claude to execute arbitrary commands. Docker provides a safety"
        echo "sandbox so your host system is protected."
        echo ""
        echo "Install Docker: https://docs.docker.com/get-docker/"
        echo ""
        echo "Advanced users: pass '--no-docker' as the third argument to bypass."
        echo "  Usage: $0 [iterations] [task-file] [--no-docker]"
        exit 1
    fi

    if ! docker info &>/dev/null 2>&1; then
        echo "ERROR: Docker daemon is not running."
        echo "Start it with: sudo systemctl start docker (Linux)"
        echo "Or launch Docker Desktop (macOS / Windows)."
        exit 1
    fi

    # Build image if not present
    if ! docker image inspect ricet:latest &>/dev/null 2>&1; then
        echo "Docker image 'ricet:latest' not found. Building..."
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        docker build -t ricet:latest -f "$SCRIPT_DIR/../docker/Dockerfile" "$SCRIPT_DIR/.." || {
            echo "ERROR: Failed to build Docker image."
            exit 1
        }
    fi

    PROJECT_DIR="$(pwd)"
    CLAUDE_DIR="${HOME}/.claude"

    echo "Launching overnight mode inside Docker container..."
    exec docker run --rm -it \
        -v "${PROJECT_DIR}:/workspace" \
        -v "${CLAUDE_DIR}:/home/ricet/.claude:ro" \
        -w /workspace \
        --memory=8g \
        --cpus=8 \
        ricet:latest \
        bash scripts/overnight-enhanced.sh "$MAX_ITERATIONS" "$TASK_FILE"
fi

if [ "$NO_DOCKER" = "--no-docker" ] && [ "$INSIDE_CONTAINER" = false ]; then
    echo "WARNING: Running overnight mode WITHOUT Docker isolation."
    echo "Claude will have unrestricted access to your host system."
    echo "Press Ctrl+C within 10 seconds to abort..."
    sleep 10
fi

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

# --- Falsification checkpoint runner ---
# Runs the falsifier agent at a named checkpoint within an iteration.
# Usage: run_falsification_checkpoint <checkpoint_name> <context_message>
# Returns 0 if passed, 1 if issues found (non-fatal unless CRITICAL).
FALSIFIER_FAILURES=0

run_falsification_checkpoint() {
    local checkpoint_name="$1"
    local context_msg="$2"
    local iteration="${3:-0}"

    log "  [FALSIFIER] Running checkpoint: $checkpoint_name (iter $iteration)"

    local falsifier_prompt="You are the Falsifier (Popperian) agent running an inline checkpoint.
Checkpoint: $checkpoint_name
Iteration: $iteration

Context of what just happened:
$context_msg

Quickly assess:
1. Are there any data leakage, statistical, or code correctness issues?
2. Are results plausible given the methodology?
3. Any red flags?

Reply: PASSED or FAILED, then list issues if any (with severity: low/medium/high/critical)."

    local falsifier_output
    if falsifier_output=$(claude --dangerously-skip-permissions -p "$falsifier_prompt" 2>&1); then
        echo "$falsifier_output" >> "$LOG_FILE"
        if echo "$falsifier_output" | grep -qi "FAILED\|CRITICAL"; then
            log "  [FALSIFIER] Checkpoint $checkpoint_name: ISSUES FOUND"
            FALSIFIER_FAILURES=$((FALSIFIER_FAILURES + 1))
            return 1
        else
            log "  [FALSIFIER] Checkpoint $checkpoint_name: PASSED"
            return 0
        fi
    else
        log "  [FALSIFIER] Checkpoint $checkpoint_name: could not run (non-fatal)"
        return 0
    fi
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

        # --- Falsification checkpoints (run DURING iteration, not just at end) ---

        # Checkpoint 1: After code changes - check git diff for issues
        DIFF_OUTPUT=$(git diff --stat 2>/dev/null || echo "no git diff available")
        if [ "$DIFF_OUTPUT" != "no git diff available" ] && [ -n "$DIFF_OUTPUT" ]; then
            FULL_DIFF=$(git diff 2>/dev/null | head -200)
            run_falsification_checkpoint "after_code_changes" \
                "Code was modified in this iteration. Git diff summary:\n$DIFF_OUTPUT\n\nDiff excerpt:\n$FULL_DIFF" \
                "$i" || true
        fi

        # Checkpoint 2: After test runs - check test output for red flags
        TEST_OUTPUT=$(tail -50 "$LOG_FILE" | grep -i -A5 "test\|pytest\|unittest\|assert" 2>/dev/null || echo "")
        if [ -n "$TEST_OUTPUT" ]; then
            run_falsification_checkpoint "after_test_run" \
                "Tests were run in this iteration. Relevant output:\n$TEST_OUTPUT" \
                "$i" || true
        fi

        # Checkpoint 3: After results - check for any generated results/outputs
        RESULT_FILES=$(find . -newer "$LOG_FILE" -name "*.csv" -o -name "*.json" -o -name "results*" 2>/dev/null | head -10 || echo "")
        RESULT_SUMMARY=$(tail -30 "$LOG_FILE")
        run_falsification_checkpoint "after_results" \
            "Iteration $i completed. New result files: $RESULT_FILES\n\nRecent output:\n$RESULT_SUMMARY" \
            "$i" || true

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
  "falsifier_issues": $FALSIFIER_FAILURES,
  "task_file": "$TASK_FILE"
}
EOF

log ""
log "=== Overnight Summary ==="
log "Iterations: $i | Successes: $SUCCESSES | Failures: $FAILURES | Falsifier issues: $FALSIFIER_FAILURES"
log "Metrics: $METRICS_FILE"

# Notify if configured
if [ -n "${NOTIFICATION_WEBHOOK:-}" ]; then
    curl -s -X POST "$NOTIFICATION_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"Overnight run complete: $SUCCESSES/$i succeeded\"}" || true
fi
