"use client";

import { Card } from "@/components/ui/card";
import type { AnalyticsResponse } from "@/lib/types";

interface Props {
  data: AnalyticsResponse;
}

function metricColor(label: string, value: number): string {
  switch (label) {
    case "Ann. Return":
      return value >= 10 ? "text-success" : value >= 0 ? "text-warning" : "text-destructive";
    case "Sharpe":
      return value >= 1 ? "text-success" : value >= 0.5 ? "text-warning" : "text-destructive";
    case "Max DD":
      return "text-destructive";
    default:
      return "text-foreground";
  }
}

const icons: Record<string, React.ReactNode> = {
  "Ann. Return": (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M7 17l5-5 4 4 5-7" /><path d="M17 7h4v4" /></svg>
  ),
  "Volatility": (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M2 12h3l3-9 4 18 3-9h3l3 6h3" /></svg>
  ),
  "Sharpe": (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 2v20M2 12h20" /><circle cx="12" cy="12" r="4" /></svg>
  ),
  "Max DD": (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M7 7l5 5 4-4 5 7" /><path d="M17 17h4v-4" /></svg>
  ),
  "% Invested": (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10" /><path d="M12 2a10 10 0 0 1 0 20" fill="currentColor" opacity="0.15" /></svg>
  ),
};

export function AnalyticsBar({ data }: Props) {
  const metrics = [
    { label: "Ann. Return", value: data.ann_return_pct ?? 0, fmt: (v: number) => `${v.toFixed(1)}%` },
    { label: "Volatility", value: data.ann_vol_pct ?? 0, fmt: (v: number) => `${v.toFixed(1)}%` },
    { label: "Sharpe", value: data.sharpe_ratio ?? 0, fmt: (v: number) => v.toFixed(2) },
    { label: "Max DD", value: data.max_drawdown_pct ?? 0, fmt: (v: number) => `${v.toFixed(1)}%` },
    { label: "% Invested", value: data.invested_pct ?? 0, fmt: (v: number) => `${v.toFixed(0)}%` },
  ];

  return (
    <div className="grid grid-cols-5 gap-3">
      {metrics.map((m) => (
        <Card key={m.label} className="glass-card p-4 text-center">
          <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-muted/50 text-foreground/50">
            {icons[m.label]}
          </div>
          <p className="text-[10px] uppercase tracking-wider text-foreground/50">{m.label}</p>
          <p className={`mt-1 text-lg font-bold ${metricColor(m.label, m.value)}`}>
            {m.fmt(m.value)}
          </p>
        </Card>
      ))}
    </div>
  );
}
