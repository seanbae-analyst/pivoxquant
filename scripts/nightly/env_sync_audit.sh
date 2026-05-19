#!/usr/bin/env bash
# env_sync_audit.sh — Vercel/Railway env drift detector (D5).
#
# 목적
# ----
# Vercel 와 Railway 양쪽 env 의 key 누락/불일치를 감지하여 silent fail (예: FMP_API_KEY
# 한쪽만 등록) 을 미연에 방지한다.
#
# 스케줄
# ------
# crontab `0 11 * * 1` (KST 월요일 11:00 weekly).
#
# 작동 원리
# --------
# 1. `vercel env ls` (Vercel CLI, 무료) + `railway variables` (Railway CLI, 무료) 호출.
# 2. PIVOX_EXPECTED_ENV 변수(또는 .env.example 의 미주석 key set)를 기준으로 누락 key 산출.
# 3. 누락이 있으면 Slack alert + exit 1. 없으면 exit 0.
#
# graceful skip
# -------------
# - vercel CLI / railway CLI 미설치 → 경고만 출력 + exit 0 (개발 머신 미준비 상태)
# - 인증되지 않음 → 경고 + exit 0 (운영자 직접 `vercel login` / `railway login` 필요)
# - SLACK_WEBHOOK_URL 미설정 → stdout fallback
#
# 비용
# ----
# Vercel CLI / Railway CLI 무료. Slack webhook 무료. 0원.
set -uo pipefail

LOG_PREFIX="[env_sync_audit $(date -u '+%Y-%m-%dT%H:%M:%SZ')]"
log()  { echo "${LOG_PREFIX} $*"; }
warn() { echo "${LOG_PREFIX} WARN: $*" >&2; }

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
EXPECTED_FILE="${ROOT_DIR}/scripts/cron/expected_env_keys.txt"
STATE_DIR="${ROOT_DIR}/state"
mkdir -p "${STATE_DIR}"

# ── helpers ──────────────────────────────────────────────────────────────────
notify_slack() {
  local msg="$1"
  if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
    curl -fsS -X POST "${SLACK_WEBHOOK_URL}" \
      -H "Content-Type: application/json" \
      -d "$(printf '{"text":"%s"}' "${msg}")" >/dev/null 2>&1 || true
  else
    warn "SLACK_WEBHOOK_URL 미설정 — stdout fallback"
    echo "[SLACK-FALLBACK] ${msg}"
  fi
}

build_expected_keys() {
  # Prefer explicit allowlist; else derive from .env.example.
  if [ -f "${EXPECTED_FILE}" ]; then
    grep -v '^[[:space:]]*#' "${EXPECTED_FILE}" | awk 'NF' | sort -u
    return
  fi
  if [ -f "${ROOT_DIR}/.env.example" ]; then
    grep -E '^[A-Z][A-Z0-9_]+=' "${ROOT_DIR}/.env.example" \
      | sed -E 's/=.*$//' \
      | sort -u
    return
  fi
  echo ""
}

# Returns 0 if a CLI is present + authenticated, 1 otherwise. Stdout = key list.
fetch_vercel_keys() {
  if ! command -v vercel >/dev/null 2>&1; then
    warn "vercel CLI 미설치 — skip"
    return 1
  fi
  # vercel env ls outputs a table; the 1st column is key. Auth errors go to stderr.
  local out
  if ! out=$(vercel env ls production 2>&1); then
    warn "vercel env ls failed: ${out}"
    return 1
  fi
  echo "${out}" \
    | awk 'NR>1 && /^[A-Z][A-Z0-9_]+/ {print $1}' \
    | sort -u
  return 0
}

fetch_railway_keys() {
  if ! command -v railway >/dev/null 2>&1; then
    warn "railway CLI 미설치 — skip"
    return 1
  fi
  local out
  if ! out=$(railway variables 2>&1); then
    warn "railway variables failed: ${out}"
    return 1
  fi
  # railway prints "KEY=value" lines, sometimes "║ KEY │ value ║" depending on version.
  echo "${out}" \
    | grep -oE '^[A-Z][A-Z0-9_]+(=|[[:space:]]*│)' \
    | sed -E 's/[=│[:space:]]+$//' \
    | sort -u
  return 0
}

diff_missing() {
  # $1 = expected, $2 = actual. Output keys missing from actual.
  comm -23 <(echo "$1") <(echo "$2")
}

# ── main ─────────────────────────────────────────────────────────────────────
log "starting env sync audit"

EXPECTED="$(build_expected_keys)"
if [ -z "${EXPECTED}" ]; then
  warn "expected key set 비어있음 — .env.example 또는 expected_env_keys.txt 필요"
  exit 0
fi

EXPECTED_COUNT=$(echo "${EXPECTED}" | wc -l | tr -d ' ')
log "expected keys: ${EXPECTED_COUNT}"

# Vercel
VERCEL_OK=0
VERCEL_KEYS=""
if VERCEL_KEYS=$(fetch_vercel_keys); then
  VERCEL_OK=1
  log "vercel keys fetched: $(echo "${VERCEL_KEYS}" | wc -l | tr -d ' ')"
fi

# Railway
RAILWAY_OK=0
RAILWAY_KEYS=""
if RAILWAY_KEYS=$(fetch_railway_keys); then
  RAILWAY_OK=1
  log "railway keys fetched: $(echo "${RAILWAY_KEYS}" | wc -l | tr -d ' ')"
fi

if [ "${VERCEL_OK}" -eq 0 ] && [ "${RAILWAY_OK}" -eq 0 ]; then
  warn "CLI 양쪽 모두 사용 불가 — audit skip"
  exit 0
fi

DRIFT_REPORT=""
DRIFT_COUNT=0

if [ "${VERCEL_OK}" -eq 1 ]; then
  MISSING=$(diff_missing "${EXPECTED}" "${VERCEL_KEYS}")
  if [ -n "${MISSING}" ]; then
    COUNT=$(echo "${MISSING}" | wc -l | tr -d ' ')
    DRIFT_COUNT=$((DRIFT_COUNT + COUNT))
    DRIFT_REPORT="${DRIFT_REPORT}\nVercel missing (${COUNT}): $(echo "${MISSING}" | tr '\n' ' ')"
  fi
fi

if [ "${RAILWAY_OK}" -eq 1 ]; then
  MISSING=$(diff_missing "${EXPECTED}" "${RAILWAY_KEYS}")
  if [ -n "${MISSING}" ]; then
    COUNT=$(echo "${MISSING}" | wc -l | tr -d ' ')
    DRIFT_COUNT=$((DRIFT_COUNT + COUNT))
    DRIFT_REPORT="${DRIFT_REPORT}\nRailway missing (${COUNT}): $(echo "${MISSING}" | tr '\n' ' ')"
  fi
fi

# Persist last audit snapshot for diff-over-time.
{
  echo "audited_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "expected_count=${EXPECTED_COUNT}"
  echo "drift_count=${DRIFT_COUNT}"
  [ "${VERCEL_OK}" -eq 1 ] && echo "vercel_keys=$(echo "${VERCEL_KEYS}" | tr '\n' ',')"
  [ "${RAILWAY_OK}" -eq 1 ] && echo "railway_keys=$(echo "${RAILWAY_KEYS}" | tr '\n' ',')"
} > "${STATE_DIR}/env_sync_last.txt"

if [ "${DRIFT_COUNT}" -gt 0 ]; then
  MSG="[WARN] PivoxQuant env drift detected (${DRIFT_COUNT} keys)${DRIFT_REPORT}"
  warn "${MSG}"
  notify_slack "${MSG}"
  exit 1
fi

log "env sync OK — no drift"
exit 0
