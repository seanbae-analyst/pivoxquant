#!/usr/bin/env bash
# production_watch.sh — pivoxquant.com/api/health UP/DOWN 전환 감지 + gmail 알림
# crontab: */15 * * * * (15분마다). 상태 전환 시에만 이메일 → 스팸 0.
# Slack webhook 대체 (Slack 워크스페이스 없음). notify_email.sh (SendGrid) 사용.
set -uo pipefail

URL="https://pivoxquant.com/api/health"
STATE_FILE="${HOME}/.pivoxquant-prod-state"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TS="$(date '+%Y-%m-%d %H:%M:%S')"

PREV=$(cat "$STATE_FILE" 2>/dev/null || echo "UNKNOWN")
STATUS=$(curl -fsSL --max-time 15 -o /dev/null -w "%{http_code}" "$URL" 2>/dev/null || echo "000")
case "$STATUS" in 2*) CURR="UP";; *) CURR="DOWN";; esac

echo "[$TS] prod=$CURR (status=$STATUS, prev=$PREV)"

if [ "$CURR" != "$PREV" ]; then
  echo "$CURR" > "$STATE_FILE"
  # 첫 실행(UNKNOWN)은 baseline — 알림 안 함. 전환 시에만.
  if [ "$PREV" != "UNKNOWN" ]; then
    if [ "$CURR" = "DOWN" ]; then
      bash "$SCRIPT_DIR/notify_email.sh" \
        "[PivoxQuant] 🚨 백엔드 다운" \
        "production 백엔드 응답 없음 (status=$STATUS) — $TS KST.
확인: https://pivoxquant.com/api/health
Railway 장애 여부: https://status.railway.com"
    else
      bash "$SCRIPT_DIR/notify_email.sh" \
        "[PivoxQuant] ✅ 백엔드 복구" \
        "production 백엔드 복구됨 (status=$STATUS) — $TS KST.
RUN_SCHEDULER=1 이라 자동화 26개 자동 ON."
    fi
  fi
fi
exit 0
