"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { useDiscover } from "@/lib/hooks";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { pnlColor, signalColor, scoreColor, fmtUsd } from "@/lib/format";
import type { ScanResult, DiscoverResult } from "@/lib/types";

type DiscoverFilter = "all" | "us" | "kr" | "buy" | "gem";

function ScanResultCard({ data }: { data: ScanResult }) {
  return (
    <div className="bezel-card">
      <div className="bezel-card-inner !p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-semibold text-white">{data.name}</p>
            <p className="text-[10px] text-zinc-600 font-mono">{data.ticker}</p>
          </div>
          <span className={`text-[9px] font-bold px-2.5 py-1 rounded-lg border ${signalColor(data.signal)}`}>
            {data.signal}
          </span>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-3 text-center">
          <div className="rounded-xl bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.04)] p-3">
            <p className="text-[9px] font-semibold text-zinc-600 uppercase tracking-wider">Score</p>
            <p className="text-xl font-bold font-mono text-white mt-1">{data.score.toFixed(0)}/100</p>
            <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-[rgba(255,255,255,0.06)]">
              <div className={`h-full rounded-full ${scoreColor(data.score)}`} style={{ width: `${data.score}%` }} />
            </div>
          </div>
          <div className="rounded-xl bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.04)] p-3">
            <p className="text-[9px] font-semibold text-zinc-600 uppercase tracking-wider">Price</p>
            <p className="text-xl font-bold font-mono text-white mt-1">
              {data.is_korean ? `₩${data.price.toLocaleString()}` : `$${data.price.toFixed(2)}`}
            </p>
          </div>
          <div className="rounded-xl bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.04)] p-3">
            <p className="text-[9px] font-semibold text-zinc-600 uppercase tracking-wider">Change</p>
            <p className={`text-xl font-bold font-mono mt-1 ${pnlColor(data.change_pct)}`}>
              {data.change_pct >= 0 ? "+" : ""}{data.change_pct.toFixed(2)}%
            </p>
          </div>
        </div>

        <div className="mt-4 flex justify-center gap-6 text-sm font-mono">
          <span className="text-emerald-400">TP {data.is_korean ? `₩${data.take_profit.toLocaleString()}` : fmtUsd(data.take_profit)}</span>
          <span className="text-red-400">SL {data.is_korean ? `₩${data.stop_loss.toLocaleString()}` : fmtUsd(data.stop_loss)}</span>
        </div>

        {data.signals.length > 0 && (
          <div className="mt-4 space-y-1.5">
            {data.signals.map((s, i) => (
              <p key={i} className={`text-xs ${s.type === "bullish" ? "text-emerald-400" : "text-red-400"}`}>
                {s.type === "bullish" ? "+" : "-"} {s.msg}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function DiscoverCard({ item }: { item: DiscoverResult }) {
  return (
    <div className="bezel-card">
      <div className="bezel-card-inner !p-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-semibold text-white">{item.name || item.ticker}</p>
            <p className="text-[10px] text-zinc-600 font-mono">{item.ticker}</p>
            <p className="text-[10px] text-zinc-700">{item.sector}</p>
          </div>
          <span className={`text-[9px] font-bold px-2 py-0.5 rounded-md border ${signalColor(item.signal)}`}>
            {item.signal}
          </span>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div>
            <p className="text-zinc-600 text-[9px]">Price</p>
            <p className="font-medium font-mono text-white">
              {item.currency === "KRW" ? `₩${item.price.toLocaleString()}` : `$${item.price.toFixed(2)}`}
            </p>
          </div>
          <div className="text-right">
            <p className="text-zinc-600 text-[9px]">Score</p>
            <p className="font-mono font-medium text-white">{item.score.toFixed(0)}</p>
          </div>
        </div>

        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-[rgba(255,255,255,0.06)]">
          <div className={`h-full rounded-full ${scoreColor(item.score)}`} style={{ width: `${item.score}%` }} />
        </div>

        {item.signal === "BUY" && item.rec_shares > 0 && (
          <div className="mt-3 rounded-lg border border-emerald-500/15 bg-emerald-500/5 px-3 py-2 text-[10px] text-emerald-400">
            Buy {item.rec_shares} shares = {fmtUsd(item.rec_investment)}
            {item.rec_timing && <span className="block text-emerald-400/70 mt-0.5">{item.rec_timing}</span>}
          </div>
        )}

        <div className="mt-2.5 flex gap-3 text-[10px] font-mono">
          <span className="text-emerald-400">
            TP {item.currency === "KRW" ? `₩${item.take_profit.toLocaleString()}` : fmtUsd(item.take_profit)}
          </span>
          <span className="text-red-400">
            SL {item.currency === "KRW" ? `₩${item.stop_loss.toLocaleString()}` : fmtUsd(item.stop_loss)}
          </span>
        </div>

        {item.already_owned && (
          <span className="mt-2 inline-block rounded-lg px-2.5 py-1 text-[9px] font-bold bg-amber-500/8 text-amber-400 border border-amber-500/20">Already Owned</span>
        )}
      </div>
    </div>
  );
}

const discoverFilters: { key: DiscoverFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "us", label: "US" },
  { key: "kr", label: "KR" },
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
      const res = await apiFetch<ScanResult>(API.signals.scan, {
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
        <p className="mb-3 font-mono text-[9px] font-semibold uppercase tracking-[1.5px] text-zinc-600">
          Analyze Ticker
        </p>
        <div className="flex gap-2">
          <Input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleScan()}
            placeholder="e.g. AAPL, 005930.KS"
            className="max-w-xs"
          />
          <button onClick={handleScan} disabled={scanning} className="rounded-xl px-5 py-2 text-sm font-semibold border border-emerald-500/20 bg-emerald-500/8 text-emerald-400 hover:bg-emerald-500/15 spring-transition transition-all duration-300 disabled:opacity-50">
            {scanning ? "Scanning..." : "Scan"}
          </button>
        </div>
        {scanResult && (
          <div className="mt-4 max-w-lg">
            <ScanResultCard data={scanResult} />
          </div>
        )}
      </div>

      {/* Auto-Scan */}
      <div>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <p className="mr-auto font-mono text-[9px] font-semibold uppercase tracking-[1.5px] text-zinc-600">
            Auto-Scan ({discover?.results.length ?? 0} stocks)
          </p>
          {discoverFilters.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`rounded-lg px-3.5 py-1.5 text-[11px] font-semibold spring-transition transition-all duration-300 border ${
                filter === f.key
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                  : "border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)] text-zinc-500 hover:text-zinc-300 hover:bg-[rgba(255,255,255,0.04)]"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {discoverLoading ? (
          <div className="flex flex-col items-center justify-center py-24">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="mt-3 text-zinc-600 text-[12px]">Scanning stocks...</span>
          </div>
        ) : filteredDiscover.length === 0 ? (
          <div className="rounded-2xl border border-[rgba(255,255,255,0.04)] bg-[var(--db-surface)] py-16 text-center">
            <p className="text-sm text-zinc-600">No results matching filter</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filteredDiscover.map((item) => (
              <DiscoverCard key={item.ticker} item={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
