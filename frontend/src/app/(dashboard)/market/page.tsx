"use client";

/**
 * Market — editorial indices board, US + KR tabs.
 *
 * Sections:
 *   - Tab switcher (US default / KR)
 *   - Grid of IndexCard (level + 1D Δ + 52W range + 30-day sparkline)
 *   - KR tab also shows USD/KRW and a short domestic derivatives summary
 *   - DisclaimerBanner
 *
 * Wired to /api/market/indices?region=us|kr via SWR (2026-04-22). Falls back
 * to the hand-crafted mock snapshot on upstream failure so the page is
 * never empty. Neutral observation language only throughout.
 */

import { useMemo, useState } from "react";
import useSWR from "swr";
import { cn } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import { MARKET_INDICES } from "@/lib/endpoints";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { IndexCard, type IndexQuote } from "@/components/market/index-card";
import {
  US_INDICES,
  KR_INDICES,
  KR_DERIVATIVES,
} from "@/components/market/mock-indices";

type MarketTab = "US" | "KR";

interface BackendIndex {
  ticker: string;
  name: string;
  level: number;
  change_1d_pct: number;
  range_52w: [number, number];
  sparkline_30d: number[];
}

const fetcher = <T,>(url: string) => apiFetch<T>(url);

/** Map the server payload → the IndexCard-shaped quote the component expects. */
function toQuote(b: BackendIndex, region: MarketTab): IndexQuote {
  const [lo, hi] = b.range_52w ?? [0, 0];
  return {
    symbol: b.ticker,
    name: b.name,
    level: b.level,
    changePct: b.change_1d_pct,
    weekHigh52: hi,
    weekLow52: lo,
    spark: (b.sparkline_30d ?? []).slice(-30),
    format: region === "KR" ? "kr" : "en",
    unit: b.ticker === "USDKRW" ? "KRW" : undefined,
  };
}

export default function MarketPage() {
  const [tab, setTab] = useState<MarketTab>("US");

  const region = tab === "US" ? "us" : "kr";
  const { data, isLoading } = useSWR<BackendIndex[]>(
    `${MARKET_INDICES}?region=${region}`,
    fetcher,
    { keepPreviousData: true },
  );

  const quotes: IndexQuote[] = useMemo(() => {
    if (Array.isArray(data) && data.length >= 3) {
      return data.map((b) => toQuote(b, tab));
    }
    // Loading / upstream failure → keep the hand-crafted snapshot visible.
    return tab === "US" ? US_INDICES : KR_INDICES;
  }, [data, tab]);

  return (
    <ErrorBoundary>
      <div className="mx-auto max-w-5xl space-y-8 px-1">
        {/* ── Header ── */}
        <header>
          <p className="text-[11px] uppercase tracking-widest text-[var(--pq-bronze,#8B6F47)]">
            Markets
          </p>
          <h1 className="mt-1 font-serif italic text-4xl font-bold text-slate-900">
            Indices Board
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Major index levels across US and Korean markets — informational only.
          </p>
        </header>

        {/* ── Tab switcher ── */}
        <div className="border-b border-slate-200">
          <nav
            aria-label="Market region"
            className="flex gap-6 text-sm"
          >
            {(["US", "KR"] as MarketTab[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTab(t)}
                className={cn(
                  "relative -mb-px border-b-2 px-0.5 py-3 transition-colors",
                  tab === t
                    ? "border-[var(--pq-bronze,#8B6F47)] font-serif italic font-bold text-slate-900"
                    : "border-transparent text-slate-500 hover:text-slate-800",
                )}
              >
                {t === "US" ? "United States" : "Korea"}
              </button>
            ))}
          </nav>
        </div>

        {/* ── Index grid ── */}
        <section
          aria-label={`${tab} indices`}
          aria-busy={isLoading}
          className="grid grid-cols-1 gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-3"
        >
          {quotes.map((q) => (
            <IndexCard key={q.symbol} quote={q} />
          ))}
        </section>

        {/* ── KR extras: FX + derivatives ── */}
        {tab === "KR" && (
          <section>
            <header className="mb-3 border-t border-slate-200 pt-4">
              <p className="text-[10px] uppercase tracking-widest text-[var(--pq-bronze,#8B6F47)]">
                Derivatives
              </p>
              <h2 className="mt-1 font-serif italic text-xl text-slate-900">
                Domestic Futures & Options
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                KOSPI 200 front-month summary.
              </p>
            </header>
            <ul className="divide-y divide-slate-100">
              {KR_DERIVATIVES.map((row) => (
                <li
                  key={row.label}
                  className="grid grid-cols-[1fr_auto_auto] items-baseline gap-4 py-3"
                >
                  <span className="text-sm text-slate-700 truncate">
                    {row.label}
                  </span>
                  <span className="font-serif italic text-lg font-bold tabular-nums text-slate-900">
                    {row.value}
                  </span>
                  <span className="text-xs text-slate-500 tabular-nums">
                    {row.note}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* ── Disclaimer ── */}
        <div className="pt-4">
          <DisclaimerBanner type="signal" />
        </div>
      </div>
    </ErrorBoundary>
  );
}
