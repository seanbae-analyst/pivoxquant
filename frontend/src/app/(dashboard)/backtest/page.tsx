"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FlaskConical, TrendingUp, Play } from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

/* ── Types ── */

interface EquityPoint {
  date: string;
  value: number;
}

interface BacktestResult {
  ticker: string;
  period: string;
  total_return: number;
  annual_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  profit_trades: number;
  loss_trades: number;
  avg_win: number;
  avg_loss: number;
  equity_curve: EquityPoint[];
}

/* ── Metric Card ── */

function MetricCard({
  label,
  value,
  color = "text-white",
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="glass-surface rounded-xl p-5 spring-transition transition-all duration-300 hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)]">
      <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-zinc-600">
        {label}
      </p>
      <p className={`mt-2 text-2xl font-bold font-mono ${color}`}>{value}</p>
    </div>
  );
}

/* ── Chart Tooltip ── */

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number }[];
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
      <p className="text-xs text-zinc-400">{label}</p>
      <p className="text-sm font-medium font-mono text-white">
        ${payload[0].value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </p>
    </div>
  );
}

/* ── Page ── */

export default function BacktestPage() {
  const [ticker, setTicker] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runBacktest() {
    const symbol = ticker.trim().toUpperCase();
    if (!symbol) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await apiFetch<BacktestResult>(
        `/api/backtest/${symbol}`,
      );
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Backtest failed. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  const pctColor = (v: number) =>
    v >= 0 ? "text-emerald-400" : "text-red-400";

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <FlaskConical className="h-7 w-7 text-cyan-400" />
          <h1 className="text-2xl font-bold tracking-tight text-white">Backtest</h1>
        </div>
        <p className="mt-1 text-[13px] text-zinc-600">
          Run a strategy backtest on any ticker to evaluate historical performance
        </p>
      </div>

      {/* Ticker Input */}
      <div className="flex items-center gap-3">
        <Input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runBacktest()}
          placeholder="Enter ticker symbol (e.g. AAPL)"
          className="h-11 max-w-xs bg-white/[0.03] border-white/[0.06] text-white placeholder:text-zinc-700 focus:border-cyan-500/30 rounded-xl"
        />
        <Button
          onClick={runBacktest}
          disabled={loading || !ticker.trim()}
          className="h-11 gap-2 bg-gradient-to-r from-cyan-500/10 to-emerald-500/10 text-cyan-400 border border-cyan-500/20 rounded-xl spring-transition disabled:opacity-50"
        >
          {loading ? (
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          Run Backtest
        </Button>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="flex min-h-[40vh] flex-col items-center justify-center gap-4">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
          <span className="text-zinc-600 text-[12px]">
            Running backtest for {ticker.trim().toUpperCase()}...
          </span>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <>
          {/* Result Header */}
          <div className="flex items-center gap-3">
            <TrendingUp className="h-5 w-5 text-cyan-400" />
            <h2 className="text-lg font-semibold text-white">
              {result.ticker} — {result.period}
            </h2>
          </div>

          {/* Metric Cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MetricCard
              label="Total Return"
              value={`${result.total_return >= 0 ? "+" : ""}${result.total_return.toFixed(2)}%`}
              color={pctColor(result.total_return)}
            />
            <MetricCard
              label="Annual Return"
              value={`${result.annual_return >= 0 ? "+" : ""}${result.annual_return.toFixed(2)}%`}
              color={pctColor(result.annual_return)}
            />
            <MetricCard
              label="Sharpe Ratio"
              value={result.sharpe_ratio.toFixed(2)}
              color={result.sharpe_ratio >= 1 ? "text-emerald-400" : result.sharpe_ratio >= 0 ? "text-zinc-300" : "text-red-400"}
            />
            <MetricCard
              label="Max Drawdown"
              value={`${result.max_drawdown.toFixed(2)}%`}
              color="text-red-400"
            />
            <MetricCard
              label="Win Rate"
              value={`${result.win_rate.toFixed(1)}%`}
              color={result.win_rate >= 50 ? "text-emerald-400" : "text-zinc-300"}
            />
            <MetricCard
              label="Total Trades"
              value={result.total_trades.toString()}
            />
            <MetricCard
              label="Avg Win"
              value={`+${result.avg_win.toFixed(2)}%`}
              color="text-emerald-400"
            />
            <MetricCard
              label="Avg Loss"
              value={`${result.avg_loss.toFixed(2)}%`}
              color="text-red-400"
            />
          </div>

          {/* Equity Curve Chart */}
          {result.equity_curve?.length > 0 && (
            <div className="glass-surface rounded-xl p-5">
              <h3 className="mb-4 text-sm font-semibold text-white">
                Equity Curve
              </h3>
              <ResponsiveContainer width="100%" height={350}>
                <AreaChart
                  data={result.equity_curve}
                  margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                >
                  <defs>
                    <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "#71717a", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    minTickGap={60}
                  />
                  <YAxis
                    tick={{ fill: "#71717a", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v: number) =>
                      `$${v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v.toFixed(0)}`
                    }
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#22d3ee"
                    strokeWidth={2}
                    fill="url(#eqGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Trade Summary */}
          <div className="glass-surface rounded-xl p-5">
            <h3 className="mb-4 text-sm font-semibold text-white">
              Trade Summary
            </h3>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div>
                <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Profit Trades</p>
                <p className="mt-1 text-lg font-bold font-mono text-emerald-400">
                  {result.profit_trades}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Loss Trades</p>
                <p className="mt-1 text-lg font-bold font-mono text-red-400">
                  {result.loss_trades}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Win / Loss Ratio</p>
                <p className="mt-1 text-lg font-bold font-mono text-zinc-300">
                  {result.loss_trades > 0
                    ? (result.profit_trades / result.loss_trades).toFixed(2)
                    : "N/A"}
                </p>
              </div>
              <div>
                <p className="text-[10px] font-semibold text-zinc-600 uppercase tracking-[0.1em]">Profit Factor</p>
                <p className="mt-1 text-lg font-bold font-mono text-zinc-300">
                  {result.avg_loss !== 0
                    ? Math.abs(
                        (result.avg_win * result.profit_trades) /
                          (result.avg_loss * result.loss_trades),
                      ).toFixed(2)
                    : "N/A"}
                </p>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Empty State */}
      {!result && !loading && !error && (
        <div className="glass-surface rounded-2xl py-12 text-center">
          <FlaskConical className="mx-auto h-12 w-12 text-zinc-600" />
          <p className="mt-3 text-[13px] text-zinc-600">
            Enter a ticker symbol and run a backtest to see results
          </p>
        </div>
      )}
    </div>
  );
}
