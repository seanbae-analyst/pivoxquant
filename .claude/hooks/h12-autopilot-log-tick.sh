#!/usr/bin/env bash
# h12-autopilot-log-tick.sh
# 세션 종료 시(Stop 이벤트) autopilot_log.md에 짧은 entry append.
# 목적: autopilot_log.md 가 다시 dead 되지 않게 자동 tick 박기.
# 0원 — 로컬 git/ls만 사용, 외부 호출 없음.

set -euo pipefail

LOG="/Users/seanbae/.claude/projects/-Users-seanbae-Desktop---/memory/autopilot_log.md"
REPO="/Users/seanbae/dev/pivoxquant"

# autopilot_log.md 없으면 silently exit (사용자 환경 차이 방지)
[ -f "$LOG" ] || exit 0

# repo 없으면 exit
[ -d "$REPO/.git" ] || exit 0

DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M)

# 오늘 이미 tick 박혔으면 skip (한 세션당 1회만)
TODAY_MARKER="<!-- session-tick:${DATE} -->"
if grep -qF "$TODAY_MARKER" "$LOG" 2>/dev/null; then
  exit 0
fi

# 최근 commit 1줄 (혹시 repo가 비어있을 수 있어 fail-safe)
LAST_COMMIT=$(cd "$REPO" && git log -1 --pretty=format:'%h %s' 2>/dev/null | head -c 100 || echo "no commits")

# 오늘 변경된 파일 수 (working tree)
CHANGED=$(cd "$REPO" && git status --porcelain 2>/dev/null | wc -l | tr -d ' ' || echo "?")

# append 짧은 entry
{
  echo ""
  echo "### ${DATE} ${TIME} session-end tick"
  echo "$TODAY_MARKER"
  echo "- last commit: \`${LAST_COMMIT}\`"
  echo "- working tree changed files: ${CHANGED}"
} >> "$LOG"

exit 0
