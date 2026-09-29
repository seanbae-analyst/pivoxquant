/**
 * Onboarding step 0 — the legal consent modal is shown only to users the
 * SERVER has no consent for (2026-09-29).
 *
 * Before: the page asked `hasLocalConsent()` (localStorage
 * `pivox_signup_consents`). `/signup/oauth-finalize` records the consents
 * server-side and then clears that key, so every new OAuth user was asked
 * for the same four consents a second time right here — and the modal's
 * snapshot was then re-POSTed by the (dashboard) flush, moving the
 * cross-border timestamp. The server (`/api/auth/me`) is now the SoT.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));
vi.mock("@/lib/locale", () => ({ useT: () => (k: string) => k }));

let authUser: Record<string, unknown> | null = null;
let authLoading = false;
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: authUser, loading: authLoading }),
}));

let localConsent = false;
vi.mock("@/components/ui/legal-consent-modal", () => ({
  LegalConsentModal: () => <div data-testid="legal-consent-modal" />,
  hasLocalConsent: () => localConsent,
}));
vi.mock("@/components/portfolio/v2/holdings-import-panel", () => ({
  HoldingsImportPanel: () => null,
}));
vi.mock("@/components/portfolio/v2/add-position-modal-v2", () => ({
  AddPositionModalV2: () => null,
}));
vi.mock("@/lib/hooks", () => ({
  fetcher: vi.fn(),
  useBrokerConnections: () => ({ data: undefined, mutate: vi.fn(), isLoading: false }),
  usePortfolioPositions: () => ({ data: { positions: [] } }),
}));

import OnboardingBrokerPage from "../broker/page";

afterEach(() => {
  cleanup();
  authUser = null;
  authLoading = false;
  localConsent = false;
});

describe("onboarding step 0 — legal consent gate reads the server", () => {
  it("does not re-ask a user whose consent oauth-finalize already recorded", () => {
    // Exactly the post-finalize state: snapshot cleared, server has it.
    authUser = {
      id: 1,
      onboarding_completed: false,
      age_confirmation_required: false,
      cross_border_consent_recorded: true,
    };
    localConsent = false;
    render(<OnboardingBrokerPage />);
    expect(screen.queryByTestId("legal-consent-modal")).toBeNull();
  });

  it("still asks a legacy user the server has no cross-border record for", () => {
    authUser = {
      id: 2,
      onboarding_completed: false,
      age_confirmation_required: false,
      cross_border_consent_recorded: false,
    };
    localConsent = false;
    render(<OnboardingBrokerPage />);
    expect(screen.getByTestId("legal-consent-modal")).toBeTruthy();
  });

  it("does not show the modal before auth has resolved", () => {
    authLoading = true;
    authUser = null;
    render(<OnboardingBrokerPage />);
    expect(screen.queryByTestId("legal-consent-modal")).toBeNull();
  });

  it("a legacy user who already ticked the modal on this device is not re-asked", () => {
    authUser = {
      id: 3,
      onboarding_completed: false,
      age_confirmation_required: false,
      cross_border_consent_recorded: false,
    };
    localConsent = true;
    render(<OnboardingBrokerPage />);
    expect(screen.queryByTestId("legal-consent-modal")).toBeNull();
  });
});
