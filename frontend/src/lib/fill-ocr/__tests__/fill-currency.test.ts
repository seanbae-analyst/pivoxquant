/**
 * Fill tables: the currency is read from the row, its header ("체결단가($)")
 * or the screen — never defaulted to KRW. A US fill whose "$" sits only in
 * the header once came back KRW (2026-09-29).
 */
import { describe, it, expect } from "vitest";
import type { OcrWord } from "@/lib/fill-ocr/parse";
import { parseFillScreen } from "@/lib/fill-ocr/parse";

let y = 0;
function line(...ws: [string, string | undefined, number][]): OcrWord[] {
  y += 60;
  return ws.map(([t, alt, x]) => ({ t, c: 90, x0: x, y0: y, x1: x + t.length * 18, y1: y + 28, ...(alt !== undefined ? { alt } : {}) }));
}

function table(head: [string, string], row: [string, string, string]): OcrWord[] {
  y = 0;
  return [
    ...line(["종목명", undefined, 40], ["매매구분", undefined, 200], ["체결수량", undefined, 360], [head[0], undefined, 520], [head[1], undefined, 720]),
    ...line(["TSLA", undefined, 40], ["매수", undefined, 210], ["3", "3", 390], [row[0], row[0].replace(/[^\d.,]/g, ""), 540], [row[1], row[1].replace(/[^\d.,]/g, ""), 740]),
    ...line(["AAPL", undefined, 40], ["매도", undefined, 210], ["2", "2", 390], ["180.00", "180.00", 540], [row[2], row[2].replace(/[^\d.,]/g, ""), 740]),
  ];
}

describe("fill table currency", () => {
  it("'$' only in the header → USD", () => {
    const { rows } = parseFillScreen(table(["체결단가($)", "체결금액($)"], ["250.10", "750.30", "360.00"]));
    expect(rows.map((r) => [r.currency, r.shares.value, r.price.value, r.amount.value])).toEqual([
      ["USD", 3, 250.1, 750.3],
      ["USD", 2, 180, 360],
    ]);
  });

  it("a US price under $100 is not dropped as an implausible won price", () => {
    // No amount column, so nothing cross-checks the price: only the won
    // plausibility rule (< 100 is not a won price) could drop it.
    y = 0;
    const { rows } = parseFillScreen([
      ...line(["종목명", undefined, 40], ["매매구분", undefined, 200], ["체결수량", undefined, 360], ["체결단가", undefined, 520]),
      ...line(["TSLA", undefined, 40], ["매수", undefined, 210], ["30", "30", 390], ["$25.01", "25.01", 540]),
    ]);
    expect([rows[0].currency, rows[0].price.value]).toEqual(["USD", 25.01]);
  });

  it("no currency printed anywhere → unknown, the user picks it", () => {
    const { rows } = parseFillScreen(table(["체결단가", "체결금액"], ["250.10", "750.30", "360.00"]));
    expect(rows.map((r) => r.currency)).toEqual([null, null]);
  });

  it("won printed on the row or in the header → KRW", () => {
    expect(parseFillScreen(table(["체결단가(원)", "체결금액(원)"], ["72,400", "217,200", "360,000"])).rows[0].currency).toBe("KRW");
    expect(parseFillScreen(table(["체결단가", "체결금액"], ["72,400원", "217,200원", "360,000원"])).rows[0].currency).toBe("KRW");
  });

  it("a bare US price shaped like MM.DD (25.10) still makes the line a trade row", () => {
    // "25.10" / "75.30" fit the month-day shape that marks a detail line
    // ("09.22 14:21:07"); under the price / amount header they are numbers.
    const { rows } = parseFillScreen(table(["체결단가($)", "체결금액($)"], ["25.10", "75.30", "360.00"]));
    expect(rows.map((r) => [r.currency, r.shares.value, r.price.value, r.amount.value])).toEqual([
      ["USD", 3, 25.1, 75.3],
      ["USD", 2, 180, 360],
    ]);
  });

  it("an MM.DD price under the price column keeps its row even with no currency printed", () => {
    // The row is found; whether "25.10" is a proven price is reconcile's
    // call (with the currency unknown it is not — the user types it).
    const { rows } = parseFillScreen(table(["체결단가", "체결금액"], ["25.10", "75.30", "360.00"]));
    expect(rows.map((r) => [r.name.value, r.shares.value, r.amount.value])).toEqual([
      ["TSLA", 3, 75.3],
      ["AAPL", 2, 360],
    ]);
    expect(rows[0].price.value ?? rows[0].price.hint).toBeTruthy();
  });

  it("an MM.DD under the date column stays a date, not a number, in a USD table", () => {
    y = 0;
    const { rows } = parseFillScreen([
      ...line(["체결일", undefined, 40], ["종목명", undefined, 200], ["매매구분", undefined, 360], ["체결수량", undefined, 520], ["체결단가($)", undefined, 700]),
      ...line(["09.28", "0928", 40], ["TSLA", undefined, 200], ["매수", undefined, 370], ["3", "3", 550], ["250.10", "250.10", 720]),
      // A detail line of only a date + a number under the name is not a row.
      ...line(["09.28", "0928", 40], ["2", "2", 200]),
    ]);
    expect(rows).toHaveLength(1);
    expect([rows[0].date.value, rows[0].date.hint, rows[0].shares.value, rows[0].price.value])
      .toEqual([null, "09.28", 3, 250.1]);
  });
});
