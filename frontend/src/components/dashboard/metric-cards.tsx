"use client";

import { cn } from "@/lib/utils";
import { fmtUsd, fmtPct, pnlColor } from "@/lib/format";
import { CardSkeleton } from "@/components/ui/loading-skeleton";
import type { PortfolioResponse, AnalyticsResponse } from "@/lib/types";
import { useT } from "@/lib/locale";

/* ── Icons (inline SVG to avoid bundle dep) ── */

function WalletIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a2.25 2.25 0 00-2.25-2.25H15a3 3 0 110-6h5.25A2.25 2.25 0 0121 6v6zm0 0v6a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 18V6a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 6" />
    </svg>
  );
}

function TrendUpIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
    </svg>
  );
}

/* ── Helpers ── */

function computeTodayPnl(positions: PortfolioResponse["positions"]): number {
  return positions.reduce((sum, p) => {
    const dayChange = p.current_price - p.avg_cost;
    return sum + dayChange * p.shares;
  }, 0);
}

function computeTodayPnlPct(portfolio: PortfolioResponse): number {
  const totalCost = portfolio.positions.reduce(
    (sum, p) => sum + p.avg_cost * p.shares,
    0,
  );
  if (totalCost === 0) return 0;
  const totalPnl = portfolio.positions.reduce(
    (sum, p) => sum + (p.current_price - p.avg_cost) * p.shares,
    0,
  );
  return (totalPnl / totalCost) * 100;
}

/* ── Single Metric Card ── */

interface MetricCardProps {
  label: string;
  icon: React.ReactNode;
  iconBg: string;
  value: string;
  sub?: string;
  subColor?: string;
}

function MetricCard({ label, icon, iconBg, value, sub, subColor }: MetricCardProps) {
  return (
    <div className="sp-card p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-500">{label}</span>
        <div className={cn("w-9 h-9 rounded-xl flex items-center justify-center", iconBg)}>
          {icon}
        </div>
      </div>
      <div>
        <p className="text-2xl font-bold text-slate-900 tabular-nums">{value}</p>
        {sub && (
          <p className={cn("text-sm font-medium tabular-nums mt-0.5", subColor ?? "text-slate-500")}>
            {sub}
          </p>
        )}
      </div>
    </div>
  );
}

/* ── Metric Cards Row ── */

interface MetricCardsProps {
  portfolio: PortfolioResponse | undefined;
  analytics: AnalyticsResponse | undefined;
  isLoading: boolean;
}

export function MetricCards({ portfolio, analytics, isLoading }: MetricCardsProps) {
  const t = useT();

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }

  const totalValue = portfolio?.total_value_usd ?? 0;
  const positions = portfolio?.positions ?? [];
  const totalPnl = computeTodayPnl(positions);
  const totalPnlPct = computeTodayPnlPct(portfolio ?? { positions: [], available_capital: 0, available_capital_krw: 0, total_value_usd: 0, total_value_krw: 0, total_value_all_krw: 0, fx_rate: 0 });
  const sharpe = analytics?.sharpe_ratio;

  // Risk score derived from Sharpe + MDD
  const riskScore = sharpe !== undefined
    ? Math.min(100, Math.max(0, Math.round(50 + sharpe * 20 - (analytics?.max_drawdown_pct ?? 0) * 0.5)))
    : 75;
  const riskStatus = riskScore >= 70 ? "GREEN" : riskScore >= 40 ? "YELLOW" : "RED";
  const riskColor = riskScore >= 70 ? "text-emerald-600" : riskScore >= 40 ? "text-amber-500" : "text-red-500";

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <MetricCard
        label={t("dashboard.metrics.portfolioValue")}
        icon={<WalletIcon />}
        iconBg="bg-violet-50 text-violet-600"
        value={fmtUsd(totalValue)}
        sub={positions.length > 0 ? `${positions.length}${t("dashboard.metrics.positions")}` : t("dashboard.metrics.noPositionsYet")}
      />
      <MetricCard
        label={t("dashboard.metrics.totalPnl")}
        icon={<TrendUpIcon />}
        iconBg={totalPnl >= 0 ? "bg-emerald-50 text-emerald-600" : "bg-red-50 text-red-500"}
        value={`${totalPnl >= 0 ? "+" : ""}${fmtUsd(totalPnl)}`}
        sub={fmtPct(totalPnlPct)}
        subColor={pnlColor(totalPnlPct)}
      />
      <MetricCard
        label={t("dashboard.metrics.riskScore")}
        icon={<ShieldIcon />}
        iconBg={riskScore >= 70 ? "bg-emerald-50 text-emerald-600" : riskScore >= 40 ? "bg-amber-50 text-amber-500" : "bg-red-50 text-red-500"}
        value={`${riskScore}/100`}
        sub={riskStatus}
        subColor={riskColor}
      />
    </div>
  );
}
