"use client";

import useSWR from "swr";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import { fmtUsd, fmtKrw } from "@/lib/format";

interface AutoTradeStatus {
  running: boolean;
  available: boolean;
  positions: number;
  positions_us: number;
  positions_kr: number;
  max_positions: number;
  max_daily_trades: number;
  trades_today: number;
  kr_equity: number;
  kr_capital: number;
  kr_daily_pnl: number;
  account: {
    equity?: number;
    cash?: number;
    buying_power?: number;
    daily_pnl?: number;
    portfolio_value?: number;
  };
  active_positions: Array<{
    ticker: string;
    qty: number;
    current_price: number;
    market_value: number;
    unrealized_pl: number;
    unrealized_plpc: number;
    side: string;
  }>;
  logs: Array<{ time: string; msg: string }>;
}

const fetcher = (url: string) => fetch(url, { credentials: "include" }).then((r) => r.json());

export default function AutoTradePage() {
  const { data, mutate } = useSWR<AutoTradeStatus>("/api/autotrade/status", fetcher, {
    refreshInterval: 10_000,
  });

  const toggleRunning = async () => {
    if (!data) return;
    await apiFetch(`/api/autotrade/${data.running ? "stop" : "start"}`, { method: "POST" });
    mutate();
  };

  if (!data) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  const acct = data.account ?? {};

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Auto Trade</h1>
          <p className="text-sm text-muted-foreground">Paper Trading Mode</p>
        </div>
        <div className="flex items-center gap-3">
          <Badge
            variant="outline"
            className={`font-semibold ${
              data.running
                ? "border-success/30 bg-success/10 text-success"
                : "border-border text-muted-foreground"
            }`}
          >
            {data.running ? "RUNNING" : "STOPPED"}
          </Badge>
          <Button
            variant={data.running ? "destructive" : "default"}
            size="sm"
            onClick={toggleRunning}
          >
            {data.running ? "Stop" : "Start"}
          </Button>
        </div>
      </div>

      {/* Account Overview */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card className="border-border bg-card p-4 text-center">
          <p className="text-[10px] text-muted-foreground">US Equity</p>
          <p className="mt-1 text-lg font-bold text-foreground">{fmtUsd(acct.equity ?? 0)}</p>
        </Card>
        <Card className="border-border bg-card p-4 text-center">
          <p className="text-[10px] text-muted-foreground">KR Equity</p>
          <p className="mt-1 text-lg font-bold text-foreground">{fmtKrw(data.kr_equity ?? 0)}</p>
        </Card>
        <Card className="border-border bg-card p-4 text-center">
          <p className="text-[10px] text-muted-foreground">Positions</p>
          <p className="mt-1 text-lg font-bold text-foreground">
            {data.positions} / {data.max_positions}
          </p>
          <p className="text-[10px] text-muted-foreground">
            US {data.positions_us} · KR {data.positions_kr}
          </p>
        </Card>
        <Card className="border-border bg-card p-4 text-center">
          <p className="text-[10px] text-muted-foreground">Trades Today</p>
          <p className="mt-1 text-lg font-bold text-foreground">
            {data.trades_today} / {data.max_daily_trades}
          </p>
        </Card>
      </div>

      {/* Active Positions */}
      <div>
        <p className="mb-3 font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground">
          Active Positions ({data.active_positions.length})
        </p>
        {data.active_positions.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No active positions</p>
        ) : (
          <div className="space-y-2">
            {data.active_positions.map((p) => (
              <Card key={p.ticker} className="flex items-center justify-between border-border bg-card px-4 py-3 text-xs">
                <div>
                  <span className="text-sm font-medium text-foreground">{p.ticker}</span>
                  <span className="ml-2 text-muted-foreground">{p.qty} shares · {p.side}</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-foreground">{fmtUsd(p.market_value)}</span>
                  <span className={p.unrealized_pl >= 0 ? "text-success" : "text-destructive"}>
                    {p.unrealized_pl >= 0 ? "+" : ""}${p.unrealized_pl.toFixed(2)}
                    ({(p.unrealized_plpc * 100).toFixed(2)}%)
                  </span>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Logs */}
      {data.logs.length > 0 && (
        <div>
          <p className="mb-3 font-mono text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground">
            Recent Logs
          </p>
          <Card className="max-h-60 overflow-y-auto border-border bg-card p-3">
            {data.logs.slice(-20).reverse().map((log, i) => (
              <p key={i} className="py-0.5 font-mono text-[11px] text-muted-foreground">
                <span className="text-foreground/50">{log.time}</span> {log.msg}
              </p>
            ))}
          </Card>
        </div>
      )}
    </div>
  );
}
