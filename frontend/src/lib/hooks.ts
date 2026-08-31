import useSWR from "swr";
import { apiFetch } from "./api";
import { isDemoMode, demoResponseFor } from "./demo";
import {
  API,
  PORTFOLIO_SUMMARY,
  PORTFOLIO_POSITIONS,
  RISK_SUMMARY,
  RISK_LAYERS,
  RISK_ROLLING_VAR,
  RISK_CORRELATION,
  PUBLIC_MARKET_SNAPSHOT,
  METHODOLOGY,
} from "./endpoints";
import { displayTicker } from "./format";
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
  PreTradeJournalResponse,
  HoldingMirrorResponse,
  ConcentrationMirrorResponse,
  ProfitLossMirrorResponse,
  TurnoverMirrorResponse,
  AveragingDownMirrorResponse,
  MethodologyResponse,
  MirrorHomeResponse,
} from "./types";

// Exported so post-mutation handlers (e.g. portfolio refreshAll) can feed a
// fresh fetch promise straight into the SWR cache — bypassing the 10s
// dedupingInterval that would otherwise serve pre-mutation data after an
// add/edit/sell.
export const fetcher = async (url: string) => {
  if (isDemoMode()) return demoResponseFor(url).body;
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.error || r.statusText || `HTTP ${r.status}`);
  }
  return r.json();
};

/* ── Public Market Snapshot (no-auth — landing ticker) ── */

/**
 * Unauthenticated fetcher for public endpoints. Unlike `fetcher` above it
 * does NOT send the session cookie (`credentials: "omit"`) — the public
 * market-snapshot route is rate-limited and cache-only and must not be
 * coupled to a login session. The backend always returns HTTP 200, but we
 * still guard `r.ok` defensively so a proxy/edge failure surfaces as an
 * SWR error (consumers degrade gracefully rather than render garbage).
 */
const publicFetcher = async (url: string) => {
  if (isDemoMode()) return demoResponseFor(url).body;
  const r = await fetch(url, { credentials: "omit" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

export interface PublicMarketSnapshotItem {
  symbol: string;
  name: string;
  value: number | null;
  change_pct: number | null;
  direction: "up" | "down" | "flat";
  is_stale: boolean;
  observed_at: string | null;
  // Bug #3 (2026-05-15): ETF-proxy disclosure for the landing ticker.
  // When the displayed `value` is an ETF price standing in for a
  // caret-prefixed US index (FMP $29 plan 402s on ^GSPC/^IXIC/^VIX),
  // the backend sets `proxy_ticker` so the frontend can render a small
  // "VIA <PROXY>" chip. Without this, an unauthenticated visitor sees
  // "S&P 500 748" (SPY price) instead of the real S&P 500 ≈ 5,700 — a
  // capital-markets-law misrepresentation risk. KR indices and FX get
  // `null` (no proxy involved). Mirrors the dashboard top-ticker
  // `proxyTicker` field (PR #379).
  proxy_ticker?: string | null;
}

export interface PublicMarketSnapshotResponse {
  ok: boolean;
  items: PublicMarketSnapshotItem[];
  generated_at: string;
  cache_warm: boolean;
}

/**
 * Landing-page market ticker feed. Polls every 60s — the backend cache
 * refreshes on its own cadence and the route is rate-limited, so a tight
 * interval buys no freshness. `keepPreviousData` holds the last good
 * payload across refreshes so the marquee never flashes empty; on a hard
 * error the consumer falls back to whatever `data` last held (or an empty
 * ticker — never a fabricated value).
 */
export function usePublicMarketSnapshot() {
  return useSWR<PublicMarketSnapshotResponse>(
    PUBLIC_MARKET_SNAPSHOT,
    publicFetcher,
    {
      refreshInterval: 60_000,
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 30_000,
      keepPreviousData: true,
      errorRetryCount: 2,
      errorRetryInterval: 10_000,
    },
  );
}

/* ── Market ── */

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
    // Bug #3 (HANDOVER v22): focus revalidation is redundant when an
    // aggressive `refreshInterval` already keeps data fresh. Tab-switch
    // focus events were the documented trigger for the 5-6× duplicate
    // fetch flood on page navigation. `revalidateOnReconnect` still
    // covers long-idle network resume.
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 2_000,
    errorRetryCount: 2,
    errorRetryInterval: 5_000,
    // Bug #6 (Wave 1, fix 2026-05-09): `fallbackData: { watchlist: [] }`
    // forced SWR's `isLoading` to false on first paint because `data` was
    // already defined. Consumers had `isLoading` branches that never
    // fired — every page hit the empty-list UI for one frame, then
    // swapped in the real data. NPE protection is preserved at every
    // call site via `data?.watchlist ?? []` (verified across 5 consumers:
    // signals, watchlist, discover, detail/[ticker], ai, home).
  });
}

/* ── Alerts ── */

export function useAlerts() {
  // Bug #2 fix (2026-05-09 deep bug hunt): backend defaults to limit=20
  // (max 50). The /alerts page Total/Unread/Today/Week stats are computed
  // from `data.alerts.length` — a user with >20 alerts saw "Total: 20"
  // and was misled. Request the max (50) so the strip is accurate for the
  // typical user. Pagination/load-more is a separate enhancement.
  return useSWR<AlertsResponse>(`${API.alerts.list}?limit=50`, fetcher, {
    refreshInterval: () => liveRefresh(10_000, 60_000),
    // Bug #3 (HANDOVER v22): the alerts bell was one of the three explicit
    // duplicate-fetch culprits flagged on page nav. `refreshInterval`
    // already keeps the badge fresh; focus revalidate just compounds the
    // load when the user tabs back in mid-poll.
    revalidateOnFocus: false,
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

// 2026-05-08 (NEW-E): agent_worker.growth_routes is registered as an
// optional blueprint (routes/__init__.py:48-58). When the agent_worker
// package is missing from a deploy, the entire /api/growth/* surface
// returns 404. Without `shouldRetryOnError: false`, SWR retried in a
// tight loop and the page got stuck on "Loading..." forever. Now the
// hook fails fast and the page renders the unavailable-fallback UI.
const GROWTH_SWR_OPTS = {
  revalidateOnFocus: false,
  shouldRetryOnError: false,
  errorRetryCount: 0,
} as const;

/* ── Pre-Trade Journal (decision-reflection feed) ── */

/**
 * Fetches the user's pre-trade reflection feed (newest first).
 *
 * Read-only mirror of the rows created by the Pre-Trade Friction flow
 * (Feature 6) — each is a "user finished thinking" record, never an executed
 * order. The /journal page renders this as a reverse-chronological feed so
 * the user can review their own past decision rationale ("User as CFO").
 *
 * Defaults `limit=50` (matches backend cap). `fallbackData` keeps the feed
 * mapper NPE-safe during initial render. SWR key is path+query so it caches
 * independently of every other surface.
 */
export function usePreTradeJournal(limit = 50) {
  const key = `${API.preTrade.list}?limit=${limit}`;
  const swr = useSWR<PreTradeJournalResponse>(key, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 30_000,
  });
  return {
    reflections: swr.data?.reflections ?? [],
    disclaimer: swr.data?.disclaimer ?? null,
    isLoading: swr.isLoading,
    error: swr.error as Error | undefined,
    mutate: swr.mutate,
  };
}

/**
 * Holding-Mirror — factual holding-period statistics from the user's own
 * closed trade pairs. Renders as a neutral 2-up comparison on /journal.
 *
 * Resilience: a 404 (backend not yet wired) is treated as "no data" rather
 * than an error, so the surrounding Decision Journal feed never breaks while
 * the cross-team backend contract lands. Real 5xx / network failures still
 * surface through `error` so the panel can show its retry affordance.
 *
 * Never returns a score / grade — only counts and average hold days.
 */
/**
 * Mirror home (거울) — the composed 선언/관찰/트윈 read for the new home.
 * 404-safe soft-empty (returns null) so the surface degrades gracefully
 * before the route is reachable. Read-only; not refreshed on focus.
 */
export function useMirrorHome() {
  const swr = useSWR<MirrorHomeResponse | null>(
    API.mirror.home,
    async (url: string): Promise<MirrorHomeResponse | null> => {
      if (isDemoMode()) return demoResponseFor(url).body as MirrorHomeResponse | null;
      const res = await fetch(url, { credentials: "include" });
      if (res.status === 404) return null;
      if (!res.ok) {
        const err = new Error(`HTTP ${res.status}`) as Error & { status?: number };
        err.status = res.status;
        throw err;
      }
      return res.json();
    },
    {
      revalidateOnFocus: false,
      dedupingInterval: 60_000,
      keepPreviousData: true,
      shouldRetryOnError: false,
    },
  );
  return {
    data: swr.data ?? null,
    isLoading: swr.data === undefined && !swr.error,
    error: swr.error as (Error & { status?: number }) | undefined,
    mutate: swr.mutate,
  };
}

export function useHoldingMirror() {
  const swr = useSWR<HoldingMirrorResponse | null>(
    API.behavior.holdingMirror,
    async (url: string): Promise<HoldingMirrorResponse | null> => {
      const res = await fetch(url, { credentials: "include" });
      // Backend not yet wired (or genuinely empty) → soft-empty, not an error.
      if (res.status === 404) return null;
      if (!res.ok) {
        const err = new Error(`HTTP ${res.status}`) as Error & {
          status?: number;
        };
        err.status = res.status;
        throw err;
      }
      return res.json();
    },
    {
      revalidateOnFocus: false,
      dedupingInterval: 60_000,
      keepPreviousData: true,
      shouldRetryOnError: false,
    },
  );

  return {
    data: swr.data ?? null,
    isLoading: swr.data === undefined && !swr.error,
    error: swr.error as Error | undefined,
    mutate: swr.mutate,
  };
}

/**
 * Concentration-Mirror — factual cost-basis composition of the user's own
 * open positions (the largest holding's share of the portfolio).
 *
 * Mirrors useHoldingMirror's posture exactly: a 404 (backend not yet wired /
 * genuinely empty) is normalised to `data === null` (soft-empty), and a hard
 * 5xx / network failure surfaces through `error` so the panel can render
 * nothing rather than a broken card — a mirror failure must NEVER take down
 * the journal feed beneath it.
 *
 * Never returns a score / grade / ratio — only a count + the largest holding's
 * weight + display name.
 */
export function useConcentrationMirror() {
  const swr = useSWR<ConcentrationMirrorResponse | null>(
    API.behavior.concentrationMirror,
    async (url: string): Promise<ConcentrationMirrorResponse | null> => {
      const res = await fetch(url, { credentials: "include" });
      // Backend not yet wired (or genuinely empty) → soft-empty, not an error.
      if (res.status === 404) return null;
      if (!res.ok) {
        const err = new Error(`HTTP ${res.status}`) as Error & {
          status?: number;
        };
        err.status = res.status;
        throw err;
      }
      return res.json();
    },
    {
      revalidateOnFocus: false,
      dedupingInterval: 60_000,
      keepPreviousData: true,
      shouldRetryOnError: false,
    },
  );

  return {
    data: swr.data ?? null,
    isLoading: swr.data === undefined && !swr.error,
    error: swr.error as Error | undefined,
    mutate: swr.mutate,
  };
}

/**
 * Profit/Loss-Mirror — factual hold-day + return statistics from the user's
 * own closed trade pairs, split by whether each pair realised a profit or a
 * loss. Renders as a neutral 2-up comparison on /journal.
 *
 * Mirrors useHoldingMirror's posture exactly: a 404 (backend not yet wired /
 * genuinely empty) is normalised to `data === null` (soft-empty), and a hard
 * 5xx / network failure surfaces through `error` so the panel can render
 * nothing rather than a broken card — a mirror failure must NEVER take down
 * the journal feed beneath it.
 *
 * Never returns a score / grade — only counts, average hold days, and the
 * raw realised return percentages (loss side keeps its negative sign).
 */
export function useProfitLossMirror() {
  const swr = useSWR<ProfitLossMirrorResponse | null>(
    API.behavior.profitLossMirror,
    async (url: string): Promise<ProfitLossMirrorResponse | null> => {
      const res = await fetch(url, { credentials: "include" });
      // Backend not yet wired (or genuinely empty) → soft-empty, not an error.
      if (res.status === 404) return null;
      if (!res.ok) {
        const err = new Error(`HTTP ${res.status}`) as Error & {
          status?: number;
        };
        err.status = res.status;
        throw err;
      }
      return res.json();
    },
    {
      revalidateOnFocus: false,
      dedupingInterval: 60_000,
      keepPreviousData: true,
      shouldRetryOnError: false,
    },
  );

  return {
    data: swr.data ?? null,
    isLoading: swr.data === undefined && !swr.error,
    error: swr.error as Error | undefined,
    mutate: swr.mutate,
  };
}

/**
 * Turnover (trade-activity) Mirror — neutral count of the user's own
 * BUY/SELL fills plus per-currency gross traded value.
 *
 * A 404 (backend not yet wired) is normalised to `data === null` so the
 * panel shows its calm empty state rather than an error. A 5xx / network
 * failure surfaces through `error` so the panel can render nothing rather
 * than a broken card — a mirror failure must NEVER take down the journal
 * feed beneath it.
 *
 * Never returns a score / grade / ratio — only fill counts, per-currency
 * gross value, and the average hold days for context.
 */
export function useTurnoverMirror() {
  const swr = useSWR<TurnoverMirrorResponse | null>(
    API.behavior.turnoverMirror,
    async (url: string): Promise<TurnoverMirrorResponse | null> => {
      const res = await fetch(url, { credentials: "include" });
      // Backend not yet wired (or genuinely empty) → soft-empty, not an error.
      if (res.status === 404) return null;
      if (!res.ok) {
        const err = new Error(`HTTP ${res.status}`) as Error & {
          status?: number;
        };
        err.status = res.status;
        throw err;
      }
      return res.json();
    },
    {
      revalidateOnFocus: false,
      dedupingInterval: 60_000,
      keepPreviousData: true,
      shouldRetryOnError: false,
    },
  );

  return {
    data: swr.data ?? null,
    isLoading: swr.data === undefined && !swr.error,
    error: swr.error as Error | undefined,
    mutate: swr.mutate,
  };
}

/**
 * Averaging-Down Mirror — neutral counts of follow-on buys (adds to an
 * already-held position) that landed below / above / at the position's
 * running average cost. 1:1 with `useTurnoverMirror`: a 404 (backend not yet
 * wired, or genuinely empty) normalises to `data === null` so the panel shows
 * its calm empty state rather than an error. A 5xx / network failure surfaces
 * through `error` so the panel can render nothing rather than a broken card —
 * a mirror failure must NEVER take down the journal feed beneath it.
 *
 * Never returns a score / grade / ratio — only integer counts.
 */
export function useAveragingDownMirror() {
  const swr = useSWR<AveragingDownMirrorResponse | null>(
    API.behavior.averagingDownMirror,
    async (url: string): Promise<AveragingDownMirrorResponse | null> => {
      const res = await fetch(url, { credentials: "include" });
      // Backend not yet wired (or genuinely empty) → soft-empty, not an error.
      if (res.status === 404) return null;
      if (!res.ok) {
        const err = new Error(`HTTP ${res.status}`) as Error & {
          status?: number;
        };
        err.status = res.status;
        throw err;
      }
      return res.json();
    },
    {
      revalidateOnFocus: false,
      dedupingInterval: 60_000,
      keepPreviousData: true,
      shouldRetryOnError: false,
    },
  );

  return {
    data: swr.data ?? null,
    isLoading: swr.data === undefined && !swr.error,
    error: swr.error as Error | undefined,
    mutate: swr.mutate,
  };
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

  // DORMANT since e064118e (artefact tree deleted). `/api/artifacts/list` no
  // longer exists, so fetching it returns 404 on every render of /reports, the
  // home queue, the companion archive and the detail panel. A null SWR key
  // disables the request while leaving the shape below untouched: every caller
  // takes its existing empty-state branch instead of an error branch.
  //
  // The key is still computed above so the query contract stays visible and
  // reviewable. To restore, drop the `false &&`.
  const swr = useSWR<ArtifactsListResponse>(false && key, fetcher, {
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

/* ── Broker connections (KIS read-only) ── */

export interface BrokerConnectionsResponse {
  kis_connected?: boolean;
  kis_last_sync?: string | null;
}

export function useBrokerConnections() {
  // DORMANT since 237a1b67 — `/api/broker/connections` went with the user-linked
  // broker integration (KIS partnership is closed to non-licensed firms; Toss's
  // Open API terms forbid sharing the app key). A null key stops the request;
  // `data` stays undefined, so `kis_connected` reads false and every caller —
  // settings section B, the onboarding step, the portfolio reconcile affordance —
  // takes its not-connected branch instead of erroring.
  return useSWR<BrokerConnectionsResponse>(
    false && API.broker.connections,
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
  // Native-currency stock subtotals (no FX unification). navUsd = US holdings
  // in USD, navKrw = KR holdings in KRW. /home shows them separately so a
  // mixed portfolio isn't collapsed into a single USD figure.
  navUsd?: number;
  navKrw?: number;
  todayPnl?: number;
  todayPnlPct?: number;
  unrealized?: number;
  realizedYtd?: number;
  // Per-currency P&L (native) — hero KPIs split US (USD) / KR (KRW).
  todayPnlUsd?: number;
  todayPnlKrw?: number;
  unrealizedUsd?: number;
  unrealizedKrw?: number;
  realizedUsd?: number;
  realizedKrw?: number;
  fxRate?: number;
  observed_at?: string;
  // Backend P1 batch (routes/portfolio.py::portfolio_summary_alias) emits
  // cashPct as cash / totalNav. Optional for backwards compatibility with
  // pre-batch backend deploys that don't yet emit the field.
  cashPct?: number;
}

export const PORTFOLIO_DEDUPE_MS = 10_000;
export const PORTFOLIO_FOCUS_THROTTLE_MS = 5_000;

export function usePortfolioSummary() {
  return useSWR<PortfolioSummary>(PORTFOLIO_SUMMARY, fetcher, {
    refreshInterval: () => liveRefresh(5_000, 60_000),
    // Bug #3 (HANDOVER v22): SSE pushes price ticks into this cache via
    // globalMutate(..., { revalidate: false }) (see realtime.tsx L337).
    // Combined with the 5-60s refreshInterval, focus revalidate adds no
    // freshness — only duplicate fetches on page nav. `focusThrottleInterval`
    // is retained as defense-in-depth in case a future override re-enables
    // focus revalidate.
    revalidateOnFocus: false,
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
    // Bug #3 (HANDOVER v22): same rationale as usePortfolioSummary — SSE
    // mutates this cache key directly (realtime.tsx L304), so focus
    // revalidate produces redundant network round-trips during nav.
    revalidateOnFocus: false,
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
  // Check the suffix before is_korean: a .KQ ticker also has
  // is_korean=true, so an is_korean-first test would swallow every
  // KOSDAQ name into KOSPI.
  const t = (p.ticker ?? "").toUpperCase();
  if (t.endsWith(".KQ")) return "KOSDAQ";
  if (t.endsWith(".KS")) return "KOSPI";
  if (p.is_korean) return "KOSPI"; // korean, suffix unknown → default KOSPI
  return "NASDAQ";
}

interface RawPositionWithSector extends RawPosition {
  sector?: string;
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

/* ── Risk v2 — Correlation Matrix (additive, v1 parity preservation) ──
 *
 * Restores the v1 RISK_CORRELATION call that was dropped from the
 * Risk-v2 page. Pure read-through SWR — backend payload shape is the
 * same as v1: { labels: string[], matrix: number[][] }. Preserves the
 * full N×N heatmap so the v2 page can render it without losing the
 * underlying observation surface.
 */

/* ── Earnings Pre-Brief (home v2 Card 3, 2026-05-19 P2 #11) ────────────
 *
 * GET /api/brief/earnings/upcoming?days=7 — 6h server-side cache + 1h
 * SWR refresh. Backend ships next_event + 3-row queue inside the 7-day
 * window. `implied_move` is labelled "30-day proxy" on the card surface
 * (true implied move requires options-chain pricing — see
 * routes/brief.py::_implied_move_pct).
 */

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
  // No name found in positions/watchlist — never surface a naked ".KS"/".KQ"
  // code (feedback_ticker_display); fall back to the seed-resolved label.
  return displayTicker(ticker);
}

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

/* ── Notification preferences (settings v2 §C matrix) ──────────────────────
 *
 * Replaces the localStorage shadow-state (GAP-E) for the 7-event × 3-channel
 * <NotificationsMatrix />. Server is the source of truth — it always returns
 * all 7 events with defaults merged (locked contract, see endpoints.ts).
 *
 * Additive: new SWR key + types + a mutation helper. No existing hook,
 * SWR key, or type field is modified.
 *
 * Legal: channel toggles only — no signal vocabulary round-trips here.
 */

export type NotificationChannel = "email" | "push" | "inapp";

export type NotificationChannelPrefs = Record<NotificationChannel, boolean>;

export type NotificationPrefsMap = Record<string, NotificationChannelPrefs>;

export interface NotificationPreferencesResponse {
  prefs: NotificationPrefsMap;
}

/**
 * Fetches the authenticated user's notification matrix. The backend always
 * returns all 7 events with defaults merged, so consumers can read
 * `data.prefs[event_id][channel]` without merging client-side. SWR key is
 * the bare endpoint path (no query params) so the cache is shared with the
 * PUT mutation's revalidation.
 */
export function useNotificationPreferences() {
  return useSWR<NotificationPreferencesResponse>(
    API.notifications.preferences,
    fetcher,
    {
      revalidateOnFocus: false,
      // Settings rarely changes from another device mid-session; a long
      // dedupe window avoids re-fetching when the user re-opens /settings.
      dedupingInterval: 60_000,
      errorRetryCount: 2,
    },
  );
}

/**
 * PUT the full preferences map. Returns the server-committed map (defaults
 * merged). Routed through `apiFetch` so CSRF + credentials + timeout match
 * the rest of the SPA. Throws `ApiError` on 400 (validation) / network so
 * the caller can roll back optimistic UI.
 */
export async function saveNotificationPreferences(
  prefs: NotificationPrefsMap,
): Promise<NotificationPreferencesResponse> {
  return apiFetch<NotificationPreferencesResponse>(
    API.notifications.preferences,
    {
      method: "PUT",
      body: JSON.stringify({ prefs }),
    },
  );
}

/* ── Customer support — 고객문의센터 + AI 고객지원 (2026-05-26) ─────────────
 *
 * Additive. SWR reads for the inquiry list/detail + mutation helpers for
 * creating an inquiry and sending an AI-support chat turn. Mutations route
 * through `apiFetch` so CSRF + credentials + 30s timeout + 401/429 handling
 * match the rest of the SPA (apiFetch throws `ApiError` with `.status`).
 *
 * Legal: this is a CUSTOMER-SUPPORT assistant (billing/account/usage) — not
 * an investment coach. No signal/advice vocabulary round-trips here.
 */

import type {
  SupportInquiriesResponse,
  SupportInquiryDetail,
  SupportInquiryCreateBody,
  SupportInquiryCreateResponse,
  SupportChatMessage,
  SupportChatRequest,
  SupportChatResponse,
  SupportAdminInquiriesResponse,
  SupportAdminInquiry,
  SupportAdminReplyBody,
  SupportStatus,
} from "./types";

/**
 * The user's own inquiry list (내 문의함). Newest-first ordering is the
 * backend's responsibility. `fallbackData` keeps the list mapper NPE-safe
 * during the initial undefined frame. SWR key is the bare endpoint so the
 * cache is shared with `createSupportInquiry`'s post-submit `mutate`.
 */
export function useSupportInquiries() {
  return useSWR<SupportInquiriesResponse>(API.support.inquiries, fetcher, {
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 15_000,
    errorRetryCount: 2,
    fallbackData: { inquiries: [] },
  });
}

/**
 * A single inquiry's full record (원문 + admin_reply). `id` is passed
 * through verbatim (string from `useParams`) — the backend route parses
 * `<int:iid>`. Pass `null`/`undefined` to disable the fetch (SWR null key).
 */
export function useSupportInquiry(id: string | number | null | undefined) {
  return useSWR<SupportInquiryDetail>(
    id != null && id !== "" ? API.support.inquiry(id) : null,
    fetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 15_000,
      errorRetryCount: 2,
    },
  );
}

/**
 * Submit a 1:1 inquiry. Returns the created envelope ({id,status,created_at}).
 * Throws `ApiError` on 400 (validation) / 401 / 429 (RATE_LIMITED) so the
 * caller can branch the inline error message. The caller is responsible for
 * `mutate(API.support.inquiries)` after success to refresh the inbox.
 */
export async function createSupportInquiry(
  body: SupportInquiryCreateBody,
): Promise<SupportInquiryCreateResponse> {
  return apiFetch<SupportInquiryCreateResponse>(API.support.inquiries, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/**
 * Send one AI-support chat turn. `history` should carry only normal
 * conversation turns (≤10) — error/guidance bubbles are excluded by the
 * caller. Throws `ApiError` on 400 (INVALID_MESSAGE) / 401 / 429.
 */
export async function sendSupportChat(
  message: string,
  history?: SupportChatMessage[],
): Promise<SupportChatResponse> {
  const payload: SupportChatRequest = { message };
  if (history && history.length > 0) {
    // Defensive cap — the backend also enforces ≤10 turns.
    payload.history = history.slice(-10);
  }
  return apiFetch<SupportChatResponse>(API.support.chat, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Admin: all inquiries (operator console). Optional `status` filter maps to
 * the `?status=` query param the backend honours (open|answered|closed).
 * Non-admin callers get a 404 from the backend → SWR surfaces `error`, which
 * the operator page renders as a "권한 없음" notice. The SWR key includes the
 * status so each filter is cached independently and `mutate` is precise.
 */
export function useAdminInquiries(status?: SupportStatus) {
  const key = status
    ? `${API.support.adminInquiries}?status=${status}`
    : API.support.adminInquiries;
  return useSWR<SupportAdminInquiriesResponse>(key, fetcher, {
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 15_000,
    errorRetryCount: 1,
  });
}

/**
 * Admin: send an operator reply to an inquiry. Returns the updated detail
 * record (status="answered", answered_at set). Throws `ApiError` on 400
 * (INVALID_REPLY) / 404 (non-admin or missing ticket). Callers should
 * `mutate` the relevant `useAdminInquiries` key on success.
 */
export async function replyToInquiry(
  id: string | number,
  reply: string,
): Promise<SupportAdminInquiry> {
  const body: SupportAdminReplyBody = { reply };
  return apiFetch<SupportAdminInquiry>(API.support.adminReply(id), {
    method: "POST",
    body: JSON.stringify(body),
  });
}
