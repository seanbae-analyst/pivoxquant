/**
 * Two-row header balance table (보유수량/매도가능 · 평균가/현재가 · 평가손익/손익률)
 * whose first header row is, on its own, a valid one-row table header.
 *
 * Word boxes copy the geometry of the production OCR dump of a broker's App
 * Store screenshot (2026-10-07, docs/product/AI_READ_EXPERIMENT_2026-10-07.md
 * §6 r2): Hangul split into syllables, a junk line between the two header
 * rows, the stock name centred between its two number lines, a stray digit
 * left of the bottom line. Names and numbers here are synthetic and consistent.
 *
 * The one-row table path read each bottom line as its own row — 매도가능 as
 * shares and 현재가 as the average cost, filled as if proven.
 */
import fs from "node:fs";
import path from "node:path";
import { describe, it, expect } from "vitest";
import type { OcrWord } from "@/lib/fill-ocr/parse";
import { parseHoldingsScreen } from "@/lib/fill-ocr/parse-holdings";

const w = (t: string, x0: number, x1: number, y: number, h = 20, alt?: string): OcrWord =>
  ({ t, c: 90, x0, x1, y0: y, y1: y + h, ...(/\d/.test(t) ? { alt: alt ?? t.replace(/[^\d.]/g, "") } : {}) });

/** One stock: top line (보유수량 · 평균가 · 평가손익), name between, bottom line (매도가능 · 현재가 · 손익률). */
function stock(y: number, name: string, top: [string, string, string], bot: [string, string, string]): OcrWord[] {
  return [
    w(top[0], 586, 615, y), w(top[1], 666, 763, y), w(top[2], 816, 912, y),
    w(name, 293, 293 + name.length * 24, y + 16, 25),
    w("1", 399, 426, y + 36, 8, ""), // a glyph read as "1"; the digits-only re-read is empty, as in the dump
    w(bot[0], 587, 615, y + 36), w(bot[1], 682, 762, y + 36), w(bot[2], 840, 912, y + 36),
  ];
}

function screen(): OcrWord[] {
  return [
    w("주식잔고/손익", 320, 540, 520, 37),
    w("총", 290, 310, 980), w("평가금액", 320, 420, 980),
    w("23,000,000원", 290, 540, 1030, 47),
    // header row 1, a junk line, header row 2
    w("。", 483, 490, 1255, 47), // the 종목명 header's sort icon, read as a dot
    w("보", 516, 534, 1267), w("유", 537, 554, 1267), w("수량", 557, 596, 1266),
    w("평균가", 684, 743, 1266), w("평", 814, 830, 1266), w("가", 835, 852, 1266), w("손익", 855, 891, 1266),
    w("~", 293, 350, 1284, 12), w("or", 295, 349, 1296, 8),
    w("매", 517, 533, 1302), w("도", 537, 554, 1304), w("가능", 558, 595, 1302),
    w("현재가", 684, 743, 1302), w("손", 834, 851, 1303), w("익", 856, 870, 1302), w("률", 878, 892, 1303),
    // (150,000 − 136,000) × 20 = +280,000
    ...stock(1369, "가나전자", ["20", "136,000", "+280,000"], ["10", "150,000", "+10.29%"]),
    // (48,000 − 51,200) × 43 = −137,600
    ...stock(1469, "다라화학", ["43", "51,200", "-137,600"], ["43", "48,000", "-6.25%"]),
    // (33,000 − 32,150) × 350 = +297,500
    ...stock(1569, "마바증권", ["350", "32,150", "+297,500"], ["201", "33,000", "+2.64%"]),
  ];
}

describe("two-row header table whose first row alone looks like a table header", () => {
  const { screenType, rows } = parseHoldingsScreen(screen());

  it("is one row per stock, not one per printed line", () => {
    expect(screenType).toBe("holdings");
    expect(rows.map((r) => r.name.value)).toEqual(["가나전자", "다라화학", "마바증권"]);
  });

  it("takes shares from 보유수량 (top) and the average from 평균가 (top)", () => {
    expect(rows.map((r) => r.shares.value)).toEqual([20, 43, 350]);
    expect(rows.map((r) => r.avgCost.value)).toEqual([136000, 51200, 32150]);
  });

  it("never fills 매도가능 as shares or 현재가 as the average cost", () => {
    const shares = rows.map((r) => r.shares.value);
    const avgs = rows.map((r) => r.avgCost.value);
    for (const sellable of [10, 201]) expect(shares).not.toContain(sellable);
    for (const current of [150000, 48000, 33000]) expect(avgs).not.toContain(current);
  });
});

// The mirror case, on a committed production-OCR dump: the SECOND header row
// (보유수량 · 매입가 · 현재가) passes as a one-row header, and each stock's top
// line (종목명 · 평가손익 · 수익률) was read under it — 평가손익 as the average.
describe("two-row header table whose second row alone looks like a table header (a03 dump)", () => {
  const dir = path.resolve(__dirname, "../../../../../tests/fixtures/screenshot_import/ai_read");
  const dump = JSON.parse(fs.readFileSync(path.join(dir, "ocr", "a03_two_row_grid.png.json"), "utf8")) as OcrWord[];
  const truth = JSON.parse(fs.readFileSync(path.join(dir, "ground_truth.json"), "utf8"))["a03_two_row_grid.png"].holdings as
    { shares: number; avg_cost: number }[];
  const { rows } = parseHoldingsScreen(dump);

  it("is one row per stock", () => {
    expect(rows).toHaveLength(truth.length);
  });

  it("fills shares and average cost only with the printed values, never 평가손익", () => {
    rows.forEach((r, i) => {
      if (r.shares.value !== null) expect(r.shares.value).toBe(truth[i].shares);
      if (r.avgCost.value !== null) expect(r.avgCost.value).toBe(truth[i].avg_cost);
    });
    expect(rows.filter((r) => r.shares.value !== null && r.avgCost.value !== null).length).toBeGreaterThan(0);
  });
});
