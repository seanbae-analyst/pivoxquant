import { describe, expect, it } from "vitest";
import {
  monthlyReportWillSend,
  nextMonthlySendDate,
} from "@/components/settings/v2/monthly-report-card";

describe("nextMonthlySendDate", () => {
  it("is the next 1st when mid-month (KST)", () => {
    expect(nextMonthlySendDate(new Date("2026-10-05T03:00:00Z"))).toBe("2026-11-01");
  });

  it("is today when it is the 1st before 08:30 KST", () => {
    // 2026-11-01 08:00 KST
    expect(nextMonthlySendDate(new Date("2026-10-31T23:00:00Z"))).toBe("2026-11-01");
  });

  it("is next month once 08:30 KST on the 1st has passed", () => {
    // 2026-11-01 09:00 KST
    expect(nextMonthlySendDate(new Date("2026-11-01T00:00:00Z"))).toBe("2026-12-01");
  });

  it("uses the KST date, not the UTC date", () => {
    // 2026-10-31 20:00 UTC = 2026-11-01 05:00 KST → still today's run
    expect(nextMonthlySendDate(new Date("2026-10-31T20:00:00Z"))).toBe("2026-11-01");
  });

  it("rolls over the year", () => {
    expect(nextMonthlySendDate(new Date("2026-12-15T00:00:00Z"))).toBe("2027-01-01");
  });
});

describe("monthlyReportWillSend", () => {
  it("is true only when all three are on", () => {
    expect(monthlyReportWillSend(true, true, true)).toBe(true);
  });

  it("is false as soon as any one is off, even while others load", () => {
    expect(monthlyReportWillSend(false, undefined, undefined)).toBe(false);
    expect(monthlyReportWillSend(true, false, true)).toBe(false);
    expect(monthlyReportWillSend(true, true, false)).toBe(false);
  });

  it("is unknown while any is still loading and none is off", () => {
    expect(monthlyReportWillSend(true, undefined, true)).toBeUndefined();
  });
});
