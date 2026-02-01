#!/bin/bash
# Runs on task error

echo "$(date -Iseconds) | ERROR | $TASK_NAME | $ERROR_MSG" >> state/sessions/current.log

# Save state for debugging
cp -r state/ state/backup_$(date +%Y%m%d_%H%M%S)/

# Notify if configured
if [ -n "$NOTIFICATION_WEBHOOK" ]; then
    curl -X POST "$NOTIFICATION_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"Error in $PROJECT_NAME: $ERROR_MSG\"}"
fi
