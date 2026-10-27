/**
 * /journal/research — 내 리서치 past the first 100.
 *
 * Pins (2026-10-15): the list follows the server's `next_before` cursor —
 * "이전 리서치 더 보기" asks for `?before=<next_before>` and shows those notes
 * too (they can be deleted from here); the control is gone on the last page;
 * a change on any card re-reads every loaded page.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import * as React from "react";
import { SWRConfig } from "swr";
import type { ResearchNote, ResearchNotesResponse } from "@/lib/types";

const fetchMock = vi.fn<(url: string) => Promise<ResearchNotesResponse>>();

vi.mock("@/lib/hooks", () => ({
  fetcher: (url: string) => fetchMock(url),
  useResearchOverview: () => ({ data: null, isLoading: false, error: undefined, mutate: vi.fn() }),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/components/journal/research/research-form", () => ({ ResearchForm: () => null }));
vi.mock("@/components/journal/research/research-summary", () => ({ ResearchSummary: () => null }));
vi.mock("@/components/journal/research/research-card", () => ({
  ResearchCard: ({ note, onChanged }: { note: ResearchNote; onChanged: () => void }) => (
    <div data-testid="research-card">
      {note.ticker}
      <button type="button" onClick={onChanged}>
        {`changed-${note.id}`}
      </button>
    </div>
  ),
}));

import ResearchPage from "@/app/(dashboard)/journal/research/page";

function note(id: number): ResearchNote {
  return {
    id,
    ticker: `T${id}`,
    name: `T${id}`,
    business: "b",
    theses: ["t"],
    invalidation: null,
    risk: null,
    numbers: null,
    info_source: null,
    surface: "journal",
    review_on: "2027-01-15",
    verdicts: [],
    review_note: null,
    reviewed_at: null,
    created_at: "2026-10-15T01:00:00",
    due: false,
    outcome: "open",
  };
}

/** 102 notes, ids 102..1 newest first; the server pages them by id. */
function serve(url: string): Promise<ResearchNotesResponse> {
  const u = new URL(url, "http://x");
  const limit = Number(u.searchParams.get("limit"));
  const before = u.searchParams.get("before");
  const ids = Array.from({ length: 102 }, (_, i) => 102 - i).filter((id) => before === null || id < Number(before));
  const page = ids.slice(0, limit);
  return Promise.resolve({
    ok: true,
    notes: page.map(note),
    next_before: ids.length > limit ? page[page.length - 1] : null,
  });
}

function renderPage() {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <ResearchPage />
    </SWRConfig>,
  );
}

describe("/journal/research — more than 100 notes", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockImplementation(serve);
  });
  afterEach(cleanup);

  it("loads the notes after the first 100 through next_before", async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId("research-card")).toHaveLength(100));
    expect(screen.queryByText("T2")).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith("/api/research-notes/list?limit=100");

    fireEvent.click(screen.getByTestId("research-load-more"));
    await waitFor(() => expect(screen.getAllByTestId("research-card")).toHaveLength(102));
    expect(fetchMock).toHaveBeenCalledWith("/api/research-notes/list?limit=100&before=3");
    expect(screen.getByText("T1")).toBeTruthy();
    expect(screen.queryByTestId("research-load-more")).toBeNull();
  });

  it("a body that is not a page (demo `{}`) draws no cards and offers no more", async () => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({} as ResearchNotesResponse);
    renderPage();
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryAllByTestId("research-card")).toHaveLength(0);
    expect(screen.queryByTestId("research-load-more")).toBeNull();
  });

  it("re-reads every loaded page after a change on a card", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId("research-load-more")).toBeTruthy());
    fireEvent.click(screen.getByTestId("research-load-more"));
    await waitFor(() => expect(screen.getByText("T1")).toBeTruthy());

    const before = fetchMock.mock.calls.filter(([u]) => u.includes("before=")).length;
    fireEvent.click(screen.getByText("changed-1"));
    await waitFor(() =>
      expect(fetchMock.mock.calls.filter(([u]) => u.includes("before=")).length).toBeGreaterThan(before),
    );
  });
});

/**
 * 다시 찾기 (2026-10-27): the bar's words and chips ride on the list URL, a
 * search shows every match (due ones included), and a miss says so.
 */
describe("/journal/research — 다시 찾기", () => {
  /** Three notes; `q` matches on the ticker, `source=report` keeps id 2. */
  function serveSearch(url: string): Promise<ResearchNotesResponse> {
    const u = new URL(url, "http://x");
    const q = (u.searchParams.get("q") ?? "").toLowerCase();
    const source = u.searchParams.get("source");
    const all = [3, 2, 1].map((id) => ({ ...note(id), info_source: id === 2 ? ("report" as const) : null }));
    const notes = all.filter(
      (n) => (!q || n.ticker.toLowerCase().includes(q)) && (!source || n.info_source === source),
    );
    return Promise.resolve({ ok: true, notes, next_before: null });
  }

  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockImplementation(serveSearch);
  });
  afterEach(cleanup);

  it("sends the typed words once typing pauses, and lists the matches", async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId("research-card")).toHaveLength(3));

    fireEvent.change(screen.getByTestId("research-search"), { target: { value: "t2" } });
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith("/api/research-notes/list?limit=100&q=t2"),
    );
    await waitFor(() => expect(screen.getAllByTestId("research-card")).toHaveLength(1));
    expect(screen.getByRole("heading", { name: /찾은 리서치\s*1개/ })).toBeTruthy();
    // One request for the word, not one per key.
    expect(fetchMock.mock.calls.filter(([u]) => u.includes("q=")).length).toBe(1);
  });

  it("a source chip filters, and 조건 지우기 brings every note back", async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId("research-card")).toHaveLength(3));

    fireEvent.click(screen.getByRole("button", { name: "리포트" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith("/api/research-notes/list?limit=100&source=report"),
    );
    await waitFor(() => expect(screen.getAllByTestId("research-card")).toHaveLength(1));
    expect(screen.getByText("T2")).toBeTruthy();

    fireEvent.click(screen.getByTestId("research-filters-clear"));
    await waitFor(() => expect(screen.getAllByTestId("research-card")).toHaveLength(3));
    expect(screen.queryByTestId("research-filters-clear")).toBeNull();
  });

  it("says so when nothing matches", async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId("research-card")).toHaveLength(3));
    fireEvent.change(screen.getByTestId("research-search"), { target: { value: "없는말" } });
    await waitFor(() => expect(screen.getByTestId("research-no-match").textContent).toContain("조건에 맞는 리서치가 없어요"));
    expect(screen.queryAllByTestId("research-card")).toHaveLength(0);
  });
});
