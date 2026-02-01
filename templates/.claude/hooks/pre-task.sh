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
