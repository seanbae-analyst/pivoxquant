/**
 * Frontend DEMO mode — portfolio / LinkedIn showcase (2026-06-18 pivot).
 *
 * When NEXT_PUBLIC_DEMO_MODE === "1" the whole app runs with NO backend and NO
 * login: `apiFetch` (lib/api.ts) short-circuits every request to canned data,
 * and the AuthProvider (lib/auth.tsx) injects a fixed demo user so the
 * (dashboard) layout's auth guard never redirects.
 *
 * This is additive + flag-gated — the real auth/data path is untouched when the
 * flag is off ("기존 기능 100% 보존"). No auto-login endpoint, no DB seed, so no
 * security or data-mutation surface. See memory: portfolio-pivot.
 *
 * Canned data is registered per endpoint in `matchDemoGet` and grows page by
 * page; any unregistered GET returns a benign `{}` so optional-chaining hooks
 * fall back to their empty state instead of hitting the absent backend.
 */
import type { User } from "./auth";
import type { MirrorHomeResponse } from "./types";

export function isDemoMode(): boolean {
  return process.env.NEXT_PUBLIC_DEMO_MODE === "1";
}

/** Fixed demo identity — onboarding done + birthdate set so the layout guard
 *  (nextAuthRedirect) returns null and the dashboard renders straight away. */
export const DEMO_USER: User = {
  id: 1,
  email: "demo@pivoxquant.com",
  name: "데모 투자자",
  available_capital: 100_000,
  available_capital_krw: 50_000_000,
  oauth_provider: "google",
  risk_profile: "balanced",
  subscription_tier: "premium",
  effective_tier: "premium",
  subscription_status: "active",
  raw_subscription_status: "active",
  onboarding_completed: true,
  birthdate_required: false,
  profile_changes_left: 3,
};

/** 거울 home sample — "성장형 선언 → 최근 30일 균형형 관찰" (영역 이동). Radar
 *  vectors are the real growth/balanced centroids so the shape gap is faithful. */
const DEMO_MIRROR_HOME: MirrorHomeResponse = {
  ok: true,
  stage: "observed",
  declared: { label: "성장형", tagline: "성장 가능성에 무게를 두고 관찰합니다.", score: 78 },
  observed: { label: "균형형", bucket_changed: true, trade_count: 23 },
  gap: [
    { key: "sector_diversity", label: "섹터 분산", direction: "up", delta: 0.4, declared: 0.45, observed: 0.85 },
    { key: "ticker_diversity", label: "종목 다양성", direction: "up", delta: 0.25, declared: 0.55, observed: 0.8 },
    { key: "declared_risk", label: "선언한 위험 감내", direction: "down", delta: -0.25, declared: 0.75, observed: 0.5 },
  ],
  drift: { available: true, descriptor: "영역 이동 관찰" },
  radar: {
    keys: [
      "holding_period", "turnover", "sector_diversity", "ticker_diversity",
      "hold_variance", "loss_cut_discipline", "declared_risk",
      "conviction_stability", "feedback_engagement",
    ],
    labels: [
      "평균 보유기간", "매매 회전율", "섹터 분산", "종목 다양성", "보유기간 편차",
      "손절 규율", "선언한 위험 감내", "확신 안정성", "피드백 반응도",
    ],
    declared: [0.48, 0.3, 0.45, 0.55, 0.45, 0.55, 0.75, 0.65, 0.6],
    observed: [0.55, 0.15, 0.85, 0.8, 0.3, 0.6, 0.5, 0.7, 0.6],
  },
  twin: {
    week_ending: "2026-06-14",
    user_return_pct: 1.1,
    twin_return_pct: 3.3,
    diff_pct: 2.2,
    user_trades_count: 2,
    twin_trades_count: 3,
  },
};

/* ── Consistent demo book — a 성장형→균형형 investor, mixed KR+US, 7 holdings
 *    across Tech / Consumer / Financials / Healthcare (matches the radar's high
 *    sector diversity). All page datasets below derive from this same book. ── */
const FX = 1378.5;

const DEMO_POSITION_ROWS = [
  { id: 1, ticker: "NVDA", name: "NVIDIA", sector: "Technology", currency: "USD", is_korean: false, shares: 40, avg_cost: 118.0, current_price: 182.5, market_value: 7300, market_value_usd: 7300, pnl_pct: 54.7, weight: 11.1, signal: "POSITIVE", score: 82 },
  { id: 2, ticker: "AAPL", name: "Apple", sector: "Technology", currency: "USD", is_korean: false, shares: 50, avg_cost: 205.0, current_price: 241.2, market_value: 12060, market_value_usd: 12060, pnl_pct: 17.7, weight: 18.4, signal: "NEUTRAL", score: 61 },
  { id: 3, ticker: "TSLA", name: "Tesla", sector: "Consumer Discretionary", currency: "USD", is_korean: false, shares: 25, avg_cost: 250.0, current_price: 412.6, market_value: 10315, market_value_usd: 10315, pnl_pct: 65.0, weight: 15.7, signal: "POSITIVE", score: 74 },
  { id: 4, ticker: "JPM", name: "JPMorgan Chase", sector: "Financials", currency: "USD", is_korean: false, shares: 30, avg_cost: 235.0, current_price: 268.4, market_value: 8052, market_value_usd: 8052, pnl_pct: 14.2, weight: 12.3, signal: "NEUTRAL", score: 58 },
  { id: 5, ticker: "LLY", name: "Eli Lilly", sector: "Healthcare", currency: "USD", is_korean: false, shares: 8, avg_cost: 820.0, current_price: 742.0, market_value: 5936, market_value_usd: 5936, pnl_pct: -9.5, weight: 9.0, signal: "NEGATIVE", score: 43 },
  { id: 6, ticker: "005930", name: "삼성전자", sector: "Technology", currency: "KRW", is_korean: true, shares: 200, avg_cost: 72000, current_price: 84300, market_value: 16860000, market_value_usd: 12231, pnl_pct: 17.1, weight: 18.6, signal: "POSITIVE", score: 69 },
  { id: 7, ticker: "005380", name: "현대차", sector: "Consumer Discretionary", currency: "KRW", is_korean: true, shares: 50, avg_cost: 245000, current_price: 268500, market_value: 13425000, market_value_usd: 9739, pnl_pct: 9.6, weight: 14.8, signal: "NEUTRAL", score: 55 },
];

const DEMO_POSITIONS = {
  positions: DEMO_POSITION_ROWS,
  available_capital: 8200,
  available_capital_krw: 11_303_700,
  total_value_usd: 65633,
  total_value_all_krw: 90_474_440,
  fx_rate: FX,
};

const DEMO_PORTFOLIO_SUMMARY = {
  totalNav: 65633,
  navUsd: 43663,
  navKrw: 30_285_000,
  todayPnl: 612,
  todayPnlPct: 0.94,
  todayPnlUsd: 612,
  todayPnlKrw: 0,
  unrealized: 11470,
  unrealizedUsd: 8833,
  unrealizedKrw: 3_635_000,
  realizedYtd: 3180,
  realizedUsd: 3180,
  realizedKrw: 0,
  fxRate: FX,
  cashPct: 12.5,
  observed_at: "2026-06-18T07:30:00+09:00",
};

const _spark = (base: number, drift: number) =>
  Array.from({ length: 30 }, (_, i) =>
    +(base * (1 + (drift * (i - 29)) / 29 + 0.012 * Math.sin(i / 3.2))).toFixed(2));

const DEMO_MARKET_INDICES = [
  { ticker: "^GSPC", name: "S&P 500", level: 6180.42, change_1d_pct: 0.42, is_stale: false, range_52w: [4820, 6240], sparkline_30d: _spark(6180.42, 0.06) },
  { ticker: "^IXIC", name: "NASDAQ 100", level: 22450.8, change_1d_pct: 0.61, is_stale: false, range_52w: [17200, 22680], sparkline_30d: _spark(22450.8, 0.08) },
  { ticker: "^VIX", name: "VIX", level: 14.2, change_1d_pct: -3.1, is_stale: false, range_52w: [11.2, 38.5], sparkline_30d: _spark(14.2, -0.1) },
  { ticker: "^KS11", name: "KOSPI", level: 3180.5, change_1d_pct: 0.85, is_stale: false, range_52w: [2380, 3240], sparkline_30d: _spark(3180.5, 0.05) },
  { ticker: "^KQ11", name: "KOSDAQ", level: 1042.3, change_1d_pct: 1.12, is_stale: false, range_52w: [780, 1060], sparkline_30d: _spark(1042.3, 0.04) },
  { ticker: "USDKRW", name: "USD/KRW", level: FX, change_1d_pct: -0.22, is_stale: false, range_52w: [1290, 1452], sparkline_30d: _spark(FX, -0.02) },
];

const DEMO_FX = {
  ok: true,
  usd_krw: FX,
  last_updated: "2026-06-18T16:30:00+09:00",
  last_updated_ts: Date.parse("2026-06-18T16:30:00+09:00"),
  age_seconds: 45,
  is_stale: false,
};

const DEMO_BROKER_CONNECTIONS = {
  kis_connected: true,
  kis_last_sync: "2026-06-18T07:30:00+09:00",
};

const DEMO_SIGNALS = {
  total: 9,
  counts: { positive: 4, negative: 1, neutral: 4 },
  signals: [
    { id: "s1", ticker: "NVDA", name: "NVIDIA", label: "POSITIVE", signal: "POSITIVE", strength: 0.82, score: 82, sector: "Technology", currency: "USD", is_korean: false, price: 182.5, change_pct: 2.1, rationale: "거래량 급증 + 50일선 상회, 모멘텀 지속.", observed_at: "2026-06-18T06:50:00+09:00", is_stale: false },
    { id: "s2", ticker: "MSFT", name: "Microsoft", label: "POSITIVE", signal: "POSITIVE", strength: 0.77, score: 77, sector: "Technology", currency: "USD", is_korean: false, price: 498.3, change_pct: 1.3, rationale: "신고가 부근 견조한 매집 흐름.", observed_at: "2026-06-18T06:50:00+09:00", is_stale: false },
    { id: "s3", ticker: "TSLA", name: "Tesla", label: "POSITIVE", signal: "POSITIVE", strength: 0.74, score: 74, sector: "Consumer Discretionary", currency: "USD", is_korean: false, price: 412.6, change_pct: 3.4, rationale: "변동성 확대 속 추세 상단 유지.", observed_at: "2026-06-18T06:50:00+09:00", is_stale: false },
    { id: "s4", ticker: "005930", name: "삼성전자", label: "POSITIVE", signal: "POSITIVE", strength: 0.69, score: 69, sector: "Technology", currency: "KRW", is_korean: true, price: 84300, change_pct: 1.2, rationale: "외국인 순매수 전환, 박스권 상단 시도.", observed_at: "2026-06-18T06:50:00+09:00", is_stale: false },
    { id: "s5", ticker: "AAPL", name: "Apple", label: "NEUTRAL", signal: "NEUTRAL", strength: 0.61, score: 61, sector: "Technology", currency: "USD", is_korean: false, price: 241.2, change_pct: 0.3, rationale: "방향성 부재, 200일선 부근 횡보.", observed_at: "2026-06-18T06:50:00+09:00", is_stale: false },
    { id: "s6", ticker: "GOOGL", name: "Alphabet", label: "NEUTRAL", signal: "NEUTRAL", strength: 0.6, score: 60, sector: "Communication", currency: "USD", is_korean: false, price: 198.4, change_pct: -0.2, rationale: "거래량 둔화, 관망 구간.", observed_at: "2026-06-18T06:50:00+09:00", is_stale: false },
    { id: "s7", ticker: "JPM", name: "JPMorgan Chase", label: "NEUTRAL", signal: "NEUTRAL", strength: 0.58, score: 58, sector: "Financials", currency: "USD", is_korean: false, price: 268.4, change_pct: 0.5, rationale: "금리 민감 구간, 추세 중립.", observed_at: "2026-06-18T06:50:00+09:00", is_stale: false },
    { id: "s8", ticker: "005380", name: "현대차", label: "NEUTRAL", signal: "NEUTRAL", strength: 0.55, score: 55, sector: "Consumer Discretionary", currency: "KRW", is_korean: true, price: 268500, change_pct: 0.7, rationale: "수출 모멘텀 vs 환율 부담 혼조.", observed_at: "2026-06-18T06:50:00+09:00", is_stale: false },
    { id: "s9", ticker: "LLY", name: "Eli Lilly", label: "NEGATIVE", signal: "NEGATIVE", strength: 0.43, score: 43, sector: "Healthcare", currency: "USD", is_korean: false, price: 742.0, change_pct: -1.8, rationale: "고점 대비 조정, 모멘텀 약화.", observed_at: "2026-06-18T06:50:00+09:00", is_stale: false },
  ],
};

const DEMO_WATCHLIST = {
  watchlist: [
    { id: 1, ticker: "MSFT", name: "Microsoft", price: 498.3, change_pct: 1.3, signal: "POSITIVE", score: 77, currency: "USD", is_korean: false, added_at: "2026-06-01T09:00:00+09:00" },
    { id: 2, ticker: "GOOGL", name: "Alphabet", price: 198.4, change_pct: -0.2, signal: "NEUTRAL", score: 60, currency: "USD", is_korean: false, added_at: "2026-06-03T09:00:00+09:00" },
    { id: 3, ticker: "035720", name: "카카오", price: 58700, change_pct: 2.4, signal: "POSITIVE", score: 66, currency: "KRW", is_korean: true, added_at: "2026-06-10T09:00:00+09:00" },
  ],
};

const DEMO_RISK_SUMMARY = {
  var_1d_pct: 2.4, var_95: 2.4, var_99: 3.8, es_1d_pct: 3.1, tail_ces: 3.5,
  max_dd_90d_pct: 8.6, daily_dd_pct: 1.2,
  corr_risk_index: 0.42, correlation_avg: 0.38, correlation_max: 0.71,
  hhi: 0.15, sector_top_name: "Technology", sector_top_pct: 48.1,
  vix: 14.2, vix_regime: "안정(저변동)", cash_pct: 12.5,
  posture: "attentive", layers_breached: 0,
  observed_at_kst: "2026-06-18T16:30:00+09:00",
};

const DEMO_RISK_LAYERS = {
  defense_score: 78,
  overall_status: "POSITIVE",
  layers: [
    { num: 1, name: "변동성", status: "POSITIVE", value: "14.2", threshold: "< 25", observation: "VIX 저변동 구간, 포트폴리오 변동성 안정.", observed_at_kst: "2026-06-18T16:30:00+09:00" },
    { num: 2, name: "집중도", status: "NEUTRAL", value: "HHI 0.15", threshold: "< 0.20", observation: "기술 섹터 48%로 다소 높음, 임계 이하.", observed_at_kst: "2026-06-18T16:30:00+09:00" },
    { num: 3, name: "상관", status: "POSITIVE", value: "0.38", threshold: "< 0.60", observation: "평균 상관 낮음, 분산 효과 유효.", observed_at_kst: "2026-06-18T16:30:00+09:00" },
    { num: 4, name: "꼬리위험", status: "NEUTRAL", value: "ES 3.1%", threshold: "< 4%", observation: "기대손실 안정권, 경계 유지.", observed_at_kst: "2026-06-18T16:30:00+09:00" },
    { num: 5, name: "유동성", status: "POSITIVE", value: "현금 12.5%", threshold: "> 5%", observation: "현금 버퍼 충분.", observed_at_kst: "2026-06-18T16:30:00+09:00" },
    { num: 6, name: "낙폭", status: "POSITIVE", value: "MDD 8.6%", threshold: "< 15%", observation: "90일 최대낙폭 통제 범위.", observed_at_kst: "2026-06-18T16:30:00+09:00" },
    { num: 7, name: "레짐", status: "POSITIVE", value: "Risk-On", threshold: "—", observation: "위험선호 국면, 추세 우호.", observed_at_kst: "2026-06-18T16:30:00+09:00" },
  ],
};

const _rvBase = Date.parse("2026-05-20T00:00:00Z");
const DEMO_RISK_ROLLING_VAR = Array.from({ length: 30 }, (_, i) => ({
  date: new Date(_rvBase + i * 86_400_000).toISOString().slice(0, 10),
  var_pct: -(1.9 + 0.7 * Math.sin(i / 3.3) + 0.4 * Math.cos(i / 2.1) + (i > 22 ? 0.5 : 0)),
}));

const DEMO_RISK_CORRELATION = {
  labels: ["NVDA", "AAPL", "TSLA", "JPM", "삼성전자", "현대차"],
  matrix: [
    [1.0, 0.62, 0.55, 0.31, 0.58, 0.27],
    [0.62, 1.0, 0.48, 0.35, 0.61, 0.3],
    [0.55, 0.48, 1.0, 0.29, 0.44, 0.41],
    [0.31, 0.35, 0.29, 1.0, 0.33, 0.38],
    [0.58, 0.61, 0.44, 0.33, 1.0, 0.46],
    [0.27, 0.3, 0.41, 0.38, 0.46, 1.0],
  ],
};

/** Canned GET response for a path, or undefined if not registered yet. */
function matchDemoGet(path: string): unknown | undefined {
  const base = path.split("?")[0];
  switch (base) {
    case "/api/auth/me":
      return { authenticated: true, user: DEMO_USER };
    case "/api/mirror-home":
      return DEMO_MIRROR_HOME;
    case "/api/market/indices":
      return DEMO_MARKET_INDICES;
    case "/api/market/fx":
      return DEMO_FX;
    case "/api/portfolio/positions":
      return DEMO_POSITIONS;
    case "/api/portfolio/summary":
      return DEMO_PORTFOLIO_SUMMARY;
    case "/api/broker/connections":
      return DEMO_BROKER_CONNECTIONS;
    case "/api/signals":
      return DEMO_SIGNALS;
    case "/api/watchlist":
      return DEMO_WATCHLIST;
    case "/api/risk/summary":
      return DEMO_RISK_SUMMARY;
    case "/api/risk/layers":
      return DEMO_RISK_LAYERS;
    case "/api/risk/rolling-var":
      return DEMO_RISK_ROLLING_VAR;
    case "/api/risk/correlation":
      return DEMO_RISK_CORRELATION;
    default:
      return undefined;
  }
}

/**
 * Resolve a demo response for any apiFetch call. In demo mode this ALWAYS hits
 * (we never touch a network), so:
 *   - mutating methods → inert `{ ok: true }`
 *   - registered GET   → its canned body
 *   - unregistered GET → `{}` (graceful empty for optional-chaining hooks)
 */
export function demoResponseFor(
  path: string,
  method?: string,
): { hit: boolean; body: unknown } {
  const verb = (method ?? "GET").toUpperCase();
  if (verb !== "GET") return { hit: true, body: { ok: true } };
  const found = matchDemoGet(path);
  return { hit: true, body: found === undefined ? {} : found };
}

/** Resolve any URL (relative or absolute) to its "/api/..." path for matching. */
function toApiPath(url: string): string {
  try {
    const u = new URL(url, "http://demo.local");
    return u.pathname + u.search;
  } catch {
    return url;
  }
}

/**
 * Patch the GLOBAL fetch in demo mode (SSR + browser) so EVERY `/api/*` request
 * — from any fetcher, server component, or Suspense data read — resolves to
 * canned data instead of hitting the (absent) backend. This is the safety net
 * behind the per-fetcher guards: without it, a single unpatched fetch to the
 * dead backend SSR-suspends a whole route forever. Non-API requests (assets,
 * HMR, OAuth) pass through untouched. Idempotent; a no-op when the flag is off.
 */
let demoFetchInstalled = false;
export function installDemoFetch(): void {
  if (demoFetchInstalled || !isDemoMode()) return;
  // CLIENT-ONLY. Patching fetch on the server replaces Next.js's instrumented
  // fetch and breaks build-time prerender ("Expected workStore to be
  // initialized"). The app's data pages are "use client" + SWR, so all data
  // fetching happens in the browser anyway; the per-fetcher guards cover any
  // server path. Never touch globalThis.fetch on the server.
  if (typeof window === "undefined") return;
  if (typeof globalThis.fetch !== "function") return;
  demoFetchInstalled = true;
  const original = globalThis.fetch.bind(globalThis);
  globalThis.fetch = async (
    input: RequestInfo | URL,
    init?: RequestInit,
  ): Promise<Response> => {
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url;
    if (url && url.includes("/api/")) {
      const method =
        init?.method ??
        (typeof input === "object" && "method" in input ? input.method : "GET");
      const { body } = demoResponseFor(toApiPath(url), method);
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return original(input, init);
  };
}

// Install eagerly on module load (both server and client) so the patch is in
// place before any data fetch fires. Guarded by isDemoMode() internally.
installDemoFetch();
