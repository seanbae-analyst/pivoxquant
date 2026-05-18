#!/usr/bin/env bash
# PivoxQuant — Local psql client setup (Wave G BLOCKED 해소)
# 2026-05-19 v45.2
#
# 목적: CEO 가 prod Railway PostgreSQL 에 직접 query 할 수 있도록 psql CLI 설치.
# 비용: 0원 (Homebrew + postgresql@16 무료).
# 안전: 설치만 수행 — DB 접속 정보는 별도 (railway run psql 또는 DATABASE_URL).

set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────
# §1. 사전 확인 — psql 이미 있으면 즉시 종료
# ──────────────────────────────────────────────────────────────────────────
echo "=== §1. psql 사전 확인 ==="
if command -v psql >/dev/null 2>&1; then
  echo "✅ psql 이미 설치됨: $(psql --version)"
  echo "   PATH 상 위치: $(command -v psql)"
  exit 0
fi
echo "ℹ️  psql 미설치 — 설치 진행."

# ──────────────────────────────────────────────────────────────────────────
# §2. Homebrew 확인
# ──────────────────────────────────────────────────────────────────────────
echo ""
echo "=== §2. Homebrew 확인 ==="
if ! command -v brew >/dev/null 2>&1; then
  echo "❌ Homebrew 미설치."
  echo "   1. https://brew.sh 에서 설치 명령 복사"
  echo "   2. terminal 에 붙여넣기 후 본 script 재실행"
  exit 1
fi
echo "✅ Homebrew: $(brew --version | head -1)"

# ──────────────────────────────────────────────────────────────────────────
# §3. postgresql@16 설치 (client only — server 는 Railway 사용)
# ──────────────────────────────────────────────────────────────────────────
echo ""
echo "=== §3. postgresql@16 설치 ==="
if brew list postgresql@16 >/dev/null 2>&1; then
  echo "ℹ️  postgresql@16 이미 brew 에 등록됨 — skip install."
else
  brew install postgresql@16
fi

# ──────────────────────────────────────────────────────────────────────────
# §4. PATH 추가 (~/.zshrc) — keg-only formula 라 명시 export 필요
# ──────────────────────────────────────────────────────────────────────────
echo ""
echo "=== §4. PATH 추가 (~/.zshrc) ==="
PG_BIN="$(brew --prefix)/opt/postgresql@16/bin"
EXPORT_LINE="export PATH=\"${PG_BIN}:\$PATH\""

if [ -f "$HOME/.zshrc" ] && grep -Fq "postgresql@16/bin" "$HOME/.zshrc"; then
  echo "ℹ️  ~/.zshrc 에 이미 postgresql@16 PATH 등록됨 — skip."
else
  echo "" >> "$HOME/.zshrc"
  echo "# Added by PivoxQuant setup_dev_psql.sh (2026-05-19)" >> "$HOME/.zshrc"
  echo "$EXPORT_LINE" >> "$HOME/.zshrc"
  echo "✅ ~/.zshrc 갱신 완료."
  echo "   적용: 새 terminal 열거나  source ~/.zshrc"
fi

# ──────────────────────────────────────────────────────────────────────────
# §5. 검증 — 절대 경로로 psql --version
# ──────────────────────────────────────────────────────────────────────────
echo ""
echo "=== §5. psql 검증 ==="
if [ -x "$PG_BIN/psql" ]; then
  "$PG_BIN/psql" --version
  echo "✅ psql 사용 가능."
else
  echo "❌ $PG_BIN/psql 실행 파일 없음. brew install 결과 확인 필요."
  exit 1
fi

# ──────────────────────────────────────────────────────────────────────────
# §6. Railway CLI 안내 (옵션) — DB 연결 검증 가이드만 출력
# ──────────────────────────────────────────────────────────────────────────
echo ""
echo "=== §6. Railway CLI (옵션) ==="
if command -v railway >/dev/null 2>&1; then
  echo "✅ railway CLI: $(railway --version)"
  echo ""
  echo "   Railway prod DB 연결 테스트 (CEO 수동 실행 권고):"
  echo "     cd /Users/seanbae/Desktop/취준/pivoxquant"
  echo "     railway link        # 프로젝트 선택"
  echo "     railway run psql -c 'SELECT version();'"
else
  echo "⚠️  railway CLI 미설치."
  echo "   설치: brew install railway  (또는  npm i -g @railway/cli)"
  echo "   문서: https://docs.railway.app/develop/cli"
fi

echo ""
echo "=== 완료 ==="
echo "다음 step: 새 terminal 또는  source ~/.zshrc  → psql --version 확인"
