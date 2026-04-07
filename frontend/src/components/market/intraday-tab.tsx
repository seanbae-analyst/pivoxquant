"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { useDaytradeScan } from "@/lib/hooks";
import { apiFetch } from "@/lib/api";
import { pnlColor, signalColor, scoreColor, fmtUsd } from "@/lib/format";
import type { DayTradeResult } from "@/lib/types";

const sf = (v: number | null | undefined, d = 1) => (v ?? 0).toFixed(d);

/* ── Detail Modal ── */
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
      await apiFetch("/api/portfolio/position/buy-new", {
        method: "POST",
        body: JSON.stringify({
          ticker: item.ticker,
          shares: Number(buyShares),
          price: item.price,
        }),
      });
      setMsg("✓ Bought & tracking!");
    } catch (e: unknown) {
      setMsg((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="border-border bg-card sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {isKr ? "🇰🇷" : "🇺🇸"} {item.name || item.ticker}
            <Badge variant="outline" className={`ml-2 text-[10px] ${signalColor(item.signal)}`}>
              {item.signal}
            </Badge>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Price + Change */}
          <div className="flex items-end justify-between">
            <p className="text-2xl font-bold text-foreground">{priceStr}</p>
            <p className={`text-sm font-medium ${pnlColor(item.change_pct ?? 0)}`}>
              {(item.change_pct ?? 0) >= 0 ? "+" : ""}{sf(item.change_pct, 2)}%
            </p>
          </div>

          {/* Indicators Grid */}
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-lg bg-muted/50 p-2 text-center text-xs">
              <p className="text-muted-foreground">RSI</p>
              <p className={`font-bold ${(item.rsi ?? 50) < 30 ? "text-success" : (item.rsi ?? 50) > 70 ? "text-destructive" : "text-foreground"}`}>
                {sf(item.rsi)}
              </p>
            </div>
            <div className="rounded-lg bg-muted/50 p-2 text-center text-xs">
              <p className="text-muted-foreground">Vol Ratio</p>
              <p className={`font-bold ${(item.vol_ratio ?? 0) > 2 ? "text-success" : "text-foreground"}`}>
                {sf(item.vol_ratio)}x
              </p>
            </div>
            <div className="rounded-lg bg-muted/50 p-2 text-center text-xs">
              <p className="text-muted-foreground">Score</p>
              <p className="font-bold text-foreground">{sf(item.score, 0)}/100</p>
            </div>
          </div>

          {/* Score bar */}
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div className={`h-full rounded-full ${scoreColor(item.score ?? 0)}`} style={{ width: `${item.score ?? 0}%` }} />
          </div>

          {/* TP/SL */}
          {(item.tp_pct != null || item.sl_pct != null) && (
            <div className="grid grid-cols-2 gap-3">
              {item.take_profit != null && (
                <div className="rounded-lg border border-success/20 bg-success/5 p-2 text-center text-xs">
                  <p className="text-success/60">Take Profit</p>
                  <p className="font-bold text-success">{cur === "KRW" ? `₩${item.take_profit.toLocaleString()}` : `$${sf(item.take_profit, 2)}`}</p>
                  <p className="text-success/50">+{sf(item.tp_pct)}%</p>
                </div>
              )}
              {item.stop_loss != null && (
                <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-2 text-center text-xs">
                  <p className="text-destructive/60">Stop Loss</p>
                  <p className="font-bold text-destructive">{cur === "KRW" ? `₩${item.stop_loss.toLocaleString()}` : `$${sf(item.stop_loss, 2)}`}</p>
                  <p className="text-destructive/50">{sf(item.sl_pct)}%</p>
                </div>
              )}
            </div>
          )}

          {/* Signals */}
          {item.signals && item.signals.length > 0 && (
            <div className="space-y-1">
              {item.signals.map((s, i) => (
                <p key={i} className={`text-xs ${s.type === "bullish" ? "text-success" : s.type === "bearish" ? "text-destructive" : "text-muted-foreground"}`}>
                  {s.type === "bullish" ? "▲" : s.type === "bearish" ? "▼" : "●"} {s.msg}
                </p>
              ))}
            </div>
          )}

          {/* Buy & Track */}
          <div className="rounded-lg border border-success/20 bg-success/5 p-3">
            <p className="mb-2 text-sm font-semibold text-success">Buy & Track</p>
            <div className="flex items-center gap-2">
              <Input type="number" value={buyShares} onChange={(e) => setBuyShares(e.target.value)} className="h-9 w-24 bg-background text-sm" min={1} />
              <span className="text-xs text-muted-foreground">shares = {cur === "KRW" ? `₩${total.toLocaleString()}` : fmtUsd(total)}</span>
            </div>
            <Button className="mt-2 w-full bg-success text-white hover:bg-success/80" onClick={handleBuyTrack} disabled={loading}>
              {loading ? "Processing..." : `Buy & Track ${buyShares} shares`}
            </Button>
          </div>

          {msg && <p className={`text-center text-xs ${msg.startsWith("✓") ? "text-success" : "text-destructive"}`}>{msg}</p>}
        </div>
      </DialogContent>
    </Dialog>
  );
}

/* ── Top Card ── */
function TopCard({ item, onClick }: { item: DayTradeResult; onClick: () => void }) {
  const isKr = item.is_korean ?? item.ticker?.includes(".K");
  const flag = isKr ? "🇰🇷" : "🇺🇸";
  const cur = item.currency ?? (isKr ? "KRW" : "USD");

  return (
    <Card className="cursor-pointer border-border bg-card p-4 transition hover:border-primary/20" onClick={onClick}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-semibold text-foreground">{flag} {item.name || item.ticker}</p>
          <p className="text-[10px] text-muted-foreground">{item.ticker}</p>
        </div>
        <Badge variant="outline" className={`text-[10px] font-semibold ${signalColor(item.signal)}`}>
          {item.signal}
        </Badge>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div>
          <p className="text-muted-foreground">Price</p>
          <p className="font-medium text-foreground">
            {cur === "KRW" ? `₩${(item.price ?? 0).toLocaleString()}` : `$${sf(item.price, 2)}`}
          </p>
        </div>
        <div className="text-right">
          <p className="text-muted-foreground">Change</p>
          <p className={`font-medium ${pnlColor(item.change_pct ?? 0)}`}>
            {(item.change_pct ?? 0) >= 0 ? "+" : ""}{sf(item.change_pct, 2)}%
          </p>
        </div>
      </div>
      <div className="mt-3">
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-muted-foreground">Score</span>
          <span className="font-mono font-medium text-foreground">{sf(item.score)}</span>
        </div>
        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div className={`h-full rounded-full ${scoreColor(item.score ?? 0)}`} style={{ width: `${item.score ?? 0}%` }} />
        </div>
      </div>
      {item.signals && item.signals.length > 0 && (
        <div className="mt-3 space-y-1">
          {item.signals.slice(0, 2).map((s, i) => (
            <p key={i} className={`text-[10px] ${s.type === "bullish" ? "text-success" : s.type === "bearish" ? "text-destructive" : "text-muted-foreground"}`}>
              {s.type === "bullish" ? "+" : s.type === "bearish" ? "-" : "·"} {s.msg}
            </p>
          ))}
        </div>
      )}
    </Card>
  );
}

/* ── Stock Row ── */
function StockRow({ item, onClick }: { item: DayTradeResult; onClick: () => void }) {
  const isKr = item.is_korean ?? item.ticker?.includes(".K");
  const flag = isKr ? "🇰🇷" : "🇺🇸";
  return (
    <div className="flex cursor-pointer items-center justify-between rounded-md border border-border bg-card px-4 py-3 transition hover:bg-muted/30" onClick={onClick}>
      <div className="flex items-center gap-3">
        <Badge variant="outline" className={`h-5 text-[9px] font-semibold ${signalColor(item.signal)}`}>
          {item.signal}
        </Badge>
        <div>
          <span className="text-sm font-medium text-foreground">{flag} {item.name || item.ticker}</span>
          <span className="ml-2 text-[10px] text-muted-foreground">{item.ticker}</span>
        </div>
      </div>
      <div className="flex items-center gap-6 text-xs">
        <span className={pnlColor(item.change_pct ?? 0)}>
          {(item.change_pct ?? 0) >= 0 ? "+" : ""}{sf(item.change_pct, 2)}%
        </span>
        <span className="text-muted-foreground">RSI {sf(item.rsi, 0)}</span>
        <span className="text-muted-foreground">Vol {sf(item.vol_ratio)}x</span>
        <span className="font-mono font-medium text-foreground">{sf(item.score, 0)}</span>
      </div>
    </div>
  );
}

/* ── Main Tab ── */
export function IntradayTab() {
  const { data, isLoading, mutate } = useDaytradeScan();
  const [selectedItem, setSelectedItem] = useState<DayTradeResult | null>(null);

  if (isLoading || !data) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <p className="mt-3 font-mono text-xs text-muted-foreground">Scanning markets...</p>
      </div>
    );
  }

  const sorted = [...data.results].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  const top5 = sorted.slice(0, 5);
  const rest = sorted.slice(5);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{data.count} tickers scanned</p>
        <button
          onClick={() => mutate()}
          className="rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground transition hover:bg-muted hover:text-foreground"
        >
          ↻ Re-scan
        </button>
      </div>

      {/* Top 5 */}
      <div>
        <p className="mb-3 font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground">
          Top 5 Opportunities
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {top5.map((item) => (
            <TopCard key={item.ticker} item={item} onClick={() => setSelectedItem(item)} />
          ))}
        </div>
      </div>

      {/* All Stocks */}
      {rest.length > 0 && (
        <div>
          <p className="mb-3 font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground">
            All Stocks ({rest.length})
          </p>
          <div className="space-y-1.5">
            {rest.map((item) => (
              <StockRow key={item.ticker} item={item} onClick={() => setSelectedItem(item)} />
            ))}
          </div>
        </div>
      )}

      {/* Detail Modal */}
      <DTDetailModal
        item={selectedItem}
        open={!!selectedItem}
        onClose={() => setSelectedItem(null)}
      />
    </div>
  );
}
