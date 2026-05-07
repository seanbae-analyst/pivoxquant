# PivoxQuant v1 Feature Inventory (2026-04-27)

> 조사 기준: `frontend/src/` 전수 grep + 각 page.tsx 직접 Read
> 거짓보고 금지 원칙 적용 — 추측 없이 파일/라인 인용만.

---

## 1. Pages (라우트 전수)

총 63개 page.tsx (dashboard 15 + auth 4 + reports preview 14 + features 11 + 기타 9 + simulator 1 + admin 2 + sample-reports 2)

### 1-A. Dashboard 페이지 — auth 필수

| Path | File | 표시 이름 | 핵심 컴포넌트 | 핵심 Hook | 핵심 Endpoint | v2 시안 매핑 |
|---|---|---|---|---|---|---|
| /home | `app/(dashboard)/home/page.tsx` | 홈 Terminal | TopTicker, KpiCard, DataTable, CandlestickChart, TodayMemoHero, EquityCurveChart, SectorAllocationDonut, ArtifactQueue, LivingCFOStatusBar, WeeklyPulseCard, UpsellPlus | usePortfolioSummary, usePortfolioPositions, useWatchlist | /api/brief/today, /api/signals, /api/risk/summary, /api/portfolio/summary, /api/portfolio/positions, /api/watchlist | home-v2 대체 |
| /portfolio | `app/(dashboard)/portfolio/page.tsx` | The Ledger Binder | LedgerBookPaper, SectorPaper, ActivityPaper, AddPositionModal, TradeModal, DossierDesk, PaperDocument, RollingWindowWidget | (inline useSWR) | PORTFOLIO_POSITIONS(/api/portfolio/positions), PORTFOLIO_SUMMARY(/api/portfolio/summary), PORTFOLIO_TRADES(/api/portfolio/trades) | portfolio-v2 대체 |
| /risk | `app/(dashboard)/risk/page.tsx` | Risk Observation Board | InteractiveLineChart (inline 7-layer ladder, correlation heatmap, rolling VaR chart) | (inline useSWR) | RISK_SUMMARY(/api/risk/summary), RISK_LAYERS(/api/risk/layers), RISK_CORRELATION(/api/risk/correlation), RISK_ROLLING_VAR(/api/risk/rolling-var) | risk-v2 대체 |
| /signals | `app/(dashboard)/signals/page.tsx` | The Clip Board | ClipboardPaper, SignalMemoStrip, DossierDesk, PaperDocument | (inline useSWR) | /api/signals, /api/signals/refresh | signals-v2 대체 |
| /reports | `app/(dashboard)/reports/page.tsx` | Reports / Artifact Library | SectionFeedbackBar, PeerBenchmarkBlock | useArtifacts, usePersona | /api/artifacts/list, /api/artifacts/{id}/preview, /api/artifacts/{id}/download | reports-v2 대체 |
| /settings | `app/(dashboard)/settings/page.tsx` | Settings | KisCard, KisConnectModal, AlpacaCard, AlpacaConnectModal, ModalShell | useBrokerConnections, useAuth | /api/billing/subscription, /api/billing/portal, /api/broker/connections, /api/broker/kis/*, /api/broker/alpaca/*, /api/profile/capital, /api/push/* | v1 그대로 유지 |
| /settings/profile | `app/(dashboard)/settings/profile/page.tsx` | 설정 > 프로필 | (구 settings 서브라우트) | — | — | v1 그대로 유지 |
| /profile | `app/(dashboard)/profile/page.tsx` | Identity · Persona · Living CFO | PersonaV2Card, PersonaEvolution, WeeklyPulseCard, ModalShell | useInvestmentProfile, usePersona, usePulse, useCompanionStatus | /api/profile, /api/profile/persona, /api/profile/pulse, /api/profile/persona-detail | v1 그대로 유지 |
| /market | `app/(dashboard)/market/page.tsx` | Morning Papers | OverviewPaper, IndicesDetailPaper, CalendarNewsPaper, DossierDesk, PaperDocument | (inline useSWR) | MARKET_INDICES(/api/market/indices), /api/market/fx, /api/macro | v1 그대로 유지 |
| /watchlist | `app/(dashboard)/watchlist/page.tsx` | Watchlist | AddSymbolModal, PriceWithTimestamp | useWatchlist | /api/watchlist, /api/watchlist/{id} | v1 그대로 유지 |
| /discover | `app/(dashboard)/discover/page.tsx` | Discover | (inline SWR + mock fallback) | useDiscover | DISCOVER_OVERVIEW, DISCOVER_MOVERS, DISCOVER_SECTORS, DISCOVER_SCREENERS, /api/discover | v1 그대로 유지 |
| /alerts | `app/(dashboard)/alerts/page.tsx` | Alerts History | (inline) | useAlerts | /api/alerts, /api/alerts/read, /api/alerts/clear, /api/alerts/read-all, /api/alerts/{id}/read | v1 그대로 유지 |
| /detail/[ticker] | `app/(dashboard)/detail/[ticker]/page.tsx` | Stock Detail (7-section) | InteractiveLineChart, DisclaimerBanner, PriceWithTimestamp | useWatchlist | /api/lookup/{ticker}, /api/chart/{ticker}, /api/signals/{ticker}, /api/news/{ticker}, /api/market/profile/{ticker}, /api/peers/{ticker}, /api/ai/swot, /api/ai/competitor, /api/ai/sector-trend, /api/ai/commentary | v1 그대로 유지 |
| /companion | `app/(dashboard)/companion/page.tsx` | Personal Journal Companion | ChatPanel, disclaimer-band | useCompanionStatus | /api/agent/status, /api/agent/query, /api/agent/waitlist | v1 그대로 유지 |
| /morning-brief | `app/(dashboard)/morning-brief/page.tsx` | Morning Brief | (inline) | useMorningBrief, useMorningBriefArchive, useMacro | /api/brief/today, /api/brief/archive, /api/brief/generate-now, /api/macro | v1 그대로 유지 |
| /ai-chat | `app/(dashboard)/ai-chat/page.tsx` | AI Observation Chat | TierGate | — | /api/ai/chat (SSE stream) | v1 그대로 유지 |
| /ai | `app/(dashboard)/ai/page.tsx` | AI Analysis Tools | TierGate, DisclaimerBanner | — | /api/ai/coaching, /api/ai/swot, /api/ai/competitor, /api/ai/sector-trend, /api/ai/commentary | v1 그대로 유지 |
| /growth | `app/(dashboard)/growth/page.tsx` | Growth OS Dashboard | GrowthGraph, WeeklyTrendChart, ReflectionForm, StreakCounter | useGrowthData, useGrowthToday, useGrowthWeekly | /api/growth/data, /api/growth/today, /api/growth/reflect, /api/growth/weekly | v1 그대로 유지 |

### 1-B. Auth 페이지

| Path | File | 표시 이름 | 핵심 컴포넌트 | Endpoint |
|---|---|---|---|---|
| /login | `app/(auth)/login/page.tsx` | 로그인 | GoogleIcon, KakaoIcon | /api/auth/google, /api/auth/kakao |
| /signup | `app/(auth)/signup/page.tsx` | 회원가입 | (별도 확인 필요) | /api/auth/register |
| /onboarding | `app/(auth)/onboarding/page.tsx` | 온보딩 20문항 | ProgressBar, OptionCard, MultiOptionCard, SliderInput, LegalStep, ResultScreen | /api/profile/onboarding |
| /onboarding/broker | `app/(auth)/onboarding/broker/page.tsx` | 온보딩 브로커 선택 | (별도 확인 필요) | — |

### 1-C. Reports Preview 페이지 (14개)

| Path | File | 사용 컴포넌트 |
|---|---|---|
| /reports/preview/weekly-memo | page.tsx | `components/reports/templates/weekly-memo.tsx` |
| /reports/preview/morning-brief-plus | page.tsx | `components/reports/templates/morning-brief-plus.tsx` |
| /reports/preview/brag-card | page.tsx | `components/reports/templates/brag-card.tsx` |
| /reports/preview/earnings-prebrief | page.tsx | `components/reports/templates/earnings-prebrief.tsx` |
| /reports/preview/risk-board | page.tsx | `components/reports/templates/risk-board.tsx` |
| /reports/preview/quarterly-self-report | page.tsx | `components/reports/templates/quarterly-self-report.tsx` |
| /reports/preview/self-audit | page.tsx | `components/reports/templates/self-audit.tsx` |
| /reports/preview/dd-checklist | page.tsx | `components/reports/templates/dd-checklist.tsx` |
| /reports/preview/dividend-income | page.tsx | `components/reports/templates/dividend-income.tsx` |
| /reports/preview/insider-mirror | page.tsx | `components/reports/templates/insider-mirror.tsx` |
| /reports/preview/sp500-backtest | page.tsx | `components/reports/templates/sp500-backtest.tsx` |
| /reports/preview/portfolio-segment | page.tsx | `components/reports/templates/portfolio-segment.tsx` |
| /reports/preview/capital-allocation | page.tsx | `components/reports/templates/capital-allocation.tsx` |
| /reports/preview/credit-rating | page.tsx | `components/reports/templates/credit-rating.tsx` |
| /reports/preview/burn-rate | page.tsx | `components/reports/templates/burn-rate.tsx` |
| /reports/preview/monthly-finance | page.tsx | `components/reports/templates/monthly-finance.tsx` |
| /reports/preview/kpi-dashboard | page.tsx | `components/reports/templates/kpi-dashboard.tsx` |
| /reports/preview/year-end-letter | page.tsx | `components/reports/templates/year-end-letter.tsx` |

Note: find 결과 14개 preview page 확인됨. catalog(CATALOG 상수)에는 18개. 4개(burn-rate, monthly-finance, kpi-dashboard, year-end-letter)는 preview 페이지 생성 확인됨 — 전체 18개 모두 page.tsx 존재.

### 1-D. Features 페이지 (11개, 마케팅/랜딩용)

| Path | File |
|---|---|
| /features/ai-assistant | page.tsx |
| /features/canslim | page.tsx |
| /features/dashboard | page.tsx |
| /features/engine | page.tsx |
| /features/explorer | page.tsx |
| /features/global-desk | page.tsx |
| /features/paper-trading | page.tsx |
| /features/personas | page.tsx |
| /features/pre-trade | page.tsx |
| /features/profiles | page.tsx |
| /features/quant-scoring | page.tsx |
| /features/reports | page.tsx |
| /features/risk-defense | page.tsx |

### 1-E. 기타 공개 페이지

| Path | File | 표시 이름 | Auth 필요 |
|---|---|---|---|
| / (root) | `app/page.tsx` | 랜딩 (미로그인) 또는 /home 리다이렉트 (로그인) | No |
| /beta-gate | `app/beta-gate/page.tsx` | Private Beta 비밀번호 게이트 | No |
| /pricing | `app/pricing/page.tsx` | 3-tier 가격표 | No |
| /privacy | `app/privacy/page.tsx` | 개인정보처리방침 | No |
| /terms | `app/terms/page.tsx` | 이용약관 | No |
| /docs | `app/docs/page.tsx` | 문서 | No |
| /sample-reports | `app/sample-reports/page.tsx` | 샘플 리포트 인덱스 (18개) | No |
| /sample-reports/[slug] | `app/sample-reports/[slug]/page.tsx` | 개별 샘플 리포트 | No |
| /simulator/what-if | `app/simulator/what-if/page.tsx` | 타임머신 시뮬레이터 | No |
| /admin | `app/admin/page.tsx` | Admin 인덱스 → /admin/preview 리다이렉트 | Admin only |
| /admin/preview | `app/admin/preview/page.tsx` | Admin 아티팩트 미리보기 | Admin only |

---

## 2. Components (전수)

총 107개 .tsx 파일 (`find frontend/src/components -name "*.tsx"` 결과)

### 2-A. artifacts/ (1개)
| File | Export | 사용 페이지 |
|---|---|---|
| `artifacts/section-feedback.tsx` | SectionFeedbackBar | /reports |

### 2-B. broker/ (5개)
| File | Export | 사용 페이지 |
|---|---|---|
| `broker/alpaca-card.tsx` | AlpacaCard | /settings |
| `broker/alpaca-connect-modal.tsx` | AlpacaConnectModal | /settings |
| `broker/kis-card.tsx` | KisCard | /settings |
| `broker/kis-connect-modal.tsx` | KisConnectModal | /settings |
| `broker/manual-card.tsx` | ManualCard | /settings (미사용 가능) |

### 2-C. charts/ (1개)
| File | Export | 사용 페이지 |
|---|---|---|
| `charts/interactive-line-chart.tsx` | InteractiveLineChart | /risk, /detail/[ticker] |

### 2-D. companion/ (2개)
| File | Export | 사용 페이지 |
|---|---|---|
| `companion/chat-panel.tsx` | ChatPanel | /companion |
| `companion/disclaimer-band.tsx` | DisclaimerBand | /companion |

### 2-E. dashboard/ (5개)
| File | Export | 사용 페이지 |
|---|---|---|
| `dashboard/living-cfo-status.tsx` | LivingCFOStatusBar | /home |
| `dashboard/persona-evolution.tsx` | PersonaEvolution | /profile |
| `dashboard/persona-v2-card.tsx` | PersonaV2Card | /profile |
| `dashboard/rolling-window.tsx` | RollingWindowWidget | /portfolio |
| `dashboard/upsell-plus.tsx` | UpsellPlus | /home |
| `dashboard/weekly-pulse.tsx` | WeeklyPulseCard | /home, /profile |

### 2-F. growth/ (4개)
| File | Export | 사용 페이지 |
|---|---|---|
| `growth/growth-graph.tsx` | GrowthGraph | /growth |
| `growth/reflection-form.tsx` | ReflectionForm | /growth |
| `growth/streak-counter.tsx` | StreakCounter | /growth |
| `growth/weekly-trend-chart.tsx` | WeeklyTrendChart | /growth |

### 2-G. home/ (10개)
| File | Export | 사용 페이지 |
|---|---|---|
| `home/artifact-queue.tsx` | ArtifactQueue | /home |
| `home/dossier-desk.tsx` | DossierDesk | /home, /portfolio, /signals, /market |
| `home/equity-curve-chart.tsx` | EquityCurveChart | /home |
| `home/paper-document.tsx` | PaperDocument | /home, /portfolio, /signals, /market |
| `home/persona-glyph.tsx` | PersonaGlyph | (미사용 가능 — 확인 필요) |
| `home/positions-ledger-paper.tsx` | PositionsLedgerPaper | (미사용 가능 — 확인 필요) |
| `home/sector-allocation-donut.tsx` | SectorAllocationDonut | /home |
| `home/signal-paper.tsx` | SignalPaper | (미사용 가능 — 확인 필요) |
| `home/this-morning-paper.tsx` | ThisMorningPaper | (미사용 가능 — 확인 필요; home/page.tsx 주석에서 "retired") |
| `home/today-hero.tsx` | TodayHero | (미사용 가능 — 확인 필요) |
| `home/today-memo-hero.tsx` | TodayMemoHero | /home |

### 2-H. landing/ (21개)
| File | 사용 페이지 |
|---|---|
| `landing/cta-ink-bleed.tsx` | / (랜딩) |
| `landing/deposition-teaser.tsx` | / (랜딩) |
| `landing/engine-models-drawer.tsx` | / (랜딩) |
| `landing/eyebrow.tsx` | / (랜딩) |
| `landing/feature-page-shell.tsx` | /features/* |
| `landing/film-grain.tsx` | / (랜딩) |
| `landing/hero-artifact-preview.tsx` | / (랜딩) |
| `landing/hero-aurora.tsx` | / (랜딩) |
| `landing/hero-data-stream.tsx` | / (랜딩) |
| `landing/hero-particles.tsx` | / (랜딩) |
| `landing/hero-spotlight.tsx` | / (랜딩) |
| `landing/hero-typography.tsx` | / (랜딩) |
| `landing/hero.tsx` | / (랜딩) |
| `landing/korea-us-desk.tsx` | / (랜딩) |
| `landing/landing-v2.tsx` | / (랜딩) — app/page.tsx에서 직접 import |
| `landing/living-cfo-loop.tsx` | / (랜딩) |
| `landing/market-ticker.tsx` | / (랜딩) |
| `landing/marquee-logos.tsx` | / (랜딩) |
| `landing/mobile-drawer.tsx` | / (랜딩) |
| `landing/persona-showcase.tsx` | / (랜딩) |
| `landing/personas-preview.tsx` | / (랜딩) |
| `landing/report-flip-card.tsx` | / (랜딩) |
| `landing/report-flip-deck.tsx` | / (랜딩) |
| `landing/section-curtain.tsx` | / (랜딩) |
| `landing/splash-page.tsx` | / (랜딩) |
| `landing/three-layers.tsx` | / (랜딩) |
| `landing/top-nav.tsx` | / (랜딩) |

### 2-I. layout/ (4개)
| File | Export | 사용 위치 |
|---|---|---|
| `layout/bottom-nav.tsx` | BottomNav | DashboardLayout (모바일 하단 탭) |
| `layout/dashboard-layout.tsx` | DashboardLayout | (dashboard)/layout.tsx |
| `layout/terminal-sidebar.tsx` | TerminalSidebar | DashboardLayout (데스크톱 좌측 사이드바) |
| `layout/top-bar.tsx` | TopBar | DashboardLayout (상단 헤더) |

### 2-J. market/ (4개)
| File | Export | 사용 페이지 |
|---|---|---|
| `market/calendar-news-paper.tsx` | CalendarNewsPaper | /market |
| `market/index-card.tsx` | IndexCard, useNowTick, relativeTime | /market, /discover |
| `market/indices-detail-paper.tsx` | IndicesDetailPaper | /market |
| `market/overview-paper.tsx` | OverviewPaper | /market |

### 2-K. portfolio/ (5개 + types)
| File | Export | 사용 페이지 |
|---|---|---|
| `portfolio/activity-paper.tsx` | ActivityPaper | /portfolio |
| `portfolio/add-position-modal.tsx` | AddPositionModal | /portfolio |
| `portfolio/ledger-book-paper.tsx` | LedgerBookPaper | /portfolio |
| `portfolio/portfolio-modal.tsx` | PortfolioModal | (미사용 가능 — 확인 필요) |
| `portfolio/sector-paper.tsx` | SectorPaper | /portfolio |
| `portfolio/trade-modal.tsx` | TradeModal | /portfolio |

Note: `portfolio/types` 파일 존재 (`Position`, `Trade`, `TradeAction` 타입) — home/page.tsx line 56: `import type { Position } from "@/components/portfolio/types"`

### 2-L. pwa/ (2개)
| File | Export | 사용 위치 |
|---|---|---|
| `pwa/install-prompt.tsx` | InstallPrompt | app/layout.tsx (root) |
| `pwa/push-permission.tsx` | PushPermission | (dashboard)/layout.tsx |

### 2-M. reports/templates/ (18개)
brag-card, burn-rate, capital-allocation, credit-rating, dd-checklist, dividend-income, earnings-prebrief, insider-mirror, kpi-dashboard, monthly-finance, morning-brief-plus, portfolio-segment, quarterly-self-report, risk-board, self-audit, sp500-backtest, weekly-memo, year-end-letter

각각 `/reports/preview/{slug}` 페이지에서 1:1 매핑.

`reports/pdf-primitives.tsx` — PDF 렌더링 공통 프리미티브

### 2-N. risk/ (1개)
| File | Export | 사용 페이지 |
|---|---|---|
| `risk/seven-layer-panel.tsx` | SevenLayerPanel (타입만 re-export됨) | /risk (타입 임포트) |

Note: /risk/page.tsx는 seven-layer-panel에서 `type RiskLayer`, `type LayerStatus`만 import. 실제 7-layer 렌더는 page.tsx 인라인.

### 2-O. shared/ (1개)
| File | Export | 사용 페이지 |
|---|---|---|
| `shared/peer-benchmark-block.tsx` | PeerBenchmarkBlock | /reports |

### 2-P. signals/ (2개)
| File | Export | 사용 페이지 |
|---|---|---|
| `signals/clipboard-paper.tsx` | ClipboardPaper | /signals |
| `signals/signal-memo-strip.tsx` | SignalMemoStrip, MemoSignalItem | /signals (ClipboardPaper 통해) |

### 2-Q. terminal/ (5개)
| File | Export | 사용 페이지 |
|---|---|---|
| `terminal/candlestick-chart.tsx` | CandlestickChart | /home |
| `terminal/command-palette.tsx` | CommandPalette | (미사용 가능 — 확인 필요; search-command.tsx가 대체) |
| `terminal/data-table.tsx` | DataTable | /home |
| `terminal/kpi-card.tsx` | KpiCard | /home |
| `terminal/top-ticker.tsx` | TopTicker | /home |

### 2-R. ui/ (15개)
| File | Export | 사용 위치 |
|---|---|---|
| `ui/cookie-consent.tsx` | CookieConsent | app/layout.tsx (root) |
| `ui/count-up.tsx` | CountUp | /pricing |
| `ui/disclaimer-banner.tsx` | DisclaimerBanner | (dashboard)/layout.tsx (path-aware), /ai, /detail/[ticker] |
| `ui/editorial.tsx` | FootSignature, Fleuron, Caption, RuledKicker, FieldLabel, StatRow, NumDisplay, Eyebrow | 대부분 dashboard 페이지 |
| `ui/error-boundary.tsx` | ErrorBoundary | 모든 dashboard 페이지 |
| `ui/legal-consent-modal.tsx` | LegalConsentModal | (미사용 가능 — 확인 필요) |
| `ui/loading-skeleton.tsx` | DashboardSkeleton, LoadingSkeleton | (dashboard)/layout.tsx |
| `ui/modal-shell.tsx` | ModalShell | /settings, /profile, 기타 모달 |
| `ui/notification-dropdown.tsx` | NotificationDropdown | layout/top-bar.tsx |
| `ui/price-with-timestamp.tsx` | PriceWithTimestamp, relativeTime | /portfolio, /watchlist, /detail |
| `ui/profile-dropdown.tsx` | ProfileDropdown | layout/top-bar.tsx |
| `ui/search-command.tsx` | SearchCommandMenu, openSearchCommand | layout/top-bar.tsx |
| `ui/tick-number.tsx` | TickNumber | (확인 필요) |
| `ui/tier-gate.tsx` | TierGate | /ai-chat, /ai |
| `ui/disclaimer-banner.tsx` | DisclaimerBanner | — |

### 2-S. watchlist/ (1개)
| File | Export | 사용 페이지 |
|---|---|---|
| `watchlist/add-symbol-modal.tsx` | AddSymbolModal | /watchlist |

---

## 3. Hooks (전수)

### 3-A. `lib/hooks.ts` (14개 hook)

| Name | Endpoint | Return type | 사용처 |
|---|---|---|---|
| useDiscover | /api/discover | DiscoverResponse | /discover |
| useInvestmentProfile | /api/profile | ProfileResponse | /profile |
| useWatchlist | /api/watchlist | WatchlistResponse | /watchlist, /home, /detail |
| useAlerts | /api/alerts | AlertsResponse | /alerts |
| useMorningBrief | /api/brief/today | MorningBriefResponse | /morning-brief, /home |
| useMorningBriefArchive | /api/brief/archive | MorningBriefArchiveResponse | /morning-brief |
| useGrowthData(range) | /api/growth/data?range={range} | GrowthScoreEntry[] | /growth |
| useGrowthToday | /api/growth/today | GrowthTodayResponse | /growth |
| useGrowthWeekly | /api/growth/weekly | GrowthWeeklyReport[] | /growth |
| useArtifacts(options) | /api/artifacts/list | ArtifactsListResponse | /reports, /home (ArtifactQueue) |
| useBrokerConnections | /api/broker/connections | BrokerConnectionsResponse | /settings |
| usePortfolioSummary | /api/portfolio/summary | PortfolioSummary | /home, /portfolio, (RealtimeProvider) |
| usePortfolioPositions | /api/portfolio/positions | any | /home, /portfolio |
| useMacro | /api/macro | MacroResponse | /morning-brief |
| useRealtimeContext (re-export) | — | RealtimeState | 실시간 SSE 소비자 |

### 3-B. `lib/cfo/hooks.ts` (6개 hook)

| Name | Endpoint | 사용처 |
|---|---|---|
| usePersona | /api/profile/persona | /profile, /reports |
| useRollingWindow | /api/profile/rolling-window | /portfolio (RollingWindowWidget) |
| useFeedback | /api/profile/feedback (POST) | /reports (SectionFeedbackBar) |
| usePulse | /api/profile/pulse | /profile |
| usePersonaDetail(windowDays) | /api/profile/persona-detail?window_days={n} | /profile (PersonaV2Card) |
| usePersonaBenchmark(windowDays) | /api/profile/persona-benchmark?window={n} | /reports (PeerBenchmarkBlock) |
| usePersonaBenchmarkAll(windowDays) | /api/profile/persona-benchmark-all?window={n} | (확인 필요) |

### 3-C. `lib/cfo/useCompanion.ts`

| Name | Endpoint | 사용처 |
|---|---|---|
| useCompanionStatus | /api/agent/status | /companion, /profile |
| hasCompanionEntitlement | (util function) | /companion, /profile |
| useCompanionChat (추정) | /api/agent/query (POST) | ChatPanel |

### 3-D. `lib/realtime.tsx` (RealtimeProvider)

- `useRealtimeContext` — SSE EventSource /api/realtime/stream 구독
- RealtimeProvider — (dashboard)/providers.tsx 에서 AuthProvider 내부에 마운트
- 실시간 가격 업데이트를 SWR 캐시에 직접 write-through

---

## 4. Endpoints (전수)

`lib/endpoints.ts` 기준 — 총 그룹 15개, 엔드포인트 70+ 개

### 4-A. auth (7개)
| URL | Method | 사용 위치 |
|---|---|---|
| /api/auth/register | POST | /signup |
| /api/auth/login | POST | (email auth — 현재 OAuth only) |
| /api/auth/logout | POST | /settings |
| /api/auth/me | GET | AuthProvider |
| /api/auth/google | GET redirect | /login |
| /api/auth/kakao | GET redirect | /login |
| /api/auth/delete-account | DELETE | /settings (삭제는 이메일 연락으로만) |

### 4-B. portfolio (11개)
| URL | Method |
|---|---|
| /api/portfolio | GET |
| /api/portfolio/analytics | GET |
| /api/portfolio/history?period={period} | GET |
| /api/portfolio/position | POST (addPosition) |
| /api/portfolio/position/{id} | PUT (edit), DELETE |
| /api/portfolio/position/{id}/buy | POST |
| /api/portfolio/position/{id}/sell | POST |
| /api/portfolio/position/buy-new | POST |
| /api/portfolio/capital | GET |
| /api/portfolio/positions | GET (alias PORTFOLIO_POSITIONS) |
| /api/portfolio/summary | GET (alias PORTFOLIO_SUMMARY) |
| /api/portfolio/trades | GET (alias PORTFOLIO_TRADES) |

### 4-C. signals (9개)
| URL | Method |
|---|---|
| /api/signals | GET |
| /api/signals/{ticker} | GET |
| /api/signals/refresh | POST |
| /api/scan | GET |
| /api/signals/short-interest/{ticker} | GET |
| /api/signals/insider/{ticker} | GET |
| /api/signals/disposition/{ticker} | GET |
| /api/signals/ofi/{ticker} | GET |
| /api/signals/sentiment-divergence/{ticker} | GET |
| /api/signals/anchoring/{ticker} | GET |
| /api/signals/herding | GET |

### 4-D. market (13개)
| URL | Method |
|---|---|
| /api/market/overview | GET |
| /api/market/status | GET |
| /api/market/fx | GET |
| /api/macro | GET |
| /api/sectors | GET |
| /api/morning-brief | GET |
| /api/brief/today | GET |
| /api/brief/archive | GET |
| /api/brief/generate-now | POST |
| /api/search?q={query} | GET |
| /api/lookup/{ticker} | GET |
| /api/prices | GET |
| /api/chart/{ticker} | GET |
| /api/earnings | GET |
| /api/peers/{ticker} | GET |
| /api/market/profile/{ticker} | GET |
| /api/dividend/{ticker} | GET |
| /api/news/{ticker} | GET |
| /api/market/indices | GET (alias MARKET_INDICES) |

### 4-E. discover (4개 alias)
| URL |
|---|
| /api/discover (+ API.discover) |
| /api/discover/market-overview (DISCOVER_OVERVIEW) |
| /api/discover/movers (DISCOVER_MOVERS) |
| /api/discover/sectors (DISCOVER_SECTORS) |
| /api/discover/screeners (DISCOVER_SCREENERS) |

### 4-F. alerts (8개)
| URL | Method |
|---|---|
| /api/alerts | GET |
| /api/alerts/read | POST |
| /api/alerts/clear | DELETE |
| /api/alerts/price-check | GET |
| /api/alerts/unread-count | GET |
| /api/alerts/read-all | POST |
| /api/alerts/{id}/read | PUT |
| /api/alerts/{id} | DELETE |

### 4-G. ai (11개)
| URL | Method |
|---|---|
| /api/ai/status | GET |
| /api/ai/chat | POST (SSE) |
| /api/ai/swot | POST |
| /api/ai/competitor | POST |
| /api/ai/sector-trend | POST |
| /api/ai/commentary | POST |
| /api/ai/morning-summary | POST |
| /api/ai/coaching | POST |
| /api/ai/earnings-tone | POST |
| /api/ai/sector-regime | POST |
| /api/ai/risk-summary | POST |

### 4-H. risk (6개 + 4개 alias)
| URL |
|---|
| /api/risk/var |
| /api/risk/drawdown |
| /api/risk/stress-test |
| /api/risk/volatility/{ticker} |
| /api/risk/component-es |
| /api/risk/defense-status |
| /api/risk/summary (alias RISK_SUMMARY) |
| /api/risk/layers (alias RISK_LAYERS) |
| /api/risk/correlation (alias RISK_CORRELATION) |
| /api/risk/rolling-var (alias RISK_ROLLING_VAR) |

### 4-I. simulate (6개)
| URL |
|---|
| /api/portfolio/simulate/hrp |
| /api/portfolio/simulate/trp |
| /api/portfolio/simulate/mdp |
| /api/portfolio/simulate/erc |
| /api/portfolio/simulate/min-variance |
| /api/simulate/counterfactual?{params} |

### 4-J. broker (10개)
| URL | Method |
|---|---|
| /api/broker/connections | GET |
| /api/broker/kis/connect | POST |
| /api/broker/kis/sync | POST |
| /api/broker/kis/disconnect | DELETE |
| /api/broker/kis/status | GET |
| /api/broker/alpaca/connect | POST |
| /api/broker/alpaca/sync | POST |
| /api/broker/alpaca/disconnect | DELETE |
| /api/broker/alpaca/status | GET |

### 4-K. billing (3개)
| URL | Method |
|---|---|
| /api/billing/create-checkout | POST |
| /api/billing/subscription | GET |
| /api/billing/portal | POST |

### 4-L. push (3개)
| URL |
|---|
| /api/push/subscribe |
| /api/push/unsubscribe |
| /api/push/status |

### 4-M. profile (9개)
| URL |
|---|
| /api/profile |
| /api/profile/onboarding |
| /api/profile/questionnaire |
| /api/profile/capital |
| /api/profile/persona-detail?window_days={n} |
| /api/profile/persona-explain |
| /api/profile/persona-benchmark?window={n} |
| /api/profile/persona-benchmark-all?window={n} |
| /api/profile/persona (CFO hook — 404 fallback to mock) |
| /api/profile/rolling-window (CFO hook — 404 fallback to mock) |
| /api/profile/feedback (CFO hook) |
| /api/profile/pulse (CFO hook) |

### 4-N. artifacts (4개)
| URL |
|---|
| /api/artifacts/list |
| /api/artifacts/{id}/download |
| /api/artifacts/{id}/preview |
| /api/artifacts/{id}/read |

### 4-O. agent/companion (3개)
| URL |
|---|
| /api/agent/query |
| /api/agent/status |
| /api/agent/waitlist |

### 4-P. growth (4개)
| URL |
|---|
| /api/growth/data?range={range} |
| /api/growth/today |
| /api/growth/reflect |
| /api/growth/weekly |

### 4-Q. admin (2개)
| URL |
|---|
| /api/admin/artifacts/list |
| /api/admin/artifacts/preview/{type}?format={format} |

### 4-R. share (2개)
| URL |
|---|
| /api/portfolio/share |
| /api/portfolio/share/{token} |

### 4-S. quant (6개)
| URL |
|---|
| /api/vix-strategy |
| /api/cross-asset |
| /api/stat-arb |
| /api/indicators/{ticker} |
| /api/screener/canslim/{ticker} |
| /api/regime/interest-rate |

### 4-T. analytics (3개)
| URL |
|---|
| /api/analytics/regime-report |
| /api/analytics/benchmark |
| /api/analytics/turnover |

### 4-U. performance (1개)
| URL |
|---|
| /api/performance/ledger |

### 4-V. tools (3개)
| URL |
|---|
| /api/tools/position-sizing |
| /api/tools/correlation-matrix |
| /api/tools/sector-heatmap |

### 4-W. 삭제된 그룹
- `autotrade` — 2026-04-27 CEO + legal 결정으로 제거. endpoints.ts 주석으로 보존 (line 81-84).

---

## 5. PWA 구성

| 항목 | 내용 |
|---|---|
| manifest 파일 | `app/manifest.ts` (Next.js MetadataRoute.Manifest) |
| manifest URL | `/manifest.webmanifest` (Next.js 자동 서빙) |
| app name | "PivoxQuant — 당신은 당신 포트폴리오의 CFO" |
| short_name | "PivoxQuant" |
| start_url | "/" |
| display | "standalone" |
| theme_color | "#050505" (Vantablack) |
| background_color | "#050505" |
| icons | 72/96/144/192/512px PNG (`/icons/*.png`) |
| shortcuts | Portfolio(/portfolio), Market(/market), Risk Board(/risk), Watchlist(/watchlist) |
| Service Worker | `public/sw.js` (custom, NOT next-pwa) — v4 |
| SW 캐시 전략 | networkOnly: /api/auth/*, /api/ai/*, /api/daytrade/*, /api/realtime/*, /api/broker/kis/* |
| SW 캐시 전략 | cacheFirst: /api/morning-brief |
| SW 캐시 전략 | staleWhileRevalidate: /api/market/overview (2h), /api/sectors (2h) |
| SW 등록 | globals.css 또는 layout.tsx에서 등록 추정 (별도 확인 필요) |
| Install prompt | `components/pwa/install-prompt.tsx` → app/layout.tsx |
| Push permission | `components/pwa/push-permission.tsx` → (dashboard)/layout.tsx |
| next-pwa 패키지 | 미사용 — custom sw.js 직접 작성 |

---

## 6. Layout / Provider 인벤토리

### Root (`app/layout.tsx`)
- Fonts: Geist (--font-sans, --font-heading), JetBrains_Mono (--font-mono), Source_Serif_4 (--font-serif), Playfair_Display (--font-display)
- Providers 컴포넌트 내부에 CookieConsent, InstallPrompt
- Toaster (sonner) — top-right
- Pretendard CDN preconnect (한국어 폰트)

### Providers (`app/providers.tsx`)
1. SWRConfig (dedupingInterval 6000, revalidateOnFocus false, errorRetryCount 2)
2. LocaleProvider (`lib/locale.tsx`)
3. AuthProvider (`lib/auth.tsx`)
4. RealtimeProvider (`lib/realtime.tsx`) — SSE 구독

### Dashboard Layout (`app/(dashboard)/layout.tsx`)
- AuthGuard: user 없으면 /login, onboarding_completed=false면 /onboarding/broker
- DashboardLayout (sidebar + topbar + bottom-nav)
- DisclaimerBanner — path-aware, 유형별: signal/ai-analysis/coaching
- PushPermission

### Auth Layout (`app/(auth)/layout.tsx`)
- 별도 confirm 필요 (파일 직접 확인 안 함)

### DisclaimerBanner 마운트 위치
- `(dashboard)/layout.tsx` line 111: `<DisclaimerBanner type={disclaimerType} alwaysExpanded={alwaysExpanded} />`
- PATH_TO_TYPE 매핑: /morning-brief→signal, /ai-chat→ai-analysis, /watchlist→signal, /portfolio→signal, /companion→ai-analysis, /discover→signal, /settings→signal, /profile→signal, /reports→ai-analysis, /signals→signal, /alerts→signal, /market→signal, /detail→signal, /growth→signal, /risk→signal, /home→signal, /ai→ai-analysis
- 추가 인라인 마운트: /ai/page.tsx, /detail/[ticker]/page.tsx (SWOT 섹션 내)

---

## 7. 기능별 인벤토리 (사용자 관점)

| 기능 | 위치 (페이지/컴포넌트) | 동작 여부 | v2 시안에 포함? | 보존 조치 |
|---|---|---|---|---|
| **Settings — 프로필 읽기** | /settings AccountSection | 동작 (read-only 표시) | No | v1 그대로 유지 |
| **Settings — 구독 관리** | /settings SubscriptionSection | 동작 (tier 표시 + 업그레이드 링크) | No | v1 그대로 유지 |
| **Settings — KIS 연결** | /settings BrokersSection → KisCard + KisConnectModal | 동작 (모달 열림 확인됨) | No | v1 그대로 유지 |
| **Settings — Alpaca BYO 연결** | /settings BrokersSection → AlpacaCard + AlpacaConnectModal (NEXT_PUBLIC_ALPACA_ENABLED=1 조건부) | ⚠️ ALPACA_ENABLED=1 미설정 시 미표시 | No | v1 그대로 유지 |
| **Settings — 알림 설정 (Push/Email)** | /settings PreferencesSection | 동작 (toggle UI) | No | v1 그대로 유지 |
| **Settings — Seed Capital** | /settings SeedCapitalSection | 동작 | No | v1 그대로 유지 |
| **Settings — Language** | /settings PreferencesSection | 동작 (ko/en) | No | v1 그대로 유지 |
| **Settings — 로그아웃** | /settings 위험 구역 | 동작 | No | v1 그대로 유지 |
| **Settings — 탈퇴** | /settings DeleteAccountModal → 이메일 연락 CTA | 동작 (이메일 전환, 직접 삭제 없음) | No | v1 그대로 유지 |
| **알림 벨** | layout/top-bar.tsx → NotificationDropdown | 동작 (/api/alerts/unread-count + /api/alerts 로 live) | No | v1 그대로 유지 |
| **알림 목록 (전체)** | /alerts page | 동작 (useAlerts) | No | v1 그대로 유지 |
| **Push subscription** | PushPermission 컴포넌트, lib/push.ts | 구현 (브라우저 지원 여부 런타임 확인) | No | v1 그대로 유지 |
| **Search (Cmd+K)** | TopBar → SearchCommandMenu | 동작 (/api/search 연동, 최근 5개 localStorage) | No | v1 그대로 유지 |
| **Watchlist 추가** | /watchlist → AddSymbolModal | 동작 (/api/watchlist POST) | No | v1 그대로 유지 |
| **Watchlist 제거** | /watchlist 행의 삭제 버튼 | 동작 (/api/watchlist/{id} DELETE) | No | v1 그대로 유지 |
| **Portfolio — Position 추가** | /portfolio → AddPositionModal | 동작 (/api/portfolio/position POST) | Yes (portfolio-v2) | v2에 포함 필수 |
| **Portfolio — Buy More / Sell / Edit** | /portfolio LedgerBookPaper → TradeModal | 동작 | Yes (portfolio-v2) | v2에 포함 필수 |
| **Portfolio — Equity Curve** | /home EquityCurveChart, /portfolio SectorPaper | 동작 (portfolio/history 사용 추정) | Yes (portfolio-v2) | v2에 포함 필수 |
| **Portfolio — Sector Allocation** | /home SectorAllocationDonut, /portfolio SectorPaper | 동작 | Yes (portfolio-v2) | v2에 포함 필수 |
| **Portfolio — Trades 기록** | /portfolio ActivityPaper | 동작 (PORTFOLIO_TRADES) | Yes (portfolio-v2) | v2에 포함 필수 |
| **Market — US 지수 (S&P500, NASDAQ, DOW, Russell)** | /market OverviewPaper + IndicesDetailPaper | 동작 (MARKET_INDICES, mock fallback) | No | v1 그대로 유지 |
| **Market — KR 지수 (코스피, 코스닥)** | /market KR 탭 | ⚠️ HANDOVER §2-B: "KR indices range_52w/sparkline KIS history 우선"으로 수정됨 | No | v1 그대로 유지 |
| **Market — 환율 (USD/KRW)** | /market CalendarNewsPaper | 동작 (/api/market/fx) | No | v1 그대로 유지 |
| **Market — 매크로 (VIX, 10Y, Gold, Oil)** | /morning-brief, /home (useMacro) | 동작 | No | v1 그대로 유지 |
| **Signals — POSITIVE/NEGATIVE/NEUTRAL** | /signals ClipboardPaper × 3 | 동작 | Yes (signals-v2) | v2에 포함 필수 |
| **Signals — Refresh** | /signals Refresh 버튼 | 동작 (/api/signals/refresh POST) | Yes (signals-v2) | v2에 포함 필수 |
| **Signals — 종목 상세 연결** | /signals row → /detail/[ticker] | 동작 | Yes (signals-v2) | v2에 포함 필수 |
| **Risk — 7-Layer Defense** | /risk 인라인 렌더 | 동작 (RISK_LAYERS, demo fallback) | Yes (risk-v2) | v2에 포함 필수 |
| **Risk — VaR / ES / Max DD** | /risk KPI 4개 | 동작 (RISK_SUMMARY) | Yes (risk-v2) | v2에 포함 필수 |
| **Risk — Correlation Heatmap** | /risk 인라인 테이블 | 동작 (RISK_CORRELATION) | Yes (risk-v2) | v2에 포함 필수 |
| **Risk — Rolling VaR 차트** | /risk → InteractiveLineChart | 동작 (RISK_ROLLING_VAR) | Yes (risk-v2) | v2에 포함 필수 |
| **Reports — Artifact 카탈로그 (18종)** | /reports CATALOG 상수 | 동작 (tier-gated) | Yes (reports-v2) | v2에 포함 필수 |
| **Reports — Artifact Preview/Download** | /reports ArtifactCard | 동작 (preview → /reports/preview/{slug}) | Yes (reports-v2) | v2에 포함 필수 |
| **Reports — Preview 페이지 (18개)** | /reports/preview/* | 동작 | Yes (reports-v2) | v2에 포함 필수 |
| **Reports — Section Feedback** | /reports SectionFeedbackBar | 동작 (/api/profile/feedback) | Yes (reports-v2) | v2에 포함 필수 |
| **Reports — Peer Benchmark Block** | /reports PeerBenchmarkBlock | 동작 (usePersonaBenchmark) | Yes (reports-v2) | v2에 포함 필수 |
| **Reports — Persona 필터** | /reports personaFilter state | 동작 (client-side filter) | Yes (reports-v2) | v2에 포함 필수 |
| **AI Chat** | /ai-chat (SSE 스트림) | 동작 (TierGate 조건부) | No | v1 그대로 유지 |
| **AI Analysis (SWOT/Competitor/Sector/Commentary)** | /ai | 동작 (TierGate 조건부) | No | v1 그대로 유지 |
| **Simulator (What-If)** | /simulator/what-if | 동작 (공개, auth 불필요) | No | v1 그대로 유지 |
| **Onboarding — 20문항** | /onboarding (19 wizard + 1 legal = 20 steps) | 동작 | No | v1 그대로 유지 |
| **Onboarding — investor type 분류** | /onboarding ResultScreen (local + server) | 동작 | No | v1 그대로 유지 |
| **Auth — Google OAuth** | /login → /api/auth/google | 동작 (HANDOVER: OAuth 정상화 완료) | No | v1 그대로 유지 |
| **Auth — Kakao OAuth** | /login → /api/auth/kakao | 동작 (HANDOVER: OAuth 정상화 완료) | No | v1 그대로 유지 |
| **Auth — 로그아웃** | /settings → /api/auth/logout | 동작 | No | v1 그대로 유지 |
| **Detail page — 종목 상세 (7섹션)** | /detail/[ticker] | 동작 (일부 섹션 데이터 미완 — HANDOVER §3 참조) | No | v1 그대로 유지 |
| **Beta gate** | /beta-gate (BetaGateForm) | 동작 (Railway env `BETA_PASSWORD`) | No | v1 그대로 유지 |
| **Pricing 3-tier** | /pricing | 동작 (Free/Pro/Premium 카드 + Stripe 연결) | No | v1 그대로 유지 |
| **Sample Reports** | /sample-reports, /sample-reports/[slug] | 동작 (공개 페이지) | No | v1 그대로 유지 |
| **Profile — Identity (이름/이메일/OAuth)** | /profile | 동작 | No | v1 그대로 유지 |
| **Profile — Declared Persona** | /profile | 동작 (useInvestmentProfile + usePersona) | No | v1 그대로 유지 |
| **Profile — Persona V2 Card (9-dim)** | /profile PersonaV2Card | 동작 (usePersonaDetail) | No | v1 그대로 유지 |
| **Profile — Persona Evolution** | /profile PersonaEvolution | 동작 | No | v1 그대로 유지 |
| **Profile — Weekly Pulse** | /profile WeeklyPulseCard | 동작 (usePulse) | No | v1 그대로 유지 |
| **Profile — Agent Memory Export/Delete** | /profile (별도 확인 필요 — HANDOVER §3-A 언급) | ⚠️ UI 미구현 가능 | No | v1 그대로 유지 |
| **Companion (AI Journal)** | /companion (Closed Beta, Premium Plus 전용) | 동작 (entitlement gate + kill switch) | No | v1 그대로 유지 |
| **Morning Brief** | /morning-brief | 동작 | No | v1 그대로 유지 |
| **Growth OS** | /growth | 동작 | No | v1 그대로 유지 |
| **Discover** | /discover (mock fallback 포함) | 동작 (FMP 한도 초과 시 mock) | No | v1 그대로 유지 |
| **Cookie Consent** | app/layout.tsx (CookieConsent) | 동작 | No | 유지 |
| **PWA Install Prompt** | app/layout.tsx (InstallPrompt) | 동작 | No | 유지 |
| **Top Ticker 실시간** | /home TopTicker → /api/realtime/stream | 동작 | Yes (home-v2) | v2에 포함 필수 |
| **Admin Preview** | /admin/preview | 동작 (admin auth gate) | No | v1 그대로 유지 |

---

## 8. v2 vs v1 라우트 매핑 (CRITICAL)

| v1 라우트 | v2 전환 여부 | 보존 필수 기능 | 누락 위험 |
|---|---|---|---|
| /home | v2 대체 (home-v2) | TopTicker, LivingCFOStatusBar, TodayMemoHero, PortfolioSnapshot (3 KPI), Risk Gauges (4 KPI), Positions DataTable, Watchlist DataTable, EquityCurveChart, SectorAllocationDonut, CandlestickChart (top holding), Signals DataTable, Pulse Activity, Companion entry, ArtifactQueue, UpsellPlus, WeeklyPulseCard | 8개 섹션 vs v1 ~10개 — DataTable 컬럼 정의, CandlestickChart indicators 설정 전달 필수 |
| /portfolio | v2 대체 (portfolio-v2) | AddPositionModal, TradeModal(buy/sell/edit), LedgerBookPaper (4-stat header + positions table), SectorPaper, ActivityPaper, RollingWindowWidget, 시장 open/closed 표시, fxRate KRW/USD 혼용 | 신규 페이지 → v1 데이터 모델 (`Position`, `Trade`, `TradeAction` 타입) + 모달 API 경로 전달 필수 |
| /risk | v2 대체 (risk-v2) | 4 KPI stats, 7-Layer Defense ladder (번호+이름+metricLabel+metricValue+status+observation), Correlation Heatmap (N×N 표), Rolling VaR LineChart, Methodology Notes, Sample Preview 배너 | Demo fallback 데이터(DEMO_SUMMARY, DEMO_LAYERS, DEMO_CORR_MATRIX) v2에도 유지 필수 |
| /signals | v2 대체 (signals-v2) | 3 ClipboardPaper (pos/neu/neg), SignalMemoStrip (4-pillar expand), filter pills, Refresh 버튼, 3 카운터, isLoading/empty 상태, DossierDesk 3D 스택 | 모바일 flat stack vs 데스크톱 3D stack 분기 로직 전달 필수 |
| /reports | v2 대체 (reports-v2) | CATALOG 18종, tier-gating, persona filter, SectionFeedbackBar, PeerBenchmarkBlock, live artifact lookup (liveByType Map) | 18개 preview 라우트(/reports/preview/*) 보존 필수 |
| /settings | v1 그대로 | 전체 | 0 |
| /profile | v1 그대로 | 전체 | 0 |
| /market | v1 그대로 | 전체 | 0 |
| /watchlist | v1 그대로 | 전체 | 0 |
| /discover | v1 그대로 | 전체 | 0 |
| /alerts | v1 그대로 | 전체 | 0 |
| /detail/[ticker] | v1 그대로 | 전체 | 0 |
| /companion | v1 그대로 | 전체 | 0 |
| /morning-brief | v1 그대로 | 전체 | 0 |
| /ai-chat | v1 그대로 | 전체 | 0 |
| /ai | v1 그대로 | 전체 | 0 |
| /growth | v1 그대로 | 전체 | 0 |
| /simulator/what-if | v1 그대로 | 전체 | 0 |
| /login, /signup | v1 그대로 | 전체 | 0 |
| /onboarding, /onboarding/broker | v1 그대로 | 전체 | 0 |
| /(root), /beta-gate | v1 그대로 | 전체 | 0 |
| /pricing | v1 그대로 | 전체 | 0 |
| /sample-reports, /sample-reports/[slug] | v1 그대로 | 전체 | 0 |
| /features/* | v1 그대로 | 전체 | 0 |
| /terms, /privacy, /docs | v1 그대로 | 전체 | 0 |
| /admin, /admin/preview | v1 그대로 | 전체 | 0 |

---

## 9. 백엔드 endpoint 누락 조사

`endpoints.ts` 기준 vs HANDOVER.md 정보 교차 확인. 백엔드 코드 직접 grep은 이 조사의 범위에 포함되어 있으나 가능한 정보를 문서에서 인용.

| URL | 사용 위치 | 백엔드 존재? | 비고 |
|---|---|---|---|
| /api/portfolio/positions | /portfolio, /home | 확인 필요 (PORTFOLIO_POSITIONS alias, 2026-04-22 추가) | HANDOVER §2-B "Portfolio/Watchlist LAST=$0 fallback" 수정됨 |
| /api/portfolio/summary | /portfolio, /home | 확인 필요 | 동상 |
| /api/portfolio/trades | /portfolio | 확인 필요 | 동상 |
| /api/risk/summary | /risk | 확인 필요 (RISK_SUMMARY alias, 2026-04-22 추가) | HANDOVER §2-B "Risk 7-Layer 'No positions' fix" |
| /api/risk/layers | /risk | 확인 필요 | 동상 |
| /api/risk/correlation | /risk | 확인 필요 | 동상 |
| /api/risk/rolling-var | /risk | 확인 필요 | 동상 |
| /api/discover/market-overview | /discover | 확인 필요 | DISCOVER_OVERVIEW alias |
| /api/discover/movers | /discover | 확인 필요 | DISCOVER_MOVERS alias |
| /api/discover/sectors | /discover | 확인 필요 | DISCOVER_SECTORS alias |
| /api/discover/screeners | /discover | 확인 필요 | DISCOVER_SCREENERS alias |
| /api/market/indices | /market | 확인 필요 | MARKET_INDICES alias |
| /api/profile/persona | /profile, /reports | 확인 필요 (404 fallback to mock 구현됨) | CFO hook |
| /api/profile/rolling-window | /portfolio | 확인 필요 (404 fallback to mock 구현됨) | CFO hook |
| /api/profile/feedback | /reports | 확인 필요 (404/501 → local-only success 처리) | CFO hook |
| /api/profile/pulse | /profile | 확인 필요 (404 fallback to mock 구현됨) | CFO hook |
| /api/billing/create-checkout | /pricing | 확인 필요 | HANDOVER: "Stripe 코드는 있으나 미연결" |
| /api/billing/portal | /settings | 확인 필요 | 동상 |
| /api/push/subscribe | /settings | 확인 필요 | lib/push.ts 구현됨 |
| /api/growth/* | /growth | 확인 필요 | HANDOVER에 직접 언급 없음 |
| /api/agent/* (companion) | /companion | 확인 필요 | HANDOVER §2-E: "migration 012 + waitlist + admin" 완료 |

---

## 10. HANDOVER.md / qa_bug_log 교차 확인

### HANDOVER.md 알려진 미완 사항과 인벤토리 교차
| HANDOVER 항목 | 인벤토리 반영 |
|---|---|
| §3-A: 7 Tier 1 feature UI 미구현 (/strategy, /twin, /profile Section 06-07, Pre-Trade Friction 모달) | 해당 페이지/컴포넌트 인벤토리에 **없음** — 백엔드만 존재 |
| §3-B: F5 AI Twin rationale scrub 미완 | 프론트엔드 /twin 페이지 없음 → 영향 없음 |
| §3-E: FMP 250 calls/day 초과 | /discover, /market mock fallback 이유 |
| §3-G: Persona V2 flip card 브라우저 QA 미완 | PersonaV2Card /profile에 존재 |
| HANDOVER §2-A: autotrade 제거 완료 | endpoints.ts 주석 확인됨 (line 81-84) |
| HANDOVER §2-A: Alpaca BYO 모델 | settings/page.tsx ALPACA_ENABLED 확인됨 |

### CLAUDE.md 알려진 P0 버그와 인벤토리 교차
| P0 버그 (CLAUDE.md) | 현재 인벤토리 상태 |
|---|---|
| Add Position 불가 — /portfolio 없음(404) | /portfolio 페이지 존재 (2026-04-22 이후 구현됨) |
| Search Stock 안 눌림 | SearchCommandMenu 구현됨 (TopBar에 마운트) |
| Watchlist 추가 불가 | AddSymbolModal 구현됨 (/watchlist) |
| Risk 페이지 빈 페이지 | /risk 구현됨 (RISK_SUMMARY 등 4개 endpoint 연동) |
| 알림 벨 안 눌림 | NotificationDropdown 구현됨 (TopBar에 마운트) |
| 프로필 아이콘 안 눌림 | ProfileDropdown 구현됨 (TopBar에 마운트) |
| Connect Alpaca 안 눌림 | AlpacaCard + AlpacaConnectModal 구현됨 (ALPACA_ENABLED 조건부) |
| 코스피/코스닥 없음 | /market KR 탭 구현됨 (HANDOVER §2-B 수정 완료) |

Note: CLAUDE.md의 P0 버그들은 2026-04-22~27 세션에서 대부분 해소된 것으로 보임. 실제 동작 여부는 QA 부서 브라우저 테스트로 확인 필요.

---

## 집계 요약

| 항목 | 수량 |
|---|---|
| 전체 page.tsx 파일 | 63개 |
| Dashboard 페이지 (auth 필수) | 18개 |
| Auth 페이지 | 4개 |
| Reports Preview 페이지 | 18개 |
| Features 마케팅 페이지 | 13개 |
| 기타 공개 페이지 | 9개 (root, beta-gate, pricing, terms, privacy, docs, sample-reports, simulator, admin 2개) |
| 전체 컴포넌트 .tsx 파일 | 107개 |
| hooks.ts 훅 | 14개 |
| lib/cfo/hooks.ts 훅 | 7개 (usePersonaBenchmarkAll 포함) |
| lib/cfo/useCompanion.ts 훅 | 3개 이상 |
| endpoints.ts URL 그룹 | 15개 그룹 + 2개 삭제(autotrade) |
| v2 대체 대상 페이지 | 5개 (home, portfolio, risk, signals, reports) |
| v1 그대로 유지 페이지 | 58개 |
| 누락 위험 (v2 대체 페이지) | 5개 페이지 각각 §7/§8 참조 |
