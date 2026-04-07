"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { fmtUsd, fmtPct, pnlColor, signalColor, scoreColor } from "@/lib/format";
import type { Position } from "@/lib/types";

interface Props {
  position: Position;
}

export function PositionCard({ position: p }: Props) {
  const displayName = p.is_korean ? p.ticker : p.name;
  const displayTicker = p.is_korean ? p.name : p.ticker;

  return (
    <Link href={`/detail/${encodeURIComponent(p.ticker)}`}>
      <Card className="cursor-pointer border-border bg-card p-5 transition hover:border-primary/20 hover:shadow-[0_0_20px_rgba(59,139,255,0.06)]">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-semibold text-foreground">{displayName}</p>
            <p className="text-xs text-muted-foreground">
              {displayTicker}
              {p.is_korean && <span className="ml-1">🇰🇷</span>}
              {p.sector === "ETF" && <span className="ml-1">📦</span>}
            </p>
          </div>
          <Badge
            variant="outline"
            className={`text-[10px] font-semibold ${signalColor(p.signal)}`}
          >
            {p.signal}
          </Badge>
        </div>

        {/* Recommendation strip */}
        {p.signal === "BUY" && p.rec_shares > 0 && (
          <div className="mt-3 rounded-lg border border-success/20 bg-success/5 px-3 py-2 text-xs text-success">
            Add {p.rec_shares} shares @ {p.price_display} = {fmtUsd(p.rec_investment)}
          </div>
        )}
        {p.signal === "SELL" && p.sell_pct > 0 && (
          <div className="mt-3 rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-xs text-destructive">
            Sell {p.sell_pct}% of position
          </div>
        )}

        {/* Data grid */}
        <div className="mt-4 grid grid-cols-2 gap-y-3 text-xs">
          <div>
            <p className="text-muted-foreground">Shares</p>
            <p className="font-medium text-foreground">{p.shares}</p>
          </div>
          <div className="text-right">
            <p className="text-muted-foreground">Current Price</p>
            <p className="font-medium text-foreground">{p.price_display}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Avg Cost</p>
            <p className="font-medium text-foreground">{fmtUsd(p.avg_cost)}</p>
          </div>
          <div className="text-right">
            <p className="text-muted-foreground">P&L</p>
            <p className={`font-medium ${pnlColor(p.pnl_pct)}`}>
              {fmtPct(p.pnl_pct)}
              {p.pnl_krw_pct != null && (
                <span className="ml-1 text-[10px] text-muted-foreground">
                  ({fmtPct(p.pnl_krw_pct)} ₩)
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Score bar */}
        <div className="mt-4">
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-muted-foreground">Quant Score</span>
            <span className="font-mono font-medium text-foreground">{p.score}/100</span>
          </div>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={`h-full rounded-full transition-all ${scoreColor(p.score)}`}
              style={{ width: `${p.score}%` }}
            />
          </div>
        </div>

        {/* TP/SL */}
        {(p.take_profit || p.stop_loss) && (
          <div className="mt-3 flex gap-3 text-[10px]">
            {p.take_profit && (
              <span className="text-success">
                TP {fmtUsd(p.take_profit)} ({fmtPct(p.tp_pct)})
              </span>
            )}
            {p.stop_loss && (
              <span className="text-destructive">
                SL {fmtUsd(p.stop_loss)} ({fmtPct(p.sl_pct)})
              </span>
            )}
          </div>
        )}

        {/* Click hint */}
        <p className="mt-3 text-center text-[9px] text-muted-foreground/40">
          Tap to analyze · buy · sell
        </p>
      </Card>
    </Link>
  );
}
