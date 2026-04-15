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
import { mutate as globalMutate } from "swr";
import { useAuth } from "./auth";
import { API } from "./endpoints";
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
}

const INITIAL_STATE: RealtimeState = {
  prices: {},
  details: {},
  connected: false,
  lastUpdate: null,
  updatedTickers: new Map(),
};

const RealtimeContext = createContext<RealtimeState>(INITIAL_STATE);

/* ── Constants ── */

/** Base delay for exponential backoff (ms). */
const BASE_DELAY_MS = 1_000;
/** Maximum reconnection delay (ms). */
const MAX_DELAY_MS = 30_000;
/** Duration to keep the flash indicator visible (ms). */
const FLASH_DURATION_MS = 1_500;
/** Minimum interval between state updates (ms) — throttle. */
const THROTTLE_MS = 500;

/* ── Provider ── */

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [state, setState] = useState<RealtimeState>(INITIAL_STATE);

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
          details?: Record<string, RealtimePriceDetail>;
          error?: string;
        };

        if (data.error) {
          return;
        }

        const prices: Record<string, number> = data.prices ?? {};
        const details: Record<string, RealtimePriceDetail> = data.details ?? {};

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
        });

        // Clear flash after FLASH_DURATION_MS
        if (directionMap.size > 0) {
          if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
          flashTimerRef.current = setTimeout(() => {
            setState((s) => ({ ...s, updatedTickers: new Map() }));
          }, FLASH_DURATION_MS);
        }

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
        // Ignore JSON parse errors from heartbeat comments
      }
    };

    es.onerror = () => {
      es.close();
      esRef.current = null;
      setState((s) => ({ ...s, connected: false }));

      if (ac.signal.aborted) return;

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

  useEffect(() => {
    // Only connect SSE when user is authenticated
    if (!user) {
      // Tear down any existing connection on logout
      abortRef.current?.abort();
      esRef.current?.close();
      esRef.current = null;
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setState(INITIAL_STATE);
      return;
    }

    connect();
    return () => {
      abortRef.current?.abort();
      esRef.current?.close();
      esRef.current = null;
      if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
    };
  }, [user, connect]);

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
