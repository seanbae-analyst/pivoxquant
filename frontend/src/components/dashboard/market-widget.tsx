"use client";

import { useMarketOverview } from "@/lib/hooks";
import { TrendingUp, TrendingDown, AlertTriangle } from "lucide-react";
import Link from "next/link";

export function MarketWidget() {
  const { data } = useMarketOverview();

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center rounded-2xl border border-[var(--ld-border)] bg-[var(--ld-surface)] p-6">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-sky-600" />
      </div>
    );
  }

  const macro = data.macro as Record<string, unknown>;
  const indices: { key: string; label: string; data: { price: number; change_pct: number } | null }[] = [
    "sp500", "nasdaq", "dow", "kospi", "btc",
  ].map((key) => {
    const label = key === "sp500" ? "S&P 500" : key === "nasdaq" ? "NASDAQ" : key === "dow" ? "DOW" : key === "kospi" ? "KOSPI" : "BTC";
    const v = macro[key];
    if (v && typeof v === "object" && "price" in (v as Record<string, unknown>)) {
      return { key, label, data: v as { price: number; change_pct: number } };
    }
    return { key, label, data: null };
  });

  const vix = typeof macro.vix === "number" ? macro.vix : null;
  const fg = (data as unknown as Record<string, unknown>).fear_greed as { value: number; label: string } | undefined;

  return (
    <Link href="/market" className="block h-full">
      <div className="flex h-full flex-col rounded-2xl border border-[var(--ld-border)] bg-[var(--ld-surface-2)] p-5 transition-all duration-300 hover:border-[var(--ld-border-light)]">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-500">Market Snapshot</h3>
          {vix != null && (
            <div className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-bold ${
              vix >= 30 ? "bg-red-50 text-red-600" : vix >= 20 ? "bg-amber-50 text-amber-600" : "bg-emerald-50 text-emerald-600"
            }`}>
              <AlertTriangle size={10} />
              VIX {vix.toFixed(1)}
            </div>
          )}
        </div>
        <div className="flex-1 space-y-2.5">
          {indices.map(({ key, label, data: d }) => d && (
            <div key={key} className="flex items-center justify-between">
              <span className="text-xs text-slate-500">{label}</span>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-semibold text-slate-700">
                  {d.price.toLocaleString(undefined, { maximumFractionDigits: key === "btc" ? 0 : 2 })}
                </span>
                <span className={`flex items-center gap-0.5 font-mono text-[10px] font-bold ${d.change_pct >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                  {d.change_pct >= 0 ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                  {d.change_pct >= 0 ? "+" : ""}{d.change_pct.toFixed(2)}%
                </span>
              </div>
            </div>
          ))}
        </div>
        {fg && (
          <div className="mt-4 border-t border-[var(--ld-border)] pt-3">
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-slate-400">Fear &amp; Greed</span>
              <span className="font-bold text-slate-500">{fg.value} — {fg.label}</span>
            </div>
          </div>
        )}
      </div>
    </Link>
  );
}
