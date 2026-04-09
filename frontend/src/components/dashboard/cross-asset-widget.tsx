"use client";

import { useCrossAsset } from "@/lib/hooks";
import { Globe, ArrowUpRight, ArrowDownRight } from "lucide-react";

export function CrossAssetWidget() {
  const { data } = useCrossAsset();
  if (!data) return <div className="flex h-full items-center justify-center rounded-2xl border border-[var(--ld-border)] bg-[var(--ld-surface)] p-5"><div className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-700 border-t-cyan-400" /></div>;

  const ranking = data.ranking?.slice(0, 6) ?? [];

  return (
    <div className="flex h-full flex-col rounded-2xl border border-[var(--ld-border)] bg-[var(--ld-surface)] p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-zinc-500">Cross-Asset Ranking</h3>
        <Globe size={14} className="text-zinc-600" />
      </div>
      {data.macro_regime && (
        <div className="mb-3 rounded-xl bg-cyan-500/10 px-3 py-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-cyan-400">{data.macro_regime}</span>
        </div>
      )}
      <div className="flex-1 space-y-1.5">
        {ranking.map((item, i) => (
          <div key={item.ticker} className="flex items-center justify-between rounded-xl px-3 py-1.5 transition-all duration-200 hover:bg-white/[0.03]">
            <div className="flex items-center gap-2.5">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white/5 text-[9px] font-bold text-zinc-500">{i + 1}</span>
              <div><p className="text-xs font-semibold text-zinc-200">{item.ticker}</p><p className="text-[9px] text-zinc-600 truncate max-w-[80px]">{item.name}</p></div>
            </div>
            <div className="text-right">
              <p className={`flex items-center gap-0.5 text-xs font-bold ${item.return_1m >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {item.return_1m >= 0 ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />}
                {item.return_1m >= 0 ? "+" : ""}{(item.return_1m * 100).toFixed(1)}%
              </p>
              <p className="text-[9px] text-zinc-600">1M return</p>
            </div>
          </div>
        ))}
      </div>
      {data.strongest && data.weakest && (
        <div className="mt-3 flex gap-2 border-t border-[var(--ld-border)] pt-3">
          <div className="flex-1 rounded-xl bg-emerald-500/10 px-2.5 py-1.5 text-center">
            <p className="text-[9px] text-emerald-500">Strongest</p><p className="text-xs font-bold text-emerald-400">{data.strongest}</p>
          </div>
          <div className="flex-1 rounded-xl bg-red-500/10 px-2.5 py-1.5 text-center">
            <p className="text-[9px] text-red-500">Weakest</p><p className="text-xs font-bold text-red-400">{data.weakest}</p>
          </div>
        </div>
      )}
    </div>
  );
}
