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
  let rawWeights = top5.map((p) => Math.max(p.score, 1) / scoreSum);

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
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
        <span className="text-zinc-600 text-[12px]">Loading...</span>
      </div>
    );
  }

  if (!rows.length) {
    return (
      <div className="space-y-4">
        <PageHeader />
        <div className="glass-surface rounded-2xl py-12 text-center">
          <Scale className="mx-auto h-10 w-10 text-zinc-600" />
          <p className="mt-4 text-sm text-zinc-400">
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
          icon={<Scale className="h-5 w-5 text-cyan-400" />}
          label="Positions Analyzed"
          value={String(rows.length)}
          sublabel="Top 5 by market value"
        />
        <MetricCard
          icon={<Target className="h-5 w-5 text-emerald-400" />}
          label="Current Sharpe"
          value={sharpe.toFixed(2)}
          sublabel="Annualized risk-adjusted return"
        />
        <MetricCard
          icon={<TrendingUp className="h-5 w-5 text-amber-400" />}
          label="Projected Sharpe Boost"
          value={`+${metrics.sharpeBoost.toFixed(2)}`}
          sublabel="Estimated improvement"
          valueColor="text-amber-400"
        />
        <MetricCard
          icon={<ArrowRight className="h-5 w-5 text-violet-400" />}
          label="Diversification Gain"
          value={`${metrics.diversGain.toFixed(1)}%`}
          sublabel="HHI concentration reduction"
          valueColor="text-violet-400"
        />
      </div>

      {/* ── Bar Chart ── */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-1 text-lg font-semibold text-white">
          Current vs Optimal Allocation
        </h2>
        <p className="mb-6 text-[13px] text-zinc-600">
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
                tick={{ fill: "#a1a1aa", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#71717a", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `${v}%`}
              />
              <Tooltip
                contentStyle={{
                  background: "#18181b",
                  border: "1px solid rgba(255,255,255,0.06)",
                  borderRadius: 12,
                  fontSize: 12,
                  color: "#fafafa",
                }}
                labelStyle={{ color: "#e4e4e7" }}
                itemStyle={{ color: "#a1a1aa" }}
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
                  <Cell key={i} fill="#22d3ee" fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4 flex items-center justify-center gap-6 text-xs text-zinc-400">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-blue-500/70" />
            Current
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-cyan-400/85" />
            Optimal
          </span>
        </div>
      </div>

      {/* ── Side-by-Side Comparison Table ── */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-1 text-lg font-semibold text-white">
          Weight Comparison
        </h2>
        <p className="mb-6 text-[13px] text-zinc-600">
          Current position weights vs score-optimized targets
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-white/[0.06] text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
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
                  className="border-b border-white/[0.04] last:border-0 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]"
                >
                  <td className="py-3 pr-4">
                    <span className="font-medium text-white">{r.ticker}</span>
                    <p className="max-w-[120px] truncate text-[10px] text-zinc-600">
                      {r.name}
                    </p>
                  </td>
                  <td className="py-3 pr-4 text-right">
                    <span
                      className={`font-mono font-medium ${
                        r.score >= 70
                          ? "text-emerald-400"
                          : r.score >= 45
                            ? "text-amber-400"
                            : "text-red-400"
                      }`}
                    >
                      {r.score}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-right font-mono text-zinc-300">
                    {(r.currentWeight * 100).toFixed(1)}%
                  </td>
                  <td className="py-3 pr-4 text-center">
                    <ArrowRight className="mx-auto h-3 w-3 text-zinc-600" />
                  </td>
                  <td className="py-3 pr-4 text-right font-mono font-medium text-cyan-400">
                    {(r.optimalWeight * 100).toFixed(1)}%
                  </td>
                  <td
                    className={`py-3 text-right font-mono font-medium ${
                      r.delta > 0.005
                        ? "text-emerald-400"
                        : r.delta < -0.005
                          ? "text-red-400"
                          : "text-zinc-500"
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
        <h2 className="mb-1 text-lg font-semibold text-white">
          Rebalancing Actions
        </h2>
        <p className="mb-6 text-[13px] text-zinc-600">
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
                  className={`flex items-center justify-between rounded-xl border px-4 py-3 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)] ${
                    isIncrease
                      ? "border-emerald-400/20 bg-emerald-400/5"
                      : "border-red-400/20 bg-red-400/5"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold ${
                        isIncrease
                          ? "bg-emerald-400/15 text-emerald-400"
                          : "bg-red-400/15 text-red-400"
                      }`}
                    >
                      {isIncrease ? "+" : "-"}
                    </span>
                    <div>
                      <p className="text-sm font-medium text-white">
                        {isIncrease ? "Increase" : "Decrease"} {r.ticker} by{" "}
                        {absPct}%
                      </p>
                      <p className="text-[10px] text-zinc-600">
                        {isIncrease ? "Buy" : "Sell"} approximately {absDollar}
                      </p>
                    </div>
                  </div>
                  <span
                    className={`text-sm font-mono font-semibold ${
                      isIncrease ? "text-emerald-400" : "text-red-400"
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
              <p className="text-sm text-zinc-400">
                Your portfolio is already close to optimal allocation.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── Expected Improvements ── */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-4 text-lg font-semibold text-white">
          Expected Improvements
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <ImprovementCard
            label="Projected Sharpe Ratio"
            from={sharpe.toFixed(2)}
            to={(sharpe + metrics.sharpeBoost).toFixed(2)}
            change={`+${metrics.sharpeBoost.toFixed(2)}`}
            color="text-amber-400"
          />
          <ImprovementCard
            label="Diversification (HHI Reduction)"
            from="Current"
            to="Optimized"
            change={`-${metrics.diversGain.toFixed(1)}% concentration`}
            color="text-violet-400"
          />
        </div>
      </div>

      {/* ── Disclaimer ── */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-4 text-lg font-semibold text-white">
          About This Optimizer
        </h2>
        <div className="space-y-2 text-xs text-zinc-400">
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
          <p className="text-zinc-600">
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
      <h1 className="text-2xl font-bold tracking-tight text-white">
        Portfolio Optimizer
      </h1>
      <p className="mt-1 text-[13px] text-zinc-600">
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
    <div className="glass-surface rounded-xl p-4 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
      <div className="flex items-center gap-2">
        {icon}
        <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">{label}</p>
      </div>
      <p className={`mt-2 text-2xl font-bold font-mono ${valueColor ?? "text-white"}`}>
        {value}
      </p>
      <p className="mt-0.5 text-[10px] text-zinc-600">{sublabel}</p>
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
    <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-4">
      <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">{label}</p>
      <div className="mt-3 flex items-center gap-3">
        <span className="text-lg font-semibold font-mono text-zinc-400">{from}</span>
        <ArrowRight className="h-4 w-4 text-zinc-600" />
        <span className="text-lg font-semibold font-mono text-white">{to}</span>
      </div>
      <p className={`mt-2 text-sm font-medium font-mono ${color}`}>{change}</p>
    </div>
  );
}
