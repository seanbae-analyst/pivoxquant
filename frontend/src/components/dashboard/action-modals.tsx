"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";

/* ── Helpers ── */

function safeError(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

function fmtCurrency(value: number, currency: string = "USD"): string {
  if (currency === "KRW") return `\u20A9${Math.round(value).toLocaleString()}`;
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPrice(value: number): string {
  return value.toFixed(2);
}

/* ── Ticker Lookup Hook ── */

interface LookupResult {
  name: string;
  price: number;
  price_display: string;
  currency: string;
  is_korean: boolean;
  sector: string;
}

function useTickerLookup() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<LookupResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const lookup = useCallback((ticker: string) => {
    const t = ticker.trim().toUpperCase();
    setQuery(t);
    setResult(null);
    setError("");

    if (!t || t.length < 1) return;

    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await apiFetch<LookupResult>(API.market.lookup(t));
        setResult(data);
        setError("");
      } catch (e: unknown) {
        setResult(null);
        setError(safeError(e));
      } finally {
        setLoading(false);
      }
    }, 400);
  }, []);

  const reset = useCallback(() => {
    setQuery("");
    setResult(null);
    setLoading(false);
    setError("");
    if (debounceRef.current) clearTimeout(debounceRef.current);
  }, []);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  return { query, result, loading, error, lookup, reset };
}

/* ═══════════════════════════════════════════════════════════════
   1. Add Position Modal
   ═══════════════════════════════════════════════════════════════ */

export function AddPositionModal({ onDone }: { onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [ticker, setTicker] = useState("");
  const [shares, setShares] = useState("1");
  const [cost, setCost] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const tickerLookup = useTickerLookup();
  const submittingRef = useRef(false);

  const handleTickerChange = (value: string) => {
    setTicker(value);
    tickerLookup.lookup(value);
  };

  // Auto-fill cost from lookup price
  useEffect(() => {
    if (tickerLookup.result && !cost) {
      setCost(fmtPrice(tickerLookup.result.price));
    }
  }, [tickerLookup.result, cost]);

  const numShares = Number(shares) || 0;
  const numCost = Number(cost) || 0;
  const totalCost = numShares * numCost;
  const currency = tickerLookup.result?.currency ?? "USD";

  const handleAdd = async () => {
    if (submittingRef.current) return;
    const t = ticker.trim().toUpperCase();
    if (!t) { setError("Please enter a ticker symbol"); return; }
    if (numShares <= 0) { setError("Shares must be greater than 0"); return; }
    if (currency === "KRW" && numShares !== Math.floor(numShares)) { setError("Korean stocks must be traded in whole shares"); return; }
    if (numCost <= 0) { setError("Average cost must be greater than 0"); return; }
    submittingRef.current = true;
    setLoading(true);
    setError("");
    try {
      await apiFetch(API.portfolio.addPosition, {
        method: "POST",
        body: JSON.stringify({
          ticker: t,
          shares: currency === "KRW" ? Math.floor(numShares) : numShares,
          avg_cost: numCost,
        }),
      });
      toast.success(`${t} 포지션 추가 완료`);
      setOpen(false);
      resetForm();
      onDone();
    } catch (e: unknown) {
      const msg = safeError(e);
      setError(msg);
      toast.error(msg);
    } finally {
      submittingRef.current = false;
      setLoading(false);
    }
  };

  const resetForm = () => {
    setTicker("");
    setShares("1");
    setCost("");
    setError("");
    tickerLookup.reset();
  };

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) resetForm();
  };

  return (
    <>
      <Button size="sm" className="text-xs gap-1.5" onClick={() => setOpen(true)}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M12 5v14M5 12h14" />
        </svg>
        Add Position
      </Button>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add New Position</DialogTitle>
            <DialogDescription>Add a stock to your portfolio by entering the ticker symbol.</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Ticker input with lookup */}
            <div>
              <Label className="text-xs text-muted-foreground">Ticker Symbol</Label>
              <Input
                value={ticker}
                onChange={(e) => handleTickerChange(e.target.value)}
                placeholder="e.g. AAPL, TSLA, 005930.KS"
                className="mt-1"
                autoFocus
              />
              {/* Lookup status */}
              {tickerLookup.loading && (
                <p className="mt-1.5 text-[11px] text-muted-foreground flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Looking up {tickerLookup.query}...
                </p>
              )}
              {tickerLookup.result && (
                <div className="mt-2 rounded-lg border border-emerald-200 bg-emerald-50/50 px-3 py-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{tickerLookup.result.name}</p>
                      <p className="text-[10px] text-slate-500">{tickerLookup.result.sector} {tickerLookup.result.is_korean ? "-- KRX" : "-- US"}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-mono font-bold text-slate-900">{tickerLookup.result.price_display}</p>
                      <p className="text-[10px] text-slate-500">{tickerLookup.result.currency}</p>
                    </div>
                  </div>
                </div>
              )}
              {tickerLookup.error && ticker.trim().length >= 1 && !tickerLookup.loading && (
                <p className="mt-1.5 text-[11px] text-amber-600">
                  Ticker not found -- you can still add it manually.
                </p>
              )}
            </div>

            {/* Shares + Cost */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs text-muted-foreground">Shares</Label>
                <Input
                  type="number"
                  value={shares}
                  onChange={(e) => setShares(e.target.value)}
                  className="mt-1"
                  min={currency === "KRW" ? 1 : 0.01}
                  step={currency === "KRW" ? 1 : "any"}
                />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Avg Cost (per share)</Label>
                <Input
                  type="number"
                  value={cost}
                  onChange={(e) => setCost(e.target.value)}
                  className="mt-1"
                  min={0}
                  step="any"
                  placeholder={tickerLookup.result ? fmtPrice(tickerLookup.result.price) : "0.00"}
                />
              </div>
            </div>

            {/* Total preview */}
            {numShares > 0 && numCost > 0 && (
              <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-500">Total Cost Basis</span>
                  <span className="font-mono font-bold text-slate-900">{fmtCurrency(totalCost, currency)}</span>
                </div>
              </div>
            )}

            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>

          <DialogFooter>
            <Button onClick={handleAdd} disabled={loading} className="w-full">
              {loading ? "Adding..." : "Add to Portfolio"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/* ═══════════════════════════════════════════════════════════════
   2. Edit Capital Modal
   ═══════════════════════════════════════════════════════════════ */

function parseCapitalInput(raw: string): number {
  // Strip commas and whitespace so users can paste formatted numbers
  const cleaned = raw.replace(/[,\s]/g, "");
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : NaN;
}

function capitalInputError(value: string, label: string): string | null {
  if (value.trim() === "") return null; // empty = 0, valid
  const n = parseCapitalInput(value);
  if (Number.isNaN(n)) return `${label}: enter a valid number`;
  if (n < 0) return `${label}: cannot be negative`;
  return null;
}

export function EditCapitalModal({
  currentUsd, currentKrw, onDone,
}: {
  currentUsd: number; currentKrw: number; onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [usd, setUsd] = useState("");
  const [krw, setKrw] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const numUsd = usd.trim() === "" ? currentUsd : parseCapitalInput(usd);
  const numKrw = krw.trim() === "" ? currentKrw : parseCapitalInput(krw);
  const usdChanged = numUsd !== currentUsd;
  const krwChanged = numKrw !== currentKrw;
  const hasChanges = usdChanged || krwChanged;

  const validationUsd = capitalInputError(usd, "USD");
  const validationKrw = capitalInputError(krw, "KRW");
  const hasValidationError = validationUsd !== null || validationKrw !== null;

  const handleSave = async () => {
    if (hasValidationError) return;
    if (!hasChanges) { setOpen(false); return; }
    setLoading(true);
    setError("");
    try {
      await apiFetch(API.portfolio.capital, {
        method: "PUT",
        body: JSON.stringify({ capital_usd: numUsd, capital_krw: numKrw }),
      });
      toast.success("자본금 수정 완료");
      setOpen(false);
      onDone();
    } catch (e: unknown) {
      const msg = safeError(e);
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleOpen = () => {
    setOpen(true);
    setUsd(currentUsd > 0 ? String(currentUsd) : "");
    setKrw(currentKrw > 0 ? String(currentKrw) : "");
    setError("");
  };

  return (
    <>
      <button
        className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium text-primary/60 transition-colors hover:bg-primary/5 hover:text-primary"
        onClick={handleOpen}
        aria-label="Edit available capital"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
        </svg>
        Edit
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-[calc(100vw-2rem)] sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Edit Available Capital</DialogTitle>
            <DialogDescription>
              Set your available cash for USD and KRW markets.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {/* USD input */}
            <div>
              <Label className="text-xs text-muted-foreground">USD Capital ($)</Label>
              <div className="relative mt-1">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">$</span>
                <Input
                  type="text"
                  inputMode="decimal"
                  value={usd}
                  onChange={(e) => setUsd(e.target.value)}
                  className="pl-7 font-mono"
                  placeholder={currentUsd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  autoFocus
                />
              </div>
              {validationUsd && (
                <p className="mt-1 text-[11px] text-destructive">{validationUsd}</p>
              )}
              {!validationUsd && usdChanged && (
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Current: ${currentUsd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
              )}
            </div>

            {/* KRW input */}
            <div>
              <Label className="text-xs text-muted-foreground">KRW Capital ({"\u20A9"})</Label>
              <div className="relative mt-1">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">{"\u20A9"}</span>
                <Input
                  type="text"
                  inputMode="numeric"
                  value={krw}
                  onChange={(e) => setKrw(e.target.value)}
                  className="pl-7 font-mono"
                  placeholder={Math.round(currentKrw).toLocaleString()}
                />
              </div>
              {validationKrw && (
                <p className="mt-1 text-[11px] text-destructive">{validationKrw}</p>
              )}
              {!validationKrw && krwChanged && (
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Current: {"\u20A9"}{Math.round(currentKrw).toLocaleString()}
                </p>
              )}
            </div>

            {/* Change preview */}
            {hasChanges && !hasValidationError && (
              <div className="rounded-lg border border-blue-200 bg-blue-50/50 px-3 py-2.5 space-y-1">
                {usdChanged && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-blue-700">USD</span>
                    <span className="font-mono text-blue-900">
                      ${currentUsd.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      {" \u2192 "}
                      ${(Number.isNaN(numUsd) ? 0 : numUsd).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                )}
                {krwChanged && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-blue-700">KRW</span>
                    <span className="font-mono text-blue-900">
                      {"\u20A9"}{Math.round(currentKrw).toLocaleString()}
                      {" \u2192 "}
                      {"\u20A9"}{Math.round(Number.isNaN(numKrw) ? 0 : numKrw).toLocaleString()}
                    </span>
                  </div>
                )}
              </div>
            )}

            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <div className="flex w-full gap-2">
              <Button variant="outline" onClick={() => setOpen(false)} className="flex-1">
                Cancel
              </Button>
              <Button
                onClick={handleSave}
                disabled={loading || hasValidationError || !hasChanges}
                className="flex-1"
              >
                {loading ? "Saving..." : "Save"}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/* ═══════════════════════════════════════════════════════════════
   3. Quick Buy Modal
   ═══════════════════════════════════════════════════════════════ */

export function QuickBuyModal({
  positionId, ticker, currentPrice, priceDisplay, recShares, currency = "USD", onDone,
}: {
  positionId: number;
  ticker: string;
  currentPrice: number;
  priceDisplay: string;
  recShares?: number;
  currency?: string;
  onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [shares, setShares] = useState(String(recShares || 1));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const submittingRef = useRef(false);
  const numShares = Number(shares) || 0;
  const total = numShares * currentPrice;

  const handleBuy = async () => {
    if (submittingRef.current) return;
    if (numShares <= 0) { setError("Shares must be greater than 0"); return; }
    if (currency === "KRW" && numShares !== Math.floor(numShares)) { setError("Korean stocks must be traded in whole shares"); return; }
    const finalShares = currency === "KRW" ? Math.floor(numShares) : numShares;
    submittingRef.current = true;
    setLoading(true);
    setError("");
    try {
      await apiFetch(API.portfolio.buyMore(positionId), {
        method: "POST",
        body: JSON.stringify({ shares: finalShares, price: currentPrice }),
      });
      toast.success(`${ticker} ${finalShares}주 매수 완료`, { description: `Total: ${fmtCurrency(total, currency)}` });
      setOpen(false);
      onDone();
    } catch (e: unknown) {
      const msg = safeError(e);
      setError(msg);
      toast.error(msg);
    } finally {
      submittingRef.current = false;
      setLoading(false);
    }
  };

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        className="h-7 text-[10px] text-emerald-600 border-emerald-200 hover:bg-emerald-50 hover:border-emerald-300"
        onClick={() => { setOpen(true); setShares(String(recShares || 1)); setError(""); }}
      >
        + Buy
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-emerald-600">Buy More {ticker}</DialogTitle>
            <DialogDescription>Add shares to your existing position.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {/* Current price */}
            <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2.5">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">Current Price</span>
                <span className="font-mono font-bold text-slate-900">{priceDisplay}</span>
              </div>
            </div>

            {/* Shares input */}
            <div>
              <Label className="text-xs text-muted-foreground">Shares to Buy</Label>
              <Input
                type="number"
                value={shares}
                onChange={(e) => setShares(e.target.value)}
                className="mt-1"
                min={1}
                step={currency === "KRW" ? 1 : "any"}
                autoFocus
              />
              {recShares && recShares > 0 && (
                <button
                  type="button"
                  className="mt-1.5 text-[10px] text-emerald-600 hover:text-emerald-700 font-medium"
                  onClick={() => setShares(String(recShares))}
                >
                  Recommended: {recShares} shares
                </button>
              )}
            </div>

            {/* Total cost */}
            {numShares > 0 && (
              <div className="rounded-lg bg-emerald-50 border border-emerald-200 px-3 py-2.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-emerald-700">Total Cost</span>
                  <span className="font-mono font-bold text-emerald-700">{fmtCurrency(total, currency)}</span>
                </div>
              </div>
            )}

            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button
              onClick={handleBuy}
              disabled={loading}
              className="w-full bg-emerald-600 text-white hover:bg-emerald-700"
            >
              {loading ? "Processing..." : `Confirm Buy ${numShares > 0 ? numShares : ""} share${numShares !== 1 ? "s" : ""}`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/* ═══════════════════════════════════════════════════════════════
   4. Quick Sell Modal
   ═══════════════════════════════════════════════════════════════ */

export function QuickSellModal({
  positionId, ticker, currentPrice, priceDisplay, maxShares, avgCost, currency = "USD", onDone,
}: {
  positionId: number;
  ticker: string;
  currentPrice: number;
  priceDisplay: string;
  maxShares: number;
  avgCost?: number;
  currency?: string;
  onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [shares, setShares] = useState(String(maxShares));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const submittingRef = useRef(false);
  const numShares = Number(shares) || 0;
  const proceeds = numShares * currentPrice;
  const costBasis = avgCost ? numShares * avgCost : 0;
  const estimatedPnl = costBasis > 0 ? proceeds - costBasis : 0;
  const estimatedPnlPct = costBasis > 0 ? (estimatedPnl / costBasis) * 100 : 0;

  const handleSell = async () => {
    if (submittingRef.current) return;
    if (numShares <= 0) { setError("Shares must be greater than 0"); return; }
    if (currency === "KRW" && numShares !== Math.floor(numShares)) { setError("Korean stocks must be traded in whole shares"); return; }
    if (numShares > maxShares) { setError(`Maximum ${maxShares} shares available`); return; }
    const finalShares = currency === "KRW" ? Math.floor(numShares) : numShares;
    submittingRef.current = true;
    setLoading(true);
    setError("");
    try {
      await apiFetch(API.portfolio.sellShares(positionId), {
        method: "POST",
        body: JSON.stringify({ shares: finalShares, price: currentPrice }),
      });
      const pnlText = avgCost && avgCost > 0
        ? `P&L: ${estimatedPnl >= 0 ? "+" : ""}${fmtCurrency(estimatedPnl, currency)}`
        : `Proceeds: ${fmtCurrency(proceeds, currency)}`;
      toast.success(`${ticker} ${finalShares}주 매도 완료`, { description: pnlText });
      setOpen(false);
      onDone();
    } catch (e: unknown) {
      const msg = safeError(e);
      setError(msg);
      toast.error(msg);
    } finally {
      submittingRef.current = false;
      setLoading(false);
    }
  };

  const isFullSell = numShares >= maxShares;

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        className="h-7 text-[10px] text-red-600 border-red-200 hover:bg-red-50 hover:border-red-300"
        onClick={() => { setOpen(true); setShares(String(maxShares)); setError(""); }}
      >
        Sell
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-red-600">Sell {ticker}</DialogTitle>
            <DialogDescription>
              {isFullSell ? "This will close your entire position." : "Sell some or all of your shares."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {/* Current price */}
            <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2.5">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">Current Price</span>
                <span className="font-mono font-bold text-slate-900">{priceDisplay}</span>
              </div>
            </div>

            {/* Shares input */}
            <div>
              <div className="flex items-center justify-between">
                <Label className="text-xs text-muted-foreground">Shares to Sell</Label>
                <button
                  type="button"
                  className="text-[10px] text-red-600 hover:text-red-700 font-medium"
                  onClick={() => setShares(String(maxShares))}
                >
                  Sell All ({maxShares})
                </button>
              </div>
              <Input
                type="number"
                value={shares}
                onChange={(e) => setShares(e.target.value)}
                className="mt-1"
                min={1}
                max={maxShares}
                step={currency === "KRW" ? 1 : "any"}
                autoFocus
              />
            </div>

            {/* Proceeds + P&L preview */}
            {numShares > 0 && (
              <div className="rounded-lg bg-red-50/50 border border-red-200 px-3 py-2.5 space-y-1.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-red-700">Estimated Proceeds</span>
                  <span className="font-mono font-bold text-red-700">{fmtCurrency(proceeds, currency)}</span>
                </div>
                {avgCost !== undefined && avgCost > 0 && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-500">Est. P&L</span>
                    <span className={`font-mono font-semibold ${estimatedPnl >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                      {estimatedPnl >= 0 ? "+" : ""}{fmtCurrency(estimatedPnl, currency)} ({estimatedPnlPct >= 0 ? "+" : ""}{estimatedPnlPct.toFixed(2)}%)
                    </span>
                  </div>
                )}
                {isFullSell && (
                  <p className="text-[10px] text-red-500 font-medium pt-1 border-t border-red-200">
                    Full position close
                  </p>
                )}
              </div>
            )}

            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button
              onClick={handleSell}
              disabled={loading}
              variant="destructive"
              className="w-full"
            >
              {loading ? "Processing..." : `Confirm Sell ${numShares > 0 ? numShares : ""} share${numShares !== 1 ? "s" : ""}`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/* ═══════════════════════════════════════════════════════════════
   5. Edit Position Modal
   ═══════════════════════════════════════════════════════════════ */

export function EditPositionModal({
  positionId, ticker, currentShares, currentAvgCost, currency = "USD", onDone,
}: {
  positionId: number;
  ticker: string;
  currentShares: number;
  currentAvgCost: number;
  currency?: string;
  onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [shares, setShares] = useState(String(currentShares));
  const [avgCost, setAvgCost] = useState(String(currentAvgCost));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const submittingRef = useRef(false);

  const numShares = Number(shares) || 0;
  const numCost = Number(avgCost) || 0;
  const totalBasis = numShares * numCost;

  const handleSave = async () => {
    if (submittingRef.current) return;
    if (numShares <= 0) { setError("Shares must be greater than 0"); return; }
    if (numCost <= 0) { setError("Average cost must be greater than 0"); return; }
    submittingRef.current = true;
    setLoading(true);
    setError("");
    try {
      await apiFetch(API.portfolio.editPosition(positionId), {
        method: "PUT",
        body: JSON.stringify({ shares: numShares, avg_cost: numCost }),
      });
      toast.success("포지션 수정 완료");
      setOpen(false);
      onDone();
    } catch (e: unknown) {
      const msg = safeError(e);
      setError(msg);
      toast.error(msg);
    } finally {
      submittingRef.current = false;
      setLoading(false);
    }
  };

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        className="h-7 text-[10px] text-muted-foreground hover:text-foreground"
        onClick={() => {
          setOpen(true);
          setShares(String(currentShares));
          setAvgCost(String(currentAvgCost));
          setError("");
        }}
      >
        Edit
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Edit {ticker}</DialogTitle>
            <DialogDescription>Manually adjust shares and average cost for this position.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="text-xs text-muted-foreground">Shares</Label>
              <Input
                type="number"
                value={shares}
                onChange={(e) => setShares(e.target.value)}
                className="mt-1"
                min={0.01}
                step="any"
                autoFocus
              />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Average Cost (per share)</Label>
              <Input
                type="number"
                value={avgCost}
                onChange={(e) => setAvgCost(e.target.value)}
                className="mt-1"
                min={0}
                step="any"
              />
            </div>

            {/* Total basis preview */}
            {numShares > 0 && numCost > 0 && (
              <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-500">Total Cost Basis</span>
                  <span className="font-mono font-bold text-slate-900">{fmtCurrency(totalBasis, currency)}</span>
                </div>
              </div>
            )}

            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button onClick={handleSave} disabled={loading} className="w-full">
              {loading ? "Saving..." : "Save Changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/* ═══════════════════════════════════════════════════════════════
   6. Buy New (Scanner) Modal
   ═══════════════════════════════════════════════════════════════ */

export function BuyNewModal({
  ticker, name, currentPrice, priceDisplay, recShares, currency = "USD", onDone,
}: {
  ticker: string;
  name: string;
  currentPrice: number;
  priceDisplay: string;
  recShares?: number;
  currency?: string;
  onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [shares, setShares] = useState(String(recShares || 1));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const submittingRef = useRef(false);
  const numShares = Number(shares) || 0;
  const total = numShares * currentPrice;

  const handleBuy = async () => {
    if (submittingRef.current) return;
    if (numShares <= 0) { setError("Shares must be greater than 0"); return; }
    if (currency === "KRW" && numShares !== Math.floor(numShares)) { setError("Korean stocks must be traded in whole shares"); return; }
    const finalShares = currency === "KRW" ? Math.floor(numShares) : numShares;
    submittingRef.current = true;
    setLoading(true);
    setError("");
    try {
      await apiFetch(API.portfolio.buyNew, {
        method: "POST",
        body: JSON.stringify({ ticker, shares: finalShares, price: currentPrice }),
      });
      toast.success(`${ticker} ${finalShares}주 매수 완료 (신규)`, { description: `Total: ${fmtCurrency(total, currency)}` });
      setOpen(false);
      onDone();
    } catch (e: unknown) {
      const msg = safeError(e);
      setError(msg);
      toast.error(msg);
    } finally {
      submittingRef.current = false;
      setLoading(false);
    }
  };

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        className="h-7 text-[10px] text-emerald-600 border-emerald-200 hover:bg-emerald-50 hover:border-emerald-300"
        onClick={() => { setOpen(true); setShares(String(recShares || 1)); setError(""); }}
      >
        Buy
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-emerald-600">Buy {ticker}</DialogTitle>
            <DialogDescription>Open a new position for {name || ticker}.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {/* Current price */}
            <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2.5">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">Current Price</span>
                <span className="font-mono font-bold text-slate-900">{priceDisplay}</span>
              </div>
            </div>

            {/* Shares input */}
            <div>
              <Label className="text-xs text-muted-foreground">Shares to Buy</Label>
              <Input
                type="number"
                value={shares}
                onChange={(e) => setShares(e.target.value)}
                className="mt-1"
                min={1}
                step={currency === "KRW" ? 1 : "any"}
                autoFocus
              />
              {recShares && recShares > 0 && (
                <button
                  type="button"
                  className="mt-1.5 text-[10px] text-emerald-600 hover:text-emerald-700 font-medium"
                  onClick={() => setShares(String(recShares))}
                >
                  Recommended: {recShares} shares
                </button>
              )}
            </div>

            {/* Total cost */}
            {numShares > 0 && (
              <div className="rounded-lg bg-emerald-50 border border-emerald-200 px-3 py-2.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-emerald-700">Total Cost</span>
                  <span className="font-mono font-bold text-emerald-700">{fmtCurrency(total, currency)}</span>
                </div>
              </div>
            )}

            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button
              onClick={handleBuy}
              disabled={loading}
              className="w-full bg-emerald-600 text-white hover:bg-emerald-700"
            >
              {loading ? "Processing..." : `Confirm Buy ${numShares > 0 ? numShares : ""} share${numShares !== 1 ? "s" : ""}`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/* ═══════════════════════════════════════════════════════════════
   7. Delete Position Modal
   ═══════════════════════════════════════════════════════════════ */

export function DeletePositionModal({
  positionId, ticker, name, shares, onDone,
}: {
  positionId: number;
  ticker: string;
  name: string;
  shares: number;
  onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const submittingRef = useRef(false);

  const handleDelete = async () => {
    if (submittingRef.current) return;
    submittingRef.current = true;
    setLoading(true);
    setError("");
    try {
      await apiFetch(API.portfolio.deletePosition(positionId), { method: "DELETE" });
      toast.success("포지션 삭제 완료");
      setOpen(false);
      onDone();
    } catch (e: unknown) {
      const msg = safeError(e);
      setError(msg);
      toast.error(msg);
    } finally {
      submittingRef.current = false;
      setLoading(false);
    }
  };

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0 text-[10px] text-foreground/30 hover:bg-red-50 hover:text-red-600"
        onClick={() => { setOpen(true); setError(""); }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-red-600">Remove Position</DialogTitle>
            <DialogDescription>
              Are you sure you want to remove <span className="font-semibold text-foreground">{name || ticker}</span> ({shares} shares) from your portfolio? This does not execute a sell order -- it only removes the record.
            </DialogDescription>
          </DialogHeader>
          {error && <p className="text-xs text-destructive">{error}</p>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="flex-1">
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={loading} className="flex-1">
              {loading ? "Removing..." : "Remove"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
