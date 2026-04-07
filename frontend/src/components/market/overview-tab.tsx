"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useMarketOverview, useCrossAsset, useVixStrategy, useSectors } from "@/lib/hooks";
import { pnlColor } from "@/lib/format";
import type { CrossAssetItem, SectorItem } from "@/lib/types";

/* Safe accessor — API shape varies, some keys may be missing */
function idx(macro: Record<string, unknown>, key: string): { price: number; change_pct: number } | null {
  const v = macro[key];
  if (v && typeof v === "object" && "price" in (v as Record<string, unknown>)) {
    const obj = v as { price: number; change_pct: number };
    return obj;
  }
  return null;
}

function num(macro: Record<string, unknown>, key: string): number | null {
  const v = macro[key];
  return typeof v === "number" ? v : null;
}

function IndexCard({ label, price, change }: { label: string; price: number; change: number }) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <p className="text-[10px] text-muted-foreground">{label}</p>
      <p className="mt-1 text-base font-bold text-foreground">
        {price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
      </p>
      <p className={`text-xs font-medium ${pnlColor(change)}`}>
        {change >= 0 ? "+" : ""}{change.toFixed(2)}%
      </p>
    </div>
  );
}

function FearGreedGauge({ value, label }: { value: number; label: string }) {
  const color =
    value >= 75 ? "text-success" : value >= 50 ? "text-warning" : value >= 25 ? "text-warning" : "text-destructive";
  return (
    <div className="flex flex-col items-center rounded-lg border border-border bg-card p-4">
      <p className="text-[10px] text-muted-foreground">Fear & Greed</p>
      <p className={`mt-2 text-3xl font-bold ${color}`}>{value}</p>
      <p className={`text-xs font-medium ${color}`}>{label}</p>
    </div>
  );
}

function CrossAssetSection({ data }: { data: { macro_label: string; ranking: CrossAssetItem[] } }) {
  return (
    <Card className="border-border bg-card p-5">
      <div className="mb-3 flex items-center justify-between">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground">
          Cross-Asset Momentum
        </p>
        <Badge variant="outline" className="text-[10px]">{data.macro_label}</Badge>
      </div>
      <div className="space-y-2">
        {data.ranking.map((item) => (
          <div key={item.ticker} className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-2 text-xs">
            <div>
              <span className="font-medium text-foreground">{item.ticker}</span>
              <span className="ml-2 text-muted-foreground">{item.name}</span>
            </div>
            <div className="flex gap-4 text-right">
              <div>
                <p className="text-[10px] text-muted-foreground">1M</p>
                <p className={pnlColor(item.return_1m ?? 0)}>
                  {(item.return_1m ?? 0) >= 0 ? "+" : ""}{(item.return_1m ?? 0).toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground">3M</p>
                <p className={pnlColor(item.return_3m ?? 0)}>
                  {(item.return_3m ?? 0) >= 0 ? "+" : ""}{(item.return_3m ?? 0).toFixed(1)}%
                </p>
              </div>
              {item.sharpe != null && (
                <div>
                  <p className="text-[10px] text-muted-foreground">Sharpe</p>
                  <p className={pnlColor(item.sharpe)}>{item.sharpe.toFixed(2)}</p>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function VixSection({ data }: { data: { vix: number; regime: string; exposure: number; action: string; color: string } }) {
  return (
    <Card className="border-border bg-card p-5">
      <p className="mb-3 font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground">
        VIX Strategy
      </p>
      <div className="grid grid-cols-3 gap-4 text-center">
        <div>
          <p className="text-[10px] text-muted-foreground">VIX</p>
          <p className="text-2xl font-bold" style={{ color: data.color }}>{data.vix.toFixed(1)}</p>
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground">Regime</p>
          <p className="mt-1 text-sm font-medium text-foreground">{data.regime.replace(/_/g, " ")}</p>
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground">Exposure</p>
          <p className="text-2xl font-bold text-foreground">{(data.exposure * 100).toFixed(0)}%</p>
        </div>
      </div>
      <p className="mt-3 text-center text-xs text-muted-foreground">{data.action}</p>
    </Card>
  );
}

function SectorHeatmap({ sectors }: { sectors: SectorItem[] }) {
  return (
    <Card className="border-border bg-card p-5">
      <p className="mb-3 font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground">
        Sector Performance
      </p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        {sectors.map((s) => (
          <div
            key={s.sector}
            className={`rounded-lg border p-3 text-center ${
              s.change_pct >= 0 ? "border-success/20 bg-success/5" : "border-destructive/20 bg-destructive/5"
            }`}
          >
            <p className="text-[11px] font-medium text-foreground">{s.sector}</p>
            <p className={`text-lg font-bold ${pnlColor(s.change_pct)}`}>
              {s.change_pct >= 0 ? "+" : ""}{s.change_pct.toFixed(2)}%
            </p>
          </div>
        ))}
      </div>
    </Card>
  );
}

export function OverviewTab() {
  const { data: overview } = useMarketOverview();
  const { data: crossAsset } = useCrossAsset();
  const { data: vix } = useVixStrategy();
  const { data: sectors } = useSectors();

  if (!overview) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  const m = overview.macro as unknown as Record<string, unknown>;
  const yc = (m.yield_curve as { t3m?: number; t5y?: number; t10y?: number; t30y?: number; inverted?: boolean; spread?: number }) ?? {};

  // Dynamically build index cards from available data
  const indexCards: { label: string; price: number; change: number }[] = [];
  const indexMap: [string, string][] = [
    ["sp500", "S&P 500"], ["nasdaq", "NASDAQ"], ["dow", "Dow Jones"], ["russell2000", "Russell 2000"],
  ];
  for (const [key, label] of indexMap) {
    const d = idx(m, key);
    if (d) indexCards.push({ label, price: d.price, change: d.change_pct });
  }

  const krCards: { label: string; price: number; change: number }[] = [];
  const krMap: [string, string][] = [["kospi", "KOSPI"], ["kosdaq", "KOSDAQ"], ["usdkrw", "USD/KRW"]];
  for (const [key, label] of krMap) {
    const d = idx(m, key);
    if (d) krCards.push({ label, price: d.price, change: d.change_pct });
  }

  const miscCards: { label: string; price: number; change: number }[] = [];
  const miscMap: [string, string][] = [
    ["dxy", "DXY"], ["eurusd", "EUR/USD"], ["oil_wti", "WTI Oil"], ["gold", "Gold"],
    ["silver", "Silver"], ["btc", "Bitcoin"],
  ];
  for (const [key, label] of miscMap) {
    const d = idx(m, key);
    if (d) miscCards.push({ label, price: d.price, change: d.change_pct });
  }

  const vixVal = num(m, "vix");
  const t10y = num(m, "treasury_10y");
  const fg = m.fear_greed as { value: number; label: string } | undefined;

  // yield curve bars
  const ycBars = [
    { label: "3M", value: yc.t3m },
    { label: "5Y", value: yc.t5y },
    { label: "10Y", value: yc.t10y },
    { label: "30Y", value: yc.t30y },
  ].filter((b) => b.value != null) as { label: string; value: number }[];

  return (
    <div className="space-y-6">
      {/* GS Analyst View */}
      <Card className="border-border bg-card p-5">
        <div className="flex items-center gap-3">
          <Badge
            variant="outline"
            className={`text-xs font-semibold ${
              overview.gs_view.bias === "BULLISH"
                ? "border-success/30 bg-success/10 text-success"
                : overview.gs_view.bias === "BEARISH"
                  ? "border-destructive/30 bg-destructive/10 text-destructive"
                  : "border-warning/30 bg-warning/10 text-warning"
            }`}
          >
            {overview.gs_view.bias}
          </Badge>
          <p className="text-sm text-muted-foreground">{overview.gs_view.bias_note}</p>
        </div>
        {overview.gs_view.themes.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {overview.gs_view.themes.map((t, i) => (
              <Badge key={i} variant="secondary" className="text-[10px]">{t}</Badge>
            ))}
          </div>
        )}
      </Card>

      {/* US Equities */}
      {indexCards.length > 0 && (
        <div>
          <p className="mb-2 font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground">
            US Equity Indices
          </p>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {indexCards.map((c) => <IndexCard key={c.label} {...c} />)}
          </div>
        </div>
      )}

      {/* Korean Markets */}
      {krCards.length > 0 && (
        <div>
          <p className="mb-2 font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground">
            Korean Markets
          </p>
          <div className={`grid gap-3 grid-cols-${krCards.length}`}>
            {krCards.map((c) => <IndexCard key={c.label} {...c} />)}
          </div>
        </div>
      )}

      {/* Volatility, Rates, Commodities */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {vixVal != null && (
          <div className="rounded-lg border border-border bg-card p-3 text-center">
            <p className="text-[10px] text-muted-foreground">VIX</p>
            <p className={`text-xl font-bold ${vixVal > 25 ? "text-destructive" : vixVal > 18 ? "text-warning" : "text-success"}`}>
              {vixVal.toFixed(1)}
            </p>
          </div>
        )}
        {t10y != null && (
          <div className="rounded-lg border border-border bg-card p-3 text-center">
            <p className="text-[10px] text-muted-foreground">10Y Treasury</p>
            <p className="text-xl font-bold text-foreground">{t10y.toFixed(2)}%</p>
          </div>
        )}
        {miscCards.map((c) => <IndexCard key={c.label} {...c} />)}
      </div>

      {/* Yield Curve */}
      {ycBars.length > 0 && (
        <Card className="border-border bg-card p-5">
          <div className="mb-3 flex items-center gap-2">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground">
              US Yield Curve
            </p>
            {yc.inverted && (
              <Badge variant="outline" className="border-destructive/30 bg-destructive/10 text-[10px] text-destructive">
                INVERTED
              </Badge>
            )}
          </div>
          <div className="flex items-end gap-4">
            {ycBars.map((y) => (
              <div key={y.label} className="flex flex-1 flex-col items-center">
                <p className="mb-1 text-xs font-medium text-foreground">{y.value.toFixed(2)}%</p>
                <div className="w-full rounded-t bg-primary" style={{ height: `${Math.max(y.value * 15, 8)}px` }} />
                <p className="mt-1 font-mono text-[10px] text-muted-foreground">{y.label}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Fear & Greed */}
      {fg && <FearGreedGauge value={fg.value} label={fg.label} />}

      {/* Cross-Asset Momentum */}
      {crossAsset && <CrossAssetSection data={crossAsset} />}

      {/* VIX Strategy */}
      {vix && <VixSection data={vix} />}

      {/* Sector Heatmap */}
      {sectors && sectors.length > 0 && <SectorHeatmap sectors={sectors} />}
    </div>
  );
}
