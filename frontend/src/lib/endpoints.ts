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
    analytics: "/api/portfolio/analytics",
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
  signals: {
    all: "/api/signals",
    one: (ticker: string) => `/api/signals/${ticker}`,
    refresh: "/api/signals/refresh",
    scan: "/api/scan",
    shortInterest: (ticker: string) => `/api/signals/short-interest/${ticker}`,
    insider: (ticker: string) => `/api/signals/insider/${ticker}`,
    disposition: (ticker: string) => `/api/signals/disposition/${ticker}`,
    ofi: (ticker: string) => `/api/signals/ofi/${ticker}`,
    sentimentDivergence: (ticker: string) => `/api/signals/sentiment-divergence/${ticker}`,
    anchoring: (ticker: string) => `/api/signals/anchoring/${ticker}`,
    herding: "/api/signals/herding",
  },
  discover: "/api/discover",
  market: {
    overview: "/api/market/overview",
    status: "/api/market/status",
    fx: "/api/market/fx",
    macro: "/api/macro",
    sectors: "/api/sectors",
    search: (query: string) => `/api/search?q=${encodeURIComponent(query)}`,
    lookup: (ticker: string) => `/api/lookup/${ticker}`,
    prices: "/api/prices",
    chart: (ticker: string) => `/api/chart/${ticker}`,
    earnings: "/api/earnings",
    // Per-ticker earnings (gated to user holdings+watchlist, §101-safe).
    // Returns the SAME item shape as the /api/earnings list items.
    earningsByTicker: (ticker: string) =>
      `/api/earnings/${encodeURIComponent(ticker)}`,
    peers: (ticker: string) => `/api/peers/${ticker}`,
    profile: (ticker: string) => `/api/market/profile/${ticker}`,
    dividend: (ticker: string) => `/api/dividend/${ticker}`,
    news: (ticker: string) => `/api/news/${ticker}`,
  },
  daytrade: {
    status: "/api/daytrade/status",
    scan: "/api/daytrade/scan",
    analyze: (ticker: string) => `/api/daytrade/analyze/${ticker}`,
    chart: (ticker: string) => `/api/daytrade/chart/${ticker}`,
    prices: "/api/daytrade/prices",
    stream: "/api/daytrade/stream",
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
  trades: "/api/trades",
  // REMOVED 2026-04-27 per CEO + legal: autotrade endpoints group retired
  // (투자일임업 등록 회피 — feature 자체 제거). Restore path:
  // 1) re-enable backend blueprint in routes/__init__.py and app.py
  // 2) restore this group + frontend page/nav/i18n.
  ai: {
    status: "/api/ai/status",
    chat: "/api/ai/chat",
    swot: "/api/ai/swot",
    competitor: "/api/ai/competitor",
    sectorTrend: "/api/ai/sector-trend",
    commentary: "/api/ai/commentary",
    morningSummary: "/api/ai/morning-summary",
    coaching: "/api/ai/coaching",
    earningsTone: "/api/ai/earnings-tone",
    sectorRegime: "/api/ai/sector-regime",
    riskSummary: "/api/ai/risk-summary",
  },
  watchlist: {
    list: "/api/watchlist",
    add: "/api/watchlist",
    remove: (id: number) => `/api/watchlist/${id}`,
    update: (id: number) => `/api/watchlist/${id}`,
  },
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
  backtest: (ticker: string) => `/api/backtest/${ticker}`,
  quant: {
    vixStrategy: "/api/vix-strategy",
    crossAsset: "/api/cross-asset",
    statArb: "/api/stat-arb",
    indicators: (ticker: string) => `/api/indicators/${ticker}`,
    canslim: (ticker: string) => `/api/screener/canslim/${ticker}`,
    interestRateRegime: "/api/regime/interest-rate",
  },
  analytics: {
    regimeReport: "/api/analytics/regime-report",
    benchmark: "/api/analytics/benchmark",
    turnover: "/api/analytics/turnover",
  },
  risk: {
    var: "/api/risk/var",
    drawdown: "/api/risk/drawdown",
    stressTest: "/api/risk/stress-test",
    volatility: (ticker: string) => `/api/risk/volatility/${ticker}`,
    componentEs: "/api/risk/component-es",
    defenseStatus: "/api/risk/defense-status",
  },
  simulate: {
    hrp: "/api/portfolio/simulate/hrp",
    trp: "/api/portfolio/simulate/trp",
    mdp: "/api/portfolio/simulate/mdp",
    erc: "/api/portfolio/simulate/erc",
    minVariance: "/api/portfolio/simulate/min-variance",
    counterfactual: (params: {
      ticker: string;
      start_date: string;
      amount: number;
      currency?: string | null;
      recurring?: string | null;
    }) => {
      const q = new URLSearchParams({
        ticker: params.ticker,
        start_date: params.start_date,
        amount: String(params.amount),
      });
      if (params.currency) q.set("currency", params.currency);
      if (params.recurring) q.set("recurring", params.recurring);
      return `/api/simulate/counterfactual?${q.toString()}`;
    },
  },
  performance: {
    ledger: "/api/performance/ledger",
  },
  tools: {
    positionSizing: "/api/tools/position-sizing",
    correlationMatrix: "/api/tools/correlation-matrix",
    sectorHeatmap: "/api/tools/sector-heatmap",
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
  share: {
    create: "/api/portfolio/share",
    get: (token: string) => `/api/portfolio/share/${token}`,
  },
  growth: {
    data: (range: string) => `/api/growth/data?range=${range}`,
    today: "/api/growth/today",
    reflect: "/api/growth/reflect",
    weekly: "/api/growth/weekly",
  },
  artifacts: {
    list: "/api/artifacts/list",
    download: (id: number) => `/api/artifacts/${id}/download`,
    preview: (id: number) => `/api/artifacts/${id}/preview`,
    markRead: (id: number) => `/api/artifacts/${id}/read`,
    // reports-v2 — additive (Stage 10, 2026-04-27). Backend GAPs.
    // Hooks fall back to client-side derivation from `list` when these 404.
    stats: "/api/artifacts/stats",
    byMonth: "/api/artifacts/by-month",
    generate: "/api/artifacts/generate",
    // Brag Card — instant on-demand preview (snapshot mode supports empty
    // portfolios). Returns { ok, data, png_base64, html }. The `data` payload
    // carries share_token / referral_code / mode / empty_reason /
    // snapshot_tickers used by the onboarding viral surface.
    bragCardPreview: "/api/artifacts/brag-card/preview",
    // Living Mirror — persona capstone PDF (선언 radar → 행동 overlay → drift
    // trajectory). On-demand: POST generate → { ok, id, data }; then
    // download(id) streams the PDF (410 when Railway's ephemeral disk has no
    // rendered file) and preview(id) returns { ok, id, data, html }.
    // Backend: routes/artifacts.py living_mirror_* (LAUNCH_FREE_ALL_TIERS).
    livingMirrorGenerate: "/api/artifacts/living-mirror/generate",
    livingMirrorPreview: (id: number) =>
      `/api/artifacts/living-mirror/preview/${id}`,
    livingMirrorDownload: (id: number) =>
      `/api/artifacts/living-mirror/download/${id}`,
  },
  admin: {
    artifactsList: "/api/admin/artifacts/list",
    artifactPreview: (type: string, format: "html" | "pdf" | "email" | "png") =>
      `/api/admin/artifacts/preview/${type}?format=${format}`,
    artifactDownload: (type: string, format: "html" | "pdf" | "email" | "png") =>
      `/api/admin/artifacts/preview/${type}?format=${format}&download=1`,
  },
  // Personal Journal Companion — Closed Beta (Premium Plus / Founding Lifetime).
  // Reflective-only agent: Remember · Mirror · Question. Not advice.
  // See reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6.
  agent: {
    query: "/api/agent/query",
    status: "/api/agent/status",
    waitlist: "/api/agent/waitlist",
  },
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
  // Customer support — 고객문의센터 + AI 고객지원 챗봇 (2026-05-26).
  // Backend contract (locked, see routes/support.py):
  //   POST   /api/support/inquiries      {category,subject,body}
  //            → 201 {id,status,created_at} | 400/401/429 RATE_LIMITED
  //   GET    /api/support/inquiries      → {inquiries:[...]}
  //   GET    /api/support/inquiries/:id  → {id,category,subject,body,status,
  //            admin_reply,created_at,answered_at,has_reply}
  //   POST   /api/support/chat           {message(1..2000),history?:[...]}
  //            → 200 {reply,escalated,inquiry_id} | 400 INVALID_MESSAGE/401/429
  // Admin slots are declared for parity with routes/support.py admin handlers
  // (no frontend consumer yet — the user-facing pages never call them).
  // Viral loop — funnel telemetry + public OG card landing (backend commit
  // 7a57a9da, routes/growth.py). Contract (locked):
  //   POST /api/track                      (PUBLIC, no auth) → {ok}
  //     body {event, channel?, ref_code?, anon_id?, meta?}
  //     event ∈ landing_view|signup|onboarding_done|artifact_opened|
  //            share_clicked|referral_signup
  //   GET  /api/card/<share_token>         (PUBLIC, OG landing)
  //     200 {ok, owner_display_name, card_image_url, summary_safe,
  //          month_label, referral_code}
  //     404 {code: CARD_NOT_FOUND|INVALID_SHARE_TOKEN} (private/missing same)
  //   POST /api/card/<share_token>/visibility (auth, owner) {is_public}
  viral: {
    track: "/api/track",
    card: (shareToken: string) => `/api/card/${encodeURIComponent(shareToken)}`,
    cardVisibility: (shareToken: string) =>
      `/api/card/${encodeURIComponent(shareToken)}/visibility`,
  },
  support: {
    inquiries: "/api/support/inquiries",
    inquiry: (id: string | number) => `/api/support/inquiries/${id}`,
    chat: "/api/support/chat",
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
export const WATCHLIST = `${API_BASE}/api/watchlist`;
export const WATCHLIST_ITEM = (id: string | number) => `${API_BASE}/api/watchlist/${id}`;
export const SEARCH = `${API_BASE}/api/search`;

// Risk + Discover + Market (added 2026-04-22) — observation endpoints wired to
// the new risk/discover/market pages. Existing API.* namespace untouched.
export const RISK_SUMMARY       = `${API_BASE}/api/risk/summary`;
export const RISK_LAYERS        = `${API_BASE}/api/risk/layers`;
export const RISK_CORRELATION   = `${API_BASE}/api/risk/correlation`;
export const RISK_ROLLING_VAR   = `${API_BASE}/api/risk/rolling-var`;
export const RISK_CONCENTRATION = `${API_BASE}/api/risk/concentration`;
export const DISCOVER_OVERVIEW  = `${API_BASE}/api/discover/market-overview`;
export const DISCOVER_MOVERS    = `${API_BASE}/api/discover/movers`;
export const DISCOVER_SECTORS   = `${API_BASE}/api/discover/sectors`;
export const DISCOVER_SCREENERS = `${API_BASE}/api/discover/screeners`;
export const MARKET_INDICES     = `${API_BASE}/api/market/indices`;

// Public (no-auth) cache-only market snapshot — backs the landing-page
// MarketTicker. Rate-limited, cache-only, always HTTP 200. No session
// cookie required. See routes/public.py::market_snapshot.
export const PUBLIC_MARKET_SNAPSHOT = `${API_BASE}/api/public/market-snapshot`;

// Public stale-data status — backs the in-app <DataStaleBanner /> mounted in
// the (dashboard) layout. Polled every 5 min via SWR. See
// routes/data_status.py for the locked response contract. Wave G C-CS3.
export const DATA_STALE_STATUS = `${API_BASE}/api/data/stale-status`;

// Methodology + data-provenance disclosure — backs /methodology (Data-trust
// Stage 1). Flag-gated behind login by default (METHODOLOGY_PUBLIC; Q-DT4) —
// static model catalog + system data lineage from routes/methodology.py.
// See docs/strategy/DATA_TRUST_STRATEGY.md.
export const METHODOLOGY = `${API_BASE}/api/methodology`;

// NPS 1-click feedback — backs <NpsWidget /> rendered after the first
// Weekly Memo. Transactional (§50 서비스 개선); no consent required.
// Body: { score: 1-10, weekly_memo_id?: string }. Wave G C-AC2.
export const FEEDBACK_NPS = `${API_BASE}/api/feedback/nps`;
