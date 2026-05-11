/**
 * Regression gate — /growth surfaces must stay on v3 Vantablack tokens.
 *
 * The Solo Founder Growth OS (`/growth` page + `components/growth/*`) was
 * originally built against the Nexora light theme (`bg-white`, `text-slate-*`,
 * `bg-green-*`, `border-green-*`, etc.) and migrated to v3 Vantablack +
 * Bronze in W6.2 (design audit Wave A.4 CRITICAL #2 + #3).
 *
 * If a future contributor adds a new growth surface using light-theme
 * Tailwind utilities, this test fails — forcing them to either use the
 * v3 tokens (`var(--pq-ink)`, `var(--pq-bronze)`, `var(--pq-ivory-line)`,
 * `var(--pq-text-*)`) or the v3 utility classes (`pq-ink-btn-bronze`,
 * `pq-ink-card`, etc.).
 *
 * Companion to: simulator-v3-tokens.test.ts (same pattern for /simulator/*).
 * This file is a tight, fast growth-only gate that runs in CI on every PR.
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const FRONTEND_SRC = join(__dirname, "..");
const GROWTH_PAGE_DIR = join(FRONTEND_SRC, "app", "(dashboard)", "growth");
const GROWTH_COMPONENTS_DIR = join(FRONTEND_SRC, "components", "growth");

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
    pattern: /\bfill-slate-\d/,
    reason: "fill-slate-* — use fill='rgba(245,240,232,0.45)' or var(--pq-bronze)",
  },
  {
    pattern: /\bbg-(green|emerald)-\d/,
    reason: "bg-(green|emerald)-* — use var(--pq-bronze) or KR pos-red",
  },
  {
    pattern: /\btext-(green|emerald)-\d/,
    reason: "text-(green|emerald)-* — use var(--pq-bronze) or #7DD897",
  },
  {
    pattern: /\bborder-(green|emerald)-\d/,
    reason: "border-(green|emerald)-* — use border-[var(--pq-bronze)]",
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
    pattern: /\bfocus:border-(slate|green|emerald)-\d/,
    reason: "focus:border-* (non-bronze) — use focus:border-[var(--pq-bronze)]",
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
      if (name.endsWith(".test.ts") || name.endsWith(".test.tsx")) continue;
      if (name.endsWith(".spec.ts") || name.endsWith(".spec.tsx")) continue;
      acc.push(full);
    }
  }
  return acc;
}

/** Strip line-comments so `// bg-white` in a code comment doesn't false-fire. */
function stripLineComment(line: string): string {
  const idx = line.indexOf("//");
  if (idx === -1) return line;
  // Don't strip inside URLs (https://...)
  if (line[idx - 1] === ":") return line;
  return line.slice(0, idx);
}

describe("design v3 lock-in — /growth surfaces use Vantablack tokens", () => {
  const files = [
    ...walk(GROWTH_PAGE_DIR),
    ...walk(GROWTH_COMPONENTS_DIR),
  ];

  it("collects at least one growth file (sanity)", () => {
    expect(files.length).toBeGreaterThan(0);
  });

  for (const { pattern, reason } of FORBIDDEN_PATTERNS) {
    it(`no /growth file uses ${pattern.source}`, () => {
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
          `${pattern.source} matched ${offenders.length} line(s) in /growth. ` +
            `${reason}\n  ${detail}`,
        );
      }
      expect(offenders).toEqual([]);
    });
  }
});
