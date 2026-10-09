#!/usr/bin/env node
/**
 * Render the installed-app assets from their SVG sources.
 *
 *   node scripts/render-pwa-assets.mjs
 *
 * Sources (committed, edit these — never the PNGs):
 *   public/icons/icon.svg           purpose "any"  → icon-{72,96,144,192,512}x…png, apple-touch-icon.png
 *   public/icons/icon-maskable.svg  purpose "maskable" (mark inside the 80% safe zone)
 *                                                  → icon-maskable-{192,512}x…png
 *   public/icons/favicon.svg        small-size cut → favicon-48x48.png, src/app/favicon.ico (16/32/48)
 *   public/icons/shortcut-*.svg     manifest long-press shortcuts → shortcut-*-{96,192}…png
 *   public/splash/wordmark.svg      AppCover wordmark → public/splash/splash-*.png
 *   src/lib/pwa-splash-screens.json the iPhone list (layout.tsx links the same list)
 *
 * The glyphs are outlines baked into the SVGs, so this needs no font and no
 * network. Rasteriser: sharp (librsvg), which ships with Next.js.
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const pub = (...p) => join(ROOT, "public", ...p);
const INK = "#050505";

/** Opaque, palette-quantised PNG (iOS rejects transparent touch icons). */
async function rasterise(svg, size, out) {
  const buf = await sharp(Buffer.from(svg), { density: Math.max(72, (72 * size) / 512 * 2) })
    .resize(size, size)
    .flatten({ background: INK })
    .png({ compressionLevel: 9, palette: true, colours: 256, effort: 10 })
    .toBuffer();
  if (out) writeFileSync(out, buf);
  return buf;
}

/** ICO with PNG-encoded entries (supported by every browser since IE Vista). */
function ico(pngs) {
  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(pngs.length, 4);
  const dir = Buffer.alloc(16 * pngs.length);
  let offset = 6 + dir.length;
  pngs.forEach(({ size, buf }, i) => {
    const o = i * 16;
    dir.writeUInt8(size >= 256 ? 0 : size, o);
    dir.writeUInt8(size >= 256 ? 0 : size, o + 1);
    dir.writeUInt8(0, o + 2);
    dir.writeUInt8(0, o + 3);
    dir.writeUInt16LE(1, o + 4);
    dir.writeUInt16LE(32, o + 6);
    dir.writeUInt32LE(buf.length, o + 8);
    dir.writeUInt32LE(offset, o + 12);
    offset += buf.length;
  });
  return Buffer.concat([header, dir, ...pngs.map((p) => p.buf)]);
}

/**
 * One launch image: the AppCover picture at device pixels. AppCover sets the
 * wordmark at min(--pq-text-display, 10vw); on every phone width 10vw is the
 * smaller, so font-size = 0.1 × width. The 1em line box is centred on the
 * screen (flex items-center over 100dvh), and the veil is AppCover's
 * radial-gradient(ellipse 80% 80% at 50% 50%, …0.03 0%, …0.012 40%, transparent 75%).
 */
function splashSvg(W, H, word) {
  const vb = word.match(/viewBox="([^"]+)"/)[1].split(/\s+/).map(Number); // [0, -915, w, 1000]
  const inner = word.replace(/^[\s\S]*?<svg[^>]*>/, "").replace(/<\/svg>\s*$/, "").replace(/<!--[\s\S]*?-->/g, "");
  const fs = 0.1 * W;
  const s = fs / 1000;
  const lineW = vb[2] * s;
  const x = (W - lineW) / 2;
  const baseline = H / 2 - fs / 2 + -vb[1] * s;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
<defs><radialGradient id="veil" cx="0.5" cy="0.5" r="0.8">
<stop offset="0" stop-color="#F5F0E8" stop-opacity="0.03"/>
<stop offset="0.4" stop-color="#F5F0E8" stop-opacity="0.012"/>
<stop offset="0.75" stop-color="#F5F0E8" stop-opacity="0"/>
</radialGradient></defs>
<rect width="${W}" height="${H}" fill="${INK}"/>
<rect width="${W}" height="${H}" fill="url(#veil)"/>
<g transform="translate(${x.toFixed(2)} ${baseline.toFixed(2)}) scale(${s.toFixed(5)})">${inner}</g>
</svg>`;
}

async function main() {
  const any = readFileSync(pub("icons", "icon.svg"), "utf8");
  const maskable = readFileSync(pub("icons", "icon-maskable.svg"), "utf8");
  const favicon = readFileSync(pub("icons", "favicon.svg"), "utf8");

  for (const size of [72, 96, 144, 192, 512]) {
    await rasterise(any, size, pub("icons", `icon-${size}x${size}.png`));
  }
  await rasterise(any, 180, pub("icons", "apple-touch-icon.png"));
  for (const size of [192, 512]) {
    await rasterise(maskable, size, pub("icons", `icon-maskable-${size}x${size}.png`));
  }
  await rasterise(favicon, 48, pub("icons", "favicon-48x48.png"));
  const icoEntries = [];
  // ICO entries must be 32-bit RGBA PNGs — Next's favicon.ico pipeline (and
  // older Windows shells) reject palette PNGs ("The PNG is not in RGBA format").
  for (const size of [16, 32, 48]) {
    const buf = await sharp(Buffer.from(favicon), { density: 144 })
      .resize(size, size)
      .ensureAlpha()
      .png({ compressionLevel: 9, palette: false })
      .toBuffer();
    icoEntries.push({ size, buf });
  }
  writeFileSync(join(ROOT, "src", "app", "favicon.ico"), ico(icoEntries));
  for (const k of ["pause", "journal", "mirror"]) {
    const svg = readFileSync(pub("icons", `shortcut-${k}.svg`), "utf8");
    for (const size of [96, 192]) {
      await rasterise(svg, size, pub("icons", `shortcut-${k}-${size}x${size}.png`));
    }
  }

  const word = readFileSync(pub("splash", "wordmark.svg"), "utf8");
  const screens = JSON.parse(readFileSync(join(ROOT, "src", "lib", "pwa-splash-screens.json"), "utf8"));
  mkdirSync(pub("splash"), { recursive: true });
  for (const s of screens) {
    const W = s.width * s.dpr;
    const H = s.height * s.dpr;
    const buf = await sharp(Buffer.from(splashSvg(W, H, word)))
      .flatten({ background: INK })
      .png({ compressionLevel: 9, palette: true, colours: 64, effort: 10, dither: 0.6 })
      .toBuffer();
    writeFileSync(pub("splash", s.file), buf);
  }
  console.log(`rendered ${5 + 1 + 2 + 1 + 6} icons, favicon.ico, ${screens.length} launch images`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
