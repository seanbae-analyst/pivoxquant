/**
 * <RelatedObservationNotes /> — the read-back above the seven questions.
 *
 * docs/design/observation-notes_2026-09-22.md §4-1, §9. Three things are
 * load-bearing and are pinned here:
 *   1. nothing renders at count 0 (an empty block is noise, and a "0개" line
 *      reads as a prompt to go write one),
 *   2. the user's own words are quoted when there is something to quote,
 *   3. there is NO write affordance on this surface — no composer, no link.
 *      A way to write a note here would be a way around the questions.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/hooks", () => ({
  useObservationNotesByTicker: vi.fn(),
}));

import { useObservationNotesByTicker } from "@/lib/hooks";
import {
  RelatedObservationNotes,
  noteExcerpt,
  RELATED_NOTES_EXCERPT_CHARS,
} from "@/components/pre-trade/related-observation-notes";
import type { ObservationNote } from "@/lib/types";

const mockedHook = vi.mocked(useObservationNotesByTicker);

function note(id: number, body: string): ObservationNote {
  return {
    id,
    body,
    tickers: [{ ticker: "NVDA", name: "NVIDIA" }],
    tags: [],
    source: "journal",
    created_at: "2026-09-20T01:00:00Z",
  };
}

function hookResult(partial: {
  notes?: ObservationNote[];
  count?: number;
  isLoading?: boolean;
  error?: Error;
}) {
  return {
    notes: partial.notes ?? [],
    count: partial.count ?? 0,
    disclaimer: null,
    isLoading: partial.isLoading ?? false,
    error: partial.error,
    mutate: vi.fn(),
  } as unknown as ReturnType<typeof useObservationNotesByTicker>;
}

describe("noteExcerpt", () => {
  it("collapses the user's line breaks into one line", () => {
    expect(noteExcerpt("첫 줄\n\n  둘째 줄")).toBe("첫 줄 둘째 줄");
  });

  it("cuts at the budget and marks the cut", () => {
    const long = "가".repeat(RELATED_NOTES_EXCERPT_CHARS + 40);
    const out = noteExcerpt(long);
    expect(out).toHaveLength(RELATED_NOTES_EXCERPT_CHARS + 1);
    expect(out.endsWith("…")).toBe(true);
  });

  it("leaves a short body untouched", () => {
    expect(noteExcerpt("짧은 기록")).toBe("짧은 기록");
  });
});

describe("<RelatedObservationNotes />", () => {
  beforeEach(() => {
    mockedHook.mockReset();
  });

  it("renders nothing when the ticker has no notes", () => {
    mockedHook.mockReturnValue(hookResult({ count: 0 }));
    const { container } = render(<RelatedObservationNotes ticker="NVDA" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing while loading", () => {
    mockedHook.mockReturnValue(
      hookResult({ count: 2, notes: [note(1, "a")], isLoading: true }),
    );
    const { container } = render(<RelatedObservationNotes ticker="NVDA" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the read failed", () => {
    mockedHook.mockReturnValue(
      hookResult({ count: 2, notes: [note(1, "a")], error: new Error("boom") }),
    );
    const { container } = render(<RelatedObservationNotes ticker="NVDA" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("disables the fetch when no ticker is chosen yet", () => {
    mockedHook.mockReturnValue(hookResult({ count: 0 }));
    render(<RelatedObservationNotes ticker="" />);
    expect(mockedHook).toHaveBeenCalledWith(null, 30);
  });

  it("shows the count line and the user's own words when there are notes", () => {
    mockedHook.mockReturnValue(
      hookResult({
        count: 2,
        notes: [
          note(1, "장 초반 거래량이 평소보다 두껍다."),
          note(2, "이틀째 같은 자리에서 멈춰 있다."),
        ],
      }),
    );
    render(<RelatedObservationNotes ticker="nvda" />);

    expect(mockedHook).toHaveBeenCalledWith("NVDA", 30);
    expect(
      screen.getByText("이 종목에 대해 최근 30일 관찰 노트 2개"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("장 초반 거래량이 평소보다 두껍다."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("이틀째 같은 자리에서 멈춰 있다."),
    ).toBeInTheDocument();
  });

  it("shows at most three excerpts however many the window holds", () => {
    const notes = [1, 2, 3, 4, 5].map((i) => note(i, `기록 ${i}`));
    mockedHook.mockReturnValue(hookResult({ count: 5, notes }));
    render(<RelatedObservationNotes ticker="NVDA" />);
    expect(screen.getByText("기록 3")).toBeInTheDocument();
    expect(screen.queryByText("기록 4")).toBeNull();
  });

  it("offers no way to write from here — §9 (no composer, no link)", () => {
    mockedHook.mockReturnValue(
      hookResult({ count: 1, notes: [note(1, "관찰만 해 둔다.")] }),
    );
    render(<RelatedObservationNotes ticker="NVDA" />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("form")).toBeNull();
  });
});
