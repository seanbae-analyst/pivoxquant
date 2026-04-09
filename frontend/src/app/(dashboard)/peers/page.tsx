"use client";

import { useState } from "react";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { Users, BarChart3 } from "lucide-react";

interface Peer {
  ticker: string;
  name: string;
  price: number;
  market_cap: number;
  pe_ratio: number;
  revenue_growth: number;
  profit_margin: number;
}

interface PeersResponse {
  ticker: string;
  peers: Peer[];
}

const fetcher = (url: string) =>
  fetch(url, { credentials: "include" }).then((r) => r.json());

function formatMarketCap(v: number) {
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  return `$${v.toLocaleString()}`;
}

function formatPct(v: number) {
  const sign = v >= 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(1)}%`;
}

export default function PeersPage() {
  const [input, setInput] = useState("");
  const [ticker, setTicker] = useState<string | null>(null);

  const { data, isLoading, error } = useSWR<PeersResponse>(
    ticker ? API.market.peers(ticker) : null,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 120_000 },
  );

  const handleSearch = () => {
    const t = input.trim().toUpperCase();
    if (t) setTicker(t);
  };

  const columns = [
    "Ticker",
    "Name",
    "Price",
    "Market Cap",
    "P/E",
    "Rev Growth",
    "Margin",
  ];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Peer Comparison
        </h1>
        <p className="mt-1 text-[13px] text-zinc-600">
          Compare a stock against its industry peers
        </p>
      </div>

      {/* Search */}
      <div className="flex gap-3">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Enter ticker (e.g. AAPL)"
          className="max-w-xs bg-white/[0.03] border-white/[0.06] text-white placeholder:text-zinc-700 focus:border-cyan-500/30 rounded-xl"
        />
        <Button
          onClick={handleSearch}
          disabled={!input.trim()}
          className="gap-2 bg-gradient-to-r from-cyan-500/10 to-emerald-500/10 text-cyan-400 border border-cyan-500/20 rounded-xl spring-transition"
        >
          <BarChart3 size={16} />
          Compare
        </Button>
      </div>

      {/* Content */}
      {!ticker ? (
        <div className="glass-surface rounded-2xl py-12 text-center">
          <Users className="mx-auto h-10 w-10 text-zinc-600" />
          <p className="mt-3 text-[13px] text-zinc-600">
            Enter a ticker above to see peer comparison.
          </p>
        </div>
      ) : isLoading ? (
        <div className="flex items-center justify-center py-20">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse mr-2" />
          <span className="text-zinc-600 text-[12px]">Loading...</span>
        </div>
      ) : error || !data?.peers?.length ? (
        <div className="glass-surface rounded-2xl py-12 text-center">
          <Users className="mx-auto h-10 w-10 text-zinc-600" />
          <p className="mt-3 text-[13px] text-zinc-600">
            No peer data found for {ticker}.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto glass-surface rounded-xl">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.06]">
                {columns.map((col) => (
                  <th
                    key={col}
                    className="px-5 py-3.5 text-left text-[10px] font-semibold uppercase tracking-[0.1em] text-zinc-600"
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.peers.map((peer) => {
                const isMain =
                  peer.ticker.toUpperCase() === ticker.toUpperCase();
                return (
                  <tr
                    key={peer.ticker}
                    className={`border-b border-white/[0.06] last:border-b-0 spring-transition transition-all duration-300 ${
                      isMain
                        ? "bg-cyan-500/[0.04]"
                        : "hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)] hover:bg-white/[0.02]"
                    }`}
                  >
                    <td className="px-5 py-4">
                      <span
                        className={`font-semibold ${isMain ? "text-cyan-400" : "text-white"}`}
                      >
                        {peer.ticker}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-zinc-300">
                      {peer.name}
                    </td>
                    <td className="px-5 py-4 font-mono text-zinc-300">
                      ${peer.price.toFixed(2)}
                    </td>
                    <td className="px-5 py-4 font-mono text-zinc-300">
                      {formatMarketCap(peer.market_cap)}
                    </td>
                    <td className="px-5 py-4 font-mono text-zinc-300">
                      {peer.pe_ratio > 0
                        ? peer.pe_ratio.toFixed(1)
                        : "N/A"}
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`font-mono ${peer.revenue_growth >= 0 ? "text-emerald-400" : "text-red-400"}`}
                      >
                        {formatPct(peer.revenue_growth)}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`font-mono ${peer.profit_margin >= 0 ? "text-emerald-400" : "text-red-400"}`}
                      >
                        {formatPct(peer.profit_margin)}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
