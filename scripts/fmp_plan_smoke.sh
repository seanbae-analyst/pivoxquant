#!/usr/bin/env bash
# fmp_plan_smoke.sh — probe every FMP /stable endpoint PivoxQuant depends on
# against a given API key, so you can see exactly what a plan (esp. the FREE
# tier) actually serves BEFORE switching keys in prod.
#
# Usage:
#   FMP_TEST_KEY=<key> bash scripts/fmp_plan_smoke.sh   # test a specific key (e.g. a new free key)
#   bash scripts/fmp_plan_smoke.sh                       # fall back to FMP_API_KEY in .env
#
# Verdict column:
#   OK         200 + JSON array with data  → endpoint usable on this plan
#   RESTRICTED 402 "Restricted Endpoint"   → plan-gated, NOT available
#   EMPTY/404  empty array or 404          → no data (wrong path, deprecated, or gated)
#   ERR        other (429 limit reached, 5xx, network)
#
# Endpoint list is the live dependency set; regenerate with:
#   grep -rhoE '_fmp_get\("(/[^"]+)"' services/ routes/ | sort -u
set -u

K="${FMP_TEST_KEY:-}"
if [ -z "$K" ] && [ -f .env ]; then
  K=$(grep -E '^FMP_API_KEY=' .env | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
fi
[ -z "$K" ] && { echo "No key. Set FMP_TEST_KEY=<key> or FMP_API_KEY in .env"; exit 1; }

B="https://financialmodelingprep.com/stable"
D=$(date +%F)
FROM=$(date -v-35d +%F 2>/dev/null || date -d '35 days ago' +%F)
TO=$(date -v+30d +%F 2>/dev/null || date -d '30 days' +%F)
YDAY=$(date -v-1d +%F 2>/dev/null || date -d 'yesterday' +%F)

EPS=(
  "quote?symbol=AAPL"
  "profile?symbol=AAPL"
  "search-symbol?query=AAPL"
  "historical-price-eod/full?symbol=AAPL&from=$FROM&to=$D"
  "dividends?symbol=AAPL"
  "income-statement?symbol=AAPL&limit=1"
  "income-statement-growth?symbol=AAPL&limit=1"
  "balance-sheet-statement?symbol=AAPL&limit=1"
  "key-metrics-ttm?symbol=AAPL"
  "ratios-ttm?symbol=AAPL"
  "earnings-calendar?from=$D&to=$TO&symbol=AAPL"
  "news/general-latest?page=0&limit=3"        # was news/general (404) — renamed 2026-06-06
  "news/stock?symbol=AAPL&limit=3"
  "insider-trading/search?symbol=AAPL&limit=3" # was insider-trading (404) — renamed 2026-06-06
  "sector-performance-snapshot?date=$YDAY"
  # ── Known plan-gated / removed (code gates these OFF; expect RESTRICTED/404) ──
  # earning-call-transcript: 402 RESTRICTED on Starter $29 (needs higher tier) →
  #   _FMP_TRANSCRIPT_AVAILABLE gate in services/ai/models.py.
  # symbol-positions-summary: 402 RESTRICTED (was institutional-holder, removed) →
  #   get_institutional_ownership degrades to available:False (canslim proxy).
  # historical/short-interest: 404 — FMP removed it from stable entirely →
  #   _FMP_SHORT_INTEREST_AVAILABLE gate in services/data/fmp.py.
  "earning-call-transcript?symbol=AAPL&limit=1"
  "institutional-ownership/symbol-positions-summary?symbol=AAPL"
  "historical/short-interest?symbol=AAPL"
)

printf "%-32s %-5s %-11s %s\n" "ENDPOINT" "HTTP" "VERDICT" "BODY"
printf '%.0s-' {1..96}; echo
ok=0; bad=0
for ep in "${EPS[@]}"; do
  name="${ep%%\?*}"
  code=$(curl -s -m 25 -w "%{http_code}" -o /tmp/_fmpb "$B/$ep&apikey=$K")
  body=$(head -c 80 /tmp/_fmpb | tr '\n' ' ' | tr -d '\r')
  case "$code" in
    200)
      if echo "$body" | grep -qE '\[\s*\]'; then verdict="EMPTY/404"; bad=$((bad+1));
      else verdict="OK"; ok=$((ok+1)); fi ;;
    402) verdict="RESTRICTED"; bad=$((bad+1)) ;;
    404) verdict="EMPTY/404"; bad=$((bad+1)) ;;
    *)   verdict="ERR";        bad=$((bad+1)) ;;
  esac
  printf "%-32s %-5s %-11s %s\n" "$name" "$code" "$verdict" "$body"
done
printf '%.0s-' {1..96}; echo
echo "OK=$ok  unusable=$bad  (of ${#EPS[@]})"
