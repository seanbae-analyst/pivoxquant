"use client";

/**
 * Backend cold-start wake-up — for full-page navigations we cannot retry.
 *
 * The backend runs on Render's free plan (`render.yaml`: `plan: free`), which
 * spins the service down after 15 idle minutes. Measured against production:
 *
 *   cold  /api/health → 502 on the first request, then 200 in 0.52 s
 *   warm  /api/health → 0.52 s
 *
 * `apiFetch()` already survives this for XHR (one retry on our own timeout —
 * see lib/api.ts). The OAuth buttons cannot: they are plain anchors, so the
 * browser does a FULL PAGE navigation to `/api/auth/google`. A sleeping
 * backend answers that with Render's own unbranded 502 page and the visitor
 * is off our site with no explanation and nothing to retry. That is what
 * "로그인이 안 된다" looks like from the outside.
 *
 * This module gives a caller two things:
 *   1. a one-shot probe fired on mount, so the container starts booting while
 *      the visitor is still reading the page;
 *   2. `wake()`, which polls until the backend answers 200 and only then lets
 *      the navigation happen.
 *
 * It deliberately does NOT go through `apiFetch()`: that layer redirects on
 * 401, toasts on 429 and retries on timeout. A liveness probe wants none of
 * that — a non-200 is simply "not awake yet, poll again".
 */

import { useCallback, useEffect, useRef, useState } from "react";

/** Unauthenticated liveness probe (routes/health.py). 200 = process + DB up. */
export const HEALTH_PATH = "/api/health";

/**
 * Per-probe abort. Warm answers land in 0.52 s, so 8 s is >15× the healthy
 * latency — it never truncates a real answer — while still bounding a socket
 * that Render is holding open during a boot, so the poll loop keeps ticking.
 */
export const WAKE_PROBE_TIMEOUT_MS = 8_000;

/**
 * Gap between probes. A cold boot is tens of seconds, so sub-second polling
 * buys nothing and just hammers the platform. 2 s adds at most 2 s to the
 * perceived wait (~5 % of it) and caps the burst at ~35 requests.
 */
export const WAKE_POLL_INTERVAL_MS = 2_000;

/**
 * Give-up point. 75 s is ~1.7× the worst cold start we have measured (43.9 s
 * on 2026-09-07, recorded in lib/api.ts). Shorter risks abandoning a boot that
 * was about to succeed; longer than ~90 s and the visitor is gone anyway — at
 * that point an honest error with a retry button beats a spinner.
 */
export const WAKE_DEADLINE_MS = 75_000;

export type BackendWakeStatus = "idle" | "waking" | "ready" | "failed";

export interface UseBackendWakeOptions {
  /** false = never probe; `wake()` resolves true at once (demo mode). */
  enabled?: boolean;
  pollIntervalMs?: number;
  deadlineMs?: number;
  probeTimeoutMs?: number;
}

export interface BackendWake {
  status: BackendWakeStatus;
  /** True once a probe has seen a 200 — the click can navigate immediately. */
  isReady: boolean;
  /** Resolves true when the backend is awake, false when we gave up. */
  wake: () => Promise<boolean>;
  /** Clear a `failed` status (used when the user presses retry). */
  reset: () => void;
}

/** setTimeout as a promise that also settles when `signal` aborts. */
function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise<void>((resolve) => {
    const done = () => {
      clearTimeout(timer);
      signal?.removeEventListener("abort", done);
      resolve();
    };
    const timer = setTimeout(done, ms);
    if (signal?.aborted) done();
    else signal?.addEventListener("abort", done, { once: true });
  });
}

/**
 * One liveness probe. Never throws — a network error, a 502 from Render's
 * router and a 503 from a degraded DB all mean the same thing here: not yet.
 */
export async function probeBackendOnce(
  timeoutMs: number = WAKE_PROBE_TIMEOUT_MS,
  signal?: AbortSignal,
): Promise<boolean> {
  if (signal?.aborted) return false;
  const controller = new AbortController();
  const onAbort = () => controller.abort();
  signal?.addEventListener("abort", onAbort, { once: true });
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(HEALTH_PATH, {
      method: "GET",
      cache: "no-store",
      // A liveness probe needs no identity; keep cookies out of it.
      credentials: "omit",
      signal: controller.signal,
    });
    return Boolean(res?.ok);
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
}

export function useBackendWake(options: UseBackendWakeOptions = {}): BackendWake {
  const {
    enabled = true,
    pollIntervalMs = WAKE_POLL_INTERVAL_MS,
    deadlineMs = WAKE_DEADLINE_MS,
    probeTimeoutMs = WAKE_PROBE_TIMEOUT_MS,
  } = options;

  const [status, setStatus] = useState<BackendWakeStatus>("idle");
  // Ref, not state: the poll loop reads it between awaits, where a state
  // snapshot captured at call time would be stale.
  const readyRef = useRef(false);
  const mountedRef = useRef(true);
  const loopAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      loopAbortRef.current?.abort();
    };
  }, []);

  // Mount pre-warm: exactly one probe. Its real job on a cold backend is to be
  // the request that STARTS the boot — Render keeps booting even after we
  // abort, so by the time the visitor clicks, the container is well underway.
  useEffect(() => {
    if (!enabled) return;
    const ac = new AbortController();
    void probeBackendOnce(probeTimeoutMs, ac.signal).then((ok) => {
      if (!ok || ac.signal.aborted || !mountedRef.current) return;
      readyRef.current = true;
      // Don't stomp on an in-flight wake(): that loop owns the transition and
      // the navigation that follows it.
      setStatus((prev) => (prev === "waking" ? prev : "ready"));
    });
    return () => ac.abort();
  }, [enabled, probeTimeoutMs]);

  const wake = useCallback(async (): Promise<boolean> => {
    if (!enabled || readyRef.current) return true;

    loopAbortRef.current?.abort();
    const ac = new AbortController();
    loopAbortRef.current = ac;
    setStatus("waking");

    const deadline = Date.now() + deadlineMs;
    while (!ac.signal.aborted) {
      if (readyRef.current) {
        setStatus("ready");
        return true;
      }
      const ok = await probeBackendOnce(probeTimeoutMs, ac.signal);
      if (ac.signal.aborted) return false;
      if (ok) {
        readyRef.current = true;
        setStatus("ready");
        return true;
      }
      // Stop before a sleep that would run past the deadline.
      if (Date.now() + pollIntervalMs >= deadline) break;
      await sleep(pollIntervalMs, ac.signal);
    }

    if (ac.signal.aborted) return false;
    setStatus("failed");
    return false;
  }, [enabled, deadlineMs, pollIntervalMs, probeTimeoutMs]);

  const reset = useCallback(() => {
    setStatus(readyRef.current ? "ready" : "idle");
  }, []);

  return { status, isReady: status === "ready", wake, reset };
}
