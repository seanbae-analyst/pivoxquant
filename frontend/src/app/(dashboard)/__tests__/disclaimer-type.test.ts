/**
 * (dashboard)/layout.tsx picks the one page-level DisclaimerBanner variant by
 * pathname. 2026-09-29: the "signal" (algorithmic signals) and "coaching" (AI
 * assistant) variants described deleted features and were removed — record
 * surfaces take "record", the behaviour mirrors keep "behavior-mirror".
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { resolveDisclaimerType } from "../layout";

describe("resolveDisclaimerType", () => {
  it.each([
    ["/journal", "behavior-mirror"],
    ["/journal/import", "behavior-mirror"],
    ["/mirror", "behavior-mirror"],
    ["/pre-trade", "record"],
    ["/portfolio", "record"],
    ["/settings", "record"],
    ["/support/contact", "record"],
    [null, "record"],
  ] as const)("%s → %s", (path, kind) => {
    expect(resolveDisclaimerType(path)).toBe(kind);
  });

  it("banner copy carries no AI / algorithmic-signal wording", () => {
    const src = readFileSync(
      join(__dirname, "..", "..", "..", "components", "ui", "disclaimer-banner.tsx"),
      "utf8",
    );
    const copy = [...src.matchAll(/(?:ko|en):\s*"([^"]*)"/g)].map((m) => m[1]).join("\n");
    expect(copy.length).toBeGreaterThan(0);
    expect(copy).not.toMatch(/\bAI\b|인공지능|어시스턴트|알고리즘|algorithm|시그널|signal|백테스트|backtest/i);
  });
});
