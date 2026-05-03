/**
 * Marketing-consent helpers (정통망법 §50 ①).
 *
 * Why this file exists
 * --------------------
 * Signup collects a `consents.marketing` checkbox in the OAuth gate
 * (`frontend/src/app/(auth)/signup/_v2/page-v2.tsx`). At click-time the
 * user is *not yet authenticated* — the OAuth round-trip happens next,
 * and only after the callback do we have a `current_user` server-side.
 * That's why the snapshot is staged in `localStorage` under
 * `pivox_signup_consents` first; this module is the second leg that
 * flushes that snapshot to the backend record once a session exists.
 *
 * Flush vs. settings-toggle
 * -------------------------
 *   `flushPendingMarketingConsent`  — runs once after sign-in. Reads the
 *     localStorage staging slot, POSTs if marketing was checked, then
 *     clears the slot regardless. Failures are silent: legal evidence is
 *     a "best effort + retry" surface, not a UX-blocking step. We do
 *     NOT block the post-signup flow on the backend POST, because the
 *     user has already cleared the OAuth gate; if Railway is cold the
 *     server-side timestamp will be re-asserted next time the user
 *     toggles in /settings.
 *
 *   `recordMarketingConsent` / `revokeMarketingConsent` — drive the
 *     /settings toggle. These DO surface failure back to the caller so
 *     the toggle UI can roll back its optimistic state.
 *
 *   `fetchMarketingConsent` — initial-state hydration for the toggle.
 *     Returns `null` when unauthenticated or when the endpoint is not
 *     yet deployed (PR #73 dependency); callers should treat that as
 *     "default off, no audit trail to display".
 */

import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";

/* Same key as signup/_v2/page-v2.tsx — DO NOT rename without updating
 * both surfaces in lock-step (this is the cross-page handshake that
 * backs the §50 evidentiary record). */
export const CONSENT_STORAGE_KEY = "pivox_signup_consents";

export interface MarketingConsentState {
  opted_in: boolean;
  marketing_consent_at: string | null;
  marketing_consent_revoked_at: string | null;
}

interface SignupConsentSnapshot {
  terms?: boolean;
  non_advisory?: boolean;
  age?: boolean;
  marketing?: boolean;
  consented_at?: string;
}

function readStagedSnapshot(): SignupConsentSnapshot | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(CONSENT_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as SignupConsentSnapshot;
  } catch {
    return null;
  }
}

function clearStagedSnapshot() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(CONSENT_STORAGE_KEY);
  } catch {
    /* quota / disabled — not load-bearing */
  }
}

/**
 * Persist the staged signup consent snapshot to the backend after the
 * OAuth round-trip lands the user back into the SPA. Idempotent and
 * silent: the user has already gone through the gate, so failing here
 * MUST NOT block any downstream UX.
 *
 * Returns `true` when a flush was attempted (regardless of HTTP result),
 * `false` when there was nothing staged.
 */
export async function flushPendingMarketingConsent(): Promise<boolean> {
  const staged = readStagedSnapshot();
  if (!staged) return false;

  // Always clear the staging slot once we've observed it — leaving it
  // around would cause repeated POSTs on every subsequent page load,
  // which would re-stamp `marketing_consent_at` and corrupt the audit
  // trail. The backend DELETE flow is the only legitimate way to opt
  // back out from here on.
  clearStagedSnapshot();

  if (!staged.marketing) {
    // User explicitly declined — nothing to record. The §50 default-deny
    // posture means "no opt-in" is the correct end state.
    return true;
  }

  try {
    await apiFetch<{ ok: boolean } & MarketingConsentState>(
      API.consents.marketing,
      { method: "POST" },
    );
  } catch (err) {
    // Best-effort flush — if the user is unauthenticated (401), the
    // endpoint is not yet deployed (404), or the network is flaky,
    // we swallow it. The /settings toggle is the recovery surface.
    if (typeof window !== "undefined" && process.env.NODE_ENV !== "production") {
      // Helpful breadcrumb for local dev; never reaches users.
      // eslint-disable-next-line no-console
      console.warn("[consents] flush failed (non-fatal):", err);
    }
  }
  return true;
}

/** GET the authenticated user's current marketing-consent record. */
export async function fetchMarketingConsent(): Promise<MarketingConsentState | null> {
  try {
    const res = await apiFetch<{ ok: boolean } & MarketingConsentState>(
      API.consents.marketing,
    );
    return {
      opted_in: !!res.opted_in,
      marketing_consent_at: res.marketing_consent_at ?? null,
      marketing_consent_revoked_at: res.marketing_consent_revoked_at ?? null,
    };
  } catch (err) {
    // 401 / 404 / network — caller treats null as "no record". 401 in
    // particular is harmless: the auth provider will redirect anyway.
    if (err instanceof ApiError && (err.status === 401 || err.status === 404)) {
      return null;
    }
    return null;
  }
}

/** POST — record an explicit opt-in. Throws on backend failure. */
export async function recordMarketingConsent(): Promise<MarketingConsentState> {
  const res = await apiFetch<{ ok: boolean } & MarketingConsentState>(
    API.consents.marketing,
    { method: "POST" },
  );
  return {
    opted_in: !!res.opted_in,
    marketing_consent_at: res.marketing_consent_at ?? null,
    marketing_consent_revoked_at: res.marketing_consent_revoked_at ?? null,
  };
}

/** DELETE — record a revocation. Throws on backend failure. */
export async function revokeMarketingConsent(): Promise<MarketingConsentState> {
  const res = await apiFetch<{ ok: boolean } & MarketingConsentState>(
    API.consents.marketing,
    { method: "DELETE" },
  );
  return {
    opted_in: !!res.opted_in,
    marketing_consent_at: res.marketing_consent_at ?? null,
    marketing_consent_revoked_at: res.marketing_consent_revoked_at ?? null,
  };
}
