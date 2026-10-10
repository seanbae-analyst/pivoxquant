"use client";

/**
 * <SectorDonutBlock /> — 160×160 SVG donut + legend (mockup §BLOCK 3a / SPEC §4.1).
 *
 * Color is never the only signal — legend pairs swatch + text label.
 * KRW positions normalized to display currency via fxRate.
 */

import * as React from "react";
import { useT } from "@/lib/locale";
import { Caption } from "@/components/ui/editorial";
import type { Position } from "@/components/portfolio/types";

interface SectorDonutBlockProps {
  positions: Position[];
  /** null when no live FX feed is available — KRW positions are then skipped. */
  fxRate: number | null;
  displayCurrency?: "USD" | "KRW";
  /**
   * Vendor market-data display gate (lib/market-display.ts). The mix is a
   * ratio, so it survives the gate: with it off the same shares are weighed
   * at average cost instead of at the vendor quote, and the card says so.
   * Defaults to true — the enabled path is unchanged.
   */
  marketDataDisplay?: boolean;
  /**
   * "card" (default): the desktop corner card — donut + legend in a box.
   * "plain" (phone 현황 page, 2026-10-10): no box, no eyebrow (the page has
   * its own section label) — one stacked bar over a full-width legend list,
   * the composition strip finance apps use. Same buckets, same percentages.
   */
  variant?: "card" | "plain";
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
  "rgba(245,240,232,0.55)",
  "rgba(245,240,232,0.22)",
  "rgba(245,240,232,0.14)",
  "var(--pq-ivory-line)",
];

function buildSectors(
  positions: Position[],
  fxRate: number | null,
  displayCurrency: "USD" | "KRW",
  marketDataDisplay = true,
): SectorBucket[] {
  const totals: Record<string, number> = {};
  let total = 0;
  for (const p of positions) {
    const mv = p.shares * (marketDataDisplay ? p.current : p.avgCost);
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
    const sector = p.sector || "미분류";
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
    { name: "기타", pct: otherPct, color: COLOR_RAMP[6] },
  ];
}

export function SectorDonutBlock({
  positions,
  fxRate,
  displayCurrency = "USD",
  marketDataDisplay = true,
  variant = "card",
}: SectorDonutBlockProps) {
  const t = useT();
  const sectors = React.useMemo(
    () => buildSectors(positions, fxRate, displayCurrency, marketDataDisplay),
    [positions, fxRate, displayCurrency, marketDataDisplay],
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

  if (variant === "plain") {
    return (
      <div data-testid="sector-plain">
        {sectors.length === 0 ? (
          <p className="py-6 text-center text-pq-body text-[var(--pq-ivory-dim)]">
            아직 섹터 구성이 없습니다.
          </p>
        ) : (
          <>
            <div
              role="img"
              aria-label={`섹터 ${sectors.length}개 구성: ${sectors
                .map((s) => `${s.name} ${s.pct.toFixed(1)}%`)
                .join(", ")}`}
              className="flex h-2 w-full gap-[2px] overflow-hidden rounded-sm"
            >
              {sectors.map((s) => (
                <span
                  key={s.name}
                  className="block h-full"
                  style={{ flexGrow: s.pct, flexBasis: 0, background: s.color }}
                />
              ))}
            </div>
            <ul className="-mx-4 mt-3">
              {sectors.map((s, i) => (
                <li
                  key={s.name}
                  className={`flex min-h-[44px] items-center gap-3 px-4 ${
                    i > 0 ? "border-t border-[var(--pq-ivory-line)]" : ""
                  }`}
                >
                  <span
                    aria-hidden
                    className="block h-2.5 w-2.5 shrink-0 rounded-sm"
                    style={{ background: s.color }}
                  />
                  <span className="min-w-0 flex-1 truncate text-pq-body text-[var(--pq-ivory)]">
                    {s.name}
                  </span>
                  <span className="font-mono text-pq-body tabular-nums text-[var(--pq-ivory-strong)]">
                    {s.pct.toFixed(1)}%
                  </span>
                </li>
              ))}
            </ul>
            {!marketDataDisplay ? (
              <div data-testid="sector-cost-basis-note" className="mt-2">
                <Caption>{t("journal.concentrationMirror.costBasisNote")}</Caption>
              </div>
            ) : null}
          </>
        )}
      </div>
    );
  }

  return (
    <div
      className="pq-card"
      style={{
        background: "var(--pq-card-bg-ink, rgba(255,255,255,0.02))",
        border: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
        borderRadius: "var(--pq-radius-card, 4px)",
        padding: 24,
        minHeight: 380,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        className="font-mono"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.02em",
          color: "var(--pq-bronze)",
          marginBottom: 20,
        }}
      >
        섹터 · 구성
      </div>

      {sectors.length === 0 ? (
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--pq-ivory-dim)",
            fontSize: "var(--pq-text-body)",
          }}
        className="font-serif" >
          아직 섹터 구성이 없습니다.
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
              aria-label={`섹터 ${sectors.length}개 구성`}
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
                stroke="var(--pq-ivory-line-faint)"
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
                className="font-mono"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.02em",
                  color: "var(--pq-ivory-dim)",
                  marginBottom: 2,
                }}
              >
                섹터
              </div>
              <div
                className="font-display"
                style={{
                  fontSize: "var(--pq-text-quote)",
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
                      ? "1px solid var(--pq-hairline-ink, var(--pq-ivory-line-soft))"
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
                    fontSize: "var(--pq-text-body)",
                    color: "var(--pq-ivory)",
                  }}
                >
                  {s.name}
                </span>
                <span
                  className="font-mono tabular-nums"
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    color: "var(--pq-ivory-strong)",
                  }}
                >
                  {s.pct.toFixed(1)}%
                </span>
              </li>
            ))}
          </ul>

          {/* Same basis clarifier the ledger and /journal carry. */}
          {!marketDataDisplay ? (
            <div data-testid="sector-cost-basis-note" style={{ marginTop: 14 }}>
              <Caption>{t("journal.concentrationMirror.costBasisNote")}</Caption>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}

export default SectorDonutBlock;
