"use client";

import { useDiscover } from "@/lib/hooks";
import Link from "next/link";
import { Sparkles, ArrowRight } from "lucide-react";

export function DiscoverWidget() {
  const { data } = useDiscover();
  if (!data) return <div className="flex h-full items-center justify-center rounded-2xl border border-[var(--ld-border)] bg-[var(--ld-surface)] p-5"><div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-sky-600" /></div>;

  const results = data.results?.slice(0, 5) ?? [];

  return (
    <div className="flex h-full flex-col rounded-2xl border border-sky-200 bg-[var(--ld-surface)] p-5">
      <div className="mb-4 flex items-center gap-2">
        <Sparkles size={14} className="text-sky-600" />
        <h3 className="text-xs font-semibold uppercase tracking-widest text-sky-600">AI Discovery</h3>
      </div>
      {results.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center"><Sparkles className="h-8 w-8 text-slate-400" /><p className="mt-2 text-xs text-slate-400">Scanning for opportunities...</p></div>
      ) : (
        <div className="flex-1 space-y-2">
          {results.map((r) => (
            <Link key={r.ticker} href={`/detail/${encodeURIComponent(r.ticker)}`} className="flex items-center justify-between rounded-xl px-3 py-2 transition-all duration-200 hover:bg-slate-50">
              <div className="flex items-center gap-2.5">
                <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${
                  r.signal === "BUY" ? "bg-emerald-50 text-emerald-600" : r.signal === "SELL" ? "bg-red-50 text-red-600" : "bg-amber-50 text-amber-600"
                }`}>{r.signal}</span>
                <div><p className="text-sm font-semibold text-slate-900">{r.name || r.ticker}</p><p className="text-[11px] text-slate-400">{r.ticker}</p></div>
              </div>
              <span className="rounded-full bg-sky-50 px-2 py-0.5 font-mono text-[10px] font-bold text-sky-600">{r.score.toFixed(0)}</span>
            </Link>
          ))}
        </div>
      )}
      <Link href="/market" className="mt-3 flex items-center justify-center gap-1.5 border-t border-[var(--ld-border)] pt-3 text-xs font-semibold text-sky-600 transition hover:text-sky-500">
        View Scanner <ArrowRight size={12} />
      </Link>
    </div>
  );
}
