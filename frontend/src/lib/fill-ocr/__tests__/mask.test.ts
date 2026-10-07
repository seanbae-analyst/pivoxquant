/**
 * lib/fill-ocr/mask.ts — what may leave the device from a broker-screen read.
 *
 * Line shapes come from the production OCR of broker App Store screenshots
 * (docs/product/AI_READ_EXPERIMENT_2026-10-07.md §6; their sample names and
 * account numbers, not real people's) and from the committed synthetic set
 * tests/fixtures/screenshot_import/ai_read/ (fake PII listed in ground_truth `pii`).
 */
import fs from "node:fs";
import path from "node:path";
import { describe, it, expect } from "vitest";
import type { OcrWord } from "@/lib/fill-ocr/parse";
import { parseHoldingsScreen } from "@/lib/fill-ocr/parse-holdings";
import { dropReason, maskScreen, maskSourceText } from "@/lib/fill-ocr/mask";

describe("dropReason — lines that must not leave the device", () => {
  it.each([
    // the holder's name sits on the account line — the number alone is not enough
    ["124-4567-8900-XX[종합_주식] 김미래 v", "account"],
    ["(7) 12345678-010 김하나 v", "account"],
    // account-type tag with the name, the number on another line
    ["[ 종 합 ( 평 생 혜택 비 대 면 )] 김 증권 =", "account"],
    // OCR garbled "통합계좌" — only the number gives the line away
    ["£57 =} 1234-5678-90", "account"],
    ["45160882-24", "account"],
    ["1O2-34-5678l9", "account"], // O / l read for 0 / 1
    ["010-1234-5678", "account"], // a phone number goes too
    ["계좌 45160882-24 이서연", "identity"],
    ["위탁 6000-0934", "identity"],
    ["이 서 연 님 의 계좌", "identity"],
    ["고객 번호", "identity"],
    ["주 문 가 능 금액 2,940,000 원", "unneeded"],
    ["예수금 6,403,600", "unneeded"],
  ])("%s → %s", (line, why) => {
    expect(dropReason(line)).toBe(why);
  });

  it.each([
    "셀트리온 20 136,000 136,000",
    "매 입 금액 747,672 평 가 손익 +558,576",
    "총 평 가 금액 23,000,000원",
    "매 도 가능 현재가 손 익 률", // a header — 매도가능 is not 주문가능
    "2026-10-01 09:31 체결가 71,000원",
    "일자 : 2022.02.18",
    "20261001 매수 10주",
    "TIGER MSCI KOREA ESG 350 136,000",
    "AAPL 12 $171.25",
  ])("keeps %s", (line) => {
    expect(dropReason(line)).toBeNull();
  });
});

describe("maskSourceText — a parsed record's source_text", () => {
  it("drops only the lines that must not leave", () => {
    expect(maskSourceText("삼성전자 매수 10주 / 계좌 123-45-678901 / 2026-10-01 체결가 71,000원"))
      .toBe("삼성전자 매수 10주 / 2026-10-01 체결가 71,000원");
  });
  it("leaves a clean record as it was", () => {
    const s = "NHN 10,037,300원 / 보유 130주 · 평균단가 94,390원";
    expect(maskSourceText(s)).toBe(s);
  });
});

describe("maskScreen on the committed synthetic set (production OCR dumps)", () => {
  const dir = path.resolve(__dirname, "../../../../../tests/fixtures/screenshot_import/ai_read");
  const truth = JSON.parse(fs.readFileSync(path.join(dir, "ground_truth.json"), "utf8")) as Record<string, { pii: string[] }>;
  const dump = (f: string) => JSON.parse(fs.readFileSync(path.join(dir, "ocr", `${f}.json`), "utf8")) as OcrWord[];

  it.each(Object.keys(truth))("%s: no account number or name survives", (f) => {
    const flat = maskScreen(dump(f)).text.replace(/\s+/g, "");
    for (const p of truth[f].pii) {
      const parts = /\d/.test(p) ? p.split(/\D+/).filter((x) => x.length >= 4) : [p];
      for (const part of parts) expect(flat).not.toContain(part);
    }
  });

  it.each(Object.keys(truth))("%s: every line a holding row was read from is kept", (f) => {
    const kept = new Set(maskScreen(dump(f)).text.split("\n"));
    for (const r of parseHoldingsScreen(dump(f)).rows) {
      for (const line of r.sourceText.split(" / ")) expect(kept).toContain(line);
    }
  });
});
