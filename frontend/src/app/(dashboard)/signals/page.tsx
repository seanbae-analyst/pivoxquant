"use client";

import { useState, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { API } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { fmtPct } from "@/lib/format";
import { ScoreBar } from "@/components/dashboard/score-bar";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { CardSkeleton } from "@/components/ui/loading-skeleton";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  RefreshCw,
  BarChart2,
  TrendingUp,
  Brain,
  Shield,
  Briefcase,
} from "lucide-react";

/* ── Types ── */

interface SignalItem {
  ticker: string;
  name: string;
  signal: string;
  score: number;
  price: number;
  change_pct: number;
  sector: string;
  currency: "USD" | "KRW";
  is_korean: boolean;
  tech_score?: number;
  fund_score?: number;
  news_score?: number;
  quant_score?: number;
}

interface SignalsListResponse {
  signals: SignalItem[];
}

/* ── Fetcher ── */

const fetcher = async (url: string) => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

/* ── Filter values ── */

const FILTERS = ["All", "POSITIVE", "NEGATIVE", "NEUTRAL"] as const;
type FilterValue = (typeof FILTERS)[number];

/* ── Signal badge ── */

function SignalBadge({ signal }: { signal: string }) {
  const cls =
    signal === "POSITIVE"
      ? "signal-positive"
      : signal === "NEGATIVE"
        ? "signal-negative"
        : "signal-neutral";
  const label =
    signal === "POSITIVE"
      ? "Positive"
      : signal === "NEGATIVE"
        ? "Negative"
        : "Neutral";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        cls,
      )}
    >
      {label}
    </span>
  );
}

/* ── Mini pillar score ── */

function MiniPillar({
  label,
  score,
  icon,
}: {
  label: string;
  score: number;
  icon: React.ReactNode;
}) {
  const color =
    score >= 70
      ? "text-emerald-600"
      : score >= 45
        ? "text-amber-500"
        : "text-red-500";

  return (
    <div className="flex items-center gap-1" title={label}>
      <span className={cn("shrink-0", color)}>{icon}</span>
      <span className={cn("text-xs font-semibold tabular-nums", color)}>
        {score}
      </span>
    </div>
  );
}

/* ── Signal Card ── */

function SignalCard({
  item,
  onClick,
}: {
  item: SignalItem;
  onClick: () => void;
}) {
  const isPositive = (item?.change_pct ?? 0) >= 0;
  const priceDisplay =
    item?.price == null
      ? "\u2014"
      : item.currency === "KRW"
        ? `₩${Math.round(item.price).toLocaleString("ko-KR")}`
        : `$${item.price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return (
    <button
      type="button"
      onClick={onClick}
      className="sp-card p-4 w-full text-left transition-all hover:shadow-md active:scale-[0.99]"
    >
      <div className="flex items-start justify-between gap-3">
        {/* Left: ticker + name */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-slate-900">
              {item.ticker}
            </span>
            <SignalBadge signal={item.signal} />
          </div>
          <p className="text-xs text-slate-500 truncate mt-0.5">
            {item.name}
          </p>
        </div>

        {/* Right: price + change */}
        <div className="text-right shrink-0">
          <p className="text-sm font-bold tabular-nums text-slate-900">
            {priceDisplay}
          </p>
          <p
            className={cn(
              "text-xs font-semibold tabular-nums",
              isPositive ? "text-emerald-600" : "text-red-500",
            )}
          >
            {fmtPct(item?.change_pct ?? 0)}
          </p>
        </div>
      </div>

      {/* Score bar mini */}
      <div className="mt-3">
        <ScoreBar score={item.score} mini />
      </div>

      {/* Pillar mini scores */}
      {(item?.tech_score != null || item?.fund_score != null) && (
        <div className="mt-3 flex items-center gap-3 border-t border-slate-100 pt-3">
          <MiniPillar
            label="기술적"
            score={item?.tech_score ?? 0}
            icon={<TrendingUp className="h-3 w-3" />}
          />
          <MiniPillar
            label="기본적"
            score={item?.fund_score ?? 0}
            icon={<BarChart2 className="h-3 w-3" />}
          />
          <MiniPillar
            label="심리"
            score={item?.news_score ?? 0}
            icon={<Brain className="h-3 w-3" />}
          />
          <MiniPillar
            label="퀀트"
            score={item?.quant_score ?? 0}
            icon={<Shield className="h-3 w-3" />}
          />
        </div>
      )}
    </button>
  );
}

/* ── Page ── */

export default function SignalsPage() {
  const router = useRouter();
  const [filter, setFilter] = useState<FilterValue>("All");
  const [refreshing, setRefreshing] = useState(false);

  const { data, isLoading, mutate } = useSWR<SignalsListResponse>(
    API.signals.all,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 30_000 },
  );

  const signals = useMemo(() => data?.signals ?? [], [data?.signals]);

  const filtered = useMemo(() => {
    if (filter === "All") return signals;
    return signals.filter((s) => s.signal === filter);
  }, [signals, filter]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await apiFetch(API.signals.refresh, { method: "POST" });
      await mutate();
    } catch {
      // silent — SWR will show stale data
    } finally {
      setRefreshing(false);
    }
  }, [mutate]);

  return (
    <ErrorBoundary>
    <div className="mx-auto max-w-3xl space-y-5">
      {/* ── Disclaimer ── */}
      <DisclaimerBanner type="signal" />

      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900">시그널</h1>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshing}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-semibold transition-all",
            "bg-slate-900 text-white hover:bg-slate-800 active:scale-[0.97]",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          )}
        >
          <RefreshCw
            className={cn("h-3.5 w-3.5", refreshing && "animate-spin")}
          />
          새로고침
        </button>
      </div>

      {/* ── Filter pills ── */}
      <div className="flex gap-2 overflow-x-auto scrollbar-hide pb-1">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={cn("filter-pill whitespace-nowrap", filter === f && "active")}
          >
            {f === "All" ? "전체" : f.charAt(0) + f.slice(1).toLowerCase()}
            {f !== "All" && (
              <span className="ml-1 tabular-nums">
                ({signals.filter((s) => s.signal === f).length})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Loading ── */}
      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        /* ── Empty state ── */
        <EmptyState
          icon={<Briefcase className="h-8 w-8" />}
          title={
            signals.length === 0
              ? "포지션 없음"
              : "해당하는 시그널 없음"
          }
          description={
            signals.length === 0
              ? "포트폴리오에 포지션을 추가하면 AI 기반 퀀트 시그널을 확인할 수 있습니다."
              : "다른 필터를 선택해 보세요."
          }
          action={
            signals.length === 0
              ? { label: "포트폴리오로 이동", href: "/home" }
              : undefined
          }
        />
      ) : (
        /* ── Signal cards ── */
        <div className="space-y-3">
          {filtered.map((item) => (
            <SignalCard
              key={item.ticker}
              item={item}
              onClick={() => router.push(`/detail/${item.ticker}`)}
            />
          ))}
        </div>
      )}
    </div>
    </ErrorBoundary>
  );
}
