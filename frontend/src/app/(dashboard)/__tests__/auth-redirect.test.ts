import { describe, expect, it } from "vitest";
import { nextAuthRedirect } from "../layout";

/**
 * F#3 (2026-05-26, PIPA §22 ⑥): the (dashboard) auth guard must send an
 * OAuth-provisioned user whose age confirmation is still outstanding to the
 * finalize step BEFORE the onboarding broker step. Priority order:
 *   no user → /login → age confirmation required → /signup/oauth-finalize →
 *   onboarding_completed === false → /onboarding/broker → stay (null).
 *
 * 2026-09-19: the key is ``age_confirmation_required``; the deprecated
 * ``birthdate_required`` is still honoured for one deploy cycle.
 */
describe("nextAuthRedirect", () => {
  it("redirects to /login when there is no user", () => {
    expect(nextAuthRedirect(null)).toBe("/login");
    expect(nextAuthRedirect(undefined)).toBe("/login");
  });

  it("redirects to finalize when age_confirmation_required is true", () => {
    expect(
      nextAuthRedirect({
        age_confirmation_required: true,
        onboarding_completed: true,
      }),
    ).toBe("/signup/oauth-finalize");
  });

  it("still redirects to finalize on the deprecated birthdate_required key", () => {
    // Deploy-window fallback: a backend that has not yet been redeployed
    // emits only the old key. It must gate exactly like the new one.
    expect(
      nextAuthRedirect({ birthdate_required: true, onboarding_completed: true }),
    ).toBe("/signup/oauth-finalize");
  });

  it("prefers the new key over the deprecated one when both are present", () => {
    expect(
      nextAuthRedirect({
        age_confirmation_required: false,
        birthdate_required: true,
        onboarding_completed: true,
      }),
    ).toBeNull();
  });

  it("prioritizes finalize over onboarding when both are pending", () => {
    expect(
      nextAuthRedirect({
        age_confirmation_required: true,
        onboarding_completed: false,
      }),
    ).toBe("/signup/oauth-finalize");
  });

  it("redirects to onboarding broker when only onboarding is incomplete", () => {
    expect(
      nextAuthRedirect({
        age_confirmation_required: false,
        onboarding_completed: false,
      }),
    ).toBe("/onboarding/broker");
  });

  it("does not redirect a fully-provisioned user", () => {
    expect(
      nextAuthRedirect({
        age_confirmation_required: false,
        onboarding_completed: true,
      }),
    ).toBeNull();
  });

  it("treats a missing age_confirmation_required as not-required (legacy users)", () => {
    expect(nextAuthRedirect({ onboarding_completed: true })).toBeNull();
  });
});
