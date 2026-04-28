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

  // Cash % — graceful fallback: if backend doesn't ship it, leave em-dash.
  // We don't compute from positions here to avoid divergence from the
  // backend's cash bucket (which may include free margin, FX, etc.).
  // TODO: surface cash bucket % once the backend snapshot exposes it.
  // Until then, render em-dash; v1 also did not surface this.
  const cashPct: number | null = null as number | null;

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
          fontFamily:
            '"JetBrains Mono","SF Mono",ui-monospace,monospace',
          fontVariantNumeric: "tabular-nums",
          fontSize: 28,
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
          fontFamily:
            '"JetBrains Mono","SF Mono",ui-monospace,monospace',
          fontVariantNumeric: "tabular-nums",
          fontSize: 12.5,
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
          stroke="var(--pq-bronze)"
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
              fontFamily:
                '"JetBrains Mono","SF Mono",ui-monospace,monospace',
              fontSize: 9.5,
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              textTransform: "uppercase",
            }}
          >
            Today P/L
          </div>
          <div
            className="font-mono"
            style={{
              fontFamily:
                '"JetBrains Mono","SF Mono",ui-monospace,monospace',
              fontVariantNumeric: "tabular-nums",
              fontSize: 14,
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
              fontFamily:
                '"JetBrains Mono","SF Mono",ui-monospace,monospace',
              fontSize: 9.5,
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              textTransform: "uppercase",
            }}
          >
            Positions
          </div>
          <div
            className="font-mono"
            style={{
              fontFamily:
                '"JetBrains Mono","SF Mono",ui-monospace,monospace',
              fontVariantNumeric: "tabular-nums",
              fontSize: 14,
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
              fontFamily:
                '"JetBrains Mono","SF Mono",ui-monospace,monospace',
              fontSize: 9.5,
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              textTransform: "uppercase",
            }}
          >
            Cash %
          </div>
          <div
            className="font-mono"
            style={{
              fontFamily:
                '"JetBrains Mono","SF Mono",ui-monospace,monospace',
              fontVariantNumeric: "tabular-nums",
              fontSize: 14,
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
