/**
 * SelfObservedRadar — the 선언(declared) vs 관찰(observed) persona shape.
 *
 * Pure geometry: two overlaid 9-axis polygons. Legal posture (mirrors
 * services/artifacts/living_mirror_service.py): the radar shows *shape only* —
 * NO score, grade, percentile, or numeric value is ever printed on an axis.
 * The user reads the gap between declaration and behaviour as a fact.
 *
 * Colours come from v3 tokens (no raw hex): 선언 = bronze, 관찰 = ivory.
 */
import * as React from "react";

interface SelfObservedRadarProps {
  /** Axis labels in FEATURE_KEYS order (Korean disclosed dimension names). */
  labels: string[];
  /** Declared centroid shape, 0..1 per axis. */
  declared: number[];
  /** Observed 30d shape, 0..1 per axis — null in the "new" stage. */
  observed: number[] | null;
  className?: string;
}

// viewBox carries horizontal padding (x from -55 to 345) so the long left/right
// axis labels (e.g. "선언한 위험 감내") never clip outside the canvas.
const VIEWBOX = "-55 0 410 300";
const CX = 150;
const CY = 148;
const R = 92;
const LABEL_R = 110;

function axisAngle(i: number, n: number): number {
  return -Math.PI / 2 + (2 * Math.PI * i) / n;
}

function point(i: number, n: number, value: number): { x: number; y: number } {
  const v = Math.max(0, Math.min(1, value));
  const a = axisAngle(i, n);
  return { x: CX + R * v * Math.cos(a), y: CY + R * v * Math.sin(a) };
}

function polygon(vec: number[]): string {
  const n = vec.length;
  return vec
    .map((v, i) => {
      const p = point(i, n, v);
      return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
    })
    .join(" ");
}

export function SelfObservedRadar({
  labels,
  declared,
  observed,
  className,
}: SelfObservedRadarProps) {
  const n = declared.length || 9;
  const rings = [0.25, 0.5, 0.75, 1];

  return (
    <svg
      viewBox={VIEWBOX}
      className={className}
      role="img"
      aria-label="선언 페르소나와 최근 30일 관찰 행동의 9축 비교. 점수 없이 모양만 표시합니다."
    >
      {/* reference rings + spokes */}
      <g style={{ fill: "none", stroke: "rgba(var(--pq-ivory-rgb), 0.10)" }} strokeWidth={1}>
        {rings.map((s) => (
          <polygon key={s} points={polygon(new Array(n).fill(s))} />
        ))}
        {Array.from({ length: n }).map((_, i) => {
          const p = point(i, n, 1);
          return <line key={i} x1={CX} y1={CY} x2={p.x} y2={p.y} />;
        })}
      </g>

      {/* 선언 (declared) — bronze */}
      <polygon
        points={polygon(declared)}
        style={{ fill: "rgba(var(--pq-bronze-rgb), 0.12)", stroke: "var(--pq-bronze)" }}
        strokeWidth={1.6}
        strokeLinejoin="round"
      />

      {/* 관찰 (observed) — ivory; absent in the "new" stage */}
      {observed && observed.length === n && (
        <polygon
          points={polygon(observed)}
          style={{ fill: "rgba(var(--pq-ivory-rgb), 0.13)", stroke: "var(--pq-ivory)" }}
          strokeWidth={1.6}
          strokeLinejoin="round"
        />
      )}

      {/* axis labels — names only, never a value (legal: shape, not score) */}
      {labels.slice(0, n).map((label, i) => {
        const a = axisAngle(i, n);
        const lx = CX + LABEL_R * Math.cos(a);
        const ly = CY + LABEL_R * Math.sin(a);
        const anchor = lx < CX - 4 ? "end" : lx > CX + 4 ? "start" : "middle";
        return (
          <text
            key={label}
            x={lx.toFixed(1)}
            y={ly.toFixed(1)}
            textAnchor={anchor}
            dominantBaseline="middle"
            fontSize={9}
            style={{
              fill: "rgba(var(--pq-ivory-rgb), 0.55)",
              fontFamily: "var(--pq-font-sans)",
            }}
          >
            {label}
          </text>
        );
      })}
    </svg>
  );
}
