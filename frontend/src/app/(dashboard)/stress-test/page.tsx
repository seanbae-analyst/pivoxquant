"use client";

import { useState, useMemo } from "react";
import { usePortfolio, useAnalytics } from "@/lib/hooks";
import type { Position } from "@/lib/types";
import { fmtUsd, fmtPct } from "@/lib/format";
import { AlertTriangle, Shield, TrendingDown, Zap } from "lucide-react";
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

/* ── Scenario definitions ── */

interface Scenario {
  id: string;
  name: string;
  year: string;
  icon: React.ReactNode;
  description: string;
  sectorDrawdowns: Record<string, number>;
  defaultDrawdown: number;
  recoveryMonths: number;
}

const SCENARIOS: Scenario[] = [
  {
    id: "2008",
    name: "2008 Financial Crisis",
    year: "2008",
    icon: <AlertTriangle className="h-5 w-5" />,
    description:
      "Global banking collapse triggered by subprime mortgage crisis. Severe impact on financials and broad equity markets.",
    sectorDrawdowns: {
      Finance: -55,
      "Financial Services": -55,
      Technology: -45,
      Energy: -40,
      Healthcare: -20,
    },
    defaultDrawdown: -35,
    recoveryMonths: 48,
  },
  {
    id: "2020",
    name: "2020 COVID Crash",
    year: "2020",
    icon: <Shield className="h-5 w-5" />,
    description:
      "Pandemic-driven market shock with fastest bear market in history. Energy and consumer sectors hit hardest.",
    sectorDrawdowns: {
      Energy: -50,
      "Consumer Cyclical": -35,
      "Consumer Defensive": -35,
      Technology: -25,
      Healthcare: -10,
    },
    defaultDrawdown: -30,
    recoveryMonths: 5,
  },
  {
    id: "2022",
    name: "2022 Rate Hike",
    year: "2022",
    icon: <TrendingDown className="h-5 w-5" />,
    description:
      "Aggressive Fed tightening crushed growth stocks and bonds simultaneously. Energy outperformed.",
    sectorDrawdowns: {
      Technology: -35,
      "Consumer Cyclical": -25,
      "Consumer Defensive": -25,
      Finance: -15,
      "Financial Services": -15,
      Energy: 10,
    },
    defaultDrawdown: -20,
    recoveryMonths: 18,
  },
  {
    id: "dotcom",
    name: "Dot-com Bubble",
    year: "2000",
    icon: <Zap className="h-5 w-5" />,
    description:
      "Tech valuations imploded after speculative excess. Nasdaq lost 78% from peak to trough over 2.5 years.",
    sectorDrawdowns: {
      Technology: -78,
      Finance: -20,
      "Financial Services": -20,
      Healthcare: -10,
    },
    defaultDrawdown: -15,
    recoveryMonths: 84,
  },
];

/* ── Helpers ── */

function getSectorDrawdown(
  sector: string,
  scenario: Scenario,
): number {
  // Try exact match first, then partial
  if (scenario.sectorDrawdowns[sector] !== undefined) {
    return scenario.sectorDrawdowns[sector];
  }
  for (const [key, val] of Object.entries(scenario.sectorDrawdowns)) {
    if (sector.toLowerCase().includes(key.toLowerCase()) ||
        key.toLowerCase().includes(sector.toLowerCase())) {
      return val;
    }
  }
  return scenario.defaultDrawdown;
}

interface PositionImpact {
  ticker: string;
  name: string;
  sector: string;
  currentValue: number;
  drawdownPct: number;
  estimatedLoss: number;
  postStressValue: number;
}

/* ── Custom tooltip ── */

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { value: number; payload: { ticker: string; estimatedLoss: number } }[];
  label?: string;
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
      <p className="text-sm font-medium text-white">{d.ticker}</p>
      <p className="text-sm text-red-400">{fmtUsd(d.estimatedLoss)}</p>
    </div>
  );
}

/* ── Page ── */

export default function StressTestPage() {
  const { data: portfolio, isLoading: pLoading } = usePortfolio();
  const { data: analytics, isLoading: aLoading } = useAnalytics();

  const [selectedId, setSelectedId] = useState<string>("2008");
  const [customDrawdown, setCustomDrawdown] = useState<number>(-30);

  const isCustom = selectedId === "custom";
  const activeScenario: Scenario | null = isCustom
    ? null
    : SCENARIOS.find((s) => s.id === selectedId) ?? null;

  /* ── Calculate impacts ── */

  const impacts = useMemo<PositionImpact[]>(() => {
    if (!portfolio?.positions) return [];
    return portfolio.positions.map((pos: Position) => {
      const drawdownPct = isCustom
        ? customDrawdown
        : activeScenario
          ? getSectorDrawdown(pos.sector, activeScenario)
          : -30;
      const estimatedLoss = pos.market_value * (drawdownPct / 100);
      return {
        ticker: pos.ticker,
        name: pos.name,
        sector: pos.sector,
        currentValue: pos.market_value,
        drawdownPct,
        estimatedLoss,
        postStressValue: pos.market_value + estimatedLoss,
      };
    });
  }, [portfolio, selectedId, customDrawdown, isCustom, activeScenario]);

  const totalLoss = impacts.reduce((sum, p) => sum + p.estimatedLoss, 0);
  const totalValue = analytics?.total_value ?? portfolio?.total_value_usd ?? 0;
  const portfolioDrawdownPct =
    totalValue > 0 ? (totalLoss / totalValue) * 100 : 0;
  const recoveryMonths = isCustom
    ? Math.round(Math.abs(customDrawdown) * 1.5)
    : activeScenario?.recoveryMonths ?? 0;

  /* ── Chart data ── */

  const chartData = useMemo(() => {
    return impacts
      .filter((p) => p.estimatedLoss !== 0)
      .sort((a, b) => a.estimatedLoss - b.estimatedLoss)
      .slice(0, 15);
  }, [impacts]);

  /* ── Loading state ── */

  if (pLoading || aLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
        <span className="text-zinc-600 text-[12px]">Loading...</span>
      </div>
    );
  }

  if (!portfolio?.positions?.length) {
    return (
      <div className="glass-surface rounded-2xl py-12 text-center">
        <AlertTriangle className="mx-auto h-10 w-10 text-zinc-500" />
        <p className="mt-4 text-zinc-400">
          No positions found. Add positions to run stress tests.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-4 px-4 py-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">Stress Test</h1>
        <p className="mt-1 text-[13px] text-zinc-600">
          Simulate historical crisis scenarios on your current portfolio
        </p>
      </div>

      {/* ── Scenario selector cards ── */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {SCENARIOS.map((s) => (
          <button
            key={s.id}
            onClick={() => setSelectedId(s.id)}
            className={`glass-surface rounded-xl p-4 text-left spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)] ${
              selectedId === s.id
                ? "border border-cyan-400/60 bg-cyan-400/10"
                : ""
            }`}
          >
            <div className="mb-2 flex items-center gap-2">
              <span
                className={
                  selectedId === s.id ? "text-cyan-400" : "text-zinc-500"
                }
              >
                {s.icon}
              </span>
              <span className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">{s.year}</span>
            </div>
            <p className="text-sm font-semibold text-white">{s.name}</p>
          </button>
        ))}

        {/* Custom scenario card */}
        <button
          onClick={() => setSelectedId("custom")}
          className={`glass-surface rounded-xl p-4 text-left spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)] ${
            isCustom
              ? "border border-cyan-400/60 bg-cyan-400/10"
              : ""
          }`}
        >
          <div className="mb-2 flex items-center gap-2">
            <span className={isCustom ? "text-cyan-400" : "text-zinc-500"}>
              <TrendingDown className="h-5 w-5" />
            </span>
            <span className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Custom</span>
          </div>
          <p className="text-sm font-semibold text-white">Custom Scenario</p>
        </button>
      </div>

      {/* ── Scenario description ── */}
      {activeScenario && (
        <p className="text-sm leading-relaxed text-zinc-400">
          {activeScenario.description}
        </p>
      )}

      {/* ── Custom slider ── */}
      {isCustom && (
        <div className="glass-surface rounded-xl p-5">
          <label className="mb-3 block text-sm font-medium text-zinc-300">
            Uniform Drawdown: {customDrawdown}%
          </label>
          <input
            type="range"
            min={-90}
            max={0}
            value={customDrawdown}
            onChange={(e) => setCustomDrawdown(Number(e.target.value))}
            className="w-full accent-cyan-400"
          />
          <div className="mt-2 flex justify-between text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
            <span>-90%</span>
            <span>0%</span>
          </div>
        </div>
      )}

      {/* ── Impact summary ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
          <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
            Estimated Loss
          </p>
          <p className="mt-2 text-2xl font-bold font-mono text-red-400">
            {fmtUsd(Math.abs(totalLoss))}
          </p>
        </div>

        <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
          <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
            Portfolio Drawdown
          </p>
          <p className="mt-2 text-2xl font-bold font-mono text-red-400">
            {fmtPct(portfolioDrawdownPct)}
          </p>
        </div>

        <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
          <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
            Est. Recovery Time
          </p>
          <p className="mt-2 text-2xl font-bold font-mono text-zinc-300">
            ~{recoveryMonths} months
          </p>
        </div>
      </div>

      {/* ── Bar chart ── */}
      {chartData.length > 0 && (
        <div className="glass-surface rounded-xl p-5">
          <h2 className="mb-4 text-sm font-semibold text-white">
            Per-Position Impact
          </h2>
          <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 36)}>
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 0, right: 20, left: 60, bottom: 0 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.06)"
                horizontal={false}
              />
              <XAxis
                type="number"
                tickFormatter={(v: number) => fmtUsd(Math.abs(v))}
                tick={{ fill: "#71717a", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                dataKey="ticker"
                type="category"
                tick={{ fill: "#d4d4d8", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                width={55}
              />
              <Tooltip
                content={<ChartTooltip />}
                cursor={{ fill: "rgba(255,255,255,0.03)" }}
              />
              <Bar dataKey="estimatedLoss" radius={[0, 4, 4, 0]}>
                {chartData.map((entry) => (
                  <Cell
                    key={entry.ticker}
                    fill={entry.estimatedLoss < 0 ? "#f87171" : "#34d399"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── Position table ── */}
      <div className="glass-surface rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.06] text-left text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">
                <th className="px-5 py-3">Ticker</th>
                <th className="px-5 py-3">Sector</th>
                <th className="px-5 py-3 text-right">Current Value</th>
                <th className="px-5 py-3 text-right">Sector Impact</th>
                <th className="px-5 py-3 text-right">Est. Loss</th>
                <th className="px-5 py-3 text-right">Post-Stress Value</th>
              </tr>
            </thead>
            <tbody>
              {impacts.map((p) => (
                <tr
                  key={p.ticker}
                  className="border-b border-white/[0.06] last:border-0 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)] hover:bg-white/[0.02]"
                >
                  <td className="px-5 py-3">
                    <span className="font-medium text-white">{p.ticker}</span>
                    <span className="ml-2 hidden text-zinc-500 sm:inline">
                      {p.name}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-zinc-400">{p.sector}</td>
                  <td className="px-5 py-3 text-right font-mono text-zinc-300">
                    {fmtUsd(p.currentValue)}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <span
                      className={`font-mono ${
                        p.drawdownPct > 0
                          ? "text-emerald-400"
                          : p.drawdownPct < 0
                            ? "text-red-400"
                            : "text-zinc-500"
                      }`}
                    >
                      {p.drawdownPct > 0 ? "+" : ""}
                      {p.drawdownPct}%
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right">
                    <span
                      className={`font-mono ${
                        p.estimatedLoss >= 0 ? "text-emerald-400" : "text-red-400"
                      }`}
                    >
                      {p.estimatedLoss >= 0 ? "+" : "-"}
                      {fmtUsd(Math.abs(p.estimatedLoss))}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right font-mono text-zinc-300">
                    {fmtUsd(p.postStressValue)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
