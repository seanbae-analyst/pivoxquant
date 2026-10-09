/**
 * One short haptic tick (2026-10-09) — Android Chrome / installed PWA only.
 *
 * `navigator.vibrate` does not exist on iOS (Safari exposes no web haptics),
 * so there it is a silent no-op; nothing else is attempted. Skipped under
 * prefers-reduced-motion, which on Android also covers "remove animations".
 * Used for moments that commit something: the pull-to-refresh threshold and
 * a step forward in the /pre-trade flow.
 */

/** Default tick length (ms) — a tap, not a buzz. */
export const HAPTIC_TICK_MS = 10;

export function hapticTick(ms: number = HAPTIC_TICK_MS): void {
  if (typeof window === "undefined" || typeof navigator === "undefined") return;
  if (typeof navigator.vibrate !== "function") return;
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
  try {
    navigator.vibrate(ms);
  } catch {
    /* some embedders throw on vibrate without a user gesture */
  }
}
