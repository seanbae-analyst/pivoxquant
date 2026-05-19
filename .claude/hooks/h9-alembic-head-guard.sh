#!/bin/bash
# H9: PostToolUse — migrations/versions/*.py 변경 후 alembic head divergence 경고
# Triggered by Claude Code PostToolUse hook on Edit or Write tool.
#
# Mode controlled by PIVOX_H9_MODE env var:
#   warn     (default, 7-day trial) — log warning only, never block
#   enforce  (after 7-day trial)    — exit 2 to block commit (future use)
#
# Log: /tmp/h9-alembic-warn.log
# alembic must be on PATH or at venv/bin/alembic in project root.

set -euo pipefail

EVENT=$(cat)
MODE="${PIVOX_H9_MODE:-warn}"

# Extract the file path that was edited/written.
FILE_PATH=$(echo "$EVENT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    fp = d.get('tool_input', {}).get('file_path', '')
    print(fp)
except Exception:
    print('')
" 2>/dev/null)

[ -z "$FILE_PATH" ] && exit 0

# Only process migration version files.
if ! echo "$FILE_PATH" | grep -qE 'migrations/versions/.*\.py$'; then
    exit 0
fi

LOG="/tmp/h9-alembic-warn.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
PROJECT_ROOT="/Users/seanbae/Desktop/취준/pivoxquant"

# Find alembic binary: project venv first, then system PATH.
ALEMBIC_BIN=""
if [ -x "$PROJECT_ROOT/venv/bin/alembic" ]; then
    ALEMBIC_BIN="$PROJECT_ROOT/venv/bin/alembic"
elif command -v alembic >/dev/null 2>&1; then
    ALEMBIC_BIN=$(command -v alembic)
else
    echo "[$TIMESTAMP] H9: alembic not found — skipping head guard." >> "$LOG"
    exit 0
fi

# Locate alembic.ini: check project root first, then migrations/ subdir.
ALEMBIC_INI=""
if [ -f "$PROJECT_ROOT/alembic.ini" ]; then
    ALEMBIC_INI="$PROJECT_ROOT/alembic.ini"
elif [ -f "$PROJECT_ROOT/migrations/alembic.ini" ]; then
    ALEMBIC_INI="$PROJECT_ROOT/migrations/alembic.ini"
else
    echo "[$TIMESTAMP] H9: alembic.ini not found — skipping head guard." >> "$LOG"
    exit 0
fi

# Run alembic heads from project root (requires alembic.ini).
HEAD_OUTPUT=$(cd "$PROJECT_ROOT" && "$ALEMBIC_BIN" -c "$ALEMBIC_INI" heads 2>&1) || {
    echo "[$TIMESTAMP] H9: alembic heads failed — skipping. Output: $HEAD_OUTPUT" >> "$LOG"
    exit 0
}

HEAD_COUNT=$(echo "$HEAD_OUTPUT" | grep -c '(head)' 2>/dev/null) || HEAD_COUNT=0
# Trim whitespace from HEAD_COUNT (wc/grep can emit trailing spaces/newlines)
HEAD_COUNT=$(echo "$HEAD_COUNT" | tr -d '[:space:]')
# Ensure HEAD_COUNT is a valid integer
case "$HEAD_COUNT" in
    ''|*[!0-9]*) HEAD_COUNT=0 ;;
esac

echo "[$TIMESTAMP] H9: migration changed ($FILE_PATH), head_count=$HEAD_COUNT" >> "$LOG"
[ -n "$HEAD_OUTPUT" ] && echo "$HEAD_OUTPUT" >> "$LOG"

if [ "$HEAD_COUNT" -gt 1 ]; then
    echo ""
    echo "H9 WARN: Multiple alembic heads detected after editing $FILE_PATH"
    echo "  Head count: $HEAD_COUNT (expected: 1)"
    echo "  Heads:"
    echo "$HEAD_OUTPUT" | grep 'head)' | sed 's/^/    /'
    echo "  Fix: create a merge migration with 'alembic merge -m \"merge\" <rev1> <rev2>'"
    echo "  Full log: $LOG"
    echo ""

    if [ "$MODE" = "enforce" ]; then
        echo "H9 ENFORCE: blocking — resolve head divergence before proceeding."
        exit 2
    fi
fi

exit 0
