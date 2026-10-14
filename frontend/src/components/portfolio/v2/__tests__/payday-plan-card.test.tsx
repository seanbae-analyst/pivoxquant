/**
 * <PaydayPlanCard /> — 월급날 배분 on /portfolio (2026-10-14).
 *
 * The legal premise of this card is that no amount leaves the browser. The
 * tests run the real SWR hooks against a recorded `fetch` and pin that every
 * request is a GET of the user's own trades or the FX rate, and that no typed
 * amount appears in any request — while the plan lands in localStorage.
 * Also: payday → form → plan → comparison flow, the look-back self-report,
 * "이 기기에서 지우기", and copy without trade verbs, advice or ratios.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import * as React from "react";
import { SWRConfig } from "swr";

vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { id: 7 } }) }));

import { PaydayPlanCard } from "@/components/portfolio/v2/payday-plan-card";
import { loadStore, saveStore, storageKey, type PaydayStore } from "@/lib/payday-plan";

type Call = { url: string; method: string; body: unknown };
let calls: Call[] = [];
let trades: unknown[] = [];

beforeEach(() => {
  calls = [];
  trades = [];
  // 2026-10-14 03:00 UTC = 12:00 KST → with payday 25 the cycle is 9/25–10/25.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-10-14T03:00:00Z"));
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push({ url, method: (init?.method ?? "GET").toUpperCase(), body: init?.body });
      const body = url.includes("/api/portfolio/trades")
        ? { trades }
        : url.includes("/api/market/fx")
          ? { ok: true, usd_krw: 1_400 }
          : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

function renderCard() {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <PaydayPlanCard />
    </SWRConfig>,
  );
}

function seed(store: PaydayStore) {
  saveStore(7, store);
}

const PLAN_OCT: PaydayStore = {
  v: 1,
  payday: 25,
  cycles: [
    {
      start: "2026-09-25",
      income: 3_500_000,
      parts: { living: 1_500_000, saving: 500_000, invest: 1_000_000, other: 200_000 },
      review: {},
      savedAt: "2026-09-25T00:00:00Z",
    },
  ],
};

describe("PaydayPlanCard", () => {
  it("starts by asking for the payday and keeps it on this device", async () => {
    renderCard();
    const card = await screen.findByTestId("payday-plan-card");
    expect(card).toHaveTextContent("월급날 배분");
    expect(card).toHaveTextContent("이 기기(브라우저)에만 저장되고 서버로 보내지 않아요");
    fireEvent.change(screen.getByLabelText("매월"), { target: { value: "25" } });
    fireEvent.click(screen.getByRole("button", { name: "월급날로 정하기" }));
    expect(await screen.findByTestId("payday-plan-form")).toHaveTextContent("9월 25일 ~ 10월 24일");
    expect(loadStore(7).payday).toBe(25);
  });

  it("saving a split stores it locally and shows the money not yet given a part", async () => {
    seed({ v: 1, payday: 25, cycles: [] });
    renderCard();
    await screen.findByTestId("payday-plan-form");
    fireEvent.change(screen.getByLabelText(/이번에 들어온 돈/), { target: { value: "3500000" } });
    fireEvent.change(screen.getByLabelText("생활비"), { target: { value: "1500000" } });
    fireEvent.change(screen.getByLabelText("투자"), { target: { value: "1,000,000" } });
    expect(screen.getByTestId("payday-unassigned")).toHaveTextContent("아직 정하지 않은 돈 1,000,000원");
    fireEvent.click(screen.getByRole("button", { name: "이 배분 저장" }));
    await screen.findByTestId("payday-plan-current");
    const saved = loadStore(7).cycles[0];
    expect(saved.start).toBe("2026-09-25");
    expect(saved.income).toBe(3_500_000);
    expect(saved.parts).toEqual({ living: 1_500_000, saving: null, invest: 1_000_000, other: null });
  });

  it("never sends an amount anywhere — GETs of trades and FX only", async () => {
    seed({ v: 1, payday: 25, cycles: [] });
    renderCard();
    await screen.findByTestId("payday-plan-form");
    fireEvent.change(screen.getByLabelText(/이번에 들어온 돈/), { target: { value: "3456789" } });
    fireEvent.change(screen.getByLabelText("투자"), { target: { value: "987654" } });
    fireEvent.click(screen.getByRole("button", { name: "이 배분 저장" }));
    await screen.findByTestId("payday-invest-compare");
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    for (const c of calls) {
      expect(c.method).toBe("GET");
      expect(c.body).toBeUndefined();
      expect(c.url).toMatch(/\/api\/(portfolio\/trades|market\/fx)/);
      for (const typed of ["3456789", "3,456,789", "987654", "987,654"]) {
        expect(c.url).not.toContain(typed);
      }
    }
    expect(window.localStorage.getItem(storageKey(7))).toContain("987654");
  });

  it("sets the investment part next to what this cycle's fills put in", async () => {
    trades = [
      { date: "2026-10-02", side: "Bought", total: 900_000, currency: "KRW", source: null },
      { date: "2026-10-06", side: "Bought", total: 300, currency: "USD", source: null },
      { date: "2026-10-07", side: "Bought", total: 5_000_000, currency: "KRW", source: "holding_seed" },
    ];
    seed(PLAN_OCT);
    renderCard();
    const cmp = await screen.findByTestId("payday-invest-compare");
    await waitFor(() => expect(cmp).toHaveTextContent("약 1,320,000원"));
    expect(cmp).toHaveTextContent("투자 몫 1,000,000원");
    expect(cmp).toHaveTextContent("몫보다 많음");
    expect(cmp).toHaveTextContent("오늘 환율로 환산");
  });

  it("within the investment part, says nothing about it", async () => {
    trades = [{ date: "2026-10-02", side: "Bought", total: 400_000, currency: "KRW", source: null }];
    seed(PLAN_OCT);
    renderCard();
    const cmp = await screen.findByTestId("payday-invest-compare");
    await waitFor(() => expect(cmp).toHaveTextContent("약 400,000원"));
    expect(cmp).not.toHaveTextContent("몫보다 많음");
  });

  it("at the next payday asks how the other parts went, and keeps the answer locally", async () => {
    vi.setSystemTime(new Date("2026-10-26T03:00:00Z")); // new cycle 10/25 – 11/25
    seed(PLAN_OCT);
    renderCard();
    const review = await screen.findByTestId("payday-review");
    fireEvent.click(within(within(review).getByRole("group", { name: "생활비 돌아보기" })).getByRole("button", { name: "더" }));
    fireEvent.click(within(within(review).getByRole("group", { name: "저축 돌아보기" })).getByRole("button", { name: "계획대로" }));
    fireEvent.click(screen.getByRole("button", { name: "돌아보기 저장" }));
    await waitFor(() => expect(loadStore(7).cycles[0].review).toEqual({ living: "more", saving: "as_planned" }));
    // The new cycle's form offers last cycle's split to start from.
    expect(screen.getByTestId("payday-plan-form")).toHaveTextContent("10월 25일 ~ 11월 24일");
    fireEvent.click(screen.getByRole("button", { name: "지난 배분 그대로 가져오기" }));
    expect(screen.getByLabelText("투자")).toHaveValue("1,000,000");
  });

  it("'이 기기에서 지우기' removes everything stored for this user", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    seed(PLAN_OCT);
    renderCard();
    await screen.findByTestId("payday-plan-current");
    fireEvent.click(screen.getByRole("button", { name: "이 기기에서 지우기" }));
    expect(window.localStorage.getItem(storageKey(7))).toBeNull();
    expect(await screen.findByRole("button", { name: "월급날로 정하기" })).toBeInTheDocument();
  });

  it("copy carries no trade verbs, advice, ratios or targets", async () => {
    trades = [{ date: "2026-10-02", side: "Bought", total: 1_900_000, currency: "KRW", source: null }];
    seed(PLAN_OCT);
    renderCard();
    const cmp = await screen.findByTestId("payday-invest-compare");
    await waitFor(() => expect(cmp).toHaveTextContent("몫보다 많음"));
    const text = screen.getByTestId("payday-plan-card").textContent ?? "";
    for (const word of ["매수", "매도", "추천", "조언", "권장", "적정", "목표", "지키", "줄이세요", "과소비", "%"]) {
      expect(text).not.toContain(word);
    }
  });
});
