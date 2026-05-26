import { describe, expect, it } from "vitest";
import { nextAuthRedirect } from "../layout";

/**
 * F#3 (2026-05-26, PIPA §22): the (dashboard) auth guard must send an
 * OAuth-provisioned user whose birthdate is still outstanding to the
 * finalize step BEFORE the onboarding broker step. Priority order:
 *   no user → /login → birthdate_required → /signup/oauth-finalize →
 *   onboarding_completed === false → /onboarding/broker → stay (null).
 */
describe("nextAuthRedirect", () => {
  it("redirects to /login when there is no user", () => {
    expect(nextAuthRedirect(null)).toBe("/login");
    expect(nextAuthRedirect(undefined)).toBe("/login");
  });

  it("redirects to finalize when birthdate_required is true", () => {
    expect(
      nextAuthRedirect({ birthdate_required: true, onboarding_completed: true }),
    ).toBe("/signup/oauth-finalize");
  });

  it("prioritizes finalize over onboarding when both are pending", () => {
    expect(
      nextAuthRedirect({
        birthdate_required: true,
        onboarding_completed: false,
      }),
    ).toBe("/signup/oauth-finalize");
  });

  it("redirects to onboarding broker when only onboarding is incomplete", () => {
    expect(
      nextAuthRedirect({
        birthdate_required: false,
        onboarding_completed: false,
      }),
    ).toBe("/onboarding/broker");
  });

  it("does not redirect a fully-provisioned user", () => {
    expect(
      nextAuthRedirect({
        birthdate_required: false,
        onboarding_completed: true,
      }),
    ).toBeNull();
  });

  it("treats a missing birthdate_required as not-required (legacy users)", () => {
    expect(nextAuthRedirect({ onboarding_completed: true })).toBeNull();
  });
});
