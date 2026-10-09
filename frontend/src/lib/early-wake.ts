/**
 * Early backend wake — one fire-and-forget `/api/health` GET at app start.
 *
 * The backend sleeps on Render's free plan (cold start ~44 s, see
 * `.github/workflows/keep-warm.yml` and lib/backend-wake.ts). Render starts
 * booting on the first request it receives, whatever its outcome — even a
 * 502 or an aborted socket. So the earlier ANY request reaches it, the
 * earlier everything else (the auth probe, the screen's data) can be served.
 *
 * This fires from the providers module as soon as the client bundle is
 * evaluated, i.e. before React hydrates and before AuthProvider's
 * `/api/auth/me` is queued.
 *
 * Cost: none in instance hours. AuthProvider already calls `/api/auth/me` on
 * every page (including the landing page), which wakes the service just the
 * same — this only moves the wake a little earlier and uses an
 * unauthenticated, cookie-less liveness route to do it. It is NOT a keep-warm:
 * one request per page load, never a timer.
 *
 * Path: `HEALTH_PATH` from lib/backend-wake (endpoints.ts has no health
 * symbol; `/api/*` is rewritten to the backend by next.config.ts).
 */

import { isDemoMode } from "./demo";
import { HEALTH_PATH } from "./backend-wake";
import { EARLY_WAKE_WINDOW_FLAG } from "./early-wake-inline";

let fired = false;

/**
 * Fire the wake request once per page load. Returns true when this call
 * actually sent it (false: already sent, server render, demo mode, or no
 * fetch). Never throws, never awaits, never retries.
 */
export function wakeBackendEarly(): boolean {
  if (fired) return false;
  if (typeof window === "undefined" || typeof fetch !== "function") return false;
  if (isDemoMode()) return false; // demo serves fixtures; there is no backend
  fired = true;
  // The optional inline <head> script (lib/early-wake-inline) already sent it.
  if ((window as unknown as Record<string, unknown>)[EARLY_WAKE_WINDOW_FLAG]) return false;
  try {
    void fetch(HEALTH_PATH, {
      method: "GET",
      cache: "no-store",
      credentials: "omit",
      // Let the request outlive a quick navigation where the browser allows.
      keepalive: true,
    }).catch(() => {
      /* a sleeping backend answering 502 / a dropped socket is expected */
    });
  } catch {
    /* fetch threw synchronously (exotic environments) — nothing to do */
  }
  return true;
}

/** Test-only: allow another wake in the same module instance. */
export function __resetEarlyWakeForTests(): void {
  fired = false;
}
