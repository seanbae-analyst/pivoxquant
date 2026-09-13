/**
 * View-model suite for the sidebar record card — pure function, no DOM.
 *
 * Fixtures are shaped from the live GET /api/behavior/friction-outcome and
 * GET /api/pre-trade/list captures the journal suites already pin. The
 * clock is fixed so the seven-day strip is deterministic regardless of the
 * machine's zone — the card pins days to Asia/Seoul, like /journal.
 */
import { describe, expect, it } from "vitest";
import { buildRecordCardView } from "@/components/layout/sidebar-record-card";
import type { FrictionOutcomeResponse, PreTradeReflection } from "@/lib/types";

// 2026-09-13 18:00 KST == 09:00Z. Seoul "today" is 09-13.
const NOW = new Date("2026-09-13T09:00:00Z");

const OUTCOME_30D: FrictionOutcomeResponse = {
  ok: true,
  period: "30d",
  window_days: 30,
  stopped: { started: 12, proceeded: 6, cancelled: 5, open: 1 },
  cancelled_followthrough: {
    cancelled: 5,
    bought_later_anyway: 1,
    never_bought: 4,
    median_days_until_bought: 2,
  },
  realised: {
    with_friction: { n: 3, median_pct: null, mean_pct: null },
    without_friction: { n: 9, median_pct: -1.2, mean_pct: -0.4 },
    comparable: false,
    min_group_n: 5,
  },
  caveats: {
    not_randomised: true,
    attribution_window_days: 7,
    cooldown_seconds_currently: 0,
  },
  insufficient: false,
};

function reflection(
  id: number,
  iso: string,
  status: PreTradeReflection["status"],
  ticker = "AAPL",
  name: string | null = "Apple Inc.",
): PreTradeReflection {
  return {
    id,
    intended_ticker: ticker,
    intended_name: name,
    intended_side: null,
    intended_shares: null,
    rationale: "",
    devil_advocate_seen: null,
    market_volatility_at_request: null,
    cooldown_started_at: iso,
    cooldown_ends_at: iso,
    proceeded_at: status === "proceeded" ? iso : null,
    cancelled_at: status === "cancelled" ? iso : null,
    auto_extended_reason: null,
    observed_context: null,
    seconds_remaining: 0,
    status,
  };
}

describe("buildRecordCardView", () => {
  it("is the calm empty state when there is no record at all", () => {
    const v = buildRecordCardView(null, [], NOW);
    expect(v.hasAny).toBe(false);
    expect(v.counts).toBeNull();
    expect(v.rhythm).toEqual([false, false, false, false, false, false, false]);
    expect(v.recent).toEqual([]);
  });

  it("carries the three 30-day counts beside each other, never alone", () => {
    const v = buildRecordCardView(OUTCOME_30D, [], NOW);
    expect(v.counts).toEqual({ started: 12, proceeded: 6, cancelled: 5 });
    expect(v.hasAny).toBe(true);
  });

  it("treats a 404 soft-empty outcome as unavailable but keeps the feed", () => {
    const rows = [reflection(1, "2026-09-13T01:00:00Z", "proceeded")];
    const v = buildRecordCardView(null, rows, NOW);
    expect(v.counts).toBeNull();
    expect(v.hasAny).toBe(true);
    expect(v.recent).toHaveLength(1);
  });

  it("lights the seven-day strip on Seoul calendar days, oldest first", () => {
    const rows = [
      // 09-13 10:00 KST (01:00Z) → today
      reflection(3, "2026-09-13T01:00:00Z", "proceeded"),
      // 09-11 23:30 KST is 14:30Z on the 11th → the 11th, not the 12th
      reflection(2, "2026-09-11T14:30:00Z", "cancelled"),
      // naive backend stamp = UTC. 2026-09-06T20:00 UTC = 09-07 05:00 KST →
      // lands on the 7th, the oldest slot of the strip.
      reflection(1, "2026-09-06T20:00:00", "proceeded"),
    ];
    const v = buildRecordCardView(OUTCOME_30D, rows, NOW);
    // slots: 07 08 09 10 11 12 13
    expect(v.rhythm).toEqual([true, false, false, false, true, false, true]);
  });

  it("ignores records outside the seven-day strip for the rhythm", () => {
    const rows = [reflection(1, "2026-09-01T01:00:00Z", "proceeded")];
    const v = buildRecordCardView(OUTCOME_30D, rows, NOW);
    expect(v.rhythm.some(Boolean)).toBe(false);
    // …but they still count as a record for the empty-state gate.
    expect(v.hasAny).toBe(true);
    expect(v.recent).toHaveLength(1);
  });

  it("keeps the three newest rows in feed order with name and Seoul short date", () => {
    const rows = [
      reflection(4, "2026-09-13T01:00:00Z", "proceeded", "005930.KS", "삼성전자"),
      reflection(3, "2026-09-12T01:00:00Z", "cancelled", "AAPL", "Apple Inc."),
      reflection(2, "2026-09-11T01:00:00Z", "pending", "TSLA", null),
      reflection(1, "2026-09-10T01:00:00Z", "proceeded"),
    ];
    const v = buildRecordCardView(OUTCOME_30D, rows, NOW);
    expect(v.recent.map((r) => r.id)).toEqual([4, 3, 2]);
    expect(v.recent[0]).toMatchObject({ name: "삼성전자", date: "9.13", status: "proceeded" });
    expect(v.recent[1]).toMatchObject({ name: "Apple Inc.", date: "9.12", status: "cancelled" });
    // No backend name → the feed's own fallback (static seed or bare ticker).
    expect(v.recent[2].name.length).toBeGreaterThan(0);
    expect(v.recent[2].status).toBe("pending");
  });

  it("renders an empty date rather than throwing on a row with no timestamp", () => {
    const r = reflection(1, "2026-09-13T01:00:00Z", "ready");
    r.cooldown_started_at = null;
    r.cooldown_ends_at = null;
    const v = buildRecordCardView(OUTCOME_30D, [r], NOW);
    expect(v.recent[0].date).toBe("");
  });
});
