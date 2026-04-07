"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { usePortfolio } from "@/lib/hooks";
import { apiFetch } from "@/lib/api";
import { fmtUsd, fmtPct, pnlColor, signalColor, scoreColor } from "@/lib/format";

const fetcher = (url: string) => fetch(url, { credentials: "include" }).then((r) => r.json());

export default function DetailPage() {
  const params = useParams();
  const router = useRouter();
  const ticker = decodeURIComponent(params.ticker as string);
  const { data: portfolio, mutate: refreshPortfolio } = usePortfolio();
  const { data: analysis, mutate: refreshAnalysis } = useSWR(`/api/signals/${ticker}`, fetcher);

  const position = portfolio?.positions.find((p) => p.ticker === ticker);

  const [buyShares, setBuyShares] = useState("1");
  const [sellShares, setSellShares] = useState("");
  const [loading, setLoading] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (position) setSellShares(String(position.shares));
  }, [position]);

  const price = analysis?.price ?? position?.current_price ?? 0;
  const priceDisplay = analysis?.price_display ?? `$${price}`;

  const handleBuy = async () => {
    if (!position) return;
    setLoading("buy");
    setMsg("");
    try {
      await apiFetch(`/api/portfolio/position/${position.id}/buy`, {
        method: "POST",
        body: JSON.stringify({ shares: Number(buyShares), price }),
      });
      setMsg("✓ Purchase complete!");
      refreshPortfolio();
      refreshAnalysis();
    } catch (e: unknown) {
      setMsg((e as Error).message);
    } finally {
      setLoading("");
    }
  };

  const handleSell = async () => {
    if (!position) return;
    setLoading("sell");
    setMsg("");
    try {
      await apiFetch(`/api/portfolio/position/${position.id}/sell`, {
        method: "POST",
        body: JSON.stringify({ shares: Number(sellShares), price }),
      });
      setMsg("✓ Sold!");
      refreshPortfolio();
      if (Number(sellShares) >= position.shares) {
        router.push("/");
      } else {
        refreshAnalysis();
      }
    } catch (e: unknown) {
      setMsg((e as Error).message);
    } finally {
      setLoading("");
    }
  };

  const handleDelete = async () => {
    if (!position || !confirm(`Delete ${ticker} from portfolio?`)) return;
    await apiFetch(`/api/portfolio/position/${position.id}`, { method: "DELETE" });
    refreshPortfolio();
    router.push("/");
  };

  if (!analysis) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Back button */}
      <button onClick={() => router.back()} className="text-sm text-muted-foreground hover:text-foreground">
        ← Back
      </button>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            {analysis.name ?? ticker}
          </h1>
          <p className="text-sm text-muted-foreground">
            {ticker} · {analysis.sector ?? ""} · {analysis.is_korean ? "🇰🇷 KRX" : "🇺🇸 US"}
          </p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-foreground">{priceDisplay}</p>
          <p className={`text-sm font-medium ${pnlColor(analysis.change_pct ?? 0)}`}>
            {(analysis.change_pct ?? 0) >= 0 ? "+" : ""}{(analysis.change_pct ?? 0).toFixed(2)}%
          </p>
        </div>
      </div>

      {/* Signal + Score */}
      <div className="flex items-center gap-4">
        <Badge className={`text-sm font-bold ${signalColor(analysis.signal)}`}>
          {analysis.signal}
        </Badge>
        <div className="flex-1">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Quant Score</span>
            <span className="font-mono font-bold">{analysis.score?.toFixed(1)}/100</span>
          </div>
          <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={`h-full rounded-full ${scoreColor(analysis.score ?? 0)}`}
              style={{ width: `${analysis.score ?? 0}%` }}
            />
          </div>
        </div>
      </div>

      {/* Score Breakdown */}
      <Card className="border-border bg-card p-5">
        <p className="mb-3 font-mono text-[10px] font-medium uppercase tracking-[1px] text-muted-foreground">
          Score Breakdown
        </p>
        <div className="grid grid-cols-4 gap-4 text-center">
          {[
            { label: "Technical", score: analysis.tech_score },
            { label: "Fundamental", score: analysis.fund_score },
            { label: "News (AI)", score: analysis.news_score },
            { label: "Quant", score: analysis.quant_score },
          ].map((s) => (
            <div key={s.label}>
              <p className="text-[10px] text-muted-foreground">{s.label}</p>
              <p className="mt-1 text-xl font-bold text-foreground">{(s.score ?? 0).toFixed(0)}</p>
              <div className="mx-auto mt-1 h-1 w-12 overflow-hidden rounded-full bg-muted">
                <div className={`h-full rounded-full ${scoreColor(s.score ?? 0)}`} style={{ width: `${s.score ?? 0}%` }} />
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Signals List */}
      <Card className="border-border bg-card p-5">
        <p className="mb-3 font-mono text-[10px] font-medium uppercase tracking-[1px] text-muted-foreground">
          Signals ({(analysis.signals as unknown[])?.length ?? 0})
        </p>
        <div className="space-y-1.5">
          {(analysis.signals as Array<{type: string; msg: string}>)?.map((s, i) => (
            <p key={i} className={`text-xs ${s.type === "bullish" ? "text-success" : s.type === "bearish" ? "text-destructive" : "text-muted-foreground"}`}>
              {s.type === "bullish" ? "▲" : s.type === "bearish" ? "▼" : "●"} {s.msg}
            </p>
          ))}
        </div>
      </Card>

      {/* TP/SL */}
      {(analysis.take_profit || analysis.stop_loss) && (
        <div className="grid grid-cols-2 gap-4">
          <Card className="border-success/20 bg-success/5 p-4 text-center">
            <p className="text-[10px] text-success/60">Take Profit</p>
            <p className="text-lg font-bold text-success">
              {analysis.is_korean ? `₩${analysis.take_profit?.toLocaleString()}` : fmtUsd(analysis.take_profit ?? 0)}
            </p>
            <p className="text-xs text-success/60">{fmtPct(analysis.tp_pct ?? 0)}</p>
          </Card>
          <Card className="border-destructive/20 bg-destructive/5 p-4 text-center">
            <p className="text-[10px] text-destructive/60">Stop Loss</p>
            <p className="text-lg font-bold text-destructive">
              {analysis.is_korean ? `₩${analysis.stop_loss?.toLocaleString()}` : fmtUsd(analysis.stop_loss ?? 0)}
            </p>
            <p className="text-xs text-destructive/60">{fmtPct(analysis.sl_pct ?? 0)}</p>
          </Card>
        </div>
      )}

      {/* Position Info (if owned) */}
      {position && (
        <Card className="border-border bg-card p-5">
          <p className="mb-3 font-mono text-[10px] font-medium uppercase tracking-[1px] text-muted-foreground">
            Your Position
          </p>
          <div className="grid grid-cols-3 gap-4 text-center text-sm">
            <div>
              <p className="text-[10px] text-muted-foreground">Shares</p>
              <p className="font-bold text-foreground">{position.shares}</p>
            </div>
            <div>
              <p className="text-[10px] text-muted-foreground">Avg Cost</p>
              <p className="font-bold text-foreground">{fmtUsd(position.avg_cost)}</p>
            </div>
            <div>
              <p className="text-[10px] text-muted-foreground">P&L</p>
              <p className={`font-bold ${pnlColor(position.pnl_pct)}`}>{fmtPct(position.pnl_pct)}</p>
            </div>
          </div>
        </Card>
      )}

      {/* Action Buttons */}
      {position && (
        <div className="grid grid-cols-2 gap-4">
          {/* Buy */}
          <Card className="border-success/20 bg-card p-4">
            <p className="mb-2 text-sm font-semibold text-success">Buy More</p>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                value={buyShares}
                onChange={(e) => setBuyShares(e.target.value)}
                className="h-9 w-24 bg-background text-sm"
                min={1}
              />
              <span className="text-xs text-muted-foreground">shares</span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Total: {fmtUsd(Number(buyShares) * price)}
            </p>
            <Button
              className="mt-3 w-full bg-success text-white hover:bg-success/80"
              onClick={handleBuy}
              disabled={loading === "buy"}
            >
              {loading === "buy" ? "Processing..." : `Buy ${buyShares} shares`}
            </Button>
          </Card>

          {/* Sell */}
          <Card className="border-destructive/20 bg-card p-4">
            <p className="mb-2 text-sm font-semibold text-destructive">Sell</p>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                value={sellShares}
                onChange={(e) => setSellShares(e.target.value)}
                className="h-9 w-24 bg-background text-sm"
                min={1}
                max={position.shares}
              />
              <Button variant="outline" size="sm" className="h-9 text-xs" onClick={() => setSellShares(String(position.shares))}>
                All
              </Button>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Proceeds: {fmtUsd(Number(sellShares) * price)}
            </p>
            <Button
              variant="destructive"
              className="mt-3 w-full"
              onClick={handleSell}
              disabled={loading === "sell"}
            >
              {loading === "sell" ? "Processing..." : `Sell ${sellShares} shares`}
            </Button>
          </Card>
        </div>
      )}

      {/* Delete */}
      {position && (
        <button
          onClick={handleDelete}
          className="w-full text-center text-xs text-destructive/40 hover:text-destructive"
        >
          Remove from portfolio
        </button>
      )}

      {/* Status */}
      {msg && (
        <p className={`text-center text-sm font-medium ${msg.startsWith("✓") ? "text-success" : "text-destructive"}`}>
          {msg}
        </p>
      )}
    </div>
  );
}
