"use client";

/**
 * Phone pager gestures (2026-10-09, CEO "멈춤부분도 들어가면 좀 화면 넘기는
 * 식으로 앱처럼"). Two hooks, no new dependency:
 *
 *   - useSwipePager — a horizontal touch swipe on a screen calls onNext /
 *     onPrev. The host decides whether the move is allowed; a refused move
 *     springs back. Vertical scrolling stays the browser's (touch-action:
 *     pan-y), a gesture that starts in a field is text editing, and a mouse
 *     never pages (pointerType "touch" / "pen" only).
 *   - useSlideIn — when the screen key changes, the screen enters from the
 *     side it was paged towards.
 *
 * Both are phone-only (useIsPhone, < md) and inert under
 * prefers-reduced-motion as far as movement goes: the swipe still pages, the
 * screen just does not travel. Durations and easing come from lib/motion.ts.
 */

import { useCallback, useEffect, useRef, type RefObject } from "react";
import { animate, useReducedMotion } from "motion/react";
import { PQ_DUR_BASE, PQ_EASE, PQ_PAGER_SLIDE_PX } from "@/lib/motion";
import { useIsPhone } from "@/lib/use-phone";

/** Horizontal travel (px) that counts as a swipe. */
export const SWIPE_MIN_PX = 56;
/** A swipe must be this many times wider than tall — otherwise it is a scroll. */
const SWIPE_AXIS_RATIO = 1.5;
/** How much of the finger's travel the screen follows while dragging. */
const DRAG_FOLLOW = 0.3;
/**
 * A click this soon after a swipe is the gesture's own (a UA may emit one
 * when the finger lifts over a button) — it must not also press the button.
 * Later clicks are the user's.
 */
const CLICK_AFTER_SWIPE_MS = 300;
/** Gestures that start in a field select text; they never page. */
const NO_SWIPE_SELECTOR = "input, textarea, select, [contenteditable='true']";

/** 1 = towards the next screen, -1 = back towards the previous one. */
export type PagerDir = 1 | -1;
/** What the host did with a swipe: paged, or refused (springs back). */
export type SwipeOutcome = "moved" | "blocked";

export interface SwipePagerOptions {
  /** Off → the handlers do nothing (desktop layout, modals). */
  enabled: boolean;
  /** Finger travelled right → left. */
  onNext: () => SwipeOutcome;
  /** Finger travelled left → right. */
  onPrev: () => SwipeOutcome;
}

type Start = { x: number; y: number; id: number };

const isTouchLike = (e: React.PointerEvent) =>
  e.pointerType === "touch" || e.pointerType === "pen";

const startsInField = (e: React.PointerEvent) =>
  e.target instanceof Element && e.target.closest(NO_SWIPE_SELECTOR) !== null;

/** Props to spread on the screen element (handlers + touch-action). */
export function useSwipePager<T extends HTMLElement>(
  ref: RefObject<T | null>,
  { enabled, onNext, onPrev }: SwipePagerOptions,
) {
  const isPhone = useIsPhone();
  const reduce = useReducedMotion();
  const active = enabled && isPhone;
  const start = useRef<Start | null>(null);
  // When the last recognised swipe ended (performance.now()), or null.
  const swipedAt = useRef<number | null>(null);

  const follow = useCallback(
    (dx: number) => {
      const el = ref.current;
      if (!el || reduce) return;
      el.style.transform = dx === 0 ? "" : `translateX(${dx * DRAG_FOLLOW}px)`;
    },
    [ref, reduce],
  );

  const springBack = useCallback(
    (dx: number) => {
      const el = ref.current;
      if (!el || reduce || dx === 0) return;
      void animate(
        el,
        { x: [dx * DRAG_FOLLOW, 0] },
        { duration: PQ_DUR_BASE, ease: PQ_EASE },
      );
    },
    [ref, reduce],
  );

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      // A new touch is a new gesture: nothing from the last one carries over.
      swipedAt.current = null;
      if (!active || !isTouchLike(e) || startsInField(e)) return;
      start.current = { x: e.clientX, y: e.clientY, id: e.pointerId };
    },
    [active],
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      const s = start.current;
      if (!s || s.id !== e.pointerId) return;
      const dx = e.clientX - s.x;
      const dy = e.clientY - s.y;
      if (Math.abs(dx) > Math.abs(dy)) follow(dx);
    },
    [follow],
  );

  const onPointerUp = useCallback(
    (e: React.PointerEvent) => {
      const s = start.current;
      start.current = null;
      if (!s || s.id !== e.pointerId) return;
      const dx = e.clientX - s.x;
      const dy = e.clientY - s.y;
      const isSwipe =
        Math.abs(dx) >= SWIPE_MIN_PX && Math.abs(dx) >= Math.abs(dy) * SWIPE_AXIS_RATIO;
      if (!isSwipe) {
        springBack(dx);
        return;
      }
      swipedAt.current = performance.now();
      const outcome = dx < 0 ? onNext() : onPrev();
      // "moved": the next screen's useSlideIn takes over the transform.
      if (outcome === "blocked") springBack(dx);
    },
    [onNext, onPrev, springBack],
  );

  const onPointerCancel = useCallback(() => {
    // The browser took the gesture (vertical scroll) — put the screen back.
    start.current = null;
    follow(0);
  }, [follow]);

  const onClickCapture = useCallback((e: React.MouseEvent) => {
    const at = swipedAt.current;
    swipedAt.current = null;
    if (at === null || performance.now() - at > CLICK_AFTER_SWIPE_MS) return;
    e.preventDefault();
    e.stopPropagation();
  }, []);

  return {
    onPointerDown,
    onPointerMove,
    onPointerUp,
    onPointerCancel,
    onClickCapture,
    style: active ? ({ touchAction: "pan-y" } as const) : undefined,
  };
}

/**
 * Slide the screen in from `dir` whenever `screenKey` changes. With
 * `animateOnMount` the first render counts as a change (a screen that is
 * itself the destination of a page, e.g. setup → question 1).
 */
export function useSlideIn<T extends HTMLElement>(
  ref: RefObject<T | null>,
  screenKey: string | number,
  dir: PagerDir,
  { enabled, animateOnMount }: { enabled: boolean; animateOnMount: boolean },
) {
  const isPhone = useIsPhone();
  const reduce = useReducedMotion();
  const shown = useRef<string | number | null>(animateOnMount ? null : screenKey);

  useEffect(() => {
    const el = ref.current;
    if (!el || shown.current === screenKey) return;
    shown.current = screenKey;
    // A fresh screen starts at its top, like an app screen — only when the
    // previous one had been scrolled past.
    if (enabled && isPhone && el.getBoundingClientRect().top < 0) {
      window.scrollTo({ top: 0, behavior: "instant" });
    }
    if (!enabled || !isPhone || reduce) {
      el.style.transform = "";
      return;
    }
    const controls = animate(
      el,
      { x: [dir * PQ_PAGER_SLIDE_PX, 0], opacity: [0, 1] },
      { duration: PQ_DUR_BASE, ease: PQ_EASE },
    );
    return () => {
      controls.stop();
      // Re-run (StrictMode double effect, a dep change) replays the entrance
      // instead of leaving the screen frozen mid-slide.
      shown.current = null;
    };
  }, [ref, screenKey, dir, enabled, isPhone, reduce]);
}
