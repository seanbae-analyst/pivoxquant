"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { usePortfolio, useAnalytics, useHistory } from "@/lib/hooks";
import { useRealtimeContext } from "@/lib/realtime";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { MorningBriefCard } from "@/components/dashboard/morning-brief-card";
import { EquityChart, type PeriodValue } from "@/components/dashboard/equity-chart";
import { SignalsWidget } from "@/components/dashboard/signals-widget";
import { RiskWidget } from "@/components/dashboard/risk-widget";
import { PositionsList } from "@/components/dashboard/positions-list";
import { PQCta } from "@/components/ui/pq-cta";
import { fmtUsd, fmtKrw, fmtPct } from "@/lib/format";
import { useT, useLocale } from "@/lib/locale";
import type { PortfolioResponse, Position } from "@/lib/types";

/* ──────────────────────────────────────────────────────────────
   /home — PivoxQuant Research Terminal (authenticated surface).

   Visual parity with the landing page's Dashboard Preview section
   (components/landing/landing-page.tsx §6 "Dashboard Preview",
   lines 3011–3295). Ivory canvas, Bronze accents, Vantablack
   Terminal chrome, serif-first typography, hairline dividers,
   mono tabular-nums for all figures.

   Copy follows PivoxQuant legal constraints — "observation"
   / "signal" / "note" only; no "recommend" / "advice" /
   "BUY" / "SELL" / "HOLD".
   ────────────────────────────────────────────────────────────── */

function getGreeting(t: (key: string) => string): string {
  const h = new Date().getHours();
  if (h < 12) return t("dashboard.greeting.morning");
  if (h < 18) return t("dashboard.greeting.afternoon");
  return t("dashboard.greeting.evening");
}

function formatDate(locale: string): string {
  const localeCode = locale === "ko" ? "ko-KR" : "en-US";
  return new Date().toLocaleDateString(localeCode, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/* ── Display helpers mirroring the old metric-cards logic ── */

type Unit = "KRW" | "USD";

function pickDisplayUnit(portfolio: PortfolioResponse | undefined): Unit {
  if (!portfolio) return "USD";
  const hasKrw =
    portfolio.total_value_krw > 0 ||
    portfolio.positions.some((p) => p.currency === "KRW" || p.is_korean);
  return hasKrw ? "KRW" : "USD";
}

function computeTotalPnl(
  positions: Position[],
  unit: Unit,
  fxRate: number,
): number {
  return positions.reduce((sum, p) => {
    const pnlNative = (p.current_price - p.avg_cost) * p.shares;
    const isKrw = p.currency === "KRW" || p.is_korean;
    if (unit === "KRW") {
      return sum + (isKrw ? pnlNative : pnlNative * (fxRate || 0));
    }
    return sum + (isKrw ? 0 : pnlNative);
  }, 0);
}

function computeTotalPnlPct(
  positions: Position[],
  unit: Unit,
  fxRate: number,
): number {
  const totalCost = positions.reduce((sum, p) => {
    const costNative = p.avg_cost * p.shares;
    const isKrw = p.currency === "KRW" || p.is_korean;
    if (unit === "KRW")
      return sum + (isKrw ? costNative : costNative * (fxRate || 0));
    return sum + (isKrw ? 0 : costNative);
  }, 0);
  if (totalCost === 0) return 0;
  return (computeTotalPnl(positions, unit, fxRate) / totalCost) * 100;
}

/* ── Bento stat cell — editorial, hairline border, no shadow ── */

function StatCell({
  label,
  value,
  sub,
  subTone,
}: {
  label: string;
  value: string;
  sub?: string;
  subTone?: "up" | "down" | "muted";
}) {
  const subColor =
    subTone === "up"
      ? "#3C7A52"
      : subTone === "down"
        ? "#9C3B3B"
        : "var(--pq-muted)";
  return (
    <div className="pq-dash-cell">
      <p className="pq-dash-label mb-3">{label}</p>
      <p className="pq-stat-num mb-1.5">{value}</p>
      {sub && (
        <p
          className="font-mono tabular-nums text-[11.5px]"
          style={{ color: subColor, letterSpacing: "0.01em" }}
        >
          {sub}
        </p>
      )}
    </div>
  );
}

/* ── Terminal chrome banner — "PivoxQuant · Monday Brief" ── */

function TerminalBanner() {
  const now = new Date().toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return (
    <div
      className="flex items-center justify-between rounded-[2px] px-5 py-2.5"
      style={{
        backgroundColor: "var(--pq-ink)",
        border: "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.08))",
      }}
    >
      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className="h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: "var(--pq-bronze)" }}
        />
        <span
          className="font-serif text-[10.5px] uppercase"
          style={{
            letterSpacing: "0.22em",
            color: "var(--pq-bronze)",
          }}
        >
          PivoxQuant · Monday Brief
        </span>
      </div>
      <span
        className="font-mono tabular-nums text-[11px]"
        style={{ color: "rgba(245,240,232,0.5)" }}
      >
        {now} KST
      </span>
    </div>
  );
}

/* ── Page ── */

export default function HomePage() {
  const { user } = useAuth();
  const { locale } = useLocale();
  const t = useT();
  const [period, setPeriod] = useState<PeriodValue>("1mo");

  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio();
  const { data: analytics, isLoading: analyticsLoading } = useAnalytics();
  const { data: history, isLoading: historyLoading } = useHistory(period);

  const realtimeCtx = useRealtimeContext();
  const firstName = user?.name?.split(" ")[0] ?? "there";

  /* Stat cell data — derived same way as the old MetricCards component
     but laid out flat for the bento grid. */
  const positions = portfolio?.positions ?? [];
  const fxRate = portfolio?.fx_rate ?? 0;
  const unit: Unit = pickDisplayUnit(portfolio);
  const totalValue =
    unit === "KRW"
      ? (portfolio?.total_value_all_krw ?? 0)
      : (portfolio?.total_value_usd ?? 0);
  const fmtValue = unit === "KRW" ? fmtKrw : fmtUsd;
  const totalPnl = computeTotalPnl(positions, unit, fxRate);
  const totalPnlPct = computeTotalPnlPct(positions, unit, fxRate);

  /* Risk score (re-derived — same formula as old MetricCards). */
  const sharpe = analytics?.sharpe_ratio;
  const mdd = analytics?.max_drawdown_pct ?? 0;
  const riskScore =
    sharpe !== undefined
      ? Math.min(100, Math.max(0, Math.round(50 + sharpe * 20 - mdd * 0.5)))
      : 75;
  const riskStatus =
    riskScore >= 70 ? "OBSERVED · STABLE" : riskScore >= 40 ? "OBSERVED · WATCH" : "OBSERVED · ELEVATED";

  return (
    <ErrorBoundary>
      <div className="mx-auto max-w-[1240px] space-y-10 pb-16">
        {/* ── Terminal banner (mirrors landing preview chrome) ── */}
        <TerminalBanner />

        {/* ── Greeting / kicker ── */}
        <header className="flex flex-col gap-4">
          <div className="pq-dash-kicker">Research Terminal</div>
          <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <h1 className="pq-dash-h2">
              {getGreeting(t)}, {firstName}
            </h1>
            <p
              className="font-mono tabular-nums text-[11.5px]"
              style={{
                color: "var(--pq-muted)",
                letterSpacing: "0.02em",
              }}
            >
              {formatDate(locale)}
            </p>
          </div>
          <p
            className="font-serif italic"
            style={{
              fontSize: "14.5px",
              lineHeight: 1.5,
              color: "rgba(10,10,10,0.55)",
              maxWidth: "58ch",
            }}
          >
            Your desk observations, rendered for the week. Read as signal — not
            as instruction.
          </p>
        </header>

        {/* ── Bento · stat cells (3 across) ── */}
        <section
          aria-label="Portfolio observations"
          className="grid grid-cols-1 gap-4 sm:grid-cols-3"
        >
          <StatCell
            label="Portfolio Value"
            value={portfolioLoading ? "—" : fmtValue(totalValue)}
            sub={
              portfolioLoading
                ? undefined
                : positions.length > 0
                  ? `${positions.length} ${t("dashboard.metrics.positions")}`
                  : t("dashboard.metrics.noPositionsYet")
            }
            subTone="muted"
          />
          <StatCell
            label="Unrealized P&L"
            value={
              portfolioLoading
                ? "—"
                : `${totalPnl >= 0 ? "+" : ""}${fmtValue(totalPnl)}`
            }
            sub={portfolioLoading ? undefined : fmtPct(totalPnlPct)}
            subTone={totalPnl >= 0 ? "up" : "down"}
          />
          <StatCell
            label="Risk Board"
            value={analyticsLoading ? "—" : `${riskScore} / 100`}
            sub={analyticsLoading ? undefined : riskStatus}
            subTone="muted"
          />
        </section>

        {/* ── Morning Brief — Artifact preview ── */}
        <MorningBriefCard />

        {/* ── Disclaimer (legally required on signal surfaces) ── */}
        <DisclaimerBanner type="signal" />

        {/* ── Equity · Observation chart (mirrors landing preview) ── */}
        <section
          aria-label="Equity observation"
          className="pq-dash-cell"
          style={{ padding: "24px" }}
        >
          <div className="mb-4 flex items-center justify-between">
            <span
              className="font-serif text-[10.5px] uppercase"
              style={{
                letterSpacing: "0.22em",
                color: "var(--pq-bronze)",
              }}
            >
              Equity · Observation
            </span>
            <PQCta href="/reports" withArrow>
              Weekly Memo
            </PQCta>
          </div>
          <EquityChart
            data={history?.data}
            isLoading={historyLoading}
            activePeriod={period}
            onPeriodChange={setPeriod}
          />
        </section>

        {/* ── Bento · Signals + Risk (2 across) ── */}
        <section
          aria-label="This week's observations"
          className="grid grid-cols-1 gap-4 lg:grid-cols-2"
        >
          <div className="pq-dash-cell" style={{ padding: 0 }}>
            <div
              className="flex items-center justify-between px-5 py-3"
              style={{
                borderBottom: "1px solid var(--pq-hairline)",
              }}
            >
              <span
                className="font-serif text-[10.5px] uppercase"
                style={{
                  letterSpacing: "0.22em",
                  color: "var(--pq-bronze)",
                }}
              >
                This Week&rsquo;s Observations
              </span>
              <Link
                href="/signals"
                className="font-serif text-[11.5px] tracking-[0.04em] transition-colors"
                style={{ color: "var(--pq-muted)" }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.color = "var(--pq-bronze)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.color = "var(--pq-muted)")
                }
              >
                All signals →
              </Link>
            </div>
            <div className="px-2 py-2">
              <SignalsWidget
                positions={portfolio?.positions}
                isLoading={portfolioLoading}
              />
            </div>
          </div>

          <div className="pq-dash-cell" style={{ padding: 0 }}>
            <div
              className="flex items-center justify-between px-5 py-3"
              style={{
                borderBottom: "1px solid var(--pq-hairline)",
              }}
            >
              <span
                className="font-serif text-[10.5px] uppercase"
                style={{
                  letterSpacing: "0.22em",
                  color: "var(--pq-bronze)",
                }}
              >
                Risk Board
              </span>
              <Link
                href="/risk"
                className="font-serif text-[11.5px] tracking-[0.04em] transition-colors"
                style={{ color: "var(--pq-muted)" }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.color = "var(--pq-bronze)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.color = "var(--pq-muted)")
                }
              >
                7-layer →
              </Link>
            </div>
            <div className="px-2 py-2">
              <RiskWidget
                analytics={analytics}
                isLoading={analyticsLoading}
                hasPositions={(portfolio?.positions?.length ?? 0) > 0}
              />
            </div>
          </div>
        </section>

        {/* ── Positions list (full width) ── */}
        <section aria-label="Positions" className="pq-dash-cell" style={{ padding: 0 }}>
          <div
            className="flex items-center justify-between px-5 py-3"
            style={{ borderBottom: "1px solid var(--pq-hairline)" }}
          >
            <span
              className="font-serif text-[10.5px] uppercase"
              style={{
                letterSpacing: "0.22em",
                color: "var(--pq-bronze)",
              }}
            >
              Positions
            </span>
            <Link
              href="/portfolio"
              className="font-serif text-[11.5px] tracking-[0.04em] transition-colors"
              style={{ color: "var(--pq-muted)" }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.color = "var(--pq-bronze)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.color = "var(--pq-muted)")
              }
            >
              Portfolio →
            </Link>
          </div>
          <div className="p-3">
            <PositionsList
              positions={portfolio?.positions}
              updatedTickers={realtimeCtx.updatedTickers}
              isLoading={portfolioLoading}
            />
          </div>
        </section>

        {/* ── Footer note — matches landing preview footnote ── */}
        <p
          className="pt-2 font-serif italic"
          style={{
            fontSize: "11.5px",
            color: "rgba(10,10,10,0.45)",
          }}
        >
          Observational signals. Not investment advice.
        </p>
      </div>
    </ErrorBoundary>
  );
}

