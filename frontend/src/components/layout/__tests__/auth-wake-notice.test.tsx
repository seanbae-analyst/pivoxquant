/**
 * (dashboard) shell on an UNKNOWN auth state (2026-10-09): hold the skeleton
 * with a waking line — never redirect a possibly signed-in user to /login
 * because the backend is still booting. Past the deadline: error + retry.
 */
import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ko from "@/messages/ko.json";

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/mirror",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/components/layout/dashboard-layout", () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock("@/lib/use-keyboard-nav", () => ({ useKeyboardNav: () => {} }));

const retryAuth = vi.fn();
const auth = { user: null as unknown, loading: false, waking: true, wakeFailed: false, retryAuth };
vi.mock("@/lib/auth", () => ({
  useAuth: () => auth,
  ageConfirmationRequired: () => false,
}));

import DashboardGroupLayout from "@/app/(dashboard)/layout";
import { LocaleProvider } from "@/lib/locale";

const renderLayout = () =>
  render(
    <LocaleProvider>
      <DashboardGroupLayout>
        <div data-testid="page">page</div>
      </DashboardGroupLayout>
    </LocaleProvider>,
  );

beforeEach(() => {
  replaceMock.mockReset();
  retryAuth.mockReset();
  Object.assign(auth, { user: null, loading: false, waking: true, wakeFailed: false });
});

describe("(dashboard) layout while auth is unknown", () => {
  it("holds with the waking line and does not redirect to /login", () => {
    renderLayout();
    expect(screen.getByTestId("auth-wake-notice").textContent).toContain(ko.auth.login.waking);
    expect(screen.queryByTestId("page")).toBeNull();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("past the deadline shows the failure and a retry that re-runs auth", () => {
    auth.wakeFailed = true;
    renderLayout();
    expect(screen.getByRole("alert").textContent).toContain(ko.auth.login.wakeFailed);
    fireEvent.click(screen.getByText(ko.auth.login.wakeRetry));
    expect(retryAuth).toHaveBeenCalledTimes(1);
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("a known signed-out state still redirects to /login", () => {
    Object.assign(auth, { waking: false });
    renderLayout();
    expect(replaceMock).toHaveBeenCalledWith(expect.stringMatching(/^\/login/));
    expect(screen.queryByTestId("auth-wake-notice")).toBeNull();
  });
});
