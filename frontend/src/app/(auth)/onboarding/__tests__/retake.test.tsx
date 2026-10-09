/**
 * `/onboarding?retake=1` — an already-onboarded user can answer the five
 * questions again (설정 → "다섯 문항 다시 답하기", 2026-10-08). Without the
 * flag the page still sends a finished user to /mirror.
 */
import { describe, it, expect, vi, afterEach, beforeAll } from "vitest";
import { render, cleanup, screen, fireEvent, waitFor } from "@testing-library/react";

const replace = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
  useSearchParams: () => new URLSearchParams(search),
}));
vi.mock("@/lib/locale", () => ({ useLocale: () => ({ locale: "ko", t: (k: string) => k }) }));
let authUser: Record<string, unknown> = { id: 1, onboarding_completed: true };
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: authUser, loading: false, refresh: vi.fn() }),
}));
const swrMutate = vi.fn();
vi.mock("swr", async (orig) => ({
  ...(await orig<typeof import("swr")>()),
  mutate: (...args: unknown[]) => swrMutate(...args),
}));
const toastError = vi.fn();
vi.mock("sonner", () => ({ toast: { error: (...a: unknown[]) => toastError(...a), success: vi.fn() } }));
vi.mock("@/lib/hooks", () => ({
  usePortfolioPositions: () => ({ data: { positions: [{ id: 1 }] } }),
}));
const apiFetch = vi.fn((): Promise<unknown> => Promise.resolve({ draft: null }));
vi.mock("@/lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetch(...(args as [])),
  ApiError: class extends Error {
    code?: string;
    constructor(status: number, message: string, code?: string) {
      super(message);
      this.code = code;
    }
  },
}));

import OnboardingPage from "../page";
import { WIZARD_QUESTIONS, LEGAL_QUESTION } from "@/data/onboarding-questions";
import { ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";

// jsdom has no Element.scrollTo; the wizard scrolls its pane on each step.
beforeAll(() => {
  if (!HTMLElement.prototype.scrollTo) HTMLElement.prototype.scrollTo = () => {};
});

/** Answer the five questions and tick every legal box, then press Save. */
async function answerAllAndSave() {
  for (const q of WIZARD_QUESTIONS) {
    fireEvent.click(await screen.findByText(String(q.options[0].label_kr)));
    fireEvent.click(screen.getByText("Next"));
  }
  for (const o of LEGAL_QUESTION.options) {
    fireEvent.click(await screen.findByText(String(o.label_kr)));
  }
  fireEvent.click(screen.getByText("Save"));
}

afterEach(() => {
  cleanup();
  replace.mockClear();
  apiFetch.mockReset();
  apiFetch.mockImplementation(() => Promise.resolve({ draft: null }));
  swrMutate.mockClear();
  toastError.mockClear();
  search = "";
  authUser = { id: 1, onboarding_completed: true };
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
    expect(screen.getByText("settingsV2.retake.quit")).toBeTruthy();
    expect(screen.queryByText(/Skip for now/)).toBeNull();
    expect(screen.getAllByText(WIZARD_QUESTIONS[0].question_kr).length).toBeGreaterThan(0);
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("with no changes left, says so up front instead of the wizard", () => {
    search = "retake=1";
    authUser = { id: 1, onboarding_completed: true, effective_tier: "free", profile_changes_left: 0 };
    render(<OnboardingPage />);
    expect(screen.getByTestId("retake-limit").textContent).toContain("settingsV2.retake.limitReached");
    expect(screen.queryByText(WIZARD_QUESTIONS[0].question_kr)).toBeNull();
    fireEvent.click(screen.getByText("settingsV2.retake.backToSettings"));
    expect(replace).toHaveBeenCalledWith("/settings");
  });

  it("does not block a non-free tier whose stored count is 0", () => {
    search = "retake=1";
    authUser = { id: 1, onboarding_completed: true, effective_tier: "pro", profile_changes_left: 0 };
    render(<OnboardingPage />);
    expect(screen.queryByTestId("retake-limit")).toBeNull();
    expect(screen.getAllByText(WIZARD_QUESTIONS[0].question_kr).length).toBeGreaterThan(0);
  });

  it("a saved retake drops the cached mirror home read", async () => {
    search = "retake=1";
    authUser = { id: 1, onboarding_completed: true, effective_tier: "free", profile_changes_left: 2 };
    apiFetch.mockImplementation(() => Promise.resolve({ ok: true, declared: [] }));
    render(<OnboardingPage />);
    await answerAllAndSave();
    await waitFor(() => expect(swrMutate).toHaveBeenCalledWith(API.mirror.home));
    const [url, init] = apiFetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(API.profile.update);
    expect(init.method).toBe("PUT");
  });

  it("PROFILE_NOT_FOUND does not ask the user to retry", async () => {
    search = "retake=1";
    apiFetch.mockImplementation(() =>
      Promise.reject(new (ApiError as unknown as new (s: number, m: string, c?: string) => Error)(404, "x", "PROFILE_NOT_FOUND")),
    );
    render(<OnboardingPage />);
    await answerAllAndSave();
    await waitFor(() => expect(toastError).toHaveBeenCalledWith("settingsV2.retake.notFound"));
    expect(swrMutate).not.toHaveBeenCalled();
  });
});
