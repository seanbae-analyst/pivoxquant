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

import { useMemo, useState, useCallback } from "react";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import {
  API,
  DISCOVER_OVERVIEW,
  DISCOVER_MOVERS,
  DISCOVER_SECTORS,
  DISCOVER_SCREENERS,
} from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import { cn, isKoreanTicker } from "@/lib/utils";
import { fmtPct, pctColorClass } from "@/lib/format";
import { useDiscover, usePortfolioPositions, useWatchlist } from "@/lib/hooks";
import type { DiscoverResult, Position } from "@/lib/types";
import { relativeTime, useNowTick } from "@/components/market/index-card";
import { ErrorBoundary } from "@/components/ui/error-boundary";

// Mock fallback data was removed (2026-04-28). Displaying stale 2024 hard-coded
// prices as if they were live misled users and created a capital-markets-law
// misrepresentation risk. When the upstream feed fails we now render an
// explicit "data unavailable" editorial state instead of fake numbers.

const jsonFetcher = <T,>(url: string) => apiFetch<T>(url);

interface BackendOverviewItem { name: string; symbol: string; level: number; change_pct: number; observed_at?: string; is_stale?: boolean; }
interface BackendMover { ticker: string; name: string; price: number; change_pct: number; }
interface BackendMoversResponse { region: string; gainers: BackendMover[]; losers: BackendMover[]; }
interface BackendSectorRow { sector: string; d1: number; d5: number; m1: number; }
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

function deltaCls(v: number) {
  // KR convention (CEO directive 2026-04-26): ▲ rising = red, ▼ falling = blue.
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
  const { data: overviewLive } = useSWR<BackendOverviewItem[]>(DISCOVER_OVERVIEW, jsonFetcher, { ...discoverOpts, fallbackData: [] });
  const { data: usMovers } = useSWR<BackendMoversResponse>(`${DISCOVER_MOVERS}?region=us`, jsonFetcher, discoverOpts);
  const { data: krMovers } = useSWR<BackendMoversResponse>(`${DISCOVER_MOVERS}?region=kr`, jsonFetcher, discoverOpts);
  const { data: sectorsLive } = useSWR<BackendSectorRow[]>(DISCOVER_SECTORS, jsonFetcher, discoverOpts);
  const { data: screenersLive } = useSWR<BackendScreeners>(DISCOVER_SCREENERS, jsonFetcher, discoverOpts);

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
      return [] as Array<{ name: string; level: string; changePct: number; observed_at: string | undefined; is_stale: boolean }>;
    }
    return overviewLive.map((o) => ({
      name: o.name,
      level: typeof o.level === "number"
        ? o.level.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
        : String(o.level),
      changePct: o.change_pct,
      observed_at: o.observed_at,
      is_stale: Boolean(o.is_stale),
    }));
  }, [overviewLive]);

  // 1s tick for re-rendering relative timestamps.
  const nowMs = useNowTick(1000);

  const fmtMoverPrice = (price: number, isKr: boolean) =>
    isKr
      ? `₩${Math.round(price).toLocaleString("ko-KR")}`
      : `$${price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

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
    } catch { /* noop */ }
    finally { setScanning(false); }
  }, [mutate]);

  return (
    <ErrorBoundary>
      <header className="mb-8 flex items-center justify-between gap-4">
        <span className="pq-ink-kicker">PIVOXQUANT · DISCOVER</span>
        <span className="font-mono text-[9.5px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
          {weekTag()}
        </span>
      </header>

      {/* Error banner — shown when primary data fetch fails */}
      {hasLoadError && (
        <div
          role="alert"
          className="mb-8 flex items-center justify-between gap-4 rounded border border-[rgba(209,136,136,0.3)] bg-[rgba(209,136,136,0.07)] px-4 py-3"
        >
          <p className="text-[12px] text-[rgba(209,136,136,0.9)]">
            Unable to load market data. The data source may be temporarily unavailable.
          </p>
          <button
            type="button"
            onClick={() => mutate()}
            className="shrink-0 font-mono text-[10px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.5)] underline underline-offset-2 hover:text-[rgba(245,240,232,0.8)] transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading skeleton — shown while initial fetch is in-flight */}
      {isLoading && !data && !hasLoadError && (
        <div className="pq-ink-empty mb-12 flex flex-col items-center gap-4 py-20 text-center">
          <Fleuron />
          <p className="text-[12px] text-[rgba(245,240,232,0.4)]">
            Loading market data…
          </p>
        </div>
      )}

      <div className="mb-10 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="pq-ink-h1">Discover</h1>
            <p className="mt-2 font-serif text-sm text-[rgba(245,240,232,0.55)]">
              Market observation across US and Korean markets — informational only.
            </p>
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

        {/* Market Overview */}
        <section className="mb-12">
          <SectionKicker eyebrow="Overview" title="Market Overview" sub="US · KR index levels (1D Δ)" />
          {overviewItems.length > 0 ? (
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {overviewItems.map((o) => (
                <div key={o.name} className="pq-ink-stat">
                  <div className="pq-ink-label truncate">{o.name}</div>
                  <div className="mt-2 font-mono tabular-nums text-[18px] text-[var(--pq-ivory)]">
                    {o.level}
                  </div>
                  <div className={"mt-1 font-mono text-[11px] " + deltaCls(o.changePct)}>
                    {fmtPct(o.changePct)}
                  </div>
                  {o.observed_at && (
                    <div className="mt-1 flex items-center gap-1.5 text-[9.5px] text-[rgba(245,240,232,0.4)]">
                      <span className="font-serif">Last obs <span className="font-mono tabular-nums">{relativeTime(o.observed_at, nowMs)}</span></span>
                      {o.is_stale && (
                        <span
                          aria-label="Stale quote"
                          title="Quote has not refreshed recently"
                          className="inline-block h-1 w-1 rounded-full bg-yellow-500/70"
                        />
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            // Empty state — fallback to MOCK_INDICES refused (stale 2024 values = legal misrepresentation risk).
            // Display explicit "unavailable" state instead of fake numbers.
            <div className="pq-ink-empty mt-4 flex flex-col items-center gap-3 rounded border border-[rgba(245,240,232,0.06)] py-10 text-center">
              <Fleuron />
              <p className="text-[12px] text-[rgba(245,240,232,0.4)]">
                Index data unavailable — market feed may be offline.
              </p>
              <button
                type="button"
                onClick={() => mutate()}
                className="font-mono text-[10px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.35)] underline underline-offset-2 hover:text-[rgba(245,240,232,0.6)] transition-colors"
              >
                Refresh
              </button>
            </div>
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
              <table className="pq-ink-table">
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
                      <td className={"num " + deltaCls(s.d5)}>{fmtPct(s.d5)}</td>
                      <td className={"num " + deltaCls(s.m1)}>{fmtPct(s.m1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="mt-5 text-[12px] italic text-[rgba(245,240,232,0.4)]">
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
            <div className="pq-ink-empty mt-5 flex flex-col items-center gap-3 rounded border border-[rgba(245,240,232,0.06)] py-10 text-center">
              <Fleuron />
              <p className="text-[12px] text-[rgba(245,240,232,0.55)]">
                보유 종목이나 관심종목을 추가하면 자동으로 분석합니다.
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => router.push("/portfolio")}
                  className="font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--pq-bronze)] underline underline-offset-2 hover:text-[var(--pq-ivory)] transition-colors"
                >
                  포지션 추가
                </button>
                <button
                  type="button"
                  onClick={() => router.push("/watchlist")}
                  className="font-mono text-[10px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.5)] underline underline-offset-2 hover:text-[rgba(245,240,232,0.85)] transition-colors"
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
              <table className="pq-ink-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Name</th>
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
                            ? `₩${Math.round(item.price).toLocaleString("ko-KR")}`
                            : `$${item.price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                    const pillCls =
                      item.signal === "POSITIVE"
                        ? "pq-ink-pill--pos"
                        : item.signal === "NEGATIVE"
                          ? "pq-ink-pill--neg"
                          : "pq-ink-pill--neu";
                    return (
                      <tr
                        key={item.ticker}
                        className="cursor-pointer"
                        onClick={() => router.push(`/detail/${item.ticker}`)}
                      >
                        <td className="font-mono text-[var(--pq-bronze)]">
                          {isKoreanTicker(item.ticker, item.is_korean) ? item.ticker : item.ticker}
                        </td>
                        <td className="text-[rgba(245,240,232,0.75)] truncate max-w-[220px]">
                          {item.name || item.ticker}
                        </td>
                        <td className="num">{priceDisplay}</td>
                        <td className={"num " + pctColorClass(item.change_pct)}>
                          {fmtPct(item.change_pct ?? 0)}
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
            <p className="mt-3 text-[10px] text-[rgba(245,240,232,0.4)]">
              Cache timestamp: {new Date(data.cached_at).toLocaleString("en-US")}
            </p>
          )}
        </section>

      {/* Legal disclaimer mounted by (dashboard)/layout.tsx — do not re-mount. */}
    </ErrorBoundary>
  );
}

/* ── local ink-themed blocks ── */

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
    <div className="border-t border-[rgba(245,240,232,0.12)] pt-4">
      <div className="pq-ink-label">{eyebrow}</div>
      <h2 className="pq-ink-h2 mt-1">{title}</h2>
      {sub ? (
        <p className="mt-1 text-[12px] text-[rgba(245,240,232,0.55)]">{sub}</p>
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
  return (
    <div>
      <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
        {title}
      </div>
      <div className="overflow-x-auto">
        <table className="pq-ink-table min-w-[320px]">
          <tbody>
            {rows.slice(0, 10).map((r) => (
              <tr key={r.ticker}>
                <td className="font-mono text-[var(--pq-bronze)] w-16">{r.ticker}</td>
                <td className="text-[rgba(245,240,232,0.75)] truncate max-w-[160px]">{r.name}</td>
                <td className="num">{r.price}</td>
                <td className={"num " + deltaCls(r.changePct)}>{fmtPct(r.changePct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/**
 * Editorial empty state for individual blocks (Movers / Screeners). Renders a
 * titled placeholder so the page rhythm is preserved when an upstream feed is
 * down — never silently swap in fabricated rows.
 */
function EmptyBlock({ title }: { title: string }) {
  return (
    <div>
      <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
        {title}
      </div>
      <p className="py-4 text-[12px] italic text-[rgba(245,240,232,0.4)]">
        Data temporarily unavailable.
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
  return (
    <div>
      <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
        {title}
      </div>
      <ul className="divide-y divide-[rgba(245,240,232,0.06)]">
        {items.slice(0, 6).map((x) => (
          <li key={x.ticker} className="grid grid-cols-[auto_1fr_auto] items-baseline gap-2 py-2.5">
            <span className="font-mono text-[12px] text-[var(--pq-bronze)]">{x.ticker}</span>
            <span className="truncate text-[11px] text-[rgba(245,240,232,0.7)]">{x.name}</span>
            <span className="font-mono text-[11px] tabular-nums text-[var(--pq-ivory)]">
              {x.metricValue}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
