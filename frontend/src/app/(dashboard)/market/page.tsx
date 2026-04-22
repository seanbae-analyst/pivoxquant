"use client";

/**
 * Market — Vantablack ink terminal card on ivory shell.
 *
 * Sections:
 *   - Header (kicker + title + week tag)
 *   - Region tabs (US / KR) — Bronze active underline
 *   - Overview strip — 5-index mini-sparkline summary row (non-interactive)
 *   - IndexCard grid (display-only — indices have no detail page)
 *   - KR: Derivatives block
 *   - Economic Calendar + News feed placeholders
 *   - DisclaimerBanner
 *
 * Neutral observation language only.
 */

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";

interface FxResponse {
  ok: boolean;
  usd_krw: number;
  last_updated: string | null;
  last_updated_ts: number;
  age_seconds: number;
  is_stale: boolean;
}
import { apiFetch } from "@/lib/api";
import { MARKET_INDICES, API } from "@/lib/endpoints";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import {
  Caption,
  Fleuron,
  FootSignature,
  RuledKicker,
} from "@/components/ui/editorial";
import { fmtPct } from "@/lib/format";
import {
  US_INDICES,
  KR_INDICES,
  KR_DERIVATIVES,
} from "@/components/market/mock-indices";
import type { IndexQuote } from "@/components/market/index-card";
import { CalendarDays, Newspaper } from "lucide-react";

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
  const router = useRouter();
  const [tab, setTab] = useState<MarketTab>("US");
  const region = tab === "US" ? "us" : "kr";

  const { data, isLoading } = useSWR<BackendIndex[]>(
    `${MARKET_INDICES}?region=${region}`,
    fetcher,
    {
      keepPreviousData: true,
      refreshInterval: 15_000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 5_000,
      errorRetryCount: 2,
      errorRetryInterval: 5_000,
    },
  );

  // Economic calendar (earnings endpoint as proxy) — upcoming events, 5min.
  const { data: earningsData } = useSWR<{ earnings?: Array<{ ticker: string; name?: string; date: string }> }>(
    API.market.earnings,
    fetcher,
    {
      refreshInterval: 300_000,
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 60_000,
      errorRetryCount: 2,
      errorRetryInterval: 10_000,
    },
  );

  // FX — independent 60s poll (backend refreshes every 60s).
  const { data: fxData } = useSWR<FxResponse>(
    API.market.fx,
    fetcher,
    {
      refreshInterval: 60_000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 30_000,
      errorRetryCount: 2,
      errorRetryInterval: 10_000,
    },
  );

  const quotes: IndexQuote[] = useMemo(() => {
    if (Array.isArray(data) && data.length >= 3) return data.map((b) => toQuote(b, tab));
    return tab === "US" ? US_INDICES : KR_INDICES;
  }, [data, tab]);

  const upcomingEarnings = (earningsData?.earnings ?? []).slice(0, 6);

  // Format FX observation timestamp for header — KST for Korean user.
  const fxStatus = useMemo(() => {
    if (!fxData?.last_updated_ts) return null;
    const d = new Date(fxData.last_updated_ts * 1000);
    const hh = d
      .toLocaleTimeString("ko-KR", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        timeZone: "Asia/Seoul",
        hour12: false,
      });
    const stale = fxData.is_stale || (fxData.age_seconds > 300);
    return {
      label: `Last observed ${hh} KST`,
      rate: fxData.usd_krw,
      stale,
    };
  }, [fxData]);

  return (
    <ErrorBoundary>
      <header className="mb-8 flex items-end justify-between gap-4">
        <div>
          <RuledKicker>Market &middot; 2026 &middot; {weekTag().split("·")[1]?.trim() ?? ""}</RuledKicker>
          <h1 className="pq-ink-h1 mt-2">Indices Board</h1>
          <p className="mt-2 font-serif italic text-[15px] text-[var(--pq-ivory)]">
            Levels across US and Korean markets.
          </p>
          <Caption className="mt-1">Informational only &middot; observed at last close.</Caption>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="font-mono text-[9.5px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
            {weekTag()}
          </span>
          {fxStatus ? (
            <div className="flex items-center gap-2">
              {fxStatus.stale ? (
                <span
                  aria-label="Stale data"
                  title="FX rate has not refreshed in over 5 minutes"
                  className="inline-block h-1.5 w-1.5 rounded-full bg-[#d1a750]"
                />
              ) : null}
              <span className="font-mono text-[10px] tabular-nums text-[rgba(245,240,232,0.55)]">
                USD/KRW {fxStatus.rate.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                {" · "}
                {fxStatus.label}
                {fxStatus.stale ? " · Stale" : ""}
              </span>
            </div>
          ) : null}
        </div>
      </header>

      {/* Region tabs — fleuron divider between US and KR */}
      <div className="pq-ink-tabs mb-8 flex items-center gap-2">
        {(["US", "KR"] as MarketTab[]).map((t, idx) => (
          <div key={t} className="flex items-center gap-2">
            {idx === 1 && (
              <span aria-hidden="true" className="mx-1 text-[var(--pq-bronze)]" style={{ opacity: 0.45, fontSize: "11px" }}>
                &#10086;
              </span>
            )}
            <button
              type="button"
              onClick={() => setTab(t)}
              data-active={tab === t}
              className="pq-ink-tab"
            >
              {t === "US" ? "United States" : "Korea"}
            </button>
          </div>
        ))}
      </div>

      {/* Overview strip — mini sparklines */}
      <section
        aria-label="Overview strip"
        className="mb-10 grid grid-cols-2 gap-4 border-y border-[rgba(245,240,232,0.1)] py-5 sm:grid-cols-3 lg:grid-cols-5"
      >
        {quotes.slice(0, 5).map((q) => (
          <OverviewMini key={q.symbol} quote={q} />
        ))}
      </section>

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

      {/* Calendar + News strip */}
      <section className="mb-10 grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Economic calendar */}
        <div>
          <div className="mb-3 flex items-center gap-2">
            <CalendarDays className="h-4 w-4 text-[var(--pq-bronze)]" strokeWidth={1.3} />
            <div>
              <div className="pq-ink-label">This Week</div>
              <h2 className="pq-ink-h2 mt-0.5">Earnings Calendar</h2>
            </div>
          </div>
          {upcomingEarnings.length === 0 ? (
            <div className="border-t border-[rgba(245,240,232,0.1)] py-8 text-center font-serif italic text-[12px] text-[rgba(245,240,232,0.4)]">
              No scheduled events in the window.
            </div>
          ) : (
            <div className="border-t border-[rgba(245,240,232,0.1)]">
              {upcomingEarnings.map((e, i) => (
                <button
                  key={`${e.ticker}-${i}`}
                  type="button"
                  onClick={() => router.push(`/detail/${e.ticker}`)}
                  className="grid w-full grid-cols-[auto_auto_1fr_auto] items-baseline gap-3 border-b border-[rgba(245,240,232,0.06)] px-2 py-3 text-left transition-colors hover:bg-[rgba(245,240,232,0.03)]"
                >
                  <span
                    aria-hidden="true"
                    className="inline-block"
                    style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--pq-bronze)", opacity: 0.75, transform: "translateY(-2px)" }}
                  />
                  <span className="font-mono text-[11px] tabular-nums text-[var(--pq-bronze)]">
                    {new Date(e.date).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                  <span className="truncate font-serif text-[13px] text-[var(--pq-ivory)]">
                    {e.name || e.ticker}
                  </span>
                  <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-[rgba(245,240,232,0.45)]">
                    {e.ticker}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* News feed placeholder */}
        <div>
          <div className="mb-3 flex items-center gap-2">
            <Newspaper className="h-4 w-4 text-[var(--pq-bronze)]" strokeWidth={1.3} />
            <div>
              <div className="pq-ink-label">Market Pulse</div>
              <h2 className="pq-ink-h2 mt-0.5">Recent Observations</h2>
            </div>
          </div>
          <div className="border-t border-[rgba(245,240,232,0.1)]">
            {[
              { time: "08:42", text: "VIX closed below 15 for the third consecutive session." },
              { time: "07:18", text: "Treasury 10Y yield eased 4bp against a softer CPI print." },
              { time: "06:05", text: "KRW/USD drifted within its 90-day band at 1,355." },
            ].map((row) => (
              <div
                key={row.time}
                className="grid grid-cols-[auto_1fr] items-baseline gap-3 border-b border-[rgba(245,240,232,0.06)] py-3"
              >
                <span className="font-mono text-[11px] tabular-nums text-[var(--pq-bronze)]">
                  {row.time}
                </span>
                <p className="font-serif italic text-[13px] leading-relaxed text-[rgba(245,240,232,0.75)]">
                  {row.text}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <FootSignature />
      <div className="mt-4 text-[rgba(245,240,232,0.7)]">
        <DisclaimerBanner type="signal" />
      </div>
    </ErrorBoundary>
  );
}

/* ── mini overview card ── */

function OverviewMini({ quote }: { quote: IndexQuote }) {
  const isPositive = quote.changePct >= 0;
  const w = 80;
  const h = 22;
  const pad = 1;
  let pts = "";
  if (quote.spark && quote.spark.length > 1) {
    const lo = Math.min(...quote.spark);
    const hi = Math.max(...quote.spark);
    const range = hi - lo || 1;
    const step = (w - pad * 2) / (quote.spark.length - 1);
    pts = quote.spark
      .map((v, i) => {
        const x = pad + i * step;
        const y = pad + ((hi - v) / range) * (h - pad * 2);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }
  return (
    <div
      className="flex items-center gap-3 border-l-[2px] border-transparent px-2 py-1 text-left"
    >
      <div className="min-w-0 flex-1">
        <div className="pq-ink-label truncate" style={{ fontSize: "9px" }}>
          {quote.name}
        </div>
        <div className="mt-0.5 font-mono text-[12px] tabular-nums text-[var(--pq-ivory)]">
          {fmtLevel(quote.level, quote.format)}
        </div>
      </div>
      <div className="text-right">
        {pts ? (
          <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} preserveAspectRatio="none">
            <polyline
              points={pts}
              fill="none"
              stroke={isPositive ? "#7db487" : "#d18888"}
              strokeWidth="1"
            />
          </svg>
        ) : null}
        <div
          className="mt-0.5 font-mono text-[10px] tabular-nums"
          style={{ color: isPositive ? "#7db487" : "#d18888" }}
        >
          {fmtPct(quote.changePct)}
        </div>
      </div>
    </div>
  );
}

/* ── inline ink index card (display-only — indices have no detail page) ── */

function IndexCardInk({
  quote,
}: {
  quote: IndexQuote;
}) {
  const { name, symbol, level, changePct, weekHigh52, weekLow52, spark, format = "en", unit } = quote;
  const isPositive = changePct >= 0;

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

  const rangePct =
    weekHigh52 > weekLow52
      ? Math.max(0, Math.min(1, (level - weekLow52) / (weekHigh52 - weekLow52)))
      : 0.5;

  return (
    <div
      className="pq-ink-stat w-full text-left"
    >
      <div className="flex items-baseline justify-between">
        <div>
          <div className="pq-ink-label">{name}</div>
          <div className="mt-0.5 font-mono text-[9px] text-[rgba(245,240,232,0.4)]">
            {symbol}
          </div>
        </div>
      </div>

      <div className="mt-3 flex items-baseline justify-between">
        <div
          className="pq-num-display"
          style={{
            fontFamily: "var(--font-mono), ui-monospace, monospace",
            fontVariantNumeric: "tabular-nums",
            fontSize: "26px",
            lineHeight: 1.05,
            letterSpacing: "-0.015em",
            color: "var(--pq-ivory)",
          }}
        >
          {fmtLevel(level, format)}
          {unit ? (
            <span className="ml-1 text-[11px] text-[rgba(245,240,232,0.5)]">{unit}</span>
          ) : null}
        </div>
        <div
          className="font-mono text-[12px]"
          style={{ color: isPositive ? "#7db487" : "#d18888" }}
        >
          {fmtPct(changePct)}
        </div>
      </div>

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
