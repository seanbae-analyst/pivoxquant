#!/bin/bash
# Overnight build verification — read-only.
#
# Runs while nobody is watching, so it only *observes*. It does not edit,
# commit, push, or delete: an unattended change nobody reviews is how a
# green morning report ends up describing a repo that no longer works.
# Everything it finds goes in a dated report for the next session to act on.
#
# The same principle applies to the report itself: every check states whether
# it actually ran. A check that could not run says so loudly instead of
# leaving an empty code block that reads like a pass.
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

# launchd hands us a bare PATH with no nvm/homebrew, so `npx` resolved to
# "command not found" and every frontend check silently reported nothing for
# months. Resolve the toolchain explicitly and fail loudly if it is absent.
NODE_BIN=""
for cand in "$HOME"/.nvm/versions/node/*/bin /opt/homebrew/bin /usr/local/bin; do
  if [ -x "$cand/npx" ]; then NODE_BIN="$cand"; fi
done
[ -n "$NODE_BIN" ] && export PATH="$NODE_BIN:$PATH"

# Run one frontend check, reporting its real exit status.
fe_check() {
  local label="$1"; shift
  local log rc
  log=$(mktemp)
  ( cd "$REPO/frontend" && "$@" ) >"$log" 2>&1
  rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "### $label — ✅ exit 0"
  else
    echo "### $label — ❌ exit $rc"
  fi
  echo '```'
  tail -12 "$log"
  echo '```'
  rm -f "$log"
}

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
  if [ -z "$NODE_BIN" ]; then
    echo "- ❌ **node 툴체인 없음 — tsc·vitest·eslint·build 4개 전부 미실행.**"
    echo "  탐색 경로: \`~/.nvm/versions/node/*/bin\`, \`/opt/homebrew/bin\`, \`/usr/local/bin\`."
    echo "  이 상태의 리포트는 프론트엔드에 대해 **아무것도 보증하지 않음**."
  else
    echo "- node: \`$NODE_BIN\` ($("$NODE_BIN/node" --version 2>/dev/null))"
    echo
    fe_check "tsc"    npx tsc --noEmit
    fe_check "vitest" npx vitest run
    fe_check "eslint" npx eslint

    # `next build` stamps the current HEAD sha into frontend/public/sw.js as the
    # PWA CACHE_VERSION. This script promises to leave the tree untouched, so
    # snapshot the file and put it back — otherwise every nightly run silently
    # dirties a tracked file and the morning `git status` lies about what changed.
    SW="$REPO/frontend/public/sw.js"
    SW_SNAP=$(mktemp)
    cp "$SW" "$SW_SNAP" 2>/dev/null
    fe_check "next build" npm run build
    if [ -s "$SW_SNAP" ] && ! cmp -s "$SW_SNAP" "$SW"; then
      cp "$SW_SNAP" "$SW"
      echo "- ℹ️ \`next build\` 가 sw.js CACHE_VERSION 을 갱신했으나 원복함 (읽기 전용 계약)."
    fi
    rm -f "$SW_SNAP"
  fi
  echo

  echo "## 4. 삭제 잔해 — 사라진 모듈을 실제로 import 하는 코드"
  echo
  echo "산문(docstring·주석) 언급은 세지 않는다. 이전 버전은 \`services.artifacts\` 의"
  echo "\`.\` 가 정규식 임의문자라 \`services/artifacts/foo.py\` 라고 적힌 docstring 까지"
  echo "매칭해 잔해 8곳·3곳을 보고했으나 실제 죽은 import 는 0건이었다."
  echo '```'
  for mod in services.artifacts services.broker services.trading routes.artifacts routes.daytrade; do
    esc=${mod//./\\.}
    lines=$(grep -rnE "^[[:space:]]*(from|import)[[:space:]]+${esc}([[:space:].]|$)|import_module\([[:space:]]*[\"']${esc}" \
            --include='*.py' routes/ services/ models/ tests/ app.py 2>/dev/null | grep -v __pycache__)
    hits=$(printf '%s' "$lines" | grep -c . | tr -d ' ')
    printf '%-24s %s곳\n' "$mod" "$hits"
    if [ "$hits" -gt 0 ]; then printf '%s\n' "$lines" | sed 's/^/    /'; fi
  done
  echo '```'
  echo

  echo "## 5. 프론트→백엔드 엔드포인트 계약"
  echo
  echo "tsc·vitest 가 구조적으로 못 잡는 층. 프론트의 \`/api/...\` 는 단순 문자열 상수라"
  echo "백엔드 라우트를 지워도 타입검사는 통과하고 런타임에만 404 가 난다."
  echo '```'
  "$PY" "$REPO/scripts/nightly/check_endpoint_contract.py" 2>&1 | tail -40
  echo '```'
  echo

  echo "## 6. 규모"
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
