"use client";

/**
 * <RouteSkeleton> — what a dashboard screen shows while its route is still
 * loading ((dashboard)/loading.tsx, 2026-10-09).
 *
 * Measured before: with the screen's data 2.5 s late, tapping 멈춤 left the
 * old screen up for 2.7 s — the tap looked ignored. This renders inside the
 * dashboard shell, so the app bar and the bottom nav stay exactly where they
 * are and only the content area turns into quiet ink placeholders: a tab
 * strip line and a few card blocks, the shape every phone screen shares. No
 * spinner. The shimmer is the shared `pq-skeleton-dark` (globals.css); it is
 * switched off here under prefers-reduced-motion (the placeholders stay).
 *
 * As it leaves (the real screen is ready), it asks the route frame to fade
 * the screen in, so content does not pop over the placeholders.
 */

import { useLayoutEffect } from "react";
import { Skeleton } from "@/components/ui/loading-skeleton";
import { revealRouteContent } from "@/components/layout/phone-route-frame";

const CARD_ROWS = [0, 1, 2] as const;
/** Square-ish corners like the cards; no shimmer under reduced motion. */
const BAR = "rounded-[2px] motion-reduce:animate-none!";

export function RouteSkeleton() {
  // Cleanup runs in the commit that removes the skeleton, before paint.
  useLayoutEffect(() => () => revealRouteContent(), []);

  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className="space-y-5 py-2 md:space-y-6 md:py-0"
      data-testid="route-skeleton"
    >
      <span className="sr-only">불러오는 중</span>
      {/* Phone: a pager tab strip / section line under the app bar. */}
      <div className="-mx-4 flex h-12 items-end gap-6 border-b border-[var(--pq-ivory-line)] px-4 pb-3 md:hidden">
        <Skeleton className={`h-3 w-12 ${BAR}`} />
        <Skeleton className={`h-3 w-10 ${BAR}`} />
        <Skeleton className={`h-3 w-14 ${BAR}`} />
      </div>
      {/* Desktop: the editorial heading line. */}
      <Skeleton className={`hidden h-8 w-48 md:block ${BAR}`} />
      {CARD_ROWS.map((i) => (
        <div
          key={i}
          className="space-y-3 rounded-[2px] border border-[var(--pq-ivory-line)] bg-[var(--pq-card-veil)] p-5"
        >
          <Skeleton className={`h-3 w-24 ${BAR}`} />
          <Skeleton className={`${i === 0 ? "h-16" : "h-10"} w-full ${BAR}`} />
          <Skeleton className={`h-3 w-2/3 ${BAR}`} />
        </div>
      ))}
    </div>
  );
}
