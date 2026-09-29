/**
 * Landing loop / hero / FAQ copy — claims must match the product (2026-09-29).
 *
 *   - The loop starts with uploading holdings (onboarding step 0 requires it,
 *     ONBOARDING_HOLDINGS_REQUIRED) — four steps, one key set per step.
 *   - The turnover figure is a sourced, observational statement (Barber &
 *     Odean, 2000), never an unsourced absolute about "your" returns.
 *   - FAQ a7 must not say images are refused / tell users to OCR elsewhere:
 *     fill captures are read in the browser (lib/fill-ocr).
 *   - FAQ a5: holdings capture + manual entry are listed; the approval rule
 *     is scoped to imported fills, not holdings.
 *   - No price_52w alert claim (off while MARKET_DATA_DISPLAY_ENABLED=0).
 *   - No persona type names (성장형/균형형/수익형 · Growth/Balanced/Income) —
 *     the 선언과 관찰 section explains the two sides without labels or scores
 *     (CEO 2026-09-29, CLAUDE.md "유형 라벨·점수는 만들지 않는다").
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import ko from "@/messages/ko.json";
import en from "@/messages/en.json";

type Landing = Record<string, Record<string, unknown>>;
const lko = (ko as unknown as { landing: Landing }).landing;
const len = (en as unknown as { landing: Landing }).landing;
const s = (l: Landing, sec: string, k: string) => String(l[sec][k]);

const flat = (o: unknown, p = ""): string[] =>
  o && typeof o === "object"
    ? Object.entries(o as Record<string, unknown>).flatMap(([k, v]) => flat(v, `${p}.${k}`))
    : [p];

describe("landing loop copy", () => {
  it("has identical landing keys in ko and en", () => {
    expect(flat(lko).sort()).toEqual(flat(len).sort());
  });

  it("renders four steps, holdings first, each with verb/body/limit", () => {
    const src = readFileSync(
      join(__dirname, "..", "components", "landing", "three-steps.tsx"),
      "utf8",
    );
    const steps = [...src.matchAll(/key: "(s\d)", route: "([^"]+)"/g)].map((m) => [m[1], m[2]]);
    expect(steps).toEqual([
      ["s1", "/portfolio"],
      ["s2", "/pre-trade"],
      ["s3", "/journal"],
      ["s4", "/mirror"],
    ]);
    for (const l of [lko, len]) {
      for (const [k] of steps) {
        for (const part of ["verb", "body", "limit"]) expect(s(l, "steps", `${k}${part}`)).toBeTruthy();
      }
      for (const n of ["pause", "notify"]) {
        expect(s(l, "steps", `${n}Title`)).toBeTruthy();
        expect(s(l, "steps", `${n}Body`)).toBeTruthy();
      }
    }
    expect(s(lko, "steps", "s1verb")).toBe("보유 올리기");
    expect(s(lko, "steps", "heading")).not.toContain("셋뿐");
  });

  it("states the turnover figure with its source, not as a claim about the reader", () => {
    for (const l of [lko, len]) expect(s(l, "hero", "description")).toContain("Barber & Odean, 2000");
    expect(s(lko, "hero", "description")).not.toMatch(/당신 수익을 깎/);
  });

  it("FAQ a7 reflects in-browser capture reading", () => {
    expect(s(lko, "faq", "a7")).not.toMatch(/이미지는 받지 않습니다|단축어의 '이미지에서 텍스트|렌즈/);
    expect(s(len, "faq", "a7")).not.toMatch(/Images are never accepted|Extract Text from Image|Lens/);
    expect(s(lko, "faq", "a7")).toContain("브라우저에서");
    expect(s(len, "faq", "a7")).toContain("in your browser");
  });

  it("FAQ a5 lists holdings capture and scopes approval to imported fills", () => {
    expect(s(lko, "faq", "a5")).toContain("잔고 화면 캡처");
    expect(s(lko, "faq", "a5")).toContain("바로 등록");
    expect(s(len, "faq", "a5")).toContain("holdings screen");
    expect(s(len, "faq", "a5")).not.toMatch(/On every path a fill is not recorded/);
  });

  it("names no alert that does not fire today and no benefit of pausing", () => {
    const text = JSON.stringify(lko) + JSON.stringify(len);
    expect(text).not.toMatch(/52주|52-week/);
    expect(s(lko, "steps", "pauseBody")).not.toMatch(/수익|효과|개선/);
    expect(s(len, "steps", "pauseBody")).not.toMatch(/return|effective|improv/i);
  });

  it("names no persona type anywhere on the landing", () => {
    // Values only — the key namespace `landing.personas` itself is kept.
    const values = (o: unknown): string[] =>
      o && typeof o === "object" ? Object.values(o as object).flatMap(values) : [String(o)];
    const koText = values(lko).join("\n");
    const enText = values(len).join("\n");
    for (const name of ["성장형", "균형형", "수익형", "투자자 유형", "페르소나"]) {
      expect(koText).not.toContain(name);
    }
    expect(enText).not.toMatch(/\b(Growth|Balanced|Income)\b|investor type|persona/i);
    for (const l of [lko, len]) {
      expect(l.personas).not.toHaveProperty("buckets");
      expect(l.personas).not.toHaveProperty("bucketsNote");
      for (const side of ["declared", "observed"]) {
        const v = (l.personas.sides as Record<string, { name: string; line: string }>)[side];
        expect(v.name).toBeTruthy();
        expect(v.line).toBeTruthy();
      }
    }
    // 선언 = the five answers, 관찰 = last 30 days; no labels, no scores.
    const sides = lko.personas.sides as Record<string, { line: string }>;
    expect(sides.declared.line).toContain("다섯 문항");
    expect(sides.observed.line).toContain("30일");
    expect(s(lko, "personas", "description")).toMatch(/유형 이름도 점수도 붙이지 않습니다/);
    expect(s(len, "personas", "description")).toMatch(/no type name and no score/);
    const src = readFileSync(
      join(__dirname, "..", "components", "landing", "personas-preview.tsx"),
      "utf8",
    );
    expect(src).not.toMatch(/BUCKETS|personas\.buckets|bucketsNote/);
  });
});
