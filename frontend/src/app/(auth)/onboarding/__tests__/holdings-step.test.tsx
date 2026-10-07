/**
 * Onboarding step 0 — holdings are required (CEO 2026-09-28: "무조건
 * 포트폴리오 작성하고 가게끔"). No skip; "next" unlocks only once at least one
 * position is saved. The server enforces the same rule
 * (ONBOARDING_HOLDINGS_REQUIRED).
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, screen, fireEvent } from "@testing-library/react";

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace }) }));
vi.mock("@/lib/locale", () => ({ useT: () => (k: string) => k }));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: 1, onboarding_completed: false }, loading: false }),
}));
vi.mock("@/components/ui/legal-consent-modal", () => ({
  LegalConsentModal: () => null,
  hasLocalConsent: () => true,
}));
vi.mock("@/components/portfolio/v2/holdings-import-panel", () => ({
  HoldingsImportPanel: () => <div data-testid="holdings-import-panel" />,
}));
vi.mock("@/components/portfolio/v2/add-position-modal-v2", () => ({
  AddPositionModalV2: ({ open }: { open: boolean }) => (open ? <div data-testid="add-modal" /> : null),
}));

let positions: unknown[] = [];
vi.mock("@/lib/hooks", () => ({
  fetcher: vi.fn(),
  useBrokerConnections: () => ({ data: undefined, mutate: vi.fn(), isLoading: false }),
  usePortfolioPositions: () => ({ data: { positions } }),
}));

import OnboardingBrokerPage from "../broker/page";

afterEach(() => {
  cleanup();
  push.mockReset();
});

describe("onboarding step 0 — holdings required", () => {
  it("with an empty book: no skip, next is locked, upload is on the page", () => {
    positions = [];
    render(<OnboardingBrokerPage />);
    expect(screen.queryByText("brokerOnboarding.skip")).toBeNull();
    expect(screen.getByTestId("holdings-import-panel")).toBeTruthy();
    expect(screen.getByText("brokerOnboarding.nextLocked")).toBeTruthy();
    const next = screen.getByTestId("onboarding-next") as HTMLButtonElement;
    expect(next.disabled).toBe(true);
    fireEvent.click(next);
    expect(push).not.toHaveBeenCalled();
  });

  it("one-at-a-time entry opens the add dialog", () => {
    positions = [];
    render(<OnboardingBrokerPage />);
    fireEvent.click(screen.getByTestId("onboarding-manual"));
    expect(screen.getByTestId("add-modal")).toBeTruthy();
  });

  it("with a holding saved: lists it and next goes on to the phone setup step", () => {
    positions = [{ id: 1, ticker: "005930.KS", name: "삼성전자", shares: 15, avg_cost: 272000, currency: "KRW" }];
    render(<OnboardingBrokerPage />);
    expect(screen.getByTestId("onboarding-held").textContent).toContain("삼성전자");
    const next = screen.getByTestId("onboarding-next") as HTMLButtonElement;
    expect(next.disabled).toBe(false);
    fireEvent.click(next);
    expect(push).toHaveBeenCalledWith("/onboarding/fills");
  });
});
