import { describe, it, expect } from "vitest";
import {
  fmtUsd,
  fmtKrw,
  fmtPct,
  fmtMoneySigned,
  fmtMoneyCompact,
  displayTicker,
  fmtPct1,
  fmtPctUnsigned,
  fmtKrwAbbrev,
  fmtUsdPlain,
} from "@/lib/format";

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

describe("fmtMoneySigned", () => {
  it("prefixes + for positives (USD)", () => {
    expect(fmtMoneySigned(1234.56, "USD")).toBe("+$1,235");
    expect(fmtMoneySigned(12.34, "USD")).toBe("+$12.34");
  });
  it("prefixes U+2212 minus for negatives (USD)", () => {
    expect(fmtMoneySigned(-1234, "USD")).toBe("−$1,234");
    expect(fmtMoneySigned(-12.34, "USD")).toBe("−$12.34");
  });
  it("prefixes + / − for KRW (rounded, KR locale)", () => {
    expect(fmtMoneySigned(123456, "KRW")).toBe("+₩123,456");
    expect(fmtMoneySigned(-123456, "KRW")).toBe("−₩123,456");
  });
  it("renders zero without sign", () => {
    expect(fmtMoneySigned(0, "USD")).toBe("$0.00");
    expect(fmtMoneySigned(0, "KRW")).toBe("₩0");
  });
  it("handles null and NaN", () => {
    expect(fmtMoneySigned(null, "USD")).toBe("$0.00");
    expect(fmtMoneySigned(NaN, "USD")).toBe("$—");
    expect(fmtMoneySigned(NaN, "KRW")).toBe("₩—");
  });
});

describe("fmtMoneyCompact", () => {
  it("USD: K/M/B/T scaling", () => {
    expect(fmtMoneyCompact(1234, "USD")).toBe("$1.2K");
    expect(fmtMoneyCompact(1_234_567, "USD")).toBe("$1.2M");
    expect(fmtMoneyCompact(2_300_000_000, "USD")).toBe("$2.3B");
    expect(fmtMoneyCompact(4_500_000_000_000, "USD")).toBe("$4.5T");
  });
  it("USD: under 1K falls back to fmtUsd", () => {
    expect(fmtMoneyCompact(12.34, "USD")).toBe("$12.34");
  });
  it("KRW: 만 / 억 / 조 myriad scaling", () => {
    expect(fmtMoneyCompact(12_345, "KRW")).toBe("₩1.2만");
    expect(fmtMoneyCompact(120_000_000, "KRW")).toBe("₩1.2억");
    expect(fmtMoneyCompact(4_500_000_000_000, "KRW")).toBe("₩4.5조");
  });
  it("KRW: under 1만 falls back to fmtKrw", () => {
    expect(fmtMoneyCompact(1234, "KRW")).toBe("₩1,234");
  });
  it("preserves sign for negatives", () => {
    expect(fmtMoneyCompact(-1_234_567, "USD")).toBe("-$1.2M");
    expect(fmtMoneyCompact(-120_000_000, "KRW")).toBe("-₩1.2억");
  });
  it("handles null / NaN", () => {
    expect(fmtMoneyCompact(null, "USD")).toBe("$0.00");
    expect(fmtMoneyCompact(NaN, "KRW")).toBe("₩—");
  });
});

describe("displayTicker", () => {
  it("prefers explicit backend name", () => {
    expect(displayTicker("005930.KS", "삼성전자")).toBe("삼성전자");
    expect(displayTicker("AAPL", "Apple Inc.")).toBe("Apple Inc.");
  });
  it("falls back to seed when name absent", () => {
    expect(displayTicker("005930.KS")).toBe("삼성전자");
    expect(displayTicker("AAPL")).toBe("Apple");
  });
  it("strips KS/KQ/KRX/KR suffix for unseeded codes", () => {
    expect(displayTicker("999999.KS")).toBe("999999");
    expect(displayTicker("999999.KQ")).toBe("999999");
  });
  it("ignores backend name that just echoes the ticker", () => {
    expect(displayTicker("AAPL", "AAPL")).toBe("Apple");
    expect(displayTicker("005930.KS", "005930")).toBe("삼성전자");
  });
  it("handles null / empty input", () => {
    expect(displayTicker(null)).toBe("");
    expect(displayTicker(undefined)).toBe("");
    expect(displayTicker("", "삼성전자")).toBe("삼성전자");
  });
});

describe("fmtPct1", () => {
  it("forces + sign on non-negative, 1dp default", () => {
    expect(fmtPct1(12.345)).toBe("+12.3%");
    expect(fmtPct1(0)).toBe("+0.0%");
  });
  it("renders negatives with the - that toFixed emits", () => {
    expect(fmtPct1(-5)).toBe("-5.0%");
    expect(fmtPct1(-12.34)).toBe("-12.3%");
  });
  it("honours custom precision", () => {
    expect(fmtPct1(12.345, 2)).toBe("+12.35%");
    expect(fmtPct1(12.3, 0)).toBe("+12%");
  });
  it('returns "—" for null / undefined / NaN (NOT "+0.0%")', () => {
    expect(fmtPct1(null)).toBe("—");
    expect(fmtPct1(undefined)).toBe("—");
    expect(fmtPct1(NaN)).toBe("—");
    expect(fmtPct1(Infinity)).toBe("—");
  });
});

describe("fmtPctUnsigned", () => {
  it("suppresses + for non-negative, keeps - for negative", () => {
    expect(fmtPctUnsigned(23.4)).toBe("23.4%");
    expect(fmtPctUnsigned(0)).toBe("0.0%");
    expect(fmtPctUnsigned(-5, 2)).toBe("-5.00%");
  });
  it("honours custom precision", () => {
    expect(fmtPctUnsigned(23.456, 2)).toBe("23.46%");
    expect(fmtPctUnsigned(23.4, 0)).toBe("23%");
  });
  it('returns "—" for null / NaN', () => {
    expect(fmtPctUnsigned(null)).toBe("—");
    expect(fmtPctUnsigned(NaN)).toBe("—");
  });
});

describe("fmtKrwAbbrev", () => {
  it("scales to 조 / 억 / 만 with default precision (1/1/0)", () => {
    expect(fmtKrwAbbrev(4_500_000_000_000)).toBe("₩4.5조");
    expect(fmtKrwAbbrev(120_000_000)).toBe("₩1.2억");
    expect(fmtKrwAbbrev(34_000_000)).toBe("₩3,400만");
    expect(fmtKrwAbbrev(1234)).toBe("₩1,234");
  });
  it("honours per-scale dp overrides", () => {
    expect(fmtKrwAbbrev(123_000_000, { dpEok: 2 })).toBe("₩1.23억");
    expect(fmtKrwAbbrev(34_500_000, { dpMan: 1 })).toBe("₩3,450.0만");
    expect(fmtKrwAbbrev(4_567_000_000_000, { dpJo: 2 })).toBe("₩4.57조");
  });
  it("prefixes - for negatives, no + for positives", () => {
    expect(fmtKrwAbbrev(-120_000_000)).toBe("-₩1.2억");
    expect(fmtKrwAbbrev(120_000_000)).toBe("₩1.2억");
  });
  it('returns "₩—" for null / NaN', () => {
    expect(fmtKrwAbbrev(null)).toBe("₩—");
    expect(fmtKrwAbbrev(NaN)).toBe("₩—");
  });
});

describe("fmtUsdPlain", () => {
  it("renders $ + value with deterministic precision (default 0dp)", () => {
    expect(fmtUsdPlain(1234)).toBe("$1,234");
    expect(fmtUsdPlain(12.34)).toBe("$12");
    expect(fmtUsdPlain(12.34, 2)).toBe("$12.34");
  });
  it("does NOT auto-flip precision at 1000 (unlike fmtUsd)", () => {
    expect(fmtUsdPlain(12, 2)).toBe("$12.00");
    expect(fmtUsdPlain(1234, 2)).toBe("$1,234.00");
  });
  it("prefixes - for negatives", () => {
    expect(fmtUsdPlain(-1234)).toBe("-$1,234");
    expect(fmtUsdPlain(-12.34, 2)).toBe("-$12.34");
  });
  it('returns "$—" for null / NaN', () => {
    expect(fmtUsdPlain(null)).toBe("$—");
    expect(fmtUsdPlain(NaN)).toBe("$—");
  });
});
