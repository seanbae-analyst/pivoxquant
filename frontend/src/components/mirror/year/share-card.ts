/**
 * 올해의 기록 공유 이미지 — counts only, drawn on the device.
 *
 * The product's one organic sharing moment, so it carries the least that can
 * still mean something: the year and a few counts. NO tickers, NO amounts,
 * NO prices, NO quotes — a quote names a stock and the user's reasoning, and
 * neither belongs on an image that leaves the app. `shareCardLines` is the
 * only source of the image's text and is pure, so a test pins exactly that.
 *
 * Nothing is uploaded: the PNG is drawn into a canvas here and handed to the
 * Web Share API (with files) or downloaded. The legal line comes from the
 * backend (`share_disclaimer`, SoT services/legal/disclaimers.py) — the card
 * is not drawn without it.
 *
 * Colours are read from the design tokens at draw time (canvas cannot take a
 * CSS variable); the fallbacks only apply when the stylesheet is absent.
 */
import type { YearRecapResponse } from "@/lib/types";

export const SHARE_WIDTH = 1080;
export const SHARE_HEIGHT = 1350;
const PAD = 96;
const WORDMARK = "PivoxQuant";
const WORDMARK_HEAD = "Pivox";
/** Some browsers start the download after the click handler returns. */
const REVOKE_AFTER_MS = 1000;

export interface ShareCardText {
  title: string;
  lines: string[];
  wordmark: string;
  disclaimer: string;
}

/** The counts lines, zero lines dropped. Pure — nothing here can name a stock. */
export function shareCardLines(data: YearRecapResponse): ShareCardText {
  const { pauses, records, fills } = data;
  const lines: string[] = [];
  if (pauses.started > 0) lines.push(`거래 전에 멈춘 ${pauses.started}번`);
  if (pauses.never_bought > 0) lines.push(`그중 사려다 멈추고 끝내 사지 않은 ${pauses.never_bought}번`);
  if (records.reasoned_fills > 0) lines.push(`이유를 적은 체결 ${records.reasoned_fills}건`);
  if (records.research_written > 0) lines.push(`직접 쓴 리서치 ${records.research_written}편`);
  if (lines.length === 0 && fills.total > 0) lines.push(`기록한 체결 ${fills.total}건`);
  return {
    title: `${data.year}년, 내 기록`,
    lines,
    wordmark: WORDMARK,
    disclaimer: data.share_disclaimer,
  };
}

/** Whether there is anything worth an image (and a legal line to print on it). */
export function canShareCard(data: YearRecapResponse): boolean {
  return !data.empty && Boolean(data.share_disclaimer) && shareCardLines(data).lines.length > 0;
}

function token(name: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v ? `rgb(${v})` : fallback;
}

function fontStack(): string {
  if (typeof document === "undefined") return "sans-serif";
  return getComputedStyle(document.body).fontFamily || "sans-serif";
}

/** Break `text` into lines that fit `maxWidth` at the context's current font. */
function wrap(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const words = text.split(" ");
  const out: string[] = [];
  let line = "";
  for (const w of words) {
    const next = line ? `${line} ${w}` : w;
    if (line && ctx.measureText(next).width > maxWidth) {
      out.push(line);
      line = w;
    } else {
      line = next;
    }
  }
  if (line) out.push(line);
  return out;
}

/** Draw the card. Returns false when the canvas has no 2D context (e.g. jsdom). */
export function drawShareCard(canvas: HTMLCanvasElement, text: ShareCardText): boolean {
  const ctx = canvas.getContext("2d");
  if (!ctx) return false;
  canvas.width = SHARE_WIDTH;
  canvas.height = SHARE_HEIGHT;
  const ink = token("--pq-ink-rgb", "rgb(5, 5, 5)");
  const ivory = token("--pq-ivory-rgb", "rgb(245, 240, 232)");
  const bronze = token("--pq-bronze-rgb", "rgb(184, 149, 106)");
  const font = fontStack();

  ctx.fillStyle = ink;
  ctx.fillRect(0, 0, SHARE_WIDTH, SHARE_HEIGHT);
  ctx.textBaseline = "top";

  ctx.fillStyle = bronze;
  ctx.font = `600 64px ${font}`;
  ctx.fillText(text.title, PAD, PAD + 40);

  let y = PAD + 220;
  ctx.fillStyle = ivory;
  ctx.font = `600 58px ${font}`;
  for (const line of text.lines) {
    for (const part of wrap(ctx, line, SHARE_WIDTH - PAD * 2)) {
      ctx.fillText(part, PAD, y);
      y += 84;
    }
    y += 28;
  }

  // The site logo: "Pivox" Ivory + "Quant" Bronze (components/ui/quant-mark.tsx).
  const markY = SHARE_HEIGHT - PAD - 150;
  const head = text.wordmark.slice(0, WORDMARK_HEAD.length);
  ctx.font = `700 44px ${font}`;
  ctx.fillStyle = ivory;
  ctx.fillText(head, PAD, markY);
  ctx.fillStyle = bronze;
  ctx.fillText(text.wordmark.slice(head.length), PAD + ctx.measureText(head).width, markY);

  ctx.globalAlpha = 0.55;
  ctx.fillStyle = ivory;
  ctx.font = `400 26px ${font}`;
  let dy = SHARE_HEIGHT - PAD - 70;
  // KR / EN halves on their own lines — wrapping the joined string left a
  // lone "advice." on the last line.
  for (const half of text.disclaimer.split(" / ")) {
    for (const part of wrap(ctx, half, SHARE_WIDTH - PAD * 2)) {
      ctx.fillText(part, PAD, dy);
      dy += 36;
    }
  }
  ctx.globalAlpha = 1;
  return true;
}

function toBlob(canvas: HTMLCanvasElement): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob((b) => resolve(b), "image/png"));
}

export type ShareResult = "shared" | "downloaded" | "cancelled" | "failed";

/**
 * Draw the card and hand it to the OS share sheet, or download it when the
 * browser cannot share files. Nothing leaves the device unless the user
 * picks a target in their own share sheet.
 */
export async function shareYearCard(data: YearRecapResponse): Promise<ShareResult> {
  if (!canShareCard(data)) return "failed";
  const canvas = document.createElement("canvas");
  if (!drawShareCard(canvas, shareCardLines(data))) return "failed";
  const blob = await toBlob(canvas);
  if (!blob) return "failed";
  const name = `pivoxquant-${data.year}.png`;
  const file = new File([blob], name, { type: "image/png" });
  if (typeof navigator.canShare === "function" && navigator.canShare({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: `${data.year}년, 내 기록` });
      return "shared";
    } catch (err) {
      // The user closing the sheet is not a failure.
      return err instanceof DOMException && err.name === "AbortError" ? "cancelled" : "failed";
    }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), REVOKE_AFTER_MS);
  return "downloaded";
}
