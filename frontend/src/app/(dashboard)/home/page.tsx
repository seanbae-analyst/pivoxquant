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

import { useMemo, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  API,
  PORTFOLIO_SUMMARY,
  PORTFOLIO_POSITIONS,
  RISK_SUMMARY,
} from "@/lib/endpoints";
import { fmtUsd, fmtPct } from "@/lib/format";
import type { Position } from "@/components/portfolio/types";

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

/* ── Equity observation curve — real points or sketch fallback ── */

function EquityCurve({ points }: { points: HistoryPoint[] }) {
  const path = useMemo(() => {
    if (!points.length) return null;
    const values = points.map((p) => p.value).filter((v) => isFinite(v));
    if (values.length < 2) return null;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const w = 500;
    const h = 220;
    const padY = 10;
    const step = w / (values.length - 1);
    const coords = values.map((v, i) => {
      const x = i * step;
      const y = padY + ((max - v) / range) * (h - padY * 2);
      return [x, y] as const;
    });
    const line = coords
      .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`)
      .join(" ");
    const area =
      line +
      ` L${w} ${h} L0 ${h} Z`;
    return { line, area, w, h };
  }, [points]);

  if (!path) {
    // Fallback sketch (same as before) when no data
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
          <line key={y} x1={0} y1={y} x2={500} y2={y} stroke="#F5F0E8" strokeOpacity={0.06} strokeWidth={0.5} />
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
    <svg
      viewBox={`0 0 ${path.w} ${path.h}`}
      className="h-full w-full"
      preserveAspectRatio="none"
      role="img"
      aria-label="Equity observation curve"
    >
      <defs>
        <linearGradient id="pqHomeCurveLive" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#8B6F47" stopOpacity="0.22" />
          <stop offset="100%" stopColor="#8B6F47" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[55, 110, 165].map((y) => (
        <line key={y} x1={0} y1={y} x2={path.w} y2={y} stroke="#F5F0E8" strokeOpacity={0.06} strokeWidth={0.5} />
      ))}
      <path d={path.area} fill="url(#pqHomeCurveLive)" />
      <path d={path.line} fill="none" stroke="#8B6F47" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ── Page ── */

export default function HomePage() {
  const { user } = useAuth();
  const [period, setPeriod] = useState<(typeof PERIODS)[number]["value"]>("6mo");

  const { data: summary } = useSWR<SummaryResponse>(PORTFOLIO_SUMMARY, fetcher, {
    revalidateOnFocus: false,
  });
  const { data: risk } = useSWR<RiskSummaryResponse>(RISK_SUMMARY, fetcher, {
    revalidateOnFocus: false,
  });
  const { data: posData } = useSWR<PositionsResponse>(PORTFOLIO_POSITIONS, fetcher, {
    revalidateOnFocus: false,
  });
  const { data: alertsData } = useSWR<AlertsResponse>(
    `${API.alerts.list}?limit=5`,
    fetcher,
    { revalidateOnFocus: false },
  );
  const { data: history } = useSWR<HistoryResponse>(
    API.portfolio.history(period),
    fetcher,
    { revalidateOnFocus: false },
  );
  const { data: brief } = useSWR<MorningBriefResponse>(
    API.market.morningBriefToday,
    fetcher,
    { revalidateOnFocus: false },
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

  /* ── Render ── */
  return (
    <ErrorBoundary>
      {/* Header */}
      <header className="mb-8 flex items-center justify-between gap-4">
        <div>
          <div
            className="font-serif uppercase"
            style={{ fontSize: "10px", letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
          >
            PivoxQuant · Monday Brief · {weekTag()}
          </div>
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
        </div>
        <span
          className="font-mono hidden sm:inline"
          style={{ fontSize: "11px", letterSpacing: "0.05em", color: "rgba(245,240,232,0.5)" }}
        >
          07:00 KST
        </span>
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
            <p className="pq-home-stat mb-1.5" style={{ color: "var(--pq-ivory)" }}>
              {m.value}
            </p>
            <p className="font-serif" style={{ fontSize: "11px", color: "rgba(245,240,232,0.55)" }}>
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
            <span
              className="font-serif uppercase"
              style={{ fontSize: "9.5px", letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
            >
              Equity · Observation
            </span>
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
            <p className="font-serif italic" style={{ fontSize: "12px", color: "rgba(245,240,232,0.45)" }}>
              No alerts observed.
            </p>
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
            <p className="font-serif italic" style={{ fontSize: "12px", color: "rgba(245,240,232,0.45)" }}>
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
                    <td
                      className="py-2.5 text-right font-mono tabular-nums"
                      style={{ fontSize: "11.5px", color: "rgba(245,240,232,0.7)" }}
                    >
                      {fmtUsd(p.current * p.shares)}
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
            <p className="font-serif italic" style={{ fontSize: "12px", color: "rgba(245,240,232,0.45)" }}>
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
            className="font-serif italic"
            style={{ fontSize: "13px", color: "rgba(245,240,232,0.5)" }}
          >
            Today&rsquo;s brief has not been dispatched yet.
          </p>
        )}
      </section>

      {/* Footer — legal note and disclaimer banner */}
      <p
        className="mb-6 font-serif italic"
        style={{ fontSize: "11px", color: "rgba(245,240,232,0.5)" }}
      >
        Observational signals. Not investment advice.
      </p>
      <DisclaimerBanner type="signal" />
    </ErrorBoundary>
  );
}
