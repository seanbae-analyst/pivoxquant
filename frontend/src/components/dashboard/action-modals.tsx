"use client";

import { useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";

/* ── Add New Position ── */
export function AddPositionModal({ onDone }: { onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [ticker, setTicker] = useState("");
  const [shares, setShares] = useState("1");
  const [cost, setCost] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleAdd = async () => {
    if (!ticker.trim()) return;
    setLoading(true);
    setError("");
    try {
      await apiFetch("/api/portfolio/position", {
        method: "POST",
        body: JSON.stringify({
          ticker: ticker.trim().toUpperCase(),
          shares: Number(shares),
          avg_cost: Number(cost) || 0,
        }),
      });
      setOpen(false);
      setTicker(""); setShares("1"); setCost("");
      onDone();
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button size="sm" className="text-xs" onClick={() => setOpen(true)}>+ Add Position</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="border-border bg-card sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add Position</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-xs text-muted-foreground">Ticker</Label>
              <Input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="e.g. AAPL, 005930.KS" className="mt-1 bg-muted" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs text-muted-foreground">Shares</Label>
                <Input type="number" value={shares} onChange={(e) => setShares(e.target.value)} className="mt-1 bg-muted" min={0.01} step="any" />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Avg Cost (per share)</Label>
                <Input type="number" value={cost} onChange={(e) => setCost(e.target.value)} className="mt-1 bg-muted" min={0} step="any" placeholder="0 = auto" />
              </div>
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
            <Button onClick={handleAdd} disabled={loading} className="w-full">
              {loading ? "Adding..." : "Add to Portfolio"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

/* ── Edit Capital ── */
export function EditCapitalModal({
  currentUsd, currentKrw, onDone,
}: {
  currentUsd: number; currentKrw: number; onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [usd, setUsd] = useState(String(currentUsd));
  const [krw, setKrw] = useState(String(currentKrw));
  const [loading, setLoading] = useState(false);

  const handleSave = async () => {
    setLoading(true);
    try {
      await apiFetch("/api/portfolio/capital", {
        method: "PUT",
        body: JSON.stringify({ capital_usd: Number(usd), capital_krw: Number(krw) }),
      });
      setOpen(false);
      onDone();
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button className="text-[10px] text-primary/60 hover:text-primary" onClick={() => { setOpen(true); setUsd(String(currentUsd)); setKrw(String(currentKrw)); }}>
        Edit
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="border-border bg-card sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Edit Available Capital</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-xs text-muted-foreground">USD Capital</Label>
              <Input type="number" value={usd} onChange={(e) => setUsd(e.target.value)} className="mt-1 bg-muted" min={0} step="any" />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">KRW Capital (₩)</Label>
              <Input type="number" value={krw} onChange={(e) => setKrw(e.target.value)} className="mt-1 bg-muted" min={0} step="any" />
            </div>
            <Button onClick={handleSave} disabled={loading} className="w-full">
              {loading ? "Saving..." : "Save"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

/* ── Quick Buy Modal ── */
export function QuickBuyModal({
  positionId, ticker, currentPrice, priceDisplay, recShares, onDone,
}: {
  positionId: number; ticker: string; currentPrice: number; priceDisplay: string; recShares?: number; onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [shares, setShares] = useState(String(recShares || 1));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const total = Number(shares) * currentPrice;

  const handleBuy = async () => {
    setLoading(true); setError("");
    try {
      await apiFetch(`/api/portfolio/position/${positionId}/buy`, {
        method: "POST",
        body: JSON.stringify({ shares: Number(shares), price: currentPrice }),
      });
      setOpen(false); onDone();
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button variant="outline" size="sm" className="h-7 text-[10px] text-success hover:bg-success/10" onClick={() => setOpen(true)}>
        + Buy
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="border-border bg-card sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-success">Buy {ticker}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Current Price: {priceDisplay}</p>
            <div>
              <Label className="text-xs text-muted-foreground">Shares</Label>
              <Input type="number" value={shares} onChange={(e) => setShares(e.target.value)} className="mt-1 bg-muted" min={1} />
            </div>
            <p className="text-sm font-medium text-foreground">
              Total: ${total.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </p>
            {error && <p className="text-xs text-destructive">{error}</p>}
            <Button onClick={handleBuy} disabled={loading} className="w-full bg-success text-white hover:bg-success/80">
              {loading ? "Processing..." : `Confirm Buy ${shares} shares`}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

/* ── Quick Sell Modal ── */
export function QuickSellModal({
  positionId, ticker, currentPrice, priceDisplay, maxShares, onDone,
}: {
  positionId: number; ticker: string; currentPrice: number; priceDisplay: string; maxShares: number; onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [shares, setShares] = useState(String(maxShares));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const proceeds = Number(shares) * currentPrice;

  const handleSell = async () => {
    setLoading(true); setError("");
    try {
      await apiFetch(`/api/portfolio/position/${positionId}/sell`, {
        method: "POST",
        body: JSON.stringify({ shares: Number(shares), price: currentPrice }),
      });
      setOpen(false); onDone();
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button variant="outline" size="sm" className="h-7 text-[10px] text-destructive hover:bg-destructive/10" onClick={() => { setOpen(true); setShares(String(maxShares)); }}>
        Sell
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="border-border bg-card sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-destructive">Sell {ticker}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Current Price: {priceDisplay}</p>
            <div className="flex items-center gap-2">
              <div className="flex-1">
                <Label className="text-xs text-muted-foreground">Shares</Label>
                <Input type="number" value={shares} onChange={(e) => setShares(e.target.value)} className="mt-1 bg-muted" min={1} max={maxShares} />
              </div>
              <Button variant="outline" size="sm" className="mt-5" onClick={() => setShares(String(maxShares))}>
                All ({maxShares})
              </Button>
            </div>
            <p className="text-sm font-medium text-foreground">
              Proceeds: ${proceeds.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </p>
            {error && <p className="text-xs text-destructive">{error}</p>}
            <Button onClick={handleSell} disabled={loading} variant="destructive" className="w-full">
              {loading ? "Processing..." : `Confirm Sell ${shares} shares`}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
