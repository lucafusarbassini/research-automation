#!/bin/bash
# Setup script for claude-flow v3 integration.
# Checks prerequisites, installs claude-flow, and verifies.

set -e

MIN_NODE_VERSION=18
CLAUDE_FLOW_PKG="claude-flow@v3alpha"

echo "=== claude-flow setup ==="

# 1. Check Node.js
if ! command -v node &>/dev/null; then
    echo "ERROR: Node.js is not installed. Install Node.js >= ${MIN_NODE_VERSION} first."
    exit 1
fi

NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt "$MIN_NODE_VERSION" ]; then
    echo "ERROR: Node.js ${MIN_NODE_VERSION}+ required, found v$(node -v | sed 's/v//')."
    exit 1
fi
echo "Node.js v$(node -v | sed 's/v//') OK"

# 2. Check npx
if ! command -v npx &>/dev/null; then
    echo "ERROR: npx not found. Install npm (comes with Node.js)."
    exit 1
fi
echo "npx OK"

# 3. Install / warm up claude-flow
echo "Installing ${CLAUDE_FLOW_PKG}..."
npx -y "${CLAUDE_FLOW_PKG}" --version || {
    echo "WARNING: claude-flow installation or version check failed."
    echo "The system will fall back to built-in implementations."
    exit 0
}

echo ""
echo "=== claude-flow ready ==="
