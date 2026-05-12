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
import { useEquityCurve, type EquityRange, type EquityPoint } from "./hooks-v2";

interface EquityCurveBlockProps {
  /** Display currency for the NAV KPI strip. */
  currency?: "USD" | "KRW";
  /** Current NAV for the KPI strip (already converted to display currency). */
  currentNav?: number;
}

// Backend whitelist: "5d" | "1mo" | "3mo" | "6mo" | "1y" — Bug #8 fix.
// "1yr" / "all" silently fell back to 5-day window on the API; both removed.
const RANGES: { key: EquityRange; label: string }[] = [
  { key: "1mo", label: "1M" },
  { key: "3mo", label: "3M" },
  { key: "6mo", label: "6M" },
  { key: "1y", label: "1Y" },
];

function fmtMoney(n: number | undefined, currency: "USD" | "KRW"): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  const dec = currency === "KRW" ? 0 : 0;
  const body = abs.toLocaleString(currency === "KRW" ? "ko-KR" : "en-US", {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
  return `${currency === "KRW" ? "₩" : "$"}${body}`;
}

function fmtPct(n: number | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function pctColor(n: number | undefined): string {
  if (n == null || !Number.isFinite(n)) return "rgba(245,240,232,0.55)";
  if (n > 0) return "var(--pq-positive, #dc2626)"; // KR convention
  if (n < 0) return "var(--pq-negative, #2563eb)";
  return "rgba(245,240,232,0.55)";
}

interface PolylineGeom {
  ptsNav: string;
  ptsBench: string;
  fillNav: string;
}

function computePolylines(
  series: EquityPoint[],
  width: number,
  height: number,
): PolylineGeom | null {
  if (!series || series.length < 2) return null;
  const navs = series.map((p) => p.nav);
  const benches = series
    .map((p) => p.benchmark)
    .filter((v): v is number => typeof v === "number" && Number.isFinite(v));
  const allVals = [...navs, ...benches];
  const min = Math.min(...allVals);
  const max = Math.max(...allVals);
  const span = max - min || 1;
  const xStep = width / (series.length - 1);
  const toY = (v: number) => height - ((v - min) / span) * height * 0.92 - height * 0.04;

  const ptsNav = series
    .map((p, i) => `${(i * xStep).toFixed(1)},${toY(p.nav).toFixed(1)}`)
    .join(" ");
  const ptsBench = series
    .map((p, i) =>
      typeof p.benchmark === "number" && Number.isFinite(p.benchmark)
        ? `${(i * xStep).toFixed(1)},${toY(p.benchmark).toFixed(1)}`
        : null,
    )
    .filter((v): v is string => v !== null)
    .join(" ");

  const lastNavY = toY(series[series.length - 1].nav);
  const fillNav =
    `M0,${height} L${ptsNav.replace(/ /g, " L")} L${(width).toFixed(1)},${height} Z`.replace(
      /M0,/,
      `M0,${lastNavY.toFixed(1)} L0,`,
    );

  return { ptsNav, ptsBench, fillNav };
}

export function EquityCurveBlock({
  currency = "USD",
  currentNav,
}: EquityCurveBlockProps) {
  const [range, setRange] = React.useState<EquityRange>("6mo");
  const { data, isLoading, error } = useEquityCurve(range);

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
    const first = series[0].benchmark;
    const last = series[series.length - 1].benchmark;
    if (typeof first !== "number" || typeof last !== "number" || !first) {
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
            const active = r.key === range;
            return (
              <button
                key={r.key}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setRange(r.key)}
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
            value={fmtMoney(currentNav, currency)}
            valueColor="var(--pq-ivory)"
          />
          <KpiCell
            label={`Range · ${range.toUpperCase()}`}
            value={fmtPct(rangeReturn)}
            valueColor={pctColor(rangeReturn)}
          />
          <KpiCell
            label="Benchmark"
            value={fmtPct(benchmarkReturn)}
            valueColor={pctColor(benchmarkReturn)}
          />
        </div>

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
