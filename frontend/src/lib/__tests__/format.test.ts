import { describe, it, expect } from "vitest";
import { fmtUsd, fmtKrw, fmtPct } from "@/lib/format";

describe("format", () => {
  it("fmtUsd renders $ + value (rounded above 1000)", () => {
    expect(fmtUsd(1234.56)).toBe("$1,235");
    expect(fmtUsd(12.34)).toBe("$12.34");
  });

  it("fmtUsd handles null/NaN", () => {
    expect(fmtUsd(null)).toBe("$0.00");
    expect(fmtUsd(NaN)).toBe("$—");
  });

  it("fmtKrw rounds + KR locale", () => {
    expect(fmtKrw(1234567)).toBe("₩1,234,567");
  });

  it("fmtPct prefixes sign + 2 decimals (n is already a percentage)", () => {
    expect(fmtPct(12.3)).toBe("+12.30%");
    expect(fmtPct(-5)).toBe("-5.00%");
    expect(fmtPct(0)).toBe("+0.00%");
  });
});
