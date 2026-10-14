/**
 * MyRulesPanel — 「내 규칙」 on /mirror (2026-10-14).
 *
 * Pins: each line and its observed fact print as the backend sent them;
 * the status is "선 안 / 선 밖", never a score, grade or streak; the −10%
 * answer reads "세지 않음"; a user without onboarding answers gets the way
 * to answer them, not an empty card; no `rules` block → nothing; the month
 * bars only appear when there are two months to compare; editing goes
 * through the existing five-question retake.
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";

import type { MirrorHomeResponse, MyRules } from "@/lib/types";
import { MyRulesPanel } from "@/components/mirror/my-rules-panel";

afterEach(cleanup);

const RULES: MyRules = {
  available: true,
  source: "onboarding",
  counted: 2,
  outside: 1,
  items: [
    {
      id: "frequency", title: "매매 횟수", line: "한 달에 매수·매도 5번 이하",
      measurable: true, status: "outside", observed: "이번 달 6번 · 선 5번",
      ceiling: 5, this_month: 6, waiting: 0, months_over: 1, months_shown: 3,
      months: [
        { month: "2026-08", count: 3, over: false, partial: false },
        { month: "2026-09", count: 5, over: false, partial: false },
        { month: "2026-10", count: 6, over: true, partial: true },
      ],
    },
    {
      id: "positions", title: "종목 수", line: "동시에 4~8종목을 들고 있다",
      measurable: true, status: "within", observed: "지금 6종목",
      side: null, open_positions: 6, lo: 4, hi: 8,
    },
    {
      id: "drawdown", title: "하락 대응", line: "한 주에 10% 빠지면 그냥 둔다",
      measurable: false, status: "not_counted",
      observed: "시세를 쓰지 않아 10% 빠진 주를 알 수 없어요 — 세지 않아요",
    },
  ],
};

function payload(rules: MyRules | null | undefined): MirrorHomeResponse {
  return {
    ok: true,
    stage: "new",
    declared: { source: "self" },
    observed: { trade_count: 0 },
    gap: [],
    drift: { available: false, descriptor: null },
    rules,
    radar: { keys: [], labels: [], declared: [], observed: null },
  };
}

describe("MyRulesPanel", () => {
  it("prints each line, its fact and a 선 안 / 선 밖 status", () => {
    render(<MyRulesPanel data={payload(RULES)} />);
    const freq = screen.getByTestId("my-rule-frequency");
    expect(freq).toHaveTextContent("한 달에 매수·매도 5번 이하");
    expect(freq).toHaveTextContent("이번 달 6번 · 선 5번");
    expect(within(freq).getByTestId("my-rule-status")).toHaveTextContent("선 밖");
    expect(within(screen.getByTestId("my-rule-positions")).getByTestId("my-rule-status"))
      .toHaveTextContent("선 안");
    expect(within(screen.getByTestId("my-rule-drawdown")).getByTestId("my-rule-status"))
      .toHaveTextContent("세지 않음");
    expect(screen.getByTestId("my-rules-panel"))
      .toHaveTextContent("지금 셀 수 있는 선 2개 중 1개에서 기록이 선 밖에 있어요.");
  });

  it("never prints a score, grade, streak or directive", () => {
    render(<MyRulesPanel data={payload(RULES)} />);
    const text = screen.getByTestId("my-rules-panel").textContent ?? "";
    for (const word of ["점수", "등급", "연속", "지키세요", "위반", "추천", "조언", "/100", "비율"]) {
      expect(text).not.toContain(word);
    }
    // The only percentage is the user's own −10% answer — no adherence rate.
    expect(text.match(/\d+%/g)).toEqual(["10%", "10%"]);
  });

  it("draws the month bars with the user's own line", () => {
    render(<MyRulesPanel data={payload(RULES)} />);
    const months = screen.getByTestId("my-rule-months");
    expect(months).toHaveTextContent("정해 둔 선 5번");
    expect(months).toHaveTextContent("이번 달");
    expect(months).toHaveTextContent("8월");
  });

  it("does not draw a one-bar chart for a single month", () => {
    const single: MyRules = {
      ...RULES,
      items: [{ ...RULES.items[0], months: [RULES.items[0].months![2]] }],
    };
    render(<MyRulesPanel data={payload(single)} />);
    expect(screen.queryByTestId("my-rule-months")).toBeNull();
  });

  it("changing a line goes through the five-question retake", () => {
    render(<MyRulesPanel data={payload(RULES)} />);
    expect(screen.getByRole("link", { name: "선 다시 정하기" }))
      .toHaveAttribute("href", "/onboarding?retake=1");
  });

  it("without onboarding answers offers the five questions instead of an empty card", () => {
    render(<MyRulesPanel data={payload({ ...RULES, available: false, items: [], counted: 0, outside: 0 })} />);
    expect(screen.queryByTestId("my-rule-frequency")).toBeNull();
    expect(screen.getByRole("link", { name: "다섯 문항 답하기 →" }))
      .toHaveAttribute("href", "/onboarding?retake=1");
  });

  it("renders nothing when the backend sent no rules block", () => {
    const { container: a } = render(<MyRulesPanel data={payload(null)} />);
    expect(a).toBeEmptyDOMElement();
    cleanup();
    const { container: b } = render(<MyRulesPanel data={payload(undefined)} />);
    expect(b).toBeEmptyDOMElement();
  });
});
