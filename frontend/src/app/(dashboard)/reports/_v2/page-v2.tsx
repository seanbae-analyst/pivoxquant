"use client";

/**
 * /reports v2 — "CFO Archive" editorial layout.
 *
 * Source of truth: frontend/design-mockups/reports-v2/{SPEC.md, MIGRATION.md, mockup.html}.
 * Toggle: NEXT_PUBLIC_REPORTS_V2=true. Default off; v1 (`_v1/page-v1.tsx`) remains live.
 *
 * Surface map (matches reports-v2 SPEC §0):
 *   - TopTicker                    (reused, full-bleed)
 *   - LivingCFOStatusBar           (reused, sticky)
 *   - ReportsHeroV2                (new — 48px Playfair "Archive" hero)
 *   - LatestArtifactCard           (new — full-width 2-col card)
 *   - ArtifactGalleryGrid          (new — 3×2 of ArtifactKindCard)
 *   - GenerateArtifactCta          (new — 3 request tiles)
 *   - YearTimelineBlock            (new — 12-month rolling list)
 *   - WeeklyPulseCard              (reused, invisible Mon trigger)
 *   - UpsellPlus                   (reused, conditional)
 *   - FootSignature                (reused, page foot)
 *   - DisclaimerBanner             (mounted by (dashboard)/layout.tsx — NOT here)
 *
 * v1 inventory mapping (per task SPEC §8):
 *   - CATALOG 18종 전수             → 6 user-facing kinds (gallery) + 18 preview
 *                                      routes preserved at `/reports/preview/*`
 *   - tier-gating                   → ArtifactKindCard internal lock + Generate CTA
 *   - persona filter                → preserved in v1; not in v2 hero (planned chip
 *                                      filter in §3 follow-up)
 *   - SectionFeedbackBar            → preserved in v1
 *   - PeerBenchmarkBlock            → preserved in v1
 *   - liveByType Map                → re-implemented in ArtifactGalleryGrid via
 *                                      `findLatestByType()`
 *   - /reports/preview/* 18 routes  → untouched, linked from each kind card
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. No BUY/SELL/HOLD/recommend/advice.
 */

import * as React from "react";

import { ErrorBoundary } from "@/components/ui/error-boundary";
import { FootSignature } from "@/components/ui/editorial";

import { TopTicker } from "@/components/terminal/top-ticker";
import { LivingCFOStatusBar } from "@/components/dashboard/living-cfo-status";
import { WeeklyPulseCard } from "@/components/dashboard/weekly-pulse";
import { UpsellPlus } from "@/components/dashboard/upsell-plus";

import {
  useArtifacts,
  usePortfolioPositions,
  useWatchlist,
  resolveTickerName,
  useArtifactStats,
  deriveArtifactStats,
} from "@/lib/hooks";
import { useAuth } from "@/lib/auth";
import type { Artifact, Position, PortfolioResponse } from "@/lib/types";
import { useT } from "@/lib/locale";

import { ReportsHeroV2 } from "@/components/reports/v2/reports-hero-v2";
import { LatestArtifactCard } from "@/components/reports/v2/latest-artifact-card";
import { ArtifactGalleryGrid } from "@/components/reports/v2/artifact-gallery-grid";
import { GenerateArtifactCta } from "@/components/reports/v2/generate-artifact-cta";
import { YearTimelineBlock } from "@/components/reports/v2/year-timeline-block";
import type { Tier } from "@/components/reports/v2/artifact-kind-card";

/**
 * Collapse the backend's 5-value tier space onto the 3-value UI `Tier`.
 *
 * founding_lifetime / premium_plus carry every premium entitlement on the
 * backend (the PAID_TIERS_* frozensets include both — see
 * services/artifacts/_tiers.py), so they map to "premium" here. 2026-06-11
 * fix: the previous raw `as Tier` cast let those strings through, and the
 * v2 components' 3-key TIER_RANK lookups ranked them `undefined` → a
 * founding user saw EVERY tile locked, including the free Brag Card
 * ("Upgrade to free"). Same bug class as the tier-gate.tsx P1 fix —
 * normalise at the page boundary so every v2 consumer inherits it.
 */
export function toUiTier(raw: string | undefined | null): Tier {
  if (raw === "premium_plus" || raw === "founding_lifetime") return "premium";
  return raw === "pro" || raw === "premium" ? raw : "free";
}

function pickLatest(artifacts: Artifact[]): Artifact | null {
  let best: Artifact | null = null;
  let bestTs = -Infinity;
  for (const a of artifacts) {
    const ts = a.sent_at ? Date.parse(a.sent_at) : 0;
    if (ts > bestTs) {
      bestTs = ts;
      best = a;
    }
  }
  return best;
}

export default function ReportsPageV2() {
  const t = useT();
  const { user } = useAuth();
  const tier = toUiTier(user?.subscription_tier);

  // Pull a generous window so the gallery + year timeline can derive
  // stats client-side until the dedicated endpoints land.
  const { artifacts, isLoading } = useArtifacts({
    type: "all",
    since: "all",
    limit: 999,
  });

  // Stats: prefer server endpoint, fall back to client derivation when 404.
  const statsSwr = useArtifactStats();
  const stats = React.useMemo(
    () => statsSwr.data ?? deriveArtifactStats(artifacts),
    [statsSwr.data, artifacts],
  );

  const positionsSwr = usePortfolioPositions<PortfolioResponse>();
  const watchlistSwr = useWatchlist();
  const positions: Position[] = React.useMemo(
    () => positionsSwr.data?.positions ?? [],
    [positionsSwr.data?.positions],
  );
  const watchlist = React.useMemo(
    () => watchlistSwr.data?.watchlist ?? [],
    [watchlistSwr.data?.watchlist],
  );
  const resolveName = React.useCallback(
    (ticker: string) => resolveTickerName(ticker, positions, watchlist),
    [positions, watchlist],
  );

  const latest = React.useMemo(() => pickLatest(artifacts), [artifacts]);

  return (
    <ErrorBoundary>
      {/* TOP TICKER — full bleed */}
      <div
        className="-mx-4 md:-ml-10 md:-mr-10 mb-4"
        style={{ maxWidth: "100vw" }}
      >
        <TopTicker />
      </div>

      {/* LIVING CFO STATUS — sticky.
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
      <ReportsHeroV2
        eyebrow={t("reports.v2.eyebrow")}
        counts={{
          memos: stats.countMemos,
          briefs: stats.countBriefs,
          bragCards: stats.countBragCards,
        }}
        loading={isLoading && artifacts.length === 0}
      />

      {/* MAIN — CEO 2026-05-28: 모바일에서 56px 고정 패딩 → clamp 으로 28~56px */}
      <main style={{ paddingTop: "clamp(28px, 6vw, 56px)" }}>
        {/* BLOCK 1 — Latest artifact */}
        <section aria-labelledby="latest-heading">
          <h2
            id="latest-heading"
            className="font-display"
            style={{
              fontWeight: 500,
              fontSize: "clamp(26px, 3.4vw, 40px)",
              lineHeight: 1.1,
              color: "var(--pq-ivory, #F5F0E8)",
              margin: "0 0 24px",
            }}
          >
            {t("reports.v2.latestHeading")}
          </h2>
          <LatestArtifactCard
            artifact={latest}
            loading={isLoading && artifacts.length === 0}
            resolveName={resolveName}
          />
        </section>

        {/* BLOCK 2 — Gallery */}
        <ArtifactGalleryGrid artifacts={artifacts} tier={tier} />

        {/* BLOCK 3 — Generate CTAs */}
        <GenerateArtifactCta tier={tier} />

        {/* BLOCK 4 — Year timeline */}
        <YearTimelineBlock
          artifacts={artifacts}
          loading={isLoading && artifacts.length === 0}
        />
      </main>

      {/* Pulse + upsell (reused, conditional) */}
      <UpsellPlus />
      <WeeklyPulseCard />

      {/* Foot signature — DisclaimerBanner mounted by (dashboard)/layout.tsx */}
      <FootSignature note={t("reports.v2.footNote")} />
    </ErrorBoundary>
  );
}
