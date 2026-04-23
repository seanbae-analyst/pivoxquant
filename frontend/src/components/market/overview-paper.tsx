"use client";

/**
 * <OverviewPaper /> — Paper 1 for /market (front sheet).
 *
 * Editorial front-page of the "Morning Papers" gazette. One hero index
 * (the first in the region) quoted large and italic, plus a 5-index
 * micro-summary strip beneath. Reads on ivory paper, not ink.
 *
 * Pure presentation — consumes IndexQuote[] from the parent page which
 * already owns the SWR subscription. No data fetching, no legal text.
 *
 * Legal: observational language only. No BUY/SELL/HOLD. Sparklines use
 * ivory-tinted bronze/clay so the sheet reads as paper.
 */

import * as React from "react";
import type { IndexQuote } from "@/components/market/index-card";
import { fmtPct } from "@/lib/format";

interface Props {
  region: "US" | "KR";
  quotes: IndexQuote[];
  marketOpen: boolean;
  liveLabel: string;
  weekTag: string;
}

function fmtLevel(v: number, kind: IndexQuote["format"] = "en"): string {
  if (kind === "int") return Math.round(v).toLocaleString("en-US");
  if (kind === "kr") {
    return v.toLocaleString("ko-KR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  return v.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function PaperSparkline({
  points,
  isPositive,
  w = 320,
  h = 54,
}: {
  points: number[];
  isPositive: boolean;
  w?: number;
  h?: number;
}) {
  if (!points || points.length < 2) return null;
  const lo = Math.min(...points);
  const hi = Math.max(...points);
  const range = hi - lo || 1;
  const pad = 2;
  const step = (w - pad * 2) / (points.length - 1);
  const pts = points
    .map((v, i) => {
      const x = pad + i * step;
      const y = pad + ((hi - v) / range) * (h - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const stroke = isPositive ? "#4a7a52" : "#a34a4a";
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      width="100%"
      height={h}
      preserveAspectRatio="none"
      aria-label="30-day sparkline"
    >
      <polyline points={pts} fill="none" stroke={stroke} strokeWidth="1.25" />
    </svg>
  );
}

function MiniRow({ quote }: { quote: IndexQuote }) {
  const isPositive = quote.changePct >= 0;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr auto auto",
        alignItems: "baseline",
        gap: 12,
        padding: "10px 0",
        borderBottom: "0.5px solid rgba(184,149,106,0.22)",
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div
          className="pq-paper-kicker"
          style={{ fontSize: 9, letterSpacing: "0.22em" }}
        >
          {quote.symbol}
        </div>
        <div
          style={{
            fontFamily: "var(--font-serif), Georgia, serif",
            fontSize: 13,
            color: "#1a1a1a",
            marginTop: 2,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {quote.name}
        </div>
      </div>
      <div
        style={{
          fontFamily: "var(--font-mono), ui-monospace, monospace",
          fontVariantNumeric: "tabular-nums",
          fontSize: 14,
          color: "#141414",
          textAlign: "right",
        }}
      >
        {fmtLevel(quote.level, quote.format)}
      </div>
      <div
        className={isPositive ? "pq-paper-pos" : "pq-paper-neg"}
        style={{
          fontFamily: "var(--font-mono), ui-monospace, monospace",
          fontVariantNumeric: "tabular-nums",
          fontSize: 11.5,
          textAlign: "right",
          minWidth: 54,
        }}
      >
        {fmtPct(quote.changePct)}
      </div>
    </div>
  );
}

export function OverviewPaper({
  region,
  quotes,
  marketOpen,
  liveLabel,
  weekTag,
}: Props) {
  const hero = quotes[0];
  const rest = quotes.slice(0, 5);

  if (!hero) {
    return (
      <div style={{ padding: "clamp(24px, 3vw, 40px)", minHeight: 320 }}>
        <div className="pq-paper-kicker">Morning Papers</div>
        <p className="pq-paper-body" style={{ marginTop: 16, }}>
          No observation available for this region.
        </p>
      </div>
    );
  }

  const heroPositive = hero.changePct >= 0;
  const regionLabel = region === "US" ? "United States" : "Korea";

  return (
    <div
      style={{
        padding: "clamp(28px, 3.5vw, 48px)",
        minHeight: 420,
        display: "flex",
        flexDirection: "column",
        gap: 20,
      }}
    >
      {/* Masthead */}
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 16,
          borderBottom: "0.5px solid rgba(184,149,106,0.3)",
          paddingBottom: 10,
          flexWrap: "wrap",
        }}
      >
        <div>
          <div className="pq-paper-kicker">
            Morning Papers &middot; {regionLabel}
          </div>
          <div
            style={{
              fontFamily: "var(--font-serif), Georgia, serif",
              fontSize: 13,
              color: "rgba(20,20,20,0.55)",
              marginTop: 3,
            }}
          >
            Levels as observed at last print.
          </div>
        </div>
        <div
          style={{
            fontFamily: "var(--font-mono), ui-monospace, monospace",
            fontSize: 10,
            textTransform: "uppercase",
            letterSpacing: "0.22em",
            color: "rgba(20,20,20,0.55)",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <span
            aria-hidden
            style={{
              display: "inline-block",
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: marketOpen ? "#4a7a52" : "rgba(20,20,20,0.35)",
            }}
          />
          <span>{liveLabel}</span>
          <span style={{ opacity: 0.4 }}>&middot;</span>
          <span>{weekTag}</span>
        </div>
      </div>

      {/* Hero headline — the first index */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) auto",
          alignItems: "flex-end",
          gap: 24,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div className="pq-paper-kicker">Headline Index</div>
          <h2
            style={{
              fontFamily: "var(--font-serif), Georgia, serif",
              fontWeight: 400,
              fontSize: "clamp(1.75rem, 3.2vw, 2.6rem)",
              lineHeight: 1.08,
              letterSpacing: "-0.02em",
              color: "#141414",
              margin: "6px 0 4px",
            }}
          >
            {hero.name}
          </h2>
          <div
            style={{
              fontFamily: "var(--font-mono), ui-monospace, monospace",
              fontSize: 10,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "rgba(20,20,20,0.55)",
            }}
          >
            {hero.symbol}
            {hero.is_stale ? " · stale" : ""}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div
            className="pq-paper-hero-num"
            style={{
              fontSize: "clamp(2.4rem, 5.2vw, 3.6rem)",
              }}
          >
            {fmtLevel(hero.level, hero.format)}
            {hero.unit ? (
              <span
                style={{
                  fontSize: "0.45em",
                  marginLeft: 6,
                  color: "rgba(20,20,20,0.55)",
                  fontStyle: "normal",
                }}
              >
                {hero.unit}
              </span>
            ) : null}
          </div>
          <div
            className={heroPositive ? "pq-paper-pos" : "pq-paper-neg"}
            style={{
              fontFamily: "var(--font-mono), ui-monospace, monospace",
              fontVariantNumeric: "tabular-nums",
              fontSize: 14,
              marginTop: 4,
            }}
          >
            {fmtPct(hero.changePct)} &middot; 1D
          </div>
        </div>
      </div>

      {/* Hero sparkline */}
      <div
        style={{
          borderTop: "0.5px solid rgba(184,149,106,0.22)",
          borderBottom: "0.5px solid rgba(184,149,106,0.22)",
          padding: "12px 0",
        }}
      >
        <PaperSparkline points={hero.spark} isPositive={heroPositive} h={64} />
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontFamily: "var(--font-mono), ui-monospace, monospace",
            fontSize: 10,
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            color: "rgba(20,20,20,0.55)",
            marginTop: 6,
          }}
        >
          <span>30-day observation</span>
          <span>
            52W {fmtLevel(hero.weekLow52, hero.format)} &middot;{" "}
            {fmtLevel(hero.weekHigh52, hero.format)}
          </span>
        </div>
      </div>

      {/* Mini 5-index summary */}
      <div>
        <div className="pq-paper-kicker" style={{ marginBottom: 6 }}>
          At-a-glance &middot; {regionLabel}
        </div>
        <div>
          {rest.map((q) => (
            <MiniRow key={q.symbol} quote={q} />
          ))}
        </div>
      </div>
    </div>
  );
}

export default OverviewPaper;
