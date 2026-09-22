/**
 * <ObservationNoteCard /> — delete is the ONLY write this surface offers, and
 * notes are append-only (docs/design/observation-notes_2026-09-22.md §8 Q1),
 * so the three states that matter are pinned here:
 *
 *   1. 삭제 → 확인 actually calls the API and tells the host which id went,
 *   2. a rejected delete says so out loud (role="alert") and puts the card
 *      back to its resting 삭제 state — a silent failure would leave the user
 *      believing their own record was erased when it was not,
 *   3. 취소 touches nothing at all.
 *
 * `@/lib/hooks` is mocked because the card calls `deleteObservationNote`
 * directly; nothing here should reach the network.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/lib/hooks", () => ({
  deleteObservationNote: vi.fn(),
}));

import { deleteObservationNote } from "@/lib/hooks";
import { ObservationNoteCard } from "@/components/journal/observation-note-card";
import type { ObservationNote } from "@/lib/types";

const mockedDelete = vi.mocked(deleteObservationNote);

function note(overrides: Partial<ObservationNote> = {}): ObservationNote {
  return {
    id: 11,
    body: "장 초반 거래량이 평소보다 두껍다.",
    tickers: [{ ticker: "005930.KS", name: "삼성전자" }],
    tags: ["거래량"],
    source: "journal",
    created_at: "2026-09-20T01:00:00Z",
    ...overrides,
  };
}

describe("<ObservationNoteCard /> — delete", () => {
  beforeEach(() => {
    mockedDelete.mockReset();
  });

  it("삭제 → 확인 deletes the note and hands the id back", async () => {
    const user = userEvent.setup();
    mockedDelete.mockResolvedValue({ ok: true, deleted: 11 });
    const onDeleted = vi.fn();

    render(<ObservationNoteCard note={note()} onDeleted={onDeleted} />);

    // The confirm step is inline — one click does not delete anything.
    await user.click(screen.getByRole("button", { name: "삭제" }));
    expect(mockedDelete).not.toHaveBeenCalled();
    expect(screen.getByText("지우면 되돌릴 수 없습니다.")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "확인" }));

    await waitFor(() => expect(mockedDelete).toHaveBeenCalledWith(11));
    await waitFor(() => expect(onDeleted).toHaveBeenCalledWith(11));
  });

  it("renders the server's message and returns to 삭제 when the delete fails", async () => {
    const user = userEvent.setup();
    mockedDelete.mockRejectedValue(new Error("노트를 찾을 수 없습니다."));
    const onDeleted = vi.fn();

    render(<ObservationNoteCard note={note()} onDeleted={onDeleted} />);

    await user.click(screen.getByRole("button", { name: "삭제" }));
    await user.click(screen.getByRole("button", { name: "확인" }));

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toBe(
        "노트를 찾을 수 없습니다.",
      ),
    );
    // Back to the resting state, and the host was never told it went.
    expect(screen.getByRole("button", { name: "삭제" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "확인" })).toBeNull();
    expect(onDeleted).not.toHaveBeenCalled();
    // The record itself is still on screen.
    expect(screen.getByText("장 초반 거래량이 평소보다 두껍다.")).toBeTruthy();
  });

  it("취소 leaves the note alone and calls nothing", async () => {
    const user = userEvent.setup();
    const onDeleted = vi.fn();

    render(<ObservationNoteCard note={note()} onDeleted={onDeleted} />);

    await user.click(screen.getByRole("button", { name: "삭제" }));
    await user.click(screen.getByRole("button", { name: "취소" }));

    expect(mockedDelete).not.toHaveBeenCalled();
    expect(onDeleted).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "삭제" })).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("장 초반 거래량이 평소보다 두껍다.")).toBeTruthy();
  });
});
