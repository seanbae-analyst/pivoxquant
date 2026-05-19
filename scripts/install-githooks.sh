#!/usr/bin/env bash
# PivoxQuant — install local git hooks
# ----------------------------------------------------------------------
# 2026-05-19 P0: Activates .githooks/ for this clone.
# Run once after cloning (or after any new hook is added).
#
# Usage:
#   bash scripts/install-githooks.sh
#
# What it does:
#   1. git config core.hooksPath .githooks  (points git to .githooks/)
#   2. chmod +x all .githooks/* files
#   3. Verifies detect-secrets is installed (required for H1 secret scan)
#   4. Prints summary
# ----------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
  echo "ERROR: not inside a git repository."
  exit 1
fi
cd "$REPO_ROOT"

echo "PivoxQuant git hooks installer"
echo "================================"
echo ""

# 1) Point git to .githooks/
echo "[1/4] git config core.hooksPath .githooks"
git config core.hooksPath .githooks
echo "  done."

# 2) Make all hooks executable.
echo ""
echo "[2/4] chmod +x .githooks/*"
HOOK_COUNT=0
for hook in .githooks/*; do
  [ -f "$hook" ] || continue
  case "$hook" in
    *.sample|*.md) continue ;;
  esac
  chmod +x "$hook"
  HOOK_COUNT=$((HOOK_COUNT + 1))
  echo "  chmod +x $hook"
done
echo "  $HOOK_COUNT hook(s) made executable."

# 3) Verify detect-secrets (required for H1 entropy scan in pre-commit).
echo ""
echo "[3/4] checking detect-secrets (required for secret entropy scan)"
if command -v detect-secrets >/dev/null 2>&1; then
  DS_VER=$(detect-secrets --version 2>/dev/null || echo "unknown")
  echo "  detect-secrets $DS_VER — OK"
else
  echo "  detect-secrets NOT found."
  echo ""
  echo "  Install it with:"
  echo "    pip install detect-secrets"
  echo "  or add it to requirements-dev.txt and:"
  echo "    pip install -r requirements-dev.txt"
  echo ""
  echo "  Without detect-secrets, the entropy scan in pre-commit will be skipped"
  echo "  (hook degrades gracefully — other checks still run)."
fi

# 4) Print summary.
echo ""
echo "[4/4] summary"
echo ""
echo "  Active hooks:"
for hook in .githooks/*; do
  [ -f "$hook" ] || continue
  case "$hook" in
    *.sample|*.md) continue ;;
  esac
  NAME=$(basename "$hook")
  LINES=$(wc -l < "$hook" | tr -d ' ')
  echo "    .githooks/$NAME  ($LINES lines)"
done
echo ""
echo "  Bypass single commit:   git commit --no-verify"
echo "  Bypass single push:     git push --no-verify"
echo "  Blocking smoke mode:    PIVOX_PREPUSH_BLOCK=1 git push"
echo ""
echo "  Regenerate secret baseline:"
echo "    detect-secrets scan routes/ services/ models/ .githooks/ scripts/ > .secrets.baseline"
echo "    git add .secrets.baseline && git commit -m 'chore: refresh detect-secrets baseline'"
echo ""
echo "Installation complete."
