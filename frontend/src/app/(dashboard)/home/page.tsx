"use client";

/**
 * /home — PivoxQuant Research Terminal.
 *
 * Rendered inside <DashboardLayout/>. Restores the full original widget
 * set against live SWR endpoints — Portfolio summary, Positions, Equity
 * curve, Risk, Alerts, Signals, Morning Brief — all rendered in the
 * Vantablack ink theme (transparent cards, ivory text, bronze accents).
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. DisclaimerBanner at foot.
 */

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  Caption,
  Fleuron,
  FootSignature,
  RuledKicker,
} from "@/components/ui/editorial";
import { InteractiveLineChart } from "@/components/charts/interactive-line-chart";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  API,
  PORTFOLIO_SUMMARY,
  PORTFOLIO_POSITIONS,
  RISK_SUMMARY,
} from "@/lib/endpoints";
import { fmtUsd, fmtPct } from "@/lib/format";
import { liveRefresh, isMarketOpen } from "@/lib/market-hours";
import {
  PriceWithTimestamp,
  relativeTime,
} from "@/components/ui/price-with-timestamp";
import type { Position } from "@/components/portfolio/types";

/** Format an ISO date or YYYY-MM-DD into a compact "Mon DD, YYYY" label. */
function fmtChartDate(d: string): string {
  const parsed = new Date(d);
  if (isNaN(parsed.getTime())) return d;
  return parsed.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

const fetcher = <T,>(url: string) => apiFetch<T>(url);

/* ── Response shapes (loose to tolerate backend variants) ── */

interface SummaryResponse {
  totalNav?: number;
  todayPnl?: number;
  todayPnlPct?: number;
  unrealized?: number;
  positionCount?: number;
}
interface RiskSummaryResponse {
  var_1d_pct?: number;
  corr_risk_index?: number;
}
interface PositionsResponse {
  positions?: Position[];
}
interface AlertItem {
  id: number | string;
  title?: string;
  message?: string;
  ticker?: string;
  severity?: string;
  created_at?: string;
  read_at?: string | null;
}
interface AlertsResponse {
  alerts?: AlertItem[];
}
interface HistoryPoint {
  date: string;
  value: number;
}
interface HistoryResponse {
  points?: HistoryPoint[];
  history?: HistoryPoint[];
}
interface MorningBriefBody {
  insight?: string;
  summary?: string;
  market_summary?: {
    sp500?: { change_pct?: number };
    nasdaq?: { change_pct?: number };
    kospi?: { change_pct?: number };
  };
}
interface MorningBriefResponse {
  available?: boolean;
  brief?: MorningBriefBody;
}

const PERIODS = [
  { label: "1M", value: "1mo" },
  { label: "3M", value: "3mo" },
  { label: "6M", value: "6mo" },
  { label: "1Y", value: "1y" },
  { label: "ALL", value: "max" },
] as const;

function weekTag(): string {
  const d = new Date();
  const first = new Date(d.getFullYear(), 0, 1);
  const days = Math.floor((d.getTime() - first.getTime()) / 86400000);
  const w = Math.ceil((days + first.getDay() + 1) / 7);
  return `${d.getFullYear()} · W${String(w).padStart(2, "0")}`;
}

function signalFor(pnlPct: number | undefined): "POSITIVE" | "NEUTRAL" | "NEGATIVE" {
  if (pnlPct == null) return "NEUTRAL";
  if (pnlPct > 0.5) return "POSITIVE";
  if (pnlPct < -0.5) return "NEGATIVE";
  return "NEUTRAL";
}

/* ── Equity observation curve — real points + hover, or sketch fallback ── */

function EquityCurve({ points }: { points: HistoryPoint[] }) {
  const valid = useMemo(
    () => points.filter((p) => p && isFinite(p.value)),
    [points],
  );

  if (valid.length < 2) {
    // Fallback sketch (no hover) when there's no data.
    return (
      <svg
        viewBox="0 0 500 220"
        className="h-full w-full"
        preserveAspectRatio="none"
        role="img"
        aria-label="Equity observation curve (no data)"
      >
        <defs>
          <linearGradient id="pqHomeCurveFallback" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8B6F47" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#8B6F47" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[60, 120, 180].map((y) => (
          <line
            key={y}
            x1={0}
            y1={y}
            x2={500}
            y2={y}
            stroke="#F5F0E8"
            strokeOpacity={0.06}
            strokeWidth={0.5}
          />
        ))}
        <path
          d="M0 170 C60 165, 100 150, 160 138 C220 125, 260 130, 320 110 C380 90, 420 95, 500 60 L500 220 L0 220 Z"
          fill="url(#pqHomeCurveFallback)"
        />
        <path
          d="M0 170 C60 165, 100 150, 160 138 C220 125, 260 130, 320 110 C380 90, 420 95, 500 60"
          fill="none"
          stroke="#8B6F47"
          strokeWidth="1.25"
          strokeLinecap="round"
        />
      </svg>
    );
  }

  return (
    <InteractiveLineChart
      points={valid}
      height={220}
      valueFormatter={(v) => fmtUsd(v)}
      dateFormatter={fmtChartDate}
      yLabel="Portfolio NAV"
      ariaLabel="Equity observation curve"
    />
  );
}

/* ── Page ── */

export default function HomePage() {
  const { user } = useAuth();
  const [period, setPeriod] = useState<(typeof PERIODS)[number]["value"]>("6mo");

  // Live-refresh cadence — market-aware (open vs closed):
  //  - summary/positions → 5s open / 60s closed  (quote-driven)
  //  - risk               → 10s open / 120s closed
  //  - alerts             → 10s open / 60s closed
  //  - history            → 15s open / 120s closed (aggregated series)
  //  - morning brief      → 10min always (daily artifact)
  const liveOpts = {
    refreshInterval: () => liveRefresh(5_000, 60_000),
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    dedupingInterval: 2_000,
    errorRetryCount: 2,
    errorRetryInterval: 5_000,
  } as const;
  const riskOpts = {
    refreshInterval: () => liveRefresh(10_000, 120_000),
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    dedupingInterval: 2_000,
    errorRetryCount: 2,
    errorRetryInterval: 5_000,
  } as const;
  const alertsOpts = {
    refreshInterval: () => liveRefresh(10_000, 60_000),
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    dedupingInterval: 2_000,
    errorRetryCount: 2,
    errorRetryInterval: 5_000,
  } as const;
  const historyOpts = {
    refreshInterval: () => liveRefresh(15_000, 120_000),
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    dedupingInterval: 5_000,
    errorRetryCount: 2,
    errorRetryInterval: 5_000,
  } as const;
  const briefOpts = {
    refreshInterval: 600_000,
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 60_000,
    errorRetryCount: 2,
    errorRetryInterval: 10_000,
  } as const;

  const { data: summary } = useSWR<SummaryResponse & { observed_at?: string }>(
    PORTFOLIO_SUMMARY,
    fetcher,
    liveOpts,
  );
  const { data: risk } = useSWR<RiskSummaryResponse>(RISK_SUMMARY, fetcher, riskOpts);
  const { data: posData } = useSWR<PositionsResponse>(PORTFOLIO_POSITIONS, fetcher, liveOpts);
  const { data: alertsData } = useSWR<AlertsResponse>(
    `${API.alerts.list}?limit=5`,
    fetcher,
    alertsOpts,
  );
  const { data: history } = useSWR<HistoryResponse>(
    API.portfolio.history(period),
    fetcher,
    historyOpts,
  );
  const { data: brief } = useSWR<MorningBriefResponse>(
    API.market.morningBriefToday,
    fetcher,
    briefOpts,
  );

  /* Derived */
  const positions = posData?.positions ?? [];
  const alerts = alertsData?.alerts ?? [];
  const unreadCount = alerts.filter((a) => !a.read_at).length;
  const historyPoints = useMemo(() => {
    const raw = history?.points ?? history?.history ?? [];
    return raw.filter((p) => p && isFinite(p.value));
  }, [history]);

  const positionsWithPnl = useMemo(
    () =>
      positions.map((p) => {
        const pnlPct = p.avgCost > 0 ? ((p.current - p.avgCost) / p.avgCost) * 100 : 0;
        return { ...p, pnlPct };
      }),
    [positions],
  );

  const topPositions = [...positionsWithPnl]
    .sort((a, b) => b.current * b.shares - a.current * a.shares)
    .slice(0, 5);

  const topSignals = [...positionsWithPnl]
    .sort((a, b) => Math.abs(b.pnlPct) - Math.abs(a.pnlPct))
    .slice(0, 5);

  /* Stats */
  const navValue = summary?.totalNav;
  const navDisplay = navValue != null ? fmtUsd(navValue) : "—";
  const navSub =
    summary?.todayPnlPct != null ? `${fmtPct(summary.todayPnlPct)} today` : "—";

  const unrealized = summary?.unrealized;
  const unrealizedDisplay = unrealized != null ? fmtUsd(unrealized) : "—";
  const positionCount = summary?.positionCount ?? positions.length;

  const riskScore =
    risk?.corr_risk_index != null
      ? Math.round(Math.max(0, Math.min(100, 100 - risk.corr_risk_index * 100)))
      : null;
  const riskDisplay = riskScore != null ? String(riskScore) : "—";
  const riskSub =
    risk?.var_1d_pct != null ? `VaR 1D ${risk.var_1d_pct.toFixed(2)}%` : "—";

  const briefInsight = brief?.brief?.insight ?? brief?.brief?.summary ?? null;
  const briefAvailable = brief?.available !== false && !!briefInsight;

  const displayName = user?.name?.split(" ")[0] || "Observer";

  /* ── Live banner — ticks every 1s so "Xs ago" stays fresh. ── */
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const marketOpen = isMarketOpen();
  const observedAt = summary?.observed_at;

  /* ── Render ── */
  return (
    <ErrorBoundary>
      {/* Header */}
      <header className="mb-8 flex items-center justify-between gap-4">
        <div>
          <RuledKicker>PivoxQuant · Monday Brief · {weekTag()}</RuledKicker>
          <h1
            className="mt-2 font-serif italic"
            style={{
              fontSize: "clamp(1.75rem, 3vw, 2.25rem)",
              lineHeight: 1.1,
              color: "var(--pq-ivory)",
              letterSpacing: "-0.015em",
            }}
          >
            Welcome back, {displayName}.
          </h1>
          <Caption className="mt-2">
            What we&rsquo;ve observed across your book since last close.
          </Caption>
        </div>
        <div className="hidden flex-col items-end gap-1 sm:flex">
          <div className="flex items-center gap-1.5 font-mono tabular-nums text-[10px]">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                marketOpen ? "bg-[#7db487] animate-pulse" : "bg-[var(--pq-bronze)] opacity-50"
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
          <span
            className="font-mono"
            style={{
              fontSize: "11px",
              letterSpacing: "0.05em",
              color: "rgba(245,240,232,0.5)",
            }}
          >
            07:00 KST
          </span>
        </div>
      </header>

      {/* 4-stat bento */}
      <section className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        {[
          { label: "Portfolio Value", value: navDisplay, sub: navSub },
          {
            label: "Unrealized P&L",
            value: unrealizedDisplay,
            sub: `${positionCount} position${positionCount === 1 ? "" : "s"}`,
          },
          { label: "Risk Index", value: riskDisplay, sub: riskSub },
          {
            label: "Alerts",
            value: String(unreadCount),
            sub: unreadCount > 0 ? "unread" : "all clear",
          },
        ].map((m) => (
          <div
            key={m.label}
            className="rounded-sm"
            style={{
              backgroundColor: "rgba(255,255,255,0.02)",
              border: "0.5px solid rgba(245,240,232,0.08)",
              padding: "20px 22px",
            }}
          >
            <p
              className="mb-2 font-serif uppercase"
              style={{ fontSize: "9.5px", letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
            >
              {m.label}
            </p>
            <div className="pq-num-display mb-1.5" style={{ color: "var(--pq-ivory)", fontFamily: "var(--font-mono), ui-monospace, monospace", fontVariantNumeric: "tabular-nums", fontSize: "28px", lineHeight: 1.05, letterSpacing: "-0.015em" }}>
              {m.value}
            </div>
            <p className="font-serif" style={{ fontSize: "11px", color: "rgba(245,240,232,0.55)" }}>
              <span style={{ color: "var(--pq-bronze)", marginRight: 4 }}>&asymp;</span>
              {m.sub}
            </p>
          </div>
        ))}
      </section>

      {/* Equity chart + Alerts */}
      <section className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Equity curve */}
        <div
          className="lg:col-span-2"
          style={{
            backgroundColor: "rgba(255,255,255,0.015)",
            borderTop: "0.5px solid rgba(245,240,232,0.08)",
            borderBottom: "0.5px solid rgba(245,240,232,0.08)",
            padding: "24px 8px",
          }}
        >
          <div className="mb-4 flex items-center justify-between px-2">
            <RuledKicker>Equity &middot; Observation</RuledKicker>
            <div className="flex gap-1">
              {PERIODS.map((p) => {
                const active = p.value === period;
                return (
                  <button
                    key={p.value}
                    onClick={() => setPeriod(p.value)}
                    className="font-mono tabular-nums"
                    style={{
                      fontSize: "10px",
                      padding: "2px 8px",
                      borderRadius: "2px",
                      border: active ? "1px solid var(--pq-bronze)" : "1px solid transparent",
                      color: active ? "var(--pq-bronze)" : "rgba(245,240,232,0.5)",
                      letterSpacing: "0.05em",
                      background: "transparent",
                      cursor: "pointer",
                    }}
                  >
                    {p.label}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="h-[220px]">
            <EquityCurve points={historyPoints} />
          </div>
        </div>

        {/* Alerts list */}
        <aside
          className="rounded-sm"
          style={{
            backgroundColor: "rgba(255,255,255,0.02)",
            border: "0.5px solid rgba(245,240,232,0.08)",
            padding: "22px 22px",
          }}
        >
          <div className="mb-3 flex items-center justify-between">
            <p
              className="font-serif uppercase"
              style={{ fontSize: "9.5px", letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
            >
              Recent Alerts
            </p>
            <Link
              href="/alerts"
              className="font-mono uppercase"
              style={{ fontSize: "9px", letterSpacing: "0.18em", color: "rgba(245,240,232,0.45)" }}
            >
              View
            </Link>
          </div>
          {alerts.length === 0 ? (
            <div className="py-6 text-center">
              <Fleuron size={12} />
              <p className="font-serif mt-2" style={{ fontSize: "13px", color: "rgba(245,240,232,0.6)" }}>
                No observations recorded yet.
              </p>
              <Caption className="mt-1">Signals will appear as we observe them.</Caption>
            </div>
          ) : (
            <ul className="flex flex-col gap-3">
              {alerts.slice(0, 5).map((a) => (
                <li
                  key={a.id}
                  style={{
                    borderBottom: "0.5px solid rgba(245,240,232,0.06)",
                    paddingBottom: "10px",
                  }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span
                      className="font-serif"
                      style={{ fontSize: "12.5px", color: "var(--pq-ivory)", lineHeight: 1.35 }}
                    >
                      {a.title || a.message || "Alert"}
                    </span>
                    {!a.read_at && (
                      <span
                        style={{
                          width: "6px",
                          height: "6px",
                          borderRadius: "50%",
                          background: "var(--pq-bronze)",
                          marginTop: "6px",
                          flexShrink: 0,
                        }}
                      />
                    )}
                  </div>
                  {a.ticker && (
                    <span
                      className="font-mono tabular-nums mt-1 inline-block"
                      style={{ fontSize: "10px", color: "rgba(245,240,232,0.45)" }}
                    >
                      {a.ticker}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </aside>
      </section>

      {/* Positions + Signals */}
      <section className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Positions */}
        <div
          className="rounded-sm"
          style={{
            backgroundColor: "rgba(255,255,255,0.02)",
            border: "0.5px solid rgba(245,240,232,0.08)",
            padding: "22px 24px",
          }}
        >
          <div className="mb-4 flex items-center justify-between">
            <p
              className="font-serif uppercase"
              style={{ fontSize: "9.5px", letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
            >
              Positions
            </p>
            <Link
              href="/portfolio"
              className="font-mono uppercase"
              style={{ fontSize: "9px", letterSpacing: "0.18em", color: "rgba(245,240,232,0.45)" }}
            >
              All
            </Link>
          </div>
          {topPositions.length === 0 ? (
            <p className="font-serif" style={{ fontSize: "12px", color: "rgba(245,240,232,0.45)" }}>
              No positions yet.
            </p>
          ) : (
            <table className="w-full" style={{ tableLayout: "fixed", borderCollapse: "collapse" }}>
              <colgroup>
                <col style={{ width: "45%" }} />
                <col style={{ width: "25%" }} />
                <col style={{ width: "30%" }} />
              </colgroup>
              <tbody>
                {topPositions.map((p) => (
                  <tr key={p.id} style={{ borderBottom: "0.5px solid rgba(245,240,232,0.06)" }}>
                    <td className="py-2.5">
                      <div className="font-serif" style={{ fontSize: "13px", color: "var(--pq-ivory)" }}>
                        {p.name}
                      </div>
                      <div
                        className="font-mono tabular-nums mt-0.5"
                        style={{ fontSize: "10px", color: "rgba(245,240,232,0.45)" }}
                      >
                        {p.symbol}
                      </div>
                    </td>
                    <td className="py-2.5 text-right">
                      <PriceWithTimestamp
                        price={p.current}
                        observedAt={p.observed_at}
                        currency={p.currency === "KRW" ? "KRW" : "USD"}
                        size="sm"
                      />
                    </td>
                    <td
                      className="py-2.5 text-right font-mono tabular-nums"
                      style={{
                        fontSize: "11.5px",
                        color: p.pnlPct >= 0 ? "#7db487" : "#d18888",
                      }}
                    >
                      {fmtPct(p.pnlPct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Signals */}
        <div
          className="rounded-sm"
          style={{
            backgroundColor: "rgba(255,255,255,0.02)",
            border: "0.5px solid rgba(245,240,232,0.08)",
            padding: "22px 24px",
          }}
        >
          <div className="mb-4 flex items-center justify-between">
            <p
              className="font-serif uppercase"
              style={{ fontSize: "9.5px", letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
            >
              Signals
            </p>
            <Link
              href="/signals"
              className="font-mono uppercase"
              style={{ fontSize: "9px", letterSpacing: "0.18em", color: "rgba(245,240,232,0.45)" }}
            >
              All
            </Link>
          </div>
          {topSignals.length === 0 ? (
            <p className="font-serif" style={{ fontSize: "12px", color: "rgba(245,240,232,0.45)" }}>
              No observations available.
            </p>
          ) : (
            <ul className="flex flex-col gap-3">
              {topSignals.map((p) => {
                const sig = signalFor(p.pnlPct);
                const cls =
                  sig === "POSITIVE"
                    ? "pq-ink-pill pq-ink-pill--pos"
                    : sig === "NEGATIVE"
                      ? "pq-ink-pill pq-ink-pill--neg"
                      : "pq-ink-pill pq-ink-pill--neu";
                return (
                  <li
                    key={p.id}
                    className="flex items-center justify-between gap-3"
                    style={{ borderBottom: "0.5px solid rgba(245,240,232,0.06)", paddingBottom: "10px" }}
                  >
                    <div className="min-w-0">
                      <div
                        className="font-serif truncate"
                        style={{ fontSize: "13px", color: "var(--pq-ivory)" }}
                      >
                        {p.name}
                      </div>
                      <div
                        className="font-mono tabular-nums mt-0.5"
                        style={{ fontSize: "10px", color: "rgba(245,240,232,0.45)" }}
                      >
                        {p.symbol}
                      </div>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <span
                        className="font-mono tabular-nums"
                        style={{
                          fontSize: "11.5px",
                          color: p.pnlPct >= 0 ? "#7db487" : "#d18888",
                        }}
                      >
                        {fmtPct(p.pnlPct)}
                      </span>
                      <span className={cls}>{sig}</span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>

      {/* Morning Brief */}
      <section
        className="mb-8 rounded-sm"
        style={{
          backgroundColor: "rgba(255,255,255,0.015)",
          border: "0.5px solid rgba(245,240,232,0.08)",
          padding: "24px 28px",
        }}
      >
        <div className="mb-3 flex items-center justify-between">
          <p
            className="font-serif uppercase"
            style={{ fontSize: "9.5px", letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
          >
            Morning Brief
          </p>
          <Link
            href="/morning-brief"
            className="font-mono uppercase"
            style={{ fontSize: "9px", letterSpacing: "0.18em", color: "rgba(245,240,232,0.45)" }}
          >
            Archive
          </Link>
        </div>
        {briefAvailable ? (
          <p
            className="font-serif"
            style={{
              fontSize: "14px",
              lineHeight: 1.55,
              color: "rgba(245,240,232,0.82)",
              maxWidth: "68ch",
            }}
          >
            {briefInsight}
          </p>
        ) : (
          <p
            className="font-serif"
            style={{ fontSize: "13px", color: "rgba(245,240,232,0.5)" }}
          >
            Today&rsquo;s brief has not been dispatched yet.
          </p>
        )}
      </section>

      {/* Footer — editorial signature, legal note, and disclaimer banner */}
      <FootSignature />
      <DisclaimerBanner type="signal" />
    </ErrorBoundary>
  );
}
