import { useState, useCallback, useMemo } from "react";
import useSWR from "swr";
import { useRealtimeContext } from "./realtime";
import { API } from "./endpoints";
import { apiFetch } from "./api";
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
  ProfileResponse,
  QuestionnaireResponse,
  AiStatusResponse,
  AiCoachingResponse,
  WatchlistResponse,
  AlertsResponse,
  MorningBriefResponse,
  MorningBriefArchiveResponse,
  FxRateResponse,
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

export function useEarnings() {
  return useSWR<EarningsResponse>(API.market.earnings, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 300_000,
  });
}

/* ── Market ── */

export function useMarketOverview() {
  return useSWR<MarketOverviewResponse>(API.market.overview, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
  });
}

export function useCrossAsset() {
  return useSWR<CrossAssetResponse>(API.quant.crossAsset, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 120_000,
  });
}

export function useVixStrategy() {
  return useSWR<VixStrategyResponse>(API.quant.vixStrategy, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 120_000,
  });
}

export function useSectors() {
  return useSWR<SectorItem[]>(API.market.sectors, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 120_000,
  });
}

export function useDaytradeScan() {
  return useSWR<DayTradeScanResponse>(API.daytrade.scan, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
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

export function useQuestionnaire() {
  return useSWR<QuestionnaireResponse>(API.profile.questionnaire, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 3600_000,
  });
}

/* ── AI ── */

export function useAiStatus() {
  return useSWR<AiStatusResponse>(API.ai.status, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 300_000,
  });
}

/**
 * Fetches AI portfolio coaching insight.
 * Uses POST endpoint — not auto-fetched by SWR. Instead, this hook
 * provides a manual `refresh` trigger and caches the result.
 */
export function useAiCoaching() {
  const [data, setData] = useState<AiCoachingResponse | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await apiFetch<AiCoachingResponse>(API.ai.coaching, {
        method: "POST",
      });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { data, error, isLoading, refresh };
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

/* ── Real-time Portfolio Prices (SSE) ── */

export { useRealtimeContext } from "./realtime";
export type { RealtimePriceDetail, PriceDirection, RealtimeState } from "./realtime";

/**
 * @deprecated Use `useRealtimeContext()` from "@/lib/realtime" for full
 * direction-aware data. This wrapper is kept for backward compatibility.
 *
 * Thin consumer of the singleton RealtimeProvider context.
 * Returns `updatedTickers` as a Set<string> (no direction info)
 * for components that only need to know *which* tickers changed.
 */
export function useRealtimePrices() {
  const ctx = useRealtimeContext();
  // Convert Map<string, PriceDirection> → Set<string> for compat
  const updatedTickers = useMemo(
    () => new Set(ctx.updatedTickers.keys()),
    [ctx.updatedTickers],
  );
  return {
    prices: ctx.prices,
    details: ctx.details,
    connected: ctx.connected,
    lastUpdate: ctx.lastUpdate,
    updatedTickers,
  };
}
