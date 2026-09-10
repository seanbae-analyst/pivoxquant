/**
 * The text tokens must stay readable on Vantablack.
 *
 * Measured against the running landing page on 2026-09-10: 20 rendered text
 * nodes fell below WCAG AA, across 8 distinct colour/size combinations. The
 * two that mattered most were the ones the law requires us to show —
 *
 *   "PivoxQuant is not a licensed investment…"   3.40:1  (needs 4.5)
 *   상호 / 대표 / 사업자등록번호 (정통망법 §62①)   4.05:1
 *
 * — and the worst was 1.57:1 on "스크롤 또는 SPACE", the only instruction for
 * getting past a full-viewport splash. A palette this dark makes low-alpha
 * text look intentional rather than broken, which is why it survived: nothing
 * measured it.
 *
 * This pins the token values. Ivory needs alpha ≥ 0.49 on #050505 and bronze
 * ≥ 0.76 — computed, not guessed — so a token edited back down fails here.
 *
 * Note --pq-bronze-wash (139,111,71): it cannot reach 4.5 at ANY alpha, since
 * fully opaque it is 4.33:1. It is a wash for fills and borders; using it for
 * small text is a mistake no opacity fixes, and the test below says so.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const CSS = readFileSync(join(process.cwd(), "src/app/globals.css"), "utf8");

/** Vantablack — the ground every dashboard and landing surface sits on. */
const GROUND: [number, number, number] = [5, 5, 5];

const AA_BODY = 4.5;

function luminance([r, g, b]: number[]): number {
  const f = (v: number) => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

function contrast(rgb: number[], alpha: number, bg = GROUND): number {
  const eff = rgb.map((v, i) => v * alpha + bg[i] * (1 - alpha));
  const [l1, l2] = [luminance(eff), luminance(bg)];
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

/** Read `--name: rgba(r, g, b, a)` out of globals.css. */
function token(name: string): { rgb: number[]; alpha: number } {
  const m = CSS.match(
    new RegExp(`--${name}:\\s*rgba\\(([^)]+)\\)`),
  );
  if (!m) throw new Error(`token --${name} not found in globals.css`);
  const parts = m[1].split(",").map((x) => parseFloat(x.trim()));
  return { rgb: parts.slice(0, 3), alpha: parts[3] ?? 1 };
}

// Tokens used as `color` on body-sized text.
const TEXT_TOKENS = [
  "pq-ivory-soft",
  "pq-ivory-mid",
  "pq-ivory-dim",
  "pq-ivory-faint",
];

describe("text tokens meet WCAG AA on Vantablack", () => {
  it.each(TEXT_TOKENS)("--%s", (name) => {
    const { rgb, alpha } = token(name);
    const ratio = contrast(rgb, alpha);
    expect(
      ratio,
      `--${name} is ${ratio.toFixed(2)}:1 at alpha ${alpha}; AA needs ${AA_BODY}. ` +
        `Ivory (245,240,232) needs alpha ≥ 0.49 against #050505.`,
    ).toBeGreaterThanOrEqual(AA_BODY);
  });

  it("--pq-ivory-faint is the floor, and it clears AA", () => {
    // It was 0.45 → 4.05:1 until 2026-09-10. Named explicitly because it is
    // the dimmest text token: if it passes, every token above it passes.
    const { alpha } = token("pq-ivory-faint");
    expect(alpha).toBeGreaterThanOrEqual(0.49);
  });
});

describe("bronze-wash is not a text colour", () => {
  it("cannot reach AA even fully opaque, so nothing should treat it as text", () => {
    const m = CSS.match(/--pq-bronze-wash-rgb:\s*([\d\s,]+);/);
    expect(m, "--pq-bronze-wash-rgb missing").toBeTruthy();
    const rgb = m![1].split(",").map((x) => parseFloat(x.trim()));
    // The point of this assertion is the ceiling, not the failure: it
    // documents WHY the splash hint had to change colour rather than alpha.
    expect(contrast(rgb, 1)).toBeLessThan(AA_BODY);
  });

  it("--pq-bronze at 0.80 does clear AA, which is what the splash uses now", () => {
    const m = CSS.match(/--pq-bronze-rgb:\s*([\d\s,]+);/);
    const rgb = m![1].split(",").map((x) => parseFloat(x.trim()));
    expect(contrast(rgb, 0.8)).toBeGreaterThanOrEqual(AA_BODY);
  });
});
