"use client";

import Link from "next/link";
import { Zap } from "lucide-react";
import type { Position } from "@/lib/types";

interface Props { positions: Position[]; }

export function SignalsWidget({ positions }: Props) {
  const signalPositions = positions.filter((p) => p.signal === "BUY" || p.signal === "SELL").sort((a, b) => b.score - a.score).slice(0, 6);
  const buyCount = positions.filter((p) => p.signal === "BUY").length;
  const sellCount = positions.filter((p) => p.signal === "SELL").length;

  return (
    <div className="flex h-full flex-col rounded-2xl border border-[var(--ld-border)] bg-[var(--ld-surface)] p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-zinc-500">Active Signals</h3>
        <div className="flex gap-2">
          {buyCount > 0 && <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold text-emerald-400">{buyCount} BUY</span>}
          {sellCount > 0 && <span className="rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-bold text-red-400">{sellCount} SELL</span>}
        </div>
      </div>
      {signalPositions.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center"><Zap className="h-8 w-8 text-zinc-700" /><p className="mt-2 text-xs text-zinc-600">No active signals</p></div>
      ) : (
        <div className="flex-1 space-y-2">
          {signalPositions.map((p) => (
            <Link key={p.id} href={`/detail/${encodeURIComponent(p.ticker)}`} className="flex items-center justify-between rounded-xl px-3 py-2 transition-all duration-200 hover:bg-white/[0.03]">
              <div className="flex items-center gap-2.5">
                <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${p.signal === "BUY" ? "bg-emerald-500/15 text-emerald-400" : "bg-red-500/15 text-red-400"}`}>{p.signal}</span>
                <div><p className="text-sm font-semibold text-white">{p.name || p.ticker}</p><p className="text-[11px] text-zinc-600">{p.ticker}</p></div>
              </div>
              <span className="rounded-full bg-white/5 px-2 py-0.5 font-mono text-[10px] font-bold text-zinc-400">{p.score.toFixed(0)}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
