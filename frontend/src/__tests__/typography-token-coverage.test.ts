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
    cap: 0,
    reason: "W18: 1×11 ticker subline migrated → --pq-text-micro; no raw literals remain",
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

/** Files migrated in PR `refactor/fontsize-phase4-w12` — Phase 4 Top 11-20
 *  offenders. Each file's pre-migration count was 10-12 inline literals; after
 *  migration only sizes with no v3 token (9, 11, 28, 36) remain. The caps
 *  below pin those remainders so a future contributor cannot re-introduce
 *  previously tokenized sizes (12 / 14 / 24 / 32 / 16 / 18 / 20). */
const PHASE4_FILES: ReadonlyArray<{ path: string; cap: number; reason: string }> = [
  {
    path: "components/reports/templates/insider-mirror.tsx",
    cap: 0,
    reason: "W17: 5×9 mono kicker migrated → --pq-text-kicker; no raw literals remain",
  },
  {
    path: "components/home/sector-allocation-donut.tsx",
    cap: 0,
    reason: "W17: 2×9 mono kicker migrated → --pq-text-kicker; no raw literals remain",
  },
  {
    path: "components/reports/templates/risk-board.tsx",
    cap: 0,
    reason: "W18: 7×11 PDF caption + 1×11 paragraph migrated → --pq-text-micro (W17 36px already tokenized); no raw literals remain",
  },
  {
    path: "components/market/overview-paper.tsx",
    cap: 1,
    reason: "W17: 1×9 kicker migrated → --pq-text-kicker; 1×0.45em em-relative unit suffix remains",
  },
  {
    path: "components/settings/v2/broker-card-v2.tsx",
    cap: 0,
    reason: "all 10 literals (12/14/32) migrated → --pq-text-eyebrow/body/h3",
  },
  {
    path: "components/risk/v2/correlation-heatmap.tsx",
    cap: 0,
    reason: "W17: 3×9 ticker label header migrated → --pq-text-kicker; no raw literals remain",
  },
  {
    path: "components/reports/v2/artifact-kind-card.tsx",
    cap: 0,
    reason: "W17: 2×9 micro-label migrated → --pq-text-kicker; no raw literals remain",
  },
  {
    path: "components/reports/templates/burn-rate.tsx",
    cap: 0,
    reason: "W17: 2×9 PDF mono kicker migrated → --pq-text-kicker; no raw literals remain",
  },
  {
    path: "components/profile/v2/identity-card-v2.tsx",
    cap: 0,
    reason: "W17: 1×28 avatar initial migrated → --pq-text-avatar; no raw literals remain",
  },
  {
    path: "components/portfolio/v2/positions-table-v2.tsx",
    cap: 0,
    reason: "all 10 literals (12/14/16) migrated → --pq-text-eyebrow/body/h6",
  },
  {
    path: "components/landing/personas-preview.tsx",
    cap: 0,
    reason: 'all 10 literals (string-form "12px"/"14px"/"24px") migrated → tokens',
  },
  {
    path: "components/home/today-memo-hero.tsx",
    cap: 0,
    reason: "W17: 2×9 meta-strip kicker migrated → --pq-text-kicker; no raw literals remain",
  },
];

makeCapAssertion(
  PHASE4_FILES,
  "typography token coverage — Phase 4 (Top 11-20 sweep) inline fontSize offenders (W12)",
);

/** Files migrated in PR `feat/typography-tokens-phase7-w17` — Phase 7 grid
 *  extension. The v3 token grid was extended in globals.css §3.3 with three
 *  new tokens to close the last token-less buckets that prior waves left
 *  inline:
 *    --pq-text-kicker     9px   (paper kicker / PDF caption / chart axis)
 *    --pq-text-avatar    28px   (avatar initial / large numeric badge)
 *    --pq-text-pdf-hero  36px   (PDF / report hero number)
 *
 *  Every Phase 7 surface migrated 9 / 28 / 36 / 26 (snap → quote 24) raw
 *  literals to tokens. Caps below pin remainders to sizes outside the
 *  current token grid (mostly 11/15/18 — deferred to a future wave once
 *  the design team locks the 11px PDF caption decision). */
const PHASE7_FILES: ReadonlyArray<{ path: string; cap: number; reason: string }> = [
  {
    path: "components/layout/terminal-sidebar.tsx",
    cap: 3,
    reason: "1×9 footer kicker migrated → --pq-text-kicker; 3 unrelated 12/14 literals remain",
  },
  {
    path: "components/charts/interactive-line-chart.tsx",
    cap: 2,
    reason: "1×9 chart tooltip kicker migrated → --pq-text-kicker; 2 unrelated literals remain",
  },
  {
    path: "components/settings/v2/subscription-card-v2.tsx",
    cap: 0,
    reason: "W17: 1×28 secondary heading migrated → --pq-text-avatar (PHASE2 cap 1 → 0)",
  },
  {
    path: "components/home/v2/portfolio-snapshot-card.tsx",
    cap: 7,
    reason: "1×28 NAV value migrated → --pq-text-avatar; 7 unrelated 12/14/15 literals remain",
  },
  {
    path: "components/reports/templates/morning-brief-plus.tsx",
    cap: 2,
    reason: "1×28 tape-tone hero migrated → --pq-text-avatar; 2 unrelated literals remain",
  },
  {
    path: "app/(auth)/signup/oauth-finalize/page.tsx",
    cap: 0,
    reason: "W18: 2×11 PIPA eyebrow + birthdate label migrated → --pq-text-micro (W17 28px already tokenized); no raw literals remain",
  },
  {
    path: "components/reports/templates/earnings-prebrief.tsx",
    cap: 7,
    reason: "2×36 implied-move + quant-signal migrated → --pq-text-pdf-hero; 7 unrelated 12/24 literals remain",
  },
  {
    path: "components/risk/v2/risk-gauge-grid.tsx",
    cap: 8,
    reason: "1×26 unit suffix snap → --pq-text-quote(24); 8 unrelated 12/14/32/44 literals remain",
  },
  {
    path: "components/reports/templates/brag-card.tsx",
    cap: 0,
    reason: "W17: 1×26 hero heading snap → --pq-text-quote(24); no raw literals remain",
  },
];

makeCapAssertion(
  PHASE7_FILES,
  "typography token coverage — Phase 7 (9/28/36 grid extension + 26 snap) inline fontSize offenders (W17)",
);

/** Files migrated in PR `typography-tokens-w18-micro` — Phase 8 micro
 *  grid extension. globals.css §3.3 gains three new tokens:
 *    --pq-text-micro    11px  (PDF caption / mono row label / paper sub-label)
 *    --pq-text-mono-md  17px  (mono row label / brand integer between h6/h5)
 *    --pq-text-callout  22px  (sub-hero callout between h4/quote)
 *  Active migrations also reuse already-defined tokens:
 *    10 → --pq-text-eyebrow-sm (10.5px, 0.5px snap inside anti-alias band)
 *    15 → --pq-text-lead       (exact)
 *  Each surface below previously held raw 10/11/15 literals; after
 *  migration cap is 0 unless an unrelated bucket remains. */
const PHASE8_FILES: ReadonlyArray<{ path: string; cap: number; reason: string }> = [
  {
    path: "components/profile/v2/six-dimensions-grid.tsx",
    cap: 8,
    reason: "W18: 1×11 sub-eyebrow loading-state migrated → --pq-text-micro; 8 unrelated 12/14 literals remain",
  },
  {
    path: "components/profile/v2/peer-benchmark-block-v2.tsx",
    cap: 8,
    reason: "W18: 1×11 sub-eyebrow loading-state migrated → --pq-text-micro; 8 unrelated 12/14 literals remain",
  },
  {
    path: "components/signals/v2/signal-card.tsx",
    cap: 8,
    reason: "W18: 1×10 stale-chip kicker migrated → --pq-text-eyebrow-sm (10.5px snap); 8 unrelated 12/14 literals remain",
  },
  {
    path: "components/landing/three-layers.tsx",
    cap: 0,
    reason: "W18: 1×15 serif body migrated → --pq-text-lead; no raw literals remain",
  },
  {
    path: "components/landing/deposition-teaser.tsx",
    cap: 7,
    reason: "W18: 1×15 question copy migrated → --pq-text-lead; 7 unrelated 12/14 literals remain",
  },
  {
    path: "components/portfolio/v2/watchlist-mini.tsx",
    cap: 7,
    reason: "W18: 1×15 display name migrated → --pq-text-lead; 7 unrelated 12/14 literals remain",
  },
  {
    path: "components/reports/empty-state.tsx",
    cap: 3,
    reason: "W18: 1×15 serif body migrated → --pq-text-lead; 3 unrelated 12/14 literals remain",
  },
  {
    path: "components/reports/v2/reports-hero-v2.tsx",
    cap: 2,
    reason: "W18: 1×15 serif lead migrated → --pq-text-lead; 2 unrelated 12/14 literals remain",
  },
  {
    path: "app/features/personas/page.tsx",
    cap: 2,
    reason: "W18: 1×15 serif body migrated → --pq-text-lead; 2 unrelated 12/14 literals remain",
  },
];

makeCapAssertion(
  PHASE8_FILES,
  "typography token coverage — Phase 8 (10/11/15 micro grid extension) inline fontSize offenders (W18)",
);

/** Treewide cap — Phase 9 (W20 long-tail closure, 2026-05-12).
 *
 * After W20 globals.css §3.3 gained three terminal tokens:
 *   --pq-text-gauge     44px  (risk-gauge solo numeric)
 *   --pq-text-hero-num  48px  (hero stat numeric — settings/risk/year-end-letter)
 *   --pq-text-pdf-micro  6px  (PDF micro footnote — pdf-primitives print only)
 *
 * The W20 sweep migrated 201 raw fontSize literals across 80 files,
 * collapsing the corpus from 216 → 15. The 15 remaining literals are all
 * intentional non-token sites where a CSS custom property cannot resolve:
 *   - app/opengraph-image.tsx (4)   Next ImageResponse — edge runtime, no var resolution
 *   - app/global-error.tsx (6)      root error boundary — runs without document tokens
 *   - components/terminal/candlestick-chart.tsx (1)  Lightweight Charts numeric API
 *   - components/landing/top-nav.tsx (1)             8px chevron glyph (sub-kicker)
 *   - components/market/overview-paper.tsx (1)       0.45em em-relative unit suffix
 *   - app/(auth)/signup/_v2/page-v2.tsx (1)          0.85em em-relative inline note
 *   - components/ui/editorial.tsx (1)                JSDoc comment example
 *
 * The treewide cap below pins these counts. Any new file that introduces
 * a token-eligible raw literal (9/10/11/12/13/14/15/16/17/18/19/20/22/24/
 * 28/32/36/44/48/6) will push the count above the cap and fail this gate.
 * Adding a new intentional allowlist entry requires bumping TREEWIDE_CAP
 * and documenting the reason in the list above.
 */
const TREEWIDE_CAP = 15;
const TREEWIDE_GLOB_DIRS = ["components", "app"] as const;

describe("typography token coverage — Phase 9 (W20 long-tail closure) treewide cap", () => {
  it(`raw fontSize literal count across components/ + app/ ≤ ${TREEWIDE_CAP}`, async () => {
    const { readdirSync, readFileSync, statSync } = await import("node:fs");
    const offenders: string[] = [];

    function walk(dir: string): void {
      for (const entry of readdirSync(dir)) {
        const full = join(dir, entry);
        const st = statSync(full);
        if (st.isDirectory()) {
          walk(full);
        } else if (st.isFile() && (full.endsWith(".tsx") || full.endsWith(".ts"))) {
          const text = readFileSync(full, "utf-8");
          const lines = text.split("\n");
          for (let i = 0; i < lines.length; i++) {
            if (RAW_FONTSIZE.test(lines[i])) {
              offenders.push(`${full.replace(FRONTEND_SRC, "")}:${i + 1} → ${lines[i].trim()}`);
            }
          }
        }
      }
    }

    for (const sub of TREEWIDE_GLOB_DIRS) {
      walk(join(FRONTEND_SRC, sub));
    }

    if (offenders.length > TREEWIDE_CAP) {
      const detail = offenders.slice(0, 30).join("\n  ");
      throw new Error(
        `Found ${offenders.length} raw fontSize literal(s) across components/ + app/, ` +
          `treewide cap is ${TREEWIDE_CAP}. New token-eligible literals must use ` +
          `var(--pq-text-*) — see globals.css §3.3 for the full grid (9/10/11/12/13/` +
          `14/15/16/17/18/19/20/22/24/28/32/36/44/48/6).\n  ${detail}`,
      );
    }
    expect(offenders.length).toBeLessThanOrEqual(TREEWIDE_CAP);
  });
});
