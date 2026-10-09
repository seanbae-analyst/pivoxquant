"use client";

/**
 * useBackDismiss — Android back / browser back closes an overlay.
 * --------------------------------------------------------------------------
 * A phone user (installed PWA especially) expects the system back gesture to
 * close the sheet or drawer on screen, not to leave the page under it. While
 * `open` is true this hook keeps one extra history entry on top of the stack:
 *
 *   open            → history.pushState({...state, __pqOverlays: [..., id]})
 *   back pressed    → popstate; the entry is gone → onClose()
 *   closed in-app   → the entry is ours and still on top → history.go(-n)
 *                     (batched, so two overlays closing in the same tick —
 *                     a nested sheet and its parent — pop both at once)
 *
 * Things it deliberately does NOT do:
 *   - No double back. A close that came from the back button finds its entry
 *     already popped and leaves history alone.
 *   - No fight with routing. A same-origin link clicked inside the overlay is
 *     a navigation, so the cleanup skips its `go(-n)` (going back would cancel
 *     the navigation Next.js is about to commit).
 *   - No leftover entry after such a link. The overlay's entry is a copy of
 *     the page under it, so a push on top of it would leave two entries for
 *     that page and the second Back would look dead. Instead the link
 *     navigates with `router.replace`, which turns the overlay's entry into
 *     the new route: page → [sheet] → 설정 becomes page → 설정, and one Back
 *     from 설정 lands on the page that opened the sheet.
 *     Programmatic navigations do the same through `navigateFromOverlay`.
 *   - The URL never changes — the entry copies `history.state`, which keeps
 *     Next.js's `__NA` tree marker, so its popstate handler restores the same
 *     route instead of reloading.
 *
 * Stable API (components/ui/sheet.tsx uses it):
 *
 *     useBackDismiss(open, onClose)
 *     useBackDismiss(open, onClose, { enabled, blocked })
 *
 *   enabled — false: never push an entry (e.g. a legally blocking gate that
 *             must not trap the back button). Default true.
 *   blocked — true: back is swallowed while true (the entry is re-pushed and
 *             onClose is not called), e.g. while a delete request is in
 *             flight. Default false.
 */

import { useContext, useEffect, useRef, useState } from "react";
// The App Router instance without useRouter()'s throw when no router is
// mounted (unit tests render sheets bare). Same module Next's own client
// code reads, so it is the live router in the app.
import { AppRouterContext } from "next/dist/shared/lib/app-router-context.shared-runtime";

/** The bit of the App Router this module needs. */
export interface OverlayRouter {
  push(href: string): void;
  replace(href: string): void;
}

const STATE_KEY = "__pqOverlays";

type OverlayHistoryState = Record<string, unknown> & {
  [STATE_KEY]?: string[];
};

let seq = 0;
/** Overlays currently open (their entry should stay). */
const live = new Set<string>();
/** A flush of closed overlays' entries is scheduled. */
let flushTimer: ReturnType<typeof setTimeout> | null = null;
/** Timestamp of the last same-origin link click inside an open overlay. */
let navigatingAt = 0;

function readStack(): string[] {
  if (typeof window === "undefined") return [];
  const s = window.history.state as OverlayHistoryState | null;
  const stack = s?.[STATE_KEY];
  return Array.isArray(stack) ? stack : [];
}

function pushEntry(id: string) {
  const prev = (window.history.state as OverlayHistoryState | null) ?? {};
  const stack = readStack();
  // An overlay that just closed in the same tick (its go(-n) not run yet)
  // left its entry on top — e.g. an action sheet handing over to a form
  // sheet. Reuse that entry instead of stacking a new one on top of it, or
  // the user would need an extra back press later.
  const stale = countStaleTrailing(stack, live);
  if (stale > 0) {
    const next: OverlayHistoryState = {
      ...prev,
      [STATE_KEY]: [...stack.slice(0, stack.length - stale), id],
    };
    window.history.replaceState(next, "");
    return;
  }
  const next: OverlayHistoryState = { ...prev, [STATE_KEY]: [...stack, id] };
  window.history.pushState(next, "");
}

/** Trailing ids on the current entry that belong to overlays no longer open. */
export function countStaleTrailing(stack: string[], open: Set<string>): number {
  let n = 0;
  for (let i = stack.length - 1; i >= 0; i--) {
    if (open.has(stack[i])) break;
    n++;
  }
  return n;
}

function scheduleFlush() {
  if (flushTimer !== null) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    // A link inside the overlay started a navigation — going back now would
    // cancel it. Leave the (same-URL) entry behind.
    if (Date.now() - navigatingAt < 1500) return;
    const n = countStaleTrailing(readStack(), live);
    if (n > 0) window.history.go(-n);
  }, 0);
}

/**
 * The in-app URL (path + query + hash) a click navigates to, or null when
 * the click is not a same-origin, same-tab navigation.
 */
function navigatingClickHref(e: MouseEvent): string | null {
  if (e.defaultPrevented || e.button !== 0) return null;
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return null;
  const target = e.target as Element | null;
  const a = target?.closest?.("a[href]") as HTMLAnchorElement | null;
  if (!a) return null;
  if (a.target && a.target !== "_self") return null;
  if (a.hasAttribute("download")) return null;
  try {
    const url = new URL(a.href, window.location.href);
    if (url.origin !== window.location.origin) return null;
    // Pure in-page hash jumps are not navigations.
    if (
      url.pathname === window.location.pathname &&
      url.search === window.location.search &&
      url.hash
    ) {
      return null;
    }
    return url.pathname + url.search + url.hash;
  } catch {
    return null;
  }
}

/** The current history entry is an overlay's (a copy of the page under it). */
function onOverlayEntry(): boolean {
  return readStack().length > 0;
}

/**
 * Call right before a programmatic navigation (router.push) that is fired
 * from inside an open overlay, so closing it does not `history.go(-n)` and
 * cancel that navigation. Links (<a href>) are detected automatically.
 */
export function markOverlayNavigation(): void {
  navigatingAt = Date.now();
}

/**
 * Navigate from inside an open (or just-closed) overlay. When the current
 * history entry is the overlay's, it is replaced by the new route rather
 * than pushed on top of, so no same-URL entry is left behind for Back to
 * stall on. Otherwise a plain push.
 */
export function navigateFromOverlay(router: OverlayRouter, href: string): void {
  markOverlayNavigation();
  if (onOverlayEntry()) router.replace(href);
  else router.push(href);
}

export interface BackDismissOptions {
  /** false → never push an entry. Default true. */
  enabled?: boolean;
  /** true → back is swallowed (entry re-pushed, onClose not called). */
  blocked?: boolean;
}

export function useBackDismiss(
  open: boolean,
  onClose: () => void,
  options: BackDismissOptions = {},
): void {
  const { enabled = true, blocked = false } = options;
  const [id] = useState(() => `o${++seq}`);
  const router = useContext(AppRouterContext);
  const onCloseRef = useRef(onClose);
  const blockedRef = useRef(blocked);
  const routerRef = useRef<OverlayRouter | null>(router);
  useEffect(() => {
    onCloseRef.current = onClose;
    blockedRef.current = blocked;
    routerRef.current = router;
  });

  const active = open && enabled;

  useEffect(() => {
    if (!active || typeof window === "undefined") return;

    live.add(id);
    // StrictMode re-runs effects: the entry from the first run is still on
    // top, so do not push a second one.
    const stack = readStack();
    if (stack[stack.length - 1] !== id) pushEntry(id);

    const onPopState = () => {
      if (readStack().includes(id)) return; // a nested overlay's entry popped
      if (blockedRef.current) {
        pushEntry(id);
        return;
      }
      live.delete(id);
      onCloseRef.current();
    };
    const onClickCapture = (e: MouseEvent) => {
      const href = navigatingClickHref(e);
      if (href === null) return;
      navigatingAt = Date.now();
      // Only the overlay whose entry is on top takes the navigation over
      // (each open overlay has this listener). Capture phase on document
      // runs before next/link's onClick: the link's own onClick (e.g. one
      // that closes the sheet) still runs, and next/link skips its push
      // because the click is already handled.
      const r = routerRef.current;
      const top = readStack();
      if (!r || top[top.length - 1] !== id) return;
      e.preventDefault();
      r.replace(href);
    };

    window.addEventListener("popstate", onPopState);
    document.addEventListener("click", onClickCapture, true);
    return () => {
      window.removeEventListener("popstate", onPopState);
      document.removeEventListener("click", onClickCapture, true);
      live.delete(id);
      scheduleFlush();
    };
  }, [active, id]);
}

/** Test-only: reset module state between cases. */
export function __resetBackDismissForTests() {
  live.clear();
  if (flushTimer !== null) clearTimeout(flushTimer);
  flushTimer = null;
  navigatingAt = 0;
}
