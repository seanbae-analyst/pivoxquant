"use client";

/**
 * <PhonePager /> — swipeable full-width pages for the phone /portfolio.
 *
 * CEO 2026-10-09: "포트폴리오 부분도 화면 넘어가는식으로 … 앱은". On a phone the
 * long single column (hero → curve → holdings → seed capital → sectors →
 * activity) becomes a row of pages you swipe between, with a tab strip that
 * follows the swipe and can be tapped.
 *
 * Mechanics — same choice as pwa/app-welcome.tsx:
 *   - plain CSS scroll-snap on the track, no gesture library. The browser
 *     owns the swipe physics, so it feels native on iOS and Android and
 *     honours the platform's own reduced-motion handling of momentum.
 *   - each page is its own vertical scroll container, so every page keeps
 *     its scroll position while you visit the others.
 *   - the tab underline is driven straight from `scrollLeft` (no React state
 *     per frame); `index` state changes only when the nearest page changes.
 *   - pages that are not the current one are `inert`, so Tab never walks
 *     focus into an off-screen page and yanks the track sideways.
 *
 * Reduced motion: a tapped tab jumps instead of gliding, and the indicator
 * dots stop animating their width.
 */

import * as React from "react";
import { useReducedMotion } from "motion/react";
import { PQ_DUR_FAST, PQ_EASE } from "@/lib/motion";

export interface PhonePage {
  /** Stable id — used for the tab / panel ids and test hooks. */
  id: string;
  /** Short tab label (2–5 Korean characters fits four tabs at 360px). */
  label: string;
  content: React.ReactNode;
}

interface PhonePagerProps {
  pages: ReadonlyArray<PhonePage>;
  /** Accessible name of the tab strip. */
  label: string;
  /** Rendered above the tab strip and kept in view (compact summary). */
  header?: React.ReactNode;
  /** Page shown first. Defaults to 0. */
  initialIndex?: number;
}

/** A tap-initiated glide gives up waiting for its target after this long. */
const TAP_LOCK_MS = 900;
const EASE_CSS = `cubic-bezier(${PQ_EASE.join(", ")})`;

function clampIndex(i: number, n: number): number {
  return Math.max(0, Math.min(n - 1, i));
}

export function PhonePager({ pages, label, header, initialIndex = 0 }: PhonePagerProps) {
  const n = pages.length;
  const reduce = useReducedMotion();
  const baseId = React.useId();
  const trackRef = React.useRef<HTMLDivElement>(null);
  const underlineRef = React.useRef<HTMLSpanElement>(null);
  const tabRefs = React.useRef<Array<HTMLButtonElement | null>>([]);
  const pageRefs = React.useRef<Array<HTMLElement | null>>([]);
  const [index, setIndex] = React.useState(() => clampIndex(initialIndex, n));
  /** Mirror of `index` for scroll / resize handlers. Written next to every
   *  setIndex (handlers only), never during render. */
  const indexRef = React.useRef(index);
  /** Target of a tab tap — scroll events on the way there don't move `index`. */
  const pendingRef = React.useRef<number | null>(null);
  const pendingTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const frame = React.useRef<number | null>(null);

  const paintUnderline = React.useCallback((progress: number) => {
    const el = underlineRef.current;
    if (el) el.style.transform = `translateX(${progress * 100}%)`;
  }, []);

  const clearPending = React.useCallback(() => {
    pendingRef.current = null;
    if (pendingTimer.current) clearTimeout(pendingTimer.current);
    pendingTimer.current = null;
  }, []);

  const readScroll = React.useCallback(() => {
    frame.current = null;
    const el = trackRef.current;
    if (!el || el.clientWidth === 0) return;
    const progress = Math.max(0, Math.min(n - 1, el.scrollLeft / el.clientWidth));
    paintUnderline(progress);
    const nearest = Math.round(progress);
    const pending = pendingRef.current;
    if (pending !== null) {
      if (Math.abs(progress - pending) > 0.02) return;
      clearPending();
    }
    if (nearest !== indexRef.current) {
      indexRef.current = nearest;
      setIndex(nearest);
    }
  }, [n, paintUnderline, clearPending]);

  const onScroll = () => {
    if (frame.current === null) frame.current = requestAnimationFrame(readScroll);
  };

  const goTo = React.useCallback(
    (i: number) => {
      const el = trackRef.current;
      const target = clampIndex(i, n);
      if (target === indexRef.current) {
        // Tapping the current tab again: back to the top of that page.
        const page = pageRefs.current[target];
        if (page && typeof page.scrollTo === "function") {
          page.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
        } else if (page) page.scrollTop = 0;
        return;
      }
      clearPending();
      pendingRef.current = target;
      pendingTimer.current = setTimeout(clearPending, TAP_LOCK_MS);
      indexRef.current = target;
      setIndex(target);
      if (!el) return;
      const left = target * el.clientWidth;
      if (typeof el.scrollTo === "function") {
        el.scrollTo({ left, behavior: reduce ? "auto" : "smooth" });
      } else {
        el.scrollLeft = left;
      }
      if (reduce) paintUnderline(target);
    },
    [n, reduce, clearPending, paintUnderline],
  );

  // First paint: open on `initialIndex` without a visible glide.
  React.useLayoutEffect(() => {
    const el = trackRef.current;
    if (el && el.clientWidth > 0) el.scrollLeft = indexRef.current * el.clientWidth;
    paintUnderline(indexRef.current);
  }, [paintUnderline]);

  // Rotation / resize: keep the current page in place rather than
  // trusting every engine to re-snap a mandatory track.
  React.useEffect(() => {
    const el = trackRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => {
      el.scrollLeft = indexRef.current * el.clientWidth;
      paintUnderline(indexRef.current);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [paintUnderline]);

  React.useEffect(
    () => () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      if (pendingTimer.current) clearTimeout(pendingTimer.current);
    },
    [],
  );

  function onTabKeyDown(e: React.KeyboardEvent) {
    const keys: Record<string, number> = {
      ArrowRight: index + 1,
      ArrowLeft: index - 1,
      Home: 0,
      End: n - 1,
    };
    if (!(e.key in keys)) return;
    e.preventDefault();
    const next = clampIndex(keys[e.key], n);
    goTo(next);
    tabRefs.current[next]?.focus();
  }

  const tabId = (i: number) => `${baseId}-tab-${pages[i].id}`;
  const panelId = (i: number) => `${baseId}-panel-${pages[i].id}`;
  const dotTransition = reduce
    ? "none"
    : `width ${PQ_DUR_FAST}s ${EASE_CSS}, background-color ${PQ_DUR_FAST}s ${EASE_CSS}`;
  const tabTransition = reduce ? "none" : `color ${PQ_DUR_FAST}s ${EASE_CSS}`;

  return (
    <div className="pq-phone-pager" data-testid="phone-pager">
      {header}

      <div
        role="tablist"
        aria-label={label}
        onKeyDown={onTabKeyDown}
        className="pq-phone-pager-tabs"
        style={{ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }}
        data-testid="phone-pager-tabs"
      >
        {pages.map((p, i) => (
          <button
            key={p.id}
            ref={(el) => {
              tabRefs.current[i] = el;
            }}
            type="button"
            role="tab"
            id={tabId(i)}
            aria-selected={i === index}
            aria-controls={panelId(i)}
            tabIndex={i === index ? 0 : -1}
            onClick={() => goTo(i)}
            className="pq-phone-pager-tab"
            style={{ transition: tabTransition }}
            data-active={i === index ? "true" : undefined}
          >
            {p.label}
          </button>
        ))}
        <span
          ref={underlineRef}
          aria-hidden
          className="pq-phone-pager-underline"
          // `transform` is painted from the scroll position (paintUnderline),
          // never from a render — a render at the 50% mark of a swipe would
          // snap it to the next tab while the finger is still mid-way.
          style={{ width: `${100 / n}%` }}
        />
      </div>

      <div
        ref={trackRef}
        onScroll={onScroll}
        onPointerDown={clearPending}
        onTouchStart={clearPending}
        className="pq-phone-pager-track"
        data-testid="phone-pager-track"
      >
        {pages.map((p, i) => (
          <section
            key={p.id}
            ref={(el) => {
              pageRefs.current[i] = el;
            }}
            role="tabpanel"
            id={panelId(i)}
            aria-labelledby={tabId(i)}
            tabIndex={i === index ? 0 : -1}
            inert={i !== index}
            className="pq-phone-pager-page"
            data-testid={`phone-page-${p.id}`}
          >
            {p.content}
          </section>
        ))}
      </div>

      <div className="pq-phone-pager-dots" aria-hidden data-testid="phone-pager-dots">
        {pages.map((p, i) => (
          <span
            key={p.id}
            style={{
              width: i === index ? 18 : 6,
              background: i === index ? "var(--pq-bronze)" : "rgba(var(--pq-ivory-rgb), 0.22)",
              transition: dotTransition,
            }}
          />
        ))}
      </div>

      <style jsx>{`
        /* Fills the space between the TopBar and the BottomNav, so each page
           scrolls on its own and the strip never leaves the screen. Anything
           the layout puts above (status banners) pushes it down; the document
           then scrolls the difference, which is also how the footer and the
           layout's disclaimer below stay reachable. */
        .pq-phone-pager {
          display: flex;
          flex-direction: column;
          height: calc(
            100vh - var(--pq-topbar-height) - var(--pq-safe-top) - 24px -
              var(--pq-bottomnav-clearance)
          );
          height: calc(
            100dvh - var(--pq-topbar-height) - var(--pq-safe-top) - 24px -
              var(--pq-bottomnav-clearance)
          );
          min-height: 420px;
        }
        .pq-phone-pager-tabs {
          position: relative;
          display: grid;
          margin: 0 -16px;
          border-bottom: 1px solid var(--pq-ivory-line);
          flex-shrink: 0;
        }
        .pq-phone-pager-tab {
          min-height: 44px;
          padding: 0 4px;
          background: transparent;
          border: none;
          font-size: 14px;
          letter-spacing: 0.01em;
          color: var(--pq-ivory-dim);
          cursor: pointer;
          white-space: nowrap;
          -webkit-tap-highlight-color: transparent;
        }
        .pq-phone-pager-tab[data-active="true"] {
          color: var(--pq-ivory);
        }
        .pq-phone-pager-tab:focus-visible {
          outline: 1px solid var(--pq-bronze);
          outline-offset: -3px;
        }
        .pq-phone-pager-underline {
          position: absolute;
          left: 0;
          bottom: -1px;
          height: 2px;
          background: var(--pq-bronze);
          pointer-events: none;
          will-change: transform;
        }
        /* position: relative on the track and on every page — an absolutely
           positioned child (e.g. the equity curve's sr-only figcaption) whose
           containing block sat outside the track escaped its clipping and
           widened the document by a page offset (390px viewport → 421px). */
        .pq-phone-pager-track {
          position: relative;
          flex: 1 1 auto;
          min-height: 0;
          display: flex;
          margin: 0 -16px;
          overflow-x: auto;
          overflow-y: hidden;
          scroll-snap-type: x mandatory;
          /* Android Chrome turns a horizontal overscroll into "back". */
          overscroll-behavior-x: contain;
          scrollbar-width: none;
        }
        .pq-phone-pager-track::-webkit-scrollbar {
          display: none;
        }
        .pq-phone-pager-page {
          position: relative;
          flex: 0 0 100%;
          width: 100%;
          height: 100%;
          overflow-y: auto;
          overflow-x: hidden;
          scroll-snap-align: start;
          scroll-snap-stop: always;
          padding: 16px 16px 24px;
          outline: none;
        }
        .pq-phone-pager-dots {
          display: flex;
          justify-content: center;
          align-items: center;
          gap: 6px;
          height: 20px;
          flex-shrink: 0;
        }
        .pq-phone-pager-dots span {
          height: 6px;
          border-radius: 9999px;
        }
        @media (prefers-reduced-motion: reduce) {
          .pq-phone-pager-track,
          .pq-phone-pager-page {
            scroll-behavior: auto;
          }
        }
      `}</style>
    </div>
  );
}

export default PhonePager;
