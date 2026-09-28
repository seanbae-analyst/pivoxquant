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
 *   2. every word containing a digit, cropped ×3 → digits-only re-read (`alt`);
 *      when its digits differ from pass 1, up to two more crops (tighter ×4,
 *      looser ×2) are read, and one that agrees with pass 1 becomes `alt`.
 *      Every other reading is kept in `alts` — a candidate only: the parsers
 *      use it where a printed total (원금, 매입금액, rate) proves one reading.
 *      A digit word with a wide empty gap before the next word on its line
 *      ("2        원" for "1,900,000원", the box cut short) is also read with
 *      the crop widened up to that next word.
 * `parse.ts` fills a number only when the two readings agree.
 */
import type { OcrWord } from "./parse";

const BASE = "/tesseract";
const PAGE_SCALE = 2;
const DIGIT_SCALE = 3;
const PAD = 4;
/** Re-crops tried when the first digit re-read disagrees: [pad, scale]. */
const RETRY_CROPS: [number, number][] = [[1, 4], [8, 2]];
const digitsOf = (s: string) => s.replace(/[^\d]/g, "");
export const MIN_SHORT_EDGE = 320;
export const MIN_LONG_EDGE = 480;
export const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
// iOS Safari refuses canvases above ~16.7M pixels (getContext → null). A
// long scroll capture ×2 exceeds that, so the page scale is clamped.
const MAX_CANVAS_PIXELS = 16_000_000;

export class OcrInputError extends Error {
  constructor(public code: "too_small" | "too_large" | "too_long" | "unreadable" | "timeout") {
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
  if (!ctx) throw new OcrInputError("too_long");
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
const READ_TIMEOUT_MS = 120_000;

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
    await page.setParameters({ preserve_interword_spaces: "1" });
    await digits.setParameters({
      tessedit_char_whitelist: "0123456789,.:/$",
      tessedit_pageseg_mode: PSM.SINGLE_LINE,
    });
  } catch (e) {
    abandoned = true;
    await Promise.allSettled(created.map((w) => w.terminate()));
    throw e;
  }
  let closed = false;
  const terminateAll = async () => {
    closed = true;
    await Promise.allSettled([page.terminate(), digits.terminate()]);
  };

  /** One capture, bounded: a recognise that never returns kills the workers
   * (the session is then unusable) instead of leaving "reading…" forever. */
  async function read(file: File, onStage?: (stage: "page" | "digits") => void): Promise<OcrWord[]> {
    if (closed) throw new OcrInputError("timeout");
    try {
      return await withTimeout(readInner(file, onStage), READ_TIMEOUT_MS);
    } catch (e) {
      if (e instanceof Error && e.message === "ocr_load_timeout") {
        await terminateAll();
        throw new OcrInputError("timeout");
      }
      throw e;
    }
  }

  async function readInner(file: File, onStage?: (stage: "page" | "digits") => void): Promise<OcrWord[]> {
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
      if (pageScale < 1) throw new OcrInputError("too_long"); // even 1:1 is over the canvas limit
      const big = scaledCanvas(bitmap, 0, 0, width, height, pageScale);
      const { data } = await page.recognize(big, {}, { blocks: true });
      const words: OcrWord[] = [];
      // The recognised line of each word, for the widened crop.
      const lineOf = new Map<OcrWord, OcrWord[]>();
      for (const b of data.blocks ?? [])
        for (const p of b.paragraphs)
          for (const l of p.lines) {
            const lineWords: OcrWord[] = [];
            for (const w of l.words) {
              const o: OcrWord = {
                t: w.text,
                c: Math.round(w.confidence),
                x0: Math.round(w.bbox.x0 / pageScale),
                y0: Math.round(w.bbox.y0 / pageScale),
                x1: Math.round(w.bbox.x1 / pageScale),
                y1: Math.round(w.bbox.y1 / pageScale),
              };
              words.push(o);
              lineWords.push(o);
              lineOf.set(o, lineWords);
            }
          }
      onStage?.("digits");
      const reread = async (w: OcrWord, pad: number, scale: number, right = w.x1 + pad, from = w.x0 - pad): Promise<string | null> => {
        const left = Math.max(0, from);
        const top = Math.max(0, w.y0 - pad);
        const cw = Math.min(width - left, right - left);
        const ch = Math.min(height - top, w.y1 - w.y0 + 2 * pad);
        if (cw < 4 || ch < 4) return null;
        const r = await digits.recognize(scaledCanvas(bitmap, left, top, cw, ch, scale));
        return r.data.text.trim();
      };
      for (const w of words) {
        if (!/\d/.test(w.t)) continue;
        const first = await reread(w, PAD, DIGIT_SCALE);
        if (first === null) continue;
        w.alt = first;
        const want = digitsOf(w.t);
        if (digitsOf(first) === want) continue;
        // A digit read against the unit glyph beside it ("2주" → "29") or a
        // dropped digit ("110" → "10"): another crop settles it only if it
        // agrees with the page reading — otherwise the disagreement stands,
        // and every reading is kept as a candidate.
        const alts = new Set<string>([first]);
        let settled = false;
        for (const [pad, scale] of RETRY_CROPS) {
          const again = await reread(w, pad, scale);
          if (again) alts.add(again);
          if (again !== null && digitsOf(again) === want) { w.alt = again; settled = true; break; }
        }
        // A lone digit ("2주") is often returned empty by the line mode.
        if (!settled && want.length === 1) {
          await digits.setParameters({ tessedit_pageseg_mode: PSM.SINGLE_CHAR });
          try {
            const again = await reread(w, 6, 4);
            if (again) alts.add(again);
            if (again !== null && digitsOf(again) === want) { w.alt = again; settled = true; }
          } finally {
            await digits.setParameters({ tessedit_pageseg_mode: PSM.SINGLE_LINE });
          }
        }
        // The box may be cut short ("1,900,000원" boxed as "2", "1,841,500" as
        // "841,500"): widen it across the non-digit words beside it — up to
        // the next word carrying digits on the right, and to the end of the
        // word before it on the left.
        if (!settled) {
          const ln = lineOf.get(w) ?? [w];
          const k = ln.indexOf(w);
          const nextDigit = ln.slice(k + 1).find((x) => /\d/.test(x.t));
          const right = nextDigit ? nextDigit.x0 - 1 : Math.min(width, (ln[ln.length - 1]?.x1 ?? w.x1) + PAD);
          const prev = ln[k - 1];
          const from = prev && !/\d/.test(prev.t) ? prev.x1 + 1 : w.x0 - PAD;
          if (right > w.x1 + PAD || from < w.x0 - PAD) {
            const wide = await reread(w, PAD, DIGIT_SCALE, right, from);
            if (wide) alts.add(wide);
          }
        }
        alts.delete(w.alt ?? "");
        const extra = [...alts].filter((a) => /\d/.test(a));
        if (extra.length) w.alts = extra;
      }
      return words;
    } finally {
      bitmap.close();
    }
  }

  return {
    read,
    async close() {
      if (!closed) await terminateAll();
    },
  };
}
