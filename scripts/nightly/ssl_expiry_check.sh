#!/usr/bin/env bash
# ssl_expiry_check.sh — TLS cert expiry probe for pivoxquant.com
#
# Schedule: CC scheduled-task cron "0 9 * * 1" (KST Monday 09:00)
# Threshold: alert if cert expires within 30 days
#
# Required:
#   (none — domain is hardcoded to pivoxquant.com)
#
# Optional:
#   SLACK_WEBHOOK_URL — Slack alert on imminent expiry
#   DOMAIN            — Override domain (default: pivoxquant.com)
#   ALERT_DAYS        — Override threshold in days (default: 30)
set -euo pipefail

LOG_PREFIX="[ssl_expiry $(date -u '+%Y-%m-%dT%H:%M:%SZ')]"
log()  { echo "${LOG_PREFIX} $*"; }
warn() { echo "${LOG_PREFIX} WARN: $*" >&2; }
fail() { echo "${LOG_PREFIX} ERROR: $*" >&2; exit 1; }

notify_slack() {
  local msg="$1"
  if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
    curl -fsS -X POST "${SLACK_WEBHOOK_URL}" \
      -H "Content-Type: application/json" \
      -d "{\"text\":\"${msg}\"}" >/dev/null 2>&1 || true
  else
    warn "SLACK_WEBHOOK_URL not set — Slack notification skipped"
  fi
}

DOMAIN="${DOMAIN:-pivoxquant.com}"
ALERT_DAYS="${ALERT_DAYS:-30}"

# --- check openssl available ---
if ! command -v openssl >/dev/null 2>&1; then
  warn "openssl not found — skipping SSL check (graceful skip)"
  exit 0
fi

log "Probing TLS cert for ${DOMAIN}:443..."

# Fetch cert NotAfter date; </dev/null closes stdin so s_client exits cleanly
NOT_AFTER=$(echo | openssl s_client \
  -servername "${DOMAIN}" \
  -connect "${DOMAIN}:443" 2>/dev/null \
  | openssl x509 -noout -enddate 2>/dev/null \
  | sed 's/notAfter=//')

if [ -z "${NOT_AFTER}" ]; then
  ERRMSG="Could not retrieve TLS cert from ${DOMAIN} — connection failed or no cert"
  warn "${ERRMSG}"
  notify_slack "ssl-expiry WARN: ${ERRMSG}"
  exit 0
fi

log "Certificate NotAfter: ${NOT_AFTER}"

# macOS date: use -j -f; Linux date: use -d
if date --version >/dev/null 2>&1; then
  # GNU date (Linux)
  EXPIRY_EPOCH=$(date -d "${NOT_AFTER}" +%s 2>/dev/null) || {
    warn "Could not parse date '${NOT_AFTER}' with GNU date"
    exit 0
  }
else
  # BSD date (macOS)
  EXPIRY_EPOCH=$(date -j -f "%b %d %T %Y %Z" "${NOT_AFTER}" +%s 2>/dev/null) || {
    warn "Could not parse date '${NOT_AFTER}' with BSD date"
    exit 0
  }
fi

NOW_EPOCH=$(date +%s)
DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))
log "Days until expiry: ${DAYS_LEFT}"

if [ "${DAYS_LEFT}" -lt "${ALERT_DAYS}" ]; then
  MSG="ssl-expiry ALERT: ${DOMAIN} TLS cert expires in ${DAYS_LEFT} days (${NOT_AFTER}). Renew NOW — Vercel auto-renew may have failed."
  warn "${MSG}"
  notify_slack "${MSG}"
  exit 1
else
  log "OK — cert for ${DOMAIN} is valid for ${DAYS_LEFT} more days"
fi
