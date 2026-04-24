"use client";

/**
 * useFocusTrap — shared focus-trap primitive for drawers / modals / sheets.
 * --------------------------------------------------------------------------
 * When `active` is true, the hook:
 *   1. Snapshots the currently focused element (the trigger).
 *   2. Moves focus to the first focusable element inside the container on
 *      the next animation frame (so slide-in / fade-in animations settle
 *      before focus lands visually).
 *   3. Installs a keydown listener on the container scoped to Tab / Shift+Tab:
 *        - Tab on last focusable  → wrap to first.
 *        - Shift+Tab on first     → wrap to last.
 *        - Either on an element outside the container → pull focus back in.
 *   4. Restores focus to the trigger when `active` flips back to false or
 *      the component unmounts.
 *
 * Keeping this in one place means every drawer/sheet/modal gets the same
 * accessible behavior without pulling in `focus-trap` or `react-focus-lock`.
 */

import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export function useFocusTrap<T extends HTMLElement>(
  active: boolean,
): RefObject<T | null> {
  const containerRef = useRef<T | null>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!active) return;
    if (typeof document === "undefined") return;

    // 1. Remember the trigger so we can restore focus on close.
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;

    // 2. Move focus inside on the next frame (let enter-animation mount first).
    const raf = requestAnimationFrame(() => {
      const node = containerRef.current;
      if (!node) return;
      const focusables = node.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      const target = focusables[0] ?? node;
      // Ensure the container itself is focusable as a fallback.
      if (target === node && !node.hasAttribute("tabindex")) {
        node.setAttribute("tabindex", "-1");
      }
      target.focus({ preventScroll: true });
    });

    // 3. Trap Tab / Shift+Tab inside the container.
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const node = containerRef.current;
      if (!node) return;

      const focusables = Array.from(
        node.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      ).filter((el) => !el.hasAttribute("data-focus-skip"));

      if (focusables.length === 0) {
        e.preventDefault();
        return;
      }

      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement as HTMLElement | null;
      const insideContainer = active && node.contains(active);

      if (e.shiftKey) {
        if (!insideContainer || active === first) {
          e.preventDefault();
          last.focus({ preventScroll: true });
        }
      } else {
        if (!insideContainer || active === last) {
          e.preventDefault();
          first.focus({ preventScroll: true });
        }
      }
    };

    document.addEventListener("keydown", onKeyDown);

    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener("keydown", onKeyDown);
      // 4. Restore focus to the trigger after unmount flush.
      const prev = previouslyFocusedRef.current;
      if (prev && typeof prev.focus === "function" && document.contains(prev)) {
        setTimeout(() => prev.focus({ preventScroll: true }), 0);
      }
    };
  }, [active]);

  return containerRef;
}
