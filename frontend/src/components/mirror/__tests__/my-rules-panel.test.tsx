/**
 * MyRulesPanel — 「내 규칙」 on /mirror (2026-10-14).
 *
 * Pins: before the user adopts the lines the card is "온보딩 때 말한 나" —
 * lines and facts, no 선 안/밖 status, and one explicit choice (adopt via
 * POST /api/profile/rules/confirm, then re-read the mirror; or change the
 * answers through the retake). After adopting: "내 규칙", each line with a
 * 선 안 / 선 밖 status, never a score, grade, streak or directive; the −10%
 * answer reads "세지 않음". No onboarding answers → the way to answer them.
 * No `rules` block → nothing. Month bars only with two months to compare.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import type { MirrorHomeResponse, MyRules } from "@/lib/types";

const calls = vi.hoisted(() => ({
  confirm: vi.fn(),
  mutate: vi.fn(),
}));
vi.mock("@/lib/hooks", () => ({ confirmMyRules: calls.confirm }));
vi.mock("swr", () => ({ mutate: calls.mutate }));

import { MyRulesPanel } from "@/components/mirror/my-rules-panel";

beforeEach(() => {
  calls.confirm.mockReset().mockResolvedValue({ ok: true, rules_confirmed_at: "2026-10-14T01:00:00" });
  calls.mutate.mockReset().mockResolvedValue(undefined);
});
afterEach(cleanup);

const ADOPTED: MyRules = {
  available: true,
  source: "onboarding",
  confirmed: true,
  confirmed_at: "2026-10-01T00:00:00",
  confirmed_on: "2026-10-01",
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
      id: "positions", title: "종목 수", line: "4종목 이상 나눠 담는다",
      measurable: true, status: "within", observed: "지금 6종목",
      open_positions: 6, min_positions: 4,
    },
    {
      id: "drawdown", title: "하락 대응", line: "한 주에 10% 빠지면 그냥 둔다",
      measurable: false, status: "not_counted",
      observed: "시세를 쓰지 않아 10% 빠진 주를 알 수 없어요 — 세지 않아요",
    },
  ],
};

const NOT_ADOPTED: MyRules = { ...ADOPTED, confirmed: false, confirmed_at: null, confirmed_on: null };

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

describe("MyRulesPanel — adopted (내 규칙)", () => {
  it("prints each line, its fact and a 선 안 / 선 밖 status", () => {
    render(<MyRulesPanel data={payload(ADOPTED)} />);
    const panel = screen.getByTestId("my-rules-panel");
    expect(panel).toHaveAttribute("data-adopted", "true");
    expect(panel).toHaveTextContent("내 규칙");
    expect(panel).toHaveTextContent("2026-10-01부터");
    const freq = screen.getByTestId("my-rule-frequency");
    expect(freq).toHaveTextContent("한 달에 매수·매도 5번 이하");
    expect(freq).toHaveTextContent("이번 달 6번 · 선 5번");
    expect(within(freq).getByTestId("my-rule-status")).toHaveTextContent("선 밖");
    expect(within(screen.getByTestId("my-rule-positions")).getByTestId("my-rule-status"))
      .toHaveTextContent("선 안");
    expect(within(screen.getByTestId("my-rule-drawdown")).getByTestId("my-rule-status"))
      .toHaveTextContent("세지 않음");
    expect(panel).toHaveTextContent("지금 셀 수 있는 선 2개 중 1개에서 기록이 선 밖에 있어요.");
    expect(screen.queryByRole("button", { name: "이 답을 내 선으로 삼기" })).toBeNull();
  });

  it("never prints a score, grade, streak or directive", () => {
    render(<MyRulesPanel data={payload(ADOPTED)} />);
    const text = screen.getByTestId("my-rules-panel").textContent ?? "";
    for (const word of ["점수", "등급", "연속", "지키세요", "위반", "추천", "조언", "/100", "비율"]) {
      expect(text).not.toContain(word);
    }
    // The only percentage is the user's own −10% answer — no adherence rate.
    expect(text.match(/\d+%/g)).toEqual(["10%", "10%"]);
  });

  it("draws the month bars with the user's own line", () => {
    render(<MyRulesPanel data={payload(ADOPTED)} />);
    const months = screen.getByTestId("my-rule-months");
    expect(months).toHaveTextContent("정해 둔 선 5번");
    expect(months).toHaveTextContent("이번 달");
    expect(months).toHaveTextContent("8월");
  });

  it("does not draw a one-bar chart for a single month", () => {
    const single: MyRules = {
      ...ADOPTED,
      items: [{ ...ADOPTED.items[0], months: [ADOPTED.items[0].months![2]] }],
    };
    render(<MyRulesPanel data={payload(single)} />);
    expect(screen.queryByTestId("my-rule-months")).toBeNull();
  });

  it("changing a line goes through the five-question retake", () => {
    render(<MyRulesPanel data={payload(ADOPTED)} />);
    expect(screen.getByRole("link", { name: "선 다시 정하기" }))
      .toHaveAttribute("href", "/onboarding?retake=1");
  });
});

describe("MyRulesPanel — not adopted (온보딩 때 말한 나)", () => {
  it("shows the lines and facts without a status, and says what adopting does", () => {
    render(<MyRulesPanel data={payload(NOT_ADOPTED)} />);
    const panel = screen.getByTestId("my-rules-panel");
    expect(panel).toHaveAttribute("data-adopted", "false");
    expect(panel).toHaveTextContent("온보딩 때 말한 나");
    expect(panel).not.toHaveTextContent("내 규칙");
    expect(screen.getByTestId("my-rule-frequency")).toHaveTextContent("이번 달 6번 · 선 5번");
    expect(screen.queryAllByTestId("my-rule-status")).toHaveLength(0);
    expect(panel).not.toHaveTextContent("선 밖");
    expect(screen.getByTestId("my-rule-months")).toHaveTextContent("답한 선 5번");
    expect(panel).toHaveTextContent("체결 알림에 한 줄");
  });

  it("adopting posts the confirmation and re-reads the mirror", async () => {
    render(<MyRulesPanel data={payload(NOT_ADOPTED)} />);
    fireEvent.click(screen.getByRole("button", { name: "이 답을 내 선으로 삼기" }));
    await waitFor(() => expect(calls.mutate).toHaveBeenCalledWith("/api/mirror-home"));
    expect(calls.confirm).toHaveBeenCalledTimes(1);
  });

  it("a failed save says so and leaves the card as it was", async () => {
    calls.confirm.mockRejectedValueOnce(new Error("온보딩 다섯 문항에 먼저 답해 주세요."));
    render(<MyRulesPanel data={payload(NOT_ADOPTED)} />);
    fireEvent.click(screen.getByRole("button", { name: "이 답을 내 선으로 삼기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("온보딩 다섯 문항에 먼저 답해 주세요.");
    expect(calls.mutate).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "이 답을 내 선으로 삼기" })).toBeEnabled();
  });

  it("changing the answers goes through the retake", () => {
    render(<MyRulesPanel data={payload(NOT_ADOPTED)} />);
    expect(screen.getByRole("link", { name: "답 고치기" }))
      .toHaveAttribute("href", "/onboarding?retake=1");
  });
});

describe("MyRulesPanel — nothing to show", () => {
  it("without onboarding answers offers the five questions instead of an empty card", () => {
    render(
      <MyRulesPanel
        data={payload({ ...NOT_ADOPTED, available: false, items: [], counted: 0, outside: 0 })}
      />,
    );
    expect(screen.queryByTestId("my-rule-frequency")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
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
