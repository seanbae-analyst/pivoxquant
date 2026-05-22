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
import { EditorialHead } from "@/components/ui/editorial";
import { fmtMoneyPlain, fmtPctSignedMinus, pctColor, displayTicker, normalizeTicker } from "@/lib/format";
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
  /** FX rate used to normalize KRW positions to USD when totalNav is USD.
   *  null when no live feed — KRW positions render with weight 0 rather
   *  than fabricate a USD figure with a stale literal. */
  fxRate: number | null;
  /** Display currency for the running totals. */
  displayCurrency?: "USD" | "KRW";
  loading?: boolean;
  onAction?: (action: TradeAction, position: Position) => void;
  onAddPosition?: () => void;
  /** Empty-state secondary path: broker sync (KIS/Alpaca). Optional. */
  onReconcile?: () => void;
  /** Whether a broker is linked — drives the secondary CTA enabled state. */
  reconcileAvailable?: boolean;
}

// Wave 4-B (2026-05-20): migrated to lib/fmtMoneyPlain + lib/fmtPctSignedMinus.
// fmtMoney → fmtMoneyPlain(n, currency, currency==="KRW" ? 0 : 2): byte-identical
//   ("—" sentinel, ASCII "-" for negatives, KRW round, USD 2dp).
// fmtPctSigned → fmtPctSignedMinus(n, 2): byte-identical (U+2212, "—" on
//   non-finite, no sign at zero, 2dp).
function fmtMoney(n: number, currency: "USD" | "KRW"): string {
  return fmtMoneyPlain(n, currency, currency === "KRW" ? 0 : 2);
}

function fmtShares(n: number): string {
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  });
}

function fmtPctSigned(n: number): string {
  return fmtPctSignedMinus(n, 2);
}

// P&L gain/loss color now uses the site-canonical KR convention helper
// (lib/format.pctColor): gain → carmine #D18888, loss → indigo #7AA0C8,
// flat → muted ivory. The old local helper inverted this (gain → bronze),
// diverging from detail/watchlist. Bronze stays a brand accent elsewhere.

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
  fxRate: number | null,
  displayCurrency: "USD" | "KRW",
): DerivedPosition[] {
  const safeTotal = totalNav > 0 ? totalNav : 1;
  const safeFx = fxRate && fxRate > 0 ? fxRate : null;
  return positions.map((p) => {
    const mv = p.shares * p.current;
    const cost = p.shares * p.avgCost;
    const pl = mv - cost;
    const plPct = cost > 0 ? (pl / cost) * 100 : 0;

    // Normalize market value to display currency for weight calc.
    // When FX is unavailable for a cross-currency position, mvNormalized
    // is 0 and the weight column reports — (handled by fmtPctSigned).
    let mvNormalized = mv;
    if (displayCurrency === "USD" && p.currency === "KRW") {
      mvNormalized = safeFx ? mv / safeFx : 0;
    } else if (displayCurrency === "KRW" && p.currency !== "KRW") {
      mvNormalized = safeFx ? mv * safeFx : 0;
    }
    const weight = mvNormalized > 0 ? (mvNormalized / safeTotal) * 100 : 0;

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
  onReconcile,
  reconcileAvailable = false,
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
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            Holdings · Ledger
          </div>
          <EditorialHead size={30} as="h2" style={{ lineHeight: 1.1 }}>
            Every line, every weight.
          </EditorialHead>
        </div>
        <span
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "rgba(245,240,232,0.55)",
          }}
        >
          {rows.length} {rows.length === 1 ? "row" : "rows"}
        </span>
      </div>

      <div
        className="pq-card"
        style={{
          background: "var(--pq-card-bg-ink, rgba(255,255,255,0.02))",
          border: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
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
              fontSize: "var(--pq-text-body)",
            }}
          className="font-serif" >
            Loading positions…
          </div>
        ) : rows.length === 0 ? (
          <div
            style={{
              padding: 64,
              textAlign: "center",
              color: "rgba(245,240,232,0.55)",
            }}
          className="font-serif" >
            <p
              className="font-display"
              style={{
                fontSize: "var(--pq-text-h5)",
                lineHeight: 1.3,
                color: "var(--pq-ivory)",
                margin: "0 0 10px 0",
                fontWeight: 500,
                letterSpacing: "-0.01em",
              }}
            >
              아직 기록된 보유 종목이 없습니다.
            </p>
            <p
              style={{
                fontSize: "var(--pq-text-body)",
                lineHeight: 1.55,
                margin: "0 auto 24px",
                maxWidth: 420,
              }}
            >
              보유 종목을 직접 입력해 책(book)을 시작하세요. 자산
              동기화하셨다면 KIS·Alpaca 연동으로 한 번에 불러올 수도 있습니다.
            </p>
            <div
              style={{
                display: "flex",
                gap: 14,
                justifyContent: "center",
                flexWrap: "wrap",
              }}
            >
              {/* Primary path — manual add (한투 유저 적음 → 수동이 주 경로) */}
              {onAddPosition && (
                <button
                  type="button"
                  onClick={onAddPosition}
                  className="font-mono uppercase"
                  style={{
                    display: "inline-flex",
                    padding: "11px 22px",
                    background: "var(--pq-bronze)",
                    color: "var(--pq-ink, #050505)",
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.2em",
                    border: "none",
                    borderRadius: "var(--pq-radius-cta, 2px)",
                    cursor: "pointer",
                  }}
                >
                  보유종목 직접 추가 →
                </button>
              )}
              {/* Secondary path — broker sync */}
              {onReconcile && (
                <button
                  type="button"
                  onClick={onReconcile}
                  disabled={!reconcileAvailable}
                  className="font-mono uppercase"
                  title={
                    reconcileAvailable
                      ? "KIS·Alpaca 계좌에서 동기화"
                      : "KIS broker 연결 필요 (Settings)"
                  }
                  aria-disabled={!reconcileAvailable}
                  style={{
                    display: "inline-flex",
                    padding: "11px 22px",
                    background: "transparent",
                    color: reconcileAvailable
                      ? "var(--pq-bronze)"
                      : "rgba(245,240,232,0.45)",
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.2em",
                    border: `1px solid ${reconcileAvailable ? "var(--pq-bronze)" : "rgba(245,240,232,0.20)"}`,
                    borderRadius: "var(--pq-radius-cta, 2px)",
                    cursor: reconcileAvailable ? "pointer" : "not-allowed",
                  }}
                >
                  KIS·Alpaca 동기화
                </button>
              )}
            </div>
          </div>
        ) : (
          /* Mobile fix (2026-05-05): wrap the 8-col table in overflow-x-auto
             so the table can horizontal-scroll within the section instead
             of forcing the entire page to horizontal-scroll on mobile. */
          <div className="overflow-x-auto" style={{ width: "100%" }}>
          <table
            style={{
              width: "100%",
              minWidth: 700,
              borderCollapse: "collapse",
            }}
          className="font-mono" >
            <thead>
              <tr>
                {headers.map((h) => (
                  <th
                    key={h.key}
                    scope="col"
                    aria-sort={ariaSort(h.key)}
                    onClick={() => onSort(h.key)}
                    className="pq-pos-th font-mono"
                    style={{
                      fontSize: "var(--pq-text-eyebrow)",
                      letterSpacing: "0.22em",
                      textTransform: "uppercase",
                      fontWeight: 500,
                      color:
                        sortKey === h.key
                          ? "var(--pq-bronze)"
                          : "rgba(245,240,232,0.55)",
                      padding: "14px 12px",
                      textAlign: h.align,
                      borderBottom:
                        "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
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
          </div>
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
    fontSize: "var(--pq-text-body)",
    color: "rgba(245,240,232,0.82)",
    borderBottom:
      "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
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
        <EditorialHead
          size={18}
          as="div"
          style={{ lineHeight: 1.2, letterSpacing: "-0.005em" }}
        >
          {displayTicker(p.symbol, p.name)}
        </EditorialHead>
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.18em",
            color: "rgba(245,240,232,0.55)",
            marginTop: 3,
          }}
        >
          {normalizeTicker(p.symbol)}
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
              background: "var(--pq-ivory-line-soft)",
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
            fontSize: "var(--pq-text-eyebrow)",
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
        fontSize: "var(--pq-text-eyebrow)",
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
