/**
 * 다시 찾기 URL helpers (lib/research.ts) — what the bar turns into on the
 * list URL. `since` is a KST calendar day, months back, clamped to month end.
 */
import { describe, expect, it } from "vitest";
import {
  EMPTY_RESEARCH_FILTERS,
  kstMonthsAgo,
  researchFilterQuery,
  researchFiltersActive,
} from "@/lib/research";

// 2026-10-27 08:00 UTC = 2026-10-27 17:00 KST.
const NOW = Date.UTC(2026, 9, 27, 8, 0);

describe("researchFilterQuery", () => {
  it("is empty with no filter on", () => {
    expect(researchFilterQuery(EMPTY_RESEARCH_FILTERS, NOW)).toBe("");
    expect(researchFiltersActive(EMPTY_RESEARCH_FILTERS)).toBe(false);
    expect(researchFiltersActive({ ...EMPTY_RESEARCH_FILTERS, q: "   " })).toBe(false);
  });

  it("carries words, chips and the period start", () => {
    const qs = researchFilterQuery(
      { q: "  HBM 공급 ", source: "none", status: "due", period: "3m" },
      NOW,
    );
    const p = new URLSearchParams(qs.slice(1));
    expect(qs.startsWith("&")).toBe(true);
    expect(p.get("q")).toBe("HBM 공급");
    expect(p.get("source")).toBe("none");
    expect(p.get("status")).toBe("due");
    expect(p.get("since")).toBe("2026-07-27");
  });

  it("caps the words at the server's 100 characters", () => {
    const qs = researchFilterQuery({ ...EMPTY_RESEARCH_FILTERS, q: "가".repeat(150) }, NOW);
    expect(new URLSearchParams(qs.slice(1)).get("q")).toHaveLength(100);
  });
});

describe("kstMonthsAgo", () => {
  it("uses the KST calendar day", () => {
    // 2026-10-31 16:00 UTC = 2026-11-01 01:00 KST.
    expect(kstMonthsAgo(1, Date.UTC(2026, 9, 31, 16, 0))).toBe("2026-10-01");
  });

  it("clamps to the month's last day and crosses years", () => {
    expect(kstMonthsAgo(1, Date.UTC(2026, 2, 31, 3, 0))).toBe("2026-02-28");
    expect(kstMonthsAgo(12, NOW)).toBe("2025-10-27");
    expect(kstMonthsAgo(3, Date.UTC(2026, 0, 15, 3, 0))).toBe("2025-10-15");
  });
});
