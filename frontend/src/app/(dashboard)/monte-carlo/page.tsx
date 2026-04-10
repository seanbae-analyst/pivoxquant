"use client";

import { useMemo, useState, useCallback } from "react";
import { usePortfolio, useAnalytics } from "@/lib/hooks";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

/* ── Monte Carlo math helpers ── */

function boxMullerRandom(): number {
  let u = 0,
    v = 0;
  while (u === 0) u = Math.random();
  while (v === 0) v = Math.random();
  return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}

function runSimulation(
  startValue: number,
  annReturn: number,
  annVol: number,
  numPaths: number,
  numDays: number,
) {
  const dt = 1 / 252;
  const mu = annReturn / 100;
  const sigma = annVol / 100;
  const drift = (mu - (sigma * sigma) / 2) * dt;
  const diffusion = sigma * Math.sqrt(dt);

  // paths[day][pathIndex]
  const paths: number[][] = Array.from({ length: numDays + 1 }, () =>
    new Array(numPaths).fill(0),
  );

  for (let p = 0; p < numPaths; p++) {
    paths[0][p] = startValue;
    for (let d = 1; d <= numDays; d++) {
      const z = boxMullerRandom();
      paths[d][p] = paths[d - 1][p] * Math.exp(drift + diffusion * z);
    }
  }

  return paths;
}

function percentile(arr: number[], p: number): number {
  const sorted = [...arr].sort((a, b) => a - b);
  const idx = (p / 100) * (sorted.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return sorted[lo];
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

interface ChartRow {
  day: number;
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
}

function buildChartData(paths: number[][]): ChartRow[] {
  const rows: ChartRow[] = [];
  // sample every N days to keep chart performant
  const totalDays = paths.length - 1;
  const step = Math.max(1, Math.floor(totalDays / 126));
  for (let d = 0; d <= totalDays; d += step) {
    const vals = paths[d];
    rows.push({
      day: d,
      p10: percentile(vals, 10),
      p25: percentile(vals, 25),
      p50: percentile(vals, 50),
      p75: percentile(vals, 75),
      p90: percentile(vals, 90),
    });
  }
  // ensure last day included
  if (rows[rows.length - 1].day !== totalDays) {
    const vals = paths[totalDays];
    rows.push({
      day: totalDays,
      p10: percentile(vals, 10),
      p25: percentile(vals, 25),
      p50: percentile(vals, 50),
      p75: percentile(vals, 75),
      p90: percentile(vals, 90),
    });
  }
  return rows;
}

/* ── Formatting ── */

function fmtUsd(v: number): string {
  return v.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
}

function fmtPct(v: number): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
}

/* ── Custom Tooltip ── */

function SimTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const data = payload[0]?.payload as ChartRow | undefined;
  if (!data) return null;
  return (
    <div
      style={{
        background: "#ffffff",
        border: "1px solid #e2e8f0",
        borderRadius: 12,
        fontSize: 12,
        color: "#0f172a",
      }}
      className="px-3 py-2 shadow-xl"
    >
      <p className="mb-1 font-medium text-slate-900">Day {data.day}</p>
      <div className="space-y-0.5">
        <p className="text-emerald-600">90th: {fmtUsd(data.p90)}</p>
        <p className="text-emerald-600/70">75th: {fmtUsd(data.p75)}</p>
        <p className="text-sky-600">Median: {fmtUsd(data.p50)}</p>
        <p className="text-red-600/70">25th: {fmtUsd(data.p25)}</p>
        <p className="text-red-600">10th: {fmtUsd(data.p10)}</p>
      </div>
    </div>
  );
}

/* ── Page ── */

const NUM_PATHS = 1000;
const NUM_DAYS = 252;

export default function MonteCarloPage() {
  const { data: portfolio } = usePortfolio();
  const { data: analytics } = useAnalytics();
  const [simKey, setSimKey] = useState(0);

  const startValue = portfolio?.total_value_usd ?? 0;
  const annReturn = analytics?.ann_return_pct ?? 10;
  const annVol = analytics?.ann_vol_pct ?? 20;

  const { chartData, finalVals } = useMemo(() => {
    if (startValue <= 0) return { chartData: [], finalVals: [] as number[] };
    const paths = runSimulation(
      startValue,
      annReturn,
      annVol,
      NUM_PATHS,
      NUM_DAYS,
    );
    const cd = buildChartData(paths);
    const fv = paths[NUM_DAYS];
    return { chartData: cd, finalVals: fv };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startValue, annReturn, annVol, simKey]);

  const rerun = useCallback(() => setSimKey((k) => k + 1), []);

  const stats = useMemo(() => {
    if (!finalVals.length)
      return {
        expected: 0,
        best: 0,
        worst: 0,
        profitProb: 0,
        expectedReturn: 0,
        bestReturn: 0,
        worstReturn: 0,
      };
    const expected = percentile(finalVals, 50);
    const best = percentile(finalVals, 90);
    const worst = percentile(finalVals, 10);
    const profitProb =
      (finalVals.filter((v) => v > startValue).length / finalVals.length) * 100;
    return {
      expected,
      best,
      worst,
      profitProb,
      expectedReturn: ((expected - startValue) / startValue) * 100,
      bestReturn: ((best - startValue) / startValue) * 100,
      worstReturn: ((worst - startValue) / startValue) * 100,
    };
  }, [finalVals, startValue]);

  /* loading state */
  if (!portfolio || !analytics) {
    return (
      <div className="flex items-center py-32">
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
        <span className="text-slate-400 text-[12px]">Loading...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* ── Header ── */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Monte Carlo Simulation
          </h1>
          <p className="mt-1 text-[13px] text-slate-500">
            {NUM_PATHS.toLocaleString()} simulated paths over {NUM_DAYS} trading
            days (1 year)
          </p>
        </div>
        <button
          onClick={rerun}
          className="bg-gradient-to-r from-sky-500/10 to-emerald-500/10 text-sky-600 border border-sky-500/20 hover:from-sky-500/20 hover:to-emerald-500/20 rounded-xl spring-transition transition-all duration-300 px-4 py-2 text-sm font-medium"
        >
          Re-run Simulation
        </button>
      </div>

      {/* ── Summary Stats ── */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          label="Expected Value"
          sublabel="50th percentile"
          value={fmtUsd(stats.expected)}
          change={fmtPct(stats.expectedReturn)}
          positive={stats.expectedReturn >= 0}
        />
        <StatCard
          label="Best Case"
          sublabel="90th percentile"
          value={fmtUsd(stats.best)}
          change={fmtPct(stats.bestReturn)}
          positive={stats.bestReturn >= 0}
        />
        <StatCard
          label="Worst Case"
          sublabel="10th percentile"
          value={fmtUsd(stats.worst)}
          change={fmtPct(stats.worstReturn)}
          positive={stats.worstReturn >= 0}
        />
        <StatCard
          label="Probability of Profit"
          sublabel={`above ${fmtUsd(startValue)}`}
          value={`${stats.profitProb.toFixed(1)}%`}
          positive={stats.profitProb >= 50}
          highlight
        />
      </div>

      {/* ── Chart ── */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-1 text-lg font-semibold text-slate-900">
          Portfolio Value Probability Cone
        </h2>
        <p className="mb-6 text-[13px] text-slate-500">
          Shaded regions show the 10th-90th percentile range of simulated
          outcomes
        </p>
        <div className="h-[420px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={chartData}
              margin={{ top: 8, right: 16, left: 16, bottom: 0 }}
            >
              <defs>
                <linearGradient id="gradOuter" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.08} />
                  <stop offset="100%" stopColor="#22d3ee" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="gradInner" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.18} />
                  <stop offset="100%" stopColor="#22d3ee" stopOpacity={0.04} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#e2e8f0"
                vertical={false}
              />
              <XAxis
                dataKey="day"
                tick={{ fontSize: 11, fill: "#71717a" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) =>
                  v === 0 ? "Today" : `${Math.round(v / 21)}m`
                }
              />
              <YAxis
                tick={{ fontSize: 11, fill: "#71717a" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) =>
                  `$${(v / 1000).toFixed(0)}k`
                }
                width={56}
              />
              <Tooltip content={<SimTooltip />} />
              {/* outer band: 10-90 */}
              <Area
                type="monotone"
                dataKey="p90"
                stroke="none"
                fill="url(#gradOuter)"
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="p10"
                stroke="none"
                fill="#ffffff"
                isAnimationActive={false}
              />
              {/* inner band: 25-75 */}
              <Area
                type="monotone"
                dataKey="p75"
                stroke="none"
                fill="url(#gradInner)"
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="p25"
                stroke="none"
                fill="#ffffff"
                isAnimationActive={false}
              />
              {/* median line */}
              <Area
                type="monotone"
                dataKey="p50"
                stroke="#22d3ee"
                strokeWidth={2}
                fill="none"
                dot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        {/* Legend */}
        <div className="mt-4 flex flex-wrap items-center justify-center gap-6 text-[13px] text-slate-500">
          <span className="flex items-center gap-2">
            <span className="inline-block h-0.5 w-5 bg-sky-500 rounded" />
            Median (50th)
          </span>
          <span className="flex items-center gap-2">
            <span className="inline-block h-3 w-5 rounded bg-sky-500/15" />
            25th - 75th
          </span>
          <span className="flex items-center gap-2">
            <span className="inline-block h-3 w-5 rounded bg-sky-500/5" />
            10th - 90th
          </span>
        </div>
      </div>

      {/* ── Assumptions ── */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">
          Simulation Assumptions
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <AssumptionItem
            label="Starting Portfolio Value"
            value={fmtUsd(startValue)}
          />
          <AssumptionItem
            label="Annualized Return"
            value={fmtPct(annReturn)}
          />
          <AssumptionItem
            label="Annualized Volatility"
            value={`${annVol.toFixed(1)}%`}
          />
        </div>
        <p className="mt-4 text-[13px] text-slate-500">
          Based on Geometric Brownian Motion: S(t+1) = S(t) * exp((mu -
          sigma^2/2)*dt + sigma*sqrt(dt)*Z). Returns and volatility are derived
          from your portfolio analytics. Past performance does not guarantee
          future results.
        </p>
      </div>
    </div>
  );
}

/* ── Sub-components ── */

function StatCard({
  label,
  sublabel,
  value,
  change,
  positive,
  highlight,
}: {
  label: string;
  sublabel: string;
  value: string;
  change?: string;
  positive: boolean;
  highlight?: boolean;
}) {
  return (
    <div className="glass-surface rounded-xl p-4 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.08)]">
      <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-[0.1em]">{label}</p>
      <p className="text-[10px] text-slate-500">{sublabel}</p>
      <p
        className={`mt-2 text-2xl font-bold font-mono ${
          highlight
            ? positive
              ? "text-emerald-600"
              : "text-red-600"
            : "text-slate-900"
        }`}
      >
        {value}
      </p>
      {change && (
        <p
          className={`mt-0.5 text-xs font-medium font-mono ${
            positive ? "text-emerald-600" : "text-red-600"
          }`}
        >
          {change}
        </p>
      )}
    </div>
  );
}

function AssumptionItem({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3">
      <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-[0.1em]">{label}</p>
      <p className="mt-1 text-lg font-semibold font-mono text-sky-600">{value}</p>
    </div>
  );
}
