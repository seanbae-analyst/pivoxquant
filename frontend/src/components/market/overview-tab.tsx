"use client";

import { useMarketOverview, useCrossAsset, useVixStrategy, useSectors } from "@/lib/hooks";
import { pnlColor } from "@/lib/format";
import type { CrossAssetItem, SectorItem } from "@/lib/types";

/* Safe accessor */
function idx(macro: Record<string, unknown>, key: string): { price: number; change_pct: number } | null {
  const v = macro[key];
  if (v && typeof v === "object" && "price" in (v as Record<string, unknown>)) {
    return v as { price: number; change_pct: number };
  }
  return null;
}
function num(macro: Record<string, unknown>, key: string): number | null {
  const v = macro[key];
  return typeof v === "number" ? v : null;
}

function IndexCard({ label, price, change }: { label: string; price: number; change: number }) {
  return (
    <div className="bezel-card group">
      <div className="bezel-card-inner !p-3.5">
        <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
        <p className="mt-1.5 text-xl font-bold font-mono text-slate-900">
          {price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
        </p>
        <p className={`mt-0.5 text-sm font-semibold font-mono ${pnlColor(change)}`}>
          {change >= 0 ? "+" : ""}{change.toFixed(2)}%
        </p>
      </div>
    </div>
  );
}

function CrossAssetSection({ data }: { data: { macro_label: string; ranking: CrossAssetItem[] } }) {
  return (
    <div className="bezel-card">
      <div className="bezel-card-inner !p-5">
        <div className="mb-4 flex items-center justify-between">
          <p className="font-mono text-[10px] font-semibold uppercase tracking-[1.2px] text-slate-400">
            Cross-Asset Momentum
          </p>
          <span className="rounded-lg px-2.5 py-1 text-[9px] font-bold bg-amber-50 text-amber-600 border border-amber-200">{data.macro_label}</span>
        </div>
        <div className="space-y-1">
          {data.ranking.map((item, i) => (
            <div key={item.ticker} className={`flex items-center justify-between rounded-xl px-3.5 py-3 text-xs spring-transition transition-all duration-300 hover:bg-slate-50 ${i % 2 === 0 ? "bg-slate-50/50" : ""}`}>
              <div className="flex items-center gap-3">
                <span className="w-6 h-6 rounded-lg bg-slate-50 flex items-center justify-center font-mono text-[10px] text-slate-400 font-bold">{i + 1}</span>
                <div>
                  <p className="text-sm font-semibold text-slate-900">{item.name || item.ticker}</p>
                  <p className="text-[10px] text-slate-400 font-mono">{item.ticker}</p>
                </div>
              </div>
              <div className="flex gap-6 text-right">
                <div>
                  <p className="text-[8px] uppercase text-slate-400 tracking-wider">1M</p>
                  <p className={`font-medium font-mono ${pnlColor(item.return_1m ?? 0)}`}>
                    {(item.return_1m ?? 0) >= 0 ? "+" : ""}{(item.return_1m ?? 0).toFixed(1)}%
                  </p>
                </div>
                <div>
                  <p className="text-[8px] uppercase text-slate-400 tracking-wider">3M</p>
                  <p className={`font-medium font-mono ${pnlColor(item.return_3m ?? 0)}`}>
                    {(item.return_3m ?? 0) >= 0 ? "+" : ""}{(item.return_3m ?? 0).toFixed(1)}%
                  </p>
                </div>
                {item.sharpe != null && (
                  <div>
                    <p className="text-[8px] uppercase text-slate-400 tracking-wider">Sharpe</p>
                    <p className={`font-medium font-mono ${pnlColor(item.sharpe)}`}>{item.sharpe.toFixed(2)}</p>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function VixSection({ data }: { data: { vix: number; regime: string; exposure: number; action: string; color: string } }) {
  return (
    <div className="bezel-card">
      <div className="bezel-card-inner !p-5">
        <p className="mb-5 font-mono text-[10px] font-semibold uppercase tracking-[1.2px] text-slate-400">
          VIX Strategy
        </p>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="rounded-xl bg-slate-50 border border-slate-200 p-4">
            <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">VIX</p>
            <p className="text-3xl font-bold font-mono mt-1" style={{ color: data.color }}>{data.vix.toFixed(1)}</p>
          </div>
          <div className="rounded-xl bg-slate-50 border border-slate-200 p-4">
            <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">Regime</p>
            <p className="mt-2 text-sm font-semibold text-slate-900 capitalize">{data.regime.replace(/_/g, " ")}</p>
          </div>
          <div className="rounded-xl bg-slate-50 border border-slate-200 p-4">
            <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">Exposure</p>
            <p className="text-3xl font-bold font-mono text-slate-900 mt-1">{(data.exposure * 100).toFixed(0)}%</p>
          </div>
        </div>
        <p className="mt-4 rounded-xl bg-slate-50 border border-slate-200 px-4 py-3 text-center text-xs text-slate-500">{data.action}</p>
      </div>
    </div>
  );
}

function SectorHeatmap({ sectors }: { sectors: SectorItem[] }) {
  return (
    <div className="bezel-card">
      <div className="bezel-card-inner !p-5">
        <p className="mb-4 font-mono text-[10px] font-semibold uppercase tracking-[1.2px] text-slate-400">
          Sector Performance
        </p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {sectors.map((s) => (
            <div
              key={s.sector}
              className={`rounded-xl border p-3.5 text-center spring-transition transition-all duration-300 hover:scale-[1.02] ${
                s.change_pct >= 0
                  ? "border-emerald-200 bg-emerald-50"
                  : "border-red-200 bg-red-50"
              }`}
            >
              <p className="text-[11px] font-medium text-slate-500">{s.sector}</p>
              <p className={`mt-1.5 text-base font-bold font-mono ${pnlColor(s.change_pct)}`}>
                {s.change_pct >= 0 ? "+" : ""}{s.change_pct.toFixed(2)}%
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function OverviewTab() {
  const { data: overview } = useMarketOverview();
  const { data: crossAsset } = useCrossAsset();
  const { data: vix } = useVixStrategy();
  const { data: sectors } = useSectors();

  if (!overview) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
        <span className="mt-3 text-slate-400 text-[12px]">Loading market data...</span>
      </div>
    );
  }

  const m = overview.macro as unknown as Record<string, unknown>;
  const yc = (m.yield_curve as { t3m?: number; t5y?: number; t10y?: number; t30y?: number; inverted?: boolean }) ?? {};

  const indexCards: { label: string; price: number; change: number }[] = [];
  for (const [key, label] of [["sp500", "S&P 500"], ["nasdaq", "NASDAQ"], ["dow", "Dow Jones"], ["russell2000", "Russell 2000"]] as const) {
    const d = idx(m, key);
    if (d) indexCards.push({ label, price: d.price, change: d.change_pct });
  }

  const krCards: { label: string; price: number; change: number }[] = [];
  for (const [key, label] of [["kospi", "KOSPI"], ["kosdaq", "KOSDAQ"], ["usdkrw", "USD/KRW"]] as const) {
    const d = idx(m, key);
    if (d) krCards.push({ label, price: d.price, change: d.change_pct });
  }

  const miscCards: { label: string; price: number; change: number }[] = [];
  for (const [key, label] of [["dxy", "DXY"], ["eurusd", "EUR/USD"], ["oil_wti", "WTI Oil"], ["gold", "Gold"], ["silver", "Silver"], ["btc", "Bitcoin"]] as const) {
    const d = idx(m, key);
    if (d) miscCards.push({ label, price: d.price, change: d.change_pct });
  }

  const vixVal = num(m, "vix");
  const t10y = num(m, "treasury_10y");
  const fg = m.fear_greed as { value: number; label: string } | undefined;
  const ycBars = [
    { label: "3M", value: yc.t3m }, { label: "5Y", value: yc.t5y },
    { label: "10Y", value: yc.t10y }, { label: "30Y", value: yc.t30y },
  ].filter((b) => b.value != null) as { label: string; value: number }[];

  return (
    <div className="space-y-4">
      {/* GS Analyst View */}
      <div className="bezel-card">
        <div className="bezel-card-inner !p-5">
          <div className="flex items-center gap-3">
            <span className="text-[8px] font-bold uppercase tracking-[0.15em] text-slate-400">GS View</span>
            <span
              className={`rounded-lg px-2.5 py-1 text-[9px] font-bold border ${
                overview.gs_view.bias === "BULLISH"
                  ? "bg-emerald-50 text-emerald-600 border-emerald-200"
                  : overview.gs_view.bias === "BEARISH"
                    ? "bg-red-50 text-red-600 border-red-200"
                    : "bg-amber-50 text-amber-600 border-amber-200"
              }`}
            >
              {overview.gs_view.bias}
            </span>
            <p className="text-sm text-slate-500">{overview.gs_view.bias_note}</p>
          </div>
          {overview.gs_view.themes?.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {overview.gs_view.themes.map((t: string, i: number) => (
                <span key={i} className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-1.5 text-[10px] font-medium text-slate-500">
                  {t}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* US Indices */}
      {indexCards.length > 0 && (
        <div>
          <p className="mb-2.5 font-mono text-[9px] font-semibold uppercase tracking-[1.5px] text-slate-400">
            US Equity Indices
          </p>
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
            {indexCards.map((c) => <IndexCard key={c.label} {...c} />)}
          </div>
        </div>
      )}

      {/* Korean Markets */}
      {krCards.length > 0 && (
        <div>
          <p className="mb-2.5 font-mono text-[9px] font-semibold uppercase tracking-[1.5px] text-slate-400">
            Korean Markets
          </p>
          <div className="grid grid-cols-3 gap-2">
            {krCards.map((c) => <IndexCard key={c.label} {...c} />)}
          </div>
        </div>
      )}

      {/* Volatility & Macro */}
      <div>
        <p className="mb-2.5 font-mono text-[9px] font-semibold uppercase tracking-[1.5px] text-slate-400">
          Volatility & Macro
        </p>
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          {vixVal != null && (
            <div className="bezel-card group">
              <div className="bezel-card-inner !p-3.5 text-center">
                <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">VIX</p>
                <p className={`mt-2 text-2xl font-bold font-mono ${vixVal > 25 ? "text-red-600" : vixVal > 18 ? "text-amber-600" : "text-emerald-600"}`}>
                  {vixVal.toFixed(1)}
                </p>
              </div>
            </div>
          )}
          {t10y != null && (
            <div className="bezel-card group">
              <div className="bezel-card-inner !p-3.5 text-center">
                <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">10Y Treasury</p>
                <p className="mt-2 text-2xl font-bold font-mono text-slate-900">{t10y.toFixed(2)}%</p>
              </div>
            </div>
          )}
          {fg && (
            <div className="bezel-card group">
              <div className="bezel-card-inner !p-3.5 text-center">
                <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">Fear & Greed</p>
                <p className={`mt-2 text-2xl font-bold font-mono ${fg.value >= 50 ? "text-emerald-600" : fg.value >= 25 ? "text-amber-600" : "text-red-600"}`}>
                  {fg.value}
                </p>
                <p className={`text-[10px] font-medium mt-0.5 ${fg.value >= 50 ? "text-emerald-600/60" : fg.value >= 25 ? "text-amber-600/60" : "text-red-600/60"}`}>
                  {fg.label}
                </p>
              </div>
            </div>
          )}
          {miscCards.slice(0, fg ? 1 : 2).map((c) => <IndexCard key={c.label} {...c} />)}
        </div>
      </div>

      {/* Commodities & Currencies */}
      {miscCards.length > (fg ? 1 : 2) && (
        <div>
          <p className="mb-2.5 font-mono text-[9px] font-semibold uppercase tracking-[1.5px] text-slate-400">
            Commodities & Currencies
          </p>
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
            {miscCards.slice(fg ? 1 : 2).map((c) => <IndexCard key={c.label} {...c} />)}
          </div>
        </div>
      )}

      {/* Yield Curve */}
      {ycBars.length > 0 && (
        <div className="bezel-card">
          <div className="bezel-card-inner !p-5">
            <div className="mb-5 flex items-center gap-3">
              <p className="font-mono text-[10px] font-semibold uppercase tracking-[1.2px] text-slate-400">
                US Yield Curve
              </p>
              {yc.inverted && (
                <span className="rounded-lg px-2.5 py-1 text-[9px] font-bold bg-red-50 text-red-600 border border-red-200">
                  INVERTED
                </span>
              )}
            </div>
            <div className="flex items-end gap-5">
              {ycBars.map((y) => (
                <div key={y.label} className="flex flex-1 flex-col items-center">
                  <p className="mb-1.5 text-xs font-bold font-mono text-slate-900">{y.value.toFixed(2)}%</p>
                  <div
                    className="w-full rounded-t-lg bg-gradient-to-t from-emerald-600/60 to-emerald-400"
                    style={{ height: `${Math.max(y.value * 18, 10)}px` }}
                  />
                  <p className="mt-2 font-mono text-[10px] text-slate-400">{y.label}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Cross-Asset Momentum */}
      {crossAsset && <CrossAssetSection data={crossAsset} />}

      {/* VIX Strategy */}
      {vix && <VixSection data={vix} />}

      {/* Sector Heatmap */}
      {sectors && sectors.length > 0 && <SectorHeatmap sectors={sectors} />}
    </div>
  );
}
