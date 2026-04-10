"use client";

import { mutate } from "swr";
import { usePortfolio, useAnalytics } from "@/lib/hooks";
import { useRealtimeContext } from "@/lib/realtime";
import { fmtUsd, fmtPct, fmtKrw } from "@/lib/format";
import { EditCapitalModal } from "@/components/dashboard/action-modals";
import { API } from "@/lib/endpoints";

export function TerminalMetrics() {
  const { data: portfolio } = usePortfolio();
  const { data: analytics } = useAnalytics();
  const { connected } = useRealtimeContext();

  const totalValue = portfolio?.total_value_usd ?? 0;
  const availableCapital = portfolio?.available_capital ?? 0;
  const availableCapitalKrw = portfolio?.available_capital_krw ?? 0;
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
      color: "text-slate-900",
      dotColor: "bg-emerald-500",
    },
    {
      label: "Avail. Capital",
      value: fmtUsd(availableCapital),
      subValue: availableCapitalKrw > 0 ? fmtKrw(availableCapitalKrw) : undefined,
      color: "text-slate-900",
      dotColor: "bg-blue-500",
      editCapital: true,
    },
    {
      label: "Avg P&L",
      value: fmtPct(avgPnl),
      color: avgPnl >= 0 ? "text-emerald-600" : "text-red-600",
      dotColor: avgPnl >= 0 ? "bg-emerald-500" : "bg-red-500",
    },
    {
      label: "Sharpe Ratio",
      value: analytics?.sharpe_ratio?.toFixed(2) ?? "—",
      color: (analytics?.sharpe_ratio ?? 0) >= 1 ? "text-emerald-600" : "text-slate-700",
      dotColor: (analytics?.sharpe_ratio ?? 0) >= 1 ? "bg-emerald-500" : "bg-slate-400",
    },
    {
      label: "Signals",
      value: `${buyCount}B · ${sellCount}S`,
      color: "text-slate-700",
      dotColor: buyCount > 0 ? "bg-amber-500" : "bg-slate-400",
    },
    {
      label: "Positions",
      value: `${positions.length}`,
      color: "text-slate-700",
      dotColor: "bg-slate-400",
    },
    {
      label: "Max Drawdown",
      value: analytics?.max_drawdown_pct != null ? `${analytics.max_drawdown_pct.toFixed(1)}%` : "—",
      color: (analytics?.max_drawdown_pct ?? 0) < -15 ? "text-red-600" : "text-slate-700",
      dotColor: (analytics?.max_drawdown_pct ?? 0) < -15 ? "bg-red-500" : "bg-slate-400",
    },
  ];

  return (
    <div className="flex items-center gap-4 md:gap-6 overflow-x-auto px-4 py-2.5 border-b border-slate-200 shrink-0 scrollbar-hide bg-white">
      {metrics.map((m, i) => (
        <div key={m.label} className="flex items-center gap-2 whitespace-nowrap shrink-0">
          <span className={`w-1.5 h-1.5 rounded-full ${m.dotColor} opacity-70`} />
          <span className="text-[9px] text-slate-400 uppercase tracking-[0.12em] font-semibold">{m.label}</span>
          <span className={`text-[13px] font-semibold font-mono tracking-tight ${m.color}`}>
            {m.value}
            {m.subValue && <span className="text-[10px] text-slate-400 ml-1 font-normal">{m.subValue}</span>}
          </span>
          {m.editCapital && (
            <EditCapitalModal
              currentUsd={availableCapital}
              currentKrw={availableCapitalKrw}
              onDone={() => mutate(API.portfolio.list)}
            />
          )}
          {i < metrics.length - 1 && <span className="text-slate-200 ml-2">|</span>}
        </div>
      ))}
      {/* Live price indicator */}
      <div className="flex items-center gap-1.5 whitespace-nowrap shrink-0 ml-auto">
        <span className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-emerald-500 animate-pulse" : "bg-slate-400"}`} />
        <span className={`text-[9px] uppercase tracking-[0.12em] font-bold ${connected ? "text-emerald-600" : "text-slate-400"}`}>
          {connected ? "LIVE" : "OFFLINE"}
        </span>
      </div>
    </div>
  );
}
