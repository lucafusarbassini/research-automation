#!/bin/bash
# Project setup script - run once after cloning or init
set -euo pipefail

echo "=== ricet Setup ==="

# Create required directories
mkdir -p state/sessions
mkdir -p state/snapshots
mkdir -p knowledge
mkdir -p figures
mkdir -p outputs

# Initialize state files if missing
if [ ! -f state/TODO.md ]; then
    echo "# TODO" > state/TODO.md
    echo "" >> state/TODO.md
    echo "- [ ] Review GOAL.md and refine success criteria" >> state/TODO.md
fi

if [ ! -f state/PROGRESS.md ]; then
    echo "# Progress" > state/PROGRESS.md
    echo "" >> state/PROGRESS.md
fi

# Check Python
if command -v python3 &> /dev/null; then
    echo "Python: $(python3 --version)"
else
    echo "WARNING: python3 not found"
fi

# Check Claude Code
if command -v claude &> /dev/null; then
    echo "Claude Code: available"
else
    echo "WARNING: claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
fi

# Check git
if command -v git &> /dev/null; then
    echo "Git: $(git --version)"
else
    echo "WARNING: git not found"
fi

echo ""
echo "Setup complete. Run 'ricet start' to begin."
