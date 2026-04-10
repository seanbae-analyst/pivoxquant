"use client";

import Link from "next/link";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";
import type { Position } from "@/lib/types";

interface Props { positions: Position[]; }

export function TopMoversWidget({ positions }: Props) {
  const sorted = [...positions].sort((a, b) => b.pnl_pct - a.pnl_pct);
  const gainers = sorted.slice(0, 3);
  const losers = sorted.slice(-3).reverse();

  return (
    <div className="flex h-full flex-col rounded-2xl border border-[var(--ld-border)] bg-[var(--ld-surface)] p-5">
      <h3 className="mb-4 text-xs font-semibold uppercase tracking-widest text-slate-500">Top Movers</h3>
      <div className="flex-1 space-y-4">
        <div>
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-600">Gainers</p>
          <div className="space-y-1.5">
            {gainers.map((p) => (
              <Link key={p.id} href={`/detail/${encodeURIComponent(p.ticker)}`} className="flex items-center justify-between rounded-xl px-3 py-1.5 transition-all duration-200 hover:bg-slate-50">
                <div>
                  <p className="text-sm font-semibold text-slate-900">{p.name || p.ticker}</p>
                  <p className="text-[11px] text-slate-400">{p.ticker}</p>
                </div>
                <span className={`flex items-center gap-0.5 text-xs font-bold ${p.pnl_pct >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                  {p.pnl_pct >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                  {p.pnl_pct >= 0 ? "+" : ""}{p.pnl_pct.toFixed(2)}%
                </span>
              </Link>
            ))}
          </div>
        </div>
        <div>
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-red-600">Losers</p>
          <div className="space-y-1.5">
            {losers.map((p) => (
              <Link key={p.id} href={`/detail/${encodeURIComponent(p.ticker)}`} className="flex items-center justify-between rounded-xl px-3 py-1.5 transition-all duration-200 hover:bg-slate-50">
                <div>
                  <p className="text-sm font-semibold text-slate-900">{p.name || p.ticker}</p>
                  <p className="text-[11px] text-slate-400">{p.ticker}</p>
                </div>
                <span className="flex items-center gap-0.5 text-xs font-bold text-red-600"><ArrowDownRight size={12} />{p.pnl_pct.toFixed(2)}%</span>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
