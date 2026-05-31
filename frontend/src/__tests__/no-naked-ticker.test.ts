/**
 * Regression gate — sample-report templates must never expose a US ticker
 * symbol without an accompanying company name.
 *
 * Background — `feedback_ticker_display` (사용자 반복 지시 3+회):
 * 종목 ticker code 단독 노출 금지. 종목명 우선 또는 병기 필수.
 *
 * Approach — read every template file in `components/reports/templates/`.
 * For each known US ticker, every occurrence in a `ticker:` field or in
 * an inline string (e.g. `"NVDA +5%"`) must be paired with the company
 * name within the same data object or adjacent characters.
 *
 * The gate is intentionally narrow: it only flags tickers from a
 * curated map of names that have appeared in templates historically.
 * That keeps it deterministic and cheap. New tickers can be added to
 * `TICKER_NAMES` as templates evolve.
 *
 * Companion to:
 * - typography-token-coverage.test.ts (same per-file allowlist pattern)
 * - ai-label-coverage.test.ts (similar legal-side scan)
 */

import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const TEMPLATES_DIR = join(
  __dirname,
  "..",
  "components",
  "reports",
  "templates",
);

/**
 * US tickers we have actually shipped in templates, mapped to a recognizable
 * company name fragment. The gate looks for the ticker, and within a small
 * window of characters, requires *one* of the name fragments to appear.
 *
 * Fragments are case-insensitive substrings — they only need to be unique
 * enough that a co-occurrence is visually obvious to a reader scanning the
 * PDF or HTML preview.
 */
const TICKER_NAMES: Record<string, string[]> = {
  PLTR: ["Palantir", "팰런티어"],
  NVDA: ["NVIDIA", "엔비디아"],
  MSFT: ["Microsoft", "마이크로소프트"],
  META: ["Meta", "메타"],
  DIS: ["Disney", "디즈니"],
  UNH: ["UnitedHealth", "유나이티드헬스"],
  DKNG: ["DraftKings", "드래프트킹스"],
  CRWD: ["CrowdStrike", "크라우드스트라이크"],
  ANET: ["Arista"],
  SHOP: ["Shopify", "쇼피파이"],
  UBER: ["Uber", "우버"],
  PANW: ["Palo Alto"],
  SNOW: ["Snowflake", "스노우플레이크"],
  TSLA: ["Tesla", "테슬라"],
  SMH: ["Semiconductor"],
  BND: ["Vanguard", "Bond"],
  PYPL: ["PayPal", "페이팔"],
  GLD: ["Gold"],
  SCHD: ["Schwab", "Dividend"],
  HD: ["Home Depot", "홈디포"],
  ASML: ["ASML Holding", "ASML"],
  COST: ["Costco", "코스트코"],
  AVGO: ["Broadcom", "브로드컴"],
};

/**
 * Words that *contain* a ticker letter sequence but are not tickers.
 * The default scan boundary `\b` already filters most false positives,
 * but a few short-sequence tickers collide with English words.
 */
const FALSE_POSITIVE_CONTEXTS: Record<string, RegExp[]> = {
  // "HD" appears in "HD메모", "HD 해소" — pre-screen for the standalone form.
  HD: [/\bHD\b/g],
  // "META" can refer to the company or generic English — both are fine,
  // we still want the company-name pairing rule to enforce clarity.
  META: [/\bMETA\b/g, /\bMeta\b/g],
};

/**
 * Returns true if `text` contains any of the provided fragments
 * within `window` characters before or after position `idx`.
 */
function hasNameNearby(
  text: string,
  idx: number,
  fragments: string[],
  window = 120,
): boolean {
  const lo = Math.max(0, idx - window);
  const hi = Math.min(text.length, idx + window);
  const slice = text.slice(lo, hi).toLowerCase();
  return fragments.some((f) => slice.includes(f.toLowerCase()));
}

function listTemplateFiles(): string[] {
  return readdirSync(TEMPLATES_DIR)
    .filter((f) => f.endsWith(".tsx"))
    .map((f) => join(TEMPLATES_DIR, f));
}

describe("sample-report templates: no naked US ticker", () => {
  const files = listTemplateFiles();

  // Sentinel — guarantees the suite always has at least one test even when
  // the templates contain zero tickers (after the 2026-05-31 fabricated-data
  // removal, the templates no longer hardcode any sample tickers, so the
  // dynamic per-ticker `it()` blocks below may generate nothing; an empty
  // suite is treated as a failure by vitest). This also asserts the scan
  // actually found template files to read.
  it("scans the template directory", () => {
    expect(files.length).toBeGreaterThan(0);
  });

  for (const file of files) {
    const filename = file.split("/").pop() ?? file;
    const src = readFileSync(file, "utf-8");

    for (const [ticker, names] of Object.entries(TICKER_NAMES)) {
      // Look for the ticker as a standalone word. Use the explicit
      // FALSE_POSITIVE_CONTEXTS pattern when defined, otherwise the
      // default word boundary scan.
      const patterns = FALSE_POSITIVE_CONTEXTS[ticker] ?? [
        new RegExp(`\\b${ticker}\\b`, "g"),
      ];

      for (const pattern of patterns) {
        const matches = [...src.matchAll(pattern)];
        if (matches.length === 0) continue;

        it(`${filename}: every "${ticker}" appears with a company name`, () => {
          const offenders: { idx: number; snippet: string }[] = [];

          for (const m of matches) {
            const idx = m.index ?? 0;
            if (!hasNameNearby(src, idx, names)) {
              const snippet = src
                .slice(Math.max(0, idx - 40), Math.min(src.length, idx + 60))
                .replace(/\s+/g, " ");
              offenders.push({ idx, snippet });
            }
          }

          expect(
            offenders,
            `naked "${ticker}" detected in ${filename} — expected one of [${names.join(
              ", ",
            )}] within 120 chars. Offenders:\n` +
              offenders
                .map((o) => `  @${o.idx}: …${o.snippet}…`)
                .join("\n"),
          ).toEqual([]);
        });
      }
    }
  }
});
