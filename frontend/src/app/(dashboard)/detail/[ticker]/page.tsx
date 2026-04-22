"use client";

/**
 * /detail/[ticker] — Stock detail, Vantablack ink theme.
 *
 * Sections:
 *  - Header: ticker / name / sector / watchlist toggle
 *  - Price + intraday change + 52W range
 *  - Chart with period tabs (1M / 3M / 6M / 1Y / 5Y)
 *  - Fundamentals (P/E, Market Cap, Dividend, Beta, EPS, 52W hi/lo)
 *  - 4-pillar Quant Breakdown (Technical / Fundamental / Sentiment / Quant)
 *  - News feed
 *  - Related artifacts (tier-gated links)
 *
 * Signals: POSITIVE / NEGATIVE / NEUTRAL only.
 */

import { useMemo, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import Link from "next/link";
import { toast } from "sonner";
import { API, WATCHLIST, WATCHLIST_ITEM } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import { fmtUsd, fmtKrw } from "@/lib/format";
import { liveRefresh } from "@/lib/market-hours";
import { PriceWithTimestamp } from "@/components/ui/price-with-timestamp";
import { cn } from "@/lib/utils";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { InteractiveLineChart } from "@/components/charts/interactive-line-chart";
import { useWatchlist } from "@/lib/hooks";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  ExternalLink,
  SearchX,
  Plus,
  Check,
  ArrowLeft,
  FileText,
  Eye,
} from "lucide-react";

/* ── Types ── */

interface Snapshot {
  pe_ratio?: number | null;
  eps?: number | null;
  beta?: number | null;
  market_cap?: number | null;
  avg_volume?: number | null;
  week52_high?: number | null;
  week52_low?: number | null;
  industry?: string;
  profit_margin?: number | null;
  revenue_growth?: number | null;
  debt_equity?: number | null;
}

interface SignalDetail {
  ticker: string;
  name: string;
  signal: string;
  score: number;
  price: number;
  change_pct: number;
  sector: string;
  currency: "USD" | "KRW";
  is_korean: boolean;
  tp_pct: number;
  sl_pct: number;
  tech_score?: number;
  fund_score?: number;
  news_score?: number;
  quant_score?: number;
  snapshot?: Snapshot;
  /** ISO 8601 timestamp of the last price observation. */
  observed_at?: string | null;
}

interface ChartPoint {
  date: string;
  close: number;
}
interface ChartResponse {
  data: ChartPoint[];
}
interface NewsItem {
  title: string;
  link: string;
  source: string;
  published: string;
}
interface NewsResponse {
  news: NewsItem[];
}
// Insider Form 4 filing (from /api/alt-data/us/insider-trades/<ticker>).
// SEC EDGAR data — US tickers only; KR tickers return empty.
interface InsiderFiling {
  insider?: string;
  relationship?: string;
  transaction_date?: string;
  transaction_code?: string;
  shares?: number;
  price?: number;
  value_usd?: number;
  acquired?: boolean;
}
interface InsiderResponse {
  ticker?: string;
  data?: InsiderFiling[];
  source?: string;
}

// Matches the actual /api/profile/<ticker> response shape (routes/market.py L433).
// Fundamentals like pe_ratio/eps/beta/52W are read from signal.snapshot instead.
interface ProfileData {
  ticker?: string;
  name?: string;
  summary?: string;
  sector?: string;
  industry?: string;
  website?: string;
  employees?: number | null;
  country?: string;
  market_cap?: number | null;
  currency?: "USD" | "KRW";
}

/* ── Fetcher ── */

const fetcher = async (url: string) => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

/* ── Helpers ── */

function isKrw(signal: SignalDetail | undefined, ticker: string): boolean {
  if (signal?.currency === "KRW") return true;
  if (signal?.is_korean === true) return true;
  return /^\d{6}\.(KS|KQ)$/i.test(ticker);
}

function fmtPrice(value: number | undefined, krw: boolean): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return krw ? fmtKrw(value) : fmtUsd(value);
}

function fmtMcap(value: number | null | undefined, krw: boolean): string {
  if (value == null || value <= 0) return "—";
  if (krw) {
    if (value >= 1e12) return `${(value / 1e12).toFixed(1)}조`;
    if (value >= 1e8) return `${(value / 1e8).toFixed(0)}억`;
    return `${value.toLocaleString()}`;
  }
  if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
  if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(0)}M`;
  return `$${value.toLocaleString()}`;
}

function fmtSignedPct(pct: number | undefined): string {
  if (pct == null || !Number.isFinite(pct)) return "—";
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function pctColor(pct: number | undefined): string {
  if (pct == null) return "text-[rgba(245,240,232,0.5)]";
  if (pct > 0) return "text-emerald-400";
  if (pct < 0) return "text-red-400";
  return "text-[rgba(245,240,232,0.6)]";
}

function pillarToken(label: string): "POSITIVE" | "NEGATIVE" | "NEUTRAL" {
  return label === "POSITIVE" ? "POSITIVE" : label === "NEGATIVE" ? "NEGATIVE" : "NEUTRAL";
}

/** Short relative time — "3d ago", "2w ago", "—". Observation tone only. */
function formatRelative(iso: string | undefined): string {
  if (!iso) return "—";
  const parsed = new Date(iso);
  if (isNaN(parsed.getTime())) return "—";
  const diffMs = Date.now() - parsed.getTime();
  if (diffMs < 0) return "—";
  const days = Math.floor(diffMs / 86_400_000);
  if (days < 1) return "today";
  if (days === 1) return "1d ago";
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return weeks === 1 ? "1w ago" : `${weeks}w ago`;
  const months = Math.floor(days / 30);
  return months === 1 ? "1mo ago" : `${months}mo ago`;
}

/* ── Chart ── */

// Period tabs. Backend accepts 1mo,3mo,6mo,1y,2y,1d,5d (routes/market.py L295).
// Max historical period supported server-side is 2Y.
const PERIODS = ["1M", "3M", "6M", "1Y", "2Y"] as const;
type Period = typeof PERIODS[number];
const PERIOD_MAP: Record<Period, string> = {
  "1M": "1mo",
  "3M": "3mo",
  "6M": "6mo",
  "1Y": "1y",
  "2Y": "2y",
};

function SparkChart({
  data,
  currency = "USD",
}: {
  data: ChartPoint[];
  currency?: "USD" | "KRW";
}) {
  if (!data || data.length < 2) {
    return (
      <div className="h-48 flex items-center justify-center text-xs text-[rgba(245,240,232,0.4)]">
        No chart data
      </div>
    );
  }
  const series = data.map((d) => ({ date: d.date, value: d.close }));
  const priceFmt = currency === "KRW" ? fmtKrw : fmtUsd;
  return (
    <InteractiveLineChart
      points={series}
      height={200}
      valueFormatter={(v) => priceFmt(v)}
      dateFormatter={(d) => {
        const parsed = new Date(d);
        return isNaN(parsed.getTime())
          ? d
          : parsed.toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "numeric",
            });
      }}
      yLabel="Last observed"
      ariaLabel="Price observation chart"
    />
  );
}

/* ── Pillar card ── */

function PillarCard({
  label,
  score,
  observation,
}: {
  label: string;
  score: number;
  observation: string;
}) {
  const safe = Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : 0;
  const token: "POSITIVE" | "NEGATIVE" | "NEUTRAL" =
    safe >= 65 ? "POSITIVE" : safe <= 35 ? "NEGATIVE" : "NEUTRAL";
  const barColor =
    token === "POSITIVE"
      ? "bg-emerald-400"
      : token === "NEGATIVE"
        ? "bg-red-400"
        : "bg-[var(--pq-bronze)]";
  const textColor =
    token === "POSITIVE"
      ? "text-emerald-400"
      : token === "NEGATIVE"
        ? "text-red-400"
        : "text-[rgba(245,240,232,0.7)]";
  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-5 rounded-[2px]">
      <div className="flex items-center justify-between">
        <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
          {label}
        </div>
        <div className={cn("text-[10px] tracking-[0.18em] uppercase", textColor)}>
          {token}
        </div>
      </div>
      <div className={cn("mt-3 font-mono text-2xl tabular-nums", textColor)}>
        {safe.toFixed(0)}
        <span className="text-xs text-[rgba(245,240,232,0.4)] ml-1">/ 100</span>
      </div>
      {/* Horizontal score bar */}
      <div className="mt-3 h-1 bg-[rgba(245,240,232,0.08)] overflow-hidden">
        <div
          className={cn("h-full transition-all", barColor)}
          style={{ width: `${safe}%` }}
        />
      </div>
      <p className="mt-3 text-[11px] leading-relaxed text-[rgba(245,240,232,0.55)] font-serif">
        {observation}
      </p>
    </div>
  );
}

/* ── Fundamentals cell ── */

function Fund({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-4 rounded-[2px]">
      <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
        {label}
      </div>
      <div className="mt-2 font-mono text-base text-[var(--pq-ivory)] tabular-nums">
        {value}
      </div>
    </div>
  );
}

/* ── Page ── */

export default function StockDetailPage() {
  const params = useParams<{ ticker: string }>();
  const router = useRouter();
  const raw = (params.ticker ?? "").toUpperCase();
  const ticker = /^\d{6}$/.test(raw) ? `${raw}.KS` : raw;
  const [period, setPeriod] = useState<Period>("1M");

  // Detail page live tiers:
  //  signal/quote    → 15s (near-realtime quote-driven)
  //  chart           → 60s (intraday bars)
  //  news            → 2min (news refresh cadence)
  //  profile         → 5min (company profile rarely changes)
  const { data: signal, isLoading: loadingSignal } = useSWR<SignalDetail>(
    ticker ? API.signals.one(ticker) : null,
    fetcher,
    {
      // Market-aware: 5s when open, 30s when closed.
      refreshInterval: () => liveRefresh(5_000, 30_000),
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 2_000,
      errorRetryCount: 2,
      errorRetryInterval: 5_000,
    },
  );
  const { data: chartRes, isLoading: loadingChart } = useSWR<ChartResponse>(
    ticker ? `${API.market.chart(ticker)}?period=${PERIOD_MAP[period]}` : null,
    fetcher,
    {
      refreshInterval: () => liveRefresh(15_000, 120_000),
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 5_000,
      shouldRetryOnError: false,
    },
  );
  const { data: newsRes, isLoading: loadingNews } = useSWR<NewsResponse>(
    ticker ? API.market.news(ticker) : null,
    fetcher,
    {
      refreshInterval: 120_000,
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 30_000,
      errorRetryCount: 2,
      errorRetryInterval: 10_000,
    },
  );
  const { data: profile, isLoading: loadingProfile } = useSWR<ProfileData>(
    ticker ? API.market.profile(ticker) : null,
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
  // Insider Form 4 — US only. KR (6-digit.KS/.KQ) skipped: SEC EDGAR US-only source.
  // Cache 10min — filings update daily at most.
  const insiderEligible = ticker && !/^\d{6}\.(KS|KQ)$/i.test(ticker);
  const { data: insiderRes } = useSWR<InsiderResponse>(
    insiderEligible ? `/api/alt-data/us/insider-trades/${ticker}?days=90` : null,
    fetcher,
    {
      refreshInterval: 600_000,
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 60_000,
      shouldRetryOnError: false,
    },
  );
  const insiderData: InsiderFiling[] = Array.isArray(insiderRes?.data)
    ? (insiderRes!.data as InsiderFiling[])
    : [];

  const { data: watchlistData, mutate: refreshWatchlist } = useWatchlist();
  const watchlistEntry = watchlistData?.watchlist?.find((w) => w.ticker === ticker);
  const inWatchlist = Boolean(watchlistEntry);

  const krw = isKrw(signal, ticker);

  const handleWatchlistToggle = useCallback(async () => {
    try {
      if (inWatchlist && watchlistEntry) {
        await apiFetch(WATCHLIST_ITEM(watchlistEntry.id), { method: "DELETE" });
        toast.success("Removed from watchlist");
      } else {
        await apiFetch(WATCHLIST, {
          method: "POST",
          body: JSON.stringify({ ticker }),
        });
        toast.success("Added to watchlist");
      }
      refreshWatchlist();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed";
      toast.error(msg);
    }
  }, [inWatchlist, watchlistEntry, ticker, refreshWatchlist]);

  const hasPillars = useMemo(
    () =>
      signal?.tech_score != null ||
      signal?.fund_score != null ||
      signal?.news_score != null ||
      signal?.quant_score != null,
    [signal],
  );

  /* ── No ticker / not-found ── */
  if (!ticker) {
    return (
      <ErrorBoundary>
        <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-12 rounded-[2px] text-center">
          <SearchX className="mx-auto h-8 w-8 text-[var(--pq-bronze)]" strokeWidth={1.2} />
          <p className="mt-4 font-serif text-xl text-[var(--pq-ivory)]">
            No ticker specified
          </p>
          <Link
            href="/discover"
            className="mt-6 inline-block pq-ink-btn-bronze"
          >
            Browse discover
          </Link>
        </div>
      </ErrorBoundary>
    );
  }

  if (!loadingSignal && !loadingProfile && !signal && !profile) {
    return (
      <ErrorBoundary>
        <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-12 rounded-[2px] text-center">
          <SearchX className="mx-auto h-8 w-8 text-[var(--pq-bronze)]" strokeWidth={1.2} />
          <p className="mt-4 font-serif text-xl text-[var(--pq-ivory)]">
            No data for &ldquo;{ticker}&rdquo;
          </p>
          <p className="mt-2 text-sm text-[rgba(245,240,232,0.5)]">
            Ticker may be unsupported or temporarily unavailable.
          </p>
          <button
            type="button"
            onClick={() => router.back()}
            className="mt-6 pq-ink-btn-ghost inline-flex items-center gap-1.5"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back
          </button>
        </div>
      </ErrorBoundary>
    );
  }

  const signalToken =
    signal?.signal === "POSITIVE" || signal?.signal === "NEGATIVE"
      ? signal.signal
      : "NEUTRAL";

  return (
    <ErrorBoundary>
      <div className="space-y-8">
        {/* ── Header ── */}
        <header className="flex items-start justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
              {signal?.sector || profile?.sector || "—"} · {krw ? "KRW" : "USD"}
            </div>
            <h1 className="mt-2 font-serif italic text-2xl md:text-3xl text-[var(--pq-ivory)] truncate">
              {signal?.name || profile?.name || ticker}
            </h1>
            <div className="mt-1 font-mono text-sm text-[rgba(245,240,232,0.5)]">
              {ticker}
            </div>
          </div>

          <button
            type="button"
            onClick={handleWatchlistToggle}
            className={cn(
              "inline-flex items-center gap-1.5",
              inWatchlist ? "pq-ink-btn-ghost" : "pq-ink-btn-bronze",
            )}
          >
            {inWatchlist ? (
              <>
                <Check className="h-3.5 w-3.5" />
                In watchlist
              </>
            ) : (
              <>
                <Plus className="h-3.5 w-3.5" />
                Add to watchlist
              </>
            )}
          </button>
        </header>

        <DisclaimerBanner type="signal" />

        {/* ── Price hero ── */}
        <section className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-6 rounded-[2px]">
          <div className="flex items-end justify-between flex-wrap gap-4">
            <div>
              <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
                Current price · observed
              </div>
              <div className="mt-2">
                <PriceWithTimestamp
                  price={signal?.price}
                  observedAt={signal?.observed_at}
                  currency={krw ? "KRW" : "USD"}
                  size="lg"
                />
              </div>
              <div
                className={cn(
                  "mt-2 flex items-center gap-1.5 tabular-nums",
                  pctColor(signal?.change_pct),
                )}
              >
                {signal?.change_pct == null ? (
                  <Minus className="h-3.5 w-3.5" />
                ) : signal.change_pct >= 0 ? (
                  <TrendingUp className="h-3.5 w-3.5" />
                ) : (
                  <TrendingDown className="h-3.5 w-3.5" />
                )}
                {fmtSignedPct(signal?.change_pct)}
                <span className="text-xs text-[rgba(245,240,232,0.4)] ml-1">
                  · 1D
                </span>
              </div>
            </div>

            <div className="text-right">
              <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
                Signal · {pillarToken(signalToken)}
              </div>
              <div className="mt-2 font-mono text-2xl md:text-3xl text-[var(--pq-ivory)] tabular-nums">
                {signal?.score ?? "—"}
              </div>
              <div className="text-xs text-[rgba(245,240,232,0.5)] mt-1">
                / 100
              </div>
            </div>
          </div>

          {/* 52W range — sourced from signal.snapshot (primary data source) */}
          {signal?.snapshot?.week52_low != null && signal?.snapshot?.week52_high != null && (
            <div className="mt-6 pt-4 border-t border-[rgba(245,240,232,0.08)]">
              <div className="flex items-center justify-between text-xs text-[rgba(245,240,232,0.5)] mb-2">
                <span>52W low · {fmtPrice(signal.snapshot.week52_low, krw)}</span>
                <span>52W high · {fmtPrice(signal.snapshot.week52_high, krw)}</span>
              </div>
              <div className="h-0.5 bg-[rgba(245,240,232,0.08)] relative">
                {signal?.price && (
                  <div
                    className="absolute top-1/2 -translate-y-1/2 h-2 w-2 rounded-full bg-[var(--pq-bronze)]"
                    style={{
                      left: `${Math.min(
                        100,
                        Math.max(
                          0,
                          ((signal.price - signal.snapshot.week52_low) /
                            (signal.snapshot.week52_high - signal.snapshot.week52_low)) *
                            100,
                        ),
                      )}%`,
                    }}
                  />
                )}
              </div>
            </div>
          )}
        </section>

        {/* ── Chart ── */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="pq-ink-h2">Price history</h2>
            <div className="flex gap-1">
              {PERIODS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPeriod(p)}
                  className={cn(
                    "px-3 py-1 text-xs tracking-[0.18em] uppercase transition-colors",
                    period === p
                      ? "text-[var(--pq-ivory)] border-b border-[var(--pq-bronze)]"
                      : "text-[rgba(245,240,232,0.4)] hover:text-[var(--pq-bronze)]",
                  )}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-5 rounded-[2px]">
            {loadingChart ? (
              <div className="h-48 animate-pulse bg-[rgba(255,255,255,0.02)]" />
            ) : (
              <SparkChart
                data={chartRes?.data ?? []}
                currency={signal?.currency ?? "USD"}
              />
            )}
          </div>
        </section>

        {/* ── Fundamentals — sourced from signal.snapshot, profile as fallback ── */}
        <section>
          <h2 className="pq-ink-h2 mb-4">Fundamentals</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <Fund
              label="P/E"
              value={
                signal?.snapshot?.pe_ratio != null &&
                Number.isFinite(signal.snapshot.pe_ratio)
                  ? Number(signal.snapshot.pe_ratio).toFixed(1)
                  : "—"
              }
            />
            <Fund
              label="Market cap"
              value={fmtMcap(
                signal?.snapshot?.market_cap ?? profile?.market_cap ?? null,
                krw,
              )}
            />
            <Fund
              label="EPS"
              value={
                signal?.snapshot?.eps != null &&
                Number.isFinite(signal.snapshot.eps)
                  ? Number(signal.snapshot.eps).toFixed(2)
                  : "—"
              }
            />
            <Fund
              label="Beta"
              value={
                signal?.snapshot?.beta != null &&
                Number.isFinite(signal.snapshot.beta)
                  ? Number(signal.snapshot.beta).toFixed(2)
                  : "—"
              }
            />
            <Fund
              label="Avg volume"
              value={
                signal?.snapshot?.avg_volume
                  ? signal.snapshot.avg_volume.toLocaleString()
                  : "—"
              }
            />
            <Fund
              label="Industry"
              value={
                signal?.snapshot?.industry ||
                profile?.industry ||
                "—"
              }
            />
          </div>
        </section>

        {/* ── Quant pillars ── */}
        <section>
          <h2 className="pq-ink-h2 mb-4">Quant breakdown</h2>
          {hasPillars ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <PillarCard
                label="Technical"
                score={signal?.tech_score ?? 0}
                observation="Price action, momentum, moving averages"
              />
              <PillarCard
                label="Fundamental"
                score={signal?.fund_score ?? 0}
                observation="Earnings, margins, debt, growth"
              />
              <PillarCard
                label="Sentiment"
                score={signal?.news_score ?? 0}
                observation="News tone and media coverage"
              />
              <PillarCard
                label="Quant"
                score={signal?.quant_score ?? 0}
                observation="Variance ratio, momentum, 52W position"
              />
            </div>
          ) : (
            <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-6 rounded-[2px] text-center text-sm text-[rgba(245,240,232,0.5)]">
              Pillar breakdown pending for this ticker.
            </div>
          )}
        </section>

        {/* ── News ── */}
        <section>
          <h2 className="pq-ink-h2 mb-4">News</h2>
          {loadingNews ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="h-16 rounded-[2px] bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] animate-pulse"
                />
              ))}
            </div>
          ) : !newsRes?.news?.length ? (
            <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-6 rounded-[2px] text-center text-sm text-[rgba(245,240,232,0.5)]">
              No recent news.
            </div>
          ) : (
            <ul className="space-y-2">
              {newsRes.news.slice(0, 8).map((n, i) => (
                <li key={i}>
                  <a
                    href={n.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group block bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-4 rounded-[2px] hover:border-[var(--pq-bronze)] transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="font-serif text-base text-[var(--pq-ivory)] group-hover:text-[var(--pq-bronze)] transition-colors line-clamp-2">
                          {n.title}
                        </p>
                        <div className="mt-1 flex items-center gap-2 text-xs text-[rgba(245,240,232,0.4)]">
                          <span>{n.source}</span>
                          <span>·</span>
                          <span>{n.published}</span>
                        </div>
                      </div>
                      <ExternalLink className="h-3.5 w-3.5 shrink-0 text-[rgba(245,240,232,0.3)] group-hover:text-[var(--pq-bronze)]" />
                    </div>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* ── Related artifacts (richer grid — observation-only) ── */}
        <section>
          <header className="mb-5 flex items-center gap-3 pb-3 border-b border-[rgba(245,240,232,0.08)]">
            <FileText className="h-4 w-4 text-[var(--pq-bronze)]" />
            <h2 className="font-serif text-xl text-[var(--pq-ivory)]">
              Related observations
            </h2>
          </header>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              {
                slug: "weekly_memo",
                name: "Weekly Memo",
                desc: "Portfolio-wide context, authored weekly",
              },
              {
                slug: "earnings_prebrief",
                name: "Earnings Pre-Brief",
                desc: "Ten-day forward earnings observation",
              },
              {
                slug: "dd_checklist",
                name: "DD Checklist",
                desc: "Structured due-diligence reference",
              },
            ].map((r) => (
              <a
                key={r.slug}
                href={`/samples/${r.slug}.pdf`}
                target="_blank"
                rel="noopener noreferrer"
                className="block border border-[rgba(245,240,232,0.08)] rounded-[2px] p-4 hover:border-[var(--pq-bronze)] hover:bg-[rgba(139,111,71,0.03)] transition-all group"
              >
                <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)] mb-2">
                  PDF · Observational
                </div>
                <div className="font-serif text-[var(--pq-ivory)] mb-1">
                  {r.name}
                </div>
                <div className="text-[11px] text-[rgba(245,240,232,0.55)]">
                  {r.desc}
                </div>
                <div className="mt-3 text-[10px] uppercase tracking-[0.22em] text-[var(--pq-bronze)] opacity-0 group-hover:opacity-100 transition-opacity">
                  Open PDF →
                </div>
              </a>
            ))}
          </div>
        </section>

        {/* ── Insider filings · last 90 days ── */}
        {insiderEligible && (
          <section>
            <header className="mb-5 flex items-center gap-3 pb-3 border-b border-[rgba(245,240,232,0.08)]">
              <Eye className="h-4 w-4 text-[var(--pq-bronze)]" />
              <h2 className="font-serif text-xl text-[var(--pq-ivory)]">
                Insider filings · last 90 days
              </h2>
            </header>
            {insiderData.length > 0 ? (
              <ul className="space-y-2">
                {insiderData.slice(0, 5).map((f, i) => {
                  const acquired = f.acquired === true;
                  const shares = Number.isFinite(f.shares as number)
                    ? (f.shares as number)
                    : 0;
                  return (
                    <li
                      key={i}
                      className="flex items-center justify-between py-2 border-b border-[rgba(245,240,232,0.06)]"
                    >
                      <div className="min-w-0">
                        <span className="text-[13px] text-[var(--pq-ivory)]">
                          {f.insider || "—"}
                        </span>
                        {f.relationship && (
                          <span className="ml-2 text-[10px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
                            {f.relationship}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span
                          className={cn(
                            "text-[11px] font-mono tabular-nums",
                            acquired ? "text-emerald-400" : "text-red-400",
                          )}
                        >
                          {acquired ? "ACQ" : "DSP"} {shares.toLocaleString()}
                        </span>
                        <span className="text-[10px] text-[rgba(245,240,232,0.5)]">
                          {formatRelative(f.transaction_date)}
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-[12px] text-[rgba(245,240,232,0.55)]">
                No public filings observed in the last 90 days.
              </p>
            )}
          </section>
        )}
      </div>
    </ErrorBoundary>
  );
}
