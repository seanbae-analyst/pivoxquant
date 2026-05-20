#!/usr/bin/env bash
# railway_recovery_watch.sh — Railway 글로벌 장애(2026-05-19, Google Cloud 차단)
# 복구 감지기. pivoxquant.com/api/health 가 200 되면 복구로 판단.
#
# 복구 시:
#   - ~/railway-recovered.flag 생성 (중복 알림 방지 + 다음 세션 신호)
#   - Slack 알림 (SLACK_WEBHOOK_URL 있으면)
#   - 로그 "RECOVERED"
# RUN_SCHEDULER=1 은 Railway 에 이미 설정됨 → 복구 시 26 APScheduler jobs 자동 ON.
#
# crontab: */10 * * * * (10분마다)
set -uo pipefail

FLAG="${HOME}/railway-recovered.flag"
URL="https://pivoxquant.com/api/health"
TS="$(date '+%Y-%m-%d %H:%M:%S')"

# 이미 복구 감지했으면 재실행 불필요 (cron 자체는 사용자가 나중에 제거)
if [ -f "$FLAG" ]; then
  echo "[$TS] already recovered (flag exists) — skip"
  exit 0
fi

STATUS=$(curl -fsSL --max-time 15 -o /dev/null -w "%{http_code}" "$URL" 2>/dev/null || echo "000")

case "$STATUS" in
  2*)
    echo "[$TS] 🎉 RECOVERED — ${URL} status=${STATUS}"
    {
      echo "recovered_at=$TS"
      echo "status=$STATUS"
    } > "$FLAG"
    if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
      curl -fsS -X POST -H 'Content-type: application/json' \
        --data "{\"text\":\"🎉 PivoxQuant Railway 백엔드 복구됨 (status=${STATUS}). RUN_SCHEDULER=1 이라 자동화 26개 자동 ON. Vercel RAILWAY_BACKEND_URL 연결 + 검증 필요.\"}" \
        "$SLACK_WEBHOOK_URL" >/dev/null 2>&1 || true
    fi
    ;;
  *)
    echo "[$TS] still down — ${URL} status=${STATUS} (Railway 장애 진행 중: status.railway.com)"
    ;;
esac
exit 0
