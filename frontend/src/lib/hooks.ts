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

export function useGrowthData(range = "365d") {
  return useSWR<GrowthScoreEntry[]>(
    API.growth.data(range),
    fetcher,
    {
      ...GROWTH_SWR_OPTS,
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
    { ...GROWTH_SWR_OPTS, dedupingInterval: 30_000 },
  );
}

export function useGrowthWeekly() {
  return useSWR<GrowthWeeklyReport[]>(
    API.growth.weekly,
    fetcher,
    {
      ...GROWTH_SWR_OPTS,
      dedupingInterval: 300_000,
      // P1 (wave1-critical): empty-array default for consumers that map.
      fallbackData: [],
    },
  );
}

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
    // Bug #3 (HANDOVER v22): risk metrics already poll every 15-60s. Focus
    // revalidate would compound the load when the user navigates from
    // /home → /risk and back. Network reconnect still triggers refresh.
    revalidateOnFocus: false,
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

export function mapLayerStatus(
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
      // Bug #3 (HANDOVER v22): same rationale as useRiskSummary.
      revalidateOnFocus: false,
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

  // Breach / strain counts derived directly from layer status.
  //
  // The backend /api/risk/summary payload exposes the 5 raw metrics
  // (var/es/hhi/corr/dd) but NOT a `layers_breached` field, so the v2 hero
  // previously fell back to `?? 0` and always rendered "none breached" even
  // when a layer was RED — a dangerous risk-misread for a finance surface.
  //
  // Mapping (see risk_defense.py — layer status is GREEN/YELLOW/RED only):
  //   RED    → NEGATIVE → breached
  //   YELLOW → NEUTRAL  → strained
  //   GREEN  → POSITIVE → within band
  const breachedCount = layers.filter((l) => l.status === "NEGATIVE").length;
  const strainedCount = layers.filter((l) => l.status === "NEUTRAL").length;

  return {
    layers,
    breachedCount,
    strainedCount,
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
  // Check the suffix before is_korean: a .KQ ticker also has
  // is_korean=true, so an is_korean-first test would swallow every
  // KOSDAQ name into KOSPI.
  const t = (p.ticker ?? "").toUpperCase();
  if (t.endsWith(".KQ")) return "KOSDAQ";
  if (t.endsWith(".KS")) return "KOSPI";
  if (p.is_korean) return "KOSPI"; // korean, suffix unknown → default KOSPI
  return "NASDAQ";
}

export function useConcentration(top = 5) {
  const swr = usePortfolioPositions<RawPositionsPayload>();
  // Array.isArray guard mirrors the useRiskTimeline fix — a backend
  // shape regression that delivers `{ positions: null }` or `{}` must
  // not page-down the /risk v2 board.
  const positions = Array.isArray(swr.data?.positions)
    ? swr.data!.positions!
    : [];

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

  const raw = (
    Array.isArray(positions.data?.positions)
      ? positions.data!.positions!
      : []
  ) as RawPositionWithSector[];
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

  // Defensive: backend always returns `jsonify([])` for rolling-var, but
  // a stale ServiceWorker cache, an upstream proxy that wraps errors as
  // `{}`, or a future shape change can deliver a non-array. Calling
  // `.slice` on a non-array is a root-level crash for /risk v2 — guard
  // with Array.isArray so partial degradation surfaces as an empty
  // timeline rather than a page-down ErrorBoundary.
  // (feedback_bug_fix_patterns: stale fallback + divergence guard)
  const raw = Array.isArray(swr.data) ? swr.data : [];
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

/* ── Earnings Pre-Brief (home v2 Card 3, 2026-05-19 P2 #11) ────────────
 *
 * GET /api/brief/earnings/upcoming?days=7 — 6h server-side cache + 1h
 * SWR refresh. Backend ships next_event + 3-row queue inside the 7-day
 * window. `implied_move` is labelled "30-day proxy" on the card surface
 * (true implied move requires options-chain pricing — see
 * routes/brief.py::_implied_move_pct).
 */

export interface EarningsBriefNextEvent {
  ticker: string;
  name: string;
  when: string;                  // ISO 8601, e.g. "2026-05-22T13:30:00Z"
  eps_est: number | null;
  rev_est: number | null;        // millions
  implied_move: number | null;   // percent (30d proxy)
}

export interface EarningsBriefQueueItem {
  ticker: string;
  name: string;
  when: string;
}

export interface EarningsBriefResponse {
  next_event: EarningsBriefNextEvent | null;
  queue: EarningsBriefQueueItem[];
}

export function useEarningsBrief(days: number = 7) {
  const key = `/api/brief/earnings/upcoming?days=${days}`;
  const swr = useSWR<EarningsBriefResponse>(key, fetcher, {
    // Backend cache is 6h; revalidate hourly so a freshly-cached payload
    // surfaces on next mount without spamming FMP.
    refreshInterval: 60 * 60 * 1000,
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 5 * 60 * 1000,
    errorRetryCount: 2,
    shouldRetryOnError: false,
  });

  return {
    data: swr.data,
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
    // Bug #3 (HANDOVER v22): the signals feed already polls every 10-60s.
    // Focus revalidate compounds load when the user navigates between the
    // signals list and detail pages. Reconnect revalidation is retained.
    revalidateOnFocus: false,
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
  // No name found in positions/watchlist — never surface a naked ".KS"/".KQ"
  // code (feedback_ticker_display); fall back to the seed-resolved label.
  return displayTicker(ticker);
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
  // DORMANT since e064118e — see useArtifacts. `/api/artifacts/stats` is gone;
  // callers already fall back to `deriveArtifactStats(artifacts)`, which now
  // derives from an empty list and yields zeroes rather than a 404.
  const swr = useSWR<ArtifactStats>(false && API.artifacts.stats, fetcher, {
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
  /** earnings_prebrief only — sent to the backend as `params.ticker`. */
  ticker?: string;
}

/**
 * Mirror of the unified endpoint's JSON response
 * (routes/artifacts.py:api_artifacts_generate). Generation is SYNCHRONOUS —
 * a resolved promise with status "ready" means the artifact row already
 * exists in the archive. (The pre-launch `{job_id, eta_seconds}` queue shape
 * never shipped; 2026-06-11 this type was aligned to the real backend.)
 */
export interface GenerateArtifactResponse {
  status: "ready" | "empty" | "interactive";
  type: ArtifactType;
  artifact_id: number | null;
  data: unknown;
  /** "empty" → enum like "no_positions" / "no_trades" / "not_in_portfolio". */
  reason: string | null;
  message: string | null;
  redirect: string | null;
  /** Present on "ready" — whether a PDF attachment was rendered. */
  pdf_available?: boolean;
  pdf_status?: "ok" | "unavailable" | "render_failed" | "not_applicable";
}

/**
 * On-demand artifact generation (Brag Card / Earnings Pre-Brief / Risk Board).
 * Resolves when the backend finishes generating (synchronous endpoint).
 *
 * Wire shape: optional kwargs ride under `params` — the endpoint reads
 * `params.ticker`, NOT a top-level `ticker` (2026-06-11 fix: the top-level
 * field was silently ignored, 400ing every earnings_prebrief request).
 */
export async function generateArtifact(
  body: GenerateArtifactBody,
): Promise<GenerateArtifactResponse> {
  const wire: { type: ArtifactType; params?: { ticker: string } } = {
    type: body.type,
  };
  if (body.ticker) wire.params = { ticker: body.ticker };
  // 2026-05-17 wave 12 P1: the raw `fetch(...)` here previously did NOT
  // attach the X-CSRF-Token header that `apiFetch` injects automatically.
  // Backend CSRF middleware (security.py:_csrf_protect) would reject any
  // POST from an authenticated client, so artifact generation silently
  // failed for the strict CSRF flow. Routed through `apiFetch` so CSRF +
  // timeout + sentry breadcrumbs all match the rest of the SPA.
  return apiFetch<GenerateArtifactResponse>(API.artifacts.generate, {
    method: "POST",
    body: JSON.stringify(wire),
  });
}

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

/* ── Methodology & data-provenance (Data-trust Stage 1) ──
 * Backs the /methodology transparency page. The payload is a static model
 * catalog + system data lineage, so we disable focus revalidation and dedupe
 * aggressively — it changes only on deploy. Flag-gated behind login by default
 * (METHODOLOGY_PUBLIC; Q-DT4) — `fetcher`'s credentialed request carries the
 * session cookie, so logged-in dashboard users pass; public after Q-DT4. */
export function useMethodology() {
  return useSWR<MethodologyResponse>(METHODOLOGY, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
  });
}
