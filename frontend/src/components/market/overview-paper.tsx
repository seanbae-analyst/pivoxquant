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
import { proxyLabel } from "@/components/market/index-card";
import { fmtPct } from "@/lib/format";

/**
 * Proxy badge pill — bronze-outlined, mono "VIA <PROXY>" surfaced next to
 * any level that is actually the ETF price, not the underlying index. Used
 * both as an inline HEADLINE prefix (so the reader sees "VIA SPY · 708.45"
 * at a glance) and in the mini-summary strip. Only rendered when
 * `proxy_ticker` is set; KR indices and FX pairs never carry one, so the
 * badge is invisible for them (Bloomberg-style conditional render).
 */
function ProxyPill({
  proxy,
  size = "sm",
  title,
}: {
  proxy: string;
  size?: "sm" | "md";
  title?: string;
}) {
  const fontSize = size === "md" ? 11 : 9.5;
  const padY = size === "md" ? 3 : 2;
  const padX = size === "md" ? 7 : 5;
  return (
    <span
      role="note"
      aria-label={`Level sourced via ${proxy} ETF proxy`}
      title={title ?? `Level via ${proxy} ETF proxy — not the underlying index level.`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontSize,
        letterSpacing: "0.18em",
        textTransform: "uppercase",
        color: "#8b6f47",
        border: "0.5px solid rgba(139,111,71,0.55)",
        background: "rgba(184,149,106,0.08)",
        padding: `${padY}px ${padX}px`,
        borderRadius: 2,
        verticalAlign: "middle",
        lineHeight: 1,
        whiteSpace: "nowrap",
        fontStyle: "normal",
      }}
    className="font-mono" >
      <span style={{ opacity: 0.75 }}>via</span>
      <span style={{ fontWeight: 600 }}>{proxy}</span>
    </span>
  );
}

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
            fontSize: 13,
            color: "#1a1a1a",
            marginTop: 2,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        className="font-serif" >
          {quote.name}
        </div>
      </div>
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "flex-end",
          gap: 6,
          fontVariantNumeric: "tabular-nums",
          fontSize: 14,
          color: "#141414",
          textAlign: "right",
        }}
        title={
          quote.proxy_ticker
            ? `Level sourced from ${quote.proxy_ticker} ETF proxy.`
            : undefined
        }
      className="font-mono" >
        {quote.proxy_ticker ? <ProxyPill proxy={quote.proxy_ticker} size="sm" /> : null}
        <span>{fmtLevel(quote.level, quote.format)}</span>
      </div>
      <div
        className={`font-mono ${isPositive ? "pq-paper-pos" : "pq-paper-neg"}`}
        style={{
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
              fontSize: 13,
              color: "rgba(20,20,20,0.55)",
              marginTop: 3,
            }}
          className="font-serif" >
            Levels as observed at last print.
          </div>
        </div>
        <div
          style={{
            fontSize: 10,
            textTransform: "uppercase",
            letterSpacing: "0.22em",
            color: "rgba(20,20,20,0.55)",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        className="font-mono" >
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
              fontWeight: 400,
              fontSize: "clamp(1.75rem, 3.2vw, 2.6rem)",
              lineHeight: 1.08,
              letterSpacing: "-0.02em",
              color: "#141414",
              margin: "6px 0 4px",
            }}
          className="font-serif" >
            {hero.name}
          </h2>
          <div
            style={{
              fontSize: 10,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "rgba(20,20,20,0.55)",
            }}
          className="font-mono" >
            {hero.symbol}
            {hero.is_stale ? " · stale" : ""}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          {/* HEADLINE proxy badge — rendered ABOVE the number so the reader
              sees "VIA SPY" before they parse the level. Prevents the
              "708.45 = S&P 500 level" misread. Omitted entirely when the
              level is a direct observation (KR indices, FX pairs, or any
              symbol FMP serves natively). */}
          {hero.proxy_ticker ? (
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                marginBottom: 6,
              }}
            >
              <ProxyPill
                proxy={hero.proxy_ticker}
                size="md"
                title={`Level sourced from ${hero.proxy_ticker} ETF (FMP Starter tier does not serve ${hero.symbol}). No ratio conversion applied.`}
              />
            </div>
          ) : null}
          <div
            className="pq-paper-hero-num"
            style={{
              fontSize: "clamp(2.4rem, 5.2vw, 3.6rem)",
              }}
            title={
              hero.proxy_ticker
                ? `Level sourced from ${hero.proxy_ticker} ETF (FMP Starter tier does not serve ${hero.symbol}). No ratio conversion applied.`
                : undefined
            }
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
            className={`font-mono ${heroPositive ? "pq-paper-pos" : "pq-paper-neg"}`}
            style={{
              fontVariantNumeric: "tabular-nums",
              fontSize: 14,
              marginTop: 4,
            }}
          >
            {fmtPct(hero.changePct)} &middot; 1D
          </div>
          {hero.proxy_ticker ? (
            <div
              style={{
                fontSize: 10,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: "rgba(20,20,20,0.55)",
                marginTop: 4,
              }}
              title="Index level via ETF proxy — level is the ETF price, not the underlying index."
            className="font-mono" >
              {proxyLabel(hero.proxy_ticker)}
            </div>
          ) : null}
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
            fontSize: 10,
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            color: "rgba(20,20,20,0.55)",
            marginTop: 6,
          }}
        className="font-mono" >
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
