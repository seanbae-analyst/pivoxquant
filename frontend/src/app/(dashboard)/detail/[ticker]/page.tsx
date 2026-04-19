"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { API } from "@/lib/endpoints";
import { fmtUsd, fmtKrw } from "@/lib/format";
import { cn } from "@/lib/utils";
import { StockHeader } from "@/components/dashboard/stock-header";
import { ScoreBar } from "@/components/dashboard/score-bar";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { EmptyState } from "@/components/ui/empty-state";
import { PriceChart } from "@/components/dashboard/price-chart";
import { Skeleton, CardSkeleton } from "@/components/ui/loading-skeleton";
import {
  TrendingUp,
  BarChart3,
  Shield,
  Brain,
  Newspaper,
  ExternalLink,
  SearchX,
} from "lucide-react";

/* ── Types for API responses ── */

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
  snapshot?: Record<string, number | string | null>;
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
  url: string;
  source: string;
  date: string;
  sentiment?: string;
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

/* ── SWR fetcher ── */

const fetcher = async (url: string) => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

/* ── Currency helpers (Fix 4) ── */

function isKrwSignal(signal: SignalDetail | undefined, ticker: string): boolean {
  if (signal?.currency === "KRW") return true;
  if (signal?.is_korean === true) return true;
  return /^\d{6}\.(KS|KQ)$/i.test(ticker);
}

function fmtPriceByCurrency(value: number, isKrw: boolean): string {
  return isKrw ? fmtKrw(value) : fmtUsd(value);
}

function fmtMarketCap(value: number, isKrw: boolean): string {
  if (isKrw) {
    if (value >= 1e12) return `${(value / 1e12).toFixed(1)}조원`;
    if (value >= 1e8) return `${(value / 1e8).toFixed(0)}억원`;
    return `${value.toLocaleString("ko-KR")}원`;
  }
  if (value >= 1e12) return `$${(value / 1e12).toFixed(1)}T`;
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  return `$${(value / 1e6).toFixed(0)}M`;
}

/* ── Period mapping ── */

const PERIOD_MAP: Record<string, string> = {
  "1W": "5d",
  "1M": "1mo",
  "3M": "3mo",
  "6M": "6mo",
  "1Y": "1y",
};

/* ── Pillar Card ── */

function PillarCard({
  label,
  icon,
  score,
}: {
  label: string;
  icon: React.ReactNode;
  score: number;
}) {
  const color =
    score >= 70
      ? "text-emerald-600"
      : score >= 45
        ? "text-amber-500"
        : "text-red-500";
  const bg =
    score >= 70
      ? "bg-emerald-50"
      : score >= 45
        ? "bg-amber-50"
        : "bg-red-50";

  return (
    <div className="sp-card p-4 flex flex-col items-center gap-2 text-center">
      <div
        className={cn(
          "w-10 h-10 rounded-xl flex items-center justify-center",
          bg,
          color,
        )}
      >
        {icon}
      </div>
      <span className="text-xs font-medium text-slate-500">{label}</span>
      <span className={cn("text-xl font-bold tabular-nums", color)}>
        {score}
      </span>
    </div>
  );
}

/* ── Metric Cell ── */

function MetricCell({
  label,
  value,
  valueColor,
}: {
  label: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5 p-3 rounded-xl bg-slate-50">
      <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">
        {label}
      </span>
      <span
        className={cn(
          "text-sm font-semibold tabular-nums",
          valueColor ?? "text-slate-900",
        )}
      >
        {value}
      </span>
    </div>
  );
}

/* ── Page ── */

export default function StockDetailPage() {
  const params = useParams<{ ticker: string }>();
  // Korean tickers arrive as bare 6-digit codes (e.g. "005930") but the
  // SignalCache / backend expects the Yahoo-style ".KS" suffix. Normalize
  // here so every downstream fetch hits the right key.
  const raw = (params.ticker ?? "").toUpperCase();
  const ticker = /^\d{6}$/.test(raw) ? `${raw}.KS` : raw;

  const [chartPeriod, setChartPeriod] = useState("1M");

  // Fetch all data
  const { data: signal, isLoading: loadingSignal } = useSWR<SignalDetail>(
    ticker ? API.signals.one(ticker) : null,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 30_000 },
  );

  const { data: chartRes, isLoading: loadingChart, error: chartError, mutate: mutateChart } = useSWR<ChartResponse>(
    ticker ? `${API.market.chart(ticker)}?period=${PERIOD_MAP[chartPeriod] ?? "1mo"}` : null,
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

  // Only gate the hero on signal load; profile is supplementary and
  // may legitimately 404 for some tickers. Blocking on it caused a tall
  // empty placeholder to linger above the hero section.
  const isLoading = loadingSignal;
  const hasPillars =
    signal?.tech_score != null ||
    signal?.fund_score != null ||
    signal?.news_score != null ||
    signal?.quant_score != null;
  /* ── No ticker path param ── */
  if (!ticker) {
    return (
      <ErrorBoundary>
        <div className="mx-auto max-w-3xl">
          <EmptyState
            icon={<SearchX className="h-8 w-8" />}
            title="No Ticker Specified"
            description="Open a stock from your portfolio, watchlist, or discover page to see details."
            action={{ label: "Browse Discover", href: "/discover" }}
          />
        </div>
      </ErrorBoundary>
    );
  }

  /* ── Ticker not found / API failure (loaded but no data anywhere) ── */
  if (!loadingSignal && !loadingProfile && !signal && !profile) {
    return (
      <ErrorBoundary>
        <div className="mx-auto max-w-3xl">
          <EmptyState
            icon={<SearchX className="h-8 w-8" />}
            title={`No data for "${ticker}"`}
            description="We could not find this ticker. It may be unsupported, delisted, or temporarily unavailable."
            action={{ label: "Back to Discover", href: "/discover" }}
          />
        </div>
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary>
    <div className="mx-auto max-w-3xl space-y-5">
      {/* ── Disclaimer ── */}
      <DisclaimerBanner type="signal" />

      {/* ── Header ── */}
      <StockHeader
        ticker={ticker}
        name={signal?.name ?? profile?.name}
        price={signal?.price}
        changePct={signal?.change_pct}
        sector={signal?.sector ?? profile?.sector}
        currency={signal?.currency}
        isKorean={signal?.is_korean}
        isLoading={isLoading}
      />

      {/* ── Score Bar ── */}
      {isLoading ? (
        <CardSkeleton />
      ) : signal ? (
        <ScoreBar score={signal.score ?? 0} signal={signal.signal ?? "NEUTRAL"} />
      ) : (
        <div className="sp-card p-5 text-center">
          <p className="text-sm text-slate-400">시그널 데이터를 불러오는 중...</p>
        </div>
      )}

      {/* ── Price Chart ── */}
      <PriceChart
        data={chartRes?.data}
        isLoading={loadingChart}
        error={chartError}
        onRetry={() => mutateChart()}
        period={chartPeriod}
        onPeriodChange={setChartPeriod}
        currency={signal?.currency}
      />

      {/* ── Key Metrics Grid ── */}
      <div className="sp-card p-5">
        <h3 className="text-base font-bold text-slate-900 mb-4">
          Key Metrics
        </h3>
        {loadingProfile && !profile ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <MetricCell
              label="Take Profit"
              value={
                signal?.price && signal?.tp_pct
                  ? fmtPriceByCurrency(
                      signal.price * (1 + signal.tp_pct / 100),
                      isKrwSignal(signal, ticker),
                    )
                  : "--"
              }
              valueColor="text-emerald-600"
            />
            <MetricCell
              label="Stop Loss"
              value={
                signal?.price && signal?.sl_pct
                  ? fmtPriceByCurrency(
                      signal.price * (1 + signal.sl_pct / 100),
                      isKrwSignal(signal, ticker),
                    )
                  : "--"
              }
              valueColor="text-red-500"
            />
            <MetricCell
              label="P/E Ratio"
              value={profile?.pe_ratio != null ? Number(profile.pe_ratio).toFixed(1) : "--"}
            />
            <MetricCell
              label="Market Cap"
              value={
                profile?.market_cap != null && profile.market_cap > 0
                  ? fmtMarketCap(profile.market_cap, isKrwSignal(signal, ticker))
                  : "--"
              }
            />
            <MetricCell
              label="52W High"
              value={
                profile?.week52_high
                  ? fmtPriceByCurrency(profile.week52_high, isKrwSignal(signal, ticker))
                  : "--"
              }
            />
            <MetricCell
              label="52W Low"
              value={
                profile?.week52_low
                  ? fmtPriceByCurrency(profile.week52_low, isKrwSignal(signal, ticker))
                  : "--"
              }
            />
          </div>
        )}
      </div>

      {/* ── Quant Breakdown (4 Pillars) ── */}
      <div>
        <h3 className="text-base font-bold text-slate-900 mb-3">
          Quant Breakdown
        </h3>
        {hasPillars ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <PillarCard
              label="Technical"
              icon={<TrendingUp className="h-5 w-5" />}
              score={signal?.tech_score ?? 0}
            />
            <PillarCard
              label="Fundamental"
              icon={<BarChart3 className="h-5 w-5" />}
              score={signal?.fund_score ?? 0}
            />
            <PillarCard
              label="Sentiment"
              icon={<Brain className="h-5 w-5" />}
              score={signal?.news_score ?? 0}
            />
            <PillarCard
              label="Quant"
              icon={<Shield className="h-5 w-5" />}
              score={signal?.quant_score ?? 0}
            />
          </div>
        ) : (
          <div className="sp-card p-6 text-center text-sm text-slate-400">
            분석 데이터 준비 중 — Analysis data pending
          </div>
        )}
      </div>

      {/* ── News ── */}
      <div className="sp-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <Newspaper className="h-4 w-4 text-slate-400" />
          <h3 className="text-base font-bold text-slate-900">News</h3>
        </div>

        {loadingNews ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : !newsRes?.news?.length ? (
          <p className="text-sm text-slate-400 py-4">
            No recent news available.
          </p>
        ) : (
          <div className="space-y-2">
            {newsRes.news.slice(0, 8).map((item, i) => (
              <a
                key={i}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-start gap-3 rounded-xl p-3 transition-colors hover:bg-slate-50 group"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-900 line-clamp-2 group-hover:text-accent transition-colors">
                    {item.title}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[11px] text-slate-400">
                      {item.source}
                    </span>
                    <span className="text-[11px] text-slate-300">|</span>
                    <span className="text-[11px] text-slate-400">
                      {item.date}
                    </span>
                  </div>
                </div>
                <ExternalLink className="h-3.5 w-3.5 shrink-0 text-slate-300 mt-0.5 group-hover:text-accent transition-colors" />
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
    </ErrorBoundary>
  );
}
