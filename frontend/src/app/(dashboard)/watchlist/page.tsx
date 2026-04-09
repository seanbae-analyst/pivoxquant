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

  if (!data) return <div className="flex items-center justify-center py-24"><span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" /><span className="ml-2 text-zinc-600 text-[12px]">Loading...</span></div>;

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }} className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white" style={{ fontFamily: "var(--font-geist-heading), sans-serif" }}>Watchlist</h1>
        <p className="mt-1 text-[13px] text-zinc-600">Track stocks you&apos;re interested in</p>
      </div>
      <div className="flex gap-2">
        <Input value={ticker} onChange={(e) => setTicker(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleAdd()} placeholder="Add ticker (e.g. AAPL)" className="max-w-xs" />
        <button onClick={handleAdd} disabled={adding} className="rounded-xl px-5 py-2 text-sm font-semibold border border-emerald-500/20 bg-emerald-500/8 text-emerald-400 hover:bg-emerald-500/15 spring-transition transition-all duration-300 disabled:opacity-50 flex items-center gap-2">
          {adding ? "..." : "Add"}
        </button>
      </div>
      {data.watchlist.length === 0 ? (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.04)] bg-[var(--db-surface)] py-20 text-center">
          <Eye className="mx-auto h-10 w-10 text-zinc-800" />
          <p className="mt-3 text-[13px] text-zinc-600">Watchlist is empty. Add tickers above.</p>
        </div>
      ) : (
        <div className="space-y-1.5">
          {data.watchlist.map((w) => (
            <div key={w.id} className="flex items-center justify-between rounded-xl bg-[var(--db-surface)] border border-[rgba(255,255,255,0.04)] px-5 py-4 spring-transition transition-all duration-300 hover:border-[rgba(255,255,255,0.08)] hover:bg-[rgba(255,255,255,0.03)] group">
              <div className="flex items-center gap-4">
                <span className={`rounded-lg px-2.5 py-1 text-[9px] font-bold border ${
                  w.signal === "BUY" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                  : w.signal === "SELL" ? "bg-red-500/10 text-red-400 border-red-500/20"
                  : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                }`}>{w.signal}</span>
                <div>
                  <span className="text-sm font-semibold text-white">{w.ticker}</span>
                  <span className="ml-2 text-sm text-zinc-600">{w.name}</span>
                </div>
              </div>
              <div className="flex items-center gap-5 text-sm">
                <span className="font-semibold font-mono text-zinc-300">{w.price_display}</span>
                <span className={`font-bold font-mono ${pnlColor(w.change_pct ?? 0)}`}>{(w.change_pct ?? 0) >= 0 ? "+" : ""}{(w.change_pct ?? 0).toFixed(2)}%</span>
                <span className="rounded-lg bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] px-2.5 py-1 font-mono text-[11px] font-bold text-zinc-500">{(w.score ?? 0).toFixed(0)}</span>
                <button onClick={() => handleRemove(w.id)} className="rounded-lg p-1.5 text-zinc-700 opacity-0 group-hover:opacity-100 spring-transition transition-all duration-300 hover:bg-red-500/10 hover:text-red-400"><X size={14} /></button>
              </div>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
