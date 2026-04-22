"use client";

/**
 * Market — Vantablack ink terminal card on ivory shell.
 *
 * Sections:
 *   - Tab switcher (US / KR) — Bronze active underline
 *   - Grid of inline IndexCard (level + 1D Δ + 52W range + 30-day sparkline)
 *   - KR tab: FX + derivatives summary
 *   - DisclaimerBanner
 *
 * Neutral observation language only.
 */

import { useMemo, useState } from "react";
import useSWR from "swr";
import { apiFetch } from "@/lib/api";
import { MARKET_INDICES } from "@/lib/endpoints";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { TerminalSidebar } from "@/components/layout/terminal-sidebar";
import { fmtPct } from "@/lib/format";
import {
  US_INDICES,
  KR_INDICES,
  KR_DERIVATIVES,
} from "@/components/market/mock-indices";
import type { IndexQuote } from "@/components/market/index-card";

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

function weekTag(): string {
  const d = new Date();
  const first = new Date(d.getFullYear(), 0, 1);
  const days = Math.floor((d.getTime() - first.getTime()) / 86400000);
  const w = Math.ceil((days + first.getDay() + 1) / 7);
  return `${d.getFullYear()} · W${String(w).padStart(2, "0")}`;
}

function fmtLevel(v: number, kind: IndexQuote["format"] = "en") {
  if (kind === "int") return Math.round(v).toLocaleString("en-US");
  if (kind === "kr") {
    return v.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
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
    if (Array.isArray(data) && data.length >= 3) return data.map((b) => toQuote(b, tab));
    return tab === "US" ? US_INDICES : KR_INDICES;
  }, [data, tab]);

  return (
    <ErrorBoundary>
      <div className="pq-ink-card">
        <header className="mb-8 flex items-center justify-between gap-4">
          <span className="pq-ink-kicker">PIVOXQUANT · MARKET</span>
          <span className="font-mono text-[9.5px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
            {weekTag()}
          </span>
        </header>

        <div className="flex gap-8 md:gap-10">
          <TerminalSidebar active="market" />
          <div className="flex-1 min-w-0">
        <div className="mb-10">
          <h1 className="pq-ink-h1">Indices Board</h1>
          <p className="mt-2 font-serif italic text-sm text-[rgba(245,240,232,0.55)]">
            Major index levels across US and Korean markets — informational only.
          </p>
        </div>

        {/* Tabs */}
        <div className="pq-ink-tabs mb-8">
          {(["US", "KR"] as MarketTab[]).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              data-active={tab === t}
              className="pq-ink-tab"
            >
              {t === "US" ? "United States" : "Korea"}
            </button>
          ))}
        </div>

        {/* Index grid */}
        <section
          aria-label={`${tab} indices`}
          aria-busy={isLoading}
          className="mb-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3"
        >
          {quotes.map((q) => (
            <IndexCardInk key={q.symbol} quote={q} />
          ))}
        </section>

        {tab === "KR" && (
          <section className="mb-12">
            <div className="border-t border-[rgba(245,240,232,0.12)] pt-4">
              <div className="pq-ink-label">Derivatives</div>
              <h2 className="pq-ink-h2 mt-1">Domestic Futures &amp; Options</h2>
              <p className="mt-1 text-[12px] text-[rgba(245,240,232,0.55)]">
                KOSPI 200 front-month summary.
              </p>
            </div>
            <ul className="mt-4 divide-y divide-[rgba(245,240,232,0.08)]">
              {KR_DERIVATIVES.map((row) => (
                <li
                  key={row.label}
                  className="grid grid-cols-[1fr_auto_auto] items-baseline gap-4 py-3"
                >
                  <span className="text-[13px] text-[rgba(245,240,232,0.8)] truncate">{row.label}</span>
                  <span className="font-mono text-[15px] tabular-nums text-[var(--pq-ivory)]">
                    {row.value}
                  </span>
                  <span className="font-mono text-[11px] tabular-nums text-[rgba(245,240,232,0.5)]">
                    {row.note}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <div className="border-t border-[rgba(245,240,232,0.1)] pt-6 text-[rgba(245,240,232,0.7)]">
          <DisclaimerBanner type="signal" />
        </div>
          </div>
        </div>
      </div>
    </ErrorBoundary>
  );
}

/* ── inline ink index card ── */

function IndexCardInk({ quote }: { quote: IndexQuote }) {
  const { name, symbol, level, changePct, weekHigh52, weekLow52, spark, format = "en", unit } = quote;
  const isPositive = changePct >= 0;

  // Sparkline
  const w = 220;
  const h = 40;
  const pad = 2;
  let pathPts = "";
  if (spark && spark.length > 1) {
    const lo = Math.min(...spark);
    const hi = Math.max(...spark);
    const range = hi - lo || 1;
    const step = (w - pad * 2) / (spark.length - 1);
    pathPts = spark
      .map((v, i) => {
        const x = pad + i * step;
        const y = pad + ((hi - v) / range) * (h - pad * 2);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }

  // 52W range position (0..1)
  const rangePct = weekHigh52 > weekLow52
    ? Math.max(0, Math.min(1, (level - weekLow52) / (weekHigh52 - weekLow52)))
    : 0.5;

  return (
    <div className="pq-ink-stat">
      <div className="flex items-baseline justify-between">
        <div>
          <div className="pq-ink-label">{name}</div>
          <div className="mt-0.5 font-mono text-[9px] text-[rgba(245,240,232,0.4)]">
            {symbol}
          </div>
        </div>
      </div>

      <div className="mt-3 flex items-baseline justify-between">
        <div className="font-serif italic text-[26px] tabular-nums text-[var(--pq-ivory)]">
          {fmtLevel(level, format)}
          {unit ? <span className="ml-1 text-[11px] text-[rgba(245,240,232,0.5)]">{unit}</span> : null}
        </div>
        <div className={"font-mono text-[12px] " + (isPositive ? "text-[#7db487]" : "text-[#d18888]")}>
          {fmtPct(changePct)}
        </div>
      </div>

      {/* Sparkline */}
      {pathPts ? (
        <svg viewBox={`0 0 ${w} ${h}`} className="mt-3 h-[36px] w-full" preserveAspectRatio="none">
          <polyline
            points={pathPts}
            fill="none"
            stroke="var(--pq-bronze)"
            strokeWidth="1.25"
          />
        </svg>
      ) : null}

      {/* 52W range bar */}
      <div className="mt-3">
        <div className="relative h-[3px] bg-[rgba(245,240,232,0.08)]">
          <div
            className="absolute top-[-2px] h-[7px] w-[2px] bg-[var(--pq-bronze)]"
            style={{ left: `${rangePct * 100}%` }}
          />
        </div>
        <div className="mt-1 flex justify-between font-mono text-[9px] text-[rgba(245,240,232,0.4)]">
          <span>{fmtLevel(weekLow52, format)}</span>
          <span className="text-[rgba(245,240,232,0.55)]">52W</span>
          <span>{fmtLevel(weekHigh52, format)}</span>
        </div>
      </div>
    </div>
  );
}
