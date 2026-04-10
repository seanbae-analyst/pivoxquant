"use client";

import { useMemo } from "react";
import { usePortfolio, useAnalytics } from "@/lib/hooks";
import { fmtUsd, fmtPct } from "@/lib/format";
import type { Position } from "@/lib/types";
import { Scale, ArrowRight, TrendingUp, Target } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

/* ── Types ── */

interface AllocationRow {
  ticker: string;
  name: string;
  score: number;
  currentWeight: number;
  optimalWeight: number;
  delta: number;
  marketValue: number;
}

/* ── Helpers ── */

function computeAllocations(
  positions: Position[],
  totalValue: number,
): AllocationRow[] {
  if (!positions.length || totalValue <= 0) return [];

  const sorted = [...positions].sort((a, b) => b.market_value - a.market_value);
  const top5 = sorted.slice(0, 5);

  const scoreSum = top5.reduce((s, p) => s + Math.max(p.score, 1), 0);
  const MAX_CAP = 0.25;

  /* First pass: raw optimal weights */
  const rawWeights = top5.map((p) => Math.max(p.score, 1) / scoreSum);

  /* Apply 25% cap iteratively */
  let capped = rawWeights.map((w) => Math.min(w, MAX_CAP));
  let excess = rawWeights.reduce(
    (s, w) => s + Math.max(0, w - MAX_CAP),
    0,
  );
  if (excess > 0) {
    const uncappedCount = capped.filter((w) => w < MAX_CAP).length;
    if (uncappedCount > 0) {
      const bonus = excess / uncappedCount;
      capped = capped.map((w) => (w < MAX_CAP ? Math.min(w + bonus, MAX_CAP) : w));
    }
  }

  /* Normalize to 100% */
  const cappedSum = capped.reduce((s, w) => s + w, 0);
  const normalized = capped.map((w) => w / cappedSum);

  return top5.map((pos, i) => {
    const currentWeight = pos.market_value / totalValue;
    const optimalWeight = normalized[i];
    return {
      ticker: pos.ticker,
      name: pos.name,
      score: pos.score,
      currentWeight,
      optimalWeight,
      delta: optimalWeight - currentWeight,
      marketValue: pos.market_value,
    };
  });
}

/* ── Page ── */

export default function OptimizerPage() {
  const { data: portfolio } = usePortfolio();
  const { data: analytics } = useAnalytics();

  const totalValue = analytics?.total_value ?? 0;
  const sharpe = analytics?.sharpe_ratio ?? 0;

  const rows = useMemo(
    () => computeAllocations(portfolio?.positions ?? [], totalValue),
    [portfolio, totalValue],
  );

  /* Projected improvements (heuristic) */
  const metrics = useMemo(() => {
    if (!rows.length) return { sharpeBoost: 0, diversGain: 0 };

    const totalAbsDelta = rows.reduce((s, r) => s + Math.abs(r.delta), 0);
    const sharpeBoost = Math.min(totalAbsDelta * 0.8, 0.35);

    const currentHHI = rows.reduce((s, r) => s + r.currentWeight ** 2, 0);
    const optimalHHI = rows.reduce((s, r) => s + r.optimalWeight ** 2, 0);
    const diversGain = Math.max(0, (currentHHI - optimalHHI) / currentHHI) * 100;

    return { sharpeBoost, diversGain };
  }, [rows]);

  /* Chart data */
  const chartData = rows.map((r) => ({
    ticker: r.ticker,
    current: +(r.currentWeight * 100).toFixed(1),
    optimal: +(r.optimalWeight * 100).toFixed(1),
  }));

  /* Loading */
  if (!portfolio || !analytics) {
    return (
      <div className="flex items-center justify-center py-32">
        <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse mr-2" />
        <span className="text-slate-400 text-[12px]">Loading...</span>
      </div>
    );
  }

  if (!rows.length) {
    return (
      <div className="space-y-4">
        <PageHeader />
        <div className="glass-surface rounded-2xl py-12 text-center">
          <Scale className="mx-auto h-10 w-10 text-slate-400" />
          <p className="mt-4 text-sm text-slate-500">
            No positions found. Add positions to see optimization suggestions.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader />

      {/* ── Summary Cards ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <MetricCard
          icon={<Scale className="h-5 w-5 text-sky-600" />}
          label="Positions Analyzed"
          value={String(rows.length)}
          sublabel="Top 5 by market value"
        />
        <MetricCard
          icon={<Target className="h-5 w-5 text-emerald-600" />}
          label="Current Sharpe"
          value={sharpe.toFixed(2)}
          sublabel="Annualized risk-adjusted return"
        />
        <MetricCard
          icon={<TrendingUp className="h-5 w-5 text-amber-500" />}
          label="Projected Sharpe Boost"
          value={`+${metrics.sharpeBoost.toFixed(2)}`}
          sublabel="Estimated improvement"
          valueColor="text-amber-500"
        />
        <MetricCard
          icon={<ArrowRight className="h-5 w-5 text-violet-500" />}
          label="Diversification Gain"
          value={`${metrics.diversGain.toFixed(1)}%`}
          sublabel="HHI concentration reduction"
          valueColor="text-violet-500"
        />
      </div>

      {/* ── Bar Chart ── */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-1 text-lg font-semibold text-slate-900">
          Current vs Optimal Allocation
        </h2>
        <p className="mb-6 text-[13px] text-slate-400">
          Score-weighted optimal with 25% max cap per position
        </p>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              barGap={4}
              margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
            >
              <XAxis
                dataKey="ticker"
                tick={{ fill: "#64748b", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `${v}%`}
              />
              <Tooltip
                contentStyle={{
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  borderRadius: 12,
                  fontSize: 12,
                  color: "#0f172a",
                }}
                labelStyle={{ color: "#334155" }}
                itemStyle={{ color: "#64748b" }}
                formatter={(value) => [`${value}%`]}
              />
              <Bar
                dataKey="current"
                name="Current"
                radius={[6, 6, 0, 0]}
                maxBarSize={40}
              >
                {chartData.map((_, i) => (
                  <Cell key={i} fill="#3b82f6" fillOpacity={0.7} />
                ))}
              </Bar>
              <Bar
                dataKey="optimal"
                name="Optimal"
                radius={[6, 6, 0, 0]}
                maxBarSize={40}
              >
                {chartData.map((_, i) => (
                  <Cell key={i} fill="#0ea5e9" fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4 flex items-center justify-center gap-6 text-xs text-slate-500">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-blue-500/70" />
            Current
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-sky-500/85" />
            Optimal
          </span>
        </div>
      </div>

      {/* ── Side-by-Side Comparison Table ── */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-1 text-lg font-semibold text-slate-900">
          Weight Comparison
        </h2>
        <p className="mb-6 text-[13px] text-slate-400">
          Current position weights vs score-optimized targets
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-[10px] font-semibold text-slate-400 uppercase tracking-[0.1em]">
                <th className="pb-3 pr-4">Ticker</th>
                <th className="pb-3 pr-4 text-right">Score</th>
                <th className="pb-3 pr-4 text-right">Current</th>
                <th className="pb-3 pr-4 text-center">
                  <ArrowRight className="mx-auto h-3 w-3" />
                </th>
                <th className="pb-3 pr-4 text-right">Optimal</th>
                <th className="pb-3 text-right">Delta</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.ticker}
                  className="border-b border-slate-100 last:border-0 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.06)]"
                >
                  <td className="py-3 pr-4">
                    <span className="font-medium text-slate-900">{r.ticker}</span>
                    <p className="max-w-[120px] truncate text-[10px] text-slate-400">
                      {r.name}
                    </p>
                  </td>
                  <td className="py-3 pr-4 text-right">
                    <span
                      className={`font-mono font-medium ${
                        r.score >= 70
                          ? "text-emerald-600"
                          : r.score >= 45
                            ? "text-amber-500"
                            : "text-red-600"
                      }`}
                    >
                      {r.score}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-right font-mono text-slate-700">
                    {(r.currentWeight * 100).toFixed(1)}%
                  </td>
                  <td className="py-3 pr-4 text-center">
                    <ArrowRight className="mx-auto h-3 w-3 text-slate-400" />
                  </td>
                  <td className="py-3 pr-4 text-right font-mono font-medium text-sky-600">
                    {(r.optimalWeight * 100).toFixed(1)}%
                  </td>
                  <td
                    className={`py-3 text-right font-mono font-medium ${
                      r.delta > 0.005
                        ? "text-emerald-600"
                        : r.delta < -0.005
                          ? "text-red-600"
                          : "text-slate-500"
                    }`}
                  >
                    {r.delta >= 0 ? "+" : ""}
                    {(r.delta * 100).toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Rebalancing Actions ── */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-1 text-lg font-semibold text-slate-900">
          Rebalancing Actions
        </h2>
        <p className="mb-6 text-[13px] text-slate-400">
          Suggested trades to reach optimal allocation
        </p>
        <div className="space-y-3">
          {rows
            .filter((r) => Math.abs(r.delta) >= 0.005)
            .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
            .map((r) => {
              const isIncrease = r.delta > 0;
              const absPct = Math.abs(r.delta * 100).toFixed(1);
              const absDollar = fmtUsd(Math.abs(r.delta) * totalValue);
              return (
                <div
                  key={r.ticker}
                  className={`flex items-center justify-between rounded-xl border px-4 py-3 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.06)] ${
                    isIncrease
                      ? "border-emerald-200 bg-emerald-50"
                      : "border-red-200 bg-red-50"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold ${
                        isIncrease
                          ? "bg-emerald-100 text-emerald-600"
                          : "bg-red-100 text-red-600"
                      }`}
                    >
                      {isIncrease ? "+" : "-"}
                    </span>
                    <div>
                      <p className="text-sm font-medium text-slate-900">
                        {isIncrease ? "Increase" : "Decrease"} {r.ticker} by{" "}
                        {absPct}%
                      </p>
                      <p className="text-[10px] text-slate-400">
                        {isIncrease ? "Buy" : "Sell"} approximately {absDollar}
                      </p>
                    </div>
                  </div>
                  <span
                    className={`text-sm font-mono font-semibold ${
                      isIncrease ? "text-emerald-600" : "text-red-600"
                    }`}
                  >
                    {isIncrease ? "+" : "-"}
                    {absPct}%
                  </span>
                </div>
              );
            })}
          {rows.filter((r) => Math.abs(r.delta) >= 0.005).length === 0 && (
            <div className="glass-surface rounded-2xl py-12 text-center">
              <p className="text-sm text-slate-500">
                Your portfolio is already close to optimal allocation.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── Expected Improvements ── */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">
          Expected Improvements
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <ImprovementCard
            label="Projected Sharpe Ratio"
            from={sharpe.toFixed(2)}
            to={(sharpe + metrics.sharpeBoost).toFixed(2)}
            change={`+${metrics.sharpeBoost.toFixed(2)}`}
            color="text-amber-500"
          />
          <ImprovementCard
            label="Diversification (HHI Reduction)"
            from="Current"
            to="Optimized"
            change={`-${metrics.diversGain.toFixed(1)}% concentration`}
            color="text-violet-500"
          />
        </div>
      </div>

      {/* ── Disclaimer ── */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">
          About This Optimizer
        </h2>
        <div className="space-y-2 text-xs text-slate-500">
          <p>
            Optimal weights are calculated using a score-weighted allocation model.
            Each position receives a weight proportional to its composite score
            relative to the total score of the top 5 holdings, subject to a 25%
            maximum cap per position.
          </p>
          <p>
            Sharpe ratio improvement estimates are heuristic projections based on the
            magnitude of rebalancing needed. Diversification gain is measured by the
            reduction in Herfindahl-Hirschman Index (HHI), a standard concentration
            metric.
          </p>
          <p className="text-slate-400">
            This is for educational and analytical purposes only. Past performance
            does not guarantee future results.
          </p>
        </div>
      </div>
    </div>
  );
}

/* ── Sub-components ── */

function PageHeader() {
  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight text-slate-900">
        Portfolio Optimizer
      </h1>
      <p className="mt-1 text-[13px] text-slate-400">
        Score-weighted allocation optimization with rebalancing suggestions
      </p>
    </div>
  );
}

function MetricCard({
  icon,
  label,
  value,
  sublabel,
  valueColor,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sublabel: string;
  valueColor?: string;
}) {
  return (
    <div className="glass-surface rounded-xl p-4 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.06)]">
      <div className="flex items-center gap-2">
        {icon}
        <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-[0.1em]">{label}</p>
      </div>
      <p className={`mt-2 text-2xl font-bold font-mono ${valueColor ?? "text-slate-900"}`}>
        {value}
      </p>
      <p className="mt-0.5 text-[10px] text-slate-400">{sublabel}</p>
    </div>
  );
}

function ImprovementCard({
  label,
  from,
  to,
  change,
  color,
}: {
  label: string;
  from: string;
  to: string;
  change: string;
  color: string;
}) {
  return (
    <div className="rounded-xl bg-slate-50 border border-slate-200 p-4">
      <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-[0.1em]">{label}</p>
      <div className="mt-3 flex items-center gap-3">
        <span className="text-lg font-semibold font-mono text-slate-500">{from}</span>
        <ArrowRight className="h-4 w-4 text-slate-400" />
        <span className="text-lg font-semibold font-mono text-slate-900">{to}</span>
      </div>
      <p className={`mt-2 text-sm font-medium font-mono ${color}`}>{change}</p>
    </div>
  );
}
