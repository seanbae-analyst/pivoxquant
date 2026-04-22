"use client";

/**
 * Discover — editorial exploration page.
 *
 * Structure:
 *   1. Market Overview (US + KR indices, 5 cards)
 *   2. Top Movers — US gainers/losers (top 10 each)
 *   3. Top Movers — KR gainers/losers (top 5 each)
 *   4. Sector Rotation (11 GICS sectors, 1D/5D/1M)
 *   5. Thematic Screeners — Oversold RSI / 52W Highs / Earnings Beat
 *   6. Live quant scan results (when backend returns)
 *   7. DisclaimerBanner
 *
 * Resilient: when FMP upstream errors (402 etc) or the discover endpoint
 * returns no results, editorial sections render mock data so the page is
 * never empty. Neutral language everywhere.
 */

import { useMemo, useState, useCallback } from "react";
import useSWR from "swr";
import { useRouter } from "next/navigation";
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
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { RefreshCw } from "lucide-react";
import {
  SectionHeading,
  IndicesRow,
  MoversTable,
  SectorRotationTable,
  ThematicBlock,
} from "@/components/discover/discover-sections";
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

function deltaTone(v: number): string {
  if (v > 0) return "text-[var(--pq-bronze,#8B6F47)]";
  if (v < 0) return "text-[#B04A3A]";
  return "text-slate-500";
}

/* ── Quant scan row (live backend, falls back gracefully) ── */

function ScanRow({
  item,
  onClick,
}: {
  item: DiscoverResult;
  onClick: () => void;
}) {
  const isPositive = (item?.change_pct ?? 0) >= 0;
  const priceDisplay =
    item?.price_display != null && item.price_display !== ""
      ? item.price_display
      : item?.price == null
        ? "\u2014"
        : item.currency === "KRW"
          ? `₩${Math.round(item.price).toLocaleString("ko-KR")}`
          : `$${item.price.toLocaleString("en-US", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}`;

  const sigTone =
    item.signal === "POSITIVE"
      ? "signal-positive"
      : item.signal === "NEGATIVE"
        ? "signal-negative"
        : "signal-neutral";

  return (
    <button
      type="button"
      onClick={onClick}
      className="grid w-full grid-cols-[auto_1fr_auto_auto] items-center gap-3 py-2.5 text-left transition-colors hover:bg-slate-50"
    >
      <span className="font-mono text-[11px] text-slate-700 w-20 truncate">
        {isKoreanTicker(item.ticker, item.is_korean)
          ? `${item.ticker}`
          : item.ticker}
      </span>
      <span className="text-xs text-slate-600 truncate">
        {item.name || item.ticker}
      </span>
      <span className="text-xs font-semibold tabular-nums text-slate-900 w-20 text-right">
        {priceDisplay}
      </span>
      <span
        className={cn(
          "text-xs font-semibold tabular-nums w-16 text-right",
          isPositive
            ? "text-[var(--pq-bronze,#8B6F47)]"
            : "text-[#B04A3A]",
        )}
      >
        {fmtPct(item?.change_pct ?? 0)}
      </span>
      <span
        className={cn(
          "col-span-4 sm:col-span-1 inline-flex items-center justify-center rounded-full px-2 py-0.5 text-[10px] font-semibold shrink-0",
          sigTone,
        )}
      >
        {item.signal.charAt(0) + item.signal.slice(1).toLowerCase()}
      </span>
    </button>
  );
}

/* ── SWR fetcher ── */
const jsonFetcher = <T,>(url: string) => apiFetch<T>(url);

interface BackendOverviewItem { name: string; symbol: string; level: number; change_pct: number; }
interface BackendMover { ticker: string; name: string; price: number; change_pct: number; }
interface BackendMoversResponse { region: string; gainers: BackendMover[]; losers: BackendMover[]; }
interface BackendSectorRow { sector: string; d1: number; d5: number; m1: number; }
interface BackendScreenerItem { ticker: string; name: string; metric: string; metric_value: string; }
interface BackendScreeners {
  oversold_rsi: BackendScreenerItem[];
  highs_52w: BackendScreenerItem[];
  earnings_beats: BackendScreenerItem[];
}

export default function DiscoverPage() {
  const router = useRouter();
  const { data, isLoading, error, mutate } = useDiscover();
  const [scanning, setScanning] = useState(false);

  // New section hooks — fallbackData keeps rendering stable even on 402/5xx.
  const { data: overviewLive } = useSWR<BackendOverviewItem[]>(
    DISCOVER_OVERVIEW,
    jsonFetcher,
    { fallbackData: [] },
  );
  const { data: usMovers } = useSWR<BackendMoversResponse>(
    `${DISCOVER_MOVERS}?region=us`,
    jsonFetcher,
  );
  const { data: krMovers } = useSWR<BackendMoversResponse>(
    `${DISCOVER_MOVERS}?region=kr`,
    jsonFetcher,
  );
  const { data: sectorsLive } = useSWR<BackendSectorRow[]>(
    DISCOVER_SECTORS,
    jsonFetcher,
  );
  const { data: screenersLive } = useSWR<BackendScreeners>(
    DISCOVER_SCREENERS,
    jsonFetcher,
  );

  // Use live scan results when available. If endpoint errors OR returns
  // an empty list, the editorial mock sections above still give the user
  // something to look at — the live row simply shows a muted placeholder.
  const results = useMemo(() => data?.results ?? [], [data?.results]);
  const hasLive = results.length > 0;
  const liveFailed = Boolean(error) && !hasLive;

  // Map backend overview → IndexCard shape used by IndicesRow.
  const overviewItems = useMemo(() => {
    if (!overviewLive || overviewLive.length === 0) return MOCK_INDICES;
    return overviewLive.map((o) => ({
      name: o.name,
      level: typeof o.level === "number"
        ? o.level.toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })
        : String(o.level),
      changePct: o.change_pct,
    }));
  }, [overviewLive]);

  const fmtMoverPrice = (price: number, isKr: boolean) =>
    isKr
      ? `₩${Math.round(price).toLocaleString("ko-KR")}`
      : `$${price.toLocaleString("en-US", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })}`;

  const usGainers = useMemo(
    () =>
      (usMovers?.gainers?.length ? usMovers.gainers : null)?.map((r) => ({
        ticker: r.ticker,
        name: r.name,
        price: fmtMoverPrice(r.price, false),
        changePct: r.change_pct,
      })) ?? MOCK_US_GAINERS,
    [usMovers],
  );
  const usLosers = useMemo(
    () =>
      (usMovers?.losers?.length ? usMovers.losers : null)?.map((r) => ({
        ticker: r.ticker,
        name: r.name,
        price: fmtMoverPrice(r.price, false),
        changePct: r.change_pct,
      })) ?? MOCK_US_LOSERS,
    [usMovers],
  );
  const krGainers = useMemo(
    () =>
      (krMovers?.gainers?.length ? krMovers.gainers : null)?.map((r) => ({
        ticker: r.ticker,
        name: r.name,
        price: fmtMoverPrice(r.price, true),
        changePct: r.change_pct,
      })) ?? MOCK_KR_GAINERS,
    [krMovers],
  );
  const krLosers = useMemo(
    () =>
      (krMovers?.losers?.length ? krMovers.losers : null)?.map((r) => ({
        ticker: r.ticker,
        name: r.name,
        price: fmtMoverPrice(r.price, true),
        changePct: r.change_pct,
      })) ?? MOCK_KR_LOSERS,
    [krMovers],
  );

  const sectorRows = useMemo(
    () =>
      sectorsLive && sectorsLive.length >= 3
        ? sectorsLive.map((s) => ({
            sector: s.sector,
            d1: s.d1,
            d5: s.d5,
            m1: s.m1,
          }))
        : MOCK_SECTORS,
    [sectorsLive],
  );

  const oversold = useMemo(
    () =>
      (screenersLive?.oversold_rsi?.length
        ? screenersLive.oversold_rsi
        : null
      )?.map((x) => ({
        ticker: x.ticker,
        name: x.name,
        metric: x.metric,
        metricValue: x.metric_value,
      })) ?? MOCK_OVERSOLD,
    [screenersLive],
  );
  const highs52w = useMemo(
    () =>
      (screenersLive?.highs_52w?.length
        ? screenersLive.highs_52w
        : null
      )?.map((x) => ({
        ticker: x.ticker,
        name: x.name,
        metric: x.metric,
        metricValue: x.metric_value,
      })) ?? MOCK_HIGHS_52W,
    [screenersLive],
  );
  const earnings = useMemo(
    () =>
      (screenersLive?.earnings_beats?.length
        ? screenersLive.earnings_beats
        : null
      )?.map((x) => ({
        ticker: x.ticker,
        name: x.name,
        metric: x.metric,
        metricValue: x.metric_value,
      })) ?? MOCK_EARNINGS_BEAT,
    [screenersLive],
  );

  const handleScan = useCallback(async () => {
    setScanning(true);
    try {
      await apiFetch(`${API.discover}?force=1`);
      await mutate();
    } catch {
      // absorb — editorial sections still render from mock data
    } finally {
      setScanning(false);
    }
  }, [mutate]);

  return (
    <ErrorBoundary>
      <div className="mx-auto max-w-4xl space-y-8 px-1">
        {/* ── Header ── */}
        <header className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] uppercase tracking-widest text-[var(--pq-bronze,#8B6F47)]">
              Exploration
            </p>
            <h1 className="mt-1 font-serif italic text-4xl font-bold text-slate-900">
              Discover
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              Market observation across US and Korean markets — informational only.
            </p>
          </div>
          <button
            type="button"
            onClick={handleScan}
            disabled={scanning}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-4 py-2 text-xs font-semibold transition-all",
              "border-slate-900 bg-slate-900 text-white hover:bg-slate-800 active:scale-[0.97]",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            <RefreshCw
              className={cn("h-3.5 w-3.5", scanning && "animate-spin")}
            />
            Scan
          </button>
        </header>

        {/* ── Market Overview ── */}
        <section>
          <SectionHeading
            eyebrow="Overview"
            title="Market Overview"
            subtitle="US · KR index levels (1D change)"
          />
          <IndicesRow items={overviewItems} />
        </section>

        {/* ── US Movers ── */}
        <section>
          <SectionHeading
            eyebrow="US Markets"
            title="Top Movers — United States"
            subtitle="Top gainers and losers by 1-day change."
          />
          <div className="grid gap-8 sm:grid-cols-2">
            <MoversTable title="Gainers" rows={usGainers} />
            <MoversTable title="Losers" rows={usLosers} />
          </div>
        </section>

        {/* ── KR Movers ── */}
        <section>
          <SectionHeading
            eyebrow="KR Markets"
            title="Top Movers — Korea"
            subtitle="KOSPI top gainers and losers by 1-day change."
          />
          <div className="grid gap-8 sm:grid-cols-2">
            <MoversTable title="Gainers" rows={krGainers} />
            <MoversTable title="Losers" rows={krLosers} />
          </div>
        </section>

        {/* ── Sector Rotation ── */}
        <section>
          <SectionHeading
            eyebrow="Rotation"
            title="Sector Rotation"
            subtitle="11 GICS sectors — 1D · 5D · 1M returns."
          />
          <SectorRotationTable rows={sectorRows} />
        </section>

        {/* ── Thematic Screeners ── */}
        <section>
          <SectionHeading
            eyebrow="Screeners"
            title="Thematic Signals"
            subtitle="Observational filters across universes."
          />
          <div className="grid gap-8 sm:grid-cols-3">
            <ThematicBlock title="Oversold (RSI < 32)" items={oversold} />
            <ThematicBlock title="52-Week Highs" items={highs52w} />
            <ThematicBlock title="Earnings Surprise" items={earnings} />
          </div>
        </section>

        {/* ── Live Quant Scan (best-effort) ── */}
        <section>
          <SectionHeading
            eyebrow="Quant"
            title="Engine Scan"
            subtitle={
              liveFailed
                ? "Live scan temporarily unavailable. Editorial sections shown above."
                : isLoading
                  ? "Loading live quant scan..."
                  : hasLive
                    ? `${results.length} tickers observed by the engine.`
                    : "Press Scan to run the live quant engine."
            }
          />
          {hasLive && (
            <div className="divide-y divide-slate-100">
              {results.slice(0, 20).map((item) => (
                <ScanRow
                  key={item.ticker}
                  item={item}
                  onClick={() => router.push(`/detail/${item.ticker}`)}
                />
              ))}
            </div>
          )}
          {data?.cached && data.cached_at && (
            <p className="mt-3 text-[11px] text-slate-400">
              Cache timestamp: {new Date(data.cached_at).toLocaleString("en-US")}
            </p>
          )}
        </section>

        {/* ── Disclaimer ── */}
        <div className="pt-4">
          <DisclaimerBanner type="signal" />
        </div>
      </div>
    </ErrorBoundary>
  );
}
