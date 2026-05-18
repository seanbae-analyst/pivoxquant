#!/usr/bin/env bash
# CAUS 오늘 sweep 결과 즉시 확인 (CEO 출근 직후 또는 cron 06:00 KST)
# 2026-05-19 v45.2 — CAUS Phase 4 첫 강화 catch 모니터링
#
# 사용:
#   bash scripts/check_caus_today.sh
#
# 출력:
#   - 오늘 sweep report 존재 여부 + 상위 30줄
#   - P0 finding 목록
#   - auto-fix log 존재 여부 (P0 발견 시)
#   - auto-created PR 안내
#   - 오늘 day rotation index + scenario 요약

set -e

cd "$(dirname "$0")/.."

TODAY=$(date +%Y-%m-%d)
REPORT_FILE="docs/qa/auto-sim-reports/${TODAY}.md"
FIX_LOG="docs/qa/auto-fix-log/${TODAY}.md"

echo "=== CAUS ${TODAY} sweep 결과 ==="
echo ""

if [ -f "$REPORT_FILE" ]; then
  echo "OK: Report 존재: $REPORT_FILE"
  echo ""
  echo "--- 첫 30줄 ---"
  head -30 "$REPORT_FILE"
  echo ""
  echo "--- P0 findings ---"
  if grep -E "P0|critical|SHIP-BLOCKER" "$REPORT_FILE" | head -10; then
    :
  else
    echo "(none — 오늘 P0 finding 없음)"
  fi
else
  echo "MISS: Report 미존재: $REPORT_FILE"
  echo "→ cron 실행 안 됐거나 scheduled-task 비활성 가능성"
  echo "→ 확인:"
  echo "    - GitHub Actions tab '.github/workflows/caus-*.yml'"
  echo "    - launchd: launchctl list | grep caus"
  echo "    - scheduled-tasks list (claude code Max plan)"
fi

echo ""

if [ -f "$FIX_LOG" ]; then
  echo "ALERT: Auto-fix loop 활성: $FIX_LOG"
  head -20 "$FIX_LOG"
  echo ""
  echo "→ auto-created PR 검토:"
  echo "   gh pr list --label caus-auto-fix"
else
  echo "OK: Auto-fix log 미존재 → P0 발견 없음 (expected on green day)"
fi

echo ""
echo "=== Day rotation 위치 ==="
DAY_OF_YEAR=$(date +%j)
# strip leading zeros so arithmetic eval does not treat as octal
DAY_OF_YEAR=$((10#$DAY_OF_YEAR))
DAY_INDEX=$(( (DAY_OF_YEAR - 1) % 10 ))
echo "오늘 = day${DAY_INDEX} scenario (10-day rotation)"

SCENARIO_FILE=$(ls scripts/caus_scenarios/day${DAY_INDEX}_*.py 2>/dev/null | head -1)
if [ -n "$SCENARIO_FILE" ]; then
  echo "파일: $SCENARIO_FILE"
  echo "요약:"
  head -5 "$SCENARIO_FILE" | sed 's/^/  /'
else
  echo "WARN: day${DAY_INDEX} scenario 파일 없음"
fi

echo ""
echo "=== 첫 강화 catch 일정 ==="
echo "  2026-05-19 (오늘) → day3 portfolio_risk 강화 첫 tick"
echo "  2026-05-20 (내일) → day4 alert_simulation 강화 첫 tick"
