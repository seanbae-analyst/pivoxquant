"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDiscover } from "@/lib/hooks";
import { apiFetch } from "@/lib/api";
import { pnlColor, signalColor, scoreColor, fmtUsd } from "@/lib/format";
import type { ScanResult, DiscoverResult } from "@/lib/types";

type DiscoverFilter = "all" | "us" | "kr" | "buy" | "gem";

function ScanResultCard({ data }: { data: ScanResult }) {
  return (
    <Card className="border-border bg-card p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-lg font-bold text-foreground">{data.ticker}</p>
          <p className="text-sm text-muted-foreground">{data.name}</p>
        </div>
        <Badge variant="outline" className={`text-sm font-semibold ${signalColor(data.signal)}`}>
          {data.signal}
        </Badge>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-4 text-center">
        <div>
          <p className="text-[10px] text-muted-foreground">Score</p>
          <p className="text-xl font-bold text-foreground">{data.score.toFixed(0)}/100</p>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div className={`h-full rounded-full ${scoreColor(data.score)}`} style={{ width: `${data.score}%` }} />
          </div>
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground">Price</p>
          <p className="text-xl font-bold text-foreground">
            {data.is_korean ? `₩${data.price.toLocaleString()}` : `$${data.price.toFixed(2)}`}
          </p>
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground">Change</p>
          <p className={`text-xl font-bold ${pnlColor(data.change_pct)}`}>
            {data.change_pct >= 0 ? "+" : ""}{data.change_pct.toFixed(2)}%
          </p>
        </div>
      </div>

      {/* TP/SL */}
      <div className="mt-4 flex justify-center gap-6 text-sm">
        <span className="text-success">TP {data.is_korean ? `₩${data.take_profit.toLocaleString()}` : fmtUsd(data.take_profit)}</span>
        <span className="text-destructive">SL {data.is_korean ? `₩${data.stop_loss.toLocaleString()}` : fmtUsd(data.stop_loss)}</span>
      </div>

      {/* Signals */}
      {data.signals.length > 0 && (
        <div className="mt-4 space-y-1.5">
          {data.signals.map((s, i) => (
            <p key={i} className={`text-xs ${s.type === "bullish" ? "text-success" : "text-destructive"}`}>
              {s.type === "bullish" ? "+" : "-"} {s.msg}
            </p>
          ))}
        </div>
      )}
    </Card>
  );
}

function DiscoverCard({ item }: { item: DiscoverResult }) {
  const flag = item.is_korean ? "🇰🇷" : "🇺🇸";
  return (
    <Card className="border-border bg-card p-4 transition hover:border-primary/20">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-semibold text-foreground">{flag} {item.name || item.ticker}</p>
          <p className="text-[10px] text-muted-foreground">{item.ticker}</p>
          <p className="text-[10px] text-muted-foreground">{item.sector}</p>
        </div>
        <Badge variant="outline" className={`text-[10px] font-semibold ${signalColor(item.signal)}`}>
          {item.signal}
        </Badge>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div>
          <p className="text-muted-foreground">Price</p>
          <p className="font-medium text-foreground">
            {item.currency === "KRW" ? `₩${item.price.toLocaleString()}` : `$${item.price.toFixed(2)}`}
          </p>
        </div>
        <div className="text-right">
          <p className="text-muted-foreground">Score</p>
          <p className="font-mono font-medium text-foreground">{item.score.toFixed(0)}</p>
        </div>
      </div>

      {/* Score bar */}
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div className={`h-full rounded-full ${scoreColor(item.score)}`} style={{ width: `${item.score}%` }} />
      </div>

      {item.signal === "BUY" && item.rec_shares > 0 && (
        <div className="mt-3 rounded-md border border-success/20 bg-success/5 px-2 py-1.5 text-[10px] text-success">
          Buy {item.rec_shares} shares = {fmtUsd(item.rec_investment)}
          {item.rec_timing && <span className="block text-success/70">{item.rec_timing}</span>}
        </div>
      )}

      <div className="mt-2 flex gap-3 text-[10px]">
        <span className="text-success">
          TP {item.currency === "KRW" ? `₩${item.take_profit.toLocaleString()}` : fmtUsd(item.take_profit)}
        </span>
        <span className="text-destructive">
          SL {item.currency === "KRW" ? `₩${item.stop_loss.toLocaleString()}` : fmtUsd(item.stop_loss)}
        </span>
      </div>

      {item.already_owned && (
        <Badge variant="secondary" className="mt-2 text-[9px]">Already Owned</Badge>
      )}
    </Card>
  );
}

const discoverFilters: { key: DiscoverFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "us", label: "🇺🇸 US" },
  { key: "kr", label: "🇰🇷 KR" },
  { key: "buy", label: "BUY Only" },
  { key: "gem", label: "Hidden Gem" },
];

export function ScannerTab() {
  const [ticker, setTicker] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [filter, setFilter] = useState<DiscoverFilter>("all");
  const { data: discover, isLoading: discoverLoading } = useDiscover();

  const handleScan = async () => {
    if (!ticker.trim()) return;
    setScanning(true);
    setScanResult(null);
    try {
      const res = await apiFetch<ScanResult>("/api/scan", {
        method: "POST",
        body: JSON.stringify({ ticker: ticker.trim().toUpperCase() }),
      });
      setScanResult(res);
    } catch {
      /* ignore */
    } finally {
      setScanning(false);
    }
  };

  const filteredDiscover = (() => {
    if (!discover?.results) return [];
    const r = discover.results;
    switch (filter) {
      case "us": return r.filter((x) => !x.is_korean);
      case "kr": return r.filter((x) => x.is_korean);
      case "buy": return r.filter((x) => x.signal === "BUY");
      case "gem": return r.filter((x) => x.score >= 65 && !x.already_owned);
      default: return [...r].sort((a, b) => b.priority - a.priority);
    }
  })();

  return (
    <div className="space-y-8">
      {/* Single Ticker Scanner */}
      <div>
        <p className="mb-3 font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground">
          Analyze Ticker
        </p>
        <div className="flex gap-2">
          <Input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleScan()}
            placeholder="e.g. AAPL, 005930.KS"
            className="max-w-xs bg-muted"
          />
          <Button onClick={handleScan} disabled={scanning} size="sm">
            {scanning ? "Scanning..." : "Scan"}
          </Button>
        </div>
        {scanResult && (
          <div className="mt-4 max-w-lg">
            <ScanResultCard data={scanResult} />
          </div>
        )}
      </div>

      {/* Auto-Scan 70 Stocks */}
      <div>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <p className="mr-auto font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground">
            Auto-Scan ({discover?.results.length ?? 0} stocks)
          </p>
          {discoverFilters.map((f) => (
            <Button
              key={f.key}
              variant={filter === f.key ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter(f.key)}
              className="h-7 text-[11px]"
            >
              {f.label}
            </Button>
          ))}
        </div>

        {discoverLoading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            <p className="mt-3 font-mono text-xs text-muted-foreground">Scanning 70 stocks...</p>
          </div>
        ) : filteredDiscover.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">No results</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filteredDiscover.map((item) => (
              <DiscoverCard key={item.ticker} item={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
