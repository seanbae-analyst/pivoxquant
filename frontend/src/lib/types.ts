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

/* ── Discover ── */

export interface DiscoverResult {
  ticker: string;
  name: string;
  signal: string;
  score: number;
  price: number;
  price_display?: string;
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

/* ── AI ── */

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

/* ── Watchlist ── */

export interface WatchlistItem {
  id: number;
  ticker: string;
  name: string;
  note?: string;
  price: number;
  /** Alias of `price` (backend serializer sends both). */
  last_price?: number;
  change_pct: number;
  /** Alias of `change_pct` (backend serializer sends both). */
  change_1d_pct?: number;
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
  /**
   * Company display name (e.g. "Samsung Electronics", "삼성전자", "Apple Inc.").
   * Backend guarantees this is present and non-empty when `ticker` is
   * present — falls back to the ticker itself when the registry can't
   * resolve a name. Null only when `ticker` is null.
   */
  name: string | null;
  data: Record<string, unknown> | null;
  is_read: boolean;
  created_at: string;
}

export interface AlertsResponse {
  alerts: AlertItem[];
  unread?: number;
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
  /** Company display name. Backend guarantees non-empty (falls back to ticker). */
  name: string;
  change_pct: number;
  direction: "up" | "down";
}

export interface MorningBriefEvent {
  ticker: string;
  /** Company display name. Backend guarantees non-empty (falls back to ticker). */
  name: string;
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

/* ── Growth OS ── */

export interface GrowthScoreEntry {
  date: string;
  activity: number;
  reflection: number;
  total: number;
  streak: number;
}

export interface GrowthBriefing {
  priorities: string[];
  motivation: string;
}

export interface GrowthReflection {
  id: number;
  questions: string[];
  answers: string[] | null;
  mood: number | null;
}

export interface GrowthTodayResponse {
  date: string;
  briefing: GrowthBriefing | null;
  reflection: GrowthReflection | null;
  score: {
    activity: number;
    reflection: number;
    total: number;
    streak: number;
  } | null;
}

export interface GrowthWeeklyReport {
  id: number;
  week_start: string;
  summary: string;
  patterns: string[];
  growth_areas: string[];
  next_week_suggestions: string[];
  week_score: number;
}

/* ── Artifact / Reports Archive ── */

export type ArtifactType =
  | "weekly_memo"
  | "morning_brief"
  | "earnings_prebrief"
  | "monthly_brag"
  | "quarterly_review"
  | "risk_report"
  | "custom";

export interface Artifact {
  id: number;
  type: ArtifactType;
  title: string;
  subtitle?: string | null;
  sent_at: string;
  opened_at: string | null;
  pdf_url?: string | null;
  thumbnail_url?: string | null;
  data_preview?: Record<string, unknown> | null;
  size_bytes?: number | null;
  period_label?: string | null;
}

export interface ArtifactsListResponse {
  artifacts: Artifact[];
  total: number;
  unread_count: number;
}
