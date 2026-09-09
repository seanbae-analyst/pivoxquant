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

# Run a command with a wall-clock cap, portably.
#
# macOS ships no coreutils `timeout`, so this polls instead. Returns the
# command's own exit code, or 124 if the cap was hit — matching `timeout(1)`
# so the caller can tell a hang from a failure.
run_capped() {
  local secs="$1"; shift
  "$@" & local pid=$!
  local waited=0
  while kill -0 "$pid" 2>/dev/null; do
    if [ "$waited" -ge "$secs" ]; then
      kill -TERM "$pid" 2>/dev/null
      sleep 5
      kill -KILL "$pid" 2>/dev/null
      wait "$pid" 2>/dev/null
      return 124
    fi
    sleep 5
    waited=$((waited + 5))
  done
  wait "$pid"
  return $?
}

# Run the backend suite, reporting its REAL exit status.
#
# 2026-09-09: this section was `pytest -q 2>&1 | tail -12`, which throws the
# exit code away — the pipeline reports tail's status, so a red suite printed
# its failures into the report and the report still read as fine. That night
# pytest also sat for 2h02m at ~3% CPU with no cap, so the whole run never
# finished and the report was left truncated mid-fence. Three ways to fail
# open in four words. fe_check already did this correctly; the backend leg
# just never got the same treatment.
#
# The cap is wall-clock rather than pytest-timeout: requirements-dev.txt
# records why that plugin was dropped on 2026-09-01 ("a declared-but-absent
# dependency is worse than none" — passing --timeout without it reads as a
# broken command). A shell-level cap needs no plugin, and it also catches
# hangs pytest-timeout cannot see, such as collection or a stuck fixture
# teardown.
PYTEST_CAP_SECONDS="${PYTEST_CAP_SECONDS:-1800}"

py_check() {
  local log rc
  log=$(mktemp)
  run_capped "$PYTEST_CAP_SECONDS" "$PY" -m pytest -q >"$log" 2>&1
  rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "### pytest — ✅ exit 0"
  elif [ "$rc" -eq 124 ]; then
    echo "### pytest — ❌ **${PYTEST_CAP_SECONDS}초 상한에서 강제 종료 (멈춤)**"
    echo
    echo "정상 완주는 로컬 기준 약 5분 30초다. 상한에 닿았다는 것은 실패가"
    echo "아니라 **정지**이고, 이 리포트는 백엔드에 대해 아무것도 보증하지 않는다."
  else
    echo "### pytest — ❌ exit $rc"
  fi
  echo '```'
  tail -12 "$log"
  echo '```'
  rm -f "$log"
}

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

# Truncation guard.
#
# The report is one `{ ... } > $OUT` block. If anything inside it hangs or is
# killed, the file is left cut off mid-write and nothing says so — on
# 2026-09-09 that produced an 11-line report (the day before: 103 lines, six
# sections) with an unclosed code fence, and it read as a normal green
# morning. A report that stops early must not be indistinguishable from one
# that passed.
#
# So the banner goes in FIRST and is removed LAST. Any exit path that skips
# the removal — hang, kill, power loss — leaves it visible at the top of the
# file, where the reader cannot miss it. The end marker is what authorises
# the removal, so it is the single thing that means "this ran to completion".
INCOMPLETE_BANNER='> 🔴 **미완주 리포트** — 이 배너가 남아 있으면 검증이 도중에 끊긴 것이다. 여기 적힌 어떤 green 도 믿지 마라.'
DONE_MARKER='<!-- verify-build:complete -->'

printf '%s\n\n' "$INCOMPLETE_BANNER" > "$OUT"

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
  py_check
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
  echo "$DONE_MARKER"
} >> "$OUT" 2>&1

# Only a report that reached its own end marker earns the banner's removal.
if grep -qF "$DONE_MARKER" "$OUT"; then
  grep -vF "$INCOMPLETE_BANNER" "$OUT" > "$OUT.tmp" && mv "$OUT.tmp" "$OUT"
  echo "wrote $OUT"
else
  echo "INCOMPLETE: $OUT — 완주 마커 없음, 배너 유지" >&2
  exit 1
fi
