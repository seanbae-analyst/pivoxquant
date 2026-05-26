"use client";

/**
 * Fires a single `landing_view` funnel event for the MAIN marketing landing
 * (pivoxquant.com → LandingV2). Without this, UTM-tagged campaign traffic
 * (e.g. ?utm_source=naver_cafe) that lands on the home page is never recorded
 * in funnel_events.channel, so channel-level acquisition can't be attributed.
 *
 * Channel is derived from the URL: utm_source, falling back to utm_medium.
 * A ?ref=<code> referral code (if present) is forwarded as the inviter code.
 * Reuses the public-card LandingViewTracker (fired useRef guard + track call)
 * with surface="landing". Attribution is read synchronously under a
 * typeof-window guard so the channel is known before the child fires once.
 * Renders nothing.
 */

import { LandingViewTracker } from "./landing-view-tracker";

function deriveAttribution(): {
  channel?: string;
  refCode?: string | null;
} {
  if (typeof window === "undefined") return {};
  const params = new URLSearchParams(window.location.search);
  const channel =
    params.get("utm_source") || params.get("utm_medium") || undefined;
  const ref = params.get("ref");
  return {
    channel: channel ?? undefined,
    refCode: ref && ref.trim().length > 0 ? ref : null,
  };
}

export function MainLandingViewTracker() {
  const { channel, refCode } = deriveAttribution();
  return (
    <LandingViewTracker channel={channel} refCode={refCode} surface="landing" />
  );
}
