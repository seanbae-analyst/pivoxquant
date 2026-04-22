"use client";

import { useMemo, useState, useEffect } from "react";
import useSWR, { mutate } from "swr";
import { toast } from "sonner";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { SummaryCards } from "@/components/portfolio/summary-cards";
import { PositionsTable } from "@/components/portfolio/positions-table";
import { RecentTrades } from "@/components/portfolio/recent-trades";
import { SectorAllocation } from "@/components/portfolio/sector-allocation";
import { AddPositionModal } from "@/components/portfolio/add-position-modal";
import { TradeModal } from "@/components/portfolio/trade-modal";
import { MOCK_POSITIONS, MOCK_TRADES } from "@/components/portfolio/mock-data";
import {
  PORTFOLIO_POSITIONS,
  PORTFOLIO_SUMMARY,
  PORTFOLIO_TRADES,
} from "@/lib/endpoints";
import { apiFetch, ApiError } from "@/lib/api";
import type { Position, Trade, TradeAction } from "@/components/portfolio/types";

/**
 * Portfolio — editorial Vantablack-tone surface.
 * Records-only UX: Add / Buy More / Sell / Edit write through to the
 * backend positions + trades endpoints. Not investment advice.
 */

interface PositionsResponse {
  positions?: Position[];
}
interface TradesResponse {
  trades?: Trade[];
}
interface SummaryResponse {
  totalNav?: number;
  todayPnl?: number;
  todayPnlPct?: number;
  unrealized?: number;
  realizedYtd?: number;
}

const fetcher = async <T,>(url: string): Promise<T> => apiFetch<T>(url);

/** Redirect on 401, surface 5xx as a toast but keep rendering via mock fallback. */
function handleApiError(err: unknown, context: string) {
  if (err instanceof ApiError && err.status === 401) {
    if (typeof window !== "undefined") window.location.href = "/login";
    return;
  }
  const message =
    err instanceof Error ? err.message : "Something went wrong";
  toast.error(`${context}: ${message}`);
}

export default function PortfolioPage() {
  const [addOpen, setAddOpen] = useState(false);
  const [tradeAction, setTradeAction] = useState<TradeAction | null>(null);
  const [targetPosition, setTargetPosition] = useState<Position | null>(null);
  const [showSkeleton, setShowSkeleton] = useState(true);

  const {
    data: posData,
    error: posErr,
    isLoading: posLoading,
  } = useSWR<PositionsResponse>(PORTFOLIO_POSITIONS, fetcher, {
    revalidateOnFocus: false,
  });

  const {
    data: sumData,
    error: sumErr,
  } = useSWR<SummaryResponse>(PORTFOLIO_SUMMARY, fetcher, {
    revalidateOnFocus: false,
  });

  const {
    data: tradesData,
    error: tradesErr,
  } = useSWR<TradesResponse>(`${PORTFOLIO_TRADES}?limit=8`, fetcher, {
    revalidateOnFocus: false,
  });

  // Surface errors once, on first settle. 5xx => mock fallback; 401 handled above.
  useEffect(() => {
    if (posErr) handleApiError(posErr, "Positions");
  }, [posErr]);
  useEffect(() => {
    if (sumErr) handleApiError(sumErr, "Summary");
  }, [sumErr]);
  useEffect(() => {
    if (tradesErr) handleApiError(tradesErr, "Trades");
  }, [tradesErr]);

  // 2-second skeleton minimum so the UI doesn't flash during fast responses.
  useEffect(() => {
    const t = setTimeout(() => setShowSkeleton(false), 2000);
    return () => clearTimeout(t);
  }, []);

  const positions: Position[] = useMemo(() => {
    if (posData?.positions && posData.positions.length > 0) {
      return posData.positions;
    }
    // Fallback: empty (if signed in w/ no holdings) vs. mock (if fetch failed).
    if (posErr) return MOCK_POSITIONS;
    return posData?.positions ?? [];
  }, [posData, posErr]);

  const trades: Trade[] = useMemo(() => {
    if (tradesData?.trades && tradesData.trades.length > 0) {
      return tradesData.trades;
    }
    if (tradesErr) return MOCK_TRADES;
    return tradesData?.trades ?? [];
  }, [tradesData, tradesErr]);

  const totals = useMemo(() => {
    // Prefer server-computed summary; compute locally as a fallback.
    let mv = 0;
    let cost = 0;
    for (const p of positions) {
      mv += p.shares * p.current;
      cost += p.shares * p.avgCost;
    }
    const unrealized = mv - cost;

    if (sumData && typeof sumData.totalNav === "number") {
      return {
        totalNav: sumData.totalNav,
        todayPnl: sumData.todayPnl ?? 0,
        todayPnlPct: sumData.todayPnlPct ?? 0,
        unrealized: sumData.unrealized ?? unrealized,
        realizedYtd: sumData.realizedYtd ?? 0,
      };
    }
    return {
      totalNav: mv,
      todayPnl: 0,
      todayPnlPct: 0,
      unrealized,
      realizedYtd: 0,
    };
  }, [sumData, positions]);

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

  if (posLoading && showSkeleton) {
    return (
      <div className="space-y-8 pb-12">
        <div className="h-12 w-48 animate-pulse rounded-sm bg-slate-100" />
        <div className="grid grid-cols-2 gap-px bg-slate-200 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-24 animate-pulse bg-white"
              aria-hidden
            />
          ))}
        </div>
        <div className="h-64 animate-pulse rounded-sm bg-slate-50" />
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="space-y-8 pb-12">
        {/* ── Header ── */}
        <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              Holdings
            </p>
            <h1 className="mt-1 font-serif text-[40px] italic leading-tight text-slate-900">
              Portfolio
            </h1>
            <p className="mt-1 text-[13px] text-slate-500">
              Your self-reported book of record. Informational only — not advice.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setAddOpen(true)}
            className="inline-flex h-10 items-center justify-center rounded-sm bg-[#8B6F47] px-5 text-[13px] font-medium tracking-wide text-white transition-colors hover:bg-[#6F5636]"
          >
            Add Position
          </button>
        </header>

        {/* ── Summary ── */}
        <SummaryCards
          totalNav={totals.totalNav}
          todayPnl={totals.todayPnl}
          todayPnlPct={totals.todayPnlPct}
          unrealized={totals.unrealized}
          realizedYtd={totals.realizedYtd}
        />

        {/* ── Positions ── */}
        <PositionsTable
          positions={positions}
          totalMarketValue={totals.totalNav}
          onAction={openAction}
        />

        {/* ── Trades + Allocation ── */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <RecentTrades trades={trades} />
          </div>
          <div className="lg:col-span-2">
            <SectorAllocation
              positions={positions}
              totalMarketValue={totals.totalNav}
            />
          </div>
        </div>

        {/* ── Disclaimer ── */}
        <div className="pt-2">
          <DisclaimerBanner type="signal" />
          <p className="mt-2 text-[11px] italic text-slate-500">
            User-entered record only. Not investment advice.
          </p>
        </div>

        {/* ── Modals ── */}
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
      </div>
    </ErrorBoundary>
  );
}
