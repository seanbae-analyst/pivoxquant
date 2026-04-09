import { useEffect, useRef, useState, useCallback } from "react";
import useSWR, { mutate as globalMutate } from "swr";
import { API } from "./endpoints";
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
} from "./types";

const fetcher = (url: string) =>
  fetch(url, { credentials: "include" }).then((r) => {
    if (!r.ok) throw new Error(r.statusText);
    return r.json();
  });

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

/* ── Real-time Portfolio Prices (SSE) ── */

export interface RealtimePriceDetail {
  price: number;
  price_display: string;
  change_pct?: number;
}

export interface RealtimePricesState {
  prices: Record<string, number>;
  details: Record<string, RealtimePriceDetail>;
  connected: boolean;
  lastUpdate: number | null;
}

/**
 * Connects to the portfolio-stream SSE endpoint.
 * Merges incoming price updates into the SWR portfolio cache so
 * every component that calls usePortfolio() sees fresh prices
 * without a full refetch.
 *
 * Returns `updatedTickers` — the set of tickers that changed in
 * the most recent SSE event, useful for flash animations.
 */
export function useRealtimePrices() {
  const [state, setState] = useState<RealtimePricesState>({
    prices: {},
    details: {},
    connected: false,
    lastUpdate: null,
  });
  const [updatedTickers, setUpdatedTickers] = useState<Set<string>>(new Set());
  const retryRef = useRef(0);
  const esRef = useRef<EventSource | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const connect = useCallback(() => {
    // Clean up any existing connection
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    const ac = new AbortController();
    abortRef.current = ac;

    const es = new EventSource(API.realtime.portfolioStream);
    esRef.current = es;

    es.onopen = () => {
      retryRef.current = 0;
      setState((s) => ({ ...s, connected: true }));
    };

    es.onmessage = (event) => {
      if (ac.signal.aborted) return;
      try {
        const data = JSON.parse(event.data);
        if (data.error) {
          console.warn("[SSE] server error:", data.error);
          return;
        }

        const prices: Record<string, number> = data.prices ?? {};
        const details: Record<string, RealtimePriceDetail> = data.details ?? {};
        const now = Date.now();

        // Track which tickers actually changed
        setState((prev) => {
          const changed = new Set<string>();
          for (const [ticker, price] of Object.entries(prices)) {
            if (prev.prices[ticker] !== price) {
              changed.add(ticker);
            }
          }
          setUpdatedTickers(changed);

          // Clear the flash after 1.5s
          if (changed.size > 0) {
            setTimeout(() => setUpdatedTickers(new Set()), 1500);
          }

          return { prices, details, connected: true, lastUpdate: now };
        });

        // Merge into SWR portfolio cache
        globalMutate(
          API.portfolio.list,
          (current: PortfolioResponse | undefined) => {
            if (!current) return current;
            const updated = current.positions.map((pos) => {
              const detail = details[pos.ticker];
              if (!detail) return pos;
              return {
                ...pos,
                price: detail.price,
                current_price: detail.price,
                price_display: detail.price_display,
                // Recalculate P&L %
                pnl_pct:
                  pos.avg_cost > 0
                    ? ((detail.price - pos.avg_cost) / pos.avg_cost) * 100
                    : pos.pnl_pct,
                market_value: detail.price * pos.shares,
              };
            });
            return { ...current, positions: updated };
          },
          { revalidate: false },
        );
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      es.close();
      esRef.current = null;
      setState((s) => ({ ...s, connected: false }));

      if (ac.signal.aborted) return;

      // Exponential backoff: 2s, 4s, 8s, … max 60s
      const delay = Math.min(2000 * 2 ** retryRef.current, 60_000);
      retryRef.current += 1;
      setTimeout(() => {
        if (!ac.signal.aborted) connect();
      }, delay);
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      abortRef.current?.abort();
      esRef.current?.close();
      esRef.current = null;
    };
  }, [connect]);

  return { ...state, updatedTickers };
}
