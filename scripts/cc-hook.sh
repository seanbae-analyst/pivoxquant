#!/bin/bash
# Claude Code -> Command Center Hook
# Receives JSON event via stdin and sends log to Command Center API.
# Designed for async execution -- must not block Claude Code operations.
#
# Supported hook events:
#   PreToolUse     -> status: in_progress
#   PostToolUse    -> status: completed
#   SubagentStart  -> status: in_progress
#   SubagentStop   -> status: completed

set -euo pipefail

readonly CC_API_URL="http://localhost:5050/api/command-center/log"
readonly TIMEOUT_SECONDS=3

EVENT=$(cat)

# Extract fields using python3 (pre-installed on macOS).
# Each field defaults to empty string on missing key or parse error.
extract_field() {
  local field="$1"
  echo "$EVENT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('$field', ''))
except Exception:
    print('')
" 2>/dev/null
}

HOOK_EVENT=$(extract_field "hook_event_name")
TOOL_NAME=$(extract_field "tool_name")
AGENT_TYPE=$(extract_field "agent_type")

# Determine source and status based on hook event type.
SOURCE=""
STATUS=""
COMMAND_DESC=""

case "$HOOK_EVENT" in
  PreToolUse)
    SOURCE="$TOOL_NAME"
    STATUS="in_progress"
    COMMAND_DESC="$TOOL_NAME called"
    ;;
  PostToolUse)
    SOURCE="$TOOL_NAME"
    STATUS="completed"
    COMMAND_DESC="$TOOL_NAME completed"
    ;;
  SubagentStart)
    SOURCE="${AGENT_TYPE:-subagent}"
    STATUS="in_progress"
    COMMAND_DESC="${AGENT_TYPE:-subagent} started"
    ;;
  SubagentStop)
    SOURCE="${AGENT_TYPE:-subagent}"
    STATUS="completed"
    COMMAND_DESC="${AGENT_TYPE:-subagent} stopped"
    ;;
  *)
    # Unsupported event -- exit silently.
    exit 0
    ;;
esac

# Skip if source could not be determined.
[ -z "$SOURCE" ] && exit 0

# Build JSON payload safely using python3 with environment variables.
# This avoids shell quoting issues with tool names containing special characters.
PAYLOAD=$(CC_SOURCE="$SOURCE" CC_COMMAND="$COMMAND_DESC" CC_STATUS="$STATUS" python3 -c "
import json, os
print(json.dumps({
    'source': os.environ['CC_SOURCE'],
    'command': os.environ['CC_COMMAND'],
    'status': os.environ['CC_STATUS']
}))
" 2>/dev/null)

[ -z "$PAYLOAD" ] && exit 0

# Send log to Command Center API.
# - timeout prevents hanging on unresponsive server
# - stdout/stderr suppressed to avoid polluting Claude Code output
# - non-zero exit from curl is intentionally ignored (|| true)
curl -s \
  --max-time "$TIMEOUT_SECONDS" \
  -X POST "$CC_API_URL" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  > /dev/null 2>&1 || true

exit 0
