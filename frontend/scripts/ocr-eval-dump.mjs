/**
 * Regenerate the OCR dumps the fill-screen parser eval runs on
 * (src/lib/fill-ocr/__tests__/eval.test.ts) — with the PRODUCTION code path.
 *
 * Bundles src/lib/fill-ocr/ocr.ts (+ tesseract.js) with Vite, loads it into
 * headless Chromium via Playwright, serves public/tesseract/ at the same
 * path the app uses, and runs openOcrSession().read() on every image. The
 * words therefore come from the same canvas preprocessing, worker, core and
 * language data a user's browser runs — not an approximation.
 *
 *   npm run predev   # copies public/tesseract/ assets first
 *   node scripts/ocr-eval-dump.mjs <images dir> <out dir>
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";
import { chromium, webkit } from "playwright";

const [inDir, outDir] = process.argv.slice(2);
if (!inDir || !outDir) {
  console.error("usage: node scripts/ocr-eval-dump.mjs <images dir> <out dir>");
  process.exit(2);
}
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const assets = path.join(root, "public", "tesseract");
if (!fs.existsSync(path.join(assets, "worker.min.js"))) {
  console.error("public/tesseract/ is missing — run `node scripts/copy-tesseract-assets.mjs` first");
  process.exit(2);
}

// 1. Bundle the production OCR module into one IIFE exposing window.PQOcr.
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "pq-ocr-"));
await build({
  root,
  logLevel: "warn",
  configFile: false,
  resolve: { alias: { "@": path.join(root, "src") } },
  build: {
    outDir: tmp,
    emptyOutDir: true,
    lib: { entry: path.join(root, "src/lib/fill-ocr/ocr.ts"), name: "PQOcr", formats: ["iife"], fileName: () => "ocr.js" },
    minify: false,
  },
});
const bundle = fs.readFileSync(path.join(tmp, "ocr.js"), "utf8");

// 2. Serve it + the assets + the images from a fake origin.
const ORIGIN = "http://ocr-eval.test";
// OCR_BROWSER=webkit runs the same OCR in Safari's engine (iOS users) — its
// canvas scaling differs from Chromium's and so can the words.
const browser = await (process.env.OCR_BROWSER === "webkit" ? webkit : chromium).launch();
const page = await browser.newPage();
await page.route(`${ORIGIN}/**`, async (route) => {
  const url = new URL(route.request().url());
  if (url.pathname === "/") return route.fulfill({ contentType: "text/html", body: "<!doctype html><html><body></body></html>" });
  if (url.pathname === "/ocr.js") return route.fulfill({ contentType: "text/javascript", body: bundle });
  let file = null;
  if (url.pathname.startsWith("/tesseract/")) file = path.join(assets, url.pathname.slice("/tesseract/".length));
  if (url.pathname.startsWith("/img/")) file = path.join(inDir, decodeURIComponent(url.pathname.slice(5)));
  if (!file || !fs.existsSync(file)) return route.fulfill({ status: 404, body: "" });
  const type = file.endsWith(".js") ? "text/javascript" : file.endsWith(".wasm") ? "application/wasm" : "application/octet-stream";
  return route.fulfill({ contentType: type, body: fs.readFileSync(file) });
});
await page.goto(`${ORIGIN}/`);
// OCR_RESAMPLE=code measures the path Safari / iOS users get (in-code
// resampling); the default in headless Chromium is the native one.
if (process.env.OCR_RESAMPLE) await page.evaluate((m) => { globalThis.__OCR_RESAMPLE = m; }, process.env.OCR_RESAMPLE);
await page.addScriptTag({ url: `${ORIGIN}/ocr.js` });

fs.mkdirSync(outDir, { recursive: true });
const images = fs.readdirSync(inDir).filter((n) => /\.(png|jpe?g|webp)$/i.test(n)).sort();
await page.evaluate(async () => { window.__session = await window.PQOcr.openOcrSession(); });
for (const name of images) {
  const t0 = Date.now();
  // Rejected inputs (e.g. below the minimum resolution) are recorded as
  // {"error": code} — the app shows the same rejection to the user.
  const out = await page.evaluate(async (n) => {
    const blob = await fetch(`/img/${encodeURIComponent(n)}`).then((r) => r.blob());
    try {
      return await window.__session.read(new File([blob], n, { type: blob.type || "image/png" }));
    } catch (e) {
      return { error: e && e.code ? e.code : String(e) };
    }
  }, name);
  fs.writeFileSync(path.join(outDir, `${name}.json`), JSON.stringify(out));
  console.log(name, `${Date.now() - t0}ms`, Array.isArray(out) ? `${out.length} words` : out.error);
}
await page.evaluate(async () => { await window.__session.close(); });
await browser.close();
fs.rmSync(tmp, { recursive: true, force: true });
