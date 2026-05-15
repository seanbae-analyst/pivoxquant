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
import { fmtPct, fmtRange52w, pctColorClass } from "@/lib/format";
import type { WatchlistItem } from "@/lib/types";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  Caption,
  EditorialHead,
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


// 52W ranges are sourced from the backend `range_52w: [lo, hi]` envelope
// (routes/watchlist.py:74-87 — Bug #9 wire-up 2026-05-13). KRW=integer /
// USD=2dp, or `null` when either bound is missing — in which case we render
// an em-dash rather than fabricating "$0.00 – $0.00". Same anti-synthesis
// policy as portfolio/page.tsx (no MOCK_POSITIONS) and discover/page.tsx
// (no MOCK_INDICES) — fabricated price history rendered alongside live
// data is a misrepresentation risk under 자본시장법.

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
        <div className="flex items-center gap-1.5 font-mono tabular-nums text-pq-eyebrow">
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

      {/* Title + CTA — promoted to Playfair-with-italic-accent (Wave 2,
          2026-05-01). Was a flat sans `pq-ink-h1 "Watchlist"` which broke
          from /portfolio v2 "Your *book.*", /risk v2 "Risk *board.*",
          /signals "*observed* … *filtered*", /discover "What the desk
          *observed.*", /alerts "When the desk *spoke.*". */}
      <div className="mb-12 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1
            className="font-display"
            style={{
              fontWeight: 500,
              fontSize: "clamp(34px, 4.6vw, 52px)",
              lineHeight: 1.06,
              letterSpacing: "-0.022em",
              color: "var(--pq-ivory)",
            }}
          >
            Symbols you are{" "}
            <span style={{ fontStyle: "italic", color: "var(--pq-bronze)" }}>
              observing.
            </span>
          </h1>
          <Caption className="mt-3 max-w-[560px]">
            Disclaimer: nothing here is a recommendation, and we do not
            recommend any action. A quiet ledger of what you have chosen to
            keep an eye on — informational only.
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
                className="h-10 animate-pulse bg-[var(--pq-ivory-line-faint)] rounded-sm"
              />
            ))}
          </div>
        ) : watchlist.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <Fleuron size={16} />
            <EditorialHead
              size={22}
              as="p"
              className="mt-2"
              style={{ lineHeight: 1.2 }}
            >
              No symbols on{" "}
              <span style={{ fontStyle: "italic", color: "var(--pq-bronze)" }}>
                watch.
              </span>
            </EditorialHead>
            <Caption className="max-w-md">
              Add one to begin observing — the ledger fills as you do.
            </Caption>
          </div>
        ) : (
          <>
            {/* Desktop / tablet — 7-column hairline table */}
            <div className="hidden md:block overflow-x-auto">
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
                          {/*
                            2026-05-15 (bug-hunter Wave 4 P2 #3,
                            feedback_ticker_display memory rule, 3rd
                            enforcement): KR tickers used to render
                            as "005930.KS" in the SYMBOL column while
                            US showed "AAPL" — asymmetric, and the
                            naked ".KS" suffix is exactly what the
                            ticker_display rule is meant to prevent.
                            The NAME column already shows the Korean
                            name (삼성전자), so the SYMBOL column
                            stripping the suffix gives the same
                            "short ticker" treatment to both regions.
                            US tickers pass through unchanged.
                          */}
                          {item.ticker.replace(/\.(KS|KQ)$/i, "")}
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
                        <td className="font-mono text-pq-mono-sm text-[rgba(245,240,232,0.55)]">
                          {fmtRange52w(item.range_52w, item.currency)}
                        </td>
                        <td className="text-pq-mono-sm text-[rgba(245,240,232,0.6)] truncate max-w-[220px]">
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
                            className="inline-flex h-11 w-11 -m-2 items-center justify-center text-[rgba(245,240,232,0.5)] hover:text-[var(--pq-bronze)] disabled:opacity-30"
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

            {/* Mobile — hairline-divided card list (P2 Wave B) */}
            <ul
              className="md:hidden border-t"
              style={{
                borderTopColor: "var(--pq-ivory-line)",
                borderTopWidth: 0.5,
              }}
            >
              {watchlist.map((item) => {
                const noteText =
                  item.note && item.note.length > 0
                    ? item.note
                    : item.signal === "POSITIVE"
                      ? "Observed — positive signal"
                      : item.signal === "NEGATIVE"
                        ? "Observed — negative signal"
                        : "Observed — neutral";
                return (
                  <li
                    key={item.id}
                    onClick={() => router.push(`/detail/${item.ticker}`)}
                    className="cursor-pointer px-1 py-3"
                    style={{
                      borderBottom: "0.5px solid var(--pq-ivory-line-soft)",
                    }}
                  >
                    {/* Row 1 — Symbol + Name */}
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="font-mono text-[var(--pq-bronze)] text-pq-body-sm tracking-wide whitespace-nowrap">
                        {item.ticker}
                      </span>
                      <span className="text-pq-caption text-[rgba(245,240,232,0.65)] truncate text-right">
                        {item.name || item.ticker}
                      </span>
                    </div>

                    {/* Row 2 — Last + 1D Δ */}
                    <div className="mt-1.5 flex items-center justify-between gap-3">
                      <PriceWithTimestamp
                        price={item.price}
                        observedAt={item.observed_at}
                        currency={item.currency}
                        size="sm"
                      />
                      <span
                        className={
                          "tabular-nums text-pq-body-sm " +
                          pctColorClass(item.change_pct)
                        }
                      >
                        {fmtPct(item.change_pct ?? 0)}
                      </span>
                    </div>

                    {/* Row 3 — Note + Remove */}
                    <div className="mt-1.5 flex items-center justify-between gap-3">
                      <span className="text-pq-caption text-[rgba(245,240,232,0.55)] truncate flex-1 min-w-0">
                        {noteText}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRemove(item);
                        }}
                        disabled={removingId === item.id}
                        aria-label={`Remove ${item.ticker}`}
                        className="inline-flex h-11 w-11 -mr-2 items-center justify-center text-[rgba(245,240,232,0.5)] hover:text-[var(--pq-bronze)] disabled:opacity-30 shrink-0"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </>
        )}

      {/* Editorial signature — legal disclaimer mounted by (dashboard)/layout.tsx */}
      <FootSignature />

      {showAdd && (
        <AddSymbolModal
          onClose={() => setShowAdd(false)}
          onAdded={() => mutate()}
        />
      )}
    </ErrorBoundary>
  );
}
