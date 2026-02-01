#!/bin/bash
# Runs before each task

echo "$(date -Iseconds) | TASK_START | $TASK_NAME" >> state/sessions/current.log

# Check disk space
DISK_FREE=$(df -h /workspace | tail -1 | awk '{print $4}')
echo "Disk free: $DISK_FREE"

# Load relevant knowledge
if [ -f "knowledge/ENCYCLOPEDIA.md" ]; then
    echo "Encyclopedia loaded ($(wc -l < knowledge/ENCYCLOPEDIA.md) lines)"
fi

# Claude-flow pre-task hook
if command -v npx &>/dev/null; then
    npx claude-flow@v3alpha hooks pre-task \
        --task "$TASK_NAME" \
        --session "$SESSION_ID" \
        2>/dev/null || true
fi
