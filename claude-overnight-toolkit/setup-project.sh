#!/bin/bash
# =============================================================================
# Set up a new project for Claude overnight autonomous operation
# =============================================================================
# Usage:
#   ./setup-project.sh /path/to/your/project
#   ./setup-project.sh /path/to/your/project --dind    # Docker-in-Docker variant
# =============================================================================

set -e
TOOLKIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "$1" ]; then
    echo "Usage: $0 /path/to/your/project [--dind]"
    echo ""
    echo "Options:"
    echo "  --dind    Use Docker-in-Docker Dockerfile (for projects that need Docker)"
    echo "            Default: Python-slim Dockerfile (for ML/data science)"
    exit 1
fi

PROJECT_DIR="$1"
USE_DIND=false
if [ "$2" = "--dind" ]; then
    USE_DIND=true
fi

echo "=== Setting up Claude Overnight Toolkit ==="
echo "Project: ${PROJECT_DIR}"
echo "Variant: $([ "$USE_DIND" = true ] && echo 'Docker-in-Docker' || echo 'Python/ML')"
echo ""

# Create directory structure
mkdir -p "${PROJECT_DIR}/sandbox"
mkdir -p "${PROJECT_DIR}/.claude/agents"
mkdir -p "${PROJECT_DIR}/experiments"
mkdir -p "${PROJECT_DIR}/reports/figures"
mkdir -p "${PROJECT_DIR}/backups"

# Copy sandbox files
echo "Copying sandbox infrastructure..."
cp "${TOOLKIT_DIR}/sandbox/sandbox-entrypoint.sh" "${PROJECT_DIR}/sandbox/"
cp "${TOOLKIT_DIR}/sandbox/watchdog.sh" "${PROJECT_DIR}/sandbox/"
cp "${TOOLKIT_DIR}/sandbox/docker-compose.sandbox.yml" "${PROJECT_DIR}/sandbox/"
cp "${TOOLKIT_DIR}/sandbox/.env.example" "${PROJECT_DIR}/sandbox/"
cp "${TOOLKIT_DIR}/sandbox/start-sandbox.sh" "${PROJECT_DIR}/sandbox/"
cp "${TOOLKIT_DIR}/sandbox/stop-sandbox.sh" "${PROJECT_DIR}/sandbox/"
cp "${TOOLKIT_DIR}/sandbox/run-overnight.sh" "${PROJECT_DIR}/sandbox/"
cp "${TOOLKIT_DIR}/sandbox/extract-work.sh" "${PROJECT_DIR}/sandbox/"
cp "${TOOLKIT_DIR}/sandbox/auto-backup.sh" "${PROJECT_DIR}/sandbox/"

# Copy appropriate Dockerfile
if [ "$USE_DIND" = true ]; then
    cp "${TOOLKIT_DIR}/sandbox/Dockerfile.dind" "${PROJECT_DIR}/sandbox/Dockerfile"
    # Enable privileged mode in compose
    sed -i 's/# privileged: true/privileged: true/' "${PROJECT_DIR}/sandbox/docker-compose.sandbox.yml"
    sed -i 's/dockerfile: Dockerfile.python/dockerfile: Dockerfile/' "${PROJECT_DIR}/sandbox/docker-compose.sandbox.yml"
else
    cp "${TOOLKIT_DIR}/sandbox/Dockerfile.python" "${PROJECT_DIR}/sandbox/Dockerfile"
    sed -i 's/dockerfile: Dockerfile.python/dockerfile: Dockerfile/' "${PROJECT_DIR}/sandbox/docker-compose.sandbox.yml"
fi

# Make scripts executable
chmod +x "${PROJECT_DIR}/sandbox/"*.sh

# Copy agent definitions
echo "Copying agent definitions..."
cp "${TOOLKIT_DIR}/agents/"*.md "${PROJECT_DIR}/.claude/agents/"

# Copy martinprompt
echo "Copying martinprompt.md..."
cp "${TOOLKIT_DIR}/martinprompt.md" "${PROJECT_DIR}/martinprompt.md"

# Copy state file templates (only if they don't exist)
echo "Copying state file templates..."
for f in CLAUDE.md task.md memory.md progress.md todo.md system.md; do
    if [ ! -f "${PROJECT_DIR}/${f}" ]; then
        cp "${TOOLKIT_DIR}/templates/${f}" "${PROJECT_DIR}/${f}"
    else
        echo "  Skipping ${f} (already exists)"
    fi
done

# Add sandbox entries to .gitignore if not already there
GITIGNORE="${PROJECT_DIR}/.gitignore"
touch "$GITIGNORE"
for pattern in "sandbox/.env" "sandbox/patches/" "sandbox/backups/" "__pycache__/" "*.pyc" ".env"; do
    if ! grep -qF "$pattern" "$GITIGNORE" 2>/dev/null; then
        echo "$pattern" >> "$GITIGNORE"
    fi
done

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit ${PROJECT_DIR}/task.md with your specific task"
echo "  2. Edit ${PROJECT_DIR}/sandbox/.env (copy from .env.example)"
echo "  3. (Optional) Customize martinprompt.md for your domain"
echo "  4. Start the sandbox:"
echo "       cd ${PROJECT_DIR}/sandbox && ./start-sandbox.sh"
echo "  5. Launch overnight loop:"
echo "       docker exec -d my-sandbox gosu agent bash /workspace/sandbox/run-overnight.sh"
echo "  6. Monitor:"
echo "       docker exec my-sandbox tail -f /agent-logs/claude-output.log"
echo "  7. Extract results:"
echo "       cd ${PROJECT_DIR}/sandbox && ./extract-work.sh"
