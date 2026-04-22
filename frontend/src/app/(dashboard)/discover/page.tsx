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
import { fmtPct } from "@/lib/format";
import { useDiscover } from "@/lib/hooks";
import type { DiscoverResult } from "@/lib/types";
import { relativeTime, useNowTick } from "@/components/market/index-card";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  MOCK_INDICES,
  MOCK_US_GAINERS,
  MOCK_US_LOSERS,
  MOCK_KR_GAINERS,
  MOCK_KR_LOSERS,
  MOCK_SECTORS,
  MOCK_OVERSOLD,
  MOCK_HIGHS_52W,
  MOCK_EARNINGS_BEAT,
} from "@/components/discover/mock-data";

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
  if (v > 0) return "text-[#7db487]";
  if (v < 0) return "text-[#d18888]";
  return "text-[rgba(245,240,232,0.55)]";
}

export default function DiscoverPage() {
  const router = useRouter();
  const { data, isLoading, error, mutate } = useDiscover();
  const [scanning, setScanning] = useState(false);

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

  const results = useMemo(() => data?.results ?? [], [data?.results]);
  const hasLive = results.length > 0;
  const liveFailed = Boolean(error) && !hasLive;

  const overviewItems = useMemo(() => {
    if (!overviewLive || overviewLive.length === 0) {
      return MOCK_INDICES.map((m) => ({ ...m, observed_at: undefined as string | undefined, is_stale: false }));
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

  const usGainers = useMemo(
    () => (usMovers?.gainers?.length ? usMovers.gainers : null)?.map((r) => ({
      ticker: r.ticker, name: r.name, price: fmtMoverPrice(r.price, false), changePct: r.change_pct,
    })) ?? MOCK_US_GAINERS,
    [usMovers],
  );
  const usLosers = useMemo(
    () => (usMovers?.losers?.length ? usMovers.losers : null)?.map((r) => ({
      ticker: r.ticker, name: r.name, price: fmtMoverPrice(r.price, false), changePct: r.change_pct,
    })) ?? MOCK_US_LOSERS,
    [usMovers],
  );
  const krGainers = useMemo(
    () => (krMovers?.gainers?.length ? krMovers.gainers : null)?.map((r) => ({
      ticker: r.ticker, name: r.name, price: fmtMoverPrice(r.price, true), changePct: r.change_pct,
    })) ?? MOCK_KR_GAINERS,
    [krMovers],
  );
  const krLosers = useMemo(
    () => (krMovers?.losers?.length ? krMovers.losers : null)?.map((r) => ({
      ticker: r.ticker, name: r.name, price: fmtMoverPrice(r.price, true), changePct: r.change_pct,
    })) ?? MOCK_KR_LOSERS,
    [krMovers],
  );
  const sectorRows = useMemo(
    () => sectorsLive && sectorsLive.length >= 3
      ? sectorsLive.map((s) => ({ sector: s.sector, d1: s.d1, d5: s.d5, m1: s.m1 }))
      : MOCK_SECTORS,
    [sectorsLive],
  );
  const oversold = useMemo(
    () => (screenersLive?.oversold_rsi?.length ? screenersLive.oversold_rsi : null)?.map((x) => ({
      ticker: x.ticker, name: x.name, metric: x.metric, metricValue: x.metric_value,
    })) ?? MOCK_OVERSOLD,
    [screenersLive],
  );
  const highs52w = useMemo(
    () => (screenersLive?.highs_52w?.length ? screenersLive.highs_52w : null)?.map((x) => ({
      ticker: x.ticker, name: x.name, metric: x.metric, metricValue: x.metric_value,
    })) ?? MOCK_HIGHS_52W,
    [screenersLive],
  );
  const earnings = useMemo(
    () => (screenersLive?.earnings_beats?.length ? screenersLive.earnings_beats : null)?.map((x) => ({
      ticker: x.ticker, name: x.name, metric: x.metric, metricValue: x.metric_value,
    })) ?? MOCK_EARNINGS_BEAT,
    [screenersLive],
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

      <div className="mb-10 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="pq-ink-h1">Discover</h1>
            <p className="mt-2 font-serif italic text-sm text-[rgba(245,240,232,0.55)]">
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
                  <div className="mt-1 flex items-center gap-1.5 font-mono text-[9.5px] text-[rgba(245,240,232,0.4)] tabular-nums">
                    <span>Last obs {relativeTime(o.observed_at, nowMs)}</span>
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
        </section>

        {/* US Movers */}
        <section className="mb-12">
          <SectionKicker eyebrow="US Markets" title="Top Movers — United States" sub="Top gainers and losers by 1D change." />
          <div className="mt-5 grid gap-8 sm:grid-cols-2">
            <MoversBlock title="Gainers" rows={usGainers} />
            <MoversBlock title="Losers" rows={usLosers} />
          </div>
        </section>

        {/* KR Movers */}
        <section className="mb-12">
          <SectionKicker eyebrow="KR Markets" title="Top Movers — Korea" sub="KOSPI top gainers and losers." />
          <div className="mt-5 grid gap-8 sm:grid-cols-2">
            <MoversBlock title="Gainers" rows={krGainers} />
            <MoversBlock title="Losers" rows={krLosers} />
          </div>
        </section>

        {/* Sector Rotation */}
        <section className="mb-12">
          <SectionKicker eyebrow="Rotation" title="Sector Rotation" sub="11 GICS sectors — 1D · 5D · 1M returns." />
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
        </section>

        {/* Thematic */}
        <section className="mb-12">
          <SectionKicker eyebrow="Screeners" title="Thematic Signals" sub="Observational filters across universes." />
          <div className="mt-5 grid gap-8 sm:grid-cols-3">
            <ThematicBlockInk title="Oversold (RSI < 32)" items={oversold} />
            <ThematicBlockInk title="52-Week Highs" items={highs52w} />
            <ThematicBlockInk title="Earnings Surprise" items={earnings} />
          </div>
        </section>

        {/* Live quant scan */}
        <section className="mb-12">
          <SectionKicker
            eyebrow="Quant"
            title="Engine Scan"
            sub={
              liveFailed
                ? "Live scan temporarily unavailable."
                : isLoading
                  ? "Loading live quant scan…"
                  : hasLive
                    ? `${results.length} tickers observed.`
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
                    const isPos = (item.change_pct ?? 0) >= 0;
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
                        <td className={"num " + (isPos ? "text-[#7db487]" : "text-[#d18888]")}>
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

      <div className="border-t border-[rgba(245,240,232,0.1)] pt-6 text-[rgba(245,240,232,0.7)]">
        <DisclaimerBanner type="signal" />
      </div>
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
      <table className="pq-ink-table">
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
