/**
 * WeeklyPulseCard — two taps and 기록하기 (2026-10-25, CEO "적어야 할게 너무
 * 많다"). 기분 and 자신감 start unpicked and both are needed; the two lines
 * are folded and optional; what was picked is what is sent.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const submit = vi.fn();
vi.mock("@/lib/cfo/hooks", () => ({
  usePulse: () => ({ data: { history: [] }, submit }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { WeeklyPulseCard } from "@/components/dashboard/weekly-pulse";

afterEach(() => {
  cleanup();
  submit.mockReset();
});

describe("WeeklyPulseCard", () => {
  it("needs both picks — no preset 3/3 is recorded", async () => {
    submit.mockResolvedValue(undefined);
    render(<WeeklyPulseCard />);
    const go = screen.getByRole("button", { name: "기분과 자신감을 골라 주세요" });
    expect(go).toBeDisabled();
    expect(
      screen.queryAllByRole("button", { pressed: true }).filter((b) =>
        /5점 중/.test(b.getAttribute("aria-label") ?? ""),
      ),
    ).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "이번 주 투자 기분 — 5점 중 2점" }));
    expect(go).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "자신감 — 5점 중 4점" }));
    const record = screen.getByRole("button", { name: "기록하기" });
    expect(record).toBeEnabled();
    fireEvent.click(record);
    await waitFor(() => expect(submit).toHaveBeenCalledTimes(1));
    expect(submit).toHaveBeenCalledWith({ mood: 2, confidence: 4, worry: "", topics: [], learn: "" });
  });

  it("folds the two lines", () => {
    render(<WeeklyPulseCard />);
    const more = screen.getByTestId("pulse-more") as HTMLDetailsElement;
    expect(more.open).toBe(false);
    expect(more).toContainElement(screen.getByLabelText("마음에 걸리는 것 하나"));
    expect(more).toContainElement(screen.getByLabelText("배우고 싶은 것"));
  });
});
