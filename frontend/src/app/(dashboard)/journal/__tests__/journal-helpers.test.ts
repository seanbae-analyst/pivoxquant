import { describe, it, expect } from "vitest";
import {
  entryTimestamp,
  absoluteDate,
  statusKind,
} from "@/app/(dashboard)/journal/page";
import type { PreTradeReflection } from "@/lib/types";

// Pure-helper coverage for the decision journal feed (previously untested).

function mk(partial: Partial<PreTradeReflection>): PreTradeReflection {
  // Test fixture — only the timestamp/status fields the helpers read matter;
  // cast through `unknown` so we don't have to stub every required field.
  return {
    id: 1,
    ticker: "AAPL",
    status: "ready",
    proceeded_at: null,
    cancelled_at: null,
    cooldown_started_at: null,
    ...partial,
  } as unknown as PreTradeReflection;
}

describe("entryTimestamp", () => {
  it("prefers proceeded_at, then cancelled_at, then cooldown_started_at", () => {
    expect(
      entryTimestamp(
        mk({
          proceeded_at: "2026-05-03",
          cancelled_at: "2026-05-02",
          cooldown_started_at: "2026-05-01",
        }),
      ),
    ).toBe("2026-05-03");
    expect(
      entryTimestamp(mk({ cancelled_at: "2026-05-02", cooldown_started_at: "2026-05-01" })),
    ).toBe("2026-05-02");
    expect(entryTimestamp(mk({ cooldown_started_at: "2026-05-01" }))).toBe("2026-05-01");
  });

  it("returns null when no timestamp present", () => {
    expect(entryTimestamp(mk({}))).toBeNull();
  });
});

describe("absoluteDate", () => {
  it("returns '' for null/empty", () => {
    expect(absoluteDate(null)).toBe("");
    expect(absoluteDate("")).toBe("");
  });

  it("returns '' for an unparseable string", () => {
    expect(absoluteDate("not-a-date")).toBe("");
  });

  it("treats a naive (no-offset) timestamp as UTC", () => {
    // 2026-05-03T20:00 UTC → 2026-05-04 05:00 KST → must render the 4th.
    const naive = absoluteDate("2026-05-03T20:00:00");
    expect(naive).toContain("4");
    expect(naive).toContain("2026");
  });

  it("respects an explicit Z / offset (no double-append)", () => {
    expect(absoluteDate("2026-05-03T20:00:00Z")).toContain("4"); // KST next day
    expect(absoluteDate("2026-05-03T20:00:00+09:00")).toContain("3");
  });
});

describe("statusKind", () => {
  it("maps proceeded / cancelled, else pending", () => {
    expect(statusKind(mk({ status: "proceeded" }))).toBe("proceeded");
    expect(statusKind(mk({ status: "cancelled" }))).toBe("cancelled");
    expect(statusKind(mk({ status: "ready" }))).toBe("pending");
    expect(statusKind(mk({ status: "pending" }))).toBe("pending");
  });
});
