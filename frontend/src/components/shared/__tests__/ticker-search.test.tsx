/**
 * <TickerSearch /> — the three behaviours the extraction had to preserve
 * when this moved out of add-position-modal-v2 (2026-09-22).
 *
 * Fake timers, not the wall clock: the component debounces on a real
 * `setTimeout`, and driving that under parallel-worker contention is what
 * made the add-position copy of these cases flake. We pin time and advance
 * the debounce + fetch microtasks explicitly (same recipe as
 * portfolio/v2/__tests__/add-position-modal-v2.test.tsx).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as React from "react";
import { TickerSearch } from "@/components/shared/ticker-search";
import type { TickerSearchResult } from "@/components/shared/ticker-search";

function jsonResponse(results: unknown[]) {
  return {
    ok: true,
    status: 200,
    json: async () => ({ results }),
  } as unknown as Response;
}

const RESULTS = [
  { ticker: "005930.KS", name: "삼성전자", exchange: "KRX", is_korean: true },
  { ticker: "AAPL", name: "Apple Inc.", exchange: "NASDAQ" },
];

/** Controlled host — mirrors how both real call sites own the input text. */
function Host({ onPick }: { onPick?: (r: TickerSearchResult) => void }) {
  const [value, setValue] = React.useState("");
  return (
    <TickerSearch
      value={value}
      onChange={setValue}
      onPick={(r) => {
        setValue(r.ticker.trim().toUpperCase());
        onPick?.(r);
      }}
      ariaLabel="Symbol"
    />
  );
}

describe("<TickerSearch />", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let user: ReturnType<typeof userEvent.setup>;

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fetchMock = vi.fn().mockResolvedValue(jsonResponse(RESULTS));
    vi.stubGlobal("fetch", fetchMock);
    user = userEvent.setup();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  async function flushSearch(ms = 300) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ms);
    });
  }

  it("coalesces keystrokes into one request after the debounce", async () => {
    render(<Host />);
    // Three keystrokes. A non-debounced field would fire three searches; the
    // debounce must collapse them into one, for the FULL query.
    await user.type(screen.getByLabelText("Symbol"), "005");

    await flushSearch();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("/api/search?q=005");
    expect(url).toContain("limit=6");

    // Nothing more fires while the query sits still.
    await flushSearch(600);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("aborts the in-flight request when the query changes again", async () => {
    // Never resolves — so the only way the first request ends is the abort.
    const signals: AbortSignal[] = [];
    fetchMock.mockImplementation((_url: string, init: RequestInit) => {
      if (init?.signal) signals.push(init.signal);
      return new Promise<Response>(() => {});
    });

    render(<Host />);
    const input = screen.getByLabelText("Symbol");

    await user.type(input, "00");
    await flushSearch();
    expect(signals).toHaveLength(1);
    expect(signals[0].aborted).toBe(false);

    await user.type(input, "5");
    await flushSearch();

    expect(signals).toHaveLength(2);
    expect(signals[0].aborted).toBe(true);
    expect(signals[1].aborted).toBe(false);
  });

  it("does not fetch again after a pick (picked suppresses the popover)", async () => {
    const onPick = vi.fn();
    render(<Host onPick={onPick} />);

    await user.type(screen.getByLabelText("Symbol"), "005");
    await flushSearch();
    expect(screen.getByRole("listbox", { name: "종목 검색 결과" })).toBeTruthy();

    await user.click(screen.getByRole("option", { name: /삼성전자/ }));

    expect(onPick).toHaveBeenCalledTimes(1);
    expect(onPick.mock.calls[0][0].ticker).toBe("005930.KS");
    expect(screen.queryByRole("listbox", { name: "종목 검색 결과" })).toBeNull();

    const callsAfterPick = fetchMock.mock.calls.length;
    // Writing the canonical ticker back into the input must NOT re-search.
    await flushSearch(400);
    expect(fetchMock.mock.calls.length).toBe(callsAfterPick);
    expect(screen.queryByRole("listbox", { name: "종목 검색 결과" })).toBeNull();
  });
});
