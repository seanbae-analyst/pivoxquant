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
import { apiFetch, ApiError } from "@/lib/api";
import {
  fmtUsd,
  fmtKrw,
  fmtPct,
  pctColorClass,
  tickerToName,
  normalizeTicker,
} from "@/lib/format";
import { liveRefresh } from "@/lib/market-hours";
import { PriceWithTimestamp } from "@/components/ui/price-with-timestamp";
import { Skeleton } from "@/components/ui/loading-skeleton";
import { cn } from "@/lib/utils";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { AiContentBadge } from "@/components/ui/ai-content-badge";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  InteractiveLineChart,
  type ChartMarker,
} from "@/components/charts/interactive-line-chart";
import {
  FieldLabel,
  StatRow,
  FootSignature,
  RuledKicker,
  EditorialHead,
} from "@/components/ui/editorial";
import {
  useWatchlist,
  usePortfolioPositions,
  useArtifacts,
  useSignals,
} from "@/lib/hooks";
import { getArtifactViewerUrl } from "@/lib/artifact-viewer";
import { WEEKLY_MEMO_EMPTY_LINE } from "@/lib/cfo/memo-schedule";
import type { Position } from "@/lib/types";
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

/**
 * Split a formatted market cap into { number, suffix } so the unit modifier
 * (조 / 억 / T / B / M) can render visually subordinate to the digits
 * (audit FINDING-035). The suffix is the trailing run of non-digit, non-dot,
 * non-comma characters; "$" prefixes stay with the number.
 */
function splitMcap(formatted: string): { num: string; suffix: string } {
  if (formatted === "—") return { num: "—", suffix: "" };
  const m = formatted.match(/^([$]?[\d.,]+)([^\d.,]*)$/);
  if (!m) return { num: formatted, suffix: "" };
  return { num: m[1], suffix: m[2] };
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
  markers,
}: {
  data: ChartPoint[];
  currency?: "USD" | "KRW";
  markers?: ChartMarker[];
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
      markers={markers}
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
      ? "bg-[var(--up)]"
      : token === "NEGATIVE"
        ? "bg-[var(--down)]"
        : "bg-[var(--pq-bronze)]";
  const textColor =
    token === "POSITIVE"
      ? "text-[var(--up)]"
      : token === "NEGATIVE"
        ? "text-[var(--down)]"
        : "text-[var(--pq-ivory-mid)]";
  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-[2px] pq-ink-card-interactive">
      <div className="flex items-center justify-between">
        <FieldLabel>{label}</FieldLabel>
        <span
          className={cn(
            "text-pq-mono-tiny tracking-[0.18em] uppercase font-medium",
            textColor,
          )}
        >
          {token}
        </span>
      </div>
      <div className={cn("pq-ink-num mt-3 leading-none", textColor)}>
        {safe.toFixed(0)}
        <span className="text-xs text-[var(--pq-ivory-faint)] ml-1.5">/ 100</span>
      </div>
      <div className="mt-3 h-[2px] bg-[var(--pq-ivory-line)] overflow-hidden">
        <div
          className={cn("h-full transition-all", barColor)}
          style={{ width: `${safe}%` }}
        />
      </div>
      <p className="mt-3 pq-detail-body text-pq-body-sm">
        {observation}
      </p>
    </div>
  );
}

/* ── AccessDeniedScreen ──
 * §101 회피 (2026-04-29): 보유/관심 종목이 아닌 임의 ticker 분석 차단.
 * 사용자는 [관심 종목 추가] 1-click으로 즉시 해제 가능.
 */
function AccessDeniedScreen({
  ticker,
  onAddedToWatchlist,
}: {
  ticker: string;
  onAddedToWatchlist: () => void;
}) {
  const router = useRouter();
  const [adding, setAdding] = useState(false);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const handleAdd = useCallback(async () => {
    setAdding(true);
    setErrMsg(null);
    try {
      await apiFetch(WATCHLIST, {
        method: "POST",
        body: JSON.stringify({ ticker }),
      });
      toast.success("Added to watchlist");
      onAddedToWatchlist();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed";
      setErrMsg(msg);
      toast.error(msg);
    } finally {
      setAdding(false);
    }
  }, [ticker, onAddedToWatchlist]);

  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-10 md:p-12 rounded-[2px] text-center max-w-2xl mx-auto">
      <Eye className="mx-auto h-8 w-8 text-[var(--pq-bronze)]" strokeWidth={1.2} />
      <p className="mt-4 font-serif text-xl text-[var(--pq-ivory)]">
        분석은 보유/관심 종목 한정입니다.
      </p>
      <p className="mt-3 text-pq-body-sm leading-relaxed text-[var(--pq-ivory-mid)]">
        {/* Name-first (FINDING-026): "Apple (AAPL)" not a naked code. */}
        <span className="text-[var(--pq-bronze)]">
          {(() => {
            const nm = tickerToName(ticker);
            // Wave G-5 G5-05 (2026-05-18) + Wave 2 sweep (2026-05-19):
            // strip .KS/.KQ via lib normalizeTicker (single source of truth).
            const display = normalizeTicker(ticker);
            return nm ? `${nm} (${display})` : display;
          })()}
        </span>
        {" "}분석은 관심종목 또는 보유 포지션으로 등록한 후 이용 가능합니다.
        한 번 추가하면 즉시 분석을 볼 수 있습니다.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <button
          type="button"
          onClick={handleAdd}
          disabled={adding}
          className="pq-ink-btn-bronze inline-flex items-center gap-1.5 disabled:opacity-40"
        >
          <Plus className="h-3.5 w-3.5" />
          {adding ? "Adding…" : "관심 종목 추가"}
        </button>
        <button
          type="button"
          onClick={() => router.back()}
          className="pq-ink-btn-ghost inline-flex items-center gap-1.5"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </button>
      </div>
      {errMsg ? (
        <p className="mt-4 text-pq-mono-xs text-[rgba(209,136,136,0.8)]">{errMsg}</p>
      ) : null}
      <p className="mt-6 text-pq-eyebrow uppercase tracking-[0.22em] text-[var(--pq-ivory-faint)]">
        Observational research only · Not investment advice
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
  // Wave G-5 P2 G5-05 (2026-05-18) + Wave 2 sweep (2026-05-19):
  // KR ticker UI strip — feedback_ticker_display 룰. API call 은 raw
  // ticker 유지, SYMBOL sub-label 등 사용자-노출 surface 만 ".KS"/".KQ"
  // suffix 제거. lib/format.ts normalizeTicker() 를 단일 source 로 사용.
  // "005930.KS" → "005930".
  const displayTicker = normalizeTicker(ticker);
  const [period, setPeriod] = useState<Period>("3M");

  const { data: signal, isLoading: loadingSignal } = useSWR<SignalDetail>(
    ticker ? API.signals.one(ticker) : null,
    fetcher,
    {
      refreshInterval: () => liveRefresh(5_000, 30_000),
      // Bug #3 (HANDOVER v22): `refreshInterval` already keeps detail-page
      // signals fresh; focus revalidate triggered duplicate fetches when
      // users switched between detail and list views.
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      // Performance audit (2026-05-09): bumped from 2_000 to 5_000 — the
      // 2s window was the outlier among SWR hooks (others use 30s/60s)
      // and allowed a narrow band of concurrent fetches when two tabs of
      // the same ticker were open. 5s matches the matching live-tick
      // refreshInterval below for consistent behaviour during market hours.
      dedupingInterval: 5_000,
      errorRetryCount: 2,
      errorRetryInterval: 5_000,
    },
  );
  const { data: chartRes, isLoading: loadingChart } = useSWR<ChartResponse>(
    ticker ? `${API.market.chart(ticker)}?period=${PERIOD_MAP[period]}` : null,
    fetcher,
    {
      refreshInterval: () => liveRefresh(15_000, 120_000),
      // Bug #3 (HANDOVER v22): same rationale — chart polls every 15-120s
      // already. No SSE push for OHLC frames.
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 5_000,
      shouldRetryOnError: false,
    },
  );
  // Observation history for THIS ticker, overlaid on the price chart as
  // tone-coloured markers. CEO 2026-05-20 "chart에 왜 없어 기록들이" — the
  // chart previously rendered the price line only and had no notion of
  // signal markers. We reuse the existing `/api/signals` feed (no new
  // endpoint, no SWR-key change) scoped to this symbol with the "all"
  // window so older observations within the chart range still surface.
  const { data: signalsRes } = useSignals(
    ticker ? { symbol: ticker, window: "all" } : {},
  );
  const chartMarkers = useMemo<ChartMarker[]>(() => {
    const all = signalsRes?.signals ?? [];
    const norm = normalizeTicker(ticker);
    return all
      .filter((s) => {
        if (!s.observed_at) return false;
        // Server may already scope by `symbol`, but defend client-side in
        // case the backend ignores the param (hooks.ts documents this).
        return (
          normalizeTicker(s.ticker) === norm ||
          (s.ticker ?? "").toUpperCase() === (ticker ?? "").toUpperCase()
        );
      })
      .map((s) => {
        const raw = (s.label ?? s.signal ?? "").toString().toUpperCase();
        const tone: ChartMarker["tone"] =
          raw === "POSITIVE"
            ? "positive"
            : raw === "NEGATIVE"
              ? "negative"
              : "neutral";
        const display =
          tone === "positive" ? "긍정" : tone === "negative" ? "부정" : "중립";
        const strength =
          typeof s.strength === "number"
            ? s.strength
            : typeof s.score === "number"
              ? s.score / 100
              : null;
        const clock = s.observed_at
          ? new Date(s.observed_at).toLocaleString("ko-KR", {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })
          : "";
        const parts = [
          `관측 · ${display}`,
          strength != null ? `강도 ${strength.toFixed(2)}` : null,
          clock || null,
        ].filter(Boolean);
        return {
          date: s.observed_at as string,
          tone,
          strength: strength ?? undefined,
          label: parts.join(" · "),
        };
      });
  }, [signalsRes, ticker]);

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
      // 2026-05-15 (bug-hunter Wave 5 P1 #3): /api/ai/swot returns
      // 503 when the upstream LLM quota is exhausted or the service
      // is restarting — same root cause as the /api/ai/coaching 503
      // closed by PR #387. Mirror that fix's graceful copy here so
      // the /detail page doesn't surface "Failed to generate SWOT"
      // (alarming) on the launch surface when the actual fact is
      // "service busy, try again."
      let msg: string;
      if (e instanceof ApiError && e.status === 503) {
        msg = "AI service is temporarily busy — please try again in a moment.";
      } else if (e instanceof ApiError && e.status === 429) {
        msg = "Too many requests right now. Please wait a moment and retry.";
      } else if (e instanceof Error) {
        msg = e.message;
      } else {
        msg = "Request failed";
      }
      setSwotError(msg);
    } finally {
      setSwotLoading(false);
    }
  }, [ticker]);

  const { data: watchlistData, mutate: refreshWatchlist, isLoading: watchlistLoading } = useWatchlist();
  const watchlistEntry = watchlistData?.watchlist?.find((w) => w.ticker === ticker);
  const inWatchlist = Boolean(watchlistEntry);

  /* §101 회피 (2026-04-29): 보유/관심 종목 화이트리스트 검사.
   * 보유 포지션 또는 관심종목에 등록된 ticker만 분석 페이지 진입 허용.
   * AccessDeniedScreen에서 1-click으로 watchlist 추가 → 즉시 해제. */
  const positionsSwr = usePortfolioPositions<{ positions?: Position[] }>();
  // 2026-05-02: pull the user's 3 most recent artifacts so the
  // "Related observations" section shows real artefacts they actually
  // received instead of three hardcoded /samples/*.pdf decoys that had
  // nothing to do with the current ticker. Backend `list` endpoint
  // doesn't filter by ticker yet — we'd rather show real cross-ticker
  // research than fake same-ticker samples.
  const artifactsSwr = useArtifacts({ limit: 3 });
  const allowlistLoading = watchlistLoading || positionsSwr.isLoading;
  const inPortfolio = useMemo(() => {
    const upper = (ticker || "").toUpperCase();
    // 2026-05-02: backend serializer emits the column as `symbol` (see
    // services/portfolio_serializer.py — frontend-shape rename). The
    // earlier `p.ticker` read silently returned undefined for every
    // row, so §101 access guard rejected every owned ticker. v19
    // f18e2b7 patched the same shape mismatch in /discover; this is
    // the second site. Read both keys so future renames degrade
    // gracefully.
    return (positionsSwr.data?.positions ?? []).some(
      (p) => {
        const t = (p as { ticker?: string; symbol?: string });
        return ((t.ticker || t.symbol || "")).toUpperCase() === upper;
      },
    );
  }, [positionsSwr.data, ticker]);
  const isAllowed = inWatchlist || inPortfolio;

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
        <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-12 rounded-[2px] text-center">
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

  /* §101 화이트리스트 가드 — allowlist 로딩 후에 검증.
   * 로딩 중에는 잠시 spinner-equivalent 빈 prelude를 표시(깜박임 방지). */
  if (!allowlistLoading && !isAllowed) {
    return (
      <ErrorBoundary>
        <div className="space-y-6">
          <button
            type="button"
            onClick={() => router.back()}
            className="inline-flex items-center gap-1.5 text-pq-mono-xs tracking-[0.14em] uppercase text-[var(--pq-ivory-dim)] hover:text-[var(--pq-bronze)] transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back
          </button>
          <AccessDeniedScreen
            ticker={ticker}
            onAddedToWatchlist={() => refreshWatchlist()}
          />
        </div>
      </ErrorBoundary>
    );
  }

  if (!loadingSignal && !loadingProfile && !signal && !profile) {
    return (
      <ErrorBoundary>
        <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-12 rounded-[2px] text-center">
          <SearchX className="mx-auto h-8 w-8 text-[var(--pq-bronze)]" strokeWidth={1.2} />
          <p className="mt-4 font-serif text-xl text-[var(--pq-ivory)]">
            No data for &ldquo;{displayTicker}&rdquo;
          </p>
          <p className="mt-2 text-sm text-[var(--pq-ivory-dim)]">
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
          className="inline-flex min-h-[44px] items-center gap-1.5 -mx-2 px-2 py-2 text-pq-mono-xs tracking-[0.14em] uppercase text-[var(--pq-ivory-dim)] hover:text-[var(--pq-bronze)] transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </button>

        {/* ══════════════════════════════════════════════════
            Editorial Hero — 3-column "IC cover" layout
           ══════════════════════════════════════════════════ */}
        <section className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] rounded-[2px]">
          {/* Kicker strip */}
          <div className="flex items-center justify-between gap-3 px-6 md:px-8 pt-6 md:pt-7 flex-wrap">
            <div className="inline-flex items-center gap-3 text-pq-eyebrow-sm tracking-[0.18em] uppercase text-[var(--pq-bronze)] font-medium">
              <span
                aria-hidden="true"
                className="inline-block w-6 h-[0.5px] bg-[var(--pq-bronze)] opacity-70"
              />
              <span>Pivoxquant · Equity Dossier</span>
              <span className="text-[var(--pq-ivory-dim)]">·</span>
              <span className="text-[var(--pq-ivory-dim)]">
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
                <div className="pq-field-label">Symbol</div>
                <h1 className="pq-detail-ticker-display mt-2">
                  {displayName}
                </h1>
                <p className="mt-2 font-mono tabular-nums text-pq-body-sm text-[var(--pq-ivory-mid)] leading-snug">
                  {displayTicker}
                </p>
                {/* Chips (FINDING-027): sector and industry were 3 separate
                    redundant chips (TECHNOLOGY · KRW · KOSPI · CONSUMER
                    ELECTRONICS). Render sector › industry as ONE hierarchical
                    chip; the listing/currency stays its own chip. */}
                <div className="mt-4 flex items-center gap-2 flex-wrap">
                  {(() => {
                    const sec =
                      sectorLine && sectorLine !== "—" ? sectorLine : "";
                    const ind = (signal?.snapshot?.industry || "").trim();
                    const taxon =
                      sec && ind && ind.toUpperCase() !== sec.toUpperCase()
                        ? `${sec} › ${ind}`
                        : sec || ind;
                    return taxon ? (
                      <span className="pq-sent-chip pq-sent-chip--neu">
                        {taxon}
                      </span>
                    ) : null;
                  })()}
                  <span className="pq-sent-chip pq-sent-chip--neu">
                    {krw ? "KRW · KOSPI" : "USD · US Listed"}
                  </span>
                </div>
                <div className="mt-4">
                  <FieldLabel tone="muted">Market cap</FieldLabel>
                  {/* FINDING-035: unit suffix (조/억/T/B) subordinate to digits. */}
                  <div className="pq-ink-num mt-1 text-pq-h5">
                    {(() => {
                      const { num, suffix } = splitMcap(fmtMcap(mcap, krw));
                      return (
                        <>
                          <span className="tabular-nums">{num}</span>
                          {suffix && (
                            <span
                              className="ml-0.5 text-pq-body-sm align-baseline text-[var(--pq-muted)]"
                              style={{ fontWeight: 400 }}
                            >
                              {suffix}
                            </span>
                          )}
                        </>
                      );
                    })()}
                  </div>
                </div>
              </div>

              {/* Price column
                  bug-hunter Bug #9: SWR returns `signal=undefined` while
                  the first request is in flight. PriceWithTimestamp falls
                  back to "—" on undefined → users saw an em-dash for ~1s
                  before the real price flashed in. Show a skeleton during
                  the initial load and only render the price once SWR has
                  resolved (cached or fresh). The em-dash is preserved for
                  resolved-but-empty states (price genuinely null). */}
              <div className="lg:col-span-4 lg:border-l lg:border-[var(--pq-ivory-line)] lg:pl-8">
                <FieldLabel>Current price</FieldLabel>
                <div className="mt-2">
                  {loadingSignal && !signal ? (
                    <div className="flex items-center gap-3">
                      <Skeleton className="h-7 w-32" />
                      <Skeleton className="h-3 w-16" />
                    </div>
                  ) : (
                    <PriceWithTimestamp
                      price={signal?.price}
                      observedAt={signal?.observed_at}
                      currency={krw ? "KRW" : "USD"}
                      size="lg"
                    />
                  )}
                </div>
                <div
                  className={cn(
                    "mt-3 inline-flex items-center gap-1.5 tabular-nums font-mono text-pq-lead",
                    pctColorClass(signal?.change_pct),
                  )}
                >
                  {loadingSignal && !signal ? (
                    <Skeleton className="h-4 w-20" />
                  ) : (
                    <>
                      {signal?.change_pct == null ? (
                        <Minus className="h-4 w-4" />
                      ) : signal.change_pct >= 0 ? (
                        <TrendingUp className="h-4 w-4" />
                      ) : (
                        <TrendingDown className="h-4 w-4" />
                      )}
                      {fmtPct(signal?.change_pct)}
                      <span className="ml-2 text-pq-eyebrow-sm tracking-[0.18em] uppercase text-[var(--pq-ivory-faint)] font-sans">
                        · 1D Δ
                      </span>
                    </>
                  )}
                </div>

                {/* 52W range rail */}
                {hasRange && (
                  <div className="mt-6">
                    <div className="flex items-center justify-between text-pq-mono-xs font-mono tabular-nums text-[var(--pq-ivory-dim)]">
                      <span>{fmtPrice(week52Low, krw)}</span>
                      <span className="text-pq-mono-tiny tracking-[0.18em] uppercase text-[var(--pq-bronze)]">
                        52W Range
                      </span>
                      <span>{fmtPrice(week52High, krw)}</span>
                    </div>
                    <div className="mt-2 h-[2px] bg-[var(--pq-ivory-line)] relative">
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
              <div className="lg:col-span-3 lg:border-l lg:border-[var(--pq-ivory-line)] lg:pl-8">
                <FieldLabel>Signal</FieldLabel>
                <div className="mt-2">
                  <span className={signalChipClass}>
                    {pillarToken(signalToken)}
                  </span>
                </div>
                <div
                  className={cn(
                    "pq-detail-stat-value mt-4",
                    // KR convention (CEO directive 2026-04-26): POSITIVE → red, NEGATIVE → blue.
                    signalTone === "pos"
                      ? "text-[var(--up)]"
                      : signalTone === "neg"
                        ? "text-[var(--down)]"
                        : "text-[var(--pq-ivory)]",
                  )}
                >
                  {signal?.score != null && Number.isFinite(signal.score)
                    ? signal.score
                    : "—"}
                  <span className="text-pq-body-sm text-[var(--pq-ivory-faint)] ml-1.5 font-sans tracking-[0.08em]">
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
              <RuledKicker>Price observation</RuledKicker>
              <EditorialHead size={22} as="h2" className="mt-1.5 italic">
                Price history
              </EditorialHead>
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
                    "px-3 py-1 text-pq-eyebrow-sm tracking-[0.18em] uppercase transition-all",
                    period === p
                      ? "text-[var(--pq-ivory)] border-b border-[var(--pq-bronze)]"
                      : "text-[var(--pq-ivory-faint)] hover:text-[var(--pq-bronze)]",
                  )}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 md:p-6 rounded-[2px]">
            {loadingChart ? (
              <div className="h-64 pq-skeleton-dark" />
            ) : (
              <SparkChart
                data={chartRes?.data ?? []}
                currency={isKrw(signal, ticker) ? "KRW" : (signal?.currency ?? "USD")}
                markers={chartMarkers}
              />
            )}
          </div>
          {/* Marker legend — only when this ticker has observation history
              within the visible window. Legal: observation framing only. */}
          {!loadingChart && chartMarkers.length > 0 && (
            <div className="mt-3 flex items-center gap-4 flex-wrap font-mono text-pq-eyebrow-sm uppercase tracking-[0.16em] text-[var(--pq-ivory-faint)]">
              <span>관측 기록 {chartMarkers.length}건</span>
              <span className="inline-flex items-center gap-1.5">
                <span
                  aria-hidden
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: 999,
                    background: "var(--pq-positive, #B8956A)",
                  }}
                />
                긍정
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span
                  aria-hidden
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: 999,
                    background: "var(--pq-negative, #D18888)",
                  }}
                />
                부정
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span
                  aria-hidden
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: 999,
                    background: "rgba(245,240,232,0.5)",
                  }}
                />
                중립
              </span>
            </div>
          )}
        </section>

        {/* ══════════════════════════════════════════════════
            Fundamentals — editorial StatRow table
           ══════════════════════════════════════════════════ */}
        <section>
          <div className="mb-5">
            <div>
              <RuledKicker>Fundamentals</RuledKicker>
              <EditorialHead size={22} as="h2" className="mt-1.5 italic">
                Key ratios &amp; valuation
              </EditorialHead>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Column 1 — Valuation */}
            <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 md:p-6 rounded-[2px]">
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
            <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 md:p-6 rounded-[2px]">
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
            <div>
              <RuledKicker>Quant breakdown</RuledKicker>
              <EditorialHead size={22} as="h2" className="mt-1.5 italic">
                Four-pillar composite
              </EditorialHead>
            </div>
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
            <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-8 rounded-[2px] text-center">
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
            <div>
              <RuledKicker>Recent coverage</RuledKicker>
              <EditorialHead size={22} as="h2" className="mt-1.5 italic">
                News feed
              </EditorialHead>
            </div>
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
            <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-8 rounded-[2px] text-center">
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
                            className="group block bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-4 rounded-[2px] hover:border-[var(--pq-bronze)] hover:bg-[rgba(139,111,71,0.04)] transition-all"
                          >
                            <div className="flex items-start justify-between gap-4">
                              <div className="min-w-0 flex-1">
                                <p className="font-serif text-pq-lead leading-snug text-[var(--pq-ivory)] group-hover:text-[var(--pq-bronze-light)] transition-colors line-clamp-2">
                                  {n.title}
                                </p>
                                <div className="mt-2 flex items-center gap-2 flex-wrap">
                                  <span className={chipClass}>{chipLabel}</span>
                                  <span className="text-pq-mono-xs text-[var(--pq-ivory-faint)] font-sans tracking-tight">
                                    {n.source}
                                  </span>
                                  <span className="text-pq-mono-xs text-[var(--pq-ivory-faint)]">·</span>
                                  <span className="text-pq-mono-xs text-[var(--pq-ivory-faint)] font-sans tabular-nums tracking-tight">
                                    {n.published}
                                  </span>
                                </div>
                              </div>
                              <ExternalLink className="h-3.5 w-3.5 shrink-0 mt-1 text-[var(--pq-ivory-faint)] group-hover:text-[var(--pq-bronze)]" />
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
            <div className="mb-5">
              <div className="flex items-center gap-3">
                <span className="shrink-0">
                  <Eye className="h-4 w-4 text-[var(--pq-bronze)]" strokeWidth={1.4} />
                </span>
                <div>
                  <RuledKicker>Form 4 · 90 days</RuledKicker>
                  <EditorialHead size={22} as="h2" className="mt-1.5 italic">
                    Insider activity
                  </EditorialHead>
                </div>
              </div>
            </div>
            <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] rounded-[2px] overflow-hidden">
              {insiderData.length > 0 ? (
                <ul className="divide-y divide-[var(--pq-ivory-line-soft)]">
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
                          <span className="text-pq-body text-[var(--pq-ivory)] font-serif">
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
                          <span className="font-mono tabular-nums text-pq-caption text-[var(--pq-ivory)]">
                            {shares.toLocaleString()}
                          </span>
                          <span className="text-pq-eyebrow-sm tracking-[0.14em] uppercase text-[var(--pq-ivory-faint)]">
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
          <div className="mb-5">
            <div className="flex items-center gap-3">
              <span className="shrink-0">
                <Sparkles className="h-4 w-4 text-[var(--pq-bronze)]" strokeWidth={1.4} />
              </span>
              <div>
                <RuledKicker>AI assistant · observation</RuledKicker>
                <EditorialHead size={22} as="h2" className="mt-1.5 italic">
                  AI analysis
                </EditorialHead>
              </div>
            </div>
            {/* AI content disclosure (regulatory ③ 2026-01) — SWOT output is AI-generated */}
            <div className="mt-3">
              <AiContentBadge variant="inline" />
            </div>
          </div>
          <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] rounded-[2px] p-5">
            {swot && (swot.swot_kr || swot.swot) ? (
              <div className="space-y-4">
                {swot.swot_kr ? (
                  <div>
                    <FieldLabel>한국어</FieldLabel>
                    <p className="mt-2 whitespace-pre-line font-sans text-pq-body leading-[1.6] text-[var(--pq-ivory)]/85">
                      {swot.swot_kr}
                    </p>
                  </div>
                ) : null}
                {swot.swot ? (
                  <div className="pt-3 border-t border-[var(--pq-ivory-line-soft)]">
                    <FieldLabel>English</FieldLabel>
                    <p className="mt-2 whitespace-pre-line font-serif text-pq-body leading-[1.65] text-[var(--pq-ivory)]/75">
                      {swot.swot}
                    </p>
                  </div>
                ) : null}
                <div className="pt-3 mt-3 border-t border-[var(--pq-ivory-line-soft)]">
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
                  className="inline-flex items-center gap-2 px-4 py-2 text-pq-mono-xs uppercase tracking-[0.18em] border border-[var(--pq-bronze)] text-[var(--pq-bronze)] hover:bg-[rgba(184,149,106,0.08)] hover:text-[var(--pq-bronze-light)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors rounded-[2px]"
                >
                  <Sparkles className="h-3 w-3" strokeWidth={1.6} />
                  {swotLoading ? "Generating…" : "Generate AI summary"}
                </button>
                {swotError ? (
                  <p className="text-pq-mono-xs text-[var(--pq-ivory-dim)]">
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
          <div className="mb-5">
            <div className="flex items-center gap-3">
              <span className="shrink-0">
                <CalendarDays className="h-4 w-4 text-[var(--pq-bronze)]" strokeWidth={1.4} />
              </span>
              <div>
                <RuledKicker>Earnings · forward window</RuledKicker>
                <EditorialHead size={22} as="h2" className="mt-1.5 italic">
                  Earnings calendar
                </EditorialHead>
              </div>
            </div>
          </div>
          <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] rounded-[2px] p-5">
            {/* Bug-hunter 2026-05-05 CRITICAL: backend `routes/market.py::earnings_calendar`
                returns only {ticker, name, date, signal, score} — eps_estimate /
                eps_actual / revenue_estimate are NOT emitted. The previous 4-col
                table displayed "—" forever for those columns and mishandled KRW
                tickers (revenue_estimate hardcoded `$…B`). Switched to the actual
                backend shape: Date · Signal · Score. The KRW currency hazard is
                eliminated since these fields are not currency-bound. */}
            {earningsForTicker.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-pq-body">
                  <thead>
                    <tr className="text-left border-b border-[var(--pq-ivory-line)]">
                      <th className="pb-2 font-mono uppercase tracking-[0.16em] text-pq-mono-xs text-[var(--pq-ivory-faint)]">
                        Date
                      </th>
                      <th className="pb-2 font-mono uppercase tracking-[0.16em] text-pq-mono-xs text-[var(--pq-ivory-faint)]">
                        Signal
                      </th>
                      <th className="pb-2 font-mono uppercase tracking-[0.16em] text-pq-mono-xs text-[var(--pq-ivory-faint)] text-right">
                        Score
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {earningsForTicker.map((e, i) => (
                      <tr
                        key={`${e.date ?? "na"}-${i}`}
                        className="border-b border-[var(--pq-ivory-line-faint)] last:border-0"
                      >
                        <td className="py-2.5 tabular-nums text-[var(--pq-ivory-soft)]">
                          {e.date
                            ? new Date(e.date).toLocaleDateString("en-US", {
                                year: "numeric",
                                month: "short",
                                day: "numeric",
                              })
                            : "—"}
                        </td>
                        <td className="py-2.5 font-mono uppercase tracking-[0.18em] text-pq-mono-xs text-[var(--pq-ivory)]/85">
                          {(e.signal as string | undefined) ?? "—"}
                        </td>
                        <td className="py-2.5 text-right font-mono tabular-nums text-[var(--pq-ivory)]/75">
                          {typeof e.score === "number"
                            ? e.score.toFixed(2)
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
            Institutional ownership — section hidden until backend endpoint
            lands in /api/alt-data (release-prep audit 2026-05-09: surfacing
            "13F holder breakdown is not yet wired" to every visitor on every
            stock detail page erodes trust right before launch). Restore the
            <section> block once the SEC EDGAR holdings feed is wired and the
            data model is finalised; in the meantime the section simply does
            not render — design intentionally omits the empty-state.
           ══════════════════════════════════════════════════ */}

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
                <EditorialHead
                  size={26}
                  as="div"
                  className="mt-1.5 italic group-hover:text-[var(--pq-bronze-light)] transition-colors"
                >
                  Ask Companion about {ticker ?? "this ticker"}
                </EditorialHead>
                <p className="mt-2 pq-detail-caption">
                  Open a Companion thread pre-seeded with the current snapshot —
                  fundamentals, signal label, and recent coverage.
                </p>
              </div>
              <div className="text-pq-eyebrow-sm uppercase tracking-[0.18em] text-[var(--pq-bronze)] opacity-60 group-hover:opacity-100 transition-opacity inline-flex items-center gap-1.5 self-center">
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
          <div className="mb-5">
            <div className="flex items-center gap-3">
              <span className="shrink-0">
                <FileText className="h-4 w-4 text-[var(--pq-bronze)]" strokeWidth={1.4} />
              </span>
              <div>
                <RuledKicker>From your archive</RuledKicker>
                <EditorialHead size={22} as="h2" className="mt-1.5 italic">
                  Recent artefacts
                </EditorialHead>
              </div>
            </div>
          </div>
          {artifactsSwr.artifacts.length === 0 ? (
            <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] rounded-[2px] p-6 text-center">
              <p className="pq-detail-caption">
                No artefacts yet — {WEEKLY_MEMO_EMPTY_LINE}
              </p>
              <Link
                href="/reports"
                className="mt-3 inline-flex items-center gap-1.5 text-pq-eyebrow-sm uppercase tracking-[0.18em] text-[var(--pq-bronze)] hover:underline"
              >
                Open Reports
                <ExternalLink className="h-3 w-3" />
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {artifactsSwr.artifacts.slice(0, 3).map((a) => {
                const label =
                  a.type === "weekly_memo" ? "Weekly Memo"
                  : a.type === "earnings_prebrief" ? "Earnings Pre-Brief"
                  : a.type === "monthly_brag" || a.type === "brag_card" ? "Brag Card"
                  : a.type === "dd_checklist" ? "DD Checklist"
                  : a.type === "risk_board" ? "Risk Board"
                  : a.type === "year_end_letter" ? "Year-End Letter"
                  : (a.type || "Artifact").replace(/_/g, " ");
                const date = a.sent_at;
                const dateLabel = date
                  ? new Date(date).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
                  : "Archived";
                return (
                  <a
                    key={a.id}
                    href={getArtifactViewerUrl({ id: a.id, type: a.type, has_file: a.has_file })}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] rounded-[2px] p-5 hover:border-[var(--pq-bronze)] hover:bg-[rgba(139,111,71,0.04)] transition-all group"
                  >
                    <FieldLabel>{dateLabel}</FieldLabel>
                    <EditorialHead
                      size={18}
                      as="div"
                      className="mt-2 italic group-hover:text-[var(--pq-bronze-light)] transition-colors"
                    >
                      {label}
                    </EditorialHead>
                    <p className="mt-2 pq-detail-caption truncate">
                      {a.title || "Open the document for context."}
                    </p>
                    <div className="mt-4 text-pq-eyebrow-sm uppercase tracking-[0.18em] text-[var(--pq-bronze)] opacity-60 group-hover:opacity-100 transition-opacity inline-flex items-center gap-1.5">
                      Open
                      <ExternalLink className="h-3 w-3" />
                    </div>
                  </a>
                );
              })}
            </div>
          )}
        </section>

        {/* ── Footer fleuron (editorial signature) ── */}
        <FootSignature />
      </div>
    </ErrorBoundary>
  );
}
