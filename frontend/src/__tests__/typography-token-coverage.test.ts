/**
 * Regression gate — Top 5 inline `fontSize:` offender files (W8 migration)
 * must continue using v3 typography tokens (`var(--pq-text-*)`), not raw
 * numeric literals.
 *
 * Background — design audit Wave A.4 HIGH #7. The PivoxQuant v3 design
 * system locks typography to an 11-step token scale defined in
 * `globals.css` (--pq-text-eyebrow, --pq-text-body, --pq-text-h3, etc.).
 * Top offender files originally carried 27/26/19/18/17 raw `fontSize:`
 * literals each (105 total across the five). PR `fontsize-top5-migration-w8`
 * migrated all literals whose dimensions match an exact token to the token.
 *
 * Remaining literals are sizes with no exact v3 token (e.g. 9px, 15px,
 * 16px, 18px, 20px) — kept inline pending a future token-scale extension.
 * Per-file caps below pin those remainders so a future contributor cannot
 * re-introduce previously migrated literals (12 / 14 / 24 / 32 / clamps).
 *
 * Companion to: growth-v3-tokens.test.ts (same pattern for /growth surface).
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const FRONTEND_SRC = join(__dirname, "..");

/** Files migrated in PR `fontsize-top5-migration-w8`. */
const TOP5_FILES: ReadonlyArray<{ path: string; cap: number; reason: string }> = [
  {
    path: "components/settings/v2/privacy-card-v2.tsx",
    cap: 1,
    reason: "1× 20px modal heading — no exact v3 token between body(14) and quote(24)",
  },
  {
    path: "components/landing/report-flip-card.tsx",
    cap: 4,
    reason: "2× 18px back-face heading, 2× 20px front-face heading — no exact v3 token",
  },
  {
    path: "components/risk/v2/sector-exposure-block.tsx",
    cap: 2,
    reason: "2× 16px leader-name (Playfair) — 종목명 main pattern, no exact v3 token",
  },
  {
    path: "components/landing/engine-models-drawer.tsx",
    cap: 3,
    reason: "3× 15px body copy — no exact v3 token between body(14) and quote(24)",
  },
  {
    path: "components/portfolio/ledger-book-paper.tsx",
    cap: 4,
    reason: "2× 9px micro-label (below HIG floor), 2× 15px paper body — no exact v3 token",
  },
];

/** Count inline `fontSize:` lines whose value starts with a raw digit
 *  (catches both bare-number `fontSize: 12` and string-px `fontSize: "12px"`). */
const RAW_FONTSIZE = /fontSize:\s*"?[0-9]/;

/** Count token usages of the form `fontSize: "var(--pq-text-...)"`. */
const TOKEN_FONTSIZE = /fontSize:\s*"var\(--pq-text-/;

describe("typography token coverage — Top 5 inline fontSize offenders", () => {
  for (const { path, cap, reason } of TOP5_FILES) {
    it(`${path}: raw fontSize literal count ≤ ${cap} (${reason})`, () => {
      const text = readFileSync(join(FRONTEND_SRC, path), "utf-8");
      const lines = text.split("\n");
      const offenders: string[] = [];
      for (let i = 0; i < lines.length; i++) {
        if (RAW_FONTSIZE.test(lines[i])) {
          offenders.push(`${path}:${i + 1} → ${lines[i].trim()}`);
        }
      }
      if (offenders.length > cap) {
        const detail = offenders.slice(0, 12).join("\n  ");
        throw new Error(
          `Found ${offenders.length} raw fontSize literal(s) in ${path}, ` +
            `cap is ${cap}. Use var(--pq-text-eyebrow|caption|body|quote|h3) ` +
            `where the size matches an exact v3 token.\n  ${detail}`,
        );
      }
      expect(offenders.length).toBeLessThanOrEqual(cap);
    });

    it(`${path}: at least one v3 token reference (sanity)`, () => {
      const text = readFileSync(join(FRONTEND_SRC, path), "utf-8");
      expect(TOKEN_FONTSIZE.test(text)).toBe(true);
    });
  }
});
