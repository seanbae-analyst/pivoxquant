"use client";

/**
 * <IndicesDetailPaper /> — Paper 2 for /market (mid sheet).
 *
 * The full index table rendered on ivory: level, 1D %, 30-day sparkline,
 * 52W range marker, observed-at timestamp. KR tab also carries a small
 * derivatives block underneath.
 *
 * Pure presentation. Consumes IndexQuote[] and optional derivatives rows.
 * Observational language only — no BUY/SELL/HOLD.
 */

import * as React from "react";
import type { IndexQuote } from "@/components/market/index-card";
import {
  relativeTime,
  useNowTick,
  proxyLabel,
} from "@/components/market/index-card";
import { fmtPct } from "@/lib/format";
import { isMarketOpen } from "@/lib/market-hours";

/** Simple domestic futures/options summary rows. Sourced from backend
 *  when available — never fabricated locally. */
export interface DerivativeRow {
  label: string;
  value: string;
  note: string;
}

/**
 * Proxy badge pill — mirrors the one in overview-paper.tsx. Rendered on
 * the detail row when `proxy_ticker` is set so the reader can't mistake
 * the ETF price (e.g. SPY 708.45) for the index level (S&P 500 ≈ 7108).
 */
function ProxyPillSmall({ proxy }: { proxy: string }) {
  return (
    <span
      role="note"
      aria-label={`Level sourced via ${proxy} ETF proxy`}
      title={`Level via ${proxy} ETF proxy — not the underlying index level.`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 3,
        fontSize: "var(--pq-text-kicker)",
        letterSpacing: "0.18em",
        textTransform: "uppercase",
        color: "#8b6f47",
        border: "0.5px solid rgba(139,111,71,0.55)",
        background: "rgba(184,149,106,0.08)",
        padding: "1.5px 5px",
        borderRadius: 2,
        lineHeight: 1,
        whiteSpace: "nowrap",
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
  derivatives?: DerivativeRow[];
}

function fmtLevel(
  v: number | null | undefined,
  kind: IndexQuote["format"] = "en",
): string {
  if (v == null || !Number.isFinite(v)) return "—";
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

function InkSpark({
  points,
  isPositive,
}: {
  points: number[];
  isPositive: boolean;
}) {
  const w = 200;
  const h = 30;
  if (!points || points.length < 2) return null;
  const lo = Math.min(...points);
  const hi = Math.max(...points);
  const range = hi - lo || 1;
  const pad = 1;
  const step = (w - pad * 2) / (points.length - 1);
  const pts = points
    .map((v, i) => {
      const x = pad + i * step;
      const y = pad + ((hi - v) / range) * (h - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  // FINDING-015: match the KR-convention paper delta hues (pq-paper-pos red /
  // pq-paper-neg blue) so the sparkline and the % delta agree on direction.
  const stroke = isPositive ? "var(--pq-paper-pos)" : "var(--pq-paper-neg)";
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      width="100%"
      height={h}
      preserveAspectRatio="none"
    >
      <polyline points={pts} fill="none" stroke={stroke} strokeWidth="1.1" />
    </svg>
  );
}

function DetailRow({ quote }: { quote: IndexQuote }) {
  const isPositive = quote.changePct >= 0;
  const now = useNowTick(1000);
  const rel = relativeTime(quote.observed_at, now);
  const stale = Boolean(quote.is_stale);
  const marketOpenNow = isMarketOpen();

  // 2026-05-15: weekHigh52/Low52 are nullable (backend nulls when
  // upstream history lags — _kis_index_snapshot 15% guard). Treat
  // missing bounds as "centred marker" placeholder rather than
  // computing arithmetic on null.
  const _hi = quote.weekHigh52;
  const _lo = quote.weekLow52;
  const rangePct =
    _hi != null && _lo != null && Number.isFinite(_hi) && Number.isFinite(_lo) && _hi > _lo
      ? Math.max(
          0,
          Math.min(
            1,
            (quote.level - _lo) / (_hi - _lo),
          ),
        )
      : 0.5;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(140px, 1.2fr) minmax(100px, 1fr) minmax(160px, 1.4fr) minmax(140px, 1fr)",
        alignItems: "center",
        gap: 18,
        padding: "14px 0",
        borderBottom: "0.5px solid rgba(184,149,106,0.22)",
      }}
    >
      {/* Name + symbol */}
      <div style={{ minWidth: 0 }}>
        <div
          style={{
            fontSize: "var(--pq-text-body)",
            color: "#141414",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        className="font-serif" >
          {quote.name}
        </div>
        <div
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "rgba(20,20,20,0.55)",
            marginTop: 2,
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        className="font-mono" >
          <span>{quote.symbol}</span>
          {quote.observed_at ? (
            <>
              <span style={{ opacity: 0.45 }}>&middot;</span>
              <span>{rel}</span>
              {stale ? (
                <span
                  aria-label="Stale quote"
                  title="Quote has not refreshed recently"
                  style={{
                    display: "inline-block",
                    width: 5,
                    height: 5,
                    borderRadius: "50%",
                    background: "#c9a555",
                  }}
                />
              ) : marketOpenNow ? (
                <span
                  aria-label="Live"
                  title="Live"
                  className="pq-live-dot"
                  style={{
                    display: "inline-block",
                    width: 5,
                    height: 5,
                    borderRadius: "50%",
                    background: "#4a7a52",
                  }}
                />
              ) : null}
            </>
          ) : null}
        </div>
      </div>

      {/* Level + change */}
      <div style={{ textAlign: "right" }}>
        {quote.proxy_ticker ? (
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              marginBottom: 3,
            }}
          >
            <ProxyPillSmall proxy={quote.proxy_ticker} />
          </div>
        ) : null}
        <div
          style={{
            fontVariantNumeric: "tabular-nums",
            fontSize: "var(--pq-text-h5)",
            color: "#141414",
            letterSpacing: "-0.01em",
          }}
          title={
            quote.proxy_ticker
              ? `Level sourced from ${quote.proxy_ticker} ETF (data provider does not serve ${quote.symbol}). No ratio conversion applied.`
              : undefined
          }
        className="font-mono" >
          {fmtLevel(quote.level, quote.format)}
          {quote.unit ? (
            <span
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                marginLeft: 4,
                color: "rgba(20,20,20,0.5)",
              }}
            >
              {quote.unit}
            </span>
          ) : null}
        </div>
        <div
          className={`font-mono ${isPositive ? "pq-paper-pos" : "pq-paper-neg"}`}
          style={{
            fontVariantNumeric: "tabular-nums",
            fontSize: "var(--pq-text-eyebrow)",
            marginTop: 2,
          }}
        >
          {fmtPct(quote.changePct)}
        </div>
        {quote.proxy_ticker ? (
          <div
            style={{
              fontSize: "var(--pq-text-kicker)",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: "rgba(20,20,20,0.5)",
              marginTop: 2,
            }}
          className="font-mono" >
            {proxyLabel(quote.proxy_ticker)}
          </div>
        ) : null}
      </div>

      {/* Sparkline */}
      <div>
        <InkSpark points={quote.spark} isPositive={isPositive} />
      </div>

      {/* 52W range */}
      <div>
        <div
          style={{
            position: "relative",
            height: 3,
            background: "rgba(20,20,20,0.08)",
          }}
        >
          <div
            style={{
              position: "absolute",
              top: -2,
              left: `${rangePct * 100}%`,
              width: 2,
              height: 7,
              background: "var(--pq-bronze, #B8956A)",
            }}
          />
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginTop: 3,
            fontVariantNumeric: "tabular-nums",
            fontSize: "var(--pq-text-eyebrow)",
            color: "rgba(20,20,20,0.55)",
          }}
        className="font-mono" >
          <span>{fmtLevel(quote.weekLow52, quote.format)}</span>
          <span style={{ letterSpacing: "0.12em" }}>52W</span>
          <span>{fmtLevel(quote.weekHigh52, quote.format)}</span>
        </div>
      </div>
    </div>
  );
}

export function IndicesDetailPaper({ region, quotes, derivatives }: Props) {
  return (
    <div
      style={{
        padding: "clamp(28px, 3.5vw, 48px)",
        minHeight: 420,
        display: "flex",
        flexDirection: "column",
        gap: 18,
      }}
    >
      <div
        style={{
          borderBottom: "0.5px solid rgba(184,149,106,0.3)",
          paddingBottom: 8,
        }}
      >
        <div className="pq-paper-kicker">The Board</div>
        <h2
          style={{
            fontWeight: 400,
            fontSize: "clamp(1.4rem, 2.4vw, 1.9rem)",
            letterSpacing: "-0.01em",
            color: "#141414",
            margin: "4px 0 2px",
          }}
        className="font-serif" >
          {region === "US" ? "United States · Indices" : "Korea · Indices"}
        </h2>
        <div
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            color: "rgba(20,20,20,0.55)",
          }}
        className="font-serif" >
          Live observation &middot; refreshing as the tape prints.
        </div>
      </div>

      {/*
        2026-05-15 (bug-hunter P1, mobile-viewport): the column headers
        + each DetailRow share a 4-column grid with `minmax(140px, …) +
        minmax(100px, …) + minmax(160px, …) + minmax(140px, …)` —
        minimum total ≈ 540px. On a 375px iPhone viewport (with the
        paper's 28px padding either side ≈ 319px content), that
        overflows the viewport and pushes the 52-week range / sparkline
        columns off-screen. The same fix pattern as
        ledger-book-paper.tsx + positions-table-v2.tsx — wrap the
        grid in an `overflow-x: auto` container so users get horizontal
        scroll instead of clipped content. Desktop unaffected (column
        widths already fit). The wrapper carries the same minWidth on
        the inner block so headers + rows align identically when
        scrolled.
      */}
      <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch" }}>
        <div style={{ minWidth: 540 }}>
          {/* Column headers */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(140px, 1.2fr) minmax(100px, 1fr) minmax(160px, 1.4fr) minmax(140px, 1fr)",
              alignItems: "baseline",
              gap: 18,
              padding: "0 0 6px",
              borderBottom: "0.5px solid rgba(184,149,106,0.3)",
            }}
          >
            <span className="pq-paper-kicker" style={{ fontSize: "var(--pq-text-kicker)" }}>
              Index
            </span>
            <span
              className="pq-paper-kicker"
              style={{ fontSize: "var(--pq-text-kicker)", textAlign: "right" }}
            >
              Level &middot; 1D
            </span>
            <span className="pq-paper-kicker" style={{ fontSize: "var(--pq-text-kicker)" }}>
              30-day observation
            </span>
            <span className="pq-paper-kicker" style={{ fontSize: "var(--pq-text-kicker)" }}>
              52-week range
            </span>
          </div>

          <div>
            {quotes.length > 0 ? (
              quotes.map((q) => <DetailRow key={q.symbol} quote={q} />)
            ) : (
              <p
                style={{
                  fontSize: "var(--pq-text-body)",
                  fontStyle: "italic",
                  color: "rgba(20,20,20,0.55)",
                  padding: "20px 0",
                  margin: 0,
                }}
              className="font-serif" >
                Index data temporarily unavailable.
              </p>
            )}
          </div>
        </div>
      </div>

      {region === "KR" && derivatives && derivatives.length > 0 ? (
        <div style={{ marginTop: 12 }}>
          <div className="pq-paper-kicker" style={{ marginBottom: 6 }}>
            Derivatives &middot; KOSPI 200 summary
          </div>
          <div>
            {derivatives.map((row) => (
              <div
                key={row.label}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto auto",
                  alignItems: "baseline",
                  gap: 16,
                  padding: "10px 0",
                  borderBottom: "0.5px solid rgba(184,149,106,0.22)",
                }}
              >
                <span
                  style={{
                    fontSize: "var(--pq-text-body)",
                    color: "#1a1a1a",
                  }}
                className="font-serif" >
                  {row.label}
                </span>
                <span
                  style={{
                    fontVariantNumeric: "tabular-nums",
                    fontSize: "var(--pq-text-body)",
                    color: "#141414",
                  }}
                className="font-mono" >
                  {row.value}
                </span>
                <span
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    color: "rgba(20,20,20,0.55)",
                  }}
                className="font-mono" >
                  {row.note}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default IndicesDetailPaper;
