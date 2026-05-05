"use client";

/**
 * /portfolio v2 — Gallery layout per SPEC.md §11 + MIGRATION.md §5.
 *
 * Source of truth: frontend/design-mockups/portfolio-v2/{SPEC.md, MIGRATION.md, mockup.html}.
 * Toggle: NEXT_PUBLIC_PORTFOLIO_V2=true. Default off; v1 (ledger binder) remains live.
 *
 * Surface map (4-block structure):
 *   - TopTicker                  (reused, full-bleed)
 *   - LivingCFOStatusBar         (reused, sticky)
 *   - PortfolioHeroV2            (NAV + reconciled time + Add / Reconcile CTAs)
 *   - EquityCurveBlock           (timeframe toggle 1mo/3mo/6mo/1yr/All)
 *   - PositionsTableV2           (8 columns, 종목명 main pattern)
 *   - 3-col grid:
 *       SectorDonutBlock | WatchlistMini | RecentTransactionsBlock
 *   - WeeklyPulseCard            (reused, invisible Mon 07:00 trigger)
 *   - FootSignature              (reused)
 *
 * Modals:
 *   - AddPositionModalV2         (state-controlled)
 *   - TradeModalV2               (state-controlled, selected position)
 *
 * Legal: action vocabulary `Add` / `Trim` / `Close` / `Edit` / `Save observation`.
 * Never the banned trade verbs. POSITIVE/NEGATIVE/NEUTRAL where applicable.
 * DisclaimerBanner mounted by (dashboard)/layout.tsx — NOT here.
 */

import * as React from "react";
import { mutate } from "swr";
import { toast } from "sonner";

import { ErrorBoundary } from "@/components/ui/error-boundary";
import { FootSignature } from "@/components/ui/editorial";

import { TopTicker } from "@/components/terminal/top-ticker";
import { LivingCFOStatusBar } from "@/components/dashboard/living-cfo-status";
import { WeeklyPulseCard } from "@/components/dashboard/weekly-pulse";
import { RollingWindowWidget } from "@/components/dashboard/rolling-window";

import {
  usePortfolioPositions,
  usePortfolioSummary,
  useFxRate,
} from "@/lib/hooks";
import {
  PORTFOLIO_POSITIONS,
  PORTFOLIO_SUMMARY,
  PORTFOLIO_TRADES,
} from "@/lib/endpoints";

import { PortfolioHeroV2 } from "@/components/portfolio/v2/portfolio-hero-v2";
import { EquityCurveBlock } from "@/components/portfolio/v2/equity-curve-block";
import { PositionsTableV2 } from "@/components/portfolio/v2/positions-table-v2";
import { SectorDonutBlock } from "@/components/portfolio/v2/sector-donut-block";
import { WatchlistMini } from "@/components/portfolio/v2/watchlist-mini";
import { RecentTransactionsBlock } from "@/components/portfolio/v2/recent-transactions-block";
import { AddPositionModalV2 } from "@/components/portfolio/v2/add-position-modal-v2";
import { TradeModalV2 } from "@/components/portfolio/v2/trade-modal-v2";

import type { Position, TradeAction } from "@/components/portfolio/types";

// FX_FALLBACK removed 2026-04-29 (was 1342, ~9% off live ~1478).
// Resolution: server fxRate → live /api/market/fx (useFxRate) → null.
// Never substitute a literal — 표시광고법 §3 기만표시 방어선.
const SAFE_FX = (sumFx: number | undefined, liveFx: number | null) =>
  sumFx && sumFx > 0 ? sumFx : liveFx && liveFx > 0 ? liveFx : null;

interface PositionsResponse {
  positions?: Position[];
}

export default function PortfolioPageV2() {
  const [addOpen, setAddOpen] = React.useState(false);
  const [tradeAction, setTradeAction] = React.useState<TradeAction | null>(null);
  const [targetPosition, setTargetPosition] = React.useState<Position | null>(
    null,
  );

  const {
    data: posData,
    isLoading: posLoading,
    error: posErr,
  } = usePortfolioPositions<PositionsResponse>();
  const { data: sumData, error: sumErr } = usePortfolioSummary();

  // Skeleton flicker guard — same 1.2s window as v1.
  const [showSkeleton, setShowSkeleton] = React.useState(true);
  React.useEffect(() => {
    const t = setTimeout(() => setShowSkeleton(false), 1200);
    return () => clearTimeout(t);
  }, []);

  // Toast on error — surfaces transient API failures (v1 parity).
  React.useEffect(() => {
    if (posErr) {
      const msg = posErr instanceof Error ? posErr.message : "Something went wrong";
      toast.error(`Positions: ${msg}`);
    }
  }, [posErr]);
  React.useEffect(() => {
    if (sumErr) {
      const msg = sumErr instanceof Error ? sumErr.message : "Something went wrong";
      toast.error(`Summary: ${msg}`);
    }
  }, [sumErr]);

  const hasLoadError = Boolean(posErr || sumErr);

  const positions: Position[] = React.useMemo(
    () => posData?.positions ?? [],
    [posData],
  );

  // Display currency — KRW only when book is exclusively KRW positions.
  const displayCurrency: "USD" | "KRW" = React.useMemo(() => {
    const hasKrw = positions.some((p) => p.currency === "KRW");
    const hasUsd = positions.some(
      (p) => p.currency === "USD" || p.currency === undefined,
    );
    return hasKrw && !hasUsd ? "KRW" : "USD";
  }, [positions]);

  // Live USD/KRW from /api/market/fx (60s poll). Used when sumData.fxRate
  // is missing — never substitute a hard-coded literal.
  const { rate: liveFx } = useFxRate();
  const fxRate: number | null = SAFE_FX(sumData?.fxRate, liveFx);

  // Total NAV in display currency.
  const totalNav = React.useMemo(() => {
    if (typeof sumData?.totalNav === "number" && sumData.totalNav > 0) {
      return sumData.totalNav;
    }
    let nav = 0;
    for (const p of positions) {
      const mv = p.shares * p.current;
      const needsConversion =
        (displayCurrency === "USD" && p.currency === "KRW") ||
        (displayCurrency === "KRW" && p.currency !== "KRW");
      if (needsConversion) {
        // Skip the position rather than apply a fake fx — keeps the NAV
        // number honest when the FX feed is down.
        if (!fxRate || fxRate <= 0) continue;
        if (displayCurrency === "USD" && p.currency === "KRW") {
          nav += mv / fxRate;
        } else {
          nav += mv * fxRate;
        }
      } else {
        nav += mv;
      }
    }
    return nav;
  }, [sumData, positions, displayCurrency, fxRate]);

  // Cash percent — backend doesn't currently emit; placeholder em-dash.
  const cashPct: number | undefined = undefined;
  const lastReconciledAt = sumData?.observed_at ?? null;

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
    mutate(
      (key) => typeof key === "string" && key.startsWith(PORTFOLIO_TRADES),
      undefined,
      { revalidate: true },
    );
  }

  // KPI deck values — preserved from v1 PortfolioPage (line 144-164).
  // Falls through to derived figures from positions when summary is silent.
  const kpis = React.useMemo(() => {
    let mv = 0;
    let cost = 0;
    for (const p of positions) {
      mv += p.shares * p.current;
      cost += p.shares * p.avgCost;
    }
    const derivedUnrealized = mv - cost;
    return {
      todayPnl: sumData?.todayPnl,
      todayPnlPct: sumData?.todayPnlPct,
      unrealized: sumData?.unrealized ?? derivedUnrealized,
      realizedYtd: sumData?.realizedYtd,
    };
  }, [sumData, positions]);

  return (
    <ErrorBoundary>
      {/* ═══════════ TOP TICKER — live strip (full bleed) ═══════════ */}
      <div
        className="-mx-4 md:-ml-10 md:-mr-10 mb-4"
        style={{ maxWidth: "100vw" }}
      >
        <TopTicker />
      </div>

      {/* ═══════════ LIVING CFO STATUS — sticky hairline ═══════════
          Mobile fix (2026-05-05): top:0 was overlapping the 56px TopBar.
          Anchor below the TopBar so the sticky bar slides under the
          header rather than colliding with it. */}
      <div
        className="sticky z-40 -mx-4 md:-ml-8 md:-mr-10 mb-2"
        style={{
          top: 56,
          background: "rgba(5,5,5,0.78)",
          backdropFilter: "blur(6px)",
          WebkitBackdropFilter: "blur(6px)",
        }}
      >
        <LivingCFOStatusBar />
      </div>

      {/* ═══════════ ERROR BANNER (v1 parity) ═══════════ */}
      {hasLoadError && (
        <div
          role="alert"
          className="font-serif"
          style={{
            margin: "0 0 16px 0",
            padding: "12px 18px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            background: "rgba(226, 185, 111, 0.06)",
            borderTop: "1px solid var(--pq-bronze)",
            borderBottom: "1px solid var(--pq-bronze)",
            color: "var(--pq-bronze)",
            letterSpacing: "0.005em",
            fontSize: 12.5,
          }}
        >
          <span>
            Unable to load live portfolio data. No fallback values are shown.
          </span>
          <button
            type="button"
            onClick={refreshAll}
            className="font-serif"
            style={{
              background: "transparent",
              border: "none",
              color: "var(--pq-bronze)",
              textDecoration: "underline",
              textUnderlineOffset: 4,
              cursor: "pointer",
              fontSize: 12.5,
            }}
          >
            Refresh
          </button>
        </div>
      )}

      {/* ═══════════ HERO ═══════════ */}
      <PortfolioHeroV2
        nav={totalNav}
        navCurrency={displayCurrency}
        positionCount={positions.length}
        cashPct={cashPct}
        lastReconciledAt={lastReconciledAt}
        reconcileAvailable={false}
        onAddPosition={() => setAddOpen(true)}
        loading={(posLoading && showSkeleton) && positions.length === 0}
        todayPnl={kpis.todayPnl}
        todayPnlPct={kpis.todayPnlPct}
        unrealized={kpis.unrealized}
        realizedYtd={kpis.realizedYtd}
      />

      {/* ═══════════ EQUITY CURVE ═══════════ */}
      <EquityCurveBlock currency={displayCurrency} currentNav={totalNav} />

      {/* ═══════════ POSITIONS TABLE ═══════════ */}
      <PositionsTableV2
        positions={positions}
        totalNav={totalNav}
        fxRate={fxRate}
        displayCurrency={displayCurrency}
        loading={posLoading}
        onAction={openAction}
        onAddPosition={() => setAddOpen(true)}
      />

      {/* ═══════════ 3-COL GRID — Sector / Watchlist / Recent ═══════════ */}
      <section
        aria-label="Allocation, watchlist, and recent activity"
        style={{ marginBottom: 40 }}
      >
        <div
          className="pq-portfolio-v2-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
            gap: 16,
          }}
        >
          <SectorDonutBlock
            positions={positions}
            fxRate={fxRate}
            displayCurrency={displayCurrency}
          />
          <WatchlistMini limit={6} />
          <RecentTransactionsBlock limit={6} />
        </div>

        <style jsx>{`
          @media (max-width: 1023px) {
            :global(.pq-portfolio-v2-grid) {
              grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            }
          }
          @media (max-width: 767px) {
            :global(.pq-portfolio-v2-grid) {
              grid-template-columns: 1fr !important;
            }
          }
        `}</style>
      </section>

      {/* ═══════════ ROLLING WINDOW (Block 5) — v1 parity (Layer 2 learning) ═══════════ */}
      {/* paper={false}: v2 페이지는 Vantablack v3 톤. ivory paper bg 는 v1 (paper desk)
          전용. CEO 직접 지적 2026-04-29: "declared vs observed 부분 왜 얘만 노래" */}
      <section
        aria-label="Rolling window behavioural analysis"
        style={{ marginBottom: 40 }}
      >
        <RollingWindowWidget paper={false} />
      </section>

      {/* ═══════════ Foot signature ═══════════ */}
      <div className="mt-6">
        <FootSignature note="PivoxQuant · User-entered record · Not investment advice" />
      </div>

      {/* Weekly Pulse — auto-triggers Monday 07:00 KST (invisible) */}
      <WeeklyPulseCard />

      {/* ═══════════ MODALS ═══════════ */}
      <AddPositionModalV2
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onSuccess={refreshAll}
      />
      <TradeModalV2
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
