"use client";

/**
 * <RollingWindowWidget /> — Layer 2 learning surface.
 *
 * Renders three aligned mini-charts (holding period / turnover / sector
 * tilt) for a user-selected rolling window (30 / 60 / 90 days) plus a
 * single-line headline: "You declared X. Your last 30 days look like Y."
 *
 * Pure inline SVG — no recharts, no lightweight-charts. Fast, crisp on
 * Retina, and works inside the paper/panel shells the portfolio sidebar
 * uses.
 *
 * Legal: descriptive, observational. No recommend/advice.
 */

import * as React from "react";
import { motion } from "motion/react";
import { PQ_DUR_MICRO } from "@/lib/motion";
import {
  useRollingWindow,
  PERSONA_LABELS,
} from "@/lib/cfo/hooks";

type WindowKey = "window_30d" | "window_60d" | "window_90d";

const WINDOW_LABEL: Record<WindowKey, string> = {
  window_30d: "30 days",
  window_60d: "60 days",
  window_90d: "90 days",
};

const WINDOW_TABS: { key: WindowKey; short: string }[] = [
  { key: "window_30d", short: "30d" },
  { key: "window_60d", short: "60d" },
  { key: "window_90d", short: "90d" },
];

interface Props {
  className?: string;
  /** Render on an ivory paper surface (portfolio sidebar). Default true. */
  paper?: boolean;
}

export function RollingWindowWidget({ className = "", paper = true }: Props) {
  const { data, isLoading } = useRollingWindow();
  const [win, setWin] = React.useState<WindowKey>("window_30d");

  const series = data?.series?.[win] ?? [];
  const contrast = data?.contrast;

  return (
    <section
      aria-label="Rolling window behavioural analysis"
      className={className}
      style={
        paper
          ? {
              background: "#F5F0E8",
              color: "#1a1612",
              padding: "22px 24px",
              borderRadius: 2,
              borderTop: "0.5px solid rgba(184,149,106,0.55)",
              boxShadow:
                "0 1px 2px rgba(184,149,106,0.12), 0 18px 36px -22px rgba(0,0,0,0.5)",
            }
          : undefined
      }
    >
      <header className="flex items-start justify-between gap-3">
        <div>
          <div
            className="text-pq-caption uppercase tracking-[0.26em]"
            style={{ color: paper ? "#B8956A" : "var(--pq-bronze)" }}
          >
            Layer 2 · Learning · Rolling window
          </div>
          <h3
            className="mt-1 font-serif text-lg"
            style={{
              color: paper ? "#1a1612" : "var(--pq-ivory)",
              letterSpacing: "-0.01em",
            }}
          >
            Declared vs observed
          </h3>
        </div>

        <div className="flex gap-1" role="tablist">
          {WINDOW_TABS.map((t) => {
            const active = win === t.key;
            return (
              <button
                key={t.key}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setWin(t.key)}
                className="px-2.5 py-1 text-pq-eyebrow uppercase tracking-[0.18em] rounded-[2px] border transition-colors"
                style={{
                  borderColor: active
                    ? "#B8956A"
                    : paper
                      ? "rgba(var(--pq-bronze-wash-rgb),0.25)"
                      : "rgba(245,240,232,0.12)",
                  background: active
                    ? paper
                      ? "rgba(var(--pq-bronze-wash-rgb),0.15)"
                      : "rgba(var(--pq-bronze-wash-rgb),0.22)"
                    : "transparent",
                  color: paper
                    ? active
                      ? "#6F5636"
                      : "rgba(26,22,18,0.6)"
                    : active
                      ? "var(--pq-bronze)"
                      : "rgba(245,240,232,0.5)",
                }}
              >
                {t.short}
              </button>
            );
          })}
        </div>
      </header>

      {/* Contrast line */}
      {contrast && (
        <motion.p
          key={win}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: PQ_DUR_MICRO }}
          className="mt-3 font-serif text-pq-body-sm"
          style={{ color: paper ? "rgba(26,22,18,0.75)" : "var(--pq-ivory)" }}
        >
          Declared ·{" "}
          <strong style={{ color: paper ? "#1a1612" : "var(--pq-ivory)" }}>
            {PERSONA_LABELS[contrast.declared_persona]} {contrast.declared_score}
          </strong>
          {"  ·  "}
          {WINDOW_LABEL[win]} observed ·{" "}
          <strong
            style={{
              color:
                contrast.declared_persona === contrast.observed_persona
                  ? paper
                    ? "#1a1612"
                    : "var(--pq-ivory)"
                  : "var(--pq-drift)",
            }}
          >
            {PERSONA_LABELS[contrast.observed_persona]} {contrast.observed_score}
          </strong>
          .
        </motion.p>
      )}

      {/* Three mini-charts */}
      <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
        <MiniChart
          label="Holding period (days)"
          points={series.map((s) => s.holdingPeriod)}
          formatter={(v) => v.toFixed(0)}
          paper={paper}
          isLoading={isLoading}
        />
        <MiniChart
          label="Turnover"
          points={series.map((s) => s.turnover)}
          formatter={(v) => `${(v * 100).toFixed(0)}%`}
          paper={paper}
          isLoading={isLoading}
        />
        <MiniChart
          label="Sector tilt"
          points={series.map((s) => s.sectorTilt)}
          formatter={(v) => v.toFixed(2)}
          paper={paper}
          isLoading={isLoading}
        />
      </div>
    </section>
  );
}

/* ── Mini-chart (inline SVG) ── */

function MiniChart({
  label,
  points,
  formatter,
  paper,
  isLoading,
}: {
  label: string;
  points: number[];
  formatter: (v: number) => string;
  paper: boolean;
  isLoading: boolean;
}) {
  const latest = points.length ? points[points.length - 1] : null;
  const w = 160;
  const h = 44;
  const pad = 2;

  let d = "";
  if (points.length > 1) {
    const min = Math.min(...points);
    const max = Math.max(...points);
    const range = Math.max(1e-6, max - min);
    const step = (w - pad * 2) / (points.length - 1);
    const y = (v: number) => h - pad - ((v - min) / range) * (h - pad * 2);
    d = points
      .map((v, i) => `${i === 0 ? "M" : "L"} ${pad + i * step},${y(v)}`)
      .join(" ");
  }

  const labelColor = paper ? "#B8956A" : "var(--pq-bronze)";
  const valueColor = paper ? "#1a1612" : "var(--pq-ivory)";

  return (
    <div>
      <div
        className="text-pq-caption uppercase tracking-[0.22em]"
        style={{ color: labelColor }}
      >
        {label}
      </div>
      <div
        className="mt-1 font-mono tabular-nums text-pq-lead"
        style={{ color: valueColor }}
      >
        {isLoading ? "…" : latest !== null ? formatter(latest) : "—"}
      </div>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        width="100%"
        height={h}
        preserveAspectRatio="none"
        role="img"
        aria-label={label}
        className="mt-1"
      >
        {d && (
          <path
            d={d}
            stroke="#B8956A"
            strokeWidth={1.1}
            fill="none"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        )}
      </svg>
    </div>
  );
}

export default RollingWindowWidget;
