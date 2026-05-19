import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

/**
 * Wave 4-B (2026-05-20) — local fmt redefinition guard.
 *
 * History: Wave 2 sweep (35+ files) + Wave 3 (further consolidation) +
 * Wave 4-B helpers (fmtPctSignedMinus / fmtMoneyPlain / fmtKrwAbbrev.trimTrailing)
 * unified frontend currency/percent formatting in `@/lib/format`. To prevent
 * regression — every previously-removed local `fmtPct`/`fmtMoney`/`fmtKrw`/
 * `fmtUsd` is one PR away from reappearing — this rule blocks any NEW
 * top-level `function fmtPct…` / `function fmtMoney…` / `function fmtKrw…` /
 * `function fmtUsd…` declaration anywhere in `src/`.
 *
 * Exceptions:
 *   - `src/lib/format.ts` itself defines the canonical helpers and is exempt.
 *   - `src/lib/__tests__/format.test.ts` may shadow names inside its block.
 *   - Two-line delegation wrappers (`function fmtMoney(n,c){ return fmtMoneyPlain(...) }`)
 *     still trigger the rule by design — replace the wrapper with a direct
 *     `import { fmtMoneyPlain }` and `fmtMoneyPlain(n,c,2)` callsite instead.
 *
 * If you genuinely need a new fmt helper with novel semantics, add it to
 * `src/lib/format.ts` with a vitest case, NOT inline in a component.
 */
const fmtRedefinitionGuard = {
  files: ["src/**/*.{ts,tsx}"],
  ignores: [
    "src/lib/format.ts",
    "src/lib/__tests__/format.test.ts",
  ],
  rules: {
    // Phase 1 (Wave 4-B 2026-05-20): "warn" surfaces drift in dev/CI output
    //   without breaking the 20 pre-existing intentionally-inlined sites
    //   (documented inline as "NOT migrated — divergence: …"). New PRs
    //   adding a top-level fmt redefinition will see the warning surfaced
    //   in `next build` and code review.
    // Phase 2 (planned post-launch): escalate to "error" after the existing
    //   20 sites have either been migrated or annotated with explicit
    //   `// eslint-disable-next-line no-restricted-syntax` opt-outs.
    "no-restricted-syntax": [
      "warn",
      {
        selector:
          "FunctionDeclaration[id.name=/^fmt(Pct|Money|Krw|Usd)/]",
        message:
          "Do not redefine fmt helpers locally — import from @/lib/format. " +
          "Wave 4-B added fmtPctSignedMinus / fmtMoneyPlain / fmtMoneyPlainSigned " +
          "/ fmtKrwAbbrev({trimTrailing}) to cover the previously-inlined patterns. " +
          "If you need novel semantics, add the helper to lib/format.ts with tests.",
      },
    ],
  },
};

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  fmtRedefinitionGuard,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
