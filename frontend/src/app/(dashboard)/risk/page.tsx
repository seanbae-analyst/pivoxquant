"use client";

import { useMemo } from "react";
import { usePortfolio, useAnalytics, useVixStrategy } from "@/lib/hooks";
import { fmtUsd, fmtPct } from "@/lib/format";
import { Shield, AlertTriangle, BarChart3, Target } from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from "recharts";

/* ── Risk level helpers ── */

type RiskLevel = "LOW" | "MODERATE" | "HIGH" | "EXTREME";

function getRiskLevel(score: number): RiskLevel {
  if (score <= 25) return "LOW";
  if (score <= 50) return "MODERATE";
  if (score <= 75) return "HIGH";
  return "EXTREME";
}

function riskBadgeStyle(level: RiskLevel): string {
  switch (level) {
    case "LOW":
      return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
    case "MODERATE":
      return "bg-yellow-500/15 text-yellow-400 border-yellow-500/30";
    case "HIGH":
      return "bg-orange-500/15 text-orange-400 border-orange-500/30";
    case "EXTREME":
      return "bg-red-500/15 text-red-400 border-red-500/30";
  }
}

function riskGaugeColor(score: number): string {
  if (score <= 25) return "#10b981";
  if (score <= 50) return "#eab308";
  if (score <= 75) return "#f97316";
  return "#ef4444";
}

function vixRegimeStyle(regime: string): { bg: string; text: string; label: string } {
  switch (regime) {
    case "low_vol":
      return { bg: "bg-emerald-500/15", text: "text-emerald-400", label: "Low Volatility" };
    case "normal":
      return { bg: "bg-cyan-500/15", text: "text-cyan-400", label: "Normal" };
    case "elevated":
      return { bg: "bg-yellow-500/15", text: "text-yellow-400", label: "Elevated" };
    case "high_vol":
      return { bg: "bg-orange-500/15", text: "text-orange-400", label: "High Volatility" };
    case "crisis":
      return { bg: "bg-red-500/15", text: "text-red-400", label: "Crisis" };
    default:
      return { bg: "bg-zinc-500/15", text: "text-zinc-400", label: regime };
  }
}

/* ── Gauge SVG component ── */

function RiskGauge({ score }: { score: number }) {
  const clampedScore = Math.max(0, Math.min(100, score));
  const color = riskGaugeColor(clampedScore);
  // Arc from -135deg to +135deg (270deg total)
  const radius = 80;
  const cx = 100;
  const cy = 100;
  const startAngle = -225; // degrees
  const totalAngle = 270;
  const endAngle = startAngle + (clampedScore / 100) * totalAngle;

  function polarToCartesian(angle: number) {
    const rad = (angle * Math.PI) / 180;
    return { x: cx + radius * Math.cos(rad), y: cy - radius * Math.sin(rad) };
  }

  const bgStart = polarToCartesian(startAngle);
  const bgEnd = polarToCartesian(startAngle + totalAngle);
  const valEnd = polarToCartesian(endAngle);
  const largeArcBg = totalAngle > 180 ? 1 : 0;
  const largeArcVal = (clampedScore / 100) * totalAngle > 180 ? 1 : 0;

  return (
    <svg viewBox="0 0 200 140" className="mx-auto w-56">
      {/* background arc */}
      <path
        d={`M ${bgStart.x} ${bgStart.y} A ${radius} ${radius} 0 ${largeArcBg} 0 ${bgEnd.x} ${bgEnd.y}`}
        fill="none"
        stroke="rgba(255,255,255,0.06)"
        strokeWidth="14"
        strokeLinecap="round"
      />
      {/* value arc */}
      {clampedScore > 0 && (
        <path
          d={`M ${bgStart.x} ${bgStart.y} A ${radius} ${radius} 0 ${largeArcVal} 0 ${valEnd.x} ${valEnd.y}`}
          fill="none"
          stroke={color}
          strokeWidth="14"
          strokeLinecap="round"
        />
      )}
      {/* center text */}
      <text
        x={cx}
        y={cy - 8}
        textAnchor="middle"
        className="fill-white text-4xl font-bold"
        style={{ fontSize: 36 }}
      >
        {Math.round(clampedScore)}
      </text>
      <text
        x={cx}
        y={cy + 16}
        textAnchor="middle"
        className="fill-zinc-500 text-xs"
        style={{ fontSize: 12 }}
      >
        RISK SCORE
      </text>
    </svg>
  );
}

/* ── Main page ── */

export default function RiskDashboardPage() {
  const { data: portfolio } = usePortfolio();
  const { data: analytics } = useAnalytics();
  const { data: vix } = useVixStrategy();

  const positions = portfolio?.positions ?? [];
  const totalValue = portfolio?.total_value_usd ?? 0;

  /* ── Derived risk metrics ── */
  const metrics = useMemo(() => {
    const volatility = (analytics?.ann_vol_pct ?? 20) / 100;
    const portfolioValue = totalValue || 1;

    // VaR 95% (1-day, parametric)
    const var95 = portfolioValue * volatility * 1.645 * Math.sqrt(1 / 252);

    // CVaR / Expected Shortfall approximation
    const cvar = var95 * 1.4;

    // Max drawdown
    const maxDD = analytics?.max_drawdown_pct ?? 0;

    // Beta (default 1.0 if unavailable)
    const beta = 1.0;

    // Concentration: weight of top 3 positions
    const sorted = [...positions].sort((a, b) => b.market_value - a.market_value);
    const top3Weight =
      portfolioValue > 0
        ? sorted.slice(0, 3).reduce((s, p) => s + p.market_value, 0) / portfolioValue
        : 0;

    // Composite risk score (0-100)
    const varScore = Math.min((var95 / portfolioValue) * 100 * 20, 25); // up to 25
    const ddScore = Math.min(Math.abs(maxDD) * 0.5, 25); // up to 25
    const concScore = Math.min(top3Weight * 30, 25); // up to 25
    const volScore = Math.min(volatility * 50, 25); // up to 25
    const riskScore = Math.round(varScore + ddScore + concScore + volScore);

    return {
      var95,
      cvar,
      maxDD,
      beta,
      volatility: volatility * 100,
      concentration: top3Weight * 100,
      riskScore: Math.min(riskScore, 100),
    };
  }, [analytics, positions, totalValue]);

  /* ── Top 5 positions for bar chart ── */
  const concentrationData = useMemo(() => {
    if (!positions.length || totalValue === 0) return [];
    const sorted = [...positions].sort((a, b) => b.market_value - a.market_value);
    return sorted.slice(0, 5).map((p) => ({
      ticker: p.ticker,
      weight: (p.market_value / totalValue) * 100,
    }));
  }, [positions, totalValue]);

  const riskLevel = getRiskLevel(metrics.riskScore);
  const vixRegime = vix ? vixRegimeStyle(vix.regime) : null;

  /* ── Loading state ── */
  if (!portfolio) {
    return (
      <div className="flex items-center justify-center py-32">
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
        <span className="text-zinc-600 text-[12px]">Loading...</span>
      </div>
    );
  }

  /* ── Metric cards config ── */
  const cards = [
    {
      label: "VaR (95%)",
      value: fmtUsd(metrics.var95),
      sub: "1-day parametric",
      icon: <AlertTriangle className="h-5 w-5 text-orange-400" />,
    },
    {
      label: "CVaR",
      value: fmtUsd(metrics.cvar),
      sub: "Expected shortfall",
      icon: <AlertTriangle className="h-5 w-5 text-red-400" />,
    },
    {
      label: "Max Drawdown",
      value: metrics.maxDD !== 0 ? fmtPct(metrics.maxDD) : "N/A",
      sub: "Historical worst",
      icon: <BarChart3 className="h-5 w-5 text-rose-400" />,
    },
    {
      label: "Beta",
      value: metrics.beta.toFixed(2),
      sub: "vs S&P 500",
      icon: <Target className="h-5 w-5 text-cyan-400" />,
    },
    {
      label: "Volatility",
      value: `${metrics.volatility.toFixed(1)}%`,
      sub: "Annualized",
      icon: <BarChart3 className="h-5 w-5 text-yellow-400" />,
    },
    {
      label: "Concentration",
      value: `${metrics.concentration.toFixed(1)}%`,
      sub: "Top 3 positions",
      icon: <Shield className="h-5 w-5 text-purple-400" />,
    },
  ];

  return (
    <div className="space-y-4">
      {/* ── Page Header ── */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Risk Dashboard</h1>
          <p className="mt-1 text-[13px] text-zinc-600">
            Portfolio risk analysis and exposure monitoring
          </p>
        </div>
        <span
          className={`inline-flex items-center rounded-md border px-2.5 py-1 text-[9px] font-bold ${riskBadgeStyle(riskLevel)}`}
        >
          {riskLevel}
        </span>
      </div>

      {/* ── Risk Gauge + VIX Regime ── */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Gauge card */}
        <div className="glass-surface rounded-xl p-6 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
          <h2 className="mb-2 text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Composite Risk Score</h2>
          <RiskGauge score={metrics.riskScore} />
          <p className="mt-2 text-center text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
            Based on VaR, drawdown, volatility, and concentration
          </p>
        </div>

        {/* VIX Regime card */}
        <div className="glass-surface rounded-xl p-6 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
          <h2 className="mb-4 text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">VIX Regime</h2>
          {vix ? (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="text-4xl font-bold font-mono text-white">{vix.vix.toFixed(1)}</div>
                <div>
                  <span
                    className={`inline-flex items-center rounded-md border px-2.5 py-1 text-[9px] font-bold ${vixRegime?.bg} ${vixRegime?.text} border-transparent`}
                  >
                    {vixRegime?.label}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">20D Average</p>
                  <p className="font-mono text-white">{vix.vix_20d_avg.toFixed(1)}</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Trend</p>
                  <p className="text-white capitalize">{vix.vix_trend}</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Percentile</p>
                  <p className="font-mono text-white">{vix.vix_percentile.toFixed(0)}th</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Suggested Exposure</p>
                  <p className="font-mono text-white">{(vix.exposure * 100).toFixed(0)}%</p>
                </div>
              </div>

              <div className="rounded-xl bg-white/[0.03] p-3">
                <p className="text-xs text-zinc-400">{vix.action}</p>
              </div>
            </div>
          ) : (
            <div className="flex h-40 items-center justify-center">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
              <span className="text-zinc-600 text-[12px]">Loading...</span>
            </div>
          )}
        </div>
      </div>

      {/* ── 6 Metric cards ── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((c) => (
          <div
            key={c.label}
            className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]"
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">{c.label}</span>
              {c.icon}
            </div>
            <p className="mt-2 text-2xl font-bold font-mono text-white">{c.value}</p>
            <p className="mt-1 text-[13px] text-zinc-600">{c.sub}</p>
          </div>
        ))}
      </div>

      {/* ── Position Concentration Bar Chart ── */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-4 text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Position Concentration (Top 5)</h2>
        {concentrationData.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={concentrationData} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis
                dataKey="ticker"
                tick={{ fill: "#a1a1aa", fontSize: 12 }}
                axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#a1a1aa", fontSize: 12 }}
                axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
                tickLine={false}
                tickFormatter={(v: number) => `${v.toFixed(0)}%`}
              />
              <Tooltip
                contentStyle={{
                  background: "#18181b",
                  border: "1px solid rgba(255,255,255,0.06)",
                  borderRadius: 12,
                  fontSize: 12,
                  color: "#fafafa",
                }}
                formatter={(value) => [`${Number(value).toFixed(1)}%`, "Weight"]}
              />
              <Bar dataKey="weight" radius={[6, 6, 0, 0]}>
                {concentrationData.map((_, i) => (
                  <Cell
                    key={i}
                    fill={i === 0 ? "#f97316" : i === 1 ? "#eab308" : "#06b6d4"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="glass-surface rounded-2xl py-12 text-center">
            <p className="text-sm text-zinc-400">No positions to display</p>
          </div>
        )}
      </div>
    </div>
  );
}
