"use client";

/**
 * useHistorySteps — the system back gesture walks a phone step flow
 * (2026-10-09, CEO "최대한 앱처럼").
 *
 * /pre-trade and /onboarding page through steps inside one URL. Without
 * this, Android's back button and the iOS edge swipe left the page from any
 * step. Now every step forward pushes a same-URL history entry carrying a
 * step marker, and back (`popstate`) returns to the step that entry names:
 *
 *   forward (button / swipe)  → pushState({ __pqStep })     one entry per step
 *   in-app 이전 / jump back    → history.go(-n) to that step's own entry, so
 *                                the stack never holds a step twice
 *   system back               → popstate → onPopTo(previous step)
 *   system forward            → onPopTo(next step) — the host may refuse
 *                                (an unanswered step), and the entry is undone
 *   flow finished (`locked`)  → history.go(-n) back to the page's own entry,
 *                                so back from the result screen leaves the
 *                                page instead of reopening the submitted form
 *
 * Never submits: a pop only ever calls `onPopTo` with a step number. Saving
 * stays the buttons' job, so back cannot resubmit anything.
 *
 * Coexists with:
 *   - Next.js — the patched pushState copies its `__NA` tree marker into our
 *     entries (we pass no URL), so its popstate handler restores the same
 *     route instead of reloading.
 *   - lib/use-back-dismiss — overlay entries carry `__pqOverlays`; a pop onto
 *     one of those is the overlay's business and ignored here.
 *   - a second visit to the page — entries left behind by an earlier mount
 *     carry another mount id; landing on one is skipped with another back.
 *
 * Phone only: pass `enabled: false` on desktop and nothing is pushed.
 */

import { useEffect, useRef, useState } from "react";

export const STEP_STATE_KEY = "__pqStep";
const OVERLAY_STATE_KEY = "__pqOverlays";

interface StepMarker {
  key: string;
  mount: string;
  idx: number;
  step: number;
}

export interface HistoryStepsOptions {
  /** Flow id — keeps two flows' markers apart. */
  key: string;
  /** Off → no entries, no listener (desktop, tests that do not care). */
  enabled: boolean;
  /** The flow's current step, 0-based and linear. */
  step: number;
  /** The flow is over (submitted / result screen): back leaves the page. */
  locked: boolean;
  /**
   * The user went back (or forward) to `step`. Apply it and return true, or
   * return false to refuse — the history entry is then undone.
   */
  onPopTo: (step: number) => boolean;
  /** A step forward was taken by the user (not by a pop). */
  onAdvance?: () => void;
}

function readMarker(state: unknown): StepMarker | null {
  if (!state || typeof state !== "object") return null;
  const m = (state as Record<string, unknown>)[STEP_STATE_KEY];
  if (!m || typeof m !== "object") return null;
  const { key, mount, idx, step } = m as Partial<StepMarker>;
  if (typeof key !== "string" || typeof mount !== "string") return null;
  if (typeof idx !== "number" || typeof step !== "number") return null;
  return { key, mount, idx, step };
}

function isOverlayEntry(state: unknown): boolean {
  if (!state || typeof state !== "object") return false;
  const stack = (state as Record<string, unknown>)[OVERLAY_STATE_KEY];
  return Array.isArray(stack) && stack.length > 0;
}

let mountSeq = 0;

export function useHistorySteps({
  key,
  enabled,
  step,
  locked,
  onPopTo,
  onAdvance,
}: HistoryStepsOptions): void {
  const [mount] = useState(() => `m${Date.now().toString(36)}${++mountSeq}`);
  /** Steps by entry index, for this mount. entries[0] = the page's own entry. */
  const entries = useRef<number[]>([]);
  const curIdx = useRef(0);
  /** Pops we caused ourselves (history.go) still to arrive. */
  const selfPops = useRef(0);
  /** The page's own path — a same-path entry without our marker is the base. */
  const pagePath = useRef("");
  const latest = useRef({ step, locked, onPopTo, onAdvance });
  useEffect(() => {
    latest.current = { step, locked, onPopTo, onAdvance };
  });

  // Mark the page's own entry as this mount's base. Overwrites a marker left
  // by an earlier visit (we came back to an entry that one pushed).
  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;
    if (entries.current.length > 0) return; // StrictMode re-run
    entries.current = [latest.current.step];
    curIdx.current = 0;
    pagePath.current = window.location.pathname;
    const marker: StepMarker = { key, mount, idx: 0, step: latest.current.step };
    const prev = (window.history.state as Record<string, unknown> | null) ?? {};
    window.history.replaceState({ ...prev, [STEP_STATE_KEY]: marker }, "");
  }, [enabled, key, mount]);

  // Keep history in line with the step the page shows.
  useEffect(() => {
    if (!enabled || typeof window === "undefined" || entries.current.length === 0) return;
    const go = (delta: number) => {
      if (delta === 0) return;
      selfPops.current += 1;
      window.history.go(delta);
    };
    if (locked) {
      if (curIdx.current > 0) {
        go(-curIdx.current);
        curIdx.current = 0;
      }
      return;
    }
    const shown = entries.current[curIdx.current];
    if (step === shown) return;
    if (step > shown) {
      const idx = curIdx.current + 1;
      entries.current = [...entries.current.slice(0, idx), step];
      curIdx.current = idx;
      const marker: StepMarker = { key, mount, idx, step };
      // No URL and no `__NA`: Next.js's patched pushState copies its own
      // tree marker in, so the entry stays a same-route entry.
      window.history.pushState({ [STEP_STATE_KEY]: marker }, "");
      latest.current.onAdvance?.();
      return;
    }
    // Back inside the app (이전 / a jump from the review screen): return to
    // that step's own entry instead of stacking a duplicate.
    for (let j = curIdx.current - 1; j >= 0; j--) {
      if (entries.current[j] === step) {
        go(j - curIdx.current);
        curIdx.current = j;
        return;
      }
    }
    // Never pushed (should not happen in a linear flow): relabel in place.
    entries.current[curIdx.current] = step;
    const prev = (window.history.state as Record<string, unknown> | null) ?? {};
    window.history.replaceState(
      { ...prev, [STEP_STATE_KEY]: { key, mount, idx: curIdx.current, step } },
      "",
    );
  }, [enabled, step, locked, key, mount]);

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;
    const onPopState = (e: PopStateEvent) => {
      if (isOverlayEntry(e.state)) return;
      const marker = readMarker(e.state);
      if (selfPops.current > 0) {
        selfPops.current -= 1;
        if (marker && marker.key === key && marker.mount === mount) curIdx.current = marker.idx;
        return;
      }
      const samePage = window.location.pathname === pagePath.current;
      if (!marker || marker.key !== key) {
        // Another route's entry — Next.js handles it. One exception: our own
        // page's entry whose marker a Next.js state update rewrote; treat it
        // as the page's base (the first step).
        if (!samePage || (marker && marker.key !== key)) return;
      } else if (marker.mount !== mount) {
        // Left behind by an earlier visit: not a step of this flow. Keep going
        // the way the user was going (almost always back). The next pop is
        // judged on its own, so a run of such entries is skipped one by one.
        window.history.back();
        return;
      }
      const idx = marker ? marker.idx : 0;
      const { step: shown, locked: isLocked, onPopTo } = latest.current;
      if (isLocked) {
        if (idx > 0) {
          selfPops.current += 1;
          window.history.go(-idx);
        }
        curIdx.current = 0;
        return;
      }
      const target = entries.current[idx] ?? marker?.step ?? entries.current[0];
      if (target === undefined) return;
      if (target === shown) {
        curIdx.current = idx;
        return;
      }
      if (onPopTo(target)) {
        curIdx.current = idx;
        return;
      }
      // Refused: put the history pointer back on the step still shown.
      const delta = curIdx.current - idx;
      if (delta !== 0) {
        selfPops.current += 1;
        window.history.go(delta);
      }
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [enabled, key, mount]);
}
