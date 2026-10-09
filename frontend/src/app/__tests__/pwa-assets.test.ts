/**
 * Installed-app assets (2026-10-09): every file the manifest and the iOS
 * launch-image links point at exists, has the size it is declared at, and the
 * manifest copy stays on-product (no CFO / advice wording).
 */
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect } from "vitest";

import manifest from "@/app/manifest";
import { SPLASH_SCREENS, SPLASH_STARTUP_IMAGES, splashMedia } from "@/lib/pwa-splash";

const PUBLIC = join(process.cwd(), "public");

function pngSize(file: string): [number, number] {
  const buf = readFileSync(file);
  expect(buf.subarray(1, 4).toString("ascii")).toBe("PNG");
  return [buf.readUInt32BE(16), buf.readUInt32BE(20)];
}

describe("PWA manifest", () => {
  const m = manifest();

  it("every icon file exists at its declared size; maskable cuts are separate files", () => {
    for (const icon of m.icons ?? []) {
      const file = join(PUBLIC, icon.src);
      expect(existsSync(file), icon.src).toBe(true);
      if (icon.type === "image/png") {
        const [w, h] = pngSize(file);
        expect(`${w}x${h}`).toBe(icon.sizes);
      }
    }
    const maskable = (m.icons ?? []).filter((i) => i.purpose === "maskable");
    expect(maskable.map((i) => i.sizes).sort()).toEqual(["192x192", "512x512"]);
    for (const i of maskable) expect(i.src).toMatch(/icon-maskable-/);
  });

  it("shortcuts are 멈춤 → 기록 → 거울, each with its own existing icon", () => {
    const sc = m.shortcuts ?? [];
    expect(sc.map((s) => [s.short_name, s.url])).toEqual([
      ["멈춤", "/pre-trade"],
      ["기록", "/journal"],
      ["거울", "/mirror"],
    ]);
    const srcs = sc.flatMap((s) => (s.icons ?? []).map((i) => i.src));
    expect(new Set(srcs).size).toBe(srcs.length);
    for (const src of srcs) expect(existsSync(join(PUBLIC, src)), src).toBe(true);
  });

  it("copy names the product, keeps the disclaimer, no advice / CFO wording", () => {
    const copy = [m.name, m.short_name, m.description, ...(m.shortcuts ?? []).flatMap((s) => [s.name, s.description])].join(" ");
    expect(m.description).toContain("투자 권유가 아닙니다");
    expect(copy).not.toMatch(/CFO|결산|추천|조언|advice|recommend|\bBUY\b|\bSELL\b|\bHOLD\b/i);
    expect(m.id).toBe("/");
  });
});

describe("iOS launch images", () => {
  it("one PNG per device, at device pixels, linked with an exact portrait media query", () => {
    expect(SPLASH_STARTUP_IMAGES).toHaveLength(SPLASH_SCREENS.length);
    for (const s of SPLASH_SCREENS) {
      const [w, h] = pngSize(join(PUBLIC, "splash", s.file));
      expect([w, h]).toEqual([s.width * s.dpr, s.height * s.dpr]);
      expect(splashMedia(s)).toBe(
        `(device-width: ${s.width}px) and (device-height: ${s.height}px) and (-webkit-device-pixel-ratio: ${s.dpr}) and (orientation: portrait)`,
      );
    }
    for (const size of ["1170x2532", "1179x2556", "1284x2778", "1290x2796", "1125x2436", "828x1792", "750x1334", "1242x2688"]) {
      expect(SPLASH_SCREENS.some((s) => s.file === `splash-${size}.png`), size).toBe(true);
    }
  });
});
