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

/** Fixed demo identity — onboarding done + age confirmation done (PIPA §22 ⑥)
 *  so the layout guard (nextAuthRedirect) returns null and the dashboard
 *  renders straight away. */
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
  age_confirmation_required: false,
  // Deprecated mirror of the key above — kept while the backend still emits it.
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
};

/* ── Consistent demo book — a 성장형→균형형 investor, mixed KR+US, 7 holdings
 *    across Tech / Consumer / Financials / Healthcare (matches the radar's high
 *    sector diversity). All page datasets below derive from this same book. ── */
const FX = 1378.5;

const DEMO_POSITION_ROWS = [
  { id: 1, ticker: "NVDA", name: "NVIDIA", sector: "Technology", currency: "USD", is_korean: false, shares: 40, avg_cost: 118.0, current_price: 182.5, market_value: 7300, market_value_usd: 7300, pnl_pct: 54.7, weight: 11.1, score: 82 },
  { id: 2, ticker: "AAPL", name: "Apple", sector: "Technology", currency: "USD", is_korean: false, shares: 50, avg_cost: 205.0, current_price: 241.2, market_value: 12060, market_value_usd: 12060, pnl_pct: 17.7, weight: 18.4, score: 61 },
  { id: 3, ticker: "TSLA", name: "Tesla", sector: "Consumer Discretionary", currency: "USD", is_korean: false, shares: 25, avg_cost: 250.0, current_price: 412.6, market_value: 10315, market_value_usd: 10315, pnl_pct: 65.0, weight: 15.7, score: 74 },
  { id: 4, ticker: "JPM", name: "JPMorgan Chase", sector: "Financials", currency: "USD", is_korean: false, shares: 30, avg_cost: 235.0, current_price: 268.4, market_value: 8052, market_value_usd: 8052, pnl_pct: 14.2, weight: 12.3, score: 58 },
  { id: 5, ticker: "LLY", name: "Eli Lilly", sector: "Healthcare", currency: "USD", is_korean: false, shares: 8, avg_cost: 820.0, current_price: 742.0, market_value: 5936, market_value_usd: 5936, pnl_pct: -9.5, weight: 9.0, score: 43 },
  { id: 6, ticker: "005930", name: "삼성전자", sector: "Technology", currency: "KRW", is_korean: true, shares: 200, avg_cost: 72000, current_price: 84300, market_value: 16860000, market_value_usd: 12231, pnl_pct: 17.1, weight: 18.6, score: 69 },
  { id: 7, ticker: "005380", name: "현대차", sector: "Consumer Discretionary", currency: "KRW", is_korean: true, shares: 50, avg_cost: 245000, current_price: 268500, market_value: 13425000, market_value_usd: 9739, pnl_pct: 9.6, weight: 14.8, score: 55 },
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







/* Persona-detail / group-benchmark fixtures removed 2026-09-12 with /profile —
 * no UI calls those endpoints any more. */
const DEMO_PROFILE = {
  has_profile: true,
  profile: { profile_type: "growth", risk_tolerance: "moderate", tagline: "성장 가능성에 무게를 두고 관찰합니다." },
};



/* ── Alerts ── */
const DEMO_ALERTS = {
  unread: 2,
  alerts: [
    { id: 1, kind: "observation", title: "NVDA 52주 고점 근접", body: "52주 범위 상단에 닿았습니다", ticker: "NVDA", name: "NVIDIA", is_read: false, created_at: "2026-06-18T06:50:00+09:00" },
    { id: 2, kind: "risk", title: "집중도 주의", body: "기술 섹터 비중 48%", is_read: false, created_at: "2026-06-17T16:30:00+09:00" },
    { id: 3, kind: "observation", title: "TSLA 변동성 확대", body: "일중 변동성 상위", ticker: "TSLA", name: "Tesla", is_read: true, read_at: "2026-06-17T10:00:00+09:00", created_at: "2026-06-17T09:30:00+09:00" },
    { id: 4, kind: "system", title: "주간 메모 도착", body: "6월 3주 거울이 준비됐어요", link: "/reports", is_read: true, read_at: "2026-06-16T09:00:00+09:00", created_at: "2026-06-16T08:00:00+09:00" },
    { id: 5, kind: "observation", title: "LLY 52주 저점 근접", body: "52주 범위 하단에 닿았습니다", ticker: "LLY", name: "Eli Lilly", is_read: true, read_at: "2026-06-15T11:00:00+09:00", created_at: "2026-06-15T07:00:00+09:00" },
  ],
};

/* ── Journal — 5 behavioural mirrors + pre-trade reflections ── */
const DEMO_HOLDING_MIRROR = {
  ok: true, period: "최근 90일", sufficient_data: true, one_sided: false, total_closed_pairs: 14,
  winners: { count: 6, median_hold_days: 31, mean_hold_days: 34, examples: [{ display_name: "NVIDIA", ticker: "NVDA", pnl_pct: 54.7, hold_days: 42 }, { display_name: "Tesla", ticker: "TSLA", pnl_pct: 65.0, hold_days: 38 }, { display_name: "삼성전자", ticker: "005930", pnl_pct: 17.1, hold_days: 28 }] },
  losers: { count: 8, median_hold_days: 9, mean_hold_days: 11, examples: [{ display_name: "Eli Lilly", ticker: "LLY", pnl_pct: -9.5, hold_days: 7 }, { display_name: "Alphabet", ticker: "GOOGL", pnl_pct: -4.2, hold_days: 5 }] },
};
const DEMO_CONCENTRATION_MIRROR = { ok: true, sufficient_data: true, ticker_count: 7, max_weight_pct: 18.6, largest_ticker: "삼성전자", cost_basis_note: "평균매입가 기준 (시장가 아님)" };
const DEMO_PL_MIRROR = {
  ok: true, period: "all", sufficient_data: true, one_sided: false, total_closed_pairs: 14,
  take_profit: { count: 6, median_hold_days: 31, mean_hold_days: 34, median_gain_pct: 18.5, mean_gain_pct: 24.1 },
  stop_loss: { count: 8, median_hold_days: 9, mean_hold_days: 11, median_loss_pct: -6.8, mean_loss_pct: -8.2 },
};
const DEMO_TURNOVER_MIRROR = {
  ok: true, period: "all", period_days: null, sufficient_data: true, trade_count: 37, buy_count: 21, sell_count: 16,
  by_currency: [{ currency: "USD", gross_value: 88200, trade_count: 24 }, { currency: "KRW", gross_value: 62400000, trade_count: 13 }],
  median_hold_days: 22, mean_hold_days: 26,
};
const DEMO_AVGDOWN_MIRROR = {
  ok: true, period: "all", period_days: null, sufficient_data: true, follow_on_count: 9, below_avg_count: 6, above_avg_count: 2, flat_count: 1,
  by_ticker: [{ ticker: "NVDA", name: "NVIDIA", follow_on: 3, below_avg: 2, above_avg: 1 }, { ticker: "005930", name: "삼성전자", follow_on: 4, below_avg: 3, above_avg: 1 }, { ticker: "TSLA", name: "Tesla", follow_on: 2, below_avg: 1, above_avg: 0 }],
};
const DEMO_PRETRADE_LIST = {
  ok: true,
  reflections: [
    { id: 1, intended_ticker: "NVDA", intended_side: "BUY", rationale: "실적 모멘텀 지속 판단, 분할 매수 1차.", status: "proceeded", proceeded_at: "2026-06-15T10:00:00+09:00", cancelled_at: null, observed_context: { sector: "Technology", vix: 14.2 } },
    { id: 2, intended_ticker: "LLY", intended_side: "SELL", rationale: "고점 대비 조정, 비중 축소 고민.", status: "cancelled", proceeded_at: null, cancelled_at: "2026-06-14T14:00:00+09:00", observed_context: { sector: "Healthcare", vix: 14.5 } },
    { id: 3, intended_ticker: "TSLA", intended_side: "BUY", rationale: "변동성 확대, 추격 매수 충동 점검 중.", status: "pending", proceeded_at: null, cancelled_at: null, observed_context: { sector: "Consumer Discretionary", vix: 14.2 } },
  ],
};
// Friction outcome (sidebar record card + /journal mirror). Counts agree with
// DEMO_PRETRADE_LIST above: 3 started → 1 proceeded / 1 cancelled / 1 open.
// `comparable: false` so the mirror honours the service's refusal and shows
// no distribution block — the demo must not imply a verdict the data lacks.
const DEMO_FRICTION_OUTCOME = {
  ok: true,
  period: "30d",
  window_days: 30,
  stopped: { started: 3, proceeded: 1, cancelled: 1, open: 1 },
  cancelled_followthrough: { cancelled: 1, bought_later_anyway: 0, never_bought: 1, median_days_until_bought: null },
  realised: {
    with_friction: { n: 1, median_pct: null, mean_pct: null },
    without_friction: { n: 2, median_pct: null, mean_pct: null },
    comparable: false,
    min_group_n: 5,
  },
  caveats: { not_randomised: true, attribution_window_days: 7, cooldown_seconds_currently: 0 },
  insufficient: false,
};


/* ── 관찰 노트 (observation notes, 2026-09-22) ──
 * The /journal timeline merges these with DEMO_PRETRADE_LIST above, and
 * /pre-trade reads them back per ticker. Tickers are drawn from
 * DEMO_POSITION_ROWS so the demo book and the demo record agree. Copy is
 * observational — what the user saw, never what to do about it. One note
 * carries no ticker at all (a market-wide note), which is the shape the
 * backend allows and the UI must not choke on. */
const DEMO_OBSERVATION_NOTES = [
  {
    id: 3,
    user_id: 1,
    body: "엔비디아는 지난주부터 장 초반 거래량이 평소보다 두껍다. 내가 왜 이걸 계속 보고 있는지는 아직 설명하지 못하겠다.",
    tickers: [{ ticker: "NVDA", name: "NVIDIA" }],
    tags: ["거래량", "관찰"],
    source: "journal",
    created_at: "2026-06-17T23:40:00Z",
  },
  {
    id: 2,
    user_id: 1,
    body: "삼성전자 평단 근처에서 손이 근질거린다. 오늘은 아무것도 하지 않고 이 문장만 적어 둔다.",
    tickers: [{ ticker: "005930", name: "삼성전자" }],
    tags: ["충동"],
    source: "portfolio",
    created_at: "2026-06-16T07:10:00Z",
  },
  {
    id: 1,
    user_id: 1,
    body: "지수가 이틀 연속 쉬었는데 내 계좌는 더 크게 흔들렸다. 종목 수보다 비중이 문제인 것 같다.",
    tickers: [],
    tags: ["집중도"],
    source: "journal",
    created_at: "2026-06-14T09:05:00Z",
  },
];

const DEMO_OBSERVATION_NOTES_LIST = {
  ok: true,
  notes: DEMO_OBSERVATION_NOTES,
  next_before: null,
};

/** `/api/observation-notes/by-ticker/<t>` — filtered from the same three. */
function _demoNotesByTicker(base: string) {
  const raw = base.slice("/api/observation-notes/by-ticker/".length);
  const ticker = decodeURIComponent(raw).trim().toUpperCase();
  const notes = DEMO_OBSERVATION_NOTES.filter((n) =>
    n.tickers.some((t) => t.ticker.toUpperCase() === ticker),
  );
  return { ok: true, ticker, count: notes.length, notes };
}

/* ── Living CFO Layer-2 + profile depth (usePersona / usePulse / useRollingWindow,
 *    lib/cfo/hooks.ts). In demo mode apiFetch resolves {} WITHOUT throwing, so the
 *    cfoFetch mock fallback never fires — these must be canned or L2 reads "missing"
 *    on every page's status bar. window_30d present + ≥3 pulses ⇒ L2 "ready". ── */
const _wkBase = Date.parse("2026-03-27T00:00:00Z");
const DEMO_PERSONA = {
  declared: { persona: "growth", label: "성장형", tagline: "성장 가능성에 무게를 두고 관찰합니다.", score: 78 },
  observed: {
    window_30d: { date: "2026-06-18", persona: "balanced", score: 72 },
    window_60d: { date: "2026-05-19", persona: "growth", score: 70 },
    window_90d: { date: "2026-04-19", persona: "growth", score: 74 },
  },
  sparkline: Array.from({ length: 12 }, (_, i) => ({
    week: new Date(_wkBase + i * 7 * 86_400_000).toISOString().slice(0, 10),
    score: Math.round(70 + 6 * Math.sin(i / 2.4) + (i >= 8 ? 4 : 0)),
  })),
  last_computed_at: "2026-06-18T07:30:00+09:00",
  drift: 18,
};
const DEMO_PULSE = {
  history: [
    { submitted_at: "2026-05-26T22:00:00Z", mood: 4, confidence: 3, worry: "기술 섹터 비중이 높아 변동성이 신경 쓰입니다.", topics: ["집중도", "변동성"], learn: "섹터 분산을 한 단계 더 넓히기" },
    { submitted_at: "2026-06-02T22:00:00Z", mood: 3, confidence: 4, worry: "급등 종목 추격 매수 충동이 있었습니다.", topics: ["매매 규율"], learn: "진입 전 멈춤 한 박자" },
    { submitted_at: "2026-06-09T22:00:00Z", mood: 4, confidence: 4, worry: "손절 라인을 자꾸 미루게 됩니다.", topics: ["손절 규율"], learn: "손절 기준을 사전에 고정" },
    { submitted_at: "2026-06-16T22:00:00Z", mood: 5, confidence: 4, worry: "", topics: ["보유 기간"], learn: "장기 보유 비중 유지" },
  ],
  next_due_at: "2026-06-23T22:00:00Z",
  cadence: "weekly",
};
const _rwBase2 = Date.parse("2026-03-20T00:00:00Z");
const _rw = (n: number) =>
  Array.from({ length: n }, (_, i) => ({
    date: new Date(_rwBase2 + i * 86_400_000).toISOString().slice(0, 10),
    holdingPeriod: Math.round(26 + 7 * Math.sin(i / 6)),
    turnover: +(0.18 + 0.06 * Math.cos(i / 7)).toFixed(2),
    sectorTilt: +(0.34 + 0.09 * Math.abs(Math.sin(i / 8))).toFixed(2),
  }));
const DEMO_ROLLING_WINDOW = {
  series: { window_30d: _rw(30), window_60d: _rw(60), window_90d: _rw(90) },
  contrast: { declared_persona: "growth", declared_score: 78, observed_persona: "balanced", observed_score: 72, window_days: 30 },
};

/* ── Portfolio equity curve (/api/portfolio/history?period=) + trades. Backend
 *    shape = { data:[{date,value,benchmark}], benchmark:{name} }; hooks-v2
 *    normalizes. NAV grows to the canned summary total (~65,633 USD-unified). ── */
const _eqBase = Date.parse("2026-03-20T00:00:00Z");
const DEMO_EQUITY_FULL = Array.from({ length: 64 }, (_, i) => {
  const f = i / 63;
  const nav = 58000 * (1 + 0.131 * f + 0.022 * Math.sin(i / 4.5) + 0.012 * Math.cos(i / 2.7));
  const bench = 2580 * (1 + 0.071 * f + 0.018 * Math.sin(i / 5.1)); // KOSPI200-scale, rebased in UI
  return { date: new Date(_eqBase + i * 86_400_000).toISOString().slice(0, 10), value: Math.round(nav), benchmark: +bench.toFixed(1) };
});
DEMO_EQUITY_FULL[DEMO_EQUITY_FULL.length - 1].value = 65633; // tie to summary NAV
const _demoEquity = (period: string) => {
  const take = period === "5d" ? 8 : period === "1mo" ? 24 : period === "2mo" ? 48 : period === "3mo" ? 64 : 64;
  return { data: DEMO_EQUITY_FULL.slice(-take), benchmark: { name: "KOSPI 200" } };
};
const DEMO_TRADES = {
  trades: [
    { id: 7, date: "2026-06-15T01:05:00Z", symbol: "NVDA", name: "NVIDIA", side: "buy", shares: 15, price: 176.2, amount: 2643, currency: "USD" },
    { id: 6, date: "2026-06-11T06:20:00Z", symbol: "005930", name: "삼성전자", side: "buy", shares: 50, price: 81000, amount: 4050000, currency: "KRW" },
    { id: 5, date: "2026-06-05T01:40:00Z", symbol: "LLY", name: "Eli Lilly", side: "sell", shares: 4, price: 768.0, amount: 3072, currency: "USD" },
    { id: 4, date: "2026-05-28T02:10:00Z", symbol: "TSLA", name: "Tesla", side: "buy", shares: 10, price: 332.5, amount: 3325, currency: "USD" },
    { id: 3, date: "2026-05-20T05:30:00Z", symbol: "005380", name: "현대차", side: "buy", shares: 20, price: 252000, amount: 5040000, currency: "KRW" },
    { id: 2, date: "2026-05-12T01:15:00Z", symbol: "AAPL", name: "Apple", side: "buy", shares: 20, price: 221.0, amount: 4420, currency: "USD" },
    { id: 1, date: "2026-05-04T01:50:00Z", symbol: "JPM", name: "JPMorgan Chase", side: "buy", shares: 30, price: 248.0, amount: 7440, currency: "USD" },
  ],
};
/* Full /api/portfolio (legacy) so RealtimeProvider sees positions ⇒ ribbon "● Live". */
const DEMO_FULL_PORTFOLIO = { positions: DEMO_POSITION_ROWS, total_value_usd: 65633, fx_rate: FX };

/* ── Per-ticker detail (/detail/[ticker]): signal hero + chart + company profile.

/* ── Global search (Cmd+K) — filter a small universe by q. ── */
const DEMO_SEARCH_UNIVERSE = [
  { ticker: "NVDA", name: "NVIDIA", exchange: "NASDAQ", is_korean: false },
  { ticker: "AAPL", name: "Apple", exchange: "NASDAQ", is_korean: false },
  { ticker: "MSFT", name: "Microsoft", exchange: "NASDAQ", is_korean: false },
  { ticker: "TSLA", name: "Tesla", exchange: "NASDAQ", is_korean: false },
  { ticker: "GOOGL", name: "Alphabet", exchange: "NASDAQ", is_korean: false },
  { ticker: "AVGO", name: "Broadcom", exchange: "NASDAQ", is_korean: false },
  { ticker: "JPM", name: "JPMorgan Chase", exchange: "NYSE", is_korean: false },
  { ticker: "LLY", name: "Eli Lilly", exchange: "NYSE", is_korean: false },
  { ticker: "UNH", name: "UnitedHealth", exchange: "NYSE", is_korean: false },
  { ticker: "005930", name: "삼성전자", exchange: "KRX", is_korean: true },
  { ticker: "005380", name: "현대차", exchange: "KRX", is_korean: true },
  { ticker: "000660", name: "SK하이닉스", exchange: "KRX", is_korean: true },
  { ticker: "035720", name: "카카오", exchange: "KRX", is_korean: true },
];
function _demoSearch(query: string) {
  const params = new URLSearchParams(query);
  const q = (params.get("q") || "").trim().toLowerCase();
  if (!q) return { results: [] };
  const results = DEMO_SEARCH_UNIVERSE.filter(
    (r) => r.ticker.toLowerCase().includes(q) || r.name.toLowerCase().includes(q),
  ).slice(0, 10);
  return { results };
}

/** Canned GET response for a path, or undefined if not registered yet. */
function matchDemoGet(path: string): unknown | undefined {
  const qIdx = path.indexOf("?");
  const base = qIdx === -1 ? path : path.slice(0, qIdx);
  const query = qIdx === -1 ? "" : path.slice(qIdx + 1);

  if (base === "/api/search") return _demoSearch(query);
  if (base.startsWith("/api/observation-notes/by-ticker/"))
    return _demoNotesByTicker(base);
  if (base === "/api/portfolio/history")
    return _demoEquity(new URLSearchParams(query).get("period") || "1mo");

  switch (base) {
    case "/api/auth/me":
      return { authenticated: true, user: DEMO_USER };
    case "/api/mirror-home":
      return DEMO_MIRROR_HOME;
    case "/api/market/fx":
      return DEMO_FX;
    case "/api/portfolio/positions":
      return DEMO_POSITIONS;
    case "/api/portfolio/summary":
      return DEMO_PORTFOLIO_SUMMARY;
    case "/api/broker/connections":
      return DEMO_BROKER_CONNECTIONS;
    case "/api/profile":
      return DEMO_PROFILE;
    case "/api/alerts":
      return DEMO_ALERTS;
    case "/api/alerts/unread-count":
      return { count: 2, unread_count: 2 };
    case "/api/behavior/holding-mirror":
      return DEMO_HOLDING_MIRROR;
    case "/api/behavior/concentration-mirror":
      return DEMO_CONCENTRATION_MIRROR;
    case "/api/behavior/profit-loss-mirror":
      return DEMO_PL_MIRROR;
    case "/api/behavior/turnover-mirror":
      return DEMO_TURNOVER_MIRROR;
    case "/api/behavior/averaging-down-mirror":
      return DEMO_AVGDOWN_MIRROR;
    case "/api/pre-trade/list":
      return DEMO_PRETRADE_LIST;
    case "/api/observation-notes/list":
      return DEMO_OBSERVATION_NOTES_LIST;
    case "/api/behavior/friction-outcome":
      return DEMO_FRICTION_OUTCOME;
    // Living CFO Layer-2 + profile depth
    case "/api/profile/persona":
      return DEMO_PERSONA;
    case "/api/profile/pulse":
      return DEMO_PULSE;
    case "/api/profile/rolling-window":
      return DEMO_ROLLING_WINDOW;
    // Portfolio equity/trades + legacy full read
    case "/api/portfolio/trades":
      return DEMO_TRADES;
    case "/api/portfolio":
      return DEMO_FULL_PORTFOLIO;
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
