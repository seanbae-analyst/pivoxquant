"use client";

/**
 * Fires a single `landing_view` funnel event on mount for the public OG card
 * landing. Rendered inside the server component so the page itself stays
 * static / cacheable while still emitting client-side telemetry.
 *
 * `refCode` (the inviter's referral code) is attached so a pre-signup view
 * can later be stitched to a `referral_signup`. Renders nothing.
 */

import { useEffect, useRef } from "react";
import { track } from "@/lib/track";

export function LandingViewTracker({
  refCode,
  channel,
  surface = "public_card",
}: {
  refCode?: string | null;
  channel?: string;
  /** Funnel surface label attached to meta — distinguishes the OG card
   *  landing ("public_card") from the main marketing landing ("landing"). */
  surface?: string;
}) {
  const fired = useRef(false);
  useEffect(() => {
    if (fired.current) return;
    fired.current = true;
    void track("landing_view", {
      refCode: refCode ?? undefined,
      channel,
      meta: { surface },
    });
  }, [refCode, channel, surface]);
  return null;
}
