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
 *   ├─ Equity Curve 90d │ Sector Allocation Donut ────┤
 *   ├─ Candlestick chart (NVDA 1D + MA20/50 + Volume) ─┤
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

import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { FootSignature } from "@/components/ui/editorial";

import { TopTicker } from "@/components/terminal/top-ticker";
import { KpiCard } from "@/components/terminal/kpi-card";
import { DataTable, type Column } from "@/components/terminal/data-table";
import { CandlestickChart } from "@/components/terminal/candlestick-chart";

import { LivingCFOStatusBar } from "@/components/dashboard/living-cfo-status";
import { WeeklyPulseCard } from "@/components/dashboard/weekly-pulse";
import { UpsellPlus } from "@/components/dashboard/upsell-plus";
import { ArtifactQueue } from "@/components/home/artifact-queue";
import { TodayMemoHero } from "@/components/home/today-memo-hero";
import { EquityCurveChart } from "@/components/home/equity-curve-chart";
import { SectorAllocationDonut } from "@/components/home/sector-allocation-donut";

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
interface MorningBriefBody {
  insight?: string;
  summary?: string;
}
interface MorningBriefResponse {
  available?: boolean;
  brief?: MorningBriefBody;
}
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

export default function HomePage() {
  const { user } = useAuth();

  // BUG-8 FIX 4: portfolio summary/positions + watchlist now go through
  // the shared hooks in `lib/hooks.ts`, which enforce a 10 s dedupe +
  // revalidateIfStale:false. The old inline `liveOpts` (2 s dedupe)
  // produced separate cache entries from `usePortfolioSummary` used by
  // other components (RealtimeProvider, dashboard sidebars), multiplying
  // portfolio calls on mount.
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
    revalidateOnFocus: true,
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
  const { data: brief, isLoading: briefLoading } = useSWR<MorningBriefResponse>(
    API.market.morningBriefToday,
    fetcher,
    briefOpts,
  );
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

  const bookCurrency: "USD" | "KRW" =
    positions.length > 0 && positions.every((p) => p.currency === "KRW")
      ? "KRW"
      : "USD";

  const briefText =
    brief?.available !== false
      ? brief?.brief?.insight ?? brief?.brief?.summary ?? null
      : null;

  // Hero variant: prefer insight as headline, fall back to summary; if both
  // exist, render summary as the body paragraph beneath the headline.
  const heroHeadline =
    brief?.available !== false
      ? brief?.brief?.insight ?? brief?.brief?.summary ?? null
      : null;
  const heroBody =
    brief?.available !== false &&
    brief?.brief?.insight &&
    brief?.brief?.summary &&
    brief.brief.insight !== brief.brief.summary
      ? brief.brief.summary ?? null
      : null;

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
        key: "ticker",
        header: "Ticker",
        width: "96px",
        render: (r) => (
          <Link
            href={`/detail/${encodeURIComponent(r.ticker)}`}
            className="pq-ticker-link"
            style={{ color: "var(--pq-bronze)", letterSpacing: "0.04em" }}
          >
            {r.ticker}
          </Link>
        ),
      },
      {
        key: "name",
        header: "Name",
        render: (r) => (
          <span
            style={{
              color: "rgba(245,240,232,0.75)",
              display: "inline-block",
              maxWidth: 200,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {r.name}
          </span>
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
  const watchItems = watch?.items ?? watch?.watchlist ?? [];
  const watchRows: WatchRow[] = useMemo(() => {
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
  }, [watchItems]);

  const watchColumns: Column<WatchRow>[] = useMemo(
    () => [
      {
        key: "ticker",
        header: "Ticker",
        width: "96px",
        render: (r) => (
          <Link
            href={`/detail/${encodeURIComponent(r.ticker)}`}
            className="pq-ticker-link"
            style={{ color: "var(--pq-bronze)", letterSpacing: "0.04em" }}
          >
            {r.ticker}
          </Link>
        ),
      },
      {
        key: "name",
        header: "Name",
        render: (r) => (
          <span
            style={{
              color: "rgba(245,240,232,0.75)",
              display: "inline-block",
              maxWidth: 200,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {r.name || "—"}
          </span>
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
              fontSize: 9.5,
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
  const signalsItems = signalsData?.signals ?? signalsData?.items ?? [];
  const signalRows: SignalRow[] = useMemo(() => {
    return signalsItems.slice(0, 12).map((s, i) => ({
      id: s.id ?? `${s.ticker || i}`,
      ticker: s.ticker || s.symbol || "—",
      label: s.label || "NEUTRAL",
      strength: s.strength ?? 0,
      observedAt: s.observed_at ?? "",
    }));
  }, [signalsItems]);

  const signalColumns: Column<SignalRow>[] = useMemo(
    () => [
      {
        key: "ticker",
        header: "Ticker",
        width: "96px",
        render: (r) => (
          <Link
            href={`/detail/${encodeURIComponent(r.ticker)}`}
            className="pq-ticker-link"
            style={{ color: "var(--pq-bronze)", letterSpacing: "0.04em" }}
          >
            {r.ticker}
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
                fontSize: 10,
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

      {/* ═══════════ LIVING CFO STATUS — sticky hairline ═══════════ */}
      <div
        className="sticky z-40 -mx-4 md:-ml-8 md:-mr-10 mb-4"
        style={{
          top: 0,
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

      {/* ═══════════ Row 1 — Today Brief │ Snapshot │ Risk Gauges ═══════════ */}
      <section
        className="grid gap-3 mb-3"
        style={{
          gridTemplateColumns: "minmax(0, 1.4fr) minmax(0, 1fr) minmax(0, 1fr)",
        }}
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
                fontSize: 9.5,
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
            style={{
              fontSize: 12.5,
              lineHeight: 1.55,
              color: "rgba(245,240,232,0.82)",
              margin: 0,
            }}
          >
            {briefText
              ? briefText
              : "No brief observed for this session. The weekly memo is assembled every Sunday 07:00 KST and will archive here."}
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
              value={
                riskSummary?.var_95 != null
                  ? Math.abs(riskSummary.var_95)
                  : undefined
              }
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
        className="grid gap-3 mb-3"
        style={{
          gridTemplateColumns: "minmax(0, 1.4fr) minmax(0, 1fr)",
        }}
      >
        <div>
          <div
            className="flex items-center justify-between mb-1"
            style={{ padding: "0 2px" }}
          >
            <span
              className="font-mono uppercase"
              style={{
                fontSize: 9.5,
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
                fontSize: 9.5,
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
        className="grid gap-3 mb-3"
        style={{
          gridTemplateColumns: "minmax(0, 1.4fr) minmax(0, 1fr)",
        }}
      >
        <div>
          <div
            className="flex items-center justify-between mb-1"
            style={{ padding: "0 2px" }}
          >
            <span
              className="font-mono uppercase"
              style={{
                fontSize: 9.5,
                letterSpacing: "0.24em",
                color: "var(--pq-bronze)",
              }}
            >
              Equity Curve · 90d
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
                fontSize: 9.5,
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

      {/* ═══════════ Row 3 — NVDA Candlestick (full width) ═══════════ */}
      <section className="mb-3">
        <div
          className="flex items-center justify-between mb-1"
          style={{ padding: "0 2px" }}
        >
          <span
            className="font-mono uppercase"
            style={{
              fontSize: 9.5,
              letterSpacing: "0.24em",
              color: "var(--pq-bronze)",
            }}
          >
            Flagship Chart — NVDA · 1D
          </span>
          <Link
            href="/detail/NVDA"
            className="font-mono uppercase"
            style={{
              fontSize: 9,
              letterSpacing: "0.2em",
              color: "rgba(245,240,232,0.4)",
            }}
          >
            Full View ›
          </Link>
        </div>
        <CandlestickChart
          ticker="NVDA"
          timeframe="1D"
          indicators={["ma20", "ma50", "volume"]}
          height={320}
        />
      </section>

      {/* ═══════════ Row 4 — Signals │ Pulse Activity ═══════════ */}
      <section
        className="grid gap-3 mb-3"
        style={{
          gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
        }}
      >
        <div>
          <div
            className="flex items-center justify-between mb-1"
            style={{ padding: "0 2px" }}
          >
            <span
              className="font-mono uppercase"
              style={{
                fontSize: 9.5,
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
                fontSize: 9.5,
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
              posColumns[0], // ticker
              posColumns[4], // current
              posColumns[5], // pnl%
              posColumns[6], // mkt value
            ]}
            rows={pulseRows}
            label="Pulse Activity"
            emptyState="Open positions to see pulse activity."
          />
        </div>
      </section>

      {/* ═══════════ Row 5 — Companion entry │ Feedback ═══════════ */}
      <section
        className="grid gap-3 mb-5"
        style={{
          gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
        }}
      >
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
              fontSize: 9.5,
              letterSpacing: "0.24em",
              color: "var(--pq-bronze)",
            }}
          >
            Companion · Personal Journal
          </span>
          <p
            style={{
              fontSize: 12,
              lineHeight: 1.55,
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

      {/* ═══════════ Foot signature + legal ═══════════ */}
      <div className="mt-6">
        <FootSignature />
        <DisclaimerBanner type="signal" />
      </div>

      {/* Weekly Pulse — auto-triggers Monday 07:00 KST */}
      <WeeklyPulseCard />
    </ErrorBoundary>
  );
}
