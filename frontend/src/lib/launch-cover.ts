/**
 * launch-cover — the installed app opens on its cover ("/"), once per launch.
 *
 * The manifest start_url is "/" (2026-10-10), but an install made while it was
 * "/mirror" keeps opening there (iOS saves the start URL at install). A launch
 * is the first page load of a session in the installed app, so: the cover marks
 * the session as covered, and a launch that lands on bare "/mirror" without
 * that mark goes to "/" first. Everything else is left alone — a reload, a URL
 * with a query, any other path (a shortcut deep link), a notification tap, and
 * the browser.
 *
 * A notification tap is told apart by the mark the service worker puts on the
 * URL it opens (2026-10-15 bug hunt: the concentration alert opens bare
 * "/mirror", so a cold launch from it was bounced to the cover).
 */

import { isStandaloneDisplay } from "@/components/pwa/app-cover";

const KEY = "pq_launch_cover";

/**
 * Query parameter on a window opened from a notification, value "push" —
 * written by public/sw.js (NOTIFICATION_LAUNCH_PARAM there; keep the two in
 * step).
 */
export const NOTIFICATION_LAUNCH_PARAM = "pq_launch";

/** Called by the cover ("/"): this session has shown it. */
export function markLaunchCovered(): void {
  try {
    window.sessionStorage.setItem(KEY, "1");
  } catch {
    /* storage blocked — the cover simply shows on the next launch too */
  }
}

/**
 * The URL this session's document was loaded at. The dashboard layout can
 * mount again later in the session on a bare "/mirror" the user walked to;
 * what counts is where the app was launched.
 */
function launchUrl(nav: PerformanceNavigationTiming | undefined): URL {
  try {
    if (nav?.name) return new URL(nav.name, window.location.href);
  } catch {
    /* not a URL — fall back to where the page is now */
  }
  return new URL(window.location.href);
}

/** True when this page load is an installed-app launch on bare "/mirror". */
export function shouldOpenOnCover(): boolean {
  if (typeof window === "undefined" || !isStandaloneDisplay()) return false;
  try {
    if (window.sessionStorage.getItem(KEY) === "1") return false;
  } catch {
    return false;
  }
  const nav = window.performance?.getEntriesByType?.("navigation")?.[0] as
    | PerformanceNavigationTiming
    | undefined;
  // A reload or back/forward is not a launch.
  if (nav && nav.type !== "navigate") return false;
  const launched = launchUrl(nav);
  if (launched.searchParams.get(NOTIFICATION_LAUNCH_PARAM) === "push") {
    // Opened to see what the notification named: this session skips the cover.
    markLaunchCovered();
    return false;
  }
  return launched.pathname === "/mirror" && !launched.search;
}
