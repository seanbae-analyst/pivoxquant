#!/bin/bash
# H6: SessionStart — HANDOVER.md 최신 200줄 자동 출력
# Triggered by Claude Code SessionStart hook.
# Outputs the first 200 lines of HANDOVER.md to give the session context
# about current project state, open PRs, external actions, etc.
#
# Token budget: ~200 lines * ~15 tokens ≈ 3,000 tokens per session start.
# Full file (4734 lines) would be ~70,000 tokens — this head-only approach
# saves 95% of tokens while preserving the most-recent prepend section.

set -euo pipefail

HANDOVER="/Users/seanbae/Desktop/취준/pivoxquant/HANDOVER.md"
LINES=200

if [ ! -f "$HANDOVER" ]; then
    echo "[H6] HANDOVER.md not found at $HANDOVER — skipping context injection."
    exit 0
fi

echo "=== [H6] HANDOVER.md — top ${LINES} lines (auto-injected by SessionStart hook) ==="
head -n "$LINES" "$HANDOVER"
echo "=== [H6] End of HANDOVER excerpt. Full file: $HANDOVER ==="

exit 0
