"use client";

/**
 * Auth wake poll — what AuthProvider does while it does not know who is
 * signed in because the backend has not answered yet.
 *
 * Measured 2026-10-09 (perf audit, cold Render backend): opening /mirror
 * redirected a signed-in user to /login at 13 s, showed the sign-in buttons
 * at ~38 s and came back at 51 s; the `/api/auth/me` retries landed at
 * 7.4 / 25.4 / 53.4 s, so ~9 s were lost AFTER the backend was already up.
 *
 * So while the auth state is "unknown" this polls the cheap, cookie-less
 * `/api/health` probe every WAKE_POLL_INTERVAL_MS and re-runs the auth probe
 * the moment it answers 200 — instead of waiting for the auth probe's own
 * retry timer. At WAKE_DEADLINE_MS (the same deadline the OAuth buttons use)
 * it reports `gaveUp`, so the shell can show an honest error with a retry
 * button rather than a spinner forever.
 *
 * 2026-10-10: past the deadline it keeps checking, every
 * AFTER_DEADLINE_POLL_MS. Measured locally (backend answering at 100 s): the
 * poll stopped at 75 s, the auth probe's own retries ran out at ~88 s, and
 * the screen never recovered after the server came up — on the installed
 * app's cover that read as a frozen app. A Render cold start that has to pull
 * the image can run past the deadline, so the error line now clears on its
 * own once the server answers; the retry button still checks at once.
 */

import { useCallback, useEffect, useState } from "react";
import {
  probeBackendOnce,
  WAKE_DEADLINE_MS,
  WAKE_POLL_INTERVAL_MS,
  WAKE_PROBE_TIMEOUT_MS,
} from "./backend-wake";

/**
 * Health said 200 but the auth probe still had no answer (e.g. a 429, or the
 * session store still warming). Back off so we do not hammer /me every 2 s.
 */
export const AUTH_AFTER_HEALTHY_BACKOFF_MS = 10_000;

/** Health-poll gap once the deadline has passed (gaveUp is showing). */
export const AFTER_DEADLINE_POLL_MS = 15_000;

export interface AuthWakePollOptions {
  pollIntervalMs?: number;
  deadlineMs?: number;
  probeTimeoutMs?: number;
  healthyBackoffMs?: number;
  afterDeadlinePollMs?: number;
}

export interface AuthWakePoll {
  /** The deadline passed with no answer from the auth probe. */
  gaveUp: boolean;
  /** Start over (button handler). Also re-runs the auth probe at once. */
  retry: () => void;
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(done, ms);
    function done() {
      clearTimeout(timer);
      signal.removeEventListener("abort", done);
      resolve();
    }
    if (signal.aborted) done();
    else signal.addEventListener("abort", done, { once: true });
  });
}

/**
 * @param unknown   true while the auth probe has never answered and its last
 *                  attempt failed with "could not reach the server".
 * @param revalidate re-runs the auth probe; resolves to the new data, or
 *                  undefined when it failed again.
 */
export function useAuthWakePoll(
  unknown: boolean,
  revalidate: () => Promise<unknown>,
  options: AuthWakePollOptions = {},
): AuthWakePoll {
  const {
    pollIntervalMs = WAKE_POLL_INTERVAL_MS,
    deadlineMs = WAKE_DEADLINE_MS,
    probeTimeoutMs = WAKE_PROBE_TIMEOUT_MS,
    healthyBackoffMs = AUTH_AFTER_HEALTHY_BACKOFF_MS,
    afterDeadlinePollMs = AFTER_DEADLINE_POLL_MS,
  } = options;
  const [gaveUp, setGaveUp] = useState(false);
  // Bumped by retry() so the effect below restarts its loop.
  const [round, setRound] = useState(0);

  useEffect(() => {
    if (!unknown) return;
    const ac = new AbortController();
    const deadline = Date.now() + deadlineMs;
    void (async () => {
      // Runs until the auth probe answers (`unknown` flips off and this
      // effect is cleaned up), the component unmounts, or retry() restarts it.
      while (!ac.signal.aborted) {
        const late = Date.now() >= deadline;
        if (late) setGaveUp(true);
        const healthy = await probeBackendOnce(probeTimeoutMs, ac.signal);
        if (ac.signal.aborted) return;
        if (healthy) {
          const data = await revalidate().catch(() => undefined);
          if (data !== undefined || ac.signal.aborted) return;
          await sleep(healthyBackoffMs, ac.signal);
        } else {
          await sleep(late ? afterDeadlinePollMs : pollIntervalMs, ac.signal);
        }
      }
    })();
    return () => ac.abort();
  }, [
    unknown,
    round,
    revalidate,
    deadlineMs,
    pollIntervalMs,
    probeTimeoutMs,
    healthyBackoffMs,
    afterDeadlinePollMs,
  ]);

  const retry = useCallback(() => {
    setGaveUp(false);
    setRound((r) => r + 1);
    void revalidate().catch(() => undefined);
  }, [revalidate]);

  // Once the backend has answered, a later outage starts a fresh deadline.
  if (!unknown && gaveUp) setGaveUp(false);

  return { gaveUp, retry };
}
