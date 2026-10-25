/**
 * 종목별 내 기록 (2026-10-25) — the view over GET /api/stock-record/<t>.
 *
 * Pins: title + holding line from the user's own book; four counts (with
 * "그 뒤로 안 산 것" when a pause had no buy after it); events grouped by
 * KST month, newest first, each with its kind and the user's own words;
 * the pause no buy followed carries "그 뒤로 사지 않음"; an empty record says
 * so; the two ways on (멈춤 · 리서치) carry the ticker; no score / grade /
 * advice words anywhere.
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";

import { StockRecordView, monthKey } from "@/components/journal/stock-record-view";
import type { StockRecordResponse } from "@/lib/types";

afterEach(cleanup);

const DATA: StockRecordResponse = {
  ok: true,
  ticker: "005930.KS",
  name: "삼성전자",
  holding: { shares: 200, avg_cost: 72000, currency: "KRW" },
  counts: { fills: 2, buys: 1, sells: 1, pauses: 1, not_taken: 1, research: 1, notes: 1 },
  events: [
    { kind: "note", at: "2026-06-16T07:10:00Z", id: 2, body: "평단 근처에서 손이 근질거린다.", tags: ["충동"] },
    { kind: "fill", at: "2026-06-11T06:20:00Z", side: "buy", shares: 50, price: 81000, currency: "KRW", after_pause: true },
    { kind: "pause", at: "2026-06-03T01:00:00Z", side: "entry", rationale: "실적·숫자 · 차트 자리", status: "cancelled", bought_after: false },
    {
      kind: "research", at: "2026-02-01T01:00:00", id: 902, theses: ["메모리 가격이 반등한다"],
      invalidation: "재고가 두 분기 연속 늘어난다", verdicts: ["right"], review_on: "2026-05-01",
      reviewed_at: "2026-05-02T01:00:00", due: false,
    },
    { kind: "fill", at: "2026-01-10T01:00:00Z", side: "sell", shares: 10, price: 60000, currency: "KRW", after_pause: false },
  ],
};

describe("StockRecordView", () => {
  it("heads with the name, the holding and four counts", () => {
    render(<StockRecordView data={DATA} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("삼성전자");
    expect(screen.getByText(/^005930 · 보유 200주 · 평균가 72,000원$/)).toBeInTheDocument();
    const counts = screen.getByRole("region", { name: "기록 수" });
    expect(counts).toHaveTextContent("산 것 1 · 판 것 1");
    expect(counts).toHaveTextContent("그 뒤로 안 산 것 1");
  });

  it("groups by KST month, newest first, with each kind and the user's words", () => {
    render(<StockRecordView data={DATA} />);
    const months = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(months).toEqual([monthKey("2026-06-16T07:10:00Z"), monthKey("2026-02-01T01:00:00"), monthKey("2026-01-10T01:00:00Z")]);
    const june = screen.getByRole("region", { name: months[0]! });
    const kinds = within(june).getAllByRole("listitem").map((li) => li.getAttribute("data-kind"));
    expect(kinds).toEqual(["note", "fill", "pause"]);
    expect(june).toHaveTextContent("평단 근처에서 손이 근질거린다.");
    expect(june).toHaveTextContent("샀어요");
    expect(june).toHaveTextContent("50주 · 81,000원");
    expect(june).toHaveTextContent("멈춤 뒤");
    expect(june).toHaveTextContent("사기 전 멈춤");
    expect(june).toHaveTextContent("그 뒤로 사지 않음");
    expect(screen.getByText("팔았어요")).toBeInTheDocument();
    expect(screen.getByText("맞음")).toBeInTheDocument();
  });

  it("says an empty record plainly and still offers the two ways on", () => {
    render(
      <StockRecordView
        data={{
          ...DATA, holding: null, events: [],
          counts: { fills: 0, buys: 0, sells: 0, pauses: 0, not_taken: 0, research: 0, notes: 0 },
        }}
      />,
    );
    expect(screen.getByTestId("stock-record-empty")).toHaveTextContent("아직 없어요");
    expect(screen.getByText(/지금 보유하지 않음/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /이 종목 멈춤 시작/ })).toHaveAttribute("href", "/pre-trade?ticker=005930.KS");
    expect(screen.getByRole("link", { name: /리서치 쓰기/ })).toHaveAttribute("href", "/journal/research?ticker=005930.KS");
  });

  it("carries no score, grade or advice words", () => {
    render(<StockRecordView data={DATA} />);
    const text = screen.getByTestId("stock-record").textContent ?? "";
    for (const w of ["점수", "등급", "추천", "조언", "매수하세요", "매도하세요", "목표가"]) {
      expect(text).not.toContain(w);
    }
  });

  it("lays SEC filings in as facts with a link, the source and the after-release counts", () => {
    const data: StockRecordResponse = {
      ...DATA,
      ticker: "AAPL",
      name: "Apple",
      holding: null,
      counts: { ...DATA.counts, filings: 1 },
      filing_reaction: {
        earnings: 2, window_days: 3, buys_after: 1, sells_after: 0, timed_fills: 3, untimed_fills: 1,
      },
      events: [
        {
          kind: "filing", at: "2026-07-30T00:00:00", filed_on: "2026-07-30", form: "8-K", label: "실적 발표",
          earnings: true, source: "SEC EDGAR",
          url: "https://www.sec.gov/Archives/edgar/data/320193/000032019326000018/aapl-20260730.htm",
        },
        ...DATA.events,
      ],
    };
    render(<StockRecordView data={data} />);
    const row = document.querySelector('li[data-kind="filing"]') as HTMLElement;
    expect(within(row).getByText("실적 발표")).toBeTruthy();
    expect(within(row).getByText(/7월 30일/)).toBeTruthy();
    expect(within(row).getByText("공시")).toBeTruthy();
    const link = within(row).getByRole("link", { name: /8-K · 원문 보기/ });
    expect(link.getAttribute("href")).toContain("sec.gov/Archives");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
    expect(screen.getByTestId("filing-source").textContent).toContain("SEC EDGAR");
    const reaction = screen.getByTestId("filing-reaction").textContent ?? "";
    expect(reaction).toContain("실적 발표 2번");
    expect(reaction).toContain("산 것 1번");
    expect(reaction).toContain("판 것 0번");
    expect(reaction).toContain("날짜만 있는 체결 1건");
  });

  it("shows no filing lines when the record has none", () => {
    render(<StockRecordView data={DATA} />);
    expect(screen.queryByTestId("filing-source")).toBeNull();
    expect(screen.queryByTestId("filing-reaction")).toBeNull();
  });
});
