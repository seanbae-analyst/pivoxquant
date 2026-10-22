/**
 * Landing "Why record" section — copy parity + claim limits (2026-10-22).
 *
 * why-record.tsx reads every string from `landing.why` via useT(). The three
 * figures are copied from public releases and must stay sourced and
 * observational:
 *   - every figure has a Source line naming the institution,
 *   - no copy promises that keeping a record changes returns or behaviour,
 *   - the research term for the sells figure is not attached to the user's
 *     own mirror (services/behavior/profit_loss_mirror.py keeps it out),
 *   - no invented figure for "how many investors keep a trading journal" —
 *     no public survey asks it.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import ko from "@/messages/ko.json";
import en from "@/messages/en.json";

const whyKo = (ko as { landing: { why: Record<string, string> } }).landing.why;
const whyEn = (en as { landing: { why: Record<string, string> } }).landing.why;

describe("landing.why copy", () => {
  it("has identical, non-empty keys in ko and en", () => {
    expect(Object.keys(whyKo).sort()).toEqual(Object.keys(whyEn).sort());
    for (const [k, v] of Object.entries({ ...whyKo, ...whyEn })) {
      expect(v, k).toBeTruthy();
    }
  });

  it("has figure, label, body, source and product line for every fact the component renders", () => {
    const src = readFileSync(
      join(__dirname, "..", "components", "landing", "why-record.tsx"),
      "utf8",
    );
    const keys = [...src.matchAll(/\{ key: "(\w+)", route:/g)].map((m) => m[1]);
    expect(keys).toEqual(["finance", "report", "sells"]);
    for (const k of keys) {
      for (const part of ["Figure", "Label", "Body", "Source", "Here"]) {
        expect(whyKo[`${k}${part}`], `${k}${part}`).toBeTruthy();
      }
    }
  });

  it("keeps the figures tied to their public sources", () => {
    expect(whyKo.financeFigure).toContain("43.4");
    expect(whyKo.financeSource).toContain("2024 전국민 금융이해력 조사");
    expect(whyKo.reportFigure).toBe("65.3%");
    expect(whyKo.reportSource).toContain("2025 펀드 투자자 조사");
    expect(whyKo.sellsSource).toContain("자본시장연구원");
  });

  it("does not overclaim", () => {
    const text = Object.values(whyKo).join(" ") + " " + Object.values(whyEn).join(" ");
    // No promise that the tool changes outcomes.
    expect(text).not.toMatch(/개선됩니다|좋아집니다|수익을 높|will improve|boosts? (your )?returns/i);
    // The deck states the limit outright.
    expect(whyKo.deck).toContain("주장이 아닙니다");
    expect(whyEn.deck).toMatch(/not a claim/);
    // The research label is not applied to the user's own trades.
    expect(text).not.toMatch(/처분효과|disposition effect/i);
    // No advice words (자본시장법 · CLAUDE.md).
    expect(text).not.toMatch(/추천|조언|recommend|advice/i);
  });
});
