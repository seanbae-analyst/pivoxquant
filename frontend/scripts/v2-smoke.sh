#!/usr/bin/env bash
# v2-smoke.sh — capture V1 vs V2 screenshots for the 9 NEXT_PUBLIC_*_V2 surfaces.
#
# CEO decision 2026-05-19 (memory: session_2026-05-19): V2 production ON track,
# smoke capture first. This script orchestrates two playwright runs (v1, v2)
# by swapping .env.local flags between runs, then leaves both screenshot sets
# under ../qa/v2-smoke/<YYYY-MM-DD>/.
#
# Run from the frontend/ directory:
#   bash scripts/v2-smoke.sh
#
# Rules followed:
#   - feedback_no_extra_cost: only uses already-installed Playwright. No paid
#     services. No network calls outside localhost.
#   - feedback_no_false_reports: writes a manifest of captured files. The
#     manifest is the only "completion proof" — the consumer (CEO / audit
#     agent) verifies by ls-ing the dir.
#   - .env.local is backed up before mutation and restored on exit (trap).

set -euo pipefail

FRONTEND_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$FRONTEND_DIR/.." && pwd)"
DATE="$(date +%Y-%m-%d)"
OUT_DIR="$REPO_ROOT/qa/v2-smoke/$DATE"
ENV_FILE="$FRONTEND_DIR/.env.local"
ENV_BACKUP="$FRONTEND_DIR/.env.local.bak.v2-smoke"

mkdir -p "$OUT_DIR/v1" "$OUT_DIR/v2"

# Restore the original .env.local even on failure so the dev environment is
# never left in a half-toggled state.
restore_env() {
  if [[ -f "$ENV_BACKUP" ]]; then
    mv "$ENV_BACKUP" "$ENV_FILE"
    echo "[v2-smoke] restored .env.local from backup"
  fi
}
trap restore_env EXIT

# Snapshot the live .env.local — the CEO's working file may have additional
# secrets we must not lose (e.g. VERCEL_OIDC_TOKEN).
cp "$ENV_FILE" "$ENV_BACKUP"

# All 9 V2 flags. Kept in one place so adding a 10th surface only touches the
# spec file + this list.
FLAGS=(
  NEXT_PUBLIC_LOGIN_V2
  NEXT_PUBLIC_SIGNUP_V2
  NEXT_PUBLIC_HOME_V2
  NEXT_PUBLIC_PORTFOLIO_V2
  NEXT_PUBLIC_RISK_V2
  NEXT_PUBLIC_SIGNALS_V2
  NEXT_PUBLIC_REPORTS_V2
  NEXT_PUBLIC_PROFILE_V2
  NEXT_PUBLIC_SETTINGS_V2
)

set_flags() {
  local value="$1"
  local tmp
  tmp="$(mktemp)"
  # Strip any existing NEXT_PUBLIC_*_V2 lines, then re-append at the desired value.
  grep -v -E '^NEXT_PUBLIC_(LOGIN|SIGNUP|HOME|PORTFOLIO|RISK|SIGNALS|REPORTS|PROFILE|SETTINGS)_V2=' \
    "$ENV_BACKUP" > "$tmp" || true
  for flag in "${FLAGS[@]}"; do
    echo "${flag}=\"${value}\"" >> "$tmp"
  done
  mv "$tmp" "$ENV_FILE"
}

run_mode() {
  local mode="$1"          # v1 | v2
  local value="$2"         # true | false
  echo "[v2-smoke] === ${mode} run (flags=${value}) ==="
  set_flags "$value"
  # Kill any straggling next dev so the new env is actually picked up.
  # Playwright's webServer.reuseExistingServer=true would otherwise glue
  # us to a stale process that already inlined the previous flag values.
  pkill -f "next dev" 2>/dev/null || true
  sleep 1
  V2_MODE="$mode" npx playwright test e2e/v2-smoke.spec.ts --reporter=list || {
    echo "[v2-smoke] playwright failed for mode=$mode — continuing to next mode"
  }
}

run_mode v1 false
run_mode v2 true

# Manifest — single line per captured PNG with size + sha256, so the audit
# step can verify nothing is empty / truncated.
{
  echo "# v2-smoke manifest — $DATE"
  echo "# columns: bytes  sha256  path"
  find "$OUT_DIR" -name "*.png" -print0 | while IFS= read -r -d '' f; do
    bytes=$(wc -c < "$f" | tr -d ' ')
    sha=$(shasum -a 256 "$f" | awk '{print $1}')
    rel="${f#$REPO_ROOT/}"
    echo "$bytes  $sha  $rel"
  done
} > "$OUT_DIR/MANIFEST.txt"

echo "[v2-smoke] done → $OUT_DIR"
echo "[v2-smoke] manifest → $OUT_DIR/MANIFEST.txt"
