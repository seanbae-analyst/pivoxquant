"use client";

/**
 * /portfolio v2 — Gallery layout per SPEC.md §11 + MIGRATION.md §5.
 *
 * Source of truth: frontend/design-mockups/portfolio-v2/{SPEC.md, MIGRATION.md, mockup.html}.
 * Sole /portfolio surface — the ledger-binder variant was deleted 2026-08-30.
 *
 * Surface map (4-block structure):
 *   - LivingCFOStatusBar         (reused, sticky)
 *   - PortfolioHeroV2            (NAV + observed time + Add CTA)
 *   - EquityCurveBlock           (timeframe toggle 1mo/3mo/6mo/1yr/All)
 *   - PositionsTableV2           (8 columns, 종목명 main pattern)
 *   - 3-col grid:
 *       SectorDonutBlock | RecentTransactionsBlock
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
import { FxAttribution } from "@/components/ui/fx-attribution";
import { useAuth } from "@/lib/auth";
import { resolveMarketDataDisplay } from "@/lib/market-display";

import { LivingCFOStatusBar } from "@/components/dashboard/living-cfo-status";
import { WeeklyPulseCard } from "@/components/dashboard/weekly-pulse";
import { RollingWindowWidget } from "@/components/dashboard/rolling-window";

import {
  usePortfolioPositions,
  usePortfolioSummary,
  useFxRate,
  fetcher,
} from "@/lib/hooks";
import {
  PORTFOLIO_POSITIONS,
  PORTFOLIO_SUMMARY,
  PORTFOLIO_TRADES,
} from "@/lib/endpoints";

import { CapitalCardV2 } from "@/components/settings/v2/capital-card-v2";
import { PortfolioHeroV2 } from "@/components/portfolio/v2/portfolio-hero-v2";
import { EquityCurveBlock } from "@/components/portfolio/v2/equity-curve-block";
import { PositionsTableV2 } from "@/components/portfolio/v2/positions-table-v2";
import { SectorDonutBlock } from "@/components/portfolio/v2/sector-donut-block";
import { RecentTransactionsBlock } from "@/components/portfolio/v2/recent-transactions-block";
import { AddPositionModalV2 } from "@/components/portfolio/v2/add-position-modal-v2";
import { TradeModalV2 } from "@/components/portfolio/v2/trade-modal-v2";
import { ObservationNoteModalV2 } from "@/components/portfolio/v2/observation-note-modal-v2";

import {
  toPosition,
  type Position,
  type BackendPositionRow,
  type TradeAction,
} from "@/components/portfolio/types";

// FX_FALLBACK removed 2026-04-29 (was 1342, ~9% off live ~1478).
// Resolution: server fxRate → live /api/market/fx (useFxRate) → null.
// Never substitute a literal — 표시광고법 §3 기만표시 방어선.
const SAFE_FX = (sumFx: number | undefined, liveFx: number | null) =>
  sumFx && sumFx > 0 ? sumFx : liveFx && liveFx > 0 ? liveFx : null;

// FINDING-021: the SWR payload is the BACKEND snake_case shape — adapt it
// to the camelCase `Position` the portfolio UI consumes (see toPosition).
interface PositionsResponse {
  positions?: BackendPositionRow[];
  /** See lib/market-display.ts — `false` means every `current` in the rows
   *  above is null/absent and must not be rendered. */
  market_data_display?: boolean;
}

export default function PortfolioPageV2() {
  const [addOpen, setAddOpen] = React.useState(false);
  const [tradeAction, setTradeAction] = React.useState<TradeAction | null>(null);
  const [targetPosition, setTargetPosition] = React.useState<Position | null>(
    null,
  );
  // 관찰 노트 target is separate state from `targetPosition`: a note is not a
  // book mutation and must not share the trade modal's lifecycle.
  const [notePosition, setNotePosition] = React.useState<Position | null>(null);

  const {
    data: posData,
    isLoading: posLoading,
    error: posErr,
  } = usePortfolioPositions<PositionsResponse>();
  const {
    data: sumData,
    isLoading: sumLoading,
    error: sumErr,
  } = usePortfolioSummary();


  // Skeleton flicker guard — same 1.2s window as v1.
  const [showSkeleton, setShowSkeleton] = React.useState(true);
  React.useEffect(() => {
    const t = setTimeout(() => setShowSkeleton(false), 1200);
    return () => clearTimeout(t);
  }, []);

  // B-11 fix (2026-05-10): explicit empty-state flash guard.
  // SWR may flip `isLoading` to false before the response resolves
  // (stale cache / dedup), causing PortfolioHeroV2 to flash
  // "0 positions · $0 · never reconciled" for one frame before data
  // arrives. Treat the absence of either response object (i.e.
  // `data === undefined`) as still loading, regardless of the SWR
  // `isLoading` flag. The 1.2s `showSkeleton` window still bounds
  // the skeleton on the happy path.
  const dataPending = posData === undefined || sumData === undefined;
  const isInitialLoad =
    showSkeleton &&
    (dataPending || (posLoading && !posData) || (sumLoading && !sumData));

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

  // FINDING-021: map the raw backend rows to the camelCase `Position`
  // shape before any consumer touches `.current` / `.avgCost` / `.symbol`.
  const positions: Position[] = React.useMemo(
    () => (posData?.positions ?? []).map(toPosition),
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

  // Native-currency stock subtotals for the hero split (USD X · KRW Y).
  // Prefer the backend summary fields, but DERIVE from positions when the
  // backend hasn't supplied a positive value — so a KR holder always sees the
  // ₩ subtotal even if the summary's KR detection (ticker-suffix) misses a
  // position or the summary response is stale (CEO 2026-05-24: portfolio still
  // showed USD only). Grouped by the position `currency` field, the same key
  // get_portfolio uses for its totals.
  const { navUsdDerived, navKrwDerived } = React.useMemo(() => {
    let u = 0;
    let k = 0;
    for (const p of positions) {
      const mv = p.shares * p.current;
      if (!Number.isFinite(mv)) continue;
      if (p.currency === "KRW") k += mv;
      else u += mv;
    }
    return { navUsdDerived: u, navKrwDerived: k };
  }, [positions]);
  // ── Vendor market-data display gate ───────────────────────────────
  // Hidden when EITHER signal is off. The backend stamps
  // `market_data_display: false` on both payloads and nulls the price
  // fields; `toPosition` would coerce those nulls to 0 via `?? 0`, so a
  // frontend that trusted only its own flag could still print "USD 0".
  // Either response saying false is enough.
  const marketDataDisplay = resolveMarketDataDisplay(
    sumData?.market_data_display === false ||
      posData?.market_data_display === false
      ? false
      : undefined,
  );

  // Cost basis — the user's own record, no vendor feed. Split by native
  // currency exactly like the NAV split above, so the hero reads
  // "USD X · KRW Y" in both modes. The backend emits `costBasisUsd` /
  // `costBasisKrw`; deriving from the rows is the fallback for a deploy that
  // predates them (same prefer-server-then-derive shape as navUsdFinal).
  const { costUsdTotal, costKrwTotal } = React.useMemo(() => {
    let u = 0;
    let k = 0;
    for (const p of positions) {
      const c = p.shares * p.avgCost;
      if (!Number.isFinite(c) || c <= 0) continue;
      if (p.currency === "KRW") k += c;
      else u += c;
    }
    return {
      costUsdTotal:
        typeof sumData?.costBasisUsd === "number" && sumData.costBasisUsd > 0
          ? sumData.costBasisUsd
          : u,
      costKrwTotal:
        typeof sumData?.costBasisKrw === "number" && sumData.costBasisKrw > 0
          ? sumData.costBasisKrw
          : k,
    };
  }, [positions, sumData]);

  const navUsdFinal =
    typeof sumData?.navUsd === "number" && sumData.navUsd > 0
      ? sumData.navUsd
      : navUsdDerived;
  const navKrwFinal =
    typeof sumData?.navKrw === "number" && sumData.navKrw > 0
      ? sumData.navKrw
      : navKrwDerived;

  // Cash percent — backend P1 batch emits `cashPct` from
  // routes/portfolio.py::portfolio_summary_alias. Falls through to undefined
  // (em-dash) when the backend deploy predates the P1 batch.
  //
  // With the gate off that number is not available and would not mean the
  // same thing if it were: its denominator is a market valuation. The cash
  // share is still a real, useful ratio at cost — "how much of what I have
  // committed is still idle" — so it is recomputed here with the identical
  // shape the backend uses (cash / (cash + book)), swapping NAV for cost.
  // When a cross-currency book has no FX rate it is dropped rather than
  // reported from a partial sum.
  const { user } = useAuth();
  const cashPct: number | undefined = React.useMemo(() => {
    if (marketDataDisplay) return sumData?.cashPct;
    const capUsd = Number(user?.available_capital ?? 0) || 0;
    const capKrw = Number(user?.available_capital_krw ?? 0) || 0;
    const needsFx = capKrw > 0 || costKrwTotal > 0;
    if (needsFx && !(fxRate && fxRate > 0)) return undefined;
    const rate = fxRate && fxRate > 0 ? fxRate : 1;
    const cashUsd = capUsd + capKrw / rate;
    const bookUsd = costUsdTotal + costKrwTotal / rate;
    const equity = cashUsd + bookUsd;
    if (!(equity > 0)) return undefined;
    return Math.max(0, Math.min(100, (cashUsd / equity) * 100));
  }, [
    marketDataDisplay,
    sumData,
    user,
    fxRate,
    costUsdTotal,
    costKrwTotal,
  ]);
  const lastReconciledAt = sumData?.observed_at ?? null;

  function openAction(action: TradeAction, position: Position) {
    setTargetPosition(position);
    setTradeAction(action);
  }

  function closeTrade() {
    setTradeAction(null);
    setTargetPosition(null);
  }

  async function refreshAll() {
    // An add/edit/sell just changed the book. A bare mutate(key) can be
    // swallowed by the 10s dedupingInterval (PORTFOLIO_DEDUPE_MS) when a
    // background refreshInterval fetch fired moments earlier — leaving the
    // holdings table and hero count showing pre-mutation data until the next
    // poll (the "I added it but it's not there" wart). Fetch fresh data
    // ourselves and write it straight into the cache (revalidate:false) so the
    // update bypasses dedupe and lands immediately. On a network blip we fall
    // back to a plain revalidate (and the periodic refreshInterval is the
    // ultimate backstop) — never overwrite the cache with undefined.
    try {
      const [pos, sum] = await Promise.all([
        fetcher(PORTFOLIO_POSITIONS),
        fetcher(PORTFOLIO_SUMMARY),
      ]);
      mutate(PORTFOLIO_POSITIONS, pos, { revalidate: false });
      mutate(PORTFOLIO_SUMMARY, sum, { revalidate: false });
    } catch {
      mutate(PORTFOLIO_POSITIONS);
      mutate(PORTFOLIO_SUMMARY);
    }
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
      </div>

      {/* ═══════════ CFO STATUS — sticky hairline ═══════════
          Mobile fix (2026-05-05): top:0 was overlapping the 56px TopBar.
          Anchor below the TopBar so the sticky bar slides under the
          header rather than colliding with it.
          z-10 (2026-05-13 thorough-fix sweep): z-40 created a stacking
          context above the TopBar wrapper (z=20), clipping
          NotificationDropdown panel. */}
      <div
        className="sticky z-10 -mx-4 md:-ml-8 md:-mr-10 mb-2"
        style={{
          // Pin beneath the TopBar (56px) incl. notch safe-area on PWAs.
          // Token: --pq-aux-sticky-top (globals.css).
          top: "var(--pq-aux-sticky-top)",
          // FINDING-022: solid ink — semi-transparent bar bled scrolled content.
          background: "var(--pq-ink)",
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
            background: "rgba(184, 149, 106, 0.06)",
            borderTop: "1px solid var(--pq-bronze)",
            borderBottom: "1px solid var(--pq-bronze)",
            color: "var(--pq-bronze)",
            letterSpacing: "0.005em",
            fontSize: "var(--pq-text-body)",
          }}
        >
          <span>
            {/* "live" left with the flag: nothing on this page is live when
                the vendor-display gate is off, and the sentence is about the
                fetch failing either way. */}
            Unable to load your portfolio. No fallback values are shown.
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
              fontSize: "var(--pq-text-body)",
            }}
          >
            Refresh
          </button>
        </div>
      )}

      {/* ═══════════ HERO ═══════════
          bug-hunter Bug #3: first paint flashed every KPI as "—" because the
          loading gate required positions.length === 0 — but once SWR hands
          back any cached payload (even empty {}), `posLoading` flips false
          before `sumData` arrives, dropping us out of the skeleton path.
          Gate on either fetch being in-flight without data, while honoring
          the existing 1.2s flicker guard. */}
      <PortfolioHeroV2
        marketDataDisplay={marketDataDisplay}
        costUsd={costUsdTotal}
        costKrw={costKrwTotal}
        nav={totalNav}
        navCurrency={displayCurrency}
        navUsd={navUsdFinal}
        navKrw={navKrwFinal}
        positionCount={positions.length}
        cashPct={cashPct}
        lastReconciledAt={lastReconciledAt}
        onAddPosition={() => setAddOpen(true)}
        loading={isInitialLoad}
        todayPnl={kpis.todayPnl}
        todayPnlPct={kpis.todayPnlPct}
        unrealized={kpis.unrealized}
        realizedYtd={kpis.realizedYtd}
        todayPnlUsd={sumData?.todayPnlUsd}
        todayPnlKrw={sumData?.todayPnlKrw}
        unrealizedUsd={sumData?.unrealizedUsd}
        unrealizedKrw={sumData?.unrealizedKrw}
        realizedUsd={sumData?.realizedUsd}
        realizedKrw={sumData?.realizedKrw}
      />

      {/* ═══════════ EQUITY CURVE ═══════════
          Every number in this block is a vendor price: the NAV series is a
          daily close snapshot, the benchmark is an index close, and SPREAD is
          the difference of the two. With the gate off the whole block is
          unmounted — including its empty state, which promises "곡선은 매일
          종가 스냅샷으로 그려집니다" and would be selling a screen we do not
          have. Nothing replaces it: a placeholder explaining the absence
          would be the same promise in smaller type. */}
      {marketDataDisplay && (
        <EquityCurveBlock
          currency={displayCurrency}
          currentNav={totalNav}
          navUsd={navUsdFinal}
          navKrw={navKrwFinal}
          hasPositions={positions.length > 0}
          // `dataPending` outlives the 1.2s `showSkeleton` window on purpose:
          // while either response is missing we do not know the NAV, and an
          // em-dash is the honest rendering of that for as long as it lasts.
          loading={dataPending || isInitialLoad}
        />
      )}

      {/* ═══════════ POSITIONS TABLE ═══════════ */}
      <PositionsTableV2
        marketDataDisplay={marketDataDisplay}
        positions={positions}
        totalNav={totalNav}
        fxRate={fxRate}
        displayCurrency={displayCurrency}
        loading={posLoading}
        onAction={openAction}
        onObservationNote={setNotePosition}
        onAddPosition={() => setAddOpen(true)}
      />

      {/* ═══════════ SEED CAPITAL ═══════════
          Moved here from /settings on 2026-09-10. This is the number the
          cash buffer above and every add / trim draw down against, so it
          belongs next to the holdings it constrains, not among account
          settings. */}
      <section aria-label="Seed capital">
        <CapitalCardV2 />
      </section>

      {/* ═══════════ 3-COL GRID — Sector / Watchlist / Recent ═══════════ */}
      <section
        aria-label="Allocation, watchlist, and recent activity"
        style={{ marginBottom: 40 }}
      >
        <div
          className="pq-portfolio-v2-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
            gap: 16,
          }}
        >
          <SectorDonutBlock
            positions={positions}
            fxRate={fxRate}
            displayCurrency={displayCurrency}
            marketDataDisplay={marketDataDisplay}
          />
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

      {/* ═══════════ Foot signature ═══════════
          FxAttribution is required, not decorative: the USD/KRW rate this
          page converts with can come from open.er-api.com
          (services/fx_service.py), whose free terms require attribution on
          the page the rates are used with. /portfolio is the only screen
          with a `useFxRate()` consumer today. */}
      <div className="mt-6">
        <FxAttribution style={{ marginBottom: 14 }} />
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
      {/* 관찰 노트 — no onSuccess refresh: a note does not change the book,
          so there is nothing on this page to revalidate. */}
      <ObservationNoteModalV2
        key={notePosition?.id ?? "no-note"}
        open={notePosition !== null}
        symbol={notePosition?.symbol ?? null}
        name={notePosition?.name ?? null}
        onClose={() => setNotePosition(null)}
      />
    </ErrorBoundary>
  );
}
