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
  const { positions, total_value_usd, total_value_krw, total_value_all_krw, available_capital, available_capital_krw, fx_rate } = data;

  const buyCount = positions.filter((p) => p.signal === "BUY").length;
  const sellCount = positions.filter((p) => p.signal === "SELL").length;
  const avgScore = positions.length
    ? Math.round(positions.reduce((s, p) => s + p.score, 0) / positions.length)
    : 0;

  const investedBasis = positions.reduce((s, p) => s + p.avg_cost * p.shares, 0);
  const totalPnlPct = investedBasis > 0 ? ((total_value_usd - investedBasis) / investedBasis) * 100 : 0;

  return (
    <div className="space-y-4">
      {/* Hero Value */}
      <Card className="glass-card glow-blue overflow-hidden border-l-4 border-l-[#003a70] p-6 md:p-8">
        <div className="flex items-start justify-between">
          <div>
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-foreground/50">
              Total Portfolio Value
            </p>
            <p className="mt-2 text-3xl font-extrabold tracking-tight text-[#0a1929] md:text-4xl">
              {fmtUsd(total_value_usd)}
            </p>
            <div className="mt-2 flex items-center gap-3">
              <span className={`text-sm font-semibold ${pnlColor(totalPnlPct)}`}>
                {totalPnlPct >= 0 ? "+" : ""}{fmtPct(totalPnlPct)}
              </span>
              {total_value_all_krw > 0 && (
                <span className="text-xs text-muted-foreground">
                  {fmtKrw(total_value_all_krw)}
                </span>
              )}
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
              avgScore >= 65 ? "bg-success/10 text-success" : avgScore >= 40 ? "bg-warning/10 text-warning" : "bg-destructive/10 text-destructive"
            }`}>
              <span className="h-1.5 w-1.5 rounded-full bg-current" />
              Score {avgScore}/100
            </span>
            {fx_rate > 0 && (
              <span className="text-[10px] text-foreground/40">
                USD/KRW {fx_rate.toLocaleString()}
              </span>
            )}
          </div>
        </div>
      </Card>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card className="glass-card p-5">
          <div className="flex items-center justify-between">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-foreground/50">
              Available Capital
            </p>
            {onRefresh && (
              <EditCapitalModal currentUsd={available_capital} currentKrw={available_capital_krw} onDone={onRefresh} />
            )}
          </div>
          <p className="mt-2 text-xl font-extrabold tracking-tight text-[#0a1929]">
            {fmtUsd(available_capital)}
          </p>
          {available_capital_krw > 0 && (
            <p className="mt-1 text-xs text-muted-foreground">
              {fmtKrw(available_capital_krw)}
            </p>
          )}
        </Card>

        <Card className="glass-card p-5">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-foreground/50">
            Positions
          </p>
          <p className="mt-2 text-xl font-extrabold tracking-tight text-[#0a1929]">
            {positions.length}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {positions.filter(p => !p.is_korean).length} US / {positions.filter(p => p.is_korean).length} KR
          </p>
        </Card>

        <Card className="glass-card p-5">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-foreground/50">
            Signals
          </p>
          <div className="mt-2 flex items-baseline gap-3">
            <span className="text-xl font-bold text-success">{buyCount} BUY</span>
            {sellCount > 0 && (
              <span className="text-sm font-semibold text-destructive">{sellCount} SELL</span>
            )}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {positions.filter(p => p.signal === "HOLD").length} HOLD
          </p>
        </Card>

        <Card className="glass-card p-5">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-foreground/50">
            Quant Score
          </p>
          <p className="mt-2 text-xl font-extrabold tracking-tight text-[#0a1929]">
            {avgScore}<span className="text-sm font-normal text-muted-foreground">/100</span>
          </p>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={`h-full rounded-full transition-all duration-700 ${
                avgScore >= 70 ? "bg-success" : avgScore >= 45 ? "bg-warning" : "bg-destructive"
              }`}
              style={{ width: `${avgScore}%` }}
            />
          </div>
        </Card>
      </div>
    </div>
  );
}
