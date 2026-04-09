"use client";

import { usePortfolio, useAnalytics, useRealtimePrices } from "@/lib/hooks";
import { fmtUsd, fmtPct } from "@/lib/format";

export function TerminalMetrics() {
  const { data: portfolio } = usePortfolio();
  const { data: analytics } = useAnalytics();
  const { connected } = useRealtimePrices();

  const totalValue = portfolio?.total_value_usd ?? 0;
  const positions = portfolio?.positions ?? [];
  const buyCount = positions.filter((p) => p.signal === "BUY").length;
  const sellCount = positions.filter((p) => p.signal === "SELL").length;
  const avgPnl = positions.length
    ? positions.reduce((s, p) => s + p.pnl_pct, 0) / positions.length
    : 0;

  const metrics = [
    {
      label: "Portfolio Value",
      value: fmtUsd(totalValue),
      color: "text-white",
      dotColor: "bg-emerald-500",
    },
    {
      label: "Avg P&L",
      value: fmtPct(avgPnl),
      color: avgPnl >= 0 ? "text-emerald-400" : "text-red-400",
      dotColor: avgPnl >= 0 ? "bg-emerald-500" : "bg-red-500",
    },
    {
      label: "Sharpe Ratio",
      value: analytics?.sharpe_ratio?.toFixed(2) ?? "—",
      color: (analytics?.sharpe_ratio ?? 0) >= 1 ? "text-emerald-400" : "text-zinc-300",
      dotColor: (analytics?.sharpe_ratio ?? 0) >= 1 ? "bg-emerald-500" : "bg-zinc-600",
    },
    {
      label: "Signals",
      value: `${buyCount}B · ${sellCount}S`,
      color: "text-zinc-300",
      dotColor: buyCount > 0 ? "bg-amber-500" : "bg-zinc-600",
    },
    {
      label: "Positions",
      value: `${positions.length}`,
      color: "text-zinc-300",
      dotColor: "bg-zinc-600",
    },
    {
      label: "Max Drawdown",
      value: analytics?.max_drawdown_pct != null ? `${analytics.max_drawdown_pct.toFixed(1)}%` : "—",
      color: (analytics?.max_drawdown_pct ?? 0) < -15 ? "text-red-400" : "text-zinc-300",
      dotColor: (analytics?.max_drawdown_pct ?? 0) < -15 ? "bg-red-500" : "bg-zinc-600",
    },
  ];

  return (
    <div className="flex items-center gap-4 md:gap-6 overflow-x-auto px-4 py-2.5 border-b border-[rgba(255,255,255,0.04)] shrink-0 scrollbar-hide" style={{ background: "rgba(5,5,8,0.6)", backdropFilter: "blur(12px)" }}>
      {metrics.map((m, i) => (
        <div key={m.label} className="flex items-center gap-2 whitespace-nowrap shrink-0">
          <span className={`w-1.5 h-1.5 rounded-full ${m.dotColor} opacity-70`} />
          <span className="text-[9px] text-zinc-600 uppercase tracking-[0.12em] font-semibold">{m.label}</span>
          <span className={`text-[13px] font-semibold font-mono tracking-tight ${m.color}`}>{m.value}</span>
          {i < metrics.length - 1 && <span className="text-zinc-800 ml-2">|</span>}
        </div>
      ))}
      {/* Live price indicator */}
      <div className="flex items-center gap-1.5 whitespace-nowrap shrink-0 ml-auto">
        <span className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-emerald-500 animate-pulse" : "bg-zinc-600"}`} />
        <span className={`text-[9px] uppercase tracking-[0.12em] font-bold ${connected ? "text-emerald-400" : "text-zinc-600"}`}>
          {connected ? "LIVE" : "OFFLINE"}
        </span>
      </div>
    </div>
  );
}
