#!/bin/bash
# =============================================================================
# Auto-shutdown watchdog with git commit before exit
# =============================================================================
# Enforces a maximum runtime for the sandbox. At 75% and 90% of the timeout,
# it logs warnings. When time is up, it auto-commits all work and shuts down.
# =============================================================================

TIMEOUT_SECONDS=$(( ${SANDBOX_TIMEOUT_HOURS:-8} * 3600 ))
WARN_75=$(( TIMEOUT_SECONDS * 75 / 100 ))
WARN_90=$(( TIMEOUT_SECONDS * 90 / 100 ))
LOGFILE="${AGENT_LOGS}/sandbox.log"
ELAPSED=0

# Detect user-switch tool
if command -v gosu &>/dev/null; then
    RUN_AS="gosu agent"
elif command -v su-exec &>/dev/null; then
    RUN_AS="su-exec agent"
else
    RUN_AS=""
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WATCHDOG] $*" | tee -a "$LOGFILE"
}

while [ $ELAPSED -lt $TIMEOUT_SECONDS ]; do
    sleep 60
    ELAPSED=$((ELAPSED + 60))

    if [ $ELAPSED -eq $WARN_75 ]; then
        REMAINING=$(( (TIMEOUT_SECONDS - ELAPSED) / 60 ))
        log "WARNING: 75% of timeout reached. ~${REMAINING} minutes remaining."
    fi
    if [ $ELAPSED -eq $WARN_90 ]; then
        REMAINING=$(( (TIMEOUT_SECONDS - ELAPSED) / 60 ))
        log "WARNING: 90% of timeout reached. ~${REMAINING} minutes remaining."
    fi
done

log "TIMEOUT REACHED (${SANDBOX_TIMEOUT_HOURS}h). Shutting down sandbox."
log "Saving uncommitted work..."
cd "${WORKSPACE}" 2>/dev/null
$RUN_AS git add -A 2>/dev/null
$RUN_AS git commit -m "Watchdog auto-save before shutdown" 2>/dev/null || true
log "Work saved."

sleep 60
kill 1 2>/dev/null
