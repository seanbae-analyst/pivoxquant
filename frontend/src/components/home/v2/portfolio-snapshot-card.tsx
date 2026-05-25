"use client";

/**
 * <PortfolioSnapshotCard /> — Card 1 of the /home v2 gallery.
 *
 * Maps v1's row-1 "Portfolio Snapshot" KPI block (NAV / Today P/L / Positions)
 * onto the editorial-card surface from home-v2 SPEC §3 row 1.
 *
 * Reuses `usePortfolioSummary()` (line 192 of lib/hooks.ts, untouched) and
 * `usePortfolioPositions()` (line 205) for the cash-pct fallback.
 *
 * Sparkline is now driven by `useEquityCurve("1mo")` from portfolio v2 hooks
 * (P0-2 fix 2026-05-19). Em-dash on empty/loading/error — no fabricated path.
 */

import * as React from "react";
import { HomeCard } from "./home-card";
import { usePortfolioSummary, usePortfolioPositions } from "@/lib/hooks";
import { useEquityCurve, type EquityPoint } from "@/components/portfolio/v2/hooks-v2";
import { pctColor, PRICE_COLOR_HEX, fmtPct, fmtMoneyPlain } from "@/lib/format";
// FINDING-021: usePortfolioPositions() returns the BACKEND position shape,
// not the camelCase `@/components/portfolio/types` Position.
import type { Position } from "@/lib/types";

interface SummaryShape {
  totalNav?: number;
  // Native-currency stock subtotals (backend portfolio_summary_alias). Shown
  // separately on /home so a mixed KR+US portfolio isn't unified into USD.
  navUsd?: number;
  navKrw?: number;
  todayPnl?: number;
  // Native-currency Today P/L subtotals (backend portfolio_summary_alias). Used
  // so a KR-only book shows ₩ P/L instead of the USD-unified figure under a KRW
  // label (~1380× wrong, v52 FX-split regression).
  todayPnlUsd?: number;
  todayPnlKrw?: number;
  todayPnlPct?: number;
  positionCount?: number;
  /**
   * Cash percentage (0..100). Backend canonical key from
   * routes/portfolio.py:894 — `"cashPct": round(cash_pct, 2)`. Honest 0
   * on empty portfolio, real value on populated. The em-dash fallback
   * stays for the rare case the field is omitted (older snapshot, error
   * path).
   */
  cashPct?: number | null;
}
interface PositionsShape {
  positions?: Position[];
}

// Wave 4-B (2026-05-20): migrated to lib/fmtMoneyPlain — byte-identical
// (abs + ASCII "-" sign + KRW round / USD 2dp + "—" sentinel).
function fmtMoney(n: number | undefined, currency: "USD" | "KRW"): string {
  return fmtMoneyPlain(n, currency, currency === "KRW" ? 0 : 2);
}

function fmtSignedMoney(n: number | undefined, currency: "USD" | "KRW"): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : n < 0 ? "-" : "";
  const abs = Math.abs(n);
  const dec = currency === "KRW" ? 0 : 2;
  const body = abs.toLocaleString(currency === "KRW" ? "ko-KR" : "en-US", {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
  return `${sign}${currency === "KRW" ? "KRW " : "USD "}${body}`;
}

// fmtPct migrated to @/lib/format (2026-05-19 Wave 2 sweep).
// Local definition retired — lib/format.ts `fmtPct` is byte-identical
// for finite inputs and uses "—" sentinel on null/non-finite, matching
// the prior behaviour at every call site in this file.
//
// fmtMoney / fmtSignedMoney NOT migrated:
//  - fmtMoney uses ASCII hyphen for negatives; lib/fmtUsd is sign-implicit.
//  - fmtSignedMoney uses ASCII "-"; lib/fmtMoneySigned uses U+2212.
//  Both behaviour deltas are user-visible — kept inline to avoid regression.

/**
 * Build polyline + fill `points` strings from real equity data.
 * Width=200 / height=36 to match the existing viewBox so callers don't
 * need to re-layout. Returns null when fewer than 2 finite points are
 * available — the consumer should em-dash in that case rather than
 * render a single dot or extrapolate.
 */
function buildSparkPoints(
  series: EquityPoint[],
  width: number,
  height: number,
): { line: string; fill: string } | null {
  const navs = series
    .map((p) => p.nav)
    .filter((v): v is number => typeof v === "number" && Number.isFinite(v));
  if (navs.length < 2) return null;

  const min = Math.min(...navs);
  const max = Math.max(...navs);
  const span = max - min || 1;
  // Inset 4px top/bottom so the stroke isn't clipped at the viewBox edge.
  const padY = 4;
  const drawH = height - padY * 2;
  const xStep = width / (navs.length - 1);
  const toY = (v: number) => padY + (1 - (v - min) / span) * drawH;

  const line = navs
    .map((v, i) => `${(i * xStep).toFixed(1)},${toY(v).toFixed(1)}`)
    .join(" ");
  const fill = `${line} ${width.toFixed(1)},${height} 0,${height}`;
  return { line, fill };
}

export function PortfolioSnapshotCard() {
  const { data: summary } = usePortfolioSummary() as {
    data: SummaryShape | undefined;
  };
  const { data: posData } = usePortfolioPositions<PositionsShape>();
  // P0-2 fix 2026-05-19: wire the sparkline to the real equity history.
  // 1-month window keeps the card responsive (small payload) and matches
  // the "today snapshot" framing of the card. 60s dedupe in hooks-v2.
  const { data: equity } = useEquityCurve("1mo");
  const equitySeries: EquityPoint[] = React.useMemo(() => {
    const raw = equity?.series ?? [];
    return raw.filter(
      (p): p is EquityPoint =>
        p != null && typeof p.nav === "number" && Number.isFinite(p.nav),
    );
  }, [equity]);
  const sparkGeom = React.useMemo(
    () => buildSparkPoints(equitySeries, 200, 36),
    [equitySeries],
  );

  const positions = posData?.positions ?? [];
  const currency: "USD" | "KRW" =
    positions.length > 0 && positions.every((p) => p.currency === "KRW")
      ? "KRW"
      : "USD";

  // Cash % — read from backend's `cashPct` field (routes/portfolio.py:894).
  // Backend computes as `cash_usd_total / equity_usd * 100` so it includes
  // free margin / FX, which we'd otherwise diverge from if we re-derived
  // client-side. Em-dash on missing/non-finite for older snapshots.
  const cashPct: number | null =
    summary?.cashPct != null && Number.isFinite(summary.cashPct)
      ? summary.cashPct
      : null;

  // Native-currency stock subtotals — show US (USD) and KR (KRW) separately
  // instead of one unified USD NAV (CEO 2026-05-24). Prefer backend fields,
  // but DERIVE from positions when the backend value is missing/0 so a KR
  // holder always sees the ₩ subtotal even if the summary's KR detection
  // misses a position or the response is stale.
  const { navUsdDerived, navKrwDerived } = React.useMemo(() => {
    let u = 0;
    let k = 0;
    for (const p of positions) {
      const pp = p as Position & {
        market_value?: number;
        current?: number;
        shares?: number;
        currency?: string;
      };
      const mv = pp.market_value ?? (pp.current ?? 0) * (pp.shares ?? 0);
      if (!Number.isFinite(mv)) continue;
      if (pp.currency === "KRW") k += mv;
      else u += mv;
    }
    return { navUsdDerived: u, navKrwDerived: k };
  }, [positions]);
  const navUsd =
    typeof summary?.navUsd === "number" && summary.navUsd > 0
      ? summary.navUsd
      : navUsdDerived;
  const navKrw =
    typeof summary?.navKrw === "number" && summary.navKrw > 0
      ? summary.navKrw
      : navKrwDerived;
  const hasUs = typeof navUsd === "number" && navUsd > 0;
  const hasKr = typeof navKrw === "number" && navKrw > 0;
  const hasSplitNav = hasUs && hasKr;
  const hasUsOnly = hasUs && !hasKr;
  const hasKrOnly = hasKr && !hasUs;
  const navTagStyle: React.CSSProperties = {
    fontSize: "var(--pq-text-eyebrow)",
    letterSpacing: "0.18em",
    color: "rgba(245, 240, 232, 0.45)",
    marginLeft: 8,
    textTransform: "uppercase",
  };

  const positionCount = summary?.positionCount ?? positions.length;
  const todayPct = summary?.todayPnlPct;

  // Today P/L — show the NATIVE figure for a single-market book. `summary.todayPnl`
  // is USD-unified; rendering it under a KRW label for a KR-only holder printed a
  // ~1380× wrong number (v52 FX-split regression). Mixed (US+KR) books keep the
  // existing unified-USD behavior since there's only one P/L line here.
  const todayPnlNative: number | undefined = hasKrOnly
    ? summary?.todayPnlKrw
    : hasUsOnly
      ? (summary?.todayPnlUsd ?? summary?.todayPnl)
      : summary?.todayPnl;
  // Sign color from the native figure for single-market books (so a KRW loss is
  // colored by the ₩ sign, not the unified-USD one); fall back to the pct color.
  const deltaColor =
    hasKrOnly || hasUsOnly
      ? pctColor(
          todayPnlNative != null && Number.isFinite(todayPnlNative)
            ? todayPnlNative
            : (todayPct ?? null),
        )
      : pctColor(todayPct ?? null);

  return (
    <HomeCard
      href="/portfolio"
      eyebrow="Portfolio · NAV"
      cornerCta="Open Book ›"
    >
      {/* NAV value — show US holdings (USD) and KR holdings (KRW) separately
          rather than unifying into one USD figure (CEO 2026-05-24). Falls
          back to the single unified NAV when only one market is held (or on
          an older backend that doesn't emit the native subtotals yet). */}
      {hasSplitNav ? (
        <div style={{ marginBottom: 4 }}>
          <div
            className="font-mono"
            style={{
              fontVariantNumeric: "tabular-nums",
              fontSize: "var(--pq-text-h3)",
              letterSpacing: "-0.02em",
              color: "var(--pq-ivory)",
              fontWeight: 500,
              lineHeight: 1.2,
            }}
          >
            {fmtMoney(navUsd, "USD")}
            <span style={navTagStyle}>US</span>
          </div>
          <div
            className="font-mono"
            style={{
              fontVariantNumeric: "tabular-nums",
              fontSize: "var(--pq-text-h3)",
              letterSpacing: "-0.02em",
              color: "var(--pq-ivory)",
              fontWeight: 500,
              lineHeight: 1.2,
            }}
          >
            {fmtMoney(navKrw, "KRW")}
            <span style={navTagStyle}>KR</span>
          </div>
        </div>
      ) : (
        <div
          className="font-mono"
          style={{
            fontVariantNumeric: "tabular-nums",
            fontSize: "var(--pq-text-avatar)",
            letterSpacing: "-0.02em",
            color: "var(--pq-ivory)",
            fontWeight: 500,
            marginBottom: 4,
          }}
        >
          {hasKrOnly
            ? fmtMoney(navKrw, "KRW")
            : hasUsOnly
              ? fmtMoney(navUsd, "USD")
              : fmtMoney(summary?.totalNav, currency)}
        </div>
      )}

      {/* Delta */}
      <div
        className="font-mono"
        style={{
          fontVariantNumeric: "tabular-nums",
          fontSize: "var(--pq-text-body)",
          color: deltaColor,
          marginBottom: 28,
        }}
      >
        {fmtSignedMoney(todayPnlNative, currency)}{" "}
        <span style={{ opacity: 0.7 }}>{fmtPct(todayPct)} today</span>
      </div>

      {/* Live equity sparkline — 1-month window. Em-dash row on empty
          history so we never fabricate a path (P0-2 fix). */}
      {sparkGeom ? (
        <svg
          viewBox="0 0 200 36"
          preserveAspectRatio="none"
          style={{ width: "100%", height: 36, display: "block", marginBottom: 24 }}
          aria-label="Portfolio NAV — last 30 days"
          role="img"
        >
          <defs>
            <linearGradient id="pq-snap-bronze" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="rgba(184,149,106,0.22)" />
              <stop offset="100%" stopColor="rgba(184,149,106,0)" />
            </linearGradient>
          </defs>
          <polygon fill="url(#pq-snap-bronze)" stroke="none" points={sparkGeom.fill} />
          <polyline
            fill="none"
            stroke="var(--pq-bronze)"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={sparkGeom.line}
          />
        </svg>
      ) : (
        <div
          className="font-mono"
          style={{
            width: "100%",
            height: 36,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "rgba(245, 240, 232, 0.4)",
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            textTransform: "uppercase",
            marginBottom: 24,
          }}
          aria-label="Equity history unavailable"
        >
          —
        </div>
      )}

      {/* 3 mini KPIs */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: 8,
          marginTop: "auto",
        }}
      >
        <div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "rgba(245, 240, 232, 0.6)",
              textTransform: "uppercase",
            }}
          >
            Today P/L
          </div>
          <div
            className="font-mono"
            style={{
              fontVariantNumeric: "tabular-nums",
              fontSize: "var(--pq-text-body)",
              color: deltaColor,
              marginTop: 2,
            }}
          >
            {fmtSignedMoney(todayPnlNative, currency)}
          </div>
        </div>
        <div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "rgba(245, 240, 232, 0.6)",
              textTransform: "uppercase",
            }}
          >
            Positions
          </div>
          <div
            className="font-mono"
            style={{
              fontVariantNumeric: "tabular-nums",
              fontSize: "var(--pq-text-body)",
              color: "var(--pq-ivory)",
              marginTop: 2,
            }}
          >
            {positionCount} open
          </div>
        </div>
        <div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "rgba(245, 240, 232, 0.6)",
              textTransform: "uppercase",
            }}
          >
            Cash %
          </div>
          <div
            className="font-mono"
            style={{
              fontVariantNumeric: "tabular-nums",
              fontSize: "var(--pq-text-body)",
              color:
                cashPct != null ? "var(--pq-ivory)" : PRICE_COLOR_HEX.flat,
              marginTop: 2,
            }}
          >
            {cashPct != null ? `${cashPct.toFixed(1)}%` : "—"}
          </div>
        </div>
      </div>
    </HomeCard>
  );
}

export default PortfolioSnapshotCard;
