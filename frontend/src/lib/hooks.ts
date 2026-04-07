import useSWR from "swr";
import type {
  PortfolioResponse,
  AnalyticsResponse,
  HistoryResponse,
  EarningsResponse,
  MarketOverviewResponse,
  CrossAssetResponse,
  VixStrategyResponse,
  SectorItem,
  DayTradeScanResponse,
  DiscoverResponse,
} from "./types";

const fetcher = (url: string) =>
  fetch(url, { credentials: "include" }).then((r) => {
    if (!r.ok) throw new Error(r.statusText);
    return r.json();
  });

/* ── Portfolio ── */

export function usePortfolio() {
  return useSWR<PortfolioResponse>("/api/portfolio", fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 30_000,
  });
}

export function useAnalytics() {
  return useSWR<AnalyticsResponse>("/api/portfolio/analytics", fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
  });
}

export function useHistory(period = "5d") {
  return useSWR<HistoryResponse>(
    `/api/portfolio/history?period=${period}`,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 },
  );
}

export function useEarnings() {
  return useSWR<EarningsResponse>("/api/earnings", fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 300_000,
  });
}

/* ── Market ── */

export function useMarketOverview() {
  return useSWR<MarketOverviewResponse>("/api/market/overview", fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
  });
}

export function useCrossAsset() {
  return useSWR<CrossAssetResponse>("/api/cross-asset", fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 120_000,
  });
}

export function useVixStrategy() {
  return useSWR<VixStrategyResponse>("/api/vix-strategy", fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 120_000,
  });
}

export function useSectors() {
  return useSWR<SectorItem[]>("/api/sectors", fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 120_000,
  });
}

export function useDaytradeScan() {
  return useSWR<DayTradeScanResponse>("/api/daytrade/scan", fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
  });
}

export function useDiscover() {
  return useSWR<DiscoverResponse>("/api/discover", fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 600_000,
  });
}
