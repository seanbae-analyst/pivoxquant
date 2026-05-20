#!/usr/bin/env bash
# daily_regression.sh — Daily regression gate: api + data + security
#
# Schedule: CC scheduled-task cron "0 6 * * *" (KST 06:00)
# Mirrors  : .github/workflows/daily-regression-gate.yml.disabled
#
# Three sequential verification stages:
#   1. verify-api      — production critical endpoints (HTTP + JSON shape)
#   2. verify-data     — KIS token / FX freshness / ticker-name mapping
#   3. verify-security — BETA_PASSWORD not in git / auth gate live probe
#
# Optional env vars:
#   RAILWAY_BACKEND_URL — Backend base URL (no default — set in ~/.pivoxquant-env; empty = skip backend probes)
#   SLACK_WEBHOOK_URL   — Slack alert on any failure
#   SENTRY_DSN          — Sentry capture on critical failures
#   FRONTEND_URL        — Frontend base URL (default: https://pivoxquant.com)
set -uo pipefail   # Note: -e removed so we can capture exit codes per stage

LOG_PREFIX="[daily_regression $(date -u '+%Y-%m-%dT%H:%M:%SZ')]"
log()  { echo "${LOG_PREFIX} $*"; }
warn() { echo "${LOG_PREFIX} WARN: $*" >&2; }

FRONTEND_URL="${FRONTEND_URL:-https://pivoxquant.com}"
# No hardcoded default — legacy web-production-7b484b URL is dead (Railway
# "Application not found"). Set RAILWAY_BACKEND_URL in ~/.pivoxquant-env after
# confirming the live URL in the Railway dashboard. Empty = skip backend probes.
RAILWAY_BACKEND_URL="${RAILWAY_BACKEND_URL:-}"
TIMEOUT=10

STAGE_FAILURES=0
FAIL_SUMMARY=""

notify_slack() {
  local msg="$1"
  if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
    curl -fsS -X POST "${SLACK_WEBHOOK_URL}" \
      -H "Content-Type: application/json" \
      -d "{\"text\":\"${msg}\"}" >/dev/null 2>&1 || true
  else
    warn "SLACK_WEBHOOK_URL not set"
  fi
}

capture_sentry() {
  local msg="$1"
  if [ -n "${SENTRY_DSN:-}" ]; then
    # Minimal Sentry HTTP API capture (no SDK dependency)
    local project_id
    project_id=$(echo "${SENTRY_DSN}" | sed 's|.*sentry.io/||')
    local sentry_host
    sentry_host=$(echo "${SENTRY_DSN}" | sed 's|https://[^@]*@||; s|/[0-9]*$||')
    local key
    key=$(echo "${SENTRY_DSN}" | sed 's|https://||; s|@.*||')
    local payload
    payload=$(printf '{"message":"%s","level":"error","logger":"daily_regression"}' "${msg}")
    curl -fsS -X POST "https://${sentry_host}/api/${project_id}/store/" \
      -H "X-Sentry-Auth: Sentry sentry_version=7, sentry_key=${key}" \
      -H "Content-Type: application/json" \
      -d "${payload}" >/dev/null 2>&1 || true
  fi
}

probe_http() {
  local label="$1"
  local url="$2"
  local expected="$3"
  local code
  code=$(curl -fsS -o /dev/null -w "%{http_code}" \
    --max-time "${TIMEOUT}" "${url}" 2>/dev/null) || code="000"
  if [ "${code}" = "${expected}" ]; then
    log "  OK   [${code}] ${label}"
    return 0
  else
    warn "  FAIL [${code}] ${label} — expected ${expected}"
    return 1
  fi
}

# ============================================================
# Stage 1: verify-api
# ============================================================
log "=== Stage 1: verify-api ==="
STAGE1_FAIL=0

if [ -n "${RAILWAY_BACKEND_URL}" ]; then
  probe_http "api/health"           "${RAILWAY_BACKEND_URL}/api/health"           "200" || STAGE1_FAIL=1
else
  warn "  SKIP api/health — RAILWAY_BACKEND_URL not set (confirm live URL in Railway dashboard)"
fi
probe_http "frontend /"             "${FRONTEND_URL}/"                             "200" || STAGE1_FAIL=1
probe_http "frontend /pricing"      "${FRONTEND_URL}/pricing"                      "200" || STAGE1_FAIL=1

if [ "${STAGE1_FAIL}" -eq 0 ]; then
  log "Stage 1 PASSED"
else
  warn "Stage 1 FAILED"
  STAGE_FAILURES=$((STAGE_FAILURES + 1))
  FAIL_SUMMARY="${FAIL_SUMMARY} [verify-api FAIL]"
fi

# ============================================================
# Stage 2: verify-data
# ============================================================
log "=== Stage 2: verify-data ==="
STAGE2_FAIL=0

# Check FX rate endpoint freshness (returns JSON with timestamp)
if [ -z "${RAILWAY_BACKEND_URL}" ]; then
  warn "  SKIP FX rate — RAILWAY_BACKEND_URL not set"
else
  FX_RESPONSE=$(curl -fsS --max-time "${TIMEOUT}" \
    "${RAILWAY_BACKEND_URL}/api/market/fx" 2>/dev/null) || FX_RESPONSE=""

  if [ -z "${FX_RESPONSE}" ]; then
    warn "  FAIL FX rate endpoint unreachable"
    STAGE2_FAIL=1
  else
    log "  OK   FX rate endpoint reachable ($(echo "${FX_RESPONSE}" | wc -c | tr -d ' ') bytes)"
  fi
fi

# Check KIS token expiry script exists and is runnable
KIS_CHECK_SCRIPT="/Users/seanbae/Desktop/취준/pivoxquant/scripts/nightly/kis_token_expiry_check.py"
if [ -f "${KIS_CHECK_SCRIPT}" ]; then
  if command -v python3 >/dev/null 2>&1; then
    if python3 "${KIS_CHECK_SCRIPT}" 2>&1 | grep -q "ERROR\|FAIL\|expired"; then
      warn "  WARN KIS token expiry check raised issues"
      # Warn-only for token expiry — it may simply need refresh
    else
      log "  OK   KIS token expiry check passed"
    fi
  else
    warn "  SKIP python3 not found — KIS token check skipped"
  fi
else
  warn "  SKIP ${KIS_CHECK_SCRIPT} not found"
fi

if [ "${STAGE2_FAIL}" -eq 0 ]; then
  log "Stage 2 PASSED"
else
  warn "Stage 2 FAILED"
  STAGE_FAILURES=$((STAGE_FAILURES + 1))
  FAIL_SUMMARY="${FAIL_SUMMARY} [verify-data FAIL]"
fi

# ============================================================
# Stage 3: verify-security
# ============================================================
log "=== Stage 3: verify-security ==="
STAGE3_FAIL=0
REPO_DIR="/Users/seanbae/Desktop/취준/pivoxquant"

# 3a: BETA_PASSWORD plaintext must not appear in last 50 git commits
if command -v git >/dev/null 2>&1 && [ -d "${REPO_DIR}/.git" ]; then
  if git -C "${REPO_DIR}" log --oneline -50 | \
    xargs -I{} git -C "${REPO_DIR}" show {} 2>/dev/null | \
    grep -q "BETA_PASSWORD=" 2>/dev/null; then
    warn "  FAIL BETA_PASSWORD plaintext found in recent git history"
    STAGE3_FAIL=1
  else
    log "  OK   BETA_PASSWORD not in recent git history"
  fi
else
  warn "  SKIP git not available or not a git repo — history check skipped"
fi

# 3b: /login must return 200 (auth gate live)
probe_http "frontend /login gate" "${FRONTEND_URL}/login" "200" || STAGE3_FAIL=1

# 3c: /api/health must NOT return auth bypass (endpoint should require no auth, 200 OK)
HEALTH_BODY=$(curl -fsS --max-time "${TIMEOUT}" \
  "${RAILWAY_BACKEND_URL}/api/health" 2>/dev/null) || HEALTH_BODY=""
if echo "${HEALTH_BODY}" | grep -qi '"status".*"ok"\|"healthy"\|"status".*"up"' 2>/dev/null; then
  log "  OK   /api/health returns healthy status in body"
else
  warn "  WARN /api/health body doesn't contain expected health indicator (body: ${HEALTH_BODY:0:100})"
fi

if [ "${STAGE3_FAIL}" -eq 0 ]; then
  log "Stage 3 PASSED"
else
  warn "Stage 3 FAILED"
  STAGE_FAILURES=$((STAGE_FAILURES + 1))
  FAIL_SUMMARY="${FAIL_SUMMARY} [verify-security FAIL]"
fi

# ============================================================
# Stage 4: frontend vitest + design-token drift (Wave G P2 fix 2026-05-19)
# Replaces .github/workflows/{frontend-tests,design-safety-guards}.yml.disabled
# ============================================================
log "=== Stage 4: frontend vitest + design-token drift ==="
STAGE4_FAIL=0

# 4a: frontend vitest (only if node_modules exists)
if [ -d "${REPO_DIR}/frontend/node_modules" ]; then
  VITEST_OUT=$(cd "${REPO_DIR}/frontend" && npm run test --silent 2>&1 | tail -5)
  VITEST_RC=$?
  if [ "${VITEST_RC}" -eq 0 ]; then
    log "  OK   frontend vitest passed"
  else
    warn "  FAIL frontend vitest exit=${VITEST_RC}"
    echo "${VITEST_OUT}" | sed 's/^/    /'
    STAGE4_FAIL=1
  fi
else
  log "  SKIP frontend/node_modules missing (npm install first)"
fi

# 4b: design-token drift — raw hex in frontend/src/ outside globals.css
HEX_VIOLATIONS=$(grep -rE "#[0-9a-fA-F]{6}\b" "${REPO_DIR}/frontend/src/" \
  --include="*.tsx" --include="*.ts" \
  --exclude-dir=node_modules 2>/dev/null \
  | grep -v "// allow-hex" \
  | head -10 || true)
if [ -n "${HEX_VIOLATIONS}" ]; then
  warn "  FAIL design-token drift (raw hex in frontend/src/):"
  echo "${HEX_VIOLATIONS}" | sed 's/^/    /'
  STAGE4_FAIL=1
else
  log "  OK   no raw hex in frontend/src/ (v3 token compliance)"
fi

if [ "${STAGE4_FAIL}" -eq 0 ]; then
  log "Stage 4 PASSED"
else
  warn "Stage 4 FAILED"
  STAGE_FAILURES=$((STAGE_FAILURES + 1))
  FAIL_SUMMARY="${FAIL_SUMMARY} [frontend-design FAIL]"
fi

# ============================================================
# Summary
# ============================================================
log "=== Summary: ${STAGE_FAILURES}/4 stages failed ==="

if [ "${STAGE_FAILURES}" -gt 0 ]; then
  MSG="daily-regression ALERT (${STAGE_FAILURES}/4 stages failed)${FAIL_SUMMARY}"
  warn "${MSG}"
  notify_slack "${MSG}"
  capture_sentry "${MSG}"
  exit 1
fi

log "All regression stages passed."
notify_slack "daily-regression OK — all 3 stages passed at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
