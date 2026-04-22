"use client";

/**
 * Watchlist — Editorial Ivory/Bronze table of observed symbols.
 *
 * - Header: italic serif "Watchlist" + Add Symbol CTA (Bronze pill).
 * - Table: Symbol · Name · Last · 1D Δ · 52W Range · Note · Actions.
 * - Empty state: one-line editorial invitation.
 * - AddSymbolModal hooks into /api/watchlist POST.
 *
 * Legal: column labels and copy say "observed" / "noted" only. No
 * buy/sell/recommend anywhere on this page.
 */

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { useWatchlist } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { fmtPct } from "@/lib/format";
import type { WatchlistItem } from "@/lib/types";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { AddSymbolModal } from "@/components/watchlist/add-symbol-modal";

/* ── helpers ────────────────────────────────────────── */

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

/** Mock 52-week range string — backend doesn't expose this on watchlist yet. */
function mock52W(item: WatchlistItem): string {
  // Deterministic hash from ticker so the display is stable across renders.
  const seed = Array.from(item.ticker).reduce((a, c) => a + c.charCodeAt(0), 0);
  const spread = 0.18 + (seed % 30) / 100; // 18–47%
  const low = item.price * (1 - spread * 0.6);
  const high = item.price * (1 + spread * 0.4);
  const fmt = (v: number) =>
    item.currency === "KRW"
      ? `₩${Math.round(v).toLocaleString("en-US")}`
      : `$${v.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  return `${fmt(low)} – ${fmt(high)}`;
}

/* ── page ───────────────────────────────────────────── */

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
      <div
        className="min-h-screen"
        style={{ background: "var(--pq-ivory)" }}
      >
        <div className="mx-auto max-w-5xl px-6 py-10">
          {/* Header */}
          <header className="flex items-end justify-between gap-6 pb-6">
            <div>
              <div
                className="text-[10px] uppercase"
                style={{ letterSpacing: "0.2em", color: "var(--pq-muted)" }}
              >
                Observations
              </div>
              <h1
                className="mt-1 text-3xl italic"
                style={{ fontFamily: "var(--font-serif), serif", color: "var(--pq-ink)" }}
              >
                Watchlist
              </h1>
              <p
                className="mt-1 text-sm italic"
                style={{ fontFamily: "var(--font-serif), serif", color: "var(--pq-muted)" }}
              >
                Symbols you have chosen to follow. Nothing here is a recommendation.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowAdd(true)}
              className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-xs uppercase transition-opacity hover:opacity-90"
              style={{
                background: "var(--pq-bronze)",
                color: "var(--pq-ivory)",
                letterSpacing: "0.2em",
              }}
            >
              <Plus className="h-3.5 w-3.5" />
              Add Symbol
            </button>
          </header>

          <DisclaimerBanner type="signal" />

          {/* Table */}
          <div
            className="mt-8 overflow-hidden"
            style={{ borderTop: "0.5px solid var(--pq-hairline)", borderBottom: "0.5px solid var(--pq-hairline)" }}
          >
            {/* Column head */}
            <div
              className="grid grid-cols-[120px_1fr_120px_100px_200px_1fr_64px] items-center gap-4 px-4 py-3 text-[10px] uppercase"
              style={{
                letterSpacing: "0.2em",
                color: "var(--pq-muted)",
                borderBottom: "0.5px solid var(--pq-hairline)",
              }}
            >
              <span>Symbol</span>
              <span>Name</span>
              <span className="text-right">Last</span>
              <span className="text-right">1D Δ</span>
              <span>52W Range</span>
              <span>Note</span>
              <span className="text-right">Actions</span>
            </div>

            {/* Rows */}
            {isLoading ? (
              <TableSkeleton />
            ) : watchlist.length === 0 ? (
              <EmptyRow />
            ) : (
              watchlist.map((item) => (
                <Row
                  key={item.id}
                  item={item}
                  onOpen={() => router.push(`/detail/${item.ticker}`)}
                  onRemove={() => handleRemove(item)}
                  removing={removingId === item.id}
                />
              ))
            )}
          </div>
        </div>

        {showAdd && (
          <AddSymbolModal
            onClose={() => setShowAdd(false)}
            onAdded={() => mutate()}
          />
        )}
      </div>
    </ErrorBoundary>
  );
}

/* ── row ────────────────────────────────────────────── */

function Row({
  item,
  onOpen,
  onRemove,
  removing,
}: {
  item: WatchlistItem;
  onOpen: () => void;
  onRemove: () => void;
  removing: boolean;
}) {
  const isPositive = (item.change_pct ?? 0) >= 0;

  return (
    <div
      className="grid cursor-pointer grid-cols-[120px_1fr_120px_100px_200px_1fr_64px] items-center gap-4 px-4 py-4 transition-colors hover:bg-[rgba(139,111,71,0.04)]"
      style={{ borderBottom: "0.5px solid var(--pq-hairline-soft)" }}
      onClick={onOpen}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter") onOpen();
      }}
    >
      {/* Symbol */}
      <span
        className="font-mono text-sm font-semibold"
        style={{ color: "var(--pq-bronze)", letterSpacing: "0.02em" }}
      >
        {item.ticker}
      </span>

      {/* Name */}
      <span
        className="truncate text-sm"
        style={{ color: "var(--pq-ink)", fontFamily: "var(--font-serif), serif" }}
      >
        {item.name || item.ticker}
      </span>

      {/* Last */}
      <span
        className="text-right font-mono text-sm"
        style={{ color: "var(--pq-ink)" }}
      >
        {formatPrice(item)}
      </span>

      {/* 1D Δ */}
      <span
        className={cn("text-right font-mono text-sm")}
        style={{ color: isPositive ? "var(--pq-bronze)" : "var(--pq-muted)" }}
      >
        {fmtPct(item.change_pct ?? 0)}
      </span>

      {/* 52W Range */}
      <span
        className="font-mono text-xs"
        style={{ color: "var(--pq-muted)" }}
      >
        {mock52W(item)}
      </span>

      {/* Note (signal label, sans-marketing) */}
      <span
        className="truncate text-xs italic"
        style={{ color: "var(--pq-muted)", fontFamily: "var(--font-serif), serif" }}
      >
        {item.signal === "POSITIVE"
          ? "Observed — positive signal"
          : item.signal === "NEGATIVE"
            ? "Observed — negative signal"
            : "Observed — neutral"}
      </span>

      {/* Actions */}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          disabled={removing}
          aria-label={`Remove ${item.ticker}`}
          className="flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-[rgba(139,111,71,0.1)] disabled:opacity-40"
          style={{ color: "var(--pq-muted)" }}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

/* ── empty + skeleton ───────────────────────────────── */

function EmptyRow() {
  return (
    <div
      className="px-4 py-16 text-center"
      style={{ borderBottom: "0.5px solid var(--pq-hairline-soft)" }}
    >
      <p
        className="text-lg italic"
        style={{ fontFamily: "var(--font-serif), serif", color: "var(--pq-ink)" }}
      >
        No symbols yet.
      </p>
      <p
        className="mt-1 text-sm italic"
        style={{ fontFamily: "var(--font-serif), serif", color: "var(--pq-muted)" }}
      >
        Add one to begin observing.
      </p>
    </div>
  );
}

function TableSkeleton() {
  return (
    <div>
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className="grid grid-cols-[120px_1fr_120px_100px_200px_1fr_64px] gap-4 px-4 py-4"
          style={{ borderBottom: "0.5px solid var(--pq-hairline-soft)" }}
        >
          <div className="h-4 w-16 animate-pulse rounded" style={{ background: "var(--pq-hairline-soft)" }} />
          <div className="h-4 w-40 animate-pulse rounded" style={{ background: "var(--pq-hairline-soft)" }} />
          <div className="h-4 w-16 animate-pulse justify-self-end rounded" style={{ background: "var(--pq-hairline-soft)" }} />
          <div className="h-4 w-12 animate-pulse justify-self-end rounded" style={{ background: "var(--pq-hairline-soft)" }} />
          <div className="h-4 w-32 animate-pulse rounded" style={{ background: "var(--pq-hairline-soft)" }} />
          <div className="h-4 w-28 animate-pulse rounded" style={{ background: "var(--pq-hairline-soft)" }} />
          <div className="h-4 w-4 animate-pulse justify-self-end rounded" style={{ background: "var(--pq-hairline-soft)" }} />
        </div>
      ))}
    </div>
  );
}
