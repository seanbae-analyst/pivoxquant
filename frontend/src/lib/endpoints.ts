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
    deleteAccount: "/api/auth/delete-account",
  },
  portfolio: {
    list: "/api/portfolio",
    analytics: "/api/portfolio/analytics",
    history: (period: string) => `/api/portfolio/history?period=${period}`,
    addPosition: "/api/portfolio/position",
    editPosition: (id: number) => `/api/portfolio/position/${id}`,
    deletePosition: (id: number) => `/api/portfolio/position/${id}`,
    buyMore: (id: number) => `/api/portfolio/position/${id}/buy`,
    sellShares: (id: number) => `/api/portfolio/position/${id}/sell`,
    buyNew: "/api/portfolio/position/buy-new",
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
    morningBrief: "/api/morning-brief",
    morningBriefToday: "/api/brief/today",
    morningBriefArchive: "/api/brief/archive",
    search: (query: string) => `/api/search?q=${encodeURIComponent(query)}`,
    lookup: (ticker: string) => `/api/lookup/${ticker}`,
    prices: "/api/prices",
    chart: (ticker: string) => `/api/chart/${ticker}`,
    earnings: "/api/earnings",
    peers: (ticker: string) => `/api/peers/${ticker}`,
    profile: (ticker: string) => `/api/profile/${ticker}`,
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
  },
  trades: "/api/trades",
  autotrade: {
    status: "/api/autotrade/status",
    start: "/api/autotrade/start",
    stop: "/api/autotrade/stop",
    sellAll: "/api/autotrade/sell-all",
    pending: "/api/autotrade/pending",
    approve: (tradeId: string) => `/api/autotrade/approve/${tradeId}`,
    reject: (tradeId: string) => `/api/autotrade/reject/${tradeId}`,
  },
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
    sync: "/api/broker/sync",
    syncKis: "/api/broker/sync-kis",
    syncStatus: "/api/broker/sync-status",
    connections: "/api/broker/connections",
  },
  share: {
    create: "/api/portfolio/share",
    get: (token: string) => `/api/portfolio/share/${token}`,
  },
} as const;
