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

/* ── Persona depth (/profile) — the 8-persona classifier showcase ── */
const _PF = {
  keys: ["holding_period", "turnover", "sector_diversity", "ticker_diversity", "hold_variance", "loss_cut_discipline", "declared_risk", "conviction_stability", "feedback_engagement"],
  labels: ["평균 보유기간", "매매 회전율", "섹터 분산", "종목 다양성", "보유기간 편차", "손절 규율", "선언한 위험 감내", "확신 안정성", "피드백 반응도"],
  observed: [0.55, 0.15, 0.85, 0.8, 0.3, 0.6, 0.5, 0.7, 0.6],
  centroid: [0.5, 0.2, 0.72, 0.72, 0.35, 0.62, 0.55, 0.68, 0.6],
  weight: [0.12, 0.14, 0.12, 0.1, 0.08, 0.12, 0.12, 0.1, 0.1],
};
const DEMO_PERSONA_DETAIL = {
  persona: "balanced",
  label: "균형형 CFO",
  tagline: "분산과 보유기간의 균형을 추구하는 관찰 프로파일.",
  confidence: 72,
  window_days: 90,
  data_sparse: false,
  trade_count: 23,
  declared_persona: "growth",
  last_computed_at: "2026-06-18T07:30:00+09:00",
  features: Object.fromEntries(_PF.keys.map((k, i) => [k, _PF.observed[i]])),
  present: Object.fromEntries(_PF.keys.map((k) => [k, 1])),
  ranking: [
    { persona: "balanced", similarity: 0.88 },
    { persona: "growth", similarity: 0.81 },
    { persona: "quant", similarity: 0.74 },
    { persona: "value", similarity: 0.69 },
    { persona: "income", similarity: 0.62 },
    { persona: "daytrader", similarity: 0.55 },
    { persona: "speculator", similarity: 0.48 },
    { persona: "beginner", similarity: 0.31 },
  ],
  breakdown: _PF.keys.map((k, i) => ({
    feature: k, label: _PF.labels[i], value: _PF.observed[i], centroid: _PF.centroid[i],
    closeness: +(1 - Math.abs(_PF.observed[i] - _PF.centroid[i])).toFixed(2), weight: _PF.weight[i],
  })),
};
const DEMO_PERSONA_BENCHMARK = {
  available: true, persona: "balanced", persona_label: "균형형", window_days: 90,
  stats: {
    avg_cagr: 0.142, avg_sharpe: 1.05, median_holding_days: 34, win_rate: 0.58, max_drawdown_avg: 0.12,
    most_held_sectors: [{ sector: "Technology", share: 0.41 }, { sector: "Consumer Discretionary", share: 0.28 }, { sector: "Financials", share: 0.16 }],
    common_mistakes: [{ label: "급등 추격 매수", count: 12 }, { label: "손절 지연", count: 8 }],
    comparison_to_all: { avg_cagr_all: 0.108, avg_sharpe_all: 0.82, median_holding_days_all: 21 },
    framing: "균형형은 분산과 보유기간에서 전체 평균을 상회합니다.",
  },
};
const _pb = (label: string, c: number, s: number, d: number) => ({ available: true, label, stats: { avg_cagr: c, avg_sharpe: s, median_holding_days: d } });
const DEMO_PERSONA_BENCHMARK_ALL = {
  window_days: 90,
  personas: {
    growth: _pb("성장형", 0.165, 1.1, 28), value: _pb("가치형", 0.121, 0.95, 96),
    balanced: _pb("균형형", 0.142, 1.05, 34), income: _pb("수익형", 0.098, 0.88, 120),
    quant: _pb("퀀트형", 0.151, 1.22, 18), speculator: _pb("투기형", 0.062, 0.41, 6),
    daytrader: _pb("단타형", 0.044, 0.35, 1),
    beginner: { available: false, label: "입문형", reason: "insufficient_group_size" },
  },
};
const DEMO_PROFILE = {
  profile: { profile_type: "growth", risk_tolerance: "moderate", tagline: "성장 가능성에 무게를 두고 관찰합니다." },
};

/* ── CFO archive (/reports) ── */
const DEMO_ARTIFACTS_LIST = {
  total: 6, unread_count: 2,
  artifacts: [
    { id: 1, type: "weekly_memo", title: "주간 메모 · 6월 3주", subtitle: "이번 주 당신의 거울", period_label: "2026-W25", sent_at: "2026-06-16T08:00:00+09:00", opened_at: null, has_file: true },
    { id: 2, type: "living_mirror", title: "리빙 미러 · 선언 vs 관찰", subtitle: "성장형 → 균형형 영역 이동", period_label: "2026-06", sent_at: "2026-06-14T08:00:00+09:00", opened_at: "2026-06-14T09:12:00+09:00", has_file: true },
    { id: 3, type: "risk_report", title: "리스크 리포트 · 7-Layer", subtitle: "posture: attentive", period_label: "2026-W24", sent_at: "2026-06-09T08:00:00+09:00", opened_at: "2026-06-09T20:00:00+09:00", has_file: true },
    { id: 4, type: "monthly_brag", title: "월간 브래그 · 5월", subtitle: "+8.2% · 균형 잡힌 한 달", period_label: "2026-05", sent_at: "2026-06-01T08:00:00+09:00", opened_at: "2026-06-01T08:30:00+09:00", has_file: true },
    { id: 5, type: "weekly_memo", title: "주간 메모 · 6월 2주", subtitle: "보유기간이 늘었습니다", period_label: "2026-W24", sent_at: "2026-06-09T08:00:00+09:00", opened_at: "2026-06-09T08:40:00+09:00", has_file: true },
    { id: 6, type: "brag_card", title: "브래그 카드 · NVDA +54.7%", subtitle: "공유용 카드", period_label: "2026-06", sent_at: "2026-06-05T08:00:00+09:00", opened_at: null, has_file: true },
  ],
};
const DEMO_ARTIFACTS_STATS = {
  total: 6, countYtd: 6, countMemos: 2, countBriefs: 2, countBragCards: 1,
  byType: { weekly_memo: 2, living_mirror: 1, risk_report: 1, monthly_brag: 1, brag_card: 1 },
  nextScheduled: { type: "weekly_memo", at: "2026-06-23T08:00:00+09:00" },
  latestIndexedAt: "2026-06-16T08:00:00+09:00",
};

/* ── Morning papers (/market) ── */
const DEMO_EARNINGS = {
  earnings: [
    { ticker: "NVDA", name: "NVIDIA", date: "2026-06-25" },
    { ticker: "AAPL", name: "Apple", date: "2026-07-01" },
    { ticker: "TSLA", name: "Tesla", date: "2026-07-02" },
    { ticker: "005930", name: "삼성전자", date: "2026-07-08" },
    { ticker: "JPM", name: "JPMorgan Chase", date: "2026-07-12" },
    { ticker: "MSFT", name: "Microsoft", date: "2026-07-22" },
  ],
};

/* ── Alerts ── */
const DEMO_ALERTS = {
  unread: 2,
  alerts: [
    { id: 1, kind: "signal", title: "NVDA POSITIVE 신호", body: "거래량 급증 + 50일선 상회", ticker: "NVDA", name: "NVIDIA", signal: "POSITIVE", score: 82, is_read: false, created_at: "2026-06-18T06:50:00+09:00" },
    { id: 2, kind: "risk", title: "집중도 주의", body: "기술 섹터 비중 48%", is_read: false, created_at: "2026-06-17T16:30:00+09:00" },
    { id: 3, kind: "observation", title: "TSLA 변동성 확대", body: "일중 변동성 상위", ticker: "TSLA", name: "Tesla", signal: "POSITIVE", score: 74, is_read: true, read_at: "2026-06-17T10:00:00+09:00", created_at: "2026-06-17T09:30:00+09:00" },
    { id: 4, kind: "system", title: "주간 메모 도착", body: "6월 3주 거울이 준비됐어요", link: "/reports", is_read: true, read_at: "2026-06-16T09:00:00+09:00", created_at: "2026-06-16T08:00:00+09:00" },
    { id: 5, kind: "signal", title: "LLY NEGATIVE 신호", body: "고점 대비 조정", ticker: "LLY", name: "Eli Lilly", signal: "NEGATIVE", score: 43, is_read: true, read_at: "2026-06-15T11:00:00+09:00", created_at: "2026-06-15T07:00:00+09:00" },
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
    { id: 1, intended_ticker: "NVDA", intended_side: "BUY", rationale: "실적 모멘텀 지속 판단, 분할 매수 1차.", status: "proceeded", proceeded_at: "2026-06-15T10:00:00+09:00", cancelled_at: null, observed_context: { signal: "POSITIVE", score: 82, sector: "Technology", vix: 14.2 } },
    { id: 2, intended_ticker: "LLY", intended_side: "SELL", rationale: "고점 대비 조정, 비중 축소 고민.", status: "cancelled", proceeded_at: null, cancelled_at: "2026-06-14T14:00:00+09:00", observed_context: { signal: "NEGATIVE", score: 43, sector: "Healthcare", vix: 14.5 } },
    { id: 3, intended_ticker: "TSLA", intended_side: "BUY", rationale: "변동성 확대, 추격 매수 충동 점검 중.", status: "pending", proceeded_at: null, cancelled_at: null, observed_context: { signal: "POSITIVE", score: 74, sector: "Consumer Discretionary", vix: 14.2 } },
  ],
};

/* ── Discover ── */
const DEMO_DISCOVER = {
  cached: true, cached_at: "2026-06-18T07:30:00+09:00",
  results: [
    { ticker: "MSFT", name: "Microsoft", signal: "POSITIVE", score: 77, price: 498.3, change_pct: 1.3, priority: 1, is_korean: false, currency: "USD", sector: "Technology", already_owned: false, snapshot: {} },
    { ticker: "AVGO", name: "Broadcom", signal: "POSITIVE", score: 71, price: 1820.5, change_pct: 2.0, priority: 2, is_korean: false, currency: "USD", sector: "Technology", already_owned: false, snapshot: {} },
    { ticker: "035720", name: "카카오", signal: "POSITIVE", score: 66, price: 58700, change_pct: 2.4, priority: 3, is_korean: true, currency: "KRW", sector: "Communication", already_owned: false, snapshot: {} },
    { ticker: "000660", name: "SK하이닉스", signal: "NEUTRAL", score: 59, price: 198000, change_pct: 0.6, priority: 4, is_korean: true, currency: "KRW", sector: "Technology", already_owned: false, snapshot: {} },
    { ticker: "UNH", name: "UnitedHealth", signal: "NEUTRAL", score: 54, price: 512.4, change_pct: -0.4, priority: 5, is_korean: false, currency: "USD", sector: "Healthcare", already_owned: false, snapshot: {} },
  ],
};
const DEMO_DISCOVER_MOVERS = {
  region: "us",
  gainers: [{ ticker: "TSLA", name: "Tesla", price: 412.6, change_pct: 3.4 }, { ticker: "AVGO", name: "Broadcom", price: 1820.5, change_pct: 2.0 }, { ticker: "NVDA", name: "NVIDIA", price: 182.5, change_pct: 2.1 }],
  losers: [{ ticker: "LLY", name: "Eli Lilly", price: 742.0, change_pct: -1.8 }, { ticker: "UNH", name: "UnitedHealth", price: 512.4, change_pct: -0.4 }],
};
const DEMO_DISCOVER_SECTORS = [
  { sector: "Technology", d1: 0.9, d5: 2.4, m1: 5.1 },
  { sector: "Consumer Discretionary", d1: 1.2, d5: 1.1, m1: 3.4 },
  { sector: "Financials", d1: 0.4, d5: -0.3, m1: 1.8 },
  { sector: "Healthcare", d1: -0.6, d5: -1.2, m1: -2.1 },
  { sector: "Energy", d1: 0.3, d5: 0.8, m1: 1.0 },
];
const DEMO_DISCOVER_SCREENERS = {
  oversold_rsi: [{ ticker: "LLY", name: "Eli Lilly", metric: "RSI", metric_value: 28.4 }, { ticker: "UNH", name: "UnitedHealth", metric: "RSI", metric_value: 31.2 }],
  highs_52w: [{ ticker: "NVDA", name: "NVIDIA", metric: "52W High", metric_value: 182.5 }, { ticker: "MSFT", name: "Microsoft", metric: "52W High", metric_value: 498.3 }],
  earnings_beats: [{ ticker: "TSLA", name: "Tesla", metric: "Surprise", metric_value: 12.3 }, { ticker: "AVGO", name: "Broadcom", metric: "Surprise", metric_value: 8.1 }],
};
const DEMO_DISCOVER_OVERVIEW = DEMO_MARKET_INDICES.map((b) => ({ name: b.name, symbol: b.ticker, level: b.level, change_pct: b.change_1d_pct, is_stale: false }));

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
    case "/api/market/overview":
      return DEMO_DISCOVER_OVERVIEW;
    case "/api/earnings":
      return DEMO_EARNINGS;
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
    case "/api/profile":
      return DEMO_PROFILE;
    case "/api/profile/persona-detail":
      return DEMO_PERSONA_DETAIL;
    case "/api/profile/persona-benchmark":
      return DEMO_PERSONA_BENCHMARK;
    case "/api/profile/persona-benchmark-all":
      return DEMO_PERSONA_BENCHMARK_ALL;
    case "/api/artifacts/list":
      return DEMO_ARTIFACTS_LIST;
    case "/api/artifacts/stats":
      return DEMO_ARTIFACTS_STATS;
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
    case "/api/discover":
      return DEMO_DISCOVER;
    case "/api/discover/market-overview":
      return DEMO_DISCOVER_OVERVIEW;
    case "/api/discover/movers":
      return DEMO_DISCOVER_MOVERS;
    case "/api/discover/sectors":
      return DEMO_DISCOVER_SECTORS;
    case "/api/discover/screeners":
      return DEMO_DISCOVER_SCREENERS;
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
