#!/bin/bash
set -e

LOGFILE="${AGENT_LOGS}/sandbox.log"

# Detect which user-switch tool is available (su-exec on Alpine, gosu on Debian)
if command -v gosu &>/dev/null; then
    RUN_AS="gosu agent"
elif command -v su-exec &>/dev/null; then
    RUN_AS="su-exec agent"
else
    RUN_AS=""
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOGFILE"
}

log "=== Sandbox Starting ==="
log "Timeout: ${SANDBOX_TIMEOUT_HOURS} hours"
log "Workspace: ${WORKSPACE}"

# -------------------------------------------------------
# 1. (Optional) Start Docker-in-Docker daemon
# -------------------------------------------------------
if command -v dockerd-entrypoint.sh &>/dev/null; then
    log "Starting Docker daemon (Docker-in-Docker)..."
    dockerd-entrypoint.sh dockerd &>/dev/null &
    DOCKERD_PID=$!
    for i in $(seq 1 30); do
        if docker info &>/dev/null; then
            log "Docker daemon ready."
            break
        fi
        [ "$i" -eq 30 ] && log "WARNING: Docker daemon did not start within 30s."
        sleep 1
    done
fi

# -------------------------------------------------------
# 2. Copy project files into workspace (isolation layer)
#    ONLY on first run — never overwrite existing work!
# -------------------------------------------------------
if [ -d "${WORKSPACE}/.git" ]; then
    log "Existing workspace with git repo found — PRESERVING work (no copy)."
elif [ -d "/project-source" ] && [ "$(ls -A /project-source 2>/dev/null)" ]; then
    log "First run: copying project files into workspace..."
    cp -a /project-source/. "${WORKSPACE}/"
    chown -R agent:agent "${WORKSPACE}"
    log "Project files copied."
else
    log "No project source mounted at /project-source. Workspace is empty."
fi

# -------------------------------------------------------
# 3. Copy Claude credentials with proper permissions
# -------------------------------------------------------
if [ -d "/claude-source" ] && [ "$(ls -A /claude-source 2>/dev/null)" ]; then
    log "Copying Claude credentials to agent home..."
    mkdir -p /home/agent/.claude
    cp -a /claude-source/. /home/agent/.claude/
    chown -R agent:agent /home/agent/.claude
    log "Claude credentials copied."
else
    log "WARNING: No Claude credentials mounted. Agent may not be able to authenticate."
fi

# -------------------------------------------------------
# 4. Configure git and initialize workspace repo
# -------------------------------------------------------
$RUN_AS git config --global user.email "sandbox-agent@overnight"
$RUN_AS git config --global user.name "Sandbox Agent"

if [ ! -d "${WORKSPACE}/.git" ]; then
    $RUN_AS git -C "${WORKSPACE}" init
    $RUN_AS git -C "${WORKSPACE}" add -A
    $RUN_AS git -C "${WORKSPACE}" commit -m "Sandbox baseline snapshot" 2>/dev/null || true
    log "Git repo initialized in workspace with baseline snapshot."
else
    log "Existing git repo found in workspace."
fi

# -------------------------------------------------------
# 5. Install Python dependencies (if requirements.txt exists)
# -------------------------------------------------------
if [ -f "${WORKSPACE}/requirements.txt" ]; then
    log "Installing Python dependencies..."
    $RUN_AS pip install --user -r "${WORKSPACE}/requirements.txt" 2>&1 | tail -5
    log "Python dependencies installed."
fi

# -------------------------------------------------------
# 6. Start the watchdog timer
# -------------------------------------------------------
log "Starting watchdog (auto-shutdown in ${SANDBOX_TIMEOUT_HOURS}h)..."
/usr/local/bin/watchdog.sh &
WATCHDOG_PID=$!

# -------------------------------------------------------
# 7. Ready — run command or idle
# -------------------------------------------------------
log "=== Sandbox Ready ==="
CONTAINER_NAME="${CONTAINER_NAME:-sandbox}"
log "To attach: docker exec -it ${CONTAINER_NAME} bash"
log "To run Claude: docker exec -it ${CONTAINER_NAME} ${RUN_AS} claude"
log ""

if [ $# -gt 0 ]; then
    log "Running command: $*"
    exec $RUN_AS "$@"
else
    log "Sandbox idle - waiting for interactive session..."
    trap 'log "Received shutdown signal."; kill ${DOCKERD_PID:-} $WATCHDOG_PID 2>/dev/null; exit 0' SIGTERM SIGINT
    while true; do
        sleep 60
    done
fi
