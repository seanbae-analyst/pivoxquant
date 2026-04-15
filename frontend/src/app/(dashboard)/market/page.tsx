"use client";

import useSWR from "swr";
import { API } from "@/lib/endpoints";
import { useMarketOverview, useSectors } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { fmtPct } from "@/lib/format";
import { Skeleton, CardSkeleton } from "@/components/ui/loading-skeleton";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Activity,
  Globe,
  TrendingUp,
  BarChart3,
  DollarSign,
  Gauge,
  Clock,
  CloudOff,
} from "lucide-react";

/* ── Types ── */

interface MarketStatusEntry {
  status?: string;
  label?: string;
  time?: string;
  open?: boolean;
  next_open?: string;
  next_close?: string;
}

interface MarketStatusResponse {
  us: MarketStatusEntry;
  kr: MarketStatusEntry;
}

/* ── Fetcher ── */

const fetcher = async (url: string) => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

/* ── Macro Card ── */

function MacroCard({
  label,
  value,
  changePct,
  icon,
  suffix,
}: {
  label: string;
  value: string;
  changePct?: number;
  icon: React.ReactNode;
  suffix?: string;
}) {
  const hasChange = changePct !== undefined && changePct !== null;
  const isPositive = (changePct ?? 0) >= 0;

  return (
    <div className="sp-card p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-slate-400">{icon}</span>
        <span className="text-xs font-medium text-slate-500">{label}</span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-lg font-bold tabular-nums text-slate-900">
          {value}
          {suffix && (
            <span className="text-sm font-medium text-slate-400">
              {suffix}
            </span>
          )}
        </span>
        {hasChange && (
          <span
            className={cn(
              "text-xs font-semibold tabular-nums",
              isPositive ? "text-emerald-600" : "text-red-500",
            )}
          >
            {fmtPct(changePct)}
          </span>
        )}
      </div>
    </div>
  );
}

/* ── Market Status Badge ── */

function StatusBadge({ label, isOpen }: { label: string; isOpen: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={cn(
          "status-dot",
          isOpen ? "active" : "inactive",
        )}
      />
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <span
        className={cn(
          "text-xs font-semibold",
          isOpen ? "text-emerald-600" : "text-slate-400",
        )}
      >
        {isOpen ? "개장" : "휴장"}
      </span>
    </div>
  );
}

/* ── Sector Bar ── */

function SectorBar({
  sector,
  changePct,
}: {
  sector: string;
  changePct: number;
}) {
  const isPositive = changePct >= 0;
  const absWidth = Math.min(Math.abs(changePct) * 10, 100);

  return (
    <div className="flex items-center gap-3 py-2">
      <span className="text-sm font-medium text-slate-700 w-24 sm:w-40 shrink-0 truncate">
        {sector}
      </span>
      <div className="flex-1 relative h-6">
        {/* Background track */}
        <div className="absolute inset-0 rounded-full bg-slate-100" />
        {/* Filled bar */}
        <div
          className={cn(
            "absolute inset-y-0 rounded-full transition-all duration-500",
            isPositive ? "bg-emerald-500/20 left-0" : "bg-red-500/20 right-0",
          )}
          style={{
            width: `${absWidth}%`,
            ...(isPositive ? { left: 0 } : { right: 0 }),
          }}
        />
        {/* Inner colored bar */}
        <div
          className={cn(
            "absolute inset-y-1 rounded-full transition-all duration-500",
            isPositive ? "bg-emerald-500 left-0.5" : "bg-red-500 right-0.5",
          )}
          style={{
            width: `${Math.max(absWidth * 0.6, 2)}%`,
            ...(isPositive ? { left: 2 } : { right: 2 }),
          }}
        />
      </div>
      <span
        className={cn(
          "text-sm font-semibold tabular-nums w-16 text-right shrink-0",
          isPositive ? "text-emerald-600" : "text-red-500",
        )}
      >
        {fmtPct(changePct)}
      </span>
    </div>
  );
}

/* ── Page ── */

export default function MarketPage() {
  const { data: overview, isLoading: loadingOverview } = useMarketOverview();
  const { data: sectors, isLoading: loadingSectors } = useSectors();
  const { data: marketStatus, isLoading: loadingStatus } =
    useSWR<MarketStatusResponse>(API.market.status, fetcher, {
      revalidateOnFocus: false,
      dedupingInterval: 60_000,
    });

  const macro = overview?.macro;

  return (
    <ErrorBoundary>
    <div className="mx-auto max-w-3xl space-y-6">
      {/* ── Header + Status ── */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">시장 현황</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            거시 지표 및 섹터 성과
          </p>
        </div>

        {/* Market status badges */}
        {loadingStatus ? (
          <Skeleton className="h-8 w-40" />
        ) : marketStatus ? (
          <div className="flex items-center gap-4">
            <StatusBadge label="US" isOpen={marketStatus.us?.status === "OPEN" || marketStatus.us?.open === true} />
            <StatusBadge label="KR" isOpen={marketStatus.kr?.status === "OPEN" || marketStatus.kr?.open === true} />
          </div>
        ) : null}
      </div>

      {/* ── Macro Cards ── */}
      {loadingOverview ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      ) : macro ? (
        <>
          {/* Row 1: Major indices */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MacroCard
              label="S&P 500"
              value={macro?.sp500?.price?.toLocaleString("en-US", {
                maximumFractionDigits: 0,
              }) ?? "\u2014"}
              changePct={macro?.sp500?.change_pct ?? 0}
              icon={<TrendingUp className="h-4 w-4" />}
            />
            <MacroCard
              label="VIX"
              value={macro?.vix?.toFixed(1) ?? "\u2014"}
              icon={<Activity className="h-4 w-4" />}
            />
            <MacroCard
              label="USD/KRW"
              value={macro?.usdkrw?.price?.toLocaleString("en-US", {
                maximumFractionDigits: 0,
              }) ?? "\u2014"}
              changePct={macro?.usdkrw?.change_pct ?? 0}
              icon={<DollarSign className="h-4 w-4" />}
            />
            <MacroCard
              label="Fear & Greed"
              value={macro?.fear_greed?.value != null ? String(macro.fear_greed.value) : "\u2014"}
              icon={<Gauge className="h-4 w-4" />}
              suffix={macro?.fear_greed?.label ? ` ${macro.fear_greed.label}` : undefined}
            />
          </div>

          {/* Row 2: More indices */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MacroCard
              label="NASDAQ"
              value={macro?.nasdaq?.price?.toLocaleString("en-US", {
                maximumFractionDigits: 0,
              }) ?? "\u2014"}
              changePct={macro?.nasdaq?.change_pct ?? 0}
              icon={<BarChart3 className="h-4 w-4" />}
            />
            <MacroCard
              label="DOW"
              value={macro?.dow?.price?.toLocaleString("en-US", {
                maximumFractionDigits: 0,
              }) ?? "\u2014"}
              changePct={macro?.dow?.change_pct ?? 0}
              icon={<BarChart3 className="h-4 w-4" />}
            />
            <MacroCard
              label="KOSPI"
              value={macro?.kospi?.price?.toLocaleString("en-US", {
                maximumFractionDigits: 0,
              }) ?? "\u2014"}
              changePct={macro?.kospi?.change_pct ?? 0}
              icon={<Globe className="h-4 w-4" />}
            />
            <MacroCard
              label="KOSDAQ"
              value={macro?.kosdaq?.price?.toLocaleString("en-US", {
                maximumFractionDigits: 0,
              }) ?? "\u2014"}
              changePct={macro?.kosdaq?.change_pct ?? 0}
              icon={<Globe className="h-4 w-4" />}
            />
          </div>

          {/* Row 3: Commodities & Crypto */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MacroCard
              label="Gold"
              value={macro?.gold?.price != null ? `$${macro.gold.price.toLocaleString("en-US", { maximumFractionDigits: 0 })}` : "\u2014"}
              changePct={macro?.gold?.change_pct ?? 0}
              icon={<DollarSign className="h-4 w-4" />}
            />
            <MacroCard
              label="WTI Oil"
              value={macro?.oil_wti?.price != null ? `$${macro.oil_wti.price.toFixed(2)}` : "\u2014"}
              changePct={macro?.oil_wti?.change_pct ?? 0}
              icon={<BarChart3 className="h-4 w-4" />}
            />
            <MacroCard
              label="Bitcoin"
              value={macro?.btc?.price != null ? `$${macro.btc.price.toLocaleString("en-US", { maximumFractionDigits: 0 })}` : "\u2014"}
              changePct={macro?.btc?.change_pct ?? 0}
              icon={<TrendingUp className="h-4 w-4" />}
            />
            <MacroCard
              label="10Y Treasury"
              value={macro?.treasury_10y != null ? `${macro.treasury_10y.toFixed(2)}%` : "\u2014"}
              icon={<Clock className="h-4 w-4" />}
            />
          </div>
        </>
      ) : (
        <EmptyState
          icon={<CloudOff className="h-8 w-8" />}
          title="시장 데이터 없음"
          description="최신 거시 지표를 불러올 수 없습니다. 잠시 후 다시 시도해 주세요."
        />
      )}

      {/* ── Sector Performance ── */}
      <div className="sp-card p-5">
        <h3 className="text-base font-bold text-slate-900 mb-4">
          섹터 성과
        </h3>

        {loadingSectors ? (
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : !sectors?.length ? (
          <p className="text-sm text-slate-400 py-4">
            섹터 데이터를 불러올 수 없습니다.
          </p>
        ) : (
          <div className="divide-y divide-slate-50">
            {[...sectors]
              .sort((a, b) => (b?.change_pct ?? 0) - (a?.change_pct ?? 0))
              .map((s) => (
                <SectorBar
                  key={s?.sector ?? "unknown"}
                  sector={s?.sector ?? "Unknown"}
                  changePct={s?.change_pct ?? 0}
                />
              ))}
          </div>
        )}
      </div>

      {/* ── GS View (if available) ── */}
      {overview?.gs_view?.bias && (
        <div className="sp-card p-5">
          <h3 className="text-base font-bold text-slate-900 mb-2">
            시장 전망
          </h3>
          <div className="flex items-center gap-2 mb-3">
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
                overview.gs_view.bias === "bullish"
                  ? "signal-positive"
                  : overview.gs_view.bias === "bearish"
                    ? "signal-negative"
                    : "signal-neutral",
              )}
            >
              {overview.gs_view.bias.charAt(0).toUpperCase() +
                overview.gs_view.bias.slice(1)}
            </span>
          </div>
          {overview.gs_view.bias_note && (
            <p className="text-sm text-slate-600 leading-relaxed">
              {overview.gs_view.bias_note}
            </p>
          )}
          {Array.isArray(overview.gs_view.themes) && overview.gs_view.themes.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {overview.gs_view.themes.map((theme: string, i: number) => (
                <span
                  key={i}
                  className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-600"
                >
                  {theme}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
    </ErrorBoundary>
  );
}
