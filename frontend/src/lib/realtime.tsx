"use client";

/**
 * RealtimeProvider — Singleton SSE connection for portfolio price streaming.
 *
 * Maintains a single EventSource to /api/realtime/portfolio-stream,
 * shares connection state + price data via React Context, and merges
 * incoming prices into the SWR portfolio cache so every usePortfolio()
 * consumer sees fresh data without refetching.
 *
 * Features:
 *  - Exponential backoff reconnection (1s -> 2s -> 4s -> ... -> max 30s)
 *  - Heartbeat detection (SSE comment lines)
 *  - Direction-aware updatedTickers (tracks "up" | "down" per ticker)
 *  - Automatic cleanup on provider unmount
 *  - Throttled updates (max 2 state updates/sec)
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import useSWR, { mutate as globalMutate } from "swr";
import { useAuth } from "./auth";
import { API, PORTFOLIO_POSITIONS, PORTFOLIO_SUMMARY } from "./endpoints";
import type { PortfolioResponse } from "./types";

/* ── Types ── */

export interface RealtimePriceDetail {
  price: number;
  price_display: string;
  change_pct?: number;
}

/** Direction a ticker price moved: "up" (green flash), "down" (red flash). */
export type PriceDirection = "up" | "down";

export interface RealtimeState {
  /** Flat price map: ticker -> price number */
  prices: Record<string, number>;
  /** Full detail map: ticker -> {price, price_display, change_pct} */
  details: Record<string, RealtimePriceDetail>;
  /** Whether the SSE EventSource is currently connected */
  connected: boolean;
  /** Epoch ms of the last successful data event */
  lastUpdate: number | null;
  /** Tickers that changed in the latest event, with direction */
  updatedTickers: Map<string, PriceDirection>;
  /** True when max retries exceeded — SSE gave up */
  failed: boolean;
}

const INITIAL_STATE: RealtimeState = {
  prices: {},
  details: {},
  connected: false,
  lastUpdate: null,
  updatedTickers: new Map(),
  failed: false,
};

const RealtimeContext = createContext<RealtimeState>(INITIAL_STATE);

/* ── Constants ── */

/** Base delay for exponential backoff (ms). */
const BASE_DELAY_MS = 1_000;
/** Maximum reconnection delay (ms). */
const MAX_DELAY_MS = 30_000;
/** Stop reconnecting after this many consecutive failures. */
const MAX_RETRIES = 5;
/** Duration to keep the flash indicator visible (ms). */
const FLASH_DURATION_MS = 1_500;
/** Minimum interval between state updates (ms) — throttle. */
const THROTTLE_MS = 500;

/* ── Provider ── */

/** Minimal fetcher — reads from the same endpoint usePortfolio() uses so
 *  SWR serves both from a single cache entry. We only need to know whether
 *  the user has >=1 position before opening the SSE stream (B6: the backend
 *  returns 400 when no positions exist, which triggered infinite onerror
 *  retries). */
const portfolioFetcher = async (url: string): Promise<PortfolioResponse> => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.error || r.statusText || `HTTP ${r.status}`);
  }
  return r.json();
};

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [state, setState] = useState<RealtimeState>(INITIAL_STATE);

  // Subscribe to the portfolio cache (shares a key with usePortfolio()) so
  // we can gate the SSE connection on positions.length > 0. Using useSWR
  // here with the same key is free — SWR de-duplicates by key.
  const { data: portfolioData } = useSWR<PortfolioResponse>(
    user ? API.portfolio.list : null,
    portfolioFetcher,
    { revalidateOnFocus: false, dedupingInterval: 30_000 },
  );
  const hasPositions =
    !!portfolioData && portfolioData.positions.length > 0;

  const esRef = useRef<EventSource | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const retryRef = useRef(0);
  const lastUpdateRef = useRef(0);
  const flashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Previous prices — used to determine direction. */
  const prevPricesRef = useRef<Record<string, number>>({});
  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    // Tear down existing connection
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

      // Throttle: skip if within THROTTLE_MS of last update
      const now = Date.now();
      if (now - lastUpdateRef.current < THROTTLE_MS) return;
      lastUpdateRef.current = now;

      try {
        const data = JSON.parse(event.data) as {
          prices?: Record<string, number>;
          details?: Record<string, RealtimePriceDetail & { observed_at?: string }>;
          positions?: Array<{
            ticker?: string;
            symbol?: string;
            price?: number;
            current_price?: number;
            change_pct?: number | null;
            timestamp?: string;
            observed_at?: string;
          }>;
          error?: string;
        };

        if (data.error) {
          return;
        }

        const prices: Record<string, number> = data.prices ?? {};
        const details: Record<string, RealtimePriceDetail & { observed_at?: string }> =
          data.details ?? {};

        // Determine direction per ticker
        const directionMap = new Map<string, PriceDirection>();
        const prev = prevPricesRef.current;
        for (const [ticker, price] of Object.entries(prices)) {
          if (prev[ticker] !== undefined && prev[ticker] !== price) {
            directionMap.set(ticker, price > prev[ticker] ? "up" : "down");
          }
        }

        // Store current prices for next comparison
        prevPricesRef.current = { ...prev, ...prices };

        setState({
          prices,
          details,
          connected: true,
          lastUpdate: now,
          updatedTickers: directionMap,
          failed: false,
        });

        // Clear flash after FLASH_DURATION_MS
        if (directionMap.size > 0) {
          if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
          flashTimerRef.current = setTimeout(() => {
            setState((s) => ({ ...s, updatedTickers: new Map() }));
          }, FLASH_DURATION_MS);
        }

        // Merge into the legacy SWR portfolio cache (API.portfolio.list →
        // /api/portfolio). This keeps existing consumers working.
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
                observed_at: detail.observed_at,
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

        // P0-A: Home / /portfolio pages consume /api/portfolio/positions
        // (alias shape). Mutate that cache key so SSE pushes reflect in UI.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        globalMutate(
          PORTFOLIO_POSITIONS,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (current: any) => {
            if (!current || !Array.isArray(current.positions)) return current;
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const positions = current.positions.map((p: any) => {
              const key = p.symbol || p.ticker;
              const detail = details[key];
              if (!detail) return p;
              const chg =
                detail.change_pct != null ? detail.change_pct : p.change_pct;
              return {
                ...p,
                current: detail.price,
                current_price: detail.price,
                price: detail.price,
                change_pct: chg,
                observed_at: detail.observed_at || new Date().toISOString(),
                price_source: "realtime",
              };
            });
            return { ...current, positions };
          },
          { revalidate: false },
        );

        // Optimistic summary refresh — backend totalNav = Σ(price × shares);
        // we bump observed_at so the UI "updated Xs ago" chip refreshes even
        // when the raw numbers round-trip identical.
        // P0-2 FIX: revalidate: false. Previously `revalidate: true` triggered
        // SWR to refetch /api/portfolio/summary on every SSE message, which
        // cascaded into RealtimeProvider remount → new EventSource → onerror
        // loop → ∞. In-place data update is sufficient.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        globalMutate(
          PORTFOLIO_SUMMARY,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (current: any) =>
            current
              ? { ...current, observed_at: new Date().toISOString() }
              : current,
          { revalidate: false },
        );
      } catch {
        // Ignore JSON parse errors from heartbeat comments
      }
    };

    es.onerror = () => {
      es.close();
      esRef.current = null;
      setState((s) => ({ ...s, connected: false }));

      if (ac.signal.aborted) return;

      // Give up after MAX_RETRIES consecutive failures
      if (retryRef.current >= MAX_RETRIES) {
        setState((s) => ({ ...s, connected: false, failed: true }));
        return;
      }

      // Exponential backoff: 1s, 2s, 4s, 8s, ... max 30s
      const delay = Math.min(
        BASE_DELAY_MS * 2 ** retryRef.current,
        MAX_DELAY_MS,
      );
      retryRef.current += 1;
      setTimeout(() => {
        if (!ac.signal.aborted) connectRef.current();
      }, delay);
    };
  }, []);

  useLayoutEffect(() => {
    connectRef.current = connect;
  });

  // P0-2 FIX: track whether the document is visible. Background tabs open
  // an SSE connection that the browser may starve or throttle, producing
  // errors that burn through our retry budget before the user returns.
  const [visible, setVisible] = useState<boolean>(() =>
    typeof document === "undefined" ? true : !document.hidden,
  );
  useEffect(() => {
    if (typeof document === "undefined") return;
    const onVis = () => setVisible(!document.hidden);
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  useEffect(() => {
    // Only connect SSE when user is authenticated AND owns >=1 position.
    // B6: portfolio-stream returns 400 for users with no positions, which
    // triggered the SSE `onerror` → 5 retries → persistent 400 spam in
    // the network log. Wait for usePortfolio() to resolve before connecting,
    // and auto-(dis)connect as positions appear or go to zero.
    if (!user) {
      // Tear down any existing connection on logout
      abortRef.current?.abort();
      esRef.current?.close();
      esRef.current = null;
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setState(INITIAL_STATE);
      return;
    }

    if (!hasPositions) {
      // Either portfolio still loading, or user truly has 0 positions.
      // Either way, don't open the stream yet. When positions.length
      // transitions 0 → >0 this effect re-runs and connects.
      abortRef.current?.abort();
      esRef.current?.close();
      esRef.current = null;
      return;
    }

    // P0-2 FIX: don't open SSE from a background tab. When the tab becomes
    // visible again, this effect re-runs and we connect fresh.
    if (!visible) {
      abortRef.current?.abort();
      esRef.current?.close();
      esRef.current = null;
      return;
    }

    // Reset retry counter whenever we (re-)enter the "should connect"
    // state — a prior streak of failures shouldn't carry forward.
    retryRef.current = 0;
    connect();
    return () => {
      abortRef.current?.abort();
      esRef.current?.close();
      esRef.current = null;
      if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
    };
  }, [user, hasPositions, visible, connect]);

  return (
    <RealtimeContext.Provider value={state}>
      {children}
    </RealtimeContext.Provider>
  );
}

/* ── Consumer hook ── */

/**
 * Returns the shared realtime price state.
 * Must be used inside <RealtimeProvider>.
 *
 * Returns:
 *  - prices: flat {ticker: number} map
 *  - details: full {ticker: RealtimePriceDetail} map
 *  - connected: boolean
 *  - lastUpdate: epoch ms | null
 *  - updatedTickers: Map<ticker, "up"|"down"> for flash animations
 */
export function useRealtimeContext(): RealtimeState {
  return useContext(RealtimeContext);
}
