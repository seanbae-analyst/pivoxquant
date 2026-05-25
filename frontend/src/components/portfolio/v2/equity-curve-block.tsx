"use client";

/**
 * <EquityCurveBlock /> — full-width equity curve + timeframe toggle.
 *
 * Mockup §BLOCK 1 / SPEC §2.
 * Inline SVG (no Recharts) — matches mockup's editorial polyline style.
 * Bronze series (portfolio NAV) + dashed ivory series (benchmark KOSPI200).
 */

import * as React from "react";
import { EditorialHead } from "@/components/ui/editorial";
import { pctColor } from "@/lib/format";
import { useEquityCurve, type EquityRange, type EquityPoint } from "./hooks-v2";

interface EquityCurveBlockProps {
  /** Display currency for the NAV KPI strip. */
  currency?: "USD" | "KRW";
  /** Current NAV for the KPI strip (already converted to display currency). */
  currentNav?: number;
  /** Native-currency subtotals — when both present the NAV KPI shows the split
   *  (USD X · KRW Y) instead of one FX-unified USD figure (CEO 2026-05-24). */
  navUsd?: number;
  navKrw?: number;
}

// Backend whitelist: "5d" | "1mo" | "3mo" | "6mo" | "1y" — Bug #8 fix.
// "1yr" / "all" silently fell back to 5-day window on the API.
// "All" is re-introduced (P0 2026-05-19) and mapped explicitly to "1y"
// — the maximum the backend supports today — so the request remains
// inside the whitelist and the user sees the longest available window
// instead of the silent 5-day fallback. The `id` is the tab's React key
// (and aria handle); `key` is the backend period actually requested.
// When the backend grows a "max" period, swap the period for the All
// tab here without changing the UI label.
const RANGES: { id: string; key: EquityRange; label: string }[] = [
  { id: "1mo", key: "1mo", label: "1M" },
  { id: "3mo", key: "3mo", label: "3M" },
  { id: "6mo", key: "6mo", label: "6M" },
  { id: "1y", key: "1y", label: "1Y" },
  { id: "all", key: "1y", label: "All" },
];

// Wave 2 sweep (2026-05-19): NOT migrated to @/lib/format.
//   fmtMoney — 0-decimal USD vs lib/fmtUsd 2-decimal under 1000.
//   fmtPct   — `n > 0 ? "+"` (zero shows no sign) vs lib's `n >= 0 ? "+"`
//              (zero shows "+0.00%"). Equity curve renders 0% on flat days
//              and we keep the sign-suppressed look here intentionally.
function fmtMoney(n: number | undefined, currency: "USD" | "KRW"): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  const dec = currency === "KRW" ? 0 : 0;
  const body = abs.toLocaleString(currency === "KRW" ? "ko-KR" : "en-US", {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
  return `${currency === "KRW" ? "KRW " : "USD "}${body}`;
}

function fmtPct(n: number | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

// Return %, benchmark %, and spread coloring now use the site-canonical KR
// convention helper (lib/format.pctColor): gain → carmine #D18888, loss →
// indigo #7AA0C8, flat → muted ivory. The old local helper inverted this.

interface PolylineGeom {
  ptsNav: string;
  ptsBench: string;
  fillNav: string;
  /** Closed polygon points for the benchmark fill area (ivory dim). */
  fillBench: string;
}

function computePolylines(
  series: EquityPoint[],
  width: number,
  height: number,
): PolylineGeom | null {
  if (!series || series.length < 2) return null;
  const navs = series.map((p) => p.nav);
  // Backend emits raw index closes for the benchmark (KOSPI ~2,600 / SPY
  // ~$450) and its comment claims the frontend rebases — but it never did,
  // so the benchmark line was crushed against the portfolio's currency value
  // on a shared y-axis (severe for KR, ~20x for US). Rebase the benchmark to
  // the portfolio's starting value ("same starting capital invested in the
  // index"): it then shares the nav scale and is the standard comparison.
  const firstBenchIdx = series.findIndex(
    (p) => typeof p.benchmark === "number" && Number.isFinite(p.benchmark),
  );
  const rebasedBench: (number | null)[] = series.map(() => null);
  if (firstBenchIdx >= 0) {
    const benchBase = series[firstBenchIdx].benchmark as number;
    const navBase = series[firstBenchIdx].nav;
    if (benchBase > 0 && Number.isFinite(navBase)) {
      series.forEach((p, i) => {
        if (typeof p.benchmark === "number" && Number.isFinite(p.benchmark)) {
          rebasedBench[i] = navBase * (p.benchmark / benchBase);
        }
      });
    }
  }
  const benches = rebasedBench.filter(
    (v): v is number => typeof v === "number" && Number.isFinite(v),
  );
  const allVals = [...navs, ...benches];
  const min = Math.min(...allVals);
  const max = Math.max(...allVals);
  const span = max - min || 1;
  const xStep = width / (series.length - 1);
  const toY = (v: number) => height - ((v - min) / span) * height * 0.92 - height * 0.04;

  const ptsNav = series
    .map((p, i) => `${(i * xStep).toFixed(1)},${toY(p.nav).toFixed(1)}`)
    .join(" ");
  const ptsBench = rebasedBench
    .map((v, i) =>
      v != null ? `${(i * xStep).toFixed(1)},${toY(v).toFixed(1)}` : null,
    )
    .filter((v): v is string => v !== null)
    .join(" ");

  // Area fill under the NAV line: start at the bottom-left baseline,
  // trace the line (first point is already at x=0), drop to the
  // bottom-right baseline, close. The prior `.replace(/M0,/, ...)` injected
  // a spurious (0,lastNavY)→(0,height) vertical segment that distorted the
  // left edge of every fill.
  const fillNav =
    `M0,${height.toFixed(1)} L${ptsNav.replace(/ /g, " L")} L${width.toFixed(1)},${height.toFixed(1)} Z`;

  // Closed polygon along the benchmark line back to the baseline.
  // Only built when we have a contiguous benchmark series for every
  // sample — partial coverage would visually distort the area.
  let fillBench = "";
  const benchContiguous =
    rebasedBench.every((v) => v != null) && ptsBench.length > 0;
  if (benchContiguous) {
    fillBench = `0,${height.toFixed(1)} ${ptsBench} ${width.toFixed(1)},${height.toFixed(1)}`;
  }

  return { ptsNav, ptsBench, fillNav, fillBench };
}

export function EquityCurveBlock({
  currency = "USD",
  currentNav,
  navUsd,
  navKrw,
}: EquityCurveBlockProps) {
  // `activeId` is the tab the user clicked (id="1mo"|"3mo"|"6mo"|"1y"|"all").
  // The backend period is resolved through the RANGES table so the "All"
  // tab can map to "1y" without duplicating React keys or aria handles.
  const [activeId, setActiveId] = React.useState<string>("6mo");
  const activeRange =
    RANGES.find((r) => r.id === activeId)?.key ??
    ("6mo" as EquityRange);
  const { data, isLoading, error } = useEquityCurve(activeRange);

  const series: EquityPoint[] = React.useMemo(() => {
    // hooks-v2 normalizes backend `{ data: [{ date, value }] }` to
    // `{ series: [{ t, nav }] }`. Bug #8 fix.
    const raw = data?.series ?? [];
    return raw.filter(
      (p): p is EquityPoint =>
        p != null && typeof p.nav === "number" && Number.isFinite(p.nav),
    );
  }, [data]);

  const rangeReturn = React.useMemo(() => {
    if (series.length < 2) return undefined;
    const first = series[0].nav;
    const last = series[series.length - 1].nav;
    if (!first) return undefined;
    return ((last - first) / first) * 100;
  }, [series]);

  const benchmarkReturn = React.useMemo(() => {
    if (series.length < 2) return undefined;
    // The benchmark series often starts mid-window (the dashed line begins
    // partway through the chart), so `series[0].benchmark` / `series[last]`
    // are commonly undefined → both BENCHMARK + SPREAD showed "—". Anchor on
    // the FIRST and LAST *valid* benchmark points instead. The resulting
    // window may be slightly shorter than the full portfolio window, but a
    // real number beats an em-dash. (2026-05-22 FIX 4.)
    const isValidBench = (v: number | undefined): v is number =>
      typeof v === "number" && Number.isFinite(v) && v !== 0;
    const first = series.find((p) => isValidBench(p.benchmark))?.benchmark;
    const last = [...series].reverse().find((p) => isValidBench(p.benchmark))
      ?.benchmark;
    if (!isValidBench(first) || !isValidBench(last)) {
      return undefined;
    }
    return ((last - first) / first) * 100;
  }, [series]);

  const SVG_W = 1200;
  const SVG_H = 280;
  const geom = computePolylines(series, SVG_W, SVG_H);

  return (
    <section
      aria-label="Equity curve"
      style={{ marginBottom: 40 }}
    >
      {/* Section header + timeframe toggle */}
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
            Equity · Curve
          </div>
          <EditorialHead size={30} as="h2" style={{ lineHeight: 1.1 }}>
            How the book moves.
          </EditorialHead>
        </div>

        {/* Timeframe pills */}
        <div role="tablist" aria-label="Timeframe" style={{ display: "flex", gap: 4 }}>
          {RANGES.map((r) => {
            const active = r.id === activeId;
            return (
              <button
                key={r.id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setActiveId(r.id)}
                className="font-mono uppercase"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.2em",
                  padding: "6px 12px",
                  background: active
                    ? "rgba(184,149,106,0.12)"
                    : "transparent",
                  color: active
                    ? "var(--pq-bronze)"
                    : "rgba(245,240,232,0.55)",
                  border: `1px solid ${active ? "var(--pq-bronze)" : "rgba(245,240,232,0.12)"}`,
                  borderRadius: "var(--pq-radius-cta, 2px)",
                  cursor: "pointer",
                  textTransform: "uppercase",
                  transition: "all 160ms",
                }}
              >
                {r.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Card with KPI strip + SVG */}
      <div
        className="pq-card"
        style={{
          background: "var(--pq-card-bg-ink, rgba(255,255,255,0.02))",
          border: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
          borderRadius: "var(--pq-radius-card, 4px)",
          padding: 24,
        }}
      >
        {/* KPI strip — 3 up */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
            gap: 24,
            paddingBottom: 20,
            marginBottom: 20,
            borderBottom:
              "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
          }}
        >
          <KpiCell
            label="NAV"
            value={
              typeof navUsd === "number" && navUsd > 0 &&
              typeof navKrw === "number" && navKrw > 0
                ? `${fmtMoney(navUsd, "USD")} · ${fmtMoney(navKrw, "KRW")}`
                : fmtMoney(currentNav, currency)
            }
            valueColor="var(--pq-ivory)"
          />
          <KpiCell
            label={`Range · ${(
              RANGES.find((r) => r.id === activeId)?.label ?? activeRange
            ).toUpperCase()}`}
            value={fmtPct(rangeReturn)}
            valueColor={pctColor(rangeReturn)}
          />
          <KpiCell
            label="Benchmark"
            value={fmtPct(benchmarkReturn)}
            valueColor={pctColor(benchmarkReturn)}
          />
        </div>

        {/* Spread KPI strip (portfolio - benchmark). Restored 2026-05-19
            after design-review flagged the footer as missing the lead
            "alpha" datum. Lives BETWEEN the KPI strip and the chart so the
            existing 3-up grid stays untouched. Em-dash when either return
            is unavailable. */}
        {(() => {
          const haveBoth =
            typeof rangeReturn === "number" &&
            Number.isFinite(rangeReturn) &&
            typeof benchmarkReturn === "number" &&
            Number.isFinite(benchmarkReturn);
          const spread = haveBoth
            ? (rangeReturn as number) - (benchmarkReturn as number)
            : undefined;
          const spreadLabel =
            spread == null
              ? "—"
              : `${spread > 0 ? "+" : ""}${spread.toFixed(2)}pp`;
          return (
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                alignItems: "baseline",
                gap: 8,
                marginTop: -8,
                marginBottom: 12,
              }}
            >
              <span
                className="font-mono uppercase"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.22em",
                  color: "rgba(245,240,232,0.55)",
                }}
              >
                Spread
              </span>
              <span
                className="font-mono tabular-nums"
                style={{
                  fontSize: "var(--pq-text-body)",
                  color: pctColor(spread),
                }}
              >
                {spreadLabel}
              </span>
            </div>
          );
        })()}

        {/* Chart */}
        <figure style={{ margin: 0 }}>
          <figcaption className="sr-only">
            Equity curve: portfolio NAV solid bronze line and benchmark dashed
            ivory line over the selected timeframe.
          </figcaption>

          {isLoading && !data ? (
            <div
              role="status"
              aria-live="polite"
              style={{
                height: SVG_H,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "rgba(245,240,232,0.55)",
                fontSize: "var(--pq-text-body)",
              }}
            className="font-serif" >
              Loading equity history…
            </div>
          ) : error ? (
            <div
              role="alert"
              style={{
                height: SVG_H,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "rgba(245,240,232,0.55)",
                fontSize: "var(--pq-text-body)",
              }}
            className="font-serif" >
              Unable to load equity history.
            </div>
          ) : !geom ? (
            <div
              style={{
                height: SVG_H,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "rgba(245,240,232,0.55)",
                fontSize: "var(--pq-text-body)",
              }}
            className="font-serif" >
              Not enough history yet.
            </div>
          ) : (
            <svg
              role="img"
              aria-label="Portfolio NAV over time"
              viewBox={`0 0 ${SVG_W} ${SVG_H}`}
              preserveAspectRatio="none"
              width="100%"
              height={SVG_H}
              style={{ display: "block" }}
            >
              <defs>
                <linearGradient id="pq-bronze-fill" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="rgba(184,149,106,0.18)" />
                  <stop offset="100%" stopColor="rgba(184,149,106,0)" />
                </linearGradient>
              </defs>

              {/* Hairline gridlines */}
              {[56, 112, 168, 224].map((y) => (
                <line
                  key={y}
                  x1={0}
                  x2={SVG_W}
                  y1={y}
                  y2={y}
                  stroke="var(--pq-ivory-line-soft)"
                  strokeWidth={1}
                />
              ))}

              {/* Benchmark fill — ivory dim polygon, rendered first so the
                  bronze portfolio fill stacks on top visually. Only drawn
                  when the benchmark series is contiguous across the range. */}
              {geom.fillBench && (
                <polygon
                  points={geom.fillBench}
                  fill="rgba(245,240,232,0.05)"
                  stroke="none"
                />
              )}

              {/* Portfolio fill */}
              <polygon
                points={`0,${SVG_H} ${geom.ptsNav} ${SVG_W},${SVG_H}`}
                fill="url(#pq-bronze-fill)"
              />

              {/* Benchmark dashed */}
              {geom.ptsBench && (
                <polyline
                  points={geom.ptsBench}
                  fill="none"
                  stroke="rgba(245,240,232,0.55)"
                  strokeWidth={1.2}
                  strokeDasharray="3 4"
                />
              )}

              {/* Portfolio line */}
              <polyline
                points={geom.ptsNav}
                fill="none"
                stroke="var(--pq-bronze)"
                strokeWidth={1.6}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </figure>

        {/* Legend */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 24,
            marginTop: 16,
            paddingTop: 16,
            borderTop: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
            flexWrap: "wrap",
          }}
        >
          <LegendSwatch
            color="var(--pq-bronze)"
            label="Portfolio"
            dashed={false}
          />
          <LegendSwatch
            color="rgba(245,240,232,0.55)"
            label="Benchmark · KOSPI200"
            dashed
          />
        </div>
      </div>
    </section>
  );
}

function KpiCell({
  label,
  value,
  valueColor,
}: {
  label: string;
  value: string;
  valueColor: string;
}) {
  return (
    <div>
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "rgba(245,240,232,0.55)",
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div
        className="font-mono tabular-nums"
        style={{
          fontSize: "var(--pq-text-quote)",
          letterSpacing: "-0.01em",
          color: valueColor,
        }}
      >
        {value}
      </div>
    </div>
  );
}

function LegendSwatch({
  color,
  label,
  dashed,
}: {
  color: string;
  label: string;
  dashed: boolean;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span
        aria-hidden
        style={{
          display: "inline-block",
          width: 14,
          height: 2,
          background: dashed
            ? `repeating-linear-gradient(to right, ${color} 0 3px, transparent 3px 7px)`
            : color,
        }}
      />
      <span
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "rgba(245,240,232,0.55)",
        }}
      >
        {label}
      </span>
    </div>
  );
}

export default EquityCurveBlock;
