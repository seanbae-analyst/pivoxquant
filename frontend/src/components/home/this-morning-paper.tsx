"use client";

/**
 * <ThisMorningPaper /> — Paper 1 (hero editorial).
 *
 * Editorial headline + one-paragraph chapeau + giant italic portfolio
 * NAV + change sub-line + bronze wax seal (Q monogram).
 *
 * Props:
 *   - totalNav, todayPnl, todayPnlPct, positionCount, currency
 *   - brief (optional editorial body text from /api/brief/today, already
 *     scrubbed by the backend legal_filter)
 *
 * Legal: no BUY/SELL/HOLD language, "observed" framing. The brief body
 * comes from /api/brief/today which runs through the backend scrub. We
 * fall back to a hard-coded neutral line if the brief is unavailable.
 */

import * as React from "react";
import { CountUp } from "@/components/ui/count-up";
import { TickNumber } from "@/components/ui/tick-number";

interface Props {
  totalNav: number | null | undefined;
  todayPnl: number | null | undefined;
  todayPnlPct: number | null | undefined;
  positionCount: number;
  currency?: "USD" | "KRW";
  brief?: string | null;
  displayName?: string;
  active?: boolean;
}

function formatDate(d: Date): string {
  return d
    .toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "2-digit",
      weekday: "long",
    })
    .toUpperCase();
}

export function ThisMorningPaper({
  totalNav,
  todayPnl,
  todayPnlPct,
  positionCount,
  currency = "USD",
  brief,
  displayName,
  active = false,
}: Props) {
  const [now] = React.useState<Date>(() => new Date());
  const pnlSign = (todayPnl ?? 0) >= 0 ? "▲" : "▼";
  const pnlTone =
    todayPnlPct == null
      ? "pq-paper-neu"
      : todayPnlPct >= 0
      ? "pq-paper-pos"
      : "pq-paper-neg";
  const pctText =
    todayPnlPct == null
      ? "—"
      : `${todayPnlPct >= 0 ? "+" : ""}${todayPnlPct.toFixed(2)}%`;
  const pnlText =
    todayPnl == null
      ? "—"
      : currency === "KRW"
      ? `\u20A9${Math.round(Math.abs(todayPnl)).toLocaleString()}`
      : `$${Math.abs(todayPnl).toLocaleString(undefined, {
          minimumFractionDigits: 0,
          maximumFractionDigits: 0,
        })}`;

  const fallbackBrief = displayName
    ? `This is what the book looks like for ${displayName} as we open the day — one ledger, ${positionCount} position${positionCount === 1 ? "" : "s"} observed across two markets.`
    : `This is what the book looks like as we open the day — one ledger, ${positionCount} position${positionCount === 1 ? "" : "s"} observed across two markets.`;

  return (
    <div
      style={{
        padding: "clamp(28px, 4vw, 56px)",
        display: "flex",
        flexDirection: "column",
        gap: 24,
        minHeight: 520,
        position: "relative",
      }}
    >
      <div className="pq-paper-kicker">
        This Morning · Daily Dossier · {formatDate(now)}
      </div>

      <h1 className="pq-paper-hero-title" style={{ maxWidth: "14ch" }}>
        This morning.
      </h1>

      <p
        className="pq-paper-body"
        style={{
          maxWidth: "58ch",
          marginTop: 4,
        }}
      >
        {brief || fallbackBrief}
      </p>

      <div style={{ marginTop: "auto", paddingTop: 32 }}>
        <div
          style={{
            fontFamily: "var(--font-sans), system-ui, sans-serif",
            fontSize: "9.5px",
            letterSpacing: "0.28em",
            textTransform: "uppercase",
            color: "#8B6F47",
            marginBottom: 8,
            fontWeight: 600,
          }}
        >
          Total Book · {currency}
        </div>
        {active ? (
          <TickNumber
            value={totalNav}
            currency={currency}
            decimals={currency === "KRW" ? 0 : 2}
            className="pq-paper-hero-num"
          />
        ) : (
          <CountUp
            value={totalNav}
            currency={currency}
            decimals={currency === "KRW" ? 0 : 2}
            className="pq-paper-hero-num"
            storageKey={`home-total-nav:${currency}`}
          />
        )}

        <div
          className="pq-paper-body"
          style={{
            marginTop: 14,
            fontSize: 13.5,
            color: "rgba(20,20,20,0.62)",
            fontFamily: "var(--font-mono), ui-monospace, monospace",
            letterSpacing: "0.01em",
          }}
        >
          <span className={pnlTone} style={{ fontWeight: 600, marginRight: 10 }}>
            {pnlSign} {pnlText} ({pctText})
          </span>
          <span style={{ color: "rgba(20,20,20,0.48)" }}>
            today · {positionCount} position{positionCount === 1 ? "" : "s"} observed
          </span>
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          bottom: "clamp(22px, 3vw, 36px)",
          right: "clamp(22px, 3vw, 36px)",
        }}
        aria-hidden
      >
        <span className="pq-wax-seal">Q</span>
      </div>
    </div>
  );
}

export default ThisMorningPaper;
