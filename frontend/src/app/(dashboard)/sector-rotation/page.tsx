"use client";

import { useMemo } from "react";
import { usePortfolio, useAnalytics, useVixStrategy, useSectors } from "@/lib/hooks";
import type { Position, SectorItem } from "@/lib/types";
import { fmtPct } from "@/lib/format";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from "recharts";
import { RotateCcw, TrendingUp, Shield, Zap } from "lucide-react";

/* ── Sector Allocation Targets ── */

interface SectorTarget {
  sector: string;
  bull: number;
  neutral: number;
  bear: number;
}

const SECTOR_TARGETS: SectorTarget[] = [
  { sector: "Technology",         bull: 25, neutral: 15, bear: 8 },
  { sector: "Consumer Cyclical",  bull: 18, neutral: 12, bear: 6 },
  { sector: "Communication Services", bull: 12, neutral: 10, bear: 7 },
  { sector: "Financial Services", bull: 10, neutral: 12, bear: 10 },
  { sector: "Industrials",        bull: 8,  neutral: 10, bear: 8 },
  { sector: "Energy",             bull: 5,  neutral: 8,  bear: 10 },
  { sector: "Healthcare",         bull: 6,  neutral: 10, bear: 15 },
  { sector: "Consumer Defensive", bull: 4,  neutral: 8,  bear: 15 },
  { sector: "Utilities",          bull: 4,  neutral: 8,  bear: 13 },
  { sector: "Real Estate",        bull: 5,  neutral: 5,  bear: 5 },
  { sector: "Basic Materials",    bull: 3,  neutral: 2,  bear: 3 },
];

type Regime = "bull" | "neutral" | "bear";

function getRegime(vix: number): Regime {
  if (vix < 18) return "bull";
  if (vix <= 25) return "neutral";
  return "bear";
}

const REGIME_META: Record<Regime, { label: string; color: string; bg: string; icon: typeof TrendingUp }> = {
  bull:    { label: "Bull",    color: "text-emerald-400", bg: "bg-emerald-400/10 border-emerald-400/30", icon: TrendingUp },
  neutral: { label: "Neutral", color: "text-amber-400",   bg: "bg-amber-400/10 border-amber-400/30",   icon: RotateCcw },
  bear:    { label: "Bear",    color: "text-red-400",     bg: "bg-red-400/10 border-red-400/30",       icon: Shield },
};

/* ── Helpers ── */

interface SectorRow {
  sector: string;
  currentWeight: number;
  recommendedWeight: number;
  change: number;
  livePrice?: number;
  liveChangePct?: number;
}

function buildSectorRows(
  positions: Position[],
  regime: Regime,
  sectorData: SectorItem[] | undefined,
): SectorRow[] {
  const totalValue = positions.reduce((s, p) => s + p.market_value, 0);
  const currentWeights = new Map<string, number>();

  for (const p of positions) {
    const key = p.sector || "Other";
    currentWeights.set(key, (currentWeights.get(key) ?? 0) + (totalValue > 0 ? (p.market_value / totalValue) * 100 : 0));
  }

  const sectorLookup = new Map<string, SectorItem>();
  if (sectorData) {
    for (const s of sectorData) {
      sectorLookup.set(s.sector, s);
    }
  }

  return SECTOR_TARGETS.map((t) => {
    const current = currentWeights.get(t.sector) ?? 0;
    const recommended = t[regime];
    const live = sectorLookup.get(t.sector);
    return {
      sector: t.sector,
      currentWeight: current,
      recommendedWeight: recommended,
      change: recommended - current,
      livePrice: live?.price,
      liveChangePct: live?.change_pct,
    };
  }).sort((a, b) => Math.abs(b.change) - Math.abs(a.change));
}

/* ── Custom Tooltip ── */

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
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
      <p className="text-sm font-semibold text-white">{label}</p>
      <div className="mt-2 space-y-1">
        {payload.map((p) => (
          <div key={p.name} className="flex items-center justify-between gap-4 text-xs">
            <span className="text-zinc-400">{p.name}</span>
            <span className="font-mono font-medium text-zinc-200">{p.value.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Action Item Card ── */

function ActionItem({ row }: { row: SectorRow }) {
  const isIncrease = row.change > 0;
  return (
    <div
      className={`flex items-center gap-3 rounded-xl border px-4 py-3 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)] ${
        isIncrease
          ? "border-emerald-400/20 bg-emerald-500/5"
          : "border-red-400/20 bg-red-500/5"
      }`}
    >
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isIncrease ? "bg-emerald-400/10" : "bg-red-400/10"
        }`}
      >
        {isIncrease ? (
          <TrendingUp className="h-4 w-4 text-emerald-400" />
        ) : (
          <Zap className="h-4 w-4 text-red-400" />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-white">
          {isIncrease ? "Increase" : "Decrease"} {row.sector}
        </p>
        <p className="text-[10px] text-zinc-600">
          {row.currentWeight.toFixed(1)}% &rarr; {row.recommendedWeight.toFixed(1)}%
        </p>
      </div>
      <span
        className={`text-sm font-mono font-bold ${
          isIncrease ? "text-emerald-400" : "text-red-400"
        }`}
      >
        {row.change >= 0 ? "+" : ""}
        {row.change.toFixed(1)}%
      </span>
    </div>
  );
}

/* ── Main Page ── */

export default function SectorRotationPage() {
  const { data: portfolio, isLoading: loadingPortfolio } = usePortfolio();
  const { data: analytics, isLoading: loadingAnalytics } = useAnalytics();
  const { data: vixData, isLoading: loadingVix } = useVixStrategy();
  const { data: sectorData } = useSectors();

  const positions = portfolio?.positions ?? [];
  const vix = vixData?.vix ?? 20;
  const regime = getRegime(vix);
  const meta = REGIME_META[regime];
  const RegimeIcon = meta.icon;

  const rows = useMemo(
    () => buildSectorRows(positions, regime, sectorData),
    [positions, regime, sectorData],
  );

  const actionItems = useMemo(
    () => rows.filter((r) => Math.abs(r.change) >= 1),
    [rows],
  );

  const chartData = useMemo(
    () =>
      rows.map((r) => ({
        sector: r.sector.replace("Communication Services", "Comm. Svcs").replace("Consumer Cyclical", "Cons. Cycl.").replace("Consumer Defensive", "Cons. Def.").replace("Financial Services", "Financials").replace("Basic Materials", "Materials"),
        Current: parseFloat(r.currentWeight.toFixed(1)),
        Recommended: parseFloat(r.recommendedWeight.toFixed(1)),
      })),
    [rows],
  );

  const isLoading = loadingPortfolio || loadingAnalytics || loadingVix;

  /* ── Loading ── */

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
        <span className="text-zinc-600 text-[12px]">Loading...</span>
      </div>
    );
  }

  /* ── Empty ── */

  if (!positions.length) {
    return (
      <div className="glass-surface rounded-2xl py-12 text-center">
        <RotateCcw className="mx-auto h-10 w-10 text-zinc-600" />
        <p className="mt-4 text-zinc-400">Add positions to see sector rotation recommendations.</p>
      </div>
    );
  }

  /* ── Render ── */

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Sector Rotation
          </h1>
          <p className="mt-1 text-[13px] text-zinc-600">
            VIX-based sector allocation recommendations for your portfolio.
          </p>
        </div>
        <div className={`flex items-center gap-2 glass-surface rounded-xl text-zinc-300 hover:text-white spring-transition border px-4 py-2 ${meta.bg}`}>
          <RegimeIcon className={`h-4 w-4 ${meta.color}`} />
          <span className={`text-[9px] font-bold ${meta.color}`}>
            {meta.label} Regime
          </span>
          <span className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
            VIX {vix.toFixed(1)}
          </span>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
          <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">VIX Level</p>
          <p className={`mt-1 text-2xl font-bold font-mono ${meta.color}`}>{vix.toFixed(1)}</p>
          {vixData && <p className="mt-0.5 text-[13px] text-zinc-600">20D avg: {vixData.vix_20d_avg.toFixed(1)}</p>}
        </div>
        <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
          <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Recommended Exposure</p>
          <p className="mt-1 text-2xl font-bold font-mono text-white">{vixData?.exposure ?? 100}%</p>
          <p className="mt-0.5 text-[13px] text-zinc-600">{vixData?.action ?? "Hold"}</p>
        </div>
        <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
          <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Sectors to Adjust</p>
          <p className="mt-1 text-2xl font-bold font-mono text-white">{actionItems.length}</p>
          <p className="mt-0.5 text-[13px] text-zinc-600">Require rebalancing</p>
        </div>
        <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
          <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Sector Coverage</p>
          <p className="mt-1 text-2xl font-bold font-mono text-white">
            {Object.keys(analytics?.sector_allocation ?? {}).length}
          </p>
          <p className="mt-0.5 text-[13px] text-zinc-600">of {SECTOR_TARGETS.length} sectors</p>
        </div>
      </div>

      {/* Chart: Current vs Recommended */}
      <div className="glass-surface rounded-xl p-6">
        <div className="mb-4 flex items-center gap-2">
          <RotateCcw className="h-5 w-5 text-cyan-400" />
          <h2 className="text-lg font-semibold text-white">
            Current vs Recommended Allocation
          </h2>
        </div>
        <div className="h-[400px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 8, right: 24, bottom: 8, left: 0 }}
            >
              <XAxis
                type="number"
                tick={{ fill: "#a1a1aa", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `${v}%`}
              />
              <YAxis
                type="category"
                dataKey="sector"
                tick={{ fill: "#a1a1aa", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={100}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
              <Legend
                wrapperStyle={{ fontSize: 12, color: "#a1a1aa" }}
              />
              <Bar dataKey="Current" fill="#60a5fa" radius={[0, 4, 4, 0]} barSize={12} />
              <Bar dataKey="Recommended" fill="#34d399" radius={[0, 4, 4, 0]} barSize={12} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Action Items + Performance Grid */}
      <div className="grid gap-4 lg:grid-cols-5">
        {/* Action Items */}
        <div className="glass-surface rounded-xl p-6 lg:col-span-2">
          <div className="mb-4 flex items-center gap-2">
            <Zap className="h-5 w-5 text-amber-400" />
            <h2 className="text-lg font-semibold text-white">
              Action Items
            </h2>
          </div>
          {actionItems.length === 0 ? (
            <div className="glass-surface rounded-2xl py-12 text-center">
              <p className="text-sm text-zinc-400">Portfolio is well-balanced for the current regime.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {actionItems.map((r) => (
                <ActionItem key={r.sector} row={r} />
              ))}
            </div>
          )}
        </div>

        {/* Sector Performance Table */}
        <div className="glass-surface rounded-xl p-6 lg:col-span-3">
          <div className="mb-4 flex items-center gap-2">
            <Shield className="h-5 w-5 text-cyan-400" />
            <h2 className="text-lg font-semibold text-white">
              Sector Allocation Detail
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-white/[0.06] text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
                  <th className="pb-3 pr-4">Sector</th>
                  <th className="pb-3 pr-4 text-right">Current</th>
                  <th className="pb-3 pr-4 text-right">Target</th>
                  <th className="pb-3 pr-4 text-right">Change</th>
                  {sectorData && <th className="pb-3 pr-4 text-right">Price</th>}
                  {sectorData && <th className="pb-3 text-right">Day Chg</th>}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    key={r.sector}
                    className="border-b border-white/[0.04] last:border-0 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]"
                  >
                    <td className="py-3 pr-4 text-zinc-300">{r.sector}</td>
                    <td className="py-3 pr-4 text-right font-mono text-zinc-300">
                      {r.currentWeight.toFixed(1)}%
                    </td>
                    <td className="py-3 pr-4 text-right font-mono text-zinc-300">
                      {r.recommendedWeight.toFixed(1)}%
                    </td>
                    <td className="py-3 pr-4 text-right">
                      <span
                        className={`inline-flex items-center rounded-md px-2.5 py-1 text-[9px] font-bold ${
                          Math.abs(r.change) < 1
                            ? "bg-zinc-800 text-zinc-400"
                            : r.change > 0
                            ? "bg-emerald-400/10 text-emerald-400"
                            : "bg-red-400/10 text-red-400"
                        }`}
                      >
                        {r.change >= 0 ? "+" : ""}
                        {r.change.toFixed(1)}%
                      </span>
                    </td>
                    {sectorData && (
                      <td className="py-3 pr-4 text-right font-mono text-zinc-300">
                        {r.livePrice != null ? `$${r.livePrice.toFixed(2)}` : "—"}
                      </td>
                    )}
                    {sectorData && (
                      <td className="py-3 text-right">
                        {r.liveChangePct != null ? (
                          <span className={`font-mono ${r.liveChangePct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                            {fmtPct(r.liveChangePct)}
                          </span>
                        ) : (
                          <span className="text-zinc-600">—</span>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
