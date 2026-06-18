"use client";

/**
 * /mirror — 거울 (the Mirror home).
 *
 * The Mirror-centric home surface: one upright editorial sentence about who
 * you ARE vs how you've TRADED (선언 vs 관찰), the 9-axis shape gap, last
 * week's AI-twin paper return vs yours, and a single pause-and-reflect nudge
 * into 「멈춤」. The behavioural loop's face: 멈춤 → 기록 → 거울.
 *
 * Additive route — does NOT replace /home (no feature flag flip here). The
 * page-level legal footer is mounted by (dashboard)/layout.tsx (/mirror →
 * "coaching"); the inline DisclaimerBanner below is the contextual
 * behaviour-mirror copy for the persona/behaviour data on this surface.
 *
 * Legal: 3 disclosed buckets only, POSITIVE/NEGATIVE/NEUTRAL framing, no
 * advice, no score on the radar. No italic (CEO 2026-06-15).
 */
import * as React from "react";

import { useAuth } from "@/lib/auth";
import { useMirrorHome } from "@/lib/hooks";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { EditorialHead, FootSignature } from "@/components/ui/editorial";
import { TopTicker } from "@/components/terminal/top-ticker";
import { LivingCFOStatusBar } from "@/components/dashboard/living-cfo-status";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { MirrorHeadline } from "@/components/mirror/mirror-headline";
import { SelfObservedRadar } from "@/components/mirror/self-observed-radar";
import { TwinWeekCard } from "@/components/mirror/twin-week-card";
import { OneThingNudge } from "@/components/mirror/one-thing-nudge";
import { ArchiveLinks } from "@/components/mirror/archive-links";

function LegendDot({ colorVar, label }: { colorVar: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-block h-2 w-2 rounded-full"
        style={{ background: `var(${colorVar})` }}
      />
      {label}
    </span>
  );
}

function MirrorSkeleton() {
  const bar = { background: "rgba(var(--pq-ivory-rgb), 0.06)" };
  return (
    <div className="space-y-4" aria-hidden>
      <div className="h-6 w-40 animate-pulse rounded" style={bar} />
      <div className="h-16 w-full animate-pulse rounded" style={bar} />
      <div className="h-[280px] w-full animate-pulse rounded" style={bar} />
    </div>
  );
}

export default function MirrorPage() {
  const { loading: authLoading } = useAuth();
  const { data, isLoading, error } = useMirrorHome();

  const showSkeleton = authLoading || isLoading;
  const showError = !showSkeleton && (Boolean(error) || !data);

  return (
    <div className="min-h-screen bg-[rgb(5,5,5)] text-[var(--pq-ivory)]">
      <TopTicker />
      <LivingCFOStatusBar />

      <div className="mx-auto max-w-3xl space-y-8 px-5 py-8 md:px-8">
        <EditorialHead>거울</EditorialHead>

        {showSkeleton && <MirrorSkeleton />}

        {showError && (
          <p
            className="text-[13px]"
            style={{ color: "rgba(var(--pq-ivory-rgb), 0.55)" }}
          >
            거울을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.
          </p>
        )}

        {data && (
          <ErrorBoundary>
            <div className="space-y-8">
              <MirrorHeadline data={data} />

              <section
                className="rounded-[4px] p-4"
                style={{ border: "1px solid var(--pq-ivory-line)" }}
              >
                <div className="flex items-center justify-between">
                  <div className="text-[12.5px]" style={{ color: "var(--pq-ivory)" }}>
                    선언 vs 관찰
                  </div>
                  <div
                    className="flex items-center gap-3 text-[10.5px]"
                    style={{ color: "rgba(var(--pq-ivory-rgb), 0.55)" }}
                  >
                    <LegendDot colorVar="--pq-bronze" label="선언(설문)" />
                    <LegendDot colorVar="--pq-ivory" label="관찰(30일)" />
                  </div>
                </div>

                <div className="mt-2 flex justify-center">
                  <SelfObservedRadar
                    className="w-full max-w-[460px]"
                    labels={data.radar.labels}
                    declared={data.radar.declared}
                    observed={data.radar.observed}
                  />
                </div>

                <p
                  className="mt-1 text-center text-[10.5px]"
                  style={{ color: "var(--pq-bronze)" }}
                >
                  각 축의 % = 최근 30일 관찰값 · 브론즈=선언, 아이보리=관찰
                </p>
              </section>

              <TwinWeekCard twin={data.twin} />
              <OneThingNudge data={data} />
              <ArchiveLinks />

              <DisclaimerBanner type="behavior-mirror" />
            </div>
          </ErrorBoundary>
        )}
      </div>

      <FootSignature />
    </div>
  );
}
