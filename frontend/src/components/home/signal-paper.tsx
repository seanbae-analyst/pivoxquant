"use client";

/**
 * <SignalPaper /> — Paper 3 (today's signal).
 *
 * Picks the single position with the largest absolute P&L% swing and
 * writes a one-sentence editorial observation on paper with a single
 * POSITIVE / NEGATIVE / NEUTRAL chip.
 *
 * Legal: strict "observed" framing. No BUY/SELL/HOLD. No "recommend",
 * "advice", or Korean equivalents.
 */

import * as React from "react";
import Link from "next/link";
import type { Position } from "@/components/portfolio/types";

interface Props {
  positions: Position[];
}

type Signal = "POSITIVE" | "NEUTRAL" | "NEGATIVE";

function signalFor(pnlPct: number): Signal {
  if (pnlPct > 0.5) return "POSITIVE";
  if (pnlPct < -0.5) return "NEGATIVE";
  return "NEUTRAL";
}

export function SignalPaper({ positions }: Props) {
  const withPnl = positions
    .map((p) => ({
      p,
      pnlPct:
        p.avgCost > 0 ? ((p.current - p.avgCost) / p.avgCost) * 100 : 0,
    }))
    .sort((a, b) => Math.abs(b.pnlPct) - Math.abs(a.pnlPct));

  const top = withPnl[0];

  if (!top) {
    return (
      <div
        style={{
          padding: "clamp(24px, 3vw, 40px)",
          minHeight: 320,
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <div className="pq-paper-kicker">Today&apos;s Signal</div>
        <p
          className="pq-paper-body"
          style={{
            color: "rgba(20,20,20,0.55)",
            fontSize: 14,
          }}
        >
          No observations recorded on this book yet. Signals surface as
          positions are opened and priced.
        </p>
      </div>
    );
  }

  const sig = signalFor(top.pnlPct);
  const toneColor =
    sig === "POSITIVE"
      ? "#4a7a52"
      : sig === "NEGATIVE"
      ? "#a54545"
      : "rgba(20,20,20,0.55)";

  const observation =
    sig === "POSITIVE"
      ? `Price divergence observed at ${top.p.name} — current quote sits ${top.pnlPct.toFixed(2)}% above cost basis.`
      : sig === "NEGATIVE"
      ? `Drawdown observed at ${top.p.name} — current quote sits ${Math.abs(top.pnlPct).toFixed(2)}% below cost basis.`
      : `Position at ${top.p.name} remains within observed band of cost basis (${top.pnlPct.toFixed(2)}%).`;

  return (
    <div
      style={{
        padding: "clamp(24px, 3vw, 40px)",
        minHeight: 320,
        display: "flex",
        flexDirection: "column",
        gap: 18,
      }}
    >
      <div className="flex items-center justify-between">
        <div className="pq-paper-kicker">Today&apos;s Signal</div>
        <Link
          href={`/detail/${top.p.symbol}`}
          className="pq-paper-kicker"
          style={{
            fontSize: 9,
            letterSpacing: "0.22em",
            color: "rgba(20,20,20,0.55)",
            textDecoration: "none",
          }}
        >
          Open file →
        </Link>
      </div>

      <div style={{ marginTop: 4 }}>
        <div
          style={{
            fontFamily: "var(--font-serif), Georgia, serif",
            fontSize: "clamp(1.5rem, 3vw, 2.25rem)",
            lineHeight: 1.1,
            color: "#1a1a1a",
            letterSpacing: "-0.02em",
          }}
        >
          {top.p.name}
        </div>
        <div
          style={{
            fontFamily: "var(--font-mono), ui-monospace, monospace",
            fontSize: 10,
            color: "rgba(20,20,20,0.48)",
            letterSpacing: "0.08em",
            marginTop: 4,
          }}
        >
          {top.p.symbol} · {top.p.sector || "—"}
        </div>
      </div>

      <p
        className="pq-paper-body"
        style={{
          fontSize: 14.5,
          maxWidth: "52ch",
          color: "rgba(20,20,20,0.82)",
        }}
      >
        {observation}
      </p>

      <div
        style={{
          marginTop: "auto",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "5px 12px",
            fontFamily: "var(--font-sans), system-ui, sans-serif",
            fontSize: 10,
            letterSpacing: "0.22em",
            textTransform: "uppercase",
            fontWeight: 600,
            color: toneColor,
            border: `0.5px solid ${toneColor}`,
            borderRadius: 2,
            background: "transparent",
          }}
        >
          {sig}
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono), ui-monospace, monospace",
            fontSize: 12,
            fontVariantNumeric: "tabular-nums",
            color: toneColor,
            fontWeight: 600,
          }}
        >
          {top.pnlPct >= 0 ? "+" : ""}
          {top.pnlPct.toFixed(2)}%
        </span>
        <span
          style={{
            fontFamily: "var(--font-serif), Georgia, serif",
            fontSize: 11.5,
            color: "rgba(20,20,20,0.45)",
          }}
        >
          · observed since entry
        </span>
      </div>
    </div>
  );
}

export default SignalPaper;
