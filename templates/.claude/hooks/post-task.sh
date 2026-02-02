#!/bin/bash
# Runs after each task

echo "$(date -Iseconds) | TASK_END | $TASK_NAME | $TASK_STATUS" >> state/sessions/current.log

# Auto-commit if changes
if [ -n "$(git status --porcelain)" ]; then
    git add -A
    git commit -m "Auto-commit after: $TASK_NAME"
fi

# Auto-update documentation (scans source, appends stubs to docs/API.md & README)
if [ "${RICET_AUTO_DOCS:-false}" = "true" ]; then
    python -c "from core.auto_docs import auto_update_docs; auto_update_docs(force=True)" 2>/dev/null || true
    if [ -n "$(git status --porcelain)" ]; then
        git add -A
        git commit -m "Auto-docs update after: $TASK_NAME"
    fi
fi

# Update progress
echo "- [x] $TASK_NAME ($(date +%H:%M))" >> state/PROGRESS.md

# Claude-flow post-task hook
if command -v npx &>/dev/null; then
    npx claude-flow@v3alpha hooks post-task \
        --task "$TASK_NAME" \
        --status "$TASK_STATUS" \
        --session "$SESSION_ID" \
        2>/dev/null || true
fi
