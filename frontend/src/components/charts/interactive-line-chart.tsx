"use client";

/**
 * InteractiveLineChart — PivoxQuant shared SVG line chart with hover
 * crosshair and tooltip. Bronze stroke on Vantablack ink.
 *
 * Design:
 *  - SVG viewBox stretches via preserveAspectRatio="none" for fluid width.
 *  - Mouse/touch move resolves nearest point index and positions crosshair.
 *  - Tooltip rendered as absolute-positioned div (HTML) over the SVG so
 *    text renders crisp at any size and can overflow SVG bounds.
 *  - Neutral observation language only: "Value", "Last observed".
 *
 * Accessibility: role="img" + aria-label describes the series.
 */

import { useRef, useState, useMemo, useCallback, useId } from "react";

export interface InteractivePoint {
  date: string;
  value: number;
}

/**
 * A signal/observation marker plotted on the price line. The chart maps
 * `date` to the nearest price point's x-position and draws a small tick
 * above the curve, coloured by `tone`. Legal: tone vocabulary is the
 * observation set (positive / negative / neutral) — never trade-action.
 */
export interface ChartMarker {
  date: string;
  tone: "positive" | "negative" | "neutral";
  /** Human-readable observation label for hover/aria (e.g. "긍정 · 강도 0.91"). */
  label?: string;
  /** 0..1 — reserved for future intensity sizing; not required. */
  strength?: number;
}

export interface InteractiveLineChartProps {
  points: InteractivePoint[];
  height?: number;
  color?: string;
  valueFormatter?: (v: number) => string;
  dateFormatter?: (d: string) => string;
  yLabel?: string;
  ariaLabel?: string;
  /** Compact mode strips axis labels and shrinks padding (for small sparklines). */
  compact?: boolean;
  /** Downsample cap — if points exceed this, evenly sample to this length. */
  maxPoints?: number;
  /**
   * Observation markers overlaid on the price line. Each is snapped to
   * the nearest charted date and drawn as a tone-coloured tick. Hidden
   * in compact mode (sparklines have no room).
   */
  markers?: ChartMarker[];
}

const MARKER_TONE: Record<ChartMarker["tone"], string> = {
  positive: "var(--pq-positive, #B8956A)",
  negative: "var(--pq-negative, #D18888)",
  neutral: "rgba(245,240,232,0.5)",
};

/**
 * Downsample an array to at most `max` points by index sampling.
 * Preserves first and last point. O(max) — safe for render path.
 */
function downsample<T>(arr: T[], max: number): T[] {
  if (arr.length <= max) return arr;
  const out: T[] = [];
  const step = (arr.length - 1) / (max - 1);
  for (let i = 0; i < max; i++) {
    out.push(arr[Math.round(i * step)]);
  }
  return out;
}

export function InteractiveLineChart({
  points,
  height = 220,
  color,
  valueFormatter,
  dateFormatter,
  yLabel,
  ariaLabel = "Observation curve",
  compact = false,
  maxPoints = 300,
  markers,
}: InteractiveLineChartProps) {
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<{ idx: number; x: number; y: number } | null>(null);

  const gradId = useId();

  const w = 1000;
  const h = height;
  const padding = compact
    ? { top: 6, right: 6, bottom: 6, left: 6 }
    : { top: 20, right: 30, bottom: 28, left: 48 };
  const innerW = w - padding.left - padding.right;
  const innerH = h - padding.top - padding.bottom;

  const sampled = useMemo(() => downsample(points, maxPoints), [points, maxPoints]);

  const geom = useMemo(() => {
    if (!sampled.length) {
      return { min: 0, max: 0, path: "", area: "", xs: [] as number[], ys: [] as number[] };
    }
    const vals = sampled.map((p) => p.value);
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const range = max - min || 1;
    const denom = sampled.length > 1 ? sampled.length - 1 : 1;
    const xs = sampled.map((_, i) => padding.left + (i / denom) * innerW);
    const ys = sampled.map((p) => padding.top + (1 - (p.value - min) / range) * innerH);
    const path = xs
      .map((x, i) => (i === 0 ? "M" : "L") + x.toFixed(1) + "," + ys[i].toFixed(1))
      .join(" ");
    const area =
      path +
      ` L${xs[xs.length - 1].toFixed(1)},${(padding.top + innerH).toFixed(1)} L${xs[0].toFixed(1)},${(padding.top + innerH).toFixed(1)} Z`;
    return { min, max, path, area, xs, ys };
  }, [sampled, innerH, innerW, padding.left, padding.top]);

  // Snap each marker's calendar date to the nearest charted point so the
  // tick lands on the curve. Day-granularity matching tolerates the
  // chart's "YYYY-MM-DD" dates vs. a signal's full ISO `observed_at`.
  const markerGeom = useMemo(() => {
    if (compact || !markers || markers.length === 0 || sampled.length < 2) {
      return [] as Array<{
        x: number;
        y: number;
        color: string;
        label: string;
      }>;
    }
    const dayMs = 86_400_000;
    const times = sampled.map((p) => {
      const t = new Date(p.date).getTime();
      return isNaN(t) ? null : t;
    });
    const out: Array<{ x: number; y: number; color: string; label: string }> = [];
    for (const m of markers) {
      const mt = new Date(m.date).getTime();
      if (isNaN(mt)) continue;
      let bestIdx = -1;
      let bestDist = Infinity;
      for (let i = 0; i < times.length; i++) {
        const ti = times[i];
        if (ti == null) continue;
        const d = Math.abs(ti - mt);
        if (d < bestDist) {
          bestDist = d;
          bestIdx = i;
        }
      }
      // Drop markers that fall outside the visible window by more than a
      // few days (e.g. a 1M chart with a 1Y-old observation).
      if (bestIdx < 0 || bestDist > 5 * dayMs) continue;
      out.push({
        x: geom.xs[bestIdx],
        y: geom.ys[bestIdx],
        color: MARKER_TONE[m.tone],
        label: m.label ?? m.tone,
      });
    }
    return out;
  }, [compact, markers, sampled, geom.xs, geom.ys]);

  const resolveHover = useCallback(
    (clientX: number) => {
      if (!ref.current || sampled.length < 2) return;
      const rect = ref.current.getBoundingClientRect();
      if (rect.width === 0) return;
      const scaleX = w / rect.width;
      const mouseX = (clientX - rect.left) * scaleX;
      const relativeX = mouseX - padding.left;
      const denom = sampled.length - 1;
      const raw = Math.round((relativeX / innerW) * denom);
      const idx = Math.max(0, Math.min(denom, raw));
      setHover({ idx, x: geom.xs[idx], y: geom.ys[idx] });
    },
    [sampled.length, geom.xs, geom.ys, innerW, padding.left],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => resolveHover(e.clientX),
    [resolveHover],
  );

  const handleTouchMove = useCallback(
    (e: React.TouchEvent<SVGSVGElement>) => {
      const t = e.touches[0];
      if (t) resolveHover(t.clientX);
    },
    [resolveHover],
  );

  const bronze = color || "var(--pq-bronze, #B8956A)";

  const hoverPoint = hover ? sampled[hover.idx] : null;

  // Empty state.
  if (sampled.length < 2) {
    return (
      <div
        className="relative w-full flex items-center justify-center text-pq-mono-sm text-[rgba(245,240,232,0.4)]"
        style={{ height }}
        role="img"
        aria-label={`${ariaLabel} (no data)`}
      >
        —
      </div>
    );
  }

  return (
    <div className="relative w-full" style={{ height }}>
      <svg
        ref={ref}
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="none"
        width="100%"
        height="100%"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHover(null)}
        onTouchStart={handleTouchMove}
        onTouchMove={handleTouchMove}
        onTouchEnd={() => setHover(null)}
        className="block cursor-crosshair touch-none"
        role="img"
        aria-label={ariaLabel}
      >
        <defs>
          <linearGradient id={`pq-area-${gradId}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={bronze} stopOpacity="0.18" />
            <stop offset="100%" stopColor={bronze} stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Gridlines (hidden in compact) */}
        {!compact &&
          [0, 0.25, 0.5, 0.75, 1].map((t) => (
            <line
              key={t}
              x1={padding.left}
              x2={w - padding.right}
              y1={padding.top + t * innerH}
              y2={padding.top + t * innerH}
              stroke="rgba(245,240,232,0.05)"
              strokeWidth="0.5"
            />
          ))}

        {/* Y-axis labels (top + bottom only, hidden in compact) */}
        {!compact &&
          [0, 1].map((t) => (
            <text
              key={t}
              x={padding.left - 8}
              y={padding.top + (1 - t) * innerH + 3}
              fontSize="10"
              fill="rgba(245,240,232,0.55)"
              textAnchor="end"
              fontFamily="var(--pq-font-mono), ui-monospace, monospace"
            >
              {valueFormatter
                ? valueFormatter(geom.min + t * (geom.max - geom.min))
                : (geom.min + t * (geom.max - geom.min)).toFixed(2)}
            </text>
          ))}

        {/* Area fill */}
        <path d={geom.area} fill={`url(#pq-area-${gradId})`} />

        {/* Line */}
        <path
          d={geom.path}
          fill="none"
          stroke={bronze}
          strokeWidth={compact ? 1.25 : 1.6}
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* Observation markers — tone-coloured ticks snapped to the curve.
            Legal: tone is the observation set, never a trade action. */}
        {markerGeom.length > 0 && (
          <g aria-label={`관측 마커 ${markerGeom.length}건`}>
            {markerGeom.map((m, i) => (
              <g key={i} role="img" aria-label={m.label}>
                <title>{m.label}</title>
                {/* connector stem from the curve up to the tick */}
                <line
                  x1={m.x}
                  x2={m.x}
                  y1={m.y}
                  y2={Math.max(padding.top, m.y - 14)}
                  stroke={m.color}
                  strokeWidth="1"
                  strokeOpacity="0.55"
                />
                <circle
                  cx={m.x}
                  cy={Math.max(padding.top, m.y - 14)}
                  r={3.5}
                  fill={m.color}
                  stroke="var(--pq-ink, #050505)"
                  strokeWidth="1.25"
                />
              </g>
            ))}
          </g>
        )}

        {/* Hover crosshair + dot */}
        {hover && (
          <g>
            <line
              x1={hover.x}
              x2={hover.x}
              y1={padding.top}
              y2={padding.top + innerH}
              stroke="rgba(245,240,232,0.3)"
              strokeWidth="0.5"
              strokeDasharray="3 3"
            />
            {!compact && (
              <line
                x1={padding.left}
                x2={w - padding.right}
                y1={hover.y}
                y2={hover.y}
                stroke="rgba(245,240,232,0.15)"
                strokeWidth="0.5"
                strokeDasharray="3 3"
              />
            )}
            <circle
              cx={hover.x}
              cy={hover.y}
              r={compact ? 3 : 4}
              fill={bronze}
              stroke="var(--pq-ink, #050505)"
              strokeWidth="1.5"
            />
          </g>
        )}
      </svg>

      {/* Tooltip overlay — absolute HTML layer for crisp text */}
      {hover && hoverPoint && (
        <div
          className="pq-chart-tooltip absolute pointer-events-none"
          style={{
            left: `${(hover.x / w) * 100}%`,
            top: `${(hover.y / h) * 100}%`,
            transform: "translate(-50%, calc(-100% - 12px))",
            minWidth: 140,
          }}
        >
          <div
            className="uppercase"
            style={{
              fontSize: "var(--pq-text-kicker)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze, #B8956A)",
              marginBottom: "4px",
            }}
          >
            {dateFormatter ? dateFormatter(hoverPoint.date) : hoverPoint.date}
          </div>
          <div
            className="tabular-nums font-mono"
            style={{
              fontSize: "var(--pq-text-body)",
              color: "var(--pq-ivory, #F5F0E8)",
            }}
          >
            {valueFormatter ? valueFormatter(hoverPoint.value) : hoverPoint.value.toFixed(2)}
          </div>
          {yLabel && (
            <div
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                color: "rgba(245,240,232,0.5)",
                marginTop: "2px",
              }}
            >
              {yLabel}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
