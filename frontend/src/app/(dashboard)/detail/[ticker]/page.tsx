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
import { cn } from "@/lib/utils";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
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
} from "lucide-react";

/* ── Types ── */

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
interface ProfileData {
  name: string;
  sector: string;
  industry: string;
  description: string;
  market_cap: number;
  pe_ratio: number | null;
  eps: number | null;
  dividend_yield: number | null;
  beta: number | null;
  avg_volume: number;
  week52_high: number;
  week52_low: number;
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

/* ── Chart ── */

const PERIODS = ["1M", "3M", "6M", "1Y", "5Y"] as const;
type Period = typeof PERIODS[number];
const PERIOD_MAP: Record<Period, string> = {
  "1M": "1mo",
  "3M": "3mo",
  "6M": "6mo",
  "1Y": "1y",
  "5Y": "5y",
};

function SparkChart({ data }: { data: ChartPoint[] }) {
  if (!data || data.length < 2) {
    return (
      <div className="h-48 flex items-center justify-center text-xs text-[rgba(245,240,232,0.4)]">
        No chart data
      </div>
    );
  }
  const values = data.map((d) => d.close);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 800;
  const h = 200;
  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const path = `M ${points.join(" L ")}`;

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="w-full h-48"
      preserveAspectRatio="none"
    >
      <path
        d={path}
        fill="none"
        stroke="var(--pq-bronze)"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/* ── Pillar card ── */

function PillarCard({
  label,
  score,
}: {
  label: string;
  score: number;
}) {
  const token =
    score >= 65 ? "POSITIVE" : score <= 35 ? "NEGATIVE" : "NEUTRAL";
  const color =
    token === "POSITIVE"
      ? "text-emerald-400"
      : token === "NEGATIVE"
        ? "text-red-400"
        : "text-[rgba(245,240,232,0.7)]";
  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-5 rounded-[2px]">
      <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
        {label}
      </div>
      <div className={cn("mt-3 font-mono text-2xl tabular-nums", color)}>
        {score}
      </div>
      <div className="mt-2 text-[10px] tracking-[0.18em] uppercase text-[rgba(245,240,232,0.5)]">
        {token}
      </div>
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

  const { data: signal, isLoading: loadingSignal } = useSWR<SignalDetail>(
    ticker ? API.signals.one(ticker) : null,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 30_000 },
  );
  const { data: chartRes, isLoading: loadingChart } = useSWR<ChartResponse>(
    ticker ? `${API.market.chart(ticker)}?period=${PERIOD_MAP[period]}` : null,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000, shouldRetryOnError: false },
  );
  const { data: newsRes, isLoading: loadingNews } = useSWR<NewsResponse>(
    ticker ? API.market.news(ticker) : null,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 120_000 },
  );
  const { data: profile, isLoading: loadingProfile } = useSWR<ProfileData>(
    ticker ? API.market.profile(ticker) : null,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 300_000 },
  );

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
          <p className="mt-4 font-serif italic text-xl text-[var(--pq-ivory)]">
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
          <p className="mt-4 font-serif italic text-xl text-[var(--pq-ivory)]">
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
            <h1 className="mt-2 font-serif italic text-3xl text-[var(--pq-ivory)] truncate">
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
                Current price
              </div>
              <div className="mt-2 font-mono text-4xl text-[var(--pq-ivory)] tabular-nums">
                {fmtPrice(signal?.price, krw)}
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
              <div className="mt-2 font-mono text-3xl text-[var(--pq-ivory)] tabular-nums">
                {signal?.score ?? "—"}
              </div>
              <div className="text-xs text-[rgba(245,240,232,0.5)] mt-1">
                / 100
              </div>
            </div>
          </div>

          {/* 52W range */}
          {profile?.week52_low != null && profile?.week52_high != null && (
            <div className="mt-6 pt-4 border-t border-[rgba(245,240,232,0.08)]">
              <div className="flex items-center justify-between text-xs text-[rgba(245,240,232,0.5)] mb-2">
                <span>52W low · {fmtPrice(profile.week52_low, krw)}</span>
                <span>52W high · {fmtPrice(profile.week52_high, krw)}</span>
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
                          ((signal.price - profile.week52_low) /
                            (profile.week52_high - profile.week52_low)) *
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
              <SparkChart data={chartRes?.data ?? []} />
            )}
          </div>
        </section>

        {/* ── Fundamentals ── */}
        <section>
          <h2 className="pq-ink-h2 mb-4">Fundamentals</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <Fund
              label="P/E"
              value={
                profile?.pe_ratio != null
                  ? Number(profile.pe_ratio).toFixed(1)
                  : "—"
              }
            />
            <Fund
              label="Market cap"
              value={fmtMcap(profile?.market_cap, krw)}
            />
            <Fund
              label="Dividend"
              value={
                profile?.dividend_yield != null
                  ? `${(profile.dividend_yield * 100).toFixed(2)}%`
                  : "—"
              }
            />
            <Fund
              label="Beta"
              value={
                profile?.beta != null ? Number(profile.beta).toFixed(2) : "—"
              }
            />
            <Fund
              label="EPS"
              value={
                profile?.eps != null ? Number(profile.eps).toFixed(2) : "—"
              }
            />
            <Fund
              label="Avg volume"
              value={
                profile?.avg_volume
                  ? profile.avg_volume.toLocaleString()
                  : "—"
              }
            />
          </div>
        </section>

        {/* ── Quant pillars ── */}
        <section>
          <h2 className="pq-ink-h2 mb-4">Quant breakdown</h2>
          {hasPillars ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <PillarCard label="Technical" score={signal?.tech_score ?? 0} />
              <PillarCard label="Fundamental" score={signal?.fund_score ?? 0} />
              <PillarCard label="Sentiment" score={signal?.news_score ?? 0} />
              <PillarCard label="Quant" score={signal?.quant_score ?? 0} />
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
                        <p className="font-serif italic text-base text-[var(--pq-ivory)] group-hover:text-[var(--pq-bronze)] transition-colors line-clamp-2">
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

        {/* ── Related artifacts ── */}
        <section>
          <h2 className="pq-ink-h2 mb-4">Related artifacts</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { slug: "dd_checklist", title: "DD Checklist" },
              { slug: "earnings_prebrief", title: "Earnings Pre-Brief" },
              { slug: "weekly_memo", title: "Weekly Memo" },
            ].map((a) => (
              <Link
                key={a.slug}
                href={`/samples/${a.slug}.pdf`}
                target="_blank"
                className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-4 rounded-[2px] flex items-center gap-3 hover:border-[var(--pq-bronze)] transition-colors group"
              >
                <FileText className="h-4 w-4 text-[var(--pq-bronze)]" />
                <span className="font-serif italic text-sm text-[var(--pq-ivory)] group-hover:text-[var(--pq-bronze)] transition-colors">
                  {a.title}
                </span>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </ErrorBoundary>
  );
}
