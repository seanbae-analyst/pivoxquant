"use client";

import { useCrossAsset } from "@/lib/hooks";
import { Globe, ArrowUpRight, ArrowDownRight } from "lucide-react";

export function CrossAssetWidget() {
  const { data } = useCrossAsset();
  if (!data) return <div className="flex h-full items-center justify-center rounded-2xl border border-[var(--ld-border)] bg-[var(--ld-surface)] p-5"><div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-sky-600" /></div>;

  const ranking = data.ranking?.slice(0, 6) ?? [];

  return (
    <div className="flex h-full flex-col rounded-2xl border border-[var(--ld-border)] bg-[var(--ld-surface)] p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-500">Cross-Asset Ranking</h3>
        <Globe size={14} className="text-slate-400" />
      </div>
      {data.macro_regime && (
        <div className="mb-3 rounded-xl bg-sky-50 px-3 py-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-sky-600">{data.macro_regime}</span>
        </div>
      )}
      <div className="flex-1 space-y-1.5">
        {ranking.map((item, i) => (
          <div key={item.ticker} className="flex items-center justify-between rounded-xl px-3 py-1.5 transition-all duration-200 hover:bg-slate-50">
            <div className="flex items-center gap-2.5">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-100 text-[9px] font-bold text-slate-500">{i + 1}</span>
              <div><p className="text-xs font-semibold text-slate-700">{item.ticker}</p><p className="text-[9px] text-slate-400 truncate max-w-[80px]">{item.name}</p></div>
            </div>
            <div className="text-right">
              <p className={`flex items-center gap-0.5 text-xs font-bold ${item.return_1m >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                {item.return_1m >= 0 ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />}
                {item.return_1m >= 0 ? "+" : ""}{(item.return_1m * 100).toFixed(1)}%
              </p>
              <p className="text-[9px] text-slate-400">1M return</p>
            </div>
          </div>
        ))}
      </div>
      {data.strongest && data.weakest && (
        <div className="mt-3 flex gap-2 border-t border-[var(--ld-border)] pt-3">
          <div className="flex-1 rounded-xl bg-emerald-50 px-2.5 py-1.5 text-center">
            <p className="text-[9px] text-emerald-500">Strongest</p><p className="text-xs font-bold text-emerald-600">{data.strongest}</p>
          </div>
          <div className="flex-1 rounded-xl bg-red-50 px-2.5 py-1.5 text-center">
            <p className="text-[9px] text-red-500">Weakest</p><p className="text-xs font-bold text-red-600">{data.weakest}</p>
          </div>
        </div>
      )}
    </div>
  );
}
