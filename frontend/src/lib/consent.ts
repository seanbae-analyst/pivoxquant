/**
 * Cookie consent state.
 *
 * Stored in localStorage so it persists across reloads. Read this BEFORE
 * initializing any analytics SDK (Sentry, GA4, PostHog, etc.).
 *
 * Storage keys:
 *   - cookie_consent: "accepted" | "essential" | "rejected" (presence = decided)
 *   - consent_analytics: "true" | "false"
 */

export type ConsentChoice = "accepted" | "essential" | "rejected";

const KEY_DECISION = "cookie_consent";
const KEY_ANALYTICS = "consent_analytics";

export function getConsentChoice(): ConsentChoice | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(KEY_DECISION);
  if (raw === "accepted" || raw === "essential" || raw === "rejected") return raw;
  return null;
}

export function hasMadeConsentChoice(): boolean {
  return getConsentChoice() !== null;
}

/**
 * Whether the user has consented to analytics/telemetry. Defaults to false
 * (privacy-preserving) when no choice has been made yet.
 *
 * Call this guard before initializing Sentry, GA4, PostHog, etc.
 */
export function hasAnalyticsConsent(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(KEY_ANALYTICS) === "true";
}

export function setConsent(choice: ConsentChoice): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY_DECISION, choice);
  window.localStorage.setItem(
    KEY_ANALYTICS,
    choice === "accepted" ? "true" : "false",
  );
  // Notify same-tab listeners; storage events only fire cross-tab.
  window.dispatchEvent(new CustomEvent("consent:change", { detail: { choice } }));
}

export function clearConsent(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(KEY_DECISION);
  window.localStorage.removeItem(KEY_ANALYTICS);
  window.dispatchEvent(new CustomEvent("consent:change", { detail: { choice: null } }));
}
