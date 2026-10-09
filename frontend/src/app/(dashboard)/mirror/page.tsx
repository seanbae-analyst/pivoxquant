"use client";

/**
 * /mirror — 거울 (the Mirror home).
 *
 * The Mirror-centric home surface: one upright editorial sentence about who
 * you ARE vs how you've TRADED (선언 vs 관찰), the 9-axis shape gap, last
 * and a single pause-and-reflect nudge
 * into 「멈춤」. The behavioural loop's face: 멈춤 → 기록 → 거울.
 *
 * /home redirects here. The legal disclaimer is mounted once by
 * (dashboard)/layout.tsx (/mirror → "behavior-mirror"); this page mounts none.
 *
 * 2026-09-29: the collapsed 「자세히」 area (MirrorDetails) is gone. Its only
 * content was PersonaEvolution — a 12-week 0–100 "persona score" line — and
 * scores are not made (CLAUDE.md). The drift this page reads is the text
 * descriptor from persona_history.compute_drift, not a score.
 *
 * 2026-10-09 (CEO "앱처럼"): on a phone (<768px, incl. the installed PWA)
 * the ready state is MirrorPhoneCards — the same blocks as swipeable story
 * cards. Skeleton / error / empty states and the desktop column are as before.
 *
 * Legal: 3 disclosed buckets only, POSITIVE/NEGATIVE/NEUTRAL framing, no
 * advice, no score on the radar. No italic (CEO 2026-06-15).
 */
import * as React from "react";

import { useAuth } from "@/lib/auth";
import { useMirrorHome } from "@/lib/hooks";
import { useIsPhone } from "@/lib/use-phone";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { EditorialHead, FootSignature } from "@/components/ui/editorial";
import { MirrorHeadline } from "@/components/mirror/mirror-headline";
import { MirrorRadarPanel } from "@/components/mirror/mirror-radar-panel";
import { MirrorPhoneCards } from "@/components/mirror/mirror-phone-cards";
import { OneThingNudge } from "@/components/mirror/one-thing-nudge";
import { PullToRefresh } from "@/components/layout/pull-to-refresh";
import { LastSyncNote } from "@/components/mirror/last-sync-note";

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
  const { data, isLoading, error, mutate } = useMirrorHome();
  // Phone pull-to-refresh re-reads the mirror (the hook's own key).
  const refresh = React.useCallback(() => mutate(), [mutate]);
  const isPhone = useIsPhone();

  // A 200 is not the same as a usable payload. A backend that answers this
  // route with a partial body — `{}` from a proxy stub, a half-migrated
  // deploy, a serializer that dropped a key — used to reach
  // `data.radar.labels` and throw during THIS component's render, which the
  // ErrorBoundary below could not catch because the JSX was evaluated here
  // rather than inside a child. The whole surface white-screened, and
  // /mirror is the product's front door.
  const ready = Boolean(
    data && data.radar && Array.isArray(data.radar.labels) && Array.isArray(data.radar.declared),
  );
  const showSkeleton = authLoading || isLoading;
  const showError = !showSkeleton && Boolean(error);
  const showEmpty = !showSkeleton && !showError && !ready;

  const errorLine = (
    <p className="text-[13px]" style={{ color: "rgba(var(--pq-ivory-rgb), 0.55)" }}>
      거울을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.
    </p>
  );

  // Phone, ready: the story cards fill the space between the app bar and the
  // bottom nav (PhonePager sizes itself), so no page wrapper or extra gutter.
  // The footer signature is desktop-only, so there is nothing to put under it.
  // A failed revalidation over cached data keeps the cards and shows the same
  // error line above them, as the desktop column does.
  if (isPhone && ready && data && !showSkeleton) {
    return (
      <PullToRefresh onRefresh={refresh}>
        <ErrorBoundary>
          <MirrorPhoneCards
            data={data}
            header={
              showError ? (
                <div className="pb-3">{errorLine}</div>
              ) : (
                // On-device copy older than 10 min: say when it was fetched
                // (renders nothing otherwise — lib/persisted-swr-cache).
                <LastSyncNote className="pb-3" />
              )
            }
          />
        </ErrorBoundary>
      </PullToRefresh>
    );
  }

  return (
    <PullToRefresh onRefresh={refresh}>
      <div className="min-h-screen bg-[rgb(5,5,5)] text-[var(--pq-ivory)]">

        {/* Phone: the app bar names the screen and <main> already pads it, so
            the page drops its own title and second gutter (2026-10-07). */}
        <div className="mx-auto max-w-3xl space-y-8 px-0 py-2 md:px-8 md:py-8">
          <div className="hidden md:block">
            <EditorialHead>거울</EditorialHead>
          </div>

          {showSkeleton && <MirrorSkeleton />}

          {showError && errorLine}

          {ready && !showError && <LastSyncNote />}

          {showEmpty && (
            <div className="space-y-3">
              <p className="text-[13px]" style={{ color: "var(--pq-ivory)" }}>
                아직 비출 기록이 없어요.
              </p>
              <p
                className="text-[12.5px]"
                style={{ color: "rgba(var(--pq-ivory-rgb), 0.55)", lineHeight: 1.6 }}
              >
                보유 종목을 등록하고 사기 전에 이유를 남기면, 선언한 나와 기록 속의
                나를 나란히 보여드립니다.
              </p>
            </div>
          )}

          {ready && data && (
            <ErrorBoundary>
              <div className="space-y-8">
                <MirrorHeadline data={data} />

                <MirrorRadarPanel data={data} />

                <OneThingNudge data={data} />
              </div>
            </ErrorBoundary>
          )}
        </div>

        <FootSignature />
      </div>
    </PullToRefresh>
  );
}
