"use client";

import { useState } from "react";
import useSWR from "swr";
import { Input } from "@/components/ui/input";
import { pnlColor } from "@/lib/format";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { Eye, X } from "lucide-react";
import { motion } from "framer-motion";

interface WatchlistItem { id: number; ticker: string; name: string; price: number; price_display: string; change_pct: number; signal: string; score: number; currency: string; is_korean: boolean; }
const fetcher = (url: string) => fetch(url, { credentials: "include" }).then((r) => r.json());

export default function WatchlistPage() {
  const { data, mutate } = useSWR<{ watchlist: WatchlistItem[] }>(API.watchlist.list, fetcher);
  const [ticker, setTicker] = useState("");
  const [adding, setAdding] = useState(false);

  const handleAdd = async () => {
    if (!ticker.trim()) return;
    setAdding(true);
    try { await apiFetch(API.watchlist.add, { method: "POST", body: JSON.stringify({ ticker: ticker.trim().toUpperCase() }) }); setTicker(""); mutate(); } catch {} finally { setAdding(false); }
  };

  const handleRemove = async (id: number) => { await apiFetch(API.watchlist.remove(id), { method: "DELETE" }); mutate(); };

  if (!data) return <div className="flex items-center justify-center py-24"><span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" /><span className="ml-2 text-slate-500 text-[12px]">Loading...</span></div>;

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }} className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900" style={{ fontFamily: "var(--font-geist-heading), sans-serif" }}>Watchlist</h1>
        <p className="mt-1 text-[13px] text-slate-500">Track stocks you&apos;re interested in</p>
      </div>
      <div className="flex gap-2">
        <Input value={ticker} onChange={(e) => setTicker(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleAdd()} placeholder="Add ticker (e.g. AAPL)" className="max-w-xs" />
        <button onClick={handleAdd} disabled={adding} className="rounded-xl px-5 py-2 text-sm font-semibold border border-emerald-500/20 bg-emerald-500/8 text-emerald-600 hover:bg-emerald-500/15 spring-transition transition-all duration-300 disabled:opacity-50 flex items-center gap-2">
          {adding ? "..." : "Add"}
        </button>
      </div>
      {data.watchlist.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white py-20 text-center">
          <Eye className="mx-auto h-10 w-10 text-slate-300" />
          <p className="mt-3 text-[13px] text-slate-500">Watchlist is empty. Add tickers above.</p>
        </div>
      ) : (
        <div className="space-y-1.5">
          {data.watchlist.map((w) => (
            <div key={w.id} className="flex items-center justify-between rounded-xl bg-white border border-slate-200 px-5 py-4 spring-transition transition-all duration-300 hover:border-slate-300 hover:bg-slate-50 group">
              <div className="flex items-center gap-4">
                <span className={`rounded-lg px-2.5 py-1 text-[9px] font-bold border ${
                  w.signal === "BUY" ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
                  : w.signal === "SELL" ? "bg-red-500/10 text-red-600 border-red-500/20"
                  : "bg-amber-500/10 text-amber-600 border-amber-500/20"
                }`}>{w.signal}</span>
                <div>
                  <span className="text-sm font-semibold text-slate-900">{w.ticker}</span>
                  <span className="ml-2 text-sm text-slate-500">{w.name}</span>
                </div>
              </div>
              <div className="flex items-center gap-5 text-sm">
                <span className="font-semibold font-mono text-slate-700">{w.price_display}</span>
                <span className={`font-bold font-mono ${pnlColor(w.change_pct ?? 0)}`}>{(w.change_pct ?? 0) >= 0 ? "+" : ""}{(w.change_pct ?? 0).toFixed(2)}%</span>
                <span className="rounded-lg bg-slate-100 border border-slate-200 px-2.5 py-1 font-mono text-[11px] font-bold text-slate-500">{(w.score ?? 0).toFixed(0)}</span>
                <button onClick={() => handleRemove(w.id)} className="rounded-lg p-1.5 text-slate-400 opacity-0 group-hover:opacity-100 spring-transition transition-all duration-300 hover:bg-red-500/10 hover:text-red-600"><X size={14} /></button>
              </div>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
