"use client";

import { useMemo } from "react";
import { usePortfolio } from "@/lib/hooks";
import type { Position } from "@/lib/types";
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
} from "recharts";
import { Target, TrendingUp, Shield, Gem, Scale } from "lucide-react";

/* ── Types ── */

interface FactorScore {
  factor: string;
  score: number;
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  color: string;
  description: string;
}

interface RadarDatum {
  factor: string;
  score: number;
}

/* ── Factor Calculation ── */

function calcFactors(positions: Position[]): FactorScore[] {
  if (!positions.length) {
    return [
      { factor: "Momentum", score: 0, icon: TrendingUp, color: "#22d3ee", description: "Average P&L across positions. High momentum means your holdings are trending upward." },
      { factor: "Value", score: 0, icon: Gem, color: "#a78bfa", description: "Proportion of low-score positions (score < 50). These may represent undervalued opportunities." },
      { factor: "Growth", score: 0, icon: Target, color: "#34d399", description: "Concentration in Tech and Healthcare sectors, typically associated with high-growth companies." },
      { factor: "Quality", score: 0, icon: Shield, color: "#fbbf24", description: "Average AI score of your holdings. Higher scores indicate stronger fundamentals and technicals." },
      { factor: "Size", score: 0, icon: Scale, color: "#f472b6", description: "Ratio of positions with above-average market value. Higher means large-cap tilted." },
    ];
  }

  /* Momentum: normalize avg pnl_pct from [-30, +30] to [0, 100] */
  const avgPnl = positions.reduce((s, p) => s + p.pnl_pct, 0) / positions.length;
  const momentum = Math.max(0, Math.min(100, ((avgPnl + 30) / 60) * 100));

  /* Value: fraction of positions with score < 50 */
  const lowScoreCount = positions.filter((p) => p.score < 50).length;
  const value = (lowScoreCount / positions.length) * 100;

  /* Growth: fraction of Tech + Healthcare positions */
  const growthSectors = new Set(["Technology", "Healthcare"]);
  const growthCount = positions.filter((p) => growthSectors.has(p.sector)).length;
  const growth = (growthCount / positions.length) * 100;

  /* Quality: average score (already 0-100) */
  const quality = positions.reduce((s, p) => s + p.score, 0) / positions.length;

  /* Size: fraction of positions with market_value > portfolio average */
  const avgMv = positions.reduce((s, p) => s + p.market_value, 0) / positions.length;
  const largeCount = positions.filter((p) => p.market_value > avgMv).length;
  const size = (largeCount / positions.length) * 100;

  return [
    { factor: "Momentum", score: Math.round(momentum), icon: TrendingUp, color: "#22d3ee", description: "Average P&L across positions. High momentum means your holdings are trending upward." },
    { factor: "Value", score: Math.round(value), icon: Gem, color: "#a78bfa", description: "Proportion of low-score positions (score < 50). These may represent undervalued opportunities." },
    { factor: "Growth", score: Math.round(growth), icon: Target, color: "#34d399", description: "Concentration in Tech and Healthcare sectors, typically associated with high-growth companies." },
    { factor: "Quality", score: Math.round(quality), icon: Shield, color: "#fbbf24", description: "Average AI score of your holdings. Higher scores indicate stronger fundamentals and technicals." },
    { factor: "Size", score: Math.round(size), icon: Scale, color: "#f472b6", description: "Ratio of positions with above-average market value. Higher means large-cap tilted." },
  ];
}

/* ── Tilt Analysis ── */

function getTiltSummary(factors: FactorScore[]): { tilt: string; recommendation: string } {
  const sorted = [...factors].sort((a, b) => b.score - a.score);
  const top = sorted.filter((f) => f.score > 0).slice(0, 2);
  const bottom = sorted.filter((f) => f.score < 60);
  const weakest = bottom.length ? bottom[bottom.length - 1] : sorted[sorted.length - 1];

  const tilt = top.length
    ? `Your portfolio is tilted toward ${top.map((f) => f.factor).join(" and ")}.`
    : "Your portfolio has no strong factor tilt.";

  const recommendation = weakest
    ? `Consider adding ${weakest.factor} exposure for better diversification.`
    : "Your portfolio is well-balanced across all factors.";

  return { tilt, recommendation };
}

/* ── Factor Card ── */

function FactorCard({ factor }: { factor: FactorScore }) {
  const Icon = factor.icon;
  return (
    <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
      <div className="flex items-center gap-3">
        <div
          className="flex h-10 w-10 items-center justify-center rounded-xl"
          style={{ backgroundColor: `${factor.color}15` }}
        >
          <Icon className="h-5 w-5" style={{ color: factor.color }} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-white">{factor.factor}</p>
          <p className="text-[13px] text-zinc-600">{factor.score}/100</p>
        </div>
        <span
          className="text-2xl font-bold font-mono"
          style={{ color: factor.color }}
        >
          {factor.score}
        </span>
      </div>

      {/* Bar */}
      <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-zinc-800">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{
            width: `${factor.score}%`,
            backgroundColor: factor.color,
          }}
        />
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-zinc-400">
        {factor.description}
      </p>
    </div>
  );
}

/* ── Main Page ── */

export default function FactorsPage() {
  const { data, isLoading } = usePortfolio();
  const positions = data?.positions ?? [];

  const factors = useMemo(() => calcFactors(positions), [positions]);
  const radarData: RadarDatum[] = useMemo(
    () => factors.map((f) => ({ factor: f.factor, score: f.score })),
    [factors],
  );
  const { tilt, recommendation } = useMemo(() => getTiltSummary(factors), [factors]);

  /* ── Loading ── */

  if (isLoading) {
    return (
      <div className="flex items-center py-32">
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
        <span className="text-zinc-600 text-[12px]">Loading...</span>
      </div>
    );
  }

  /* ── Empty ── */

  if (!positions.length) {
    return (
      <div className="glass-surface rounded-2xl py-12 text-center">
        <Target className="mx-auto h-10 w-10 text-zinc-700" />
        <p className="mt-3 text-[13px] text-zinc-600">No positions to analyze.</p>
      </div>
    );
  }

  /* ── Render ── */

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Factor Exposure Analysis
        </h1>
        <p className="mt-1 text-[13px] text-zinc-600">
          Understand your portfolio&apos;s style tilts across five key investment factors.
        </p>
      </div>

      {/* Tilt Summary */}
      <div className="glass-surface rounded-xl p-6">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-cyan-400/10">
            <Target className="h-5 w-5 text-cyan-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">Portfolio Tilt</h2>
            <p className="mt-1 text-sm text-zinc-300">{tilt}</p>
            <p className="mt-1 text-[13px] text-zinc-600">{recommendation}</p>
          </div>
        </div>
      </div>

      {/* Radar Chart */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-4 text-lg font-semibold text-white">
          Factor Radar
        </h2>
        <div className="h-[380px]">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart cx="50%" cy="50%" outerRadius="75%" data={radarData}>
              <PolarGrid stroke="#3f3f46" />
              <PolarAngleAxis
                dataKey="factor"
                tick={{ fill: "#a1a1aa", fontSize: 13, fontWeight: 500 }}
              />
              <Radar
                name="Exposure"
                dataKey="score"
                stroke="#22d3ee"
                fill="#22d3ee"
                fillOpacity={0.2}
                strokeWidth={2}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Factor Cards */}
      <div>
        <h2 className="mb-4 text-lg font-semibold text-white">
          Factor Breakdown
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {factors.map((f) => (
            <FactorCard key={f.factor} factor={f} />
          ))}
        </div>
      </div>
    </div>
  );
}
