#!/bin/bash
# H6: SessionStart — LIVE 프로젝트 상태 주입
#
# 2026-08-30 재작성. 이전 버전은 HANDOVER.md 상단 200줄(≈27KB / 8,000토큰)을
# 통째로 주입했다. 문제 두 가지:
#   1) 비용 — 주석엔 "≈3,000토큰"이라 적혀 있었으나 한글이라 실측 2.7배 초과.
#   2) 정확도 — 주입 내용이 마지막 세션 시점에 고정돼, 공백이 길어지면
#      stale 서사가 매 세션 사실처럼 주입된다. CLAUDE.md 중요원칙 §1
#      ("동적수치는 SessionStart hook LIVE 값") 과 정면으로 어긋난다.
#
# 새 방식: 매번 실측되는 값(git/prod)만 짧게 + HANDOVER 는 최신 헤더만 포인터로.
# 목표 예산: ≈2KB / 600토큰 (이전 대비 93% 절감).

set -uo pipefail
REPO="/Users/seanbae/Desktop/취준/pivoxquant"
HANDOVER="$REPO/HANDOVER.md"
cd "$REPO" 2>/dev/null || exit 0

echo "=== [H6] PivoxQuant LIVE 상태 — $(date '+%Y-%m-%d %H:%M %Z') ==="

# --- git 실측 ---
BRANCH=$(git branch --show-current 2>/dev/null)
HEAD_LINE=$(git log -1 --format='%h %s' 2>/dev/null | cut -c1-90)
HEAD_DATE=$(git log -1 --format='%cs' 2>/dev/null)
DIRTY=$(git status --porcelain 2>/dev/null | grep -vc '^??')
UNTRACKED=$(git status --porcelain 2>/dev/null | grep -c '^??')
AB=$(git rev-list --left-right --count origin/main...HEAD 2>/dev/null | awk '{print $2" ahead / "$1" behind"}')

echo "branch : $BRANCH  ($AB origin/main)"
echo "HEAD   : $HEAD_LINE  [$HEAD_DATE]"
echo "작업중 : 미커밋 ${DIRTY} · untracked ${UNTRACKED}"

# --- prod 실측 (짧은 타임아웃, 실패해도 세션 시작 막지 않음) ---
BE=$(curl -s -o /dev/null -m 4 -w '%{http_code}' https://web-production-7b484b.up.railway.app/api/health 2>/dev/null || echo "타임아웃")
FE=$(curl -s -o /dev/null -m 4 -w '%{http_code}' -L https://www.pivoxquant.com 2>/dev/null || echo "타임아웃")
echo "prod   : backend=$BE  frontend=$FE   (backend 200 아니면 로그인 이후 기능 전부 죽음)"

# --- HANDOVER 는 포인터만 ---
if [ -f "$HANDOVER" ]; then
  # 버전 태그 + 날짜만 뽑는다 (한글 제목은 절단 시 깨지므로 제외 — staleness 판단엔 불필요)
  LATEST=$(grep -m1 '^## v[0-9]' "$HANDOVER" | sed -E 's/^## (v[0-9]+ [0-9~\-]*).*/\1/')
  echo "handover: ${LATEST:-(섹션 없음)}"
  echo "          전문 $(wc -l < "$HANDOVER" | tr -d ' ')줄 → 필요 시 $HANDOVER 를 직접 읽을 것"
fi
echo "=== [H6] end ==="
exit 0
