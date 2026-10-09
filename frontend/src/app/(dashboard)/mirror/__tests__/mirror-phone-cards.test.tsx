/**
 * /mirror on a phone — swipeable story cards (CEO 2026-10-09 "앱처럼").
 *
 * What must hold:
 *   - phone + ready → PhonePager in dots mode, cards in the page's own order:
 *     오늘의 거울 → 선언 vs 관찰 → 간극 → 한 가지만;
 *   - the 간극 card is dropped when there is no gap and no drift;
 *   - nothing is lost from the desktop column (sentence, radar, every gap
 *     row, drift, the 멈춤 link) and nothing is added that the column does
 *     not say (no score, grade or type label);
 *   - skeleton / error / empty states stay; desktop keeps the column.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";

import type { MirrorHomeResponse } from "@/lib/types";

const state = vi.hoisted(() => ({
  phone: true,
  swr: { data: null, isLoading: false, error: null } as {
    data: unknown;
    isLoading: boolean;
    error: unknown;
  },
}));

vi.mock("@/lib/auth", () => ({ useAuth: () => ({ loading: false }) }));
vi.mock("@/lib/hooks", () => ({ useMirrorHome: () => state.swr }));
vi.mock("@/lib/use-phone", () => ({ useIsPhone: () => state.phone }));
vi.mock("motion/react", () => ({ useReducedMotion: () => false }));

import MirrorPage from "@/app/(dashboard)/mirror/page";

const payload: MirrorHomeResponse = {
  ok: true,
  stage: "observed",
  declared: { source: "self" },
  observed: { trade_count: 12 },
  gap: [
    { key: "holding_period", label: "평균 보유기간", direction: "down", delta: -0.3, declared: 0.8, observed: 0.5 },
    { key: "turnover", label: "매매 회전율", direction: "up", delta: 0.2, declared: 0.2, observed: 0.4 },
    { key: "concentration", label: "집중도", direction: "up", delta: 0.12, declared: 0.4, observed: 0.6 },
    { key: "sector_diversity", label: "섹터 분산", direction: "down", delta: -0.1, declared: 0.6, observed: 0.5 },
  ],
  drift: { available: true, descriptor: "영역 이동 관찰" },
  radar: {
    keys: ["holding_period", "turnover", "concentration", "sector_diversity"],
    labels: ["평균 보유기간", "매매 회전율", "집중도", "섹터 분산"],
    declared: [0.8, 0.2, 0.4, 0.6],
    declared_axes: ["holding_period", "turnover", "concentration", "sector_diversity"],
    observed: [0.5, 0.4, 0.6, 0.5],
    observed_axes: ["holding_period", "turnover", "concentration"],
  },
};

function setData(data: unknown, extra: Partial<typeof state.swr> = {}) {
  state.swr = { data, isLoading: false, error: null, ...extra };
}

afterEach(() => {
  cleanup();
  state.phone = true;
  setData(null);
});

describe("/mirror phone — story cards", () => {
  it("lays the ready mirror out as four dot-navigated cards in reading order", () => {
    setData(payload);
    render(<MirrorPage />);
    expect(screen.getByTestId("phone-pager")).toBeInTheDocument();
    expect(screen.queryByTestId("phone-pager-tabs")).toBeNull();
    const tabs = within(screen.getByRole("tablist", { name: "거울 카드" })).getAllByRole("tab");
    expect(tabs.map((t) => t.getAttribute("aria-label"))).toEqual([
      "오늘의 거울",
      "선언 vs 관찰",
      "간극",
      "한 가지만",
    ]);
    expect(tabs[0]).toHaveAttribute("aria-selected", "true");
  });

  it("keeps every block of the desktop column, one per card", () => {
    setData(payload);
    render(<MirrorPage />);
    const today = screen.getByTestId("phone-page-today");
    expect(within(today).getByRole("heading", { level: 1 }).textContent).toBe(
      "선언과 가장 크게 갈라진 곳: 평균 보유기간 — 최근 30일은 선언보다 짧게 관찰됐어요.",
    );

    const radar = screen.getByTestId("phone-page-radar");
    expect(within(radar).getByText("선언 vs 관찰")).toBeInTheDocument();
    expect(within(radar).getByRole("img")).toBeInTheDocument();
    expect(within(radar).getByText("선언(설문)")).toBeInTheDocument();

    // Every gap row the backend sent — not only the desktop's top three.
    const gap = screen.getByTestId("phone-page-gap");
    const rows = within(gap).getAllByRole("listitem");
    expect(rows.map((r) => r.textContent)).toEqual([
      "평균 보유기간선언보다 짧게↓30%p",
      "매매 회전율선언보다 높게↑20%p",
      "집중도선언보다 높게↑12%p",
      "섹터 분산선언보다 낮게↓10%p",
    ]);
    expect(within(gap).getByText("영역 이동 관찰")).toBeInTheDocument();

    const one = screen.getByTestId("phone-page-one-thing");
    expect(within(one).getByRole("link", { name: /멈춤으로 가기/ })).toHaveAttribute(
      "href",
      "/pre-trade",
    );
  });

  it("drops the 간극 card when there is neither a gap nor a drift", () => {
    setData({ ...payload, gap: [], drift: { available: false, descriptor: null } });
    render(<MirrorPage />);
    const labels = screen.getAllByRole("tab").map((t) => t.getAttribute("aria-label"));
    expect(labels).toEqual(["오늘의 거울", "선언 vs 관찰", "한 가지만"]);
    expect(screen.queryByTestId("phone-page-gap")).toBeNull();
  });

  it("keeps the 간극 card for a drift alone", () => {
    setData({ ...payload, gap: [] });
    render(<MirrorPage />);
    const gap = screen.getByTestId("phone-page-gap");
    expect(within(gap).queryAllByRole("listitem")).toHaveLength(0);
    expect(within(gap).getByText("영역 이동 관찰")).toBeInTheDocument();
  });

  it("names no type, grade or score on any card, even from a stale payload", () => {
    const stale = {
      ...payload,
      declared: { source: "centroid", label: "성장형", tagline: "x" },
      observed: { trade_count: 12, label: "균형형", bucket_changed: true },
    };
    setData(stale);
    const { container } = render(<MirrorPage />);
    const text = container.textContent ?? "";
    // Negative assertions: these words must NOT appear. // legal-ok
    const banned = ["성장형", "균형형", "수익형", "정합도", "점수", "등급", "추천", "조언"]; // legal-ok
    for (const w of banned) {
      expect(text).not.toContain(w);
    }
    expect(text).not.toMatch(/\b(BUY|SELL|HOLD)\b/); // legal-ok
    expect(text).not.toMatch(/score|grade/i);
  });

  it("a failed revalidation keeps the cards and shows the error line", () => {
    setData(payload, { error: new Error("HTTP 500") });
    render(<MirrorPage />);
    expect(screen.getByTestId("phone-pager")).toBeInTheDocument();
    expect(screen.getByText(/거울을 불러오지 못했어요/)).toBeInTheDocument();
  });

  it("keeps skeleton, error and empty states (no pager) on a phone", () => {
    setData(undefined, { isLoading: true });
    const { container, unmount } = render(<MirrorPage />);
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    expect(screen.queryByTestId("phone-pager")).toBeNull();
    unmount();

    setData(undefined, { error: new Error("HTTP 500") });
    render(<MirrorPage />);
    expect(screen.getByText(/거울을 불러오지 못했어요/)).toBeInTheDocument();
    expect(screen.queryByTestId("phone-pager")).toBeNull();
    cleanup();

    setData({});
    render(<MirrorPage />);
    expect(screen.getByText("아직 비출 기록이 없어요.")).toBeInTheDocument();
    expect(screen.queryByTestId("phone-pager")).toBeNull();
  });

  it("desktop keeps the single column — no pager", () => {
    state.phone = false;
    setData(payload);
    render(<MirrorPage />);
    expect(screen.queryByTestId("phone-pager")).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.getByTestId("mirror-radar-panel")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /멈춤으로 가기/ })).toBeInTheDocument();
  });

  it("sources mount no DisclaimerBanner and use no italic", () => {
    const root = join(__dirname, "..", "..", "..", "..");
    for (const rel of [
      "app/(dashboard)/mirror/page.tsx",
      "components/mirror/mirror-phone-cards.tsx",
      "components/mirror/mirror-radar-panel.tsx",
      "components/mirror/mirror-headline.tsx",
    ]) {
      const src = readFileSync(join(root, rel), "utf8");
      expect(src, rel).not.toMatch(/<DisclaimerBanner/);
      // Comments say "No italic"; only a class or a style may not.
      expect(src, rel).not.toMatch(/className=[^>]*(?<![-\w])italic\b/);
      expect(src, rel).not.toMatch(/fontStyle:\s*["']italic/);
    }
  });
});
