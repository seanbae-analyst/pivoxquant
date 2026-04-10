"use client";

import { useVixStrategy } from "@/lib/hooks";
import { Shield, TrendingUp, TrendingDown, Minus } from "lucide-react";

export function VixWidget() {
  const { data } = useVixStrategy();
  if (!data) return <div className="flex h-full items-center justify-center rounded-2xl border border-[var(--ld-border)] bg-[var(--ld-surface)] p-5"><div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-sky-600" /></div>;

  const rc = data.color === "green" ? { bg: "bg-emerald-50", text: "text-emerald-600" } : data.color === "yellow" ? { bg: "bg-amber-50", text: "text-amber-600" } : { bg: "bg-red-50", text: "text-red-600" };
  const trendIcon = data.vix_trend === "rising" ? <TrendingUp size={12} className="text-red-600" /> : data.vix_trend === "falling" ? <TrendingDown size={12} className="text-emerald-600" /> : <Minus size={12} className="text-slate-500" />;

  return (
    <div className="flex h-full flex-col rounded-2xl border border-[var(--ld-border)] bg-[var(--ld-surface)] p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-500">VIX Regime</h3>
        <Shield size={14} className="text-slate-400" />
      </div>
      <div className="mb-4 flex items-center gap-4">
        <div className={`flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl ${rc.bg}`}>
          <span className={`text-2xl font-bold ${rc.text}`}>{data.vix.toFixed(1)}</span>
        </div>
        <div>
          <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${rc.bg} ${rc.text}`}>{data.regime}</span>
          <div className="mt-1 flex items-center gap-1.5">{trendIcon}<span className="text-[10px] text-slate-500">20D avg: {data.vix_20d_avg.toFixed(1)}</span></div>
        </div>
      </div>
      <div className="mt-auto space-y-2 border-t border-[var(--ld-border)] pt-3">
        <div className="flex items-center justify-between text-xs"><span className="text-slate-400">Percentile</span><span className="font-semibold text-slate-700">{data.vix_percentile.toFixed(0)}th</span></div>
        <div className="flex items-center justify-between text-xs"><span className="text-slate-400">Rec. Exposure</span><span className="font-semibold text-slate-700">{data.exposure.toFixed(0)}%</span></div>
        <div className="flex items-center justify-between text-xs"><span className="text-slate-400">Action</span><span className={`font-semibold ${rc.text}`}>{data.action}</span></div>
      </div>
    </div>
  );
}
