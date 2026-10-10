/**
 * launch-cover — the installed app opens on its cover ("/"), once per launch.
 *
 * The manifest start_url is "/" (2026-10-10), but an install made while it was
 * "/mirror" keeps opening there (iOS saves the start URL at install). A launch
 * is the first page load of a session in the installed app, so: the cover marks
 * the session as covered, and a launch that lands on bare "/mirror" without
 * that mark goes to "/" first. Everything else is left alone — a reload, a URL
 * with a query, any other path (a notification or shortcut deep link), and the
 * browser.
 */

import { isStandaloneDisplay } from "@/components/pwa/app-cover";

const KEY = "pq_launch_cover";

/** Called by the cover ("/"): this session has shown it. */
export function markLaunchCovered(): void {
  try {
    window.sessionStorage.setItem(KEY, "1");
  } catch {
    /* storage blocked — the cover simply shows on the next launch too */
  }
}

/** True when this page load is an installed-app launch on bare "/mirror". */
export function shouldOpenOnCover(): boolean {
  if (typeof window === "undefined" || !isStandaloneDisplay()) return false;
  try {
    if (window.sessionStorage.getItem(KEY) === "1") return false;
  } catch {
    return false;
  }
  if (window.location.pathname !== "/mirror" || window.location.search) return false;
  const nav = window.performance?.getEntriesByType?.("navigation")?.[0] as
    | PerformanceNavigationTiming
    | undefined;
  // A reload or back/forward is not a launch.
  if (nav && nav.type !== "navigate") return false;
  return true;
}
