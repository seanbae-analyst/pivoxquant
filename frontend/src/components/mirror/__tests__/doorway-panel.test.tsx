/**
 * DoorwayPanel — 「문 앞」 on /mirror (2026-10-15).
 *
 * Pins: the counts the backend sends are read back as facts — how many opens,
 * the three answers as bars, which opens ended in a fill, the "not happened"
 * follow-up, fills through the door — plus the recent answers with the user's
 * own line and the backend's caveats. Never a score, grade, streak or
 * directive. Never set up → one invite line (desktop) or nothing (phone).
 * Set up but quiet → one line pointing at the settings.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";

import type { DoorwaySummaryResponse } from "@/lib/types";

vi.mock("@/lib/hooks", () => ({
  useDoorwaySummary: () => ({ data: null, isLoading: false, error: undefined, mutate: vi.fn() }),
}));

import { DoorwayPanelView, doorwayFacts, kstStamp } from "@/components/mirror/doorway-panel";

afterEach(cleanup);

const hours = Array(24).fill(0);
hours[9] = 3;
hours[22] = 1;

const SUMMARY: DoorwaySummaryResponse = {
  ok: true,
  window_days: 30,
  follow_minutes: 60,
  later_days: 30,
  first_check_at: "2026-09-20T00:12:00",
  total: 9,
  intents: { look: 5, buy: 3, sell: 1 },
  look: { n: 5, traded: 1 },
  said: {
    buy: { n: 3, as_said: 1, other: 1, none: 1 },
    sell: { n: 1, as_said: 0, other: 0, none: 1 },
  },
  not_happened: { n: 2, later: 1, never: 0, open: 1 },
  fills: { total: 4, through_door: 3 },
  by_hour_kst: hours,
  recent: [
    { id: 9, at: "2026-10-15T00:05:00", intent: "buy", ticker: "005930.KS", name: "삼성전자", note: "삼성전자 실적 전에", app: "toss", outcome: "none" },
    { id: 8, at: "2026-10-14T13:02:00", intent: "look", ticker: null, name: null, note: null, app: "toss", outcome: "traded" },
  ],
  caveats: ["누가 언제 앱을 열지는 무작위가 아니므로, 이 숫자로 질문의 효과를 말할 수는 없습니다."],
};

describe("DoorwayPanelView", () => {
  it("reads the counts back as facts", () => {
    render(<DoorwayPanelView data={SUMMARY} />);
    expect(screen.getByText("증권 앱을 9번 열었어요")).toBeInTheDocument();
    const bars = screen.getByTestId("doorway-intents");
    expect(within(bars).getByText("그냥 보기")).toBeInTheDocument();
    expect(within(bars).getByText("5")).toBeInTheDocument();
    const facts = within(screen.getByTestId("doorway-facts")).getAllByRole("listitem").map((li) => li.textContent);
    expect(facts).toEqual([
      "그냥 보기 5번 중 1번은 60분 안에 체결이 있었어요.",
      "살 게 있음 3번 — 말한 대로 체결 1 · 다른 체결 1 · 체결 없음 1",
      "팔 게 있음 1번 — 말한 대로 체결 0 · 다른 체결 0 · 체결 없음 1",
      "종목을 적고 체결 없이 끝난 2번 중 30일 안에 그 종목 체결 1 · 체결 없음 0 · 아직 30일이 안 됨 1",
      "이 기간 체결 4건 중 3건이 문을 거쳤어요.",
    ]);
    expect(screen.getByTestId("doorway-hours")).toBeInTheDocument();
  });

  it("lists recent answers with the user's own line and the outcome", () => {
    render(<DoorwayPanelView data={SUMMARY} />);
    const rows = screen.getAllByTestId("doorway-recent");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("삼성전자 실적 전에")).toBeInTheDocument();
    expect(within(rows[0]).getByText("체결 없음")).toBeInTheDocument();
    expect(within(rows[1]).getByText("체결 있음")).toBeInTheDocument();
    expect(screen.getByText(SUMMARY.caveats[0])).toBeInTheDocument();
  });

  it("invites once when the door was never set up, and only where asked", () => {
    const never = { ...SUMMARY, first_check_at: null, total: 0 };
    const { container, rerender } = render(<DoorwayPanelView data={never} />);
    expect(container.textContent).toBe("");
    rerender(<DoorwayPanelView data={never} invite />);
    expect(screen.getByTestId("doorway-invite")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /설정 안내 보기/ })).toHaveAttribute("href", "/settings?s=doorway");
  });

  it("says the window is quiet when set up but empty", () => {
    render(<DoorwayPanelView data={{ ...SUMMARY, total: 0, recent: [] }} />);
    expect(screen.getByText(/최근 30일 동안 문 앞 기록이 없어요/)).toBeInTheDocument();
    expect(screen.queryByTestId("doorway-intents")).toBeNull();
  });

  it("drops fact lines for answers that did not occur", () => {
    const facts = doorwayFacts({
      ...SUMMARY,
      look: { n: 0, traded: 0 },
      said: { buy: { n: 0, as_said: 0, other: 0, none: 0 }, sell: { n: 0, as_said: 0, other: 0, none: 0 } },
      not_happened: { n: 0, later: 0, never: 0, open: 0 },
      fills: { total: 0, through_door: 0 },
    });
    expect(facts).toEqual([]);
  });

  it("stamps in KST", () => {
    expect(kstStamp("2026-10-15T00:05:00")).toBe("10.15 09:05");
    expect(kstStamp(null)).toBe("");
  });

  it("carries no score, grade, directive or italic", () => {
    const { container } = render(<DoorwayPanelView data={SUMMARY} />);
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/점수|등급|연속|줄이세요|하세요|추천|조언|\bBUY\b|\bSELL\b/);
    const src = readFileSync(join(__dirname, "..", "doorway-panel.tsx"), "utf8");
    expect(src).not.toMatch(/className=[^>]*(?<![-\w])italic\b/);
    expect(src).not.toMatch(/fontStyle:\s*["']italic/);
    expect(src).not.toMatch(/<DisclaimerBanner/);
  });
});
