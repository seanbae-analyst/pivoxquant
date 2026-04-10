"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { QuickBuyModal, QuickSellModal, EditPositionModal, DeletePositionModal } from "@/components/dashboard/action-modals";
import { fmtUsd, fmtPct, pnlColor, signalColor, scoreColor } from "@/lib/format";
import type { Position } from "@/lib/types";

interface Props {
  position: Position;
  onUpdate?: () => void;
}

export function PositionCard({ position: p, onUpdate }: Props) {
  const displayName = p.name || p.ticker;

  const signalBg = p.signal === "BUY"
    ? "bg-success/10 text-success border-success/20"
    : p.signal === "SELL"
      ? "bg-destructive/10 text-destructive border-destructive/20"
      : "bg-muted text-muted-foreground border-border";

  return (
    <Card className="glass-card group overflow-hidden transition-all duration-300 hover:border-primary/15 hover:shadow-lg hover:shadow-primary/5">
      {/* Header */}
      <div className="flex items-start justify-between p-5 pb-0">
        <div className="min-w-0 flex-1">
          <p className="truncate text-base font-bold text-foreground">{displayName}</p>
          <p className="mt-0.5 text-[11px] text-foreground/50">
            {p.ticker}{p.is_korean ? " · KRX" : ""}{p.sector !== "Unknown" ? ` · ${p.sector}` : ""}
          </p>
        </div>
        <Badge variant="outline" className={`border text-[10px] font-bold ${signalBg}`}>
          {p.signal}
        </Badge>
      </div>

      {/* Price & P&L hero */}
      <div className="px-5 pt-4">
        <div className="flex items-end justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-wider text-foreground/50">Current</p>
            <p className="text-lg font-bold text-foreground">{p.price_display}</p>
          </div>
          <div className="text-right">
            <p className="text-[10px] uppercase tracking-wider text-foreground/50">P&L</p>
            <p className={`text-lg font-bold ${pnlColor(p.pnl_pct)}`}>
              {p.pnl_pct >= 0 ? "+" : ""}{fmtPct(p.pnl_pct)}
            </p>
          </div>
        </div>
        {p.pnl_krw_pct != null && (
          <p className="mt-1 text-right text-[10px] text-foreground/40">
            KRW {p.pnl_krw_pct >= 0 ? "+" : ""}{fmtPct(p.pnl_krw_pct)}
          </p>
        )}
      </div>

      {/* Recommendation */}
      {p.signal === "BUY" && p.rec_shares > 0 && (
        <div className="mx-5 mt-3 rounded-lg border border-success/15 bg-success/5 px-3 py-2">
          <p className="text-xs font-medium text-success">
            Add {p.rec_shares} shares @ {p.price_display}
          </p>
          {p.rec_timing && (
            <p className="mt-0.5 text-[10px] text-success/60">{p.rec_timing}</p>
          )}
        </div>
      )}
      {p.signal === "SELL" && p.sell_pct > 0 && (
        <div className="mx-5 mt-3 rounded-lg border border-destructive/15 bg-destructive/5 px-3 py-2">
          <p className="text-xs font-medium text-destructive">
            Sell {p.sell_pct}% of position
          </p>
        </div>
      )}

      {/* Data grid */}
      <div className="mt-4 grid grid-cols-2 gap-y-3 border-t border-border/50 px-5 py-4 text-xs">
        <div>
          <p className="text-foreground/50">Shares</p>
          <p className="mt-0.5 font-medium text-foreground">{p.shares}</p>
        </div>
        <div className="text-right">
          <p className="text-foreground/50">Avg Cost</p>
          <p className="mt-0.5 font-medium text-foreground">{fmtUsd(p.avg_cost)}</p>
        </div>
        <div>
          <p className="text-foreground/50">Market Value</p>
          <p className="mt-0.5 font-medium text-foreground">{fmtUsd(p.market_value)}</p>
        </div>
        <div className="text-right">
          <p className="text-foreground/50">Sector</p>
          <p className="mt-0.5 font-medium text-foreground">{p.sector}</p>
        </div>
      </div>

      {/* Score */}
      <div className="border-t border-border/50 px-5 py-3">
        <div className="flex items-center justify-between text-[10px]">
          <span className="uppercase tracking-wider text-foreground/50">Quant Score</span>
          <span className={`font-mono font-bold ${scoreColor(p.score)}`}>{p.score}/100</span>
        </div>
        <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={`h-full rounded-full transition-all duration-700 ${scoreColor(p.score)}`}
            style={{ width: `${p.score}%` }}
          />
        </div>
      </div>

      {/* TP/SL */}
      {(p.take_profit || p.stop_loss) && (
        <div className="flex gap-4 border-t border-border/50 px-5 py-2.5 text-[10px]">
          {p.take_profit && (
            <span className="text-success/70">TP {fmtUsd(p.take_profit)} <span className="text-success/40">({fmtPct(p.tp_pct)})</span></span>
          )}
          {p.stop_loss && (
            <span className="text-destructive/70">SL {fmtUsd(p.stop_loss)} <span className="text-destructive/40">({fmtPct(p.sl_pct)})</span></span>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-1.5 border-t border-border/50 p-3">
        <Link href={`/detail/${encodeURIComponent(p.ticker)}`} className="flex-1">
          <Button variant="outline" size="sm" className="h-8 w-full text-[11px] font-medium text-primary hover:bg-primary/10 hover:border-primary/30">
            Analyze
          </Button>
        </Link>
        <QuickBuyModal
          positionId={p.id}
          ticker={p.ticker}
          currentPrice={p.current_price}
          priceDisplay={p.price_display}
          recShares={p.rec_shares}
          currency={p.currency}
          onDone={() => onUpdate?.()}
        />
        <QuickSellModal
          positionId={p.id}
          ticker={p.ticker}
          currentPrice={p.current_price}
          priceDisplay={p.price_display}
          maxShares={p.shares}
          avgCost={p.avg_cost}
          currency={p.currency}
          onDone={() => onUpdate?.()}
        />
        <EditPositionModal
          positionId={p.id}
          ticker={p.ticker}
          currentShares={p.shares}
          currentAvgCost={p.avg_cost}
          currency={p.currency}
          onDone={() => onUpdate?.()}
        />
        <DeletePositionModal
          positionId={p.id}
          ticker={p.ticker}
          name={displayName}
          shares={p.shares}
          onDone={() => onUpdate?.()}
        />
      </div>
    </Card>
  );
}
