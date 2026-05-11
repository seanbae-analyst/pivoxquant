/**
 * had-session — a single-bit "this browser has ever held an authenticated
 * session" marker stored in localStorage.
 *
 * Why it exists
 * -------------
 * The "Session expired — please log in again" banner on /login?expired=1
 * is appropriate ONLY when a real session existed and lapsed. A first-time
 * visitor whose protected fetch returned 401 is not "expired" — they were
 * never authenticated to begin with, and showing them the expired message
 * is misleading (E2E P2 #11).
 *
 * Lifecycle
 * ---------
 * - mark()  — called when AuthProvider first observes an authenticated user
 *             (login success or warm session restore).
 * - clear() — called from logout(), so the next 401 on this device is
 *             treated as a fresh-guest 401 rather than an expiry.
 * - read()  — called by apiFetch before deciding which login URL to bounce
 *             the user to. If false, drop the `?expired=1` query string.
 *
 * Storage
 * -------
 * localStorage["pq_had_session"] = "1"  (single literal, no PII, no token).
 * SSR-safe via window typeof guards.
 */

const KEY = "pq_had_session";

export function markHadSession(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, "1");
  } catch {
    /* QuotaExceeded / privacy mode — fine, we just degrade to "show the
       banner unconditionally", same as before this guard existed. */
  }
}

export function clearHadSession(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* see above */
  }
}

export function hadSession(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}
