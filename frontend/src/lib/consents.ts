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

export interface CrossBorderConsentState {
  opted_in: boolean;
  cross_border_consent_at: string | null;
  cross_border_consent_revoked_at: string | null;
}

interface SignupConsentSnapshot {
  terms?: boolean;
  non_advisory?: boolean;
  age?: boolean;
  cross_border?: boolean;
  marketing?: boolean;
  consented_at?: string;
}

export function readStagedSnapshot(): SignupConsentSnapshot | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(CONSENT_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as SignupConsentSnapshot;
  } catch {
    return null;
  }
}

export function clearStagedSnapshot() {
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
export async function flushPendingMarketingConsent(
  stagedOverride?: SignupConsentSnapshot | null,
): Promise<boolean> {
  // 2026-05-17 wave F-4 P0 — caller (dashboard layout) now reads the
  // snapshot once and passes it to both marketing + cross-border flushes
  // before clearing, eliminating the race where marketing cleared the
  // localStorage slot synchronously and cross-border then read null.
  // We still accept ``undefined`` for back-compat with any direct caller.
  const staged = stagedOverride !== undefined ? stagedOverride : readStagedSnapshot();
  if (!staged) return false;

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
    // Flush failed — 401 (auth not settled mid-OAuth), 404, or flaky
    // network. Do NOT silently drop a consent the user actively gave at
    // signup: return false so the caller keeps the staged snapshot and
    // retries on the next dashboard mount. (Prior code swallowed this and
    // returned true → the snapshot was cleared and the opt-in was lost,
    // leaving the user with marketing_consent_at NULL → no artifact mail.)
    if (typeof window !== "undefined") {
      console.error("[consents] marketing flush failed — will retry:", err);
    }
    return false;
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


// ── Cross-border data-transfer consent (PIPA §28-8) ──────────────────────
//
// 개인정보보호법 §28-8 (2024-09 시행): 개인정보 국외 이전 시 별도로 알리고
// 명시적 동의를 받아야 함. PivoxQuant 의 국외 위탁처는 미국 법인 7개(Render /
// Supabase(데이터는 서울 리전) / Vercel / SendGrid / Sentry / Google / Stripe)
// + 프랑스 소재 1개(Brevo) = 총 8개이며(2026-09-10 정정: Anthropic·Railway 는
// 은퇴), 전체 목록·국가·이전 항목은 개인정보처리방침 §6 이
// SoT 이다(frontend/src/content/privacy-ko.md, #cross-border 앵커). 이 동의는
// boolean opt-in + 타임스탬프(cross_border_consent_at)만 저장하고 위탁처 목록·
// 동의 문안 버전은 보관하지 않으므로, 라벨에 열거되는 위탁처가 바뀌어도
// 저장 스키마는 변경되지 않는다(방침 §6 이 고지 SoT). 모든 사용자에게 적용된다.

/**
 * Persist the staged cross-border consent (PIPA §28-8) snapshot to the
 * backend after the OAuth round-trip. Mirrors flushPendingMarketingConsent
 * — best-effort, silent failures.
 *
 * Note: do NOT clear the staging snapshot here. flushPendingMarketingConsent
 * already does that on the same key, so we just observe it. Order: marketing
 * flush should run first (it clears), then this cross-border flush sees a
 * snapshot that's already been read once but not yet wiped — which is fine
 * because the MARKETING_CONSENT_KEY clear is idempotent.
 */
export async function flushPendingCrossBorderConsent(
  stagedOverride?: SignupConsentSnapshot | null,
): Promise<boolean> {
  // 2026-05-17 wave F-4 P0 — see flushPendingMarketingConsent for the
  // race fix; this helper now accepts an explicit snapshot so the
  // caller can read the localStorage slot once and feed both flushes
  // before clearing.
  const staged = stagedOverride !== undefined ? stagedOverride : readStagedSnapshot();
  if (!staged) return false;
  if (!staged.cross_border) return true;

  try {
    await apiFetch<{ ok: boolean } & CrossBorderConsentState>(
      API.consents.crossBorder,
      { method: "POST" },
    );
  } catch (err) {
    // Same retry-preserving contract as flushPendingMarketingConsent:
    // a failed flush returns false so the caller keeps the snapshot.
    if (typeof window !== "undefined") {
      console.error("[consents] cross-border flush failed — will retry:", err);
    }
    return false;
  }
  return true;
}

/** GET the authenticated user's current cross-border consent record. */
export async function fetchCrossBorderConsent(): Promise<CrossBorderConsentState | null> {
  try {
    const res = await apiFetch<{ ok: boolean } & CrossBorderConsentState>(
      API.consents.crossBorder,
    );
    return {
      opted_in: !!res.opted_in,
      cross_border_consent_at: res.cross_border_consent_at ?? null,
      cross_border_consent_revoked_at: res.cross_border_consent_revoked_at ?? null,
    };
  } catch (err) {
    if (err instanceof ApiError && (err.status === 401 || err.status === 404)) {
      return null;
    }
    return null;
  }
}

/** POST — record an explicit opt-in. Throws on backend failure. */
export async function recordCrossBorderConsent(): Promise<CrossBorderConsentState> {
  const res = await apiFetch<{ ok: boolean } & CrossBorderConsentState>(
    API.consents.crossBorder,
    { method: "POST" },
  );
  return {
    opted_in: !!res.opted_in,
    cross_border_consent_at: res.cross_border_consent_at ?? null,
    cross_border_consent_revoked_at: res.cross_border_consent_revoked_at ?? null,
  };
}

/** DELETE — record a revocation. Throws on backend failure. */
export async function revokeCrossBorderConsent(): Promise<CrossBorderConsentState> {
  const res = await apiFetch<{ ok: boolean } & CrossBorderConsentState>(
    API.consents.crossBorder,
    { method: "DELETE" },
  );
  return {
    opted_in: !!res.opted_in,
    cross_border_consent_at: res.cross_border_consent_at ?? null,
    cross_border_consent_revoked_at: res.cross_border_consent_revoked_at ?? null,
  };
}
