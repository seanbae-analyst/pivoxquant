#!/usr/bin/env bash
# PivoxQuant cron job dispatcher
# Usage: run.sh <job-name>
# Jobs: api-health | db-backup | ssl-expiry | vercel-canary | daily-regression
#       sendgrid-quota | morning-brief-kpi | signup-funnel
#       credentials-expiry | env-audit | error-rate
#       ticker-name-audit | email-compliance | section101-check
#       checkout-followup | email-scheduler | inactive-nudge
#       commerce-registration
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
  credentials-expiry)
    ./venv/bin/python scripts/nightly/credentials_expiry_check.py; EC=$?
    ;;
  env-audit)
    bash scripts/nightly/env_sync_audit.sh; EC=$?
    ;;
  error-rate)
    # baseline mode default per audit rule #5; flip to alert after 1 week
    # of samples by setting PIVOX_ERROR_RATE_MODE=alert in ~/.pivoxquant-env.
    PIVOX_ERROR_RATE_MODE="${PIVOX_ERROR_RATE_MODE:-baseline}" \
      ./venv/bin/python scripts/nightly/error_rate_check.py; EC=$?
    ;;
  ticker-name-audit)
    ./venv/bin/python scripts/nightly/ticker_name_audit.py; EC=$?
    ;;
  email-compliance)
    ./venv/bin/python scripts/nightly/email_compliance_check.py; EC=$?
    ;;
  section101-check)
    ./venv/bin/python scripts/nightly/section101_compliance_check.py; EC=$?
    ;;
  checkout-followup)
    # Wave G C-M1 — Stripe checkout.session.expired 1h follow-up.
    # Suggested cadence: ``*/15 * * * *`` (every 15 min). The +1h delay
    # only needs ±15min precision. Dispatcher is gated by
    # ``PIVOX_CHECKOUT_FOLLOWUP_ENABLED`` env (default false) — when
    # false the queue rows are stamped ``feature_flag_off`` and the
    # cron exits 0 without emailing. Variance-flag flip drains pending
    # backlog automatically.
    ./venv/bin/python scripts/nightly/checkout_followup_dispatcher.py; EC=$?
    ;;
  email-scheduler)
    # Wave G S5 — D+0/D+3/D+7 onboarding sequence dispatcher.
    # Suggested cadence: ``*/15 * * * *`` (every 15 min). D+0 needs
    # ±15min precision (immediate post-signup); D+3 / D+7 are calendar
    # nudges where the cron lag is negligible. Dispatcher is gated by
    # ``PIVOX_ONBOARDING_SEQUENCE_ENABLED`` env (default false) — when
    # false the queue rows are stamped ``feature_flag_off`` and the
    # cron exits 0 without emailing. Variance-flag flip after the
    # lawyer's Q-S1 answer drains pending backlog automatically.
    ./venv/bin/python scripts/nightly/email_scheduler_dispatcher.py; EC=$?
    ;;
  commerce-registration)
    # Wave I L-3 — 통신판매업 신고 D-day 월간 알림 (전자상거래법 §12).
    # Suggested cadence (APScheduler 가 primary): ``0 9 1 * *`` (매월 1일 09:00 KST).
    # macOS crontab fallback 시 동일 cron expression 사용. feature flag
    # ``PIVOX_COMMERCE_REGISTERED=true`` 설정 시 스크립트 내부에서 즉시 exit 0 —
    # 신고 완료 후 ~/.pivoxquant-env 1줄 추가만으로 알림 자동 중단.
    ./venv/bin/python scripts/nightly/commerce_registration_reminder.py; EC=$?
    ;;
  inactive-nudge)
    # Wave G C-S2 — 24h onboarding inactive nudge.
    # Suggested cadence: ``0 * * * *`` (every hour, on the hour). The
    # window is a rolling 1h slice (24h-25h ago), so the 1h cadence
    # gives every signup exactly one shot. Dispatcher is gated by
    # ``PIVOX_INACTIVE_NUDGE_ENABLED`` env (default false) AND
    # ``PIVOX_CS1_CONSENT_ENABLED`` (default false) — when either is
    # off the cron exits 0 without emailing. Both flips required;
    # CS1 framework gates the per-user INFORMATION consent at the
    # sender layer regardless of this script.
    ./venv/bin/python scripts/nightly/inactive_nudge_dispatcher.py; EC=$?
    ;;
  *)
    echo "Unknown job: $JOB" >&2
    EC=2
    ;;
esac

echo "[$(date '+%Y-%m-%d %H:%M:%S')] END $JOB exit=$EC"
exit $EC
