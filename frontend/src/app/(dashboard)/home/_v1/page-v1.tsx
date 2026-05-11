"use client";

/**
 * /home — PivoxQuant Professional Terminal.
 *
 * Phase 1 rebuild (2026-04-24): the paper-dossier desk (ThisMorning /
 * Ledger / Signal stacks) has been retired in favour of a Bloomberg-style
 * terminal layout. Data hooks, legal scrub, KRW/USD split, and the
 * DisclaimerBanner remain intact — only the render layer changed.
 *
 * Layout:
 *   ┌── TopTicker (live) ──────────────────────────────────┐
 *   ├─ TodayMemoHero — CFO hero with Artifact CTA chips ─┤
 *   ├─ Today Brief │ Portfolio Snapshot │ Risk Gauges ──┤
 *   ├─ Positions table │ Watchlist table ──────────────┤
 *   ├─ Equity Curve 3mo │ Sector Allocation Donut ────┤
 *   ├─ Candlestick chart (top holding 1D + MA20/50 + Vol) ─┤
 *   ├─ Signals stream │ Pulse Activity ───────────────┤
 *   └─ Companion entry │ Feedback summary ──────────────┘
 *
 * Out-of-scope for Phase 1: /portfolio, /market, /signals, /risk,
 * /watchlist pages (not touched). /reports stays as Dossier.
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. DisclaimerBanner retained.
 */

import Link from "next/link";
import { useMemo } from "react";
import useSWR from "swr";

import { ErrorBoundary } from "@/components/ui/error-boundary";
import { FootSignature, Fleuron } from "@/components/ui/editorial";

import { TopTicker } from "@/components/terminal/top-ticker";
import { KpiCard } from "@/components/terminal/kpi-card";
import { DataTable, type Column } from "@/components/terminal/data-table";
import { CandlestickChart } from "@/components/terminal/candlestick-chart";

import { LivingCFOStatusBar } from "@/components/dashboard/living-cfo-status";
import { WeeklyPulseCard } from "@/components/dashboard/weekly-pulse";
import { UpsellPlus } from "@/components/dashboard/upsell-plus";
import { ArtifactQueue } from "@/components/home/artifact-queue";
import { TodayMemoHero } from "@/components/home/today-memo-hero";
// P0-1 perf fix (2026-05-10): recharts lazy-loaded via next/dynamic wrappers.
// Static imports pulled 391KB(raw)/112KB(gzip) into the home initial bundle.
import { EquityCurveChart } from "@/components/home/equity-curve-chart-dynamic";
import { SectorAllocationDonut } from "@/components/home/sector-allocation-donut-dynamic";

import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { API } from "@/lib/endpoints";
import { pctColor, PRICE_COLOR_HEX } from "@/lib/format";
import {
  usePortfolioSummary,
  usePortfolioPositions,
  useWatchlist,
} from "@/lib/hooks";
import type { Position } from "@/components/portfolio/types";

/* ── Response shapes ── */

interface SummaryResponse {
  totalNav?: number;
  todayPnl?: number;
  todayPnlPct?: number;
  unrealized?: number;
  positionCount?: number;
  observed_at?: string;
}
interface PositionsResponse {
  positions?: Position[];
}
interface WatchlistItem {
  id?: number | string;
  ticker?: string;
  symbol?: string;
  name?: string;
  last_price?: number;
  price?: number;
  change_pct?: number | null;
  market?: string;
}
interface WatchlistResponse {
  items?: WatchlistItem[];
  watchlist?: WatchlistItem[];
}
// Morning Brief types removed 2026-04-29 — backend Morning Brief deprecated.
interface SignalItem {
  id?: number | string;
  ticker?: string;
  symbol?: string;
  label?: string;
  strength?: number;
  observed_at?: string;
}
interface SignalsResponse {
  signals?: SignalItem[];
  items?: SignalItem[];
}
interface RiskSummaryResponse {
  // Backend (/api/risk/summary) snake_case PERCENT values
  var_1d_pct?: number;
  es_1d_pct?: number;
  max_dd_90d_pct?: number;
  corr_risk_index?: number;
  // Legacy fractional fields kept as fallbacks
  var_95?: number;
  var_99?: number;
  max_drawdown?: number;
  sharpe?: number;
  gauge?: {
    vix?: number;
    correlation?: number;
    concentration?: number;
  };
}

const fetcher = <T,>(url: string) => apiFetch<T>(url);

/* ── Table row shapes ── */

interface PosRow {
  id: string | number;
  ticker: string;
  name: string;
  shares: number;
  avgCost: number;
  current: number;
  pnlPct: number;
  marketValue: number;
  sector: string;
}

interface WatchRow {
  id: string | number;
  ticker: string;
  name: string;
  price: number | null;
  changePct: number | null;
  market: string;
}

interface SignalRow {
  id: string | number;
  ticker: string;
  label: string;
  strength: number;
  observedAt: string;
}

/* ── Utilities ── */

function fmtMoney(n: number | undefined, currency: "USD" | "KRW"): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  const dec = currency === "KRW" ? 0 : 2;
  const body = abs.toLocaleString(currency === "KRW" ? "ko-KR" : "en-US", {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
  return `${sign}${currency === "KRW" ? "\u20A9" : "$"}${body}`;
}

function fmtPct(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

/* ── Page ── */

export default function HomePageV1() {
  const { user } = useAuth();

  // BUG-8 FIX 4: portfolio summary/positions + watchlist now go through
  // the shared hooks in `lib/hooks.ts`, which enforce a 10 s dedupe +
  // revalidateIfStale:false. The old inline `liveOpts` (2 s dedupe)
  // produced separate cache entries from `usePortfolioSummary` used by
  // other components (RealtimeProvider, dashboard sidebars), multiplying
  // portfolio calls on mount.
  // Morning Brief SWR options retained for risk-summary call below.
  const briefOpts = {
    refreshInterval: 600_000,
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 60_000,
    errorRetryCount: 2,
    errorRetryInterval: 10_000,
  } as const;
  const signalsOpts = {
    refreshInterval: 30_000,
    // Bug #3 (HANDOVER v22): aligned with useSignals — focus revalidate
    // would compound load on home → signals nav.
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 10_000,
    errorRetryCount: 2,
    errorRetryInterval: 5_000,
  } as const;

  const { data: summary } = usePortfolioSummary() as {
    data: SummaryResponse | undefined;
  };
  const { data: posData } = usePortfolioPositions<PositionsResponse>();
  const { data: watch } = useWatchlist() as {
    data: WatchlistResponse | undefined;
  };
  // Morning Brief deprecated — placeholders kept so existing JSX remains safe.
  const brief: undefined = undefined;
  const briefLoading = false;
  const { data: signalsData } = useSWR<SignalsResponse>(
    API.signals.all,
    fetcher,
    signalsOpts,
  );
  const { data: riskSummary } = useSWR<RiskSummaryResponse>(
    "/api/risk/summary",
    fetcher,
    briefOpts,
  );

  const positions = useMemo(() => posData?.positions ?? [], [posData]);
  const positionCount = summary?.positionCount ?? positions.length;

  /* Top holding — drives the candlestick chart below. Sorted by market
     value (current price × shares) desc. Returns the company name as the
     primary identity (display) and the ticker as the secondary technical
     handle (chart fetch / link). Falls back to null when portfolio is
     empty → empty-state UI. */
  const topHolding = useMemo<{ ticker: string; name: string } | null>(() => {
    if (!positions || positions.length === 0) return null;
    const ranked = [...positions].sort((a, b) => {
      const av = (a.current ?? 0) * (a.shares ?? 0);
      const bv = (b.current ?? 0) * (b.shares ?? 0);
      return bv - av;
    });
    const top = ranked[0];
    if (!top?.symbol) return null;
    return { ticker: top.symbol, name: top.name || top.symbol };
  }, [positions]);
  const topTicker = topHolding?.ticker ?? null;

  const bookCurrency: "USD" | "KRW" =
    positions.length > 0 && positions.every((p) => p.currency === "KRW")
      ? "KRW"
      : "USD";

  // Morning Brief deprecated 2026-04-29 — hero copy now empty-state by default.
  void brief;
  const briefText: string | null = null;
  const heroHeadline: string | null = null;
  const heroBody: string | null = null;

  const displayName = user?.name?.split(" ")[0] || "Observer";

  /* Positions table rows */
  const posRows: PosRow[] = useMemo(() => {
    return positions.map((p) => {
      const cur = p.current ?? 0;
      const avg = p.avgCost ?? 0;
      const pnl = avg > 0 ? ((cur - avg) / avg) * 100 : 0;
      return {
        id: p.id,
        ticker: p.symbol,
        name: p.name,
        shares: p.shares,
        avgCost: avg,
        current: cur,
        pnlPct: pnl,
        marketValue: cur * p.shares,
        sector: p.sector,
      };
    });
  }, [positions]);

  const posColumns: Column<PosRow>[] = useMemo(
    () => [
      {
        key: "name",
        header: "Name",
        sortAccessor: (r) => r.name || r.ticker,
        render: (r) => (
          <Link
            href={`/detail/${encodeURIComponent(r.ticker)}`}
            className="block pq-ticker-link"
            style={{ textDecoration: "none" }}
          >
            <div
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-body)",
                lineHeight: 1.2,
                color: "var(--pq-ivory)",
                maxWidth: 220,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {r.name || r.ticker}
            </div>
            <div
              className="font-mono"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                marginTop: 2,
                color: "rgba(245,240,232,0.45)",
                letterSpacing: "0.06em",
              }}
            >
              {r.ticker}
            </div>
          </Link>
        ),
      },
      {
        key: "shares",
        header: "Shares",
        align: "right",
        render: (r) => r.shares.toLocaleString("en-US"),
      },
      {
        key: "avgCost",
        header: "Avg Cost",
        align: "right",
        render: (r) => fmtMoney(r.avgCost, bookCurrency),
      },
      {
        key: "current",
        header: "Last",
        align: "right",
        render: (r) => fmtMoney(r.current, bookCurrency),
      },
      {
        key: "pnlPct",
        header: "P/L %",
        align: "right",
        render: (r) => (
          <span style={{ color: pctColor(r.pnlPct) }}>{fmtPct(r.pnlPct)}</span>
        ),
      },
      {
        key: "marketValue",
        header: "Mkt Value",
        align: "right",
        render: (r) => fmtMoney(r.marketValue, bookCurrency),
      },
    ],
    [bookCurrency],
  );

  /* Watchlist table rows */
  const watchRows: WatchRow[] = useMemo(() => {
    const watchItems = watch?.items ?? watch?.watchlist ?? [];
    return watchItems.map((w, i) => {
      const ticker = w.ticker || w.symbol || `W-${i}`;
      return {
        id: w.id ?? ticker,
        ticker,
        name: w.name ?? "",
        price: w.last_price ?? w.price ?? null,
        changePct: w.change_pct ?? null,
        market: w.market ?? "",
      };
    });
  }, [watch?.items, watch?.watchlist]);

  const watchColumns: Column<WatchRow>[] = useMemo(
    () => [
      {
        key: "name",
        header: "Name",
        sortAccessor: (r) => r.name || r.ticker,
        render: (r) => (
          <Link
            href={`/detail/${encodeURIComponent(r.ticker)}`}
            className="block pq-ticker-link"
            style={{ textDecoration: "none" }}
          >
            <div
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-body)",
                lineHeight: 1.2,
                color: "var(--pq-ivory)",
                maxWidth: 220,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {r.name || r.ticker}
            </div>
            <div
              className="font-mono"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                marginTop: 2,
                color: "rgba(245,240,232,0.45)",
                letterSpacing: "0.06em",
              }}
            >
              {r.ticker}
            </div>
          </Link>
        ),
      },
      {
        key: "price",
        header: "Last",
        align: "right",
        render: (r) =>
          r.price == null
            ? "—"
            : fmtMoney(r.price, r.market === "KR" ? "KRW" : "USD"),
      },
      {
        key: "changePct",
        header: "Δ%",
        align: "right",
        render: (r) => (
          <span style={{ color: pctColor(r.changePct) }}>
            {fmtPct(r.changePct)}
          </span>
        ),
      },
      {
        key: "market",
        header: "Mkt",
        width: "56px",
        render: (r) => (
          <span
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.18em",
              color: "rgba(245,240,232,0.45)",
            }}
          >
            {r.market || "—"}
          </span>
        ),
      },
    ],
    [],
  );

  /* Signals rows */
  const signalRows: SignalRow[] = useMemo(() => {
    const signalsItems = signalsData?.signals ?? signalsData?.items ?? [];
    return signalsItems.slice(0, 12).map((s, i) => ({
      id: s.id ?? `${s.ticker || i}`,
      ticker: s.ticker || s.symbol || "—",
      label: s.label || "NEUTRAL",
      strength: s.strength ?? 0,
      observedAt: s.observed_at ?? "",
    }));
  }, [signalsData?.signals, signalsData?.items]);

  const signalColumns: Column<SignalRow>[] = useMemo(
    () => [
      {
        key: "ticker",
        header: "Symbol",
        width: "112px",
        render: (r) => (
          <Link
            href={`/detail/${encodeURIComponent(r.ticker)}`}
            className="block pq-ticker-link"
            style={{ textDecoration: "none" }}
          >
            <div
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-body)",
                lineHeight: 1.2,
                color: "var(--pq-ivory)",
                letterSpacing: "0.02em",
              }}
            >
              {r.ticker}
            </div>
          </Link>
        ),
      },
      {
        key: "label",
        header: "Signal",
        render: (r) => {
          // KR convention: POSITIVE → red, NEGATIVE → blue (single source: lib/format.ts).
          const color =
            r.label === "POSITIVE"
              ? PRICE_COLOR_HEX.up
              : r.label === "NEGATIVE"
                ? PRICE_COLOR_HEX.down
                : PRICE_COLOR_HEX.flat;
          return (
            <span
              className="font-mono uppercase"
              style={{
                color,
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.2em",
              }}
            >
              {r.label}
            </span>
          );
        },
      },
      {
        key: "strength",
        header: "Strength",
        align: "right",
        render: (r) => r.strength.toFixed(2),
      },
      {
        key: "observedAt",
        header: "Observed",
        align: "right",
        render: (r) =>
          r.observedAt
            ? new Date(r.observedAt).toLocaleTimeString("en-GB", {
                hour: "2-digit",
                minute: "2-digit",
              })
            : "—",
      },
    ],
    [],
  );

  /* Pulse activity — last 5 positions sorted by |pnlPct| */
  const pulseRows = useMemo(() => {
    return [...posRows]
      .sort((a, b) => Math.abs(b.pnlPct) - Math.abs(a.pnlPct))
      .slice(0, 5);
  }, [posRows]);

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
          Mobile fix (2026-05-05): top:0 was overlapping the 56px TopBar
          when scrolled. Anchor below the TopBar so the sticky bar slides
          under the header rather than colliding with it. */}
      <div
        className="sticky z-40 -mx-4 md:-ml-8 md:-mr-10 mb-4"
        style={{
          top: 56,
          background: "rgba(10,10,10,0.78)",
          backdropFilter: "blur(6px)",
          WebkitBackdropFilter: "blur(6px)",
        }}
      >
        <LivingCFOStatusBar />
      </div>

      {/* ═══════════ CFO HERO — Today's memo + Artifact CTAs ═══════════ */}
      <TodayMemoHero
        headline={heroHeadline}
        body={heroBody}
        loading={briefLoading && heroHeadline == null}
        displayName={displayName}
      />

      {/* ═══════════ Row 1 — Today Brief │ Snapshot │ Risk Gauges ═══════════
          Mobile fix (2026-05-05): collapse 3-col to 1-col below md.
          At 375px, three minmax(0, 1fr) columns produced ~115px each and
          made all three cards illegible. */}
      <section
        className="grid gap-3 mb-3 grid-cols-1 md:[grid-template-columns:minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1fr)]"
      >
        {/* Today Brief card — editorial summary */}
        <div
          style={{
            background: "var(--pq-card-bg-ink)",
            border: "1px solid var(--pq-hairline-ink)",
            padding: "14px 16px",
            display: "flex",
            flexDirection: "column",
            gap: 8,
            minHeight: 140,
          }}
        >
          <div className="flex items-center justify-between">
            <span
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.24em",
                color: "var(--pq-bronze)",
              }}
            >
              Today Brief · {displayName}
            </span>
            <Link
              href="/reports"
              className="font-mono uppercase"
              style={{
                fontSize: 9,
                letterSpacing: "0.2em",
                color: "rgba(245,240,232,0.4)",
              }}
            >
              Archive ›
            </Link>
          </div>
          <p
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-body)",
              lineHeight: 1.6,
              color: "rgba(245,240,232,0.82)",
              margin: 0,
            }}
          >
            {briefText
              ? briefText
              : "No brief observed for this session. The weekly memo lands every Monday 07:00 KST and will archive here."}
          </p>
        </div>

        {/* Portfolio Snapshot — 3 KPIs in one block */}
        <div
          style={{
            display: "grid",
            gridTemplateRows: "1fr 1fr",
            gap: 8,
          }}
        >
          <KpiCard
            label="Total NAV"
            value={summary?.totalNav}
            format="currency"
            currency={bookCurrency}
            delta={summary?.todayPnlPct}
            deltaFormat="percent"
            size="sm"
          />
          <div className="grid grid-cols-2 gap-2">
            <KpiCard
              label="Today P/L"
              value={summary?.todayPnl}
              format="currency"
              currency={bookCurrency}
              delta={summary?.todayPnlPct}
              deltaFormat="percent"
              size="sm"
            />
            <KpiCard
              label="Positions"
              value={positionCount}
              format="plain"
              size="sm"
              suffix="open"
            />
          </div>
        </div>

        {/* Risk Gauges */}
        <div
          style={{
            display: "grid",
            gridTemplateRows: "1fr 1fr",
            gap: 8,
          }}
        >
          <div className="grid grid-cols-2 gap-2">
            <KpiCard
              label="VaR 95"
              value={(() => {
                // Backend canonical: var_1d_pct (PERCENT). Legacy: var_95 (fraction).
                // KpiCard format="percent" expects a fraction (0..1) and renders ×100.
                const raw = riskSummary?.var_1d_pct ?? riskSummary?.var_95;
                if (raw == null || !Number.isFinite(raw)) return undefined;
                const frac = Math.abs(raw) <= 1 ? raw : raw / 100;
                return Math.abs(frac);
              })()}
              format="percent"
              size="sm"
            />
            <KpiCard
              label="Sharpe"
              value={riskSummary?.sharpe}
              format="plain"
              size="sm"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <KpiCard
              label="Max DD"
              value={
                riskSummary?.max_drawdown != null
                  ? Math.abs(riskSummary.max_drawdown)
                  : undefined
              }
              format="percent"
              size="sm"
            />
            <KpiCard
              label="VIX"
              value={riskSummary?.gauge?.vix}
              format="plain"
              size="sm"
            />
          </div>
        </div>
      </section>

      {/* ═══════════ Row 2 — Positions │ Watchlist ═══════════ */}
      <section
        className="grid gap-3 mb-3 grid-cols-1 md:[grid-template-columns:minmax(0,1.4fr)_minmax(0,1fr)]"
      >
        <div>
          <div
            className="flex items-center justify-between mb-1"
            style={{ padding: "0 2px" }}
          >
            <span
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.24em",
                color: "var(--pq-bronze)",
              }}
            >
              Positions
            </span>
            <Link
              href="/portfolio"
              className="font-mono uppercase"
              style={{
                fontSize: 9,
                letterSpacing: "0.2em",
                color: "rgba(245,240,232,0.4)",
              }}
            >
              Open Book ›
            </Link>
          </div>
          <DataTable<PosRow>
            columns={posColumns}
            rows={posRows}
            label="Positions"
            initialSort={{ key: "marketValue", dir: "desc" }}
            emptyState="No positions recorded."
          />
        </div>

        <div>
          <div
            className="flex items-center justify-between mb-1"
            style={{ padding: "0 2px" }}
          >
            <span
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.24em",
                color: "var(--pq-bronze)",
              }}
            >
              Watchlist
            </span>
            <Link
              href="/watchlist"
              className="font-mono uppercase"
              style={{
                fontSize: 9,
                letterSpacing: "0.2em",
                color: "rgba(245,240,232,0.4)",
              }}
            >
              Manage ›
            </Link>
          </div>
          <DataTable<WatchRow>
            columns={watchColumns}
            rows={watchRows}
            label="Watchlist"
            emptyState="Watchlist empty — add symbols from /watchlist."
          />
        </div>
      </section>

      {/* ═══════════ Row 2.5 — Equity Curve │ Sector Allocation ═══════════ */}
      <section
        className="grid gap-3 mb-3 grid-cols-1 md:[grid-template-columns:minmax(0,1.4fr)_minmax(0,1fr)]"
      >
        <div>
          <div
            className="flex items-center justify-between mb-1"
            style={{ padding: "0 2px" }}
          >
            <span
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.24em",
                color: "var(--pq-bronze)",
              }}
            >
              Equity Curve · 3mo
            </span>
            <Link
              href="/portfolio"
              className="font-mono uppercase"
              style={{
                fontSize: 9,
                letterSpacing: "0.2em",
                color: "rgba(245,240,232,0.4)",
              }}
            >
              Open Book ›
            </Link>
          </div>
          <EquityCurveChart currency={bookCurrency} height={240} />
        </div>

        <div>
          <div
            className="flex items-center justify-between mb-1"
            style={{ padding: "0 2px" }}
          >
            <span
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.24em",
                color: "var(--pq-bronze)",
              }}
            >
              Sector Allocation
            </span>
            <span
              className="font-mono uppercase"
              style={{
                fontSize: 9,
                letterSpacing: "0.2em",
                color: "rgba(245,240,232,0.4)",
              }}
            >
              {positions.length}{" "}
              {positions.length === 1 ? "position" : "positions"}
            </span>
          </div>
          <SectorAllocationDonut
            positions={positions}
            currency={bookCurrency}
            height={240}
          />
        </div>
      </section>

      {/* ═══════════ Row 3 — Top Holding Chart (full width) ═══════════ */}
      <section className="mb-3">
        <div
          className="flex items-center justify-between mb-1"
          style={{ padding: "0 2px" }}
        >
          <div style={{ minWidth: 0 }}>
            {/* Eyebrow — section label only (mono uppercase remains the
                design signature for eyebrows; numbers/codes excluded). */}
            <div
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.24em",
                color: "var(--pq-bronze)",
              }}
            >
              Top Holding
            </div>
            {/* Name first, ticker as a small bronze handle. CEO directive
                2026-04-26: "ticker 번호 두면 어케 아냐 종목 이름을 둬야지" — so
                the company name leads, and the ticker code is demoted to a
                secondary technical handle next to it. */}
            {topHolding ? (
              <h2
                className="font-serif"
                style={{
                  fontSize: 20,
                  lineHeight: 1.2,
                  color: "var(--pq-ivory)",
                  margin: "4px 0 0 0",
                  fontWeight: 500,
                  letterSpacing: "-0.005em",
                }}
              >
                {topHolding.name}
                <span
                  className="font-mono"
                  style={{
                    marginLeft: 10,
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.06em",
                    color: "rgba(245,240,232,0.45)",
                    fontWeight: 400,
                  }}
                >
                  {topHolding.ticker}
                </span>
              </h2>
            ) : null}
            <p
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                lineHeight: 1.5,
                color: "rgba(245,240,232,0.55)",
                margin: "4px 0 0 0",
              }}
            >
              Daily closing price with 20- and 50-day moving averages.
            </p>
          </div>
          {topTicker ? (
            <Link
              href={`/detail/${encodeURIComponent(topTicker)}`}
              className="font-mono uppercase"
              style={{
                fontSize: 9,
                letterSpacing: "0.2em",
                color: "rgba(245,240,232,0.4)",
              }}
            >
              Full View ›
            </Link>
          ) : null}
        </div>
        {topTicker ? (
          <CandlestickChart
            ticker={topTicker}
            timeframe="1D"
            indicators={["ma20", "ma50", "volume"]}
            height={320}
            showKpiChips
          />
        ) : (
          <div className="pq-ink-empty">
            <Fleuron size={13} />
            <p
              className="font-serif"
              style={{ marginTop: 12, fontStyle: "italic", fontSize: "var(--pq-text-body)" }}
            >
              Add your first position to see your top holding chart.
            </p>
            <div style={{ marginTop: 16 }}>
              <Link href="/portfolio" className="pq-ink-btn-bronze">
                Open Portfolio
              </Link>
            </div>
          </div>
        )}
      </section>

      {/* ═══════════ Row 4 — Signals │ Pulse Activity ═══════════ */}
      <section
        className="grid gap-3 mb-3 grid-cols-1 md:grid-cols-2"
      >
        <div>
          <div
            className="flex items-center justify-between mb-1"
            style={{ padding: "0 2px" }}
          >
            <span
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.24em",
                color: "var(--pq-bronze)",
              }}
            >
              Signals Stream
            </span>
            <Link
              href="/signals"
              className="font-mono uppercase"
              style={{
                fontSize: 9,
                letterSpacing: "0.2em",
                color: "rgba(245,240,232,0.4)",
              }}
            >
              All Signals ›
            </Link>
          </div>
          <DataTable<SignalRow>
            columns={signalColumns}
            rows={signalRows}
            label="Signals"
            emptyState="No signals observed."
          />
        </div>

        <div>
          <div
            className="flex items-center justify-between mb-1"
            style={{ padding: "0 2px" }}
          >
            <span
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.24em",
                color: "var(--pq-bronze)",
              }}
            >
              Pulse Activity
            </span>
            <span
              className="font-mono uppercase"
              style={{
                fontSize: 9,
                letterSpacing: "0.2em",
                color: "rgba(245,240,232,0.4)",
              }}
            >
              Top 5 moves
            </span>
          </div>
          <DataTable<PosRow>
            columns={[
              posColumns[0], // name + ticker (combined)
              posColumns[3], // current
              posColumns[4], // pnl%
              posColumns[5], // mkt value
            ]}
            rows={pulseRows}
            label="Pulse Activity"
            emptyState="Open positions to see pulse activity."
          />
        </div>
      </section>

      {/* ═══════════ Row 5 — Companion entry │ Feedback ═══════════ */}
      <section className="grid gap-3 mb-5 grid-cols-1 md:grid-cols-2">
        {/* Companion entry */}
        <Link
          href="/companion"
          style={{
            background: "var(--pq-card-bg-ink)",
            border: "1px solid var(--pq-hairline-ink)",
            padding: "16px 18px",
            display: "flex",
            flexDirection: "column",
            gap: 8,
            textDecoration: "none",
            minHeight: 110,
            transition: "border-color 0.2s ease",
          }}
          className="hover:border-[color:var(--pq-bronze)]"
        >
          <span
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.24em",
              color: "var(--pq-bronze)",
            }}
          >
            Companion · Personal Journal
          </span>
          <p
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-body)",
              lineHeight: 1.6,
              color: "rgba(245,240,232,0.75)",
              margin: 0,
            }}
          >
            A reflective agent that remembers your trades and asks the questions
            you keep forgetting. Premium Plus beta.
          </p>
          <span
            className="font-mono uppercase ml-auto"
            style={{
              fontSize: 9,
              letterSpacing: "0.2em",
              color: "rgba(245,240,232,0.4)",
              marginTop: "auto",
            }}
          >
            Open Companion ›
          </span>
        </Link>

        {/* Artifacts + Feedback summary */}
        <div>
          <ArtifactQueue />
        </div>
      </section>

      {/* ═══════════ Premium Plus upsell (conditional) ═══════════ */}
      <div className="mt-4">
        <UpsellPlus />
      </div>

      {/* ═══════════ Foot signature ═══════════ */}
      {/* Legal disclaimer is mounted once by (dashboard)/layout.tsx as a
          path-aware footer — do not re-mount here. */}
      <div className="mt-6">
        <FootSignature />
      </div>

      {/* Weekly Pulse — auto-triggers Monday 07:00 KST */}
      <WeeklyPulseCard />
    </ErrorBoundary>
  );
}
