"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { QuickBuyModal, QuickSellModal } from "@/components/dashboard/action-modals";
import { fmtUsd, fmtPct, pnlColor, signalColor, scoreColor } from "@/lib/format";
import { apiFetch } from "@/lib/api";
import type { Position } from "@/lib/types";

interface Props {
  position: Position;
  onUpdate?: () => void;
}

export function PositionCard({ position: p, onUpdate }: Props) {
  const displayName = p.name || p.ticker;  // 항상 이름이 위
  const displayTicker = p.ticker;

  const handleDelete = async () => {
    if (!confirm(`Delete ${p.ticker} from portfolio?`)) return;
    await apiFetch(`/api/portfolio/position/${p.id}`, { method: "DELETE" });
    onUpdate?.();
  };

  return (
    <Card className="border-border bg-card p-5 transition hover:border-primary/20 hover:shadow-[0_0_20px_rgba(59,139,255,0.06)]">
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
        <Badge variant="outline" className={`text-[10px] font-semibold ${signalColor(p.signal)}`}>
          {p.signal}
        </Badge>
      </div>

      {/* Recommendation strip */}
      {p.signal === "BUY" && p.rec_shares > 0 && (
        <div className="mt-3 rounded-lg border border-success/20 bg-success/5 px-3 py-2 text-xs text-success">
          Add {p.rec_shares} shares @ {p.price_display} = {fmtUsd(p.rec_investment)}
          {p.rec_timing && <span className="block text-[10px] text-success/70">{p.rec_timing}</span>}
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
              <span className="ml-1 text-[10px] text-muted-foreground">({fmtPct(p.pnl_krw_pct)} ₩)</span>
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
          <div className={`h-full rounded-full transition-all ${scoreColor(p.score)}`} style={{ width: `${p.score}%` }} />
        </div>
      </div>

      {/* TP/SL */}
      {(p.take_profit || p.stop_loss) && (
        <div className="mt-3 flex gap-3 text-[10px]">
          {p.take_profit && <span className="text-success">TP {fmtUsd(p.take_profit)} ({fmtPct(p.tp_pct)})</span>}
          {p.stop_loss && <span className="text-destructive">SL {fmtUsd(p.stop_loss)} ({fmtPct(p.sl_pct)})</span>}
        </div>
      )}

      {/* ── Action Buttons ── */}
      <div className="mt-4 flex gap-1.5">
        <Link href={`/detail/${encodeURIComponent(p.ticker)}`} className="flex-1">
          <Button variant="outline" size="sm" className="h-7 w-full text-[10px] text-primary hover:bg-primary/10">
            Analyze
          </Button>
        </Link>
        <QuickBuyModal
          positionId={p.id}
          ticker={p.ticker}
          currentPrice={p.current_price}
          priceDisplay={p.price_display}
          recShares={p.rec_shares}
          onDone={() => onUpdate?.()}
        />
        <QuickSellModal
          positionId={p.id}
          ticker={p.ticker}
          currentPrice={p.current_price}
          priceDisplay={p.price_display}
          maxShares={p.shares}
          onDone={() => onUpdate?.()}
        />
        <Button
          variant="outline"
          size="sm"
          className="h-7 w-7 p-0 text-[10px] text-destructive/50 hover:bg-destructive/10 hover:text-destructive"
          onClick={handleDelete}
        >
          ✕
        </Button>
      </div>
    </Card>
  );
}
