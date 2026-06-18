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
 *  - Exponential backoff with jitter (1s → 2s → 4s → 8s → 16s → 32s → 60s cap)
 *    plus 50-100% jitter multiplier to prevent thundering-herd reconnects
 *    after a backend restart
 *  - Reconnect paused while document.visibilityState !== "visible"
 *  - Reset attempt counter on successful onopen
 *  - Heartbeat detection (SSE comment lines)
 *  - Direction-aware updatedTickers (tracks "up" | "down" per ticker)
 *  - Automatic cleanup on provider unmount (cancels pending reconnect timers)
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
import { isDemoMode, demoResponseFor } from "./demo";

/* ── Types ── */

export interface RealtimePriceDetail {
  price: number;
  price_display: string;
  change_pct?: number;
  /**
   * Wave F-2 Bug #1: true when the backend served this quote from the
   * fmp_stale cache (FMP 402 cooldown / daily-budget exhausted). UI
   * surfaces (top-ticker, portfolio rows) must render a visible "STALE"
   * chip when set — capital-markets-law §6 misrepresentation guard.
   */
  stale?: boolean;
  /** ISO/epoch timestamp when the cached value was last observed live. */
  stale_at?: string | number | null;
  /** Provider key: "kis" | "kis_ws" | "fmp" | "fmp_stale". */
  source?: string;
  /** ISO timestamp of the most recent observation forwarded by the backend. */
  observed_at?: string | null;
}

/** Direction a ticker price moved: "up" (green flash), "down" (red flash). */
export type PriceDirection = "up" | "down";

export interface RealtimeState {
  /** Flat price map: ticker -> price number */
  prices: Record<string, number>;
  /** Full detail map: ticker -> {price, price_display, change_pct, stale, ...} */
  details: Record<string, RealtimePriceDetail>;
  /** Whether the SSE EventSource is currently connected */
  connected: boolean;
  /** Epoch ms of the last successful data event */
  lastUpdate: number | null;
  /** Tickers that changed in the latest event, with direction */
  updatedTickers: Map<string, PriceDirection>;
  /** True when max retries exceeded — SSE gave up */
  failed: boolean;
  /**
   * Wave F-2 Bug #2: distinct from `failed`. True when the backend
   * sent an explicit ``event: error`` (e.g. SSE_LIMIT_EXCEEDED — the
   * user already has 3 concurrent streams open in other tabs). The
   * UI should stop retrying and tell the user *why*; the auto-reconnect
   * exponential backoff that powers `failed` is the wrong UX here.
   */
  limitExceeded: boolean;
  /**
   * True when the provider is actively trying to maintain an SSE connection
   * (i.e. user is signed in, has positions, and tab is visible). False when
   * the stream is intentionally torn down (logged out, 0 positions, hidden
   * tab). Used by the status banner to distinguish "intentionally idle"
   * from "trying but disconnected" — without this, the yellow "재연결 중"
   * banner would show forever for any user with no positions.
   */
  streamActive: boolean;
}

/**
 * Shape of an individual row in GET /api/portfolio/positions (alias endpoint;
 * see routes/portfolio.py `_build_positions_list`). We only type the fields we
 * actually read or overwrite here — extra backend fields (side, purchaseDate,
 * notes, sector, isKorean, name, ...) are preserved via rest-spread.
 *
 * Both `symbol` and `ticker` are accepted because legacy callers sometimes
 * seed the cache with a `Position` shape (src/lib/types.ts). At runtime at
 * least one of the two is present; `key` falls back between them.
 */
interface PositionAliasRow {
  symbol?: string;
  ticker?: string;
  current?: number;
  current_price?: number;
  price?: number;
  change_pct?: number;
  observed_at?: string | null;
  price_source?: string;
  /** Wave F-2 Bug #1: forward stale flag to row consumers. */
  stale?: boolean;
  stale_at?: string | number | null;
  /** Preserve any additional backend fields we don't explicitly touch. */
  [key: string]: unknown;
}

/** Cache body for the PORTFOLIO_POSITIONS SWR key. */
interface PositionsAliasResponse {
  positions: PositionAliasRow[];
  [key: string]: unknown;
}

/**
 * Cache body for the PORTFOLIO_SUMMARY SWR key (see
 * routes/portfolio.py `portfolio_summary_alias`). We only set `observed_at`
 * in-place so the UI "updated Xs ago" chip refreshes; all KPI fields
 * (totalNav, todayPnl, etc.) are left untouched via rest-spread.
 */
interface PortfolioSummaryCache {
  observed_at?: string;
  [key: string]: unknown;
}

const INITIAL_STATE: RealtimeState = {
  prices: {},
  details: {},
  connected: false,
  lastUpdate: null,
  updatedTickers: new Map(),
  failed: false,
  limitExceeded: false,
  streamActive: false,
};

const RealtimeContext = createContext<RealtimeState>(INITIAL_STATE);

/* ── Constants ── */

/**
 * Exponential-backoff schedule for SSE reconnects (ms).
 * Indexed by `retryRef.current`; values past the end are clamped to the
 * final entry (60 s). Each scheduled delay is multiplied by a jitter factor
 * in [0.5, 1.0) to spread reconnect attempts after a backend restart and
 * avoid a thundering herd.
 */
const RECONNECT_DELAYS_MS = [
  1_000, 2_000, 4_000, 8_000, 16_000, 32_000, 60_000,
] as const;
/** Stop reconnecting after this many consecutive failures. */
const MAX_RETRIES = RECONNECT_DELAYS_MS.length;
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
  if (isDemoMode()) return demoResponseFor(url).body as PortfolioResponse;
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
    !!portfolioData && Array.isArray(portfolioData.positions) && portfolioData.positions.length > 0;

  const esRef = useRef<EventSource | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const retryRef = useRef(0);
  const lastUpdateRef = useRef(0);
  const flashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Pending reconnect timer (must be cleared on cleanup so unmount is clean). */
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Previous prices — used to determine direction. */
  const prevPricesRef = useRef<Record<string, number>>({});
  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    // Tear down existing connection + any pending reconnect timer so we
    // don't end up with two EventSources racing.
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    // Mark the stream as actively trying — the status banner reads this
    // to distinguish "intentionally idle" (no user / no positions / hidden
    // tab) from "trying but disconnected" (yellow banner).
    setState((s) => (s.streamActive ? s : { ...s, streamActive: true }));

    const ac = new AbortController();
    abortRef.current = ac;

    const es = new EventSource(API.realtime.portfolioStream);
    esRef.current = es;

    es.onopen = () => {
      retryRef.current = 0;
      setState((s) => ({
        ...s,
        connected: true,
        streamActive: true,
        // A fresh successful open clears any prior limit-exceeded state.
        limitExceeded: false,
      }));
    };

    // Wave F-2 Bug #2: backend signals SSE_LIMIT_EXCEEDED as a 200
    // text/event-stream with a single ``event: error`` payload (not a
    // 429). EventSource can't read a non-200 body, so a JSON 429 would
    // surface only as ``onerror`` → 7-step backoff → permanent
    // ``failed:true`` with no diagnostic. Handle the named event
    // explicitly: stop retrying, set ``limitExceeded`` so the status
    // banner can show an actionable message ("이미 다른 탭에서…"),
    // and tear down without scheduling a reconnect.
    es.addEventListener("error", (event: MessageEvent) => {
      if (ac.signal.aborted) return;
      let code: string | undefined;
      try {
        const body = JSON.parse(event.data ?? "{}");
        code = body?.code;
      } catch {
        // Native EventSource ``onerror`` events have no data field —
        // those are handled by the assignment-based ``es.onerror``
        // below. Only the backend-emitted ``event: error`` carries
        // a JSON body, so a parse failure means this is a transport
        // error to be handled by the reconnect path.
        return;
      }
      if (code === "SSE_LIMIT_EXCEEDED") {
        es.close();
        esRef.current = null;
        retryRef.current = MAX_RETRIES; // belt+suspenders: stop reconnects
        setState((s) => ({
          ...s,
          connected: false,
          streamActive: false,
          limitExceeded: true,
        }));
      }
    });

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
            stale?: boolean;
            stale_at?: string | number | null;
            price_source?: string;
          }>;
          error?: string;
        };

        if (data.error) {
          return;
        }

        const prices: Record<string, number> = data.prices ?? {};
        const details: Record<string, RealtimePriceDetail & { observed_at?: string }> =
          data.details ?? {};

        // Transient all-provider failure (FMP 402 + KIS down) sends an empty
        // price payload. Skip it ONLY when we previously had prices — keep the
        // last-known values on screen (they age into "stale" via lastUpdate) instead
        // of blanking the portfolio. A genuinely empty book (0 positions) has an
        // empty prevPricesRef too, so this guard never blocks the legitimate empty
        // state.
        if (
          Object.keys(prices).length === 0 &&
          Object.keys(details).length === 0 &&
          Object.keys(prevPricesRef.current).length > 0
        ) {
          return;
        }

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

        setState((s) => ({
          ...s,
          prices,
          details,
          connected: true,
          lastUpdate: now,
          updatedTickers: directionMap,
          failed: false,
          // A successful payload clears any prior limit-exceeded flag.
          limitExceeded: false,
          streamActive: true,
        }));

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
        globalMutate(
          PORTFOLIO_POSITIONS,
          (current: PositionsAliasResponse | undefined) => {
            if (!current || !Array.isArray(current.positions)) return current;
            const positions = current.positions.map((p: PositionAliasRow) => {
              const key = p.symbol || p.ticker;
              if (!key) return p;
              const detail = details[key];
              if (!detail) return p;
              const chg =
                detail.change_pct != null ? detail.change_pct : p.change_pct;
              // Wave F-2 Bug #1: a stale detail tagged by the backend
              // (fmp_stale fallback) must propagate to row consumers
              // so the "지연" chip renders on /portfolio rows — not
              // just on the ribbon. Same misrepresentation guard as
              // the landing ticker (PR #381).
              const isStale = detail.stale === true;
              return {
                ...p,
                current: detail.price,
                current_price: detail.price,
                price: detail.price,
                change_pct: chg,
                observed_at: detail.observed_at || new Date().toISOString(),
                stale: isStale,
                stale_at: detail.stale_at ?? null,
                price_source: isStale
                  ? (detail.source ?? "fmp_stale")
                  : (detail.source ?? "realtime"),
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
        globalMutate(
          PORTFOLIO_SUMMARY,
          (current: PortfolioSummaryCache | undefined) =>
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

      // Explicit disconnect (cleanup / unmount / logout / tab hidden):
      // never schedule a reconnect.
      if (ac.signal.aborted) return;

      // Pause reconnect attempts while the tab is hidden — the
      // visibilitychange effect will trigger a fresh connect() once the
      // user returns. Don't burn through the retry budget in the
      // background.
      if (typeof document !== "undefined" && document.hidden) return;

      // Give up after MAX_RETRIES consecutive failures
      if (retryRef.current >= MAX_RETRIES) {
        setState((s) => ({ ...s, connected: false, failed: true }));
        return;
      }

      // Exponential backoff schedule (1s, 2s, 4s, 8s, 16s, 32s, 60s cap)
      // with 50–100% jitter to avoid thundering-herd reconnects when the
      // backend restarts and many clients hit it at once.
      const baseDelay =
        RECONNECT_DELAYS_MS[
          Math.min(retryRef.current, RECONNECT_DELAYS_MS.length - 1)
        ];
      const jittered = baseDelay * (0.5 + Math.random() * 0.5);
      retryRef.current += 1;

      // Track the timer so cleanup can cancel a pending reconnect.
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null;
        if (ac.signal.aborted) return;
        if (typeof document !== "undefined" && document.hidden) return;
        connectRef.current();
      }, jittered);
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
    /** Explicit disconnect — used by logout / no-positions / hidden-tab /
     *  unmount branches. Aborts the AbortController so a queued reconnect
     *  bails out, closes any open EventSource, and cancels a pending
     *  reconnect timer (otherwise it would re-open a connection after
     *  unmount). */
    const teardown = () => {
      abortRef.current?.abort();
      esRef.current?.close();
      esRef.current = null;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      // P2 (2026-05-22): prevPricesRef survives logout/no-positions teardown,
      // so on next login the first tick compares the new user's prices against
      // the previous user's stale prices and flashes a wrong up/down direction.
      // Reset it alongside the state so direction tracking starts clean. (It is
      // also the empty-payload guard's "have we seen prices?" signal, so a
      // clean teardown correctly treats the next session as fresh.)
      prevPricesRef.current = {};
      // Banner reads streamActive to know we're no longer trying — clears
      // the persistent yellow "재연결 중" for users with no positions / hidden tab.
      setState((s) =>
        s.streamActive || s.connected
          ? { ...s, streamActive: false, connected: false }
          : s,
      );
    };

    // Only connect SSE when user is authenticated AND owns >=1 position.
    // B6: portfolio-stream returns 400 for users with no positions, which
    // triggered the SSE `onerror` → 5 retries → persistent 400 spam in
    // the network log. Wait for usePortfolio() to resolve before connecting,
    // and auto-(dis)connect as positions appear or go to zero.
    if (!user) {
      teardown();
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setState(INITIAL_STATE);
      return;
    }

    if (!hasPositions) {
      // Either portfolio still loading, or user truly has 0 positions.
      // Either way, don't open the stream yet. When positions.length
      // transitions 0 → >0 this effect re-runs and connects.
      teardown();
      return;
    }

    // P0-2 FIX: don't open SSE from a background tab. When the tab becomes
    // visible again, this effect re-runs and we connect fresh.
    if (!visible) {
      teardown();
      return;
    }

    // Reset retry counter whenever we (re-)enter the "should connect"
    // state — a prior streak of failures shouldn't carry forward.
    retryRef.current = 0;
    connect();
    return () => {
      teardown();
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

/* ── Status-only hook ── */

/**
 * Lightweight subscription to just the connection-status slice of
 * RealtimeState — for components (banners, indicators) that only care
 * whether the SSE stream is healthy and shouldn't re-render on every
 * price tick.
 *
 * Returns:
 *  - connected: SSE EventSource is currently open
 *  - failed:    MAX_RETRIES exceeded — stream gave up; user is seeing stale prices
 *  - lastUpdate: epoch ms of the last successful data event (null if never)
 *
 * Rendering rules (consumed by <RealtimeStatusBanner />):
 *  - !streamActive                                 → no banner (idle by design)
 *  - streamActive && failed                        → red  "연결 실패"
 *  - streamActive && !connected && !failed         → yellow "재연결 중"
 *  - streamActive && connected                     → no banner
 */
export function useRealtimeStatus(): {
  connected: boolean;
  failed: boolean;
  streamActive: boolean;
  lastUpdate: number | null;
} {
  const ctx = useContext(RealtimeContext);
  return {
    connected: ctx.connected,
    failed: ctx.failed,
    streamActive: ctx.streamActive,
    lastUpdate: ctx.lastUpdate,
  };
}
