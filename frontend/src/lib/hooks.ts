import useSWR from "swr";
import {
  API,
  PORTFOLIO_SUMMARY,
  PORTFOLIO_POSITIONS,
  RISK_SUMMARY,
  RISK_LAYERS,
  RISK_ROLLING_VAR,
  RISK_CORRELATION,
} from "./endpoints";
import { liveRefresh } from "./market-hours";
import type {
  DiscoverResponse,
  ProfileResponse,
  WatchlistResponse,
  WatchlistItem,
  AlertsResponse,
  GrowthScoreEntry,
  GrowthTodayResponse,
  GrowthWeeklyReport,
  ArtifactsListResponse,
  ArtifactType,
  SignalEntry,
  SignalsResponse,
  SignalFilters,
  SignalLabel,
  Position,
} from "./types";

const fetcher = async (url: string) => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.error || r.statusText || `HTTP ${r.status}`);
  }
  return r.json();
};

/* ── Market ── */

export function useDiscover() {
  return useSWR<DiscoverResponse>(API.discover, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 600_000,
    // P1 (wave1-critical): render-safe default — consumers reading
    // `data.results` won't NPE during the initial undefined frame.
    fallbackData: { results: [], cached: false },
  });
}

export function useInvestmentProfile() {
  return useSWR<ProfileResponse>(API.profile.get, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 300_000,
    // P1 (wave1-critical): "logged-in but no profile yet" identity. Lets
    // onboarding gates evaluate `has_profile` immediately without
    // an interim undefined frame.
    fallbackData: { profile: null, has_profile: false },
  });
}

/* ── Watchlist ── */

export function useWatchlist() {
  return useSWR<WatchlistResponse>(API.watchlist.list, fetcher, {
    // Market-aware: 5s when any market is open, 60s when all closed.
    refreshInterval: () => liveRefresh(5_000, 60_000),
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    dedupingInterval: 2_000,
    errorRetryCount: 2,
    errorRetryInterval: 5_000,
    // P1 (wave1-critical): empty-list default so iterating consumers
    // don't NPE on `.map` during the first paint.
    fallbackData: { watchlist: [] },
  });
}

/* ── Alerts ── */

export function useAlerts() {
  return useSWR<AlertsResponse>(API.alerts.list, fetcher, {
    refreshInterval: () => liveRefresh(10_000, 60_000),
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    dedupingInterval: 2_000,
    errorRetryCount: 2,
    errorRetryInterval: 5_000,
    // P1 (wave1-critical): empty-list default so the notification bell
    // and dropdown render safely on first paint.
    fallbackData: { alerts: [], unread: 0 },
  });
}

/* ── Morning Brief ── REMOVED 2026-04-29
 * Backend Morning Brief service deprecated and deleted. Frontend hooks
 * (useMorningBrief, useMorningBriefArchive) and types
 * (MorningBriefResponse, MorningBriefArchiveResponse) removed in sync.
 */

/* ── Growth OS ── */

export function useGrowthData(range = "365d") {
  return useSWR<GrowthScoreEntry[]>(
    API.growth.data(range),
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60_000,
      // P1 (wave1-critical): empty-array default so chart renderers
      // (Recharts) don't NPE during initial render.
      fallbackData: [],
    },
  );
}

export function useGrowthToday() {
  return useSWR<GrowthTodayResponse>(
    API.growth.today,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 30_000 },
  );
}

export function useGrowthWeekly() {
  return useSWR<GrowthWeeklyReport[]>(
    API.growth.weekly,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 300_000,
      // P1 (wave1-critical): empty-array default for consumers that map.
      fallbackData: [],
    },
  );
}

/* ── Artifacts (My Reports library) ── */

export interface UseArtifactsOptions {
  type?: ArtifactType | "all";
  since?: "30d" | "90d" | "all";
  limit?: number;
}

/**
 * Fetches the user's artifact (report) archive.
 * Returns artifacts plus total count and unread count for sidebar badge.
 * Builds the request URL with query params so SWR caches each filter
 * combination independently.
 */
export function useArtifacts(options: UseArtifactsOptions = {}) {
  const { type, since, limit } = options;
  const qs = new URLSearchParams();
  if (type && type !== "all") qs.set("type", type);
  if (since && since !== "all") qs.set("since", since);
  if (typeof limit === "number") qs.set("limit", String(limit));
  const qsStr = qs.toString();
  const key = qsStr.length > 0 ? `${API.artifacts.list}?${qsStr}` : API.artifacts.list;

  const swr = useSWR<ArtifactsListResponse>(key, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 30_000,
  });

  return {
    artifacts: swr.data?.artifacts ?? [],
    total: swr.data?.total ?? 0,
    unreadCount: swr.data?.unread_count ?? 0,
    isLoading: swr.isLoading,
    error: swr.error as Error | undefined,
    mutate: swr.mutate,
  };
}

/* ── Broker connections (KIS + Alpaca paper, 2026-04-22) ── */

export interface BrokerConnectionsResponse {
  kis_connected?: boolean;
  kis_last_sync?: string | null;
  alpaca_connected?: boolean;
  alpaca_last_sync?: string | null;
  alpaca_mode?: "paper" | "live";
}

export function useBrokerConnections() {
  return useSWR<BrokerConnectionsResponse>(
    API.broker.connections,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 30_000 },
  );
}

/* ── Portfolio Summary / Positions (shared dedupe) ──
 *
 * P0-3 FIX: Multiple dashboard pages (home, portfolio, risk) plus the
 * RealtimeProvider all subscribed to /api/portfolio/summary with low
 * dedupingInterval (2s), producing 5+ concurrent requests on mount.
 * This shared hook enforces a 10s dedupe window + throttled focus
 * revalidation and does NOT revalidate if the cache is fresh.
 */

export interface PortfolioSummary {
  totalNav?: number;
  todayPnl?: number;
  todayPnlPct?: number;
  unrealized?: number;
  realizedYtd?: number;
  fxRate?: number;
  observed_at?: string;
}

export const PORTFOLIO_DEDUPE_MS = 10_000;
export const PORTFOLIO_FOCUS_THROTTLE_MS = 5_000;

export function usePortfolioSummary() {
  return useSWR<PortfolioSummary>(PORTFOLIO_SUMMARY, fetcher, {
    refreshInterval: () => liveRefresh(5_000, 60_000),
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: false,
    dedupingInterval: PORTFOLIO_DEDUPE_MS,
    focusThrottleInterval: PORTFOLIO_FOCUS_THROTTLE_MS,
    errorRetryCount: 2,
  });
}

/**
 * Live USD/KRW from /api/market/fx — backend scheduler refreshes ~60s.
 * Returns null when feed is unavailable (rather than a stale literal).
 *
 * Why a dedicated hook (and not `usePortfolioSummary().fxRate`):
 *   - Portfolio summary's fxRate field is computed at NAV time and may be
 *     missing for users with no holdings. The market/fx feed is independent.
 *   - We poll less aggressively (60s) since FX moves slowly intraday.
 */
export function useFxRate(): { rate: number | null; isStale: boolean } {
  const { data } = useSWR<{
    ok?: boolean;
    usd_krw?: number;
    is_stale?: boolean;
  }>(API.market.fx, fetcher, {
    refreshInterval: 60_000,
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 30_000,
    errorRetryCount: 1,
  });
  const rate =
    typeof data?.usd_krw === "number" && data.usd_krw > 0
      ? data.usd_krw
      : null;
  return { rate, isStale: Boolean(data?.is_stale) };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function usePortfolioPositions<T = any>() {
  return useSWR<T>(PORTFOLIO_POSITIONS, fetcher, {
    refreshInterval: () => liveRefresh(5_000, 60_000),
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: false,
    dedupingInterval: PORTFOLIO_DEDUPE_MS,
    focusThrottleInterval: PORTFOLIO_FOCUS_THROTTLE_MS,
    errorRetryCount: 2,
  });
}

/* ── Real-time Portfolio Prices (SSE) ── */

export { useRealtimeContext } from "./realtime";
export type { RealtimePriceDetail, PriceDirection, RealtimeState } from "./realtime";

/* ── Risk v2 (additive — does not modify any v1 hook) ──
 *
 * Five new hooks back the /risk v2 "Risk Board" page. Three call existing
 * backend endpoints (RISK_SUMMARY / RISK_LAYERS / RISK_ROLLING_VAR); the
 * remaining two derive their data client-side from PORTFOLIO_POSITIONS
 * (no new endpoint required). All five share a 60s idle / 5s live dedupe
 * window — same cadence as the existing portfolio hooks.
 */

export interface RiskSummaryV2 {
  var_1d_pct?: number;
  var_95?: number;
  var_99?: number;
  es_1d_pct?: number;
  tail_ces?: number;
  max_dd_90d_pct?: number;
  daily_dd_pct?: number;
  corr_risk_index?: number;
  correlation_avg?: number;
  correlation_max?: number;
  hhi?: number;
  sector_top_name?: string;
  sector_top_pct?: number;
  vix?: number;
  vix_regime?: string;
  cash_pct?: number;
  posture?: "composed" | "attentive" | "strained" | "breached";
  layers_breached?: number;
  observed_at_kst?: string;
}

export function useRiskSummary() {
  return useSWR<RiskSummaryV2>(RISK_SUMMARY, fetcher, {
    refreshInterval: () => liveRefresh(15_000, 60_000),
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    dedupingInterval: 15_000,
    errorRetryCount: 2,
  });
}

export type RiskLayerStatus = "POSITIVE" | "NEGATIVE" | "NEUTRAL";

export interface RiskLayerV2 {
  num: 1 | 2 | 3 | 4 | 5 | 6 | 7;
  name: string;
  description?: string;
  status: RiskLayerStatus;
  value: string;
  threshold?: string;
  observedAtKst?: string;
}

interface BackendRiskLayer {
  no?: number;
  num?: number;
  name: string;
  description?: string;
  metric_label?: string;
  metric_value?: string;
  value?: string;
  threshold?: string;
  status: "POSITIVE" | "NEGATIVE" | "NEUTRAL" | "GREEN" | "YELLOW" | "RED";
  observation?: string;
  observed_at_kst?: string;
}

interface RiskLayersV2Response {
  layers?: BackendRiskLayer[];
  defense_score?: number;
  overall_status?: string;
}

function mapLayerStatus(
  s: BackendRiskLayer["status"],
): RiskLayerStatus {
  if (s === "POSITIVE" || s === "GREEN") return "POSITIVE";
  if (s === "NEGATIVE" || s === "RED") return "NEGATIVE";
  return "NEUTRAL";
}

export function useRiskLayers() {
  const swr = useSWR<RiskLayersV2Response | BackendRiskLayer[]>(
    RISK_LAYERS,
    fetcher,
    {
      refreshInterval: () => liveRefresh(15_000, 60_000),
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 15_000,
      errorRetryCount: 2,
    },
  );

  const raw = Array.isArray(swr.data) ? swr.data : swr.data?.layers ?? [];
  const layers: RiskLayerV2[] = raw.map((l): RiskLayerV2 => {
    const num = ((l.num ?? l.no) as RiskLayerV2["num"]) ?? 1;
    return {
      num,
      name: l.name,
      description: l.description ?? l.metric_label,
      status: mapLayerStatus(l.status),
      value: l.value ?? l.metric_value ?? "—",
      threshold: l.threshold,
      observedAtKst: l.observed_at_kst,
    };
  });

  return {
    layers,
    isLoading: swr.isLoading,
    error: swr.error as Error | undefined,
    mutate: swr.mutate,
  };
}

export interface ConcentrationEntry {
  rank: number;
  name: string;
  ticker: string;
  exchange: string;
  weightPct: number;
}

interface RawPosition {
  ticker?: string;
  symbol?: string;
  name?: string;
  company_name?: string;
  exchange?: string;
  market?: string;
  weight?: number;
  weight_pct?: number;
  market_value?: number;
  market_value_usd?: number;
  total_value?: number;
  is_korean?: boolean;
  currency?: string;
}

interface RawPositionsPayload {
  positions?: RawPosition[];
  total_value_usd?: number;
  total_value_all_krw?: number;
  fx_rate?: number;
}

function inferExchange(p: RawPosition): string {
  if (p.exchange) return p.exchange;
  if (p.market) return p.market;
  if (p.is_korean || (p.ticker ?? "").endsWith(".KS")) return "KOSPI";
  if (p.is_korean || (p.ticker ?? "").endsWith(".KQ")) return "KOSDAQ";
  return "NASDAQ";
}

export function useConcentration(top = 5) {
  const swr = usePortfolioPositions<RawPositionsPayload>();
  const positions = swr.data?.positions ?? [];

  const totalKrw = swr.data?.total_value_all_krw ?? 0;
  const totalUsd = swr.data?.total_value_usd ?? 0;
  const fx = swr.data?.fx_rate ?? 1300;

  // Compute weights even when backend doesn't return them pre-computed.
  const weighted = positions
    .map((p): { p: RawPosition; weight: number } => {
      const explicit = p.weight_pct ?? p.weight;
      if (explicit != null && Number.isFinite(explicit)) {
        return { p, weight: explicit > 1 ? explicit : explicit * 100 };
      }
      const mvUsd = p.market_value_usd ?? p.market_value ?? p.total_value ?? 0;
      const mvKrw =
        p.currency === "KRW" || p.is_korean ? mvUsd : mvUsd * fx;
      const denom = totalKrw > 0 ? totalKrw : totalUsd > 0 ? totalUsd : 0;
      const w = denom > 0 ? (mvKrw / denom) * 100 : 0;
      return { p, weight: w };
    })
    .sort((a, b) => b.weight - a.weight)
    .slice(0, top);

  const entries: ConcentrationEntry[] = weighted.map((row, i) => ({
    rank: i + 1,
    name: row.p.name ?? row.p.company_name ?? row.p.ticker ?? row.p.symbol ?? "—",
    ticker: row.p.ticker ?? row.p.symbol ?? "—",
    exchange: inferExchange(row.p),
    weightPct: Number.isFinite(row.weight) ? row.weight : 0,
  }));

  return {
    entries,
    sumPct: entries.reduce((acc, e) => acc + e.weightPct, 0),
    isLoading: swr.isLoading,
    error: swr.error as Error | undefined,
  };
}

export interface SectorEntry {
  name: string;
  pct: number;
  leaderName: string;
  leaderTicker: string;
}

export interface SectorExposureResult {
  sectors: SectorEntry[];
  sectorCount: number;
  cashPct: number;
  isLoading: boolean;
  error: Error | undefined;
}

interface RawPositionWithSector extends RawPosition {
  sector?: string;
}

export function useSectorExposure(): SectorExposureResult {
  const positions = usePortfolioPositions<RawPositionsPayload>();
  const summary = usePortfolioSummary();

  const raw = (positions.data?.positions ?? []) as RawPositionWithSector[];
  const totalKrw = positions.data?.total_value_all_krw ?? 0;
  const totalUsd = positions.data?.total_value_usd ?? 0;
  const fx = positions.data?.fx_rate ?? 1300;

  const groups = new Map<
    string,
    { pct: number; leaderName: string; leaderTicker: string; leaderWeight: number }
  >();

  for (const p of raw) {
    const explicit = p.weight_pct ?? p.weight;
    let w =
      explicit != null && Number.isFinite(explicit)
        ? explicit > 1
          ? explicit
          : explicit * 100
        : 0;
    if (w === 0) {
      const mvUsd = p.market_value_usd ?? p.market_value ?? p.total_value ?? 0;
      const mvKrw =
        p.currency === "KRW" || p.is_korean ? mvUsd : mvUsd * fx;
      const denom = totalKrw > 0 ? totalKrw : totalUsd > 0 ? totalUsd : 0;
      w = denom > 0 ? (mvKrw / denom) * 100 : 0;
    }
    const sector = (p.sector ?? "Other").toString();
    const name = p.name ?? p.company_name ?? p.ticker ?? p.symbol ?? "—";
    const ticker = p.ticker ?? p.symbol ?? "—";
    const cur = groups.get(sector);
    if (!cur) {
      groups.set(sector, {
        pct: w,
        leaderName: name,
        leaderTicker: ticker,
        leaderWeight: w,
      });
    } else {
      cur.pct += w;
      if (w > cur.leaderWeight) {
        cur.leaderWeight = w;
        cur.leaderName = name;
        cur.leaderTicker = ticker;
      }
    }
  }

  const sectors: SectorEntry[] = Array.from(groups.entries())
    .map(([name, v]) => ({
      name,
      pct: v.pct,
      leaderName: v.leaderName,
      leaderTicker: v.leaderTicker,
    }))
    .sort((a, b) => b.pct - a.pct);

  // cashPct sourced from summary if exposed; otherwise inferred from
  // positions (1 - sum of position weights). Falls back to 0 cleanly.
  type SummaryWithCash = { cashPct?: number; cash_pct?: number };
  const sum = summary.data as (typeof summary.data & SummaryWithCash) | undefined;
  const summaryCash = sum?.cashPct ?? sum?.cash_pct;
  const positionsTotal = sectors.reduce((a, s) => a + s.pct, 0);
  const inferredCash = Math.max(0, 100 - positionsTotal);
  const cashPct =
    summaryCash != null && Number.isFinite(summaryCash)
      ? summaryCash > 1
        ? summaryCash
        : summaryCash * 100
      : inferredCash;

  return {
    sectors,
    sectorCount: sectors.length,
    cashPct,
    isLoading: positions.isLoading || summary.isLoading,
    error: (positions.error ?? summary.error) as Error | undefined,
  };
}

export interface RiskTimelinePoint {
  t: string;
  score: number;
}

export interface RiskTimelineResult {
  series: RiskTimelinePoint[];
  today: number | null;
  avg: number | null;
  max: number | null;
  daysAboveStrain: number;
  strainThreshold: number;
  isLoading: boolean;
  error: Error | undefined;
}

interface RollingVarPayload {
  date: string;
  var_pct: number;
}

/**
 * Composite risk score 0..100 derived from rolling VaR. Higher = more
 * strain. We map |VaR%| into a soft 0..100 band where ~−5% maps to ~80
 * (the strain threshold). The series is "data-source: derived" (per
 * SPEC §6) until the backend ships a first-class composite endpoint.
 */
function varToScore(varPct: number): number {
  const abs = Math.abs(varPct);
  // 0% -> 0, 5% -> 80, 7%+ saturates near 100
  const score = (abs / 5) * 80;
  return Math.max(0, Math.min(100, Math.round(score)));
}

export function useRiskTimeline(days: 30 | 90 | 180 = 30): RiskTimelineResult {
  const swr = useSWR<RollingVarPayload[]>(RISK_ROLLING_VAR, fetcher, {
    refreshInterval: () => liveRefresh(30_000, 300_000),
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
    errorRetryCount: 2,
  });

  const raw = swr.data ?? [];
  const sliced = raw.slice(-days);
  const series: RiskTimelinePoint[] = sliced.map((p) => ({
    t: p.date,
    score: varToScore(p.var_pct),
  }));

  const today = series.length > 0 ? series[series.length - 1].score : null;
  const avg =
    series.length > 0
      ? Math.round(series.reduce((a, p) => a + p.score, 0) / series.length)
      : null;
  const max =
    series.length > 0 ? series.reduce((a, p) => Math.max(a, p.score), 0) : null;
  const strainThreshold = 60;
  const daysAboveStrain = series.filter((p) => p.score > strainThreshold).length;

  return {
    series,
    today,
    avg,
    max,
    daysAboveStrain,
    strainThreshold,
    isLoading: swr.isLoading,
    error: swr.error as Error | undefined,
  };
}

/* ── Risk v2 — Correlation Matrix (additive, v1 parity preservation) ──
 *
 * Restores the v1 RISK_CORRELATION call that was dropped from the
 * Risk-v2 page. Pure read-through SWR — backend payload shape is the
 * same as v1: { labels: string[], matrix: number[][] }. Preserves the
 * full N×N heatmap so the v2 page can render it without losing the
 * underlying observation surface.
 */

export interface RiskCorrelationPayload {
  labels: string[];
  matrix: number[][];
}

export function useRiskCorrelation() {
  const swr = useSWR<RiskCorrelationPayload>(RISK_CORRELATION, fetcher, {
    refreshInterval: () => liveRefresh(60_000, 300_000),
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 60_000,
    errorRetryCount: 2,
    shouldRetryOnError: false,
  });

  const labels = swr.data?.labels ?? [];
  const matrix = swr.data?.matrix ?? [];
  const hasData = labels.length > 0 && matrix.length > 0;

  return {
    labels,
    matrix,
    hasData,
    isLoading: swr.isLoading,
    error: swr.error as Error | undefined,
    mutate: swr.mutate,
  };
}

/* ── Signals v2 (additive — does not modify any v1 hook) ──
 *
 * Wraps the existing `/api/signals` endpoint with SWR + filter query
 * parameters. Backend may not yet honor the filter params; in that
 * case the hook will still return the full stream and v2 components
 * filter client-side. Either way the wire format stays consistent.
 *
 * Banned vocabulary (BUY/SELL/HOLD/recommend/advice) is rejected by
 * the legal-guard CI and assumed clean on arrival.
 */

export function useSignals(filters: Partial<SignalFilters> = {}) {
  const qs = new URLSearchParams();
  if (filters.labels && filters.labels.size > 0) {
    qs.set("labels", Array.from(filters.labels).join(","));
  }
  if (typeof filters.strengthMin === "number") {
    qs.set("strength_min", String(filters.strengthMin));
  }
  if (typeof filters.strengthMax === "number") {
    qs.set("strength_max", String(filters.strengthMax));
  }
  if (filters.symbol) qs.set("symbol", filters.symbol);
  if (filters.window) qs.set("window", filters.window);
  const qsStr = qs.toString();
  const key = qsStr.length > 0 ? `${API.signals.all}?${qsStr}` : API.signals.all;

  return useSWR<SignalsResponse>(key, fetcher, {
    // Match v1 cadence: 10s open / 60s closed.
    refreshInterval: () => liveRefresh(10_000, 60_000),
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    dedupingInterval: 4_000,
    errorRetryCount: 2,
    errorRetryInterval: 5_000,
  });
}

/**
 * Resolve a company name from a ticker by consulting the user's
 * portfolio positions and watchlist. Falls back to the ticker itself
 * when no match is found (graceful degradation per audit WARN-2).
 *
 * Pure function — does NOT call any hook. Components are expected to
 * pull `usePortfolioPositions` + `useWatchlist` once and pass the
 * arrays in. This keeps the resolver cheap inside list-rendering loops.
 */
export function resolveTickerName(
  ticker: string,
  positions: Position[] | undefined,
  watchlist: WatchlistItem[] | undefined,
): string {
  if (!ticker) return "";
  const t = ticker.toUpperCase();
  if (Array.isArray(positions)) {
    for (const p of positions) {
      if ((p?.ticker ?? "").toUpperCase() === t && p?.name) return p.name;
    }
  }
  if (Array.isArray(watchlist)) {
    for (const w of watchlist) {
      if ((w?.ticker ?? "").toUpperCase() === t && w?.name) return w.name;
    }
  }
  return ticker;
}

// Re-export for downstream import convenience without a second import line.
export type { SignalEntry, SignalsResponse, SignalFilters, SignalLabel };

/* ── Reports v2 — Artifact stats + archive + generate (Stage 10, 2026-04-27)
 *
 * Additive. Existing `useArtifacts(...)` is untouched. These hooks back the
 * /reports v2 "CFO Archive" surface. Backend endpoints are GAPs; both stats
 * and archive degrade gracefully — when the endpoint is missing the hook
 * derives the data client-side from the `useArtifacts({ limit: 999 })` cache.
 *
 * Legal: hooks consume server data only; banned vocabulary
 * (BUY/SELL/HOLD/recommend/advice) MUST never round-trip through here.
 */

import type { Artifact } from "./types";

export interface ArtifactStats {
  total: number;
  countYtd: number;
  countMemos: number;       // weekly_memo + legacy morning_brief
  countBriefs: number;      // earnings_prebrief
  countBragCards: number;   // monthly_brag
  byType: Partial<Record<ArtifactType, number>>;
  nextScheduled: { type: ArtifactType; at: string } | null;
  latestIndexedAt: string | null;
}

/**
 * Aggregate stats for the /reports v2 hero + status bar. When the backend
 * endpoint 404s, the SWR error path lets the caller fall back to a
 * client-side derivation via `deriveArtifactStats(artifacts)` below.
 */
export function useArtifactStats() {
  const swr = useSWR<ArtifactStats>(API.artifacts.stats, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
    shouldRetryOnError: false,
  });
  return swr;
}

/**
 * Pure helper — derives `ArtifactStats` from a flat artifact list.
 * Matches the backend contract so callers can swap server data for
 * client-derived stats without refactoring.
 */
export function deriveArtifactStats(artifacts: Artifact[]): ArtifactStats {
  const yearStart = new Date(new Date().getFullYear(), 0, 1).getTime();
  const byType: Partial<Record<ArtifactType, number>> = {};
  let countYtd = 0;
  let latestTs = 0;
  for (const a of artifacts) {
    byType[a.type] = (byType[a.type] ?? 0) + 1;
    const ts = a.sent_at ? Date.parse(a.sent_at) : 0;
    if (ts && ts >= yearStart) countYtd += 1;
    if (ts && ts > latestTs) latestTs = ts;
  }
  return {
    total: artifacts.length,
    countYtd,
    countMemos: byType.weekly_memo ?? 0,
    countBriefs: byType.earnings_prebrief ?? 0,
    // 2026-05-02: count both monthly_brag (auto digest) and brag_card
    // (one-off) — keep client-derived stats in lockstep with the server
    // contract in routes/artifacts.py::artifacts_stats.
    countBragCards: (byType.monthly_brag ?? 0) + (byType.brag_card ?? 0),
    byType,
    nextScheduled: null,
    latestIndexedAt: latestTs ? new Date(latestTs).toISOString() : null,
  };
}

export interface ArtifactArchiveMonth {
  month: string;            // "YYYY-MM"
  artifacts: Artifact[];
  count: number;
}

/**
 * Pure helper — buckets artifacts into the most recent N months
 * (default 12). Returns months descending (newest first), each with
 * its full artifact list and count. Months with zero artifacts are
 * still included so the year timeline renders all 12 rows.
 */
export function deriveArchiveMonths(
  artifacts: Artifact[],
  monthsBack: number = 12,
): ArtifactArchiveMonth[] {
  const buckets = new Map<string, Artifact[]>();
  // Seed empty buckets for the rolling window
  const now = new Date();
  for (let i = 0; i < monthsBack; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    buckets.set(key, []);
  }
  for (const a of artifacts) {
    if (!a.sent_at) continue;
    const d = new Date(a.sent_at);
    if (isNaN(d.getTime())) continue;
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    if (buckets.has(key)) buckets.get(key)!.push(a);
  }
  return Array.from(buckets.entries())
    .map(([month, arr]) => ({ month, artifacts: arr, count: arr.length }))
    .sort((a, b) => (a.month < b.month ? 1 : -1));
}

export interface GenerateArtifactBody {
  type: ArtifactType;
  ticker?: string;          // for earnings_prebrief
  topic?: string;           // for risk_report / custom
}

export interface GenerateArtifactResponse {
  job_id: string;
  eta_seconds: number;
}

/**
 * On-demand artifact generation (Brag Card / Earnings Pre-Brief / Risk Note).
 * Returns a job id; SWR polling on `useArtifacts()` will surface the new
 * artifact when ready (no separate polling hook needed for the v2 launch).
 *
 * Backend GAP: `POST /api/artifacts/generate`. Until shipped, this throws
 * a recognizable error so the UI can show a "queued offline" state.
 */
export async function generateArtifact(
  body: GenerateArtifactBody,
): Promise<GenerateArtifactResponse> {
  const r = await fetch(API.artifacts.generate, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}));
    throw new Error(
      (detail as { error?: string }).error ||
        r.statusText ||
        `HTTP ${r.status}`,
    );
  }
  return r.json() as Promise<GenerateArtifactResponse>;
}
