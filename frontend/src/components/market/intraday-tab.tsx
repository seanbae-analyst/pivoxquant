"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { useDaytradeScan } from "@/lib/hooks";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { pnlColor, signalColor, scoreColor, fmtUsd } from "@/lib/format";
import type { DayTradeResult } from "@/lib/types";

const sf = (v: number | null | undefined, d = 1) => (v ?? 0).toFixed(d);

/* Detail Modal */
function DTDetailModal({
  item,
  open,
  onClose,
}: {
  item: DayTradeResult | null;
  open: boolean;
  onClose: () => void;
}) {
  const [buyShares, setBuyShares] = useState("1");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  if (!item) return null;

  const isKr = item.is_korean ?? item.ticker?.includes(".K");
  const cur = item.currency ?? (isKr ? "KRW" : "USD");
  const priceStr = cur === "KRW" ? `₩${(item.price ?? 0).toLocaleString()}` : `$${sf(item.price, 2)}`;
  const total = Number(buyShares) * (item.price ?? 0);

  const handleBuyTrack = async () => {
    setLoading(true);
    setMsg("");
    try {
      await apiFetch(API.portfolio.buyNew, {
        method: "POST",
        body: JSON.stringify({
          ticker: item.ticker,
          shares: Number(buyShares),
          price: item.price,
        }),
      });
      setMsg("Position added successfully");
    } catch (e: unknown) {
      setMsg((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-slate-900">
            {item.name || item.ticker}
            <span className={`ml-2 text-[9px] font-bold px-2 py-0.5 rounded-md border ${signalColor(item.signal)}`}>
              {item.signal}
            </span>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex items-end justify-between">
            <p className="text-2xl font-bold font-mono text-slate-900">{priceStr}</p>
            <p className={`text-sm font-medium font-mono ${pnlColor(item.change_pct ?? 0)}`}>
              {(item.change_pct ?? 0) >= 0 ? "+" : ""}{sf(item.change_pct, 2)}%
            </p>
          </div>

          <div className="grid grid-cols-3 gap-2">
            {[
              { label: "RSI", value: sf(item.rsi), color: (item.rsi ?? 50) < 30 ? "text-emerald-600" : (item.rsi ?? 50) > 70 ? "text-red-600" : "text-slate-900" },
              { label: "Vol Ratio", value: `${sf(item.vol_ratio)}x`, color: (item.vol_ratio ?? 0) > 2 ? "text-emerald-600" : "text-slate-900" },
              { label: "Score", value: `${sf(item.score, 0)}/100`, color: "text-slate-900" },
            ].map((m) => (
              <div key={m.label} className="rounded-xl bg-slate-50 border border-slate-200 p-3 text-center text-xs">
                <p className="text-slate-400 text-[9px] uppercase tracking-wider">{m.label}</p>
                <p className={`font-bold font-mono mt-1 ${m.color}`}>{m.value}</p>
              </div>
            ))}
          </div>

          <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div className={`h-full rounded-full ${scoreColor(item.score ?? 0)}`} style={{ width: `${item.score ?? 0}%` }} />
          </div>

          {(item.tp_pct != null || item.sl_pct != null) && (
            <div className="grid grid-cols-2 gap-3">
              {item.take_profit != null && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-center text-xs">
                  <p className="text-emerald-500 text-[9px] uppercase tracking-wider">Take Profit</p>
                  <p className="font-bold font-mono text-emerald-600 mt-1">{cur === "KRW" ? `₩${item.take_profit.toLocaleString()}` : `$${sf(item.take_profit, 2)}`}</p>
                  <p className="text-emerald-500 text-[10px]">+{sf(item.tp_pct)}%</p>
                </div>
              )}
              {item.stop_loss != null && (
                <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-center text-xs">
                  <p className="text-red-500 text-[9px] uppercase tracking-wider">Stop Loss</p>
                  <p className="font-bold font-mono text-red-600 mt-1">{cur === "KRW" ? `₩${item.stop_loss.toLocaleString()}` : `$${sf(item.stop_loss, 2)}`}</p>
                  <p className="text-red-500 text-[10px]">{sf(item.sl_pct)}%</p>
                </div>
              )}
            </div>
          )}

          {item.signals && item.signals.length > 0 && (
            <div className="space-y-1">
              {item.signals.map((s, i) => (
                <p key={i} className={`text-xs ${s.type === "bullish" ? "text-emerald-600" : s.type === "bearish" ? "text-red-600" : "text-slate-500"}`}>
                  {s.type === "bullish" ? "+" : s.type === "bearish" ? "-" : "·"} {s.msg}
                </p>
              ))}
            </div>
          )}

          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <p className="mb-2 text-sm font-semibold text-emerald-600">Buy & Track</p>
            <div className="flex items-center gap-2">
              <Input type="number" value={buyShares} onChange={(e) => setBuyShares(e.target.value)} className="h-9 w-24 text-sm" min={1} />
              <span className="text-xs text-slate-500">shares = {cur === "KRW" ? `₩${total.toLocaleString()}` : fmtUsd(total)}</span>
            </div>
            <Button className="mt-3 w-full" onClick={handleBuyTrack} disabled={loading}>
              {loading ? "Processing..." : `Buy & Track ${buyShares} shares`}
            </Button>
          </div>

          {msg && <p className={`text-center text-xs ${msg.startsWith("Position") ? "text-emerald-600" : "text-red-600"}`}>{msg}</p>}
        </div>
      </DialogContent>
    </Dialog>
  );
}

/* Top Card */
function TopCard({ item, onClick }: { item: DayTradeResult; onClick: () => void }) {
  const isKr = item.is_korean ?? item.ticker?.includes(".K");
  const cur = item.currency ?? (isKr ? "KRW" : "USD");

  return (
    <div className="bezel-card cursor-pointer" onClick={onClick}>
      <div className="bezel-card-inner !p-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-semibold text-slate-900">{item.name || item.ticker}</p>
            <p className="text-[10px] text-slate-400 font-mono">{item.ticker}</p>
          </div>
          <span className={`text-[9px] font-bold px-2 py-0.5 rounded-md border ${signalColor(item.signal)}`}>
            {item.signal}
          </span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div>
            <p className="text-slate-400 text-[9px]">Price</p>
            <p className="font-medium font-mono text-slate-900">
              {cur === "KRW" ? `₩${(item.price ?? 0).toLocaleString()}` : `$${sf(item.price, 2)}`}
            </p>
          </div>
          <div className="text-right">
            <p className="text-slate-400 text-[9px]">Change</p>
            <p className={`font-medium font-mono ${pnlColor(item.change_pct ?? 0)}`}>
              {(item.change_pct ?? 0) >= 0 ? "+" : ""}{sf(item.change_pct, 2)}%
            </p>
          </div>
        </div>
        <div className="mt-3">
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-slate-400">Score</span>
            <span className="font-mono font-medium text-slate-900">{sf(item.score)}</span>
          </div>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div className={`h-full rounded-full ${scoreColor(item.score ?? 0)}`} style={{ width: `${item.score ?? 0}%` }} />
          </div>
        </div>
        {item.signals && item.signals.length > 0 && (
          <div className="mt-3 space-y-1">
            {item.signals.slice(0, 2).map((s, i) => (
              <p key={i} className={`text-[10px] ${s.type === "bullish" ? "text-emerald-600" : s.type === "bearish" ? "text-red-600" : "text-slate-400"}`}>
                {s.type === "bullish" ? "+" : s.type === "bearish" ? "-" : "·"} {s.msg}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* Stock Row */
function StockRow({ item, onClick }: { item: DayTradeResult; onClick: () => void }) {
  return (
    <div className="flex cursor-pointer items-center justify-between rounded-xl border border-slate-200 bg-[var(--db-surface)] px-4 py-3 spring-transition transition-all duration-300 hover:bg-slate-50 hover:border-slate-300 group" onClick={onClick}>
      <div className="flex items-center gap-3">
        <span className={`text-[9px] font-bold px-2 py-0.5 rounded-md border ${signalColor(item.signal)}`}>
          {item.signal}
        </span>
        <div>
          <p className="text-sm font-semibold text-slate-900 group-hover:text-emerald-600 spring-transition transition-colors">{item.name || item.ticker}</p>
          <p className="text-[10px] text-slate-400 font-mono">{item.ticker}</p>
        </div>
      </div>
      <div className="flex items-center gap-6 text-xs">
        <span className={`font-mono ${pnlColor(item.change_pct ?? 0)}`}>
          {(item.change_pct ?? 0) >= 0 ? "+" : ""}{sf(item.change_pct, 2)}%
        </span>
        <span className="text-slate-400 font-mono">RSI {sf(item.rsi, 0)}</span>
        <span className="text-slate-400 font-mono">Vol {sf(item.vol_ratio)}x</span>
        <span className="font-mono font-medium text-slate-900">{sf(item.score, 0)}</span>
      </div>
    </div>
  );
}

/* Main Tab */
export function IntradayTab() {
  const { data, isLoading, mutate } = useDaytradeScan();
  const [selectedItem, setSelectedItem] = useState<DayTradeResult | null>(null);

  if (isLoading || !data) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
        <span className="mt-3 text-slate-400 text-[12px]">Scanning intraday opportunities...</span>
      </div>
    );
  }

  const sorted = [...data.results].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  const top5 = sorted.slice(0, 5);
  const rest = sorted.slice(5);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">{data.count} tickers scanned</p>
        <button
          onClick={() => mutate()}
          className="rounded-xl px-4 py-2 text-sm font-medium border border-slate-200 bg-slate-50 text-slate-500 hover:text-slate-900 hover:bg-slate-100 spring-transition transition-all duration-300"
        >
          Re-scan
        </button>
      </div>

      {/* Top 5 */}
      <div>
        <p className="mb-3 font-mono text-[9px] font-semibold uppercase tracking-[1.5px] text-slate-400">
          Top 5 Opportunities
        </p>
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-5">
          {top5.map((item) => (
            <TopCard key={item.ticker} item={item} onClick={() => setSelectedItem(item)} />
          ))}
        </div>
      </div>

      {/* All Stocks */}
      {rest.length > 0 && (
        <div>
          <p className="mb-3 font-mono text-[9px] font-semibold uppercase tracking-[1.5px] text-slate-400">
            All Stocks ({rest.length})
          </p>
          <div className="space-y-1.5">
            {rest.map((item) => (
              <StockRow key={item.ticker} item={item} onClick={() => setSelectedItem(item)} />
            ))}
          </div>
        </div>
      )}

      <DTDetailModal
        item={selectedItem}
        open={!!selectedItem}
        onClose={() => setSelectedItem(null)}
      />
    </div>
  );
}
