/**
 * <ObservationNoteComposer /> — the caps that keep a POST from being a
 * round-trip the backend will only reject (docs/design/
 * observation-notes_2026-09-22.md §2, §6).
 *
 * The network layer is mocked at `@/lib/api`, which is the module
 * `lib/hooks.ts::createObservationNote` calls — so the assertions are on the
 * exact request body the composer would put on the wire.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    constructor(
      public status: number,
      message: string,
      public code?: string,
    ) {
      super(message);
    }
  }
  return { apiFetch: vi.fn(), ApiError };
});

import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import {
  ObservationNoteComposer,
  OBS_NOTE_MAX_CHARS,
  noteTickerKey,
  tagRejection,
} from "@/components/journal/observation-note-composer";
import type { ObservationNote } from "@/lib/types";

const mockedFetch = vi.mocked(apiFetch);

function noteFixture(overrides: Partial<ObservationNote> = {}): ObservationNote {
  return {
    id: 7,
    body: "장 초반 거래량이 평소보다 두껍다.",
    tickers: [],
    tags: [],
    source: "journal",
    created_at: "2026-09-22T01:00:00Z",
    ...overrides,
  };
}

function jsonResponse(results: unknown[]) {
  return {
    ok: true,
    status: 200,
    json: async () => ({ results }),
  } as unknown as Response;
}

describe("<ObservationNoteComposer /> — submit gating", () => {
  beforeEach(() => {
    mockedFetch.mockReset();
  });

  it("blocks submit while the body is blank", async () => {
    const user = userEvent.setup();
    render(<ObservationNoteComposer source="journal" />);

    const submit = screen.getByRole("button", { name: "기록" });
    expect(submit).toBeDisabled();

    // Whitespace alone is still blank.
    await user.type(screen.getByLabelText("관찰 노트 본문"), "   ");
    expect(screen.getByRole("button", { name: "기록" })).toBeDisabled();

    await user.click(submit);
    expect(mockedFetch).not.toHaveBeenCalled();
  });

  it("blocks submit past the 5000-char cap and says so", async () => {
    render(<ObservationNoteComposer source="journal" />);
    const textarea = screen.getByLabelText("관찰 노트 본문");

    await act(async () => {
      // Typing 5001 chars through userEvent is far too slow — set directly.
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        "value",
      )!.set!;
      setter.call(textarea, "가".repeat(OBS_NOTE_MAX_CHARS + 1));
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    });

    expect(screen.getByRole("button", { name: "기록" })).toBeDisabled();
    expect(
      screen.getByText(`${OBS_NOTE_MAX_CHARS + 1} / ${OBS_NOTE_MAX_CHARS}`),
    ).toBeTruthy();
    // The copy must not promise a truncated save — the server rejects.
    expect(
      screen.getByText(`${OBS_NOTE_MAX_CHARS}자를 넘으면 기록할 수 없습니다.`),
    ).toBeTruthy();
    expect(mockedFetch).not.toHaveBeenCalled();
  });

  it("counts code points, not UTF-16 units, so the cap matches Python len()", async () => {
    render(<ObservationNoteComposer source="journal" />);
    const textarea = screen.getByLabelText("관찰 노트 본문");

    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        "value",
      )!.set!;
      // 3 astral code points = 6 UTF-16 units; the server sees 3.
      setter.call(textarea, "  🙂🙂🙂  ");
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    });

    expect(screen.getByText(`3 / ${OBS_NOTE_MAX_CHARS}`)).toBeTruthy();
    expect(screen.getByRole("button", { name: "기록" })).not.toBeDisabled();

    // At exactly the cap in code points the composer still submits; one more
    // astral char is over, even though `String.length` would have said so
    // 2500 characters earlier.
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        "value",
      )!.set!;
      setter.call(textarea, "🙂".repeat(OBS_NOTE_MAX_CHARS));
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(
      screen.getByText(`${OBS_NOTE_MAX_CHARS} / ${OBS_NOTE_MAX_CHARS}`),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "기록" })).not.toBeDisabled();
  });

  it("POSTs body + tickers + tags + source and hands the note to onCreated", async () => {
    const user = userEvent.setup();
    const note = noteFixture({ tags: ["거래량"] });
    mockedFetch.mockResolvedValue({ ok: true, note });
    const onCreated = vi.fn();

    render(
      <ObservationNoteComposer
        source="portfolio"
        defaultTickers={["aapl"]}
        onCreated={onCreated}
      />,
    );

    await user.type(
      screen.getByLabelText("관찰 노트 본문"),
      "장 초반 거래량이 평소보다 두껍다.",
    );
    await user.type(screen.getByLabelText("태그 입력"), "거래량{Enter}");
    await user.click(screen.getByRole("button", { name: "기록" }));

    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    const [url, opts] = mockedFetch.mock.calls[0];
    expect(url).toBe(API.observationNotes.create);
    expect((opts as RequestInit).method).toBe("POST");
    expect(JSON.parse((opts as RequestInit).body as string)).toEqual({
      body: "장 초반 거래량이 평소보다 두껍다.",
      // defaultTickers are normalized to the canonical upper-case form.
      tickers: ["AAPL"],
      tags: ["거래량"],
      source: "portfolio",
    });

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(note));
    // The form clears after a committed note.
    expect((screen.getByLabelText("관찰 노트 본문") as HTMLTextAreaElement).value).toBe("");
  });

  it("renders the server's own error_kr message on a 400", async () => {
    const user = userEvent.setup();
    mockedFetch.mockRejectedValue(new Error("본문을 입력해 주세요."));

    render(<ObservationNoteComposer source="journal" />);
    await user.type(screen.getByLabelText("관찰 노트 본문"), "메모");
    await user.click(screen.getByRole("button", { name: "기록" }));

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toBe("본문을 입력해 주세요."),
    );
  });
});

describe("<ObservationNoteComposer /> — tag cap", () => {
  beforeEach(() => {
    mockedFetch.mockReset();
  });

  it("rejects a tag longer than 40 chars and keeps it out of the chip row", async () => {
    const user = userEvent.setup();
    render(<ObservationNoteComposer source="journal" />);

    const tagInput = screen.getByLabelText("태그 입력");
    const tooLong = "ㄱ".repeat(41);
    await user.type(tagInput, `${tooLong}{Enter}`);

    expect(screen.getByRole("status").textContent).toContain("40자");
    expect(screen.queryByLabelText(`${tooLong} 태그 빼기`)).toBeNull();
    // A 40-char tag is accepted.
    await user.clear(tagInput);
    const justFits = "ㄴ".repeat(40);
    await user.type(tagInput, `${justFits}{Enter}`);
    expect(screen.getByLabelText(`${justFits} 태그 빼기`)).toBeTruthy();
  });

  it("refuses a tag carrying a quote or a backslash — the server 400s them", async () => {
    const user = userEvent.setup();
    render(<ObservationNoteComposer source="journal" />);

    const tagInput = screen.getByLabelText("태그 입력");
    await user.type(tagInput, '거래"량{Enter}');

    expect(screen.getByRole("status").textContent).toContain("큰따옴표");
    expect(screen.queryByLabelText('거래"량 태그 빼기')).toBeNull();

    // Both banned characters, checked on the pure helper (userEvent's key
    // parser makes a literal backslash awkward to type).
    expect(tagRejection('거래"량', [])).toBe("bad_chars");
    expect(tagRejection("거래\\량", [])).toBe("bad_chars");
    expect(tagRejection("거래량", [])).toBeNull();
  });
});

describe("noteTickerKey", () => {
  it("folds a bare KR code onto its .KS/.KQ spelling", () => {
    expect(noteTickerKey("005930")).toBe("005930");
    expect(noteTickerKey("005930.KS")).toBe("005930");
    expect(noteTickerKey("005930.ks")).toBe("005930");
    expect(noteTickerKey("068270.KQ")).toBe("068270");
    // A US ticker is untouched, and so is a suffix that is not an exchange.
    expect(noteTickerKey("aapl")).toBe("AAPL");
    expect(noteTickerKey("BRK.B")).toBe("BRK.B");
  });
});

describe("<ObservationNoteComposer /> — ticker cap", () => {
  beforeEach(() => {
    mockedFetch.mockReset();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse([{ ticker: "TSLA", name: "Tesla Inc.", exchange: "NASDAQ" }]),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("stops at 5 tickers — the search box disappears and a 6th cannot be added", async () => {
    const user = userEvent.setup();
    render(
      <ObservationNoteComposer
        source="journal"
        defaultTickers={["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "TSLA"]}
      />,
    );

    // The 6th default ticker is dropped, not silently over-filled.
    for (const t of ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]) {
      expect(screen.getByLabelText(`${t} 빼기`)).toBeTruthy();
    }
    expect(screen.queryByLabelText("TSLA 빼기")).toBeNull();
    expect(screen.getByText("종목 · 선택 (5/5)")).toBeTruthy();

    // At the cap the picker is not offered at all, so no 6th can be picked.
    expect(screen.queryByLabelText("종목 검색")).toBeNull();

    // Freeing a slot brings the picker back.
    await user.click(screen.getByLabelText("AAPL 빼기"));
    expect(screen.getByLabelText("종목 검색")).toBeTruthy();
  });
});

describe("<ObservationNoteComposer /> — ticker dedupe", () => {
  beforeEach(() => {
    mockedFetch.mockReset();
  });

  it("treats 005930 and 005930.KS as one ticker", async () => {
    render(
      <ObservationNoteComposer
        source="journal"
        defaultTickers={["005930", "005930.KS", "005930"]}
      />,
    );

    // One chip, in the spelling that arrived first.
    expect(screen.getByLabelText("005930 빼기")).toBeTruthy();
    expect(screen.queryByLabelText("005930.KS 빼기")).toBeNull();
    expect(screen.getByText("종목 · 선택 (1/5)")).toBeTruthy();
  });
});
