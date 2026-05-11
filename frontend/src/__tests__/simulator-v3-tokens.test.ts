/**
 * Regression gate — /simulator/* must stay on v3 Vantablack tokens.
 *
 * The simulator (what-if Time Machine, future counterfactual surfaces) is the
 * public viral-acquisition entry point. It was originally built against the
 * Nexora light theme (`bg-white`, `text-slate-*`, `bg-green-*`, etc.) and
 * migrated to v3 Vantablack + Bronze (CRITICAL #1 in design audit Wave A.4).
 *
 * If a future contributor adds a new simulator surface using light-theme
 * Tailwind utilities, this test fails — forcing them to either use the
 * v3 tokens (`var(--pq-ink)`, `var(--pq-bronze)`, `var(--pq-ivory-line)`,
 * `var(--pq-text-*)`) or the v3 utility classes (`pq-ink-btn-bronze`,
 * `pq-ink-btn-ghost`, `pq-ink-label`, `pq-ink-card`, `pq-skeleton-dark`).
 *
 * Companion to: design-token-drift skill (broader project-wide scan).
 * This file is a tight, fast simulator-only gate that runs in CI on every PR.
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const FRONTEND_SRC = join(__dirname, "..");
const SIMULATOR_DIR = join(FRONTEND_SRC, "app", "simulator");

/** Tailwind/CSS markers that signal Nexora light-theme creep into the dark
 *  surface. Each is a substring match against a source line. */
const FORBIDDEN_PATTERNS: Array<{ pattern: RegExp; reason: string }> = [
  { pattern: /\bbg-white\b/, reason: "bg-white — use var(--pq-ink) or pq-ink-card" },
  {
    pattern: /\bborder-slate-\d/,
    reason: "border-slate-* — use var(--pq-ivory-line)",
  },
  {
    pattern: /\btext-slate-\d/,
    reason: "text-slate-* — use var(--pq-text-primary|secondary) or var(--pq-ivory)",
  },
  {
    pattern: /\bbg-slate-(?!900\b)\d/,
    reason: "bg-slate-* (light variants) — use ink or ghost ivory tint",
  },
  {
    pattern: /\bbg-(green|emerald)-\d/,
    reason: "bg-(green|emerald)-* — use var(--pq-bronze) or KR pos-red",
  },
  {
    pattern: /\bbg-blue-\d/,
    reason: "bg-blue-* — use var(--pq-bronze) or KR neg-blue (#7aa0c8)",
  },
  {
    pattern: /\bdivide-slate-\d/,
    reason: "divide-slate-* — use 1px solid var(--pq-ivory-line-soft)",
  },
  {
    pattern: /\bfocus:ring-(slate|green|blue|emerald)-\d/,
    reason: "focus:ring-* (non-bronze) — use ring var(--pq-bronze)",
  },
  {
    pattern: /\bfocus:border-slate-\d/,
    reason: "focus:border-slate-* — use focus:ring-* var(--pq-bronze)",
  },
  {
    pattern: /\bshadow-lg\b/,
    reason:
      "shadow-lg — Vantablack v3 uses ivory hairlines, not white shadows. Remove or use border var(--pq-ivory-line).",
  },
];

const TARGET_EXTS = new Set([".ts", ".tsx"]);

function walk(dir: string, acc: string[] = []): string[] {
  let entries: string[];
  try {
    entries = readdirSync(dir);
  } catch {
    return acc;
  }
  for (const name of entries) {
    if (name === "node_modules" || name === ".next") continue;
    const full = join(dir, name);
    let st;
    try {
      st = statSync(full);
    } catch {
      continue;
    }
    if (st.isDirectory()) {
      walk(full, acc);
    } else if (TARGET_EXTS.has(name.slice(name.lastIndexOf(".")))) {
      // Exclude tests so docstring mentions don't self-trigger.
      if (name.endsWith(".test.ts") || name.endsWith(".test.tsx")) continue;
      if (name.endsWith(".spec.ts") || name.endsWith(".spec.tsx")) continue;
      acc.push(full);
    }
  }
  return acc;
}

/** Strip comments so `// bg-white` in a code comment doesn't false-fire.
 *  Heuristic: line-comments only (block comments would need parsing). */
function stripLineComment(line: string): string {
  // crude — find the first `//` that isn't inside a string literal.
  // Good enough for our flat scan: we only care about *user-visible*
  // class strings, which never contain `//`.
  const idx = line.indexOf("//");
  if (idx === -1) return line;
  // ensure the // isn't inside a URL like https://... — bail if preceded by `:`.
  if (line[idx - 1] === ":") return line;
  return line.slice(0, idx);
}

describe("design v3 lock-in — /simulator/* uses Vantablack tokens", () => {
  const files = walk(SIMULATOR_DIR);

  it("collects at least one simulator file (sanity)", () => {
    expect(files.length).toBeGreaterThan(0);
  });

  for (const { pattern, reason } of FORBIDDEN_PATTERNS) {
    it(`no /simulator/* file uses ${pattern.source}`, () => {
      const offenders: string[] = [];
      for (const file of files) {
        const text = readFileSync(file, "utf-8");
        const lines = text.split("\n");
        for (let i = 0; i < lines.length; i++) {
          const code = stripLineComment(lines[i]);
          if (pattern.test(code)) {
            offenders.push(
              `${relative(FRONTEND_SRC, file)}:${i + 1} → ${lines[i].trim()}`,
            );
          }
        }
      }
      if (offenders.length > 0) {
        const detail = offenders.slice(0, 8).join("\n  ");
        throw new Error(
          `${pattern.source} matched ${offenders.length} line(s) in /simulator/. ` +
            `${reason}\n  ${detail}`,
        );
      }
      expect(offenders).toEqual([]);
    });
  }
});
