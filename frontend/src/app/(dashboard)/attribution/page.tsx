"use client";

import { useMemo } from "react";
import { usePortfolio } from "@/lib/hooks";
import type { Position } from "@/lib/types";
import { fmtPct, fmtUsd } from "@/lib/format";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import {
  PieChart,
  TrendingUp,
  TrendingDown,
  BarChart3,
} from "lucide-react";

/* ── Types ── */

interface Attribution {
  ticker: string;
  name: string;
  sector: string;
  weight: number;
  pnl_pct: number;
  contribution: number;
}

interface SectorAttribution {
  sector: string;
  contribution: number;
  count: number;
}

/* ── Helpers ── */

function calcAttributions(positions: Position[]): Attribution[] {
  const totalValue = positions.reduce((s, p) => s + p.market_value, 0);
  if (totalValue === 0) return [];
  return positions.map((p) => ({
    ticker: p.ticker,
    name: p.name,
    sector: p.sector,
    weight: (p.market_value / totalValue) * 100,
    pnl_pct: p.pnl_pct,
    contribution: (p.market_value / totalValue) * p.pnl_pct,
  }));
}

function calcSectorAttribution(attrs: Attribution[]): SectorAttribution[] {
  const map = new Map<string, SectorAttribution>();
  for (const a of attrs) {
    const key = a.sector || "Other";
    const existing = map.get(key);
    if (existing) {
      existing.contribution += a.contribution;
      existing.count += 1;
    } else {
      map.set(key, { sector: key, contribution: a.contribution, count: 1 });
    }
  }
  return Array.from(map.values()).sort(
    (a, b) => b.contribution - a.contribution,
  );
}

/* ── Custom Tooltip ── */

function WaterfallTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: Attribution }[];
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
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
      <p className="text-sm font-semibold text-white">{d.ticker}</p>
      <p className="text-[13px] text-zinc-400">{d.name}</p>
      <div className="mt-2 space-y-1 text-[13px]">
        <div className="flex justify-between gap-6">
          <span className="text-zinc-600">Weight</span>
          <span className="text-zinc-300 font-mono">{d.weight.toFixed(1)}%</span>
        </div>
        <div className="flex justify-between gap-6">
          <span className="text-zinc-600">P&L</span>
          <span className={`font-mono ${d.pnl_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {fmtPct(d.pnl_pct)}
          </span>
        </div>
        <div className="flex justify-between gap-6">
          <span className="text-zinc-600">Contribution</span>
          <span
            className={`font-mono ${
              d.contribution >= 0 ? "text-emerald-400" : "text-red-400"
            }`}
          >
            {d.contribution >= 0 ? "+" : ""}
            {d.contribution.toFixed(3)}%
          </span>
        </div>
      </div>
    </div>
  );
}

/* ── Stat Card ── */

function StatCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
      <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
        {label}
      </p>
      <p className={`mt-1 text-2xl font-bold font-mono ${color ?? "text-white"}`}>
        {value}
      </p>
      {sub && <p className="mt-0.5 text-[13px] text-zinc-600">{sub}</p>}
    </div>
  );
}

/* ── Main Page ── */

export default function AttributionPage() {
  const { data, isLoading } = usePortfolio();
  const positions = data?.positions ?? [];

  const attributions = useMemo(
    () => calcAttributions(positions).sort((a, b) => b.contribution - a.contribution),
    [positions],
  );

  const sectorAttrs = useMemo(
    () => calcSectorAttribution(attributions),
    [attributions],
  );

  const totalPnl = useMemo(
    () => attributions.reduce((s, a) => s + a.contribution, 0),
    [attributions],
  );

  const avgPnl = useMemo(
    () => (attributions.length ? totalPnl / attributions.length : 0),
    [attributions, totalPnl],
  );

  const best = attributions[0];
  const worst = attributions[attributions.length - 1];

  const topContributors = attributions.slice(0, 3);
  const topDetractors = [...attributions]
    .sort((a, b) => a.contribution - b.contribution)
    .slice(0, 3);

  /* ── Loading / Empty ── */

  if (isLoading) {
    return (
      <div className="flex items-center py-32">
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
        <span className="text-zinc-600 text-[12px]">Loading...</span>
      </div>
    );
  }

  if (!positions.length) {
    return (
      <div className="glass-surface rounded-2xl py-12 text-center">
        <BarChart3 className="mx-auto h-10 w-10 text-zinc-700" />
        <p className="mt-3 text-[13px] text-zinc-600">No positions to attribute.</p>
      </div>
    );
  }

  /* ── Render ── */

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Performance Attribution
        </h1>
        <p className="mt-1 text-[13px] text-zinc-600">
          How each position and sector contributed to your portfolio returns.
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total P&L Contribution"
          value={`${totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(2)}%`}
          color={totalPnl >= 0 ? "text-emerald-400" : "text-red-400"}
        />
        <StatCard
          label="Avg Position Contribution"
          value={`${avgPnl >= 0 ? "+" : ""}${avgPnl.toFixed(3)}%`}
          color={avgPnl >= 0 ? "text-emerald-400" : "text-red-400"}
        />
        <StatCard
          label="Best Performer"
          value={best?.ticker ?? "\u2014"}
          sub={best ? fmtPct(best.pnl_pct) : undefined}
          color="text-emerald-400"
        />
        <StatCard
          label="Worst Performer"
          value={worst?.ticker ?? "\u2014"}
          sub={worst ? fmtPct(worst.pnl_pct) : undefined}
          color="text-red-400"
        />
      </div>

      {/* Waterfall Chart */}
      <div className="glass-surface rounded-xl p-6">
        <div className="mb-4 flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-cyan-400" />
          <h2 className="text-lg font-semibold text-white">
            P&L Contribution by Position
          </h2>
        </div>
        <div className="h-[360px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={attributions}
              margin={{ top: 8, right: 16, bottom: 8, left: 0 }}
            >
              <XAxis
                dataKey="ticker"
                tick={{ fill: "#71717a", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#71717a", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `${v.toFixed(2)}%`}
              />
              <Tooltip
                content={<WaterfallTooltip />}
                cursor={{ fill: "rgba(255,255,255,0.03)" }}
              />
              <Bar dataKey="contribution" radius={[6, 6, 0, 0]}>
                {attributions.map((a, i) => (
                  <Cell
                    key={i}
                    fill={a.contribution >= 0 ? "#34d399" : "#f87171"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Sector Attribution + Contributors Grid */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Sector Attribution */}
        <div className="glass-surface rounded-xl p-6 lg:col-span-1">
          <div className="mb-4 flex items-center gap-2">
            <PieChart className="h-5 w-5 text-cyan-400" />
            <h2 className="text-lg font-semibold text-white">
              Sector Attribution
            </h2>
          </div>
          <div className="space-y-3">
            {sectorAttrs.map((s) => (
              <div key={s.sector}>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-300">{s.sector}</span>
                  <span
                    className={`text-sm font-medium font-mono ${
                      s.contribution >= 0 ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    {s.contribution >= 0 ? "+" : ""}
                    {s.contribution.toFixed(3)}%
                  </span>
                </div>
                <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
                  <div
                    className={`h-full rounded-full ${
                      s.contribution >= 0 ? "bg-emerald-400" : "bg-red-400"
                    }`}
                    style={{
                      width: `${Math.min(
                        Math.abs(s.contribution) /
                          Math.max(
                            ...sectorAttrs.map((x) =>
                              Math.abs(x.contribution),
                            ),
                            0.01,
                          ) *
                          100,
                        100,
                      )}%`,
                    }}
                  />
                </div>
                <p className="mt-0.5 text-[10px] text-zinc-600">
                  {s.count} position{s.count !== 1 ? "s" : ""}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Top Contributors */}
        <div className="glass-surface rounded-xl p-6">
          <div className="mb-4 flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-emerald-400" />
            <h2 className="text-lg font-semibold text-white">
              Top Contributors
            </h2>
          </div>
          <div className="space-y-3">
            {topContributors.map((a, i) => (
              <div
                key={a.ticker}
                className="flex items-center gap-3 rounded-xl bg-emerald-500/5 border border-white/[0.06] px-4 py-3 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-400/10 text-xs font-bold text-emerald-400">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-white">
                    {a.ticker}
                  </p>
                  <p className="truncate text-[13px] text-zinc-600">{a.name}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium font-mono text-emerald-400">
                    +{a.contribution.toFixed(3)}%
                  </p>
                  <p className="text-[10px] text-zinc-600">
                    {a.weight.toFixed(1)}% weight
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Top Detractors */}
        <div className="glass-surface rounded-xl p-6">
          <div className="mb-4 flex items-center gap-2">
            <TrendingDown className="h-5 w-5 text-red-400" />
            <h2 className="text-lg font-semibold text-white">
              Top Detractors
            </h2>
          </div>
          <div className="space-y-3">
            {topDetractors.map((a, i) => (
              <div
                key={a.ticker}
                className="flex items-center gap-3 rounded-xl bg-red-500/5 border border-white/[0.06] px-4 py-3 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-red-400/10 text-xs font-bold text-red-400">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-white">
                    {a.ticker}
                  </p>
                  <p className="truncate text-[13px] text-zinc-600">{a.name}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium font-mono text-red-400">
                    {a.contribution.toFixed(3)}%
                  </p>
                  <p className="text-[10px] text-zinc-600">
                    {a.weight.toFixed(1)}% weight
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
