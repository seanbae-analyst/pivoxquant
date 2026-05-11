/**
 * Regression gate — Risk Board sample template must expose the
 * "7-Layer Risk Defense" matrix.
 *
 * W7.2 / E2E P1 #14 added a dedicated page mapping backend
 * `risk_defense.py` layers L1-L7 (VaR / Correlation / VIX / Tail /
 * Daily / Sector / Cash) to the sample-reports/risk-board template.
 * This is a key PivoxQuant differentiator (PR #199 hhi + 7-layer
 * threshold + observed_at_kst). If a future contributor strips the
 * 7-Layer section out of the template — for instance by accidentally
 * reverting page numbering or refactoring the PDF copy — this gate
 * fails and forces the surface to stay intact.
 *
 * The matrix is checked at the source level so the test is fast
 * (no JSX render) and stable across vitest workers.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const TEMPLATE_PATH = join(
  __dirname,
  "..",
  "components",
  "reports",
  "templates",
  "risk-board.tsx",
);

describe("Risk Board template — 7-Layer Risk Defense matrix (W7.2)", () => {
  const source = readFileSync(TEMPLATE_PATH, "utf-8");

  it("template surfaces the '7-Layer Risk Defense' heading", () => {
    // Allow either hyphenated "7-Layer" or spaced "7 Layer" forms.
    expect(source).toMatch(/7[- ]Layer Risk Defense/);
  });

  it("template references all 7 layer identifiers (L1-L7)", () => {
    for (const id of ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]) {
      expect(
        source.includes(`<strong>${id}</strong>`),
        `expected layer marker <strong>${id}</strong> in risk-board template`,
      ).toBe(true);
    }
  });

  it("template names each of the 7 defense layers", () => {
    // Mirrors backend `risk_defense.py` layer names (lines 8-14).
    const layerNames = [
      "VaR",
      "Correlation",
      "VIX",
      "Tail Risk",
      "Daily Loss",
      "Sector Concentration",
      "Cash Buffer",
    ];
    for (const name of layerNames) {
      expect(
        source.includes(name),
        `expected layer name "${name}" in risk-board template`,
      ).toBe(true);
    }
  });

  it("template advertises the matrix as a PivoxQuant differentiator", () => {
    expect(source).toMatch(/PivoxQuant 차별점/);
  });

  it("template links the matrix to the backend module name (provenance)", () => {
    expect(source).toMatch(/risk_defense\.py/);
  });

  it("template carries compliance language (관측·경보 시스템 / not advice)", () => {
    // No buy/sell/hold language — observation labels only.
    expect(source).toMatch(/관측[·•・]경보 시스템/);
    expect(source).not.toMatch(/\b(BUY|SELL|HOLD)\b/);
    expect(source).not.toMatch(/추천|조언|recommend|advice/i);
  });

  it("template uses 4-page numbering (01/04 — 04/04) after 7-Layer insertion", () => {
    for (const meta of ["01/04", "02/04", "03/04", "04/04"]) {
      expect(
        source.includes(meta),
        `expected page meta "${meta}" in risk-board template`,
      ).toBe(true);
    }
  });
});
