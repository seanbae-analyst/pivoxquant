"use client";

import { Card } from "@/components/ui/card";
import { EditCapitalModal } from "@/components/dashboard/action-modals";
import { fmtUsd, fmtKrw, fmtPct, pnlColor } from "@/lib/format";
import type { PortfolioResponse } from "@/lib/types";

interface Props {
  data: PortfolioResponse;
  onRefresh?: () => void;
}

export function SummaryCards({ data, onRefresh }: Props) {
  const { positions, total_value_usd, total_value_krw, available_capital, available_capital_krw } = data;

  const buyCount = positions.filter((p) => p.signal === "BUY").length;
  const sellCount = positions.filter((p) => p.signal === "SELL").length;
  const avgScore = positions.length
    ? Math.round(positions.reduce((s, p) => s + p.score, 0) / positions.length)
    : 0;

  const investedBasis = positions.reduce((s, p) => s + p.avg_cost * p.shares, 0);
  const totalPnlPct = investedBasis > 0 ? ((total_value_usd - investedBasis) / investedBasis) * 100 : 0;

  const cards = [
    {
      label: "Portfolio Value",
      value: fmtUsd(total_value_usd),
      sub: total_value_krw > 0 ? fmtKrw(total_value_krw) : undefined,
      extra: fmtPct(totalPnlPct),
      extraClass: pnlColor(totalPnlPct),
    },
    {
      label: "Available Capital",
      value: fmtUsd(available_capital),
      sub: available_capital_krw > 0 ? fmtKrw(available_capital_krw) : undefined,
      editable: true,
    },
    {
      label: "Signals",
      value: `${buyCount} BUY`,
      sub: sellCount > 0 ? `${sellCount} SELL` : undefined,
      extraClass: sellCount > 0 ? "text-destructive" : undefined,
    },
    {
      label: "Avg Quant Score",
      value: `${avgScore}/100`,
      bar: avgScore,
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {cards.map((c) => (
        <Card
          key={c.label}
          className="border-border bg-gradient-to-br from-card to-secondary p-5"
        >
          <div className="flex items-center justify-between">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground">
              {c.label}
            </p>
            {c.editable && onRefresh && (
              <EditCapitalModal currentUsd={available_capital} currentKrw={available_capital_krw} onDone={onRefresh} />
            )}
          </div>
          <p className="mt-2 text-2xl font-bold tracking-tight text-foreground">
            {c.value}
            {c.extra && (
              <span className={`ml-2 text-sm font-medium ${c.extraClass}`}>
                {c.extra}
              </span>
            )}
          </p>
          {c.sub && (
            <p className={`mt-1 text-xs font-medium ${c.extraClass ?? "text-muted-foreground"}`}>
              {c.sub}
            </p>
          )}
          {c.bar !== undefined && (
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={`h-full rounded-full transition-all ${
                  c.bar >= 70
                    ? "bg-success"
                    : c.bar >= 45
                      ? "bg-warning"
                      : "bg-destructive"
                }`}
                style={{ width: `${c.bar}%` }}
              />
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}
