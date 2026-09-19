/**
 * Guard: every font stack must carry a Hangul-capable family.
 *
 * Why this test exists
 * --------------------
 * Geist, JetBrains Mono, Source Serif 4 and Playfair Display — the four
 * next/font families this product loads — are all LATIN-ONLY. None of them
 * has a single Hangul glyph.
 *
 * A stack missing a Korean face does not fail loudly. The browser silently
 * falls through to whatever the OS offers, so Korean rendered in a different
 * face (and, via next/font's `... Fallback` metric-adjusted stand-ins, at a
 * distorted width) from the Latin sitting next to it in the same sentence.
 * Measured on 2026-09-19 at 375px: 126 of 137 Korean text nodes on the
 * landing page resolved to `"Source Serif 4", "Source Serif 4 Fallback"` —
 * a stack with no Korean in it at all.
 *
 * It had been patched by hand, one rule at a time (.pq-hero-h1 got its
 * Pretendard fallback in commit 67a4d966, 2026-06-06) — the same failure
 * shape as the ~20 scattered inline `wordBreak: "keep-all"` styles. Hand
 * patching does not hold, so the invariant is asserted here instead.
 *
 * Scope: globals.css is the token/design-system layer. PDF + report
 * surfaces (.pq-report / .pq-pdf-* / .report-surface) are excluded — they
 * render through WeasyPrint with its own font configuration, not the
 * browser, and their serif stack already names Noto Serif KR.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/** Families that actually carry Hangul glyphs. */
const KOREAN_FAMILIES = [
  "Pretendard",
  "Apple SD Gothic",
  "AppleGothic",
  "Malgun",
  "Noto Sans KR",
  "Noto Serif KR",
  "Nanum",
  "Source Han",
];

const GLOBALS = resolve(__dirname, "../globals.css");

interface Decl {
  line: number;
  value: string;
  selector: string;
}

function selectorBefore(css: string, pos: number): string {
  const head = css.slice(0, pos);
  const open = head.lastIndexOf("{");
  if (open < 0) return "";
  // `open - 1`: lastIndexOf(s, from) can return `from` itself, and `open` IS
  // a "{" — searching from `open` would return `open` and slice an empty
  // selector, silently classifying every rule as non-report.
  const start = Math.max(
    head.lastIndexOf("}", open - 1),
    head.lastIndexOf("{", open - 1),
    head.lastIndexOf(";", open - 1),
    head.lastIndexOf("*/", open - 1),
  );
  return head.slice(start + 1, open).replace(/\s+/g, " ").trim();
}

function fontFamilyDecls(css: string): Decl[] {
  const out: Decl[] = [];
  const re = /font-family:\s*([^;]+);/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(css))) {
    out.push({
      line: css.slice(0, m.index).split("\n").length,
      value: m[1].trim(),
      selector: selectorBefore(css, m.index),
    });
  }
  return out;
}

const hasKorean = (v: string) => KOREAN_FAMILIES.some((f) => v.includes(f));

/** @font-face family NAMING (the `font-family` inside an @font-face block)
 *  declares a name, it is not a stack — nothing to fall back to. */
const isFontFaceName = (d: Decl) => d.value.startsWith('"PQ ');

/** WeasyPrint surfaces — different renderer, different font config. */
const isReportSurface = (d: Decl) =>
  /pq-pdf|pq-report|report-surface/.test(d.selector);

describe("globals.css — Korean coverage in every font stack", () => {
  const css = readFileSync(GLOBALS, "utf8");
  const decls = fontFamilyDecls(css);

  it("finds the declarations at all (guards against the regex silently rotting)", () => {
    expect(decls.length).toBeGreaterThan(50);
  });

  it("every screen-surface font-family names a Hangul-capable family", () => {
    const offenders = decls
      .filter((d) => !isFontFaceName(d) && !isReportSurface(d))
      .filter((d) => !hasKorean(d.value))
      .map((d) => `globals.css:${d.line}  ${d.value}`);

    expect(
      offenders,
      `These stacks have no Hangul-capable family, so Korean falls through to ` +
        `an OS-dependent face:\n${offenders.join("\n")}\n\n` +
        `Append "Pretendard Variable", Pretendard before the generic keyword.`,
    ).toEqual([]);
  });

  it("the four Tailwind font tokens each carry Pretendard", () => {
    // These drive the font-sans / font-mono / font-serif / font-display
    // utilities, i.e. the path every NEW component takes.
    for (const token of [
      "--font-sans",
      "--font-mono",
      "--font-serif",
      "--font-display",
    ]) {
      const m = new RegExp(`\\n\\s*\\${token}:\\s*([^;]+);`).exec(css);
      expect(m, `${token} not found in globals.css`).not.toBeNull();
      expect(m![1], `${token} is missing a Korean face`).toContain("Pretendard");
    }
  });

  it("the --pq-font-* aliases each carry Pretendard", () => {
    for (const token of [
      "--pq-font-sans",
      "--pq-font-mono",
      "--pq-font-serif",
      "--pq-font-display",
    ]) {
      const m = new RegExp(`\\n\\s*\\${token}:\\s*([^;]+);`).exec(css);
      expect(m, `${token} not found in globals.css`).not.toBeNull();
      expect(m![1], `${token} is missing a Korean face`).toContain("Pretendard");
    }
  });
});
