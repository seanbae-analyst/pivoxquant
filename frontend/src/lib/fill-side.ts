/**
 * Fill-side wire tokens for the import path (screenshot OCR review rows and
 * `pending_trades.action`).
 *
 * These are internal side values exchanged with the parser / backend — never
 * labels. Display goes through `sideLabelKo` ("진입" / "정리"). They live in a
 * .ts module so user-facing tsx carries no bare side literals (design guard
 * DS6, `.github/workflows/design-safety-guards.yml`). Values are unchanged.
 */

import type { Side } from "@/lib/fill-ocr/parse";

export const SIDE_BUY = "BUY" as const satisfies Side;
export const SIDE_SELL = "SELL" as const satisfies Side;
