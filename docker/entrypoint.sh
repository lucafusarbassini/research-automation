#!/usr/bin/env bash
# =============================================================================
# research-automation Docker entrypoint
#
# Usage:
#   docker compose up          -> starts web terminal on :7681
#   docker run ... --shell     -> drops into interactive bash
#   docker run ... --overnight -> runs overnight autonomous mode
#   docker run ... <command>   -> runs arbitrary command
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Colours for terminal output
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${CYAN}[entrypoint]${NC} $*"; }
warn()  { echo -e "${YELLOW}[entrypoint]${NC} $*"; }
error() { echo -e "${RED}[entrypoint]${NC} $*"; }
ok()    { echo -e "${GREEN}[entrypoint]${NC} $*"; }

# ---------------------------------------------------------------------------
# 1. Check required API keys
# ---------------------------------------------------------------------------
info "Checking environment..."

MISSING_KEYS=()

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    MISSING_KEYS+=("ANTHROPIC_API_KEY")
fi

if [ ${#MISSING_KEYS[@]} -gt 0 ]; then
    warn "Missing API keys: ${MISSING_KEYS[*]}"
    warn "Some features will be unavailable."
    warn "Set them in docker-compose.yml or pass with -e flag."
else
    ok "ANTHROPIC_API_KEY present."
fi

# Optional keys — just inform
[ -n "${OPENAI_API_KEY:-}" ]   && ok "OPENAI_API_KEY present."
[ -n "${GITHUB_TOKEN:-}" ]     && ok "GITHUB_TOKEN present."

# ---------------------------------------------------------------------------
# 2. Load .env if present (for local development)
# ---------------------------------------------------------------------------
if [ -f /workspace/.env ]; then
    info "Loading /workspace/.env"
    set -a
    # shellcheck source=/dev/null
    source /workspace/.env
    set +a
fi

# ---------------------------------------------------------------------------
# 3. Activate the Python virtualenv
# ---------------------------------------------------------------------------
if [ -d /opt/venv ]; then
    export PATH="/opt/venv/bin:$PATH"
fi

# ---------------------------------------------------------------------------
# 4. Set up claude-flow (idempotent, fast on repeat runs)
# ---------------------------------------------------------------------------
SETUP_SCRIPT="/opt/research-automation/scripts/setup_claude_flow.sh"
if [ -x "$SETUP_SCRIPT" ]; then
    info "Running claude-flow setup..."
    if bash "$SETUP_SCRIPT" 2>&1 | while IFS= read -r line; do echo "  $line"; done; then
        ok "claude-flow ready."
    else
        warn "claude-flow setup returned non-zero (continuing anyway)."
    fi
else
    warn "setup_claude_flow.sh not found — skipping."
fi

# ---------------------------------------------------------------------------
# 5. Ensure workspace has git initialised
# ---------------------------------------------------------------------------
if [ -d /workspace ] && [ ! -d /workspace/.git ]; then
    info "Initialising git in /workspace..."
    git init /workspace -q 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# 6. Dispatch based on arguments
# ---------------------------------------------------------------------------
print_banner() {
    echo -e "${BOLD}"
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║   research-automation  v0.2.0            ║"
    echo "  ║   Python $(python3 --version 2>&1 | cut -d' ' -f2)  |  Node $(node --version)         ║"
    echo "  ╚══════════════════════════════════════════╝"
    echo -e "${NC}"
}

case "${1:-}" in
    --web)
        print_banner
        info "Starting web terminal on port ${TTYD_PORT:-7681}..."
        info "Connect your browser to http://localhost:${TTYD_PORT:-7681}"

        # Install ttyd if not present
        if ! command -v ttyd &>/dev/null; then
            info "Installing ttyd..."
            apt-get update -qq && apt-get install -y -qq ttyd >/dev/null 2>&1 || {
                # Fallback: download binary
                TTYD_VERSION="1.7.7"
                curl -fsSL "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.$(uname -m)" \
                    -o /usr/local/bin/ttyd && chmod +x /usr/local/bin/ttyd
            }
        fi

        exec ttyd \
            --port "${TTYD_PORT:-7681}" \
            --writable \
            --title-fixed "research-automation" \
            --base-path / \
            bash --login -c "cd /workspace && print_banner() { echo 'research-automation ready. Type: research --help'; }; print_banner; exec bash"
        ;;

    --shell)
        print_banner
        info "Dropping into interactive shell..."
        cd /workspace
        exec bash --login
        ;;

    --overnight)
        print_banner
        info "Starting overnight autonomous mode..."
        shift
        cd /workspace
        exec research overnight "$@"
        ;;

    --help|-h)
        print_banner
        echo "Usage: docker run research-automation [MODE]"
        echo ""
        echo "Modes:"
        echo "  --web          Start web terminal (default, port 7681)"
        echo "  --shell        Interactive bash shell"
        echo "  --overnight    Run overnight autonomous mode"
        echo "  <command>      Run arbitrary command"
        echo ""
        echo "Environment variables:"
        echo "  ANTHROPIC_API_KEY   Required for Claude features"
        echo "  OPENAI_API_KEY      Optional, for embeddings"
        echo "  GITHUB_TOKEN        Optional, for GitHub integration"
        echo "  TTYD_PORT           Web terminal port (default: 7681)"
        exit 0
        ;;

    *)
        # Pass through to arbitrary command
        exec "$@"
        ;;
esac
