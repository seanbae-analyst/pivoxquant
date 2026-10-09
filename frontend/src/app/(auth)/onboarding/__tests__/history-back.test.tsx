/**
 * /onboarding on a phone — the system back gesture (Android back, iOS edge
 * swipe → popstate) steps back through the questions instead of leaving
 * onboarding (lib/use-history-steps, 2026-10-09).
 *
 * Pinned here:
 *   - back walks to the previous question and keeps the answers;
 *   - system forward re-enters only reached, answered steps (and never the
 *     result screen — that is Save's alone);
 *   - after Save, back does not reopen the legal step (no second save);
 *   - md+ pushes no history entries.
 */
import { describe, it, expect, vi, afterEach, beforeAll } from "vitest";
import { render, cleanup, screen, fireEvent, act } from "@testing-library/react";

const replace = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
  useSearchParams: () => new URLSearchParams(search),
}));
vi.mock("@/lib/locale", () => ({ useLocale: () => ({ locale: "ko", t: (k: string) => k }) }));
let authUser: Record<string, unknown> = { id: 1, onboarding_completed: false };
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: authUser, loading: false, refresh: vi.fn() }),
}));
vi.mock("swr", async (orig) => ({
  ...(await orig<typeof import("swr")>()),
  mutate: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("@/lib/hooks", () => ({
  usePortfolioPositions: () => ({ data: { positions: [{ id: 1 }] } }),
}));
const apiFetch = vi.fn((url: string, init?: RequestInit): Promise<unknown> => {
  void url;
  if (init?.method === "POST" || init?.method === "PUT") {
    return Promise.resolve({ ok: true, declared: [] });
  }
  return Promise.resolve({ draft: null });
});
vi.mock("@/lib/api", () => ({
  apiFetch: (...args: unknown[]) => apiFetch(...(args as [string, RequestInit?])),
  ApiError: class extends Error {
    code?: string;
  },
}));

import OnboardingPage from "../page";
import { WIZARD_QUESTIONS, LEGAL_QUESTION } from "@/data/onboarding-questions";
import { API } from "@/lib/endpoints";
import { SWIPE_MIN_PX } from "@/lib/use-swipe-pager";
import { onboardingStepReachable } from "@/components/onboarding/onboarding-phone";

const FAR = SWIPE_MIN_PX + 24;
const originalMatchMedia = window.matchMedia;

beforeAll(() => {
  if (!HTMLElement.prototype.scrollTo) HTMLElement.prototype.scrollTo = () => {};
  // useSlideIn scrolls the window to the top of a fresh screen.
  window.scrollTo = (() => {}) as typeof window.scrollTo;
});

function stubViewport(phone: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes("max-width") ? phone : query.includes("reduced-motion"),
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

function swipe(dx: number, pointerType = "touch") {
  // Start on the step's heading — inside the pane, not a field.
  const el = screen.getByTestId("onboarding-screen").querySelector("h2") ?? screen.getByTestId("onboarding-pane");
  const base = { pointerId: 1, pointerType, clientX: 200, clientY: 300 };
  fireEvent.pointerDown(el, base);
  fireEvent.pointerUp(el, { ...base, clientX: 200 + dx });
}

const progress = () => screen.getByTestId("onboarding-phone-progress").textContent ?? "";
const heading = () => screen.getByTestId("onboarding-screen").querySelector("h2")?.textContent ?? "";
const nextBtn = () => screen.getByTestId("onboarding-next") as HTMLButtonElement;
/** A real tap: pointerdown/up in place, then the click (a new gesture). */
function tap(el: Element) {
  const base = { pointerId: 2, pointerType: "touch", clientX: 10, clientY: 10 };
  fireEvent.pointerDown(el, base);
  fireEvent.pointerUp(el, base);
  fireEvent.click(el);
}
const pick = (qi: number, oi = 0) =>
  tap(screen.getByText(String(WIZARD_QUESTIONS[qi].options[oi].label_kr)));
const tickAllLegal = () => {
  for (const o of LEGAL_QUESTION.options) tap(screen.getByText(String(o.label_kr)));
};

/** Bodies of every save (POST /onboarding or PUT /profile) so far. */
function saves(): { url: string; method: string; body: unknown }[] {
  return apiFetch.mock.calls
    .filter(([, init]) => init?.method === "POST" || init?.method === "PUT")
    .filter(([url]) => url === API.profile.onboarding || url === API.profile.update)
    .map(([url, init]) => ({
      url,
      method: String(init?.method),
      body: JSON.parse(String(init?.body)),
    }));
}

/** Phone: answer every question (option `oi`) and page with swipes only. */
function swipeThroughQuestions(oi = 0) {
  WIZARD_QUESTIONS.forEach((_, qi) => {
    pick(qi, oi);
    swipe(-FAR);
  });
}

afterEach(() => {
  cleanup();
  window.matchMedia = originalMatchMedia;
  replace.mockClear();
  apiFetch.mockClear();
  search = "";
  authUser = { id: 1, onboarding_completed: false };
  localStorage.clear();
});

async function popstateSettle() {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 30));
  });
}
async function systemBack() {
  await act(async () => {
    window.history.back();
  });
  await popstateSettle();
}
async function systemForward() {
  await act(async () => {
    window.history.forward();
  });
  await popstateSettle();
  await popstateSettle();
}

describe("/onboarding · system back (phone)", () => {
  it("back steps to the previous question and keeps the answer", async () => {
    window.history.replaceState({ __NA: true }, "", "/onboarding");
    stubViewport(true);
    render(<OnboardingPage />);
    pick(0);
    tap(nextBtn());
    pick(1);
    tap(nextBtn());
    expect(progress()).toContain("문항 3 / 5");

    await systemBack();
    expect(progress()).toContain("문항 2 / 5");
    await systemBack();
    expect(progress()).toContain("문항 1 / 5");
    expect(heading()).toBe(WIZARD_QUESTIONS[0].question_kr);
    // The answer survived the trip: Next is enabled on question 1.
    expect(nextBtn().disabled).toBe(false);
    expect(saves()).toHaveLength(0);
  });

  it("system forward returns to a step already reached and answered", async () => {
    window.history.replaceState({ __NA: true }, "", "/onboarding");
    stubViewport(true);
    render(<OnboardingPage />);
    pick(0, 0);
    tap(nextBtn());
    expect(progress()).toContain("문항 2 / 5");
    await systemBack();
    expect(progress()).toContain("문항 1 / 5");
    await systemForward();
    expect(progress()).toContain("문항 2 / 5");
    expect(saves()).toHaveLength(0);
  });

  it("the forward gate: every earlier step answered, never past the legal step", () => {
    const answered = [true, true, false, false, false, false];
    expect(onboardingStepReachable(1, answered)).toBe(true);
    expect(onboardingStepReachable(2, answered)).toBe(true);
    expect(onboardingStepReachable(3, answered)).toBe(false);
    expect(onboardingStepReachable(6, Array(6).fill(true))).toBe(false); // result: Save only
  });

  it("after Save, back does not reopen the legal step", async () => {
    window.history.replaceState({ __NA: true }, "", "/onboarding");
    stubViewport(true);
    render(<OnboardingPage />);
    swipeThroughQuestions();
    tickAllLegal();
    tap(nextBtn());
    await screen.findByText("오늘 이렇게 말씀하셨습니다.");
    await popstateSettle();
    const state = window.history.state as { __pqStep?: { idx: number } };
    expect(state.__pqStep?.idx).toBe(0);
    expect(screen.queryByTestId("onboarding-pane")).toBeNull();
    expect(saves()).toHaveLength(1);
  });

  it("md+ pushes no step entries", () => {
    window.history.replaceState({ __NA: true }, "", "/onboarding");
    stubViewport(false);
    const before = window.history.length;
    render(<OnboardingPage />);
    pick(0);
    tap(nextBtn());
    expect(window.history.length).toBe(before);
  });
});
