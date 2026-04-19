"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/loading-skeleton";
import type { AnalyticsResponse } from "@/lib/types";

/* ── Progress ring (SVG) ── */

function ScoreRing({ score, size = 64 }: { score: number; size?: number }) {
  const r = (size - 8) / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (score / 100) * circumference;

  const color =
    score >= 70 ? "#10b981" : score >= 40 ? "#f59e0b" : "#ef4444";

  return (
    <svg width={size} height={size} className="rotate-[-90deg]">
      {/* Background track */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="#f1f5f9"
        strokeWidth={6}
      />
      {/* Score arc */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={6}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        className="transition-all duration-700 ease-out"
      />
    </svg>
  );
}

/* ── Risk Widget ── */

interface RiskWidgetProps {
  analytics: AnalyticsResponse | undefined;
  isLoading: boolean;
  hasPositions?: boolean;
}

export function RiskWidget({ analytics, isLoading, hasPositions = true }: RiskWidgetProps) {
  if (isLoading) {
    return (
      <div className="sp-card p-5 space-y-4">
        <Skeleton className="h-5 w-28" />
        <div className="flex items-center gap-4">
          <Skeleton className="h-16 w-16 rounded-full" />
          <div className="space-y-2 flex-1">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-3 w-32" />
          </div>
        </div>
      </div>
    );
  }

  if (!hasPositions) {
    return (
      <div className="sp-card p-5 flex flex-col">
        <h3 className="text-base font-bold text-slate-900 mb-4">
          리스크 방어
        </h3>
        <div className="flex-1 flex items-center justify-center py-6">
          <p className="text-sm text-slate-400 text-center">
            포지션이 없습니다 — 리스크 분석 대기중
          </p>
        </div>
        <Link
          href="/portfolio"
          className="mt-auto text-sm font-semibold text-accent hover:text-accent/80 transition-colors self-start"
        >
          포지션 추가 &rarr;
        </Link>
      </div>
    );
  }

  const sharpe = analytics?.sharpe_ratio ?? 0;
  const mdd = analytics?.max_drawdown_pct ?? 0;

  // Composite risk score: higher is better
  const score = Math.min(
    100,
    Math.max(0, Math.round(50 + sharpe * 20 - mdd * 0.5)),
  );
  const status = score >= 70 ? "GREEN" : score >= 40 ? "YELLOW" : "RED";
  const statusColor =
    score >= 70
      ? "text-emerald-600"
      : score >= 40
        ? "text-amber-500"
        : "text-red-500";
  const statusBg =
    score >= 70
      ? "bg-emerald-50"
      : score >= 40
        ? "bg-amber-50"
        : "bg-red-50";

  return (
    <div className="sp-card p-5 flex flex-col">
      <h3 className="text-base font-bold text-slate-900 mb-4">
        리스크 방어
      </h3>

      <div className="flex items-center gap-5 mb-5">
        {/* Score ring */}
        <div className="relative flex-shrink-0">
          <ScoreRing score={score} />
          <span className="absolute inset-0 flex items-center justify-center text-lg font-bold text-slate-900 tabular-nums">
            {score}
          </span>
        </div>

        {/* Status info */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-700">상태</span>
            <span
              className={cn(
                "rounded-full px-2.5 py-0.5 text-xs font-bold",
                statusBg,
                statusColor,
              )}
            >
              {status}
            </span>
          </div>
          {analytics?.sharpe_ratio !== undefined && (
            <p className="text-xs text-slate-500">
              Sharpe {sharpe.toFixed(2)} / MDD {mdd.toFixed(1)}%
            </p>
          )}
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <p className="text-xs text-slate-500">연환산 수익</p>
          <p className="text-sm font-bold text-slate-900 tabular-nums">
            {analytics?.ann_return_pct !== undefined
              ? `${analytics.ann_return_pct.toFixed(1)}%`
              : "--"}
          </p>
        </div>
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <p className="text-xs text-slate-500">연환산 변동성</p>
          <p className="text-sm font-bold text-slate-900 tabular-nums">
            {analytics?.ann_vol_pct !== undefined
              ? `${analytics.ann_vol_pct.toFixed(1)}%`
              : "--"}
          </p>
        </div>
      </div>

      <Link
        href="/risk"
        className="mt-auto text-sm font-semibold text-accent hover:text-accent/80 transition-colors self-start"
      >
        상세 보기 &rarr;
      </Link>
    </div>
  );
}
