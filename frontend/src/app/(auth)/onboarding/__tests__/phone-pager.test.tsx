/**
 * /onboarding on a phone (2026-10-09, matching the 멈춤 phone flow): the five
 * questions and the legal step are screens you swipe between.
 *
 * Pinned here:
 *   - a forward swipe pages only from an answered step and never answers;
 *   - the legal step never pages forward by swipe (ticked or not) — only the
 *     Save button submits, so its confirmations cannot be skipped;
 *   - back keeps every answer; there is no back from the first question;
 *   - the POST (first run) / PUT (retake) body from the swiped phone flow is
 *     byte-identical to the md+ button flow for the same answers;
 *   - the result screen does not swipe back into a resubmit;
 *   - mouse drags and md+ viewports never page.
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
const hint = () => screen.queryByTestId("onboarding-swipe-hint")?.textContent ?? null;
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

describe("/onboarding · phone pager", () => {
  it("a forward swipe on an unanswered question is refused and answers nothing", () => {
    stubViewport(true);
    render(<OnboardingPage />);
    expect(progress()).toContain("문항 1 / 5");
    swipe(-FAR);
    expect(heading()).toBe(WIZARD_QUESTIONS[0].question_kr);
    expect(hint()).toContain("답을 하나 고르면");
    expect(nextBtn().disabled).toBe(true);
    expect(screen.getByTestId("onboarding-seg-0").getAttribute("data-state")).toBe("current");

    pick(0);
    expect(hint()).toBeNull();
    swipe(-FAR);
    expect(heading()).toBe(WIZARD_QUESTIONS[1].question_kr);
    expect(progress()).toContain("문항 2 / 5");
    expect(hint()).toBeNull();
  });

  it("swiping back keeps answers; no back from the first question", () => {
    stubViewport(true);
    render(<OnboardingPage />);
    swipe(FAR);
    expect(heading()).toBe(WIZARD_QUESTIONS[0].question_kr);

    pick(0, 1);
    swipe(-FAR);
    pick(1, 2);
    swipe(-FAR);
    swipe(FAR);
    swipe(FAR);
    expect(heading()).toBe(WIZARD_QUESTIONS[0].question_kr);
    expect(screen.getByTestId("onboarding-seg-0").getAttribute("data-state")).toBe("done");
    expect(screen.getByTestId("onboarding-seg-1").getAttribute("data-state")).toBe("done");
    expect(nextBtn().disabled).toBe(false);
    // Forward again over answered screens, no re-answering needed.
    swipe(-FAR);
    swipe(-FAR);
    expect(heading()).toBe(WIZARD_QUESTIONS[2].question_kr);
    expect(progress()).toContain("답 2 / 5");
  });

  it("the legal step never pages forward by swipe — only Save submits", async () => {
    stubViewport(true);
    render(<OnboardingPage />);
    swipeThroughQuestions();
    expect(progress()).toContain("마지막 확인");

    swipe(-FAR);
    expect(hint()).toContain("모든 항목을 확인해야");
    expect(saves()).toHaveLength(0);

    // Every box but one: still refused.
    for (const o of LEGAL_QUESTION.options.slice(1)) {
      tap(screen.getByText(String(o.label_kr)));
    }
    swipe(-FAR);
    expect(saves()).toHaveLength(0);
    expect(nextBtn().disabled).toBe(true);

    tap(screen.getByText(String(LEGAL_QUESTION.options[0].label_kr)));
    swipe(-FAR);
    expect(hint()).toContain("저장 버튼을 눌러야");
    expect(saves()).toHaveLength(0);

    tap(nextBtn());
    await waitFor(() => expect(saves()).toHaveLength(1));
    expect(await screen.findByText("오늘 이렇게 말씀하셨습니다.")).toBeTruthy();
  });

  it("the result screen does not swipe back into a resubmit", async () => {
    stubViewport(true);
    render(<OnboardingPage />);
    swipeThroughQuestions();
    tickAllLegal();
    tap(nextBtn());
    await screen.findByText("오늘 이렇게 말씀하셨습니다.");
    expect(screen.queryByTestId("onboarding-pane")).toBeNull();

    const surface = screen.getByText("오늘 이렇게 말씀하셨습니다.");
    const base = { pointerId: 3, pointerType: "touch", clientX: 100, clientY: 300 };
    fireEvent.pointerDown(surface, base);
    fireEvent.pointerUp(surface, { ...base, clientX: 100 + FAR });
    fireEvent.keyDown(document.body, { key: "ArrowLeft" });
    expect(screen.getByText("오늘 이렇게 말씀하셨습니다.")).toBeTruthy();
    expect(saves()).toHaveLength(1);
  });

  it("first-run POST body from the swiped phone flow equals the md+ button flow", async () => {
    // md+: buttons only, as before.
    stubViewport(false);
    render(<OnboardingPage />);
    // md+ keeps the AnimatePresence exit, so each screen arrives async.
    for (const q of WIZARD_QUESTIONS) {
      fireEvent.click(await screen.findByText(String(q.options[1].label_kr)));
      fireEvent.click(screen.getByText("Next"));
    }
    for (const o of LEGAL_QUESTION.options) {
      fireEvent.click(await screen.findByText(String(o.label_kr)));
    }
    fireEvent.click(screen.getByText("Save"));
    await waitFor(() => expect(saves()).toHaveLength(1));
    const desktop = saves()[0];
    cleanup();
    apiFetch.mockClear();
    localStorage.clear();

    stubViewport(true);
    render(<OnboardingPage />);
    swipeThroughQuestions(1);
    tickAllLegal();
    tap(nextBtn());
    await waitFor(() => expect(saves()).toHaveLength(1));
    const phone = saves()[0];

    expect(phone).toEqual(desktop);
    expect(phone.url).toBe(API.profile.onboarding);
    expect(phone.method).toBe("POST");
    expect(JSON.stringify(phone.body)).toBe(JSON.stringify(desktop.body));
  });

  it("retake on a phone saves with PUT /profile and the same body shape", async () => {
    search = "retake=1";
    authUser = { id: 1, onboarding_completed: true, effective_tier: "free", profile_changes_left: 2 };
    stubViewport(true);
    render(<OnboardingPage />);
    swipeThroughQuestions();
    tickAllLegal();
    tap(nextBtn());
    await waitFor(() => expect(saves()).toHaveLength(1));
    const [save] = saves();
    expect(save.url).toBe(API.profile.update);
    expect(save.method).toBe("PUT");
    const body = save.body as { answers: Record<string, unknown> };
    for (const q of WIZARD_QUESTIONS) {
      expect(body.answers[q.id]).toBe(String(q.options[0].value));
    }
    expect(body.answers.legal_confirmations).toEqual(
      LEGAL_QUESTION.options.map((o) => String(o.value)),
    );
    expect(Object.keys(body.answers).sort()).toEqual(
      [...WIZARD_QUESTIONS.map((q) => q.id), "legal_confirmations"].sort(),
    );
  });

  it("mouse drags and md+ viewports never page", () => {
    stubViewport(true);
    render(<OnboardingPage />);
    pick(0);
    swipe(-FAR, "mouse");
    expect(heading()).toBe(WIZARD_QUESTIONS[0].question_kr);
    cleanup();

    stubViewport(false);
    render(<OnboardingPage />);
    pick(0);
    swipe(-FAR);
    expect(screen.getAllByText(WIZARD_QUESTIONS[0].question_kr).length).toBeGreaterThan(0);
    expect(screen.queryByText(WIZARD_QUESTIONS[1].question_kr)).toBeNull();
    // The md+ step counter moves synchronously with the step — still 1.
    expect(screen.getByText("1 of 6")).toBeTruthy();
  });
});
