"use client";

/**
 * Discover — Vantablack ink terminal card on ivory shell.
 *
 * Sections:
 *   1. Market overview — 5 indices small dark cards
 *   2. Top movers US (gainers / losers)
 *   3. Top movers KR (gainers / losers)
 *   4. Sector rotation (1D / 5D / 1M)
 *   5. Thematic screeners (oversold / 52W highs / earnings beats)
 *   6. Live engine scan (best-effort)
 *
 * Neutral observation language only.
 */

import { useMemo, useState, useCallback, useEffect } from "react";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import {
  API,
  DISCOVER_OVERVIEW,
  DISCOVER_MOVERS,
  DISCOVER_SECTORS,
  DISCOVER_SCREENERS,
} from "@/lib/endpoints";
import { apiFetch, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { fmtPct, pctColorClass, displayName, displayTicker, normalizeTicker } from "@/lib/format";
import { useDiscover, usePortfolioPositions, useWatchlist } from "@/lib/hooks";
import type { DiscoverResult, Position } from "@/lib/types";
import { relativeTime, useNowTick } from "@/lib/market";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  Caption,
  Fleuron as PqFleuron,
  FootSignature,
  RuledKicker,
} from "@/components/ui/editorial";

// Mock fallback data was removed (2026-04-28). Displaying stale 2024 hard-coded
// prices as if they were live misled users and created a capital-markets-law
// misrepresentation risk. When the upstream feed fails we now render an
// explicit "data unavailable" editorial state instead of fake numbers.

const jsonFetcher = <T,>(url: string) => apiFetch<T>(url);

interface BackendOverviewItem { name: string; symbol: string; level: number; change_pct: number; observed_at?: string; is_stale?: boolean; proxy_ticker?: string; }
interface BackendMover { ticker: string; name: string; price: number; change_pct: number; }
interface BackendMoversResponse { region: string; gainers: BackendMover[]; losers: BackendMover[]; }
// d5 / m1 are now `number | null`: the backend no longer fabricates them
// from d1×2.5 / d1×5.0 — when the multi-day window is unavailable it sends
// null, and we render "—" rather than a misleading derived figure.
interface BackendSectorRow { sector: string; d1: number; d5: number | null; m1: number | null; }
interface BackendScreenerItem { ticker: string; name: string; metric: string; metric_value: string; }
interface BackendScreeners {
  oversold_rsi: BackendScreenerItem[];
  highs_52w: BackendScreenerItem[];
  earnings_beats: BackendScreenerItem[];
}

function weekTag(): string {
  const d = new Date();
  const first = new Date(d.getFullYear(), 0, 1);
  const days = Math.floor((d.getTime() - first.getTime()) / 86400000);
  const w = Math.ceil((days + first.getDay() + 1) / 7);
  return `${d.getFullYear()} · W${String(w).padStart(2, "0")}`;
}

function deltaCls(v: number | null | undefined) {
  // KR convention (CEO directive 2026-04-26): ▲ rising = red, ▼ falling = blue.
  if (v == null) return "text-[rgba(245,240,232,0.55)]";
  if (v > 0) return "text-[#d18888]";
  if (v < 0) return "text-[#7aa0c8]";
  return "text-[rgba(245,240,232,0.55)]";
}

// Fleuron ornament — consistent with portfolio empty-state convention
function Fleuron() {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className="mx-auto opacity-30"
    >
      <path
        d="M12 2C12 2 9 6 9 9C9 12 12 14 12 14C12 14 15 12 15 9C15 6 12 2 12 2Z"
        fill="currentColor"
      />
      <path
        d="M12 22C12 22 15 18 15 15C15 12 12 10 12 10C12 10 9 12 9 15C9 18 12 22 12 22Z"
        fill="currentColor"
      />
      <path
        d="M2 12C2 12 6 9 9 9C12 9 14 12 14 12C14 12 12 15 9 15C6 15 2 12 2 12Z"
        fill="currentColor"
      />
      <path
        d="M22 12C22 12 18 15 15 15C12 15 10 12 10 12C10 12 12 9 15 9C18 9 22 12 22 12Z"
        fill="currentColor"
      />
    </svg>
  );
}

export default function DiscoverPage() {
  const router = useRouter();
  const { data, isLoading, error, mutate } = useDiscover();
  const [scanning, setScanning] = useState(false);

  // Aggregate load error: all primary SWR calls failed and no data
  const hasLoadError = Boolean(error) && !data;

  // Discover is editorial; backend 2h-caches to absorb FMP 402 bursts.
  // Client refresh at 5min so users see fresh content without stampeding upstream.
  const discoverOpts = {
    refreshInterval: 300_000,
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 60_000,
    errorRetryCount: 2,
    errorRetryInterval: 10_000,
  } as const;
  const { data: overviewLive, mutate: mutateOverview } = useSWR<BackendOverviewItem[]>(DISCOVER_OVERVIEW, jsonFetcher, { ...discoverOpts, fallbackData: [] });
  const { data: usMovers, mutate: mutateUsMovers } = useSWR<BackendMoversResponse>(`${DISCOVER_MOVERS}?region=us`, jsonFetcher, discoverOpts);
  const { data: krMovers, mutate: mutateKrMovers } = useSWR<BackendMoversResponse>(`${DISCOVER_MOVERS}?region=kr`, jsonFetcher, discoverOpts);
  const { data: sectorsLive, mutate: mutateSectors } = useSWR<BackendSectorRow[]>(DISCOVER_SECTORS, jsonFetcher, discoverOpts);
  const { data: screenersLive, mutate: mutateScreeners } = useSWR<BackendScreeners>(DISCOVER_SCREENERS, jsonFetcher, discoverOpts);

  // BUG A fix (movers cold-load race): /api/discover/movers reads the
  // per-user `discover_cache` that the base scan (useDiscover → /api/discover)
  // populates. On mount both fire in parallel, so movers reads the cache
  // before the (slower) base scan finishes and 503s / renders empty, only
  // recovering after the 5-min refreshInterval. Re-validate the movers SWRs
  // once the base scan resolves so Top Movers recovers immediately.
  useEffect(() => {
    if (!isLoading) {
      void mutateUsMovers();
      void mutateKrMovers();
    }
  }, [isLoading, data, mutateUsMovers, mutateKrMovers]);

  // §101 회피 (2026-04-29): Engine Scan 결과를 사용자 보유/관심 종목 화이트리스트로
  // 한정. 백엔드도 동일 가드를 추가하나, 프론트에서도 백업 가드를 유지해
  // 임의 종목 시그널이 노출되는 회색지대를 차단.
  const positionsSwr = usePortfolioPositions<{ positions?: Position[] }>();
  const watchlistSwr = useWatchlist();
  const userTickerSet = useMemo(() => {
    const s = new Set<string>();
    // Backend `/api/portfolio/positions` (routes/portfolio.py::_build_positions_list)
    // serializes the ticker under the `symbol` key, NOT `ticker` — the legacy
    // /api/portfolio endpoint used `ticker`, which is what `Position` in
    // lib/types.ts still names. Read both so this scope guard works regardless
    // of which endpoint shape SWR happens to return; without `symbol`, every
    // production user with positions saw "Add holdings or watchlist symbols"
    // and the §101 scope filter blocked their own Engine Scan results
    // (verified live 2026-05-01: 3 positions, hasUserScope still false).
    (positionsSwr.data?.positions ?? []).forEach((p) => {
      const t =
        (p as Position & { symbol?: string }).symbol ?? p.ticker;
      if (t) s.add(t.toUpperCase());
    });
    (watchlistSwr.data?.watchlist ?? []).forEach((w) => {
      if (w.ticker) s.add(w.ticker.toUpperCase());
    });
    return s;
  }, [positionsSwr.data, watchlistSwr.data]);
  const hasUserScope = userTickerSet.size > 0;

  const results = useMemo(() => {
    const all = data?.results ?? [];
    if (!hasUserScope) return [] as typeof all;
    return all.filter((r) => r.ticker && userTickerSet.has(r.ticker.toUpperCase()));
  }, [data?.results, userTickerSet, hasUserScope]);
  const hasLive = results.length > 0;
  const liveFailed = Boolean(error) && !hasLive;

  const overviewItems = useMemo(() => {
    // Never fall back to MOCK_INDICES (2024 hardcoded values) — displaying
    // stale 2024 prices as if they were live misleads users and creates a
    // capital-markets-law misrepresentation risk. Return empty so the UI
    // renders a "data unavailable" editorial state instead of fake numbers.
    if (!overviewLive || overviewLive.length === 0) {
      return [] as Array<{ name: string; level: string; changePct: number; observed_at: string | undefined; is_stale: boolean; proxy_ticker?: string }>;
    }
    return overviewLive.map((o) => ({
      name: o.name,
      level: typeof o.level === "number"
        ? o.level.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
        : String(o.level),
      changePct: o.change_pct,
      observed_at: o.observed_at,
      is_stale: Boolean(o.is_stale),
      // Carry the ETF proxy through so the row can disclose "via SPY" — the
      // backend sends it (routes/discover.py) but it was being dropped here,
      // leaving an ETF share price (SPY ~$600) labelled as "S&P 500" with no
      // disclosure. The /market page already discloses it (ProxyPill); this is
      // surface parity (capital-markets-law misrepresentation guard).
      proxy_ticker: o.proxy_ticker,
    }));
  }, [overviewLive]);

  // 1s tick for re-rendering relative timestamps.
  const nowMs = useNowTick(1000);

  const fmtMoverPrice = (price: number, isKr: boolean) =>
    isKr
      ? `KRW ${Math.round(price).toLocaleString("ko-KR")}`
      : `USD ${price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  // All `?? MOCK_*` fallbacks removed 2026-04-28 — backend 503 / FMP 402
  // must not be papered over with hardcoded 2024 prices (legal risk).
  // Empty arrays produce <EmptyBlock/> editorial fallbacks below.
  const usGainers = useMemo(
    () => (usMovers?.gainers?.length ? usMovers.gainers : []).map((r) => ({
      ticker: r.ticker, name: r.name, price: fmtMoverPrice(r.price, false), changePct: r.change_pct,
    })),
    [usMovers],
  );
  const usLosers = useMemo(
    () => (usMovers?.losers?.length ? usMovers.losers : []).map((r) => ({
      ticker: r.ticker, name: r.name, price: fmtMoverPrice(r.price, false), changePct: r.change_pct,
    })),
    [usMovers],
  );
  const krGainers = useMemo(
    () => (krMovers?.gainers?.length ? krMovers.gainers : []).map((r) => ({
      ticker: r.ticker, name: r.name, price: fmtMoverPrice(r.price, true), changePct: r.change_pct,
    })),
    [krMovers],
  );
  const krLosers = useMemo(
    () => (krMovers?.losers?.length ? krMovers.losers : []).map((r) => ({
      ticker: r.ticker, name: r.name, price: fmtMoverPrice(r.price, true), changePct: r.change_pct,
    })),
    [krMovers],
  );
  const sectorRows = useMemo(
    () => sectorsLive && sectorsLive.length >= 3
      ? sectorsLive.map((s) => ({ sector: s.sector, d1: s.d1, d5: s.d5, m1: s.m1 }))
      : [],
    [sectorsLive],
  );
  // §101 회피 (2026-04-29): Thematic Signals도 보유/관심 종목으로 한정.
  // 임의 종목에 POSITIVE/NEGATIVE pill을 노출하면 자문 회색지대.
  const filterToScope = useCallback(
    <T extends { ticker: string }>(list: T[]) =>
      hasUserScope
        ? list.filter((x) => x.ticker && userTickerSet.has(x.ticker.toUpperCase()))
        : [],
    [hasUserScope, userTickerSet],
  );

  const oversold = useMemo(
    () => filterToScope(
      (screenersLive?.oversold_rsi?.length ? screenersLive.oversold_rsi : []).map((x) => ({
        ticker: x.ticker, name: x.name, metric: x.metric, metricValue: x.metric_value,
      })),
    ),
    [screenersLive, filterToScope],
  );
  const highs52w = useMemo(
    () => filterToScope(
      (screenersLive?.highs_52w?.length ? screenersLive.highs_52w : []).map((x) => ({
        ticker: x.ticker, name: x.name, metric: x.metric, metricValue: x.metric_value,
      })),
    ),
    [screenersLive, filterToScope],
  );
  const earnings = useMemo(
    () => filterToScope(
      (screenersLive?.earnings_beats?.length ? screenersLive.earnings_beats : []).map((x) => ({
        ticker: x.ticker, name: x.name, metric: x.metric, metricValue: x.metric_value,
      })),
    ),
    [screenersLive, filterToScope],
  );

  const handleScan = useCallback(async () => {
    setScanning(true);
    try {
      await apiFetch(`${API.discover}?force=1`);
      await mutate();
      // BUG B fix: the base mutate() above only revalidates useDiscover (the
      // live engine-scan card). The section SWRs (movers/overview/sectors/
      // screeners) have separate keys, so without this they keep showing the
      // pre-scan (often empty) cache until the 5-min refreshInterval. movers
      // in particular reads the discover_cache the force-scan just rebuilt.
      await Promise.allSettled([
        mutateUsMovers(),
        mutateKrMovers(),
        mutateOverview(),
        mutateSectors(),
        mutateScreeners(),
      ]);
    } catch (err) {
      // Bug NEW-A fix (2026-05-08): the previous `catch { /* noop */ }`
      // silently swallowed 401/429/500 — users saw the spinner stop with
      // no feedback. apiFetch already routes 401 → /login and 429 → its
      // own toast, so re-throws on 408/500/network land here and need
      // their own surface. Use sonner (same canonical pattern as
      // alerts/page.tsx, watchlist/page.tsx, settings/_v2/page-v2.tsx).
      if (err instanceof ApiError) {
        if (err.status === 408) {
          toast.error("스캔 요청이 시간 초과되었습니다. 잠시 후 다시 시도해주세요.");
        } else if (err.status >= 500) {
          toast.error("스캔 서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.");
        } else if (err.status !== 401 && err.status !== 429) {
          // 401 redirects in apiFetch; 429 toasts in apiFetch.
          toast.error(err.message || "스캔 실패");
        }
      } else {
        toast.error(err instanceof Error ? err.message : "스캔 실패");
      }
    } finally {
      setScanning(false);
    }
  }, [mutate, mutateUsMovers, mutateKrMovers, mutateOverview, mutateSectors, mutateScreeners]);

  return (
    <ErrorBoundary>
      {/* Legal disclaimer mounted once at the bottom by (dashboard)/layout.tsx
          (CEO 2026-05-24: disclaimer only at the bottom, every page). */}
      {/* Editorial header — RuledKicker matches /home, /portfolio v2, /risk v2.
          Replaces the bare `pq-ink-kicker` span the old card-grid layout used. */}
      <header className="mb-8 flex items-center justify-between gap-4">
        <RuledKicker>PivoxQuant &middot; Discover &middot; {weekTag()}</RuledKicker>
        <span className="font-mono text-pq-caption uppercase tracking-[0.22em] text-[rgba(245,240,232,0.45)]">
          {hasLoadError ? "Stale tape" : "Live observation"}
        </span>
      </header>

      {/* Error banner — shown when primary data fetch fails */}
      {hasLoadError && (
        <div
          role="alert"
          className="mb-8 flex items-center justify-between gap-4 rounded border border-[rgba(209,136,136,0.3)] bg-[rgba(209,136,136,0.07)] px-4 py-3"
        >
          <p className="text-pq-caption text-[rgba(209,136,136,0.9)]">
            Unable to load market data. The data source may be temporarily unavailable.
          </p>
          <button
            type="button"
            onClick={() => mutate()}
            className="shrink-0 font-mono text-pq-eyebrow uppercase tracking-[0.18em] text-[rgba(245,240,232,0.5)] underline underline-offset-2 hover:text-[rgba(245,240,232,0.8)] transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading skeleton — shown while initial fetch is in-flight */}
      {isLoading && !data && !hasLoadError && (
        <div className="pq-ink-empty mb-12 flex flex-col items-center gap-4 py-20 text-center">
          <Fleuron />
          <p className="text-pq-caption text-[rgba(245,240,232,0.4)]">
            Loading market data…
          </p>
        </div>
      )}

      {/* Hero block — matches v3 lock-in convention: Eyebrow + Playfair
          headline with italic accent (cf. /portfolio v2 "Your book.",
          /risk v2 "Risk board.", /signals "The stream is observed,
          not advised"). The old `pq-ink-h1` rendered as a flat sans
          headline that broke the editorial tone. */}
      <div className="mb-12 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div
            className="font-mono text-pq-caption uppercase"
            style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
          >
            Discovery &middot; US + KR
          </div>
          <h1
            className="mt-3 font-display"
            style={{
              fontWeight: 500,
              fontSize: "var(--pq-text-h1-dash)",
              lineHeight: 1.06,
              letterSpacing: "-0.022em",
              color: "var(--pq-ivory)",
            }}
          >
            What the desk{" "}
            <span style={{ color: "var(--pq-bronze)" }}>
              observed.
            </span>
          </h1>
          <Caption className="mt-3 max-w-[560px]">
            Market readings across US and Korean tape, plus a quant pass
            limited to your holdings and watchlist. Informational only —
            never instructions to trade.
          </Caption>
        </div>
        <button
          type="button"
          onClick={handleScan}
          disabled={scanning}
          className="pq-ink-btn-ghost disabled:opacity-40"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", scanning && "animate-spin")} />
          Scan
        </button>
      </div>

        {/* Market Overview — editorial hairline list (Wave 1, 2026-05-01)
            replaces the 5-card SaaS grid that visually broke from the
            v3 lock-in (Vantablack + Bronze + Playfair) used everywhere
            else. Same data, two-column hairline strip grouped US / KR
            so region affinity is glanceable. No card boxes, no bg
            tiles — just hairline-divided rows like /risk v2 ladder. */}
        <section className="mb-14">
          <SectionKicker
            eyebrow="Overview"
            title="Where the tape stands."
            sub="US and Korean index levels — observed at last print."
          />
          {overviewItems.length > 0 ? (
            <div className="mt-6 grid gap-x-12 gap-y-2 md:grid-cols-2">
              {(["us", "kr"] as const).map((region) => {
                const rows = overviewItems.filter((o) => {
                  const name = o.name.toUpperCase();
                  const isKr = name.includes("KOSPI") || name.includes("KOSDAQ");
                  return region === "kr" ? isKr : !isKr;
                });
                if (rows.length === 0) return null;
                return (
                  <div key={region} className="flex flex-col">
                    <div
                      className="mb-2 font-mono text-pq-eyebrow uppercase"
                      style={{
                        letterSpacing: "0.22em",
                        color: "var(--pq-bronze)",
                      }}
                    >
                      {region === "us" ? "United States" : "Korea"}
                    </div>
                    <div className="border-t border-[var(--pq-ivory-line)]">
                      {rows.map((o) => (
                        <div
                          key={o.name}
                          className="grid grid-cols-[1fr_auto_64px] items-baseline gap-3 border-b border-[var(--pq-ivory-line-soft)] py-3"
                        >
                          <span
                            className="font-serif text-pq-body"
                            style={{
                              color: "var(--pq-ivory)",
                              display: "inline-flex",
                              alignItems: "baseline",
                              gap: 6,
                              flexWrap: "wrap",
                            }}
                          >
                            {o.name}
                            {o.proxy_ticker ? (
                              <span
                                role="note"
                                aria-label={`Level sourced via ${o.proxy_ticker} ETF proxy`}
                                title={`Level via ${o.proxy_ticker} ETF proxy — not the underlying index level.`}
                                className="font-mono"
                                style={{
                                  fontSize: "var(--pq-text-kicker)",
                                  letterSpacing: "0.16em",
                                  textTransform: "uppercase",
                                  color: "rgb(var(--pq-bronze-wash-rgb))",
                                  border: "0.5px solid rgba(var(--pq-bronze-wash-rgb), 0.55)",
                                  background: "rgba(var(--pq-bronze-wash-rgb), 0.08)",
                                  padding: "1px 4px",
                                  borderRadius: 2,
                                  lineHeight: 1,
                                  whiteSpace: "nowrap",
                                  fontStyle: "normal",
                                }}
                              >
                                via {o.proxy_ticker}
                              </span>
                            ) : null}
                          </span>
                          <span
                            className="font-mono tabular-nums text-pq-lead"
                            style={{ color: "var(--pq-ivory)" }}
                          >
                            {o.level}
                          </span>
                          <span
                            className={
                              "text-right font-mono tabular-nums text-pq-caption " +
                              deltaCls(o.changePct)
                            }
                          >
                            {fmtPct(o.changePct)}
                          </span>
                        </div>
                      ))}
                    </div>
                    {/* Last-observed footnote — editorial caption tucked under
                        the strip, not on every row, to keep the rhythm clean. */}
                    {rows.some((r) => r.observed_at) && (
                      <p
                        className="mt-2 font-serif text-pq-caption"
                        style={{ color: "rgba(245,240,232,0.4)" }}
                      >
                        Last observed{" "}
                        <span className="font-mono not-italic tabular-nums">
                          {(() => {
                            const fresh = rows
                              .map((r) => r.observed_at)
                              .filter(Boolean)[0] as string | undefined;
                            return fresh ? relativeTime(fresh, nowMs) : "—";
                          })()}
                        </span>
                        {rows.some((r) => r.is_stale) && (
                          <span
                            aria-label="Stale quote in this region"
                            title="One or more quotes have not refreshed recently"
                            className="ml-2 inline-block h-1 w-1 align-middle rounded-full bg-[var(--pq-stale)]"
                          />
                        )}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <EditorialEmpty
              note="Index tape paused — market feed may be offline."
              ctaLabel="Refresh"
              onCta={() => mutate()}
            />
          )}
        </section>

        {/* US Movers — neutral observation, public market data */}
        <section className="mb-12">
          <SectionKicker eyebrow="US Markets" title="Today's Movers — United States" sub="Public market data — 1D change observation." />
          <div className="mt-5 grid gap-8 sm:grid-cols-2">
            {usGainers.length > 0
              ? <MoversBlock title="Gainers" rows={usGainers} />
              : <EmptyBlock title="Gainers" />}
            {usLosers.length > 0
              ? <MoversBlock title="Losers" rows={usLosers} />
              : <EmptyBlock title="Losers" />}
          </div>
        </section>

        {/* KR Movers — neutral observation, public market data */}
        <section className="mb-12">
          <SectionKicker eyebrow="KR Markets" title="Today's Movers — Korea" sub="KOSPI 1D change observation." />
          <div className="mt-5 grid gap-8 sm:grid-cols-2">
            {krGainers.length > 0
              ? <MoversBlock title="Gainers" rows={krGainers} />
              : <EmptyBlock title="Gainers" />}
            {krLosers.length > 0
              ? <MoversBlock title="Losers" rows={krLosers} />
              : <EmptyBlock title="Losers" />}
          </div>
        </section>

        {/* Sector Rotation */}
        <section className="mb-12">
          <SectionKicker eyebrow="Rotation" title="Sector Rotation" sub="11 GICS sectors — 1D · 5D · 1M returns." />
          {sectorRows.length > 0 ? (
            <div className="mt-5 overflow-x-auto">
              <table className="pq-ink-table min-w-[480px]">
                <thead>
                  <tr>
                    <th>Sector</th>
                    <th className="num">1D</th>
                    <th className="num">5D</th>
                    <th className="num">1M</th>
                  </tr>
                </thead>
                <tbody>
                  {sectorRows.map((s) => (
                    <tr key={s.sector}>
                      <td className="text-[rgba(245,240,232,0.85)]">{s.sector}</td>
                      <td className={"num " + deltaCls(s.d1)}>{fmtPct(s.d1)}</td>
                      {/* d5 / m1 may be null (backend stopped fabricating them
                          from d1) — render "—", never a coerced "0.00%". */}
                      <td className={"num " + deltaCls(s.d5)}>{s.d5 == null ? "—" : fmtPct(s.d5)}</td>
                      <td className={"num " + deltaCls(s.m1)}>{s.m1 == null ? "—" : fmtPct(s.m1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="mt-5 text-pq-caption text-[rgba(245,240,232,0.4)]">
              Sector rotation data unavailable.
            </p>
          )}
        </section>

        {/* Thematic — limited to user's holdings + watchlist (§101 회피) */}
        <section className="mb-12">
          <SectionKicker
            eyebrow="Screeners"
            title="Thematic Observations"
            sub={
              hasUserScope
                ? "Observational filters — limited to your holdings and watchlist."
                : "Add holdings or watchlist symbols to surface thematic observations."
            }
          />
          {hasUserScope ? (
            <div className="mt-5 grid gap-8 sm:grid-cols-3">
              {oversold.length > 0
                ? <ThematicBlockInk title="Oversold (RSI < 32)" items={oversold} />
                : <EmptyBlock title="Oversold (RSI < 32)" />}
              {highs52w.length > 0
                ? <ThematicBlockInk title="52-Week Highs" items={highs52w} />
                : <EmptyBlock title="52-Week Highs" />}
              {earnings.length > 0
                ? <ThematicBlockInk title="Earnings Surprise" items={earnings} />
                : <EmptyBlock title="Earnings Surprise" />}
            </div>
          ) : (
            <div className="pq-ink-empty mt-5 flex flex-col items-center gap-3 rounded border border-[var(--pq-ivory-line-soft)] py-10 text-center">
              <Fleuron />
              <p className="text-pq-caption text-[rgba(245,240,232,0.55)]">
                보유 종목이나 관심종목을 추가하면 자동으로 분석합니다.
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => router.push("/portfolio")}
                  className="font-mono text-pq-eyebrow uppercase tracking-[0.18em] text-[var(--pq-bronze)] underline underline-offset-2 hover:text-[var(--pq-ivory)] transition-colors"
                >
                  포지션 추가
                </button>
                <button
                  type="button"
                  onClick={() => router.push("/watchlist")}
                  className="font-mono text-pq-eyebrow uppercase tracking-[0.18em] text-[rgba(245,240,232,0.5)] underline underline-offset-2 hover:text-[rgba(245,240,232,0.85)] transition-colors"
                >
                  관심종목 추가
                </button>
              </div>
            </div>
          )}
        </section>

        {/* Live quant scan — limited to user's holdings + watchlist (§101 회피) */}
        <section className="mb-12">
          <SectionKicker
            eyebrow="Quant"
            title="Engine Scan"
            sub={
              !hasUserScope
                ? "보유 종목이나 관심종목을 추가하면 자동으로 분석합니다."
                : liveFailed
                  ? "Live scan temporarily unavailable."
                  : isLoading
                    ? "Loading live quant scan…"
                    : hasLive
                      ? `${results.length} of your symbols observed.`
                      : "Press Scan to run the live engine."
            }
          />
          {hasLive && (
            <div className="mt-5 overflow-x-auto">
              <table className="pq-ink-table min-w-[560px]">
                <thead>
                  <tr>
                    <th>Stock</th>
                    <th className="num">Last</th>
                    <th className="num">1D Δ</th>
                    <th>Signal</th>
                  </tr>
                </thead>
                <tbody>
                  {results.slice(0, 20).map((item: DiscoverResult) => {
                    const priceDisplay =
                      item?.price_display != null && item.price_display !== ""
                        ? item.price_display
                        : item?.price == null
                          ? "—"
                          : item.currency === "KRW"
                            ? `KRW ${Math.round(item.price).toLocaleString("ko-KR")}`
                            : `USD ${item.price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                    const pillCls =
                      item.signal === "POSITIVE"
                        ? "pq-ink-pill--pos"
                        : item.signal === "NEGATIVE"
                          ? "pq-ink-pill--neg"
                          : "pq-ink-pill--neu";
                    // Column-1 dead code removed (PR #212 follow-up):
                    //   `isKoreanTicker(...) ? item.ticker : item.ticker`
                    // Restructure: name as hero, ticker as subline.
                    // Memory feedback_ticker_display — name first across all surfaces.
                    return (
                      <tr
                        key={item.ticker}
                        className="cursor-pointer"
                        onClick={() => router.push(`/detail/${item.ticker}`)}
                      >
                        <td className="max-w-[260px]">
                          <div className="truncate text-[var(--pq-ivory)]">
                            {displayTicker(item.ticker, item.name)}
                          </div>
                          {item.name && (
                            <div className="font-mono text-pq-eyebrow tracking-[0.06em] text-[rgba(245,240,232,0.45)] truncate">
                              {normalizeTicker(item.ticker)}
                            </div>
                          )}
                        </td>
                        <td className="num">{priceDisplay}</td>
                        <td className={"num " + pctColorClass(item.change_pct)}>
                          {fmtPct(item.change_pct)}
                        </td>
                        <td>
                          <span className={"pq-ink-pill " + pillCls}>
                            {item.signal.charAt(0) + item.signal.slice(1).toLowerCase()}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {data?.cached && data.cached_at && (
            <p className="mt-3 font-serif text-pq-caption text-[rgba(245,240,232,0.4)]">
              Cached at{" "}
              <span className="font-mono not-italic tabular-nums">
                {new Date(data.cached_at).toLocaleString("en-US")}
              </span>
            </p>
          )}
        </section>

        {/* Editorial foot signature — matches /home, /portfolio v2, /risk v2,
            /watchlist. Legal disclaimer is mounted by (dashboard)/layout.tsx. */}
        <FootSignature note="PivoxQuant &middot; Observational research only &middot; Not investment advice" />
    </ErrorBoundary>
  );
}

/* ── editorial section primitives (Wave 1, 2026-05-01) ──
 * The previous local helpers (SectionKicker / MoversBlock / EmptyBlock /
 * ThematicBlockInk) used plain `pq-ink-label` + `pq-ink-h2` which produced
 * a flat "fintech dashboard" tone. The page now matches the v3 lock-in
 * (Vantablack + Bronze + Playfair) used by /home, /portfolio v2, /risk v2,
 * /watchlist, and /signals — Eyebrow tracking 0.22em + serif headline +
 * italic caption + bronze hairline above each section.
 */
function SectionKicker({
  eyebrow,
  title,
  sub,
}: {
  eyebrow: string;
  title: string;
  sub?: string;
}) {
  return (
    <div
      className="border-t pt-5"
      style={{ borderTopColor: "rgba(184,149,106,0.32)", borderTopWidth: 0.5 }}
    >
      <div
        className="font-mono text-pq-eyebrow uppercase"
        style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
      >
        {eyebrow}
      </div>
      <h2
        className="mt-2 font-display"
        style={{
          fontWeight: 500,
          fontSize: "clamp(22px, 2.4vw, 28px)",
          lineHeight: 1.18,
          letterSpacing: "-0.018em",
          color: "var(--pq-ivory)",
        }}
      >
        {title}
      </h2>
      {sub ? (
        <p
          className="mt-1.5 font-serif"
          style={{
            fontSize: "var(--pq-text-body)",
            lineHeight: 1.5,
            color: "rgba(245,240,232,0.55)",
          }}
        >
          {sub}
        </p>
      ) : null}
    </div>
  );
}

/**
 * Editorial empty-section state. Used when the upstream feed is down or
 * when a region/screener has no data. Centered Fleuron + italic serif
 * caption + optional ghost CTA. No fabricated rows — see legal note in
 * the file header.
 */
function EditorialEmpty({
  note,
  ctaLabel,
  onCta,
}: {
  note: string;
  ctaLabel?: string;
  onCta?: () => void;
}) {
  return (
    <div className="mt-6 flex flex-col items-center gap-3 py-12 text-center">
      <PqFleuron size={14} />
      <p
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-body)",
          color: "rgba(245,240,232,0.5)",
        }}
      >
        {note}
      </p>
      {ctaLabel && onCta ? (
        <button
          type="button"
          onClick={onCta}
          className="font-mono text-pq-eyebrow uppercase underline underline-offset-4 transition-colors"
          style={{
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.5)",
            textDecorationColor: "rgba(184,149,106,0.4)",
          }}
        >
          {ctaLabel}
        </button>
      ) : null}
    </div>
  );
}

function MoversBlock({
  title,
  rows,
}: {
  title: string;
  rows: { ticker: string; name: string; price: string; changePct: number }[];
}) {
  // 2026-05-17 P3-01: name-first per feedback_ticker_display (사용자 반복 지시 3+회).
  // Ticker becomes a small mono-style subtitle under the canonical name.
  return (
    <div>
      <div className="mb-2 font-mono text-pq-eyebrow uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
        {title}
      </div>
      <div className="overflow-x-auto">
        <table className="pq-ink-table min-w-[320px]">
          <tbody>
            {rows.slice(0, 10).map((r) => {
              const name = displayName(r.ticker, r.name);
              return (
                <tr key={r.ticker}>
                  <td className="text-[rgba(245,240,232,0.85)] truncate max-w-[200px]">{name}</td>
                  <td className="font-mono text-pq-eyebrow text-[var(--pq-bronze)] tabular-nums w-20">
                    {normalizeTicker(r.ticker)}
                  </td>
                  <td className="num">{r.price}</td>
                  <td className={"num " + deltaCls(r.changePct)}>{fmtPct(r.changePct)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/**
 * Editorial empty state for individual blocks (Movers / Screeners). Renders
 * a titled placeholder so the page rhythm is preserved when an upstream
 * feed is down — never silently swap in fabricated rows. Italic serif copy
 * matches the Caption tone used elsewhere in the v3 lock-in.
 */
function EmptyBlock({ title }: { title: string }) {
  return (
    <div>
      <div
        className="mb-2 font-mono text-pq-eyebrow uppercase"
        style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
      >
        {title}
      </div>
      <p
        className="py-4 font-serif"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          color: "rgba(245,240,232,0.45)",
        }}
      >
        Tape paused — feed temporarily unavailable.
      </p>
    </div>
  );
}

function ThematicBlockInk({
  title,
  items,
}: {
  title: string;
  items: { ticker: string; name: string; metric: string; metricValue: string }[];
}) {
  // 2026-05-17 P3-01: name-first ordering per feedback_ticker_display.
  // Layout: [name (truncated) | ticker (mono caption) | metric value (num)].
  return (
    <div>
      <div className="mb-2 font-mono text-pq-eyebrow uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
        {title}
      </div>
      <ul className="divide-y divide-[var(--pq-ivory-line-soft)]">
        {items.slice(0, 6).map((x) => {
          const name = displayName(x.ticker, x.name);
          return (
            <li key={x.ticker} className="grid grid-cols-[1fr_auto_auto] items-baseline gap-2 py-2.5">
              <span className="truncate text-pq-mono-sm text-[rgba(245,240,232,0.85)]">{name}</span>
              <span className="font-mono text-pq-caption text-[var(--pq-bronze)] tabular-nums">
                {normalizeTicker(x.ticker)}
              </span>
              <span className="font-mono text-pq-mono-sm tabular-nums text-[var(--pq-ivory)]">
                {x.metricValue}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
