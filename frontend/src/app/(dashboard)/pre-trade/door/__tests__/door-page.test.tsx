/**
 * /pre-trade/door — 웹 문 (2026-10-15).
 *
 * Pins: 그냥 보기 saves at once; 살/팔 게 있음 ask for one optional line and
 * then save; the `app` tag comes from ?app= (and only a safe slug); the reply
 * is the server's count line; 「멈춤」 is offered only for 살 게 있음 with a
 * ticker and carries the ticker, never the line; past answers can be deleted,
 * all of them — the list follows the server's `next_before` cursor
 * ("이전 기록 더 보기", 2026-10-21).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render as rtlRender, screen, waitFor, within } from "@testing-library/react";
import * as React from "react";
import { SWRConfig } from "swr";

const calls = vi.hoisted(() => ({
  create: vi.fn(),
  remove: vi.fn(),
  fetch: vi.fn<(url: string) => Promise<unknown>>(),
  checks: [] as unknown[],
}));

vi.mock("@/lib/hooks", () => ({
  createDoorwayCheck: calls.create,
  deleteDoorwayCheck: calls.remove,
  fetcher: (url: string) => calls.fetch(url),
  useDoorwaySummary: () => ({ data: null, isLoading: false, error: undefined, mutate: vi.fn() }),
}));

import DoorPage from "@/app/(dashboard)/pre-trade/door/page";

function render(ui: React.ReactElement) {
  return rtlRender(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>{ui}</SWRConfig>,
  );
}

/** Serves `calls.checks` (newest first) the way routes/doorway.py pages them by id. */
function serve(url: string) {
  const u = new URL(url, "http://x");
  const limit = Number(u.searchParams.get("limit"));
  const before = u.searchParams.get("before");
  const rows = (calls.checks as { id: number }[]).filter((c) => before === null || c.id < Number(before));
  const page = rows.slice(0, limit);
  return Promise.resolve({
    ok: true,
    checks: page,
    next_before: rows.length > limit ? page[page.length - 1].id : null,
  });
}

function check(id: number, note: string) {
  return { id, intent: "look", ticker: null, name: null, note, app: "toss", source: "automation", created_at: "2026-10-14T06:10:00" };
}

function reply(intent: string, ticker: string | null, message: string) {
  return {
    ok: true,
    check: { id: 1, intent, ticker, name: ticker ? "삼성전자" : null, note: null, app: "kiwoom", source: "web", created_at: "2026-10-15T00:05:00" },
    today: 3,
    message,
    pause_url: null,
  };
}

beforeEach(() => {
  calls.create.mockReset();
  calls.remove.mockReset().mockResolvedValue({ ok: true, deleted: 7 });
  calls.fetch.mockReset().mockImplementation(serve);
  calls.checks = [];
  window.history.replaceState(null, "", "/pre-trade/door?app=kiwoom");
});
afterEach(cleanup);

describe("web door", () => {
  it("saves 그냥 보기 at once with the app tag", async () => {
    calls.create.mockResolvedValue(reply("look", null, "기록했어요 · 오늘 3번째 열림"));
    render(<DoorPage />);
    fireEvent.click(screen.getByRole("button", { name: "그냥 보기" }));
    await waitFor(() => expect(screen.getByTestId("door-done")).toBeInTheDocument());
    expect(calls.create).toHaveBeenCalledWith({ intent: "look", note: undefined, app: "kiwoom" });
    expect(screen.getByText("기록했어요 · 오늘 3번째 열림")).toBeInTheDocument();
    expect(screen.queryByTestId("door-pause-link")).toBeNull();
  });

  it("asks for a line on 살 게 있음, then offers 멈춤 for the ticker only", async () => {
    calls.create.mockResolvedValue(reply("buy", "005930.KS", "기록했어요 · 삼성전자 · 오늘 3번째 열림"));
    render(<DoorPage />);
    fireEvent.click(screen.getByRole("button", { name: "살 게 있음" }));
    fireEvent.change(screen.getByTestId("door-line"), { target: { value: "  삼성전자 실적 전에  " } });
    fireEvent.click(screen.getByRole("button", { name: "남기기" }));
    await waitFor(() => expect(screen.getByTestId("door-done")).toBeInTheDocument());
    expect(calls.create).toHaveBeenCalledWith({ intent: "buy", note: "삼성전자 실적 전에", app: "kiwoom" });
    const link = screen.getByTestId("door-pause-link");
    expect(link).toHaveAttribute("href", "/pre-trade?ticker=005930.KS");
    expect(link.getAttribute("href")).not.toMatch(/실적/);
  });

  it("keeps the screen up on a bare {ok: true} (demo mode)", async () => {
    calls.create.mockResolvedValue({ ok: true });
    render(<DoorPage />);
    fireEvent.click(screen.getByRole("button", { name: "살 게 있음" }));
    fireEvent.click(screen.getByRole("button", { name: "남기기" }));
    await waitFor(() => expect(screen.getByTestId("door-done")).toBeInTheDocument());
    expect(screen.getByText("기록했어요")).toBeInTheDocument();
    expect(screen.queryByTestId("door-pause-link")).toBeNull();
  });

  it("drops an unsafe app tag", async () => {
    window.history.replaceState(null, "", "/pre-trade/door?app=%3Cscript%3E");
    calls.create.mockResolvedValue(reply("look", null, "기록했어요 · 오늘 1번째 열림"));
    render(<DoorPage />);
    fireEvent.click(screen.getByRole("button", { name: "그냥 보기" }));
    await waitFor(() => expect(calls.create).toHaveBeenCalled());
    expect(calls.create).toHaveBeenCalledWith({ intent: "look", note: undefined, app: undefined });
  });

  it("shows the server's error line and stays on the question", async () => {
    const { ApiError } = await import("@/lib/api");
    calls.create.mockRejectedValue(new ApiError(429, "오늘 남길 수 있는 문 앞 기록 100건을 모두 썼습니다.", "DOORWAY_DAILY_LIMIT"));
    render(<DoorPage />);
    fireEvent.click(screen.getByRole("button", { name: "그냥 보기" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("100건"));
    expect(screen.queryByTestId("door-done")).toBeNull();
  });

  it("lists past answers and deletes one", async () => {
    calls.checks = [
      { id: 7, intent: "sell", ticker: "TSLA", name: "Tesla", note: "반등 정리", app: "toss", source: "automation", created_at: "2026-10-14T06:10:00" },
    ];
    render(<DoorPage />);
    const list = await screen.findByTestId("door-recent");
    expect(within(list).getByText("반등 정리")).toBeInTheDocument();
    expect(screen.queryByTestId("door-more")).toBeNull();
    const reads = calls.fetch.mock.calls.length;
    fireEvent.click(within(list).getByRole("button", { name: /기록 지우기/ }));
    await waitFor(() => expect(calls.remove).toHaveBeenCalledWith(7));
    await waitFor(() => expect(calls.fetch.mock.calls.length).toBeGreaterThan(reads));
  });

  it("reaches answers past the first 20 and can delete them", async () => {
    calls.checks = Array.from({ length: 25 }, (_, i) => check(25 - i, `열림 ${25 - i}`));
    render(<DoorPage />);
    await screen.findByText("열림 25");
    expect(screen.queryByText("열림 5")).toBeNull();
    fireEvent.click(screen.getByTestId("door-more"));
    await screen.findByText("열림 5");
    expect(calls.fetch).toHaveBeenCalledWith("/api/doorway/checks?limit=20&before=6");
    expect(screen.getByText("열림 1")).toBeInTheDocument();
    expect(screen.queryByTestId("door-more")).toBeNull();

    calls.remove.mockImplementation(async (id: number) => {
      calls.checks = (calls.checks as { id: number }[]).filter((c) => c.id !== id);
      return { ok: true, deleted: id };
    });
    const row = screen.getByText("열림 1").closest("li") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: /기록 지우기/ }));
    await waitFor(() => expect(calls.remove).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.queryByText("열림 1")).toBeNull());
    expect(screen.getByText("열림 2")).toBeInTheDocument();
  });

  it("says so when a delete fails instead of dropping the error", async () => {
    calls.checks = [check(7, "열림 7")];
    calls.remove.mockReset().mockRejectedValue(new Error("network"));
    render(<DoorPage />);
    await screen.findByText("열림 7");
    const list = screen.getByTestId("door-recent");
    fireEvent.click(within(list).getByRole("button", { name: /기록 지우기/ }));
    expect(await within(list).findByRole("alert")).toHaveTextContent("지우지 못했어요");
    expect(screen.getByText("열림 7")).toBeInTheDocument();
  });
});
