/**
 * Toss 내 투자 — two unlabelled lines per stock, no average cost printed.
 * Word boxes mimic the production OCR dump of a real capture (names and
 * numbers here are synthetic), including its misreads: 주 read as "%" / "F",
 * an empty digit re-read, and the round logo read as letters left of the name.
 */
import { describe, it, expect } from "vitest";
import type { OcrWord } from "@/lib/fill-ocr/parse";
import { parseHoldingsScreen } from "@/lib/fill-ocr/parse-holdings";

let y = 0;
type W = string | [string, string] | [string, string, number];
function line(...ws: W[]): OcrWord[] {
  y += 70;
  let x = 190;
  return ws.map((w) => {
    const [t, alt, at] = Array.isArray(w) ? w : [w, /\d/.test(w) ? w : undefined];
    if (at !== undefined) x = at;
    const out: OcrWord = { t, c: 90, x0: x, y0: y, x1: x + t.length * 20, y1: y + 30, ...(alt !== undefined ? { alt } : {}) };
    x += t.length * 20 + 20;
    return out;
  });
}

function toss(): OcrWord[] {
  y = 0;
  return [
    ...line(["내", "", 60], "투자"),
    ...line(["직접", "", 60], "설정한", "순", "현재가", "평가금", ["6", "6"], "원"), // "$" read as 6
    ...line(["국내주식", "", 60], ["-20.4%", "20.4"]),
    // cost = 859,449 + 982,051 = 1,841,500; 982,051 ÷ 1,841,500 = 53.33% → "53.3%" proves it
    ...line("가나전자", ["859,449", "859,449", 700], "원"),
    ...line(["©", "", 90]),
    ...line("29", "주", ["-982,051", "982,051", 600], ["(53.3%)", "53.3"]),
    // "19%" is 19주; the rate 37.6% is 37.667% truncated
    ...line(["MA", "", 60], "다라화학", ["911,936", "911,936", 700], "원"),
    ...line(["19%", "19"], ["-551,064", "551,064", 600], ["(37.6%)", "37.6"]),
    // the rate does not reproduce → the quotient is only a hint
    ...line("마바전자", ["1,000,000", "1,000,000", 700], "원"),
    ...line(["3F", "3"], ["-100,000", "100,000", 600], ["(20.0%)", "20.0"]),
    // the digit re-read came back empty → shares are a hint, so is the average
    ...line("사아전자", ["3,717,420", "3,717,420", 700], "원"),
    ...line(["2", ""], "주", ["-82,580", "82,580", 600], ["(2.1%)", "2.1"]),
    ...line(["해외주식", "", 60], ["-59.1%", "59.1"]),
    ...line("자차에너지", ["273,753", "273,753", 700], "원"),
    ...line("24", "주", ["-536,937", "536,937", 600], ["(66.2%)", "66.2"]),
  ];
}

describe("Toss 내 투자 capture", () => {
  const { screenType, rows } = parseHoldingsScreen(toss());

  it("is a holdings screen, one row per stock, logo letters dropped", () => {
    expect(screenType).toBe("holdings");
    expect(rows.map((r) => r.name.value)).toEqual(["가나전자", "다라화학", "마바전자", "사아전자", "자차에너지"]);
  });

  it("reads shares from the first token even when 주 is misread, if both readings agree", () => {
    expect(rows.map((r) => r.shares.value)).toEqual([29, 19, 3, null, 24]);
    expect(rows[3].shares.hint).toBe("2");
  });

  it("fills the average only when the printed rate proves (amount − P/L) is the cost", () => {
    expect(rows[0].avgCost).toEqual({ value: 63500 }); // (859,449 + 982,051) ÷ 29
    expect(rows[1].avgCost).toEqual({ value: 77000 });
    expect(rows[0].flags).toContain("derived_avg");
    expect(rows[2].avgCost).toEqual({ value: null, hint: "366667" });
    expect(rows[3].avgCost).toEqual({ value: null, hint: "1900000" });
  });

  it("gives no won average for an overseas stock shown in won", () => {
    expect(rows[4].currency).toBeNull();
    expect(rows[4].flags).toContain("foreign_in_krw");
    expect(rows[4].avgCost).toEqual({ value: null });
  });
});

describe("Toss capture cropped to the rows only (no header, misread 주)", () => {
  function cropped(): OcrWord[] {
    y = 0;
    return [
      ...line("가나전자", ["4,305,923", "4,305,923", 700], "원"),
      ...line(["자", "", 150], ["248", "248", 190], "주", ["-650,937", "0937", 600], ["(13.1%)", "13.19"]),
      ...line("다라차", ["1.062,711", "1,062,711", 700], "원"),
      ...line(["3", "3:"], "수", ["-601,289", "601,289", 600], ["(36.1%)", "36.1"]), // digit pass adds ":"
      ...line("마바코인", ["132,913", "132,913", 700], "원"),
      ...line(["(JES", ""], ["-1,440,777", "1,440,777", 600], ["(91.5%)", "91.5"]),
    ];
  }
  const { screenType, rows } = parseHoldingsScreen(cropped());

  it("is still a holdings screen", () => {
    expect(screenType).toBe("holdings");
    expect(rows.map((r) => r.name.value)).toEqual(["가나전자", "다라차", "마바코인"]);
  });

  it("skips logo letters before the share count and reads a comma misread as '.'", () => {
    expect(rows[0].shares).toEqual({ value: 248 });
    expect(rows[0].avgCost).toEqual({ value: 19987 }); // (4,305,923 + 650,937) ÷ 248
    expect(rows[1].shares).toEqual({ value: 3 });
    expect(rows[1].avgCost).toEqual({ value: 554667 });
  });

  it("keeps a row whose share count is unreadable", () => {
    expect(rows[2].shares.value).toBeNull();
    expect(rows[2].avgCost.value).toBeNull();
  });
});

describe("labelled cards: name digits and the cross-check gate", () => {
  function kv(): OcrWord[] {
    y = 0;
    return [
      ...line(["잔고", "", 20]),
      ...line(["현", "", 20], "대", "차", ["3", "3"], "우", ["86", ""]),
      ...line(["평가손익", "", 20], ["-76,060", "76,060", 500], "원"),
      ...line(["보유수량", "", 20], ["4", "4", 500], "주"),
      ...line(["평균단가", "", 20], ["34,570", "34,570", 500], "원"),
      ...line(["평가금액", "", 20], ["62,220", "62,220", 500], "원"),
      ...line(["비", "", 20], "투", "엔"),
      ...line(["평가손익", "", 20], ["+90,675", "90,675", 500], "원"),
      // 117주: the box missed the leading 1, so both readings say 17
      ...line(["보유수량", "", 20], ["17", "17", 500], "주"),
      ...line(["평균단가", "", 20], ["8.370", "8,370", 500], "원"),
      ...line(["평가금액", "", 20], ["1,069,965", "1,069,965", 500], "원"),
    ];
  }
  const { rows } = parseHoldingsScreen(kv());

  it("keeps a digit inside a name — 현대차3우B is not 현대차", () => {
    expect(rows[0].name.value).toBe("현대차3우");
    expect(rows[0].shares).toEqual({ value: 4 });
  });

  it("fills nothing when the printed amounts disprove every reading", () => {
    expect(rows[1].shares.value).toBeNull();
    expect(rows[1].avgCost.value).toBeNull();
    expect(rows[1].flags).toContain("amount_mismatch");
  });
});

describe("Toss 해외주식 with the $ toggle on", () => {
  function usdScreen(): OcrWord[] {
    y = 0;
    return [
      ...line(["해외주식", "", 60], ["-59.1%", "59.1"]),
      // "$184.32" has no comma; the page pass reads "$" as "%"
      ...line("가나파워", ["%184.32", "$184.32", 700]),
      // cost $555.60, 371.28 ÷ 555.60 = 66.82% → "66.8%", page misreads it "66.89%"
      ...line("24", "주", ["-$371.28", "$371.28", 600], ["(66.89%)", "66.8"]),
      ...line("다라항공", ["$634.70", "$634.70", 700]),
      ...line("110", "주", ["+$2.20", "$2.20", 600], ["(0.3%)", "0.3"]),
    ];
  }
  const { rows } = parseHoldingsScreen(usdScreen());

  it("reads dollar amounts and proves the dollar average", () => {
    expect(rows.map((r) => [r.name.value, r.currency, r.shares.value, r.avgCost.value])).toEqual([
      ["가나파워", "USD", 24, 23.15],
      ["다라항공", "USD", 110, 5.75],
    ]);
  });
});

describe("Toss 자세히 보기 table (word boxes as OCR read a real capture)", () => {
  // x positions and misreads copied from the production OCR dump of a real
  // capture; names and numbers are synthetic.
  function detail(): OcrWord[] {
    y = 0;
    return [
      ...line(["종", "", 74], "목", "명", ["|", "", 306], ["1", "", 450], "주", "평균", "금액", ["총", "", 873], "금액"),
      ...line(["가나전자", "", 73], [".7%", ".7", 309], ["272,000", "272,000", 517], "원", ["4,048,149", "4,048,149", 810], "원"),
      ...line(["15%", "15", 76], ["51¢", "51", 309], ["현재가", "", 453], ["270,500", "270,500", 546], "원", ["원금", "", 782], ["4,080,000", "4,080,000", 846], "원"),
      // "554,666원" read with "%", "원금" read as "HZ", 3주 as "3F"
      ...line(["다라차", "", 73], ["1.2%", "1.2", 309], ["554,666%", "554,666", 517], ["1,061,214", "1,061,214", 813]),
      ...line(["3F", "3", 74], ["86%", "86", 309], ["현재가", "", 453], ["354,500", "354,500", 555], ["HZ", "", 782], ["1,664,000", "1,664,000", 849]),
      // share count unreadable ("29주" → "on"): 원금 ÷ 평균 = 29
      ...line(["마바글로벌", "", 74], ["1.0%", "0", 309], ["63,500", "63,500", 541], ["846,427", "846,427", 847]),
      ...line(["on", "", 74], ["73%", "73", 309], ["현재가", "", 473], ["29,250", "29,250", 567], "원", ["원금", "", 782], ["1,841,500", "1,841,500", 867], "원"),
      // 19주 read "19 수": 수 is not part of the name
      ...line(["사아비전", "", 73], ["1.9%", "1.9", 309], ["77,000", "77,000", 541], "원", ["878,757", "878,757", 847], "원"),
      ...line(["19", "19", 76], ["수", "", 113], ["43", "43", 313], ["현재가", "", 473], ["46,350", "46,350", 566], ["원금", "", 782], ["1,463,000", "1,463,000", 849]),
      // garbled average: 현재가 must not take its place
      ...line(["자차화학", "", 73], ["2.0%", "2.0", 309], ["ro", "", 436], ["2,606,430", "2,606,430", 596]),
      ...line(["72", "72", 41], ["현재가", "", 453], ["27575", "27575", 483], ["원금", "", 782], ["2,606,400", "2,606,400", 849]),
    ];
  }
  const { screenType, rows } = parseHoldingsScreen(detail());

  it("reads the printed average, proven by 원금", () => {
    expect(screenType).toBe("holdings");
    expect(rows.map((r) => [r.name.value, r.shares.value, r.avgCost.value])).toEqual([
      ["가나전자", 15, 272000],
      ["다라차", 3, 554666], // 554,666 × 3 = 1,663,998 ≈ 1,664,000
      ["마바글로벌", 29, 63500],
      ["사아비전", 19, 77000],
      ["자차화학", null, null],
    ]);
    expect(rows[2].flags).toContain("derived_shares");
  });
});

describe("Toss 내 투자: a share count with no 주 glyph", () => {
  it("is a hint only — '7주' read as '73' must not become 73 shares", () => {
    y = 0;
    const { rows } = parseHoldingsScreen([
      ...line("가나증권", ["1,637,022", "1,637,022", 700], "원"),
      ...line(["73", "73"], ["-4,662,978", "4,662,978", 600], ["(74.0%)", "74.0"]),
      ...line("다라테크", ["2,245,202", "2,245,202", 700], "원"),
      ...line(["93", "93"], "주", ["-2,320,698", "2,320,698", 600], ["(50.8%)", "50.8"]),
    ]);
    expect(rows[0].shares).toEqual({ value: null, hint: "73" });
    expect(rows[0].avgCost.value).toBeNull();
    expect(rows[1].shares).toEqual({ value: 93 });
  });
});

describe("extra digit readings (alts) are candidates, proven only by 원금", () => {
  function words(): OcrWord[] {
    y = 0;
    const out = [
      ...line(["종", "", 74], "목", "명", ["|", "", 306], ["1", "", 450], "주", "평균", "금액", ["총", "", 873], "금액"),
      // "1,900,000원" boxed as "2"; the widened crop read the whole amount.
      ...line(["가나닉스", "", 73], ["2.0%", "2.0", 309], ["2", "1,9", 483], ["3,531,819", "3,531,819", 811], "원"),
      ...line(["2", "2", 74], "주", ["81", "81", 313], ["현재가", "", 453], ["1,770,000", "1,770,000", 519], ["원금", "", 782], ["3,800,000", "3,800,000", 847]),
      // "1,841,500" read "11841,500" / ",841,500"; the left-widened crop got it; 29주 unread.
      ...line(["다라센", "", 74], ["1.0%", "0", 309], ["63,500", "63,500", 541], ["846,427", "846,427", 847]),
      ...line(["on", "", 74], ["현재가", "", 473], ["29,250", "29,250", 567], ["원금", "", 782], ["11841,500", ",841,500", 867]),
    ];
    out.find((x) => x.t === "2" && x.x0 === 483)!.alts = ["1,900,000"];
    out.find((x) => x.t === "11841,500")!.alts = ["841,500", "1,841,500"];
    return out;
  }
  const { rows } = parseHoldingsScreen(words());

  it("uses the reading that makes shares × avg = 원금", () => {
    expect(rows.map((r) => [r.name.value, r.shares.value, r.avgCost.value])).toEqual([
      ["가나닉스", 2, 1900000],
      ["다라센", 29, 63500],
    ]);
  });

  it("does not use an extra reading without the 원금 check", () => {
    const ws = words().filter((x) => x.t !== "3,800,000" && x.t !== "원금");
    const { rows: r2 } = parseHoldingsScreen(ws);
    expect(r2[0]?.avgCost.value ?? null).toBeNull();
  });
});

describe("misreads that once passed every check (Safari-path OCR, 2026-09-28)", () => {
  it("'2주' read '25' before the P/L is not 25 shares — '+' starts the P/L, not a 주 glyph", () => {
    y = 0;
    const { rows } = parseHoldingsScreen([
      ...line("가나기업", ["1,241,794", "1,241,794", 700], "원"),
      ...line(["25", "25"], ["+688,794", "688,794", 600], ["(68.8%)", "68.8"]),
      ...line("다라화학", ["911,936", "911,936", 700], "원"),
      ...line(["19", "19"], "주", ["-551,064", "551,064", 600], ["(37.6%)", "37.6"]),
    ]);
    expect(rows[0].shares.value).toBeNull();
    expect(rows[0].avgCost.value).toBeNull();
  });

  it("an amount split in two ('24,542' '952원') with a P/L read '9,542.952' fills nothing", () => {
    // Both are 1/1000 of the truth, so the rate (a ratio) still checks out.
    y = 0;
    const { rows } = parseHoldingsScreen([
      ...line("가나우", ["24,542", "24,542", 700], ["952%]", "9522", 800]),
      ...line(["30%", "30"], ["+9,542.952", "9,542.952", 600], ["(63.6%)", "63.6"]),
      ...line("다라화학", ["911,936", "911,936", 700], "원"),
      ...line(["19", "19"], "주", ["-551,064", "551,064", 600], ["(37.6%)", "37.6"]),
    ]);
    expect(rows[0].avgCost.value).toBeNull();
  });
});

describe("매도가능 / 주문가능 N주 is not a second share count", () => {
  it("on the same line as 보유 N주 it is skipped — no merged_record", () => {
    y = 0;
    const { rows } = parseHoldingsScreen([
      ...line(["보유종목", "", 20]),
      ...line(["가나전자", "", 20]),
      ...line(["보유", "", 20], ["10", "10"], "주", "매도가능", ["10", "10"], "주"),
      ...line(["평균단가", "", 20], ["70,000", "70,000", 500], "원"),
      ...line(["다라화학", "", 20]),
      ...line(["보유", "", 20], ["5", "5"], "주", "주문가능", ["5", "5"], "주"),
      ...line(["평균단가", "", 20], ["30,000", "30,000", 500], "원"),
    ]);
    expect(rows.map((r) => [r.name.value, r.shares.value, r.avgCost.value, r.flags])).toEqual([
      ["가나전자", 10, 70000, []],
      ["다라화학", 5, 30000, []],
    ]);
  });

  it("on a line of its own it does not start a nameless record", () => {
    y = 0;
    const { rows } = parseHoldingsScreen([
      ...line(["보유종목", "", 20]),
      ...line(["가나전자", "", 20]),
      ...line(["보유", "", 20], ["10", "10"], "주"),
      ...line(["매도가능", "", 20], ["10", "10"], "주"),
      ...line(["평균단가", "", 20], ["70,000", "70,000", 500], "원"),
      ...line(["다라화학", "", 20]),
      ...line(["보유", "", 20], ["5", "5"], "주"),
      ...line(["매도가능수량", "", 20], ["5", "5"], "주"),
      ...line(["평균단가", "", 20], ["30,000", "30,000", 500], "원"),
    ]);
    expect(rows.map((r) => [r.name.value, r.shares.value, r.avgCost.value])).toEqual([
      ["가나전자", 10, 70000],
      ["다라화학", 5, 30000],
    ]);
  });
});
