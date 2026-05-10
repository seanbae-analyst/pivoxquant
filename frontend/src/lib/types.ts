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
  // `auto_trade_preference` removed 2026-05-10 — autotrade feature was
  // physically deleted 2026-05-05 (legal: 투자일임업 회피, see memory
  // session_2026-05-03). The backend `InvestmentProfile` may still
  // serialize the column, but no frontend surface reads it.
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
  /** ISO 8601 timestamp the backend observed the last `price`. */
  observed_at?: string | null;
}

export interface WatchlistResponse {
  watchlist: WatchlistItem[];
}

/* ── Alerts ── */

export interface AlertItem {
  id: number;
  /**
   * Alert kind/category from `services/serializers.py:serialize_alert`.
   * Examples: "signal", "risk", "system", "observation". May be null
   * for legacy alerts created before the `kind` column existed.
   */
  kind: string | null;
  /** Short headline. Backend falls back to `message` when `title` is empty. */
  title: string;
  /** Long-form body text. Optional — null for short alerts. */
  body: string | null;
  /** Optional deep-link path (e.g. "/settings#capital"). */
  link: string | null;
  /** Legacy message field — backend still emits it for v1 surfaces. */
  message: string | null;
  ticker: string | null;
  /**
   * Company display name (e.g. "Samsung Electronics", "삼성전자", "Apple Inc.").
   * Backend guarantees this is present and non-empty when `ticker` is
   * present — falls back to the ticker itself when the registry can't
   * resolve a name. Null only when `ticker` is null.
   */
  name: string | null;
  signal?: string | null;
  score?: number | null;
  rec_shares?: number | null;
  rec_investment?: number | null;
  read_at?: string | null;
  is_read: boolean;
  created_at: string;
  /**
   * @deprecated Backend never returns this. Use `kind` instead.
   * Kept optional for v1 callers — will be undefined at runtime.
   */
  type?: string;
  /**
   * @deprecated Backend never returns this. Kept optional for v1 callers.
   */
  data?: Record<string, unknown> | null;
}

export interface AlertsResponse {
  alerts: AlertItem[];
  unread?: number;
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

/* ── Morning Brief ── REMOVED 2026-04-29
 * Backend Morning Brief service deprecated. All MorningBrief* types
 * (MorningBriefIndex / MorningBriefPortfolioChange / MorningBriefEvent /
 * MorningBriefContent / MorningBriefResponse / MorningBriefArchiveItem /
 * MorningBriefArchiveResponse) removed in sync with the backend deletion.
 *
 * Note: `ArtifactType` retains the `"morning_brief"` literal (line ~410)
 * so historical artifact rows persisted before the deprecation continue
 * to deserialize without runtime errors.
 */

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
  | "custom"
  // ── Wave 2 (2026-04-29) — backend `_ARTIFACT_DISPATCH` 17/18 type union.
  // Additive only; existing literals retained for archived rows.
  | "brag_card"
  | "self_audit"
  | "risk_board"
  | "year_end_letter"
  | "quarterly_self_report"
  | "kpi_dashboard"
  | "dd_checklist"
  | "dividend_income"
  | "monthly_finance"
  | "burn_rate"
  | "capital_allocation"
  | "credit_rating"
  | "insider_mirror"
  | "portfolio_segment"
  | "pre_trade_checklist"
  | "sp500_backtest";

export interface Artifact {
  id: number;
  type: ArtifactType;
  title: string;
  subtitle?: string | null;
  sent_at: string | null;
  /**
   * Created timestamp. Used as date fallback when `sent_at` is null
   * (e.g., draft artifact not yet emailed). Bug #11 wave 3b — without
   * this, /reports brag card would render "—" instead of a real date.
   */
  created_at?: string | null;
  opened_at: string | null;
  pdf_url?: string | null;
  thumbnail_url?: string | null;
  data_preview?: Record<string, unknown> | null;
  size_bytes?: number | null;
  period_label?: string | null;
  /**
   * True when the backend has rendered a real file on disk for this
   * row (PDF / PNG / HTML). Drives the "Open full memo" CTA — false
   * means we route to the in-app preview shell instead of the
   * download endpoint.
   */
  has_file?: boolean;
}

export interface ArtifactsListResponse {
  artifacts: Artifact[];
  total: number;
  unread_count: number;
}

/* ── Signals v2 (additive — does not modify any v1 type) ──
 *
 * Wire format: POSITIVE / NEGATIVE / NEUTRAL only. Banned vocabulary
 * (BUY/SELL/HOLD/recommend/advice) MUST never reach the client.
 * Backend `routes/signals.py::all()` is responsible for the label
 * mapper; this front-end type just consumes the canonical shape.
 */

export type SignalLabel = "POSITIVE" | "NEGATIVE" | "NEUTRAL";

export interface SignalEntry {
  id?: number | string;
  ticker: string;            // "AAPL", "005930.KS"
  /**
   * Company display name. The legacy `/api/signals` endpoint already
   * sends this on the v1 MemoSignalItem shape, so re-using it is safe.
   * If the field is missing, the v2 page will fall back to the
   * watchlist+positions name resolver and ultimately to the ticker
   * itself (graceful degradation).
   */
  name?: string | null;
  exchange?: string | null;
  signal?: string;           // v1 alias — same value as label
  label?: SignalLabel;
  score?: number;            // v1: 0..100 composite
  strength?: number;         // v2: 0..1 (derived from score / 100)
  rationale?: string | null;
  observed_at?: string | null;
  price?: number | null;
  change_pct?: number | null;
  currency?: "USD" | "KRW";
  is_korean?: boolean;
  sector?: string | null;
  // Backend `routes/signals.py:45` flags entries served from the
  // SignalCache when the underlying data crossed the freshness TTL.
  // Frontend uses this to badge a "STALE" indicator so users can
  // distinguish a fresh observation from a cached one.
  is_stale?: boolean;
}

export interface SignalsResponse {
  signals: SignalEntry[];
  total?: number;
  counts?: { positive: number; negative: number; neutral: number };
  symbols_filtered?: number;
}

export interface SignalFilters {
  labels: Set<SignalLabel>;
  strengthMin: number;   // 0..1
  strengthMax: number;   // 0..1
  symbol: string | null; // exact ticker or null
  // W6-1 (Wave 6 follow-up, 2026-05-09): "all" added so the V2 signals
  // page can opt out of the freshness cutoff. Backend `observed_at` is
  // a cache-write timestamp, so a 24h "today" default silently emptied
  // the list when SignalCache lagged. See signals/_v2/page-v2.tsx
  // DEFAULT_FILTERS comment.
  window: "today" | "7d" | "30d" | "all";
}
