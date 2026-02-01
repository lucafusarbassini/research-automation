#!/bin/bash
# Launch interactive research session
set -euo pipefail

SESSION_NAME=${1:-$(date +%Y%m%d_%H%M%S)}
SESSION_DIR="state/sessions"
SESSION_FILE="$SESSION_DIR/${SESSION_NAME}.json"

mkdir -p "$SESSION_DIR"

# Create session record
cat > "$SESSION_FILE" << EOF
{
  "name": "$SESSION_NAME",
  "started": "$(date -Iseconds)",
  "status": "active",
  "token_estimate": 0
}
EOF

echo "=== Interactive Session: $SESSION_NAME ==="
echo "Session file: $SESSION_FILE"
echo ""

# Launch Claude Code
claude --session-id "$SESSION_NAME"

# Mark session as completed
python3 -c "
import json
from pathlib import Path
f = Path('$SESSION_FILE')
d = json.loads(f.read_text())
d['status'] = 'completed'
from datetime import datetime
d['ended'] = datetime.now().isoformat()
f.write_text(json.dumps(d, indent=2))
" 2>/dev/null || true

echo "Session $SESSION_NAME ended."
