import { describe, expect, it } from "vitest";
import { fmtKstClock } from "../signal-card";
import { fmtWhen } from "@/components/home/v2/earnings-pre-brief-card";
import { absoluteDate } from "@/app/(dashboard)/journal/page";

/**
 * F#1/#2/#4 (2026-05-26): time/date helpers that render a "KST" / ko-KR
 * Korea-anchored label must pin the wall clock to Asia/Seoul, NOT the
 * browser-local zone. These assertions use explicit UTC instants whose KST
 * wall clock differs from UTC (and rolls the calendar day), so the expected
 * output is host-timezone-independent: if the helper omitted
 * `timeZone: "Asia/Seoul"`, a non-KST CI host would produce different digits.
 *
 * KST = UTC+9.
 *   2026-05-22T13:30:00Z → 2026-05-22 22:30 KST  (same day, +9h)
 *   2026-05-22T20:00:00Z → 2026-05-23 05:00 KST  (rolls to next day)
 */

describe("fmtKstClock (signal-card, F#1)", () => {
  it("renders the KST wall clock with a trailing label", () => {
    expect(fmtKstClock("2026-05-22T13:30:00Z")).toBe("22:30 KST");
  });

  it("rolls over the day boundary correctly (late UTC → next KST day)", () => {
    // 20:00Z = 05:00 KST next day. Local-time getHours() on a UTC host would
    // have rendered "20:00 KST" here — wrong.
    expect(fmtKstClock("2026-05-22T20:00:00Z")).toBe("05:00 KST");
  });

  it("returns the em-dash sentinel for invalid/missing input", () => {
    expect(fmtKstClock(null)).toBe("—");
    expect(fmtKstClock("not-a-date")).toBe("—");
  });
});

describe("fmtWhen (earnings-pre-brief-card, F#2)", () => {
  it("renders a ko-KR KST datetime", () => {
    // "5월 22일 22:30" — KST wall clock for 13:30Z.
    const out = fmtWhen("2026-05-22T13:30:00Z");
    expect(out).toContain("5월 22일");
    expect(out).toContain("22:30");
  });

  it("rolls to the next KST calendar day for late-UTC instants", () => {
    const out = fmtWhen("2026-05-22T20:00:00Z");
    expect(out).toContain("5월 23일");
    expect(out).toContain("05:00");
  });

  it("returns the em-dash sentinel for invalid input", () => {
    expect(fmtWhen("nope")).toBe("—");
  });
});

describe("absoluteDate (journal, F#4)", () => {
  it("renders the KST calendar date for a UTC-anchored timestamp", () => {
    // Naive timestamp (no Z) is treated as UTC by the helper's guard, then
    // converted to KST. 20:00Z → 2026-05-23 in KST, so the year/month/day
    // must reflect the rolled KST day.
    const out = absoluteDate("2026-05-22T20:00:00");
    expect(out).toContain("2026년");
    expect(out).toContain("5월 23일");
  });

  it("keeps a same-day instant on the same KST date", () => {
    const out = absoluteDate("2026-05-22T13:30:00Z");
    expect(out).toContain("5월 22일");
  });

  it("returns empty string for missing input", () => {
    expect(absoluteDate(null)).toBe("");
  });
});
