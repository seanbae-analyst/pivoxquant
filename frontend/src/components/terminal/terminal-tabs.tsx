"use client";

import { useState } from "react";
import Link from "next/link";
import { usePortfolio, useMarketOverview, useDiscover } from "@/lib/hooks";
import { useRealtimeContext } from "@/lib/realtime";
import { fmtUsd, fmtPct, signalColor, pnlColor } from "@/lib/format";
import { AddPositionModal, QuickBuyModal, QuickSellModal, EditPositionModal, DeletePositionModal } from "@/components/dashboard/action-modals";

type Tab = "holdings" | "market" | "movers" | "discover";

export function TerminalTabs() {
  const [activeTab, setActiveTab] = useState<Tab>("holdings");

  const tabs: { key: Tab; label: string }[] = [
    { key: "holdings", label: "Holdings" },
    { key: "market", label: "Market" },
    { key: "movers", label: "Movers" },
    { key: "discover", label: "Discover" },
  ];

  return (
    <div className="flex flex-col h-full border-t border-slate-200">
      {/* Tab bar */}
      <div className="flex items-center gap-0.5 px-3 py-1.5 border-b border-slate-200 shrink-0 bg-slate-50">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`text-[11px] font-semibold px-3.5 py-1.5 rounded-lg spring-transition transition-all duration-300 ${
              activeTab === t.key
                ? "bg-emerald-50 text-emerald-600 border border-emerald-200"
                : "text-slate-400 hover:text-slate-700 hover:bg-slate-100"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto min-h-0 scrollbar-thin">
        {activeTab === "holdings" && <HoldingsTab />}
        {activeTab === "market" && <MarketTab />}
        {activeTab === "movers" && <MoversTab />}
        {activeTab === "discover" && <DiscoverTab />}
      </div>
    </div>
  );
}

function HoldingsTab() {
  const { data, mutate } = usePortfolio();
  const { updatedTickers } = useRealtimeContext();
  const positions = data?.positions ?? [];
  const refresh = () => mutate();

  if (!positions.length) {
    return (
      <div className="p-8 text-center">
        <div className="w-10 h-10 rounded-2xl bg-slate-50 border border-slate-200 flex items-center justify-center mx-auto mb-3">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-slate-400">
            <path d="M2 14 L5.5 9 L9 11 L12.5 5.5 L16 3.5" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M2 16 L16 16" strokeLinecap="round" />
          </svg>
        </div>
        <p className="text-slate-400 text-[12px] mb-3">No positions yet</p>
        <AddPositionModal onDone={refresh} />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Add Position button row */}
      <div className="flex items-center justify-end px-3 py-1.5 border-b border-slate-100 shrink-0">
        <AddPositionModal onDone={refresh} />
      </div>
      <div className="flex-1 overflow-y-auto min-h-0">
        <table className="w-full text-[11px]">
          <thead>
            <tr className="text-[9px] text-slate-400 uppercase tracking-[0.1em] text-left border-b border-slate-200 sticky top-0 bg-white z-10">
              <th className="px-4 py-2.5 font-semibold">Name</th>
              <th className="px-3 py-2.5 font-semibold text-right">Price</th>
              <th className="px-3 py-2.5 font-semibold text-right">P&L</th>
              <th className="px-3 py-2.5 font-semibold text-center">Signal</th>
              <th className="px-3 py-2.5 font-semibold text-right">Score</th>
              <th className="px-3 py-2.5 font-semibold text-right hidden md:table-cell">Value</th>
              <th className="px-3 py-2.5 font-semibold text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr
                key={p.id}
                className="border-t border-slate-100 hover:bg-slate-50 spring-transition transition-colors duration-300 cursor-pointer group"
              >
                <td className="px-4 py-2.5">
                  <Link href={`/detail/${p.ticker}`} className="group-hover:text-emerald-600 spring-transition transition-colors duration-300">
                    <p className="text-sm font-semibold text-slate-900">{p.name || p.ticker}</p>
                    <p className="text-[10px] text-slate-400 font-mono">{p.ticker}</p>
                  </Link>
                </td>
                <td className={`px-3 py-2.5 text-right font-mono text-slate-700 ${
                  updatedTickers.has(p.ticker)
                    ? updatedTickers.get(p.ticker) === "down" ? "price-flash-down" : "price-flash-up"
                    : ""
                }`}>{p.price_display}</td>
                <td className={`px-3 py-2.5 text-right font-mono font-medium ${pnlColor(p.pnl_pct)}`}>{fmtPct(p.pnl_pct)}</td>
                <td className="px-3 py-2.5 text-center">
                  <span className={`inline-block px-2 py-0.5 rounded-md text-[9px] font-bold border ${signalColor(p.signal)}`}>
                    {p.signal}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-right">
                  <span className="font-mono text-slate-500">{p.score}</span>
                </td>
                <td className="px-3 py-2.5 text-right font-mono text-slate-500 hidden md:table-cell">{fmtUsd(p.market_value)}</td>
                <td className="px-3 py-2.5 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <QuickBuyModal positionId={p.id} ticker={p.ticker} currentPrice={p.current_price} priceDisplay={p.price_display} recShares={p.rec_shares} currency={p.currency} onDone={refresh} />
                    <QuickSellModal positionId={p.id} ticker={p.ticker} currentPrice={p.current_price} priceDisplay={p.price_display} maxShares={p.shares} avgCost={p.avg_cost} currency={p.currency} onDone={refresh} />
                    <EditPositionModal positionId={p.id} ticker={p.ticker} currentShares={p.shares} currentAvgCost={p.avg_cost} currency={p.currency} onDone={refresh} />
                    <DeletePositionModal positionId={p.id} ticker={p.ticker} name={p.name || p.ticker} shares={p.shares} onDone={refresh} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MarketTab() {
  const { data } = useMarketOverview();
  if (!data) {
    return (
      <div className="p-8 flex items-center justify-center">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse mr-2" />
        <span className="text-slate-400 text-[12px]">Loading market data...</span>
      </div>
    );
  }

  const m = data.macro;
  const indices = [
    { label: "S&P 500", data: m.sp500 },
    { label: "NASDAQ", data: m.nasdaq },
    { label: "DOW", data: m.dow },
    { label: "KOSPI", data: m.kospi },
    { label: "BTC", data: m.btc },
    { label: "Gold", data: m.gold },
    { label: "Oil", data: m.oil_wti },
    { label: "USD/KRW", data: m.usdkrw },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-slate-100">
      {indices.map((idx) => (
        <div key={idx.label} className="bg-white px-4 py-3.5 hover:bg-slate-50 spring-transition transition-colors duration-300">
          <p className="text-[9px] text-slate-400 uppercase tracking-[0.1em] font-medium">{idx.label}</p>
          <p className="text-[15px] font-mono font-bold text-slate-900 mt-1">
            {idx.data.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </p>
          <p className={`text-[10px] font-mono font-semibold mt-0.5 ${pnlColor(idx.data.change_pct)}`}>
            {fmtPct(idx.data.change_pct)}
          </p>
        </div>
      ))}
      <div className="bg-white px-4 py-3.5">
        <p className="text-[9px] text-slate-400 uppercase tracking-[0.1em] font-medium">VIX</p>
        <p className={`text-[15px] font-mono font-bold mt-1 ${m.vix >= 30 ? "text-red-600" : m.vix >= 20 ? "text-amber-500" : "text-emerald-600"}`}>
          {m.vix.toFixed(1)}
        </p>
        <p className="text-[9px] text-slate-400 mt-0.5">Fear & Greed: {m.fear_greed.label}</p>
      </div>
      <div className="bg-white px-4 py-3.5">
        <p className="text-[9px] text-slate-400 uppercase tracking-[0.1em] font-medium">10Y Treasury</p>
        <p className="text-[15px] font-mono font-bold text-slate-900 mt-1">{m.treasury_10y.toFixed(2)}%</p>
        <p className="text-[9px] text-slate-400 mt-0.5">Yield {m.yield_curve.inverted ? "Inverted" : "Normal"}</p>
      </div>
      {data.gs_view && (
        <div className="bg-white px-4 py-3.5 col-span-2">
          <p className="text-[9px] text-slate-400 uppercase tracking-[0.1em] font-medium">GS View</p>
          <span className={`inline-block text-[9px] font-bold px-2 py-0.5 rounded-md mt-1.5 ${
            data.gs_view.bias === "BULLISH" ? "bg-emerald-50 text-emerald-600 border border-emerald-200"
            : data.gs_view.bias === "BEARISH" ? "bg-red-50 text-red-600 border border-red-200"
            : "bg-amber-50 text-amber-600 border border-amber-200"
          }`}>{data.gs_view.bias}</span>
          <p className="text-[10px] text-slate-500 mt-1.5 line-clamp-1">{data.gs_view.bias_note}</p>
        </div>
      )}
    </div>
  );
}

function MoversTab() {
  const { data } = usePortfolio();
  const positions = data?.positions ?? [];
  const sorted = [...positions].sort((a, b) => b.pnl_pct - a.pnl_pct);
  const gainers = sorted.slice(0, 5);
  const losers = sorted.slice(-5).reverse();

  return (
    <div className="grid grid-cols-2 divide-x divide-slate-200">
      <div>
        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-200 bg-emerald-50/50">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          <p className="text-[9px] text-emerald-600 font-bold uppercase tracking-[0.15em]">Top Gainers</p>
        </div>
        {gainers.map((p) => (
          <div key={p.id} className="flex items-center justify-between px-4 py-2.5 hover:bg-slate-50 spring-transition transition-colors duration-300">
            <Link href={`/detail/${p.ticker}`} className="hover:text-emerald-600 spring-transition transition-colors">
              <p className="text-sm font-semibold text-slate-900">{p.name || p.ticker}</p>
              <p className="text-[10px] text-slate-400 font-mono">{p.ticker}</p>
            </Link>
            <span className={`text-[11px] font-mono font-semibold ${pnlColor(p.pnl_pct)}`}>{fmtPct(p.pnl_pct)}</span>
          </div>
        ))}
      </div>
      <div>
        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-200 bg-red-50/50">
          <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
          <p className="text-[9px] text-red-600 font-bold uppercase tracking-[0.15em]">Top Losers</p>
        </div>
        {losers.map((p) => (
          <div key={p.id} className="flex items-center justify-between px-4 py-2.5 hover:bg-slate-50 spring-transition transition-colors duration-300">
            <Link href={`/detail/${p.ticker}`} className="hover:text-emerald-600 spring-transition transition-colors">
              <p className="text-sm font-semibold text-slate-900">{p.name || p.ticker}</p>
              <p className="text-[10px] text-slate-400 font-mono">{p.ticker}</p>
            </Link>
            <span className={`text-[11px] font-mono font-semibold ${pnlColor(p.pnl_pct)}`}>{fmtPct(p.pnl_pct)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function DiscoverTab() {
  const { data } = useDiscover();
  const results = data?.results ?? [];

  if (!results.length) {
    return (
      <div className="p-8 flex items-center justify-center">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse mr-2" />
        <span className="text-slate-400 text-[12px]">Scanning for opportunities...</span>
      </div>
    );
  }

  return (
    <div>
      {results.slice(0, 8).map((r) => (
        <div key={r.ticker} className="flex items-center justify-between px-4 py-3 border-b border-slate-100 hover:bg-slate-50 spring-transition transition-colors duration-300 group">
          <div className="flex items-center gap-3">
            <span className={`text-[8px] font-bold px-2 py-0.5 rounded-md border ${signalColor(r.signal)}`}>{r.signal}</span>
            <div>
              <p className="text-sm font-semibold text-slate-900 group-hover:text-emerald-600 spring-transition transition-colors">{r.name || r.ticker}</p>
              <p className="text-[10px] text-slate-400 font-mono">{r.ticker}</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-[10px] font-mono text-slate-400">{r.score}</span>
            <span className={`text-[11px] font-mono font-semibold ${pnlColor(r.change_pct)}`}>{fmtPct(r.change_pct)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
