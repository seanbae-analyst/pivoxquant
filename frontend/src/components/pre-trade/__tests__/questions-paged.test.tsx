/**
 * QuestionsStep `pagedOnPhone` (2026-10-07): one question per screen on a
 * phone. Only the current question is visible below md; "검토했음 · 다음"
 * ticks it and moves on; the start button bar shows on the last question.
 * Without the prop (the modals) nothing changes.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { useState } from "react";

vi.mock("@/lib/api", () => {
  class ApiError extends Error {}
  return { apiFetch: vi.fn(), ApiError };
});
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { QuestionsStep } from "@/components/pre-trade/pre-trade-friction-core";

function Host({ paged, onBack }: { paged: boolean; onBack?: () => void }) {
  const [acks, setAcks] = useState<Record<number, boolean>>({});
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const allAcked = [1, 2, 3, 4, 5, 6, 7].every((n) => acks[n]);
  return (
    <QuestionsStep
      acks={acks} setAcks={setAcks}
      answers={answers} setAnswers={setAnswers}
      allAcked={allAcked} submitting={false}
      onBack={onBack} onStart={() => {}}
      pagedOnPhone={paged}
    />
  );
}

const hiddenOnPhone = (el: HTMLElement) => el.className.includes("hidden md:block");

afterEach(cleanup);

describe("QuestionsStep · pagedOnPhone", () => {
  it("shows one question at a time; next ticks it and advances", () => {
    render(<Host paged />);
    expect(hiddenOnPhone(screen.getByTestId("question-1"))).toBe(false);
    expect(hiddenOnPhone(screen.getByTestId("question-2"))).toBe(true);
    expect(screen.getByTestId("questions-progress").textContent).toContain("질문 1 / 7");

    fireEvent.click(screen.getByTestId("questions-next"));
    expect(hiddenOnPhone(screen.getByTestId("question-1"))).toBe(true);
    expect(hiddenOnPhone(screen.getByTestId("question-2"))).toBe(false);
    const box1 = screen.getByTestId("question-1").querySelector('input[type="checkbox"]') as HTMLInputElement;
    expect(box1.checked).toBe(true);

    for (let i = 0; i < 5; i++) fireEvent.click(screen.getByTestId("questions-next"));
    expect(screen.getByTestId("questions-progress").textContent).toContain("질문 7 / 7");
    expect(screen.queryByTestId("questions-next")).toBeNull();
    // Last question: tick it and start is enabled.
    const box7 = screen.getByTestId("question-7").querySelector('input[type="checkbox"]') as HTMLInputElement;
    fireEvent.click(box7);
    const start = screen.getByText(/진입 시계 시작/).closest("button") as HTMLButtonElement;
    expect(start.disabled).toBe(false);
  });

  it("previous on the first question goes back to setup", () => {
    const onBack = vi.fn();
    render(<Host paged onBack={onBack} />);
    fireEvent.click(screen.getByTestId("questions-prev"));
    expect(onBack).toHaveBeenCalled();
  });

  it("without the prop, the list renders as before", () => {
    render(<Host paged={false} />);
    expect(screen.queryByTestId("questions-pager")).toBeNull();
    for (let n = 1; n <= 7; n++) expect(hiddenOnPhone(screen.getByTestId(`question-${n}`))).toBe(false);
  });
});
