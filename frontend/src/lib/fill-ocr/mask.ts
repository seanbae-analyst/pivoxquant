/**
 * What may leave the device from a broker-screen OCR read — on the device,
 * before anything is sent.
 *
 * docs/product/AI_READ_EXPERIMENT_2026-10-07.md §2·§6. Lines, not characters:
 *   1. DROP identity lines — 계좌 · 위탁 · 고객 · …님 (account / customer headers)
 *   2. DROP lines nothing downstream needs — 예수금 · 주문가능 · 출금가능
 *   3. DROP any line holding something shaped like an account number (8+
 *      digits joined by hyphens, or 8+ in a row; OCR look-alikes O/o/l/I/|
 *      count as digits) or an account-type tag like [종합_주식]
 * Rule 3 drops the whole line, not just the digits: in real apps the holder's
 * name sits on the account line ("124-4567-8900-XX[종합_주식] 김미래"), and
 * masking only the number leaked it on 3 of 8 App Store screenshots.
 * The two rules overlap on purpose — OCR garbled "통합계좌" into "£57 =}" and
 * only the account number on that line removed it.
 *
 * Keywords are matched with spaces removed: OCR splits Hangul into syllables
 * ("주 문 가 능"). Money amounts (commas) and dates (2026-10-01, 20261001)
 * are never taken for an account number; a phone number is. The server masks
 * again (services/imports mask_sensitive).
 */
import { groupLines, type OcrWord } from "./parse";

const DROP_IDENTITY = /계좌|위탁|고객|님/;
const DROP_UNNEEDED = /예수금|주문가능|출금가능/;
const ACCOUNT_TAG = /\[[^\]]*(종합|위탁|주식|CMA|ISA|연금|비대면|저축)[^\]]*\]/;
const D = "[0-9OolI|]";
const ACCOUNT = new RegExp(`${D}{2,}(?:\\s?[-–]\\s?${D}{2,}){1,3}|${D}{8,}`, "g");
const digitsOf = (s: string) => s.replace(/[Oo]/g, "0").replace(/[lI|]/g, "1").replace(/\D/g, "");
// A date is not an account number — fills need it (the server's
// mask_sensitive keeps ISO / compact dates the same way).
const DATE = /^(19|20)\d{2}[-–]?(0[1-9]|1[0-2])[-–]?(0[1-9]|[12]\d|3[01])$/;
const accountLike = (m: string) => digitsOf(m).length >= 8 && !m.includes(",") && !DATE.test(m.replace(/\s/g, ""));

export type DropReason = "identity" | "unneeded" | "account";

/** Why a line must not leave the device, or null when it may. */
export function dropReason(line: string): DropReason | null {
  const squashed = line.replace(/\s+/g, "");
  if (DROP_IDENTITY.test(squashed)) return "identity";
  if (DROP_UNNEEDED.test(squashed)) return "unneeded";
  if (ACCOUNT_TAG.test(squashed)) return "account";
  return (line.match(ACCOUNT) ?? []).some(accountLike) ? "account" : null;
}

export interface MaskedScreen {
  /** The kept lines, top to bottom — the only text an AI reader would get. */
  text: string;
  dropped: Record<DropReason, number>;
}

/** A whole screen's OCR words → the text that may leave the device. */
export function maskScreen(words: OcrWord[]): MaskedScreen {
  const dropped: Record<DropReason, number> = { identity: 0, unneeded: 0, account: 0 };
  const kept: string[] = [];
  for (const { text } of groupLines(words)) {
    const why = dropReason(text);
    if (why) dropped[why]++;
    else kept.push(text);
  }
  return { text: kept.join("\n"), dropped };
}

/** A parser's `sourceText` ("line / line / …") with the lines that must not
 * leave the device removed. Sent as the import's source_text. */
export function maskSourceText(sourceText: string): string {
  return sourceText.split(" / ").filter((l) => dropReason(l) === null).join(" / ");
}
