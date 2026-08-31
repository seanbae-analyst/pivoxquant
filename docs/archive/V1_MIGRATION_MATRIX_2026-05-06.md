# _v1 디렉토리 마이그 매핑 매트릭스 — 2026-05-06

> 목적: feedback_feature_preservation 룰에 따라 _v1 dirs 9개 삭제 전 v2 매핑 검증.
> 빠진 기능 0건 verified 후만 삭제 PR 가능.
>
> 조사 방법: 각 _v1/page-v1.tsx 직접 읽기 + 활성 page.tsx feature-flag 로직 확인 + .env.local V2 flags 확인.
> 조사일: 2026-05-06
> 조사자: investigator agent (grep/Read 기반, 추측 없음)

---

## 공통 패턴 (9개 전체)

모든 9개 _v1 디렉토리는 동일한 구조를 따름:

| 항목 | 내용 |
|------|------|
| 파일 구성 | 각 `_v1/` 안에 `page-v1.tsx` 1개만 존재 (총 9파일) |
| 연동 방식 | 상위 `page.tsx`가 `dynamic()` lazy-import + env flag로 v1/v2 전환 |
| _v2 존재 여부 | 9개 전부 `_v2/page-v2.tsx` 존재 확인됨 |
| feature flag 구조 | `NEXT_PUBLIC_{PAGE}_V2=true` → v2 활성, unset/false → v1 활성 |

---

## 1. signup/_v1

- **활성 v2**: `frontend/src/app/(auth)/signup/page.tsx` — 존재 확인
- **feature flag**: `NEXT_PUBLIC_SIGNUP_V2` — `.env.local`에 미설정 (v1이 현재 활성 기본값)
- **_v1 파일**: `_v1/page-v1.tsx` (405줄)
- **_v1 주요 기능**:
  - `GoogleIcon`, `KakaoIcon` SVG 컴포넌트 (인라인)
  - `Consents` 인터페이스: `terms / non_advisory / age / cross_border / marketing` (5개 체크박스)
  - `Checkbox` 커스텀 컴포넌트 (pulse 애니메이션 포함)
  - `CONSENT_STORAGE_KEY = "pivox_signup_consents"` — localStorage 동의 스냅샷 저장
  - `allRequired` state: 4개 필수 항목 전부 체크 시에만 OAuth 버튼 활성화
  - `pulseUnchecked` — 미체크 항목 ring pulse 하이라이트 (900ms 자동 해제)
  - `handleOAuthClick` — OAuth 전 localStorage 동의 기록 후 리다이렉트
  - 법적 동의 항목 5개: [필수] 이용약관+개인정보, [필수] 투자자문업 아님, [필수] 만 14세, [필수] PIPA §28-8 국외 이전, [선택] 마케팅
  - `API.auth.google` / `API.auth.kakao` — 두 OAuth 버튼
  - 로그인 링크, 베타 뱃지
- **v2와의 차이**:
  - 매핑: `page.tsx`가 v1을 import (`SignupPageV1 from "./_v1/page-v1"`)하고 v2는 dynamic lazy
  - v1은 현재 활성 기본값 (flag 미설정 = v1 렌더)
  - v2 (`_v2/page-v2.tsx`)는 Vantablack editorial split layout — 동일 기능(동의 게이팅, OAuth flow, localStorage 스냅샷)을 다른 시각 레이어로 구현한다는 코드 주석 확인
  - ✅ 동일 (v2에 보존): OAuth flow, consent gating, localStorage persistence
  - 미확인: v2 파일 내 checkbox pulse 애니메이션, 5개 consent 항목 텍스트 완전 일치 여부 (v2 파일 미열람 — 이 매트릭스는 v1 인벤토리가 목적)
- **결정**: **SAFE_DELETE** (조건부 — v2 파일에서 5개 consent 항목 + pulse UX 동일성 CEO 확인 후)

---

## 2. login/_v1

- **활성 v2**: `frontend/src/app/(auth)/login/page.tsx` — 존재 확인
- **feature flag**: `NEXT_PUBLIC_LOGIN_V2` — `.env.local`에 미설정 (v1이 현재 활성 기본값)
- **_v1 파일**: `_v1/page-v1.tsx` (145줄)
- **_v1 주요 기능**:
  - `GoogleIcon`, `KakaoIcon` SVG 컴포넌트 (인라인)
  - `useAuth` + `useRouter` — 로그인 상태면 `/home` 리다이렉트
  - `loading` 스피너
  - `API.auth.google` / `API.auth.kakao` — 두 OAuth 버튼 (직접 href, 동의 게이팅 없음)
  - 이용약관/개인정보처리방침 링크 포함 legal footer
  - 회원가입 링크
- **v2와의 차이**:
  - 코드 주석: "OAuth flow + useAuth + redirect to /home are identical across both — only the visual layer differs"
  - ✅ 동일 (v2에 보존): OAuth flow, useAuth redirect, legal footer
- **결정**: **SAFE_DELETE** (조건부 — v2 legal footer 동일성 확인 후)

---

## 3. settings/_v1

- **활성 v2**: `frontend/src/app/(dashboard)/settings/page.tsx` — 존재 확인
- **feature flag**: `NEXT_PUBLIC_SETTINGS_V2=true` — `.env.local`에 **true 설정됨** (v2가 현재 활성)
- **_v1 파일**: `_v1/page-v1.tsx` (872줄)
- **_v1 주요 기능**:
  - `AccountSection` — user name/email/oauth_provider (read-only) + /profile 링크
  - `SeedCapitalSection` — USD/KRW seed capital 입력 + `API.profile.capital` POST + `fmtUsd`/`fmtKrw`
  - `SubscriptionSection` — `API.billing.subscription` SWR + tier badge + Upgrade/Manage billing 버튼 + `API.billing.portal` POST
  - `BrokersSection` — `useBrokerConnections()` + `KisCard` + `AlpacaCard` (ALPACA_ENABLED env) + `KisConnectModal` + `AlpacaConnectModal` + Sync/Disconnect handlers
  - `PreferencesSection` — Push 토글 (`subscribeToPush`/`unsubscribeFromPush`/`getPushSubscription`) + Email 토글 (localStorage `sp_mb_email`) + 마케팅 이메일 opt-out (`API.profile.emailPreferences` PATCH) + 실적발표 opt-out + 언어 선택 (ko/en) + `useLocale`
  - `Toggle` 커스텀 컴포넌트
  - `DeleteAccountModal` — mailto 링크
  - `handleSignOut` — `logout()` + `/` 리다이렉트
  - `ErrorBoundary` 래핑
  - Import: `sonner toast`, `KisCard`, `KisConnectModal`, `AlpacaCard`, `AlpacaConnectModal`, `isPushSupported`, `subscribeToPush`, `unsubscribeFromPush`, `getPushSubscription`, `useLocale`, `fmtUsd`, `fmtKrw`
- **v2와의 차이**:
  - 코드 주석: "v2 = editorial CFO room dials — 5 sections (A Identity · B Brokers · C Notifications · D Subscription · E Privacy) with sticky anchor rail"
  - v2가 현재 프로덕션 활성 (NEXT_PUBLIC_SETTINGS_V2=true)
  - v1은 현재 fallback (v2=false일 때만 렌더)
  - 확인 필요: v2에서 `SeedCapitalSection`, `BrokersSection`, `PreferencesSection` (push/email/opt-out/locale) 전부 포함 여부
- **결정**: **NEEDS_PORT 검토** — v2 파일 내 위 5개 기능 섹션 포함 여부 별도 확인 필요 (본 매트릭스 범위 외 — v2 파일 미열람)

---

## 4. home/_v1

- **활성 v2**: `frontend/src/app/(dashboard)/home/page.tsx` — 존재 확인
- **feature flag**: `NEXT_PUBLIC_HOME_V2=true` — `.env.local`에 **true 설정됨** (v2가 현재 활성)
- **_v1 파일**: `_v1/page-v1.tsx` (1117줄)
- **_v1 주요 기능**:
  - `TopTicker` (full-bleed 실시간 ticker strip)
  - `LivingCFOStatusBar` (sticky, top:56 모바일 수정 포함)
  - `TodayMemoHero` (briefText + loading prop)
  - Portfolio Snapshot: `KpiCard` × 3 (Total NAV, Today P/L, Positions)
  - Risk Gauges: `KpiCard` × 4 (VaR 95, Sharpe, Max DD, VIX) — `riskSummary` SWR
  - Positions 테이블: `DataTable<PosRow>` 6 columns — name/shares/avgCost/current/pnlPct/marketValue
  - Watchlist 테이블: `DataTable<WatchRow>` 4 columns — name/last/Δ%/market
  - `EquityCurveChart` (3mo, `bookCurrency`)
  - `SectorAllocationDonut` (positions 기반)
  - CandlestickChart: top holding 1D + MA20/MA50 + volume — `topHolding` 계산 로직
  - Signals Stream 테이블: `DataTable<SignalRow>` — `API.signals.all` SWR (30s refresh)
  - Pulse Activity 테이블: posRows 상위 5 |pnlPct| 정렬
  - Companion 링크 카드 (`/companion`)
  - `ArtifactQueue`
  - `UpsellPlus`
  - `FootSignature`
  - `WeeklyPulseCard`
  - SWR 옵션: briefOpts(600s refresh), signalsOpts(30s refresh) + dedupingInterval 3계층
  - `bookCurrency` 자동 감지 (KRW only vs mixed)
  - `topHolding` 계산: positions를 marketValue 내림차순 정렬 → 1위 반환
  - 코드 주석: "Morning Brief deprecated 2026-04-29"
- **v2와의 차이**:
  - v2는 gallery 레이아웃 (코드 주석: "gallery shell per home-v2 SPEC.md")
  - v2가 현재 활성 (NEXT_PUBLIC_HOME_V2=true)
  - v1은 fallback
- **결정**: **NEEDS_PORT 검토** — v2가 위 컴포넌트 전부 포함하는지 확인 필요

---

## 5. signals/_v1

- **활성 v2**: `frontend/src/app/(dashboard)/signals/page.tsx` — 존재 확인
- **feature flag**: `NEXT_PUBLIC_SIGNALS_V2=true` — `.env.local`에 **true 설정됨** (v2가 현재 활성)
- **_v1 파일**: `_v1/page-v1.tsx` (452줄)
- **_v1 주요 기능**:
  - `API.signals.all` SWR — `liveRefresh(10_000, 60_000)` 시장시간 연동 refresh
  - `API.signals.refresh` POST — 수동 Refresh 버튼
  - `DossierDesk` + `PaperDocument` 3D 클립보드 스택 UI
  - `ClipboardPaper` 컴포넌트 (kicker/title/tone/items props)
  - `SignalMemoStrip` 4-pillar 확장 패널 (`expandedId` 상태)
  - Filter pills: All / POSITIVE / NEUTRAL / NEGATIVE
  - Tally strip: Positive/Neutral/Negative 각 count
  - 점수 임계값 범례: Positive ≥65, Neutral 35-65, Negative <35
  - 3D desktop 적층 (z-index 전환, active paper 포그라운드)
  - 모바일 vertical flat stack fallback
  - `weekTag()` 헬퍼
  - `PRICE_COLOR_HEX` 한국 관례 컬러 (up=red, down=blue)
  - `FootSignature`
  - Import: `DossierDesk`, `PaperDocument`, `ClipboardPaper`, `MemoSignalItem` type
- **v2와의 차이**:
  - 코드 주석: "v2 = editorial signals stream — hero + filter bar + top movers + timeline"
  - v2가 현재 활성 (NEXT_PUBLIC_SIGNALS_V2=true)
  - v1은 fallback
  - v1 고유: DossierDesk 3D 클립보드 스택 시각 UX, `ClipboardPaper`, 4-pillar expansion strip
- **결정**: **NEEDS_PORT 검토** — v2에서 4-pillar expansion, Refresh 버튼, score threshold legend 제공 여부 확인 필요

---

## 6. profile/_v1

- **활성 v2**: `frontend/src/app/(dashboard)/profile/page.tsx` — 존재 확인
- **feature flag**: `NEXT_PUBLIC_PROFILE_V2=true` — `.env.local`에 **true 설정됨** (v2가 현재 활성)
- **_v1 파일**: `_v1/page-v1.tsx` (857줄)
- **_v1 주요 기능**:
  - `AccountSection` (identity card — initials avatar, name/email, tier badge, oauth_provider)
  - Display name 수정 form (`API.profile.update` PATCH)
  - Investor assessment section — `useInvestmentProfile()` + `/onboarding` 링크
  - `PersonaV2Card` — 9-dim observed persona
  - `LivingCFOControls` — declared persona 표시, drift alerts 토글 (localStorage `pq_cfo_drift_alerts_enabled`), pulse cadence 선택 (weekly/biweekly/monthly), feedback count, `WeeklyPulseCard inline`
  - `PersonaEvolution` bare
  - `JournalCompanionSubsection` — `hasCompanionEntitlement()`, waitlist form (`/api/agent/waitlist` POST), Closed Beta 처리
  - `AgentDataSubsection` — export (`/api/agent/export` → JSON blob download), delete (`/api/agent/delete` DELETE + localStorage wipe 7개 키)
  - `DeleteAccountModal` — PIPA 30일 삭제 고지 포함
  - `personaIsMock` 배너 — sample data 경고
  - Hooks: `usePersona`, `usePulse`, `useCompanionStatus`, `useInvestmentProfile`
  - Import: `PersonaEvolution`, `PersonaV2Card`, `WeeklyPulseCard`, `hasCompanionEntitlement`, `useCompanionStatus`, `PERSONA_LABELS`, `usePersona`, `usePulse`
- **v2와의 차이**:
  - 코드 주석: "v2 = editorial 8-block layout"
  - v2가 현재 활성 (NEXT_PUBLIC_PROFILE_V2=true)
  - v1은 fallback
- **결정**: **NEEDS_PORT 검토** — v2에서 `AgentDataSubsection` (export/delete PIPA), `JournalCompanionSubsection`, drift alerts, pulse cadence 전부 포함 여부 확인 필요

---

## 7. portfolio/_v1

- **활성 v2**: `frontend/src/app/(dashboard)/portfolio/page.tsx` — 존재 확인
- **feature flag**: `NEXT_PUBLIC_PORTFOLIO_V2=true` — `.env.local`에 **true 설정됨** (v2가 현재 활성)
- **_v1 파일**: `_v1/page-v1.tsx` (448줄)
- **_v1 주요 기능**:
  - `PORTFOLIO_POSITIONS` / `PORTFOLIO_SUMMARY` / `PORTFOLIO_TRADES` SWR — `liveRefresh(5_000, 60_000)`
  - `LedgerBookPaper` — 4-stat + 전체 positions 테이블 (onAction/onDelete prop)
  - `SectorPaper` — sectorAlloc 가중치 바
  - `ActivityPaper` — trades 최근 N개 연대기
  - `AddPositionModal` — 포지션 추가
  - `TradeModal` — Buy More / Sell / Edit (action: `TradeAction`)
  - `DossierDesk` + `PaperDocument` — 3D 바인더 UI (desktop spread + mobile flat)
  - `RollingWindowWidget paper`
  - `handleDelete` — `PORTFOLIO_POSITIONS/{id}` DELETE + confirm
  - `totals` 계산 — sumData fallback + liveFx 우선순위 (hardcoded literal 제거)
  - `sectorAlloc` — KRW→USD 변환 (liveFx 없으면 KRW 슬롯 skip)
  - `bookCurrency` 자동 감지
  - 1s tick clock — "Live · Xs ago" 배너
  - Load error 배너 (no fake fallback 정책)
  - `relativeTime` 헬퍼
  - `FootSignature`
  - Import: `liveRefresh`, `isMarketOpen`, `relativeTime`, `useFxRate`, `ApiError`
- **v2와의 차이**:
  - 코드 주석: "v2 = gallery shell per portfolio-v2 SPEC.md"
  - v2가 현재 활성 (NEXT_PUBLIC_PORTFOLIO_V2=true)
  - v1은 fallback
  - v1 고유 UI: DossierDesk 3D 바인더, LedgerBookPaper/SectorPaper/ActivityPaper
- **결정**: **NEEDS_PORT 검토** — v2에서 AddPositionModal/TradeModal/handleDelete/RollingWindowWidget 포함 여부 확인 필요

---

## 8. risk/_v1

- **활성 v2**: `frontend/src/app/(dashboard)/risk/page.tsx` — 존재 확인
- **feature flag**: `NEXT_PUBLIC_RISK_V2=true` — `.env.local`에 **true 설정됨** (v2가 현재 활성)
- **_v1 파일**: `_v1/page-v1.tsx` (619줄)
- **_v1 주요 기능**:
  - `RISK_SUMMARY` / `RISK_LAYERS` / `RISK_CORRELATION` / `RISK_ROLLING_VAR` — 4개 SWR 동시 페치
  - `anyLoading` guard — 초기 로딩 중 Sample 배너 억제
  - `isEmptyPortfolio` / `isAuthError` 감지 — demo fallback 전환
  - `DEMO_SUMMARY`, `DEMO_LAYERS`, `DEMO_TICKERS`, `DEMO_CORR_MATRIX`, `buildDemoVarPoints()` — 미인증/빈포트폴리오 일러스트레이티브 데이터
  - 4개 KPI stat (`KpiStat`) — VaR/ES/Max DD/Corr Index
  - Seven-Layer Risk Defense 테이블 (7행 inline)
  - Correlation heatmap 테이블 — hover tooltip, diverging gradient (Bronze/muted-rose)
  - `RollingVarInk` — `InteractiveLineChart` 기반 rolling VaR 30일 (interactive hover)
  - Methodology Notes (5개 항목)
  - Sample-preview 배너 — auth/empty 두 가지 CTA 분기
  - 부호 정규화: `var_pct` 양수→음수 강제 (`-Math.abs(p.var_pct)`)
  - `shouldRetryOnError: false` (401 비재시도)
  - `mapStatus()` — GREEN/YELLOW/RED → green/yellow/red
  - `is401()` 헬퍼
  - Import: `ApiError`, `InteractiveLineChart`, `RISK_SUMMARY`, `RISK_LAYERS`, `RISK_CORRELATION`, `RISK_ROLLING_VAR`
- **v2와의 차이**:
  - 코드 주석: "v2 = editorial Risk Board — hero + 4 big gauges + 7-layer breakdown + concentration + sector + 30-day timeline"
  - v2가 현재 활성 (NEXT_PUBLIC_RISK_V2=true)
  - v1은 fallback
  - v1 고유: `InteractiveLineChart` 기반 hover 가능 VaR 차트, correlation heatmap 테이블, Methodology Notes 섹션
- **결정**: **NEEDS_PORT 검토** — v2에서 correlation heatmap, methodology notes, interactive VaR hover chart 포함 여부 확인 필요

---

## 9. reports/_v1

- **활성 v2**: `frontend/src/app/(dashboard)/reports/page.tsx` — 존재 확인
- **feature flag**: `NEXT_PUBLIC_REPORTS_V2=true` — `.env.local`에 **true 설정됨** (v2가 현재 활성)
- **_v1 파일**: `_v1/page-v1.tsx` (359줄)
- **_v1 주요 기능**:
  - `CATALOG` — 18개 artifact 타입 목록 (slug/type/title/cadence/minTier/personas)
  - `hasAccess()` — tier 게이팅 (free/pro/premium rank 비교)
  - `ArtifactCard` — live artifact 있으면 sent_at + view/download, 없으면 sample PDF fallback
  - `getArtifactViewerUrl()` — type-aware 뷰어 라우팅 (PDF inline vs in-app preview)
  - `liveByType` Map — artifact type별 최신 아티팩트 인덱싱
  - `useArtifacts({ type: "all", since: "all" })` SWR
  - `SectionFeedbackBar` — artifact/section별 Useful/Meh/Skip 반응 수집
  - `PeerBenchmarkBlock` — declaredPersona 있을 때 90일 peer 중앙값 컨텍스트
  - Tier filter: all / free / pro / premium
  - Persona filter: all / growth / value / balanced / income / quant / beginner
  - `previewRoute` — `/reports/preview/{slug}` (kebab-cased)
  - `samplePdf` — `/samples/{slug}.pdf`
  - `footerNote` — artifact count + tier 표시
  - `usePersona()`, `PERSONA_LABELS`
  - Import: `useArtifacts`, `getArtifactViewerUrl`, `SectionFeedbackBar`, `PeerBenchmarkBlock`
- **v2와의 차이**:
  - 코드 주석: "v2 = CFO Archive — hero + latest artifact + 6-card gallery + request box + year timeline. The 18 /reports/preview/* sub-routes remain mounted in both."
  - v2가 현재 활성 (NEXT_PUBLIC_REPORTS_V2=true)
  - v1은 fallback
  - v1 고유: 18개 전체 CATALOG 표시, Tier/Persona 이중 필터, `SectionFeedbackBar`, `PeerBenchmarkBlock`
- **결정**: **NEEDS_PORT 검토** — v2에서 CATALOG 18개 전부, tier filter, persona filter, SectionFeedbackBar, PeerBenchmarkBlock 포함 여부 확인 필요

---

## 종합

### 활성 기본값 현황 (`.env.local` 기준)

| 페이지 | 현재 활성 | 비고 |
|--------|-----------|------|
| signup | **v1** (flag 미설정) | v1이 production 기본값 |
| login | **v1** (flag 미설정) | v1이 production 기본값 |
| home | v2 (flag=true) | v1은 fallback |
| settings | v2 (flag=true) | v1은 fallback |
| signals | v2 (flag=true) | v1은 fallback |
| profile | v2 (flag=true) | v1은 fallback |
| portfolio | v2 (flag=true) | v1은 fallback |
| risk | v2 (flag=true) | v1은 fallback |
| reports | v2 (flag=true) | v1은 fallback |

### SAFE_DELETE (즉시 삭제 가능 — 조건 충족 후)

아래 2개는 v2 코드 주석에서 "OAuth flow / consent gating / localStorage 동일, 시각 레이어만 다름"이 명시됨.
단, v2 파일의 5개 consent 항목 텍스트 + pulse UX 동일성은 본 매트릭스에서 v2 파일을 열지 않았으므로 미검증.

- `(auth)/signup/_v1` — signup/_v2 코드 주석 검증 후 SAFE
- `(auth)/login/_v1` — login/_v2 코드 주석 검증 후 SAFE

### NEEDS_PORT 검토 (v2 파일 열어 기능 확인 후 결정)

| _v1 | 확인 필요 항목 |
|-----|---------------|
| `settings/_v1` | SeedCapitalSection, BrokersSection, PreferencesSection(push/email opt-out/locale) v2 포함 여부 |
| `home/_v1` | TopTicker, LivingCFOStatusBar, EquityCurveChart, SectorAllocationDonut, CandlestickChart, ArtifactQueue, WeeklyPulseCard v2 포함 여부 |
| `signals/_v1` | 4-pillar expansion strip, score threshold legend, Refresh 버튼, DossierDesk 3D UI v2 포함 여부 |
| `profile/_v1` | AgentDataSubsection(export/delete PIPA), JournalCompanionSubsection, drift alerts, pulse cadence v2 포함 여부 |
| `portfolio/_v1` | AddPositionModal, TradeModal, handleDelete, RollingWindowWidget, DossierDesk 3D UI v2 포함 여부 |
| `risk/_v1` | correlation heatmap (interactive), InteractiveLineChart VaR hover, Methodology Notes v2 포함 여부 |
| `reports/_v1` | CATALOG 18개, tier filter, persona filter, SectionFeedbackBar, PeerBenchmarkBlock v2 포함 여부 |

### KEEP (현재 유지)

없음 — 모든 _v1 디렉토리는 삭제 대상. 단, 위 NEEDS_PORT 검토 완료 전까지는 삭제 불가.

---

## 삭제 절차 (CEO ACK 후)

1. **NEEDS_PORT 검토 선행**: 각 `_v2/page-v2.tsx` 파일을 열어 v1 기능 항목이 100% 포함되는지 확인 (investigator 추가 조사 또는 engineering 검토)
2. **signup/_v1 / login/_v1**: v2 파일 consent UX 동일성 확인 후 PR #1 (2개 파일, <30 files)
3. **나머지 7개**: NEEDS_PORT 검토 완료 후, 빠진 기능 0건 확인된 것만 PR #2 묶음
4. **PR 분할 기준**: feedback_pr_workflow 룰 — 30개 이상이면 분할 (본 케이스는 최대 9파일, 단일 PR 가능)
5. **각 PR 본문에 인용**: 이 매트릭스 경로 + "기능 빠짐 0건 verified" 문구 필수
6. **머지 후 1주 모니터링**: regression 발견 시 즉시 revert
7. **NEEDS_PORT 항목에서 빠진 기능 발견 시**: 별도 engineering task로 v2 이식 후 후속 PR

---

## 참조 파일 목록

| _v1 파일 | 라인수 | 활성 page.tsx |
|----------|--------|---------------|
| `(auth)/signup/_v1/page-v1.tsx` | 405 | `(auth)/signup/page.tsx` |
| `(auth)/login/_v1/page-v1.tsx` | 145 | `(auth)/login/page.tsx` |
| `(dashboard)/settings/_v1/page-v1.tsx` | 872 | `(dashboard)/settings/page.tsx` |
| `(dashboard)/home/_v1/page-v1.tsx` | 1117 | `(dashboard)/home/page.tsx` |
| `(dashboard)/signals/_v1/page-v1.tsx` | 452 | `(dashboard)/signals/page.tsx` |
| `(dashboard)/profile/_v1/page-v1.tsx` | 857 | `(dashboard)/profile/page.tsx` |
| `(dashboard)/portfolio/_v1/page-v1.tsx` | 448 | `(dashboard)/portfolio/page.tsx` |
| `(dashboard)/risk/_v1/page-v1.tsx` | 619 | `(dashboard)/risk/page.tsx` |
| `(dashboard)/reports/_v1/page-v1.tsx` | 359 | `(dashboard)/reports/page.tsx` |
| **합계** | **5274줄** | |
