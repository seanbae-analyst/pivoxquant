"use client";

/**
 * Bug #17 (Wave 3c, fix 2026-05-09) — vim-style "g + key" goto sequences.
 *
 * `frontend/src/components/ui/profile-dropdown.tsx::ShortcutsModal` lists
 * three sequences in the Keyboard Shortcuts modal:
 *
 *   G then H  → /home
 *   G then P  → /portfolio
 *   G then W  → /watchlist
 *
 * Until this commit, those rows were aspirational — no handler was wired,
 * so pressing the sequence did nothing. The modal advertised functionality
 * the app did not deliver.
 *
 * This hook installs a single document-level keydown listener that:
 *   1. Captures a leading "g" press, opens a 1.5s pending window.
 *   2. If the next keydown within the window matches a registered key,
 *      navigates via Next.js router and consumes the event.
 *   3. Any non-matching key (or timeout) closes the window silently.
 *
 * Activation guards (skip the sequence so users can type normally):
 *   - Active element is an editable field (input/textarea/contenteditable)
 *   - Modifier key held (⌘/Ctrl/Alt/Meta) — palette is ⌘K, not interfered
 *   - IME composition in progress (event.isComposing)
 *
 * Call from a single mount point (dashboard layout) so the listener is
 * installed exactly once. Multiple mounts compete and double-fire.
 */

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

const PENDING_WINDOW_MS = 1500;

/** Keep in sync with `ShortcutsModal` — visible to users. */
const GOTO_MAP: Readonly<Record<string, string>> = {
  h: "/home",
  p: "/portfolio",
  w: "/watchlist",
};

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (target.isContentEditable) return true;
  return false;
}

export function useKeyboardNav() {
  const router = useRouter();
  // ref instead of state — we don't want re-renders on every keypress.
  const pendingRef = useRef<{ at: number } | null>(null);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      // Skip if user is typing or hitting a chord with modifiers (palette, etc.)
      if (e.isComposing) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (isEditableTarget(e.target)) return;

      const key = e.key.toLowerCase();
      const pending = pendingRef.current;

      // Step 2: a goto-target arrived inside the pending window.
      if (pending && Date.now() - pending.at <= PENDING_WINDOW_MS) {
        pendingRef.current = null;
        const dest = GOTO_MAP[key];
        if (dest) {
          e.preventDefault();
          router.push(dest);
        }
        // Non-matching key silently cancels — no preventDefault so the
        // user's keystroke (e.g. plain typing) still reaches its target.
        return;
      }

      // Step 1: leading "g" opens the pending window.
      if (key === "g") {
        pendingRef.current = { at: Date.now() };
        return;
      }

      // Any other key with no pending state — ignore.
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [router]);
}
