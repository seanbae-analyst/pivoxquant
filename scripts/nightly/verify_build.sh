#!/bin/bash
# Overnight build verification — read-only.
#
# Runs while nobody is watching, so it only *observes*. It does not edit,
# commit, push, or delete: an unattended change nobody reviews is how a
# green morning report ends up describing a repo that no longer works.
# Everything it finds goes in a dated report for the next session to act on.
#
# Scheduled by com.pivoxquant.nightly.verify.plist. Requires the Mac to stay
# awake — `caffeinate -dimsu` or `sudo pmset -c sleep 0`.

set -uo pipefail

REPO="/Users/seanbae/Desktop/취준/pivoxquant"
cd "$REPO" || exit 1

STAMP=$(date '+%Y-%m-%d')
OUT="$REPO/docs/qa/nightly-verify-$STAMP.md"
mkdir -p "$(dirname "$OUT")"

PY="$REPO/venv/bin/python"

{
  echo "# 야간 빌드 검증 — $(date '+%Y-%m-%d %H:%M %Z')"
  echo
  echo "브랜치: \`$(git branch --show-current)\`"
  echo "HEAD: \`$(git log -1 --format='%h %s' | cut -c1-90)\`"
  echo "미커밋: $(git status --porcelain | grep -vc '^??')개 · untracked: $(git status --porcelain | grep -c '^??')개"
  echo

  echo "## 1. 앱 부팅"
  if BOOT=$("$PY" -c "
from app import create_app
a = create_app()
print(f'OK routes={len(list(a.url_map.iter_rules()))}')
" 2>&1 | grep -E '^OK'); then
    echo "- ✅ $BOOT"
  else
    echo "- ❌ 부팅 실패"
    echo '```'
    "$PY" -c "from app import create_app; create_app()" 2>&1 | tail -20
    echo '```'
  fi
  echo

  echo "## 2. 백엔드 테스트"
  echo '```'
  "$PY" -m pytest -q 2>&1 | tail -12
  echo '```'
  echo

  echo "## 3. 프론트엔드"
  cd "$REPO/frontend" || exit 1
  echo "### tsc"
  echo '```'
  npx tsc --noEmit 2>&1 | tail -8 || true
  echo '```'
  echo "### vitest"
  echo '```'
  npx vitest run --reporter=dot 2>&1 | tail -8 || true
  echo '```'
  echo "### eslint"
  echo '```'
  npx eslint 2>&1 | tail -8 || true
  echo '```'
  echo "### next build"
  echo '```'
  npm run build 2>&1 | tail -15 || true
  echo '```'
  cd "$REPO" || exit 1
  echo

  echo "## 4. 삭제 잔해 — 사라진 모듈을 가리키는 코드"
  echo '```'
  for mod in services.artifacts services.broker services.trading routes.artifacts routes.daytrade; do
    hits=$(grep -rn "$mod" --include='*.py' routes/ services/ models/ tests/ app.py 2>/dev/null \
           | grep -v __pycache__ | grep -vE ':[0-9]+:\s*#' | wc -l | tr -d ' ')
    printf '%-24s %s곳\n' "$mod" "$hits"
  done
  echo '```'
  echo

  echo "## 5. 규모"
  echo '```'
  printf 'routes 파일    %s\n' "$(ls routes/*.py | wc -l | tr -d ' ')"
  printf 'endpoints      %s\n' "$(grep -rhoE '@[a-z_]+\.route\(' routes/*.py | wc -l | tr -d ' ')"
  printf 'services 파일  %s\n' "$(find services -name '*.py' -not -path '*__pycache__*' | wc -l | tr -d ' ')"
  printf 'Python 줄      %s\n' "$(find routes services models -name '*.py' -not -path '*__pycache__*' | xargs wc -l | tail -1 | awk '{print $1}')"
  printf 'tests 파일     %s\n' "$(ls tests/*.py | wc -l | tr -d ' ')"
  echo '```'
  echo

  echo "---"
  echo "읽기 전용 실행. 수정·커밋·푸시 없음."
} > "$OUT" 2>&1

echo "wrote $OUT"
