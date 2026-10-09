"use client";

/**
 * JournalPager — the /journal sections as swipeable pages on a phone.
 *
 * 2026-10-09, CEO: "기록부분이랑 포트폴리오 부분도 화면 넘어가는식으로 구상
 * 바꿔줘 앱은". Below md the page's sections sit side by side in a horizontal
 * CSS scroll-snap track: swipe between them, or tap the tab strip. At md and
 * up the track and the page boxes dissolve (`md:flex-col` + `md:contents`), so
 * the desktop page is the same stacked column it always was — each section's
 * own `md:order-*` puts it back in the desktop sequence.
 *
 * No gesture library: the browser does the swipe, the snap and the momentum,
 * so it also behaves under prefers-reduced-motion (tab taps jump instead of
 * gliding) and with a keyboard (arrow keys on the tab strip).
 *
 * Vertical scroll stays on the window — the layout's legal disclaimer is
 * mounted after the page and must stay reachable — but every page keeps its
 * own vertical position:
 *   - only the active page has a height; the others are height 0 and paint
 *     over the track (clipped by it), so a short page never inherits the
 *     blank height of a long one;
 *   - each inactive page is translated so the spot it was last read at sits
 *     right under the tab strip, which is what slides into view mid-swipe;
 *   - when a swipe settles, the window is scrolled to that same spot, so the
 *     picture does not move when the new page takes over.
 * Inactive pages are `inert`, so focus and screen readers stay on the page in
 * view.
 */

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type KeyboardEvent,
  type ReactNode,
} from "react";

export interface JournalPage {
  id: string;
  label: string;
  content: ReactNode;
}

/** Tailwind's `md` is 48rem; below it is the phone layout. */
const PHONE_QUERY = "(max-width: 47.99rem)";
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/**
 * How long the track must be still before a swipe counts as settled. Safari
 * (the installed iOS app) has no `scrollend` before 26, so this debounce is
 * the settle signal there; elsewhere `scrollend` arrives first.
 */
const SETTLE_DELAY_MS = 120;

function subscribeMedia(onChange: () => void): () => void {
  const lists = [PHONE_QUERY, REDUCED_MOTION_QUERY]
    .map((q) => window.matchMedia?.(q))
    .filter((m): m is MediaQueryList => Boolean(m));
  lists.forEach((m) => m.addEventListener("change", onChange));
  return () => lists.forEach((m) => m.removeEventListener("change", onChange));
}

function matches(query: string): boolean {
  return window.matchMedia?.(query).matches ?? false;
}

function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    subscribeMedia,
    () => matches(query),
    () => false,
  );
}

/**
 * Scroll the window without a glide. Since 2026-10-09 `html` is smooth only
 * on the landing (globals.css), so this is belt-and-braces: should a smooth
 * rule ever reach this page again, a plain scrollTo would animate, and older
 * WebKit rejects `behavior: "instant"` — so the CSS is lifted for the call.
 */
function jumpWindowTo(top: number): void {
  const root = document.documentElement;
  const previous = root.style.scrollBehavior;
  root.style.scrollBehavior = "auto";
  window.scrollTo(0, top);
  root.style.scrollBehavior = previous;
}

function clampIndex(i: number, count: number): number {
  return Math.min(Math.max(i, 0), count - 1);
}

export function JournalPager({
  pages,
  requestedPage,
  ariaLabel,
  onPageChange,
}: {
  pages: ReadonlyArray<JournalPage>;
  /** A deep link's page (e.g. #weekly-pulse). Jumps there whenever it changes. */
  requestedPage: number;
  ariaLabel: string;
  /**
   * Called with the new page's index once a page change commits (a settled
   * swipe, a tapped tab, or a requested page). Optional — /journal does not
   * need it; /journal/import keeps its submit target on the page in view.
   */
  onPageChange?: (index: number) => void;
}) {
  const isPhone = useMediaQuery(PHONE_QUERY);
  const reducedMotion = useMediaQuery(REDUCED_MOTION_QUERY);
  const count = pages.length;

  const [active, setActive] = useState(0);
  /** The page nearest the viewport mid-swipe — what the strip highlights. */
  const [near, setNear] = useState(0);

  const activeRef = useRef(0);
  const stripRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const underlineRef = useRef<HTMLSpanElement>(null);
  const pageRefs = useRef<Array<HTMLDivElement | null>>([]);
  /** Per page: how far into the page (px) it was last read. */
  const savedOffsets = useRef<number[]>([]);
  const pendingScroll = useRef<number | null>(null);
  const settleTimer = useRef<number | null>(null);
  const frame = useRef<number | null>(null);
  // Held in a ref so an inline callback does not re-create commit/settle (and
  // re-subscribe the track's listeners) on every parent render.
  const onPageChangeRef = useRef(onPageChange);
  useEffect(() => {
    onPageChangeRef.current = onPageChange;
  }, [onPageChange]);

  /** Document y at which the track's top sits flush under the sticky strip. */
  const anchorY = useCallback((): number => {
    const track = trackRef.current;
    const strip = stripRef.current;
    if (!track || !strip) return 0;
    const stuckBottom =
      (parseFloat(getComputedStyle(strip).top) || 0) + strip.offsetHeight;
    return Math.max(
      0,
      track.getBoundingClientRect().top + window.scrollY - stuckBottom,
    );
  }, []);

  /** How far the reader has scrolled into the active page. */
  const readDepth = useCallback(
    (): number => Math.max(0, window.scrollY - anchorY()),
    [anchorY],
  );

  /** Line each off-screen page up so its last-read spot meets the strip. */
  const alignInactive = useCallback(() => {
    const depth = isPhone ? readDepth() : 0;
    pageRefs.current.forEach((el, i) => {
      if (!el) return;
      const offset = savedOffsets.current[i] ?? 0;
      el.style.transform =
        isPhone && i !== activeRef.current
          ? `translateY(${depth - offset}px)`
          : "";
    });
  }, [isPhone, readDepth]);

  const commit = useCallback(
    (next: number) => {
      const prev = activeRef.current;
      if (next === prev) return;
      const depth = readDepth();
      const anchor = anchorY();
      savedOffsets.current[prev] = depth;
      const resume = savedOffsets.current[next] ?? 0;
      // Resume where this page was left; a page never read starts at its top
      // (or stays put while the reader is still above the pages). Desktop
      // stacks every section, so there is nothing to resume there.
      pendingScroll.current = !isPhone
        ? null
        : resume > 0
          ? anchor + resume
          : depth > 0
            ? anchor
            : null;
      activeRef.current = next;
      setActive(next);
      setNear(next);
      onPageChangeRef.current?.(next);
    },
    [anchorY, readDepth, isPhone],
  );

  const settle = useCallback(() => {
    if (settleTimer.current !== null) {
      window.clearTimeout(settleTimer.current);
      settleTimer.current = null;
    }
    const track = trackRef.current;
    if (!track || track.clientWidth === 0) return;
    commit(clampIndex(Math.round(track.scrollLeft / track.clientWidth), count));
  }, [commit, count]);

  // Window scroll after a page change, before paint — see the file comment.
  // On MOUNT there is no page change to land: the off-screen pages are out
  // of view, so lining them up can wait a frame instead of forcing a
  // synchronous layout in the middle of hydration (alignInactive measures the
  // strip and the track; measured 2026-10-09 at 4× CPU throttle).
  const mounted = useRef(false);
  useLayoutEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      const id = window.requestAnimationFrame(() => alignInactive());
      return () => window.cancelAnimationFrame(id);
    }
    const track = trackRef.current;
    if (track) track.scrollTop = 0;
    if (pendingScroll.current !== null) {
      jumpWindowTo(pendingScroll.current);
      pendingScroll.current = null;
    }
    alignInactive();
  }, [active, alignInactive]);

  // Deep link: land on the page without a glide, before the first paint. The
  // page change itself commits on the next frame, like any settled swipe.
  useLayoutEffect(() => {
    const track = trackRef.current;
    const target = clampIndex(requestedPage, count);
    if (!track || target === activeRef.current) return;
    track.scrollLeft = target * track.clientWidth;
    const id = window.requestAnimationFrame(() => commit(target));
    return () => window.cancelAnimationFrame(id);
  }, [requestedPage, count, commit]);

  // Keep the off-screen pages lined up while the active one is read, and keep
  // the track on its page when the width changes (rotation, split view).
  useEffect(() => {
    if (!isPhone) {
      alignInactive();
      return;
    }
    const onScroll = () => {
      if (frame.current !== null) return;
      frame.current = window.requestAnimationFrame(() => {
        frame.current = null;
        alignInactive();
      });
    };
    const onResize = () => {
      const track = trackRef.current;
      if (track) track.scrollLeft = activeRef.current * track.clientWidth;
      alignInactive();
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
      if (frame.current !== null) window.cancelAnimationFrame(frame.current);
      frame.current = null;
    };
  }, [isPhone, alignInactive]);

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    track.addEventListener("scrollend", settle);
    return () => {
      track.removeEventListener("scrollend", settle);
      if (settleTimer.current !== null) window.clearTimeout(settleTimer.current);
    };
  }, [settle]);

  const onTrackScroll = () => {
    const track = trackRef.current;
    if (!track || track.clientWidth === 0) return;
    const progress = track.scrollLeft / track.clientWidth;
    // The underline follows the finger: it is driven by the scroll position,
    // never animated on its own.
    if (underlineRef.current) {
      underlineRef.current.style.transform = `translateX(${progress * 100}%)`;
    }
    setNear(clampIndex(Math.round(progress), count));
    if (settleTimer.current !== null) window.clearTimeout(settleTimer.current);
    settleTimer.current = window.setTimeout(settle, SETTLE_DELAY_MS);
  };

  const goTo = (i: number) => {
    const track = trackRef.current;
    if (!track) return;
    alignInactive();
    track.scrollTo({
      left: clampIndex(i, count) * track.clientWidth,
      // The track sets no scroll-behavior, so "auto" is a jump.
      behavior: reducedMotion ? "auto" : "smooth",
    });
  };

  const onTabKey = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (step === 0) return;
    e.preventDefault();
    const next = clampIndex(i + step, count);
    goTo(next);
    document.getElementById(`journal-tab-${pages[next].id}`)?.focus();
  };

  return (
    <>
      <div
        ref={stripRef}
        role="tablist"
        aria-label={ariaLabel}
        className="sticky z-10 -mx-4 flex h-12 border-b md:hidden"
        data-pq-chrome
        style={{
          // Flush under the app bar, which is safe-top + 56px tall in the
          // installed app (globals.css --pq-aux-sticky-top). Not the token
          // itself: journal/page.tsx re-points it below this strip.
          top: "calc(var(--pq-topbar-height) + var(--pq-safe-top))",
          background: "var(--pq-ink)",
          borderColor: "var(--pq-ivory-line)",
        }}
        data-testid="journal-tabs"
      >
        {pages.map((p, i) => {
          const selected = i === active;
          return (
            <button
              key={p.id}
              id={`journal-tab-${p.id}`}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={`journal-page-${p.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => goTo(i)}
              onKeyDown={(e) => onTabKey(e, i)}
              className="flex-1 text-center text-[15px] transition-colors duration-[var(--motion-duration-fast)] motion-reduce:transition-none"
              style={{
                color: i === near ? "var(--pq-ivory)" : "var(--pq-ivory-dim)",
              }}
              data-testid={`journal-tab-${p.id}`}
            >
              {p.label}
            </button>
          );
        })}
        <span
          ref={underlineRef}
          aria-hidden
          className="pointer-events-none absolute bottom-0 left-0 flex h-[2px] justify-center"
          style={{
            width: `${100 / count}%`,
            transform: `translateX(${active * 100}%)`,
          }}
        >
          <span
            className="mx-6 block h-full flex-1"
            style={{ background: "var(--pq-bronze)" }}
          />
        </span>
      </div>

      <div
        ref={trackRef}
        onScroll={onTrackScroll}
        className="-mx-4 flex snap-x snap-mandatory items-start overflow-x-auto overflow-y-hidden overscroll-x-contain [scrollbar-width:none] [&::-webkit-scrollbar]:hidden md:mx-0 md:snap-none md:flex-col md:items-stretch md:overflow-visible"
        data-testid="journal-pager"
      >
        {pages.map((p, i) => {
          const current = i === active;
          return (
            <div
              key={p.id}
              ref={(el) => {
                pageRefs.current[i] = el;
              }}
              id={`journal-page-${p.id}`}
              role={isPhone ? "tabpanel" : undefined}
              aria-labelledby={isPhone ? `journal-tab-${p.id}` : undefined}
              inert={isPhone && !current}
              // pb-12 (phone): the floating page dots sit 10px above the
              // bottom nav; reserve their height so a page's last block
              // scrolls clear of them instead of ending underneath.
              className={`relative w-full shrink-0 snap-start snap-always px-4 pt-4 pb-12 md:contents ${current ? "" : "h-0"}`}
              data-testid={`journal-page-${p.id}`}
              data-active={current ? "true" : "false"}
            >
              {p.content}
            </div>
          );
        })}
      </div>

      {/* Page dots, iOS-style above the bottom nav. Decorative — the tab
          strip carries the page state for assistive tech. */}
      <div
        aria-hidden
        className="pointer-events-none fixed left-1/2 z-40 flex -translate-x-1/2 items-center gap-1.5 rounded-full border px-2.5 py-1.5 md:hidden"
        style={{
          bottom:
            "calc(var(--pq-bottomnav-height) + var(--pq-safe-bottom) + 10px)",
          background: "var(--pq-ink)",
          borderColor: "var(--pq-ivory-line)",
        }}
        data-pq-chrome
        data-testid="journal-page-dots"
      >
        {pages.map((p, i) => (
          <span
            key={p.id}
            className="block h-[5px] rounded-full transition-[width,background-color] duration-[var(--motion-duration-base)] ease-[var(--motion-easing-emphasized)] motion-reduce:transition-none"
            style={{
              width: i === near ? 16 : 5,
              background:
                i === near ? "var(--pq-bronze)" : "var(--pq-ivory-line)",
            }}
          />
        ))}
      </div>
    </>
  );
}
