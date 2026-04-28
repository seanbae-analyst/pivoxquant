"use client";

/**
 * <SectorDonutBlock /> — 160×160 SVG donut + legend (mockup §BLOCK 3a / SPEC §4.1).
 *
 * Color is never the only signal — legend pairs swatch + text label.
 * KRW positions normalized to display currency via fxRate.
 */

import * as React from "react";
import type { Position } from "@/components/portfolio/types";

interface SectorDonutBlockProps {
  positions: Position[];
  /** null when no live FX feed is available — KRW positions are then skipped. */
  fxRate: number | null;
  displayCurrency?: "USD" | "KRW";
}

interface SectorBucket {
  name: string;
  pct: number;
  color: string;
}

const COLOR_RAMP: string[] = [
  "var(--pq-bronze, #B8956A)",
  "var(--pq-bronze-light, #A3845C)",
  "var(--pq-bronze-deep, #6F5636)",
  "rgba(245,240,232,0.32)",
  "rgba(245,240,232,0.22)",
  "rgba(245,240,232,0.14)",
  "rgba(245,240,232,0.08)",
];

function buildSectors(
  positions: Position[],
  fxRate: number | null,
  displayCurrency: "USD" | "KRW",
): SectorBucket[] {
  const totals: Record<string, number> = {};
  let total = 0;
  for (const p of positions) {
    const mv = p.shares * p.current;
    let normalized: number;
    const needsConversion =
      (displayCurrency === "USD" && p.currency === "KRW") ||
      (displayCurrency === "KRW" && p.currency !== "KRW");
    if (needsConversion) {
      // Skip rather than apply a placeholder fx — keeps the sector chart
      // honest when the FX feed is down.
      if (!fxRate || fxRate <= 0) continue;
      normalized =
        displayCurrency === "USD" && p.currency === "KRW"
          ? mv / fxRate
          : mv * fxRate;
    } else {
      normalized = mv;
    }
    const sector = p.sector || "Unclassified";
    totals[sector] = (totals[sector] ?? 0) + normalized;
    total += normalized;
  }
  if (total <= 0) return [];

  const sorted = Object.entries(totals)
    .map(([name, mv]) => ({ name, pct: (mv / total) * 100 }))
    .sort((a, b) => b.pct - a.pct);

  // Top 6 + "Other"
  if (sorted.length <= 7) {
    return sorted.map((s, i) => ({ ...s, color: COLOR_RAMP[i % COLOR_RAMP.length] }));
  }
  const top = sorted.slice(0, 6);
  const otherPct = sorted.slice(6).reduce((acc, s) => acc + s.pct, 0);
  return [
    ...top.map((s, i) => ({ ...s, color: COLOR_RAMP[i] })),
    { name: "Other", pct: otherPct, color: COLOR_RAMP[6] },
  ];
}

export function SectorDonutBlock({
  positions,
  fxRate,
  displayCurrency = "USD",
}: SectorDonutBlockProps) {
  const sectors = React.useMemo(
    () => buildSectors(positions, fxRate, displayCurrency),
    [positions, fxRate, displayCurrency],
  );

  // Donut geometry — circumference and rotation per segment
  const SIZE = 160;
  const STROKE = 16;
  const R = (SIZE - STROKE) / 2;
  const CIRC = 2 * Math.PI * R;

  const segments = React.useMemo(() => {
    return sectors.reduce<
      { name: string; pct: number; color: string; dash: number; offset: number }[]
    >((acc, s) => {
      const prev = acc[acc.length - 1];
      const cumulative = prev ? prev.offset * -1 + prev.dash : 0;
      const dash = (s.pct / 100) * CIRC;
      const offset = -cumulative;
      acc.push({ ...s, dash, offset });
      return acc;
    }, []);
  }, [sectors, CIRC]);

  return (
    <div
      className="pq-card"
      style={{
        background: "var(--pq-card-bg-ink, rgba(255,255,255,0.02))",
        border: "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.08))",
        borderRadius: "var(--pq-radius-card, 4px)",
        padding: 24,
        minHeight: 380,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontFamily: '"JetBrains Mono","SF Mono",ui-monospace,monospace',
          fontSize: 10.5,
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 20,
        }}
      >
        Sectors · Mix
      </div>

      {sectors.length === 0 ? (
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "rgba(245,240,232,0.55)",
            fontFamily: '"Source Serif 4",Georgia,serif',
            fontSize: 13,
          }}
        >
          No allocation yet.
        </div>
      ) : (
        <>
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              marginBottom: 20,
              position: "relative",
            }}
          >
            <svg
              role="img"
              aria-label={`Sector allocation across ${sectors.length} sectors`}
              width={SIZE}
              height={SIZE}
              viewBox={`0 0 ${SIZE} ${SIZE}`}
              style={{ transform: "rotate(-90deg)" }}
            >
              <circle
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={R}
                fill="none"
                stroke="rgba(245,240,232,0.04)"
                strokeWidth={STROKE}
              />
              {segments.map((s, i) => (
                <circle
                  key={i}
                  cx={SIZE / 2}
                  cy={SIZE / 2}
                  r={R}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={STROKE}
                  strokeDasharray={`${s.dash} ${CIRC - s.dash}`}
                  strokeDashoffset={s.offset}
                />
              ))}
            </svg>
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                pointerEvents: "none",
              }}
            >
              <div
                className="font-mono uppercase"
                style={{
                  fontFamily:
                    '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                  fontSize: 9.5,
                  letterSpacing: "0.22em",
                  color: "rgba(245,240,232,0.40)",
                  marginBottom: 2,
                }}
              >
                Sectors
              </div>
              <div
                className="font-serif"
                style={{
                  fontFamily:
                    '"Playfair Display","Source Serif 4",Georgia,serif',
                  fontSize: 22,
                  color: "var(--pq-ivory)",
                  fontWeight: 500,
                }}
              >
                {sectors.length}
              </div>
            </div>
          </div>

          <ul
            style={{
              listStyle: "none",
              padding: 0,
              margin: 0,
              display: "flex",
              flexDirection: "column",
            }}
          >
            {sectors.map((s, i) => (
              <li
                key={s.name}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "8px 0",
                  borderBottom:
                    i < sectors.length - 1
                      ? "1px solid var(--pq-hairline-ink, rgba(245,240,232,0.06))"
                      : "none",
                }}
              >
                <span
                  aria-hidden
                  style={{
                    width: 12,
                    height: 12,
                    background: s.color,
                    borderRadius: 1,
                    flexShrink: 0,
                  }}
                />
                <span
                  className="font-serif"
                  style={{
                    flex: 1,
                    fontFamily:
                      '"Source Serif 4",Georgia,serif',
                    fontSize: 13,
                    color: "var(--pq-ivory)",
                  }}
                >
                  {s.name}
                </span>
                <span
                  className="font-mono tabular-nums"
                  style={{
                    fontFamily:
                      '"JetBrains Mono","SF Mono",ui-monospace,monospace',
                    fontSize: 12,
                    color: "rgba(245,240,232,0.82)",
                  }}
                >
                  {s.pct.toFixed(1)}%
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

export default SectorDonutBlock;
