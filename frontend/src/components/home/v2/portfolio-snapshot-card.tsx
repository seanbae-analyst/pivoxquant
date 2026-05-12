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
 * The bronze inline-SVG sparkline is decorative — there is no `useEquityCurve`
 * hook yet (SPEC GAP). It's a static sigil so the card composition lands.
 */

import * as React from "react";
import { HomeCard } from "./home-card";
import { usePortfolioSummary, usePortfolioPositions } from "@/lib/hooks";
import { pctColor, PRICE_COLOR_HEX } from "@/lib/format";
import type { Position } from "@/components/portfolio/types";

interface SummaryShape {
  totalNav?: number;
  todayPnl?: number;
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

function fmtMoney(n: number | undefined, currency: "USD" | "KRW"): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  const dec = currency === "KRW" ? 0 : 2;
  const body = abs.toLocaleString(currency === "KRW" ? "ko-KR" : "en-US", {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
  return `${sign}${currency === "KRW" ? "₩" : "$"}${body}`;
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
  return `${sign}${currency === "KRW" ? "₩" : "$"}${body}`;
}

function fmtPct(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

export function PortfolioSnapshotCard() {
  const { data: summary } = usePortfolioSummary() as {
    data: SummaryShape | undefined;
  };
  const { data: posData } = usePortfolioPositions<PositionsShape>();

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

  const positionCount = summary?.positionCount ?? positions.length;
  const todayPnl = summary?.todayPnl;
  const todayPct = summary?.todayPnlPct;
  const deltaColor = pctColor(todayPct ?? null);

  return (
    <HomeCard
      href="/portfolio"
      eyebrow="Portfolio · NAV"
      cornerCta="Open Book ›"
    >
      {/* NAV value */}
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
        {fmtMoney(summary?.totalNav, currency)}
      </div>

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
        {fmtSignedMoney(todayPnl, currency)}{" "}
        <span style={{ opacity: 0.7 }}>{fmtPct(todayPct)} today</span>
      </div>

      {/* Decorative bronze sparkline (no live equity-curve hook yet) */}
      <svg
        viewBox="0 0 200 36"
        preserveAspectRatio="none"
        style={{ width: "100%", height: 36, display: "block", marginBottom: 24 }}
        aria-hidden
      >
        <polyline
          fill="none"
          stroke="rgba(245, 240, 232, 0.6)"
          strokeWidth="1.4"
          points="0,28 14,26 28,29 42,22 56,24 70,18 84,20 98,15 112,17 126,11 140,14 154,9 168,12 182,7 196,10"
        />
        <polyline
          fill="rgba(184,149,106,0.06)"
          stroke="none"
          points="0,28 14,26 28,29 42,22 56,24 70,18 84,20 98,15 112,17 126,11 140,14 154,9 168,12 182,7 196,10 196,36 0,36"
        />
      </svg>

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
            {fmtSignedMoney(todayPnl, currency)}
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
