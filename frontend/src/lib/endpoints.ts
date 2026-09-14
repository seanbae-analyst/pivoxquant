/**
 * API endpoint constants — single source of truth for all backend URLs.
 * Replaces magic strings throughout the frontend.
 */
export const API = {
  auth: {
    register: "/api/auth/register",
    login: "/api/auth/login",
    logout: "/api/auth/logout",
    me: "/api/auth/me",
    google: "/api/auth/google",
    kakao: "/api/auth/kakao",
    /**
     * PIPA §22 ⑥ — birthdate interstitial.
     * Hit by the ``/signup/oauth-finalize`` page after the OAuth callback
     * redirects new (and legacy NULL-birthdate) users there. Body =
     * ``{ birthdate: "yyyy-mm-dd" }``. Errors return one of the i18n codes
     * defined in ``services/age_verification.py``:
     *   birthdate_required / birthdate_invalid_format /
     *   birthdate_unrealistic / below_min_age / birthdate_already_set
     */
    oauthFinalize: "/api/auth/oauth-finalize",
    deleteAccount: "/api/auth/delete-account",
    // PIPA §21 30-day soft-delete request (default deletion path — sets
    // deletion_requested_at, logs out, emails a self-service cancel link).
    deleteRequest: "/api/auth/delete-request",
    // Token-authenticated cancel of the 30-day request (no session — the
    // emailed HMAC token is the credential). Hit by /delete-cancel page.
    deleteCancel: "/api/auth/delete-cancel",
  },
  portfolio: {
    list: "/api/portfolio",
    history: (period: string) => `/api/portfolio/history?period=${period}`,
    // Singular `/position` endpoints (addPosition / editPosition / deletePosition /
    // buyMore / sellShares / buyNew) were removed 2026-05-02 — the frontend uses
    // the plural `/api/portfolio/positions[/<id>]` aliases (see PORTFOLIO_POSITIONS
    // and add-position-modal-v2.tsx). Backend handlers remain for back-compat
    // but emit a Deprecation header and warning log on every call.
    //
    // 2026-05-17: `capital: "/api/portfolio/capital"` removed. The constant had
    // zero call sites in frontend/src — `update_capital` is wired through
    // `API.profile.capital` ("/api/profile/capital", PUT) instead. The backend
    // PUT /api/portfolio/capital handler is still live (test_security.py +
    // test_portfolio.py exercise it); deleting only the unused frontend slot.
  },
  market: {
    // 2026-09-01 — 14개 죽은 라우트를 백엔드에서 제거하면서 함께 정리했다.
    // overview / status / macro / sectors / lookup / prices / chart /
    // earnings / earningsByTicker / peers / profile / dividend / news 는
    // 8-31 prune 으로 사라진 디스커버·마켓 화면의 잔재였고, 정의만 남아
    // FMP 를 가장 많이 쓰는 엔드포인트들을 살아있는 것처럼 보이게 했다.
    fx: "/api/market/fx",
    search: (query: string) => `/api/search?q=${encodeURIComponent(query)}`,
  },
  alerts: {
    list: "/api/alerts",
    read: "/api/alerts/read",
    clear: "/api/alerts/clear",
    priceCheck: "/api/alerts/price-check",
    // Bell-dropdown endpoints (added 2026-04-22)
    unreadCount: "/api/alerts/unread-count",
    readAll: "/api/alerts/read-all",
    itemRead: (id: string | number) => `/api/alerts/${id}/read`,
    itemDelete: (id: string | number) => `/api/alerts/${id}`,
  },
  // 2026-09-01 — removed four constants whose backend routes do not exist:
  //   portfolio.analytics · discover · watchlist.{list,add,remove,update} · backtest
  // Each was checked against the live Flask url_map and had ZERO callers in
  // src/ (the `useWatchlist` hook that read watchlist.list was itself never
  // called). They were traps: wiring a feature to one would 404 silently.
  // NOT removed, and deliberately so — `broker.*` also 404s, but it is gated
  // off behind BROKER_LINKING_AVAILABLE=false with a documented reason (KIS
  // partnership / Toss terms), so nothing fires the request.
  //
  // `admin.artifacts*` used to be listed here on the same grounds ("the admin
  // pages treat 401/403/404 as render blank"). That reasoning was the bug:
  // admin/layout probed artifactsList to decide who was an admin, so the 404
  // denied everyone including the owner. Removed 2026-09-07 (e1dc8e64) once
  // the gate moved to a live endpoint.
  trades: "/api/trades",
  realtime: {
    // 2026-05-17 — Wave F-2 Bug #5: `/api/realtime/stream` removed.
    // Had zero frontend consumers yet still shared the per-user SSE
    // slot counter (`_MAX_SSE_PER_USER=3`) with `/portfolio-stream`,
    // creating a cheap slot-exhaustion DoS surface. Backend now
    // returns 410 Gone. Restore path:
    //   1. add a real frontend consumer (otherwise: dead code)
    //   2. revert backend stub in routes/realtime.py
    //   3. restore this slot here
    portfolioStream: "/api/realtime/portfolio-stream",
    price: (ticker: string) => `/api/realtime/price/${ticker}`,
    status: "/api/realtime/status",
  },
  profile: {
    get: "/api/profile",
    onboarding: "/api/profile/onboarding",
    // 2026-05-17 wave 12 UX P0 — onboarding partial-save (device handoff).
    // GET returns {draft: {...} | null}; PUT accepts {answers: {...}}.
    // The wizard PUTs every few questions so progress survives ITP / device
    // switch / private browsing without relying on localStorage alone.
    onboardingDraft: "/api/profile/onboarding/draft",
    update: "/api/profile",
    questionnaire: "/api/profile/questionnaire",
    capital: "/api/profile/capital",
    // PIPA §35 self-service data export (routes/profile.py::export_profile).
    //   - `export`     → full personal-data record as JSON (instant download).
    //   - `exportCsv`  → single tabular dataset as CSV. dataset ∈
    //                    trades | positions | watchlist (raw stored fields) |
    //                    capital_gains | capital_gains_summary (해외주식
    //                    양도소득세 — FIFO realised P&L + trade-date FX,
    //                    참고용 추정; KRW blank when FX unavailable, never
    //                    fabricated) | journal | pulse (본인 기록 free-text).
    export: "/api/profile/export",
    exportCsv: (
      dataset:
        | "trades"
        | "positions"
        | "watchlist"
        | "capital_gains"
        | "capital_gains_summary"
        | "journal"
        | "pulse",
    ) => `/api/profile/export?format=csv&dataset=${dataset}`,
    //   - `exportXlsx` → ALL tabular datasets as ONE multi-sheet .xlsx
    //                    workbook (one sheet per dataset), or a single dataset
    //                    when one is passed. Same raw-fact columns as CSV;
    //                    opens directly in Excel / Numbers / Google Sheets.
    exportXlsx: (
      dataset?:
        | "trades"
        | "positions"
        | "watchlist"
        | "capital_gains"
        | "capital_gains_summary"
        | "journal"
        | "pulse",
    ) =>
      dataset
        ? `/api/profile/export?format=xlsx&dataset=${dataset}`
        : `/api/profile/export?format=xlsx`,
    // Email opt-out preferences (정통망법 §50). Backend: PATCH
    // routes/profile.py::patch_email_preferences. Body accepts either
    // or both of `email_opt_out` (global) and `email_opt_out_earnings`
    // (per-channel) as booleans. Returns committed values.
    emailPreferences: "/api/profile/email-preferences",
    // Persona v2 — 9-dim classifier surface (backend: routes/profile.py).
    // See `frontend/src/lib/cfo/hooks.ts` for response shapes.
    personaDetail: (windowDays: number = 90) =>
      `/api/profile/persona-detail?window_days=${windowDays}`,
    personaExplain: "/api/profile/persona-explain",
    personaBenchmark: (windowDays: 30 | 90 | 365 = 90) =>
      `/api/profile/persona-benchmark?window=${windowDays}`,
    personaBenchmarkAll: (windowDays: 30 | 90 | 365 = 90) =>
      `/api/profile/persona-benchmark-all?window=${windowDays}`,
    // ── Living-mirror reads consumed by lib/cfo/hooks.ts ──────────────────
    // Added 2026-09-06. These five were called with hardcoded path literals
    // for as long as they existed, which quietly made this file an INCOMPLETE
    // source of truth: the 2026-09-01 audit that walked every constant here
    // against the backend url_map could not see them, and the two dead routes
    // found on 2026-09-02 (`/api/agent/delete`, `/api/portfolio/reconcile`)
    // were both outside it. A path that is not here is a path nothing audits.
    persona: "/api/profile/persona",
    rollingWindow: "/api/profile/rolling-window",
    // GET returns the vote history; POST records one artifact vote.
    feedback: "/api/profile/feedback",
    // GET pulse history; POST appends one weekly entry.
    pulse: "/api/profile/pulse",
    // PATCH persists the ko/en choice server-side so it survives a device
    // change (the `sp_locale` cookie only covers this browser).
    locale: "/api/profile/locale",
  },
  billing: {
    createCheckout: "/api/billing/create-checkout",
    subscription: "/api/billing/subscription",
    portal: "/api/billing/portal",
  },
  push: {
    subscribe: "/api/push/subscribe",
    unsubscribe: "/api/push/unsubscribe",
    status: "/api/push/status",
  },
  // Per-event-type × per-channel notification matrix (settings v2 §C).
  // Backend (2026-05-21) persists the 7-event × 3-channel toggle grid that
  // the <NotificationsMatrix /> previously kept only in a localStorage shadow
  // (GAP-E). Locked contract:
  //   GET  → { prefs: { "<event_id>": { email, push, inapp }, ... } }  (server
  //          always returns all 7 events with defaults merged)
  //   PUT  body { prefs: {...} } → 200 { prefs: {...} } | 400 (validation)
  notifications: {
    preferences: "/api/notifications/preferences",
  },
  broker: {
    connections: "/api/broker/connections",
    // KIS (한국투자증권) — read-only Korean brokerage.
    kisConnect: "/api/broker/kis/connect",
    kisSync: "/api/broker/kis/sync",
    kisDisconnect: "/api/broker/kis/disconnect",
    kisStatus: "/api/broker/kis/status",
  },
  // `admin.artifacts*` (list / preview / download) removed 2026-09-07. The
  // 2026-08-31 prune deleted every artifact route — the backend url_map has
  // matched /artifact/ ZERO times since. They survived because admin/layout
  // used artifactsList as its allow-list probe, which is precisely what broke
  // the gate: a 404 probe reads as "not an admin" and denied everyone. The
  // gate now gets its answer from `support.adminInquiries`, so these three
  // have no consumers left (verified by symbol, not by path string).
  // Behaviour Mirror — factual holding-period statistics from the user's own
  // closed trade pairs (disposition-effect "mirror"). Read-only, @api_auth.
  // Renders as a neutral 2-up comparison on the /journal page; NEVER a score,
  // grade, or "bias" label (자본시장법 / PIPA §23 posture). Response shape is
  // HoldingMirrorResponse in lib/types.ts — backend contract locked 1:1.
  behavior: {
    holdingMirror: "/api/behavior/holding-mirror",
    // Concentration Mirror — factual cost-basis composition of the user's own
    // open positions (largest holding's share of the portfolio). Read-only,
    // @api_auth. Renders as a neutral fact sentence beneath the disposition
    // mirror on /journal; NEVER a score, grade, or "과집중/위험" label
    // (자본시장법 / PIPA §23). Response = ConcentrationMirrorResponse, 1:1.
    concentrationMirror: "/api/behavior/concentration-mirror",
    // Friction Outcome — what the *pause* actually led to: how the started
    // records resolved (proceeded / cancelled / open), whether cancellations
    // persisted or were merely delayed, and the two realised-return
    // distributions side by side. Read-only, @api_auth.
    //
    // ⚠️ The response carries `caveats` and `realised.comparable`. Those are
    // NOT decoration — the comparison is not randomised (the user chooses
    // which trades to pause), and the service REFUSES the comparison below
    // `min_group_n`. Any UI reading this must surface them; dropping them
    // turns an honest observation into an implied causal claim
    // (자본시장법 / DECISIONS.md AI 점수화 폐기).
    frictionOutcome: "/api/behavior/friction-outcome",
    // Profit/Loss Mirror — factual hold-day + return statistics split by
    // whether the user's own closed pairs realised a profit or a loss.
    // Read-only, @api_auth. Renders as a neutral 2-up beneath the other
    // mirrors on /journal; NEVER a score, grade, or "처분효과/편향" label
    // (자본시장법 / PIPA §23). Response = ProfitLossMirrorResponse, 1:1.
    profitLossMirror: "/api/behavior/profit-loss-mirror",
    // Turnover Mirror — factual trade-activity: BUY/SELL fill counts +
    // per-currency gross traded value (NO ratio/percentage — a turnover
    // ratio needs a live valuation denominator + meaningless across FX).
    // Read-only, @api_auth. Renders as a neutral panel beneath the other
    // mirrors on /journal; NEVER a score, grade, or "회전율/과잉거래" label
    // (자본시장법 / PIPA §23). Response = TurnoverMirrorResponse, 1:1.
    turnoverMirror: "/api/behavior/turnover-mirror",
    // Averaging-Down Mirror — factual counts of follow-on buys (adds to an
    // already-held position) that landed below / above / at the position's
    // running average cost. NO ratio/score — integer counts only; same-ticker
    // price comparison so no live price/FX. Read-only, @api_auth. Renders as a
    // neutral panel beneath the other mirrors on /journal; NEVER a score,
    // grade, or "물타기" judgement (자본시장법 / PIPA §23).
    // Response = AveragingDownMirrorResponse, 1:1.
    averagingDownMirror: "/api/behavior/averaging-down-mirror",
  },
  // Mirror home (거울) — single composed read: 선언 vs 관찰 persona shape, the
  // top diverging behavioural dimensions, the drift descriptor, and the latest
  // AI-twin weekly paper-vs-user report. Read-only, @api_auth. Composes the
  // existing persona/twin services (routes/mirror_home.py). NEVER surfaces an
  // 8-code persona — only 성장형/균형형/수익형 + neutral dimension labels.
  mirror: {
    home: "/api/mirror-home",
  },
  // Pre-Trade Friction (Feature 6) — self-imposed cooldown + reflection.
  // Backend never places an order; /proceed only stamps "user finished
  // thinking". See routes/pre_trade.py and services/pre_trade/friction.py.
  preTrade: {
    start: "/api/pre-trade/start",
    status: (id: number) => `/api/pre-trade/${id}`,
    proceed: (id: number) => `/api/pre-trade/${id}/proceed`,
    cancel: (id: number) => `/api/pre-trade/${id}/cancel`,
    // 2026-06-02: Storage-proof trust artifact — returns the caller's OWN
    // rationale in BOTH plaintext and the exact ciphertext stored at rest, so
    // the user *witnesses* encryption instead of reading a claim. @api_auth.
    storageProof: (id: number) => `/api/pre-trade/${id}/storage-proof`,
    // 2026-05-21: Journal feed — the user's own pre-trade reflections in
    // reverse-chronological order (newest first). Read-only, @api_auth.
    // Each row is "user finished thinking" — never an executed order.
    list: "/api/pre-trade/list",
  },
  // Marketing-consent record (정통망법 §50 ① — sender bears the burden of
  // proving prior opt-in). Backend lives in routes/consents.py (PR #73).
  // - GET    : returns { opted_in, marketing_consent_at, marketing_consent_revoked_at }
  // - POST   : record explicit opt-in (clears prior revocation, flips email_opt_out=false)
  // - DELETE : record revocation (sets email_opt_out=true)
  consents: {
    marketing: "/api/consents/marketing",
    crossBorder: "/api/consents/cross-border",
  },
  // Import Inbox (2026-09-13, docs/product/IMPORT_INBOX_DESIGN.md §API).
  // The server receives only what the user uploads — a CSV/XLSX file or
  // pasted fill-notification text — and parks parsed rows in pending_trades.
  // Nothing reaches trade_history/positions until the user approves a row
  // with a thesis. No broker keys, no images, no AI on the server.
  //   create      POST multipart {file, consent=true} | JSON {text, source, consent}
  //   pending     GET  → {pending[], count}
  //   pendingItem PATCH {ticker?, name?, action?, shares?, price?, traded_at?}
  //   approve     POST {thesis} (3~500자) → {ok, pending, trade_id, position_id}
  //   reject      POST → {ok}
  imports: {
    create: "/api/portfolio/imports",
    pending: "/api/portfolio/imports/pending",
    pendingItem: (id: number) => `/api/portfolio/imports/pending/${id}`,
    approve: (id: number) => `/api/portfolio/imports/pending/${id}/approve`,
    reject: (id: number) => `/api/portfolio/imports/pending/${id}/reject`,
    // Phase 2 v3-A — personal access tokens (IMPORT_INBOX_DESIGN.md §Phase 2).
    //   tokens   GET → {tokens[], active_limit} · POST {name, consent:true} → 201 {…, token} (raw token appears here only)
    //   token    DELETE → {ok} (revoke, idempotent)
    //   webhook  display-only path: POST + `Authorization: Bearer pvx_…` + {"text": "…"}
    tokens: "/api/portfolio/imports/tokens",
    token: (id: number) => `/api/portfolio/imports/tokens/${id}`,
    webhook: "/api/portfolio/imports/webhook",
  },
  support: {
    inquiries: "/api/support/inquiries",
    inquiry: (id: string | number) => `/api/support/inquiries/${id}`,
    // Admin slots — blueprint url_prefix is `/api/support`, so the admin
    // handlers live under `/api/support/admin/...` (NOT `/api/admin/support`).
    // Consumed by the operator console at /admin/support.
    adminInquiries: "/api/support/admin/inquiries",
    adminReply: (id: string | number) => `/api/support/admin/inquiries/${id}/reply`,
  },
} as const;

// Portfolio (added 2026-04-22) — frontend-shape aliases for the new /portfolio page.
// Existing `API.portfolio.*` entries above remain authoritative for legacy callers.
export const PORTFOLIO_POSITIONS = "/api/portfolio/positions";
export const PORTFOLIO_SUMMARY = "/api/portfolio/summary";
export const PORTFOLIO_TRADES = "/api/portfolio/trades";

// Watchlist + Search (added 2026-04-22) — spec-matched aliases used by the
// new watchlist page and the Cmd+K command palette. `API.watchlist.*` above
// remains authoritative for existing callers; these are path-only shortcuts.
const API_BASE = "";
export const SEARCH = `${API_BASE}/api/search`;

// Risk + Discover + Market (added 2026-04-22) — observation endpoints wired to
// the new risk/discover/market pages. Existing API.* namespace untouched.
export const RISK_SUMMARY       = `${API_BASE}/api/risk/summary`;
export const RISK_LAYERS        = `${API_BASE}/api/risk/layers`;
export const RISK_CORRELATION   = `${API_BASE}/api/risk/correlation`;
export const RISK_ROLLING_VAR   = `${API_BASE}/api/risk/rolling-var`;

// Public (no-auth) cache-only market snapshot — backs the landing-page
// MarketTicker. Rate-limited, cache-only, always HTTP 200. No session
// cookie required. See routes/public.py::market_snapshot.
export const PUBLIC_MARKET_SNAPSHOT = `${API_BASE}/api/public/market-snapshot`;

// Public stale-data status — backs the in-app <DataStaleBanner /> mounted in
// the (dashboard) layout. Polled every 5 min via SWR. See
// routes/data_status.py for the locked response contract. Wave G C-CS3.
export const DATA_STALE_STATUS = `${API_BASE}/api/data/stale-status`;


// NPS 1-click feedback — backs <NpsWidget /> rendered after the first
// Weekly Memo. Transactional (§50 서비스 개선); no consent required.
// Body: { score: 1-10, weekly_memo_id?: string }. Wave G C-AC2.
export const FEEDBACK_NPS = `${API_BASE}/api/feedback/nps`;
