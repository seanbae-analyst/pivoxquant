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
 *     the navigation Next.js is about to commit). The left-behind entry is
 *     the same URL as the page under it, so it is harmless.
 *   - The URL never changes — the entry copies `history.state`, which keeps
 *     Next.js's `__NA` tree marker, so its popstate handler restores the same
 *     route instead of reloading.
 *
 * Stable API (the 더보기 drawer in components/layout/bottom-nav.tsx and
 * components/ui/sheet.tsx both use it):
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

import { useEffect, useRef, useState } from "react";

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

function isNavigatingClick(e: MouseEvent): boolean {
  if (e.defaultPrevented || e.button !== 0) return false;
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return false;
  const target = e.target as Element | null;
  const a = target?.closest?.("a[href]") as HTMLAnchorElement | null;
  if (!a) return false;
  if (a.target && a.target !== "_self") return false;
  if (a.hasAttribute("download")) return false;
  try {
    const url = new URL(a.href, window.location.href);
    if (url.origin !== window.location.origin) return false;
    // Pure in-page hash jumps are not navigations.
    if (
      url.pathname === window.location.pathname &&
      url.search === window.location.search &&
      url.hash
    ) {
      return false;
    }
  } catch {
    return false;
  }
  return true;
}

/**
 * Call right before a programmatic navigation (router.push) that is fired
 * from inside an open overlay, so closing it does not `history.go(-n)` and
 * cancel that navigation. Links (<a href>) are detected automatically.
 */
export function markOverlayNavigation(): void {
  navigatingAt = Date.now();
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
  const onCloseRef = useRef(onClose);
  const blockedRef = useRef(blocked);
  useEffect(() => {
    onCloseRef.current = onClose;
    blockedRef.current = blocked;
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
      if (isNavigatingClick(e)) navigatingAt = Date.now();
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
