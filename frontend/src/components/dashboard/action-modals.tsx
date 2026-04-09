"use client";

import { useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";

function safeError(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

/* ── Add New Position ── */
export function AddPositionModal({ onDone }: { onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [ticker, setTicker] = useState("");
  const [shares, setShares] = useState("1");
  const [cost, setCost] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleAdd = async () => {
    if (!ticker.trim()) { setError("Please enter a ticker"); return; }
    if (Number(shares) <= 0) { setError("Shares must be greater than 0"); return; }
    setLoading(true);
    setError("");
    try {
      await apiFetch(API.portfolio.addPosition, {
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
      setError(safeError(e));
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
  const [error, setError] = useState("");

  const handleSave = async () => {
    setLoading(true);
    setError("");
    try {
      await apiFetch(API.portfolio.capital, {
        method: "PUT",
        body: JSON.stringify({ capital_usd: Number(usd), capital_krw: Number(krw) }),
      });
      setOpen(false);
      onDone();
    } catch (e: unknown) {
      setError(safeError(e));
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
            {error && <p className="text-xs text-destructive">{error}</p>}
            <Button onClick={handleSave} disabled={loading} className="w-full">
              {loading ? "Saving..." : "Save"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

function fmtCurrency(value: number, currency: string = "USD"): string {
  if (currency === "KRW") return `₩${Math.round(value).toLocaleString()}`;
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

/* ── Quick Buy Modal ── */
export function QuickBuyModal({
  positionId, ticker, currentPrice, priceDisplay, recShares, currency = "USD", onDone,
}: {
  positionId: number; ticker: string; currentPrice: number; priceDisplay: string; recShares?: number; currency?: string; onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [shares, setShares] = useState(String(recShares || 1));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const numShares = Number(shares) || 0;
  const total = numShares * currentPrice;

  const handleBuy = async () => {
    if (numShares <= 0) { setError("Shares must be greater than 0"); return; }
    setLoading(true); setError("");
    try {
      await apiFetch(API.portfolio.buyMore(positionId), {
        method: "POST",
        body: JSON.stringify({ shares: numShares, price: currentPrice }),
      });
      setOpen(false); onDone();
    } catch (e: unknown) {
      setError(safeError(e));
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
              Total: {fmtCurrency(total, currency)}
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
  positionId, ticker, currentPrice, priceDisplay, maxShares, currency = "USD", onDone,
}: {
  positionId: number; ticker: string; currentPrice: number; priceDisplay: string; maxShares: number; currency?: string; onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [shares, setShares] = useState(String(maxShares));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const numShares = Number(shares) || 0;
  const proceeds = numShares * currentPrice;

  const handleSell = async () => {
    if (numShares <= 0) { setError("Shares must be greater than 0"); return; }
    if (numShares > maxShares) { setError(`Maximum ${maxShares} shares available to sell`); return; }
    setLoading(true); setError("");
    try {
      await apiFetch(API.portfolio.sellShares(positionId), {
        method: "POST",
        body: JSON.stringify({ shares: numShares, price: currentPrice }),
      });
      setOpen(false); onDone();
    } catch (e: unknown) {
      setError(safeError(e));
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
              Proceeds: {fmtCurrency(proceeds, currency)}
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

/* ── Edit Position Modal ── */
export function EditPositionModal({
  positionId, ticker, currentShares, currentAvgCost, onDone,
}: {
  positionId: number; ticker: string; currentShares: number; currentAvgCost: number; onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [shares, setShares] = useState(String(currentShares));
  const [avgCost, setAvgCost] = useState(String(currentAvgCost));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    const numShares = Number(shares);
    const numCost = Number(avgCost);
    if (numShares <= 0) { setError("Shares must be greater than 0"); return; }
    if (numCost < 0) { setError("Average cost must be 0 or greater"); return; }
    setLoading(true); setError("");
    try {
      await apiFetch(API.portfolio.editPosition(positionId), {
        method: "PUT",
        body: JSON.stringify({ shares: numShares, avg_cost: numCost }),
      });
      setOpen(false); onDone();
    } catch (e: unknown) {
      setError(safeError(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button variant="ghost" size="sm" className="h-7 text-[10px] text-muted-foreground hover:text-foreground" onClick={() => { setOpen(true); setShares(String(currentShares)); setAvgCost(String(currentAvgCost)); setError(""); }}>
        Edit
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="border-border bg-card sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Edit {ticker}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-xs text-muted-foreground">Shares</Label>
              <Input type="number" value={shares} onChange={(e) => setShares(e.target.value)} className="mt-1 bg-muted" min={0.01} step="any" />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Avg Cost</Label>
              <Input type="number" value={avgCost} onChange={(e) => setAvgCost(e.target.value)} className="mt-1 bg-muted" min={0} step="any" />
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
            <Button onClick={handleSave} disabled={loading} className="w-full">
              {loading ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
