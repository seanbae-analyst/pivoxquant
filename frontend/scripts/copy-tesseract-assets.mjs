/**
 * Copy the Tesseract.js runtime into public/tesseract/ so the screenshot
 * import (src/lib/fill-ocr/ocr.ts) loads everything same-origin — no CDN,
 * no blob: worker. CSP stays `worker-src 'self'`; only `'wasm-unsafe-eval'`
 * was added to script-src (middleware.ts). public/tesseract/ is gitignored
 * and rebuilt on every `npm run dev` / `npm run build`.
 *
 * Language data is the 4.0.0_best_int model — the same one the offline
 * eval dumps were made with (scripts/ocr-eval-dump.mjs, Node default).
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const out = path.join(root, "public", "tesseract");
const pkgDir = (name) => path.dirname(require.resolve(`${name}/package.json`));

const copies = [
  [path.join(pkgDir("tesseract.js"), "dist", "worker.min.js"), path.join(out, "worker.min.js")],
  // The plain .js + separate .wasm builds, NOT the *.wasm.js ones: those embed
  // the wasm as a data: URI and first try fetch(data:…), which connect-src
  // blocks (console noise, then a slower fallback).
  ...[
    "tesseract-core-simd-lstm.js", "tesseract-core-simd-lstm.wasm",
    "tesseract-core-lstm.js", "tesseract-core-lstm.wasm",
  ].map((f) => [
    path.join(pkgDir("tesseract.js-core"), f),
    // Same folder as worker.min.js: the core resolves its .wasm relative to
    // the worker script, not to corePath.
    path.join(out, f),
  ]),
  ...["kor", "eng"].map((lang) => [
    path.join(pkgDir(`@tesseract.js-data/${lang}`), "4.0.0_best_int", `${lang}.traineddata.gz`),
    path.join(out, "lang", `${lang}.traineddata.gz`),
  ]),
];

for (const [src, dst] of copies) {
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  const same = fs.existsSync(dst) && fs.statSync(dst).size === fs.statSync(src).size;
  if (!same) fs.copyFileSync(src, dst);
}
console.log(`tesseract assets → ${path.relative(root, out)} (${copies.length} files)`);
