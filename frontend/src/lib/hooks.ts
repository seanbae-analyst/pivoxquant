import useSWR from "swr";
import { apiFetch } from "./api";
import { isDemoMode, demoResponseFor } from "./demo";
import {
  API,
  PORTFOLIO_SUMMARY,
  PORTFOLIO_POSITIONS,
  PUBLIC_MARKET_SNAPSHOT,
} from "./endpoints";
import { liveRefresh } from "./market-hours";
import type {
  ProfileResponse,
  AlertsResponse,
  PreTradeJournalResponse,
  HoldingMirrorResponse,
  ConcentrationMirrorResponse,
  FrictionOutcomeResponse,
  ProfitLossMirrorResponse,
  TurnoverMirrorResponse,
  AveragingDownMirrorResponse,
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

/* `resolveTickerName(ticker, positions, watchlist)` lived here until
 * 2026-09-01. It resolved a company name from the user's positions/watchlist
 * and fell back to `displayTicker()` so a naked ".KS"/".KQ" code could never
 * reach the UI. Removed because it had ZERO callers — only a mention in a
 * format.ts comment — and it depended on the watchlist endpoint, which no
 * longer exists on the backend.
 *
 * ⚠️ The RULE it enforced still stands (feedback_ticker_display: never surface
 * a bare ticker code). `displayTicker()` in lib/format.ts is what enforces it
 * today. If you need name resolution again, rebuild it against a surface that
 * actually has data — not against watchlist.
 */

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
 * an investment-guidance surface. No signal vocabulary round-trips here.
 */

import type {
  SupportInquiriesResponse,
  SupportInquiryDetail,
  SupportInquiryCreateBody,
  SupportInquiryCreateResponse,
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

/**
 * Friction Outcome — what the pause led to. Same SWR contract as the other
 * behaviour mirrors: 404 is a soft-empty (route not deployed yet), never an
 * error banner.
 */
export function useFrictionOutcome() {
  const swr = useSWR<FrictionOutcomeResponse | null>(
    API.behavior.frictionOutcome,
    async (url: string): Promise<FrictionOutcomeResponse | null> => {
      const res = await fetch(url, { credentials: "include" });
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
