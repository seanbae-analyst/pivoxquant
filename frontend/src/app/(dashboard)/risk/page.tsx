"use client";

/**
 * /risk v2 — "Risk Board" editorial layout.
 *
 * Source of truth: frontend/design-mockups/risk-v2/{SPEC.md, MIGRATION.md, mockup.html}.
 * Sole /risk surface — the ink-card terminal was deleted 2026-08-30.
 *
 * Surface map (matches v1 inventory + risk-v2 SPEC §0):
 *   - TopTicker                    (reused, full-bleed)
 *   - LivingCFOStatusBar           (reused, sticky)
 *   - RiskHeroV2                   (new — editorial hero)
 *   - Block 1: RiskGaugeGrid       (4 KPI big-gauge cards 2×2)
 *   - Block 2: SevenLayerBreakdown (7 stacked rows)
 *   - Block 3: ConcentrationTable  (top-5, 종목명 main pattern)
 *   - Block 4: SectorExposureBlock (220px donut + leader table 2-col)
 *   - Block 5: RiskTimelineChart   (30-day composite line)
 *   - Methodology rail
 *   - FootSignature                (reused)
 *   - DisclaimerBanner             (mounted by (dashboard)/layout.tsx — NOT here)
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. Observation language only.
 */

import * as React from "react";
import { useLocale, useT } from "@/lib/locale";

import { ErrorBoundary } from "@/components/ui/error-boundary";
import { EditorialHead, FootSignature } from "@/components/ui/editorial";

import { TopTicker } from "@/components/terminal/top-ticker";
import { LivingCFOStatusBar } from "@/components/dashboard/living-cfo-status";

import {
  useRiskSummary,
  useRiskLayers,
  useConcentration,
  useSectorExposure,
  useRiskTimeline,
} from "@/lib/hooks";

import { RiskHeroV2 } from "@/components/risk/v2/risk-hero-v2";
import { RiskGaugeGrid } from "@/components/risk/v2/risk-gauge-grid";
import { SevenLayerBreakdown } from "@/components/risk/v2/seven-layer-breakdown";
import { ConcentrationTable } from "@/components/risk/v2/concentration-table";
import { SectorExposureBlock } from "@/components/risk/v2/sector-exposure-block";
import { RiskTimelineChart } from "@/components/risk/v2/risk-timeline-chart";
import { CorrelationHeatmap } from "@/components/risk/v2/correlation-heatmap";

export function derivePosture(
  layersCount: number,
  breached: number,
  strained: number,
): "insufficient" | "composed" | "attentive" | "strained" | "breached" {
  // No layers means nothing was measured — not that everything measured came
  // back calm. Reporting "composed" here made an empty book indistinguishable
  // from a genuinely steady one, and the hero went on to claim "all layers
  // within band, none breached" about layers that were never observed.
  if (layersCount === 0) return "insufficient";
  if (breached >= 1) return "breached";
  if (strained >= 3) return "strained";
  if (strained >= 1) return "attentive";
  return "composed";
}

export default function RiskPageV2() {
  const { locale } = useLocale();
  const t = useT();
  const { data: summary } = useRiskSummary();
  const layersHook = useRiskLayers();
  const concentration = useConcentration(5);
  const sectorExposure = useSectorExposure();
  const timeline = useRiskTimeline(30);

  const layers = layersHook.layers;
  // Breach / strain counts come from the layers payload, not summary —
  // /api/risk/summary has no `layers_breached` field, so the prior
  // `summary?.layers_breached ?? 0` always rendered 0 ("none breached")
  // even when a layer was RED. Summary value (if a future backend release
  // publishes one) still takes precedence.
  const breachedCount = summary?.layers_breached ?? layersHook.breachedCount;
  const strainedCount = layersHook.strainedCount;
  const posture =
    summary?.posture ??
    derivePosture(layers.length, breachedCount, strainedCount);

  // Build "loudest signal" sentence — concentration is the canonical loud
  // signal per SPEC §1; falls back to a generic clause if missing.
  const loudestSignal =
    summary?.sector_top_name && summary?.sector_top_pct != null
      ? `Concentration is the loudest signal — ${summary.sector_top_name} weight at ${
          (summary.sector_top_pct > 1
            ? summary.sector_top_pct
            : summary.sector_top_pct * 100
          ).toFixed(1)
        }% of book.`
      : null;

  const observedAt = summary?.observed_at_kst ?? null;

  return (
    <ErrorBoundary>
      {/* TOP TICKER — full bleed */}
      <div
        className="-mx-4 md:-ml-10 md:-mr-10 mb-4"
        style={{ maxWidth: "100vw" }}
      >
        <TopTicker />
      </div>

      {/* LIVING CFO STATUS — sticky hairline.
       * z-10 (2026-05-13 thorough-fix sweep): was z-40, clipped the
       * NotificationDropdown panel by stacking above the TopBar wrapper
       * (z=20 in globals.css). */}
      <div
        className="sticky z-10 -mx-4 md:-ml-8 md:-mr-10 mb-2"
        style={{
          // Pin beneath the TopBar (56px) incl. notch safe-area on PWAs.
          // Token: --pq-aux-sticky-top (globals.css).
          top: "var(--pq-aux-sticky-top)",
          // FINDING-022: solid ink — semi-transparent bar bled scrolled content.
          background: "var(--pq-ink)",
        }}
      >
        <LivingCFOStatusBar />
      </div>

      {/* HERO */}
      <RiskHeroV2
        eyebrow={`Risk · 7-Layer Defense · ${new Date().toLocaleDateString(locale === "ko" ? "ko-KR" : "en-US", { weekday: "long", timeZone: "Asia/Seoul" })}`}
        posture={posture}
        breachedCount={breachedCount}
        strainedCount={strainedCount}
        loudestSignal={loudestSignal}
        observedAtKst={observedAt}
      />

      {/* BLOCKS */}
      {/* Not <main>: DashboardLayout already provides the page's single
          <main id="main-content"> landmark, and nesting a second one is
          invalid HTML — it gives the page two main landmarks and makes
          "skip to main content" ambiguous for screen readers. */}
      <div style={{ paddingTop: 56 }}>
        <RiskGaugeGrid summary={summary} layers={layers} />

        <SevenLayerBreakdown
          layers={layers}
          observedAtKst={observedAt ?? undefined}
        />

        {/* Correlation matrix — v1 RISK_CORRELATION parity (additive). */}
        <CorrelationHeatmap />

        <ConcentrationTable
          entries={concentration.entries}
          sumPct={concentration.sumPct}
        />

        <SectorExposureBlock
          sectors={sectorExposure.sectors}
          sectorCount={sectorExposure.sectorCount}
          cashPct={sectorExposure.cashPct}
        />

        <RiskTimelineChart
          series={timeline.series}
          today={timeline.today}
          avg={timeline.avg}
          max={timeline.max}
          daysAboveStrain={timeline.daysAboveStrain}
          strainThreshold={timeline.strainThreshold}
        />

        {/* Methodology rail — preserves v1 Methodology Notes */}
        <section style={{ marginBottom: 64 }} aria-label="Methodology notes">
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            {t("riskBoard.methodologyEyebrow")}
          </div>
          <EditorialHead size={32} as="h2" style={{ margin: "0 0 22px 0" }}>
            {t("riskBoard.methodologyHeading")}
          </EditorialHead>
          <ul
            style={{
              listStyle: "none",
              padding: 0,
              margin: 0,
              borderTop: "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
            }}
          >
            {[
              {
                k: "01",
                title: t("riskBoard.notes.var.title"),
                body: t("riskBoard.notes.var.body"),
              },
              {
                k: "02",
                title: t("riskBoard.notes.es.title"),
                body: t("riskBoard.notes.es.body"),
              },
              {
                k: "03",
                title: t("riskBoard.notes.hhi.title"),
                body: t("riskBoard.notes.hhi.body"),
              },
              {
                k: "04",
                title: t("riskBoard.notes.correlation.title"),
                body: t("riskBoard.notes.correlation.body"),
              },
              {
                k: "05",
                title: t("riskBoard.notes.sevenLayer.title"),
                body: t("riskBoard.notes.sevenLayer.body"),
              },
              {
                k: "06",
                title: t("riskBoard.notes.timeline.title"),
                body: t("riskBoard.notes.timeline.body"),
              },
            ].map((note, i, arr) => (
              <li
                key={note.k}
                style={{
                  display: "grid",
                  gridTemplateColumns: "40px 1fr",
                  gap: 16,
                  padding: "16px 0",
                  borderBottom:
                    i < arr.length - 1
                      ? "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))"
                      : "none",
                }}
              >
                <span
                  className="font-mono"
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    color: "var(--pq-bronze)",
                    letterSpacing: "0.04em",
                  }}
                >
                  {note.k}
                </span>
                <div>
                  <div
                    className="font-display"
                    style={{
                      fontSize: "var(--pq-text-h6)",
                      color: "var(--pq-ivory)",
                      letterSpacing: "-0.005em",
                      marginBottom: 4,
                    }}
                  >
                    {note.title}
                  </div>
                  <div
                    className="font-serif"
                    style={{
                      fontSize: "var(--pq-text-body)",
                      color: "rgba(245,240,232,0.70)",
                      lineHeight: 1.55,
                    }}
                  >
                    {note.body}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {/* Foot signature */}
      <div style={{ marginTop: 24 }}>
        <FootSignature />
      </div>
    </ErrorBoundary>
  );
}
