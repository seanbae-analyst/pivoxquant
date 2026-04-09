"use client";

import useSWR from "swr";
import { API } from "@/lib/endpoints";
import { History } from "lucide-react";
import { motion } from "framer-motion";

interface Trade { id: number; ticker: string; name: string; action: string; shares: number; price_per_share: number; total_value: number; pnl: number; pnl_pct: number; currency: string; traded_at: string; }
const fetcher = (url: string) => fetch(url, { credentials: "include" }).then((r) => r.json());

export default function TradesPage() {
  const { data } = useSWR<{ trades: Trade[] }>(API.trades, fetcher);
  if (!data) return <div className="flex items-center justify-center py-24"><span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" /><span className="ml-2 text-zinc-600 text-[12px]">Loading...</span></div>;

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }} className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white" style={{ fontFamily: "var(--font-geist-heading), sans-serif" }}>Trade History</h1>
        <p className="mt-1 text-[13px] text-zinc-600">Complete record of all executed trades</p>
      </div>
      {data.trades.length === 0 ? (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.04)] bg-[var(--db-surface)] py-20 text-center">
          <History className="mx-auto h-10 w-10 text-zinc-800" />
          <p className="mt-3 text-[13px] text-zinc-600">No trades yet</p>
        </div>
      ) : (
        <div className="space-y-1.5">
          {data.trades.map((t) => (
            <div key={t.id} className="flex items-center justify-between rounded-xl bg-[var(--db-surface)] border border-[rgba(255,255,255,0.04)] px-5 py-4 spring-transition transition-all duration-300 hover:border-[rgba(255,255,255,0.08)] hover:bg-[rgba(255,255,255,0.03)]">
              <div className="flex items-center gap-4">
                <span className={`rounded-lg px-2.5 py-1 text-[9px] font-bold border ${
                  t.action === "BUY" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-red-500/10 text-red-400 border-red-500/20"
                }`}>{t.action}</span>
                <div>
                  <span className="text-sm font-semibold text-white">{t.ticker}</span>
                  {t.name && <span className="ml-2 text-sm text-zinc-600">{t.name}</span>}
                </div>
              </div>
              <div className="flex items-center gap-6 text-sm">
                <span className="text-zinc-500 font-mono">{t.shares} shares</span>
                <span className="font-semibold font-mono text-zinc-300">{t.currency === "KRW" ? "₩" : "$"}{(t.price_per_share ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                {t.pnl_pct != null && t.action === "SELL" && <span className={`font-bold font-mono ${t.pnl_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>{t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct.toFixed(2)}%</span>}
                <span className="text-zinc-700 text-[11px]">{new Date(t.traded_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
