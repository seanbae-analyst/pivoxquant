/**
 * A fill screen whose date header has no year ("9 월 23 일"), and a price
 * that starts like a year ("$2050.25") — 2026-10-13 bug hunt.
 */
import { describe, it, expect } from "vitest";
import type { OcrWord } from "@/lib/fill-ocr/parse";
import { parseFillScreen } from "@/lib/fill-ocr/parse";

let y = 0;
function line(...ts: string[]): OcrWord[] {
  y += 60;
  let x = 40;
  return ts.map((t) => {
    const digits = /^[\d$.,]+$/.test(t) ? { alt: t } : {};
    const w: OcrWord = { t, c: 90, x0: x, y0: y, x1: x + t.length * 18, y1: y + 28, ...digits };
    x += t.length * 18 + 16;
    return w;
  });
}

describe("fill cards: a yearless date header", () => {
  it("is not the stock name", () => {
    y = 0;
    const words = [
      ...line("거래", "내역"),
      ...line("9", "월", "23", "일"),
      ...line("삼성전자", "724,000", "원"),
      ...line("10", "주", "구매", "주당", "72,400", "원"),
    ];
    const { rows } = parseFillScreen(words);
    expect(rows).toHaveLength(1);
    expect(rows[0].name.value).toBe("삼성전자");
    expect(rows[0].shares.value).toBe(10);
    expect(rows[0].price.value).toBe(72400);
  });

  it("each record keeps its own name across a 12월 → 1월 turn", () => {
    y = 0;
    const words = [
      ...line("체결내역"),
      ...line("12", "월", "30", "일"),
      ...line("삼성전자", "724,000", "원"),
      ...line("10", "주", "구매", "ㆍ", "주당", "72,400", "원"),
      ...line("1", "월", "2", "일"),
      ...line("카카오", "627,750", "원"),
      ...line("15", "주", "구매", "ㆍ", "주당", "41,850", "원"),
    ];
    const names = parseFillScreen(words).rows.map((r) => r.name.value);
    expect(names).toEqual(["삼성전자", "카카오"]);
  });
});

describe("fill cards: a price is not a year", () => {
  it("$2050.25 does not date the fill 2050", () => {
    y = 0;
    const words = [
      ...line("체결내역"),
      ...line("9", "월", "23", "일"),
      ...line("BKNG", "매수", "$2050.25"),
      ...line("1", "주", "x", "$2050.25"),
    ];
    const { rows } = parseFillScreen(words);
    expect(rows).toHaveLength(1);
    expect(rows[0].price.value).toBe(2050.25);
    expect(String(rows[0].date.value ?? "")).not.toMatch(/^2050/);
  });

  it("a real year on the screen still dates a yearless header", () => {
    y = 0;
    const words = [
      ...line("체결내역", "2025.09"),
      ...line("9", "월", "23", "일"),
      ...line("BKNG", "매수", "$2050.25"),
      ...line("1", "주", "x", "$2050.25"),
    ];
    const { rows } = parseFillScreen(words);
    expect(rows[0].date.value).toBe("2025-09-23");
  });
});

describe("fill cards: an undated header resets the date", () => {
  it("a card under '1 월 2 일' is not dated by '2026년 12월 30일' above it", () => {
    y = 0;
    const words = [
      ...line("체결내역"),
      ...line("2026", "년", "12", "월", "30", "일"),
      ...line("삼성전자", "724,000", "원"),
      ...line("10", "주", "구매", "ㆍ", "주당", "72,400", "원"),
      ...line("1", "월", "2", "일"),
      ...line("카카오", "627,750", "원"),
      ...line("15", "주", "구매", "ㆍ", "주당", "41,850", "원"),
    ];
    const rows = parseFillScreen(words).rows;
    const kakao = rows.find((r) => r.name.value === "카카오");
    expect(rows.find((r) => r.name.value === "삼성전자")?.date.value).toBe("2026-12-30");
    expect(kakao?.date.value).not.toBe("2026-12-30");
  });
});
