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
 * Rows are not clickable — see the note above PositionRow for why.
 */

import * as React from "react";
import { useT } from "@/lib/locale";
import { useIsPhone } from "@/lib/use-phone";
import { Sheet } from "@/components/ui/sheet";
import { Caption, EditorialHead } from "@/components/ui/editorial";
import { ChevronRight } from "lucide-react";
import { fmtMoneyPlain, fmtPctSignedMinus, pctColor, priceDir, displayTicker, normalizeTicker } from "@/lib/format";
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
  /**
   * Vendor market-data display gate (lib/market-display.ts). When false the
   * LAST / P/L % / MKT VALUE columns are removed — each one is a vendor price
   * or a function of one — and WEIGHT is recomputed at average cost. Defaults
   * to true so the enabled path is byte-identical to before the flag.
   */
  marketDataDisplay?: boolean;
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
  /**
   * Open the 관찰 노트 composer for one row (docs/design/
   * observation-notes_2026-09-22.md §5 진입점). Deliberately NOT a
   * `TradeAction`: that union feeds <TradeModalV2 />'s copy table and its
   * three members are all book mutations. Writing a note changes nothing
   * about the position, so it gets its own channel.
   */
  onObservationNote?: (position: Position) => void;
  onAddPosition?: () => void;
  /** Empty-state secondary path: broker sync (KIS). Optional. */
  /** Whether a broker is linked — drives the secondary CTA enabled state. */
}

// Wave 4-B (2026-05-20): migrated to lib/fmtMoneyPlain + lib/fmtPctSignedMinus.
// fmtMoney → fmtMoneyPlain(n, currency, currency==="KRW" ? 0 : 2): byte-identical
//   ("—" sentinel, ASCII "-" for negatives, KRW round, USD 2dp).
// fmtPctSigned → fmtPctSignedMinus(n, 2): byte-identical (U+2212, "—" on
//   non-finite, no sign at zero, 2dp).
// eslint-disable-next-line no-restricted-syntax -- local fmt* helper kept per Wave 2/4-B sweep (delegates to, or intentionally diverges from, @/lib/format); see adjacent note
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

// eslint-disable-next-line no-restricted-syntax -- local fmt* helper kept per Wave 2/4-B sweep (delegates to, or intentionally diverges from, @/lib/format); see adjacent note
function fmtPctSigned(n: number): string {
  return fmtPctSignedMinus(n, 2);
}

/**
 * Weight label. With the vendor-quote gate off the weight is cost-basis, and
 * the label says so — the table header and the phone card share this string
 * so the number is never read as a market weight (same convention as
 * /journal's 평균매입가 기준 비중).
 */
function weightLabel(marketDataDisplay: boolean): string {
  return marketDataDisplay ? "비중" : "비중 · 취득가 기준";
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

/**
 * Which price each row is measured at.
 *
 * "market" — `p.current`, the vendor quote. The original behaviour.
 * "cost"   — `p.avgCost`, what the user paid. Used when the vendor-display
 *            gate is off. The weight denominator is then the book's own total
 *            cost rather than the backend's NAV, so the column still sums to
 *            100% without a single quote being read.
 */
export type ValuationBasis = "market" | "cost";

interface TableHeader {
  key: SortKey;
  label: string;
  align: "left" | "right";
}

// Exported for unit testing the FX-aware weight math (KR-only/US-only/mixed).
export function derive(
  positions: Position[],
  totalNav: number,
  fxRate: number | null,
  displayCurrency: "USD" | "KRW",
  basis: ValuationBasis = "market",
): DerivedPosition[] {
  const safeFx = fxRate && fxRate > 0 ? fxRate : null;
  const unitPrice = (p: Position) => (basis === "cost" ? p.avgCost : p.current);
  /** Same cross-currency rule as below, hoisted so the cost denominator
   *  and the per-row value are normalized identically. */
  const normalize = (p: Position, v: number): number => {
    if (displayCurrency === "USD" && p.currency === "KRW") {
      return safeFx ? v / safeFx : 0;
    }
    if (displayCurrency === "KRW" && p.currency !== "KRW") {
      return safeFx ? v * safeFx : 0;
    }
    return v;
  };
  // `totalNav` is always USD-unified (backend portfolio summary alias). When the
  // display currency is KRW the per-position `mvNormalized` below is computed in
  // KRW, so the weight denominator must be KRW too — otherwise a KR-only book
  // divides KRW by USD and reports ~138,000% weights (v52 FX-split regression).
  const totalNavInDisplay =
    displayCurrency === "KRW" && safeFx ? totalNav * safeFx : totalNav;
  // Cost basis owns its own denominator: `totalNav` is a market figure and is
  // null/absent from the backend when the display gate is off. Summing the
  // book's own normalized cost keeps the column at 100% with no quote.
  const costDenominator =
    basis === "cost"
      ? positions.reduce(
          (acc, p) => acc + Math.max(0, normalize(p, p.shares * p.avgCost)),
          0,
        )
      : 0;
  const denominator = basis === "cost" ? costDenominator : totalNavInDisplay;
  const safeTotal = denominator > 0 ? denominator : 1;
  return positions.map((p) => {
    const mv = p.shares * unitPrice(p);
    const cost = p.shares * p.avgCost;
    const pl = mv - cost;
    const plPct = cost > 0 ? (pl / cost) * 100 : 0;

    // Normalize the value to display currency for weight calc.
    // When FX is unavailable for a cross-currency position, mvNormalized
    // is 0 and the weight column reports — (handled by fmtPctSigned).
    const mvNormalized = normalize(p, mv);
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
  marketDataDisplay = true,
  positions,
  totalNav,
  fxRate,
  displayCurrency = "USD",
  loading,
  onAction,
  onObservationNote,
  onAddPosition,
}: PositionsTableV2Props) {
  const t = useT();
  const isPhone = useIsPhone();
  const [sortKey, setSortKey] = React.useState<SortKey>("weight");
  const [sortDir, setSortDir] = React.useState<"asc" | "desc">("desc");

  const basis: ValuationBasis = marketDataDisplay ? "market" : "cost";

  const rows = React.useMemo(
    () =>
      sortRows(
        derive(positions, totalNav, fxRate, displayCurrency, basis),
        sortKey,
        sortDir,
      ),
    [positions, totalNav, fxRate, displayCurrency, basis, sortKey, sortDir],
  );

  // A sort key can outlive its column: the user sorts by P/L %, the gate
  // flips, and the header it points at is gone. Fall back to Weight, which
  // exists in both column sets.
  React.useEffect(() => {
    if (
      !marketDataDisplay &&
      (sortKey === "last" || sortKey === "plPct" || sortKey === "value")
    ) {
      setSortKey("weight");
      setSortDir("desc");
    }
  }, [marketDataDisplay, sortKey]);

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

  // LAST is the vendor quote; P/L % and MKT VALUE are derived from it. All
  // three leave the table with the gate off — removed, not em-dashed, so no
  // empty money column invites the reader to assume a zero.
  const marketHeaders: TableHeader[] = [
    { key: "last", label: "현재가", align: "right" },
    { key: "plPct", label: "손익률", align: "right" },
    { key: "value", label: "평가액", align: "right" },
  ];
  const headers: TableHeader[] = [
    { key: "name", label: "종목", align: "left" },
    { key: "shares", label: "수량", align: "right" },
    { key: "avgCost", label: "평균가", align: "right" },
    ...(marketDataDisplay ? marketHeaders : []),
    {
      key: "weight",
      label: weightLabel(marketDataDisplay),
      align: "right",
    },
    { key: "sector", label: "섹터", align: "left" },
  ];

  // Phone (2026-10-10, CEO "앱처럼"): its own tree — a full-bleed list of
  // tappable rows under one column label, no boxed card, no section headline.
  // Desktop below is untouched.
  if (isPhone) {
    return (
      <PhoneHoldings
        rows={rows}
        loading={!!loading}
        marketDataDisplay={marketDataDisplay}
        onAction={onAction}
        onObservationNote={onObservationNote}
        onAddPosition={onAddPosition}
        costBasisNote={t("journal.concentrationMirror.costBasisNote")}
      />
    );
  }

  return (
    <section aria-label="보유 종목" style={{ marginBottom: 40 }}>
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          marginBottom: 20,
        }}
      >
        {/* Phone: an editorial section headline over a list of cards is
            page-chrome, not content (2026-10-07). */}
        <div className="hidden md:block">
          <div
            className="font-mono"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.02em",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            보유 종목 · 장부
          </div>
          <EditorialHead size={30} as="h2" style={{ lineHeight: 1.1 }}>
            {t("dashboard.portfolio.positions.heading")}
          </EditorialHead>
        </div>
        <span
          className="font-mono"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.02em",
            color: "var(--pq-ivory-dim)",
          }}
        >
          {rows.length}개 종목
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
              color: "var(--pq-ivory-dim)",
              fontSize: "var(--pq-text-body)",
            }}
          className="font-serif" >
            보유 종목을 불러오는 중…
          </div>
        ) : rows.length === 0 ? (
          <div
            style={{
              padding: 64,
              textAlign: "center",
              color: "var(--pq-ivory-dim)",
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
              동기화하셨다면 KIS 연동으로 한 번에 불러올 수도 있습니다.
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
                  className="font-mono"
                  style={{
                    display: "inline-flex",
                    padding: "11px 22px",
                    background: "var(--pq-bronze)",
                    color: "var(--pq-ink, #050505)",
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.02em",
                    border: "none",
                    borderRadius: "var(--pq-radius-cta, 2px)",
                    cursor: "pointer",
                  }}
                >
                  보유종목 직접 추가 →
                </button>
              )}
              {/* Secondary path — broker sync */}
            </div>
          </div>
        ) : (
          /* Phone holdings are a separate tree (PhoneHoldings, early return
             above). Mobile fix (2026-05-05): wrap the 8-col table in overflow-x-auto
             so the table can horizontal-scroll within the section instead
             of forcing the entire page to horizontal-scroll on mobile. */
          <div className="overflow-x-auto" style={{ width: "100%" }}>
          <table
            style={{
              width: "100%",
              // Three fewer columns need less room before the horizontal
              // scroll kicks in on a 375px phone.
              minWidth: marketDataDisplay ? 700 : 520,
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
                      letterSpacing: "0.02em",
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
                  onAction={onAction}
                  onObservationNote={onObservationNote}
                  marketDataDisplay={marketDataDisplay}
                />
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {/* Basis footnote — the header says "취득가 기준" in short; the full
          clarifier lives here, verbatim the wording /journal already uses. */}
      {!marketDataDisplay && rows.length > 0 ? (
        <div data-testid="positions-cost-basis-note" style={{ marginTop: 12 }}>
          <Caption>{t("journal.concentrationMirror.costBasisNote")}</Caption>
        </div>
      ) : null}

      <style jsx>{`
        :global(.pq-pos-row) {
          transition: background-color 160ms ease;
        }
        :global(.pq-pos-row:hover) {
          background-color: rgba(184, 149, 106, 0.03);
        }
        :global(.pq-pos-row:hover .pq-row-actions),
        :global(.pq-pos-row:focus-within .pq-row-actions) {
          opacity: 1;
        }
        :global(.pq-row-actions) {
          opacity: 0;
          transition: opacity 160ms ease;
        }
        /* Touch screens (iPhone) have no hover: the Add / Trim / Edit / note
           buttons stayed invisible yet still tappable. Show them always and
           give them a finger-sized hit area. */
        @media (hover: none) {
          :global(.pq-row-actions) {
            opacity: 1;
          }
          :global(.pq-row-actions button) {
            min-height: 36px;
          }
        }
        :global(.pq-pos-row:focus-visible) {
          outline: 1px solid var(--pq-bronze);
          outline-offset: -1px;
        }
      `}</style>
    </section>
  );
}

// The row is NOT a link. It used to be: onClick pushed /detail/[ticker],
// which the 2026-08-31 prune deleted — next.config.ts:78 now permanently
// redirects /detail/:path* → /portfolio, so clicking a row on /portfolio
// navigated back to /portfolio. A no-op dressed as navigation, announced to
// screen readers as role="link" and reachable by Tab.
//
// Removed rather than repointed, following the same prune's other consumer:
// top-bar.tsx dropped its Cmd+K palette for exactly this reason (see the
// comment there — "its stock results only ever routed to /detail/[ticker]").
// Sending the row somewhere new would be a product decision, not a cleanup.
//
// The live affordances stay: the hover tint and the Add / Trim / Edit
// buttons, which are real buttons and do real work.
function PositionRow({
  row,
  onAction,
  onObservationNote,
  marketDataDisplay = true,
}: {
  row: DerivedPosition;
  onAction?: (action: TradeAction, position: Position) => void;
  onObservationNote?: (position: Position) => void;
  marketDataDisplay?: boolean;
}) {
  const p = row.raw;
  const cur = p.currency ?? "USD";

  function handleAction(e: React.MouseEvent, action: TradeAction) {
    e.stopPropagation();
    e.preventDefault();
    onAction?.(action, p);
  }

  function handleNote(e: React.MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    onObservationNote?.(p);
  }

  const cellStyle: React.CSSProperties = {
    padding: "16px 12px",
    fontSize: "var(--pq-text-body)",
    color: "var(--pq-ivory-strong)",
    borderBottom:
      "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
    whiteSpace: "nowrap",
    fontVariantNumeric: "tabular-nums",
  };

  return (
    <tr className="pq-pos-row">
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
            color: "var(--pq-ivory-dim)",
            marginTop: 3,
          }}
        >
          {normalizeTicker(p.symbol)}
        </div>
        {/* Hover-revealed actions. `flexWrap` so the fourth button folds onto
            a second line on a 375px phone instead of widening the already
            horizontally-scrolling table. */}
        {(onAction || onObservationNote) && (
          <div
            className="pq-row-actions"
            style={{
              marginTop: 8,
              display: "flex",
              flexWrap: "wrap",
              gap: 8,
            }}
          >
            {onAction && (
              <>
                <RowActionBtn
                  label="추가"
                  ariaLabel={`${normalizeTicker(p.symbol)} 추가 기록`}
                  onClick={(e) => handleAction(e, "buy")}
                />
                <RowActionBtn
                  label="정리"
                  ariaLabel={`${normalizeTicker(p.symbol)} 정리 기록`}
                  onClick={(e) => handleAction(e, "sell")}
                />
                <RowActionBtn
                  label="수정"
                  ariaLabel={`${normalizeTicker(p.symbol)} 수정`}
                  onClick={(e) => handleAction(e, "edit")}
                />
              </>
            )}
            {/* 관찰 노트 — the product noun the reader recognizes from /journal. */}
            {onObservationNote && (
              <RowActionBtn
                label="관찰 노트"
                onClick={handleNote}
                ariaLabel={`${normalizeTicker(p.symbol)} 관찰 노트 작성`}
              />
            )}
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
          color: "var(--pq-ivory-dim)",
        }}
      >
        {fmtMoney(p.avgCost, cur)}
      </td>

      {/* 4 · Last · 5 · P/L % · 6 · Mkt Value — vendor price and its
          derivatives. Omitted entirely (not blanked) when the gate is off,
          so the row has no money cell without a price behind it. */}
      {marketDataDisplay ? (
        <>
          <td style={{ ...cellStyle, textAlign: "right" }}>
            {fmtMoney(p.current, cur)}
          </td>
          <td
            style={{
              ...cellStyle,
              textAlign: "right",
              color: pctColor(row.plPct),
            }}
          >
            {fmtPctSigned(row.plPct)}
          </td>
          <td style={{ ...cellStyle, textAlign: "right" }}>
            {fmtMoney(row.mv, cur)}
          </td>
        </>
      ) : null}

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

/**
 * Phone holdings (2026-10-10, CEO "너무 웹사이트 같음 앱처럼").
 *
 * Was: an "N개 종목" eyebrow over a bordered box of three-line cards, each
 * repeating "비중 · 취득가 기준", with nothing saying a card could be tapped.
 * Now a native list — full-bleed rows with hairline separators inset past
 * the monogram, one column label for the whole list, a chevron on every row,
 * and a pressed state. A row opens a bottom sheet with the holding's details
 * and the same four actions (추가 / 정리 / 수정 / 관찰 노트, same handlers).
 *
 * Values per row, by the vendor-display gate:
 *   OFF (shipped default) — right column is the cost-basis weight, with the
 *     row's cost (shares × average cost) under it. The column label says
 *     "비중 · 취득가 기준" once, the way a table header would.
 *   ON — right column is the market value, with the P/L % under it in the
 *     KR convention colour (pctColor) and a ▲ / ▼ glyph.
 */
function PhoneHoldings({
  rows,
  loading,
  marketDataDisplay,
  onAction,
  onObservationNote,
  onAddPosition,
  costBasisNote,
}: {
  rows: DerivedPosition[];
  loading: boolean;
  marketDataDisplay: boolean;
  onAction?: (action: TradeAction, position: Position) => void;
  onObservationNote?: (position: Position) => void;
  onAddPosition?: () => void;
  costBasisNote: string;
}) {
  if (loading && rows.length === 0) {
    return (
      <section aria-label="보유 종목" aria-busy="true" data-testid="positions-phone">
        <div role="status" className="sr-only">보유 종목을 불러오는 중…</div>
        <ul aria-hidden className="-mx-4">
          {[0, 1, 2, 3].map((i) => (
            <li key={i} className="flex items-center gap-3 px-4 py-3.5">
              <span className="pq-skeleton-dark block h-9 w-9 shrink-0 rounded-full" />
              <span className="flex flex-1 flex-col gap-2">
                <span className="pq-skeleton-dark block h-4 w-28" />
                <span className="pq-skeleton-dark block h-3 w-40" />
              </span>
              <span className="pq-skeleton-dark block h-4 w-14" />
            </li>
          ))}
        </ul>
      </section>
    );
  }

  if (rows.length === 0) {
    return (
      <section
        aria-label="보유 종목"
        data-testid="positions-phone"
        className="flex min-h-[50vh] flex-col items-center justify-center px-4 text-center"
      >
        <p className="text-pq-h6 font-medium text-[var(--pq-ivory)]">
          아직 기록된 보유 종목이 없습니다
        </p>
        <p className="mt-2 max-w-[300px] text-pq-body-sm leading-[1.55] text-[var(--pq-ivory-dim)]">
          지금 들고 있는 종목을 직접 입력하거나, 증권사 앱 잔고 화면 캡처로 한 번에 올릴 수 있습니다.
        </p>
        {onAddPosition && (
          <button
            type="button"
            onClick={onAddPosition}
            className="pq-cta-bronze mt-6 inline-flex min-h-[48px] items-center rounded-sm bg-[var(--pq-bronze)] px-6 text-pq-body font-medium text-[var(--pq-ink)] transition-opacity active:opacity-80"
          >
            보유종목 추가
          </button>
        )}
      </section>
    );
  }

  return (
    <section aria-label="보유 종목" data-testid="positions-phone">
      <div className="flex items-baseline justify-between pb-2 text-pq-caption text-[var(--pq-ivory-dim)]">
        <span>{rows.length}개 종목</span>
        {marketDataDisplay ? (
          <span>평가액 · 손익률</span>
        ) : (
          <span data-testid="position-card-weight-basis">{weightLabel(false)}</span>
        )}
      </div>
      <ul className="-mx-4 border-y border-[var(--pq-ivory-line)]" data-testid="positions-cards">
        {rows.map((r, i) => (
          <PositionCard
            key={r.raw.id}
            row={r}
            first={i === 0}
            onAction={onAction}
            onObservationNote={onObservationNote}
            marketDataDisplay={marketDataDisplay}
          />
        ))}
      </ul>
      {!marketDataDisplay ? (
        <div data-testid="positions-cost-basis-note" className="mt-3">
          <Caption>{costBasisNote}</Caption>
        </div>
      ) : null}
    </section>
  );
}

/** First visible character of a holding's display name — "삼", "A". */
function monogramOf(title: string): string {
  const ch = Array.from(title.trim())[0] ?? "·";
  return ch.toUpperCase();
}

function Monogram({ title, size = 36 }: { title: string; size?: 36 | 44 }) {
  return (
    <span
      aria-hidden
      className={`flex shrink-0 items-center justify-center rounded-full border border-[var(--pq-ivory-line)] font-serif text-[var(--pq-ivory-mid)] ${
        size === 44 ? "h-11 w-11 text-pq-h5" : "h-9 w-9 text-pq-lead"
      }`}
    >
      {monogramOf(title)}
    </span>
  );
}

/** "▲ +12.34%" / "▼ −3.20%" / "0.00%" — colour + glyph, never colour alone. */
function PctWithGlyph({ pct }: { pct: number }) {
  const dir = priceDir(pct);
  return (
    <span style={{ color: pctColor(pct) }}>
      {dir === "up" ? "▲ " : dir === "down" ? "▼ " : ""}
      {fmtPctSigned(pct)}
    </span>
  );
}

/**
 * One holding row — same values and actions as the desktop PositionRow.
 * Tapping it opens a sheet: the holding's figures, then the four actions as
 * full-width 52px rows (same handlers as the desktop buttons).
 */
function PositionCard({
  row,
  first,
  onAction,
  onObservationNote,
  marketDataDisplay = true,
}: {
  row: DerivedPosition;
  first: boolean;
  onAction?: (action: TradeAction, position: Position) => void;
  onObservationNote?: (position: Position) => void;
  marketDataDisplay?: boolean;
}) {
  const p = row.raw;
  const cur = p.currency ?? "USD";
  const name = normalizeTicker(p.symbol);
  const title = displayTicker(p.symbol, p.name);
  const hasActions = !!(onAction || onObservationNote);
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const titleId = `position-actions-${p.id}`;
  const weightText = `${Number.isFinite(row.weight) ? row.weight.toFixed(1) : "—"}%`;
  const costAmount = p.shares * p.avgCost;

  // Close the action sheet, then hand off to the host (which opens its own
  // trade / note sheet in the same tick).
  const run = (fn: () => void) => {
    setSheetOpen(false);
    fn();
  };

  const summary = (
    <>
      <Monogram title={title} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-pq-lead font-medium text-[var(--pq-ivory)]">
          {title}
        </span>
        <span className="mt-0.5 block truncate font-mono text-pq-caption tabular-nums text-[var(--pq-ivory-dim)]">
          {fmtShares(p.shares)}주 · 평균 {fmtMoney(p.avgCost, cur)}
        </span>
      </span>
      <span className="shrink-0 text-right font-mono tabular-nums">
        {marketDataDisplay ? (
          <>
            <span className="block text-pq-body text-[var(--pq-ivory)]">{fmtMoney(row.mv, cur)}</span>
            <span className="mt-0.5 block text-pq-caption">
              <PctWithGlyph pct={row.plPct} />
            </span>
          </>
        ) : (
          <>
            <span className="block text-pq-body text-[var(--pq-ivory)]">{weightText}</span>
            <span className="mt-0.5 block text-pq-caption text-[var(--pq-ivory-dim)]">
              {fmtMoney(costAmount, cur)}
            </span>
          </>
        )}
      </span>
    </>
  );

  return (
    <li className="relative" data-testid="position-card">
      {/* Hairline inset past the monogram, like a native grouped list. */}
      {!first && (
        <span
          aria-hidden
          className="pointer-events-none absolute right-0 top-0 left-[64px] h-px bg-[var(--pq-ivory-line)]"
        />
      )}
      {hasActions ? (
        <button
          type="button"
          onClick={() => setSheetOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={sheetOpen}
          aria-label={`${title} — 기록 동작 열기`}
          data-testid="position-card-open"
          className="flex min-h-[64px] w-full items-center gap-3 py-3 pl-4 pr-2 text-left transition-colors active:bg-[var(--pq-ivory-line-faint)] [-webkit-tap-highlight-color:transparent]"
        >
          {summary}
          <ChevronRight aria-hidden className="h-4 w-4 shrink-0 text-[var(--pq-ivory-dim)]" />
        </button>
      ) : (
        <div className="flex min-h-[64px] items-center gap-3 px-4 py-3">{summary}</div>
      )}

      {hasActions && (
        <Sheet
          open={sheetOpen}
          onClose={() => setSheetOpen(false)}
          ariaLabelledBy={titleId}
          testId="position-action-sheet"
        >
          <div className="flex items-center gap-3 pb-3 pt-1">
            <Monogram title={title} size={44} />
            <div className="min-w-0">
              <div id={titleId} className="truncate font-serif text-pq-h4 text-[var(--pq-ivory)]">
                {title}
              </div>
              <div className="mt-0.5 truncate font-mono text-pq-caption text-[var(--pq-ivory-dim)]">
                {name}
                {p.sector ? ` · ${p.sector}` : ""}
              </div>
            </div>
          </div>

          <dl
            className="grid grid-cols-2 gap-x-4 gap-y-3 border-t border-[var(--pq-ivory-line)] py-4"
            data-testid="position-sheet-figures"
          >
            <SheetFigure label="수량" value={`${fmtShares(p.shares)}주`} />
            <SheetFigure label="평균가" value={fmtMoney(p.avgCost, cur)} />
            {marketDataDisplay ? (
              <>
                <SheetFigure label="현재가" value={fmtMoney(p.current, cur)} />
                <SheetFigure label="평가액" value={fmtMoney(row.mv, cur)} />
                <SheetFigure label="손익률" value={<PctWithGlyph pct={row.plPct} />} />
                <SheetFigure label={weightLabel(true)} value={weightText} />
              </>
            ) : (
              <>
                <SheetFigure label="취득금액" value={fmtMoney(costAmount, cur)} />
                <SheetFigure label={weightLabel(false)} value={weightText} />
              </>
            )}
          </dl>

          <ul className="-mx-5 border-t border-[var(--pq-ivory-line)]" role="list">
            {onAction && (
              <>
                <SheetActionRow label="추가" hint="더 산 내역을 기록" ariaLabel={`${name} 추가 기록`} onClick={() => run(() => onAction("buy", p))} />
                <SheetActionRow label="정리" hint="판 내역을 기록" ariaLabel={`${name} 정리 기록`} onClick={() => run(() => onAction("sell", p))} />
                <SheetActionRow label="수정" hint="평균가 · 메모 고치기" ariaLabel={`${name} 수정`} onClick={() => run(() => onAction("edit", p))} />
              </>
            )}
            {onObservationNote && (
              <SheetActionRow label="관찰 노트" hint="이 종목에 대해 적어 두기" ariaLabel={`${name} 관찰 노트 작성`} onClick={() => run(() => onObservationNote(p))} />
            )}
          </ul>
        </Sheet>
      )}
    </li>
  );
}

function SheetFigure({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-pq-caption text-[var(--pq-ivory-dim)]">{label}</dt>
      <dd className="mt-0.5 truncate font-mono text-pq-body tabular-nums text-[var(--pq-ivory)]">
        {value}
      </dd>
    </div>
  );
}

function SheetActionRow({
  label,
  hint,
  ariaLabel,
  onClick,
}: {
  label: string;
  hint: string;
  ariaLabel: string;
  onClick: () => void;
}) {
  return (
    <li className="border-b border-[var(--pq-ivory-line)]">
      <button
        type="button"
        onClick={onClick}
        aria-label={ariaLabel}
        className="flex min-h-[52px] w-full items-center gap-3 px-5 py-3 text-left transition-colors active:bg-[var(--pq-ivory-line-faint)] [-webkit-tap-highlight-color:transparent]"
      >
        <span className="flex-1 text-pq-h6 text-[var(--pq-ivory)]">{label}</span>
        <span className="text-pq-caption text-[var(--pq-ivory-dim)]">{hint}</span>
        <ChevronRight aria-hidden className="h-4 w-4 shrink-0 text-[var(--pq-ivory-dim)]" />
      </button>
    </li>
  );
}

function RowActionBtn({
  label,
  onClick,
  ariaLabel,
}: {
  label: string;
  onClick: (e: React.MouseEvent) => void;
  /** Row-scoped accessible name — the visible label repeats on every row. */
  ariaLabel?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      className="font-mono"
      style={{
        fontSize: "var(--pq-text-eyebrow)",
        letterSpacing: "0.02em",
        padding: "4px 10px",
        background: "transparent",
        color: "var(--pq-bronze)",
        border: "1px solid rgba(184,149,106,0.4)",
        borderRadius: "var(--pq-radius-cta, 2px)",
        cursor: "pointer",
      }}
    >
      {label}
    </button>
  );
}

export default PositionsTableV2;
