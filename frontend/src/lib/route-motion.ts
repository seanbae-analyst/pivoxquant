/**
 * Phone route motion — pure decisions (2026-10-09, CEO "최대한 앱처럼").
 *
 * Which way a dashboard navigation should move, and whether the window
 * scroll of the destination should come back. No DOM, no React — the
 * wrapper that acts on these lives in components/layout/phone-route-frame.
 *
 *   tab   — one bottom-nav destination to another: a quiet fade-through.
 *   push  — deeper into the same section (/journal → /journal/import):
 *           the new screen arrives from the right.
 *   pop   — back out of it (or any history back into a deeper screen):
 *           the screen arrives from the left.
 *   none  — same path (search/hash only) or the first render.
 */

export type RouteMotion = "tab" | "push" | "pop" | "none";

/**
 * Bottom-nav destinations whose window scroll is remembered and restored
 * whenever the user comes back, however they come back (a tab tap is a push
 * navigation, so without this it would always start at the top).
 *
 * /pre-trade is a flow, not a reading screen: its page state (the step)
 * starts over on every visit, so restoring an old scroll offset there would
 * land a fresh setup form half-scrolled.
 */
export const SCROLL_MEMORY_ROOTS: ReadonlyArray<string> = [
  "/mirror",
  "/journal",
  "/portfolio",
  "/settings",
];

function segments(path: string): string[] {
  return path.split("?")[0].split("#")[0].split("/").filter(Boolean);
}

/** True when `path` is one of the top-level dashboard screens (depth 1). */
export function isTopLevel(path: string): boolean {
  return segments(path).length === 1;
}

/**
 * How the screen should move from `prev` to `next`.
 *
 * `popped` — the change came from the history stack (back / forward / the
 * Android back button / an iOS edge swipe), not from a link or a push.
 */
export function classifyRouteChange(
  prev: string | null,
  next: string,
  popped: boolean,
): RouteMotion {
  if (prev === null || prev === next) return "none";
  const a = segments(prev);
  const b = segments(next);
  const sameSection = a.length > 0 && b.length > 0 && a[0] === b[0];
  let kind: RouteMotion;
  if (sameSection) {
    kind = b.length > a.length ? "push" : b.length < a.length ? "pop" : "tab";
  } else {
    // Another section: arriving at its root is a tab switch; arriving deep
    // inside it (a card that links to /journal/import) is a drill-down.
    kind = b.length <= 1 ? "tab" : "push";
  }
  // History back into a deeper screen still reads as "back".
  if (popped && kind === "push") return "pop";
  return kind;
}

/**
 * Whether the destination's remembered window scroll should be restored.
 * History moves always restore (that is what "back" means); other moves
 * restore only on the remembered tab roots — a drill-down starts at its top.
 */
export function shouldRestoreScroll(next: string, popped: boolean): boolean {
  if (popped) return true;
  const path = next.split("?")[0];
  return SCROLL_MEMORY_ROOTS.includes(path);
}
