/**
 * Backend position row shape — emitted by /api/portfolio + /api/portfolio/positions.
 *
 * 2026-05-15 (autonomous wave sweep-3): historically this type
 * declared only snake_case fields, matching the legacy /api/portfolio
 * payload (routes/portfolio.py line 227). The newer /api/portfolio/
 * positions alias (line 826 _build_positions_list) emits camelCase
 * (`avgCost / current / purchaseDate / isKorean`). Consumers reading
 * `p.current_price` against the new payload silently produced
 * undefined → cur=0 → KRW 0/USD 0 rendering across /portfolio, /home v1/v2,
 * and the sector-allocation donut (bug-hunter P0/P2 findings).
 *
 * Both shapes are now declared so the next consumer doesn't repeat
 * the regression. Defensive reads should use:
 *   const cur = p.current ?? p.current_price ?? 0;
 *   const avg = p.avgCost ?? p.avg_cost ?? 0;
 */
export interface Position {
  id: number;
  ticker: string;
  shares: number;
  avg_cost: number;
  /** Camel-case mirror of `avg_cost` (emitted by /api/portfolio/positions). */
  avgCost?: number;
  price: number;
  current_price: number;
  /** Camel-case mirror of `current_price` (emitted by /api/portfolio/positions). */
  current?: number;
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
  // 2026-05-17 (PR #413): GET /api/profile surfaces global email opt-out
  // flags so settings/_v2 can hydrate the "email delivery" toggle from
  // server truth, not just localStorage. Both optional so older
  // deployments without the surface still type-check.
  email_opt_out?: boolean;
  email_opt_out_earnings?: boolean;
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
  /**
   * 52-week price range `[low, high]`. Backend emits KRW=integer / USD=2dp,
   * or `null` when either bound is missing (routes/watchlist.py:74-87 — Bug
   * #9 wire-up 2026-05-13). Frontend renders em-dash on null instead of
   * fabricating "$0.00 - $0.00".
   */
  range_52w?: [number, number] | null;
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

/* ── Pre-Trade Journal (decision-reflection feed) ── */

/**
 * One pre-trade reflection row from `GET /api/pre-trade/list`.
 *
 * Additive only — mirrors routes/pre_trade.py serialization. The
 * `intended_side` wire field still carries the legacy BUY/SELL tokens; the
 * UI MUST translate it through `@/lib/pre-trade` (sideLabel / sideFromWire)
 * before display — bare BUY/SELL labels are banned under KCMA §17. The
 * frontend renders "진입(ENTRY) / 정리(EXIT)".
 *
 * `status` is the row lifecycle: pending → ready → proceeded | cancelled.
 * `proceeded_at` / `cancelled_at` are terminal stamps ("user finished
 * thinking"); the backend never executes an order.
 */
export interface PreTradeReflection {
  id: number;
  intended_ticker: string;
  /** Server-resolved company name (삼성전자) — lead with this, ticker as sub. */
  intended_name?: string | null;
  /** Legacy wire token (BUY/SELL/null). NEVER render raw — see @/lib/pre-trade. */
  intended_side: string | null;
  intended_shares: number | null;
  rationale: string;
  /** Snapshot of the 7-question devil's-advocate reflection (free text). */
  devil_advocate_seen: string | null;
  market_volatility_at_request: string | null;
  cooldown_started_at: string | null;
  cooldown_ends_at: string | null;
  /** ISO timestamp the user chose to proceed, else null. */
  proceeded_at: string | null;
  /** ISO timestamp the user chose to cancel, else null. */
  cancelled_at: string | null;
  auto_extended_reason: string | null;
  seconds_remaining: number;
  status: "pending" | "ready" | "proceeded" | "cancelled";
}

export interface PreTradeJournalResponse {
  ok: boolean;
  disclaimer?: string | null;
  reflections: PreTradeReflection[];
}

/* ────────────────────────────────────────────────────────────────────────
 * Holding-Mirror — disposition-effect "mirror" (NOT a score / diagnosis).
 *
 * GET /api/behavior/holding-mirror returns factual holding-period statistics
 * computed from the user's OWN closed trade pairs over a trailing window.
 * The frontend renders it as a neutral 2-up comparison: average holding
 * period of positions sold while up vs. sold while down. No judgement, no
 * grade, no "bias" label is ever surfaced (자본시장법 / PIPA §23 posture).
 *
 * Backend contract is locked 1:1 with this shape — do NOT rename keys.
 *   - `sufficient_data` false  → too few closed pairs to show an average.
 *   - `one_sided` true         → all closed pairs fell on one side (winners
 *                                or losers only); the empty side renders an
 *                                em-dash sentinel rather than a fabricated 0.
 * ────────────────────────────────────────────────────────────────────── */
export interface HoldingMirrorExample {
  display_name: string;
  ticker: string;
  pnl_pct: number | null;
  hold_days: number;
  sell_at: string | null;
}

export interface HoldingMirrorSide {
  count: number;
  median_hold_days: number | null;
  mean_hold_days: number | null;
  examples: HoldingMirrorExample[];
}

export interface HoldingMirrorResponse {
  ok: boolean;
  disclaimer?: string;
  /** Trailing window label, e.g. "최근 90일" / "Last 90 days". */
  period?: string;
  sufficient_data: boolean;
  one_sided: boolean;
  total_closed_pairs: number;
  /**
   * A side is `null` when the backend has no qualifying pairs for it — both
   * sides are `null` when `sufficient_data` is false, and exactly one is
   * `null` when `one_sided` is true (services/profile/holding_mirror.py).
   * The renderer treats a null side as an em-dash sentinel, never a 0.
   */
  winners: HoldingMirrorSide | null;
  losers: HoldingMirrorSide | null;
}

/* ────────────────────────────────────────────────────────────────────────
 * Concentration-Mirror — factual cost-basis composition "mirror".
 *
 * GET /api/behavior/concentration-mirror returns how much of the user's OWN
 * open portfolio (at 평균매입가 / average cost, NOT market price) sits in their
 * single largest holding. It is purely observational — a description of the
 * current composition stated as a fact: "보유 N개 중 X가 67.3%". No score,
 * grade, index, ratio, or "집중 위험 / 과집중 / 분산 필요" label is ever
 * surfaced (자본시장법 / PIPA §23 / DECISIONS.md AI 점수화 폐기). The user reads
 * the fact and draws their own conclusion (research_cbt_bias_model.md —
 * 사실만 비추고 재구성은 사용자).
 *
 * Backend contract is locked 1:1 with this shape (routes/behavior.py
 * /concentration-mirror + services/behavior/concentration_mirror.py) — do NOT
 * rename keys.
 *   - `sufficient_data` false  → no open position with a positive cost basis;
 *                                `max_weight_pct` / `largest_ticker` are null
 *                                and `ticker_count` is 0. Renders the calm
 *                                empty state (no call-to-action).
 *   - `cost_basis_note`        → the "평균매입가 기준 (시장가 아님)" clarifier the
 *                                backend supplies verbatim (oversight guard).
 * ────────────────────────────────────────────────────────────────────── */
export interface ConcentrationMirrorResponse {
  ok: boolean;
  disclaimer?: string;
  sufficient_data: boolean;
  /** Number of open positions counted (positive shares × positive avg cost). */
  ticker_count: number;
  /** Largest holding's share of the portfolio at cost basis, rounded to 0.1%. */
  max_weight_pct: number | null;
  /** Display NAME of the largest holding ("삼성전자"), never a naked code. */
  largest_ticker: string | null;
  /** Backend-supplied clarifier, e.g. "평균매입가 기준 (시장가 아님)". */
  cost_basis_note: string;
}

/* ────────────────────────────────────────────────────────────────────────
 * Profit/Loss-Mirror — factual hold-day + return "mirror".
 *
 * GET /api/behavior/profit-loss-mirror splits the user's OWN closed FIFO
 * round trips by the sign of the realised return on the SELL leg, and reports
 * how long each side was held and by what percent it closed. It is purely
 * observational — raw numbers, never a verdict on any individual trade. No
 * score, grade, index, ratio, or "처분효과 / 편향 / 과속 / 지연 / 개선" label is
 * ever surfaced (자본시장법 / PIPA §23 / DECISIONS.md AI 점수화 폐기). The user
 * reads the fact and draws their own conclusion (research_cbt_bias_model.md —
 * 사실만 비추고 재구성은 사용자).
 *
 * Backend contract is locked 1:1 with this shape (routes/behavior.py
 * /profit-loss-mirror + services/behavior/profit_loss_mirror.py) — do NOT
 * rename keys.
 *   - `sufficient_data` false → too few classified (non-break-even) pairs;
 *                               both sides are null.
 *   - `one_sided` true        → all classified pairs realised a profit OR a
 *                               loss only; the empty side is null (renders an
 *                               em-dash sentinel, never a fabricated 0).
 *   - stop_loss return %      → keeps its NEGATIVE sign (raw fact, never abs).
 *   - No `examples` array — the disposition (holding) mirror already exposes
 *                               examples on the same page.
 * ────────────────────────────────────────────────────────────────────── */
export interface ProfitLossMirrorTakeProfitSide {
  count: number;
  median_hold_days: number | null;
  mean_hold_days: number | null;
  /** Median realised gain on profit-taking sells (positive). */
  median_gain_pct: number | null;
  mean_gain_pct: number | null;
}

export interface ProfitLossMirrorStopLossSide {
  count: number;
  median_hold_days: number | null;
  mean_hold_days: number | null;
  /** Median realised loss on loss-realising sells (NEGATIVE — raw fact). */
  median_loss_pct: number | null;
  mean_loss_pct: number | null;
}

export interface ProfitLossMirrorResponse {
  ok: boolean;
  disclaimer?: string;
  /** Trailing window label echoed by the route ("all" / "30d"). */
  period?: string;
  sufficient_data: boolean;
  one_sided: boolean;
  total_closed_pairs: number;
  /** Null when no profit-realising pair, or when sufficient_data is false. */
  take_profit: ProfitLossMirrorTakeProfitSide | null;
  /** Null when no loss-realising pair, or when sufficient_data is false. */
  stop_loss: ProfitLossMirrorStopLossSide | null;
}

/* ────────────────────────────────────────────────────────────────────────
 * Turnover Mirror — factual trade-activity reflection (GET
 * /api/behavior/turnover-mirror + services/behavior/turnover_mirror.py). A
 * neutral count of the user's own BUY/SELL fills plus per-currency gross
 * traded value. It is purely observational — raw counts and value sums,
 * never a verdict on activity level.
 *
 * There is deliberately NO turnover ratio / percentage: a ratio needs a
 * live portfolio-valuation denominator (breaking determinism) and mixing
 * KRW/USD market values into one figure is meaningless. So we report
 * absolute frequency + per-currency gross value only. No score, grade,
 * index, ratio, or "회전율 / 과잉거래 / 과속" label is ever surfaced
 * (자본시장법 / PIPA §23 / DECISIONS.md AI 점수화 폐기). Efficacy statistics
 * (Barber&Odean, KCMI 회전율, etc.) are NEVER cited.
 *
 * Backend contract is locked 1:1 with this shape — do NOT rename keys.
 *   - `sufficient_data` false → fewer than the minimum fills in the window;
 *                               count fields are null, by_currency is [].
 *   - per-currency `gross_value` is the sum of total_value for that
 *                               currency, NEVER FX-converted into a mix.
 *   - `median_hold_days` / `mean_hold_days` are null when no round trip
 *                               closed in the window.
 * ────────────────────────────────────────────────────────────────────── */
export interface TurnoverMirrorCurrencyRow {
  currency: string;
  /** Sum of total_value for this currency (raw, not FX-converted). */
  gross_value: number;
  trade_count: number;
}

export interface TurnoverMirrorResponse {
  ok: boolean;
  disclaimer?: string;
  /** Trailing window label echoed by the route ("all" / "30d"). */
  period?: string;
  /** Window length in days the backend applied (null = all history). */
  period_days: number | null;
  sufficient_data: boolean;
  /** Total BUY + SELL fills in the window. */
  trade_count: number;
  /** Null when sufficient_data is false. */
  buy_count: number | null;
  sell_count: number | null;
  /** Per-currency gross traded value; [] when sufficient_data is false. */
  by_currency: TurnoverMirrorCurrencyRow[];
  /** Null when no round trip closed in the window. */
  median_hold_days: number | null;
  mean_hold_days: number | null;
}

/* ── Averaging-Down Mirror (GET /api/behavior/averaging-down-mirror) ──
 *   A neutral, retrospective COUNT of follow-on buys (adds to an
 *   already-held position) and how many landed below / above / at the
 *   position's running average cost at the instant of that add.
 *
 *   Invariants:
 *   - INTEGER COUNTS ONLY — never a ratio / percentage / score / grade /
 *     label. No "물타기" / judgement vocabulary anywhere.
 *   - Counts are `null` when `sufficient_data` is false (too few follow-on
 *     adds to mirror stably); `by_ticker` is `[]`.
 *   - Same-ticker price comparison only → no FX conversion involved.
 * ──────────────────────────────────────────────────────────────────── */
export interface AveragingDownMirrorTickerRow {
  ticker: string;
  /** Display name when known; null falls back to the ticker at render. */
  name: string | null;
  follow_on: number;
  below_avg: number;
  above_avg: number;
}

export interface AveragingDownMirrorResponse {
  ok: boolean;
  disclaimer?: string;
  /** Trailing window label echoed by the route ("all" / "30d"). */
  period?: string;
  /** Window length in days the backend applied (null = all history). */
  period_days: number | null;
  sufficient_data: boolean;
  /** Total follow-on adds in the window; null when sufficient_data is false. */
  follow_on_count: number | null;
  /** Adds priced below the running average; null when insufficient. */
  below_avg_count: number | null;
  /** Adds priced above the running average; null when insufficient. */
  above_avg_count: number | null;
  /** Adds priced at the running average (±epsilon); null when insufficient. */
  flat_count: number | null;
  /** Neutral per-ticker breakdown; [] when sufficient_data is false. */
  by_ticker: AveragingDownMirrorTickerRow[];
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
  | "sp500_backtest"
  | "living_mirror";

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

/* ──────────────────────────────────────────────────────────────────────────
 * Customer support — 고객문의센터 + AI 고객지원 (2026-05-26).
 *
 * Additive only. Backend contract locked in routes/support.py + endpoints.ts
 * `API.support`. The AI chat surface is "AI 고객지원" (customer-support
 * assistant) — never an investment coach (자본시장법). No BUY/SELL/HOLD or
 * 추천/조언 vocabulary round-trips through these shapes.
 * ────────────────────────────────────────────────────────────────────────── */

/** Inquiry category — billing(결제/환불) / account(계정) / technical(기술) / other(기타). */
export type SupportCategory = "billing" | "account" | "technical" | "other";

/** Inquiry status — open(접수) / answered(답변완료) / closed. */
export type SupportStatus = "open" | "answered" | "closed";

/** Row shape returned by GET /api/support/inquiries (list). */
export interface SupportInquiryListItem {
  id: number;
  category: SupportCategory;
  subject: string;
  status: SupportStatus;
  created_at: string;
  answered_at: string | null;
  has_reply: boolean;
}

/** Full record returned by GET /api/support/inquiries/:id (detail). */
export interface SupportInquiryDetail {
  id: number;
  category: SupportCategory;
  subject: string;
  body: string;
  status: SupportStatus;
  admin_reply: string | null;
  created_at: string;
  answered_at: string | null;
  has_reply: boolean;
}

/** GET /api/support/inquiries → list envelope. */
export interface SupportInquiriesResponse {
  inquiries: SupportInquiryListItem[];
}

/** POST /api/support/inquiries body. */
export interface SupportInquiryCreateBody {
  category: SupportCategory;
  subject: string;
  body: string;
}

/** POST /api/support/inquiries → 201 created envelope. */
export interface SupportInquiryCreateResponse {
  id: number;
  status: SupportStatus;
  created_at: string;
}

/** One conversation turn passed back to POST /api/support/chat (history). */
export interface SupportChatMessage {
  role: "user" | "assistant";
  content: string;
}

/** POST /api/support/chat body. history is capped at 10 turns server-side. */
export interface SupportChatRequest {
  message: string;
  history?: SupportChatMessage[];
}

/**
 * POST /api/support/chat → reply envelope. When `escalated` is true and
 * `inquiry_id` is a positive number, the bot opened a 1:1 inquiry on the
 * user's behalf (surface a "내 문의함에서 보기" link).
 */
export interface SupportChatResponse {
  reply: string;
  escalated: boolean;
  inquiry_id: number | null;
}

/**
 * Admin view of an inquiry (GET /api/support/admin/inquiries). Extends the
 * detail record with operator-only fields. Reuses SupportInquiryDetail so the
 * shared fields stay in lock-step with the user-facing detail contract.
 */
export interface SupportAdminInquiry extends SupportInquiryDetail {
  /** Owning user's id (operator-only). */
  user_id: number;
  /** Owning user's email at submit time (operator-only). */
  email_snapshot: string;
}

/** GET /api/support/admin/inquiries → list envelope. */
export interface SupportAdminInquiriesResponse {
  inquiries: SupportAdminInquiry[];
}

/** POST /api/support/admin/inquiries/:id/reply body. */
export interface SupportAdminReplyBody {
  reply: string;
}

// ── Viral loop (backend commit 7a57a9da) ──────────────────────────────────

/** Whitelisted funnel events accepted by POST /api/track. */
export type FunnelEvent =
  | "landing_view"
  | "signup"
  | "onboarding_done"
  | "artifact_opened"
  | "share_clicked"
  | "referral_signup";

/** POST /api/track body. All fields except `event` optional + bounded. */
export interface TrackEventBody {
  event: FunnelEvent;
  channel?: string; // ≤40
  ref_code?: string; // ≤16
  anon_id?: string; // ≤64
  meta?: Record<string, string | number | boolean>; // keys ≤12 / vals ≤200
}

/**
 * `data` payload inside the brag-card preview response
 * (POST /api/artifacts/brag-card/preview → { ok, data, png_base64, html }).
 * Mirrors `BragCardContext.to_dict()` on the Python side. Snapshot fields
 * (`mode` / `empty_reason` / `snapshot_tickers`) drive the empty-portfolio
 * Activation surface in onboarding.
 */
export interface BragCardPreviewData {
  user_name: string;
  referral_code: string;
  month_label: string;
  month_label_long: string;
  return_pct: number | null;
  trade_count: number;
  best_ticker: string | null;
  best_return_pct: number | null;
  anonymous: boolean;
  is_empty: boolean;
  share_token: string | null;
  mode: "trades" | "snapshot";
  empty_reason:
    | "no_closed_trades_holdings"
    | "no_closed_trades_watchlist"
    | "no_activity"
    | null;
  snapshot_tickers: string[];
}

/** Full envelope from POST /api/artifacts/brag-card/preview. */
export interface BragCardPreviewResponse {
  ok: boolean;
  data: BragCardPreviewData;
  png_base64: string | null;
  html: string;
}

/**
 * GET /api/card/<share_token> — public OG landing payload.
 * 404 (private/missing) surfaces as a thrown ApiError, never this shape.
 * `summary_safe` is server-generated §101-safe copy (factual + generic).
 */
export interface PublicCardResponse {
  ok: boolean;
  owner_display_name: string;
  card_image_url: string | null;
  summary_safe: string;
  month_label: string | null;
  referral_code: string | null;
}

/**
 * POST /api/artifacts/living-mirror/generate — persists the caller's persona
 * capstone PDF and returns its id + the render context payload.
 *
 * `data` is the LivingMirrorService context (JSON-serialisable). We only type
 * the fields the UI surfaces; the full shape carries radar/gap/trajectory the
 * PDF renders. Stage drives the post-generate copy:
 *   new        — declared radar only (행동/궤적 빈칸)
 *   observed   — declared vs observed overlay + gap rows
 *   trajectory — overlay + drift narrative + sparkline
 * No score / grade / percentile / rank ever appears here (점수화 폐기).
 */
export interface LivingMirrorData {
  stage?: "new" | "observed" | "trajectory";
  declared_label?: string;
  observed_label?: string | null;
  period_label?: string;
  has_observed?: boolean;
}

export interface LivingMirrorGenerateResponse {
  ok: boolean;
  id: number;
  data: LivingMirrorData;
}

/* ── Methodology & data-provenance transparency (Data-trust Stage 1) ──
 * Backs GET /api/methodology (routes/methodology.py) and the /methodology
 * page. Observation-only disclosure; field names locked to the backend
 * contract. See docs/strategy/DATA_TRUST_STRATEGY.md. */

export interface MethodologyModel {
  name: string;
  category: string;
  module: string;
  description_kr: string;
  description_en: string;
  /** Published paper / textbook anchor — the reproducibility hook. */
  academic_source: string;
}

export interface MethodologyDataSource {
  source: string;
  description: string;
  coverage: string;
}

export interface MethodologyResponse {
  ok: boolean;
  categories: string[];
  category_counts: Record<string, number>;
  total: number;
  active: number;
  models: MethodologyModel[];
  data_lineage: MethodologyDataSource[];
  reproducibility: { statement_kr: string; statement_en: string };
  disclaimer: string;
}
