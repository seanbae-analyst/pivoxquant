"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { usePortfolio } from "@/lib/hooks";
import { API } from "@/lib/endpoints";
import { fmtPct, signalColor, pnlColor } from "@/lib/format";
import { apiFetch } from "@/lib/api";

const fetcher = (url: string) =>
  fetch(url, { credentials: "include" }).then((r) => {
    if (!r.ok) throw new Error(r.statusText);
    return r.json();
  });

interface WatchlistItem {
  id: number;
  ticker: string;
  name: string;
  price: number;
  change_pct: number;
  signal: string;
  score: number;
  is_korean: boolean;
}

export function RightPanel() {
  const [section, setSection] = useState<"watchlist" | "signals">("watchlist");

  return (
    <div className="w-[280px] border-l border-[rgba(255,255,255,0.04)] flex flex-col shrink-0 hidden md:flex" style={{ background: "rgba(5,5,8,0.6)", backdropFilter: "blur(12px)" }}>
      {/* Section toggle */}
      <div className="flex items-center gap-0.5 p-1.5 border-b border-[rgba(255,255,255,0.04)] shrink-0">
        <button
          onClick={() => setSection("watchlist")}
          className={`flex-1 text-[10px] font-bold uppercase tracking-[0.12em] py-2 rounded-lg spring-transition transition-all duration-300 ${
            section === "watchlist"
              ? "bg-emerald-500/8 text-emerald-400 border border-emerald-500/15"
              : "text-zinc-600 hover:text-zinc-300"
          }`}
        >
          Watchlist
        </button>
        <button
          onClick={() => setSection("signals")}
          className={`flex-1 text-[10px] font-bold uppercase tracking-[0.12em] py-2 rounded-lg spring-transition transition-all duration-300 ${
            section === "signals"
              ? "bg-emerald-500/8 text-emerald-400 border border-emerald-500/15"
              : "text-zinc-600 hover:text-zinc-300"
          }`}
        >
          Signals
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto min-h-0 scrollbar-thin">
        {section === "watchlist" ? <WatchlistSection /> : <SignalsSection />}
      </div>

      {/* Quick actions */}
      <div className="border-t border-[rgba(255,255,255,0.04)] p-3 space-y-2 shrink-0">
        <Link
          href="/autotrade"
          className="block w-full text-center text-[10px] font-bold py-2.5 rounded-xl bg-emerald-500/8 border border-emerald-500/15 text-emerald-400 hover:bg-emerald-500/15 spring-transition transition-all duration-300 uppercase tracking-[0.1em]"
        >
          Auto Trading
        </Link>
        <Link
          href="/morning"
          className="block w-full text-center text-[10px] font-semibold py-2.5 rounded-xl bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] text-zinc-500 hover:text-zinc-300 hover:bg-[rgba(255,255,255,0.05)] spring-transition transition-all duration-300"
        >
          Morning Brief
        </Link>
      </div>
    </div>
  );
}

function WatchlistSection() {
  const { data, mutate } = useSWR<{ items: WatchlistItem[] }>(API.watchlist.list, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 30_000,
  });
  const [ticker, setTicker] = useState("");

  const items = data?.items ?? [];

  const handleAdd = async () => {
    if (!ticker.trim()) return;
    await apiFetch(API.watchlist.add, {
      method: "POST",
      body: JSON.stringify({ ticker: ticker.trim().toUpperCase() }),
    });
    setTicker("");
    mutate();
  };

  const handleRemove = async (id: number) => {
    await apiFetch(API.watchlist.remove(id), { method: "DELETE" });
    mutate();
  };

  return (
    <div>
      {/* Add input */}
      <div className="flex items-center gap-1.5 p-3 border-b border-[rgba(255,255,255,0.04)]">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          placeholder="Add ticker..."
          className="flex-1 text-[11px] bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] rounded-lg px-3 py-2 text-white placeholder:text-zinc-700 focus:outline-none focus:border-emerald-500/30 focus:shadow-[0_0_12px_rgba(16,185,129,0.06)] spring-transition transition-all duration-300"
        />
        <button onClick={handleAdd} className="text-[10px] font-bold text-emerald-400 px-3 py-2 hover:bg-emerald-500/10 rounded-lg spring-transition transition-all duration-300">
          Add
        </button>
      </div>

      {items.length === 0 ? (
        <div className="py-10 text-center">
          <div className="w-8 h-8 rounded-xl bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] flex items-center justify-center mx-auto mb-2">
            <svg width="14" height="14" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-zinc-700">
              <path d="M9 2l2 4.2L15.5 7l-3.5 3.3.8 4.7L9 12.8l-3.8 2.2.8-4.7L2.5 7l4.5-.8z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <p className="text-zinc-700 text-[11px]">No items in watchlist</p>
        </div>
      ) : (
        items.map((item) => (
          <div key={item.id} className="flex items-center justify-between px-3 py-2.5 hover:bg-[rgba(255,255,255,0.02)] spring-transition transition-colors duration-300 group">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-md border ${signalColor(item.signal)}`}>
                {item.signal}
              </span>
              <Link href={`/detail/${item.ticker}`} className="hover:text-emerald-400 spring-transition transition-colors duration-300 truncate">
                <p className="text-sm font-semibold text-white">{item.name || item.ticker}</p>
                <p className="text-[10px] text-zinc-600 font-mono">{item.ticker}</p>
              </Link>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className={`text-[10px] font-mono font-medium ${pnlColor(item.change_pct)}`}>
                {fmtPct(item.change_pct)}
              </span>
              <button
                onClick={() => handleRemove(item.id)}
                className="opacity-0 group-hover:opacity-100 text-zinc-700 hover:text-red-400 spring-transition transition-all duration-300 text-sm leading-none"
              >
                ×
              </button>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function SignalsSection() {
  const { data } = usePortfolio();
  const positions = data?.positions ?? [];
  const signaled = positions
    .filter((p) => p.signal === "BUY" || p.signal === "SELL")
    .sort((a, b) => b.score - a.score);

  if (!signaled.length) {
    return (
      <div className="py-10 text-center">
        <div className="w-8 h-8 rounded-xl bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] flex items-center justify-center mx-auto mb-2">
          <svg width="14" height="14" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-zinc-700">
            <path d="M13 2L3 14h5v4l10-12h-5V2z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <p className="text-zinc-700 text-[11px]">No active signals</p>
      </div>
    );
  }

  return (
    <div>
      {signaled.map((p) => (
        <div key={p.id} className="flex items-center justify-between px-3 py-2.5 hover:bg-[rgba(255,255,255,0.02)] spring-transition transition-colors duration-300 group">
          <div className="flex items-center gap-2.5">
            <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-md border ${signalColor(p.signal)}`}>
              {p.signal}
            </span>
            <Link href={`/detail/${p.ticker}`} className="hover:text-emerald-400 spring-transition transition-colors duration-300">
              <p className="text-sm font-semibold text-white">{p.name || p.ticker}</p>
              <p className="text-[10px] text-zinc-600 font-mono">{p.ticker}</p>
            </Link>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[10px] font-mono text-zinc-600">{p.score}</span>
            <span className={`text-[10px] font-mono font-medium ${pnlColor(p.pnl_pct)}`}>{fmtPct(p.pnl_pct)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
