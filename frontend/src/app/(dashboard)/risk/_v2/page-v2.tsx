"use client";

/**
 * /risk v2 — "Risk Board" editorial layout.
 *
 * Source of truth: frontend/design-mockups/risk-v2/{SPEC.md, MIGRATION.md, mockup.html}.
 * Toggle: NEXT_PUBLIC_RISK_V2=true. Default off; v1 remains live.
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
import { useLocale } from "@/lib/locale";

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

function derivePosture(
  layersCount: number,
  negatives: number,
): "composed" | "attentive" | "strained" | "breached" {
  if (layersCount === 0) return "composed";
  if (negatives >= 3) return "strained";
  if (negatives >= 1) return "attentive";
  return "composed";
}

export default function RiskPageV2() {
  const { locale } = useLocale();
  const { data: summary } = useRiskSummary();
  const layersHook = useRiskLayers();
  const concentration = useConcentration(5);
  const sectorExposure = useSectorExposure();
  const timeline = useRiskTimeline(30);

  const layers = layersHook.layers;
  const negatives = layers.filter((l) => l.status === "NEGATIVE").length;
  const posture =
    summary?.posture ?? derivePosture(layers.length, negatives);
  const breachedCount = summary?.layers_breached ?? 0;

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

      {/* LIVING CFO STATUS — sticky hairline */}
      <div
        className="sticky z-40 -mx-4 md:-ml-8 md:-mr-10 mb-2"
        style={{
          top: 56,
          background: "rgba(5,5,5,0.78)",
          backdropFilter: "blur(6px)",
          WebkitBackdropFilter: "blur(6px)",
        }}
      >
        <LivingCFOStatusBar />
      </div>

      {/* HERO */}
      <RiskHeroV2
        eyebrow={`Risk · 7-Layer Defense · ${new Date().toLocaleDateString(locale === "ko" ? "ko-KR" : "en-US", { weekday: "long" })}`}
        posture={posture}
        breachedCount={breachedCount}
        strainedCount={negatives}
        loudestSignal={loudestSignal}
        observedAtKst={observedAt}
      />

      {/* BLOCKS */}
      <main style={{ paddingTop: 56 }}>
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
              fontSize: 10.5,
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            Methodology · How these are observed
          </div>
          <EditorialHead size={32} as="h2" style={{ margin: "0 0 22px 0" }}>
            Notes.
          </EditorialHead>
          <ul
            style={{
              listStyle: "none",
              padding: 0,
              margin: 0,
              borderTop: "1px solid var(--pq-hairline, rgba(245,240,232,0.08))",
            }}
          >
            {[
              {
                k: "01",
                title: "VaR (1-day, 95%)",
                body: "Historical percentile on the 90-day return window, weighted by position size.",
              },
              {
                k: "02",
                title: "Component Expected Shortfall",
                body: "Mean of returns below the VaR cutoff — the 5% left-tail observation.",
              },
              {
                k: "03",
                title: "Concentration HHI",
                body: "Herfindahl–Hirschman index on sector weights. < 0.25 considered diffuse.",
              },
              {
                k: "04",
                title: "Correlation",
                body: "Pairwise 90-day returns, Ledoit–Wolf shrunk covariance. Cluster max flagged when > 0.65.",
              },
              {
                k: "05",
                title: "7-Layer Defense",
                body: "Independent observations across VaR, correlation, VIX, tail, daily drawdown, sector concentration, and cash buffer.",
              },
              {
                k: "06",
                title: "Composite timeline",
                body: "0–100 score derived from rolling VaR; higher = more strain. Backend may publish a first-class composite score in a future release.",
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
                      ? "1px solid var(--pq-hairline, rgba(245,240,232,0.08))"
                      : "none",
                }}
              >
                <span
                  className="font-mono"
                  style={{
                    fontSize: 12,
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
                      fontSize: 16,
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
                      fontSize: 13,
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
      </main>

      {/* Foot signature */}
      <div style={{ marginTop: 24 }}>
        <FootSignature />
      </div>
    </ErrorBoundary>
  );
}
