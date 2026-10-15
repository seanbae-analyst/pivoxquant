/**
 * 올해의 기록 — /mirror/year view, page and the counts-only share card.
 *
 * Pins: the four sections render from the backend's counts and the user's own
 * sentences; a section with nothing of its own is not drawn; an empty year is
 * one honest line (no zero tables); the year selector shows only with more
 * than one year; the share image's text names no stock, no amount, no
 * sentence; no copy carries a score, grade, advice or "결산".
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import * as React from "react";
import type { YearRecapResponse } from "@/lib/types";

let recap: { data: YearRecapResponse | null; isLoading: boolean; error: Error | undefined } = {
  data: null,
  isLoading: false,
  error: undefined,
};

vi.mock("@/lib/hooks", () => ({
  useYearRecap: () => recap,
}));

import { YearRecapView } from "@/components/mirror/year/year-recap-view";
import { canShareCard, drawShareCard, shareCardLines } from "@/components/mirror/year/share-card";
import YearRecapPage from "@/app/(dashboard)/mirror/year/page";

const months = [3, 2, 0, 5, 4, 1, 0, 6, 3, 2].map((count, i) => ({
  month: `2026-${String(i + 1).padStart(2, "0")}`,
  count,
}));

const FULL: YearRecapResponse = {
  ok: true,
  disclaimer: "본 정보는 지난 거래의 회고적 사실 관찰이며 미래 예측이나 거래 권유가 아닙니다.",
  share_disclaimer: "정보 제공 목적이며 투자 권유가 아닙니다. / Information only, not investment advice.",
  year: 2026,
  years: [2026],
  range: { start: "2026-01-01", end: "2026-10-15", partial: true },
  fills: { total: 26, buys: 17, sells: 9, tickers: 8, months_active: 8, by_month: months },
  pauses: { started: 14, proceeded: 7, cancelled: 6, open: 1, cancelled_buy: 6, bought_later_anyway: 2, never_bought: 4 },
  records: {
    reasoned_fills: 19,
    research_written: 3,
    research_reviewed: 1,
    verdicts: { right: 1, wrong: 1, unknown: 0 },
    observation_notes: 5,
  },
  holding: { sells: 9, median_days: 23.5 },
  rules: {
    confirmed_on: "2026-08-10",
    frequency: {
      ceiling: 5,
      months: [
        { month: "2026-08", count: 4, over: false, partial: true },
        { month: "2026-09", count: 7, over: true, partial: false },
      ],
      within: 1,
      outside: 1,
    },
    holding: { min_days: 7, sells: 3, sooner: 1 },
  },
  quotes: [
    { kind: "first_reason", source: "pause", text: "실적 발표 전에 사 두고 싶다", date: "2026-01-06", ticker: "NVDA", name: "NVIDIA" },
    { kind: "not_taken", source: "pause", text: "다들 산다길래 나도 들어가려 했다", date: "2026-03-18", ticker: "TSLA", name: "Tesla" },
    { kind: "scored_thesis", source: "research", text: "메모리 가격이 반등한다", date: "2026-02-01", ticker: "005930.KS", name: "삼성전자", verdict: "right" },
  ],
  doorway: null,
  empty: false,
};

const BANNED = /점수|등급|순위|연속|잘했|개선|결산|추천|조언|advice|recommend|\bBUY\b|\bSELL\b|\bHOLD\b/i;

afterEach(() => {
  cleanup();
  recap = { data: null, isLoading: false, error: undefined };
});

describe("YearRecapView", () => {
  it("renders the four sections from the backend's counts and the user's words", () => {
    render(<YearRecapView data={FULL} />);
    const numbers = screen.getByTestId("year-numbers");
    expect(within(numbers).getByText("26")).toBeTruthy();
    expect(within(numbers).getByText("매수 17 · 매도 9")).toBeTruthy();
    expect(within(numbers).getByText("23.5")).toBeTruthy();
    expect(screen.getByTestId("year-month-bars").getAttribute("aria-label")).toContain("8월 6건");

    const notTaken = screen.getByTestId("year-not-taken");
    expect(within(notTaken).getByText("4")).toBeTruthy();
    expect(within(notTaken).getByText(/멈춤 14번 중/)).toBeTruthy();

    expect(screen.getByTestId("year-quote-not_taken").textContent).toContain("다들 산다길래 나도 들어가려 했다");
    expect(screen.getByTestId("year-quote-not_taken").textContent).toContain("3월 18일 · Tesla");
    expect(screen.getByTestId("year-quote-scored_thesis").textContent).toContain("내 채점 맞음");

    const rules = screen.getByTestId("year-rules");
    expect(within(rules).getByText(/선 안 1달 · 선 밖 1달/)).toBeTruthy();
    expect(screen.getByTestId("year-rules-holding").textContent).toBe("매도 3번 중 7일 전에 판 것 1번");
  });

  it("hides sections with nothing of their own", () => {
    const thin: YearRecapResponse = {
      ...FULL,
      pauses: { started: 0, proceeded: 0, cancelled: 0, open: 0, cancelled_buy: 0, bought_later_anyway: 0, never_bought: 0 },
      quotes: [],
      rules: null,
    };
    render(<YearRecapView data={thin} />);
    expect(screen.getByTestId("year-numbers")).toBeTruthy();
    expect(screen.queryByTestId("year-not-taken")).toBeNull();
    expect(screen.queryByTestId("year-words")).toBeNull();
    expect(screen.queryByTestId("year-rules")).toBeNull();
    expect(screen.queryByTestId("year-doorway")).toBeNull();
  });

  it("shows the year at the door as counts only", () => {
    render(
      <YearRecapView
        data={{
          ...FULL,
          doorway: {
            total: 41,
            intents: { look: 23, buy: 14, sell: 4 },
            look: { n: 23, traded: 3 },
            said: {
              buy: { n: 14, as_said: 6, other: 2, none: 6 },
              sell: { n: 4, as_said: 2, other: 0, none: 2 },
            },
            not_happened: { n: 7, later: 2, never: 3, open: 2 },
            fills: { total: 15, through_door: 13 },
            follow_minutes: 60,
            later_days: 30,
          },
        }}
      />,
    );
    const door = screen.getByTestId("year-doorway");
    const text = door.textContent ?? "";
    expect(text).toContain("41번");
    expect(text).toContain("살 게 · 팔 게 있다고 한 18번 중 말한 대로 체결 8번");
    expect(text).toContain("종목을 적고 체결 없이 끝난 7번 중 30일 안에 그 종목 체결 2 · 체결 없음 3");
    expect(text).not.toMatch(BANNED);
  });

  it("an empty year is one honest line, not a table of zeros", () => {
    render(<YearRecapView data={{ ...FULL, empty: true }} />);
    expect(screen.getByTestId("year-empty").textContent).toBe("2026년에는 남긴 기록이 없어요.");
    expect(screen.queryByTestId("year-numbers")).toBeNull();
  });

  it("carries no score, grade, advice or 결산 words", () => {
    const { container } = render(<YearRecapView data={FULL} />);
    expect(container.textContent ?? "").not.toMatch(BANNED);
  });
});

describe("share card", () => {
  it("is counts only — no ticker, name, amount or sentence", () => {
    const text = shareCardLines(FULL);
    const all = [text.title, ...text.lines, text.wordmark].join("\n");
    expect(text.title).toBe("2026년, 내 기록");
    expect(text.lines).toEqual([
      "사기 전에 멈춘 14번",
      "그중 끝내 사지 않은 4번",
      "이유를 적은 체결 19건",
      "직접 쓴 리서치 3편",
    ]);
    for (const q of FULL.quotes) {
      expect(all).not.toContain(q.text);
      expect(all).not.toContain(q.ticker as string);
      expect(all).not.toContain(q.name as string);
    }
    expect(all).not.toMatch(/005930|NVDA|TSLA|원|\$|₩|%/);
    expect(all).not.toMatch(BANNED);
    expect(text.disclaimer).toBe(FULL.share_disclaimer);
  });

  it("draws exactly those lines on the canvas, the legal line in its two halves", () => {
    const drawn: string[] = [];
    const ctx = {
      fillRect: () => undefined,
      fillText: (t: string) => drawn.push(t),
      measureText: (t: string) => ({ width: t.length * 10 }),
    } as unknown as CanvasRenderingContext2D;
    const canvas = { getContext: () => ctx } as unknown as HTMLCanvasElement;
    const text = shareCardLines(FULL);
    expect(drawShareCard(canvas, text)).toBe(true);
    expect(canvas.width).toBe(1080);
    expect(drawn).toEqual([
      text.title,
      ...text.lines,
      "PivoxQuant",
      "정보 제공 목적이며 투자 권유가 아닙니다.",
      "Information only, not investment advice.",
    ]);
  });

  it("drops zero lines and is not offered for an empty year or without the legal line", () => {
    const quiet = { ...FULL, pauses: { ...FULL.pauses, started: 0, never_bought: 0 } };
    expect(shareCardLines(quiet).lines).toEqual(["이유를 적은 체결 19건", "직접 쓴 리서치 3편"]);
    expect(canShareCard(FULL)).toBe(true);
    expect(canShareCard({ ...FULL, empty: true })).toBe(false);
    expect(canShareCard({ ...FULL, share_disclaimer: "" })).toBe(false);
  });
});

describe("/mirror/year page", () => {
  it("titles the year without 결산 and offers the share button", () => {
    recap = { data: FULL, isLoading: false, error: undefined };
    render(<YearRecapPage />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("2026년, 내 기록");
    expect(screen.getByTestId("year-share")).toBeTruthy();
    expect(screen.queryByRole("group", { name: "연도" })).toBeNull();
  });

  it("shows the year selector only with more than one year", () => {
    recap = { data: { ...FULL, years: [2026, 2025] }, isLoading: false, error: undefined };
    render(<YearRecapPage />);
    const group = screen.getByRole("group", { name: "연도" });
    expect(within(group).getAllByRole("button").map((b) => b.textContent)).toEqual(["2026년", "2025년"]);
  });

  it("an empty year shows no share button", () => {
    recap = { data: { ...FULL, empty: true }, isLoading: false, error: undefined };
    render(<YearRecapPage />);
    expect(screen.queryByTestId("year-share")).toBeNull();
    expect(screen.getByTestId("year-empty")).toBeTruthy();
  });
});
