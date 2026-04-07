"use client";

import useSWR from "swr";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { pnlColor } from "@/lib/format";

interface Trade {
  id: number;
  ticker: string;
  name: string;
  action: string;
  shares: number;
  price_per_share: number;
  total_value: number;
  pnl: number;
  pnl_pct: number;
  currency: string;
  traded_at: string;
}

const fetcher = (url: string) => fetch(url, { credentials: "include" }).then((r) => r.json());

export default function TradesPage() {
  const { data } = useSWR<{ trades: Trade[] }>("/api/trades", fetcher);

  if (!data) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <h1 className="text-lg font-semibold text-foreground">Trade History</h1>

      {data.trades.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">No trades yet</p>
      ) : (
        <div className="space-y-2">
          {data.trades.map((t) => (
            <Card key={t.id} className="flex items-center justify-between border-border bg-card px-4 py-3">
              <div className="flex items-center gap-3">
                <Badge
                  variant="outline"
                  className={`text-[10px] font-semibold ${
                    t.action === "BUY"
                      ? "border-success/30 bg-success/10 text-success"
                      : "border-destructive/30 bg-destructive/10 text-destructive"
                  }`}
                >
                  {t.action}
                </Badge>
                <div>
                  <span className="text-sm font-medium text-foreground">{t.ticker}</span>
                  {t.name && <span className="ml-2 text-xs text-muted-foreground">{t.name}</span>}
                </div>
              </div>
              <div className="flex items-center gap-5 text-xs">
                <span className="text-muted-foreground">{t.shares} shares</span>
                <span className="text-foreground">
                  {t.currency === "KRW" ? "₩" : "$"}
                  {(t.price_per_share ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
                {t.pnl_pct != null && t.action === "SELL" && (
                  <span className={pnlColor(t.pnl_pct)}>
                    {t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct.toFixed(2)}%
                  </span>
                )}
                <span className="text-muted-foreground">
                  {new Date(t.traded_at).toLocaleDateString()}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
