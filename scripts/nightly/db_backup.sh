#!/usr/bin/env bash
# db_backup.sh — Railway PostgreSQL nightly dump → gzip → GPG → local rotation
#
# Schedule: CC scheduled-task cron "0 3 * * *" (KST 03:00)
# Storage : ~/pivoxquant-backups/ (local, 7-day rotation)
# Restore :
#   gpg --decrypt ~/pivoxquant-backups/dump-YYYY-MM-DD.sql.gz.gpg | gunzip | psql $TARGET_DATABASE_URL
#
# Required env vars:
#   DATABASE_URL      — Railway PostgreSQL connection string
#   GPG_PASSPHRASE    — Symmetric GPG passphrase (store in 1Password)
#
# Optional:
#   BACKUP_DIR        — Override local backup dir (default: ~/pivoxquant-backups)
#   SLACK_WEBHOOK_URL — Slack alert on failure/success
#   RETAIN_DAYS       — Days to keep (default: 7)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_PREFIX="[db_backup $(date -u '+%Y-%m-%dT%H:%M:%SZ')]"

log()  { echo "${LOG_PREFIX} $*"; }
warn() { echo "${LOG_PREFIX} WARN: $*" >&2; }
fail() { echo "${LOG_PREFIX} ERROR: $*" >&2; notify_slack "FAIL" "$*"; exit 1; }

notify_slack() {
  local status="$1"
  local msg="$2"
  if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
    curl -fsS -X POST "${SLACK_WEBHOOK_URL}" \
      -H "Content-Type: application/json" \
      -d "{\"text\":\"db-backup ${status}: ${msg}\"}" >/dev/null 2>&1 || true
  fi
}

# --- guard: required env vars ---
if [ -z "${DATABASE_URL:-}" ]; then
  warn "DATABASE_URL not set — skipping backup (graceful skip)"
  notify_slack "SKIP" "DATABASE_URL not configured"
  exit 0
fi

if [ -z "${GPG_PASSPHRASE:-}" ]; then
  warn "GPG_PASSPHRASE not set — skipping backup (graceful skip)"
  notify_slack "SKIP" "GPG_PASSPHRASE not configured"
  exit 0
fi

# --- config ---
BACKUP_DIR="${BACKUP_DIR:-${HOME}/pivoxquant-backups}"
RETAIN_DAYS="${RETAIN_DAYS:-7}"
DATE_STAMP="$(date -u '+%Y-%m-%d')"
DUMP_FILE="${BACKUP_DIR}/dump-${DATE_STAMP}.sql.gz.gpg"
TEMP_GZ="/tmp/pivoxquant-dump-${DATE_STAMP}-$$.sql.gz"

mkdir -p "${BACKUP_DIR}"
log "Backup dir: ${BACKUP_DIR}"
log "Target file: ${DUMP_FILE}"

# --- check pg_dump available ---
if ! command -v pg_dump >/dev/null 2>&1; then
  fail "pg_dump not found. Install postgresql-client: brew install postgresql"
fi

# --- skip if today's dump already exists (idempotent) ---
if [ -f "${DUMP_FILE}" ]; then
  log "Dump for ${DATE_STAMP} already exists — idempotent skip"
  exit 0
fi

# --- run pg_dump → gzip ---
log "Running pg_dump..."
if ! pg_dump "${DATABASE_URL}" | gzip -9 > "${TEMP_GZ}"; then
  rm -f "${TEMP_GZ}"
  fail "pg_dump failed for date ${DATE_STAMP}"
fi
TEMP_SIZE=$(du -sh "${TEMP_GZ}" | cut -f1)
log "Dump completed: ${TEMP_SIZE} (compressed)"

# --- GPG encrypt ---
log "Encrypting with GPG..."
if ! echo "${GPG_PASSPHRASE}" | gpg --batch --yes --passphrase-fd 0 \
  --symmetric --cipher-algo AES256 \
  --output "${DUMP_FILE}" "${TEMP_GZ}"; then
  rm -f "${TEMP_GZ}" "${DUMP_FILE}"
  fail "GPG encryption failed"
fi
rm -f "${TEMP_GZ}"
FINAL_SIZE=$(du -sh "${DUMP_FILE}" | cut -f1)
log "Encrypted dump saved: ${DUMP_FILE} (${FINAL_SIZE})"

# --- rotate old backups ---
log "Rotating backups older than ${RETAIN_DAYS} days..."
DELETED=0
while IFS= read -r old_file; do
  log "  Deleting: ${old_file}"
  rm -f "${old_file}"
  DELETED=$((DELETED + 1))
done < <(find "${BACKUP_DIR}" -name "dump-*.sql.gz.gpg" -mtime "+${RETAIN_DAYS}" 2>/dev/null)
log "Rotation: deleted ${DELETED} old backup(s)"

# --- count remaining ---
REMAINING=$(find "${BACKUP_DIR}" -name "dump-*.sql.gz.gpg" | wc -l | tr -d ' ')
log "Backup complete. ${REMAINING} dump(s) in ${BACKUP_DIR}"
notify_slack "OK" "dump-${DATE_STAMP} saved (${FINAL_SIZE}), ${REMAINING} total on disk"
