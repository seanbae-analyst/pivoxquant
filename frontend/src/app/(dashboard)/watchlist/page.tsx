"use client";

/**
 * Watchlist — Vantablack ink terminal card on ivory shell.
 *
 * Records "observed" symbols. Neutral observation language only.
 * No buy/sell/recommend. DisclaimerBanner at foot.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { useWatchlist } from "@/lib/hooks";
import { fmtPct, pctColorClass } from "@/lib/format";
import type { WatchlistItem } from "@/lib/types";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import {
  Caption,
  Fleuron,
  FootSignature,
  RuledKicker,
} from "@/components/ui/editorial";
import { AddSymbolModal } from "@/components/watchlist/add-symbol-modal";
import { isMarketOpen } from "@/lib/market-hours";
import {
  PriceWithTimestamp,
  relativeTime,
} from "@/components/ui/price-with-timestamp";

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

// Never synthesize 52W ranges from the current price — fabricated price
// history rendered alongside live data is a misrepresentation risk under
// 자본시장법. Same policy as portfolio/page.tsx (no MOCK_POSITIONS) and
// discover/page.tsx (no MOCK_INDICES). Until WatchlistItem carries real
// `high_52w` / `low_52w` fields from the backend, render an em dash.

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

  // 1s tick for the "Live" banner.
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const marketOpen = isMarketOpen();
  // Use the most recently observed price as the page-level stamp.
  const latestObserved = useMemo(() => {
    let latest: number | null = null;
    for (const it of watchlist) {
      if (it.observed_at) {
        const t = new Date(it.observed_at).getTime();
        if (Number.isFinite(t) && (latest == null || t > latest)) latest = t;
      }
    }
    return latest ? new Date(latest).toISOString() : null;
  }, [watchlist]);

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
        <RuledKicker>PivoxQuant &middot; Watchlist &middot; {weekTag()}</RuledKicker>
        <div className="flex items-center gap-1.5 font-mono tabular-nums text-[10px]">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              marketOpen
                ? "bg-[#7db487] animate-pulse"
                : "bg-[var(--pq-bronze)] opacity-50"
            }`}
          />
          <span
            className="uppercase tracking-[0.22em]"
            style={{ color: "var(--pq-bronze)" }}
          >
            {marketOpen ? "Live" : "Closed"}
          </span>
          {latestObserved && (
            <span style={{ color: "rgba(245,240,232,0.5)" }}>
              · {relativeTime(latestObserved, nowMs)}
            </span>
          )}
        </div>
      </header>

      {/* Title + CTA */}
        <div className="mb-10 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="pq-ink-h1">Watchlist</h1>
            <p className="mt-2 font-serif text-[15px] text-[var(--pq-ivory)]">
              Symbols you are observing.
            </p>
            <Caption className="mt-1">
              Nothing here is a recommendation. Informational only.
            </Caption>
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
                className="h-10 animate-pulse bg-[rgba(245,240,232,0.04)] rounded-sm"
              />
            ))}
          </div>
        ) : watchlist.length === 0 ? (
          <div className="pq-ink-empty text-center py-16">
            <Fleuron size={16} />
            <div className="font-serif text-xl text-[var(--pq-ivory)] mt-3">No symbols yet.</div>
            <Caption className="mt-2">Add one to begin observing.</Caption>
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
                      <td className="num">
                        <PriceWithTimestamp
                          price={item.price}
                          observedAt={item.observed_at}
                          currency={item.currency}
                          size="sm"
                        />
                      </td>
                      <td
                        className={
                          // KR convention via single source (lib/format.ts): ▲ red, ▼ blue.
                          "num " + pctColorClass(item.change_pct)
                        }
                      >
                        {fmtPct(item.change_pct ?? 0)}
                      </td>
                      <td className="font-mono text-[11px] text-[rgba(245,240,232,0.55)]">
                        {/* 52W range pending real backend field — see note above. */}
                        —
                      </td>
                      <td className="text-[11px] text-[rgba(245,240,232,0.6)] truncate max-w-[220px]">
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

      {/* Editorial signature + Disclaimer */}
      <FootSignature />
      <div className="mt-4 text-[rgba(245,240,232,0.7)]">
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
