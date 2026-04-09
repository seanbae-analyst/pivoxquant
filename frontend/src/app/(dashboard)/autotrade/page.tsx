"use client";

import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { fmtUsd, fmtKrw } from "@/lib/format";
import { Bot, DollarSign, Briefcase, Activity, Power } from "lucide-react";
import { motion } from "framer-motion";

interface AutoTradeStatus {
  running: boolean; available: boolean; positions: number; positions_us: number; positions_kr: number;
  max_positions: number; max_daily_trades: number; trades_today: number; kr_equity: number;
  kr_capital: number; kr_daily_pnl: number;
  account: { equity?: number; cash?: number; buying_power?: number; daily_pnl?: number; portfolio_value?: number; };
  active_positions: Array<{ ticker: string; qty: number; current_price: number; market_value: number; unrealized_pl: number; unrealized_plpc: number; side: string; }>;
  logs: Array<{ time: string; msg: string }>;
}

const fetcher = (url: string) => fetch(url, { credentials: "include" }).then((r) => r.json());

export default function AutoTradePage() {
  const { data, mutate } = useSWR<AutoTradeStatus>(API.autotrade.status, fetcher, { refreshInterval: 10_000 });

  const toggleRunning = async () => {
    if (!data) return;
    await apiFetch(data?.running ? API.autotrade.stop : API.autotrade.start, { method: "POST" });
    mutate();
  };

  if (!data) return <div className="flex items-center justify-center py-24"><span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" /><span className="ml-2 text-zinc-600 text-[12px]">Loading...</span></div>;

  const acct = data.account ?? {};
  const running = data.running ?? false;
  const positions = data.positions ?? 0;
  const maxPositions = data.max_positions ?? 0;
  const positionsUs = data.positions_us ?? 0;
  const positionsKr = data.positions_kr ?? 0;
  const tradesToday = data.trades_today ?? 0;
  const maxDailyTrades = data.max_daily_trades ?? 0;
  const activePositions = data.active_positions ?? [];
  const logs = data.logs ?? [];

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }} className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white" style={{ fontFamily: "var(--font-geist-heading), sans-serif" }}>Auto Trade</h1>
          <p className="mt-1 text-[13px] text-zinc-600">Paper Trading Mode — Automated entry & exit</p>
        </div>
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-2 rounded-full px-4 py-2 text-[10px] font-bold tracking-wider border ${
            running
              ? "bg-emerald-500/8 text-emerald-400 border-emerald-500/15"
              : "bg-[rgba(255,255,255,0.03)] text-zinc-600 border-[rgba(255,255,255,0.06)]"
          }`}>
            <div className={`h-2 w-2 rounded-full ${running ? "bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.6)] animate-pulse" : "bg-zinc-700"}`} />
            {running ? "RUNNING" : "STOPPED"}
          </div>
          <Button onClick={toggleRunning} variant={running ? "destructive" : "default"} className="gap-2">
            <Power size={16} />
            {running ? "Stop" : "Start"}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
        {[
          { icon: <DollarSign className="h-4 w-4 text-emerald-400" />, label: "US Equity", value: fmtUsd(acct.equity ?? 0) },
          { icon: <DollarSign className="h-4 w-4 text-cyan-400" />, label: "KR Equity", value: fmtKrw(data.kr_equity ?? 0) },
          { icon: <Briefcase className="h-4 w-4 text-amber-400" />, label: "Positions", value: `${positions} / ${maxPositions}`, sub: `US ${positionsUs} · KR ${positionsKr}` },
          { icon: <Activity className="h-4 w-4 text-emerald-400" />, label: "Trades Today", value: `${tradesToday} / ${maxDailyTrades}` },
        ].map((m) => (
          <div key={m.label} className="bezel-card">
            <div className="bezel-card-inner !p-5">
              <div className="flex items-center gap-2">{m.icon}<p className="text-[9px] font-semibold text-zinc-600 uppercase tracking-[0.12em]">{m.label}</p></div>
              <p className="mt-3 text-xl font-bold text-white font-mono">{m.value}</p>
              {(m as { sub?: string }).sub && <p className="mt-0.5 text-[11px] text-zinc-600">{(m as { sub?: string }).sub}</p>}
            </div>
          </div>
        ))}
      </div>

      <div>
        <h2 className="mb-4 text-lg font-bold text-white" style={{ fontFamily: "var(--font-geist-heading), sans-serif" }}>
          Active Positions <span className="text-sm font-normal text-zinc-600">({activePositions.length})</span>
        </h2>
        {activePositions.length === 0 ? (
          <div className="rounded-2xl border border-[rgba(255,255,255,0.04)] bg-[var(--db-surface)] py-16 text-center">
            <Bot className="mx-auto h-10 w-10 text-zinc-800" />
            <p className="mt-3 text-[13px] text-zinc-600">No active positions</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {activePositions.map((p) => (
              <div key={p.ticker} className="flex items-center justify-between rounded-xl bg-[var(--db-surface)] border border-[rgba(255,255,255,0.04)] px-5 py-4 spring-transition transition-all duration-300 hover:border-[rgba(255,255,255,0.08)]">
                <div>
                  <span className="text-sm font-semibold text-white">{p.ticker}</span>
                  <span className="ml-3 text-sm text-zinc-600">{p.qty} shares · {p.side}</span>
                </div>
                <div className="flex items-center gap-6">
                  <span className="text-sm font-semibold font-mono text-zinc-300">{fmtUsd(p.market_value)}</span>
                  <span className={`text-sm font-bold font-mono ${p.unrealized_pl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {p.unrealized_pl >= 0 ? "+" : ""}${p.unrealized_pl.toFixed(2)} ({(p.unrealized_plpc * 100).toFixed(2)}%)
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {logs.length > 0 && (
        <div>
          <h2 className="mb-4 text-lg font-bold text-white" style={{ fontFamily: "var(--font-geist-heading), sans-serif" }}>Recent Logs</h2>
          <div className="max-h-60 overflow-y-auto rounded-xl bg-[var(--db-surface)] border border-[rgba(255,255,255,0.04)] p-5 scrollbar-thin">
            {logs.slice(-20).reverse().map((log, i) => (
              <p key={i} className="py-1 font-mono text-[11px] text-zinc-500"><span className="text-zinc-700">{log.time}</span> {log.msg}</p>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
