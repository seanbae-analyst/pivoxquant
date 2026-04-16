export interface Position {
  id: number;
  ticker: string;
  shares: number;
  avg_cost: number;
  price: number;
  current_price: number;
  price_display: string;
  pnl_pct: number;
  pnl_krw_pct: number | null;
  buy_fx_rate: number | null;
  cur_fx_rate: number | null;
  krw_cost: number | null;
  krw_value: number | null;
  market_value: number;
  signal: "POSITIVE" | "NEGATIVE" | "NEUTRAL" | "—";
  score: number;
  rec_shares: number;
  rec_investment: number;
  rec_timing: string;
  name: string;
  sector: string;
  currency: "USD" | "KRW";
  is_korean: boolean;
  sell_pct: number;
  sell_timing: string;
  capital_needed: number | null;
  capital_gap: number | null;
  take_profit: number | null;
  stop_loss: number | null;
  tp_pct: number;
  sl_pct: number;
  regime_profile: string;
  regime_label: string;
  regime_label_kr: string;
  priority: number;
}

export interface PortfolioResponse {
  positions: Position[];
  available_capital: number;
  available_capital_krw: number;
  total_value_usd: number;
  total_value_krw: number;
  total_value_all_krw: number;
  fx_rate: number;
}

export interface AnalyticsResponse {
  total_value: number;
  cash: number;
  invested_pct: number;
  sector_allocation: Record<string, number>;
  ann_return_pct?: number;
  ann_vol_pct?: number;
  sharpe_ratio?: number;
  max_drawdown_pct?: number;
}

export interface HistoryPoint {
  date: string;
  value: number;
}

export interface HistoryResponse {
  data: HistoryPoint[];
}

export interface EarningsItem {
  ticker: string;
  name: string;
  date: string;
  signal: string;
  score: number;
}

export interface EarningsResponse {
  earnings: EarningsItem[];
}

/* ── Market ── */

export interface IndexData {
  price: number;
  change_pct: number;
}

export interface YieldCurve {
  t3m: number;
  t5y: number;
  t10y: number;
  t30y: number;
  spread: number;
  inverted: boolean;
}

export interface MarketOverviewResponse {
  macro: {
    sp500: IndexData;
    nasdaq: IndexData;
    dow: IndexData;
    russell2000: IndexData;
    kospi: IndexData;
    kosdaq: IndexData;
    usdkrw: IndexData;
    vix: number;
    treasury_10y: number;
    treasury_5y: number;
    dxy: IndexData;
    eurusd: IndexData;
    oil_wti: IndexData;
    gold: IndexData;
    silver: IndexData;
    btc: IndexData;
    fear_greed: { value: number; label: string };
    yield_curve: YieldCurve;
  };
  gs_view: {
    bias: string;
    bias_note: string;
    themes: string[];
  };
  cached_at: string;
}

export interface CrossAssetItem {
  ticker: string;
  name: string;
  price: number;
  return_1m: number;
  return_3m: number;
  return_6m: number;
  volatility: number;
  sharpe: number;
}

export interface CrossAssetResponse {
  macro_regime: string;
  macro_label: string;
  macro_kr: string;
  strongest: string;
  weakest: string;
  ranking: CrossAssetItem[];
}

export interface VixStrategyResponse {
  vix: number;
  vix_20d_avg: number;
  vix_trend: string;
  vix_percentile: number;
  regime: string;
  color: string;
  exposure: number;
  action: string;
  action_kr: string;
}

export interface SectorItem {
  sector: string;
  price: number;
  change_pct: number;
  volume: number;
  top_movers: string[];
}

/* ── Intraday ── */

export interface SignalMsg {
  type: "bullish" | "bearish";
  msg: string;
  msg_kr: string;
}

export interface DayTradeResult {
  ticker: string;
  name: string;
  price: number;
  change_pct: number;
  score: number;
  signal: string;
  is_korean: boolean;
  currency: string;
  signals: SignalMsg[];
  rsi: number;
  vol_ratio: number;
  vwap: number | null;
  take_profit: number;
  stop_loss: number;
  tp_pct: number;
  sl_pct: number;
  trailing_stop_pct: number;
  atr: number;
  is_held?: boolean;
  regime_profile?: string;
}

export interface DayTradeScanResponse {
  results: DayTradeResult[];
  count: number;
}

/* ── Scanner ── */

export interface ScanResult {
  ticker: string;
  name: string;
  signal: string;
  score: number;
  price: number;
  change_pct: number;
  signals: SignalMsg[];
  snapshot: Record<string, number | string | null>;
  take_profit: number;
  stop_loss: number;
  is_korean: boolean;
}

export interface DiscoverResult {
  ticker: string;
  name: string;
  signal: string;
  score: number;
  price: number;
  change_pct: number;
  priority: number;
  is_korean: boolean;
  currency: string;
  sector: string;
  already_owned: boolean;
  take_profit: number;
  stop_loss: number;
  rec_shares: number;
  rec_investment: number;
  rec_timing: string;
  needs_capital?: boolean;
  snapshot: Record<string, number | string | null>;
}

export interface DiscoverResponse {
  results: DiscoverResult[];
  cached: boolean;
  cached_at?: string;
}

// ── Investment Profile ──
export interface InvestmentProfile {
  profile_type: string;
  experience_level: string;
  investment_goal: string;
  risk_tolerance: number;
  time_horizon: string;
  preferred_markets: string;
  preferred_sectors: string;
  auto_trade_preference: string;
  daily_time: string;
  tech_weight: number;
  fund_weight: number;
  news_weight: number;
  tp_min: number;
  tp_max: number;
  sl_min: number;
  sl_max: number;
  max_positions: number;
  buy_threshold: number;
  sell_threshold: number;
  ai_coaching_style: string;
  alert_frequency: string;
}

export interface ProfileResponse {
  profile: InvestmentProfile | null;
  has_profile: boolean;
  changes_left?: number;
  subscription_tier?: string;
}

export interface QuestionOption {
  value: string | number;
  label: string;
  label_kr: string;
  icon?: string;
}

export interface Question {
  id: string;
  question: string;
  question_kr: string;
  type?: string;
  options: QuestionOption[];
}

export interface QuestionnaireResponse {
  questions: Question[];
}

/* ── AI ── */

export interface AiStatusResponse {
  available: boolean;
}

export interface AiCoachingResponse {
  insight: string;
  insight_kr: string;
}

export interface AiSwotResponse {
  swot: string;
  swot_kr: string;
}

export interface AiCommentaryResponse {
  commentary: string;
  commentary_kr: string;
}

export interface AiCompetitorResponse {
  analysis: string;
  analysis_kr: string;
}

export interface AiSectorTrendResponse {
  trend: string;
  trend_kr: string;
  sector: string;
}

export interface AiMorningSummaryResponse {
  summary: string;
  summary_kr: string;
}

export interface AiChatMessage {
  role: "user" | "assistant";
  content: string;
}

/* ── Portfolio Share ── */

export interface ShareTokenResponse {
  token: string;
  expires_at: string;
  share_url: string;
}

/** Public portfolio position — sensitive fields stripped server-side */
export interface SharedPosition {
  ticker: string;
  name: string;
  sector: string;
  shares: number;
  avg_cost: number;
  price: number;
  price_display: string;
  pnl_pct: number;
  market_value: number;
  signal: "POSITIVE" | "NEGATIVE" | "NEUTRAL" | "—";
  score: number;
  currency: "USD" | "KRW";
  is_korean: boolean;
  tp_pct: number;
  sl_pct: number;
}

export interface SharedPortfolioResponse {
  owner_name: string;
  positions: SharedPosition[];
  total_value_usd: number;
  total_value_all_krw: number;
  avg_score: number;
  total_pnl_pct: number;
  buy_count: number;
  sell_count: number;
  fx_rate: number;
  created_at: string;
  expires_at: string;
}

/* ── Watchlist ── */

export interface WatchlistItem {
  id: number;
  ticker: string;
  name: string;
  price: number;
  change_pct: number;
  signal: string;
  score: number;
  currency: "USD" | "KRW";
  is_korean: boolean;
  added_at: string;
}

export interface WatchlistResponse {
  watchlist: WatchlistItem[];
}

/* ── Alerts ── */

export interface AlertItem {
  id: number;
  type: string;
  message: string;
  ticker: string | null;
  data: Record<string, unknown> | null;
  is_read: boolean;
  created_at: string;
}

export interface AlertsResponse {
  alerts: AlertItem[];
}

/* ── Search ── */

export interface SearchResult {
  ticker: string;
  name: string;
  exchange?: string;
  currency: string;
  is_korean?: boolean;
}

/* ── Lookup ── */

export interface LookupResult {
  ticker: string;
  name: string;
  price: number;
  change_pct?: number;
  exchange?: string;
  currency: string;
  ok?: boolean;
  price_display?: string;
  is_korean?: boolean;
}

/* ── Morning Brief ── */

export interface MorningBriefIndex {
  price: number;
  change_pct: number;
}

export interface MorningBriefPortfolioChange {
  ticker: string;
  change_pct: number;
  direction: "up" | "down";
}

export interface MorningBriefEvent {
  ticker: string;
  event_type: string;
  event_time: string;
  description: string;
}

export interface MorningBriefContent {
  market_summary: {
    sp500?: MorningBriefIndex;
    nasdaq?: MorningBriefIndex;
    dow?: MorningBriefIndex;
    kospi?: MorningBriefIndex;
    kosdaq?: MorningBriefIndex;
    vix?: MorningBriefIndex;
  };
  portfolio_changes: MorningBriefPortfolioChange[];
  events: MorningBriefEvent[];
  insight: string;
}

export interface MorningBriefResponse {
  available: boolean;
  brief?: MorningBriefContent;
  message?: string;
  generated_at?: string;
  date?: string;
}

export interface MorningBriefArchiveItem {
  date: string;
  created_at?: string;
  content: MorningBriefContent;
}

export interface MorningBriefArchiveResponse {
  ok: boolean;
  count: number;
  briefs: MorningBriefArchiveItem[];
}

/* ── Counterfactual ("What-If") Simulator ── */

export type RecurringMode = "none" | "monthly" | "weekly" | null;

export interface WhatIfChartPoint {
  date: string;
  price: number;
  invested: number;
  value: number;
  buy_point?: boolean;
}

export interface WhatIfMilestone {
  date: string;
  label: string;
  label_kr?: string;
  type: "multiplier" | "threshold" | "ath" | "drawdown";
  value: number | null;
}

export interface WhatIfBenchmark {
  ticker: string;
  end_value: number;
  return_pct: number;
  total_invested?: number;
  diff_value?: number;
  diff_pct?: number;
}

/**
 * Backend shape is flat (no nested input/result) — see
 * routes/counterfactual.py:625. Keep this 1:1 with the JSON keys.
 */
export interface WhatIfSuccessResponse {
  success: true;
  ticker: string;
  start_date: string;
  first_buy_date: string;
  end_date: string;
  recurring: "none" | "weekly" | "monthly";
  recurring_amount?: number;
  amount_initial: number;
  total_invested: number;
  end_value: number;
  profit_loss: number;
  return_pct: number;
  annualized_return_pct: number | null;
  duration_days: number;
  shares_total: number;
  first_buy_price: number;
  last_price: number;
  currency: "USD" | "KRW";
  chart_data: WhatIfChartPoint[];
  milestones: WhatIfMilestone[];
  benchmark: WhatIfBenchmark | null;
  disclaimers: string[];
}

export interface WhatIfErrorResponse {
  success: false;
  error_code:
    | "TICKER_NOT_FOUND"
    | "DATE_BEFORE_LISTING"
    | "DATE_IN_FUTURE"
    | "AMOUNT_OUT_OF_RANGE"
    | "DATA_UNAVAILABLE"
    | string;
  message: string;
  suggestion?: {
    field: string;
    value: string;
    reason?: string;
  };
}

export type WhatIfResponse = WhatIfSuccessResponse | WhatIfErrorResponse;

/* ── FX Rate ── */

/**
 * Response shape for GET /api/market/fx.
 * Backend scheduler refreshes the underlying rate every 1 minute; frontend
 * should poll at ~30s intervals with `useFxRate()` to stay near-realtime.
 */
export interface FxRateResponse {
  ok: true;
  usd_krw: number;
  /** ISO-8601 UTC timestamp of the last successful upstream fetch. Null when never fetched. */
  last_updated: string | null;
  /** Unix epoch timestamp (float) of the last successful fetch. 0 when never fetched. */
  last_updated_ts: number;
  /** Seconds since last successful fetch. -1 when never fetched. */
  age_seconds: number;
  /** True when the cached rate is older than 10 minutes (degraded display recommended). */
  is_stale: boolean;
  /** Deprecated alias for is_stale — kept for backward compatibility. */
  stale: boolean;
  /** Expected refresh cadence hint (seconds). */
  ttl_seconds: number;
}
