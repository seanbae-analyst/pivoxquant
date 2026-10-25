/**
 * 리서치 양식 — form, scoring, summary, and the read-only /pre-trade block.
 *
 * Pins: the form needs a stock and at least one reason ("뭘로 돈을 버나" is
 * optional and folded since 2026-10-25, with 위험 · 숫자), and
 * sends exactly what was typed (blank optional fields omitted, 다시 볼 날
 * chip → review_months); scoring needs a verdict for every reason and does
 * NOT show the result on the user's fills until it is saved; the summary is
 * counts only; /pre-trade's block is text only (no link, button or form);
 * no copy carries advice, targets or a grade.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import * as React from "react";
import type { ResearchNote, ResearchOverviewResponse } from "@/lib/types";

const createResearchNote = vi.fn();
const reviewResearchNote = vi.fn();
const deleteResearchNote = vi.fn();
let overview: { data: ResearchOverviewResponse | null; isLoading: boolean; error: Error | undefined } = {
  data: null,
  isLoading: true,
  error: undefined,
};
let byTicker: { note: ResearchNote | null; count: number; isLoading: boolean } = { note: null, count: 0, isLoading: false };

vi.mock("@/lib/hooks", () => ({
  createResearchNote: (...a: unknown[]) => createResearchNote(...a),
  reviewResearchNote: (...a: unknown[]) => reviewResearchNote(...a),
  deleteResearchNote: (...a: unknown[]) => deleteResearchNote(...a),
  useResearchByTicker: () => byTicker,
  useResearchOverview: () => overview,
}));

import { ResearchForm } from "@/components/journal/research/research-form";
import { ResearchCard } from "@/components/journal/research/research-card";
import { ResearchSummary } from "@/components/journal/research/research-summary";
import { RelatedResearch } from "@/components/pre-trade/related-research";
import { ResearchEntry } from "@/components/journal/research-entry";

const NOTE: ResearchNote = {
  id: 11,
  ticker: "AAPL",
  name: "Apple",
  business: "아이폰과 서비스 구독으로 번다",
  theses: ["서비스 매출 비중이 오른다", "교체 주기가 짧아진다"],
  invalidation: "서비스 매출이 두 분기 연속 준다",
  risk: null,
  numbers: null,
  info_source: "report",
  surface: "journal",
  review_on: "2026-10-15",
  verdicts: [],
  review_note: null,
  reviewed_at: null,
  created_at: "2026-07-15T03:00:00",
  due: true,
  outcome: "gain",
};

const BANNED = ["추천", "조언", "권장", "적정", "목표", "지키", "점수", "등급", "적중률", "%", "매수하세요", "매도하세요"];

beforeEach(() => {
  createResearchNote.mockReset();
  reviewResearchNote.mockReset();
  deleteResearchNote.mockReset();
  byTicker = { note: null, count: 0, isLoading: false };
});
afterEach(() => cleanup());

describe("ResearchForm", () => {
  it("sends exactly what was typed, folded fields included", async () => {
    createResearchNote.mockResolvedValue({ ok: true, note: { ...NOTE, id: 99 } });
    const onSaved = vi.fn();
    render(<ResearchForm defaultTicker={{ ticker: "AAPL", name: "Apple" }} onSaved={onSaved} />);
    const save = screen.getByRole("button", { name: "저장" });
    expect(save).toBeDisabled();

    fireEvent.change(screen.getByLabelText("이 회사는 뭘로 돈을 버나"), { target: { value: " 구독료로 번다 " } });
    expect(save).toBeDisabled(); // a business line alone is not a reason
    fireEvent.change(screen.getByLabelText("이유 1"), { target: { value: "마진이 회복된다" } });
    fireEvent.click(screen.getByRole("button", { name: /이유 하나 더/ }));
    fireEvent.change(screen.getByLabelText("이유 2"), { target: { value: "   " } });
    fireEvent.change(screen.getByLabelText("이게 보이면 틀린 것"), { target: { value: "두 분기 연속 마진 하락" } });
    fireEvent.click(within(screen.getByRole("group", { name: "어디서 알게 됐나" })).getByRole("button", { name: "유튜브" }));
    fireEvent.click(within(screen.getByRole("group", { name: "다시 볼 날" })).getByRole("button", { name: "6개월 뒤" }));
    expect(save).toBeEnabled();
    fireEvent.click(save);

    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(createResearchNote).toHaveBeenCalledWith({
      ticker: "AAPL",
      business: "구독료로 번다",
      theses: ["마진이 회복된다"],
      invalidation: "두 분기 연속 마진 하락",
      risk: undefined,
      numbers: undefined,
      info_source: "youtube",
      review_months: 6,
      surface: "journal",
    });
  });

  // 2026-10-25 (CEO "적어야 할게 너무 많다"): two fields open, three folded.
  it("saves with a reason alone; 뭘로 돈을 버나 · 위험 · 숫자 start folded", async () => {
    createResearchNote.mockResolvedValue({ ok: true, note: { ...NOTE, id: 100, business: "" } });
    const onSaved = vi.fn();
    render(<ResearchForm defaultTicker={{ ticker: "AAPL", name: "Apple" }} onSaved={onSaved} />);
    const more = screen.getByTestId("research-more") as HTMLDetailsElement;
    expect(more.open).toBe(false);
    expect(within(more).getByLabelText("이 회사는 뭘로 돈을 버나")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("이유 1"), { target: { value: "마진이 회복된다" } });
    const save = screen.getByRole("button", { name: "저장" });
    expect(save).toBeEnabled();
    fireEvent.click(save);
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(createResearchNote.mock.calls.at(-1)?.[0]).toMatchObject({
      business: undefined,
      theses: ["마진이 회복된다"],
    });
  });

  it("stops at three reasons and carries no advice words", () => {
    render(<ResearchForm defaultTicker={{ ticker: "AAPL" }} onSaved={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /이유 하나 더/ }));
    fireEvent.click(screen.getByRole("button", { name: /이유 하나 더/ }));
    expect(screen.queryByRole("button", { name: /이유 하나 더/ })).toBeNull();
    const text = (screen.getByTestId("research-form").textContent ?? "") +
      Array.from(document.querySelectorAll("input,textarea")).map((el) => (el as HTMLInputElement).placeholder).join(" ");
    for (const w of BANNED) expect(text).not.toContain(w);
  });
});

describe("ResearchCard scoring", () => {
  it("needs a verdict for every reason and hides the fill result until saved", async () => {
    reviewResearchNote.mockResolvedValue({ ok: true, note: { ...NOTE, verdicts: ["right", "wrong"], reviewed_at: "2026-10-15T01:00:00" } });
    const onChanged = vi.fn();
    render(<ResearchCard note={NOTE} onChanged={onChanged} startOpen />);
    const review = screen.getByTestId("research-review");
    // While scoring, the result on the user's own fills is not on screen.
    expect(screen.getByTestId("research-card")).not.toHaveTextContent("판 뒤 이익");

    const save = within(review).getByRole("button", { name: "채점 저장" });
    fireEvent.click(within(within(review).getByRole("group", { name: "이유 1 채점" })).getByRole("button", { name: "맞음" }));
    expect(save).toBeDisabled();
    fireEvent.click(within(within(review).getByRole("group", { name: "이유 2 채점" })).getByRole("button", { name: "틀림" }));
    expect(save).toBeEnabled();
    fireEvent.click(save);
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    expect(reviewResearchNote).toHaveBeenCalledWith(11, { verdicts: ["right", "wrong"], note: undefined });
  });

  it("after scoring, the card shows the verdicts and the fill result as a fact", () => {
    render(
      <ResearchCard
        note={{ ...NOTE, verdicts: ["right", "wrong"], reviewed_at: "2026-10-15T01:00:00", due: false }}
        onChanged={() => {}}
      />,
    );
    const card = screen.getByTestId("research-card");
    expect(card).toHaveTextContent("채점함 · 판 뒤 이익");
    expect(card).toHaveTextContent("맞음");
    expect(card).toHaveTextContent("틀림");
    expect(card).toHaveTextContent("안 봄"); // numbers left blank
    for (const w of BANNED) expect(card.textContent ?? "").not.toContain(w);
  });
});

describe("ResearchSummary", () => {
  const base: ResearchOverviewResponse = {
    ok: true,
    due: [],
    counts: { notes: 3, scored: 2, due: 0, waiting: 1 },
    judgment: {
      right: { gain: 2, loss: 1, flat: 0, open: 1 },
      wrong: { gain: 1, loss: 0, flat: 0, open: 0 },
    },
    unknown: 1,
    by_source: {
      report: { right: 2, wrong: 0, unknown: 0 },
      youtube: { right: 1, wrong: 1, unknown: 1 },
      social: { right: 0, wrong: 0, unknown: 0 },
      ai: { right: 0, wrong: 0, unknown: 0 },
      self: { right: 1, wrong: 0, unknown: 0 },
      none: { right: 0, wrong: 0, unknown: 0 },
    },
  };

  it("prints judgment × result and per-source counts, never a rate", () => {
    render(<ResearchSummary data={base} />);
    const table = screen.getByTestId("research-judgment");
    expect(table).toHaveTextContent("이유 맞음211"); // gain 2 · loss 1 · open 1 (no 본전 column when 0)
    expect(table).toHaveTextContent("이유 틀림100");
    expect(table).not.toHaveTextContent("판 뒤 본전");
    expect(screen.getByTestId("research-summary")).toHaveTextContent("채점한 이유 6개");
    expect(screen.getByTestId("research-summary")).toHaveTextContent("모름 1개는 빼고 셌어요");
    const bySource = screen.getByTestId("research-by-source");
    expect(bySource).toHaveTextContent("유튜브맞음 1 · 틀림 1 · 모름 1");
    expect(bySource).not.toHaveTextContent("지인·SNS"); // empty sources are left out
    for (const w of BANNED) expect(screen.getByTestId("research-summary").textContent ?? "").not.toContain(w);
  });

  it("says plainly that nothing is scored yet", () => {
    render(<ResearchSummary data={{ ...base, counts: { ...base.counts, scored: 0 } }} />);
    expect(screen.getByTestId("research-summary-empty")).toHaveTextContent("아직 채점한 리서치가 없어요");
  });
});

describe("ResearchEntry (기록 화면)", () => {
  it("stays reachable while the overview loads or fails — only the count waits", () => {
    for (const state of [
      { data: null, isLoading: true, error: undefined },
      { data: null, isLoading: false, error: new Error("cold start") },
    ]) {
      overview = state;
      render(<ResearchEntry />);
      const row = screen.getByTestId("research-entry");
      expect(row.getAttribute("href")).toBe("/journal/research");
      expect(row).not.toHaveTextContent("다시 볼 것");
      cleanup();
    }
  });

  it("shows the due count once the overview arrives", () => {
    overview = {
      data: { counts: { due: 2 } } as unknown as ResearchOverviewResponse,
      isLoading: false,
      error: undefined,
    };
    render(<ResearchEntry />);
    expect(screen.getByTestId("research-entry")).toHaveTextContent("다시 볼 것 2개");
  });
});

describe("RelatedResearch (/pre-trade)", () => {
  it("renders nothing without research on the symbol", () => {
    const { container } = render(<RelatedResearch ticker="AAPL" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the reasons and the 틀린 신호 read-only — no link, button or form", () => {
    byTicker = { note: NOTE, count: 2, isLoading: false };
    render(<RelatedResearch ticker="aapl" />);
    const block = screen.getByTestId("related-research");
    expect(block).toHaveTextContent("7월 15일에 쓴 내 리서치 (2개 중 최근)");
    expect(block).toHaveTextContent("서비스 매출 비중이 오른다");
    expect(block).toHaveTextContent("틀렸다고 볼 신호");
    expect(block.querySelector("a,button,form,input,textarea")).toBeNull();
  });
});
