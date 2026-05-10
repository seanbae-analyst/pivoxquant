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
    capital: "/api/portfolio/capital",
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
    stream: "/api/realtime/stream",
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
    update: "/api/profile",
    questionnaire: "/api/profile/questionnaire",
    capital: "/api/profile/capital",
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
  broker: {
    connections: "/api/broker/connections",
    // KIS (한국투자증권) — read-only Korean brokerage.
    kisConnect: "/api/broker/kis/connect",
    kisSync: "/api/broker/kis/sync",
    kisDisconnect: "/api/broker/kis/disconnect",
    kisStatus: "/api/broker/kis/status",
    // Alpaca (US equity, paper-only; re-added 2026-04-22).
    // Live trading is disabled; backend rejects env="live".
    alpacaConnect: "/api/broker/alpaca/connect",
    alpacaSync: "/api/broker/alpaca/sync",
    alpacaDisconnect: "/api/broker/alpaca/disconnect",
    alpacaStatus: "/api/broker/alpaca/status",
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
  // Pre-Trade Friction (Feature 6) — self-imposed cooldown + reflection.
  // Backend never places an order; /proceed only stamps "user finished
  // thinking". See routes/pre_trade.py and services/pre_trade/friction.py.
  preTrade: {
    start: "/api/pre-trade/start",
    status: (id: number) => `/api/pre-trade/${id}`,
    proceed: (id: number) => `/api/pre-trade/${id}/proceed`,
    cancel: (id: number) => `/api/pre-trade/${id}/cancel`,
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
