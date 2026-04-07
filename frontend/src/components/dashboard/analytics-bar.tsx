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

export function AnalyticsBar({ data }: Props) {
  const metrics = [
    { label: "Ann. Return", value: data.ann_return_pct ?? 0, fmt: (v: number) => `${v.toFixed(1)}%` },
    { label: "Volatility", value: data.ann_vol_pct ?? 0, fmt: (v: number) => `${v.toFixed(1)}%` },
    { label: "Sharpe", value: data.sharpe_ratio ?? 0, fmt: (v: number) => v.toFixed(2) },
    { label: "Max DD", value: data.max_drawdown_pct ?? 0, fmt: (v: number) => `${v.toFixed(1)}%` },
    { label: "% Invested", value: data.invested_pct ?? 0, fmt: (v: number) => `${v.toFixed(0)}%` },
  ];

  return (
    <Card className="border-border bg-card p-4">
      <div className="grid grid-cols-5 gap-2">
        {metrics.map((m) => (
          <div key={m.label} className="text-center">
            <p className="text-[11px] text-muted-foreground">{m.label}</p>
            <p className={`mt-1 text-xl font-bold ${metricColor(m.label, m.value)}`}>
              {m.fmt(m.value)}
            </p>
          </div>
        ))}
      </div>
    </Card>
  );
}
