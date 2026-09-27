/**
 * Toss 내 투자 — two unlabelled lines per stock, no average cost printed.
 * Word boxes mimic the production OCR dump of a real capture (names and
 * numbers here are synthetic), including its glyph misreads of 주.
 */
import { describe, it, expect } from "vitest";
import type { OcrWord } from "@/lib/fill-ocr/parse";
import { parseHoldingsScreen } from "@/lib/fill-ocr/parse-holdings";

let y = 0;
function line(...ws: (string | [string, string])[]): OcrWord[] {
  y += 70;
  let x = 60;
  return ws.map((w) => {
    const [t, alt] = Array.isArray(w) ? w : [w, /\d/.test(w) ? w : undefined];
    const out: OcrWord = { t, c: 90, x0: x, y0: y, x1: x + t.length * 20, y1: y + 30, ...(alt !== undefined ? { alt } : {}) };
    x += t.length * 20 + 20;
    return out;
  });
}

function toss(): OcrWord[] {
  y = 0;
  return [
    ...line("내", "투자"),
    ...line("직접", "설정한", "순", "현재가", "평가금", "원"),
    ...line("국내주식", ["-20.4%", "20.4"]),
    ...line("가나전자", "1,841,500", "원"),
    ...line("©"),
    ...line("29", "주", ["-241,500", "241,500"], ["(13.1%)", "13.1"]),
    ...line("다라화학", "911,936", "원"),
    ...line(["19%", "19"], ["-551,064", "551,064"], ["(37.6%)", "37.6"]),
    ...line("해외주식", ["-59.1%", "59.1"]),
    ...line("마바에너지", "273,753", "원"),
    ...line("24", "주", ["-536,937", "536,937"], ["(66.2%)", "66.2"]),
  ];
}

describe("Toss 내 투자 capture", () => {
  const { screenType, rows } = parseHoldingsScreen(toss());

  it("is a holdings screen", () => {
    expect(screenType).toBe("holdings");
    expect(rows.map((r) => r.name.value)).toEqual(["가나전자", "다라화학", "마바에너지"]);
  });

  it("reads shares only when the 주 glyph and both readings agree", () => {
    expect(rows[0].shares).toEqual({ value: 29 });
    expect(rows[1].shares).toEqual({ value: null, hint: "19" }); // "19%" is a misread 19주
  });

  it("never fills the average — (amount − P/L) ÷ shares is a hint", () => {
    expect(rows[0].avgCost).toEqual({ value: null, hint: "71828" });
    expect(rows[1].avgCost).toEqual({ value: null, hint: "77000" });
  });

  it("gives no won average for an overseas stock shown in won", () => {
    expect(rows[2].currency).toBeNull();
    expect(rows[2].flags).toContain("foreign_in_krw");
    expect(rows[2].avgCost.value).toBeNull();
    expect(rows[2].avgCost.hint).toBeUndefined();
  });
});
