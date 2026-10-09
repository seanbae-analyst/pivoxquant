"use client";

/**
 * <PullToRefresh> — pull down at the top of a phone screen to reload it
 * (2026-10-09, /mirror · /journal · /portfolio).
 *
 * Gesture (lib/pull-to-refresh holds the numbers):
 *   - starts only when the window is at its top AND no scroll container
 *     between the finger and this wrapper is scrolled (the phone pager pages
 *     scroll themselves) — so it never steals a normal scroll;
 *   - only a downward, mostly vertical move becomes a pull; a sideways one is
 *     left alone for the swipe pagers;
 *   - the indicator follows with rubber-band resistance, the arc fills
 *     towards the 70px threshold, and crossing it gives one haptic tick
 *     (lib/haptics: Android only, skipped under reduced motion);
 *   - releasing past the threshold calls `onRefresh` (the page's own SWR
 *     mutates); the spinner holds until it settles, the data on screen stays.
 *   - ignored while a bottom sheet is open (`data-pq-sheet-open` on <html>).
 *
 * The browser's own pull-to-refresh would fire on the same gesture, so while
 * this is mounted on a phone the root scroller's `overscroll-behavior-y` is
 * set to `contain` (only if the stylesheet left it at `auto` — the installed
 * app already sets `none`), and restored on unmount. Our touchmove also
 * cancels the native bounce while a pull is in progress.
 *
 * Reduced motion: the pull still works; the indicator jumps instead of
 * gliding back, and the arc does not spin.
 *
 * Desktop (md+): renders the children in a plain div, no listeners.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";
import { PQ_DUR_BASE, PQ_EASE } from "@/lib/motion";
import { useIsPhone } from "@/lib/use-phone";
import { hapticTick } from "@/lib/haptics";
import {
  PULL_MIN_SPIN_MS,
  PULL_REST_PX,
  PULL_THRESHOLD_PX,
  classifyPull,
  rubberBand,
  type PullIntent,
} from "@/lib/pull-to-refresh";

type Phase = "idle" | "pulling" | "refreshing";

const SHEET_OPEN_ATTR = "data-pq-sheet-open";
const INDICATOR_SIZE = 36;
const ARC_RADIUS = 8;
const ARC_LENGTH = 2 * Math.PI * ARC_RADIUS;
const SETTLE_TRANSITION = `transform ${PQ_DUR_BASE}s cubic-bezier(${PQ_EASE.join(", ")}), opacity ${PQ_DUR_BASE}s`;

/** Is any scroll container from `el` up to (not incl.) `stop` scrolled down? */
function scrolledAncestor(el: EventTarget | null, stop: HTMLElement): boolean {
  let node = el instanceof Element ? el : null;
  while (node && node !== stop) {
    if (node.scrollTop > 0 && node.scrollHeight > node.clientHeight) return true;
    node = node.parentElement;
  }
  return false;
}

type Gesture = { x: number; y: number; intent: PullIntent; dist: number; ticked: boolean };

export function PullToRefresh({
  onRefresh,
  children,
}: {
  /** The page's refresh — its SWR hooks' `mutate`s. */
  onRefresh: () => Promise<unknown>;
  children: React.ReactNode;
}) {
  const isPhone = useIsPhone();
  const reduce = useReducedMotion() ?? false;
  const wrapRef = useRef<HTMLDivElement>(null);
  const indicatorRef = useRef<HTMLDivElement>(null);
  const arcRef = useRef<SVGCircleElement>(null);
  const gesture = useRef<Gesture | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const phaseRef = useRef<Phase>("idle");
  const refreshRef = useRef(onRefresh);
  useEffect(() => {
    refreshRef.current = onRefresh;
  }, [onRefresh]);

  const paint = useCallback(
    (dist: number, settle: boolean) => {
      const ind = indicatorRef.current;
      const arc = arcRef.current;
      if (!ind) return;
      ind.style.transition = settle && !reduce ? SETTLE_TRANSITION : "none";
      ind.style.transform = `translate(-50%, ${dist - INDICATOR_SIZE}px)`;
      ind.style.opacity = dist <= 0 ? "0" : String(Math.min(1, dist / (PULL_THRESHOLD_PX * 0.6)));
      if (arc && phaseRef.current !== "refreshing") {
        const progress = Math.min(1, dist / PULL_THRESHOLD_PX);
        arc.style.strokeDasharray = `${ARC_LENGTH * progress * 0.85} ${ARC_LENGTH}`;
        arc.style.transform = `rotate(${-90 + progress * 270}deg)`;
      }
    },
    [reduce],
  );

  const setPhaseBoth = (p: Phase) => {
    phaseRef.current = p;
    setPhase(p);
  };

  const runRefresh = useCallback(async () => {
    setPhaseBoth("refreshing");
    const arc = arcRef.current;
    if (arc) {
      arc.style.strokeDasharray = `${ARC_LENGTH * 0.7} ${ARC_LENGTH}`;
      arc.style.transform = "";
    }
    paint(PULL_REST_PX, true);
    const minSpin = new Promise((r) => setTimeout(r, PULL_MIN_SPIN_MS));
    await Promise.allSettled([refreshRef.current(), minSpin]);
    setPhaseBoth("idle");
    paint(0, true);
  }, [paint]);

  // The browser's own pull-to-refresh is off only while ours is here.
  useEffect(() => {
    if (!isPhone) return;
    const root = document.documentElement;
    if (getComputedStyle(root).overscrollBehaviorY !== "auto") return;
    const previous = root.style.overscrollBehaviorY;
    root.style.overscrollBehaviorY = "contain";
    return () => {
      root.style.overscrollBehaviorY = previous;
    };
  }, [isPhone]);

  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap || !isPhone) return;

    const onStart = (e: TouchEvent) => {
      gesture.current = null;
      if (phaseRef.current === "refreshing" || e.touches.length !== 1) return;
      if (document.documentElement.hasAttribute(SHEET_OPEN_ATTR)) return;
      if (window.scrollY > 0 || scrolledAncestor(e.target, wrap)) return;
      const t = e.touches[0];
      gesture.current = { x: t.clientX, y: t.clientY, intent: "undecided", dist: 0, ticked: false };
    };

    const onMove = (e: TouchEvent) => {
      const g = gesture.current;
      if (!g || g.intent === "other") return;
      if (e.touches.length !== 1) {
        gesture.current = null;
        paint(0, true);
        setPhaseBoth("idle");
        return;
      }
      const t = e.touches[0];
      const dx = t.clientX - g.x;
      const dy = t.clientY - g.y;
      if (g.intent === "undecided") {
        g.intent = window.scrollY > 0 ? "other" : classifyPull(dx, dy);
        if (g.intent !== "pull") return;
        setPhaseBoth("pulling");
      }
      if (e.cancelable) e.preventDefault();
      g.dist = rubberBand(dy);
      if (!g.ticked && g.dist >= PULL_THRESHOLD_PX) {
        g.ticked = true;
        hapticTick();
      }
      paint(g.dist, false);
    };

    const onEnd = () => {
      const g = gesture.current;
      gesture.current = null;
      if (!g || g.intent !== "pull") return;
      if (g.dist >= PULL_THRESHOLD_PX) {
        void runRefresh();
      } else {
        setPhaseBoth("idle");
        paint(0, true);
      }
    };

    wrap.addEventListener("touchstart", onStart, { passive: true });
    wrap.addEventListener("touchmove", onMove, { passive: false });
    wrap.addEventListener("touchend", onEnd);
    wrap.addEventListener("touchcancel", onEnd);
    return () => {
      wrap.removeEventListener("touchstart", onStart);
      wrap.removeEventListener("touchmove", onMove);
      wrap.removeEventListener("touchend", onEnd);
      wrap.removeEventListener("touchcancel", onEnd);
    };
  }, [isPhone, paint, runRefresh]);

  return (
    <div
      ref={wrapRef}
      className={isPhone ? "overscroll-y-contain" : undefined}
      data-pq-pull-refresh={isPhone ? phase : undefined}
    >
      {isPhone && (
        <div
          ref={indicatorRef}
          aria-hidden
          className="pointer-events-none fixed left-1/2 z-[15] flex items-center justify-center rounded-full border border-[var(--pq-ivory-line)] bg-[var(--pq-ink)]"
          style={{
            top: "calc(var(--pq-topbar-height) + var(--pq-safe-top))",
            width: INDICATOR_SIZE,
            height: INDICATOR_SIZE,
            opacity: 0,
            transform: `translate(-50%, ${-INDICATOR_SIZE}px)`,
          }}
          data-testid="pull-indicator"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            className={
              phase === "refreshing" ? "animate-spin motion-reduce:animate-none" : undefined
            }
          >
            <circle cx="10" cy="10" r={ARC_RADIUS} fill="none" stroke="var(--pq-ivory-line)" strokeWidth="2" />
            <circle
              ref={arcRef}
              cx="10"
              cy="10"
              r={ARC_RADIUS}
              fill="none"
              stroke="var(--pq-bronze)"
              strokeWidth="2"
              strokeLinecap="round"
              style={{ transformOrigin: "10px 10px", strokeDasharray: `0 ${ARC_LENGTH}` }}
            />
          </svg>
        </div>
      )}
      {isPhone && (
        <span className="sr-only" role="status" aria-live="polite">
          {phase === "refreshing" ? "새로 고치는 중" : ""}
        </span>
      )}
      {children}
    </div>
  );
}
