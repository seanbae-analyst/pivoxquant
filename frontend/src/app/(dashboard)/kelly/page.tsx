"use client";

import { useState, useMemo } from "react";
import { usePortfolio, useAnalytics } from "@/lib/hooks";
import { fmtUsd, fmtPct } from "@/lib/format";
import { Calculator, Target, Shield, AlertTriangle } from "lucide-react";

/* ── Kelly math ── */

function kellyPct(winRate: number, rewardRisk: number): number {
  if (rewardRisk <= 0) return 0;
  const k = winRate - (1 - winRate) / rewardRisk;
  return Math.max(0, k);
}

/* ── Page ── */

export default function KellyPage() {
  const { data: portfolio } = usePortfolio();
  const { data: analytics } = useAnalytics();

  /* Interactive calculator inputs */
  const [customWin, setCustomWin] = useState(55);
  const [customR, setCustomR] = useState(2.0);

  const customKelly = kellyPct(customWin / 100, customR) * 100;
  const customHalfKelly = customKelly / 2;

  /* Position-level Kelly calculations */
  const positionData = useMemo(() => {
    if (!portfolio?.positions) return [];
    return portfolio.positions.map((pos) => {
      const w = Math.min(Math.max(pos.score / 100, 0.01), 0.99);
      const r = pos.tp_pct && pos.sl_pct && pos.sl_pct !== 0
        ? Math.abs(pos.tp_pct / pos.sl_pct)
        : 2.0;
      const k = kellyPct(w, r);
      const halfK = k / 2;
      return { ...pos, winRate: w, rRatio: r, kelly: k, halfKelly: halfK };
    });
  }, [portfolio]);

  const availableCapital = portfolio?.available_capital ?? 0;
  const totalValue = analytics?.total_value ?? 0;
  const totalCapital = totalValue + availableCapital;

  /* Summary stats */
  const summary = useMemo(() => {
    if (!positionData.length || totalCapital <= 0)
      return { optimalPct: 0, currentPct: 0, diff: 0 };

    const totalOptimalDollars = positionData.reduce(
      (sum, p) => sum + p.halfKelly * totalCapital,
      0,
    );
    const optimalPct = (totalOptimalDollars / totalCapital) * 100;
    const currentPct = analytics?.invested_pct ?? 0;
    return {
      optimalPct: Math.min(optimalPct, 100),
      currentPct,
      diff: currentPct - Math.min(optimalPct, 100),
    };
  }, [positionData, totalCapital, analytics]);

  /* Loading */
  if (!portfolio || !analytics) {
    return (
      <div className="flex items-center justify-center py-32">
        <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse mr-2" />
        <span className="text-slate-400 text-[12px]">Loading...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* ── Header ── */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Kelly Criterion Calculator
        </h1>
        <p className="mt-1 text-[13px] text-slate-400">
          Optimal position sizing based on edge and reward/risk ratio
        </p>
      </div>

      {/* ── Summary Cards ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <SummaryCard
          icon={<Target className="h-5 w-5 text-sky-600" />}
          label="Kelly-Optimal Allocation"
          value={`${summary.optimalPct.toFixed(1)}%`}
          sublabel={`of ${fmtUsd(totalCapital)} total capital`}
        />
        <SummaryCard
          icon={<Shield className="h-5 w-5 text-emerald-600" />}
          label="Current Allocation"
          value={`${summary.currentPct.toFixed(1)}%`}
          sublabel={`${fmtUsd(totalValue)} invested`}
        />
        <SummaryCard
          icon={
            <AlertTriangle
              className={`h-5 w-5 ${
                Math.abs(summary.diff) < 5
                  ? "text-emerald-600"
                  : "text-amber-500"
              }`}
            />
          }
          label="Deviation"
          value={`${summary.diff >= 0 ? "+" : ""}${summary.diff.toFixed(1)}%`}
          sublabel={
            summary.diff > 5
              ? "Over-invested vs Kelly optimal"
              : summary.diff < -5
                ? "Under-invested vs Kelly optimal"
                : "Within Kelly optimal range"
          }
          valueColor={
            Math.abs(summary.diff) < 5 ? "text-emerald-600" : "text-amber-500"
          }
        />
      </div>

      {/* ── Risk Meter ── */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">
          Portfolio Risk Meter
        </h2>
        <RiskMeter
          currentPct={summary.currentPct}
          optimalPct={summary.optimalPct}
        />
      </div>

      {/* ── Interactive Calculator ── */}
      <div className="glass-surface rounded-xl p-6">
        <div className="mb-4 flex items-center gap-2">
          <Calculator className="h-5 w-5 text-sky-600" />
          <h2 className="text-lg font-semibold text-slate-900">
            Custom Calculator
          </h2>
        </div>
        <p className="mb-6 text-[13px] text-slate-400">
          Kelly % = W - (1 - W) / R where W = win rate, R = avg win / avg loss
        </p>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {/* Win Rate Input */}
          <div>
            <label className="mb-1.5 block text-[10px] font-semibold text-slate-400 uppercase tracking-[0.1em]">
              Win Rate (%)
            </label>
            <input
              type="number"
              min={1}
              max={99}
              step={1}
              value={customWin}
              onChange={(e) =>
                setCustomWin(
                  Math.min(99, Math.max(1, Number(e.target.value) || 1)),
                )
              }
              className="w-full rounded-xl bg-slate-50 border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-sky-500/50"
            />
            <p className="mt-1 text-[10px] text-slate-400">
              Probability of a winning trade (1-99)
            </p>
          </div>

          {/* Reward/Risk Ratio Input */}
          <div>
            <label className="mb-1.5 block text-[10px] font-semibold text-slate-400 uppercase tracking-[0.1em]">
              Reward / Risk Ratio
            </label>
            <input
              type="number"
              min={0.1}
              max={20}
              step={0.1}
              value={customR}
              onChange={(e) =>
                setCustomR(
                  Math.min(20, Math.max(0.1, Number(e.target.value) || 0.1)),
                )
              }
              className="w-full rounded-xl bg-slate-50 border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-sky-500/50"
            />
            <p className="mt-1 text-[10px] text-slate-400">
              Average win size / Average loss size
            </p>
          </div>

          {/* Result */}
          <div className="flex flex-col justify-center rounded-xl bg-slate-50 border border-slate-200 px-4 py-3">
            <div className="flex items-baseline justify-between">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-[0.1em]">Full Kelly</span>
              <span className="text-xl font-bold font-mono text-sky-600">
                {customKelly.toFixed(1)}%
              </span>
            </div>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-[0.1em]">Half Kelly (rec.)</span>
              <span className="text-lg font-semibold font-mono text-emerald-600">
                {customHalfKelly.toFixed(1)}%
              </span>
            </div>
            {totalCapital > 0 && (
              <div className="mt-2 border-t border-slate-200 pt-2">
                <div className="flex items-baseline justify-between">
                  <span className="text-[10px] text-slate-400">
                    Suggested size
                  </span>
                  <span className="text-sm font-medium font-mono text-slate-700">
                    {fmtUsd((customHalfKelly / 100) * totalCapital)}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Position Sizing Table ── */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-1 text-lg font-semibold text-slate-900">
          Position Sizing Table
        </h2>
        <p className="mb-6 text-[13px] text-slate-400">
          Kelly-optimal sizing for each position based on score and TP/SL ratio
        </p>

        {positionData.length === 0 ? (
          <div className="glass-surface rounded-2xl py-12 text-center">
            <p className="text-sm text-slate-500">
              No positions found. Add positions to see Kelly sizing.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-[10px] font-semibold text-slate-400 uppercase tracking-[0.1em]">
                  <th className="pb-3 pr-4">Ticker</th>
                  <th className="pb-3 pr-4 text-right">Score</th>
                  <th className="pb-3 pr-4 text-right">
                    Win Rate
                  </th>
                  <th className="pb-3 pr-4 text-right">R Ratio</th>
                  <th className="pb-3 pr-4 text-right">
                    Kelly %
                  </th>
                  <th className="pb-3 pr-4 text-right">
                    Half Kelly %
                  </th>
                  <th className="pb-3 text-right">
                    Recommended $
                  </th>
                </tr>
              </thead>
              <tbody>
                {positionData
                  .sort((a, b) => b.halfKelly - a.halfKelly)
                  .map((p) => (
                    <tr
                      key={p.id}
                      className="border-b border-slate-100 last:border-0 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.06)]"
                    >
                      <td className="py-3 pr-4">
                        <div>
                          <span className="font-medium text-slate-900">
                            {p.ticker}
                          </span>
                          <p className="text-[10px] text-slate-400 truncate max-w-[120px]">
                            {p.name}
                          </p>
                        </div>
                      </td>
                      <td className="py-3 pr-4 text-right">
                        <span
                          className={`font-mono font-medium ${
                            p.score >= 70
                              ? "text-emerald-600"
                              : p.score >= 45
                                ? "text-amber-500"
                                : "text-red-600"
                          }`}
                        >
                          {p.score}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-right font-mono text-slate-700">
                        {(p.winRate * 100).toFixed(0)}%
                      </td>
                      <td className="py-3 pr-4 text-right font-mono text-slate-700">
                        {p.rRatio.toFixed(1)}
                      </td>
                      <td className="py-3 pr-4 text-right font-mono text-sky-600 font-medium">
                        {(p.kelly * 100).toFixed(1)}%
                      </td>
                      <td className="py-3 pr-4 text-right font-mono text-emerald-600 font-medium">
                        {(p.halfKelly * 100).toFixed(1)}%
                      </td>
                      <td className="py-3 text-right font-mono text-slate-700">
                        {fmtUsd(p.halfKelly * totalCapital)}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Disclaimer ── */}
      <div className="glass-surface rounded-xl p-6">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">
          About Kelly Criterion
        </h2>
        <div className="space-y-2 text-xs text-slate-500">
          <p>
            The Kelly Criterion calculates the theoretically optimal fraction of
            capital to risk on a single bet. Formula: Kelly % = W - (1 - W) / R
            where W is win probability and R is the ratio of average win to
            average loss.
          </p>
          <p>
            Half-Kelly (50% of full Kelly) is widely recommended in practice to
            reduce volatility while retaining most of the growth benefit. Full
            Kelly can lead to extreme drawdowns in real-world conditions.
          </p>
          <p>
            Position scores are used as a proxy for win probability (score / 100)
            and the TP/SL percentage ratio is used as the reward/risk ratio R. If
            TP or SL is not set, a default R of 2.0 is used.
          </p>
          <p className="text-slate-400">
            This is for educational and analytical purposes only. Past
            performance does not guarantee future results.
          </p>
        </div>
      </div>
    </div>
  );
}

/* ── Sub-components ── */

function SummaryCard({
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

function RiskMeter({
  currentPct,
  optimalPct,
}: {
  currentPct: number;
  optimalPct: number;
}) {
  const maxPct = Math.max(currentPct, optimalPct, 100);
  const currentPos = Math.min((currentPct / maxPct) * 100, 100);
  const optimalPos = Math.min((optimalPct / maxPct) * 100, 100);

  const diff = currentPct - optimalPct;
  const status =
    Math.abs(diff) < 5
      ? { label: "Well-Balanced", color: "text-emerald-600" }
      : diff > 0
        ? { label: "Over-Allocated", color: "text-amber-500" }
        : { label: "Under-Allocated", color: "text-sky-600" };

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className={`text-sm font-medium ${status.color}`}>
          {status.label}
        </span>
        <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-[0.1em]">
          {Math.abs(diff).toFixed(1)}% {diff >= 0 ? "above" : "below"} optimal
        </span>
      </div>

      {/* Gauge bar */}
      <div className="relative h-6 w-full rounded-full bg-slate-100 overflow-hidden">
        {/* Optimal zone highlight */}
        <div
          className="absolute inset-y-0 bg-emerald-100 border-l border-r border-emerald-300"
          style={{
            left: `${Math.max(optimalPos - 3, 0)}%`,
            width: `6%`,
          }}
        />
        {/* Current allocation bar */}
        <div
          className={`absolute inset-y-0 left-0 rounded-full transition-all duration-500 ${
            Math.abs(diff) < 5
              ? "bg-emerald-200"
              : diff > 0
                ? "bg-amber-200"
                : "bg-sky-200"
          }`}
          style={{ width: `${currentPos}%` }}
        />
        {/* Optimal marker */}
        <div
          className="absolute top-0 h-full w-0.5 bg-emerald-600"
          style={{ left: `${optimalPos}%` }}
        />
        {/* Current marker */}
        <div
          className={`absolute top-0 h-full w-0.5 ${
            Math.abs(diff) < 5 ? "bg-slate-900" : diff > 0 ? "bg-amber-500" : "bg-sky-600"
          }`}
          style={{ left: `${currentPos}%` }}
        />
      </div>

      {/* Labels */}
      <div className="mt-2 flex items-center justify-between text-[10px]">
        <span className="text-slate-400">0%</span>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full bg-emerald-600" />
            <span className="text-slate-500">
              Optimal ({optimalPct.toFixed(0)}%)
            </span>
          </span>
          <span className="flex items-center gap-1">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                Math.abs(diff) < 5
                  ? "bg-slate-900"
                  : diff > 0
                    ? "bg-amber-500"
                    : "bg-sky-600"
              }`}
            />
            <span className="text-slate-500">
              Current ({currentPct.toFixed(0)}%)
            </span>
          </span>
        </div>
        <span className="text-slate-400">100%</span>
      </div>
    </div>
  );
}
