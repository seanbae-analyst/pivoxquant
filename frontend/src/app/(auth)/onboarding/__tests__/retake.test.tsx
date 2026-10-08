/**
 * `/onboarding?retake=1` — an already-onboarded user can answer the five
 * questions again (설정 → "다섯 문항 다시 답하기", 2026-10-08). Without the
 * flag the page still sends a finished user to /mirror.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, screen } from "@testing-library/react";

const replace = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
  useSearchParams: () => new URLSearchParams(search),
}));
vi.mock("@/lib/locale", () => ({ useLocale: () => ({ locale: "ko", t: (k: string) => k }) }));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: 1, onboarding_completed: true }, loading: false, refresh: vi.fn() }),
}));
vi.mock("@/lib/hooks", () => ({
  usePortfolioPositions: () => ({ data: { positions: [{ id: 1 }] } }),
}));
const apiFetch = vi.fn(() => Promise.resolve({ draft: null }));
vi.mock("@/lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetch(...(args as [])),
  ApiError: class extends Error {},
}));

import OnboardingPage from "../page";
import { WIZARD_QUESTIONS } from "@/data/onboarding-questions";

afterEach(() => {
  cleanup();
  replace.mockClear();
  apiFetch.mockClear();
  search = "";
});

describe("onboarding retake", () => {
  it("sends a finished user to /mirror without the flag", () => {
    const { container } = render(<OnboardingPage />);
    expect(replace).toHaveBeenCalledWith("/mirror");
    expect(container.innerHTML).toBe("");
  });

  it("shows the wizard again with ?retake=1 — no skip, no draft read", () => {
    search = "retake=1";
    render(<OnboardingPage />);
    expect(replace).not.toHaveBeenCalledWith("/mirror");
    expect(screen.getByText("그만두기")).toBeTruthy();
    expect(screen.queryByText(/Skip for now/)).toBeNull();
    expect(screen.getAllByText(WIZARD_QUESTIONS[0].question_kr).length).toBeGreaterThan(0);
    expect(apiFetch).not.toHaveBeenCalled();
  });
});
