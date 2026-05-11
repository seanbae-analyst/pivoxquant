/**
 * W7.1 Regression guard — TopNav singleton mega-dropdown.
 * ----------------------------------------------------------------------
 * E2E user-tester P1 #16-19: rapid hover Living CFO → Personas →
 * Signature → Pricing → Docs left ghost trail of faded previous dropdown
 * content. Root cause: outer AnimatePresence wrapper was keyed by
 * activeGroup.key, so every hover transition triggered a full
 * exit+enter cycle. Switching to a SINGLE keyed wrapper +
 * inner AnimatePresence content swap eliminates the trail.
 *
 * Additional fix: Pricing dropdown allowed hero "investor language" text
 * to bleed through backdrop blur. Solid backstop layer at #060606 +
 * background opacity bumped 0.94 → 0.985 prevents this.
 *
 * This test is SOURCE-LEVEL (string assertions on the TopNav file)
 * because the visual ghosting is a Framer Motion timing concern that
 * cannot be reliably reproduced under JSDOM. The invariants we lock in
 * are structural — if someone re-introduces the per-group key on the
 * OUTER panel, this test fails and the ghost regresses.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const TOP_NAV_PATH = join(
  __dirname,
  "..",
  "components",
  "landing",
  "top-nav.tsx"
);

describe("TopNav mega-dropdown singleton (W7.1 #16-19)", () => {
  const source = readFileSync(TOP_NAV_PATH, "utf-8");

  it("outer mega-panel uses a STATIC key (singleton, not per-group)", () => {
    expect(source).toContain('key="nav-mega-panel"');
    const innerKeyMatches =
      source.match(/(?<!-)key=\{activeGroup\.key\}/g) ?? [];
    expect(innerKeyMatches.length).toBeLessThanOrEqual(1);
  });

  it("uses a nested AnimatePresence for inner content crossfade", () => {
    const matches = source.match(/<AnimatePresence/g) ?? [];
    expect(matches.length).toBeGreaterThanOrEqual(2);
    expect(source).toContain('initial={false}');
  });

  it("declares contentVariants with sub-200ms timing for fast crossfade", () => {
    expect(source).toContain("contentVariants");
    expect(source).toMatch(/exit:\s*\{[\s\S]*?duration:\s*0\.0?8/);
  });

  it("panel background is opaque enough to prevent hero text bleed-through", () => {
    expect(source).toContain("rgba(6,6,6,0.985)");
    expect(source).not.toContain("rgba(6,6,6,0.94)");
    expect(source).toMatch(/backgroundColor:\s*["'][^"']*#060606/);
  });

  it("hover transitions are guarded by a single activeKey enum (no parallel state)", () => {
    const useStateActiveKey = source.match(
      /useState<string \| null>\(null\)/g
    );
    expect(useStateActiveKey).not.toBeNull();
    expect(source).not.toMatch(/setLivingCfoOpen|setPricingOpen|setPersonasOpen/);
  });

  it("each nav button writes to the SAME activeKey state (no per-button local state)", () => {
    expect(source).toContain("openGroup(group.key)");
    const mapBodyMatches = source.match(
      /NAV_GROUPS\.map\(\(group\)\s*=>\s*\{[\s\S]*?return/
    );
    expect(mapBodyMatches).not.toBeNull();
    if (mapBodyMatches) {
      expect(mapBodyMatches[0]).not.toContain("useState");
    }
  });
});
