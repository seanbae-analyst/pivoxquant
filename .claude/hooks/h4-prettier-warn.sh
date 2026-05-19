#!/bin/bash
# H4: PostToolUse — Edit/Write on frontend/src/**/*.{ts,tsx,js,jsx} 후 prettier check
# Triggered by Claude Code PostToolUse hook on Edit or Write tool.
#
# Mode controlled by PIVOX_H4_MODE env var:
#   warn     (default, 7-day trial) — prettier --check only, no write
#   enforce  (after 7-day trial)    — prettier --write applied
#
# Log: /tmp/h4-prettier-dryrun.log
# prettier binary: frontend/node_modules/.bin/prettier (project-local)

set -euo pipefail

EVENT=$(cat)
MODE="${PIVOX_H4_MODE:-warn}"

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

# Only process frontend TS/TSX/JS/JSX files.
if ! echo "$FILE_PATH" | grep -qE 'frontend/src/.*\.(ts|tsx|js|jsx)$'; then
    exit 0
fi

# Must be an actual file that exists.
[ -f "$FILE_PATH" ] || exit 0

PRETTIER_BIN="/Users/seanbae/Desktop/취준/pivoxquant/frontend/node_modules/.bin/prettier"

# Fallback to npx prettier if project-local binary is missing.
if [ ! -x "$PRETTIER_BIN" ]; then
    if command -v npx >/dev/null 2>&1; then
        PRETTIER_BIN="npx prettier"
    else
        echo "[H4] prettier not found (checked node_modules/.bin and npx) — skipping." >> /tmp/h4-prettier-dryrun.log 2>&1
        exit 0
    fi
fi

LOG="/tmp/h4-prettier-dryrun.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

if [ "$MODE" = "enforce" ]; then
    # enforce mode: actually format the file.
    # shellcheck disable=SC2086
    if $PRETTIER_BIN --write "$FILE_PATH" >> "$LOG" 2>&1; then
        echo "[$TIMESTAMP] H4 ENFORCE: formatted $FILE_PATH" >> "$LOG"
    else
        echo "[$TIMESTAMP] H4 ENFORCE: prettier failed on $FILE_PATH" >> "$LOG"
    fi
else
    # warn mode: check only, no write.
    # shellcheck disable=SC2086
    CHECK_OUTPUT=$($PRETTIER_BIN --check "$FILE_PATH" 2>&1)
    CHECK_EXIT=$?
    echo "[$TIMESTAMP] H4 WARN-ONLY ($FILE_PATH):" >> "$LOG"
    echo "$CHECK_OUTPUT" >> "$LOG"

    if [ "$CHECK_EXIT" -ne 0 ]; then
        echo ""
        echo "H4 WARN: $FILE_PATH has prettier formatting issues (warn-only mode)."
        echo "  To fix: cd frontend && npx prettier --write $(basename "$FILE_PATH")"
        echo "  To enable auto-format: export PIVOX_H4_MODE=enforce"
        echo "  Full diff logged: $LOG"
        echo ""
    fi
fi

exit 0
