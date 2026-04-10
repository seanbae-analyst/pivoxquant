"use client";

import { useState } from "react";
import { mutate } from "swr";
import { Input } from "@/components/ui/input";
import { BuyNewModal } from "@/components/dashboard/action-modals";
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
            <p className="text-sm font-semibold text-slate-900">{data.name}</p>
            <p className="text-[10px] text-slate-400 font-mono">{data.ticker}</p>
          </div>
          <span className={`text-[9px] font-bold px-2.5 py-1 rounded-lg border ${signalColor(data.signal)}`}>
            {data.signal}
          </span>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-3 text-center">
          <div className="rounded-xl bg-slate-50 border border-slate-200 p-3">
            <p className="text-[9px] font-semibold text-slate-400 uppercase tracking-wider">Score</p>
            <p className="text-xl font-bold font-mono text-slate-900 mt-1">{data.score.toFixed(0)}/100</p>
            <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-slate-100">
              <div className={`h-full rounded-full ${scoreColor(data.score)}`} style={{ width: `${data.score}%` }} />
            </div>
          </div>
          <div className="rounded-xl bg-slate-50 border border-slate-200 p-3">
            <p className="text-[9px] font-semibold text-slate-400 uppercase tracking-wider">Price</p>
            <p className="text-xl font-bold font-mono text-slate-900 mt-1">
              {data.is_korean ? `₩${data.price.toLocaleString()}` : `$${data.price.toFixed(2)}`}
            </p>
          </div>
          <div className="rounded-xl bg-slate-50 border border-slate-200 p-3">
            <p className="text-[9px] font-semibold text-slate-400 uppercase tracking-wider">Change</p>
            <p className={`text-xl font-bold font-mono mt-1 ${pnlColor(data.change_pct)}`}>
              {data.change_pct >= 0 ? "+" : ""}{data.change_pct.toFixed(2)}%
            </p>
          </div>
        </div>

        <div className="mt-4 flex justify-center gap-6 text-sm font-mono">
          <span className="text-emerald-600">TP {data.is_korean ? `₩${data.take_profit.toLocaleString()}` : fmtUsd(data.take_profit)}</span>
          <span className="text-red-600">SL {data.is_korean ? `₩${data.stop_loss.toLocaleString()}` : fmtUsd(data.stop_loss)}</span>
        </div>

        {data.signals.length > 0 && (
          <div className="mt-4 space-y-1.5">
            {data.signals.map((s, i) => (
              <p key={i} className={`text-xs ${s.type === "bullish" ? "text-emerald-600" : "text-red-600"}`}>
                {s.type === "bullish" ? "+" : "-"} {s.msg}
              </p>
            ))}
          </div>
        )}

        {data.signal === "BUY" && (
          <div className="mt-4">
            <BuyNewModal
              ticker={data.ticker}
              name={data.name}
              currentPrice={data.price}
              priceDisplay={data.is_korean ? `\u20A9${data.price.toLocaleString()}` : `$${data.price.toFixed(2)}`}
              currency={data.is_korean ? "KRW" : "USD"}
              onDone={() => mutate(API.portfolio.list)}
            />
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
            <p className="text-sm font-semibold text-slate-900">{item.name || item.ticker}</p>
            <p className="text-[10px] text-slate-400 font-mono">{item.ticker}</p>
            <p className="text-[10px] text-slate-400">{item.sector}</p>
          </div>
          <span className={`text-[9px] font-bold px-2 py-0.5 rounded-md border ${signalColor(item.signal)}`}>
            {item.signal}
          </span>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div>
            <p className="text-slate-400 text-[9px]">Price</p>
            <p className="font-medium font-mono text-slate-900">
              {item.currency === "KRW" ? `₩${item.price.toLocaleString()}` : `$${item.price.toFixed(2)}`}
            </p>
          </div>
          <div className="text-right">
            <p className="text-slate-400 text-[9px]">Score</p>
            <p className="font-mono font-medium text-slate-900">{item.score.toFixed(0)}</p>
          </div>
        </div>

        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div className={`h-full rounded-full ${scoreColor(item.score)}`} style={{ width: `${item.score}%` }} />
        </div>

        {item.signal === "BUY" && item.rec_shares > 0 && !item.already_owned && (
          <div className="mt-3 flex items-center gap-2">
            <BuyNewModal
              ticker={item.ticker}
              name={item.name}
              currentPrice={item.price}
              priceDisplay={item.currency === "KRW" ? `\u20A9${item.price.toLocaleString()}` : `$${item.price.toFixed(2)}`}
              recShares={item.rec_shares}
              currency={item.currency}
              onDone={() => mutate(API.portfolio.list)}
            />
            <span className="text-[10px] text-emerald-600">
              {item.rec_shares} shares = {fmtUsd(item.rec_investment)}
            </span>
          </div>
        )}

        <div className="mt-2.5 flex gap-3 text-[10px] font-mono">
          <span className="text-emerald-600">
            TP {item.currency === "KRW" ? `₩${item.take_profit.toLocaleString()}` : fmtUsd(item.take_profit)}
          </span>
          <span className="text-red-600">
            SL {item.currency === "KRW" ? `₩${item.stop_loss.toLocaleString()}` : fmtUsd(item.stop_loss)}
          </span>
        </div>

        {item.already_owned && (
          <span className="mt-2 inline-block rounded-lg px-2.5 py-1 text-[9px] font-bold bg-amber-50 text-amber-600 border border-amber-200">Already Owned</span>
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
        <p className="mb-3 font-mono text-[9px] font-semibold uppercase tracking-[1.5px] text-slate-400">
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
          <button onClick={handleScan} disabled={scanning} className="rounded-xl px-5 py-2 text-sm font-semibold border border-emerald-200 bg-emerald-50 text-emerald-600 hover:bg-emerald-100 spring-transition transition-all duration-300 disabled:opacity-50">
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
          <p className="mr-auto font-mono text-[9px] font-semibold uppercase tracking-[1.5px] text-slate-400">
            Auto-Scan ({discover?.results.length ?? 0} stocks)
          </p>
          {discoverFilters.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`rounded-lg px-3.5 py-1.5 text-[11px] font-semibold spring-transition transition-all duration-300 border ${
                filter === f.key
                  ? "bg-emerald-50 text-emerald-600 border-emerald-200"
                  : "border-slate-200 bg-slate-50 text-slate-500 hover:text-slate-700 hover:bg-slate-100"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {discoverLoading ? (
          <div className="flex flex-col items-center justify-center py-24">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="mt-3 text-slate-400 text-[12px]">Scanning stocks...</span>
          </div>
        ) : filteredDiscover.length === 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-[var(--db-surface)] py-16 text-center">
            <p className="text-sm text-slate-400">No results matching filter</p>
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
