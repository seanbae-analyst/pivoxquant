import { describe, expect, it } from "vitest";
import { fill, fmt, money, signed } from "@/lib/reports";

describe("report formatters (mirror the PDF's Jinja filters)", () => {
  it("fmt: thousands separators, em dash for missing", () => {
    expect(fmt(1949000)).toBe("1,949,000");
    expect(fmt(23, 1)).toBe("23.0");
    expect(fmt(null)).toBe("—");
    expect(fmt("abc")).toBe("—");
  });

  it("signed: keeps the sign of a loss", () => {
    expect(signed(6.2)).toBe("+6.20");
    expect(signed(-5)).toBe("−5.00");
    expect(signed(undefined)).toBe("—");
  });

  it("money: KRW without decimals, others two", () => {
    expect(money(1949000, "KRW")).toBe("1,949,000");
    expect(money(1540, "USD")).toBe("1,540.00");
  });

  it("fill: replaces every placeholder", () => {
    expect(fill("{n}건 미만 · {n}", { n: 5 })).toBe("5건 미만 · 5");
    expect(fill(undefined, { n: 1 })).toBe("");
  });
});
