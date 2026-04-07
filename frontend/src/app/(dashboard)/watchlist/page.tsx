"use client";

import { useState } from "react";
import useSWR from "swr";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { pnlColor, signalColor } from "@/lib/format";
import { apiFetch } from "@/lib/api";

interface WatchlistItem {
  id: number;
  ticker: string;
  name: string;
  price: number;
  price_display: string;
  change_pct: number;
  signal: string;
  score: number;
  currency: string;
  is_korean: boolean;
}

const fetcher = (url: string) => fetch(url, { credentials: "include" }).then((r) => r.json());

export default function WatchlistPage() {
  const { data, mutate } = useSWR<{ watchlist: WatchlistItem[] }>("/api/watchlist", fetcher);
  const [ticker, setTicker] = useState("");
  const [adding, setAdding] = useState(false);

  const handleAdd = async () => {
    if (!ticker.trim()) return;
    setAdding(true);
    try {
      await apiFetch("/api/watchlist", {
        method: "POST",
        body: JSON.stringify({ ticker: ticker.trim().toUpperCase() }),
      });
      setTicker("");
      mutate();
    } catch { /* ignore */ }
    finally { setAdding(false); }
  };

  const handleRemove = async (id: number) => {
    await apiFetch(`/api/watchlist/${id}`, { method: "DELETE" });
    mutate();
  };

  if (!data) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <h1 className="text-lg font-semibold text-foreground">Watchlist</h1>

      <div className="flex gap-2">
        <Input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          placeholder="Add ticker (e.g. AAPL)"
          className="max-w-xs bg-muted"
        />
        <Button onClick={handleAdd} disabled={adding} size="sm">
          {adding ? "..." : "+ Add"}
        </Button>
      </div>

      {data.watchlist.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">
          Watchlist is empty. Add tickers above.
        </p>
      ) : (
        <div className="space-y-2">
          {data.watchlist.map((w) => (
            <Card key={w.id} className="flex items-center justify-between border-border bg-card px-4 py-3">
              <div className="flex items-center gap-3">
                <Badge variant="outline" className={`text-[10px] font-semibold ${signalColor(w.signal)}`}>
                  {w.signal}
                </Badge>
                <div>
                  <span className="text-sm font-medium text-foreground">
                    {w.is_korean ? "🇰🇷" : "🇺🇸"} {w.ticker}
                  </span>
                  <span className="ml-2 text-xs text-muted-foreground">{w.name}</span>
                </div>
              </div>
              <div className="flex items-center gap-4 text-xs">
                <span className="font-medium text-foreground">{w.price_display}</span>
                <span className={pnlColor(w.change_pct)}>
                  {(w.change_pct ?? 0) >= 0 ? "+" : ""}{(w.change_pct ?? 0).toFixed(2)}%
                </span>
                <span className="font-mono text-muted-foreground">{(w.score ?? 0).toFixed(0)}</span>
                <button
                  onClick={() => handleRemove(w.id)}
                  className="text-destructive/60 hover:text-destructive"
                >
                  ✕
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
