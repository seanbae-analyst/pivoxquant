"use client";

/**
 * /detail/[ticker] — Stock detail, Vantablack editorial (v2).
 *
 * Redesigned 2026-04-22 to "Goldman IC desk" standard:
 *  - 3-column editorial hero (identity / price / signal)
 *  - Typography trinity: Source Serif 4 italic H1, JetBrains Mono numbers,
 *    Geist sans-serif small-caps kickers (0.12em instead of 0.22em).
 *  - Hairline editorial rules + bronze accent; no radius > 2px.
 *  - Grouped news (date headers + sentiment chips), stat-row fundamentals.
 *  - Editorial "Data unavailable" fallbacks instead of bare em-dashes.
 *
 * Signals: POSITIVE / NEGATIVE / NEUTRAL only — BUY/SELL banned by law.
 * DisclaimerBanner(signal) retained inside the hero block.
 */

import { useMemo, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import Link from "next/link";
import { toast } from "sonner";
import { API, WATCHLIST, WATCHLIST_ITEM } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import { fmtUsd, fmtKrw, pctColorClass } from "@/lib/format";
import { liveRefresh } from "@/lib/market-hours";
import { PriceWithTimestamp } from "@/components/ui/price-with-timestamp";
import { cn } from "@/lib/utils";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { InteractiveLineChart } from "@/components/charts/interactive-line-chart";
import { FieldLabel, StatRow } from "@/components/ui/editorial";
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
  Sparkles,
  CalendarDays,
  Building2,
  MessageSquare,
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
// Insider Form 4 — SEC EDGAR, US tickers only.
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

// AI SWOT — POST /api/ai/swot
interface SwotResponse {
  swot?: string;
  swot_kr?: string;
}

// Earnings calendar — GET /api/earnings (filtered by ticker client-side).
// Backend (routes/market.py:440) returns:
//   { earnings: [{ ticker, name, date, signal, score }] }
// `signal` is POSITIVE/NEGATIVE/NEUTRAL/—. eps_*/revenue_* fields are
// kept optional for forward-compat if backend ever extends the schema.
interface EarningsItem {
  ticker?: string;
  symbol?: string;        // alias compat — not currently emitted
  name?: string;
  date?: string;
  signal?: "POSITIVE" | "NEGATIVE" | "NEUTRAL" | "—" | string;
  score?: number;
  eps_estimate?: number | null;       // forward-compat (unused today)
  eps_actual?: number | null;
  revenue_estimate?: number | null;
  revenue_actual?: number | null;
}
interface EarningsResponse {
  earnings?: EarningsItem[];
  data?: EarningsItem[];
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

function fmtPrice(value: number | undefined | null, krw: boolean): string {
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

function fmtSignedPct(pct: number | string | null | undefined): string {
  if (pct == null) return "—";
  // Signals cache sometimes returns numeric strings — coerce defensively
  // so a valid value doesn't fall through to the em-dash branch.
  const n = typeof pct === "number" ? pct : Number(pct);
  if (!Number.isFinite(n)) return "—";
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
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

/** Lightweight keyword-based news sentiment — editorial classifier, observation-only. */
function classifyNewsSentiment(title: string): "pos" | "neg" | "neu" {
  const t = title.toLowerCase();
  const pos = [
    "beat", "beats", "surge", "surges", "rally", "rallies", "record high",
    "upgrade", "raised", "strong", "growth", "profit", "buyback",
    "partnership", "approval", "wins", "boost", "breakthrough",
    "outperform", "exceeds", "milestone", "expands",
  ];
  const neg = [
    "miss", "misses", "plunge", "plunges", "drop", "drops", "decline",
    "downgrade", "cut", "weak", "lawsuit", "probe", "investigation",
    "recall", "loss", "fraud", "bankruptcy", "warns", "warning",
    "layoffs", "halt", "suspends", "scandal", "subpoena", "underperform",
  ];
  for (const w of pos) if (t.includes(w)) return "pos";
  for (const w of neg) if (t.includes(w)) return "neg";
  return "neu";
}

/** Bucket news items by human day label ("Today", "Yesterday", "Apr 18"). */
function bucketNewsByDay(items: NewsItem[]): Array<{ label: string; items: NewsItem[] }> {
  const buckets = new Map<string, NewsItem[]>();
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const dayMs = 86_400_000;

  for (const n of items) {
    const dt = new Date(n.published);
    const ts = isNaN(dt.getTime()) ? NaN : dt.getTime();
    let label: string;
    if (!Number.isFinite(ts)) {
      label = "Undated";
    } else {
      const local = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()).getTime();
      const delta = today - local;
      if (delta <= 0) label = "Today";
      else if (delta < dayMs * 1.5) label = "Yesterday";
      else if (delta < dayMs * 7) {
        label = dt.toLocaleDateString("en-US", { weekday: "long" });
      } else {
        label = dt.toLocaleDateString("en-US", { month: "short", day: "numeric" });
      }
    }
    const arr = buckets.get(label) ?? [];
    arr.push(n);
    buckets.set(label, arr);
  }
  return Array.from(buckets.entries()).map(([label, items]) => ({ label, items }));
}

/* ── Chart ── */

// Backend accepts 1mo/3mo/6mo/1y/2y (routes/market.py L295). 2Y is server max.
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
      <div className="h-64 flex items-center justify-center pq-detail-empty-note">
        Chart data unavailable for this window.
      </div>
    );
  }
  const series = data.map((d) => ({ date: d.date, value: d.close }));
  const priceFmt = currency === "KRW" ? fmtKrw : fmtUsd;
  return (
    <InteractiveLineChart
      points={series}
      height={260}
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
  // KR convention (CEO directive 2026-04-26): POSITIVE → red (▲), NEGATIVE → blue (▼).
  const barColor =
    token === "POSITIVE"
      ? "bg-[#D18888]"
      : token === "NEGATIVE"
        ? "bg-[#7AA0C8]"
        : "bg-[var(--pq-bronze)]";
  const textColor =
    token === "POSITIVE"
      ? "text-[#D18888]"
      : token === "NEGATIVE"
        ? "text-[#7AA0C8]"
        : "text-[rgba(245,240,232,0.7)]";
  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-5 rounded-[2px] pq-ink-card-interactive">
      <div className="flex items-center justify-between">
        <FieldLabel>{label}</FieldLabel>
        <span
          className={cn(
            "text-[9px] tracking-[0.18em] uppercase font-medium",
            textColor,
          )}
        >
          {token}
        </span>
      </div>
      <div className={cn("mt-3 font-mono text-[28px] tabular-nums leading-none", textColor)}>
        {safe.toFixed(0)}
        <span className="text-xs text-[rgba(245,240,232,0.4)] ml-1.5">/ 100</span>
      </div>
      <div className="mt-3 h-[2px] bg-[rgba(245,240,232,0.08)] overflow-hidden">
        <div
          className={cn("h-full transition-all", barColor)}
          style={{ width: `${safe}%` }}
        />
      </div>
      <p className="mt-3 pq-detail-body text-[13px]">
        {observation}
      </p>
    </div>
  );
}

/* ── Page ── */

export default function StockDetailPage() {
  const params = useParams<{ ticker: string }>();
  const router = useRouter();
  const raw = (params.ticker ?? "").toUpperCase();
  const ticker = /^\d{6}$/.test(raw) ? `${raw}.KS` : raw;
  const [period, setPeriod] = useState<Period>("3M");

  const { data: signal, isLoading: loadingSignal } = useSWR<SignalDetail>(
    ticker ? API.signals.one(ticker) : null,
    fetcher,
    {
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

  // Earnings calendar — server returns next-30d list; client filters by ticker.
  const { data: earningsRes } = useSWR<EarningsResponse>(
    ticker ? API.market.earnings : null,
    fetcher,
    {
      refreshInterval: 600_000,
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 60_000,
      shouldRetryOnError: false,
    },
  );
  const earningsForTicker: EarningsItem[] = useMemo(() => {
    const list = earningsRes?.earnings ?? earningsRes?.data ?? [];
    if (!ticker) return [];
    const upper = ticker.toUpperCase();
    return list
      .filter((e) => {
        const t = (e.ticker || e.symbol || "").toUpperCase();
        return t === upper;
      })
      .slice(0, 4);
  }, [earningsRes, ticker]);

  // AI SWOT — on-demand POST (Claude is rate-limited; user-triggered).
  const [swot, setSwot] = useState<SwotResponse | null>(null);
  const [swotLoading, setSwotLoading] = useState(false);
  const [swotError, setSwotError] = useState<string | null>(null);
  const handleGenerateSwot = useCallback(async () => {
    if (!ticker) return;
    setSwotLoading(true);
    setSwotError(null);
    try {
      const res = await apiFetch<SwotResponse>(API.ai.swot, {
        method: "POST",
        body: JSON.stringify({ ticker }),
      });
      setSwot(res);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Request failed";
      setSwotError(msg);
    } finally {
      setSwotLoading(false);
    }
  }, [ticker]);

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

  const newsGroups = useMemo(
    () => (newsRes?.news ? bucketNewsByDay(newsRes.news.slice(0, 12)) : []),
    [newsRes],
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
          <Link href="/discover" className="mt-6 inline-block pq-ink-btn-bronze">
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

  // Sector resolution — some upstream paths emit the string literal
  // "UNKNOWN" / "Unknown" instead of null when a vendor (e.g. KIS for KR
  // equities) doesn't publish a sector. Treat those as absent so the
  // profile API fallback gets a chance before we fall through to em-dash.
  const sectorRaw = (signal?.sector || profile?.sector || "").trim();
  const sectorLine =
    sectorRaw && sectorRaw.toUpperCase() !== "UNKNOWN"
      ? sectorRaw
      : (profile?.sector &&
         profile.sector.toUpperCase() !== "UNKNOWN"
          ? profile.sector
          : "—");
  const displayName = signal?.name || profile?.name || ticker;
  const mcap = signal?.snapshot?.market_cap ?? profile?.market_cap ?? null;
  const week52Low = signal?.snapshot?.week52_low;
  const week52High = signal?.snapshot?.week52_high;
  const hasRange =
    week52Low != null && week52High != null && week52High > week52Low;

  // 52W position percent (guarded)
  const rangePos =
    hasRange && signal?.price != null
      ? Math.min(
          100,
          Math.max(
            0,
            ((signal.price - (week52Low as number)) /
              ((week52High as number) - (week52Low as number))) *
              100,
          ),
        )
      : null;

  const signalTone: "pos" | "neg" | "neu" =
    signalToken === "POSITIVE" ? "pos" : signalToken === "NEGATIVE" ? "neg" : "neu";
  const signalChipClass =
    signalToken === "POSITIVE"
      ? "pq-ink-pill pq-ink-pill--pos"
      : signalToken === "NEGATIVE"
        ? "pq-ink-pill pq-ink-pill--neg"
        : "pq-ink-pill pq-ink-pill--neu";

  return (
    <ErrorBoundary>
      <div className="space-y-10">
        {/* ── Back nav ── */}
        <button
          type="button"
          onClick={() => router.back()}
          className="inline-flex items-center gap-1.5 text-[11px] tracking-[0.14em] uppercase text-[rgba(245,240,232,0.5)] hover:text-[var(--pq-bronze)] transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </button>

        {/* ══════════════════════════════════════════════════
            Editorial Hero — 3-column "IC cover" layout
           ══════════════════════════════════════════════════ */}
        <section className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] rounded-[2px]">
          {/* Kicker strip */}
          <div className="flex items-center justify-between gap-3 px-6 md:px-8 pt-6 md:pt-7 flex-wrap">
            <div className="inline-flex items-center gap-3 text-[10px] tracking-[0.18em] uppercase text-[var(--pq-bronze)] font-medium">
              <span
                aria-hidden="true"
                className="inline-block w-6 h-[0.5px] bg-[var(--pq-bronze)] opacity-70"
              />
              <span>Pivoxquant · Equity Dossier</span>
              <span className="text-[rgba(245,240,232,0.35)]">·</span>
              <span className="text-[rgba(245,240,232,0.55)]">
                {new Date().toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                })}
              </span>
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
          </div>

          {/* Hero body */}
          <div className="px-6 md:px-8 pt-5 pb-6 md:pb-7">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8">
              {/* Identity column */}
              <div className="lg:col-span-5">
                <div className="pq-field-label">Ticker</div>
                <h1 className="pq-detail-ticker-display mt-2">
                  {ticker}
                </h1>
                <p className="mt-2 font-serif text-[15px] text-[rgba(245,240,232,0.68)] leading-snug">
                  {displayName}
                </p>
                <div className="mt-4 flex items-center gap-2 flex-wrap">
                  <span className="pq-sent-chip pq-sent-chip--neu">
                    {sectorLine}
                  </span>
                  <span className="pq-sent-chip pq-sent-chip--neu">
                    {krw ? "KRW · KOSPI" : "USD · US Listed"}
                  </span>
                  {signal?.snapshot?.industry && (
                    <span className="pq-sent-chip pq-sent-chip--neu">
                      {signal.snapshot.industry}
                    </span>
                  )}
                </div>
                <div className="mt-4">
                  <FieldLabel tone="muted">Market cap</FieldLabel>
                  <div className="mt-1 font-mono tabular-nums text-[18px] text-[var(--pq-ivory)]">
                    {fmtMcap(mcap, krw)}
                  </div>
                </div>
              </div>

              {/* Price column */}
              <div className="lg:col-span-4 lg:border-l lg:border-[rgba(245,240,232,0.08)] lg:pl-8">
                <FieldLabel>Current price</FieldLabel>
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
                    "mt-3 inline-flex items-center gap-1.5 tabular-nums font-mono text-[15px]",
                    pctColorClass(signal?.change_pct),
                  )}
                >
                  {signal?.change_pct == null ? (
                    <Minus className="h-4 w-4" />
                  ) : signal.change_pct >= 0 ? (
                    <TrendingUp className="h-4 w-4" />
                  ) : (
                    <TrendingDown className="h-4 w-4" />
                  )}
                  {fmtSignedPct(signal?.change_pct)}
                  <span className="ml-2 text-[10px] tracking-[0.18em] uppercase text-[rgba(245,240,232,0.4)] font-sans">
                    · 1D Δ
                  </span>
                </div>

                {/* 52W range rail */}
                {hasRange && (
                  <div className="mt-6">
                    <div className="flex items-center justify-between text-[11px] font-mono tabular-nums text-[rgba(245,240,232,0.55)]">
                      <span>{fmtPrice(week52Low, krw)}</span>
                      <span className="text-[9px] tracking-[0.18em] uppercase text-[var(--pq-bronze)]">
                        52W Range
                      </span>
                      <span>{fmtPrice(week52High, krw)}</span>
                    </div>
                    <div className="mt-2 h-[2px] bg-[rgba(245,240,232,0.08)] relative">
                      {rangePos != null && (
                        <div
                          className="absolute top-1/2 -translate-y-1/2 h-2 w-2 rounded-full bg-[var(--pq-bronze)] shadow-[0_0_8px_rgba(139,111,71,0.5)]"
                          style={{ left: `${rangePos}%`, transform: `translate(-50%, -50%)` }}
                        />
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Signal column */}
              <div className="lg:col-span-3 lg:border-l lg:border-[rgba(245,240,232,0.08)] lg:pl-8">
                <FieldLabel>Signal</FieldLabel>
                <div className="mt-2">
                  <span className={signalChipClass}>
                    {pillarToken(signalToken)}
                  </span>
                </div>
                <div
                  className={cn(
                    "mt-4 font-mono tabular-nums text-[40px] leading-none",
                    // KR convention (CEO directive 2026-04-26): POSITIVE → red, NEGATIVE → blue.
                    signalTone === "pos"
                      ? "text-[#D18888]"
                      : signalTone === "neg"
                        ? "text-[#7AA0C8]"
                        : "text-[var(--pq-ivory)]",
                  )}
                >
                  {signal?.score != null && Number.isFinite(signal.score)
                    ? signal.score
                    : "—"}
                  <span className="text-[13px] text-[rgba(245,240,232,0.4)] ml-1.5 font-sans tracking-[0.08em]">
                    / 100
                  </span>
                </div>
                <p className="mt-3 pq-detail-caption">
                  Composite score — 4-pillar observational blend.
                </p>
              </div>
            </div>
          </div>

          {/* Disclaimer docked at hero base */}
          <div className="px-6 md:px-8 pb-6 md:pb-7">
            <DisclaimerBanner type="signal" />
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            Chart — Price observation
           ══════════════════════════════════════════════════ */}
        <section>
          <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
            <div>
              <div className="pq-section-kicker">Price observation</div>
              <h2 className="pq-detail-h2 mt-1.5">Price history</h2>
            </div>
            <div
              role="tablist"
              aria-label="Chart period"
              className="flex gap-1 items-center"
            >
              {PERIODS.map((p) => (
                <button
                  key={p}
                  type="button"
                  role="tab"
                  aria-selected={period === p}
                  onClick={() => setPeriod(p)}
                  className={cn(
                    "px-3 py-1 text-[10px] tracking-[0.18em] uppercase transition-all",
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

          <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-5 md:p-6 rounded-[2px]">
            {loadingChart ? (
              <div className="h-64 pq-skeleton-dark" />
            ) : (
              <SparkChart
                data={chartRes?.data ?? []}
                currency={isKrw(signal, ticker) ? "KRW" : (signal?.currency ?? "USD")}
              />
            )}
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            Fundamentals — editorial StatRow table
           ══════════════════════════════════════════════════ */}
        <section>
          <div className="mb-5">
            <div className="pq-section-kicker">Fundamentals</div>
            <h2 className="pq-detail-h2 mt-1.5">Key ratios & valuation</h2>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Column 1 — Valuation */}
            <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-5 md:p-6 rounded-[2px]">
              <FieldLabel>Valuation · Earnings</FieldLabel>
              <div className="mt-3">
                <StatRow
                  label="P/E ratio"
                  value={
                    signal?.snapshot?.pe_ratio != null &&
                    Number.isFinite(signal.snapshot.pe_ratio)
                      ? Number(signal.snapshot.pe_ratio).toFixed(1)
                      : "—"
                  }
                />
                <StatRow
                  label="EPS (ttm)"
                  value={
                    signal?.snapshot?.eps != null &&
                    Number.isFinite(signal.snapshot.eps)
                      ? Number(signal.snapshot.eps).toFixed(2)
                      : "—"
                  }
                />
                <StatRow
                  label="Market cap"
                  value={fmtMcap(mcap, krw)}
                />
                <StatRow
                  label="Beta (vs S&P 500)"
                  value={
                    signal?.snapshot?.beta != null &&
                    Number.isFinite(signal.snapshot.beta)
                      ? Number(signal.snapshot.beta).toFixed(2)
                      : "—"
                  }
                />
              </div>
              {(signal?.snapshot?.pe_ratio == null &&
                signal?.snapshot?.eps == null) && (
                <p className="mt-4 pq-detail-empty-note">
                  Financials pending next filing — snapshot refreshes after EDGAR/DART publish.
                </p>
              )}
            </div>

            {/* Column 2 — Liquidity / Quality */}
            <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-5 md:p-6 rounded-[2px]">
              <FieldLabel>Liquidity · Quality</FieldLabel>
              <div className="mt-3">
                <StatRow
                  label="Avg volume (3mo)"
                  value={
                    signal?.snapshot?.avg_volume &&
                    Number.isFinite(signal.snapshot.avg_volume)
                      ? signal.snapshot.avg_volume.toLocaleString()
                      : "—"
                  }
                />
                <StatRow
                  label="Profit margin"
                  value={
                    signal?.snapshot?.profit_margin != null &&
                    Number.isFinite(signal.snapshot.profit_margin)
                      ? `${(Number(signal.snapshot.profit_margin) * 100).toFixed(1)}%`
                      : "—"
                  }
                  tone={
                    signal?.snapshot?.profit_margin != null
                      ? signal.snapshot.profit_margin > 0
                        ? "pos"
                        : "neg"
                      : "neu"
                  }
                />
                <StatRow
                  label="Revenue growth (YoY)"
                  value={
                    signal?.snapshot?.revenue_growth != null &&
                    Number.isFinite(signal.snapshot.revenue_growth)
                      ? `${(Number(signal.snapshot.revenue_growth) * 100).toFixed(1)}%`
                      : "—"
                  }
                  tone={
                    signal?.snapshot?.revenue_growth != null
                      ? signal.snapshot.revenue_growth > 0
                        ? "pos"
                        : "neg"
                      : "neu"
                  }
                />
                <StatRow
                  label="Debt / Equity"
                  value={
                    signal?.snapshot?.debt_equity != null &&
                    Number.isFinite(signal.snapshot.debt_equity)
                      ? Number(signal.snapshot.debt_equity).toFixed(2)
                      : "—"
                  }
                />
              </div>
            </div>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            Quant breakdown — 4 pillars
           ══════════════════════════════════════════════════ */}
        <section>
          <div className="mb-5">
            <div className="pq-section-kicker">Quant breakdown</div>
            <h2 className="pq-detail-h2 mt-1.5">Four-pillar composite</h2>
          </div>
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
            <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-8 rounded-[2px] text-center">
              <p className="pq-detail-empty-note">
                Pillar breakdown pending — composite calibration in progress.
              </p>
            </div>
          )}
        </section>

        {/* ══════════════════════════════════════════════════
            News — grouped by day with sentiment chips
           ══════════════════════════════════════════════════ */}
        <section>
          <div className="mb-5">
            <div className="pq-section-kicker">Recent coverage</div>
            <h2 className="pq-detail-h2 mt-1.5">News feed</h2>
          </div>
          {loadingNews ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="h-16 rounded-[2px] pq-skeleton-dark"
                />
              ))}
            </div>
          ) : !newsGroups.length ? (
            <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-8 rounded-[2px] text-center">
              <p className="pq-detail-empty-note">
                No headlines observed in the last 14 days — re-checking every 2 minutes.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {newsGroups.map((group) => (
                <div key={group.label}>
                  <div className="pq-news-date-header">{group.label}</div>
                  <ul className="space-y-2">
                    {group.items.map((n, i) => {
                      const sent = classifyNewsSentiment(n.title);
                      const chipClass =
                        sent === "pos"
                          ? "pq-sent-chip pq-sent-chip--pos"
                          : sent === "neg"
                            ? "pq-sent-chip pq-sent-chip--neg"
                            : "pq-sent-chip pq-sent-chip--neu";
                      const chipLabel =
                        sent === "pos" ? "Positive" : sent === "neg" ? "Negative" : "Neutral";
                      return (
                        <li key={`${group.label}-${i}`}>
                          <a
                            href={n.link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="group block bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] p-4 rounded-[2px] hover:border-[var(--pq-bronze)] hover:bg-[rgba(139,111,71,0.04)] transition-all"
                          >
                            <div className="flex items-start justify-between gap-4">
                              <div className="min-w-0 flex-1">
                                <p className="font-serif text-[15px] leading-snug text-[var(--pq-ivory)] group-hover:text-[var(--pq-bronze-light)] transition-colors line-clamp-2">
                                  {n.title}
                                </p>
                                <div className="mt-2 flex items-center gap-2 flex-wrap">
                                  <span className={chipClass}>{chipLabel}</span>
                                  <span className="text-[11px] text-[rgba(245,240,232,0.45)] font-mono tracking-tight">
                                    {n.source}
                                  </span>
                                  <span className="text-[11px] text-[rgba(245,240,232,0.3)]">·</span>
                                  <span className="text-[11px] text-[rgba(245,240,232,0.45)] font-mono tracking-tight">
                                    {n.published}
                                  </span>
                                </div>
                              </div>
                              <ExternalLink className="h-3.5 w-3.5 shrink-0 mt-1 text-[rgba(245,240,232,0.3)] group-hover:text-[var(--pq-bronze)]" />
                            </div>
                          </a>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* ══════════════════════════════════════════════════
            Insider filings · US only
           ══════════════════════════════════════════════════ */}
        {insiderEligible && (
          <section>
            <div className="mb-5 flex items-center gap-3">
              <Eye className="h-4 w-4 text-[var(--pq-bronze)]" strokeWidth={1.4} />
              <div>
                <div className="pq-section-kicker">Form 4 · 90 days</div>
                <h2 className="pq-detail-h2 mt-1.5">Insider activity</h2>
              </div>
            </div>
            <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] rounded-[2px] overflow-hidden">
              {insiderData.length > 0 ? (
                <ul className="divide-y divide-[rgba(245,240,232,0.06)]">
                  {insiderData.slice(0, 6).map((f, i) => {
                    const acquired = f.acquired === true;
                    const shares = Number.isFinite(f.shares as number)
                      ? (f.shares as number)
                      : 0;
                    return (
                      <li
                        key={i}
                        className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-[rgba(139,111,71,0.03)] transition-colors"
                      >
                        <div className="min-w-0 flex-1">
                          <span className="text-[13.5px] text-[var(--pq-ivory)] font-serif">
                            {f.insider || "—"}
                          </span>
                          {f.relationship && (
                            <span className="ml-2.5 pq-field-label">
                              {f.relationship}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 shrink-0">
                          <span
                            className={cn(
                              "pq-sent-chip",
                              acquired ? "pq-sent-chip--pos" : "pq-sent-chip--neg",
                            )}
                          >
                            {acquired ? "Acquired" : "Disposed"}
                          </span>
                          <span className="font-mono tabular-nums text-[12px] text-[var(--pq-ivory)]">
                            {shares.toLocaleString()}
                          </span>
                          <span className="text-[10px] tracking-[0.14em] uppercase text-[rgba(245,240,232,0.45)]">
                            {formatRelative(f.transaction_date)}
                          </span>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <div className="p-6 text-center">
                  <p className="pq-detail-empty-note">
                    No public Form 4 filings observed in the last 90 days.
                  </p>
                </div>
              )}
            </div>
          </section>
        )}

        {/* ══════════════════════════════════════════════════
            AI Analysis — on-demand SWOT (POSITIVE/NEGATIVE/NEUTRAL framing)
           ══════════════════════════════════════════════════ */}
        <section>
          <div className="mb-5 flex items-center gap-3">
            <Sparkles className="h-4 w-4 text-[var(--pq-bronze)]" strokeWidth={1.4} />
            <div>
              <div className="pq-section-kicker">AI assistant · observation</div>
              <h2 className="pq-detail-h2 mt-1.5">AI analysis</h2>
            </div>
          </div>
          <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] rounded-[2px] p-5">
            {swot && (swot.swot_kr || swot.swot) ? (
              <div className="space-y-4">
                {swot.swot_kr ? (
                  <div>
                    <FieldLabel>한국어</FieldLabel>
                    <p className="mt-2 whitespace-pre-line text-[14px] leading-[1.7] text-[var(--pq-ivory)]/85">
                      {swot.swot_kr}
                    </p>
                  </div>
                ) : null}
                {swot.swot ? (
                  <div className="pt-3 border-t border-[rgba(245,240,232,0.06)]">
                    <FieldLabel>English</FieldLabel>
                    <p className="mt-2 whitespace-pre-line text-[14px] leading-[1.7] text-[var(--pq-ivory)]/75">
                      {swot.swot}
                    </p>
                  </div>
                ) : null}
                <div className="pt-3 mt-3 border-t border-[rgba(245,240,232,0.06)]">
                  <DisclaimerBanner type="signal" />
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-start gap-3">
                <p className="pq-detail-caption">
                  AI analysis is being prepared. Trigger an observation summary
                  for {ticker ?? "this ticker"} below.
                </p>
                <button
                  type="button"
                  onClick={handleGenerateSwot}
                  disabled={swotLoading || !ticker}
                  className="inline-flex items-center gap-2 px-4 py-2 text-[11px] uppercase tracking-[0.18em] border border-[var(--pq-bronze)] text-[var(--pq-bronze)] hover:bg-[rgba(184,149,106,0.08)] hover:text-[var(--pq-bronze-light)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors rounded-[2px]"
                >
                  <Sparkles className="h-3 w-3" strokeWidth={1.6} />
                  {swotLoading ? "Generating…" : "Generate AI summary"}
                </button>
                {swotError ? (
                  <p className="text-[11px] text-[rgba(245,240,232,0.5)]">
                    Unable to generate right now ({swotError}). Try again later.
                  </p>
                ) : null}
              </div>
            )}
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            Earnings calendar — next + last quarters
           ══════════════════════════════════════════════════ */}
        <section>
          <div className="mb-5 flex items-center gap-3">
            <CalendarDays className="h-4 w-4 text-[var(--pq-bronze)]" strokeWidth={1.4} />
            <div>
              <div className="pq-section-kicker">Earnings · forward window</div>
              <h2 className="pq-detail-h2 mt-1.5">Earnings calendar</h2>
            </div>
          </div>
          <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] rounded-[2px] p-5">
            {earningsForTicker.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="text-left border-b border-[rgba(245,240,232,0.08)]">
                      <th className="pb-2 font-mono uppercase tracking-[0.16em] text-[10px] text-[rgba(245,240,232,0.45)]">
                        Date
                      </th>
                      <th className="pb-2 font-mono uppercase tracking-[0.16em] text-[10px] text-[rgba(245,240,232,0.45)] text-right">
                        EPS estimate
                      </th>
                      <th className="pb-2 font-mono uppercase tracking-[0.16em] text-[10px] text-[rgba(245,240,232,0.45)] text-right">
                        EPS actual
                      </th>
                      <th className="pb-2 font-mono uppercase tracking-[0.16em] text-[10px] text-[rgba(245,240,232,0.45)] text-right">
                        Revenue est.
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {earningsForTicker.map((e, i) => (
                      <tr
                        key={`${e.date ?? "na"}-${i}`}
                        className="border-b border-[rgba(245,240,232,0.04)] last:border-0"
                      >
                        <td className="py-2.5 text-[var(--pq-ivory)]/85">
                          {e.date
                            ? new Date(e.date).toLocaleDateString("en-US", {
                                year: "numeric",
                                month: "short",
                                day: "numeric",
                              })
                            : "—"}
                        </td>
                        <td className="py-2.5 text-right font-mono tabular-nums text-[var(--pq-ivory)]/75">
                          {e.eps_estimate != null
                            ? e.eps_estimate.toFixed(2)
                            : "—"}
                        </td>
                        <td className="py-2.5 text-right font-mono tabular-nums text-[var(--pq-ivory)]">
                          {e.eps_actual != null
                            ? e.eps_actual.toFixed(2)
                            : "—"}
                        </td>
                        <td className="py-2.5 text-right font-mono tabular-nums text-[var(--pq-ivory)]/75">
                          {e.revenue_estimate != null
                            ? `$${(e.revenue_estimate / 1e9).toFixed(2)}B`
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="pq-detail-caption">
                Next earnings date not available for {ticker ?? "this ticker"} in the
                forward 30-day window.
              </p>
            )}
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            Institutional ownership — placeholder (backend endpoint pending)
           ══════════════════════════════════════════════════ */}
        <section>
          <div className="mb-5 flex items-center gap-3">
            <Building2 className="h-4 w-4 text-[var(--pq-bronze)]" strokeWidth={1.4} />
            <div>
              <div className="pq-section-kicker">Institutional · 13F</div>
              <h2 className="pq-detail-h2 mt-1.5">Institutional ownership</h2>
            </div>
          </div>
          <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] rounded-[2px] p-5">
            <p className="pq-detail-caption">
              13F holder breakdown is not yet wired. Surface scheduled once the
              SEC EDGAR holdings feed lands in /api/alt-data.
            </p>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            Companion CTA — context handoff
           ══════════════════════════════════════════════════ */}
        <section>
          <Link
            href={`/companion?ticker=${encodeURIComponent(ticker ?? "")}`}
            className="block bg-[rgba(184,149,106,0.04)] border border-[var(--pq-bronze)]/40 rounded-[2px] p-5 hover:bg-[rgba(184,149,106,0.08)] hover:border-[var(--pq-bronze)] transition-all group"
          >
            <div className="flex items-start gap-4">
              <MessageSquare
                className="h-5 w-5 text-[var(--pq-bronze)] mt-0.5"
                strokeWidth={1.4}
              />
              <div className="flex-1">
                <FieldLabel>AI Assistant · context handoff</FieldLabel>
                <div className="mt-1.5 font-serif text-[18px] text-[var(--pq-ivory)] group-hover:text-[var(--pq-bronze-light)] transition-colors">
                  Ask Companion about {ticker ?? "this ticker"}
                </div>
                <p className="mt-2 pq-detail-caption">
                  Open a Companion thread pre-seeded with the current snapshot —
                  fundamentals, signal label, and recent coverage.
                </p>
              </div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-[var(--pq-bronze)] opacity-60 group-hover:opacity-100 transition-opacity inline-flex items-center gap-1.5 self-center">
                Open
                <ExternalLink className="h-3 w-3" />
              </div>
            </div>
          </Link>
        </section>

        {/* ══════════════════════════════════════════════════
            Related observations — Artifact links
           ══════════════════════════════════════════════════ */}
        <section>
          <div className="mb-5 flex items-center gap-3">
            <FileText className="h-4 w-4 text-[var(--pq-bronze)]" strokeWidth={1.4} />
            <div>
              <div className="pq-section-kicker">Research library</div>
              <h2 className="pq-detail-h2 mt-1.5">Related observations</h2>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              {
                slug: "weekly_memo",
                name: "Weekly Memo",
                desc: "Portfolio-wide context, authored every Sunday.",
                kind: "PDF · 2 pages",
              },
              {
                slug: "earnings_prebrief",
                name: "Earnings Pre-Brief",
                desc: "Ten-day forward earnings observation playbook.",
                kind: "PDF · 4 pages",
              },
              {
                slug: "dd_checklist",
                name: "DD Checklist",
                desc: "Structured due-diligence reference and markers.",
                kind: "PDF · 3 pages",
              },
            ].map((r) => (
              <a
                key={r.slug}
                href={`/samples/${r.slug}.pdf`}
                target="_blank"
                rel="noopener noreferrer"
                className="block bg-[rgba(255,255,255,0.02)] border border-[rgba(245,240,232,0.08)] rounded-[2px] p-5 hover:border-[var(--pq-bronze)] hover:bg-[rgba(139,111,71,0.04)] transition-all group"
              >
                <FieldLabel>{r.kind}</FieldLabel>
                <div className="mt-2 font-serif text-[17px] text-[var(--pq-ivory)] group-hover:text-[var(--pq-bronze-light)] transition-colors">
                  {r.name}
                </div>
                <p className="mt-2 pq-detail-caption">{r.desc}</p>
                <div className="mt-4 text-[10px] uppercase tracking-[0.18em] text-[var(--pq-bronze)] opacity-60 group-hover:opacity-100 transition-opacity inline-flex items-center gap-1.5">
                  Open PDF
                  <ExternalLink className="h-3 w-3" />
                </div>
              </a>
            ))}
          </div>
        </section>

        {/* ── Footer fleuron ── */}
        <footer className="pt-6 mt-4 border-t border-[rgba(245,240,232,0.06)] text-center">
          <p className="pq-detail-caption">
            PivoxQuant · Observational research only · Not investment advice
          </p>
        </footer>
      </div>
    </ErrorBoundary>
  );
}
