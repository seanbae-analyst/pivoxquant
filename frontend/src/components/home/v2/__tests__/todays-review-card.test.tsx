/**
 * TodaysReviewCard (record-as-spine Phase 3) — contracts:
 *   - empty journal / loading / error → renders NOTHING (a new user's home
 *     must stay byte-identical to the pre-Phase-3 page)
 *   - with a reflection → quotes the user's own rationale + shows the
 *     Phase-2 observed-context chip, links to /journal
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mockJournal = vi.fn();
vi.mock("@/lib/hooks", () => ({
  usePreTradeJournal: (...args: unknown[]) => mockJournal(...args),
}));
vi.mock("@/lib/locale", () => ({
  useLocale: () => ({ locale: "ko" }),
}));

import { TodaysReviewCard } from "@/components/home/v2/todays-review-card";

const REFLECTION = {
  id: 1,
  intended_ticker: "AAPL",
  intended_name: "Apple Inc.",
  intended_side: "BUY",
  intended_shares: 10,
  rationale: "실적 모멘텀 확인 후 분할 진입 계획.",
  devil_advocate_seen: null,
  market_volatility_at_request: null,
  cooldown_started_at: "2026-06-10T01:00:00",
  cooldown_ends_at: "2026-06-10T01:00:00",
  proceeded_at: "2026-06-10T01:00:05",
  cancelled_at: null,
  auto_extended_reason: null,
  observed_context: { signal: "NEUTRAL", score: 61.8, vix: 18.2 },
  seconds_remaining: 0,
  status: "proceeded",
};

describe("TodaysReviewCard", () => {
  it("renders nothing while loading / on error / when the journal is empty", () => {
    for (const state of [
      { reflections: [], isLoading: true, error: undefined },
      { reflections: [], isLoading: false, error: new Error("x") },
      { reflections: [], isLoading: false, error: undefined },
    ]) {
      mockJournal.mockReturnValue(state);
      const { container, unmount } = render(<TodaysReviewCard />);
      expect(container.innerHTML).toBe("");
      unmount();
    }
  });

  it("quotes the latest reflection with its observed-context chip", () => {
    mockJournal.mockReturnValue({
      reflections: [REFLECTION],
      isLoading: false,
      error: undefined,
    });
    render(<TodaysReviewCard />);
    const card = screen.getByTestId("todays-review");
    expect(card.getAttribute("href")).toBe("/journal");
    expect(card.textContent).toContain("실적 모멘텀 확인 후 분할 진입 계획.");
    expect(card.textContent).toContain("Apple Inc.");
    expect(card.textContent).toContain("NEUTRAL 62"); // rounded score
    expect(card.textContent).toContain("VIX 18.2");
    // §17: the side wire token must never render raw.
    expect(card.textContent).not.toMatch(/\bBUY\b/);
  });
});
