"use client";

import useSWR from "swr";
import { API } from "@/lib/endpoints";
import { Bell } from "lucide-react";
import { motion } from "framer-motion";

interface Alert { id: number; ticker: string; message: string; signal: string; score: number; rec_shares: number; rec_investment: number; created_at: string; is_read: boolean; }
const fetcher = (url: string) => fetch(url, { credentials: "include" }).then((r) => r.json());

export default function AlertsPage() {
  const { data } = useSWR<{ alerts: Alert[]; unread: number }>(API.alerts.list, fetcher);
  if (!data) return <div className="flex items-center justify-center py-24"><span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" /><span className="ml-2 text-zinc-600 text-[12px]">Loading...</span></div>;

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }} className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white" style={{ fontFamily: "var(--font-geist-heading), sans-serif" }}>Alerts</h1>
          <p className="mt-1 text-[13px] text-zinc-600">Trading signals and notifications</p>
        </div>
        {data.unread > 0 && <span className="rounded-full px-4 py-1.5 text-[10px] font-bold text-emerald-400 bg-emerald-500/8 border border-emerald-500/15">{data.unread} unread</span>}
      </div>
      {data.alerts.length === 0 ? (
        <div className="rounded-2xl border border-[rgba(255,255,255,0.04)] bg-[var(--db-surface)] py-20 text-center">
          <Bell className="mx-auto h-10 w-10 text-zinc-800" />
          <p className="mt-3 text-[13px] text-zinc-600">No alerts yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {data.alerts.map((a) => (
            <div key={a.id} className={`flex items-start gap-4 rounded-xl p-5 spring-transition transition-all duration-300 border ${
              !a.is_read
                ? "bg-[var(--db-surface)] border-emerald-500/10 shadow-[0_0_20px_rgba(16,185,129,0.04)]"
                : "bg-[var(--db-surface)] border-[rgba(255,255,255,0.04)]"
            }`}>
              <span className={`mt-0.5 shrink-0 rounded-lg px-2.5 py-1 text-[9px] font-bold border ${
                a.signal === "BUY" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                : a.signal === "SELL" ? "bg-red-500/10 text-red-400 border-red-500/20"
                : "bg-amber-500/10 text-amber-400 border-amber-500/20"
              }`}>{a.signal}</span>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-white">{a.ticker}</span>
                  <span className="text-[11px] text-zinc-700">{new Date(a.created_at).toLocaleDateString()}</span>
                </div>
                <p className="mt-1 text-[13px] text-zinc-400">{a.message}</p>
                {a.rec_shares > 0 && <p className="mt-1.5 text-[11px] font-medium text-emerald-400">Rec: {a.rec_shares} shares (${a.rec_investment.toFixed(0)})</p>}
              </div>
              <span className="shrink-0 rounded-lg bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] px-2.5 py-1 font-mono text-[11px] font-bold text-zinc-500">{(a.score ?? 0).toFixed(0)}</span>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
