"use client";

import { useState, useMemo } from "react";
import { useHistory, useMarketOverview } from "@/lib/hooks";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { TrendingUp, BarChart3, Activity, Target } from "lucide-react";

/* ── Period config ── */

type Period = "1mo" | "3mo" | "6mo" | "1y";

const PERIODS: { key: Period; label: string; days: number }[] = [
  { key: "1mo", label: "1M", days: 21 },
  { key: "3mo", label: "3M", days: 63 },
  { key: "6mo", label: "6M", days: 126 },
  { key: "1y", label: "1Y", days: 252 },
];

/* ── Helpers ── */

function normalize(values: number[]): number[] {
  if (!values.length) return [];
  const base = values[0];
  if (base === 0) return values.map(() => 100);
  return values.map((v) => (v / base) * 100);
}

function calcReturn(values: number[], days: number): number {
  if (values.length < 2) return 0;
  const start = Math.max(0, values.length - days - 1);
  const end = values.length - 1;
  if (values[start] === 0) return 0;
  return ((values[end] - values[start]) / values[start]) * 100;
}

function fmtPctSigned(v: number): string {
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

/* ── Simulated benchmark series from a single change_pct ── */

function simulateBenchmarkSeries(
  changePct: number,
  length: number,
): number[] {
  // Given we only have the current price and overall change_pct,
  // create a plausible path from base price to current price
  // using interpolation with slight daily noise (seeded).
  const totalReturn = changePct / 100;
  const dailyReturn = Math.pow(1 + totalReturn, 1 / Math.max(length, 1)) - 1;
  const series: number[] = [1000];
  for (let i = 1; i < length; i++) {
    // deterministic "noise" based on index
    const noise = 1 + (Math.sin(i * 7.3 + i * i * 0.01) * 0.002);
    series.push(series[i - 1] * (1 + dailyReturn) * noise);
  }
  return series;
}

/* ── Custom tooltip ── */

function ChartTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: { value: number; name: string; color: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "#18181b",
        border: "1px solid rgba(255,255,255,0.06)",
        borderRadius: 12,
        fontSize: 12,
        color: "#fafafa",
      }}
      className="px-4 py-3 shadow-xl"
    >
      <p className="mb-1.5 text-[13px] text-zinc-600">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2 text-sm">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: p.color }}
          />
          <span className="text-zinc-400">{p.name}:</span>
          <span className="font-semibold font-mono text-white">{p.value.toFixed(2)}</span>
        </div>
      ))}
    </div>
  );
}

/* ── Summary card ── */

function SummaryCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
      <div className="mb-3 flex items-center gap-2">
        <Icon size={16} className="text-zinc-600" />
        <span className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
          {label}
        </span>
      </div>
      <p className={`text-2xl font-bold font-mono ${color}`}>{value}</p>
    </div>
  );
}

/* ── Page ── */

export default function BenchmarkPage() {
  const [period, setPeriod] = useState<Period>("3mo");
  const { data: history, isLoading: histLoading } = useHistory(period);
  const { data: overview, isLoading: mktLoading } = useMarketOverview();

  const isLoading = histLoading || mktLoading;

  /* Build chart data */
  const { chartData, portfolioReturn, benchmarkReturn, alpha, beta } =
    useMemo(() => {
      const points = history?.data ?? [];
      if (!points.length || !overview) {
        return {
          chartData: [],
          portfolioReturn: 0,
          benchmarkReturn: 0,
          alpha: 0,
          beta: 1,
        };
      }

      const portfolioValues = points.map((p) => p.value);
      const normPortfolio = normalize(portfolioValues);

      // Simulate benchmark path matching S&P 500 change_pct over the period
      const sp = overview.macro.sp500;
      const benchValues = simulateBenchmarkSeries(
        sp.change_pct,
        points.length,
      );
      const normBenchmark = normalize(benchValues);

      const data = points.map((p, i) => ({
        date: p.date.length > 5 ? p.date.slice(5) : p.date, // MM-DD
        portfolio: Number(normPortfolio[i].toFixed(2)),
        sp500: Number(normBenchmark[i].toFixed(2)),
      }));

      const pRet =
        portfolioValues.length >= 2
          ? ((portfolioValues[portfolioValues.length - 1] -
              portfolioValues[0]) /
              portfolioValues[0]) *
            100
          : 0;
      const bRet = sp.change_pct;
      const a = pRet - bRet;

      // Simple beta approximation: ratio of portfolio vol to benchmark vol
      const pDailyReturns: number[] = [];
      const bDailyReturns: number[] = [];
      for (let i = 1; i < portfolioValues.length; i++) {
        pDailyReturns.push(
          (portfolioValues[i] - portfolioValues[i - 1]) /
            portfolioValues[i - 1],
        );
        bDailyReturns.push(
          (benchValues[i] - benchValues[i - 1]) / benchValues[i - 1],
        );
      }

      let covariance = 0;
      let benchVariance = 0;
      const pMean =
        pDailyReturns.reduce((s, v) => s + v, 0) / pDailyReturns.length || 0;
      const bMean =
        bDailyReturns.reduce((s, v) => s + v, 0) / bDailyReturns.length || 0;
      for (let i = 0; i < pDailyReturns.length; i++) {
        covariance += (pDailyReturns[i] - pMean) * (bDailyReturns[i] - bMean);
        benchVariance += (bDailyReturns[i] - bMean) ** 2;
      }
      const b = benchVariance !== 0 ? covariance / benchVariance : 1;

      return {
        chartData: data,
        portfolioReturn: pRet,
        benchmarkReturn: bRet,
        alpha: a,
        beta: b,
      };
    }, [history, overview]);

  /* Period-specific returns for comparison table */
  const tableRows = useMemo(() => {
    const points = history?.data ?? [];
    if (!points.length || !overview) return [];
    const portfolioValues = points.map((p) => p.value);
    const sp = overview.macro.sp500;
    const benchValues = simulateBenchmarkSeries(sp.change_pct, points.length);

    return [
      { label: "1 Week", days: 5 },
      { label: "1 Month", days: 21 },
      { label: "3 Months", days: 63 },
    ].map((row) => {
      const pRet = calcReturn(portfolioValues, row.days);
      const bRet = calcReturn(benchValues, row.days);
      return {
        period: row.label,
        portfolio: pRet,
        benchmark: bRet,
        alpha: pRet - bRet,
      };
    });
  }, [history, overview]);

  /* ── Render ── */

  if (isLoading) {
    return (
      <div className="flex items-center py-32">
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
        <span className="text-zinc-600 text-[12px]">Loading...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Benchmark Comparison
        </h1>
        <p className="mt-1 text-[13px] text-zinc-600">
          Track your portfolio performance against the S&P 500
        </p>
      </div>

      {/* Period selector */}
      <div className="flex gap-2">
        {PERIODS.map((p) => (
          <button
            key={p.key}
            onClick={() => setPeriod(p.key)}
            className={`rounded-xl px-4 py-1.5 text-sm font-medium spring-transition transition-all duration-300 ${
              period === p.key
                ? "bg-gradient-to-r from-cyan-500/10 to-emerald-500/10 text-cyan-400 border border-cyan-500/20"
                : "bg-white/[0.03] border border-white/[0.06] text-zinc-400 hover:text-zinc-300 hover:border-white/[0.1]"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <SummaryCard
          icon={TrendingUp}
          label="Portfolio Return"
          value={fmtPctSigned(portfolioReturn)}
          color={portfolioReturn >= 0 ? "text-emerald-400" : "text-red-400"}
        />
        <SummaryCard
          icon={BarChart3}
          label="S&P 500 Return"
          value={fmtPctSigned(benchmarkReturn)}
          color={benchmarkReturn >= 0 ? "text-emerald-400" : "text-red-400"}
        />
        <SummaryCard
          icon={Target}
          label="Alpha"
          value={fmtPctSigned(alpha)}
          color={alpha >= 0 ? "text-cyan-400" : "text-red-400"}
        />
        <SummaryCard
          icon={Activity}
          label="Beta"
          value={beta.toFixed(2)}
          color="text-white"
        />
      </div>

      {/* Chart */}
      <div className="glass-surface rounded-xl p-6">
        <div className="mb-4">
          <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
            Normalized Performance (Base = 100)
          </p>
        </div>
        {chartData.length > 0 ? (
          <div className="h-[340px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(255,255,255,0.06)"
                />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#71717a", fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fill: "#71717a", fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  domain={["auto", "auto"]}
                  tickFormatter={(v: number) => v.toFixed(0)}
                />
                <Tooltip content={<ChartTooltip />} />
                <Legend
                  verticalAlign="top"
                  align="right"
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={{ fontSize: 12, color: "#a1a1aa" }}
                />
                <Line
                  type="monotone"
                  dataKey="portfolio"
                  name="Portfolio"
                  stroke="#22d3ee"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: "#22d3ee" }}
                />
                <Line
                  type="monotone"
                  dataKey="sp500"
                  name="S&P 500"
                  stroke="#a78bfa"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: "#a78bfa" }}
                  strokeDasharray="6 3"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="glass-surface rounded-2xl py-12 text-center">
            <p className="text-[13px] text-zinc-600">
              No portfolio history available for this period.
            </p>
          </div>
        )}
      </div>

      {/* Comparison table */}
      <div className="glass-surface rounded-xl p-6">
        <p className="mb-4 text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
          Performance Comparison
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.06]">
                <th className="pb-3 text-left text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
                  Period
                </th>
                <th className="pb-3 text-right text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
                  Portfolio
                </th>
                <th className="pb-3 text-right text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
                  S&P 500
                </th>
                <th className="pb-3 text-right text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
                  Alpha
                </th>
              </tr>
            </thead>
            <tbody>
              {tableRows.map((row) => (
                <tr
                  key={row.period}
                  className="border-b border-white/[0.06] last:border-0 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]"
                >
                  <td className="py-3 text-zinc-300">{row.period}</td>
                  <td
                    className={`py-3 text-right font-semibold font-mono ${
                      row.portfolio >= 0 ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    {fmtPctSigned(row.portfolio)}
                  </td>
                  <td
                    className={`py-3 text-right font-semibold font-mono ${
                      row.benchmark >= 0 ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    {fmtPctSigned(row.benchmark)}
                  </td>
                  <td
                    className={`py-3 text-right font-bold font-mono ${
                      row.alpha >= 0 ? "text-cyan-400" : "text-red-400"
                    }`}
                  >
                    {fmtPctSigned(row.alpha)}
                  </td>
                </tr>
              ))}
              {tableRows.length === 0 && (
                <tr>
                  <td
                    colSpan={4}
                    className="py-6 text-center text-[13px] text-zinc-600"
                  >
                    No data available
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Footnote */}
      <p className="text-[13px] text-zinc-600">
        Benchmark data is approximated from current S&P 500 change percentage.
        Beta is calculated using daily return covariance. Past performance does
        not guarantee future results.
      </p>
    </div>
  );
}
