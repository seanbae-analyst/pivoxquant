#!/bin/bash
# H5: PreToolUse — rm -rf / git reset --hard / git clean -fdx 차단
# Triggered by Claude Code PreToolUse hook on Bash tool.
# Reads JSON event from stdin (Claude Code hook protocol).
#
# Safe paths (always allowed): /tmp/, node_modules/, __pycache__/
# Blocked patterns: rm -rf, rm -fr, git reset --hard, git clean -fdx
#
# Exit codes:
#   0 — allow (no destructive pattern or safe path)
#   2 — block (destructive command detected outside safe paths)

set -euo pipefail

EVENT=$(cat)

# Extract the bash command from the hook event JSON.
COMMAND=$(echo "$EVENT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    # Claude Code PreToolUse sends tool_input.command for Bash tool
    cmd = d.get('tool_input', {}).get('command', '')
    print(cmd)
except Exception:
    print('')
" 2>/dev/null)

[ -z "$COMMAND" ] && exit 0

# Use Python for robust pattern matching and safe-path logic.
RESULT=$(python3 - "$COMMAND" <<'PYEOF'
import sys, re

cmd = sys.argv[1]

# Destructive patterns
destructive_patterns = [
    r'rm\s+-[a-zA-Z]*r[a-zA-Z]*f\b',   # rm -rf, rm -fr, rm -Rf etc.
    r'rm\s+-[a-zA-Z]*f[a-zA-Z]*r\b',
    r'git\s+reset\s+--hard\b',
    r'git\s+clean\s+-[a-zA-Z]*f',       # git clean -f, -fd, -fdx, -fdX
]

# Safe path prefixes — if the ONLY paths in the command are these, allow
safe_prefixes = ['/tmp/', 'node_modules/', '__pycache__/']

is_destructive = any(re.search(p, cmd) for p in destructive_patterns)

if not is_destructive:
    print('allow')
    sys.exit(0)

# Check if all path-like arguments are under safe prefixes.
# Extract all path-like tokens (starting with / or relative paths that look like dirs).
# Strategy: remove the rm/git command and flags, then check remaining tokens.
tokens = cmd.split()
path_tokens = []
skip_next = False
for i, tok in enumerate(tokens):
    if skip_next:
        skip_next = False
        continue
    # Skip command names and flags
    if tok in ('rm', 'git', 'reset', 'clean', '--hard', '--dry-run', '-n'):
        continue
    if tok.startswith('-'):
        continue
    # This looks like a path or target
    path_tokens.append(tok)

if not path_tokens:
    # No explicit paths — be conservative and block (e.g., bare "git reset --hard")
    print('block')
    sys.exit(0)

# Check: are all tokens under safe prefixes?
all_safe = all(
    any(tok.startswith(prefix) for prefix in safe_prefixes)
    for tok in path_tokens
)

if all_safe:
    print('allow')
else:
    print('block')
PYEOF
)

if [ "$RESULT" = "block" ]; then
    echo "H5 BLOCKED: Destructive command detected."
    echo "Use --dry-run or confirm with user before running:"
    echo "  $COMMAND"
    echo "Auto-allowed safe paths: /tmp/, node_modules/, __pycache__/"
    exit 2
fi

exit 0
