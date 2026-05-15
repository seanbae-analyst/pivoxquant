"use client";

/**
 * /home v2 — Direction B · Gallery layout.
 *
 * Source of truth: frontend/design-mockups/home-v2/{SPEC.md, MIGRATION.md}.
 * Toggle: NEXT_PUBLIC_HOME_V2=true. Default off; v1 remains live.
 *
 * Surface map (matches v1 17-module inventory):
 *   - TopTicker                 (reused, full-bleed)
 *   - LivingCFOStatusBar        (reused, sticky)
 *   - TodayMemoHeroV2           (new — editorial CFO hero)
 *   - 6-card gallery (3×2):
 *       1. PortfolioSnapshotCard  (NAV / spark / Today P/L / Positions / Cash%)
 *       2. RiskBoardCard          (4 horizontal CSS gauges + composure word)
 *       3. EarningsPreBriefCard   (graceful empty until backend ships)
 *       4. PositionsTopCard       (top 5 by weight, mini-rows)
 *       5. SignalsCard            (top 3 POSITIVE/NEGATIVE/NEUTRAL)
 *       6. CompanionArchiveCard   (artifact count + last 3)
 *   - WeeklyPulseCard           (reused, invisible Mon 07:00 trigger)
 *   - UpsellPlus                (reused, conditional on free tier)
 *   - FootSignature             (reused, page foot)
 *   - DisclaimerBanner          (mounted by (dashboard)/layout.tsx — NOT here)
 *
 * Deep links replace the 5 dense surfaces v1 carried inline:
 *   Watchlist table         → /watchlist
 *   EquityCurveChart        → /portfolio
 *   SectorAllocationDonut   → /portfolio
 *   CandlestickChart        → /detail/[ticker]
 *   PulseActivity table     → /portfolio
 *
 * Legal: POSITIVE / NEGATIVE / NEUTRAL only. No BUY/SELL/HOLD/recommend/advice.
 */

import * as React from "react";

import { ErrorBoundary } from "@/components/ui/error-boundary";
import { EditorialHead, FootSignature } from "@/components/ui/editorial";

import { TopTicker } from "@/components/terminal/top-ticker";

import { LivingCFOStatusBar } from "@/components/dashboard/living-cfo-status";
import { WeeklyPulseCard } from "@/components/dashboard/weekly-pulse";
import { UpsellPlus } from "@/components/dashboard/upsell-plus";

import { useAuth } from "@/lib/auth";
// Morning Brief deprecated 2026-04-29 — useMorningBrief removed.

import { TodayMemoHeroV2 } from "@/components/home/v2/today-memo-hero-v2";
import { HomeCardStyles } from "@/components/home/v2/home-card";
import { PortfolioSnapshotCard } from "@/components/home/v2/portfolio-snapshot-card";
import { RiskBoardCard } from "@/components/home/v2/risk-board-card";
import { EarningsPreBriefCard } from "@/components/home/v2/earnings-pre-brief-card";
import { PositionsTopCard } from "@/components/home/v2/positions-top-card";
import { SignalsCard } from "@/components/home/v2/signals-card";
import { CompanionArchiveCard } from "@/components/home/v2/companion-archive-card";

// Morning Brief types removed 2026-04-29 — backend deprecated.

export default function HomePageV2() {
  const { user } = useAuth();
  // Morning Brief hook removed — hero now in empty/coming-soon state.
  const heroHeadline: string | null = null;
  const heroBody: string | null = null;
  const audioDuration: string | null = null;
  const briefLoading = false;

  const displayName = user?.name?.split(" ")[0] || "Observer";

  return (
    <ErrorBoundary>
      <HomeCardStyles />

      {/* Visually hidden page heading for AT / heading-order. */}
      <h1 className="sr-only">홈 — 포트폴리오 대시보드</h1>

      {/* ═══════════ TOP TICKER — live strip (full bleed) ═══════════ */}
      <div
        className="-mx-4 md:-ml-10 md:-mr-10 mb-4"
        style={{ maxWidth: "100vw" }}
      >
        <TopTicker />
      </div>

      {/* ═══════════ LIVING CFO STATUS — sticky hairline ═══════════
       * z-10 (2026-05-13 thorough-fix sweep): was z-40 which created a
       * stacking context above the TopBar wrapper (z=20 in globals.css),
       * clipping the NotificationDropdown panel from the topbar. The bar
       * sticks under the TopBar (`top: 56`) so it never needs to render
       * above it. Pattern mirrored across home / portfolio / risk /
       * settings / reports / profile v2 pages + home v1. */}
      <div
        className="sticky z-10 -mx-4 md:-ml-8 md:-mr-10 mb-2"
        style={{
          top: 56,
          // FINDING-022: was rgba(5,5,5,0.78) + blur — scrolled content
          // bled through the semi-transparent bar. Solid ink so the sticky
          // header always wins the stack cleanly.
          background: "var(--pq-ink)",
        }}
      >
        <LivingCFOStatusBar />
      </div>

      {/* ═══════════ HERO — Today's Memo (editorial) ═══════════ */}
      <TodayMemoHeroV2
        headline={heroHeadline}
        body={heroBody}
        audioDuration={audioDuration}
        displayName={displayName}
        loading={briefLoading && heroHeadline == null}
      />

      {/* ═══════════ GALLERY — 6 cards, 3 × 2 ═══════════ */}
      <section
        className="mb-10"
        aria-label="Six rooms"
        style={{ marginBottom: 40 }}
      >
        {/* Section header */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-between",
            marginBottom: 24,
          }}
        >
          <div>
            <div
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.22em",
                color: "var(--pq-bronze)",
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              The Book · Snapshot
            </div>
            <EditorialHead size={40} as="h2">
              Six rooms.
            </EditorialHead>
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
            gap: 12,
          }}
          className="pq-home-grid-v2"
        >
          <PortfolioSnapshotCard />
          <RiskBoardCard />
          <EarningsPreBriefCard />
          <PositionsTopCard />
          <SignalsCard />
          <CompanionArchiveCard />
        </div>

        {/* Mobile/tablet collapse */}
        <style jsx>{`
          @media (max-width: 1023px) {
            .pq-home-grid-v2 {
              grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            }
          }
          @media (max-width: 767px) {
            .pq-home-grid-v2 {
              grid-template-columns: 1fr !important;
            }
          }
        `}</style>
      </section>

      {/* ═══════════ Premium Plus upsell (conditional) ═══════════ */}
      <div className="mt-4">
        <UpsellPlus />
      </div>

      {/* ═══════════ Foot signature ═══════════ */}
      {/* Legal disclaimer is mounted once by (dashboard)/layout.tsx as a
          path-aware footer — do not re-mount here. */}
      <div className="mt-6">
        <FootSignature />
      </div>

      {/* Weekly Pulse — auto-triggers Monday 07:00 KST (invisible) */}
      <WeeklyPulseCard />
    </ErrorBoundary>
  );
}
