/**
 * Viral-loop funnel telemetry — fire-and-forget client helper for
 * POST /api/track (backend commit 7a57a9da, routes/growth.py).
 *
 * The endpoint is PUBLIC (no auth) and the backend swallows insert errors
 * into a 200 `{ok:false}` so the client never retry-storms. This helper
 * therefore never throws and never blocks the caller: every send is best
 * effort. A logged-in user is attributed server-side via the session
 * cookie; for anonymous landing views we attach a persisted random
 * `anon_id` (non-PII) so a pre-signup → signup journey can be stitched.
 *
 * §101 / privacy: the bodies carry only an event name, an optional channel
 * label, the inviter's ref_code, and a bounded `meta` map. No PII, no
 * ticker+forecast pairs. The backend re-validates + clips every field.
 */

import { API } from "./endpoints";
import type { FunnelEvent, TrackEventBody } from "./types";

const ANON_ID_KEY = "pq_anon_id";

/**
 * Stable per-browser random id (non-PII) used to attribute anonymous
 * landing views to a later signup. Lazily created in localStorage. Returns
 * undefined on the server or when storage is unavailable (private mode).
 */
export function getAnonId(): string | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    let id = localStorage.getItem(ANON_ID_KEY);
    if (!id) {
      id =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : Math.random().toString(36).slice(2) + Date.now().toString(36);
      // anon_id is clipped to 64 chars server-side; a UUID is 36.
      localStorage.setItem(ANON_ID_KEY, id);
    }
    return id;
  } catch {
    return undefined;
  }
}

/**
 * Coerce a meta map into the bounded { string|number|boolean } shape the
 * backend accepts (keys ≤12, values ≤200 chars). We pass through as-is and
 * let the server clip — this is a light client-side guard against obviously
 * oversized payloads only.
 */
function clampMeta(
  meta: TrackEventBody["meta"],
): TrackEventBody["meta"] | undefined {
  if (!meta) return undefined;
  const out: Record<string, string | number | boolean> = {};
  let count = 0;
  for (const [k, v] of Object.entries(meta)) {
    if (count >= 12) break;
    if (typeof v === "string" && v.length > 200) {
      out[k] = v.slice(0, 200);
    } else {
      out[k] = v;
    }
    count += 1;
  }
  return out;
}

/**
 * Send one funnel event. Never throws; resolves to `true` when the POST
 * round-tripped 2xx (regardless of the body's `ok`), `false` otherwise.
 *
 * Uses `fetch` directly (not `apiFetch`) because:
 *   - it must work for anonymous callers (apiFetch redirects on 401),
 *   - it must never surface a toast on rate-limit (telemetry is silent),
 *   - it should use `keepalive` so an in-flight beacon survives navigation.
 */
export async function track(
  event: FunnelEvent,
  opts?: {
    channel?: string;
    refCode?: string;
    meta?: TrackEventBody["meta"];
    /** Pass false to skip attaching the persisted anon_id. */
    includeAnonId?: boolean;
  },
): Promise<boolean> {
  if (typeof window === "undefined") return false;

  const body: TrackEventBody = { event };
  if (opts?.channel) body.channel = opts.channel.slice(0, 40);
  if (opts?.refCode) body.ref_code = opts.refCode.slice(0, 16);
  const anon = opts?.includeAnonId === false ? undefined : getAnonId();
  if (anon) body.anon_id = anon;
  const meta = clampMeta(opts?.meta);
  if (meta && Object.keys(meta).length > 0) body.meta = meta;

  try {
    const res = await fetch(API.viral.track, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      keepalive: true,
    });
    return res.ok;
  } catch {
    return false;
  }
}
