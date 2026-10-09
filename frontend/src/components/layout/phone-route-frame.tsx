"use client";

/**
 * <PhoneRouteFrame> — how a dashboard screen arrives on a phone
 * (2026-10-09, CEO "최대한 앱처럼 고퀄리티").
 *
 * Wraps the page slot of (dashboard)/layout.tsx. Below md (the installed PWA
 * included) it does three things on every route change; at md and up it
 * renders its children in a plain div and does nothing else.
 *
 * 1. Motion (lib/route-motion decides which):
 *      tab  — bottom-nav destination to destination: the screen fades in.
 *      push — deeper (/journal → /journal/import): arrives from the right.
 *      pop  — back out: arrives from the left.
 *    Only `opacity` and a relative `left` offset move — never `transform`.
 *    A transform would make this wrapper the containing block of every
 *    `position: fixed` element inside the page (the journal page dots, a
 *    sheet), and they would jump for the length of the animation. While a
 *    screen slides, <main> clips horizontal overflow (`overflow-x: clip`
 *    keeps sticky headers working, unlike `hidden`). When the browser has
 *    already animated the move itself (the iOS edge swipe sets
 *    PopStateEvent.hasUAVisualTransition) nothing is played on top of it.
 *    prefers-reduced-motion: every move becomes a short fade, no travel.
 *
 * 2. Scroll memory (lib/scroll-memory): each route keeps its window scroll
 *    and the scroll of the scroll containers inside it (phone pager pages and
 *    tracks). Returning to a bottom-nav destination, or going back to any
 *    screen, restores it — instantly (html has scroll-behavior: smooth, so
 *    it is lifted for the jump), before paint when the content is already
 *    there, and otherwise as soon as it is tall enough (≤ 3 s, abandoned the
 *    moment the user touches the screen). A drill-down starts at its top.
 *
 * 3. Offline: an inline banner above the screen while the device is offline
 *    (components/pwa/offline-banner), so the app stays the app.
 *
 * The loading skeleton ((dashboard)/loading.tsx) calls `revealRouteContent`
 * as it leaves, so the real screen fades in over it instead of popping.
 */

import { useEffect, useLayoutEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { useReducedMotion } from "motion/react";
import { PQ_DUR_BASE, PQ_DUR_FAST, PQ_EASE, PQ_ROUTE_SLIDE_PX } from "@/lib/motion";
import { useIsPhone } from "@/lib/use-phone";
import { classifyRouteChange, shouldRestoreScroll, type RouteMotion } from "@/lib/route-motion";
import {
  nodePath,
  persistScrollMemory,
  readRouteScroll,
  rememberInnerScroll,
  rememberWindowScroll,
  resolveNodePath,
  type RouteScroll,
} from "@/lib/scroll-memory";
import { OfflineBanner } from "@/components/pwa/offline-banner";

/** A pop is matched to the route change that follows it within this window. */
const POP_MATCH_MS = 3_000;
/** How long a restore waits for the destination to grow tall enough. */
const RESTORE_WAIT_MS = 3_000;
const EASE_CSS = `cubic-bezier(${PQ_EASE.join(", ")})`;
const SHEET_OPEN_ATTR = "data-pq-sheet-open";
/** Where content fades in from when it replaces the loading skeleton. */
const REVEAL_FROM_OPACITY = 0.4;

type LastPop = { path: string; at: number; ua: boolean };

/* ── Module state: one frame is mounted at a time ─────────────────────────── */

let lastPop: LastPop | null = null;
let frameEl: HTMLElement | null = null;
let framePhone = false;

function onPopStateCapture(e: PopStateEvent) {
  const ua = (e as PopStateEvent & { hasUAVisualTransition?: boolean }).hasUAVisualTransition;
  lastPop = { path: window.location.pathname, at: performance.now(), ua: ua === true };
}

function takePop(path: string): LastPop | null {
  const pop = lastPop;
  lastPop = null;
  if (!pop || pop.path !== path || performance.now() - pop.at > POP_MATCH_MS) return null;
  return pop;
}

function sheetOpen(): boolean {
  return document.documentElement.hasAttribute(SHEET_OPEN_ATTR);
}

/** Scroll the window without the html-level smooth glide. */
function jumpWindowTo(y: number) {
  const root = document.documentElement;
  const previous = root.style.scrollBehavior;
  root.style.scrollBehavior = "auto";
  window.scrollTo(0, y);
  root.style.scrollBehavior = previous;
}

function jumpElementTo(el: Element, top: number, left: number) {
  const h = el as HTMLElement;
  const previous = h.style.scrollBehavior;
  h.style.scrollBehavior = "auto";
  h.scrollTop = top;
  h.scrollLeft = left;
  h.style.scrollBehavior = previous;
}

/* ── Motion ───────────────────────────────────────────────────────────────── */

function playMotion(el: HTMLElement, kind: RouteMotion, reduce: boolean): Animation | null {
  if (kind === "none" || typeof el.animate !== "function") return null;
  const slide = !reduce && (kind === "push" || kind === "pop");
  const from = kind === "pop" ? -PQ_ROUTE_SLIDE_PX : PQ_ROUTE_SLIDE_PX;
  const main = el.closest("main");
  if (slide) {
    el.style.position = "relative";
    if (main) main.style.overflowX = "clip";
  }
  const animation = el.animate(
    slide
      ? [
          { opacity: 0, left: `${from}px` },
          { opacity: 1, left: "0px" },
        ]
      : [{ opacity: 0 }, { opacity: 1 }],
    {
      duration: (reduce ? PQ_DUR_FAST : PQ_DUR_BASE) * 1000,
      easing: EASE_CSS,
    },
  );
  const cleanup = () => {
    if (!slide) return;
    el.style.position = "";
    if (main) main.style.overflowX = "";
  };
  animation.addEventListener("finish", cleanup);
  animation.addEventListener("cancel", cleanup);
  return animation;
}

/**
 * The loading skeleton is leaving and the real screen is taking its place:
 * fade the screen in instead of swapping it. Phone only; no-op elsewhere.
 */
export function revealRouteContent(): void {
  const el = frameEl;
  if (!el || !framePhone || typeof el.animate !== "function") return;
  // From part-way, not from 0: the skeleton is already gone, so a full fade
  // would blink to ink between the placeholders and the content.
  el.animate([{ opacity: REVEAL_FROM_OPACITY }, { opacity: 1 }], {
    duration: PQ_DUR_FAST * 1000,
    easing: EASE_CSS,
  });
}

/* ── Scroll restore ───────────────────────────────────────────────────────── */

/**
 * What a restore in flight has not put back yet. Scroll events on those
 * targets are the restore's own (or the browser clamping a short page), not
 * the user's, so they are not recorded; everything else records as usual.
 */
type PendingRestore = { window: boolean; inner: Set<string> };

/**
 * Put the window and the remembered scroll containers back where they were.
 * `pending` is updated as each lands. Returns a cancel function; `onDone`
 * runs once everything landed, the wait ran out, or it was cancelled.
 */
function restoreScroll(
  root: HTMLElement,
  saved: RouteScroll,
  pending: PendingRestore,
  onDone: () => void,
): () => void {
  let cancelled = false;
  let frame = 0;
  const start = performance.now();
  const inner = new Map(Object.entries(saved.inner));
  pending.window = true;
  pending.inner = new Set(inner.keys());

  const finish = () => {
    if (cancelled) return;
    cancelled = true;
    pending.window = false;
    pending.inner.clear();
    cancelAnimationFrame(frame);
    window.removeEventListener("touchstart", finish, true);
    window.removeEventListener("wheel", finish, true);
    window.removeEventListener("keydown", finish, true);
    onDone();
  };

  const attempt = () => {
    if (cancelled) return;
    if (pending.window) {
      const maxY = document.documentElement.scrollHeight - window.innerHeight;
      if (saved.y <= 0 || maxY >= saved.y - 1) {
        jumpWindowTo(saved.y);
        pending.window = false;
      }
    }
    for (const [key, pos] of inner) {
      const el = resolveNodePath(root, key);
      if (!el) continue;
      const fitsTop = el.scrollHeight - el.clientHeight >= pos.top - 1;
      const fitsLeft = el.scrollWidth - el.clientWidth >= pos.left - 1;
      if (fitsTop && fitsLeft) {
        jumpElementTo(el, pos.top, pos.left);
        inner.delete(key);
        pending.inner.delete(key);
      }
    }
    if ((!pending.window && inner.size === 0) || performance.now() - start > RESTORE_WAIT_MS) {
      finish();
      return;
    }
    frame = requestAnimationFrame(attempt);
  };

  // The user taking over ends the restore.
  window.addEventListener("touchstart", finish, true);
  window.addEventListener("wheel", finish, true);
  window.addEventListener("keydown", finish, true);
  attempt();
  return finish;
}

/* ── Component ────────────────────────────────────────────────────────────── */

export function PhoneRouteFrame({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "";
  const isPhone = useIsPhone();
  const reduce = useReducedMotion() ?? false;
  const ref = useRef<HTMLDivElement>(null);
  /** The route whose scroll the listeners are recording. */
  const currentPath = useRef<string | null>(null);
  /** What a restore in flight has not put back yet (see PendingRestore). */
  const pendingRestore = useRef<PendingRestore>({ window: false, inner: new Set() });
  const cancelRestore = useRef<(() => void) | null>(null);
  const animation = useRef<Animation | null>(null);

  // History moves, recorded before Next.js handles them (capture phase).
  useEffect(() => {
    window.addEventListener("popstate", onPopStateCapture, true);
    return () => window.removeEventListener("popstate", onPopStateCapture, true);
  }, []);

  useEffect(() => {
    const el = ref.current;
    frameEl = el;
    framePhone = isPhone;
    return () => {
      if (frameEl === el) frameEl = null;
    };
  }, [isPhone]);

  // Record scroll positions per route (phone only).
  useEffect(() => {
    if (!isPhone) return;
    const onWindowScroll = () => {
      const path = currentPath.current;
      if (!path || pendingRestore.current.window || sheetOpen()) return;
      rememberWindowScroll(path, window.scrollY);
    };
    const onAnyScroll = (e: Event) => {
      const path = currentPath.current;
      const root = ref.current;
      const target = e.target;
      if (!path || !root || sheetOpen()) return;
      if (!(target instanceof Element) || target === root || !root.contains(target)) return;
      const key = nodePath(root, target);
      if (key === null || pendingRestore.current.inner.has(key)) return;
      rememberInnerScroll(path, key, target.scrollTop, target.scrollLeft);
    };
    const onHide = () => persistScrollMemory();
    window.addEventListener("scroll", onWindowScroll, { passive: true });
    document.addEventListener("scroll", onAnyScroll, { passive: true, capture: true });
    window.addEventListener("pagehide", onHide);
    document.addEventListener("visibilitychange", onHide);
    return () => {
      window.removeEventListener("scroll", onWindowScroll);
      document.removeEventListener("scroll", onAnyScroll, { capture: true });
      window.removeEventListener("pagehide", onHide);
      document.removeEventListener("visibilitychange", onHide);
    };
  }, [isPhone]);

  // A route change: runs after Next.js's own scroll handling (that lives in
  // a child layout effect) and before the browser paints the new screen.
  useLayoutEffect(() => {
    const el = ref.current;
    const prev = currentPath.current;
    currentPath.current = pathname;
    if (!el || !isPhone) return;
    const pop = takePop(pathname);
    const kind = classifyRouteChange(prev, pathname, pop !== null);
    if (kind === "none") return;
    persistScrollMemory();

    cancelRestore.current?.();
    const saved = shouldRestoreScroll(pathname, pop !== null) ? readRouteScroll(pathname) : null;
    if (saved) {
      cancelRestore.current = restoreScroll(el, saved, pendingRestore.current, () => {
        cancelRestore.current = null;
      });
    } else if (window.scrollY > 0) {
      // A fresh screen (or a remembered one never scrolled) starts at its top.
      jumpWindowTo(0);
    }

    animation.current?.cancel();
    animation.current = pop?.ua ? null : playMotion(el, kind, reduce);
  }, [pathname, isPhone, reduce]);

  useEffect(
    () => () => {
      cancelRestore.current?.();
      animation.current?.cancel();
    },
    [],
  );

  return (
    <>
      <OfflineBanner />
      <div ref={ref} data-pq-route-frame>
        {children}
      </div>
    </>
  );
}
