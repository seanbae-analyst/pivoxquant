"use client";

/**
 * FlipLandingShell — scroll-hijacking 3D page-flip wrapper.
 *
 * Responsibilities:
 *   1. Detect environment → enable hijack only when desktop (>=1024px) AND
 *      user has NOT requested reduced motion. Otherwise render children as a
 *      normal long-scroll page (fallback).
 *   2. Maintain `pageIndex` + `direction` state.
 *   3. Listen to wheel / keydown / touch input and advance/rewind with a lock
 *      window so flips don't stack mid-animation.
 *   4. Render a right-side ProgressDots nav + a one-time "Scroll or press Space"
 *      hint.
 *   5. Provide context so individual <FlipPage> children can render correctly.
 *
 * Notes on "taller than viewport" pages: inside a page, native scroll still
 * works — we only hijack wheel when the inner scroll is already at its
 * extreme in the requested direction. This matches the Apple Keynote behavior
 * and avoids trapping users inside long pages (Archetype / Pricing / FAQ).
 */

import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useReducedMotion, AnimatePresence, motion } from "motion/react";

interface FlipContextValue {
  enabled: boolean;
  activeIndex: number;
  direction: 1 | -1;
  total: number;
}

const FlipCtx = createContext<FlipContextValue>({
  enabled: false,
  activeIndex: 0,
  direction: 1,
  total: 0,
});

export function useFlipContext() {
  return useContext(FlipCtx);
}

export interface FlipLandingShellProps {
  /** Number of <FlipPage> children the shell will host. */
  total: number;
  /** Optional labels for ProgressDots tooltips + screen readers. */
  labels?: string[];
  /**
   * Optional per-page kind. "splash" renders a diamond (◆) dot to mark the
   * cover page; "page" renders the default circle. Omitting falls back to
   * all circles. Added 2026-04-23 for the Splash Page 0.
   */
  kinds?: Array<"splash" | "page">;
  /**
   * When true, the shell ignores wheel/key/touch events (e.g. while a modal
   * drawer is open). ProgressDots remain clickable.
   */
  paused?: boolean;
  children: ReactNode;
}

// Enable hijack only above this width — below, use native scroll.
const DESKTOP_MIN_WIDTH = 1024;
// Wheel deltaY threshold to register an intent (prevents trackpad jitter).
const WHEEL_THRESHOLD = 24;
// Touch swipe distance threshold.
const TOUCH_THRESHOLD = 70;
// Duration a flip "locks" the input queue.
const FLIP_LOCK_MS = 1100;

export function FlipLandingShell({ total, labels, kinds, paused, children }: FlipLandingShellProps) {
  const prefersReduced = useReducedMotion();
  const [mounted, setMounted] = useState(false);
  const [isDesktop, setIsDesktop] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [direction, setDirection] = useState<1 | -1>(1);
  const [showHint, setShowHint] = useState(false);
  const lockedRef = useRef(false);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const touchStartY = useRef<number | null>(null);

  // Mount + viewport width detection.
  useEffect(() => {
    setMounted(true);
    const check = () => setIsDesktop(window.innerWidth >= DESKTOP_MIN_WIDTH);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  const enabled = mounted && isDesktop && !prefersReduced;

  // Toggle body overflow when hijack is engaged.
  useEffect(() => {
    if (!enabled) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [enabled]);

  // One-shot hint on mount.
  useEffect(() => {
    if (!enabled) return;
    setShowHint(true);
    const t = window.setTimeout(() => setShowHint(false), 3400);
    return () => window.clearTimeout(t);
  }, [enabled]);

  const goTo = useCallback(
    (next: number, dir: 1 | -1) => {
      if (lockedRef.current) return;
      const clamped = Math.max(0, Math.min(total - 1, next));
      if (clamped === activeIndex) return;
      lockedRef.current = true;
      setDirection(dir);
      setActiveIndex(clamped);
      setShowHint(false);
      window.setTimeout(() => {
        lockedRef.current = false;
      }, FLIP_LOCK_MS);
    },
    [activeIndex, total],
  );

  // Check whether the currently-active page's inner content is at its scroll
  // extreme in the given direction. If not, we DO NOT hijack — we let the page
  // scroll naturally.
  const activePageAtEdge = useCallback(
    (dir: 1 | -1): boolean => {
      if (!stageRef.current) return true;
      const activeEl = stageRef.current.querySelector<HTMLElement>(
        `[data-flip-index="${activeIndex}"]`,
      );
      if (!activeEl) return true;
      const inner = activeEl.querySelector<HTMLElement>(".pq-flip-page__inner");
      if (!inner) return true;
      const { scrollTop, scrollHeight, clientHeight } = inner;
      if (dir === 1) {
        return scrollTop + clientHeight >= scrollHeight - 4;
      }
      return scrollTop <= 4;
    },
    [activeIndex],
  );

  // Wheel listener.
  useEffect(() => {
    if (!enabled) return;
    const onWheel = (e: WheelEvent) => {
      if (paused) return;
      if (Math.abs(e.deltaY) < WHEEL_THRESHOLD) return;
      const dir: 1 | -1 = e.deltaY > 0 ? 1 : -1;
      if (!activePageAtEdge(dir)) return; // let inner scroll
      e.preventDefault();
      goTo(activeIndex + dir, dir);
    };
    const node = stageRef.current;
    if (!node) return;
    node.addEventListener("wheel", onWheel, { passive: false });
    return () => node.removeEventListener("wheel", onWheel);
  }, [enabled, activeIndex, activePageAtEdge, goTo, paused]);

  // Keyboard listener.
  useEffect(() => {
    if (!enabled) return;
    const onKey = (e: KeyboardEvent) => {
      if (paused) return;
      // Ignore if focus is inside form fields.
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (
        e.key === "ArrowDown" ||
        e.key === "PageDown" ||
        e.key === " " ||
        e.key === "Spacebar"
      ) {
        if (!activePageAtEdge(1)) return;
        e.preventDefault();
        goTo(activeIndex + 1, 1);
      } else if (e.key === "ArrowUp" || e.key === "PageUp") {
        if (!activePageAtEdge(-1)) return;
        e.preventDefault();
        goTo(activeIndex - 1, -1);
      } else if (e.key === "Home") {
        e.preventDefault();
        goTo(0, -1);
      } else if (e.key === "End") {
        e.preventDefault();
        goTo(total - 1, 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [enabled, activeIndex, activePageAtEdge, goTo, total, paused]);

  // Touch swipe (desktop trackpad rarely triggers, but keep for touch-laptops).
  useEffect(() => {
    if (!enabled) return;
    const node = stageRef.current;
    if (!node) return;
    const onTouchStart = (e: TouchEvent) => {
      touchStartY.current = e.touches[0]?.clientY ?? null;
    };
    const onTouchEnd = (e: TouchEvent) => {
      if (paused) return;
      if (touchStartY.current == null) return;
      const endY = e.changedTouches[0]?.clientY ?? touchStartY.current;
      const delta = touchStartY.current - endY;
      touchStartY.current = null;
      if (Math.abs(delta) < TOUCH_THRESHOLD) return;
      const dir: 1 | -1 = delta > 0 ? 1 : -1;
      if (!activePageAtEdge(dir)) return;
      goTo(activeIndex + dir, dir);
    };
    node.addEventListener("touchstart", onTouchStart, { passive: true });
    node.addEventListener("touchend", onTouchEnd, { passive: true });
    return () => {
      node.removeEventListener("touchstart", onTouchStart);
      node.removeEventListener("touchend", onTouchEnd);
    };
  }, [enabled, activeIndex, activePageAtEdge, goTo, paused]);

  // Reset inner scroll when a new page becomes active — otherwise users see
  // the previous page's scroll position on re-entry.
  useEffect(() => {
    if (!enabled || !stageRef.current) return;
    const activeEl = stageRef.current.querySelector<HTMLElement>(
      `[data-flip-index="${activeIndex}"] .pq-flip-page__inner`,
    );
    if (activeEl) activeEl.scrollTop = 0;
  }, [activeIndex, enabled]);

  const ctxValue = useMemo<FlipContextValue>(
    () => ({ enabled, activeIndex, direction, total }),
    [enabled, activeIndex, direction, total],
  );

  return (
    <FlipCtx.Provider value={ctxValue}>
      <div
        ref={stageRef}
        className={
          enabled ? "pq-flip-stage pq-flip-stage--active" : "pq-flip-stage"
        }
        data-flip-enabled={enabled ? "true" : "false"}
      >
        {children}

        {enabled && total > 1 && (
          <ProgressDots
            total={total}
            active={activeIndex}
            labels={labels}
            kinds={kinds}
            onJump={(next) =>
              goTo(next, next > activeIndex ? 1 : -1)
            }
          />
        )}

        <AnimatePresence>
          {enabled && showHint && (
            <motion.div
              key="pq-flip-hint"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
              className="pq-flip-hint"
              aria-hidden
            >
              Scroll or press Space to turn the page
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </FlipCtx.Provider>
  );
}

/* ──────────────────────────────────────────────
   ProgressDots — right-side vertical nav
   ────────────────────────────────────────────── */

function ProgressDots({
  total,
  active,
  labels,
  kinds,
  onJump,
}: {
  total: number;
  active: number;
  labels?: string[];
  kinds?: Array<"splash" | "page">;
  onJump: (index: number) => void;
}) {
  return (
    <nav className="pq-flip-dots" aria-label="Landing page sections">
      <ol className="pq-flip-dots__list">
        {Array.from({ length: total }).map((_, i) => {
          const isActive = i === active;
          const label = labels?.[i] ?? `Section ${i + 1}`;
          const kind = kinds?.[i] ?? "page";
          const btnClass = [
            "pq-flip-dots__btn",
            isActive ? "pq-flip-dots__btn--active" : "",
            kind === "splash" ? "pq-flip-dots__btn--splash" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <li key={i}>
              <button
                type="button"
                className={btnClass}
                onClick={() => onJump(i)}
                aria-current={isActive ? "true" : undefined}
                aria-label={`Go to ${label}`}
                title={label}
              >
                <span aria-hidden className="pq-flip-dots__mark" />
              </button>
            </li>
          );
        })}
      </ol>
      <span className="pq-flip-dots__count" aria-hidden>
        <span className="pq-flip-dots__count-num">
          {String(active + 1).padStart(2, "0")}
        </span>
        <span className="pq-flip-dots__count-sep">/</span>
        <span className="pq-flip-dots__count-total">
          {String(total).padStart(2, "0")}
        </span>
      </span>
    </nav>
  );
}
