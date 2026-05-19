#!/usr/bin/env bash
# PivoxQuant cron job dispatcher
# Usage: run.sh <job-name>
# Jobs: api-health | db-backup | ssl-expiry | vercel-canary | daily-regression
#       sendgrid-quota | morning-brief-kpi | signup-funnel
set -uo pipefail

JOB="${1:-}"
REPO="/Users/seanbae/Desktop/취준/pivoxquant"
LOG_DIR="${HOME}/pivoxquant-cron-logs"
LOG="${LOG_DIR}/${JOB}.log"
ENV_FILE="${HOME}/.pivoxquant-env"

if [ -z "$JOB" ]; then
  echo "Usage: $0 <job-name>" >&2
  exit 2
fi

mkdir -p "$LOG_DIR"
cd "$REPO" || { echo "REPO not found: $REPO" >&2; exit 2; }

# shellcheck disable=SC1090
[ -f "$ENV_FILE" ] && source "$ENV_FILE"

exec >> "$LOG" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] START $JOB"

EC=0
case "$JOB" in
  api-health)
    # Follow redirects (Vercel → Railway). Accept any 2xx as healthy.
    RESPONSE=$(curl -fsSL --max-time 15 -w "HTTPSTATUS:%{http_code}" https://pivoxquant.com/api/health 2>&1 || true)
    STATUS=$(echo "$RESPONSE" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    case "$STATUS" in
      2*) echo "api-health status=${STATUS} OK" ;;
      *)
        echo "api-health status=${STATUS} FAIL"
        if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
          curl -fsS -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"🚨 PivoxQuant api-health FAIL: status=${STATUS}\"}" \
            "$SLACK_WEBHOOK_URL" || true
        fi
        EC=1
        ;;
    esac
    ;;
  db-backup)
    bash scripts/nightly/db_backup.sh; EC=$?
    ;;
  ssl-expiry)
    bash scripts/nightly/ssl_expiry_check.sh; EC=$?
    ;;
  vercel-canary)
    bash scripts/nightly/vercel_canary.sh; EC=$?
    ;;
  daily-regression)
    bash scripts/nightly/daily_regression.sh; EC=$?
    ;;
  sendgrid-quota)
    ./venv/bin/python scripts/nightly/sendgrid_quota_check.py; EC=$?
    ;;
  morning-brief-kpi)
    ./venv/bin/python scripts/morning_brief/build_brief_kpi.py; EC=$?
    ;;
  signup-funnel)
    PIVOX_FUNNEL_ALERT_MODE="${PIVOX_FUNNEL_ALERT_MODE:-warn}" \
      ./venv/bin/python scripts/nightly/signup_funnel_check.py; EC=$?
    ;;
  *)
    echo "Unknown job: $JOB" >&2
    EC=2
    ;;
esac

echo "[$(date '+%Y-%m-%d %H:%M:%S')] END $JOB exit=$EC"
exit $EC
