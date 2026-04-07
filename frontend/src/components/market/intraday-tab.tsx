"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useDaytradeScan } from "@/lib/hooks";
import { pnlColor, signalColor, scoreColor } from "@/lib/format";
import type { DayTradeResult } from "@/lib/types";

/* Safe number formatting — handles null/undefined */
const sf = (v: number | null | undefined, d = 1) => (v ?? 0).toFixed(d);

function TopCard({ item }: { item: DayTradeResult }) {
  const isKr = item.is_korean ?? item.ticker?.includes(".K");
  const flag = isKr ? "🇰🇷" : "🇺🇸";
  const cur = item.currency ?? (isKr ? "KRW" : "USD");

  return (
    <Card className="border-border bg-card p-4 transition hover:border-primary/20">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-semibold text-foreground">{flag} {item.ticker}</p>
          {item.name && <p className="text-[11px] text-muted-foreground">{item.name}</p>}
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
        <div>
          <p className="text-muted-foreground">RSI</p>
          <p className={`font-medium ${(item.rsi ?? 50) < 30 ? "text-success" : (item.rsi ?? 50) > 70 ? "text-destructive" : "text-foreground"}`}>
            {sf(item.rsi)}
          </p>
        </div>
        <div className="text-right">
          <p className="text-muted-foreground">Vol Ratio</p>
          <p className={`font-medium ${(item.vol_ratio ?? 0) > 2 ? "text-success" : "text-foreground"}`}>
            {sf(item.vol_ratio)}x
          </p>
        </div>
      </div>
      {/* Score bar */}
      <div className="mt-3">
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-muted-foreground">Score</span>
          <span className="font-mono font-medium text-foreground">{sf(item.score)}</span>
        </div>
        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div className={`h-full rounded-full ${scoreColor(item.score ?? 0)}`} style={{ width: `${item.score ?? 0}%` }} />
        </div>
      </div>
      {/* Signals */}
      {item.signals && item.signals.length > 0 && (
        <div className="mt-3 space-y-1">
          {item.signals.slice(0, 3).map((s, i) => (
            <p key={i} className={`text-[10px] ${s.type === "bullish" ? "text-success" : s.type === "bearish" ? "text-destructive" : "text-muted-foreground"}`}>
              {s.type === "bullish" ? "+" : s.type === "bearish" ? "-" : "·"} {s.msg}
            </p>
          ))}
        </div>
      )}
      {/* TP/SL */}
      {(item.tp_pct != null || item.sl_pct != null) && (
        <div className="mt-3 flex gap-3 text-[10px]">
          {item.tp_pct != null && <span className="text-success">TP +{sf(item.tp_pct)}%</span>}
          {item.sl_pct != null && <span className="text-destructive">SL {sf(item.sl_pct)}%</span>}
        </div>
      )}
    </Card>
  );
}

function StockRow({ item }: { item: DayTradeResult }) {
  const isKr = item.is_korean ?? item.ticker?.includes(".K");
  const flag = isKr ? "🇰🇷" : "🇺🇸";
  return (
    <div className="flex items-center justify-between rounded-md border border-border bg-card px-4 py-3 transition hover:bg-muted/30">
      <div className="flex items-center gap-3">
        <Badge variant="outline" className={`h-5 text-[9px] font-semibold ${signalColor(item.signal)}`}>
          {item.signal}
        </Badge>
        <div>
          <span className="text-sm font-medium text-foreground">{flag} {item.ticker}</span>
          {item.name && <span className="ml-2 text-xs text-muted-foreground">{item.name}</span>}
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

export function IntradayTab() {
  const { data, isLoading, mutate } = useDaytradeScan();

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
            <TopCard key={item.ticker} item={item} />
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
              <StockRow key={item.ticker} item={item} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
