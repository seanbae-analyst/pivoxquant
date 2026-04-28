# PivoxQuant Autopilot State (2026-04-27 자율 운영)

CEO 명령: 운동 갔다 오는 동안 5페이지 v2 구현 + push + PR. 기능 절대 깨지면 안 됨. 정직 보고.

## 진행 상태 (체크박스)

- [x] Stage 1a: P0 cron timezone fix (`vix_spike_monitor` 1줄, app.py:1146)
- [x] Stage 1b: P1 today-hero fallback fix (13 파일 19 라인 `#0A0A0A` → `#050505`)
- [x] Stage 1c: v1 feature inventory (`docs/v1-feature-inventory.md`, 63 페이지 / 107 컴포넌트)
- [x] Stage 2: home-v2 구현 (8 신규 컴포넌트, 17/17 v1 모듈 매핑, 빌드 87/87 성공)
- [x] Stage 3: home-v2 audit (CONDITIONAL PASS, WARN 5건 P2)
- [x] Stage 4: portfolio-v2 구현 (file write 완료, 9 신규 컴포넌트 — Stream idle timeout으로 보고 누락. Stage 5b에서 검증 완료)
- [x] Stage 5: portfolio-v2 audit — CONDITIONAL PASS → Stage 5b에서 FAIL 2건 fix 완료 (PASS)
- [x] Stage 6: risk-v2 구현 (6 신규 컴포넌트 + 5 신규 hook + v1/v2 toggle. tsc 0 errors / eslint 0 errors / 빌드 ✓ both flags)
- [x] Stage 7: risk-v2 audit (CONDITIONAL PASS — WARN 4건 P1-P3, FAIL 0건. 빌드 87/87 양쪽. Stage 8 진행 가능)
- [x] Stage 8: signals-v2 구현 (5 신규 컴포넌트 + useSignals/resolveTickerName/useTickerNameResolver hooks + SignalEntry/SignalsResponse/SignalFilters/SignalLabel types + v1/v2 toggle. tsc 0 errors / eslint 0 errors-warnings / 빌드 ✓ both flags. 종목명 main 패턴: signal-card + top-movers-strip Playfair name + mono ticker dim with resolveName fallback positions→watchlist→ticker. v1 verbatim preserved — diff EXIT 0 vs HEAD signals/page.tsx modulo export rename. endpoints.ts 0 changes.)
- [x] Stage 9: signals-v2 audit (CONDITIONAL PASS — FAIL-1 빌드 차단 reports/_v2/page-v2.tsx 미존재. signals 자체는 PASS. 상세: AUTOPILOT_STATE.md §Stage 9)
- [x] Stage 10: reports-v2 구현 (6 신규 컴포넌트 reports/v2/{reports-hero-v2, latest-artifact-card, artifact-gallery-grid, artifact-kind-card, generate-artifact-cta, year-timeline-block} + 3 신규 hook `useArtifactStats`/`useArtifactArchive`/`generateArtifact` + 2 helper `deriveArtifactStats`/`deriveArchiveMonths` + 4 신규 endpoint stats/byMonth/generate/jobStatus + v1/v2 toggle. tsc 0 errors / eslint 0 errors-warnings / 빌드 ✓ both flags. /reports/preview/* 18 라우트 모두 정적 prerender 보존 (V2 OFF: 18 routes, V2 ON: 18 routes). 종목명 main 패턴: latest-artifact-card mention rows Playfair name + mono ticker dim + KR pct color, gallery-card display name Playfair 22 + mono cadence sub-line, year-timeline month abbrev Playfair 22 + mono year. v1 verbatim preserved — CATALOG 18종 / tier-gating / persona filter / SectionFeedbackBar / PeerBenchmarkBlock / liveByType Map 100% 매핑. endpoints.ts 6줄 추가만, hooks.ts 추가만, types.ts 무변경. 법적 금지어 UI 0건 ("Not investment advice" 디스클레이머는 portfolio-v2/morning-brief/ai 등 6개 파일 동일 표준 패턴).)
- [x] Stage 11: reports-v2 audit (PASS — WARN 2건 P2. 빌드 both flags 18/18 preview routes. Stage 12 진행 가능)
- [x] Stage 12: PWA service worker cache bump (`public/sw.js` CACHE_VERSION sp-v4 → sp-v5. activate handler가 sp-v5 외 모든 캐시 evict. next.config.ts의 `/sw.js` no-cache 헤더로 즉시 갱신. manifest.ts theme #050505 락-인 유지. next-pwa/workbox/serwist 미사용 — 자체 SW만 v5 bump.)
- [x] Stage 13: feature branch + commit + push + PR (branch `home-v2-rebuild-2026-04-27`, commit `63f16ee`, PR #7 → https://github.com/seanbae-analyst/pivoxquant/pull/7. 85 files changed, +22826 / -2902. push 성공. PR 본문에 5페이지 매핑 표 + 검증 결과 + carry-over 명시)
- [x] Stage 14: PushNotification 발송 (데스크톱 알림 — 모바일 push는 Remote Control 비활성으로 미발송)
- [x] **자율 운영 종료** — 모든 14 stage 완료. v1 100% 보존 검증 통과 (P0 RollingWindowWidget gap fix됨). PWA cache bump 완료. PR 머지 검토 사용자에게 위임.
- [x] Stage 15 (post-PR): CI fail 2건 fix
  - Legal Guard FAIL: `risk-board.tsx:396` "RECOMMENDED ACTIONS · NEXT REBAL" → "REBALANCE NOTES · OBSERVED" (사전 위반, commit `d92f2fd6` brought, 우리 PR이 처음 잡음)
  - Backend lint FAIL: ruff 9× F401 unused imports — `ai_service.py` / `app.py` / `services/{alert_service,artifacts/{brag_card,earnings_prebrief,weekly_memo},morning_brief_service}.py`에서 `legal_filter.{safe_scrub,ensure_disclaimer}` import 제거 (사전 dead imports, ruff autofix)
  - 검증: `ruff check ai_service.py app.py services/` → All checks passed
  - 안전성: 함수 정의는 `legal_filter.py`에 보존, 다른 파일들 사용 그대로

## 자동화 메커니즘

매 cron trigger마다 새 Claude session 깨어남:
1. 본 파일 (`AUTOPILOT_STATE.md`) 읽고 첫 unchecked stage 식별
2. 해당 stage 작업 진행 (frontend-dev / audit-code / backend-dev sub-agent 호출)
3. 완료 시 본 파일에 [x] 마크
4. 모든 stage 완료 시 PushNotification + scheduled task delete

## 안전 규칙 (모든 stage 공통)

- 기존 컴포넌트/hook/endpoint **수정 X** (신규 추가만)
- 법적 금지어 0건: BUY/SELL/HOLD/recommend/advice/AI Coach/추천/조언
- 종목명 main 패턴: Playfair name 14-22px + mono ticker 10-11px dim
- 디자인 토큰 v3 락-인만 (Vantablack/Bronze/Bronze-light/Bronze-deep/Ivory)
- DisclaimerBanner footer (layout.tsx 자동, 별도 X)
- main 직접 push X — feature branch + PR
- 정직 보고 — grep/test 결과만 인용

## Reference

- Mockup 5장: `frontend/design-mockups/{home,portfolio,risk,signals,reports}-v2/`
- Inventory: `docs/v1-feature-inventory.md`
- Daily memo 설계: `docs/design/daily-memo-system.md`
- Memory: `~/.claude/projects/-Users-seanbae-Desktop---/memory/MEMORY.md`

## 발견된 사전 위험 (별도 조치 필요)

1. KST 15:00 morning_brief 발사 원인 (작업 범위 밖) — backend-dev 별도 디버깅. `morning_brief_daily` cron timezone은 이미 명시됨, 원인은 `is_main_worker()` guard 또는 misfire_grace_time
2. `signals-card.tsx` ticker primary 노출 (WARN-2) — 백엔드 `/api/signals` 응답에 `name` 필드 없음. 종목명 main 패턴 미충족, 백엔드 schema 확장 필요
3. **[2026-04-27] 통합 보존 audit P0 누락 RollingWindowWidget fix 완료** — `frontend/src/app/(dashboard)/portfolio/_v2/page-v2.tsx` 에 `<RollingWindowWidget paper />` Block 5 추가 (v1 line 310/357 패턴 보존). import 라인 39, JSX 라인 319.
4. **[2026-04-27] P1 RISK_CORRELATION 보존 fix 완료** — 신규 `frontend/src/components/risk/v2/correlation-heatmap.tsx` (236줄, 옵션 A) + `useRiskCorrelation` hook 추가 (`lib/hooks.ts:650`). v1 N×N heatmap + diverging gradient(Bronze pos / muted-rose neg) 그대로 v2 톤(Vantablack + Bronze hover outline)으로 포팅. risk-v2 page.tsx Block 2/3 사이에 마운트.
5. **[2026-04-27] P1 portfolio-v2 에러 핸들링 강화 fix 완료** — `_v2/page-v2.tsx` 에 v1 패턴 이식: `posErr` / `sumErr` toast.error (sonner), `hasLoadError` 배너 + Refresh 버튼, `showSkeleton` 1.2s 보호. `usePortfolioPositions` / `usePortfolioSummary` 의 `error` 필드 활용. 변경 X (additive only).
6. **[2026-04-27] P1 portfolio-v2 Hero KPI deck 추가 fix 완료** — `portfolio-hero-v2.tsx` 에 4개 신규 props (`todayPnl` / `todayPnlPct` / `unrealized` / `realizedYtd`) + 3-col KPI deck sub-component (`HeroKpi`) + `fmtMoneySigned` helper. v1 4-stat 표기 패턴(positive/negative 토큰 컬러 페어링) 보존. page-v2.tsx에서 sumData/derived 값 전달.

### 검증 (2026-04-27)
- `npx tsc --noEmit`: 0 errors
- `npx eslint src/app/(dashboard)/portfolio/_v2 src/app/(dashboard)/risk/_v2 src/components/risk/v2 src/components/portfolio/v2 src/lib/hooks.ts`: 0 errors
- `npm run build` (default V1): ✓ Compiled successfully
- `NEXT_PUBLIC_PORTFOLIO_V2=true NEXT_PUBLIC_RISK_V2=true npm run build`: ✓ Compiled successfully in 21.1s
- 금지어 grep (BUY/SELL/HOLD/recommend/advice/추천/조언): UI 문자열 0건. "not advice" 면책 문구 5건은 legal 의무 문구로 정상.
- `grep -n RollingWindowWidget portfolio/_v2/page-v2.tsx`: line 39 import + line 319 JSX
- `grep -rn RISK_CORRELATION risk/v2/ risk/_v2/ hooks.ts`: 8 hits (component + page comment + hook + endpoint export)
- Hero KPI props grep: 4개 신규 props 정확히 추가 (line 39/41/43/45 props, line 117-120 destructure, line 209-256 render)

## Stage 5 audit 결과 (portfolio-v2) — 2026-04-27

### FAIL (2건 — 수정 필요)
- FAIL-1 [P0 빌드]: `_v2/page-v2.tsx` 미존재. portfolio page.tsx는 v2 toggle 미구현 — 현재 v1 full code 직접 노출. SPEC §11 + MIGRATION.md §5 toggle pattern 미적용. build 통과는 되지만 v2 기능 진입점 없음.
- FAIL-2 [ESLint 1 error]: `sector-donut-block.tsx:92` — `let cumulative` reassigned after render (react-hooks/immutability). fix: wrap segments computation in `useMemo`.

### WARN (4건 — P1/P2)
- WARN-1: `hooks.ts` 수정됨 — import 1줄 확장 + Risk v2 hooks 371줄 추가. Portfolio 안전 규칙("수정 X") 경계 위반. Risk-v2 hooks 추가는 additive-only이고 기존 함수 무변경이지만 SPEC 위반임. 다음 risk-v2 audit에서 재검증 필요.
- WARN-2: `trade-modal-v2.tsx` comment line에 "action: buy|sell" 백엔드 payload 문서화 (line 15). 실제 토스트/UI에는 노출 안 되지만 주석에 buy/sell 잔존.
- WARN-3: `positions-table-v2.tsx` styled-jsx `<style jsx>` 사용. next.config.ts에 styledJsx 설정 없으나, node_modules에 styled-jsx 설치됨 + 기존 home-v2에서도 동일 패턴 사용. 빌드 영향 없음.
- WARN-4: `_v2/` directory 존재하지만 비어있음 (page-v2.tsx 없음). MIGRATION.md는 `page.tsx`를 server component toggle로 쓰는 패턴 요구.

### 통과 항목 (증거)
- 9 컴포넌트 파일 존재 확인: `ls` 결과 9개 출력
- `_v1/page-v1.tsx` 존재: 확인 (portfolio v1 fallback)
- `lib/hooks.ts` 기존 함수 무변경: `git diff` — removed 1줄(import 확장), 신규 함수만 추가
- `lib/endpoints.ts` 0 변경: `git diff` 출력 없음
- 기존 v1 컴포넌트 (ledger-book-paper, sector-paper, activity-paper, add-position-modal, trade-modal) 수정 0: git diff 출력 없음
- 법적 금지어 0건: BUY/SELL/HOLD/recommend/advice/추천/조언 — v2 파일에서 미노출 (comment 내 문서화만 있음, UI 문자열 아님)
- Action vocabulary: Add/Trim/Close/Save observation 확인. "Buy"/"Sell" 버튼 라벨 0건
- TypeScript errors (portfolio v2): 0건 (tsc --noEmit 출력에 portfolio v2 경로 없음)
- raw hex 0건: 모든 hex는 `var(--pq-..., #fallback)` 형태 — 새 color 도입 없음
- console.log 0건
- useFocusTrap 존재: `ls lib/` 확인
- PORTFOLIO_POSITIONS POST endpoint 정합: backend line 694 `/positions POST` 확인
- 종목명 main 패턴: positions-table-v2:429-450 (Playfair 18px + mono 10.5px), watchlist-mini:128-150, recent-transactions-block:164-185 확인

### 다음 sub-agent 지시사항
1. [FAIL-1] `frontend/src/app/(dashboard)/portfolio/page.tsx`를 MIGRATION.md §5 toggle 패턴으로 교체. 현재 v1 full code → 서버 컴포넌트로 변환, `NEXT_PUBLIC_PORTFOLIO_V2=true`이면 `_v2/page-v2.tsx` 렌더. v1 code는 `_v1/page-v1.tsx`에 이미 존재.
2. [FAIL-1 cont] `frontend/src/app/(dashboard)/portfolio/_v2/page-v2.tsx` 신규 생성 — SPEC 4-block 구조: PortfolioHeroV2 + EquityCurveBlock + PositionsTableV2 + 3-col grid (SectorDonutBlock/WatchlistMini/RecentTransactionsBlock) + AddPositionModalV2 + TradeModalV2.
3. [FAIL-2] `sector-donut-block.tsx:88-94` — `let cumulative` + `segments` 연산을 `useMemo(()=>{ let c=0; return sectors.map(...); }, [sectors])` 로 감싸기. ESLint react-hooks/immutability 해결.
