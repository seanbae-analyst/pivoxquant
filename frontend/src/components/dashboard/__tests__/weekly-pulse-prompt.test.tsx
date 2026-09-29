/**
 * <WeeklyPulsePrompt /> — Monday-only link to the single pulse form on
 * /journal. Replaced the auto-opening modal on /portfolio (2026-09-29).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

const usePulseMock = vi.fn();
vi.mock("@/lib/cfo/hooks", () => ({ usePulse: () => usePulseMock() }));

import { LocaleProvider } from "@/lib/locale";
import {
  WeeklyPulsePrompt,
  isPulsePromptDue,
} from "@/components/dashboard/weekly-pulse-prompt";

// 2026-09-28 is a Monday. 01:00Z = 10:00 KST Monday.
const MON_10_KST = new Date("2026-09-28T01:00:00Z");

describe("isPulsePromptDue", () => {
  it("is due on Monday after 07:00 KST with no pulse this week", () => {
    expect(isPulsePromptDue([], MON_10_KST)).toBe(true);
    expect(
      isPulsePromptDue([{ submitted_at: "2026-09-21T02:00:00Z" }], MON_10_KST),
    ).toBe(true);
  });

  it("is not due once this week's pulse exists (naive UTC timestamps too)", () => {
    // 2026-09-27T15:30Z = Monday 00:30 KST
    expect(
      isPulsePromptDue([{ submitted_at: "2026-09-27T15:30:00" }], MON_10_KST),
    ).toBe(false);
  });

  it("is not due before 07:00 KST Monday or on other days", () => {
    expect(isPulsePromptDue([], new Date("2026-09-27T21:00:00Z"))).toBe(false); // Mon 06:00 KST
    expect(isPulsePromptDue([], new Date("2026-09-29T01:00:00Z"))).toBe(false); // Tue
    expect(isPulsePromptDue([], new Date("2026-09-27T01:00:00Z"))).toBe(false); // Sun
  });
});

describe("<WeeklyPulsePrompt />", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(MON_10_KST);
    window.localStorage.clear();
  });
  afterEach(() => {
    vi.useRealTimers();
    usePulseMock.mockReset();
  });

  const renderPrompt = () =>
    render(
      <LocaleProvider>
        <WeeklyPulsePrompt />
      </LocaleProvider>,
    );

  it("links to the journal pulse section when due, and never opens a dialog", () => {
    usePulseMock.mockReturnValue({ data: { history: [] } });
    renderPrompt();
    const link = screen.getByRole("link");
    expect(link.getAttribute("href")).toBe("/journal#weekly-pulse");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders nothing when this week's pulse is already written", () => {
    usePulseMock.mockReturnValue({
      data: { history: [{ submitted_at: "2026-09-28T00:10:00Z" }] },
    });
    const { container } = renderPrompt();
    expect(container.textContent).toBe("");
  });

  it("renders nothing until the history has loaded", () => {
    usePulseMock.mockReturnValue({ data: undefined });
    const { container } = renderPrompt();
    expect(container.textContent).toBe("");
  });

  it("hides for the rest of the day once dismissed", () => {
    usePulseMock.mockReturnValue({ data: { history: [] } });
    const first = renderPrompt();
    act(() => {
      fireEvent.click(screen.getByRole("button"));
    });
    expect(first.container.textContent).toBe("");
    first.unmount();
    const second = renderPrompt();
    expect(second.container.textContent).toBe("");
  });
});
