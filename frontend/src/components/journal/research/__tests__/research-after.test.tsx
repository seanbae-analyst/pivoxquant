/**
 * <ResearchAfter /> — before a note is scored, fill prices stay hidden (the
 * money seen first pulls the score); after scoring they show. The page says
 * nearness is not cause, and links to the whole stock record.
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import * as React from "react";
import { ResearchAfter } from "@/components/journal/research/research-after";
import type { ResearchNote, StockRecordEvent } from "@/lib/types";

const NOTE: ResearchNote = {
  id: 7, ticker: "005930.KS", name: "삼성전자", business: "", theses: ["메모리 가격이 반등한다"],
  invalidation: null, risk: null, numbers: null, info_source: null, surface: "journal",
  review_on: "2026-09-01", verdicts: [], review_note: null, reviewed_at: null,
  created_at: "2026-05-31T16:00:00", due: false, outcome: "open",
};
const EVENTS: StockRecordEvent[] = [
  { kind: "fill", at: "2026-06-10T02:00:00.000001", side: "buy", shares: 3, price: 71500, currency: "KRW", after_pause: true },
];

afterEach(cleanup);

describe("<ResearchAfter />", () => {
  it("hides fill prices until the note is scored", () => {
    render(<ResearchAfter note={NOTE} events={EVENTS} today="2026-10-27" />);
    expect(screen.getByTestId("after-price-locked")).toBeTruthy();
    expect(screen.getByTestId("after-fill-locked").textContent).toBe("3주");
    expect(screen.queryByText(/71,500/)).toBeNull();
    expect(screen.getByText("멈춤 뒤")).toBeTruthy();
    expect(screen.getByText(/거래의 이유였다는 뜻은 아니에요/)).toBeTruthy();
  });

  it("shows prices once scored", () => {
    render(
      <ResearchAfter note={{ ...NOTE, reviewed_at: "2026-09-02T03:00:00", verdicts: ["right"] }} events={EVENTS} today="2026-10-27" />,
    );
    expect(screen.queryByTestId("after-price-locked")).toBeNull();
    expect(screen.queryByTestId("after-fill-locked")).toBeNull();
    expect(screen.getByText(/71,500/)).toBeTruthy();
    expect(screen.getByText("채점함")).toBeTruthy();
  });

  it("says when nothing came after, and links to the whole stock record", () => {
    render(<ResearchAfter note={NOTE} events={[]} today="2026-10-27" />);
    expect(screen.getByTestId("research-after-empty")).toBeTruthy();
    expect(screen.getByRole("link", { name: /이 종목 기록 전체/ }).getAttribute("href")).toBe("/journal/stock/005930.KS");
  });
});
