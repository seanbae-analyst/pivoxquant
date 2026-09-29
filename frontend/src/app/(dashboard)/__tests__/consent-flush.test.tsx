/**
 * (dashboard) layout — staged consent flush must not re-POST a cross-border
 * consent the server already recorded (2026-09-29).
 *
 * `/signup/oauth-finalize` stamps `cross_border_consent_at` in its own
 * transaction. A leftover `pivox_signup_consents` snapshot (e.g. written by
 * the onboarding modal) used to be re-POSTed to /api/consents/cross-border on
 * the next dashboard mount, moving that timestamp off the real consent moment.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, cleanup, waitFor } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/mirror",
}));

let authUser: Record<string, unknown> | null = null;
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: authUser, loading: false }),
  ageConfirmationRequired: (u: { age_confirmation_required?: boolean } | null) =>
    Boolean(u?.age_confirmation_required),
}));
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
  ApiError: class ApiError extends Error {},
}));
vi.mock("@/components/layout/dashboard-layout", () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock("@/components/ui/loading-skeleton", () => ({ DashboardSkeleton: () => null }));
vi.mock("@/components/pwa/push-permission", () => ({ PushPermission: () => null }));
vi.mock("@/components/ui/disclaimer-banner", () => ({ DisclaimerBanner: () => null }));
vi.mock("@/components/ui/realtime-status-banner", () => ({ RealtimeStatusBanner: () => null }));
vi.mock("@/components/ui/data-stale-banner", () => ({ DataStaleBanner: () => null }));
vi.mock("@/lib/use-keyboard-nav", () => ({ useKeyboardNav: () => {} }));

import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { CONSENT_STORAGE_KEY } from "@/lib/consents";
import Layout from "../layout";

const mockedFetch = vi.mocked(apiFetch);

function stage() {
  window.localStorage.setItem(
    CONSENT_STORAGE_KEY,
    JSON.stringify({
      terms: true,
      non_advisory: true,
      age: true,
      cross_border: true,
      marketing: false,
    }),
  );
}

beforeEach(() => {
  mockedFetch.mockReset();
  mockedFetch.mockResolvedValue({ ok: true } as never);
  window.localStorage.clear();
});
afterEach(() => {
  cleanup();
  authUser = null;
});

describe("(dashboard) layout consent flush", () => {
  it("does not re-POST cross-border when the server already has it, and clears the snapshot", async () => {
    authUser = {
      id: 1,
      onboarding_completed: true,
      age_confirmation_required: false,
      cross_border_consent_recorded: true,
    };
    stage();
    render(<Layout><div /></Layout>);

    await waitFor(() =>
      expect(window.localStorage.getItem(CONSENT_STORAGE_KEY)).toBeNull(),
    );
    expect(mockedFetch).not.toHaveBeenCalledWith(
      API.consents.crossBorder,
      expect.anything(),
    );
  });

  it("still promotes the snapshot for a legacy user with no server record", async () => {
    authUser = {
      id: 2,
      onboarding_completed: true,
      age_confirmation_required: false,
      cross_border_consent_recorded: false,
    };
    stage();
    render(<Layout><div /></Layout>);

    await waitFor(() =>
      expect(mockedFetch).toHaveBeenCalledWith(API.consents.crossBorder, {
        method: "POST",
      }),
    );
  });
});
