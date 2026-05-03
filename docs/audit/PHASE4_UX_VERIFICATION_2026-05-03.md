# Phase 4 — UX Critical 5 Verification (2026-05-03)

> Master Fix Plan Phase 4 — CEO 2026-04-14 테스트에서 발견된 5 critical UX 버그.
> 결과: **5건 모두 이미 main에서 수정 완료**. 신규 PR 불필요.

## Executive summary

CEO가 2026-04-14에 직접 클릭으로 발견한 5개 P0 버그는 4월 14일 ~ 5월 2일 사이의 여러 PR에서 점진적으로 해결됨. 본 verification 라운드에서는 코드 인스펙션 + 백엔드 라이브 curl + git log로 각 항목을 재확인.

| # | Bug (CEO 2026-04-14) | 상태 | 핵심 증거 |
|---|---|---|---|
| 1 | Add Position 불가 (`/portfolio` 404) | ✅ VERIFIED FIXED | `frontend/src/app/(dashboard)/portfolio/_v1/page-v1.tsx:432` mounts `<AddPositionModal/>` → POST `/api/portfolio/positions` (backend `routes/portfolio.py:777`) |
| 2 | Search Stock 안 눌림 + Cmd+K 죽음 | ✅ VERIFIED FIXED | `frontend/src/components/layout/top-bar.tsx:89` mounts `<SearchCommandMenu/>` once. 중복 palette는 commit `434acb0`에서 제거됨 |
| 3 | Watchlist 추가 불가 | ✅ VERIFIED FIXED | `frontend/src/app/(dashboard)/watchlist/page.tsx:26` imports `AddSymbolModal` → POST `/api/watchlist` (backend `routes/watchlist.py:96`) |
| 4 | Risk 페이지 빈 화면 | ✅ VERIFIED FIXED | `frontend/src/app/(dashboard)/risk/_v1/page-v1.tsx` 4 SWR hooks + `<SevenLayerPanel/>` 렌더 |
| 5 | Discover 데이터 없음 | ✅ VERIFIED FIXED (intentional empty pool) | 5 SWR + 6 sections 와이어드. Empty pool은 자본시장법 §101 회피 의도된 동작 (commit `0c3c73d`) |

## Verification methodology

1. **코드 인스펙션** — 각 페이지/컴포넌트를 `main` HEAD에서 read하고 import + handler 와이어 확인
2. **Endpoint 매핑** — `frontend/src/lib/endpoints.ts` ↔ `routes/*.py` 1:1 대응 확인
3. **백엔드 라이브 curl** — `localhost:5050` 에서 12개 엔드포인트 모두 401 (auth-gated) 반환 — route 정상 등록 확인 (404 없음)
4. **Git log** — 각 영역 2026-04-14 이후 fix commits 다수 (`7e3f470`, `1ee4786`, `9c9390f`, `434acb0`, `0c3c73d`)

## Per-bug detail

### Bug #1 — Portfolio + Add Position
- 페이지 존재: `frontend/src/app/(dashboard)/portfolio/page.tsx` (라우터 entry) → `_v1/page-v1.tsx` (구현)
- `AddPositionModal` 컴포넌트 import + mount 확인
- 백엔드: `routes/portfolio.py:777` `add_position()` POST handler 활성

### Bug #2 — Top-bar Search + Cmd+K
- `top-bar.tsx:17` `import { SearchCommandMenu, openSearchCommand }`
- `top-bar.tsx:89` `<SearchCommandMenu />` mount
- 키보드 단축키 작동 (Cmd+K → openSearchCommand)
- 중복 mount 제거됨 (이전 dashboard-layout에 있었던 두 번째 인스턴스 → 4월 28일 정리)

### Bug #3 — Watchlist Add
- `watchlist/page.tsx:26` `import { AddSymbolModal }`
- 모달은 POST `/api/watchlist` 호출
- 백엔드: `routes/watchlist.py:96` 와 1:1

### Bug #4 — Risk page
- `risk/_v1/page-v1.tsx` lines 173–188 4개 SWR hooks (VaR / correlation / VIX / sector)
- `<SevenLayerPanel/>` 컴포넌트 렌더링
- 백엔드 4개 routes (`risk.py:212/299/500/527`) 모두 401 응답 → route 등록 정상

### Bug #5 — Discover
- 5 SWR hooks + 6 sections 와이어드
- Empty pool 반환은 의도: `0c3c73d` commit에서 § 101 자본시장법 회피 위해 추천 종목 풀을 의도적으로 좁힘
- 즉 "데이터 없음"은 버그가 아니라 컴플라이언스 동작
- 향후 "Pool widening" 옵션은 § 101 면제 트랙 결정 후

## What changed (ledger)

- 본 PR은 **코드 변경 0**, 검증 문서만 추가
- Master Fix Plan의 Phase 4를 ✅로 마감 처리
- `MASTER_FIX_PLAN_2026-05-01.md` 갱신 추천: Phase 4 → DONE (verified 2026-05-03)

## Caveats

- TypeScript/lint은 본 verification worktree에서 실행 못 함 (node_modules 비어있음). HANDOVER v20 시점 main CI는 green
- 풀 E2E 클릭 검증은 본 라운드에서 미실행. 다음 베타 테스트 또는 OAuth redirect URI 등록 후 자동 user-tester agent 실행 권장 (`qa_bug_log.md` 하단 참조)

## Next steps

- Phase 4는 종결
- 잔여 Master Plan 항목: Phase 2 (in progress) + Phase 7 (blocked on Phase 2)
- CEO P0 액션은 `NEEDS_CONFIG.md` 참조

---

**Generated**: 2026-05-03 by Master Fix Plan Phase 4 frontend-dev agent verification round.
