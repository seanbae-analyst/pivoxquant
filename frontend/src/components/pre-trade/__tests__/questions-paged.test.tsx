/**
 * QuestionsStep `pagedOnPhone` — one question per screen on a phone
 * (2026-10-07), swipe + slide + last review screen (2026-10-09, CEO "화면
 * 넘기는 식으로 앱처럼").
 *
 * Pinned here:
 *   - "검토했음 · 다음" ticks the current question and moves on (unchanged).
 *   - A swipe NEVER ticks: forward only from an already-ticked question,
 *     otherwise it is refused with a hint. Back always works; from the first
 *     question it returns to setup.
 *   - After question 7 comes a review screen; only its button starts.
 *   - Answers and ticks survive paging back and forth.
 *   - Mouse drags, gestures that start in a field, and md+ viewports never page.
 *   - Without the prop (the modals) nothing changes.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { useState } from "react";

vi.mock("@/lib/api", () => {
  class ApiError extends Error {}
  return { apiFetch: vi.fn(), ApiError };
});
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { QuestionsStep } from "@/components/pre-trade/pre-trade-friction-core";
import { SWIPE_MIN_PX } from "@/lib/use-swipe-pager";

function Host({
  paged,
  onBack,
  onStart = () => {},
  submitting = false,
}: {
  paged: boolean;
  onBack?: () => void;
  onStart?: () => void;
  submitting?: boolean;
}) {
  const [acks, setAcks] = useState<Record<number, boolean>>({});
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const allAcked = [1, 2, 3, 4, 5, 6, 7].every((n) => acks[n]);
  return (
    <QuestionsStep
      acks={acks} setAcks={setAcks}
      answers={answers} setAnswers={setAnswers}
      allAcked={allAcked} submitting={submitting}
      onBack={onBack} onStart={onStart}
      pagedOnPhone={paged}
    />
  );
}

const hiddenOnPhone = (el: HTMLElement) => el.className.includes("hidden md:block");
const progress = () => screen.getByTestId("questions-progress").textContent ?? "";
const box = (n: number) =>
  screen.getByTestId(`question-${n}`).querySelector('input[type="checkbox"]') as HTMLInputElement;
const answerInput = (n: number) =>
  screen.getByTestId(`question-${n}`).querySelector('input:not([type="checkbox"])') as HTMLInputElement;
/** The question's own text — a swipe surface that is not a field. */
const questionText = (n: number) =>
  screen.getByTestId(`question-${n}`).querySelector("p") as HTMLElement;

/** Width below md decides "phone"; reduced motion keeps jsdom off the animator. */
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

function swipe(
  el: Element,
  dx: number,
  { pointerType = "touch", dy = 0 }: { pointerType?: string; dy?: number } = {},
) {
  const base = { pointerId: 1, pointerType, clientX: 200, clientY: 300 };
  fireEvent.pointerDown(el, base);
  fireEvent.pointerMove(el, { ...base, clientX: 200 + dx / 2 });
  fireEvent.pointerUp(el, { ...base, clientX: 200 + dx, clientY: 300 + dy });
}
const FAR = SWIPE_MIN_PX + 24;

/** A real finger tap: pointer down/up, then the click. */
function tap(el: Element) {
  const base = { pointerId: 2, pointerType: "touch", clientX: 10, clientY: 10 };
  fireEvent.pointerDown(el, base);
  fireEvent.pointerUp(el, base);
  fireEvent.click(el);
}

const originalMatchMedia = window.matchMedia;
beforeEach(() => stubViewport(false));
afterEach(() => {
  cleanup();
  window.matchMedia = originalMatchMedia;
});

describe("QuestionsStep · pagedOnPhone · buttons", () => {
  it("shows one question at a time; next ticks it and advances", () => {
    render(<Host paged />);
    expect(hiddenOnPhone(screen.getByTestId("question-1"))).toBe(false);
    expect(hiddenOnPhone(screen.getByTestId("question-2"))).toBe(true);
    expect(progress()).toContain("질문 1 / 7");

    fireEvent.click(screen.getByTestId("questions-next"));
    expect(hiddenOnPhone(screen.getByTestId("question-1"))).toBe(true);
    expect(hiddenOnPhone(screen.getByTestId("question-2"))).toBe(false);
    expect(box(1).checked).toBe(true);
    expect(progress()).toContain("검토 1 / 7");
    expect(screen.getByTestId("progress-seg-1").dataset.state).toBe("acked");
    expect(screen.getByTestId("progress-seg-2").dataset.state).toBe("current");
  });

  it("after question 7 comes the review screen, whose button starts", () => {
    const onStart = vi.fn();
    render(<Host paged onStart={onStart} />);
    for (let i = 0; i < 6; i++) fireEvent.click(screen.getByTestId("questions-next"));
    expect(progress()).toContain("질문 7 / 7");
    expect(screen.queryByTestId("questions-review")).toBeNull();
    expect(screen.queryByTestId("questions-start-phone")).toBeNull();

    fireEvent.click(screen.getByTestId("questions-next"));
    expect(progress()).toContain("마지막 확인");
    expect(screen.getByTestId("questions-review")).toBeTruthy();
    for (let n = 1; n <= 7; n++) expect(hiddenOnPhone(screen.getByTestId(`question-${n}`))).toBe(true);
    expect(screen.queryByTestId("questions-next")).toBeNull();

    const start = screen.getByTestId("questions-start-phone") as HTMLButtonElement;
    expect(start.disabled).toBe(false);
    fireEvent.click(start);
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("the start button is disabled while submitting (double-submit guard)", () => {
    const onStart = vi.fn();
    const { rerender } = render(<Host paged onStart={onStart} />);
    for (let i = 0; i < 7; i++) fireEvent.click(screen.getByTestId("questions-next"));
    rerender(<Host paged onStart={onStart} submitting />);
    const start = screen.getByTestId("questions-start-phone") as HTMLButtonElement;
    expect(start.disabled).toBe(true);
    expect(start.textContent).toContain("시작하는 중");
    fireEvent.click(start);
    expect(onStart).not.toHaveBeenCalled();
  });

  it("the review screen shows each answer and jumps back to a question", () => {
    render(<Host paged />);
    fireEvent.change(answerInput(1), { target: { value: "손절가 -8%" } });
    for (let i = 0; i < 7; i++) fireEvent.click(screen.getByTestId("questions-next"));
    expect(screen.getByTestId("review-jump-1").textContent).toContain("손절가 -8%");
    expect(screen.getByTestId("review-jump-2").textContent).toContain("답 없이 검토함");

    fireEvent.click(screen.getByTestId("review-jump-3"));
    expect(progress()).toContain("질문 3 / 7");
    expect(hiddenOnPhone(screen.getByTestId("question-3"))).toBe(false);
  });

  it("previous on the first question goes back to setup", () => {
    const onBack = vi.fn();
    render(<Host paged onBack={onBack} />);
    fireEvent.click(screen.getByTestId("questions-prev"));
    expect(onBack).toHaveBeenCalled();
  });

  it("a phone has one back control (the action bar's), stepping one screen", () => {
    const onBack = vi.fn();
    render(<Host paged onBack={onBack} />);
    for (let i = 0; i < 7; i++) fireEvent.click(screen.getByTestId("questions-next"));
    expect(progress()).toContain("마지막 확인");
    // Footer "← 이전" (→ setup) and the footer start are md+ only.
    expect(screen.getByTestId("questions-footer-back").className).toContain("hidden md:inline-block");
    fireEvent.click(screen.getByTestId("questions-prev"));
    expect(onBack).not.toHaveBeenCalled();
    expect(progress()).toContain("질문 7 / 7");
    fireEvent.click(screen.getByTestId("questions-prev"));
    expect(progress()).toContain("질문 6 / 7");
  });

  it("without the prop, the list renders as before", () => {
    const { unmount } = render(<Host paged={false} onBack={() => {}} />);
    expect(screen.getByTestId("questions-footer-back").className).not.toContain("hidden");
    unmount();
    render(<Host paged={false} />);
    expect(screen.queryByTestId("questions-pager")).toBeNull();
    expect(screen.queryByTestId("questions-progress")).toBeNull();
    expect(screen.queryByTestId("questions-review")).toBeNull();
    for (let n = 1; n <= 7; n++) expect(hiddenOnPhone(screen.getByTestId(`question-${n}`))).toBe(false);
  });
});

describe("QuestionsStep · pagedOnPhone · swipe", () => {
  beforeEach(() => stubViewport(true));

  it("a forward swipe on an unticked question is refused and ticks nothing", () => {
    render(<Host paged />);
    swipe(questionText(1), -FAR);
    expect(progress()).toContain("질문 1 / 7");
    expect(box(1).checked).toBe(false);
    expect(screen.getByTestId("questions-swipe-hint")).toBeTruthy();
    // Ticking clears the hint; the next swipe pages.
    tap(box(1));
    expect(screen.queryByTestId("questions-swipe-hint")).toBeNull();
    swipe(questionText(1), -FAR);
    expect(progress()).toContain("질문 2 / 7");
    expect(box(2).checked).toBe(false);
  });

  it("swiping back keeps answers and ticks; from question 1 it returns to setup", () => {
    const onBack = vi.fn();
    render(<Host paged onBack={onBack} />);
    fireEvent.change(answerInput(1), { target: { value: "한 줄 답" } });
    fireEvent.click(screen.getByTestId("questions-next"));
    expect(progress()).toContain("질문 2 / 7");

    swipe(questionText(2), FAR);
    expect(progress()).toContain("질문 1 / 7");
    expect(answerInput(1).value).toBe("한 줄 답");
    expect(box(1).checked).toBe(true);

    // Q1 is ticked, so a forward swipe pages again.
    swipe(questionText(1), -FAR);
    expect(progress()).toContain("질문 2 / 7");
    swipe(questionText(2), FAR);
    swipe(questionText(1), FAR);
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("the review screen never starts from a swipe", () => {
    const onStart = vi.fn();
    render(<Host paged onStart={onStart} />);
    for (let i = 0; i < 7; i++) fireEvent.click(screen.getByTestId("questions-next"));
    const review = screen.getByTestId("questions-review");
    swipe(review, -FAR);
    expect(onStart).not.toHaveBeenCalled();
    expect(progress()).toContain("마지막 확인");
    swipe(review, FAR);
    expect(progress()).toContain("질문 7 / 7");
  });

  it("a swipe that ends on a review row does not also tap it", () => {
    render(<Host paged />);
    for (let i = 0; i < 7; i++) fireEvent.click(screen.getByTestId("questions-next"));
    const row = screen.getByTestId("review-jump-2");
    swipe(row, -FAR);
    fireEvent.click(row); // the click a touch UA may fire after the gesture
    expect(progress()).toContain("마지막 확인");
    tap(row); // a plain tap afterwards works
    expect(progress()).toContain("질문 2 / 7");
  });

  it("ignores short, vertical, mouse and in-field gestures", () => {
    render(<Host paged />);
    fireEvent.click(box(1));
    swipe(questionText(1), -(SWIPE_MIN_PX - 10));
    swipe(questionText(1), -FAR, { dy: FAR });
    swipe(questionText(1), -FAR, { pointerType: "mouse" });
    swipe(answerInput(1), -FAR);
    expect(progress()).toContain("질문 1 / 7");
  });

  it("md+ viewports never page by swipe", () => {
    stubViewport(false);
    render(<Host paged />);
    fireEvent.click(box(1));
    swipe(questionText(1), -FAR);
    expect(progress()).toContain("질문 1 / 7");
  });
});
