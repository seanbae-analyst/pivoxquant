"use client";

/**
 * Portfolio — The Ledger Binder.
 *
 * Three ivory papers on a Vantablack dossier desk:
 *   Paper 1 · LedgerBookPaper  — 4-stat + full positions table (every row)
 *   Paper 2 · SectorPaper      — bronze weighting bars (tilt -3°)
 *   Paper 3 · ActivityPaper    — recent trades chronology (tilt +4°)
 *
 * Records-only UX: Add / Buy More / Sell / Edit write through to the
 * backend positions + trades endpoints via the existing modals.
 * Not investment advice. DisclaimerBanner at foot.
 *
 * IMPORTANT: All SWR hooks, handlers, and modal logic are preserved from
 * the prior revision — only the render tree was re-wrapped into the
 * Dossier/Paper primitives.
 */

import { useMemo, useState, useEffect } from "react";
import useSWR, { mutate } from "swr";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { FootSignature, RuledKicker } from "@/components/ui/editorial";
import { DossierDesk } from "@/components/home/dossier-desk";
import { PaperDocument } from "@/components/home/paper-document";
import { LedgerBookPaper } from "@/components/portfolio/ledger-book-paper";
import { SectorPaper } from "@/components/portfolio/sector-paper";
import { ActivityPaper } from "@/components/portfolio/activity-paper";
import { AddPositionModal } from "@/components/portfolio/add-position-modal";
import { TradeModal } from "@/components/portfolio/trade-modal";
import { RollingWindowWidget } from "@/components/dashboard/rolling-window";
import {
  PORTFOLIO_POSITIONS,
  PORTFOLIO_SUMMARY,
  PORTFOLIO_TRADES,
} from "@/lib/endpoints";
import { apiFetch, ApiError } from "@/lib/api";
import { liveRefresh, isMarketOpen } from "@/lib/market-hours";
import { relativeTime } from "@/components/ui/price-with-timestamp";
import { toast } from "sonner";
import type { Position, Trade, TradeAction } from "@/components/portfolio/types";

const FX_FALLBACK = 1342;

interface PositionsResponse { positions?: Position[]; }
interface TradesResponse { trades?: Trade[]; }
interface SummaryResponse {
  totalNav?: number;
  todayPnl?: number;
  todayPnlPct?: number;
  unrealized?: number;
  realizedYtd?: number;
  fxRate?: number;
}

const fetcher = async <T,>(url: string): Promise<T> => apiFetch<T>(url);

function handleApiError(err: unknown, context: string) {
  if (err instanceof ApiError && err.status === 401) {
    if (typeof window !== "undefined") window.location.href = "/login";
    return;
  }
  const message = err instanceof Error ? err.message : "Something went wrong";
  toast.error(`${context}: ${message}`);
}

function weekTag(): string {
  const d = new Date();
  const first = new Date(d.getFullYear(), 0, 1);
  const days = Math.floor((d.getTime() - first.getTime()) / 86400000);
  const w = Math.ceil((days + first.getDay() + 1) / 7);
  return `${d.getFullYear()} · W${String(w).padStart(2, "0")}`;
}

export default function PortfolioPage() {
  const [addOpen, setAddOpen] = useState(false);
  const [tradeAction, setTradeAction] = useState<TradeAction | null>(null);
  const [targetPosition, setTargetPosition] = useState<Position | null>(null);
  const [showSkeleton, setShowSkeleton] = useState(true);

  // Market-aware refresh — 5s when open, 60s when closed.
  // P0-3 FIX: bumped dedupingInterval 2s → 10s and added focusThrottleInterval
  // + revalidateIfStale:false so we don't pile 5+ in-flight requests when
  // RealtimeProvider + SSE handlers + sibling components race mount.
  const swrOpts = {
    refreshInterval: () => liveRefresh(5_000, 60_000),
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    revalidateIfStale: false,
    dedupingInterval: 10_000,
    focusThrottleInterval: 5_000,
    errorRetryCount: 2,
  } as const;
  // Trades are append-only and don't need sub-minute refresh.
  const tradesOpts = {
    refreshInterval: () => liveRefresh(15_000, 60_000),
    revalidateOnFocus: true,
    dedupingInterval: 5_000,
    errorRetryCount: 2,
  } as const;

  const { data: posData, error: posErr, isLoading: posLoading } =
    useSWR<PositionsResponse>(PORTFOLIO_POSITIONS, fetcher, swrOpts);
  const { data: sumData, error: sumErr } =
    useSWR<SummaryResponse & { observed_at?: string }>(PORTFOLIO_SUMMARY, fetcher, swrOpts);
  const { data: tradesData, error: tradesErr } =
    useSWR<TradesResponse>(`${PORTFOLIO_TRADES}?limit=8`, fetcher, tradesOpts);

  // 1s tick for the "Live · Xs ago" header banner.
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const marketOpen = isMarketOpen();
  const observedAt = sumData?.observed_at;

  useEffect(() => { if (posErr) handleApiError(posErr, "Positions"); }, [posErr]);
  useEffect(() => { if (sumErr) handleApiError(sumErr, "Summary"); }, [sumErr]);
  useEffect(() => { if (tradesErr) handleApiError(tradesErr, "Trades"); }, [tradesErr]);

  useEffect(() => {
    const t = setTimeout(() => setShowSkeleton(false), 1200);
    return () => clearTimeout(t);
  }, []);

  // Never fall back to MOCK_POSITIONS / MOCK_TRADES (hardcoded SPY/QQQ/AAPL
  // fixtures) — displaying fake holdings in a real portfolio view is a
  // misrepresentation risk under 자본시장법, and a trust risk regardless.
  // Same policy as discover/page.tsx (see comment near MOCK_INDICES).
  // On error we render an empty state + an explicit retry banner below.
  const positions: Position[] = useMemo(() => {
    if (posErr) return [];
    return posData?.positions ?? [];
  }, [posData, posErr]);

  const trades: Trade[] = useMemo(() => {
    if (tradesErr) return [];
    return tradesData?.trades ?? [];
  }, [tradesData, tradesErr]);

  const hasLoadError = Boolean(posErr || tradesErr);

  const totals = useMemo(() => {
    let mv = 0;
    let cost = 0;
    for (const p of positions) {
      mv += p.shares * p.current;
      cost += p.shares * p.avgCost;
    }
    const unrealized = mv - cost;
    const fx = (sumData?.fxRate && sumData.fxRate > 0) ? sumData.fxRate : FX_FALLBACK;
    if (sumData && typeof sumData.totalNav === "number") {
      return {
        totalNav: sumData.totalNav,
        todayPnl: sumData.todayPnl ?? 0,
        todayPnlPct: sumData.todayPnlPct ?? 0,
        unrealized: sumData.unrealized ?? unrealized,
        realizedYtd: sumData.realizedYtd ?? 0,
        fxRate: fx,
      };
    }
    return { totalNav: mv, todayPnl: 0, todayPnlPct: 0, unrealized, realizedYtd: 0, fxRate: fx };
  }, [sumData, positions]);

  // Sector allocation — computed inline.
  // KRW positions are converted to USD via fxRate so that mixed-currency
  // books don't sum raw won values into the dollar bucket (previously a
  // ₩1,389,100 KRW position rendered as $1,389,100 in the sector chart).
  const sectorAlloc = useMemo(() => {
    const byS: Record<string, number> = {};
    let total = 0;
    const fx = totals.fxRate && totals.fxRate > 0 ? totals.fxRate : FX_FALLBACK;
    for (const p of positions) {
      const rawMv = p.shares * p.current;
      const mvUsd = p.currency === "KRW" ? rawMv / fx : rawMv;
      byS[p.sector] = (byS[p.sector] ?? 0) + mvUsd;
      total += mvUsd;
    }
    return Object.entries(byS)
      .map(([sector, mv]) => ({ sector, mv, pct: total > 0 ? (mv / total) * 100 : 0 }))
      .sort((a, b) => b.mv - a.mv);
  }, [positions, totals.fxRate]);

  function openAction(action: TradeAction, position: Position) {
    setTargetPosition(position);
    setTradeAction(action);
  }
  function closeTrade() {
    setTradeAction(null);
    setTargetPosition(null);
  }
  function refreshAll() {
    mutate(PORTFOLIO_POSITIONS);
    mutate(PORTFOLIO_SUMMARY);
    mutate(`${PORTFOLIO_TRADES}?limit=8`);
  }

  // Book display currency — honors the first position's currency, else USD.
  const bookCurrency: "USD" | "KRW" =
    positions.find((p) => p.currency === "KRW") &&
    !positions.find((p) => p.currency === "USD" || p.currency === undefined)
      ? "KRW"
      : "USD";

  const observedAgo =
    observedAt && marketOpen ? relativeTime(observedAt, nowMs) : null;

  if (posLoading && showSkeleton) {
    return (
      <div className="animate-pulse">
        <div className="h-4 w-40 bg-[rgba(245,240,232,0.08)] rounded-sm" />
        <div className="mt-6 h-10 w-56 bg-[rgba(245,240,232,0.08)] rounded-sm" />
        <div className="mt-10 grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-[rgba(245,240,232,0.04)] rounded-sm" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      {/* Terminal header row */}
      <header className="mb-6 flex items-center justify-between gap-4">
        <RuledKicker>PivoxQuant &middot; Portfolio &middot; {weekTag()}</RuledKicker>
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
          {observedAt && (
            <span style={{ color: "rgba(245,240,232,0.5)" }}>
              · {relativeTime(observedAt, nowMs)}
            </span>
          )}
        </div>
      </header>

      {hasLoadError && (
        <div
          role="alert"
          className="mb-4 flex items-center justify-between gap-3 px-4 py-3 font-mono text-[11px] uppercase tracking-[0.18em]"
          style={{
            background: "rgba(226, 185, 111, 0.06)",
            borderTop: "1px solid var(--pq-bronze)",
            borderBottom: "1px solid var(--pq-bronze)",
            color: "var(--pq-bronze)",
          }}
        >
          <span>
            Unable to load live portfolio data. No fallback values are shown.
          </span>
          <button
            type="button"
            onClick={refreshAll}
            className="underline-offset-4 hover:underline"
          >
            Refresh
          </button>
        </div>
      )}

      {/* ═══════════ THE LEDGER BINDER ═══════════ */}
      <DossierDesk maxTilt={1.0}>
        {/* ── Desktop: spread binder (left Ledger + right column of Sector/Activity) ── */}
        <div
          className="hidden md:grid"
          style={{
            margin: "0 auto",
            maxWidth: 1180,
            padding: "48px 0 32px",
            gridTemplateColumns: "minmax(0, 1.55fr) minmax(0, 1fr)",
            gap: 28,
            alignItems: "start",
          }}
        >
          {/* Paper 1 — Ledger book (main, flat, left page) */}
          <PaperDocument
            rotation={0}
            zOffset={0}
            xOffset={0}
            active
            ariaLabel="Portfolio ledger book"
          >
            <LedgerBookPaper
              positions={positions}
              totals={totals}
              bookCurrency={bookCurrency}
              observedAgo={observedAgo}
              onAddPosition={() => setAddOpen(true)}
              onAction={openAction}
            />
          </PaperDocument>

          {/* Right column — Rolling Window → Sector → Activity */}
          <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
            {/* RollingWindowWidget renders its own ivory paper surface */}
            <RollingWindowWidget paper />

            <PaperDocument
              rotation={-3}
              zOffset={-20}
              xOffset={8}
              ariaLabel="Sector weighting paper"
            >
              <SectorPaper rows={sectorAlloc} bookCurrency={bookCurrency} />
            </PaperDocument>

            <PaperDocument
              rotation={4}
              zOffset={-20}
              xOffset={-8}
              ariaLabel="Activity chronology paper"
            >
              <ActivityPaper
                trades={trades}
                bookCurrency={bookCurrency}
                limit={10}
              />
            </PaperDocument>
          </div>
        </div>

        {/* ── Mobile: flat vertical stack (Ledger → Sector → Activity) ── */}
        <div
          className="md:hidden flex flex-col gap-5"
          style={{ padding: "12px 0 24px" }}
        >
          <PaperDocument
            rotation={0}
            zOffset={0}
            xOffset={0}
            ariaLabel="Portfolio ledger book"
          >
            <LedgerBookPaper
              positions={positions}
              totals={totals}
              bookCurrency={bookCurrency}
              observedAgo={observedAgo}
              onAddPosition={() => setAddOpen(true)}
              onAction={openAction}
            />
          </PaperDocument>

          <RollingWindowWidget paper />

          <PaperDocument
            rotation={0}
            zOffset={0}
            xOffset={0}
            ariaLabel="Sector weighting paper"
          >
            <SectorPaper rows={sectorAlloc} bookCurrency={bookCurrency} />
          </PaperDocument>

          <PaperDocument
            rotation={0}
            zOffset={0}
            xOffset={0}
            ariaLabel="Activity chronology paper"
          >
            <ActivityPaper
              trades={trades}
              bookCurrency={bookCurrency}
              limit={10}
            />
          </PaperDocument>
        </div>
      </DossierDesk>

      {/* Editorial foot signature — legal disclaimer mounted by (dashboard)/layout.tsx */}
      <FootSignature note="PivoxQuant &middot; User-entered record &middot; Not investment advice" />

      {/* Modals — overlaid, retain existing ivory styling */}
      <AddPositionModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onSuccess={refreshAll}
      />
      <TradeModal
        key={targetPosition?.id ?? "none"}
        open={tradeAction !== null && targetPosition !== null}
        onClose={closeTrade}
        action={tradeAction ?? "buy"}
        position={targetPosition}
        onSuccess={refreshAll}
      />
    </ErrorBoundary>
  );
}
