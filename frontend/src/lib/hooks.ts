import useSWR from "swr";
import { API, PORTFOLIO_SUMMARY, PORTFOLIO_POSITIONS } from "./endpoints";
import { liveRefresh } from "./market-hours";
import type {
  DiscoverResponse,
  ProfileResponse,
  WatchlistResponse,
  AlertsResponse,
  MorningBriefResponse,
  MorningBriefArchiveResponse,
  GrowthScoreEntry,
  GrowthTodayResponse,
  GrowthWeeklyReport,
  ArtifactsListResponse,
  ArtifactType,
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
  });
}

export function useInvestmentProfile() {
  return useSWR<ProfileResponse>(API.profile.get, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 300_000,
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
  });
}

/* ── Morning Brief ── */

export function useMorningBrief() {
  return useSWR<MorningBriefResponse>(
    API.market.morningBriefToday,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 * 10 },
  );
}

export function useMorningBriefArchive() {
  return useSWR<MorningBriefArchiveResponse>(
    API.market.morningBriefArchive,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 * 30 },
  );
}

/* ── Growth OS ── */

export function useGrowthData(range = "365d") {
  return useSWR<GrowthScoreEntry[]>(
    API.growth.data(range),
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 },
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
    { revalidateOnFocus: false, dedupingInterval: 300_000 },
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
