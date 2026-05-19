#!/usr/bin/env bash
# vercel_canary.sh — Critical path liveness probe for pivoxquant.com
#
# Schedule: CC scheduled-task cron "*/30 * * * *" (every 30 minutes)
# Paths   : / /api/health /login /pricing
# Expected: 200 for public pages, 200/302 for /login (may redirect)
#
# Optional:
#   SLACK_WEBHOOK_URL    — Slack alert on any probe failure
#   FRONTEND_URL         — Override frontend base URL (default: https://pivoxquant.com)
#   RAILWAY_BACKEND_URL  — Override backend base URL (for /api/health)
#   CANARY_TIMEOUT       — curl timeout in seconds (default: 10)
set -euo pipefail

LOG_PREFIX="[vercel_canary $(date -u '+%Y-%m-%dT%H:%M:%SZ')]"
log()  { echo "${LOG_PREFIX} $*"; }
warn() { echo "${LOG_PREFIX} WARN: $*" >&2; }

FRONTEND_URL="${FRONTEND_URL:-https://pivoxquant.com}"
RAILWAY_BACKEND_URL="${RAILWAY_BACKEND_URL:-https://web-production-7b484b.up.railway.app}"
TIMEOUT="${CANARY_TIMEOUT:-10}"

FAIL_COUNT=0
FAIL_REASONS=""

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

probe() {
  local label="$1"
  local url="$2"
  local allowed="$3"   # space-separated acceptable HTTP codes

  local code
  code=$(curl -fsS -o /dev/null -w "%{http_code}" \
    --max-time "${TIMEOUT}" \
    --location \
    "${url}" 2>/dev/null) || code="000"

  local ok=false
  for accepted in ${allowed}; do
    if [ "${code}" = "${accepted}" ]; then
      ok=true
      break
    fi
  done

  if ${ok}; then
    log "OK   [${code}] ${label} — ${url}"
  else
    warn "FAIL [${code}] ${label} — ${url} (expected: ${allowed})"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    FAIL_REASONS="${FAIL_REASONS}| ${label} got ${code} (expected ${allowed})"
  fi
}

log "Starting canary probes..."

# Frontend paths
probe "homepage"  "${FRONTEND_URL}/"          "200"
probe "login"     "${FRONTEND_URL}/login"      "200 302"
probe "pricing"   "${FRONTEND_URL}/pricing"    "200"

# Backend health (Vercel rewrites /api/* → Railway; also probe Railway directly)
probe "api-health-vercel"  "${FRONTEND_URL}/api/health"          "200"
probe "api-health-railway" "${RAILWAY_BACKEND_URL}/api/health"   "200"

log "Canary complete: ${FAIL_COUNT} failure(s)"

if [ "${FAIL_COUNT}" -gt 0 ]; then
  MSG="vercel-canary ALERT (${FAIL_COUNT} failure(s)) ${FAIL_REASONS}"
  warn "${MSG}"
  notify_slack "${MSG}"
  exit 1
fi

log "All probes passed."
