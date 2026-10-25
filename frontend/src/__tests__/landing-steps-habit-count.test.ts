/**
 * Landing loop card s3 names how many habits /journal computes (2026-10-22).
 *
 * The copy said "다섯 가지 습관" for a month after the rebuy mirror (#671)
 * made it six. This pins the number in both locales to the trade-record
 * mirrors the journal page actually mounts. FrictionOutcomeMirror is not
 * counted: it reads pre-trade reflections, not the trade record.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import ko from "@/messages/ko.json";
import en from "@/messages/en.json";

const KO = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉"];
const EN = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"];

describe("landing.steps.s3body habit count", () => {
  it("matches the trade-record mirrors /journal renders", () => {
    const page = readFileSync(
      join(__dirname, "..", "app", "(dashboard)", "journal", "page.tsx"),
      "utf8",
    );
    const mirrors = new Set(
      [...page.matchAll(/<(\w+Mirror)\s*\/>/g)]
        .map((m) => m[1])
        .filter((name) => name !== "FrictionOutcomeMirror"),
    );
    const n = mirrors.size;
    expect(n).toBeGreaterThan(0);

    const steps = (key: typeof ko | typeof en) =>
      (key as unknown as { landing: { steps: { s3body: string } } }).landing.steps.s3body;
    expect(steps(ko)).toContain(`${KO[n]} 가지 습관`);
    expect(steps(en)).toContain(`${EN[n]} habits`);
  });
});
