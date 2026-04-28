"use client";

/**
 * <PositionsTableV2 /> — Bloomberg-grade ledger (mockup §BLOCK 2 / SPEC §3).
 *
 * 8 columns: Name / Shares / Avg Cost / Last / P/L % / Mkt Value / Weight / Sector.
 *
 * 종목명 main pattern (CEO directive 2026-04-26):
 *   Playfair 18px ivory NAME (primary)
 *   mono 10.5px dim TICKER (secondary, below name)
 *
 * Legal: Action column uses `Add` / `Trim` / `Close` only — never BUY/SELL.
 * Row click → /detail/[ticker]. Action buttons stop propagation.
 */

import * as React from "react";
import { useRouter } from "next/navigation";
import type { Position, TradeAction } from "@/components/portfolio/types";

type SortKey =
  | "name"
  | "shares"
  | "avgCost"
  | "last"
  | "plPct"
  | "value"
  | "weight"
  | "sector";

interface PositionsTableV2Props {
  positions: Position[];
  /** Total NAV in display currency for weight calc. */
  totalNav: number;
  /** FX rate used to normalize KRW positions to USD when totalNav is USD. */
  fxRate: number;
  /** Display currency for the running totals. */
  displayCurrency?: "USD" | "KRW";
  loading?: boolean;
  onAction?: (action: TradeAction, position: Position) => void;
  onAddPosition?: () => void;
}

function fmtMoney(n: number, currency: "USD" | "KRW"): string {
  if (!Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  const dec = currency === "KRW" ? 0 : 2;
  const body = abs.toLocaleString(currency === "KRW" ? "ko-KR" : "en-US", {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
  return `${sign}${currency === "KRW" ? "₩" : "$"}${body}`;
}

function fmtShares(n: number): string {
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  });
}

function fmtPctSigned(n: number): string {
  if (!Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${sign}${Math.abs(n).toFixed(2)}%`;
}

function pctColor(n: number): string {
  if (!Number.isFinite(n)) return "rgba(245,240,232,0.55)";
  if (n > 0) return "var(--pq-positive, #dc2626)";
  if (n < 0) return "var(--pq-negative, #2563eb)";
  return "rgba(245,240,232,0.55)";
}

interface DerivedPosition {
  raw: Position;
  pl: number;
  plPct: number;
  mv: number; // market value in own currency
  mvNormalized: number; // converted to display currency for weight calc
  weight: number; // 0..100
}

function derive(
  positions: Position[],
  totalNav: number,
  fxRate: number,
  displayCurrency: "USD" | "KRW",
): DerivedPosition[] {
  const safeTotal = totalNav > 0 ? totalNav : 1;
  return positions.map((p) => {
    const mv = p.shares * p.current;
    const cost = p.shares * p.avgCost;
    const pl = mv - cost;
    const plPct = cost > 0 ? (pl / cost) * 100 : 0;

    // Normalize market value to display currency for weight calc.
    let mvNormalized = mv;
    if (displayCurrency === "USD" && p.currency === "KRW") {
      mvNormalized = mv / (fxRate || 1);
    } else if (displayCurrency === "KRW" && p.currency !== "KRW") {
      mvNormalized = mv * (fxRate || 1);
    }
    const weight = (mvNormalized / safeTotal) * 100;

    return { raw: p, pl, plPct, mv, mvNormalized, weight };
  });
}

function sortRows(
  rows: DerivedPosition[],
  key: SortKey,
  dir: "asc" | "desc",
): DerivedPosition[] {
  const copy = [...rows];
  const m = dir === "asc" ? 1 : -1;
  copy.sort((a, b) => {
    switch (key) {
      case "name":
        return a.raw.name.localeCompare(b.raw.name) * m;
      case "shares":
        return (a.raw.shares - b.raw.shares) * m;
      case "avgCost":
        return (a.raw.avgCost - b.raw.avgCost) * m;
      case "last":
        return (a.raw.current - b.raw.current) * m;
      case "plPct":
        return (a.plPct - b.plPct) * m;
      case "value":
        return (a.mvNormalized - b.mvNormalized) * m;
      case "weight":
        return (a.weight - b.weight) * m;
      case "sector":
        return a.raw.sector.localeCompare(b.raw.sector) * m;
    }
  });
  return copy;
}

export function PositionsTableV2({
  positions,
  totalNav,
  fxRate,
  displayCurrency = "USD",
  loading,
  onAction,
  onAddPosition,
}: PositionsTableV2Props) {
  const router = useRouter();
  const [sortKey, setSortKey] = React.useState<SortKey>("weight");
  const [sortDir, setSortDir] = React.useState<"asc" | "desc">("desc");

  const rows = React.useMemo(
    () => sortRows(derive(positions, totalNav, fxRate, displayCurrency), sortKey, sortDir),
    [positions, totalNav, fxRate, displayCurrency, sortKey, sortDir],
  );

  function onSort(k: SortKey) {
    if (sortKey === k) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(k);
      setSortDir(k === "name" || k === "sector" ? "asc" : "desc");
    }
  }

  function ariaSort(k: SortKey): "ascending" | "descending" | "none" {
    if (sortKey !== k) return "none";
    return sortDir === "asc" ? "ascending" : "descending";
  }

  const headers: { key: SortKey; label: string; align: "left" | "right" }[] = [
    { key: "name", label: "Name", align: "left" },
    { key: "shares", label: "Shares", align: "right" },
    { key: "avgCost", label: "Avg cost", align: "right" },
    { key: "last", label: "Last", align: "right" },
    { key: "plPct", label: "P/L %", align: "right" },
    { key: "value", label: "Mkt value", align: "right" },
    { key: "weight", label: "Weight", align: "right" },
    { key: "sector", label: "Sector", align: "left" },
  ];

  return (
    <section aria-label="Positions" style={{ marginBottom: 40 }}>
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          marginBottom: 20,
        }}
      >
        <div>
          <div
            className="font-mono uppercase"
            style={{
              fontFamily:
                '"JetBrains Mono","SF Mono",ui-monospace,monospace',
              fontSize: 10.5,
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            Holdings · Ledger
          </div>
          <h2
            className="font-serif"
            style={{
              fontFamily: '"Playfair Display","Source Serif 4",Georgia,serif',
              fontWeight: 500,
              fontSize: 30,
              lineHeight: 1.1,
              letterSpacing: "var(--pq-track-tight, -0.02em)",
              color: "var(--pq-ivory)",
              margin: 0,
            }}
          >
            Every line, every weight.
          </h2>
        </div>
        <span
          className="font-mono uppercase"
          style={{
            fontFamily: '"JetBrains Mono","SF Mono",ui-monospace,monospace',
            fontSize: 9.5,
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.40)",
          }}
        >
          {rows.length} {rows.length === 1 ? "row" : "rows"}
        </span>
      </div>

      <div
        className="pq-card"
        style={{
          background: "var(--pq-card-bg-ink, rgba(255,255,255,0.02))",
          border: "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.08))",
          borderRadius: "var(--pq-radius-card, 4px)",
          overflow: "hidden",
        }}
      >
        {loading && rows.length === 0 ? (
          <div
            role="status"
            aria-live="polite"
            style={{
              padding: 40,
              textAlign: "center",
              color: "rgba(245,240,232,0.55)",
              fontFamily: '"Source Serif 4",Georgia,serif',
              fontSize: 14,
            }}
          >
            Loading positions…
          </div>
        ) : rows.length === 0 ? (
          <div
            style={{
              padding: 64,
              textAlign: "center",
              color: "rgba(245,240,232,0.55)",
              fontFamily: '"Source Serif 4",Georgia,serif',
            }}
          >
            <p style={{ fontSize: 16, lineHeight: 1.5, margin: "0 0 20px 0" }}>
              No positions observed yet.
            </p>
            {onAddPosition && (
              <button
                type="button"
                onClick={onAddPosition}
                className="font-mono uppercase"
                style={{
                  display: "inline-flex",
                  padding: "10px 20px",
                  background: "var(--pq-bronze)",
                  color: "var(--pq-ink, #050505)",
                  fontFamily:
                    '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                  fontSize: 11,
                  letterSpacing: "0.2em",
                  border: "none",
                  borderRadius: "var(--pq-radius-cta, 2px)",
                  cursor: "pointer",
                }}
              >
                Add your first position →
              </button>
            )}
          </div>
        ) : (
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontFamily:
                '"JetBrains Mono","SF Mono",ui-monospace,monospace',
            }}
          >
            <thead>
              <tr>
                {headers.map((h) => (
                  <th
                    key={h.key}
                    scope="col"
                    aria-sort={ariaSort(h.key)}
                    onClick={() => onSort(h.key)}
                    className="pq-pos-th"
                    style={{
                      fontFamily:
                        '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                      fontSize: 10.5,
                      letterSpacing: "0.22em",
                      textTransform: "uppercase",
                      fontWeight: 500,
                      color:
                        sortKey === h.key
                          ? "var(--pq-bronze)"
                          : "rgba(245,240,232,0.40)",
                      padding: "14px 12px",
                      textAlign: h.align,
                      borderBottom:
                        "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.08))",
                      cursor: "pointer",
                      userSelect: "none",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {h.label}
                    {sortKey === h.key && (
                      <span aria-hidden style={{ marginLeft: 6, opacity: 0.7 }}>
                        {sortDir === "asc" ? "▲" : "▼"}
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <PositionRow
                  key={r.raw.id}
                  row={r}
                  onClick={() =>
                    router.push(`/detail/${encodeURIComponent(r.raw.symbol)}`)
                  }
                  onAction={onAction}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      <style jsx>{`
        :global(.pq-pos-row) {
          transition: background-color 160ms ease;
          cursor: pointer;
        }
        :global(.pq-pos-row:hover) {
          background-color: rgba(184, 149, 106, 0.03);
        }
        :global(.pq-pos-row:hover .pq-row-actions) {
          opacity: 1;
        }
        :global(.pq-row-actions) {
          opacity: 0;
          transition: opacity 160ms ease;
        }
        :global(.pq-pos-row:focus-visible) {
          outline: 1px solid var(--pq-bronze);
          outline-offset: -1px;
        }
      `}</style>
    </section>
  );
}

function PositionRow({
  row,
  onClick,
  onAction,
}: {
  row: DerivedPosition;
  onClick: () => void;
  onAction?: (action: TradeAction, position: Position) => void;
}) {
  const p = row.raw;
  const cur = p.currency ?? "USD";

  function handleAction(e: React.MouseEvent, action: TradeAction) {
    e.stopPropagation();
    e.preventDefault();
    onAction?.(action, p);
  }

  const cellStyle: React.CSSProperties = {
    padding: "16px 12px",
    fontSize: 13.5,
    color: "rgba(245,240,232,0.82)",
    borderBottom:
      "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.08))",
    whiteSpace: "nowrap",
    fontVariantNumeric: "tabular-nums",
  };

  return (
    <tr
      className="pq-pos-row"
      tabIndex={0}
      role="link"
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
    >
      {/* 1 · Name (종목명 main pattern) */}
      <td style={{ ...cellStyle, textAlign: "left", minWidth: 200 }}>
        <div
          className="font-serif"
          style={{
            fontFamily: '"Playfair Display","Source Serif 4",Georgia,serif',
            fontSize: 18,
            fontWeight: 500,
            lineHeight: 1.2,
            color: "var(--pq-ivory)",
            letterSpacing: "-0.005em",
          }}
        >
          {p.name}
        </div>
        <div
          className="font-mono uppercase"
          style={{
            fontFamily:
              '"JetBrains Mono","SF Mono",ui-monospace,monospace',
            fontSize: 10.5,
            letterSpacing: "0.18em",
            color: "rgba(245,240,232,0.40)",
            marginTop: 3,
          }}
        >
          {p.symbol}
        </div>
        {/* Hover-revealed actions */}
        {onAction && (
          <div
            className="pq-row-actions"
            style={{
              marginTop: 8,
              display: "flex",
              gap: 8,
            }}
          >
            <RowActionBtn label="Add" onClick={(e) => handleAction(e, "buy")} />
            <RowActionBtn
              label="Trim"
              onClick={(e) => handleAction(e, "sell")}
            />
            <RowActionBtn
              label="Edit"
              onClick={(e) => handleAction(e, "edit")}
            />
          </div>
        )}
      </td>

      {/* 2 · Shares */}
      <td style={{ ...cellStyle, textAlign: "right" }}>{fmtShares(p.shares)}</td>

      {/* 3 · Avg Cost (muted) */}
      <td
        style={{
          ...cellStyle,
          textAlign: "right",
          color: "rgba(245,240,232,0.55)",
        }}
      >
        {fmtMoney(p.avgCost, cur)}
      </td>

      {/* 4 · Last */}
      <td style={{ ...cellStyle, textAlign: "right" }}>
        {fmtMoney(p.current, cur)}
      </td>

      {/* 5 · P/L % */}
      <td
        style={{
          ...cellStyle,
          textAlign: "right",
          color: pctColor(row.plPct),
        }}
      >
        {fmtPctSigned(row.plPct)}
      </td>

      {/* 6 · Mkt Value */}
      <td style={{ ...cellStyle, textAlign: "right" }}>
        {fmtMoney(row.mv, cur)}
      </td>

      {/* 7 · Weight + bronze gradient bar */}
      <td style={{ ...cellStyle, textAlign: "right", width: 96 }}>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-end",
            gap: 6,
          }}
        >
          <span>{Number.isFinite(row.weight) ? row.weight.toFixed(1) : "—"}%</span>
          <div
            aria-hidden
            style={{
              width: "100%",
              height: 2,
              background: "rgba(245,240,232,0.06)",
              position: "relative",
            }}
          >
            <div
              style={{
                position: "absolute",
                left: 0,
                top: 0,
                bottom: 0,
                width: `${Math.max(0, Math.min(100, row.weight))}%`,
                background:
                  "linear-gradient(to right, var(--pq-bronze-deep, #6F5636), var(--pq-bronze, #B8956A))",
              }}
            />
          </div>
        </div>
      </td>

      {/* 8 · Sector tag */}
      <td style={{ ...cellStyle, textAlign: "left" }}>
        <span
          className="sector-tag font-mono uppercase"
          style={{
            display: "inline-block",
            fontFamily:
              '"JetBrains Mono","SF Mono",ui-monospace,monospace',
            fontSize: 10,
            letterSpacing: "0.2em",
            padding: "4px 8px",
            border: "1px solid var(--pq-bronze)",
            borderRadius: "var(--pq-radius-cta, 2px)",
            color: "var(--pq-bronze)",
            textTransform: "uppercase",
          }}
        >
          {p.sector || "—"}
        </span>
      </td>
    </tr>
  );
}

function RowActionBtn({
  label,
  onClick,
}: {
  label: string;
  onClick: (e: React.MouseEvent) => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="font-mono uppercase"
      style={{
        fontFamily: '"JetBrains Mono","SF Mono",ui-monospace,monospace',
        fontSize: 9.5,
        letterSpacing: "0.2em",
        padding: "4px 10px",
        background: "transparent",
        color: "var(--pq-bronze)",
        border: "1px solid rgba(184,149,106,0.4)",
        borderRadius: "var(--pq-radius-cta, 2px)",
        cursor: "pointer",
        textTransform: "uppercase",
      }}
    >
      {label}
    </button>
  );
}

export default PositionsTableV2;
