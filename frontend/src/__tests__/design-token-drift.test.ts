/**
 * Shadow-color token drift guard — 2026-06-11 sweep (v64 아침 결정 ④).
 *
 * The v64 design audit's invisible-hairline class of bugs came from raw
 * color literals drifting on Vantablack surfaces. The Wave-1C RGB triplet
 * tokens (--pq-bronze-rgb / --pq-ivory-rgb / --pq-bronze-wash-rgb) existed
 * but shadows kept hardcoding the triplets. This guard pins the sweep:
 * shadow declarations must compose via rgba(var(--pq-*-rgb), α), never the
 * raw brand triplets, so a brand re-tint stays a one-line token change.
 *
 * Scope mirrors the sweep deliberately: SHADOW declarations only (box/text/
 * drop-shadow). Backgrounds and gradients still carry literals — widening
 * the guard is a separate design decision.
 * (frozen byte-for-byte as rollback insurance).
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(__dirname, "..");

const BRAND_TRIPLET =
  /rgba\(\s*(184\s*,\s*149\s*,\s*106|245\s*,\s*240\s*,\s*232|139\s*,\s*111\s*,\s*71)\s*,/;
const SHADOW_KEY = /box-shadow|text-shadow|drop-shadow|boxShadow|textShadow/i;

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (name === "node_modules") continue;
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(tsx|ts|css)$/.test(name) && !/\.(test|spec)\./.test(name)) out.push(p);
  }
  return out;
}

describe("shadow color token drift", () => {
  it("globals.css shadow declarations never hardcode brand triplets", () => {
    const css = readFileSync(join(SRC, "app", "globals.css"), "utf-8");
    // Declaration-unit scan — handles multi-line box-shadow lists.
    const violations = css
      .split(";")
      .filter((decl) => SHADOW_KEY.test(decl) && BRAND_TRIPLET.test(decl))
      .map((decl) => decl.trim().slice(0, 80));
    expect(violations).toEqual([]);
  });

  it("inline styles never hardcode brand triplets in shadow lines", () => {
    const violations: string[] = [];
    for (const file of walk(SRC)) {
      const lines = readFileSync(file, "utf-8").split("\n");
      lines.forEach((line, i) => {
        if (SHADOW_KEY.test(line) && BRAND_TRIPLET.test(line)) {
          violations.push(`${file.replace(SRC, "src")}:${i + 1}`);
        }
      });
    }
    expect(violations).toEqual([]);
  });

  it("the triplet tokens the sweep relies on stay defined", () => {
    const css = readFileSync(join(SRC, "app", "globals.css"), "utf-8");
    for (const token of [
      "--pq-bronze-rgb:",
      "--pq-ivory-rgb:",
      "--pq-bronze-wash-rgb:",
    ]) {
      expect(css).toContain(token);
    }
  });

  it("bronze-wash (#8B6F47) never reappears as a literal anywhere", () => {
    // 2026-06-11 follow-up sweep: ALL 105 rgba(139,111,71,*) literals were
    // tokenized (shadows AND washes/gradients/rings), so the pending design
    // decision — merge into canonical --pq-bronze or keep — is a ONE-LINE
    // token edit. A new literal would silently fork that decision again.
    const violations: string[] = [];
    const LIT = /rgba\(\s*139\s*,\s*111\s*,\s*71\s*,/;
    for (const file of walk(SRC)) {
      const lines = readFileSync(file, "utf-8").split("\n");
      lines.forEach((line, i) => {
        if (LIT.test(line)) {
          violations.push(`${file.replace(SRC, "src")}:${i + 1}`);
        }
      });
    }
    expect(violations).toEqual([]);
  });
});
