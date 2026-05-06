"use client";

/**
 * /signals — The Clip Board.
 *
 * Cascades the /home + /market + /portfolio Dossier concept onto the
 * signals terminal. Three clipboard papers on the Vantablack desk, one
 * per tone:
 *
 *   Paper 1 — Top Positive   — front sheet (above threshold)
 *   Paper 2 — Neutral Zone   — mid sheet rotated (within band)
 *   Paper 3 — Top Negative   — back sheet tilted further (below threshold)
 *
 * Each paper renders a list of SignalMemoStrip rows; clicking a row
 * unfolds an in-place memo with the observation + four-pillar breakdown.
 * Clicking a paper itself lifts the whole clipboard forward on desktop.
 *
 * All SWR hooks, real-time cadence (liveRefresh 10s open / 60s closed),
 * filter pills, refresh endpoint, and DisclaimerBanner are preserved
 * verbatim. Only the render layer has been redesigned.
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL language only. No BUY/SELL/HOLD,
 * no advice/recommend language. DisclaimerBanner type="signal" preserved.
 */

import { useState, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { API } from "@/lib/endpoints";
import { apiFetch } from "@/lib/api";
import { PRICE_COLOR_HEX } from "@/lib/format";
import { liveRefresh } from "@/lib/market-hours";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { FootSignature } from "@/components/ui/editorial";
import { RefreshCw, Zap } from "lucide-react";

import { DossierDesk } from "@/components/home/dossier-desk";
import { PaperDocument } from "@/components/home/paper-document";
import { ClipboardPaper } from "@/components/signals/clipboard-paper";
import type { MemoSignalItem } from "@/components/signals/signal-memo-strip";

/* ── Types ── */

type SignalItem = MemoSignalItem;

interface SignalsListResponse {
  signals: SignalItem[];
}

/* ── Fetcher ── */

const fetcher = async (url: string) => {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

/* ── Filters ── */

const FILTERS = ["All", "POSITIVE", "NEUTRAL", "NEGATIVE"] as const;
type FilterValue = (typeof FILTERS)[number];

function filterLabel(f: FilterValue) {
  if (f === "All") return "All";
  return f.charAt(0) + f.slice(1).toLowerCase();
}

function weekTag(): string {
  const d = new Date();
  const first = new Date(d.getFullYear(), 0, 1);
  const days = Math.floor((d.getTime() - first.getTime()) / 86400000);
  const w = Math.ceil((days + first.getDay() + 1) / 7);
  return `${d.getFullYear()} · W${String(w).padStart(2, "0")}`;
}

/* ── Page ── */

export default function SignalsPageV1() {
  const router = useRouter();
  const [filter, setFilter] = useState<FilterValue>("All");
  const [refreshing, setRefreshing] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading, mutate } = useSWR<SignalsListResponse>(
    API.signals.all,
    fetcher,
    {
      // Market-aware: 10s open / 60s closed.
      refreshInterval: () => liveRefresh(10_000, 60_000),
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 3_000,
      errorRetryCount: 2,
      errorRetryInterval: 5_000,
    },
  );

  const signals = useMemo(() => data?.signals ?? [], [data?.signals]);

  const { positive, neutral, negative } = useMemo(() => {
    const p: SignalItem[] = [];
    const n: SignalItem[] = [];
    const neu: SignalItem[] = [];
    for (const s of signals) {
      if (s.signal === "POSITIVE") p.push(s);
      else if (s.signal === "NEGATIVE") n.push(s);
      else neu.push(s);
    }
    const byScore = (a: SignalItem, b: SignalItem) =>
      (b.score ?? 0) - (a.score ?? 0);
    return {
      positive: p.sort(byScore).slice(0, 12),
      neutral: neu.sort(byScore).slice(0, 12),
      negative: n.sort((a, b) => (a.score ?? 0) - (b.score ?? 0)).slice(0, 12),
    };
  }, [signals]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await apiFetch(API.signals.refresh, { method: "POST" });
      await mutate();
    } catch {
      // silent — SWR keeps stale view
    } finally {
      setRefreshing(false);
    }
  }, [mutate]);

  const onToggle = useCallback(
    (ticker: string) =>
      setExpandedId((prev) => (prev === ticker ? null : ticker)),
    [],
  );
  const onOpenDetail = useCallback(
    (ticker: string) => router.push(`/detail/${ticker}`),
    [router],
  );

  const showAll = filter === "All";
  const showPos = showAll || filter === "POSITIVE";
  const showNeu = showAll || filter === "NEUTRAL";
  const showNeg = showAll || filter === "NEGATIVE";

  /* ── Active-paper controller ── */
  type PaperId = "positive" | "neutral" | "negative";
  const [active, setActive] = useState<PaperId | null>(null);
  const onSelect = (id: PaperId) =>
    setActive((cur) => (cur === id ? null : id));

  return (
    <ErrorBoundary>
      {/* ═══════════ HEADER ═══════════ */}
      <header className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="pq-ink-kicker">
            SIGNALS · {weekTag()}
          </div>
          <h1 className="pq-ink-h1 mt-2">The Clip Board</h1>
          <p className="mt-1 text-[10.5px] uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
            내 포지션 시그널 — {signals.length} covered
          </p>
          <p className="mt-2 max-w-xl font-serif text-sm text-[rgba(245,240,232,0.55)]">
            My Holdings — Signals. Quantitative observations on your covered
            tickers. Clip any memo to unfold its four-pillar readout in place.
          </p>
          {/* Objective threshold legend — score-based classification, not opinion. */}
          <div className="mt-3 flex flex-wrap items-center gap-3 text-[10px] text-[rgba(245,240,232,0.55)]">
            <span className="pq-ink-pill pq-ink-pill--pos">Positive</span>
            <span className="-ml-1">= score ≥ 65</span>
            <span className="pq-ink-pill pq-ink-pill--neu">Neutral</span>
            <span className="-ml-1">= 35–65</span>
            <span className="pq-ink-pill pq-ink-pill--neg">Negative</span>
            <span className="-ml-1">= score &lt; 35</span>
          </div>
          <p className="mt-2 max-w-xl text-[11px] italic text-[rgba(245,240,232,0.45)]">
            Objective classification by composite score — not advice or recommendation.
          </p>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshing}
          className="pq-ink-btn-ghost disabled:opacity-40 self-start md:self-auto"
        >
          <RefreshCw
            className={"h-3.5 w-3.5 " + (refreshing ? "animate-spin" : "")}
          />
          <span>Refresh</span>
        </button>
      </header>

      {/* Tally strip */}
      <div className="mb-6 grid grid-cols-3 gap-6 border-y border-[rgba(245,240,232,0.1)] py-4">
        <div>
          <div className="pq-ink-label">Positive</div>
          <div
            className="mt-1 font-serif text-[26px] tabular-nums"
            style={{ color: PRICE_COLOR_HEX.up }}
          >
            {positive.length}
          </div>
        </div>
        <div>
          <div className="pq-ink-label">Neutral</div>
          <div className="mt-1 font-serif text-[26px] tabular-nums text-[var(--pq-ivory)]">
            {neutral.length}
          </div>
        </div>
        <div>
          <div className="pq-ink-label">Negative</div>
          <div
            className="mt-1 font-serif text-[26px] tabular-nums"
            style={{ color: PRICE_COLOR_HEX.down }}
          >
            {negative.length}
          </div>
        </div>
      </div>

      {/* Filter pills */}
      <div className="pq-ink-tabs mb-6">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => {
              setFilter(f);
              setActive(null);
              setExpandedId(null);
            }}
            data-active={filter === f}
            className="pq-ink-tab"
          >
            {filterLabel(f)}
          </button>
        ))}
      </div>

      {/* ═══════════ LOADING / EMPTY ═══════════ */}
      {isLoading && signals.length === 0 ? (
        <div className="py-24 text-center font-serif text-[13px] text-[rgba(245,240,232,0.4)]">
          Loading observations…
        </div>
      ) : signals.length === 0 ? (
        <div className="py-24 text-center">
          <Zap
            className="mx-auto h-8 w-8 text-[var(--pq-bronze)]"
            strokeWidth={1.3}
          />
          <div className="mt-3 font-serif text-[14px] text-[rgba(245,240,232,0.6)]">
            No observations on record.
          </div>
          <p className="mt-1 text-[12px] text-[rgba(245,240,232,0.4)]">
            Add positions or tickers to your watchlist to surface memos.
          </p>
        </div>
      ) : (
        /* ═══════════ THE DESK ═══════════ */
        <DossierDesk>
          {/* ── Desktop: 3D stacked clipboard papers ── */}
          <div
            className="hidden md:block relative"
            style={{
              margin: "0 auto",
              maxWidth: 1020,
              padding: "56px 0 36px",
            }}
          >
            {/* Paper 3 — Negative (deepest, left fan) */}
            {showNeg && (
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  top: 90,
                  zIndex: active === "negative" ? 30 : 1,
                }}
              >
                <PaperDocument
                  rotation={-6.5}
                  zOffset={-90}
                  xOffset={-70}
                  active={active === "negative"}
                  dimmed={active !== null && active !== "negative"}
                  onClick={() => onSelect("negative")}
                  ariaLabel="Top negative signals clipboard"
                >
                  <ClipboardPaper
                    kicker="Clip Board · III"
                    title="Top Negative"
                    tone="neg"
                    items={negative}
                    expandedId={expandedId}
                    onToggle={onToggle}
                    onOpenDetail={onOpenDetail}
                  />
                </PaperDocument>
              </div>
            )}

            {/* Paper 2 — Neutral (mid, right fan) */}
            {showNeu && (
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  top: 44,
                  zIndex: active === "neutral" ? 30 : 2,
                }}
              >
                <PaperDocument
                  rotation={-3.5}
                  zOffset={-40}
                  xOffset={52}
                  active={active === "neutral"}
                  dimmed={active !== null && active !== "neutral"}
                  onClick={() => onSelect("neutral")}
                  ariaLabel="Neutral zone signals clipboard"
                >
                  <ClipboardPaper
                    kicker="Clip Board · II"
                    title="Neutral Zone"
                    tone="neu"
                    items={neutral}
                    expandedId={expandedId}
                    onToggle={onToggle}
                    onOpenDetail={onOpenDetail}
                  />
                </PaperDocument>
              </div>
            )}

            {/* Paper 1 — Positive (front) */}
            {showPos && (
              <div
                style={{
                  position: "relative",
                  zIndex:
                    active === "positive" || active === null ? 20 : 10,
                }}
              >
                <PaperDocument
                  rotation={0}
                  zOffset={0}
                  xOffset={0}
                  active={active === "positive"}
                  dimmed={active !== null && active !== "positive"}
                  onClick={() => onSelect("positive")}
                  ariaLabel="Top positive signals clipboard"
                >
                  <ClipboardPaper
                    kicker="Clip Board · I"
                    title="Top Positive"
                    tone="pos"
                    items={positive}
                    expandedId={expandedId}
                    onToggle={onToggle}
                    onOpenDetail={onOpenDetail}
                  />
                </PaperDocument>
              </div>
            )}

            {/* Spacer reserves footprint for the deepest paper */}
            <div aria-hidden style={{ height: 640 }} />

            <p
              style={{
                textAlign: "center",
                fontSize: 12,
                color: "rgba(245,240,232,0.4)",
                letterSpacing: "0.02em",
                marginTop: 28,
              }}
            className="font-serif" >
              {active
                ? "Click the surfaced clipboard again to return it to the stack."
                : "Click any clipboard to draw it forward."}
            </p>
          </div>

          {/* ── Mobile: vertical flat stack ── */}
          <div
            className="md:hidden flex flex-col gap-5"
            style={{ padding: "12px 0 24px" }}
          >
            {showPos && (
              <PaperDocument
                rotation={0}
                zOffset={0}
                xOffset={0}
                ariaLabel="Top positive signals clipboard"
              >
                <ClipboardPaper
                  kicker="Clip Board · I"
                  title="Top Positive"
                  tone="pos"
                  items={positive}
                  expandedId={expandedId}
                  onToggle={onToggle}
                  onOpenDetail={onOpenDetail}
                />
              </PaperDocument>
            )}
            {showNeu && (
              <PaperDocument
                rotation={0}
                zOffset={0}
                xOffset={0}
                ariaLabel="Neutral zone signals clipboard"
              >
                <ClipboardPaper
                  kicker="Clip Board · II"
                  title="Neutral Zone"
                  tone="neu"
                  items={neutral}
                  expandedId={expandedId}
                  onToggle={onToggle}
                  onOpenDetail={onOpenDetail}
                />
              </PaperDocument>
            )}
            {showNeg && (
              <PaperDocument
                rotation={0}
                zOffset={0}
                xOffset={0}
                ariaLabel="Top negative signals clipboard"
              >
                <ClipboardPaper
                  kicker="Clip Board · III"
                  title="Top Negative"
                  tone="neg"
                  items={negative}
                  expandedId={expandedId}
                  onToggle={onToggle}
                  onOpenDetail={onOpenDetail}
                />
              </PaperDocument>
            )}
          </div>
        </DossierDesk>
      )}

      {/* Foot signature — legal disclaimer mounted by (dashboard)/layout.tsx */}
      <FootSignature />
    </ErrorBoundary>
  );
}
