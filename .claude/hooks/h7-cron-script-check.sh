#!/bin/bash
# H7: PostToolUse — Edit/Write on scripts/nightly/ or .githooks/ 경로 후 경고
# Triggered by Claude Code PostToolUse hook on Edit or Write tool.
# Reads JSON event from stdin (Claude Code hook protocol).
#
# If the modified file is under scripts/nightly/ or .githooks/,
# outputs a reminder to smoke-test the script before committing.

set -euo pipefail

EVENT=$(cat)

# Extract the file path that was edited/written.
FILE_PATH=$(echo "$EVENT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    # Edit tool: tool_input.file_path
    # Write tool: tool_input.file_path
    fp = d.get('tool_input', {}).get('file_path', '')
    print(fp)
except Exception:
    print('')
" 2>/dev/null)

[ -z "$FILE_PATH" ] && exit 0

# Check if the file is in a cron/hook script directory.
if echo "$FILE_PATH" | grep -qE '(scripts/nightly/|\.githooks/|scripts/cron/)'; then
    echo ""
    echo "H7 WARN: Cron/hook script changed: $FILE_PATH"
    echo "  Verify with smoke test before committing:"
    echo "    bash $FILE_PATH --dry-run   (if supported)"
    echo "    bash -n $FILE_PATH          (syntax check)"
    echo "  Last cron logs: ls ~/pivoxquant-cron-logs/ | tail -5"
    echo ""
fi

exit 0
