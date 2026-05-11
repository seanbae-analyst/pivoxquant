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

/** Files migrated in PR `fontsize-phase2-w9` — Top 6-10 offenders.
 *  Caps below pin the count of *remaining* raw literals (sizes with no exact
 *  v3 token — 9, 11, 15, 16, 18, 20, 28). Migrated sizes (12 / 14 / 24 / 32)
 *  must stay tokenized; future contributors cannot re-introduce them. */
const PHASE2_FILES: ReadonlyArray<{ path: string; cap: number; reason: string }> = [
  {
    path: "app/(dashboard)/home/_v1/page-v1.tsx",
    cap: 10,
    reason:
      "9× 9px chip/micro-label (below HIG floor) + 1× 20px sub-heading — no exact v3 token",
  },
  {
    path: "components/market/indices-detail-paper.tsx",
    cap: 7,
    reason:
      "6× 9px paper kicker (Vantablack paper aesthetic) + 1× 18px hero number — no exact v3 token",
  },
  {
    path: "components/companion/chat-panel.tsx",
    cap: 4,
    reason:
      "3× 15px chat body + 1× 9px micro-timestamp — no exact v3 token between body(14)/quote(24)",
  },
  {
    path: "components/settings/v2/subscription-card-v2.tsx",
    cap: 1,
    reason: "1× 28px secondary heading — no exact v3 token between quote(24) and h3(32)",
  },
  {
    path: "app/pricing/page.tsx",
    cap: 2,
    reason: "2× 15px/16px tier body copy — no exact v3 token between body(14) and quote(24)",
  },
  {
    path: "components/signals/signal-memo-strip.tsx",
    cap: 1,
    reason: "1× 18px memo headline — no exact v3 token between body(14) and quote(24)",
  },
  {
    path: "components/reports/templates/dd-checklist.tsx",
    cap: 1,
    reason: "1× 11px tab number (uppercase eyebrow micro-variant) — no exact v3 token",
  },
  {
    path: "components/profile/v2/companion-entry-v2.tsx",
    cap: 0,
    reason: "all literals match an exact v3 token (12 / 14 / 24)",
  },
  {
    path: "app/(dashboard)/settings/_v2/page-v2.tsx",
    cap: 0,
    reason: "all literals match an exact v3 token (12 / 14)",
  },
  {
    path: "app/(dashboard)/companion/page.tsx",
    cap: 2,
    reason: "2× 15px hero-card body copy — no exact v3 token between body(14) and quote(24)",
  },
];

/** Count inline `fontSize:` lines whose value starts with a raw digit
 *  (catches both bare-number `fontSize: 12` and string-px `fontSize: "12px"`). */
const RAW_FONTSIZE = /fontSize:\s*"?[0-9]/;

/** Count token usages of the form `fontSize: "var(--pq-text-...)"`. */
const TOKEN_FONTSIZE = /fontSize:\s*"var\(--pq-text-/;

function makeCapAssertion(
  files: ReadonlyArray<{ path: string; cap: number; reason: string }>,
  label: string,
) {
  describe(label, () => {
    for (const { path, cap, reason } of files) {
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
}

makeCapAssertion(TOP5_FILES, "typography token coverage — Top 5 inline fontSize offenders (W8)");
makeCapAssertion(
  PHASE2_FILES,
  "typography token coverage — Phase 2 (Top 6-10) inline fontSize offenders (W9)",
);

/** Files migrated in PR `typography-tokens-extension-w10` — Phase 3
 *  high-impact sweep using new tokens (--pq-text-button/lead/h6/h5/h4)
 *  for 13/15/16/18/20px sizes. Caps below pin the count of *remaining*
 *  raw literals (sizes outside the new token set — primarily 12/14/9/24
 *  that still match earlier-step tokens or HIG-borderline micro-labels).
 *  Any future 13/15/16/18/20 introduction in these files will exceed the
 *  cap. Phase 4 will sweep the remaining 32 sites in low-impact files
 *  plus tree-wide 12/14/24/32 ratchet. */
const PHASE3_FILES: ReadonlyArray<{ path: string; cap: number; reason: string }> = [
  {
    path: "components/landing/report-flip-card.tsx",
    cap: 0,
    reason: "4 literals (2×18, 2×20) migrated → --pq-text-h5/h4; no others remain",
  },
  {
    path: "components/reports/v2/latest-artifact-card.tsx",
    cap: 9,
    reason: "2×15 + 1×18 migrated → --pq-text-lead/h5; 9 unrelated literals remain (12/14)",
  },
  {
    path: "components/landing/engine-models-drawer.tsx",
    cap: 0,
    reason: "3×15 migrated → --pq-text-lead; no others remain",
  },
  {
    path: "components/companion/chat-panel.tsx",
    cap: 1,
    reason: "3×15 migrated → --pq-text-lead; 1×9 micro-timestamp remains (HIG borderline)",
  },
  {
    path: "components/risk/v2/seven-layer-breakdown.tsx",
    cap: 8,
    reason: "1×16 + 1×18 migrated → --pq-text-h6/h5; 8 unrelated literals remain (12/14)",
  },
  {
    path: "components/risk/v2/sector-exposure-block.tsx",
    cap: 0,
    reason: "2×16 leader-name migrated → --pq-text-h6; no others remain",
  },
  {
    path: "components/risk/v2/concentration-table.tsx",
    cap: 6,
    reason: "2×18 migrated → --pq-text-h5; 6 unrelated literals remain (12/14)",
  },
  {
    path: "components/portfolio/v2/portfolio-hero-v2.tsx",
    cap: 4,
    reason: "2×18 migrated → --pq-text-h5; 4 unrelated literals remain (12/14)",
  },
  {
    path: "components/portfolio/ledger-book-paper.tsx",
    cap: 2,
    reason: "2×15 migrated → --pq-text-lead; 2×9 micro-label remain (paper aesthetic)",
  },
  {
    path: "components/landing/landing-v2.tsx",
    cap: 4,
    reason: "1×15 + 1×18 migrated → --pq-text-lead/h5; 4 unrelated literals remain (12/14)",
  },
  {
    path: "components/landing/feature-page-shell.tsx",
    cap: 8,
    reason: "1×15 + 1×20 migrated → --pq-text-lead/h4; 8 unrelated literals remain (12/14)",
  },
  {
    path: "app/pricing/page.tsx",
    cap: 0,
    reason: "1×15 + 1×16 migrated → --pq-text-lead/h6; no others remain (only PHASE2 caps)",
  },
  {
    path: "app/(dashboard)/growth/page.tsx",
    cap: 0,
    reason: "2×18 migrated → --pq-text-h5; no others remain",
  },
  {
    path: "app/(dashboard)/companion/page.tsx",
    cap: 0,
    reason: "2×15 migrated → --pq-text-lead; no others remain",
  },
  {
    path: "app/(auth)/signup/_v2/page-v2.tsx",
    cap: 8,
    reason: "2×13 migrated → --pq-text-button; 8 unrelated literals remain (12/14)",
  },
  {
    path: "app/(auth)/login/_v2/page-v2.tsx",
    cap: 3,
    reason: "1×13 + 1×16 migrated → --pq-text-button/h6; 3 unrelated literals remain (12/14)",
  },
  {
    path: "components/signals/v2/top-movers-strip.tsx",
    cap: 6,
    reason: "1×18 migrated → --pq-text-h5; 6 unrelated literals remain (12/14)",
  },
  {
    path: "components/signals/v2/signals-hero-v2.tsx",
    cap: 1,
    reason: "1×15 migrated → --pq-text-lead; 1×12 unrelated literal remains",
  },
  {
    path: "components/signals/v2/signals-filter-bar.tsx",
    cap: 4,
    reason: "1×16 migrated → --pq-text-h6; 4 unrelated literals remain (12)",
  },
  {
    path: "components/signals/signal-memo-strip.tsx",
    cap: 0,
    reason: "1×18 migrated → --pq-text-h5; no others remain (only PHASE2 cap)",
  },
];

makeCapAssertion(
  PHASE3_FILES,
  "typography token coverage — Phase 3 (15/16/18/20/13 sweep) inline fontSize offenders (W10)",
);
