"use client";

/**
 * <PersonaEvolution /> — 12-week persona-score timeline.
 *
 * Replaces the thumbnail sparkline in PersonaCard with a full-width
 * editorial chart:
 *
 *   • 12 weekly snapshots (pulled from `usePersona().sparkline`)
 *   • Motion-path stroke reveal on mount (respects reduced motion)
 *   • Hover/focus any week → tooltip with that week's score, mood,
 *     and confidence (from usePulse history, best-effort matched by
 *     ISO week)
 *   • Drift weeks (declared ≠ observed 30d) are tagged with a bronze
 *     warning glyph at the plotted point
 *
 * Pure presentation; no writes. Falls back to a skeleton when data
 * is loading. Rendered inline inside the Living CFO settings section
 * and — optionally — in a flex row under PersonaCard.
 */

import * as React from "react";
import { motion, useReducedMotion } from "motion/react";
import { AlertTriangle } from "lucide-react";

import {
  usePersona,
  usePulse,
  PERSONA_LABELS,
  type PersonaId,
} from "@/lib/cfo/hooks";

/* ──────────────────────────────────────────────────────────────── */

interface Props {
  /** When true, render without a surrounding ivory panel — for settings. */
  bare?: boolean;
  className?: string;
}

export function PersonaEvolution({ bare = false, className = "" }: Props) {
  const { data, isLoading } = usePersona();
  const { data: pulse } = usePulse();
  const reduceMotion = useReducedMotion();

  const points = data?.sparkline ?? [];
  const pulseHistory = pulse?.history ?? [];
  const drift = data?.drift ?? 0;
  const observedPersona =
    (data?.observed?.window_30d?.persona as PersonaId | undefined) ?? null;
  const declaredPersona =
    (data?.declared?.persona as PersonaId | undefined) ?? null;
  const hasDrift = drift > 20 && observedPersona !== declaredPersona;

  const shell: React.CSSProperties = bare
    ? {}
    : {
        background: "#F5F0E8",
        color: "#1a1612",
        padding: "22px 24px",
        borderRadius: 2,
        boxShadow:
          "0 1px 2px rgba(184,149,106,0.12), 0 18px 36px -22px rgba(0,0,0,0.5)",
        borderTop: "0.5px solid rgba(184,149,106,0.55)",
      };

  const declaredLabel =
    declaredPersona && PERSONA_LABELS[declaredPersona]
      ? PERSONA_LABELS[declaredPersona]
      : "Your CFO";

  return (
    <section
      className={`pq-persona-evolution ${className}`}
      style={shell}
      aria-label="Persona score — 12 week evolution"
    >
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div
            className="font-mono uppercase text-[12px] tracking-[0.26em]"
            style={{ color: bare ? "var(--pq-bronze)" : "#B8956A" }}
          >
            Persona Evolution · 12 weeks
          </div>
          <h3
            className="mt-1 font-serif text-[18px]"
            style={{ color: bare ? "var(--pq-ivory)" : "#1a1612" }}
          >
            How your {declaredLabel.toLowerCase()} has drifted
          </h3>
        </div>
        {hasDrift && (
          <span
            className="inline-flex items-center gap-1 font-mono uppercase text-[12px] tracking-[0.22em] px-2 py-1 rounded-[2px]"
            style={{
              color: "#a35b3b",
              background: bare ? "rgba(163,91,59,0.10)" : "rgba(163,91,59,0.12)",
              border: "0.5px solid rgba(163,91,59,0.35)",
            }}
          >
            <AlertTriangle className="h-3 w-3" />
            Material drift
          </span>
        )}
      </header>

      <div className="mt-5">
        {isLoading ? (
          <div
            aria-hidden
            className="w-full"
            style={{
              height: 120,
              background:
                "repeating-linear-gradient(0deg, rgba(139,111,71,0.08) 0, rgba(139,111,71,0.08) 1px, transparent 1px, transparent 8px)",
            }}
          />
        ) : (
          <EvolutionChart
            points={points}
            pulseHistory={pulseHistory}
            reduceMotion={Boolean(reduceMotion)}
            bare={bare}
            declaredPersona={declaredPersona}
            observedPersona={observedPersona}
          />
        )}
      </div>

      {/* Legend */}
      <div
        className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px]"
        style={{ color: bare ? "rgba(245,240,232,0.55)" : "rgba(26,22,18,0.55)" }}
      >
        <span className="inline-flex items-center gap-1.5">
          <span
            className="h-[2px] w-4"
            style={{ background: bare ? "var(--pq-bronze)" : "#B8956A" }}
            aria-hidden
          />
          Weekly persona score
        </span>
        <span className="inline-flex items-center gap-1.5">
          <AlertTriangle
            className="h-3 w-3"
            style={{ color: "#a35b3b" }}
            aria-hidden
          />
          Drift-flagged week
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: bare ? "var(--pq-ivory)" : "#1a1612" }}
            aria-hidden
          />
          Hover a week for pulse detail
        </span>
      </div>
    </section>
  );
}

/* ══════════════════ Chart ══════════════════ */

interface EvolutionChartProps {
  points: { week: string; score: number }[];
  pulseHistory: { submitted_at: string; mood: number; confidence: number }[];
  reduceMotion: boolean;
  bare: boolean;
  declaredPersona: PersonaId | null;
  observedPersona: PersonaId | null;
}

function EvolutionChart({
  points,
  pulseHistory,
  reduceMotion,
  bare,
  declaredPersona,
  observedPersona,
}: EvolutionChartProps) {
  const [hoverIdx, setHoverIdx] = React.useState<number | null>(null);

  if (points.length === 0) {
    return (
      <p
        className="font-serif text-[13px]"
        style={{ color: bare ? "rgba(245,240,232,0.5)" : "rgba(26,22,18,0.55)" }}
      >
        Your evolution chart fills in as weekly snapshots accumulate.
      </p>
    );
  }

  const width = 520;
  const height = 120;
  const padX = 14;
  const padY = 16;
  const min = Math.min(...points.map((p) => p.score));
  const max = Math.max(...points.map((p) => p.score));
  const range = Math.max(1, max - min);
  const step = (width - padX * 2) / Math.max(1, points.length - 1);

  const x = (i: number) => padX + i * step;
  const y = (v: number) =>
    height - padY - ((v - min) / range) * (height - padY * 2);

  const pathD = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${x(i)},${y(p.score)}`)
    .join(" ");
  const areaD = `${pathD} L ${x(points.length - 1)},${height - padY} L ${padX},${height - padY} Z`;

  // Drift flags per week — mark the ones where score deviates more than
  // 15 points from the overall median (proxy: declared ≠ observed).
  const median = [...points].map((p) => p.score).sort((a, b) => a - b)[
    Math.floor(points.length / 2)
  ];
  const driftWeek = (i: number) =>
    Math.abs(points[i].score - median) > 15 ||
    (i === points.length - 1 &&
      declaredPersona !== null &&
      observedPersona !== null &&
      declaredPersona !== observedPersona);

  // Pulse lookup — map week iso-start to the closest pulse submitted
  // within the 7-day window after that week's start.
  const findPulseForWeek = (weekIso: string) => {
    const start = new Date(weekIso).getTime();
    const end = start + 7 * 86_400_000;
    return pulseHistory.find((p) => {
      const t = new Date(p.submitted_at).getTime();
      return t >= start && t < end;
    });
  };

  const strokeColor = bare ? "var(--pq-bronze, #B8956A)" : "#B8956A";
  const areaFill = bare ? "rgba(184,149,106,0.14)" : "rgba(139,111,71,0.10)";
  const axisColor = bare
    ? "rgba(245,240,232,0.14)"
    : "rgba(139,111,71,0.22)";
  const labelColor = bare
    ? "rgba(245,240,232,0.5)"
    : "rgba(26,22,18,0.55)";

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        preserveAspectRatio="none"
        role="img"
        aria-label={`12-week persona timeline, ${points.length} points`}
        style={{ display: "block", maxHeight: 160 }}
      >
        {/* axis hairline */}
        <line
          x1={padX}
          x2={width - padX}
          y1={height - padY}
          y2={height - padY}
          stroke={axisColor}
          strokeWidth={0.5}
          strokeDasharray="2 3"
        />
        {/* area */}
        <path d={areaD} fill={areaFill} />
        {/* stroke with reveal */}
        <motion.path
          d={pathD}
          fill="none"
          stroke={strokeColor}
          strokeWidth={1.4}
          strokeLinecap="round"
          strokeLinejoin="round"
          pathLength={1}
          initial={
            reduceMotion ? { pathLength: 1 } : { pathLength: 0, opacity: 0 }
          }
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{
            duration: reduceMotion ? 0 : 1.4,
            ease: [0.16, 1, 0.3, 1],
          }}
        />
        {/* interaction dots */}
        {points.map((p, i) => {
          const cx = x(i);
          const cy = y(p.score);
          const isDrift = driftWeek(i);
          const active = hoverIdx === i;
          return (
            <g key={p.week}>
              {isDrift && (
                <circle
                  cx={cx}
                  cy={cy}
                  r={7}
                  fill="rgba(163,91,59,0.10)"
                  stroke="rgba(163,91,59,0.55)"
                  strokeWidth={0.5}
                />
              )}
              <circle
                cx={cx}
                cy={cy}
                r={active ? 4.2 : i === points.length - 1 ? 3.2 : 2.2}
                fill={isDrift ? "#a35b3b" : strokeColor}
                stroke={bare ? "var(--pq-ink)" : "#F5F0E8"}
                strokeWidth={1}
              />
              <rect
                // Hit-target — larger than the glyph for accessibility.
                x={cx - step / 2}
                y={0}
                width={step}
                height={height}
                fill="transparent"
                onMouseEnter={() => setHoverIdx(i)}
                onMouseLeave={() => setHoverIdx((v) => (v === i ? null : v))}
                onFocus={() => setHoverIdx(i)}
                onBlur={() => setHoverIdx((v) => (v === i ? null : v))}
                role="button"
                tabIndex={0}
                aria-label={`Week of ${p.week}, score ${p.score}`}
                style={{ cursor: "pointer", outline: "none" }}
              />
            </g>
          );
        })}
      </svg>

      {/* X-axis sparse labels — first/middle/last */}
      <div
        className="mt-2 flex justify-between font-mono text-[12px] uppercase tracking-[0.2em] tabular-nums"
        style={{ color: labelColor }}
      >
        <span>{points[0]?.week.slice(5) ?? ""}</span>
        <span className="hidden sm:inline">
          {points[Math.floor(points.length / 2)]?.week.slice(5) ?? ""}
        </span>
        <span>{points[points.length - 1]?.week.slice(5) ?? ""}</span>
      </div>

      {/* Tooltip */}
      {hoverIdx !== null && points[hoverIdx] && (
        <HoverCard
          weekIso={points[hoverIdx].week}
          score={points[hoverIdx].score}
          pulse={findPulseForWeek(points[hoverIdx].week)}
          bare={bare}
          drifted={driftWeek(hoverIdx)}
        />
      )}
    </div>
  );
}

function HoverCard({
  weekIso,
  score,
  pulse,
  bare,
  drifted,
}: {
  weekIso: string;
  score: number;
  pulse: { submitted_at: string; mood: number; confidence: number } | undefined;
  bare: boolean;
  drifted: boolean;
}) {
  return (
    <div
      role="tooltip"
      className="mt-3 inline-block font-serif"
      style={{
        background: bare ? "rgba(10,10,10,0.85)" : "rgba(26,22,18,0.92)",
        color: bare ? "var(--pq-ivory)" : "#F5F0E8",
        border: `0.5px solid ${drifted ? "rgba(163,91,59,0.55)" : "rgba(184,149,106,0.35)"}`,
        padding: "10px 12px",
        borderRadius: 2,
        fontSize: 12,
      }}
    >
      <div
        className="font-mono uppercase text-[12px] tracking-[0.22em]"
        style={{ color: "var(--pq-bronze, #B8956A)" }}
      >
        Week of {weekIso}
      </div>
      <div className="mt-0.5">
        Persona score <span className="tabular-nums">{score}</span>
        {drifted && (
          <span
            style={{ marginLeft: 8, color: "#d68965" }}
            className="text-[11px]"
          >
            · drift flagged
          </span>
        )}
      </div>
      {pulse ? (
        <div className="mt-1 text-[12px]" style={{ opacity: 0.85 }}>
          Pulse · mood {pulse.mood}/5 · confidence {pulse.confidence}/5
        </div>
      ) : (
        <div className="mt-1 text-[12px]" style={{ opacity: 0.65 }}>
          No pulse submitted this week
        </div>
      )}
    </div>
  );
}

export default PersonaEvolution;
