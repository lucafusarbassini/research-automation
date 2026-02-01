#!/bin/bash
# Runs after each task

echo "$(date -Iseconds) | TASK_END | $TASK_NAME | $TASK_STATUS" >> state/sessions/current.log

# Auto-commit if changes
if [ -n "$(git status --porcelain)" ]; then
    git add -A
    git commit -m "Auto-commit after: $TASK_NAME"
fi

# Update progress
echo "- [x] $TASK_NAME ($(date +%H:%M))" >> state/PROGRESS.md
