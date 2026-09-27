/**
 * In-browser OCR for fill-screen screenshots (docs/product/SCREENSHOT_IMPORT_DESIGN.md).
 *
 * The image never leaves the device. Tesseract.js runs in a same-origin Web
 * Worker with its runtime self-hosted under /tesseract/ (copied from
 * node_modules by scripts/copy-tesseract-assets.mjs), so CSP needs only
 * `worker-src 'self'` + `'wasm-unsafe-eval'`.
 *
 * Two passes, matching the offline eval (scripts/ocr-eval-dump.mjs):
 *   1. whole image ×2, grayscale, contrast-stretched → kor+eng words + boxes
 *   2. every word containing a digit, cropped ×3 → digits-only re-read (`alt`)
 * `parse.ts` fills a number only when the two readings agree.
 */
import type { OcrWord } from "./parse";

const BASE = "/tesseract";
const PAGE_SCALE = 2;
const DIGIT_SCALE = 3;
const PAD = 4;
export const MIN_SHORT_EDGE = 320;
export const MIN_LONG_EDGE = 480;
export const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
// iOS Safari refuses canvases above ~16.7M pixels (getContext → null). A
// long scroll capture ×2 exceeds that, so the page scale is clamped.
const MAX_CANVAS_PIXELS = 16_000_000;

export class OcrInputError extends Error {
  constructor(public code: "too_small" | "too_large" | "unreadable") {
    super(code);
  }
}

type TesseractWorker = Awaited<ReturnType<typeof import("tesseract.js")["createWorker"]>>;

// Smallest module using a SIMD opcode (same probe as wasm-feature-detect).
const SIMD_PROBE = new Uint8Array([
  0, 97, 115, 109, 1, 0, 0, 0, 1, 5, 1, 96, 0, 1, 123, 3, 2, 1, 0, 10, 10, 1, 8, 0, 65, 0, 253, 15, 253, 98, 11,
]);

function corePath(): string {
  let simd = false;
  try {
    simd = WebAssembly.validate(SIMD_PROBE);
  } catch {
    simd = false;
  }
  // An explicit .js file (not a directory): the core then loads its .wasm
  // from the same folder instead of fetch(data:…), which CSP connect-src blocks.
  return `${BASE}/${simd ? "tesseract-core-simd-lstm.js" : "tesseract-core-lstm.js"}`;
}

function workerOptions() {
  return {
    workerPath: `${BASE}/worker.min.js`,
    corePath: corePath(),
    langPath: `${BASE}/lang`,
    workerBlobURL: false,
    gzip: true,
  };
}

/** Grayscale + min/max contrast stretch (sharp's `.grayscale().normalize()`). */
function toGrayStretched(ctx: CanvasRenderingContext2D, w: number, h: number) {
  const img = ctx.getImageData(0, 0, w, h);
  const d = img.data;
  let lo = 255, hi = 0;
  for (let i = 0; i < d.length; i += 4) {
    const y = Math.round(0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]);
    d[i] = y;
    if (y < lo) lo = y;
    if (y > hi) hi = y;
  }
  const span = Math.max(1, hi - lo);
  for (let i = 0; i < d.length; i += 4) {
    const v = Math.round(((d[i] - lo) * 255) / span);
    d[i] = d[i + 1] = d[i + 2] = v;
  }
  ctx.putImageData(img, 0, 0);
}

function scaledCanvas(src: CanvasImageSource, sx: number, sy: number, sw: number, sh: number, scale: number) {
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(sw * scale));
  c.height = Math.max(1, Math.round(sh * scale));
  const ctx = c.getContext("2d", { willReadFrequently: true });
  if (!ctx) throw new OcrInputError("too_large");
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(src, sx, sy, sw, sh, 0, 0, c.width, c.height);
  toGrayStretched(ctx, c.width, c.height);
  return c;
}

export interface OcrSession {
  read(file: File, onStage?: (stage: "page" | "digits") => void): Promise<OcrWord[]>;
  close(): Promise<void>;
}

const LOAD_TIMEOUT_MS = 90_000;

/** Reject instead of hanging when the worker/core/language data cannot load
 * (a failed core load aborts inside the worker and never settles). */
function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("ocr_load_timeout")), ms);
    p.then(
      (v) => { clearTimeout(timer); resolve(v); },
      (e) => { clearTimeout(timer); reject(e); },
    );
  });
}

/** Load both workers once; reuse them for every capture in a batch. */
export async function openOcrSession(): Promise<OcrSession> {
  const { createWorker, PSM } = await import("tesseract.js");
  let loadError: unknown = null;
  let abandoned = false;
  // Every worker ever created is tracked so a timeout or a failed second
  // worker never leaves one running (a late-resolving createWorker after
  // the timeout is terminated as soon as it arrives).
  const created: TesseractWorker[] = [];
  const track = (p: Promise<TesseractWorker>) =>
    p.then((w) => {
      created.push(w);
      if (abandoned) void w.terminate();
      return w;
    });
  const opts = { ...workerOptions(), errorHandler: (e: unknown) => { loadError = e; } };
  const load = async () => {
    const p = await track(createWorker(["kor", "eng"], 1, opts));
    const d = await track(createWorker("eng", 1, opts));
    return [p, d] as const;
  };
  let page: TesseractWorker, digits: TesseractWorker;
  try {
    [page, digits] = await withTimeout(load(), LOAD_TIMEOUT_MS);
    if (loadError) throw loadError;
  } catch (e) {
    abandoned = true;
    await Promise.allSettled(created.map((w) => w.terminate()));
    throw e;
  }
  await page.setParameters({ preserve_interword_spaces: "1" });
  await digits.setParameters({
    tessedit_char_whitelist: "0123456789,.:/$",
    tessedit_pageseg_mode: PSM.SINGLE_LINE,
  });

  async function read(file: File, onStage?: (stage: "page" | "digits") => void): Promise<OcrWord[]> {
    if (file.size > MAX_IMAGE_BYTES) throw new OcrInputError("too_large");
    let bitmap: ImageBitmap;
    try {
      // EXIF orientation applied so a photographed screen reads upright.
      bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    } catch {
      throw new OcrInputError("unreadable");
    }
    const { width, height } = bitmap;
    if (Math.min(width, height) < MIN_SHORT_EDGE || Math.max(width, height) < MIN_LONG_EDGE) {
      bitmap.close();
      throw new OcrInputError("too_small");
    }
    try {
      onStage?.("page");
      const pageScale = Math.min(PAGE_SCALE, Math.sqrt(MAX_CANVAS_PIXELS / (width * height)));
      if (pageScale < 1) throw new OcrInputError("too_large"); // even 1:1 is over the canvas limit
      const big = scaledCanvas(bitmap, 0, 0, width, height, pageScale);
      const { data } = await page.recognize(big, {}, { blocks: true });
      const words: OcrWord[] = [];
      for (const b of data.blocks ?? [])
        for (const p of b.paragraphs)
          for (const l of p.lines)
            for (const w of l.words)
              words.push({
                t: w.text,
                c: Math.round(w.confidence),
                x0: Math.round(w.bbox.x0 / pageScale),
                y0: Math.round(w.bbox.y0 / pageScale),
                x1: Math.round(w.bbox.x1 / pageScale),
                y1: Math.round(w.bbox.y1 / pageScale),
              });
      onStage?.("digits");
      for (const w of words) {
        if (!/\d/.test(w.t)) continue;
        const left = Math.max(0, w.x0 - PAD);
        const top = Math.max(0, w.y0 - PAD);
        const cw = Math.min(width - left, w.x1 - w.x0 + 2 * PAD);
        const ch = Math.min(height - top, w.y1 - w.y0 + 2 * PAD);
        if (cw < 4 || ch < 4) continue;
        const crop = scaledCanvas(bitmap, left, top, cw, ch, DIGIT_SCALE);
        const r = await digits.recognize(crop);
        w.alt = r.data.text.trim();
      }
      return words;
    } finally {
      bitmap.close();
    }
  }

  return {
    read,
    async close() {
      await Promise.allSettled([page.terminate(), digits.terminate()]);
    },
  };
}
