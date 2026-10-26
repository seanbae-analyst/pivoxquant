/**
 * The "x" / "×" of "20주 × 24,350" marks a price only as a word of its own —
 * "AMEX" ends in x too (2026-09-28: the amount after it became the price).
 */
import { describe, it, expect } from "vitest";
import type { OcrWord } from "@/lib/fill-ocr/parse";
import { parseFillScreen } from "@/lib/fill-ocr/parse";

let y = 0;
function line(...ws: [string, string | undefined][]): OcrWord[] {
  y += 60;
  let x = 40;
  return ws.map(([t, alt]) => {
    const w: OcrWord = { t, c: 90, x0: x, y0: y, x1: x + t.length * 18, y1: y + 28, ...(alt !== undefined ? { alt } : {}) };
    x += t.length * 18 + 16;
    return w;
  });
}

describe("fill cards: the times sign", () => {
  it("'×' reads the price; 'AMEX 359,000' does not", () => {
    y = 0;
    const words = [
      ...line(["체결내역", undefined]),
      ...line(["2026.09.25", "2026.09.25"]),
      ...line(["대한항공", undefined], ["매도", undefined], ["20", "20"], ["주", undefined], ["×", undefined], ["24,350", "24,350"]),
      ...line(["13:05", "13:05"], ["487,000", "487,000"], ["원", undefined]),
      ...line(["AMEX", undefined], ["359,000", "359,000"]),
      ...line(["5", "5"], ["주", undefined], ["구매", undefined], ["주당", undefined], ["71,800", "71,800"], ["구매완료", undefined]),
    ];
    const { rows } = parseFillScreen(words);
    const prices = rows.map((r) => r.price.value);
    expect(prices).toContain(24350);
    expect(prices).not.toContain(359000);
  });
});

describe("fill cards: 오전/오후 next to the clock (2026-10-21)", () => {
  it("reads 오후 02:05 as 14:05, and leaves a 24-hour clock alone", () => {
    y = 0;
    const words = [
      ...line(["체결내역", undefined]),
      ...line(["2026.09.25", "2026.09.25"]),
      ...line(["대한항공", undefined], ["매도", undefined], ["20", "20"], ["주", undefined], ["×", undefined], ["24,350", "24,350"]),
      ...line(["오후", undefined], ["02:05", "02:05"], ["487,000", "487,000"], ["원", undefined]),
    ];
    const { rows } = parseFillScreen(words);
    expect(rows.map((r) => r.time?.value)).toContain("14:05");
    expect(rows.map((r) => r.time?.value)).not.toContain("02:05");
  });
});
