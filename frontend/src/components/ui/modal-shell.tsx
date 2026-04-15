"use client";

import {
  useEffect,
  useRef,
  useCallback,
  type ReactNode,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { cn } from "@/lib/utils";

/**
 * ModalShell — accessible modal wrapper.
 *
 * Features:
 *   - ESC key closes the modal.
 *   - Focus trap (Tab cycles inside the dialog).
 *   - First focusable element receives focus on open.
 *   - Returns focus to the trigger element on close.
 *   - Click on backdrop closes the modal (optional).
 *   - Locks body scroll while open.
 *
 * Usage: render conditionally (e.g. `{open && <ModalShell ... />}`).
 * The component handles its own keyboard / focus lifecycle on mount/unmount.
 */

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

interface ModalShellProps {
  onClose: () => void;
  children: ReactNode;
  /** Outer wrapper className (e.g. layout/positioning). */
  className?: string;
  /** Whether clicking the backdrop closes the modal. Default: true. */
  closeOnBackdrop?: boolean;
  /** ARIA label for the dialog (use when no visible title is available). */
  ariaLabel?: string;
  /** ID of element labelling the dialog (preferred over ariaLabel). */
  ariaLabelledBy?: string;
}

export function ModalShell({
  onClose,
  children,
  className,
  closeOnBackdrop = true,
  ariaLabel,
  ariaLabelledBy,
}: ModalShellProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  /** Focus the first focusable element inside the dialog. */
  const focusFirst = useCallback(() => {
    const node = containerRef.current;
    if (!node) return;
    const focusables = node.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
    const target = focusables[0] ?? node;
    target.focus();
  }, []);

  /** Save trigger, focus first input, restore on unmount. */
  useEffect(() => {
    previouslyFocusedRef.current =
      typeof document !== "undefined"
        ? (document.activeElement as HTMLElement | null)
        : null;

    // requestAnimationFrame so animations / portals settle first.
    const raf = requestAnimationFrame(focusFirst);

    // Lock body scroll.
    const prevOverflow =
      typeof document !== "undefined" ? document.body.style.overflow : "";
    if (typeof document !== "undefined") {
      document.body.style.overflow = "hidden";
    }

    return () => {
      cancelAnimationFrame(raf);
      if (typeof document !== "undefined") {
        document.body.style.overflow = prevOverflow;
      }
      // Restore focus to the trigger after close.
      const prev = previouslyFocusedRef.current;
      if (prev && typeof prev.focus === "function") {
        // setTimeout 0 to wait for React to flush the unmount.
        setTimeout(() => prev.focus(), 0);
      }
    };
  }, [focusFirst]);

  /** Global ESC handler (works even if focus escapes the dialog). */
  useEffect(() => {
    function handleKey(e: globalThis.KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  /** Focus trap: Tab / Shift+Tab cycle inside the dialog. */
  function handleKeyDown(e: ReactKeyboardEvent<HTMLDivElement>) {
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

    if (e.shiftKey) {
      if (active === first || !node.contains(active)) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (active === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  function handleBackdropMouseDown(e: React.MouseEvent<HTMLDivElement>) {
    if (!closeOnBackdrop) return;
    if (e.target === e.currentTarget) onClose();
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        // Mobile: scrollable container with bottom-anchored sheet feel; sm+: centered dialog
        "fixed inset-0 z-50 flex items-end justify-center overflow-y-auto bg-black/40 p-3 sm:items-center sm:p-4",
        className,
      )}
      onMouseDown={handleBackdropMouseDown}
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
      aria-label={ariaLabelledBy ? undefined : ariaLabel}
      aria-labelledby={ariaLabelledBy}
    >
      {children}
    </div>
  );
}
