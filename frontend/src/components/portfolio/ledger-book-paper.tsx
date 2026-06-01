"use client";

/**
 * <LedgerBookPaper /> — Paper 1 on /portfolio.
 *
 * The "book of record." Editorial 4-stat header + full positions table.
 * Unlike the /home PositionsLedgerPaper, this sheet shows every row with
 * the full action column (+ / − / ✎ / × on hover) and keeps KRW rows
 * alongside USD rows without hiding or truncating.
 *
 * Pure presentation:
 *  - consumes Position[] + a precomputed totals object
 *  - calls `onAction(action, position)` to delegate CRUD to the parent
 *    (which owns the existing TradeModal / AddPositionModal).
 *
 * Legal: no BUY/SELL/HOLD pills on positions. CRUD buttons use glyphs
 * with aria-labels ("Record additional buy", "Record sale", "Edit
 * recorded entry", "Remove recorded entry") — user-entered record.
 */

import * as React from "react";
import { useRouter } from "next/navigation";
import { PriceWithTimestamp } from "@/components/ui/price-with-timestamp";
import type { Position, TradeAction } from "@/components/portfolio/types";
import { fmtPct, displayTicker, normalizeTicker } from "@/lib/format";

interface Totals {
  totalNav: number;
  todayPnl: number;
  todayPnlPct: number;
  unrealized: number;
  realizedYtd: number;
  // null when neither the portfolio summary endpoint nor the live /api/market/fx
  // feed has a fresh USD/KRW rate. Mixed-currency math elides KRW positions
  // rather than fabricate a USD figure with a stale literal (was FX_FALLBACK=1342).
  fxRate: number | null;
}

interface Props {
  positions: Position[];
  totals: Totals;
  bookCurrency?: "USD" | "KRW";
  observedAgo?: string | null;
  onAddPosition: () => void;
  onAction: (action: TradeAction, p: Position) => void;
  /** Optional delete hook; parent may pass null to hide the × glyph. */
  onDelete?: (p: Position) => void;
}

/* ── Paper-scope formatters (dark-on-ivory, editorial) ── */

// eslint-disable-next-line no-restricted-syntax -- local fmt* helper kept per Wave 2/4-B sweep (delegates to, or intentionally diverges from, @/lib/format); see adjacent note
function fmtMoneyBig(v: number | null | undefined, cur: "USD" | "KRW"): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (cur === "KRW") return "KRW " + Math.round(v).toLocaleString();
  return (
    "USD " +
    v.toLocaleString(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    })
  );
}
// eslint-disable-next-line no-restricted-syntax -- local fmt* helper kept per Wave 2/4-B sweep (delegates to, or intentionally diverges from, @/lib/format); see adjacent note
function fmtMoneyCell(v: number, cur: "USD" | "KRW"): string {
  if (cur === "KRW") return "KRW " + Math.round(v).toLocaleString();
  return (
    "USD " +
    v.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}
// fmtPctSigned migrated to lib/fmtPct (2026-05-19 Wave 2 sweep).
// Behaviour byte-identical: same `v >= 0 ? "+"` sign rule, toFixed(2),
// "—" sentinel on non-finite. lib accepts null/undefined too, which is
// a superset of the old signature so all callers stay safe.
const fmtPctSigned = fmtPct;

function toneClass(v: number): string {
  if (v > 0.005) return "pq-paper-pos";
  if (v < -0.005) return "pq-paper-neg";
  return "pq-paper-neu";
}

/* ── Component ── */

export function LedgerBookPaper({
  positions,
  totals,
  bookCurrency = "USD",
  observedAgo,
  onAddPosition,
  onAction,
  onDelete,
}: Props) {
  const router = useRouter();

  // Stats on the hero. NAV is USD-normalised from backend.
  const stats: Array<{ label: string; value: string; sub?: string; tone?: string }> = [
    {
      label: `Book Value · ${bookCurrency}`,
      value: fmtMoneyBig(totals.totalNav, bookCurrency),
      sub:
        bookCurrency === "USD" && totals.fxRate && totals.fxRate > 0
          ? "KRW " + Math.round(totals.totalNav * totals.fxRate).toLocaleString()
          : undefined,
    },
    {
      label: "Today · P&L",
      value: fmtMoneyBig(totals.todayPnl, bookCurrency),
      sub: fmtPctSigned(totals.todayPnlPct ?? 0),
      tone: toneClass(totals.todayPnl ?? 0),
    },
    {
      label: "Unrealized",
      value: fmtMoneyBig(totals.unrealized, bookCurrency),
      tone: toneClass(totals.unrealized ?? 0),
    },
    {
      label: "Positions Held",
      value: String(positions.length),
    },
  ];

  // Sort: USD by abs pnl%, then KRW — but render every row, never truncate.
  const sorted = [...positions].sort((a, b) => {
    if ((a.currency ?? "USD") !== (b.currency ?? "USD")) {
      return (a.currency ?? "USD") === "KRW" ? 1 : -1;
    }
    const ap = a.avgCost > 0 ? (a.current - a.avgCost) / a.avgCost : 0;
    const bp = b.avgCost > 0 ? (b.current - b.avgCost) / b.avgCost : 0;
    return Math.abs(bp) - Math.abs(ap);
  });

  const kicker = observedAgo
    ? `PORTFOLIO · LEDGER · observed ${observedAgo}`
    : "PORTFOLIO · LEDGER · BOOK OF RECORD";

  return (
    <div
      style={{
        padding: "clamp(28px, 4vw, 56px)",
        display: "flex",
        flexDirection: "column",
        gap: 28,
        minHeight: 640,
        position: "relative",
      }}
    >
      {/* Header row — kicker + add CTA */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="pq-paper-kicker">{kicker}</div>
        <button
          type="button"
          onClick={onAddPosition}
          aria-label="Add a new position to the book"
          className="pq-paper-kicker"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.24em",
            color: "#B8956A",
            background: "transparent",
            border: "0.5px solid rgba(184,149,106,0.55)",
            padding: "7px 14px",
            borderRadius: 2,
            cursor: "pointer",
            textTransform: "uppercase",
            fontWeight: 600,
            transition: "background 180ms ease, color 180ms ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(184,149,106,0.1)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
          }}
        >
          + Add to book →
        </button>
      </div>

      {/* Hero title */}
      <h1 className="pq-paper-hero-title" style={{ maxWidth: "12ch" }}>
        The book.
      </h1>

      <p
        className="pq-paper-body"
        style={{ maxWidth: "58ch", marginTop: -8, fontSize: "var(--pq-text-lead)" }}
      >
        Positions, cost basis, and observed performance across your two
        markets. User-entered record only — not investment advice.
      </p>

      {/* 4-stat grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 20,
          paddingTop: 8,
          paddingBottom: 4,
          borderTop: "0.5px solid rgba(184,149,106,0.32)",
          borderBottom: "0.5px solid rgba(184,149,106,0.22)",
          paddingInline: 0,
          marginBlock: 4,
        }}
      >
        {stats.map((s) => (
          <div key={s.label} style={{ padding: "16px 0" }}>
            <div
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.26em",
                textTransform: "uppercase",
                color: "#B8956A",
                marginBottom: 8,
                fontWeight: 600,
              }}
            className="font-sans" >
              {s.label}
            </div>
            <div
              className={`font-serif ${s.tone ?? ""}`}
              style={{
                fontSize: "clamp(1.6rem, 3vw, 2rem)",
                lineHeight: 1.05,
                letterSpacing: "-0.02em",
                color: s.tone ? undefined : "#1a1a1a",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {s.value}
            </div>
            {s.sub && (
              <div
                className={`font-mono ${s.tone ?? ""}`}
                style={{
                  marginTop: 4,
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.02em",
                  color: s.tone ? undefined : "rgba(20,20,20,0.48)",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {s.sub}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Positions table */}
      <div style={{ marginTop: 4 }}>
        <div className="flex items-baseline justify-between" style={{ marginBottom: 10 }}>
          <div
            style={{
              fontSize: "clamp(1rem, 1.6vw, 1.125rem)",
              color: "#1a1a1a",
              letterSpacing: "-0.005em",
            }}
          className="font-serif" >
            Positions
          </div>
          <div
            className="pq-paper-kicker"
            style={{ fontSize: "var(--pq-text-kicker)", color: "rgba(20,20,20,0.48)" }}
          >
            {positions.length} held
          </div>
        </div>

        {sorted.length === 0 ? (
          <p
            className="pq-paper-body"
            style={{
              color: "rgba(20,20,20,0.55)",
              fontSize: "var(--pq-text-body)",
              padding: "32px 0",
              textAlign: "center",
            }}
          >
            No positions observed in this book yet. Use{" "}
            <span style={{ color: "#B8956A" }}>+ Add to book</span> to begin
            recording.
          </p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                minWidth: 780,
                borderCollapse: "collapse",
              }}
            >
              <colgroup>
                {/* Widened market-value + unrealized cols so 7-digit KRW
                    values (KRW 1,389,100 etc.) don't truncate to "KRW 1,". */}
                <col style={{ width: "22%" }} />
                <col style={{ width: "8%" }} />
                <col style={{ width: "11%" }} />
                <col style={{ width: "12%" }} />
                <col style={{ width: "14%" }} />
                <col style={{ width: "14%" }} />
                <col style={{ width: "13%" }} />
                <col style={{ width: "6%" }} />
              </colgroup>
              <thead>
                <tr>
                  {[
                    { l: "Name", a: "left" },
                    { l: "Side", a: "left" },
                    { l: "Qty", a: "right" },
                    { l: "Avg cost", a: "right" },
                    { l: "Last", a: "right" },
                    { l: "Market value", a: "right" },
                    { l: "Δ / %", a: "right" },
                    { l: "", a: "right" },
                  ].map((h, i) => (
                    <th
                      key={i}
                      className="pq-paper-kicker"
                      style={{
                        textAlign: h.a as "left" | "right",
                        padding: "0 6px 10px 6px",
                        borderBottom: "0.5px solid rgba(184,149,106,0.32)",
                        fontSize: "var(--pq-text-kicker)",
                      }}
                    >
                      {h.l}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((p) => {
                  const cur: "USD" | "KRW" = p.currency === "KRW" ? "KRW" : "USD";
                  const mv = p.shares * p.current;
                  const unreal = (p.current - p.avgCost) * p.shares;
                  const unrealPct =
                    p.avgCost > 0
                      ? ((p.current - p.avgCost) / p.avgCost) * 100
                      : 0;
                  const tone = toneClass(unrealPct);
                  const openDetail = () => router.push(`/detail/${p.symbol}`);
                  return (
                    <tr
                      key={p.id}
                      className="pq-paper-row pq-ledger-row"
                      tabIndex={0}
                      role="link"
                      aria-label={`Open ${p.symbol} detail`}
                      onClick={openDetail}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          openDetail();
                        }
                      }}
                      style={{ cursor: "pointer" }}
                    >
                      <td style={{ padding: "14px 6px 14px 0" }}>
                        <div
                          style={{
                            fontSize: "var(--pq-text-lead)",
                            color: "#1a1a1a",
                            fontWeight: 500,
                            letterSpacing: "-0.005em",
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            maxWidth: 260,
                          }}
                        className="font-serif" >
                          {displayTicker(p.symbol, p.name)}
                        </div>
                        <div
                          style={{
                            fontSize: "var(--pq-text-eyebrow)",
                            color: "rgba(20,20,20,0.48)",
                            letterSpacing: "0.04em",
                            marginTop: 2,
                          }}
                        className="font-mono" >
                          {normalizeTicker(p.symbol)} · {cur} · {p.sector || "—"}
                        </div>
                      </td>
                      <td
                        style={{
                          padding: "14px 6px",
                          fontSize: "var(--pq-text-eyebrow)",
                          letterSpacing: "0.08em",
                          textTransform: "uppercase",
                          color: "rgba(20,20,20,0.6)",
                        }}
                      className="font-mono" >
                        {p.side}
                      </td>
                      <td
                        style={{
                          padding: "14px 6px",
                          textAlign: "right",
                          fontSize: "var(--pq-text-body)",
                          fontVariantNumeric: "tabular-nums",
                          color: "rgba(20,20,20,0.78)",
                        }}
                      className="font-mono" >
                        {p.shares.toLocaleString("en-US")}
                      </td>
                      <td
                        style={{
                          padding: "14px 6px",
                          textAlign: "right",
                          fontSize: "var(--pq-text-body)",
                          fontVariantNumeric: "tabular-nums",
                          color: "rgba(20,20,20,0.6)",
                        }}
                      className="font-mono" >
                        {fmtMoneyCell(p.avgCost, cur)}
                      </td>
                      <td
                        style={{
                          padding: "14px 6px",
                          textAlign: "right",
                          fontSize: "var(--pq-text-body)",
                          fontVariantNumeric: "tabular-nums",
                          color: "#1a1a1a",
                          fontWeight: 600,
                        }}
                      className="font-mono" >
                        <PriceWithTimestamp
                          price={p.current}
                          observedAt={p.observed_at}
                          currency={cur}
                          size="sm"
                        />
                      </td>
                      <td
                        style={{
                          padding: "14px 6px",
                          textAlign: "right",
                          fontSize: "var(--pq-text-body)",
                          fontVariantNumeric: "tabular-nums",
                          color: "rgba(20,20,20,0.78)",
                        }}
                      className="font-mono" >
                        {fmtMoneyCell(mv, cur)}
                      </td>
                      <td
                        className={`font-mono ${tone}`}
                        style={{
                          padding: "14px 6px",
                          textAlign: "right",
                          fontSize: "var(--pq-text-body)",
                          fontVariantNumeric: "tabular-nums",
                          fontWeight: 600,
                        }}
                      >
                        <div>{fmtMoneyCell(unreal, cur)}</div>
                        <div style={{ fontSize: "var(--pq-text-eyebrow)", opacity: 0.75, marginTop: 2 }}>
                          {fmtPctSigned(unrealPct)}
                        </div>
                      </td>
                      <td
                        style={{
                          padding: "14px 0 14px 6px",
                          textAlign: "right",
                          whiteSpace: "nowrap",
                        }}
                      >
                        <div
                          className="pq-ledger-actions"
                          style={{
                            display: "inline-flex",
                            gap: 8,
                            alignItems: "center",
                          }}
                        >
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onAction("buy", p);
                            }}
                            aria-label={`Record additional purchase for ${p.symbol}`}
                            title="Record additional purchase"
                            className="font-mono"
                            style={actionBtn}
                          >
                            +
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onAction("sell", p);
                            }}
                            aria-label={`Record sale for ${p.symbol}`}
                            title="Record sale"
                            className="font-mono"
                            style={actionBtn}
                          >
                            −
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onAction("edit", p);
                            }}
                            aria-label={`Edit recorded entry for ${p.symbol}`}
                            title="Edit recorded entry"
                            className="font-mono"
                            style={actionBtn}
                          >
                            ✎
                          </button>
                          {onDelete && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                onDelete(p);
                              }}
                              aria-label={`Remove recorded entry for ${p.symbol}`}
                              title="Remove recorded entry"
                              className="font-mono"
                              style={{ ...actionBtn, color: "rgba(163,74,74,0.7)" }}
                            >
                              ×
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Bronze Q seal */}
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

const actionBtn: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  width: 22,
  height: 22,
  border: "0.5px solid rgba(184,149,106,0.45)",
  background: "transparent",
  color: "#B8956A",
  fontSize: "var(--pq-text-eyebrow)",
  lineHeight: 1,
  cursor: "pointer",
  borderRadius: 2,
  transition: "background 150ms ease, color 150ms ease",
};

export default LedgerBookPaper;
