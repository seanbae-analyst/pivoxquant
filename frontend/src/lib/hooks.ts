import useSWR from "swr";
import { API } from "./endpoints";
import type {
  PortfolioResponse,
  AnalyticsResponse,
  HistoryResponse,
  MarketOverviewResponse,
  SectorItem,
  DiscoverResponse,
  ProfileResponse,
  WatchlistResponse,
  AlertsResponse,
  MorningBriefResponse,
  MorningBriefArchiveResponse,
  FxRateResponse,
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

/* ── Portfolio ── */

export function usePortfolio() {
  return useSWR<PortfolioResponse>(API.portfolio.list, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 30_000,
  });
}

export function useAnalytics() {
  return useSWR<AnalyticsResponse>(API.portfolio.analytics, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
  });
}

export function useHistory(period = "5d") {
  return useSWR<HistoryResponse>(
    API.portfolio.history(period),
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 },
  );
}

/* ── Market ── */

export function useMarketOverview() {
  return useSWR<MarketOverviewResponse>(API.market.overview, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
  });
}

export function useSectors() {
  return useSWR<SectorItem[]>(API.market.sectors, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 120_000,
  });
}

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

/* ── FX Rate ── */

/**
 * Live USD/KRW exchange rate. Polls every 30 seconds for near-realtime
 * cross-currency math. The backend scheduler refreshes the underlying
 * rate every 1 minute, so this cadence surfaces updates within ~30s of
 * the upstream fetch while staying cheap (memory-only on the server).
 *
 * Falls back to 1400 if the endpoint is unreachable.
 *
 * Returns:
 *   rate: current USD→KRW rate (number)
 *   stale: true if backend reports the rate is > 10 minutes old
 *   lastUpdated: ISO-8601 UTC timestamp of the last successful upstream fetch
 *   ageSeconds: seconds since last successful fetch (-1 if never)
 *   isLoading / error: SWR state flags
 */
export function useFxRate() {
  const { data, error, isLoading } = useSWR<FxRateResponse>(
    API.market.fx,
    fetcher,
    {
      refreshInterval: 30_000,    // 30s — tighter than backend cadence for snappy UI
      dedupingInterval: 15_000,   // block duplicate in-flight requests within 15s
      revalidateOnFocus: true,    // refresh when user returns to the tab
    },
  );
  return {
    rate: data?.usd_krw ?? 1400,
    stale: data?.is_stale ?? data?.stale ?? false,
    lastUpdated: data?.last_updated ?? null,
    ageSeconds: data?.age_seconds ?? -1,
    isLoading,
    error,
  };
}

/* ── Watchlist ── */

export function useWatchlist() {
  return useSWR<WatchlistResponse>(API.watchlist.list, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 30_000,
  });
}

/* ── Alerts ── */

export function useAlerts() {
  return useSWR<AlertsResponse>(API.alerts.list, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 30_000,
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

/* ── Broker connections (KIS / Kiwoom / Alpaca status) ── */

export interface BrokerConnectionsResponse {
  kis_connected?: boolean;
  kiwoom_connected?: boolean;
  alpaca_connected?: boolean;
  kis_last_sync?: string | null;
  kiwoom_last_upload?: string | null;
  alpaca_last_sync?: string | null;
}

export function useBrokerConnections() {
  return useSWR<BrokerConnectionsResponse>(
    API.broker.connections,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 30_000 },
  );
}

/* ── Real-time Portfolio Prices (SSE) ── */

export { useRealtimeContext } from "./realtime";
export type { RealtimePriceDetail, PriceDirection, RealtimeState } from "./realtime";
