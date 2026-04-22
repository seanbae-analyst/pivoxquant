"use client";

/**
 * Watchlist — Vantablack ink terminal card on ivory shell.
 *
 * Records "observed" symbols. Neutral observation language only.
 * No buy/sell/recommend. DisclaimerBanner at foot.
 */

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { useWatchlist } from "@/lib/hooks";
import { fmtPct } from "@/lib/format";
import type { WatchlistItem } from "@/lib/types";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { AddSymbolModal } from "@/components/watchlist/add-symbol-modal";

function formatPrice(item: WatchlistItem): string {
  if (item.price == null) return "—";
  if (item.currency === "KRW") {
    return `₩${Math.round(item.price).toLocaleString("en-US")}`;
  }
  return `$${item.price.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function mock52W(item: WatchlistItem): string {
  if (!item.price) return "—";
  const seed = Array.from(item.ticker).reduce((a, c) => a + c.charCodeAt(0), 0);
  const spread = 0.18 + (seed % 30) / 100;
  const low = item.price * (1 - spread * 0.6);
  const high = item.price * (1 + spread * 0.4);
  const fmt = (v: number) =>
    item.currency === "KRW"
      ? `₩${Math.round(v).toLocaleString("en-US")}`
      : `$${v.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  return `${fmt(low)} – ${fmt(high)}`;
}

function weekTag(): string {
  const d = new Date();
  const first = new Date(d.getFullYear(), 0, 1);
  const days = Math.floor((d.getTime() - first.getTime()) / 86400000);
  const w = Math.ceil((days + first.getDay() + 1) / 7);
  return `${d.getFullYear()} · W${String(w).padStart(2, "0")}`;
}

export default function WatchlistPage() {
  const router = useRouter();
  const { data, isLoading, mutate } = useWatchlist();
  const [showAdd, setShowAdd] = useState(false);
  const [removingId, setRemovingId] = useState<number | null>(null);

  const watchlist = useMemo<WatchlistItem[]>(
    () => data?.watchlist ?? [],
    [data?.watchlist],
  );

  const handleRemove = useCallback(
    async (item: WatchlistItem) => {
      setRemovingId(item.id);
      try {
        await apiFetch(API.watchlist.remove(item.id), { method: "DELETE" });
        toast.success(`${item.ticker} removed`);
        await mutate();
      } catch {
        toast.error(`Could not remove ${item.ticker}`);
      } finally {
        setRemovingId(null);
      }
    },
    [mutate],
  );

  return (
    <ErrorBoundary>
      {/* Terminal header */}
      <header className="mb-8 flex items-center justify-between gap-4">
        <span className="pq-ink-kicker">PIVOXQUANT · WATCHLIST</span>
        <span className="font-mono text-[9.5px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
          {weekTag()}
        </span>
      </header>

      {/* Title + CTA */}
        <div className="mb-10 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="pq-ink-h1">Watchlist</h1>
            <p className="mt-2 font-serif italic text-sm text-[rgba(245,240,232,0.55)]">
              Symbols you have chosen to follow. Nothing here is a recommendation.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowAdd(true)}
            className="pq-ink-btn-bronze"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Symbol
          </button>
        </div>

        {/* Table */}
        {isLoading ? (
          <div className="space-y-2">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-10 animate-pulse bg-white/5 rounded-sm"
              />
            ))}
          </div>
        ) : watchlist.length === 0 ? (
          <div className="pq-ink-empty">
            <div className="font-serif italic text-xl text-[var(--pq-ivory)]">No symbols yet.</div>
            <div className="mt-2 text-sm">Add one to begin observing.</div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="pq-ink-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Name</th>
                  <th className="num">Last</th>
                  <th className="num">1D Δ</th>
                  <th>52W Range</th>
                  <th>Note</th>
                  <th className="num">Remove</th>
                </tr>
              </thead>
              <tbody>
                {watchlist.map((item) => {
                  const isPositive = (item.change_pct ?? 0) >= 0;
                  return (
                    <tr
                      key={item.id}
                      className="cursor-pointer"
                      onClick={() => router.push(`/detail/${item.ticker}`)}
                    >
                      <td className="font-mono text-[var(--pq-bronze)] tracking-wide">
                        {item.ticker}
                      </td>
                      <td className="text-[rgba(245,240,232,0.75)] truncate max-w-[240px]">
                        {item.name || item.ticker}
                      </td>
                      <td className="num">{formatPrice(item)}</td>
                      <td
                        className={
                          "num " +
                          (isPositive ? "text-[#7db487]" : "text-[#d18888]")
                        }
                      >
                        {fmtPct(item.change_pct ?? 0)}
                      </td>
                      <td className="font-mono text-[11px] text-[rgba(245,240,232,0.55)]">
                        {mock52W(item)}
                      </td>
                      <td className="text-[11px] italic text-[rgba(245,240,232,0.6)] truncate max-w-[220px]">
                        {item.note && item.note.length > 0
                          ? item.note
                          : item.signal === "POSITIVE"
                            ? "Observed — positive signal"
                            : item.signal === "NEGATIVE"
                              ? "Observed — negative signal"
                              : "Observed — neutral"}
                      </td>
                      <td className="num">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRemove(item);
                          }}
                          disabled={removingId === item.id}
                          aria-label={`Remove ${item.ticker}`}
                          className="inline-flex h-7 w-7 items-center justify-center text-[rgba(245,240,232,0.5)] hover:text-[var(--pq-bronze)] disabled:opacity-30"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

      {/* Disclaimer */}
      <div className="mt-12 border-t border-[rgba(245,240,232,0.1)] pt-6 text-[rgba(245,240,232,0.7)]">
        <DisclaimerBanner type="signal" />
      </div>

      {showAdd && (
        <AddSymbolModal
          onClose={() => setShowAdd(false)}
          onAdded={() => mutate()}
        />
      )}
    </ErrorBoundary>
  );
}
