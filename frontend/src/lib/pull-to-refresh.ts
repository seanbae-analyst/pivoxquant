/**
 * Pull-to-refresh — gesture math and the SWR refresh helper (2026-10-09).
 * The component is components/layout/pull-to-refresh.tsx.
 */

import { mutate } from "swr";

/** Damped pull (px) at which releasing refreshes. */
export const PULL_THRESHOLD_PX = 70;
/** The damped pull never goes past this, however far the finger travels. */
export const PULL_MAX_PX = 140;
/** Where the indicator rests while the refresh runs. */
export const PULL_REST_PX = 56;
/** Finger travel before the gesture is classified (pull / not a pull). */
export const PULL_SLOP_PX = 8;
/** A pull must be this many times taller than wide — otherwise it is a swipe. */
export const PULL_AXIS_RATIO = 1.4;
/** The spinner stays at least this long, so a fast refresh still reads. */
export const PULL_MIN_SPIN_MS = 500;

/**
 * Rubber-band resistance: the indicator follows the finger 1:1 at first and
 * ever more slowly after, approaching PULL_MAX_PX. The threshold (70) is
 * reached at ~97px of finger travel.
 */
export function rubberBand(dy: number): number {
  if (dy <= 0) return 0;
  return PULL_MAX_PX * (1 - Math.exp(-dy / PULL_MAX_PX));
}

export type PullIntent = "undecided" | "pull" | "other";

/**
 * Classify a gesture from its travel so far. Only a downward, mostly
 * vertical move is a pull; anything sideways belongs to the swipe pagers.
 */
export function classifyPull(dx: number, dy: number): PullIntent {
  if (Math.abs(dx) < PULL_SLOP_PX && Math.abs(dy) < PULL_SLOP_PX) return "undecided";
  if (dy > 0 && dy >= Math.abs(dx) * PULL_AXIS_RATIO) return "pull";
  return "other";
}

/** "/api/x?limit=5" → "/api/x" */
function basePath(key: string): string {
  return key.split("?")[0];
}

/**
 * Revalidate every SWR key whose path is one of `keys` (query strings
 * ignored, so `usePreTradeJournal`'s `${API.preTrade.list}?limit=50` matches
 * `API.preTrade.list`). Keys and endpoints are the hooks' own — nothing is
 * renamed; only keys a mounted hook is using actually refetch. The cached
 * data stays on screen while the refetch runs (no skeleton).
 */
export function revalidateKeys(keys: ReadonlyArray<string>): Promise<unknown> {
  const bases = new Set(keys.map(basePath));
  return mutate((key: unknown) => typeof key === "string" && bases.has(basePath(key)));
}
